"""
Authentication Protection Middleware

Handles corrupted user sessions and database issues that cause
'list index out of range' errors in Django authentication system.
"""

import logging
from django.contrib.auth import logout
from django.contrib.sessions.models import Session
from django.shortcuts import redirect
from django.urls import reverse
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.models import AnonymousUser

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
            # Try to access user attribute to trigger authentication
            user = getattr(request, 'user', None)
            
            # If user access triggers an error, it will be caught below
            if user is not None:
                # Force evaluation of lazy user object
                is_authenticated = user.is_authenticated
                
        except (IndexError, ValueError, TypeError) as e:
            # Handle list index out of range and other corruption errors
            logger.warning(f"Authentication corruption detected: {e}")
            logger.warning(f"Request path: {request.path}")
            logger.warning(f"Session key: {request.session.session_key}")
            
            # Clear the corrupted session
            try:
                # Clear session data
                request.session.flush()
                
                # Set user to anonymous
                request.user = AnonymousUser()
                
                logger.info("Cleared corrupted session and set anonymous user")
                
            except Exception as cleanup_error:
                logger.error(f"Error clearing corrupted session: {cleanup_error}")
            
            # For AJAX requests, return JSON error
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'error': 'Session corruption detected',
                    'message': 'Please refresh the page and log in again',
                    'redirect': reverse('account_login') if hasattr(reverse, 'account_login') else '/accounts/login/'
                }, status=401)
            
            # For regular requests, redirect to login
            return redirect('/accounts/login/?next=' + request.path)
        
        except Exception as e:
            # Handle any other unexpected authentication errors
            logger.error(f"Unexpected authentication error: {e}")
            logger.error(f"Request path: {request.path}")
            
            # Try to clear session and continue
            try:
                request.session.flush()
                request.user = AnonymousUser()
            except Exception:
                pass
            
            # For AJAX requests
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'error': 'Authentication system error',
                    'message': 'Please refresh the page',
                }, status=500)
            
            # Continue with anonymous user for regular requests
            request.user = AnonymousUser()
        
        return None

    def process_exception(self, request, exception):
        """Handle exceptions that might be related to authentication corruption"""
        
        if isinstance(exception, IndexError):
            # This is likely the 'list index out of range' error we're seeing
            logger.error(f"IndexError in authentication: {exception}")
            logger.error(f"Request path: {request.path}")
            logger.error(f"User: {getattr(request, 'user', 'Unknown')}")
            
            # Try to clear the session
            try:
                request.session.flush()
                request.user = AnonymousUser()
                logger.info("Cleared session due to IndexError")
            except Exception as cleanup_error:
                logger.error(f"Error clearing session after IndexError: {cleanup_error}")
            
            # For AJAX requests
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'error': 'Database corruption detected',
                    'message': 'Session cleared. Please refresh and try again.',
                    'redirect': '/accounts/login/'
                }, status=500)
        
        # Let other exceptions continue normal handling
        return None