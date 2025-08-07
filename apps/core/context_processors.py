"""
Context processors for MySQL multi-tenant system
"""
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import AnonymousUser


def business_context(request):
    """Add business context to templates with MySQL multi-tenant routing"""
    context = {
        'tenant': getattr(request, 'tenant', None),
        'business': getattr(request, 'tenant', None),  # For backward compatibility
        'business_slug': getattr(request, 'tenant_slug', None),
        'current_year': timezone.now().year,
        'app_name': 'Autowash',
        'company_name': 'Autowash Technologies',
        'is_tenant_context': hasattr(request, 'tenant') and request.tenant is not None,
        'tenant_urls': {},
        'nav_urls': {},
    }
    
    # Add tenant-specific context if we're in a tenant context
    if hasattr(request, 'tenant') and request.tenant:
        tenant = request.tenant
        slug = tenant.slug
        
        # Check if business is verified
        is_verified = getattr(tenant, 'is_verified', False)
        
        context.update({
            'business_name': tenant.name,
            'business_logo': tenant.logo.url if tenant.logo else None,
            'business_phone': tenant.phone,
            'business_email': tenant.email,
            'business_timezone': getattr(tenant, 'timezone', 'Africa/Nairobi'),
            'business_verified': is_verified,
            'business_slug': tenant.slug,
            'business_url_prefix': f'/business/{tenant.slug}',
            'tenant_subdomain': tenant.subdomain,
            'tenant_primary_domain': tenant.primary_domain,
        })
        
        # Generate tenant-aware URLs
        context['tenant_urls'] = {
            'dashboard': f'/business/{slug}/',
            'services': f'/business/{slug}/services/',
            'pos_dashboard': f'/business/{slug}/services/dashboard/',
            'customers': f'/business/{slug}/customers/',
            'employees': f'/business/{slug}/employees/',
            'inventory': f'/business/{slug}/inventory/',
            'reports': f'/business/{slug}/reports/',
            'payments': f'/business/{slug}/payments/',
            'settings': f'/business/{slug}/businesses/settings/',
            'settings_overview': f'/business/{slug}/businesses/settings/',
        }
        
        # Navigation URLs
        base_url = f'/business/{slug}'
        context['nav_urls'] = {
            'home': f'{base_url}/',
            'services': {
                'list': f'{base_url}/services/',
                'create': f'{base_url}/services/create/',
                'dashboard': f'{base_url}/services/dashboard/',
                'pos': f'{base_url}/services/dashboard/',
            },
            'customers': {
                'list': f'{base_url}/customers/',
                'create': f'{base_url}/customers/create/',
            },
            'employees': {
                'list': f'{base_url}/employees/',
                'create': f'{base_url}/employees/create/',
            },
            'inventory': {
                'list': f'{base_url}/inventory/',
                'create': f'{base_url}/inventory/create/',
            },
            'reports': {
                'dashboard': f'{base_url}/reports/',
                'revenue': f'{base_url}/reports/revenue/',
                'services': f'{base_url}/reports/services/',
            },
            'payments': f'{base_url}/payments/',
            'settings': f'{base_url}/businesses/settings/',
        }
        
        # Add verification status if not verified
        if not is_verified:
            try:
                verification = tenant.verification
                context.update({
                    'verification_status': verification.status,
                    'verification_submitted': verification.submitted_at,
                })
            except:
                context.update({
                    'verification_status': 'pending',
                    'verification_submitted': None,
                })
    else:
        # Public context
        context.update({
            'business_url_prefix': '',
            'is_public_context': True,
        })
    
    return context


def user_role_context(request):
    """Add user role context for tenant"""
    context = {}
    
    if hasattr(request, 'user') and request.user.is_authenticated:
        context['user'] = request.user
        context['is_authenticated'] = True
        
        # Check if user is in tenant context
        if hasattr(request, 'tenant') and request.tenant:
            tenant = request.tenant
            
            # Check if user is owner
            if tenant.owner == request.user:
                context['user_role'] = 'owner'
                context['is_owner'] = True
                context['is_admin'] = True
                context['is_manager'] = True
            else:
                # Check if user is an employee
                try:
                    from apps.employees.models import Employee
                    from apps.core.database_router import TenantDatabaseManager
                    
                    # Ensure tenant database is registered
                    db_alias = f"tenant_{tenant.id}"
                    TenantDatabaseManager.add_tenant_to_settings(tenant)
                    
                    employee = Employee.objects.using(db_alias).filter(
                        user_id=request.user.id, 
                        is_active=True
                    ).first()
                    
                    if employee:
                        context['user_role'] = employee.role
                        context['is_owner'] = employee.role == 'owner'
                        context['is_admin'] = employee.role in ['owner', 'manager']
                        context['is_manager'] = employee.role in ['owner', 'manager']
                        context['is_attendant'] = employee.role == 'attendant'
                        context['is_supervisor'] = employee.role == 'supervisor'
                        context['is_cashier'] = employee.role == 'cashier'
                        context['is_cleaner'] = employee.role == 'cleaner'
                        context['employee'] = employee
                    else:
                        context['user_role'] = None
                        context['is_owner'] = False
                        context['is_admin'] = False
                        context['is_manager'] = False
                        context['is_attendant'] = False
                        context['is_supervisor'] = False
                        context['is_cashier'] = False
                        context['is_cleaner'] = False
                        context['employee'] = None
                except Exception as e:
                    # Handle database connection errors gracefully
                    context['user_role'] = None
                    context['is_owner'] = False
                    context['is_admin'] = False
                    context['is_manager'] = False
                    context['is_attendant'] = False
                    context['is_supervisor'] = False
                    context['is_cashier'] = False
                    context['is_cleaner'] = False
                    context['employee'] = None
        else:
            # Public context - no specific role
            context['user_role'] = None
            context['is_owner'] = False
            context['is_admin'] = False
            context['is_manager'] = False
            context['is_attendant'] = False
            context['is_supervisor'] = False
            context['is_cashier'] = False
            context['is_cleaner'] = False
            context['employee'] = None
    else:
        context['user'] = AnonymousUser()
        context['is_authenticated'] = False
        context['user_role'] = None
        context['is_owner'] = False
        context['is_admin'] = False
        context['is_manager'] = False
        context['is_attendant'] = False
        context['is_supervisor'] = False
        context['is_cashier'] = False
        context['is_cleaner'] = False
        context['employee'] = None
    
    return context


def navigation_context(request):
    """Add navigation context"""
    context = {
        'current_path': request.path,
        'current_path_name': request.resolver_match.url_name if request.resolver_match else None,
    }
    
    # Add tenant-specific navigation
    if hasattr(request, 'tenant') and request.tenant:
        tenant = request.tenant
        context.update({
            'nav_dashboard_url': f'/business/{tenant.slug}/',
            'nav_customers_url': f'/business/{tenant.slug}/customers/',
            'nav_employees_url': f'/business/{tenant.slug}/employees/',
            'nav_services_url': f'/business/{tenant.slug}/services/',
            'nav_inventory_url': f'/business/{tenant.slug}/inventory/',
            'nav_reports_url': f'/business/{tenant.slug}/reports/',
            'nav_payments_url': f'/business/{tenant.slug}/payments/',
            'nav_settings_url': f'/business/{tenant.slug}/settings/',
        })
    else:
        # Public navigation
        context.update({
            'nav_home_url': '/',
            'nav_login_url': '/accounts/login/',
            'nav_register_url': '/accounts/register/',
            'nav_about_url': '/about/',
        })
    
    return context


def notifications_context(request):
    """Add notifications context"""
    context = {
        'notifications': [],
        'unread_count': 0,
    }
    
    if hasattr(request, 'user') and request.user.is_authenticated:
        # Add user notifications logic here
        pass
    
    return context


def performance_context(request):
    """Add performance monitoring context"""
    context = {
        'debug_mode': settings.DEBUG,
        'environment': 'development' if settings.DEBUG else 'production',
    }
    
    if settings.DEBUG:
        context.update({
            'database_queries_enabled': True,
            'template_debug': True,
        })
    
    return context


def verification_context(request):
    """Add verification context for businesses"""
    context = {}
    
    if hasattr(request, 'tenant') and request.tenant:
        tenant = request.tenant
        
        context.update({
            'business_verified': tenant.is_verified,
            'verification_required': not tenant.is_verified,
        })
        
        # Add verification details if available
        try:
            verification = tenant.verification
            context.update({
                'verification_status': verification.status,
                'verification_submitted_at': verification.submitted_at,
                'verification_notes': verification.notes,
            })
        except:
            context.update({
                'verification_status': 'pending',
                'verification_submitted_at': None,
                'verification_notes': '',
            })
    
    return context


