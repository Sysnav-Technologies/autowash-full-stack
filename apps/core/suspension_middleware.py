"""
Suspension Middleware
Handles suspension checks for users, businesses, subscriptions, and employees
"""
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils.deprecation import MiddlewareMixin
from django.contrib import messages
from django.urls import reverse
from django.contrib.auth.models import AnonymousUser
import re


class SuspensionCheckMiddleware(MiddlewareMixin):
    """
    Middleware to check for various suspension states and redirect accordingly
    Checks for:
    1. User account suspension (is_active=False)
    2. Business suspension (is_active=False)
    3. Subscription suspension (status='suspended')
    4. Employee suspension (status='suspended')
    """
    
    # URLs that should be accessible even when suspended
    EXEMPT_URLS = [
        r'^/auth/',
        r'^/accounts/logout/',
        r'^/accounts/suspended/',
        r'^/public/',
        r'^/static/',
        r'^/media/',
        r'^/admin/',
        r'^/system-admin/',
        r'^/api/public/',
        r'^/health/',
        r'^/$',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def __call__(self, request):
        response = self.get_response(request)
        return response
    
    def process_request(self, request):
        """Check for suspension states before processing the request"""
        
        # Skip suspension checks for exempt URLs
        if self._is_exempt_url(request.path):
            return None
        
        # Skip for anonymous users
        if not request.user.is_authenticated:
            return None
        
        # Skip for superusers (they can access everything)
        if request.user.is_superuser:
            return None
        
        # Check user account suspension
        suspension_check = self._check_user_suspension(request)
        if suspension_check:
            return suspension_check
        
        # Check business-specific suspensions (only for tenant URLs)
        if hasattr(request, 'tenant') and request.tenant:
            business_check = self._check_business_suspension(request)
            if business_check:
                return business_check
            
            subscription_check = self._check_subscription_suspension(request)
            if subscription_check:
                return subscription_check
            
            employee_check = self._check_employee_suspension(request)
            if employee_check:
                return employee_check
        
        return None
    
    def _is_exempt_url(self, path):
        """Check if URL is exempt from suspension checks"""
        return any(re.match(pattern, path) for pattern in self.EXEMPT_URLS)
    
    def _check_user_suspension(self, request):
        """Check if user account is suspended"""
        if not request.user.is_active:
            return render(request, 'suspension/user_suspended.html', {
                'suspension_type': 'user_account',
                'title': 'Account Suspended',
                'message': 'Your user account has been suspended. Please contact support for assistance.',
                'support_email': 'support@autowash.co.ke',
                'support_phone': '+254 700 000 000',
            })
        return None
    
    def _check_business_suspension(self, request):
        """Check if business is suspended"""
        if not request.tenant.is_active:
            return render(request, 'suspension/business_suspended.html', {
                'suspension_type': 'business',
                'business': request.tenant,
                'title': 'Business Suspended',
                'message': f'The business "{request.tenant.name}" has been suspended.',
                'reason': getattr(request.tenant, 'rejection_reason', 'Administrative action'),
                'support_email': 'support@autowash.co.ke',
                'support_phone': '+254 700 000 000',
            })
        return None
    
    def _check_subscription_suspension(self, request):
        """Check if business subscription is suspended"""
        if hasattr(request.tenant, 'subscription') and request.tenant.subscription:
            subscription = request.tenant.subscription
            if subscription.status == 'suspended':
                return render(request, 'suspension/subscription_suspended.html', {
                    'suspension_type': 'subscription',
                    'business': request.tenant,
                    'subscription': subscription,
                    'title': 'Subscription Suspended',
                    'message': f'The subscription for "{request.tenant.name}" has been suspended.',
                    'reason': getattr(subscription, 'cancellation_reason', 'Payment issues or policy violation'),
                    'support_email': 'support@autowash.co.ke',
                    'support_phone': '+254 700 000 000',
                })
        return None
    
    def _check_employee_suspension(self, request):
        """Check if employee is suspended"""
        try:
            from apps.employees.models import Employee
            
            # Try to get employee record
            employee = Employee.objects.filter(
                user_id=request.user.id,
                is_active=True
            ).first()
            
            if employee and employee.status == 'suspended':
                return render(request, 'suspension/employee_suspended.html', {
                    'suspension_type': 'employee',
                    'business': request.tenant,
                    'employee': employee,
                    'title': 'Employee Account Suspended',
                    'message': f'Your employee account at "{request.tenant.name}" has been suspended.',
                    'support_email': request.tenant.email or 'support@autowash.co.ke',
                    'support_phone': request.tenant.phone or '+254 700 000 000',
                })
        except Exception:
            # If there's an error checking employee status, don't block access
            pass
        
        return None


class BusinessAccessControlMiddleware(MiddlewareMixin):
    """
    Additional middleware for business access control
    Ensures users have proper access to business features
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def __call__(self, request):
        response = self.get_response(request)
        return response
    
    def process_request(self, request):
        """Check business access permissions"""
        
        # Skip for non-business URLs
        if not self._is_business_url(request.path):
            return None
        
        # Skip for anonymous users (will be handled by login_required)
        if not request.user.is_authenticated:
            return None
        
        # Skip for superusers
        if request.user.is_superuser:
            return None
        
        # Must have a tenant for business URLs
        if not hasattr(request, 'tenant') or not request.tenant:
            return render(request, 'errors/business_not_found.html', {
                'title': 'Business Not Found',
                'message': 'The requested business could not be found or is not accessible.',
            }, status=404)
        
        # Check if user has access to this business
        access_check = self._check_business_access(request)
        if access_check:
            return access_check
        
        return None
    
    def _is_business_url(self, path):
        """Check if URL is a business-specific URL"""
        return path.startswith('/business/')
    
    def _check_business_access(self, request):
        """Check if user has access to the business"""
        user = request.user
        tenant = request.tenant
        
        # Business owner always has access (even if suspended from employee role)
        if tenant.owner_id == user.id:
            return None
        
        # Check if user is an employee
        try:
            from apps.employees.models import Employee
            
            employee = Employee.objects.filter(
                user_id=user.id,
                is_active=True
            ).first()
            
            if not employee:
                return render(request, 'errors/access_denied.html', {
                    'title': 'Access Denied',
                    'message': f'You do not have permission to access "{tenant.name}". You must be an employee or owner.',
                    'business': tenant,
                }, status=403)
            
            # Employee exists but check if they can login
            if not employee.can_login:
                return render(request, 'errors/access_denied.html', {
                    'title': 'Login Disabled',
                    'message': f'Your login access to "{tenant.name}" has been disabled. Please contact your manager.',
                    'business': tenant,
                    'employee': employee,
                }, status=403)
        
        except Exception:
            # If there's an error, allow access (other middleware will handle authentication)
            pass
        
        return None
