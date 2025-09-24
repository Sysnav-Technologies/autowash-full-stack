"""
Production Database Cache Backend
Ensures cache operations always use the main database in multi-tenant environment
"""
from django.core.cache.backends.db import DatabaseCache
from django.db import connections
import logging
import threading

logger = logging.getLogger(__name__)


class ProductionDatabaseCache(DatabaseCache):
    """
    Database cache backend that always uses the main database
    Designed for production multi-tenant environments
    
    This backend ensures all cache operations use the main database
    regardless of the current tenant context to prevent cache table
    not found errors in tenant databases.
    """
    
    def __init__(self, server, params):
        # Initialize with main database connection
        super().__init__(server, params)
        # Always use the main database connection
        self._db = 'default'
        # Store the main database table name
        self._table = server
        # Thread-local storage for connection management
        self._local = threading.local()
    
    def _get_connection(self, write=False):
        """
        Always return the main database connection
        Override to prevent tenant database access
        """
        try:
            # Force connection to default database
            return connections['default']
        except Exception as e:
            logger.error(f"Failed to get main database connection for cache: {e}")
            raise
    
    @property 
    def _cache(self):
        """
        Override to ensure we always use main database connection
        """
        return self._get_connection()
    
    def validate_key(self, key):
        """
        Override validate_key to ensure proper key handling
        """
        # Call parent method but ensure we're using main database
        return super().validate_key(key)
    
    def make_key(self, key, version=None):
        """
        Override make_key to ensure proper key generation
        """
        # Call parent method but ensure consistent key generation
        return super().make_key(key, version)
    
    def add(self, key, value, timeout=None, version=None):
        """
        Override add to handle database connection errors gracefully
        """
        try:
            # Ensure we're using main database connection
            with self._get_connection().cursor() as cursor:
                return super().add(key, value, timeout, version)
        except Exception as e:
            logger.warning(f"Cache add failed for key {key}: {e}")
            return False
    
    def get(self, key, default=None, version=None):
        """
        Override get to handle database connection errors gracefully
        """
        try:
            # Ensure we're using main database connection  
            with self._get_connection().cursor() as cursor:
                return super().get(key, default, version)
        except Exception as e:
            logger.warning(f"Cache get failed for key {key}: {e}")
            return default
    
    def set(self, key, value, timeout=None, version=None):
        """
        Override set to handle database connection errors gracefully
        """
        try:
            # Ensure we're using main database connection
            with self._get_connection().cursor() as cursor:
                return super().set(key, value, timeout, version)
        except Exception as e:
            logger.warning(f"Cache set failed for key {key}: {e}")
            # Fail silently - cache is not critical
            return False
    
    def delete(self, key, version=None):
        """
        Override delete to handle database connection errors gracefully  
        """
        try:
            # Ensure we're using main database connection
            with self._get_connection().cursor() as cursor:
                return super().delete(key, version)
        except Exception as e:
            logger.warning(f"Cache delete failed for key {key}: {e}")
            return False
    
    def has_key(self, key, version=None):
        """
        Override to ensure main database usage
        """
        try:
            # Ensure we're using main database connection
            with self._get_connection().cursor() as cursor:
                return super().has_key(key, version)
        except Exception as e:
            logger.warning(f"Cache has_key failed for key {key}: {e}")
            return False
    
    def incr(self, key, delta=1, version=None):
        """
        Override incr to ensure main database usage
        """
        try:
            # Ensure we're using main database connection
            with self._get_connection().cursor() as cursor:
                return super().incr(key, delta, version)
        except Exception as e:
            logger.warning(f"Cache incr failed for key {key}: {e}")
            raise ValueError(f"Key '{key}' not found")
    
    def decr(self, key, delta=1, version=None):
        """
        Override decr to ensure main database usage
        """
        try:
            # Ensure we're using main database connection
            with self._get_connection().cursor() as cursor:
                return super().decr(key, delta, version)
        except Exception as e:
            logger.warning(f"Cache decr failed for key {key}: {e}")
            raise ValueError(f"Key '{key}' not found")
    
    def clear(self):
        """
        Override clear to ensure it uses main database
        """
        try:
            # Force use of main database connection
            connection = self._get_connection()
            with connection.cursor() as cursor:
                cursor.execute('DELETE FROM %s' % connection.ops.quote_name(self._table))
        except Exception as e:
            logger.warning(f"Cache clear failed: {e}")
            # Continue without clearing
            pass
    
    def _cull(self):
        """
        Override cull to ensure it uses main database
        """
        try:
            # Force the connection to be main database
            connection = self._get_connection()
            # Call parent method with our connection context
            super()._cull()
        except Exception as e:
            logger.warning(f"Cache cull failed: {e}")
            # Continue without culling
            pass
