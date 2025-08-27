"""
MySQL Multi-Tenant Middleware
Replaces django-tenants middleware for MySQL compatibility
"""
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from django.core.cache import cache
from apps.core.tenant_models import Tenant
from apps.core.database_router import TenantDatabaseRouter, TenantDatabaseManager
import re
import logging

logger = logging.getLogger(__name__)


class MySQLTenantMiddleware(MiddlewareMixin):
    """
    MySQL-compatible tenant middleware
    Resolves tenant from URL path and sets up database routing
    """
    
    def process_request(self, request):
        """Process incoming request to identify and set tenant"""
        
        # Skip tenant resolution for static and media files
        path = request.path_info
        if path.startswith('/static/') or path.startswith('/media/') or path.startswith('/favicon.ico'):
            return None
        
        # Clear any existing tenant context
        TenantDatabaseRouter.clear_tenant()
        
        # Get hostname and path
        hostname = request.get_host().lower()
        
        # Try to resolve tenant from different methods
        tenant = None
        
        # Method 1: Subdomain-based (e.g., business1.autowash.co.ke)
        if not tenant:
            tenant = self._resolve_from_subdomain(hostname)
        
        # Method 2: Path-based (e.g., /business/business1/)
        if not tenant:
            tenant, modified_path = self._resolve_from_path(path)
            if tenant and modified_path != path:
                # Store the modified path for URL resolution
                request.tenant_path_prefix = f"/business/{tenant.slug}"
                request.path_info = modified_path
        
        # Method 3: Custom domain (e.g., mybusiness.com)
        if not tenant:
            tenant = self._resolve_from_custom_domain(hostname)
        
        if tenant:
            # Set tenant in router
            TenantDatabaseRouter.set_tenant(tenant)
            
            # Add tenant database to settings if not already there
            db_alias = f"tenant_{tenant.id}"
            if db_alias not in settings.DATABASES:
                TenantDatabaseManager.add_tenant_to_settings(tenant)
            
            # Store tenant in request
            request.tenant = tenant
            
            # Add tenant context to request
            request.tenant_slug = tenant.slug
            request.tenant_subdomain = tenant.subdomain
            
        else:
            # No tenant found - handle public area
            request.tenant = None
            
            # Check if this is a tenant-specific URL without valid tenant
            if self._is_tenant_url(path) and not self._is_public_url(path):
                raise Http404("Business not found")
    
    def process_response(self, request, response):
        """Clean up tenant context after request"""
        TenantDatabaseRouter.clear_tenant()
        return response
    
    def _resolve_from_subdomain(self, hostname):
        """Resolve tenant from subdomain"""
        # Pattern: business1.autowash.co.ke
        main_domain = getattr(settings, 'MAIN_DOMAIN', 'autowash.co.ke')
        
        if hostname.endswith(f'.{main_domain}'):
            subdomain = hostname.replace(f'.{main_domain}', '')
            
            # Use cache for performance (with error handling)
            cache_key = f"tenant_subdomain_{subdomain}"
            tenant = None
            try:
                tenant = cache.get(cache_key)
            except Exception as e:
                logger.warning(f"Cache get failed for subdomain {subdomain}: {e}")
                # Continue without cache
            
            if tenant is None:
                try:
                    tenant = Tenant.objects.get_by_subdomain(subdomain)
                    if tenant:
                        try:
                            cache.set(cache_key, tenant, 300)  # Cache for 5 minutes
                        except Exception as e:
                            logger.warning(f"Cache set failed for subdomain {subdomain}: {e}")
                            # Continue without caching
                except Exception:
                    tenant = None
            
            return tenant
        
        return None
    
    def _resolve_from_path(self, path):
        """Resolve tenant from URL path"""
        # Pattern: /business/business1/dashboard/
        path_pattern = r'^/business/([a-z0-9-]+)/?'
        match = re.match(path_pattern, path)
        
        if match:
            tenant_slug = match.group(1)
            
            # Use cache for performance (with error handling)
            cache_key = f"tenant_slug_{tenant_slug}"
            tenant = None
            try:
                tenant = cache.get(cache_key)
            except Exception as e:
                logger.warning(f"Cache get failed for slug {tenant_slug}: {e}")
                # Continue without cache
            
            if tenant is None:
                try:
                    tenant = Tenant.objects.get(slug=tenant_slug, is_active=True)
                    try:
                        cache.set(cache_key, tenant, 300)  # Cache for 5 minutes
                    except Exception as e:
                        logger.warning(f"Cache set failed for slug {tenant_slug}: {e}")
                        # Continue without caching
                except Tenant.DoesNotExist:
                    tenant = None
            
            if tenant:
                # Remove tenant prefix from path
                new_path = re.sub(r'^/business/[a-z0-9-]+', '', path) or '/'
                return tenant, new_path
        
        return None, path
    
    def _resolve_from_custom_domain(self, hostname):
        """Resolve tenant from custom domain"""
        # Use cache for performance (with error handling)
        cache_key = f"tenant_domain_{hostname}"
        tenant = None
        try:
            tenant = cache.get(cache_key)
        except Exception as e:
            logger.warning(f"Cache get failed for domain {hostname}: {e}")
            # Continue without cache
        
        if tenant is None:
            try:
                tenant = Tenant.objects.get_by_domain(hostname)
                if tenant:
                    try:
                        cache.set(cache_key, tenant, 300)  # Cache for 5 minutes
                    except Exception as e:
                        logger.warning(f"Cache set failed for domain {hostname}: {e}")
                        # Continue without caching
            except Exception:
                tenant = None
        
        return tenant
    
    def _is_tenant_url(self, path):
        """Check if URL is tenant-specific"""
        tenant_patterns = [
            r'^/business/',
            r'^/dashboard/',
            r'^/employees/',
            r'^/customers/',
            r'^/services/',
            r'^/inventory/',
            r'^/reports/',
            r'^/payments/',
            r'^/expenses/',
            r'^/notifications/',
        ]
        
        return any(re.match(pattern, path) for pattern in tenant_patterns)
    
    def _is_public_url(self, path):
        """Check if URL is public (doesn't require tenant)"""
        public_patterns = [
            r'^/$',
            r'^/auth/',
            r'^/accounts/',
            r'^/admin/',
            r'^/api/public/',
            r'^/static/',
            r'^/media/',
            r'^/health/',
        ]
        
        return any(re.match(pattern, path) for pattern in public_patterns)


