"""
Custom Database Cache Backend
Forces cache operations to always use the main database, not tenant databases
"""
from django.core.cache.backends.db import DatabaseCache
from django.db import connections, router


class MainDatabaseCache(DatabaseCache):
    """
    Database cache backend that always uses the main database
    This prevents issues where cache operations try to access tenant databases
    """
    
    def __init__(self, server, params):
        super().__init__(server, params)
        # Force the cache to always use the default database connection
        self._db = 'default'
    
    def _get_connection(self):
        """
        Always return the main database connection
        """
        return connections['default']
