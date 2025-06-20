from django.utils import timezone
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse
from django.conf import settings
from django_tenants.utils import get_tenant_model, get_public_schema_name
from django_tenants.middleware.main import TenantMainMiddleware
from django.db import connection
from django.http import Http404
from django.apps import apps
import pytz

class SimpleSessionFixMiddleware:
    """
    Improved middleware to ensure session persistence across tenant switches.
    Must be placed BEFORE PathBasedTenantMiddleware.
    """
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Store original session key and data before processing
        original_session_key = None
        original_session_data = {}
        
        if hasattr(request, 'session') and request.session:
            try:
                original_session_key = request.session.session_key
                # Only copy if session has data
                if request.session.keys():
                    original_session_data = dict(request.session)
                # Reduced logging for production
                if settings.DEBUG:
                    print(f"Preserved session key: {original_session_key}")
                    print(f"Preserved session data: {original_session_data}")
            except Exception as e:
                if settings.DEBUG:
                    print(f"Error preserving session: {e}")
        
        # Process the request
        response = self.get_response(request)
        
        # Only save session if it was modified or if we need to restore data
        try:
            if hasattr(request, 'session') and request.session:
                # Check if session was lost during processing
                current_session_key = request.session.session_key
                current_data = dict(request.session) if request.session.keys() else {}
                
                # If session key changed or data was lost, restore it
                if (original_session_key and 
                    (not current_session_key or current_session_key != original_session_key or
                     (original_session_data and not current_data))):
                    
                    if settings.DEBUG:
                        print("Session appears to have been lost, restoring...")
                    
                    # Restore the original session data
                    for key, value in original_session_data.items():
                        request.session[key] = value
                    
                    # Force save only if we restored data
                    if original_session_data:
                        request.session.save()
                        if settings.DEBUG:
                            print("Session restored and saved")
                
                # Only save if session is modified and not already saved
                elif request.session.modified and not getattr(request.session, '_saved', False):
                    request.session.save()
                    request.session._saved = True
                    if settings.DEBUG:
                        print("Session saved normally")
                    
        except Exception as e:
            if settings.DEBUG:
                print(f"Error handling session in middleware: {e}")
            # Don't let session errors break the response
            pass
        
        return response

