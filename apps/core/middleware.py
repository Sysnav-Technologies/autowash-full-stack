# apps/core/middleware.py - Updated version

from django.utils import timezone
from django.contrib.auth.models import AnonymousUser
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse
from django_tenants.utils import get_tenant_model, get_public_schema_name
import pytz

class BusinessContextMiddleware:
    """Middleware to add business context to requests"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Check if tenant attribute exists (added by django-tenants middleware)
        if hasattr(request, 'tenant') and request.tenant:
            # Add business context for tenant schemas
            if request.tenant.schema_name != get_public_schema_name():
                request.business = request.tenant
                
                # IMPORTANT: Check if business is verified for tenant access
                if not request.business.is_verified and not request.user.is_superuser:
                    # Only allow access to logout and verification endpoints
                    allowed_paths = [
                        '/auth/logout/',
                        '/auth/verification-pending/',
                        '/auth/business/verification/',
                        '/admin/',  # Allow admin access
                    ]
                    
                    if not any(request.path.startswith(path) for path in allowed_paths):
                        # Redirect unverified business users to verification pending
                        messages.warning(request, 'Business verification is required to access this area.')
                        return redirect('accounts:verification_pending')
                        
            else:
                request.business = None
        else:
            # If no tenant attribute, we're probably on public schema or tenant not set
            request.business = None
        
        response = self.get_response(request)
        return response

class TimezoneMiddleware:
    """Middleware to set timezone based on business settings"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Check if business exists and has timezone setting
        if hasattr(request, 'business') and request.business:
            # Get business timezone from settings or default to Africa/Nairobi
            business_timezone = getattr(request.business, 'timezone', 'Africa/Nairobi')
            try:
                timezone.activate(pytz.timezone(business_timezone))
            except pytz.UnknownTimeZoneError:
                # Fallback to default if timezone is invalid
                timezone.activate(pytz.timezone('Africa/Nairobi'))
        else:
            # Default timezone for public schema or when no business
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
            # Only try to update activity if we're in a tenant schema (not public)
            if hasattr(request, 'business') and request.business:
                try:
                    from apps.employees.models import Employee
                    # Try to get employee profile and update last activity
                    employee = Employee.objects.get(user=request.user)
                    employee.last_activity = timezone.now()
                    employee.save(update_fields=['last_activity'])
                except Employee.DoesNotExist:
                    # User is not an employee, that's fine
                    pass
                except Exception as e:
                    # Log error but don't break the request
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to update user activity: {e}")
        
        return response

class VerificationMiddleware:
    """Middleware to enforce business verification for tenant access"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Only apply to tenant schemas (not public)
        if (hasattr(request, 'business') and request.business and 
            request.business.schema_name != get_public_schema_name()):
            
            # Skip check for superusers
            if request.user.is_superuser:
                response = self.get_response(request)
                return response
            
            # Check if business is verified
            if not request.business.is_verified:
                # Define paths that should be accessible for unverified businesses
                allowed_paths = [
                    '/logout/',
                    '/verification-pending/',
                    '/business/verification/',
                    '/static/',
                    '/media/',
                    '/admin/',
                ]
                
                # Check if current path is allowed
                path_allowed = any(request.path.startswith(path) for path in allowed_paths)
                
                if not path_allowed:
                    # Build the verification pending URL for the public schema
                    verification_url = f"http{'s' if request.is_secure() else ''}://{request.get_host().split('.')[1:]}/auth/verification-pending/"
                    return redirect(verification_url)
        
        response = self.get_response(request)
        return response