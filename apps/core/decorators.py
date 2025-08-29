from functools import wraps
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
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

def suspension_check_required(view_func):
    """
    Decorator to perform comprehensive suspension checks
    This should be used on views that need extra suspension validation
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        # Skip for superusers
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        # Check user suspension
        if not request.user.is_active:
            return render(request, 'suspension/user_suspended.html', {
                'suspension_type': 'user_account',
                'title': 'Account Suspended',
                'message': 'Your user account has been suspended. Please contact support for assistance.',
            })
        
        # Check business suspension (if in tenant context)
        if hasattr(request, 'tenant') and request.tenant:
            if not request.tenant.is_active:
                return render(request, 'suspension/business_suspended.html', {
                    'suspension_type': 'business',
                    'business': request.tenant,
                    'title': 'Business Suspended',
                    'message': f'The business "{request.tenant.name}" has been suspended.',
                    'reason': getattr(request.tenant, 'rejection_reason', 'Administrative action'),
                })
            
            # Check subscription suspension (access from main database, not tenant)
            try:
                # Note: subscription is accessed from main database via tenant FK, not tenant database
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
                        })
            except Exception as e:
                # Handle database errors gracefully
                print(f"Warning: Could not check subscription status for tenant {request.tenant.slug}: {e}")
                pass
            
            # Check employee suspension
            try:
                from apps.employees.models import Employee
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
                    })
            except Exception:
                # If there's an error checking employee status, don't block access
                pass
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def employee_required(roles=None):
    """Decorator to ensure user is an employee with specific roles"""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        @business_required
        @suspension_check_required
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated or not request.user.id:
                return redirect('/auth/login/')
            
            # Check if user is the business owner directly (fallback)
            if hasattr(request, 'tenant') and request.tenant:
                if request.tenant.owner_id == request.user.id:
                    # User is the business owner, grant access
                    try:
                        from apps.employees.models import Employee
                        from apps.core.database_router import TenantDatabaseManager
                        
                        # Ensure tenant database is registered in settings
                        TenantDatabaseManager.add_tenant_to_settings(request.tenant)
                        
                        # Use the correct tenant database for owner employee record
                        db_alias = f"tenant_{request.tenant.id}"
                        
                        # Try to get or create employee record for owner in tenant database
                        employee, created = Employee.objects.using(db_alias).get_or_create(
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
                from apps.core.database_router import TenantDatabaseManager
                
                # Ensure tenant database is registered in settings
                if hasattr(request, 'tenant') and request.tenant:
                    TenantDatabaseManager.add_tenant_to_settings(request.tenant)
                    
                    # Use the correct tenant database
                    db_alias = f"tenant_{request.tenant.id}"
                    
                    # FIX: Use user_id and tenant-specific database for cross-schema compatibility
                    employee = Employee.objects.using(db_alias).get(user_id=request.user.id, is_active=True)
                else:
                    # Fallback to default database if no tenant (shouldn't happen)
                    employee = Employee.objects.get(user_id=request.user.id, is_active=True)
                
                if not employee.is_active:
                    return render(request, 'errors/access_denied.html', {
                        'title': 'Account Inactive',
                        'message': 'Your employee account is inactive.',
                        'business': getattr(request, 'tenant', None),
                        'employee': employee,
                    }, status=403)
                
                if not employee.can_login:
                    return render(request, 'errors/access_denied.html', {
                        'title': 'Login Disabled',
                        'message': 'Your login access has been disabled. Please contact your manager.',
                        'business': getattr(request, 'tenant', None),
                        'employee': employee,
                    }, status=403)
                
                if employee.status == 'suspended':
                    return render(request, 'suspension/employee_suspended.html', {
                        'suspension_type': 'employee',
                        'business': getattr(request, 'tenant', None),
                        'employee': employee,
                        'title': 'Employee Account Suspended',
                        'message': f'Your employee account has been suspended.',
                    })
                
                if employee.status not in ['active']:
                    return render(request, 'errors/access_denied.html', {
                        'title': 'Account Not Active',
                        'message': f'Your account status is "{employee.get_status_display()}". Only active employees can access the system.',
                        'business': getattr(request, 'tenant', None),
                        'employee': employee,
                    }, status=403)
                
                if roles and employee.role not in roles:
                    return render(request, 'errors/access_denied.html', {
                        'title': 'Insufficient Permissions',
                        'message': f'You need {" or ".join(roles)} role to access this page. Your current role is "{employee.get_role_display()}".',
                        'business': getattr(request, 'tenant', None),
                        'employee': employee,
                    }, status=403)
                
                request.employee = employee
                return view_func(request, *args, **kwargs)
                
            except Employee.DoesNotExist:
                return render(request, 'errors/access_denied.html', {
                    'title': 'Not an Employee',
                    'message': 'You are not registered as an employee in this business.',
                    'business': getattr(request, 'tenant', None),
                }, status=403)
                
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
    @suspension_check_required
    def _wrapped_view(request, *args, **kwargs):
        try:
            if not request.business.subscription:
                messages.warning(request, 'This business does not have a subscription. Please contact support.')
                business_slug = getattr(request, 'business_slug', request.business.slug)
                return redirect(f'/business/{business_slug}/subscriptions/upgrade/')
            
            subscription = request.business.subscription
            
            # Check for suspended subscription (handled by suspension_check_required but double-check)
            if subscription.status == 'suspended':
                return render(request, 'suspension/subscription_suspended.html', {
                    'suspension_type': 'subscription',
                    'business': request.business,
                    'subscription': subscription,
                    'title': 'Subscription Suspended',
                    'message': f'The subscription for "{request.business.name}" has been suspended.',
                    'reason': getattr(subscription, 'cancellation_reason', 'Payment issues or policy violation'),
                })
            
            # Check for inactive subscription
            if not subscription.is_active:
                messages.warning(request, 'Your subscription is not active. Please renew to continue using the service.')
                business_slug = getattr(request, 'business_slug', request.business.slug)
                return redirect(f'/business/{business_slug}/subscriptions/upgrade/')
        
        except Exception as e:
            # Handle database errors gracefully (e.g., missing subscription table)
            print(f"Warning: Could not check subscription for business {request.business.slug}: {e}")
            messages.warning(request, 'Unable to verify subscription status. Please contact support if you encounter issues.')
        
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