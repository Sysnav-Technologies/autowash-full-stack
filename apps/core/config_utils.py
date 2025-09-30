"""
Configuration Utilities for AutoWash Multi-Tenant System

Centralized configuration management to avoid repeated initialization
and provide consistent settings across the application.
"""

from django.conf import settings
from django.core.cache import cache
from decouple import config
import logging
import os

logger = logging.getLogger(__name__)

# Cache for configuration values to avoid repeated lookups
_config_cache = {}


class ConfigManager:
    """Centralized configuration manager"""
    
    # Environment detection
    RENDER = config('RENDER', default=False, cast=bool)
    CPANEL = config('CPANEL', default=False, cast=bool) 
    LOCAL = not RENDER and not CPANEL
    
    # Database settings
    DB_CONFIG = {
        'ENGINE': 'django.db.backends.mysql',
        'CONN_MAX_AGE': 0,  # Disable connection pooling for stability
        'CONN_HEALTH_CHECKS': True,
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': (
                "SET sql_mode='STRICT_TRANS_TABLES',"
                "autocommit=1,"
                "wait_timeout=28800,"
                "interactive_timeout=28800,"
                "net_read_timeout=600,"
                "net_write_timeout=600,"
                "innodb_lock_wait_timeout=120"
            ),
            'autocommit': True,
            'connect_timeout': 30,  # Reduced timeout for faster failure detection
            'read_timeout': 30,
            'write_timeout': 30,
            'isolation_level': None,
        },
        'TEST': {
            'CHARSET': 'utf8mb4',
            'COLLATION': 'utf8mb4_unicode_ci',
        },
        'ATOMIC_REQUESTS': False,  # Disable for better multi-tenant performance
        'TIME_ZONE': None,  # Use global TIME_ZONE setting
        'AUTOCOMMIT': True,  # Enable autocommit for MySQL
    }
    
    # Multi-tenant settings
    MAIN_DOMAIN = config('MAIN_DOMAIN', default='autowash.co.ke')
    TENANT_CACHE_TIMEOUT = 30  # 30 seconds for tenant caching
    CONNECTION_RETRY_ATTEMPTS = 2
    CONNECTION_RETRY_DELAY = 0.5
    
    # Session settings
    SESSION_CONFIG = {
        'ENGINE': 'django.contrib.sessions.backends.db',
        'COOKIE_AGE': 3600 * 12,  # 12 hours
        'COOKIE_NAME': 'autowash_sessionid',
        'COOKIE_SECURE': not settings.DEBUG and (CPANEL or RENDER),
        'COOKIE_HTTPONLY': True,
        'COOKIE_SAMESITE': 'Lax',
        'SAVE_EVERY_REQUEST': False,
        'EXPIRE_AT_BROWSER_CLOSE': False,
    }
    
    @classmethod
    def get_db_config(cls, name=None, user=None, password=None, host=None, port=None):
        """Get database configuration with custom parameters"""
        db_config = cls.DB_CONFIG.copy()
        
        if name:
            db_config['NAME'] = name
        if user:
            db_config['USER'] = user  
        if password:
            db_config['PASSWORD'] = password
        if host:
            db_config['HOST'] = host
        if port:
            db_config['PORT'] = port
            
        return db_config
    
    @classmethod
    def get_tenant_db_config(cls, tenant):
        """Get database configuration for a specific tenant"""
        return cls.get_db_config(
            name=tenant.database_name,
            user=tenant.database_user,
            password=tenant.database_password,
            host=tenant.database_host,
            port=tenant.database_port
        )
    
    @classmethod
    def is_production(cls):
        """Check if running in production environment"""
        return cls.CPANEL or cls.RENDER
    
    @classmethod
    def is_development(cls):
        """Check if running in development environment"""
        return cls.LOCAL
    
    @classmethod
    def get_allowed_hosts(cls):
        """Get allowed hosts based on environment"""
        if cls.LOCAL:
            return ['localhost', '127.0.0.1', '*.localhost', 'testserver']
        elif cls.RENDER:
            hosts = ['.onrender.com', 'autowash-3jpr.onrender.com', 'autowash.co.ke', 'www.autowash.co.ke', '*.autowash.co.ke']
            external_host = config('RENDER_EXTERNAL_HOSTNAME', default='')
            if external_host:
                hosts.append(external_host)
            return hosts
        else:  # CPANEL
            hosts = ['app.autowash.co.ke', 'autowash.co.ke', 'www.autowash.co.ke', '*.autowash.co.ke', 'www.app.autowash.co.ke']
            cpanel_domain = config('CPANEL_DOMAIN', default='')
            if cpanel_domain:
                hosts.append(cpanel_domain)
            return hosts


