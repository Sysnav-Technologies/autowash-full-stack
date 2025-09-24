"""
Hybrid Cache Backend for AutoWash Multi-Tenant System
====================================================

This hybrid cache backend combines multiple cache storage types to optimize
performance while maintaining compatibility with hosting environments that
have limited cache backend options (e.g., cPanel without Redis).

Strategy:
1. Small, frequently accessed data -> Local Memory Cache (fast access)
2. Tenant-specific data -> Database Cache (persistent, shared across processes)
3. Static/template cache -> File System Cache (when appropriate)

Author: AutoWash Development Team
"""

from django.core.cache.backends.base import BaseCache
from django.core.cache.backends.locmem import LocMemCache
from django.core.cache.backends.db import DatabaseCache
from django.core.cache.backends.filebased import FileBasedCache
from django.core.cache import InvalidCacheBackendError
from django.utils.encoding import force_str
from django.utils.module_loading import import_string
import hashlib
import time
import os
import logging

logger = logging.getLogger(__name__)


class HybridCacheBackend(BaseCache):
    """
    Hybrid cache backend that intelligently routes cache operations
    based on key patterns and data characteristics.
    
    Features:
    - Tenant isolation for multi-tenant applications
    - Intelligent cache routing based on key patterns
    - Memory cache for frequently accessed small data
    - Database cache for persistent tenant data
    - File cache for static content when appropriate
    - Automatic fallback mechanisms
    """
    
    def __init__(self, location, params):
        super().__init__(params)
        
        # Initialize component cache backends
        self.memory_cache = LocMemCache(
            location='memory_cache',
            params={
                'MAX_ENTRIES': params.get('MEMORY_MAX_ENTRIES', 1000),
                'CULL_FREQUENCY': params.get('MEMORY_CULL_FREQUENCY', 3),
                **{k: v for k, v in params.items() if k.startswith('MEMORY_')}
            }
        )
        
        # Database cache for persistent data
        db_params = {
            'LOCATION': params.get('DB_TABLE', 'cache_table'),
            **{k: v for k, v in params.items() if k.startswith('DB_')}
        }
        self.database_cache = DatabaseCache(
            location=db_params['LOCATION'],
            params=db_params
        )
        
        # Optional file cache for static content (when filesystem is suitable)
        self.file_cache = None
        if params.get('USE_FILE_CACHE', False):
            file_location = params.get('FILE_LOCATION', '/tmp/django_cache')
            try:
                self.file_cache = FileBasedCache(
                    location=file_location,
                    params={k: v for k, v in params.items() if k.startswith('FILE_')}
                )
            except Exception as e:
                logger.warning(f"File cache initialization failed: {e}")
        
        # Cache routing configuration
        self.memory_patterns = params.get('MEMORY_PATTERNS', [
            'session:', 'user:', 'auth:', 'csrf:', 'quick_'
        ])
        self.database_patterns = params.get('DATABASE_PATTERNS', [
            'tenant:', 'business:', 'customer:', 'service:', 'inventory:'
        ])
        self.file_patterns = params.get('FILE_PATTERNS', [
            'template:', 'static:', 'media:'
        ])
        
        logger.info("HybridCacheBackend initialized with components: "
                   f"Memory={bool(self.memory_cache)}, "
                   f"Database={bool(self.database_cache)}, "
                   f"File={bool(self.file_cache)}")
    
    def _get_backend_for_key(self, key):
        """
        Determine which cache backend to use based on key pattern.
        
        Returns tuple of (primary_backend, fallback_backends)
        """
        key_str = force_str(key)
        
        # Check for memory cache patterns (fastest access)
        for pattern in self.memory_patterns:
            if pattern in key_str:
                return self.memory_cache, [self.database_cache]
        
        # Check for file cache patterns (static content)
        if self.file_cache:
            for pattern in self.file_patterns:
                if pattern in key_str:
                    return self.file_cache, [self.database_cache, self.memory_cache]
        
        # Default to database cache with memory fallback
        return self.database_cache, [self.memory_cache]
    
    def _make_tenant_aware_key(self, key):
        """
        Ensure key includes tenant context for proper isolation.
        This integrates with our TenantCache utility.
        """
        from .cache_utils import TenantCache
        
        # If key already looks tenant-aware, return as-is
        key_str = force_str(key)
        if ':tenant:' in key_str or key_str.startswith('tenant:'):
            return key_str
        
        # Try to get tenant context and make key tenant-aware
        try:
            tenant_cache = TenantCache()
            return tenant_cache._make_tenant_key(key_str, include_version=False)
        except Exception:
            # Fallback to original key if tenant context not available
            return key_str
    
    def get(self, key, default=None, version=None):
        """
        Retrieve value from appropriate cache backend with fallbacks.
        """
        tenant_key = self._make_tenant_aware_key(key)
        final_key = self.make_key(tenant_key, version=version)
        
        primary_backend, fallback_backends = self._get_backend_for_key(final_key)
        
        # Try primary backend first
        try:
            value = primary_backend.get(final_key, None, version=version)
            if value is not None:
                return value
        except Exception as e:
            logger.warning(f"Primary cache backend failed for key {final_key}: {e}")
        
        # Try fallback backends
        for backend in fallback_backends:
            if backend is None:
                continue
            try:
                value = backend.get(final_key, None, version=version)
                if value is not None:
                    # Store in primary backend for faster future access
                    try:
                        primary_backend.set(final_key, value, version=version)
                    except Exception:
                        pass  # Don't fail if we can't store in primary
                    return value
            except Exception as e:
                logger.warning(f"Fallback cache backend failed for key {final_key}: {e}")
        
        return default
    
    def set(self, key, value, timeout=None, version=None):
        """
        Store value in appropriate cache backend with replication.
        """
        tenant_key = self._make_tenant_aware_key(key)
        final_key = self.make_key(tenant_key, version=version)
        
        primary_backend, fallback_backends = self._get_backend_for_key(final_key)
        
        # Always store in primary backend
        success = False
        try:
            primary_backend.set(final_key, value, timeout=timeout, version=version)
            success = True
        except Exception as e:
            logger.error(f"Failed to store in primary cache backend for key {final_key}: {e}")
        
        # For critical data (tenant-specific), also store in fallback
        if 'tenant:' in force_str(final_key) and fallback_backends:
            for backend in fallback_backends[:1]:  # Only first fallback for replication
                if backend is None:
                    continue
                try:
                    backend.set(final_key, value, timeout=timeout, version=version)
                    success = True
                except Exception as e:
                    logger.warning(f"Failed to replicate to fallback cache: {e}")
        
        if not success:
            raise Exception(f"All cache backends failed for key {final_key}")
    
    def delete(self, key, version=None):
        """
        Delete from all backends to ensure consistency.
        """
        tenant_key = self._make_tenant_aware_key(key)
        final_key = self.make_key(tenant_key, version=version)
        
        # Delete from all backends
        backends = [self.memory_cache, self.database_cache]
        if self.file_cache:
            backends.append(self.file_cache)
        
        deleted = False
        for backend in backends:
            if backend is None:
                continue
            try:
                backend.delete(final_key, version=version)
                deleted = True
            except Exception as e:
                logger.warning(f"Failed to delete from cache backend: {e}")
        
        return deleted
    
    def has_key(self, key, version=None):
        """
        Check if key exists in any backend.
        """
        tenant_key = self._make_tenant_aware_key(key)
        final_key = self.make_key(tenant_key, version=version)
        
        primary_backend, fallback_backends = self._get_backend_for_key(final_key)
        
        # Check primary first
        try:
            if primary_backend.has_key(final_key, version=version):
                return True
        except Exception:
            pass
        
        # Check fallbacks
        for backend in fallback_backends:
            if backend is None:
                continue
            try:
                if backend.has_key(final_key, version=version):
                    return True
            except Exception:
                pass
        
        return False
    
    def clear(self):
        """
        Clear all cache backends.
        """
        backends = [self.memory_cache, self.database_cache]
        if self.file_cache:
            backends.append(self.file_cache)
        
        for backend in backends:
            if backend is None:
                continue
            try:
                backend.clear()
            except Exception as e:
                logger.warning(f"Failed to clear cache backend: {e}")
    
    def get_many(self, keys, version=None):
        """
        Get multiple keys, optimizing by grouping by backend.
        """
        result = {}
        backend_keys = {}  # Group keys by their target backend
        
        # Group keys by target backend
        for key in keys:
            tenant_key = self._make_tenant_aware_key(key)
            final_key = self.make_key(tenant_key, version=version)
            primary_backend, _ = self._get_backend_for_key(final_key)
            
            if primary_backend not in backend_keys:
                backend_keys[primary_backend] = []
            backend_keys[primary_backend].append((final_key, key))  # (final_key, original_key)
        
        # Fetch from each backend
        for backend, key_pairs in backend_keys.items():
            if backend is None:
                continue
            try:
                backend_keys_only = [kp[0] for kp in key_pairs]
                backend_result = backend.get_many(backend_keys_only, version=version)
                
                # Map back to original keys
                for final_key, original_key in key_pairs:
                    if final_key in backend_result:
                        result[original_key] = backend_result[final_key]
            except Exception as e:
                logger.warning(f"get_many failed for backend: {e}")
        
        return result
    
    def set_many(self, data, timeout=None, version=None):
        """
        Set multiple keys, optimizing by grouping by backend.
        """
        backend_data = {}  # Group data by target backend
        
        # Group by target backend
        for key, value in data.items():
            tenant_key = self._make_tenant_aware_key(key)
            final_key = self.make_key(tenant_key, version=version)
            primary_backend, _ = self._get_backend_for_key(final_key)
            
            if primary_backend not in backend_data:
                backend_data[primary_backend] = {}
            backend_data[primary_backend][final_key] = value
        
        # Set in each backend
        for backend, backend_dict in backend_data.items():
            if backend is None:
                continue
            try:
                backend.set_many(backend_dict, timeout=timeout, version=version)
            except Exception as e:
                logger.error(f"set_many failed for backend: {e}")
    
    def delete_many(self, keys, version=None):
        """
        Delete multiple keys from all backends.
        """
        final_keys = []
        for key in keys:
            tenant_key = self._make_tenant_aware_key(key)
            final_key = self.make_key(tenant_key, version=version)
            final_keys.append(final_key)
        
        # Delete from all backends
        backends = [self.memory_cache, self.database_cache]
        if self.file_cache:
            backends.append(self.file_cache)
        
        for backend in backends:
            if backend is None:
                continue
            try:
                backend.delete_many(final_keys, version=version)
            except Exception as e:
                logger.warning(f"delete_many failed for backend: {e}")
    
    def incr(self, key, delta=1, version=None):
        """
        Increment value, using primary backend.
        """
        tenant_key = self._make_tenant_aware_key(key)
        final_key = self.make_key(tenant_key, version=version)
        
        primary_backend, _ = self._get_backend_for_key(final_key)
        return primary_backend.incr(final_key, delta=delta, version=version)
    
    def decr(self, key, delta=1, version=None):
        """
        Decrement value, using primary backend.
        """
        tenant_key = self._make_tenant_aware_key(key)
        final_key = self.make_key(tenant_key, version=version)
        
        primary_backend, _ = self._get_backend_for_key(final_key)
        return primary_backend.decr(final_key, delta=delta, version=version)
    
    def touch(self, key, timeout=None, version=None):
        """
        Touch key in all relevant backends.
        """
        tenant_key = self._make_tenant_aware_key(key)
        final_key = self.make_key(tenant_key, version=version)
        
        # Touch in all backends that might have this key
        backends = [self.memory_cache, self.database_cache]
        if self.file_cache:
            backends.append(self.file_cache)
        
        touched = False
        for backend in backends:
            if backend is None:
                continue
            try:
                if backend.touch(final_key, timeout=timeout, version=version):
                    touched = True
            except Exception as e:
                logger.warning(f"Touch failed for backend: {e}")
        
        return touched


class TenantAwareHybridCache(HybridCacheBackend):
    """
    Extended hybrid cache with enhanced tenant awareness and management features.
    """
    
    def clear_tenant_cache(self, tenant_schema=None):
        """
        Clear all cache entries for a specific tenant.
        """
        from .cache_utils import TenantCache
        
        try:
            tenant_cache = TenantCache()
            
            # If no tenant specified, use current tenant context
            if tenant_schema is None:
                tenant_schema = tenant_cache._get_current_tenant_schema()
            
            if not tenant_schema:
                logger.warning("No tenant context for cache clearing")
                return
            
            # Clear tenant-specific patterns from all backends
            tenant_prefix = f"tenant:{tenant_schema}:"
            
            backends = [self.memory_cache, self.database_cache]
            if self.file_cache:
                backends.append(self.file_cache)
            
            cleared_count = 0
            for backend in backends:
                if backend is None:
                    continue
                    
                try:
                    # For backends that support pattern deletion
                    if hasattr(backend, 'delete_pattern'):
                        backend.delete_pattern(f"{tenant_prefix}*")
                        cleared_count += 1
                    else:
                        # Fallback: try to enumerate and delete (less efficient)
                        if hasattr(backend, '_cache') and hasattr(backend._cache, 'keys'):
                            keys_to_delete = [
                                key for key in backend._cache.keys()
                                if key.startswith(tenant_prefix)
                            ]
                            for key in keys_to_delete:
                                backend.delete(key)
                                cleared_count += 1
                except Exception as e:
                    logger.warning(f"Failed to clear tenant cache from backend: {e}")
            
            logger.info(f"Cleared {cleared_count} cache entries for tenant {tenant_schema}")
            
        except Exception as e:
            logger.error(f"Failed to clear tenant cache: {e}")
    
    def get_cache_stats(self):
        """
        Get statistics from all cache backends.
        """
        stats = {
            'backends': {},
            'total_keys': 0,
            'memory_usage': 'unknown'
        }
        
        backends = [
            ('memory', self.memory_cache),
            ('database', self.database_cache),
            ('file', self.file_cache)
        ]
        
        for name, backend in backends:
            if backend is None:
                continue
                
            backend_stats = {'available': True, 'keys': 0}
            
            try:
                # Try to get backend-specific stats
                if hasattr(backend, 'get_stats'):
                    backend_stats.update(backend.get_stats())
                elif hasattr(backend, '_cache'):
                    backend_stats['keys'] = len(getattr(backend._cache, 'data', {}))
                
                stats['backends'][name] = backend_stats
                stats['total_keys'] += backend_stats.get('keys', 0)
                
            except Exception as e:
                stats['backends'][name] = {
                    'available': False,
                    'error': str(e)
                }
        
        return stats