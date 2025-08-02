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
                # Check tenant membership
                try:
                    from apps.core.tenant_models import TenantUser
                    membership = TenantUser.objects.get(tenant=tenant, user=request.user, is_active=True)
                    context['user_role'] = membership.role
                    context['is_owner'] = membership.role == 'owner'
                    context['is_admin'] = membership.role in ['owner', 'admin']
                    context['is_manager'] = membership.role in ['owner', 'admin', 'manager']
                except:
                    context['user_role'] = None
                    context['is_owner'] = False
                    context['is_admin'] = False
                    context['is_manager'] = False
        else:
            # Public context - no specific role
            context['user_role'] = None
            context['is_owner'] = False
            context['is_admin'] = False
            context['is_manager'] = False
    else:
        context['user'] = AnonymousUser()
        context['is_authenticated'] = False
        context['user_role'] = None
        context['is_owner'] = False
        context['is_admin'] = False
        context['is_manager'] = False
    
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
