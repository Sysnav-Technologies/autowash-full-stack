# autowash/urls_public.py - Public schema URLs (completely separate from tenant URLs)
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.shortcuts import redirect
from django.http import HttpResponseRedirect

from apps.core.views import health_check

def public_root_redirect(request):
    """Handle root redirects for public schema"""
    print("[PUBLIC] PUBLIC ROOT REDIRECT")
         
    if request.user.is_authenticated:
        # User is logged in but in public schema - redirect to their business or dashboard
        try:
            business = request.user.owned_businesses.first()
            if business and business.is_verified:
                return HttpResponseRedirect(f'/business/{business.slug}/')
            else:
                return HttpResponseRedirect('/auth/dashboard/')
        except:
            return HttpResponseRedirect('/auth/dashboard/')
    else:
        # Anonymous user - show public landing
        return HttpResponseRedirect('/public/')

print("[PUBLIC] PUBLIC URLs configuration loaded")

urlpatterns = [
    # Health
    path('health/', health_check, name='health_check'),
    # Public admin (system-wide)
    path('system-admin/', admin.site.urls),
         
    # Authentication and account management (public schema)
    path('auth/', include('apps.accounts.urls')),
    path('accounts/', include('allauth.urls')),
         
    # # Business registration and tenant creation (public schema)
    # path('business/', include('apps.businesses.public_urls')),  # Public business operations
         
    # Public pages (landing, marketing, etc.)
    path('public/', include([
        path('', TemplateView.as_view(template_name='public/landing.html'), name='landing'),
        path('pricing/', TemplateView.as_view(template_name='public/pricing.html'), name='pricing'),
        path('features/', TemplateView.as_view(template_name='public/features.html'), name='features'),
        path('contact/', TemplateView.as_view(template_name='public/contact.html'), name='contact'),
        path('about/', TemplateView.as_view(template_name='public/about.html'), name='about'),
    ])),
         
    # Subscriptions (public schema)
    path('subscriptions/', include('apps.subscriptions.urls')),
         
    # CRITICAL: Business path routing - this triggers the middleware
    # When someone visits /business/slug/, the middleware intercepts and switches tenant
    re_path(r'^business/(?P<slug>[\w-]+)/', include([
        # This is a placeholder - the middleware will handle the actual routing
        # by switching to tenant schema and stripping the business prefix
        path('', lambda request, slug: HttpResponseRedirect('/'), name='business_root'),
    ])),
         
    # API endpoints for public access
    # path('api/auth/', include('dj_rest_auth.urls')),
    # path('api/public/', include('apps.accounts.api_urls')),
         
    # Root redirect
    path('', public_root_redirect, name='public_root_redirect'),
]

# Debug Toolbar - Only when debugging is enabled
if settings.DEBUG:
    try:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
        print("[DEBUG] Debug toolbar URLs added to PUBLIC schema")
    except ImportError:
        print("[WARNING] Debug toolbar not available (not installed)")

# Serve media files when in local development or when debugging on Render
if not getattr(settings, 'RENDER', True) or settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)