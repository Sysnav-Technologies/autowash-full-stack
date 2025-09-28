"""
Database Connection Protection Middleware

Handles database connection issues, specifically "Command Out of Sync" 
and other PyMySQL-related errors in multi-tenant environments.
"""

import logging
from django.http import HttpResponse, JsonResponse
from django.db import connection
from django.core.exceptions import ImproperlyConfigured
from django.utils.deprecation import MiddlewareMixin
import pymysql

logger = logging.getLogger(__name__)


class DatabaseConnectionProtectionMiddleware(MiddlewareMixin):
    """
    Middleware to handle database connection issues that can cause 
    "Command Out of Sync" and other MySQL-related errors.
    """
    
    def process_request(self, request):
        """Process request and handle database connection issues"""
        try:
            # Test database connection health
            if hasattr(connection, 'ensure_connection'):
                connection.ensure_connection()
            
        except (pymysql.err.OperationalError, pymysql.err.InterfaceError) as e:
            error_code = getattr(e, 'args', (None,))[0] if hasattr(e, 'args') and e.args else None
            
            if error_code in [2006, 2013, 2014]:  # MySQL gone away, lost connection, command out of sync
                logger.warning(f"Database connection issue detected (code {error_code}): {e}")
                
                # Force close the connection to reset
                try:
                    connection.close()
                    logger.info("Forced database connection reset")
                except Exception as close_error:
                    logger.error(f"Error closing database connection: {close_error}")
                    
        except Exception as e:
            # Log other database-related errors but don't interrupt the request
            logger.error(f"Unexpected database error in protection middleware: {e}")
            
        return None
    
    def process_response(self, request, response):
        """Process response and ensure clean database state"""
        try:
            # Ensure all database connections are properly closed after request
            if hasattr(connection, 'close_if_unusable_or_obsolete'):
                connection.close_if_unusable_or_obsolete()
        except Exception as e:
            logger.error(f"Error in database cleanup: {e}")
            
        return response
    
    def process_exception(self, request, exception):
        """Handle database-related exceptions"""
        if isinstance(exception, (pymysql.err.OperationalError, pymysql.err.InterfaceError)):
            error_code = getattr(exception, 'args', (None,))[0] if hasattr(exception, 'args') and exception.args else None
            
            logger.error(f"Database exception caught (code {error_code}): {exception}")
            logger.error(f"Request path: {request.path}")
            
            # Force connection reset
            try:
                connection.close()
                logger.info("Database connection reset due to exception")
            except Exception as reset_error:
                logger.error(f"Error resetting connection: {reset_error}")
            
            # Return appropriate error response
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'error': 'Database connection error',
                    'message': 'Please try again in a moment',
                    'code': error_code
                }, status=500)
            else:
                return HttpResponse(
                    "Database connection error. Please refresh the page and try again.",
                    status=500
                )
        
        return None