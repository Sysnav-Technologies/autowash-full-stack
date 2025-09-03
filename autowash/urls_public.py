from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.shortcuts import redirect
from django.http import HttpResponseRedirect

from apps.core.views import health_check

def public_root_redirect(request):
    if request.user.is_authenticated:
        try:
            business = request.user.owned_tenants.first()
            if business and business.is_verified:
                return HttpResponseRedirect(f'/business/{business.slug}/')
            else:
                return HttpResponseRedirect('/auth/dashboard/')
        except:
            return HttpResponseRedirect('/auth/dashboard/')
    else:
        return HttpResponseRedirect('/public/')

# Public URL Configuration
urlpatterns = [
    # System health and administration
    path('health/', health_check, name='health_check'),
    path('admin/', admin.site.urls),
    path('system-admin/', include('apps.system_admin.urls')),
         
    # Authentication (public schema)
    path('auth/', include('apps.accounts.urls')),
    path('accounts/', include('allauth.urls')),
         
    # Public marketing pages
    path('public/', include([
        path('', TemplateView.as_view(template_name='public/landing.html'), name='landing'),
        path('pricing/', TemplateView.as_view(template_name='public/pricing.html'), name='pricing'),
        path('features/', TemplateView.as_view(template_name='public/features.html'), name='features'),
        path('contact/', TemplateView.as_view(template_name='public/contact.html'), name='contact'),
        path('about/', TemplateView.as_view(template_name='public/about.html'), name='about'),
    ])),
         
    # Subscriptions (public access)
    path('subscriptions/', include('apps.subscriptions.urls')),
         
    # Business tenant routing
    re_path(r'^business/(?P<slug>[\w-]+)/', include([
        path('', lambda request, slug: HttpResponseRedirect('/'), name='business_root'),
    ])),
         
    # Root redirect
    path('', public_root_redirect, name='public_root_redirect'),
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

# Static and media files (development only)
if not getattr(settings, 'RENDER', True) or settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)