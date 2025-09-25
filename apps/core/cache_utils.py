""""""

Cache Refresh UtilitiesCache utilities for consistent cache key management across the core app

Simple utilities to ensure cache refresh for tenant dataEnsures all cache operations use the same prefix and timeout as defined in settings

Can be used anywhere in the application to force cache updatesENHANCED for multi-tenant environments with proper tenant isolation

""""""

from django.core.cache import cachefrom django.core.cache import cache

from apps.core.database_router import get_current_tenantfrom django.conf import settings

import loggingimport logging

import hashlib

logger = logging.getLogger(__name__)import time



logger = logging.getLogger(__name__)

def refresh_order_cache(tenant_id=None, order_id=None, customer_id=None):

    """

    Refresh cache for order-related dataclass TenantCache:

    Can be called from any view or function that modifies orders    """

        Tenant-aware cache utility that ensures proper isolation between tenants

    Args:    """

        tenant_id: Tenant ID (auto-detected if not provided)    

        order_id: Specific order ID to refresh    # REAL-TIME SYSTEM - Force minimal timeout to prevent any staleness

        customer_id: Customer ID to refresh related data    _cache_config = settings.CACHES.get('default', {})

    """    KEY_PREFIX = _cache_config.get('KEY_PREFIX', 'autowash_cache')

    if not tenant_id:    DEFAULT_TIMEOUT = 10  # STRICTLY 10 seconds - real-time priority

        tenant = get_current_tenant()    

        if not tenant:    @classmethod

            return False    def _get_tenant_id(cls):

        tenant_id = str(tenant.id)        """Get current tenant ID from thread-local storage"""

            try:

    try:            from apps.core.database_router import TenantDatabaseRouter

        # Basic order cache keys            tenant = TenantDatabaseRouter.get_tenant()

        order_keys = [            if tenant:

            'orders_list',                return getattr(tenant, 'id', 'default')

            'service_orders_list',            return 'public'  # For public/main schema operations

            'pending_orders',        except:

            'pending_service_orders',            return 'public'

            'completed_orders',    

            'completed_service_orders',    @classmethod

            'in_progress_orders',    def get_key(cls, key, tenant_id=None):

            'in_progress_service_orders',        """

            'recent_orders',        Generate a tenant-specific cache key with proper isolation

            'recent_service_orders',        Args:

            'orders_count',            key: The cache key

            'service_orders_count',            tenant_id: Optional tenant ID override

            'dashboard_orders',        """

            'dashboard_service_orders',        if tenant_id is None:

            'order_stats',            tenant_id = cls._get_tenant_id()

            'service_order_stats',        

        ]        # Create tenant-isolated cache key

                tenant_key = f"tenant_{tenant_id}_{key}"

        # Add specific order cache if provided        

        if order_id:        # Add version hash to prevent issues after updates

            order_keys.extend([        version_hash = cls._get_version_hash()

                f'order_{order_id}',        versioned_key = f"v_{version_hash}_{tenant_key}"

                f'service_order_{order_id}',        

                f'order_{order_id}_items',        return versioned_key

                f'service_order_{order_id}_items',    

            ])    @classmethod

            def _get_version_hash(cls):

        # Add customer-specific cache if provided        """Generate a version hash to invalidate cache after deployments"""

        if customer_id:        try:

            order_keys.extend([            # Use deployment timestamp or app version

                f'customer_{customer_id}_orders',            version_string = getattr(settings, 'APP_VERSION', str(int(time.time() // 3600)))  # Changes every hour by default

                f'customer_{customer_id}_recent_orders',            return hashlib.md5(version_string.encode()).hexdigest()[:8]

            ])        except:

                    return 'default'

        # Clear all order cache keys    

        for key in order_keys:    @classmethod

            tenant_key = f"tenant_{tenant_id}:{key}"    def get(cls, key, default=None, tenant_id=None):

            cache.delete(tenant_key)        """

                Get value from cache with tenant isolation and error handling

        # Clear page cache        """

        cache.delete(f"tenant_{tenant_id}:views.decorators.cache")        try:

        cache.delete(f"tenant_{tenant_id}:middleware.cache")            cache_key = cls.get_key(key, tenant_id)

        cache.delete(f"tenant_{tenant_id}:template.cache")            return cache.get(cache_key, default)

                except Exception as e:

        logger.info(f"Order cache refreshed for tenant {tenant_id}")            logger.warning(f"Tenant cache get failed for key '{key}': {e}")

        return True            return default

            

    except Exception as e:    @classmethod

        logger.error(f"Failed to refresh order cache: {e}")    def set(cls, key, value, timeout=None, tenant_id=None):

        return False        """

        Set value in cache with tenant isolation and consistent timeout

        """

def refresh_customer_cache(tenant_id=None, customer_id=None):        try:

    """            cache_key = cls.get_key(key, tenant_id)

    Refresh cache for customer-related data            timeout = timeout or cls.DEFAULT_TIMEOUT

                cache.set(cache_key, value, timeout)

    Args:            return True

        tenant_id: Tenant ID (auto-detected if not provided)        except Exception as e:

        customer_id: Specific customer ID to refresh            logger.warning(f"Tenant cache set failed for key '{key}': {e}")

    """            return False

    if not tenant_id:    

        tenant = get_current_tenant()    @classmethod

        if not tenant:    def delete(cls, key, tenant_id=None):

            return False        """

        tenant_id = str(tenant.id)        Delete value from cache with tenant isolation

            """

    try:        try:

        customer_keys = [            cache_key = cls.get_key(key, tenant_id)

            'customers_list',            cache.delete(cache_key)

            'recent_customers',            return True

            'active_customers',        except Exception as e:

            'customer_count',            logger.warning(f"Tenant cache delete failed for key '{key}': {e}")

            'dashboard_customers',            return False

        ]    

            @classmethod

        if customer_id:    def clear_tenant(cls, tenant_id=None):

            customer_keys.extend([        """

                f'customer_{customer_id}',        Clear all cache entries for a specific tenant

                f'customer_{customer_id}_orders',        """

                f'customer_{customer_id}_payments',        if tenant_id is None:

                f'customer_{customer_id}_vehicles',            tenant_id = cls._get_tenant_id()

            ])        

                try:

        for key in customer_keys:            # This is a simplified approach - in production you might want to use cache.delete_many

            tenant_key = f"tenant_{tenant_id}:{key}"            # For now, we'll track keys and delete them

            cache.delete(tenant_key)            # Note: File-based cache doesn't support pattern deletion, so we'll implement a registry

                        registry_key = f"cache_registry_tenant_{tenant_id}"

        logger.info(f"Customer cache refreshed for tenant {tenant_id}")            registered_keys = cache.get(registry_key, set())

        return True            

                    for key in registered_keys:

    except Exception as e:                cache.delete(key)

        logger.error(f"Failed to refresh customer cache: {e}")                

        return False            cache.delete(registry_key)

            return True

        except Exception as e:

def refresh_payment_cache(tenant_id=None):            logger.warning(f"Tenant cache clear failed for tenant '{tenant_id}': {e}")

    """            return False

    Refresh cache for payment-related data    

    """    @classmethod

    if not tenant_id:    def get_info(cls):

        tenant = get_current_tenant()        """

        if not tenant:        Get cache configuration info for debugging

            return False        """

        tenant_id = str(tenant.id)        return {

    @classmethod
    def get_cache_info(cls):
        """Get current cache system information"""
        return {
            'current_tenant': cls._get_tenant_id(),
            'key_prefix': cls.KEY_PREFIX,
            'default_timeout': cls.DEFAULT_TIMEOUT,
            'backend': cls._cache_config.get('BACKEND', 'Unknown'),
            'location': cls._cache_config.get('LOCATION', 'Unknown'),
            'version_hash': cls._get_version_hash()
        }

# Legacy class for backward compatibility

            'monthly_revenue',class CoreCache(TenantCache):

        ]    """Backward compatibility alias"""

            pass

        for key in payment_keys:

            tenant_key = f"tenant_{tenant_id}:{key}"

            cache.delete(tenant_key)# Convenience functions with tenant awareness

            def get_cache_key(key, tenant_id=None):

        logger.info(f"Payment cache refreshed for tenant {tenant_id}")    """Generate a tenant-specific cache key"""

        return True    return TenantCache.get_key(key, tenant_id)

        

    except Exception as e:def cache_get(key, default=None, tenant_id=None):

        logger.error(f"Failed to refresh payment cache: {e}")    """Get from cache with tenant isolation"""

        return False    return TenantCache.get(key, default, tenant_id)



def cache_set(key, value, timeout=None, tenant_id=None):

def refresh_dashboard_cache(tenant_id=None):    """Set in cache with tenant isolation"""

    """    return TenantCache.set(key, value, timeout, tenant_id)

    Refresh cache for dashboard data

    Use this when you want to refresh all dashboard-related cachedef cache_delete(key, tenant_id=None):

    """    """Delete from cache with tenant isolation"""

    if not tenant_id:    return TenantCache.delete(key, tenant_id)

        tenant = get_current_tenant()

        if not tenant:def clear_tenant_cache(tenant_id=None):

            return False    """Clear all cache for a tenant"""

        tenant_id = str(tenant.id)    return TenantCache.clear_tenant(tenant_id)
    
    try:
        dashboard_keys = [
            'dashboard_data',
            'dashboard_stats',
            'dashboard_charts',
            'dashboard_widgets',
            'dashboard_orders',
            'dashboard_customers',
            'dashboard_payments',
            'dashboard_metrics',
            'recent_activities',
            'performance_indicators',
        ]
        
        for key in dashboard_keys:
            tenant_key = f"tenant_{tenant_id}:{key}"
            cache.delete(tenant_key)
            
        # Clear page cache for dashboard
        cache.delete(f"tenant_{tenant_id}:views.decorators.cache")
        cache.delete(f"tenant_{tenant_id}:middleware.cache")
        cache.delete(f"tenant_{tenant_id}:template.cache")
            
        logger.info(f"Dashboard cache refreshed for tenant {tenant_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to refresh dashboard cache: {e}")
        return False


def refresh_all_cache(tenant_id=None):
    """
    Nuclear option: Refresh ALL cache for a tenant
    Use sparingly - only when you need to ensure everything is fresh
    """
    if not tenant_id:
        tenant = get_current_tenant()
        if not tenant:
            return False
        tenant_id = str(tenant.id)
    
    try:
        # Try to clear tenant-specific cache if backend supports it
        from apps.core.cache_backends import TenantAwareCacheHandler
        TenantAwareCacheHandler.clear_tenant_cache(tenant_id)
        
        logger.info(f"ALL cache refreshed for tenant {tenant_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to refresh all cache: {e}")
        return False


def force_cache_refresh(request=None, tenant_id=None):
    """
    Helper function that can be called from any view
    Automatically detects tenant from request if not provided
    
    Usage in views:
        from apps.core.cache_utils import force_cache_refresh
        force_cache_refresh(request)  # Auto-detects tenant
        force_cache_refresh(tenant_id='some-tenant-id')  # Specific tenant
    """
    if not tenant_id and request:
        if hasattr(request, 'tenant') and request.tenant:
            tenant_id = str(request.tenant.id)
        else:
            tenant = get_current_tenant()
            tenant_id = str(tenant.id) if tenant else None
    
    if not tenant_id:
        logger.warning("Cannot force cache refresh - no tenant ID available")
        return False
    
    # Refresh the most commonly used cache
    success = True
    success &= refresh_order_cache(tenant_id)
    success &= refresh_dashboard_cache(tenant_id)
    
    return success