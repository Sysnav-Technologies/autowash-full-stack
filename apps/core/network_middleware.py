"""
Network connectivity middleware to prevent database operations during slow or unstable internet.
This middleware helps prevent duplicate operations and data corruption during network issues.
"""

import time
import threading
from datetime import datetime, timedelta
from django.conf import settings
from django.http import JsonResponse
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin


class NetworkProtectionMiddleware(MiddlewareMixin):
    """
    Middleware to protect against duplicate database operations during slow internet.
    
    This middleware:
    1. Tracks request timing to detect slow connections
    2. Prevents duplicate form submissions
    3. Blocks database modifications during detected network issues
    4. Provides user feedback about network status
    """
    
    # Class-level storage for tracking network status
    _request_times = {}
    _slow_connection_detected = False
    _last_slow_detection = None
    _duplicate_submissions = {}
    _lock = threading.Lock()
    
    # Configuration
    SLOW_REQUEST_THRESHOLD = getattr(settings, 'NETWORK_SLOW_THRESHOLD', 3.0)  # seconds
    DUPLICATE_WINDOW = getattr(settings, 'NETWORK_DUPLICATE_WINDOW', 5.0)  # seconds
    PROTECTION_DURATION = getattr(settings, 'NETWORK_PROTECTION_DURATION', 30.0)  # seconds
    
    # URLs that modify database (add more as needed)
    DATABASE_MODIFYING_METHODS = ['POST', 'PUT', 'PATCH', 'DELETE']
    PROTECTED_URL_PATTERNS = [
        'order',
        'inventory',
        'customer',
        'employee',
        'service',
        'payment',
        'expense',
    ]
    
    def process_request(self, request):
        """Check network status before processing request."""
        current_time = time.time()
        
        with self._lock:
            # Check if we're in protection mode
            if self.__class__._is_protection_active():
                if self._should_block_request(request):
                    return self._handle_blocked_request(request)
            
            # Check for duplicate submissions
            if self._is_duplicate_submission(request, current_time):
                return self._handle_duplicate_submission(request)
        
        # Store request start time
        request._network_start_time = current_time
        return None
    
    def process_response(self, request, response):
        """Track request completion time and detect slow connections."""
        if hasattr(request, '_network_start_time'):
            request_duration = time.time() - request._network_start_time
            
            try:
                with self._lock:
                    # Update request timing data
                    self._update_request_timing(request, request_duration)
                    
                    # Detect slow connection
                    if request_duration > self.SLOW_REQUEST_THRESHOLD:
                        self._detect_slow_connection()
            except Exception as e:
                # Don't let middleware errors break the response
                import logging
                logging.getLogger(__name__).warning(f"Network middleware error: {e}")
        
        return response
    
    @classmethod
    def _is_protection_active(cls):
        """Check if network protection is currently active."""
        try:
            if not cls._slow_connection_detected or not cls._last_slow_detection:
                return False
            
            time_since_detection = time.time() - cls._last_slow_detection
            return time_since_detection < cls.PROTECTION_DURATION
        except Exception:
            # If there's any error, assume protection is not active
            return False
    
    def _should_block_request(self, request):
        """Determine if this request should be blocked."""
        try:
            # Only block database-modifying requests
            if request.method not in self.DATABASE_MODIFYING_METHODS:
                return False
            
            # Don't block critical auth or admin requests
            if any(pattern in request.path.lower() for pattern in ['login', 'logout', 'admin', 'csrf']):
                return False
            
            # Check if URL matches protected patterns
            path = request.path.lower()
            for pattern in self.PROTECTED_URL_PATTERNS:
                if pattern in path:
                    return True
            
            return False
        except Exception:
            # If there's any error in checking, don't block the request
            return False
    
    def _is_duplicate_submission(self, request, current_time):
        """Check if this is a duplicate form submission."""
        try:
            if request.method not in self.DATABASE_MODIFYING_METHODS:
                return False
            
            # Create a unique key for this request including form data hash
            user_id = getattr(request.user, 'id', 'anonymous') if hasattr(request, 'user') else 'anonymous'
            
            # Include form data in uniqueness check for better duplicate detection
            form_data_str = ''
            if hasattr(request, 'POST') and request.POST:
                # Sort and concatenate non-csrf form data for consistent hashing
                sorted_data = sorted([f"{k}:{v}" for k, v in request.POST.items() if k != 'csrfmiddlewaretoken'])
                form_data_str = '|'.join(sorted_data)
            
            # Create request signature
            import hashlib
            form_hash = hashlib.md5(form_data_str.encode()).hexdigest()[:8] if form_data_str else 'no-data'
            request_key = f"{user_id}:{request.path}:{request.method}:{form_hash}"
            
            # Check for recent identical requests
            if request_key in self._duplicate_submissions:
                last_request_time = self._duplicate_submissions[request_key]
                if current_time - last_request_time < self.DUPLICATE_WINDOW:
                    return True
            
            # Store this request
            self._duplicate_submissions[request_key] = current_time
            
            # Clean up old entries
            self._cleanup_duplicate_tracking(current_time)
            
            return False
        except Exception:
            # If there's any error in duplicate detection, allow the request
            return False

    def _cleanup_duplicate_tracking(self, current_time):
        """Remove old entries from duplicate tracking."""
        try:
            # Remove entries older than the duplicate window
            cutoff_time = current_time - self.DUPLICATE_WINDOW - 60  # Extra 60 seconds buffer
            keys_to_remove = [
                key for key, timestamp in self._duplicate_submissions.items() 
                if timestamp < cutoff_time
            ]
            for key in keys_to_remove:
                del self._duplicate_submissions[key]
        except Exception:
            # If cleanup fails, just continue - this is not critical
            pass
    
    def _handle_blocked_request(self, request):
        """Handle a blocked request due to network protection."""
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # AJAX request
            return JsonResponse({
                'error': True,
                'message': 'Network protection active. Please wait for connection to stabilize.',
                'network_protection': True,
                'retry_after': int(self.PROTECTION_DURATION - (time.time() - self._last_slow_detection))
            }, status=429)
        else:
            # Regular request
            messages.warning(
                request,
                'Network protection is active due to slow connection. '
                'Database modifications are temporarily disabled to prevent duplicates.'
            )
            
            # Redirect to a safe page (referrer or home)
            redirect_url = request.META.get('HTTP_REFERER')
            if not redirect_url:
                try:
                    redirect_url = reverse('dashboard:overview')
                except:
                    redirect_url = '/'
            
            return redirect(redirect_url)
    
    def _handle_duplicate_submission(self, request):
        """Handle a duplicate form submission."""
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': True,
                'message': 'Duplicate submission detected. Please wait before trying again.',
                'duplicate_submission': True
            }, status=429)
        else:
            messages.warning(
                request,
                'Duplicate submission detected. Please wait a moment before trying again.'
            )
            
            redirect_url = request.META.get('HTTP_REFERER', '/')
            return redirect(redirect_url)
    
    def _update_request_timing(self, request, duration):
        """Update request timing statistics."""
        # Keep only recent request times
        current_time = time.time()
        cutoff_time = current_time - 60  # Keep last 60 seconds
        
        # Clean up old entries
        self._request_times = {
            timestamp: duration 
            for timestamp, duration in self._request_times.items() 
            if timestamp > cutoff_time
        }
        
        # Add current request
        self._request_times[current_time] = duration
    
    def _detect_slow_connection(self):
        """Detect if connection is consistently slow."""
        current_time = time.time()
        recent_times = [
            duration for timestamp, duration in self._request_times.items()
            if current_time - timestamp < 30  # Last 30 seconds
        ]
        
        if len(recent_times) >= 3:  # Need at least 3 requests
            avg_time = sum(recent_times) / len(recent_times)
            slow_count = sum(1 for t in recent_times if t > self.SLOW_REQUEST_THRESHOLD)
            
            # If more than 50% of recent requests are slow
            if slow_count / len(recent_times) > 0.5 and avg_time > self.SLOW_REQUEST_THRESHOLD:
                self._slow_connection_detected = True
                self._last_slow_detection = current_time
    
    def _cleanup_duplicate_tracking(self, current_time):
        """Clean up old duplicate submission tracking entries."""
        cutoff_time = current_time - self.DUPLICATE_WINDOW * 2
        self._duplicate_submissions = {
            key: timestamp 
            for key, timestamp in self._duplicate_submissions.items()
            if timestamp > cutoff_time
        }
    
    @classmethod
    def get_network_status(cls):
        """Get current network protection status (for templates/frontend)."""
        with cls._lock:
            return {
                'protection_active': cls._is_protection_active(),
                'slow_connection': cls._slow_connection_detected,
                'last_detection': cls._last_slow_detection,
                'request_count': len(cls._request_times),
                'avg_response_time': (
                    sum(cls._request_times.values()) / len(cls._request_times)
                    if cls._request_times else 0
                )
            }