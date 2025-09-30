"""
MySQL Multi-Tenant Middleware
Enhanced with connection state management and error handling
"""
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from apps.core.tenant_models import Tenant
from apps.core.database_router import TenantDatabaseRouter, TenantDatabaseManager
from apps.core.uuid_utils import is_valid_uuid, safe_uuid_convert, fix_corrupted_uuid_field
from apps.core.config_utils import (
    config_manager, cache_utils, connection_state, error_utils
)
from django.core.cache import cache
import re
import logging
import uuid
import time

logger = logging.getLogger(__name__)


class MySQLTenantMiddleware(MiddlewareMixin):
    """
    REAL-TIME MySQL-compatible tenant middleware
    Resolves tenant from URL path and sets up database routing with minimal caching
    """
    
    def process_request(self, request):
        """Process incoming request to identify and set tenant with connection state monitoring"""
        
        # Skip tenant resolution for static and media files
        path = request.path_info
        if path.startswith('/static/') or path.startswith('/media/') or path.startswith('/favicon.ico'):
            return None
        
        # Check if connection is slow and handle accordingly
        if connection_state.should_block_actions() and self._is_action_request(request):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'error': 'Connection slow',
                    'message': 'Connection is slow. Please wait and try again.',
                    'blocked': True
                }, status=503)
            # For non-AJAX requests, let them through but add warning
        
        # Clear any existing tenant context
        TenantDatabaseRouter.clear_tenant()
        
        # Get hostname and path
        hostname = request.get_host().lower()
        
        # Add connection state to request for template access
        request.connection_state = connection_state.get_connection_state()
        
        # Track tenant resolution time
        start_time = time.time()
        tenant = None
        
        try:
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
            
            # Monitor resolution time
            resolution_time = time.time() - start_time
            if resolution_time > config_manager.CONNECTION_RETRY_DELAY * 2:
                logger.warning(f"Slow tenant resolution: {resolution_time:.2f}s for {hostname}")
                connection_state.set_connection_slow(True, duration=60)
            
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
                    
        except Exception as e:
            logger.error(f"Error in tenant resolution: {e}")
            # Set connection as slow if database errors occur
            if error_utils.is_connection_error(e):
                connection_state.set_connection_slow(True, duration=120)
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'error': 'Database error',
                        'message': error_utils.get_user_friendly_error_message(e, request),
                        'blocked': True
                    }, status=503)
            raise
    
    def process_response(self, request, response):
        """Clean up tenant context after request"""
        TenantDatabaseRouter.clear_tenant()
        return response
    
    def _resolve_from_subdomain(self, hostname):
        """Resolve tenant from subdomain - REAL-TIME with minimal caching"""
        try:
            # Pattern: business1.autowash.co.ke
            main_domain = getattr(settings, 'MAIN_DOMAIN', 'autowash.co.ke')
            
            # Defensive hostname validation
            if not hostname or not isinstance(hostname, str) or len(hostname.strip()) == 0:
                logger.debug(f"Invalid hostname provided: {hostname}")
                return None
                
            hostname = hostname.strip().lower()
            
            if hostname.endswith(f'.{main_domain}'):
                subdomain = hostname.replace(f'.{main_domain}', '')
                
                # Validate subdomain is not empty and contains valid characters
                if not subdomain or len(subdomain.strip()) == 0:
                    logger.debug(f"Empty subdomain extracted from hostname: {hostname}")
                    return None
                
                # Validate subdomain format (only alphanumeric, hyphens, underscores)
                if not re.match(r'^[a-z0-9_-]+$', subdomain):
                    logger.debug(f"Invalid subdomain format: {subdomain}")
                    return None
                
                # Use cache utils for consistent key generation
                cache_key = cache_utils.get_subdomain_cache_key(subdomain)
                tenant = cache.get(cache_key)
                
                if tenant is None:
                    # Try database query with retry logic
                    tenant = self._query_tenant_with_retry('subdomain', subdomain, cache_key)
                
                return tenant
            
            return None
            
        except Exception as e:
            logger.error(f"Critical error in _resolve_from_subdomain for hostname {hostname}: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            return None
    
    def _resolve_from_path(self, path):
        """Resolve tenant from URL path - REAL-TIME with minimal caching"""
        # Pattern: /business/business1/dashboard/
        path_pattern = r'^/business/([a-z0-9-]+)/?'
        match = re.match(path_pattern, path)
        
        if match:
            tenant_slug = match.group(1)
            
            # Use cache utils for consistent key generation
            cache_key = cache_utils.get_slug_cache_key(tenant_slug)
            tenant = cache.get(cache_key)
            
            if tenant is None:
                # Try database query with retry logic
                tenant = self._query_tenant_with_retry('slug', tenant_slug, cache_key)
            
            if tenant:
                # Remove tenant prefix from path
                new_path = re.sub(r'^/business/[a-z0-9-]+', '', path) or '/'
                return tenant, new_path
        
        return None, path
    
    def _resolve_from_custom_domain(self, hostname):
        """Resolve tenant from custom domain - REAL-TIME with minimal caching"""
        # Use cache utils for consistent key generation
        cache_key = cache_utils.get_domain_cache_key(hostname)
        tenant = cache.get(cache_key)
        
        if tenant is None:
            # Try database query with retry logic
            tenant = self._query_tenant_with_retry('custom_domain', hostname, cache_key)
        
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
    
    def _is_action_request(self, request):
        """Check if request is an action that should be blocked during slow connections"""
        # Block POST, PUT, DELETE requests during slow connections
        if request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
            return True
        
        # Block specific GET requests that are actions
        path = request.path_info
        action_patterns = [
            r'/api/',
            r'/create/',
            r'/update/',
            r'/delete/',
            r'/save/',
            r'/process/',
        ]
        
        return any(re.search(pattern, path) for pattern in action_patterns)
    
    def _query_tenant_with_retry(self, field_name, field_value, cache_key):
        """Query tenant with retry logic using config utils"""
        
        for attempt in range(config_manager.CONNECTION_RETRY_ATTEMPTS + 1):
            try:
                logger.debug(f"Querying for {field_name}: {field_value} (attempt {attempt + 1})")
                
                # Build query based on field type
                if field_name == 'subdomain':
                    tenant = Tenant.objects.using('default').filter(
                        subdomain=field_value, 
                        is_active=True
                    ).first()
                elif field_name == 'slug':
                    tenant = Tenant.objects.using('default').filter(
                        slug=field_value, 
                        is_active=True
                    ).first()
                elif field_name == 'custom_domain':
                    tenant = Tenant.objects.using('default').filter(
                        custom_domain=field_value, 
                        is_active=True
                    ).first()
                else:
                    logger.error(f"Unknown field_name: {field_name}")
                    return None
                
                if tenant:
                    logger.debug(f"Found tenant: {tenant.id} for {field_name}: {field_value}")
                    # Validate tenant UUID fields before caching
                    try:
                        if not is_valid_uuid(tenant.id):
                            logger.error(f"Tenant {field_value} has invalid UUID: {tenant.id}")
                            return None
                    except Exception as uuid_error:
                        logger.error(f"UUID validation error for {field_name} {field_value}: {uuid_error}")
                        return None
                    
                    # Cache successfully retrieved tenant using cache utils
                    try:
                        cache.set(cache_key, tenant, timeout=config_manager.TENANT_CACHE_TIMEOUT)
                    except Exception as cache_error:
                        logger.warning(f"Failed to cache tenant: {cache_error}")
                    
                    return tenant
                else:
                    logger.debug(f"No tenant found for {field_name}: {field_value}")
                    return None
                    
            except Exception as e:
                logger.error(f"Database error resolving {field_name} {field_value} (attempt {attempt + 1}): {e}")
                
                # Check if this is a connection-related error using error utils
                if error_utils.is_connection_error(e) and attempt < config_manager.CONNECTION_RETRY_ATTEMPTS:
                    # Connection lost, retry after a short delay
                    retry_delay = config_manager.CONNECTION_RETRY_DELAY * (attempt + 1)
                    logger.warning(f"Connection error, retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    continue
                
                # For final attempt or non-connection errors, log and return None
                if attempt == config_manager.CONNECTION_RETRY_ATTEMPTS:
                    logger.error(f"Final attempt failed for {field_name} {field_value}: {e}")
                    import traceback
                    logger.error(f"Full traceback: {traceback.format_exc()}")
                    
                    # Mark connection as slow for persistent errors
                    connection_state.set_connection_slow(True, duration=300)  # 5 minutes
                
                return None
        
        return None


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
                    # Cache subscription data for performance
                    sub_cache_key = f"sub_data_{tenant_id}"
                    subscription_data = cache.get(sub_cache_key)
                    
                    if subscription_data is None:
                        # Get subscription from default database with proper error handling
                        subscription = None
                        try:
                            # Validate tenant_id before using it in queries
                            if tenant_id and is_valid_uuid(tenant_id):
                                # Use business_id (Django auto-created field for ForeignKey)
                                subscription = Subscription.objects.using('default').filter(
                                    business_id=tenant_id
                                ).order_by('-created_at').first()
                            else:
                                logger.warning(f"Invalid tenant_id for subscription lookup: {tenant_id}")
                        except Exception as e:
                            logger.warning(f"Error querying subscription for tenant {tenant_id}: {e}")
                            subscription = None
                        
                        subscription_data = {
                            'is_active': subscription.is_active if subscription else False,  # Use property method
                            'is_expired': not subscription.is_active if subscription else True,  # Use property method
                            'subscription': subscription
                        }
                        # Cache for 2 minutes to balance freshness and performance
                        cache.set(sub_cache_key, subscription_data, timeout=10)  # Real-time: 10 seconds
                    
                    # Store subscription data for template access
                    request.subscription_cache = subscription_data['subscription']
                    request.subscription_is_active = subscription_data['is_active']
                    request.subscription_is_expired = subscription_data['is_expired']
            
            # Load tenant settings with cache
            try:
                settings_cache_key = f"settings_{tenant.id}"
                settings_obj = cache.get(settings_cache_key)
                
                if settings_obj is None:
                    # Try to get settings from tenant database
                    from apps.core.tenant_models import TenantSettings
                    db_alias = f"tenant_{tenant.id}"
                    TenantDatabaseManager.add_tenant_to_settings(tenant)
                    settings_obj = TenantSettings.objects.using(db_alias).filter(tenant_id=tenant.id).first()
                    
                    if not settings_obj:
                        # Create default settings if they don't exist
                        settings_obj = TenantSettings.objects.using(db_alias).create(tenant_id=tenant.id)
                    
                    # Cache settings for 10 minutes
                    cache.set(settings_cache_key, settings_obj, timeout=10)  # Real-time: 10 seconds
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
            if not tenant_id or not is_valid_uuid(tenant_id):
                return f'/business/{getattr(tenant, "slug", "unknown")}/subscriptions/upgrade/'
            
            # Get subscription from default database - use tenant ID not object
            subscription = Subscription.objects.using('default').filter(
                business_id=tenant_id
            ).order_by('-created_at').first()
            
            # Store subscription data for template access without triggering database queries
            request.subscription_cache = subscription
            request.subscription_is_active = subscription.is_active if subscription else False  # Use property method
            request.subscription_is_expired = not subscription.is_active if subscription else True  # Use property method
            
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
            logger.error(f"ERROR Error in subscription middleware: {e}")
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
