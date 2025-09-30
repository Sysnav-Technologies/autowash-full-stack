"""
Simple Health Check API for AutoWash
Optimized for unified AutoWash Manager connection monitoring
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import never_cache
from django.db import connection
from django.utils import timezone
import time


@csrf_exempt
@require_http_methods(["GET"])
@never_cache
def health_check(request):
    """
    Lightweight health check endpoint for AutoWash Manager
    Returns basic system status optimized for quick response
    """
    start_time = time.time()
    
    try:
        # Quick database connectivity test
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        
        response_time = round((time.time() - start_time) * 1000, 2)
        
        # Quick tenant info if available
        tenant_info = 'public'
        if hasattr(request, 'tenant') and request.tenant:
            tenant_info = request.tenant.name
        
        return JsonResponse({
            'status': 'ok',
            'timestamp': timezone.now().isoformat(),
            'response_time_ms': response_time,
            'tenant': tenant_info,
            'database': 'ok'
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'timestamp': timezone.now().isoformat(),
            'error': str(e),
            'database': 'error'
        }, status=500)


@csrf_exempt  
@require_http_methods(["GET"])
@never_cache
def ping(request):
    """Ultra-fast ping endpoint for connection testing"""
    return JsonResponse({
        'status': 'ok',
        'timestamp': int(time.time())
    })