from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    # Public admin
    path('system-admin/', admin.site.urls),
    
    # Public authentication
    path('auth/', include('apps.accounts.urls')),
    path('accounts/', include('allauth.urls')),
    
    
    # Landing pages
    path('', TemplateView.as_view(template_name='public/landing.html'), name='landing'),
    path('pricing/', TemplateView.as_view(template_name='public/pricing.html'), name='pricing'),
    path('features/', TemplateView.as_view(template_name='public/features.html'), name='features'),
    path('contact/', TemplateView.as_view(template_name='public/contact.html'), name='contact'),
    
    # Subscriptions
    path('subscriptions/', include('apps.subscriptions.urls')),
    
    # # API
    # path('api/auth/', include('dj_rest_auth.urls')),
    # path('api/public/', include('apps.accounts.api_urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    