"""
Cache utilities for consistent cache key management across the core app
Ensures all cache operations use the same prefix and timeout as defined in settings
ENHANCED for multi-tenant environments with proper tenant isolation
"""
from django.core.cache import cache
from django.conf import settings
import logging
import hashlib
import time

logger = logging.getLogger(__name__)


class TenantCache:
    """
    Tenant-aware cache utility that ensures proper isolation between tenants
    """
    
    # Get settings from CACHES configuration
    _cache_config = settings.CACHES.get('default', {})
    KEY_PREFIX = _cache_config.get('KEY_PREFIX', 'autowash_cache')
    DEFAULT_TIMEOUT = _cache_config.get('TIMEOUT', 300)
    
    @classmethod
    def _get_tenant_id(cls):
        """Get current tenant ID from thread-local storage"""
        try:
            from apps.core.database_router import TenantDatabaseRouter
            tenant = TenantDatabaseRouter.get_tenant()
            if tenant:
                return getattr(tenant, 'id', 'default')
            return 'public'  # For public/main schema operations
        except:
            return 'public'
    
    @classmethod
    def get_key(cls, key, tenant_id=None):
        """
        Generate a tenant-specific cache key with proper isolation
        Args:
            key: The cache key
            tenant_id: Optional tenant ID override
        """
        if tenant_id is None:
            tenant_id = cls._get_tenant_id()
        
        # Create tenant-isolated cache key
        tenant_key = f"tenant_{tenant_id}_{key}"
        
        # Add version hash to prevent issues after updates
        version_hash = cls._get_version_hash()
        versioned_key = f"v_{version_hash}_{tenant_key}"
        
        return versioned_key
    
    @classmethod
    def _get_version_hash(cls):
        """Generate a version hash to invalidate cache after deployments"""
        try:
            # Use deployment timestamp or app version
            version_string = getattr(settings, 'APP_VERSION', str(int(time.time() // 3600)))  # Changes every hour by default
            return hashlib.md5(version_string.encode()).hexdigest()[:8]
        except:
            return 'default'
    
    @classmethod
    def get(cls, key, default=None, tenant_id=None):
        """
        Get value from cache with tenant isolation and error handling
        """
        try:
            cache_key = cls.get_key(key, tenant_id)
            return cache.get(cache_key, default)
        except Exception as e:
            logger.warning(f"Tenant cache get failed for key '{key}': {e}")
            return default
    
    @classmethod
    def set(cls, key, value, timeout=None, tenant_id=None):
        """
        Set value in cache with tenant isolation and consistent timeout
        """
        try:
            cache_key = cls.get_key(key, tenant_id)
            timeout = timeout or cls.DEFAULT_TIMEOUT
            cache.set(cache_key, value, timeout)
            return True
        except Exception as e:
            logger.warning(f"Tenant cache set failed for key '{key}': {e}")
            return False
    
    @classmethod
    def delete(cls, key, tenant_id=None):
        """
        Delete value from cache with tenant isolation
        """
        try:
            cache_key = cls.get_key(key, tenant_id)
            cache.delete(cache_key)
            return True
        except Exception as e:
            logger.warning(f"Tenant cache delete failed for key '{key}': {e}")
            return False
    
    @classmethod
    def clear_tenant(cls, tenant_id=None):
        """
        Clear all cache entries for a specific tenant
        """
        if tenant_id is None:
            tenant_id = cls._get_tenant_id()
        
        try:
            # This is a simplified approach - in production you might want to use cache.delete_many
            # For now, we'll track keys and delete them
            # Note: File-based cache doesn't support pattern deletion, so we'll implement a registry
            registry_key = f"cache_registry_tenant_{tenant_id}"
            registered_keys = cache.get(registry_key, set())
            
            for key in registered_keys:
                cache.delete(key)
                
            cache.delete(registry_key)
            return True
        except Exception as e:
            logger.warning(f"Tenant cache clear failed for tenant '{tenant_id}': {e}")
            return False
    
    @classmethod
    def get_info(cls):
        """
        Get cache configuration info for debugging
        """
        return {
            'current_tenant': cls._get_tenant_id(),
            'key_prefix': cls.KEY_PREFIX,
            'default_timeout': cls.DEFAULT_TIMEOUT,
            'backend': cls._cache_config.get('BACKEND', 'Unknown'),
            'location': cls._cache_config.get('LOCATION', 'Unknown'),
            'version_hash': cls._get_version_hash()
        }


# Legacy class for backward compatibility
class CoreCache(TenantCache):
    """Backward compatibility alias"""
    pass


# Convenience functions with tenant awareness
def get_cache_key(key, tenant_id=None):
    """Generate a tenant-specific cache key"""
    return TenantCache.get_key(key, tenant_id)

def cache_get(key, default=None, tenant_id=None):
    """Get from cache with tenant isolation"""
    return TenantCache.get(key, default, tenant_id)

def cache_set(key, value, timeout=None, tenant_id=None):
    """Set in cache with tenant isolation"""
    return TenantCache.set(key, value, timeout, tenant_id)

def cache_delete(key, tenant_id=None):
    """Delete from cache with tenant isolation"""
    return TenantCache.delete(key, tenant_id)

def clear_tenant_cache(tenant_id=None):
    """Clear all cache for a tenant"""
    return TenantCache.clear_tenant(tenant_id)