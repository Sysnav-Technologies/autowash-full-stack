from django.utils import timezone
from django.contrib.auth.models import AnonymousUser
from django_tenants.utils import get_tenant_model, get_public_schema_name
import pytz

class BusinessContextMiddleware:
    """Middleware to add business context to requests"""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Add business context for tenant schemas
        if not request.tenant.schema_name == get_public_schema_name():
            request.business = request.tenant
        else:
            request.business = None
            
        response = self.get_response(request)
        return response

class TimezoneMiddleware:
    """Middleware to set timezone based on business settings"""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if hasattr(request, 'business') and request.business:
            # Get business timezone from settings or default to Africa/Nairobi
            business_timezone = getattr(request.business, 'timezone', 'Africa/Nairobi')
            timezone.activate(pytz.timezone(business_timezone))
        else:
            timezone.activate(pytz.timezone('Africa/Nairobi'))
            
        response = self.get_response(request)
        return response

class UserActivityMiddleware:
    """Middleware to track user activity"""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Update last activity for authenticated users
        if hasattr(request, 'user') and not isinstance(request.user, AnonymousUser):
            from apps.employees.models import Employee
            try:
                # Try to get employee profile and update last activity
                employee = Employee.objects.get(user=request.user)
                employee.last_activity = timezone.now()
                employee.save(update_fields=['last_activity'])
            except Employee.DoesNotExist:
                pass
                
        return response