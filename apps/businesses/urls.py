from django.urls import path
from . import views
from apps.accounts.views import profile_view

app_name = 'businesses'

urlpatterns = [
    # Main Dashboard
    path('', views.dashboard_view, name='dashboard'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('profile/', profile_view, name='profile'),

    
    # Analytics
    path('analytics/', views.analytics_view, name='analytics'),
    
    # Goals Management
    path('goals/', views.goals_view, name='goals'),
    
    # Alerts Management
    path('alerts/', views.alerts_view, name='alerts'),
    path('alerts/<int:alert_id>/resolve/', views.resolve_alert, name='resolve_alert'),
    
    # API Endpoints
    path('api/dashboard-data/', views.dashboard_data_api, name='api_dashboard_data'),
    # Debug endpoints 
    path('debug/user-context/', views.debug_user_context, name='debug_user_context'),
    path('debug/fix-employee/', views.fix_user_employee_record, name='fix_user_employee'),

    # Settings 
    path('settings/', views.settings_overview, name='settings_overview'),
    path('settings/business/', views.business_settings_view, name='business_settings'),
    path('settings/services/', views.service_settings_view, name='service_settings'),
    path('settings/payment/', views.payment_settings_view, name='payment_settings'),
    path('settings/notifications/', views.notification_settings_view, name='notification_settings'),
    path('settings/integrations/', views.integration_settings_view, name='integration_settings'),
    path('settings/backup/', views.backup_settings_view, name='backup_settings'),
    path('settings/security/', views.security_settings_view, name='security_settings'),
    path('settings/users/', views.user_management_view, name='user_management'),

    # Subscription Management
    path('subscription/', views.subscription_overview, name='subscription_overview'),
    path('subscription/overview/', views.subscription_overview, name='subscription_overview'),
    path('subscription/billing/', views.billing_history, name='billing_history'),
    path('subscription/payment-methods/', views.payment_methods, name='payment_methods'),
    path('subscription/usage/', views.usage_analytics, name='usage_analytics'),
    path('subscription/settings/', views.subscription_settings, name='subscription_settings'),

    # Settings API endpoints
    path('settings/api/backup/create/', views.create_backup_ajax, name='create_backup'),
    path('settings/api/backup/download/<str:backup_id>/', views.download_backup, name='download_backup'),
    path('settings/api/integrations/test/<str:integration>/', views.test_integration_ajax, name='test_integration'),
]