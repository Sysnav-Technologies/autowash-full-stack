"""
Enhanced Database Connection Protection Middleware

Handles database connection issues, connection pooling, and retry logic
for multi-tenant MySQL environments with high concurrency.
"""

import logging
import time
from django.http import HttpResponse, JsonResponse
from django.db import connection, connections
from django.core.exceptions import ImproperlyConfigured
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache
import pymysql

logger = logging.getLogger(__name__)


class DatabaseConnectionProtectionMiddleware(MiddlewareMixin):
    """
    Enhanced middleware to handle database connection issues with retry logic,
    connection health monitoring, and proper cleanup for multi-tenant environments.
    """
    
    # Connection health check settings
    HEALTH_CHECK_INTERVAL = 60  # 1 minute
    MAX_RETRY_ATTEMPTS = 5  # Increased retries
    RETRY_DELAY = 1.0  # 1 second between retries
    CONNECTION_TIMEOUT = 5  # 5 seconds connection timeout
    
    def process_request(self, request):
        """Process request with enhanced database connection management"""
        
        # Skip connection checks for static files
        if self._is_static_request(request):
            return None
            
        try:
            return self._ensure_database_health(request)
        except (pymysql.Error, ConnectionError) as e:
            logger.error(f"Database connection error: {str(e)}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'error': 'Database Connection Error',
                    'message': 'Unable to connect to database. Please try again.',
                    'retry': True
                }, status=503)
            return HttpResponse("Database connection error. Please try again later.", status=503)
    
    def _is_static_request(self, request):
        """Check if request is for static content"""
        path = request.path_info
        static_paths = ['/static/', '/media/', '/favicon.ico', '/robots.txt']
        return any(path.startswith(static_path) for static_path in static_paths)
    
    def _ensure_database_health(self, request):
        """Ensure database connections are healthy with retry logic"""
        
        attempt = 0
        last_error = None
        
        while attempt < self.MAX_RETRY_ATTEMPTS:
            try:
                # Set connection timeouts
                connection.ensure_connection()
                for conn in connections.all():
                    conn.connect()
                    if hasattr(conn.connection, 'ping'):
                        conn.connection.ping(reconnect=True)
                return None
                
            except (pymysql.Error, ConnectionError) as e:
                last_error = e
                attempt += 1
                if attempt < self.MAX_RETRY_ATTEMPTS:
                    time.sleep(self.RETRY_DELAY * attempt)  # Exponential backoff
                    continue
                    
                # Clear connection on persistent failure
                for conn in connections.all():
                    conn.close_if_unusable_or_obsolete()
                    
                raise  # Re-raise the last error if all retries failed
                
        # Check if we need to perform health check
        if not self._should_check_connection_health():
            return None
        
        retry_count = 0
        while retry_count < self.MAX_RETRY_ATTEMPTS:
            try:
                # Test all database connections
                self._test_all_connections()
                
                # Update health check timestamp
                cache.set('db_last_health_check', int(time.time()), timeout=self.HEALTH_CHECK_INTERVAL + 60)
                return None
                
            except (pymysql.err.OperationalError, pymysql.err.InterfaceError) as e:
                retry_count += 1
                error_code = getattr(e, 'args', (None,))[0] if hasattr(e, 'args') and e.args else None
                
                logger.warning(f"Database connection issue (attempt {retry_count}/{self.MAX_RETRY_ATTEMPTS}, code {error_code}): {e}")
                
                if error_code in [2006, 2013, 2014, 2055]:  # Connection lost, timeout, or protocol errors
                    self._reset_all_connections()
                    
                    if retry_count < self.MAX_RETRY_ATTEMPTS:
                        time.sleep(self.RETRY_DELAY * retry_count)  # Exponential backoff
                    else:
                        return self._handle_connection_failure(request, e, error_code)
                else:
                    # Non-recoverable error
                    return self._handle_connection_failure(request, e, error_code)
                    
            except Exception as e:
                logger.error(f"Unexpected database error in protection middleware: {e}")
                return None
                
        return None
    
    def _should_check_connection_health(self):
        """Determine if connection health check is needed"""
        last_check = cache.get('db_last_health_check', 0)
        return (int(time.time()) - last_check) > self.HEALTH_CHECK_INTERVAL
    
    def _test_all_connections(self):
        """Test health of all database connections"""
        for alias in connections:
            conn = connections[alias]
            try:
                if hasattr(conn, 'ensure_connection'):
                    conn.ensure_connection()
                    # Simple query to verify connection
                    with conn.cursor() as cursor:
                        cursor.execute("SELECT 1")
                        cursor.fetchone()
            except Exception as e:
                logger.warning(f"Connection test failed for database '{alias}': {e}")
                raise
    
    def _reset_all_connections(self):
        """Reset all database connections"""
        for alias in connections:
            try:
                connections[alias].close()
                logger.info(f"Reset database connection for '{alias}'")
            except Exception as e:
                logger.error(f"Error resetting connection '{alias}': {e}")
    
    def _handle_connection_failure(self, request, exception, error_code):
        """Handle final connection failure"""
        logger.error(f"Final database connection failure (code {error_code}): {exception}")
        logger.error(f"Request path: {request.path}")
        
        # Reset connections as last resort
        self._reset_all_connections()
        
        # Return appropriate error response
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': 'Database temporarily unavailable',
                'message': 'Please try again in a moment',
                'code': error_code,
                'retry_after': 5
            }, status=503)
        else:
            return HttpResponse(
                "Database temporarily unavailable. Please refresh the page and try again.",
                status=503
            )
    
    def process_response(self, request, response):
        """Process response and ensure clean database state"""
        try:
            # Clean up unused connections to prevent accumulation
            self._cleanup_idle_connections()
        except Exception as e:
            logger.error(f"Error in database cleanup: {e}")
            
        return response
    
    def _cleanup_idle_connections(self):
        """Clean up idle database connections"""
        for alias in connections:
            try:
                conn = connections[alias]
                if hasattr(conn, 'close_if_unusable_or_obsolete'):
                    conn.close_if_unusable_or_obsolete()
            except Exception as e:
                logger.debug(f"Error cleaning up connection '{alias}': {e}")
    
    def process_exception(self, request, exception):
        """Handle database-related exceptions with enhanced error handling"""
        if isinstance(exception, (pymysql.err.OperationalError, pymysql.err.InterfaceError)):
            error_code = getattr(exception, 'args', (None,))[0] if hasattr(exception, 'args') and exception.args else None
            
            logger.error(f"Database exception caught (code {error_code}): {exception}")
            logger.error(f"Request path: {request.path}")
            logger.error(f"Request method: {request.method}")
            
            # Force connection reset for all connections
            self._reset_all_connections()
            
            # Clear any cached connection health status
            cache.delete('db_last_health_check')
            
            # Return appropriate error response based on error type
            if error_code in [2006, 2013]:  # Connection lost/gone away
                status_code = 503  # Service temporarily unavailable
                message = "Database connection lost. Please try again."
            elif error_code == 2014:  # Commands out of sync
                status_code = 500  # Internal server error
                message = "Database synchronization error. Please try again."
            else:
                status_code = 500
                message = "Database error occurred. Please try again."
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'error': 'Database error',
                    'message': message,
                    'code': error_code,
                    'retry_after': 2
                }, status=status_code)
            else:
                return HttpResponse(f"{message}", status=status_code)
        
        return None