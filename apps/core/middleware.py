from django.utils import timezone
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.contrib import messages
from django.conf import settings
from django_tenants.utils import get_tenant_model, get_public_schema_name
from django_tenants.middleware.main import TenantMainMiddleware
from django.db import connection
from django.http import Http404
from django.apps import apps
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.middleware import SessionMiddleware
import pytz

class TenantAwareSessionMiddleware:
    """
    Complete replacement for Django's SessionMiddleware that works with multi-tenant setup.
    Handles all session operations safely across tenant switches.
    """
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Initialize session from cookie
        session_key = request.COOKIES.get(settings.SESSION_COOKIE_NAME)
        request.session = SessionStore(session_key)
        
        # Store original session state
        original_session_data = {}
        if request.session.session_key and request.session.exists(request.session.session_key):
            try:
                # Load session data
                request.session.load()
                original_session_data = dict(request.session.items())
            except Exception:
                # If session is corrupted, create a new one
                request.session.create()
        
        # Mark as not modified initially
        request.session.modified = False
        request.session._tenant_safe = True  # Mark this as our safe session
        
        # Store backup for tenant switching
        request._session_backup = {
            'data': original_session_data,
            'key': request.session.session_key,
        }
        
        # Process request
        response = self.get_response(request)
        
        # Handle session saving safely
        self._safe_session_save(request, response)
        
        return response
    
    def _safe_session_save(self, request, response):
        """Safely save session without conflicts"""
        try:
            if not hasattr(request, 'session'):
                return
            
            # Only save if session was modified
            if request.session.modified:
                # Check if session key exists
                if not request.session.session_key:
                    request.session.create()
                
                # Try to save, but handle conflicts gracefully
                try:
                    request.session.save()
                except Exception:
                    # If save fails, create new session with same data
                    old_data = dict(request.session.items())
                    request.session.create()
                    request.session.update(old_data)
                    request.session.save()
                
                # Set session cookie
                if request.session.session_key:
                    response.set_cookie(
                        settings.SESSION_COOKIE_NAME,
                        request.session.session_key,
                        max_age=settings.SESSION_COOKIE_AGE,
                        expires=None,
                        domain=settings.SESSION_COOKIE_DOMAIN,
                        path=settings.SESSION_COOKIE_PATH,
                        secure=settings.SESSION_COOKIE_SECURE,
                        httponly=settings.SESSION_COOKIE_HTTPONLY,
                        samesite=settings.SESSION_COOKIE_SAMESITE,
                    )
                    
        except Exception:
            # Never let session errors break the response
            pass

class PathBasedTenantMiddleware(TenantMainMiddleware):
    """
    Enhanced path-based tenant middleware with bulletproof session handling.
    """
    
    def process_request(self, request):
        # Get session backup data
        session_backup = getattr(request, '_session_backup', {})
        session_data = session_backup.get('data', {})
        
        hostname = self.hostname_from_request(request)
        domain_model = apps.get_model(settings.TENANT_DOMAIN_MODEL)
        
        path = request.path_info
        tenant_domain = None
        
        request.original_path = path
        
        # Handle business path routing
        if path.startswith('/business/'):
            path_parts = path.strip('/').split('/')
            
            if len(path_parts) >= 2:
                business_slug = path_parts[1]
                
                try:
                    tenant_model = get_tenant_model()
                    tenant = tenant_model.objects.get(slug=business_slug, is_active=True)
                    
                    domain_name = f'{business_slug}.path-based.local'
                    try:
                        tenant_domain = domain_model.objects.filter(tenant=tenant).first()
                        if not tenant_domain:
                            tenant_domain = domain_model.objects.create(
                                domain=domain_name,
                                tenant=tenant,
                                is_primary=True
                            )
                    except Exception:
                        tenant_domain = domain_model.objects.filter(tenant=tenant).first()
                    
                    # Update request path
                    if len(path_parts) > 2:
                        remaining_path = '/' + '/'.join(path_parts[2:])
                        if not remaining_path.endswith('/') and '.' not in remaining_path.split('/')[-1]:
                            remaining_path += '/'
                    else:
                        remaining_path = '/'
                    
                    request.path_info = remaining_path
                    request.path = remaining_path
                    request.business_slug_from_path = business_slug
                    request.tenant_business = tenant
                    
                except tenant_model.DoesNotExist:
                    pass
                except Exception:
                    pass
        
        # Handle public tenant
        if not tenant_domain:
            try:
                tenant_model = get_tenant_model()
                public_tenant = tenant_model.objects.get(schema_name=get_public_schema_name())
                
                try:
                    tenant_domain = domain_model.objects.filter(tenant=public_tenant).first()
                    if not tenant_domain:
                        tenant_domain = domain_model.objects.create(
                            domain=hostname,
                            tenant=public_tenant,
                            is_primary=True
                        )
                except Exception:
                    tenant_domain = domain_model.objects.filter(tenant=public_tenant).first()
                    if not tenant_domain:
                        tenant_domain = domain_model.objects.create(
                            domain=f'fallback-{hostname}',
                            tenant=public_tenant,
                            is_primary=False
                        )
                
            except tenant_model.DoesNotExist:
                raise Http404("Public tenant not found")
        
        # Set tenant and switch schema
        request.tenant = tenant_domain.tenant
        connection.set_tenant(request.tenant)
        
        # CRITICAL: Restore session data after schema switch
        if session_data and hasattr(request, 'session'):
            try:
                # Clear current session and restore data
                request.session.clear()
                request.session.update(session_data)
                request.session.modified = True
                        
            except Exception:
                pass
        
        # Set URL configuration
        if hasattr(request.tenant, 'schema_name'):
            if request.tenant.schema_name == get_public_schema_name():
                request.urlconf = getattr(settings, 'PUBLIC_SCHEMA_URLCONF', 'autowash.urls_public')
            else:
                request.urlconf = getattr(settings, 'ROOT_URLCONF', 'autowash.urls')

