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
            
            # Use cache for performance
            cache_key = f"tenant_subdomain_{subdomain}"
            tenant = cache.get(cache_key)
            
            if tenant is None:
                try:
                    tenant = Tenant.objects.get_by_subdomain(subdomain)
                    if tenant:
                        cache.set(cache_key, tenant, 300)  # Cache for 5 minutes
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
            
            # Use cache for performance
            cache_key = f"tenant_slug_{tenant_slug}"
            tenant = cache.get(cache_key)
            
            if tenant is None:
                try:
                    tenant = Tenant.objects.get(slug=tenant_slug, is_active=True)
                    cache.set(cache_key, tenant, 300)  # Cache for 5 minutes
                except Tenant.DoesNotExist:
                    tenant = None
            
            if tenant:
                # Remove tenant prefix from path
                new_path = re.sub(r'^/business/[a-z0-9-]+', '', path) or '/'
                return tenant, new_path
        
        return None, path
    
    def _resolve_from_custom_domain(self, hostname):
        """Resolve tenant from custom domain"""
        # Use cache for performance
        cache_key = f"tenant_domain_{hostname}"
        tenant = cache.get(cache_key)
        
        if tenant is None:
            try:
                tenant = Tenant.objects.get_by_domain(hostname)
                if tenant:
                    cache.set(cache_key, tenant, 300)  # Cache for 5 minutes
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
    Middleware to add business context to requests
    Replaces the previous BusinessContextMiddleware
    """
    
    def process_request(self, request):
        """Add business context to request"""
        tenant = getattr(request, 'tenant', None)
        
        if tenant:
            # Add business context
            request.business = tenant  # For backward compatibility
            request.business_id = tenant.id
            request.business_slug = tenant.slug
            request.business_name = tenant.name
            
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
            request.tenant_settings = None


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