class PathBasedTenantMiddleware(TenantMainMiddleware):
    """
    Custom middleware to handle path-based tenant routing instead of subdomain.
    URLs like: /business/slug/ instead of slug.domain.com
    """
    
    def process_request(self, request):
        """
        Override process_request to handle path-based routing
        """
        if settings.DEBUG:
            print(f"\n" + "="*30 + " TENANT MIDDLEWARE " + "="*30)
            print(f"Processing request: {request.path}")
            print(f"Method: {request.method}")
        
        # CRITICAL FIX: Store session data before tenant switching
        session_data = {}
        if hasattr(request, 'session') and request.session:
            try:
                # Copy session data before potential loss
                session_data = dict(request.session)
                session_key = request.session.session_key
                if settings.DEBUG:
                    print(f"Preserved session data: {session_data}")
                    print(f"Session key: {session_key}")
            except Exception as e:
                if settings.DEBUG:
                    print(f"Error preserving session: {e}")
        
        # Store session info for debugging
        if hasattr(request, 'session') and request.session.session_key and settings.DEBUG:
            print(f"Session key exists: {request.session.session_key}")
            if '_auth_user_id' in request.session:
                print(f"User ID in session: {request.session['_auth_user_id']}")
        
        # Get the hostname
        hostname = self.hostname_from_request(request)
        if settings.DEBUG:
            print(f"Hostname: {hostname}")
        
        # Get the domain model from settings or use default
        domain_model = apps.get_model(settings.TENANT_DOMAIN_MODEL)
        
        # Check if this is a business path
        path = request.path_info
        tenant_domain = None
        
        if settings.DEBUG:
            print(f"Path info: {path}")
        
        # Store the original path for later use
        request.original_path = path
        
        # If path starts with /business/, extract tenant slug
        if path.startswith('/business/'):
            path_parts = path.strip('/').split('/')
            if settings.DEBUG:
                print(f"Path parts: {path_parts}")
            
            if len(path_parts) >= 2:
                business_slug = path_parts[1]
                if settings.DEBUG:
                    print(f"Business slug extracted: {business_slug}")
                
                try:
                    # Get the tenant model and find by slug
                    tenant_model = get_tenant_model()
                    tenant = tenant_model.objects.get(slug=business_slug, is_active=True)
                    if settings.DEBUG:
                        print(f"Tenant found: {tenant.name} (verified: {tenant.is_verified})")
                    
                    # Try to get existing domain first, then create if needed
                    domain_name = f'{business_slug}.path-based.local'
                    try:
                        tenant_domain = domain_model.objects.filter(tenant=tenant).first()
                        if not tenant_domain:
                            # No domain exists, create one
                            tenant_domain = domain_model.objects.create(
                                domain=domain_name,
                                tenant=tenant,
                                is_primary=True
                            )
                            if settings.DEBUG:
                                print(f"Created new domain: {domain_name}")
                        else:
                            if settings.DEBUG:
                                print(f"Using existing domain: {tenant_domain.domain}")
                    except Exception as e:
                        if settings.DEBUG:
                            print(f"Domain creation error: {e}")
                        # If there's any issue, just get the first available domain
                        tenant_domain = domain_model.objects.filter(tenant=tenant).first()
                    
                    # CRITICAL FIX: Update request path to remove business prefix for URL resolution
                    # Ensure we have a leading slash for the remaining path
                    if len(path_parts) > 2:
                        remaining_path = '/' + '/'.join(path_parts[2:])
                        if not remaining_path.endswith('/') and '.' not in remaining_path.split('/')[-1]:
                            remaining_path += '/'
                    else:
                        remaining_path = '/'
                    
                    # Store business info on request
                    request.path_info = remaining_path
                    request.path = remaining_path  # Also update request.path
                    request.business_slug_from_path = business_slug
                    request.tenant_business = tenant  # Store tenant reference
                    if settings.DEBUG:
                        print(f"Updated path_info to: {remaining_path}")
                        print(f"Updated path to: {remaining_path}")
                        print(f"Stored business slug: {business_slug}")
                    
                except tenant_model.DoesNotExist:
                    if settings.DEBUG:
                        print(f"Business not found: {business_slug}")
                    # Business not found, will fall back to public schema
                    pass
                except Exception as e:
                    if settings.DEBUG:
                        print(f"Error finding tenant: {e}")
                    pass
        
        # If no tenant domain found, use public schema
        if not tenant_domain:
            if settings.DEBUG:
                print("Using public schema")
            try:
                tenant_model = get_tenant_model()
                public_tenant = tenant_model.objects.get(schema_name=get_public_schema_name())
                
                # Try to get existing domain first, then create if needed
                try:
                    tenant_domain = domain_model.objects.filter(tenant=public_tenant).first()
                    if not tenant_domain:
                        # No domain exists, create one
                        tenant_domain = domain_model.objects.create(
                            domain=hostname,
                            tenant=public_tenant,
                            is_primary=True
                        )
                        if settings.DEBUG:
                            print(f"Created public domain: {hostname}")
                    else:
                        if settings.DEBUG:
                            print(f"Using existing public domain: {tenant_domain.domain}")
                except Exception as e:
                    if settings.DEBUG:
                        print(f"Public domain error: {e}")
                    # If there's any issue, just get the first available domain
                    tenant_domain = domain_model.objects.filter(tenant=public_tenant).first()
                    if not tenant_domain:
                        # Last resort: create a new domain
                        tenant_domain = domain_model.objects.create(
                            domain=f'fallback-{hostname}',
                            tenant=public_tenant,
                            is_primary=False
                        )
                
            except tenant_model.DoesNotExist:
                # This shouldn't happen in normal operation
                raise Http404("Public tenant not found")
        
        # Set the tenant on the request
        request.tenant = tenant_domain.tenant
        
        # CRITICAL FIX: Store session data on request before schema switch
        request._preserved_session_data = session_data
        
        # Switch database connection to the correct schema
        connection.set_tenant(request.tenant)
        
        if settings.DEBUG:
            print(f"Selected tenant: {request.tenant.schema_name}")
        
        # CRITICAL FIX: Restore session data after schema switch if lost
        if session_data and hasattr(request, 'session'):
            try:
                # Check if session was lost
                if not request.session or not request.session.keys():
                    if settings.DEBUG:
                        print("Session was lost, attempting to restore...")
                    for key, value in session_data.items():
                        request.session[key] = value
                    request.session.save()  # Force save
                    if settings.DEBUG:
                        print(f"Restored session data: {dict(request.session)}")
                else:
                    if settings.DEBUG:
                        print("Session preserved successfully")
            except Exception as e:
                if settings.DEBUG:
                    print(f"Error restoring session: {e}")
        
        # Set up URL routing based on tenant type
        if hasattr(request.tenant, 'schema_name'):
            if request.tenant.schema_name == get_public_schema_name():
                # Public schema - use public URLs
                request.urlconf = getattr(settings, 'PUBLIC_SCHEMA_URLCONF', 'autowash.urls_public')
                if settings.DEBUG:
                    print(f"Using public URL conf")
            else:
                # Tenant schema - use tenant URLs  
                request.urlconf = getattr(settings, 'ROOT_URLCONF', 'autowash.urls')
                if settings.DEBUG:
                    print(f"Using tenant URL conf")
        
        if settings.DEBUG:
            print("="*76)

