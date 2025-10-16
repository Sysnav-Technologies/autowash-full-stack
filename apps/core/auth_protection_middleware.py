"""
Authentication Protection Middleware

Handles corrupted user sessions, database issues, and session corruption
that cause crashes in Django authentication system including MySQL
"Command Out of Sync" and SessionInterrupted errors.
"""

import logging
from django.contrib.auth import logout
from django.contrib.sessions.models import Session
from django.contrib.sessions.exceptions import SessionInterrupted
from django.db.utils import OperationalError
from django.shortcuts import redirect
from django.urls import reverse
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.models import AnonymousUser
import pymysql

logger = logging.getLogger(__name__)


class AuthProtectionMiddleware(MiddlewareMixin):
    """
    Middleware to protect against corrupted authentication data causing system crashes.
    
    This middleware should be placed BEFORE SubscriptionAccessMiddleware in settings.
    """
    
    def process_request(self, request):
        """Process request and handle authentication corruption gracefully"""

        # List of paths that don't require authentication protection
        exempt_paths = [
            '/admin/login/',
            '/accounts/login/',
            '/accounts/signup/',
            '/accounts/password/reset/',
            '/static/',
            '/media/',
            '/favicon.ico',
        ]

        # Skip exempt paths
        if any(request.path.startswith(path) for path in exempt_paths):
            return None

        try:
            # Ensure session is properly initialized before accessing user
            if hasattr(request, 'session') and hasattr(request.session, '_get_session'):
                # Force session cache initialization to prevent AttributeError
                try:
                    _ = request.session._session
                except AttributeError:
                    # Initialize _session_cache if missing
                    request.session._session_cache = {}

            # Try to access user attribute to trigger authentication
            user = getattr(request, 'user', None)

            # If user access triggers an error, it will be caught below
            if user is not None:
                # Force evaluation of lazy user object
                is_authenticated = user.is_authenticated

        except (IndexError, ValueError, TypeError, SessionInterrupted, OperationalError, pymysql.err.OperationalError) as e:
            # Handle authentication corruption, session interruption, and database errors
            error_type = type(e).__name__
            logger.warning(f"Authentication/Session error detected ({error_type}): {e}")
            logger.warning(f"Request path: {request.path}")
            logger.warning(f"Session key: {getattr(request.session, 'session_key', 'None')}")

            # Only clear session for REAL corruption issues, not initialization errors
            if isinstance(e, (SessionInterrupted, OperationalError, pymysql.err.OperationalError)):
                # Clear the corrupted session for real database/connection issues
                try:
                    # Clear session data - handle different corruption types
                    if hasattr(request, 'session'):
                        # Force flush the session to clear corruption
                        request.session.flush()
                        # Create new session
                        request.session.create()
                        # Ensure _session_cache is initialized after session operations
                        if not hasattr(request.session, '_session_cache'):
                            request.session._session_cache = {}

                    # Set user to anonymous
                    request.user = AnonymousUser()

                    logger.info(f"Cleared corrupted session due to {error_type}")

                except Exception as cleanup_error:
                    logger.error(f"Error clearing corrupted session: {cleanup_error}")
                    # Force create new anonymous user
                    try:
                        request.user = AnonymousUser()
                    except Exception:
                        pass

                # For AJAX requests, return JSON error
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', ''):
                    return JsonResponse({
                        'error': f'Session corruption detected ({error_type})',
                        'message': 'Please refresh the page and log in again',
                        'redirect': '/accounts/login/'
                    }, status=401)

                # For regular requests, redirect to login
                return redirect('/accounts/login/?next=' + request.path)
            else:
                # For other errors (like AttributeError from missing _session_cache), just log and continue
                logger.warning(f"Non-critical session error ({error_type}), continuing with request")
                # Don't clear session or logout user for these errors
        
        except Exception as e:
            # Handle any other unexpected authentication errors
            logger.error(f"Unexpected authentication error: {e}")
            logger.error(f"Request path: {request.path}")

            # Only clear session for critical errors, not for session cache issues
            if isinstance(e, (OperationalError, pymysql.err.OperationalError)):
                # Clear session for database connection issues
                try:
                    request.session.flush()
                    # Ensure _session_cache is initialized after session operations
                    if not hasattr(request.session, '_session_cache'):
                        request.session._session_cache = {}
                    request.user = AnonymousUser()
                except Exception:
                    pass

                # For AJAX requests
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'error': 'Database connection error',
                        'message': 'Please refresh the page',
                    }, status=500)
            else:
                # For other errors (like AttributeError), just log and continue without clearing session
                logger.warning(f"Non-critical authentication error ({type(e).__name__}), continuing without session clear")
                # Don't set user to anonymous or clear session for these errors
        
        return None

    def process_exception(self, request, exception):
        """Handle exceptions that might be related to authentication corruption"""
        
        # Handle session interruption errors
        if isinstance(exception, SessionInterrupted):
            logger.error(f"SessionInterrupted error: {exception}")
            logger.error(f"Request path: {request.path}")
            logger.error(f"User: {getattr(request, 'user', 'Unknown')}")
            
            # Clear the corrupted session
            try:
                request.session.flush()
                # Ensure _session_cache is initialized after session operations
                if not hasattr(request.session, '_session_cache'):
                    request.session._session_cache = {}
                request.user = AnonymousUser()
                logger.info("Cleared session due to SessionInterrupted")
            except Exception as cleanup_error:
                logger.error(f"Error clearing session after SessionInterrupted: {cleanup_error}")
            
            # For AJAX requests
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'error': 'Session interrupted',
                    'message': 'Session was deleted during request. Please refresh and log in again.',
                    'redirect': '/accounts/login/'
                }, status=401)
            
            # For regular requests, redirect to login
            return redirect('/accounts/login/?session_interrupted=1')
        
        # Handle MySQL operational errors
        if isinstance(exception, (OperationalError, pymysql.err.OperationalError)):
            error_msg = str(exception)
            if "Command Out of Sync" in error_msg or "2014" in error_msg:
                logger.error(f"MySQL Command Out of Sync error: {exception}")
                logger.error(f"Request path: {request.path}")

                # Clear session to prevent further corruption
                try:
                    request.session.flush()
                    # Ensure _session_cache is initialized after session operations
                    if not hasattr(request.session, '_session_cache'):
                        request.session._session_cache = {}
                    request.user = AnonymousUser()
                    logger.info("Cleared session due to MySQL Command Out of Sync")
                except Exception as cleanup_error:
                    logger.error(f"Error clearing session after MySQL error: {cleanup_error}")

                # For AJAX requests
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'error': 'Database connection error',
                        'message': 'Database connection corrupted. Please refresh the page.',
                        'redirect': '/accounts/login/'
                    }, status=500)

                # For regular requests, redirect to a safe page
                return redirect('/accounts/login/?db_error=1')
            else:
                # For other MySQL errors, don't clear session - just log
                logger.warning(f"MySQL operational error (non-critical): {exception}")
                logger.warning(f"Request path: {request.path}")
        
        if isinstance(exception, IndexError):
            # This is likely the 'list index out of range' error we're seeing
            logger.error(f"IndexError in authentication: {exception}")
            logger.error(f"Request path: {request.path}")
            logger.error(f"User: {getattr(request, 'user', 'Unknown')}")

            # Only clear session for critical IndexError cases, not all of them
            error_msg = str(exception)
            if "list index out of range" in error_msg.lower():
                # Clear session for critical list index errors that indicate real corruption
                try:
                    request.session.flush()
                    # Ensure _session_cache is initialized after session operations
                    if not hasattr(request.session, '_session_cache'):
                        request.session._session_cache = {}
                    request.user = AnonymousUser()
                    logger.info("Cleared session due to critical IndexError")
                except Exception as cleanup_error:
                    logger.error(f"Error clearing session after IndexError: {cleanup_error}")

                # For AJAX requests
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'error': 'Database corruption detected',
                        'message': 'Session cleared. Please refresh and try again.',
                        'redirect': '/accounts/login/'
                    }, status=500)
            else:
                # For other IndexError types, just log and continue
                logger.warning(f"Non-critical IndexError, continuing without session clear")
        
        # Let other exceptions continue normal handling
        return None

    def process_response(self, request, response):
        """Handle session save errors during response processing"""
        try:
            # This method is called after the view processes the request
            # Check if there are any session issues that might cause problems
            if hasattr(request, 'session') and hasattr(request.session, 'modified'):
                if request.session.modified:
                    # Try to save the session - if this fails, we'll catch it
                    pass
        except (SessionInterrupted, OperationalError, pymysql.err.OperationalError) as e:
            logger.error(f"Session save error during response: {e}")
            logger.error(f"Request path: {request.path}")

            # Only clear session for critical database errors, not for cache issues
            if isinstance(e, (OperationalError, pymysql.err.OperationalError)):
                # Clear session to prevent cascade failures for real DB issues
                try:
                    request.session.flush()
                    # Ensure _session_cache is initialized after session operations
                    if not hasattr(request.session, '_session_cache'):
                        request.session._session_cache = {}
                    logger.info("Flushed session during response processing due to DB save error")
                except Exception as cleanup_error:
                    logger.error(f"Error flushing session during response: {cleanup_error}")
            else:
                # For SessionInterrupted and other errors, just log
                logger.warning(f"Session error during response (not cleared): {type(e).__name__}")

        except Exception as e:
            logger.error(f"Unexpected session error during response: {e}")

        return response