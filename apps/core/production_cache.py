"""
Production Database Cache Backend
Ensures cache operations always use the main database in multi-tenant environment
"""
from django.core.cache.backends.db import DatabaseCache
from django.db import connections


class ProductionDatabaseCache(DatabaseCache):
    """
    Database cache backend that always uses the main database
    Designed for production multi-tenant environments
    """
    
    def __init__(self, server, params):
        super().__init__(server, params)
        # Always use the main database connection
        self._db = 'default'
    
    def _get_connection(self, write=False):
        """
        Always return the main database connection
        """
        return connections['default']
    
    @property 
    def _cache(self):
        """
        Override to ensure we always use main database connection
        """
        return connections['default']
