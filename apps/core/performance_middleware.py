"""
Performance Monitoring Middleware
Tracks database query performance and response times
"""
import time
import logging
from django.db import connection
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('autowash.performance')

class PerformanceMonitoringMiddleware(MiddlewareMixin):
    """
    Middleware to monitor database queries and response times
    Helps track performance improvements after optimization
    """
    
    def process_request(self, request):
        # Start timing the request
        request._performance_start_time = time.time()
        request._performance_start_queries = len(connection.queries)
        
    def process_response(self, request, response):
        # Only monitor if we have performance data
        if not hasattr(request, '_performance_start_time'):
            return response
            
        # Calculate timing
        end_time = time.time()
        duration_ms = (end_time - request._performance_start_time) * 1000
        
        # Calculate query count
        end_queries = len(connection.queries)
        query_count = end_queries - request._performance_start_queries
        
        # Get additional context
        tenant = getattr(request, 'tenant', None)
        tenant_name = tenant.slug if tenant else 'unknown'
        
        # Log performance data
        performance_data = {
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(end_time)),
            'tenant': tenant_name,
            'operation': f"{request.method} {request.path}",
            'duration_ms': round(duration_ms, 2),
            'query_count': query_count,
            'details': {
                'status_code': response.status_code,
                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:100],
                'ip_address': self.get_client_ip(request),
            }
        }
        
        # Log warning for slow requests (>500ms)
        if duration_ms > 500:
            logger.warning(f"SLOW REQUEST: {performance_data}")
        
        # Log all dashboard requests for monitoring
        if 'dashboard' in request.path or request.path.endswith('/'):
            logger.info(f"PERFORMANCE: {performance_data}")
        
        # Add performance headers for debugging
        if settings.DEBUG:
            response['X-Performance-Time'] = f"{duration_ms:.2f}ms"
            response['X-Performance-Queries'] = str(query_count)
        
        return response
    
    def get_client_ip(self, request):
        """Get the client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip