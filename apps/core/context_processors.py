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
    }
    
    # Add tenant-specific context if we're in a tenant context
    if hasattr(request, 'tenant') and request.tenant:
        tenant = request.tenant
        
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
