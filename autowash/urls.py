from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.shortcuts import redirect
from django.http import HttpResponseRedirect, HttpResponse

from apps.core.views import health_check

admin.site.site_header = "Autowash System Administration"
admin.site.site_title = "System Admin"
admin.site.index_title = "System Administration Panel"

def root_redirect(request):
    """Smart root redirect based on user authentication and business context"""
    print(f"\n" + "="*50)
    print(f"ROOT REDIRECT CALLED")
    print(f"User authenticated: {request.user.is_authenticated}")
    print(f"User: {request.user if request.user.is_authenticated else 'Anonymous'}")
    print(f"Current path: {request.path}")
    print(f"Original path: {getattr(request, 'original_path', 'Not set')}")
    print(f"Business context: {getattr(request, 'business', None)}")
    print(f"="*50)
    
    if hasattr(request, 'business') and request.business:
        print(f"Already in business context: {request.business.name}")
        print(f"This should be handled by business views, not root redirect")
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
        print(f"User not authenticated, redirecting to public")
        return HttpResponseRedirect('/public/')
    
    try:
        if request.user.is_authenticated:
            try:
                from apps.core.tenant_models import Tenant as Business
                business = Business.objects.filter(
                    owner=request.user
                ).select_related('owner').first()
                
                if business:
                    print(f"User business found: {business.name}")
                    print(f"Business verified: {business.is_verified}")
                    
                    # Check subscription status first
                    if not hasattr(business, 'subscription') or not business.subscription or not business.subscription.is_active:
                        # Business doesn't have an active subscription - redirect to subscription selection
                        print(f"Business has no active subscription, redirecting to subscription selection")
                        return HttpResponseRedirect('/subscriptions/select/')
                    
                    # Check verification status
                    if business.is_verified:
                        business_url = f'/business/{business.slug}/'
                        print(f"Redirecting to verified business: {business_url}")
                        return HttpResponseRedirect(business_url)
                    else:
                        print(f"Business not verified, redirecting to verification")
                        return HttpResponseRedirect('/auth/verification-pending/')
                else:
                    print(f"No business found, redirecting to business registration")
                    return HttpResponseRedirect('/auth/business/register/')
                    
            except Exception as e:
                print(f"Error checking business: {e}")
                return HttpResponseRedirect('/auth/dashboard/')
                
    except Exception as e:
        print(f"Root redirect error: {e}")
        return HttpResponseRedirect('/public/')

print("TENANT URLs configuration loaded (post-middleware)")

urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('admin/', admin.site.urls),
    path('system-admin/', include('apps.system_admin.urls')),
    
    path('auth/', include('apps.accounts.urls')),
    path('accounts/', include('allauth.urls')),
    
    path('contact/', TemplateView.as_view(template_name='public/contact.html'), name='contact'),
    
    path('public/', include([
        path('', TemplateView.as_view(template_name='public/landing.html'), name='public_landing'),
        path('pricing/', TemplateView.as_view(template_name='public/pricing.html'), name='public_pricing'),
        path('features/', TemplateView.as_view(template_name='public/features.html'), name='public_features'),
        path('contact/', TemplateView.as_view(template_name='public/contact.html'), name='public_contact'),
        path('about/', TemplateView.as_view(template_name='public/about.html'), name='public_about'),
    ])),
    
    path('customers/', include('apps.customers.urls')),
    path('business/', include('apps.businesses.urls')),
    path('employees/', include('apps.employees.urls')),
    path('services/', include('apps.services.urls')),
    path('inventory/', include('apps.inventory.urls')),
    path('suppliers/', include('apps.suppliers.urls')),
    path('subscriptions/', include('apps.subscriptions.urls')),
    path('payments/', include('apps.payments.urls')),
    path('reports/', include('apps.reports.urls')),
    path('expenses/', include('apps.expenses.urls')),
    path('notifications/', include('apps.notification.urls')),
    
    path('', root_redirect, name='root_redirect'),
]

if settings.DEBUG:
    try:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
        print("Debug toolbar URLs added to TENANT schema")
    except ImportError:
        print("Debug toolbar not available (not installed)")

    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)