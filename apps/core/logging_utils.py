"""
AutoWash Logging Utilities
Comprehensive logging system for tenant activities, performance, security, and business analytics
Compatible with custom MySQL tenant system
"""

import logging
import json
from datetime import datetime
from uuid import UUID
from decimal import Decimal
from django.utils import timezone
from django.db import connection

class AutoWashJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for AutoWash logging that handles UUID, Decimal, and datetime objects"""
    
    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

# Initialize loggers
tenant_logger = logging.getLogger('autowash.tenant_activity')
login_logger = logging.getLogger('autowash.user_logins')
performance_logger = logging.getLogger('autowash.performance')
security_logger = logging.getLogger('autowash.security')
business_logger = logging.getLogger('autowash.business')

def get_current_tenant_name():
    """Get current tenant name from custom MySQL tenant system"""
    try:
        # Get tenant name from database name or connection schema
        db_name = connection.settings_dict.get('NAME', '')
        if db_name:
            # Extract tenant name from database name if it follows a pattern
            # Adjust this logic based on your tenant naming convention
            if '_' in db_name:
                return db_name.split('_')[-1]  # e.g., 'autowash_executive_wash' -> 'executive_wash'
            return db_name
        return 'default'
    except:
        return 'unknown'

def get_current_tenant_from_request(request=None):
    """Get tenant info from request path or session"""
    if request:
        try:
            # Extract tenant from URL path like /business/executive-wash/
            path_parts = request.path.strip('/').split('/')
            if len(path_parts) >= 2 and path_parts[0] == 'business':
                return path_parts[1]  # e.g., 'executive-wash'
        except:
            pass
    
    return get_current_tenant_name()

class AutoWashLogger:
    """Main logging class for AutoWash system"""
    
    @staticmethod
    def log_tenant_action(action, user=None, details=None, tenant=None, request=None):
        """Log tenant-specific actions"""
        if not tenant:
            tenant = get_current_tenant_from_request(request)
        
        log_data = {
            'timestamp': timezone.now().isoformat(),
            'tenant': tenant,
            'action': action,
            'user': user.username if user else 'anonymous',
            'user_id': user.id if user else None,
            'details': details or {},
        }
        
        tenant_logger.info(f"TENANT_ACTION: {json.dumps(log_data, cls=AutoWashJSONEncoder)}")
    
    @staticmethod
    def log_user_login(user, success=True, ip_address=None, user_agent=None, tenant=None, request=None):
        """Log user login attempts"""
        if not tenant:
            tenant = get_current_tenant_from_request(request)
        
        log_data = {
            'timestamp': timezone.now().isoformat(),
            'tenant': tenant,
            'username': user.username if user else 'unknown',
            'user_id': user.id if user else None,
            'success': success,
            'ip_address': ip_address,
            'user_agent': user_agent,
        }
        
        login_logger.info(f"LOGIN_ATTEMPT: {json.dumps(log_data, cls=AutoWashJSONEncoder)}")
    
    @staticmethod
    def log_performance(operation, duration_ms, details=None, tenant=None, request=None):
        """Log performance metrics"""
        if not tenant:
            tenant = get_current_tenant_from_request(request)
        
        log_data = {
            'timestamp': timezone.now().isoformat(),
            'tenant': tenant,
            'operation': operation,
            'duration_ms': duration_ms,
            'details': details or {},
        }
        
        performance_logger.info(f"PERFORMANCE: {json.dumps(log_data, cls=AutoWashJSONEncoder)}")
    
    @staticmethod
    def log_security_event(event_type, severity='WARNING', user=None, details=None, tenant=None, request=None):
        """Log security events"""
        if not tenant:
            tenant = get_current_tenant_from_request(request)
        
        log_data = {
            'timestamp': timezone.now().isoformat(),
            'tenant': tenant,
            'event_type': event_type,
            'severity': severity,
            'user': user.username if user else 'anonymous',
            'user_id': user.id if user else None,
            'details': details or {},
        }
        
        security_logger.warning(f"SECURITY_EVENT: {json.dumps(log_data, cls=AutoWashJSONEncoder)}")
    
    @staticmethod
    def log_business_event(event_type, amount=None, customer=None, service=None, details=None, tenant=None, request=None):
        """Log business/revenue events"""
        if not tenant:
            tenant = get_current_tenant_from_request(request)
        
        log_data = {
            'timestamp': timezone.now().isoformat(),
            'tenant': tenant,
            'event_type': event_type,
            'amount': amount,
            'customer_id': customer.id if customer else None,
            'service_id': service.id if service else None,
            'details': details or {},
        }
        
        business_logger.info(f"BUSINESS_EVENT: {json.dumps(log_data, cls=AutoWashJSONEncoder)}")


class LoggingMiddleware:
    """Middleware to automatically log requests and performance"""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = timezone.now()
        
        response = self.get_response(request)
        
        # Calculate response time
        end_time = timezone.now()
        duration_ms = (end_time - start_time).total_seconds() * 1000
        
        # Log performance for slow requests (> 1 second)
        if duration_ms > 1000:
            AutoWashLogger.log_performance(
                operation=f"{request.method} {request.path}",
                duration_ms=duration_ms,
                details={
                    'status_code': response.status_code,
                    'user_agent': request.META.get('HTTP_USER_AGENT', '')[:100],
                    'ip_address': self.get_client_ip(request),
                },
                request=request
            )
        
        return response
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


# Decorator for automatic performance logging
def log_performance(operation_name):
    """Decorator to automatically log function performance"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = timezone.now()
            try:
                result = func(*args, **kwargs)
                end_time = timezone.now()
                duration_ms = (end_time - start_time).total_seconds() * 1000
                
                AutoWashLogger.log_performance(
                    operation=f"{func.__module__}.{func.__name__}",
                    duration_ms=duration_ms,
                    details={'operation_name': operation_name}
                )
                return result
            except Exception as e:
                end_time = timezone.now()
                duration_ms = (end_time - start_time).total_seconds() * 1000
                
                AutoWashLogger.log_performance(
                    operation=f"{func.__module__}.{func.__name__}",
                    duration_ms=duration_ms,
                    details={
                        'operation_name': operation_name,
                        'error': str(e),
                        'status': 'failed'
                    }
                )
                raise
        return wrapper
    return decorator