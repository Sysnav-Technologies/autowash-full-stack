from functools import wraps
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.contrib import messages
from django.core.exceptions import PermissionDenied

def business_required(view_func):
    """Decorator to ensure user is in a business tenant"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not hasattr(request, 'business') or not request.business:
            messages.error(request, 'You must be accessing from a business domain.')
            return redirect('/public/')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def employee_required(roles=None):
    """Decorator to ensure user is an employee with specific roles"""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        @business_required
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated or not request.user.id:
                return redirect('/auth/login/')
            
            # Check if user is the business owner directly (fallback)
            if hasattr(request, 'tenant') and request.tenant:
                if request.tenant.owner_id == request.user.id:
                    # User is the business owner, grant access
                    try:
                        from apps.employees.models import Employee
                        # Try to get or create employee record for owner
                        employee, created = Employee.objects.get_or_create(
                            user_id=request.user.id,
                            defaults={
                                'employee_id': f'OWN{request.user.id}',
                                'role': 'owner',
                                'employment_type': 'full_time',
                                'status': 'active',
                                'is_active': True,
                                'can_login': True,
                                'hire_date': request.tenant.created_at.date(),
                            }
                        )
                        if created:
                            print(f"Auto-created employee record for business owner: {request.user.username}")
                        request.employee = employee
                        return view_func(request, *args, **kwargs)
                    except Exception as e:
                        print(f"Error creating employee record for owner: {e}")
                        # Continue with regular employee check
                        pass
                
            try:
                from apps.employees.models import Employee
                # FIX: Use user_id instead of user foreign key for cross-schema compatibility
                employee = Employee.objects.get(user_id=request.user.id, is_active=True)
                
                if not employee.is_active:
                    raise PermissionDenied("Your account is not active.")
                
                if roles and employee.role not in roles:
                    raise PermissionDenied(f"You need {' or '.join(roles)} role to access this page.")
                
                request.employee = employee
                return view_func(request, *args, **kwargs)
                
            except Employee.DoesNotExist:
                messages.error(request, 'You are not registered as an employee in this business.')
                # Redirect to public instead of accounts:profile
                return redirect('/public/')
                
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
            # Construct proper business URL for path-based routing
            business_slug = getattr(request, 'business_slug', request.business.slug)
            return redirect(f'/business/{business_slug}/subscriptions/plans/')
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
                business_slug = getattr(request, 'business_slug', request.business.slug)
                return redirect(f'/business/{business_slug}/subscriptions/upgrade/')
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