class SharedAuthenticationMiddleware:
    """
    Custom authentication middleware that works across tenant schemas.
    This ensures authentication persists when switching from public to tenant schemas.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if settings.DEBUG:
            print(f"\n" + "="*25 + " SHARED AUTH MIDDLEWARE " + "="*25)
            print(f"Processing request: {request.path}")
            print(f"Current schema: {connection.get_schema()}")
        
        # Debug session info
        if hasattr(request, 'session') and settings.DEBUG:
            print(f"Session exists: {bool(request.session)}")
            print(f"Session key: {getattr(request.session, 'session_key', 'None')}")
            print(f"Session items: {dict(request.session) if request.session else 'None'}")
            if request.session and '_auth_user_id' in request.session:
                print(f"Auth user ID in session: {request.session['_auth_user_id']}")
        
        # Check for preserved session data
        if hasattr(request, '_preserved_session_data') and request._preserved_session_data:
            if settings.DEBUG:
                print(f"Found preserved session data: {request._preserved_session_data}")
            
            # If current session is empty but we have preserved data, restore it
            if not request.session or not request.session.keys():
                if settings.DEBUG:
                    print("Restoring session from preserved data...")
                try:
                    for key, value in request._preserved_session_data.items():
                        request.session[key] = value
                    request.session.save()  # Force save
                    if settings.DEBUG:
                        print(f"Session restored: {dict(request.session)}")
                except Exception as e:
                    if settings.DEBUG:
                        print(f"Error restoring session: {e}")
        
        # Only apply to tenant schemas (not public)
        if (hasattr(request, 'tenant') and request.tenant and 
            request.tenant.schema_name != get_public_schema_name()):
            
            if settings.DEBUG:
                print(f"In tenant schema: {request.tenant.schema_name}")
            
            # CRITICAL FIX: Check session more thoroughly
            user_id = None
            if hasattr(request, 'session') and request.session:
                # Try multiple ways to get the user ID
                user_id = request.session.get('_auth_user_id')
                if not user_id:
                    # Alternative session key patterns
                    for key in request.session.keys():
                        if 'auth' in key.lower() and 'user' in key.lower():
                            if settings.DEBUG:
                                print(f"Found alternative auth key: {key} = {request.session[key]}")
                            user_id = request.session[key]
                            break
                
                # Also check preserved session data
                if not user_id and hasattr(request, '_preserved_session_data'):
                    user_id = request._preserved_session_data.get('_auth_user_id')
                    if settings.DEBUG:
                        print(f"Found user ID in preserved data: {user_id}")
            
            if user_id:
                if settings.DEBUG:
                    print(f"Found user ID: {user_id}")
                
                # If user is not already authenticated in this schema, authenticate them
                if not hasattr(request, 'user') or isinstance(request.user, AnonymousUser):
                    if settings.DEBUG:
                        print(f"User not authenticated in tenant schema, authenticating...")
                    
                    try:
                        # Switch to public schema to get user
                        from django_tenants.utils import schema_context
                        with schema_context(get_public_schema_name()):
                            User = get_user_model()
                            user = User.objects.get(pk=user_id)
                            if settings.DEBUG:
                                print(f"Found user in public schema: {user.username}")
                            
                            # Set the user on the request
                            request.user = user
                            if settings.DEBUG:
                                print(f"User authenticated in tenant schema: {user.username}")
                            
                            # Ensure session is properly restored
                            if hasattr(request, 'session'):
                                request.session['_auth_user_id'] = str(user_id)
                                request.session.save()
                            
                    except Exception as e:
                        if settings.DEBUG:
                            print(f"Error authenticating user in tenant schema: {e}")
                        request.user = AnonymousUser()
                else:
                    if settings.DEBUG:
                        print(f"User already authenticated: {request.user.username}")
            else:
                if settings.DEBUG:
                    print(f"No authentication session data found")
                
                # CRITICAL FIX: Check if we have a user object from Django's auth middleware
                if hasattr(request, 'user') and request.user.is_authenticated:
                    if settings.DEBUG:
                        print(f"User already authenticated by Django middleware: {request.user.username}")
                    # User is already authenticated, no need to do anything
                else:
                    if settings.DEBUG:
                        print(f"Setting AnonymousUser")
                    request.user = AnonymousUser()
        else:
            if settings.DEBUG:
                print(f"In public schema or no tenant")
        
        if settings.DEBUG:
            print("="*72)
        response = self.get_response(request)
        return response

class BusinessContextMiddleware:
    """Middleware to add business context to requests with path-based routing"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if settings.DEBUG:
            print(f"\n" + "="*25 + " BUSINESS CONTEXT MIDDLEWARE " + "="*25)
            print(f"Processing request: {request.path}")
            print(f"User authenticated: {hasattr(request, 'user') and request.user.is_authenticated}")
            print(f"User: {getattr(request, 'user', 'No user attr yet')}")
        
        # Check if tenant attribute exists (added by path-based tenant middleware)
        if hasattr(request, 'tenant') and request.tenant:
            # Add business context for tenant schemas
            if request.tenant.schema_name != get_public_schema_name():
                request.business = request.tenant
                if settings.DEBUG:
                    print(f"Business context set: {request.business.name}")
                
                # Get business slug from stored attribute
                if hasattr(request, 'business_slug_from_path'):
                    request.business_slug = request.business_slug_from_path
                    if settings.DEBUG:
                        print(f"Business slug set: {request.business_slug}")
                
                # IMPORTANT: Check if business is verified for tenant access
                # Only enforce verification checks for authenticated users
                if not request.business.is_verified:
                    if settings.DEBUG:
                        print(f"Business not verified")
                    
                    # Allow access during authentication process (before user is set)
                    if not hasattr(request, 'user'):
                        if settings.DEBUG:
                            print(f"No user attribute yet, allowing request to continue")
                    elif not request.user.is_authenticated:
                        if settings.DEBUG:
                            print(f"User not authenticated yet, allowing request to continue")
                    elif request.user.is_superuser:
                        if settings.DEBUG:
                            print(f"Superuser detected, allowing access")
                    else:
                        # Check if user is the business owner
                        if hasattr(request.user, 'owned_businesses'):
                            user_business = request.user.owned_businesses.filter(id=request.business.id).first()
                            if user_business:
                                if settings.DEBUG:
                                    print(f"User is business owner, checking allowed paths")
                                
                                # Only allow access to logout and verification endpoints
                                allowed_paths = [
                                    '/logout/',
                                    '/verification-pending/',
                                    '/business/verification/',
                                    '/admin/',
                                    '/static/',
                                    '/media/',
                                    '/debug/',  # Allow debug paths
                                ]
                                
                                current_path = request.path_info
                                path_allowed = any(current_path.startswith(path) for path in allowed_paths)
                                if settings.DEBUG:
                                    print(f"Current path: {current_path}")
                                    print(f"Path allowed: {path_allowed}")
                                
                                if not path_allowed:
                                    # Redirect unverified business users to verification pending
                                    if settings.DEBUG:
                                        print(f"Redirecting business owner to verification pending")
                                    messages.warning(request, 'Business verification is required to access this area.')
                                    return redirect('/auth/verification-pending/')
                            else:
                                if settings.DEBUG:
                                    print(f"User is not business owner, denying access")
                                messages.error(request, 'You do not have access to this business.')
                                return redirect('/public/')
                        
            else:
                request.business = None
                request.business_slug = None
                if settings.DEBUG:
                    print(f"Public schema - no business context")
        else:
            # If no tenant attribute, we're probably on public schema
            request.business = None
            request.business_slug = None
            if settings.DEBUG:
                print(f"No tenant - no business context")
        
        if settings.DEBUG:
            print("="*78)
        response = self.get_response(request)
        return response