class CacheUtils:
    """Utilities for consistent caching across the application"""
    
    @staticmethod
    def get_tenant_cache_key(tenant_id, suffix=""):
        """Generate consistent cache key for tenant data"""
        return f"tenant_{tenant_id}_{suffix}" if suffix else f"tenant_{tenant_id}"
    
    @staticmethod
    def get_subdomain_cache_key(subdomain):
        """Generate cache key for subdomain lookup"""
        return f"sub_{subdomain}"
    
    @staticmethod
    def get_slug_cache_key(slug):
        """Generate cache key for slug lookup"""
        return f"slug_{slug}"
    
    @staticmethod
    def get_domain_cache_key(domain):
        """Generate cache key for custom domain lookup"""
        return f"domain_{domain}"
    
    @staticmethod
    def cache_tenant(tenant, timeout=None):
        """Cache tenant data with consistent keys"""
        if not timeout:
            timeout = ConfigManager.TENANT_CACHE_TIMEOUT
            
        # Cache by different lookup methods
        cache.set(CacheUtils.get_subdomain_cache_key(tenant.subdomain), tenant, timeout)
        cache.set(CacheUtils.get_slug_cache_key(tenant.slug), tenant, timeout)
        if tenant.custom_domain:
            cache.set(CacheUtils.get_domain_cache_key(tenant.custom_domain), tenant, timeout)
    
    @staticmethod
    def invalidate_tenant_cache(tenant):
        """Invalidate all cached data for a tenant"""
        cache.delete(CacheUtils.get_subdomain_cache_key(tenant.subdomain))
        cache.delete(CacheUtils.get_slug_cache_key(tenant.slug))
        if tenant.custom_domain:
            cache.delete(CacheUtils.get_domain_cache_key(tenant.custom_domain))
        
        # Also clear tenant-specific caches
        cache.delete(CacheUtils.get_tenant_cache_key(tenant.id, "settings"))
        cache.delete(CacheUtils.get_tenant_cache_key(tenant.id, "subscription"))


class ConnectionStateManager:
    """Manages connection state and provides user feedback"""
    
    CONNECTION_SLOW_THRESHOLD = 3.0  # 3 seconds
    CONNECTION_TIMEOUT_THRESHOLD = 10.0  # 10 seconds
    
    @staticmethod
    def is_connection_slow():
        """Check if connection is currently slow"""
        return cache.get('connection_slow', False)
    
    @staticmethod
    def set_connection_slow(is_slow=True, duration=60):
        """Set connection slow state"""
        cache.set('connection_slow', is_slow, timeout=duration)
    
    @staticmethod
    def get_connection_state():
        """Get current connection state for frontend"""
        return {
            'is_slow': ConnectionStateManager.is_connection_slow(),
            'message': 'Connection is slow. Please wait...' if ConnectionStateManager.is_connection_slow() else None,
            'timestamp': cache.get('connection_slow_timestamp', 0)
        }
    
    @staticmethod
    def should_block_actions():
        """Determine if user actions should be blocked due to connection issues"""
        return ConnectionStateManager.is_connection_slow()


class ErrorUtils:
    """Utilities for consistent error handling"""
    
    CONNECTION_ERROR_CODES = [2006, 2013, 2014, 2055]  # MySQL connection error codes
    
    @staticmethod
    def is_connection_error(exception):
        """Check if exception is a connection-related error"""
        import pymysql
        
        if not isinstance(exception, (pymysql.err.OperationalError, pymysql.err.InterfaceError)):
            return False
            
        error_code = getattr(exception, 'args', (None,))[0] if hasattr(exception, 'args') and exception.args else None
        return error_code in ErrorUtils.CONNECTION_ERROR_CODES
    
    @staticmethod
    def get_user_friendly_error_message(exception, request=None):
        """Get user-friendly error message based on exception type"""
        import pymysql
        
        if isinstance(exception, (pymysql.err.OperationalError, pymysql.err.InterfaceError)):
            error_code = getattr(exception, 'args', (None,))[0] if hasattr(exception, 'args') and exception.args else None
            
            if error_code in [2006, 2013]:  # Connection lost
                return "Connection to the server was lost. Please refresh the page and try again."
            elif error_code == 2014:  # Commands out of sync
                return "Server synchronization error. Please refresh the page and try again."
            elif error_code == 2055:  # Timeout
                return "Server response timeout. Please check your internet connection and try again."
            else:
                return "Database connection error. Please try again in a moment."
        
        return "An unexpected error occurred. Please try again."


# Global instances for easy access
config_manager = ConfigManager()
cache_utils = CacheUtils()
connection_state = ConnectionStateManager()
error_utils = ErrorUtils()