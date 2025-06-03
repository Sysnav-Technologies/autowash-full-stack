from functools import wraps
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.core.exceptions import PermissionDenied

def business_required(view_func):
    """Decorator to ensure user is in a business tenant"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not hasattr(request, 'business') or not request.business:
            messages.error(request, 'You must be accessing from a business domain.')
            return HttpResponseRedirect(reverse('landing'))
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def employee_required(roles=None):
    """Decorator to ensure user is an employee with specific roles"""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        @business_required
        def _wrapped_view(request, *args, **kwargs):
            try:
                from apps.employees.models import Employee
                employee = Employee.objects.get(user=request.user)
                
                if not employee.is_active:
                    raise PermissionDenied("Your account is not active.")
                
                if roles and employee.role not in roles:
                    raise PermissionDenied(f"You need {' or '.join(roles)} role to access this page.")
                
                request.employee = employee
                return view_func(request, *args, **kwargs)
                
            except Employee.DoesNotExist:
                messages.error(request, 'You are not registered as an employee in this business.')
                return HttpResponseRedirect(reverse('accounts:profile'))
                
        return _wrapped_view
    return decorator

def owner_required(view_func):
    """Decorator to ensure user is a business owner"""
    return employee_required(['owner'])(view_func)

def manager_required(view_func):
    """Decorator to ensure user is a manager or owner"""
    return employee_required(['owner', 'manager'])(view_func)

def attendant_required(view_func):
    """Decorator to ensure user is an attendant, manager, or owner"""
    return employee_required(['owner', 'manager', 'attendant'])(view_func)

def subscription_active_required(view_func):
    """Decorator to ensure business has an active subscription"""
    @wraps(view_func)
    @business_required
    def _wrapped_view(request, *args, **kwargs):
        if not request.business.subscription or not request.business.subscription.is_active:
            messages.warning(request, 'Your subscription is not active. Please renew to continue using the service.')
            return HttpResponseRedirect(reverse('subscriptions:plans'))
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def feature_required(feature_name):
    """Decorator to check if business subscription includes a specific feature"""
    def decorator(view_func):
        @wraps(view_func)
        @subscription_active_required
        def _wrapped_view(request, *args, **kwargs):
            subscription = request.business.subscription
            if not subscription.has_feature(feature_name):
                messages.error(request, f'This feature ({feature_name}) is not available in your current plan.')
                return HttpResponseRedirect(reverse('subscriptions:upgrade'))
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def ajax_required(view_func):
    """Decorator to ensure request is AJAX"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return HttpResponseForbidden('AJAX request required')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def ratelimit_key(group, request):
    """Custom ratelimit key function"""
    if hasattr(request, 'business') and request.business:
        return f"{group}:{request.business.id}:{request.user.id if request.user.is_authenticated else request.META.get('REMOTE_ADDR')}"
    return f"{group}:{request.user.id if request.user.is_authenticated else request.META.get('REMOTE_ADDR')}"