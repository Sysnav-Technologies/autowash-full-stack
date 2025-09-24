"""
Multi-Tenant Database Cache Backend
Extends Django's DatabaseCache to provide tenant-specific cache isolation
"""
from django.core.cache.backends.db import DatabaseCache
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from apps.core.database_router import get_current_tenant
import threading
import uuid


class MultiTenantDatabaseCache(DatabaseCache):
    """
    Database cache backend with automatic tenant isolation
    Each tenant gets a unique cache namespace to prevent data leakage
    """
    
    def __init__(self, server, params):
        super().__init__(server, params)
        self._tenant_cache = {}  # Store tenant-specific cache prefixes
        
    def _get_tenant_prefix(self):
        """Get cache key prefix for current tenant"""
        tenant = get_current_tenant()
        
        if tenant:
            tenant_id = str(tenant.id)
            # Cache the tenant prefix to avoid repeated string operations
            if tenant_id not in self._tenant_cache:
                self._tenant_cache[tenant_id] = f"tenant_{tenant_id}:"
            return self._tenant_cache[tenant_id]
        else:
            # Default/system cache for non-tenant operations
            return "system:"
    
    def _make_tenant_key(self, key, version=None):
        """Create tenant-specific cache key"""
        # Get the base key from parent class
        base_key = self.make_key(key, version)
        
        # Add tenant prefix
        tenant_prefix = self._get_tenant_prefix()
        return f"{tenant_prefix}{base_key}"
    
    def add(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        """Add a value to the cache only if the key doesn't already exist"""
        tenant_key = self._make_tenant_key(key, version)
        return super().add(tenant_key, value, timeout, None)  # version=None since we handle it
    
    def get(self, key, default=None, version=None):
        """Retrieve a value from the cache"""
        tenant_key = self._make_tenant_key(key, version)
        return super().get(tenant_key, default, None)  # version=None since we handle it
    
    def set(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        """Set a value in the cache"""
        tenant_key = self._make_tenant_key(key, version)
        return super().set(tenant_key, value, timeout, None)  # version=None since we handle it
    
    def touch(self, key, timeout=DEFAULT_TIMEOUT, version=None):
        """Update the expiration time for a key"""
        tenant_key = self._make_tenant_key(key, version)
        return super().touch(tenant_key, timeout, None)
    
    def delete(self, key, version=None):
        """Delete a value from the cache"""
        tenant_key = self._make_tenant_key(key, version)
        return super().delete(tenant_key, None)
    
    def has_key(self, key, version=None):
        """Check if a key exists in the cache"""
        tenant_key = self._make_tenant_key(key, version)
        return super().has_key(tenant_key, None)
    
    def incr(self, key, delta=1, version=None):
        """Increment a cached integer value"""
        tenant_key = self._make_tenant_key(key, version)
        return super().incr(tenant_key, delta, None)
    
    def decr(self, key, delta=1, version=None):
        """Decrement a cached integer value"""
        tenant_key = self._make_tenant_key(key, version)
        return super().decr(tenant_key, delta, None)
    
    def get_many(self, keys, version=None):
        """Retrieve multiple values from the cache"""
        # Create mapping of original keys to tenant keys
        key_mapping = {}
        tenant_keys = []
        
        for key in keys:
            tenant_key = self._make_tenant_key(key, version)
            key_mapping[tenant_key] = key
            tenant_keys.append(tenant_key)
        
        # Get values with tenant keys
        results = super().get_many(tenant_keys, None)
        
        # Convert back to original keys
        return {key_mapping[tenant_key]: value for tenant_key, value in results.items()}
    
    def set_many(self, data, timeout=DEFAULT_TIMEOUT, version=None):
        """Set multiple values in the cache"""
        # Convert keys to tenant-specific keys
        tenant_data = {}
        for key, value in data.items():
            tenant_key = self._make_tenant_key(key, version)
            tenant_data[tenant_key] = value
        
        return super().set_many(tenant_data, timeout, None)
    
    def delete_many(self, keys, version=None):
        """Delete multiple values from the cache"""
        tenant_keys = [self._make_tenant_key(key, version) for key in keys]
        return super().delete_many(tenant_keys, None)
    
    def clear_tenant_cache(self, tenant_id=None):
        """Clear cache for specific tenant"""
        if not tenant_id:
            tenant = get_current_tenant()
            if tenant:
                tenant_id = str(tenant.id)
            else:
                return  # No tenant to clear
        
        # Get all cache entries for this tenant
        prefix = f"tenant_{tenant_id}:"
        
        # Note: This is a simplified approach. For production, you might want
        # to implement a more efficient method using SQL patterns
        try:
            with self._cache.get_connection(True) as cursor:
                cursor.execute(
                    f"DELETE FROM {self._table} WHERE cache_key LIKE %s",
                    [f"{prefix}%"]
                )
        except Exception as e:
            # Fallback: clear all cache if tenant-specific clearing fails
            self.clear()
            
    def clear(self):
        """Clear all cache entries (system-wide)"""
        return super().clear()


class TenantAwareCacheHandler:
    """
    Helper class for tenant-aware cache operations
    Provides high-level cache operations with automatic tenant isolation
    """
    
    @staticmethod
    def cache_for_tenant(tenant_id, key, value, timeout=3600):
        """Cache a value for a specific tenant"""
        from django.core.cache import cache
        tenant_key = f"tenant_{tenant_id}:{key}"
        cache.set(tenant_key, value, timeout)
    
    @staticmethod
    def get_from_tenant_cache(tenant_id, key, default=None):
        """Get a value from tenant-specific cache"""
        from django.core.cache import cache
        tenant_key = f"tenant_{tenant_id}:{key}"
        return cache.get(tenant_key, default)
    
    @staticmethod
    def clear_tenant_cache(tenant_id):
        """Clear all cache entries for a specific tenant"""
        from django.core.cache import cache
        if hasattr(cache, 'clear_tenant_cache'):
            cache.clear_tenant_cache(tenant_id)
        else:
            # Fallback for non-tenant-aware cache backends
            cache.clear()
    
    @staticmethod
    def invalidate_tenant_views(tenant_id):
        """Invalidate cached views for a specific tenant"""
        from django.core.cache import cache
        patterns = [
            f"tenant_{tenant_id}:views.decorators.cache",
            f"tenant_{tenant_id}:template.cache",
        ]
        
        for pattern in patterns:
            if hasattr(cache, 'delete_pattern'):
                cache.delete_pattern(pattern)