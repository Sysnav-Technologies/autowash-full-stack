from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # Authentication
    path('auth/', include('apps.accounts.urls')),
    path('accounts/', include('allauth.urls')),
    
    # API
    # path('api/auth/', include('dj_rest_auth.urls')),
    # path('api/', include('apps.core.api_urls')),
    
    # Main App URLs (Tenant-specific)
    path('', include('apps.businesses.urls')),
    path('employees/', include('apps.employees.urls')),
    path('customers/', include('apps.customers.urls')),
    path('services/', include('apps.services.urls')),
    path('inventory/', include('apps.inventory.urls')),
    path('suppliers/', include('apps.suppliers.urls')),
    path('payments/', include('apps.payments.urls')),
    path('reports/', include('apps.reports.urls')),
    # path('expenses/', include('apps.expenses.urls')),
    path('notifications/', include('apps.notification.urls')),
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