def subscription_flow_context(request):
    """Add subscription flow context for onboarding"""
    context = {
        'flow_step': 'unknown',
        'flow_completed': False,
        'flow_progress': 0,
        'subscription_active': False,
        'subscription_required': True,
    }
    
    if hasattr(request, 'user') and request.user.is_authenticated:
        try:
            from apps.accounts.models import Business
            business = Business.objects.get(owner=request.user)
            
            # Step 1: Business Registration - Always completed if we have a business
            registration_completed = True
            
            # Step 2: Subscription Selection/Payment
            subscription_completed = False
            if hasattr(business, 'subscription') and business.subscription and business.subscription.is_active:
                subscription_completed = True
                context['subscription_active'] = True
            else:
                context['subscription_active'] = False
                
            # Step 3: Verification
            verification_completed = business.is_verified
            
            # Determine current step and progress
            if not registration_completed:
                context['flow_step'] = 'registration'
                context['flow_progress'] = 0
            elif not subscription_completed:
                context['flow_step'] = 'subscription'
                context['flow_progress'] = 25
            elif not verification_completed:
                context['flow_step'] = 'verification'
                context['flow_progress'] = 50
            else:
                context['flow_step'] = 'completed'
                context['flow_progress'] = 100
                context['flow_completed'] = True
                
            # Add step completion status
            context.update({
                'registration_completed': registration_completed,
                'subscription_completed': subscription_completed,
                'verification_completed': verification_completed,
                'business_name': business.name,
                'business_subdomain': business.subdomain,
            })
            
        except:
            # No business found - user needs to register
            context.update({
                'flow_step': 'registration',
                'flow_progress': 0,
                'registration_completed': False,
                'subscription_completed': False,
                'verification_completed': False,
            })
    
    return context


def sidebar_context(request):
    """Add sidebar-specific context variables"""
    context = {}
    
    # Only add sidebar context for authenticated users in tenant context
    if (hasattr(request, 'user') and request.user.is_authenticated and 
        hasattr(request, 'tenant') and request.tenant):
        
        try:
            # Get pending orders count
            from apps.services.models import ServiceOrder
            from apps.core.database_router import TenantDatabaseManager
            
            db_alias = f"tenant_{request.tenant.id}"
            TenantDatabaseManager.add_tenant_to_settings(request.tenant)
            
            pending_orders_count = ServiceOrder.objects.using(db_alias).filter(
                status='pending'
            ).count()
            
            active_queue_count = 0
            try:
                from apps.services.models import ServiceQueue
                active_queue_count = ServiceQueue.objects.using(db_alias).filter(
                    status__in=['waiting', 'in_service']
                ).count()
            except:
                pass
            
            # Get active shifts count
            active_shifts_count = 0
            try:
                from apps.businesses.models import Shift
                active_shifts_count = Shift.objects.using(db_alias).filter(
                    status='active'
                ).count()
            except:
                pass
            
            # Get pending payments count
            pending_payments = 0
            try:
                from apps.payments.models import Payment
                pending_payments = Payment.objects.using(db_alias).filter(
                    status='pending'
                ).count()
            except:
                pass
            
            # Get pending employee requests count
            pending_employee_requests = 0
            try:
                from apps.employees.models import Employee
                pending_employee_requests = Employee.objects.using(db_alias).filter(
                    status='pending'
                ).count()
            except:
                pass
            
            context.update({
                'pending_orders_count': pending_orders_count,
                'active_queue_count': active_queue_count,
                'active_shifts_count': active_shifts_count,
                'pending_payments': pending_payments,
                'pending_employee_requests': pending_employee_requests,
            })
            
        except Exception as e:
            # Handle any database errors gracefully
            context.update({
                'pending_orders_count': 0,
                'active_queue_count': 0,
                'active_shifts_count': 0,
                'pending_payments': 0,
                'pending_employee_requests': 0,
            })
    
    return context


def user_role_context(request):
    """
    Add user role context to templates
    """
    context = {
        'user_role': None,
        'is_owner': False,
        'is_manager': False,
        'is_supervisor': False,
        'is_attendant': False,
        'is_cleaner': False,
        'is_cashier': False,
        'can_access_dashboard': False,
        'can_manage_employees': False,
        'can_manage_services': False,
        'can_view_reports': False,
    }
    
    if hasattr(request, 'employee') and request.employee:
        role = request.employee.role
        context.update({
            'user_role': role,
            'is_owner': role == 'owner',
            'is_manager': role == 'manager',
            'is_supervisor': role == 'supervisor',
            'is_attendant': role == 'attendant',
            'is_cleaner': role == 'cleaner',
            'is_cashier': role == 'cashier',
        })
        
        # Role-based permissions
        if role in ['owner', 'manager']:
            context.update({
                'can_access_dashboard': True,
                'can_manage_employees': True,
                'can_manage_services': True,
                'can_view_reports': True,
            })
        elif role == 'supervisor':
            context.update({
                'can_access_dashboard': False,
                'can_manage_employees': False,
                'can_manage_services': True,
                'can_view_reports': True,
            })
        elif role in ['attendant', 'cleaner', 'cashier']:
            context.update({
                'can_access_dashboard': False,
                'can_manage_employees': False,
                'can_manage_services': False,
                'can_view_reports': False,
            })
    
    return context