class TenantBusinessContextMiddleware(MiddlewareMixin):
    """
    Middleware to add business context to requests and enforce subscription access
    """
    
    def process_request(self, request):
        """Add business context to request and check subscription status"""
        tenant = getattr(request, 'tenant', None)
        
        if tenant:
            # Add business context - avoid setting tenant object directly to prevent DB routing issues
            request.business_id = tenant.id
            request.business_slug = tenant.slug
            request.business_name = tenant.name
            
            # Create a simple object with basic properties for template access
            class BusinessContext:
                def __init__(self, tenant):
                    self.id = tenant.id
                    self.slug = tenant.slug
                    self.name = tenant.name
                    
            request.business = BusinessContext(tenant)
            
            # Check subscription status before allowing access to business features
            if self._should_check_subscription(request.path_info):
                subscription_redirect = self._check_subscription_access(tenant, request)
                if subscription_redirect:
                    return HttpResponseRedirect(subscription_redirect)
            else:
                # For subscription-related pages, still set subscription context but don't block access
                from apps.subscriptions.models import Subscription
                from django.utils import timezone
                
                # Get tenant ID safely to avoid database routing issues
                tenant_id = getattr(tenant, 'id', None) if tenant else None
                if tenant_id:
                    # Get subscription from default database - use tenant ID not object
                    subscription = Subscription.objects.using('default').filter(business_id=tenant_id).first()
                    
                    # Store subscription data for template access without triggering database queries
                    request.subscription_cache = subscription
                    request.subscription_is_active = subscription.is_active if subscription else False
                    request.subscription_is_expired = not subscription.is_active if subscription else True
            
            # Load tenant settings
            try:
                # Try to get settings from tenant database
                from apps.core.tenant_models import TenantSettings
                db_alias = f"tenant_{tenant.id}"
                TenantDatabaseManager.add_tenant_to_settings(tenant)
                settings_obj = TenantSettings.objects.using(db_alias).filter(tenant_id=tenant.id).first()
                
                if not settings_obj:
                    # Create default settings if they don't exist
                    settings_obj = TenantSettings.objects.using(db_alias).create(tenant_id=tenant.id)
            except Exception as e:
                print(f"Warning: Could not load tenant settings: {e}")
                settings_obj = None
            
            request.tenant_settings = settings_obj
        else:
            request.business = None
            request.business_id = None
            request.business_slug = None
            request.business_name = None
    
    def _should_check_subscription(self, path):
        """Check if this path requires subscription validation"""
        # Only check subscription for business-specific paths
        if not path.startswith('/business/'):
            return False
            
        # Only allow subscription-related and auth URLs when subscription is expired
        allowed_business_paths = [
            '/subscriptions/',
            '/auth/logout/',
        ]
        
        # Extract the path after the business slug (e.g., /business/executive-wash/dashboard/ -> /dashboard/)
        path_parts = path.split('/')
        if len(path_parts) >= 4:  # ['', 'business', 'slug', 'remaining...']
            business_relative_path = '/' + '/'.join(path_parts[3:])
            
            for allowed_path in allowed_business_paths:
                if business_relative_path.startswith(allowed_path):
                    return False
        
        # Always allow static/media files
        if path.startswith('/static/') or path.startswith('/media/'):
            return False
        
        # Block everything else when in business context
        return True
    
    def _check_subscription_access(self, tenant, request):
        """Check if tenant has valid subscription for accessing business features"""
        try:
            from apps.subscriptions.models import Subscription
            from django.utils import timezone
            
            # Get tenant ID safely to avoid database routing issues
            tenant_id = getattr(tenant, 'id', None) if tenant else None
            if not tenant_id:
                return f'/business/{getattr(tenant, "slug", "unknown")}/subscriptions/upgrade/'
            
            # Get subscription from default database - use tenant ID not object
            subscription = Subscription.objects.using('default').filter(business_id=tenant_id).first()
            
            # Store subscription data for template access without triggering database queries
            request.subscription_cache = subscription
            request.subscription_is_active = subscription.is_active if subscription else False
            request.subscription_is_expired = not subscription.is_active if subscription else True
            
            if not subscription:
                # No subscription found
                return f'/business/{tenant.slug}/subscriptions/upgrade/'
            
            # Check if subscription is active
            if not subscription.is_active:
                if subscription.status == 'expired':
                    return f'/business/{tenant.slug}/subscriptions/upgrade/'
                elif subscription.status == 'trial':
                    # Check if trial has expired
                    if subscription.trial_end_date and timezone.now() > subscription.trial_end_date:
                        # Update status and redirect using default database
                        subscription.status = 'expired'
                        subscription.save(using='default')
                        return f'/business/{tenant.slug}/subscriptions/upgrade/'
                elif subscription.status in ['cancelled', 'suspended']:
                    return f'/business/{tenant.slug}/subscriptions/upgrade/'
            
            # Subscription is valid, allow access
            return None
            
        except Exception as e:
            print(f"ERROR Error in subscription middleware: {e}")
            # In case of error, redirect to upgrade to be safe
            return f'/business/{tenant.slug}/subscriptions/upgrade/'


class TenantURLMiddleware(MiddlewareMixin):
    """
    Middleware to handle URL generation for tenants
    """
    
    def process_request(self, request):
        """Set up URL resolver for tenant"""
        tenant = getattr(request, 'tenant', None)
        
        if tenant:
            # Store original resolver
            from django.urls import get_resolver
            request.original_resolver = get_resolver()
            
            # Set tenant-specific URL configuration
            if hasattr(settings, 'TENANT_URLCONF'):
                request.urlconf = settings.TENANT_URLCONF
            
            # Add tenant URL helper methods
            def tenant_reverse(viewname, args=None, kwargs=None):
                """Reverse URL with tenant prefix"""
                from django.urls import reverse
                url = reverse(viewname, args=args, kwargs=kwargs)
                
                # Add tenant prefix for path-based routing
                if hasattr(request, 'tenant_path_prefix'):
                    url = request.tenant_path_prefix + url
                
                return url
            
            request.tenant_reverse = tenant_reverse
