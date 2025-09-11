from .views import health_check, manifest_view, offline_view, pwa_push_subscription, pwa_test_view
from django.urls import path

app_name = 'core'
urlpatterns = [
    path('health/', health_check, name='health_check'),
    
    # PWA URLs
    path('manifest.json', manifest_view, name='manifest'),
    path('offline/', offline_view, name='offline'),
    path('pwa-test/', pwa_test_view, name='pwa_test'),
    path('api/push-subscription/', pwa_push_subscription, name='pwa_push_subscription'),
]