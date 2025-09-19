from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.shortcuts import redirect
from django.http import HttpResponseRedirect, HttpResponse

from apps.core.views import health_check, serve_legal_document

admin.site.site_header = "Autowash System Administration"
admin.site.site_title = "System Admin"
admin.site.index_title = "System Administration Panel"

def root_redirect(request):
    if hasattr(request, 'business') and request.business:
        try:
            from apps.businesses.views import dashboard_view
            return dashboard_view(request)
        except ImportError:
            from django.template.response import TemplateResponse
            return TemplateResponse(request, 'businesses/dashboard.html', {
                'business': request.business,
                'title': 'Business Dashboard'
            })
    
    if not request.user.is_authenticated:
        return HttpResponseRedirect('/public/')
    
    if request.user.is_superuser:
        return HttpResponseRedirect('/system-admin/')
    try:
        if request.user.is_authenticated:
            try:
                from apps.core.tenant_models import Tenant as Business
                business = Business.objects.filter(
                    owner=request.user
                ).select_related('owner').first()
                
                if business:
                    if not hasattr(business, 'subscription') or not business.subscription:
                        return HttpResponseRedirect('/subscriptions/select/')
                    elif business.subscription and not business.subscription.is_active:
                        return HttpResponseRedirect(f'/business/{business.slug}/subscriptions/upgrade/')
                    
                    if business.is_verified:
                        business_url = f'/business/{business.slug}/'
                        return HttpResponseRedirect(business_url)
                    else:
                        return HttpResponseRedirect('/auth/verification-pending/')
                else:
                    try:
                        verified_tenants = Business.objects.filter(is_verified=True, is_active=True)
                        
                        for tenant in verified_tenants:
                            try:
                                from apps.employees.models import Employee
                                from apps.core.database_router import TenantDatabaseManager
                                
                                TenantDatabaseManager.add_tenant_to_settings(tenant)
                                db_alias = f"tenant_{tenant.id}"
                                
                                employee = Employee.objects.using(db_alias).filter(
                                    user_id=request.user.id, 
                                    is_active=True
                                ).first()
                                
                                if employee:
                                    business_url = _get_employee_redirect_url(tenant.slug, employee.role)
                                    return HttpResponseRedirect(business_url)
                                        
                            except Exception:
                                continue
                                
                    except Exception:
                        pass
                    
                    return HttpResponseRedirect('/auth/business/register/')
                    
            except Exception:
                return HttpResponseRedirect('/auth/dashboard/')
                
    except Exception:
        return HttpResponseRedirect('/public/')

def _get_employee_redirect_url(tenant_slug, role):
    """Get appropriate redirect URL based on employee role"""
    role_urls = {
        'owner': f'/business/{tenant_slug}/',
        'manager': f'/business/{tenant_slug}/',
        'supervisor': f'/business/{tenant_slug}/services/',
        'attendant': f'/business/{tenant_slug}/services/dashboard/',
        'cleaner': f'/business/{tenant_slug}/employees/dashboard/',
        'cashier': f'/business/{tenant_slug}/payments/',
    }
    return role_urls.get(role, f'/business/{tenant_slug}/employees/dashboard/')

# URL Configuration
urlpatterns = [
    # Health check and administration
    path('health/', health_check, name='health_check'),
    path('admin/', admin.site.urls),
    path('system-admin/', include('apps.system_admin.urls')),
    
    # Core app URLs (PWA, manifest, etc.)
    path('', include('apps.core.urls', namespace='core')),
    
    # Authentication and accounts
    path('auth/', include('apps.accounts.urls')),
    path('accounts/', include('allauth.urls')),
    
    # Public pages
    path('public/', include([
        path('', TemplateView.as_view(template_name='public/landing.html'), name='public_landing'),
        path('pricing/', TemplateView.as_view(template_name='public/pricing.html'), name='public_pricing'),
        path('features/', TemplateView.as_view(template_name='public/features.html'), name='public_features'),
        path('contact/', TemplateView.as_view(template_name='public/contact.html'), name='public_contact'),
        path('about/', TemplateView.as_view(template_name='public/about.html'), name='public_about'),
    ])),
    
    # Business management and tenant URLs
    path('business/', include('apps.businesses.urls')),
    path('subscriptions/', include('apps.subscriptions.urls')),
    
    # Application URLs (tenant-specific)
    path('customers/', include('apps.customers.urls')),
    path('employees/', include('apps.employees.urls')),
    path('services/', include('apps.services.urls')),
    path('inventory/', include('apps.inventory.urls')),
    path('suppliers/', include('apps.suppliers.urls')),
    path('payments/', include('apps.payments.urls')),
    path('reports/', include('apps.reports.urls')),
    path('expenses/', include('apps.expenses.urls')),
    path('notifications/', include('apps.notification.urls')),
    path('messaging/', include('messaging.urls')),
    
    # Legal documents and contact
    path('contact/', TemplateView.as_view(template_name='public/contact.html'), name='contact'),
    path('legal/<str:document_name>/', serve_legal_document, name='serve_legal_document'),
    
    # Root redirect
    path('', root_redirect, name='root_redirect'),
]

# Development settings
if settings.DEBUG:
    try:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass

# Static and media files
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)