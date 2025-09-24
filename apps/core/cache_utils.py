"""
Cache utilities for consistent cache key management across the core app
Ensures all cache operations use the same prefix and timeout as defined in settings
"""
from django.core.cache import cache
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class CoreCache:
    """
    Centralized cache utility for the core app that ensures consistency with settings
    """
    
    # Get settings from CACHES configuration
    _cache_config = settings.CACHES.get('default', {})
    KEY_PREFIX = _cache_config.get('KEY_PREFIX', 'autowash_cache')
    DEFAULT_TIMEOUT = _cache_config.get('TIMEOUT', 300)
    
    @classmethod
    def get_key(cls, key):
        """
        Generate a properly prefixed cache key
        Note: Django automatically applies KEY_PREFIX, but this ensures explicit consistency
        """
        # Django will automatically prepend the KEY_PREFIX, so we don't double-prefix
        return key
    
    @classmethod
    def get(cls, key, default=None):
        """
        Get value from cache with error handling
        """
        try:
            cache_key = cls.get_key(key)
            return cache.get(cache_key, default)
        except Exception as e:
            logger.warning(f"Cache get failed for key '{key}': {e}")
            return default
    
    @classmethod
    def set(cls, key, value, timeout=None):
        """
        Set value in cache with consistent timeout and error handling
        """
        try:
            cache_key = cls.get_key(key)
            timeout = timeout or cls.DEFAULT_TIMEOUT
            cache.set(cache_key, value, timeout)
            return True
        except Exception as e:
            logger.warning(f"Cache set failed for key '{key}': {e}")
            return False
    
    @classmethod
    def delete(cls, key):
        """
        Delete value from cache with error handling
        """
        try:
            cache_key = cls.get_key(key)
            cache.delete(cache_key)
            return True
        except Exception as e:
            logger.warning(f"Cache delete failed for key '{key}': {e}")
            return False
    
    @classmethod
    def get_info(cls):
        """
        Get cache configuration info for debugging
        """
        return {
            'key_prefix': cls.KEY_PREFIX,
            'default_timeout': cls.DEFAULT_TIMEOUT,
            'backend': cls._cache_config.get('BACKEND', 'Unknown'),
            'location': cls._cache_config.get('LOCATION', 'Unknown')
        }


# Convenience functions for backward compatibility
def get_cache_key(key):
    """Generate a properly prefixed cache key"""
    return CoreCache.get_key(key)

def cache_get(key, default=None):
    """Get from cache with error handling"""
    return CoreCache.get(key, default)

def cache_set(key, value, timeout=None):
    """Set in cache with consistent timeout"""
    return CoreCache.set(key, value, timeout)

def cache_delete(key):
    """Delete from cache with error handling"""
    return CoreCache.delete(key)