class SharedAuthenticationMiddleware:
    """
    Enhanced authentication middleware that works across schemas without session conflicts.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Only handle tenant schemas
        if (hasattr(request, 'tenant') and request.tenant and 
            request.tenant.schema_name != get_public_schema_name()):
            
            self._handle_tenant_authentication(request)
        
        response = self.get_response(request)
        return response
    
    def _handle_tenant_authentication(self, request):
        """Handle authentication in tenant schemas"""
        user_id = None
        
        # Get user ID from session
        if hasattr(request, 'session') and request.session:
            user_id = request.session.get('_auth_user_id')
            
            # Also check session backup if current session is empty
            if not user_id:
                session_backup = getattr(request, '_session_backup', {})
                user_id = session_backup.get('data', {}).get('_auth_user_id')
        
        if user_id:
            # Authenticate user if not already authenticated
            if not hasattr(request, 'user') or isinstance(request.user, AnonymousUser):
                try:
                    from django_tenants.utils import schema_context
                    with schema_context(get_public_schema_name()):
                        User = get_user_model()
                        user = User.objects.get(pk=user_id)
                        request.user = user
                        
                        # Ensure session has the user ID
                        if hasattr(request, 'session'):
                            request.session['_auth_user_id'] = str(user_id)
                            request.session.modified = True
                            
                except Exception:
                    request.user = AnonymousUser()
        else:
            # Set anonymous user if no authentication found
            if not hasattr(request, 'user') or not request.user.is_authenticated:
                request.user = AnonymousUser()

class BusinessContextMiddleware:
    """Business context middleware with verification checks"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if hasattr(request, 'tenant') and request.tenant:
            if request.tenant.schema_name != get_public_schema_name():
                request.business = request.tenant
                
                if hasattr(request, 'business_slug_from_path'):
                    request.business_slug = request.business_slug_from_path
                
                # Handle unverified business access
                if not request.business.is_verified:
                    if (hasattr(request, 'user') and request.user.is_authenticated and 
                        not request.user.is_superuser):
                        
                        if hasattr(request.user, 'owned_businesses'):
                            user_business = request.user.owned_businesses.filter(id=request.business.id).first()
                            if user_business:
                                # Allow specific paths for business owners
                                allowed_paths = [
                                    '/logout/', '/verification-pending/', '/business/verification/',
                                    '/admin/', '/static/', '/media/', '/debug/', '/auth/',
                                ]
                                
                                current_path = request.path_info
                                path_allowed = any(current_path.startswith(path) for path in allowed_paths)
                                
                                if not path_allowed:
                                    messages.warning(request, 'Business verification is required to access this area.')
                                    return redirect('/auth/verification-pending/')
                            else:
                                messages.error(request, 'You do not have access to this business.')
                                return redirect('/public/')
            else:
                request.business = None
                request.business_slug = None
        else:
            request.business = None
            request.business_slug = None
        
        response = self.get_response(request)
        return response

class TimezoneMiddleware:
    """Set timezone based on business settings"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if hasattr(request, 'business') and request.business:
            business_timezone = getattr(request.business, 'timezone', 'Africa/Nairobi')
            try:
                timezone.activate(pytz.timezone(business_timezone))
            except pytz.UnknownTimeZoneError:
                timezone.activate(pytz.timezone('Africa/Nairobi'))
        else:
            timezone.activate(pytz.timezone('Africa/Nairobi'))
        
        response = self.get_response(request)
        return response

class UserActivityMiddleware:
    """Track user activity across schemas"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        if (hasattr(request, 'user') and not isinstance(request.user, AnonymousUser) and
            hasattr(request, 'business') and request.business):
            try:
                from apps.employees.models import Employee
                employee = Employee.objects.get(user_id=request.user.id, is_active=True)
                employee.last_activity = timezone.now()
                employee.save(update_fields=['last_activity'])
            except (Employee.DoesNotExist, Exception):
                pass
        
        return response

# Fake SessionMiddleware class for admin compatibility
class FakeSessionMiddleware:
    """
    Fake SessionMiddleware that satisfies Django admin's requirements
    but doesn't actually do anything since our TenantAwareSessionMiddleware handles everything.
    """
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Do nothing - just pass through
        return self.get_response(request)