class TimezoneMiddleware:
    """Middleware to set timezone based on business settings"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Check if business exists and has timezone setting
        if hasattr(request, 'business') and request.business:
            # Get business timezone from settings or default to Africa/Nairobi
            business_timezone = getattr(request.business, 'timezone', 'Africa/Nairobi')
            try:
                timezone.activate(pytz.timezone(business_timezone))
            except pytz.UnknownTimeZoneError:
                # Fallback to default if timezone is invalid
                timezone.activate(pytz.timezone('Africa/Nairobi'))
        else:
            # Default timezone for public schema or when no business
            timezone.activate(pytz.timezone('Africa/Nairobi'))
        
        response = self.get_response(request)
        return response

class UserActivityMiddleware:
    """Middleware to track user activity - FIXED for cross-schema compatibility"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Update last activity for authenticated users
        if hasattr(request, 'user') and not isinstance(request.user, AnonymousUser):
            # Only try to update activity if we're in a tenant schema (not public)
            if hasattr(request, 'business') and request.business:
                try:
                    from apps.employees.models import Employee
                    # FIXED: Use user_id instead of user for cross-schema compatibility
                    employee = Employee.objects.get(user_id=request.user.id, is_active=True)
                    employee.last_activity = timezone.now()
                    employee.save(update_fields=['last_activity'])
                except Employee.DoesNotExist:
                    # User is not an employee, log for debugging
                    if settings.DEBUG:
                        print(f"DEBUG: User {request.user.username} (ID: {request.user.id}) has no employee record in business {request.business.name}")
                except Exception as e:
                    # Log error but don't break the request
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to update user activity: {e}")
        
        return response