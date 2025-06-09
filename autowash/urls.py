# autowash/urls.py - Main URLs for TENANT schema (after middleware strips business prefix)
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.shortcuts import redirect
from django.http import HttpResponseRedirect, HttpResponse

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
    
    # IMPORTANT: If we're already in a business context (tenant schema), 
    # show the business dashboard
    if hasattr(request, 'business') and request.business:
        print(f"Already in business context: {request.business.name}")
        print(f"This should be handled by business views, not root redirect")
        # Import and call the business dashboard view directly
        try:
            from apps.businesses.views import dashboard_view
            return dashboard_view(request)
        except ImportError:
            # Fallback if businesses app doesn't have dashboard_view
            from django.template.response import TemplateResponse
            return TemplateResponse(request, 'businesses/dashboard.html', {
                'business': request.business,
                'title': 'Business Dashboard'
            })
    
    try:
        if request.user.is_authenticated:
            # Check if user owns a business
            try:
                business = request.user.owned_businesses.first()
                if business:
                    print(f"User business found: {business.name}")
                    print(f"Business verified: {business.is_verified}")
                    
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
        else:
            print(f"User not authenticated, redirecting to public")
            return HttpResponseRedirect('/public/')
    except Exception as e:
        print(f"Root redirect error: {e}")
        # Fallback in case of any errors
        return HttpResponseRedirect('/public/')

# IMPORTANT: These URLs are for TENANT schemas AFTER the middleware has stripped the business prefix
# So /business/eldo-wash/customers/ becomes /customers/ by the time it reaches here
print("🏢 TENANT URLs configuration loaded (post-middleware)")

urlpatterns = [
    # Admin for tenants  
    path('admin/', admin.site.urls),
    
    # Authentication (tenant-specific but accessible from tenant context)
    path('auth/', include('apps.accounts.urls')),
    path('accounts/', include('allauth.urls')),
    
    # Business management apps - these paths are AFTER business prefix is stripped
    # So /business/eldo-wash/customers/ becomes /customers/
    path('customers/', include('apps.customers.urls')),
    path('business/', include('apps.businesses.urls')),
    path('employees/', include('apps.employees.urls')),
    path('services/', include('apps.services.urls')),
    path('inventory/', include('apps.inventory.urls')),
    path('suppliers/', include('apps.suppliers.urls')),
    path('payments/', include('apps.payments.urls')),
    path('reports/', include('apps.reports.urls')),
    # path('expenses/', include('apps.expenses.urls')),
    path('notifications/', include('apps.notification.urls')),
    
    # # Business dashboard and settings
    # path('dashboard/', include('apps.businesses.urls')),  # If you have separate dashboard URLs
    # path('settings/', include('apps.businesses.settings_urls')),  # If you have settings URLs
    
    # API endpoints (if needed in tenant context)   
    # path('api/', include('apps.core.api_urls')),
    
    # Root path for business dashboard - this handles /business/slug/ -> /
    path('', root_redirect, name='root_redirect'),
]

# Debug Toolbar - Only when debugging is enabled
if settings.DEBUG:
    try:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
        print("🐛 Debug toolbar URLs added to TENANT schema")
    except ImportError:
        print("⚠️ Debug toolbar not available (not installed)")

# Serve media files when in local development or when debugging on Render
if not getattr(settings, 'RENDER', True) or settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)