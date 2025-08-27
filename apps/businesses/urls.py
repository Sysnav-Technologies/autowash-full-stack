from django.urls import path, include
from . import views
from . import views_tenant_settings as settings_views
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

    # Settings - Production System
    path('settings/', settings_views.settings_overview, name='settings_overview'),
    path('settings/business/', settings_views.business_settings_view, name='business_settings'),
    path('settings/services/', settings_views.service_settings_view, name='service_settings'),
    path('settings/payment/', settings_views.payment_settings_view, name='payment_settings'),
    path('settings/notifications/', settings_views.notification_settings_view, name='notification_settings'),
    path('settings/features/', settings_views.feature_settings_view, name='feature_settings'),
    path('settings/hours/', settings_views.business_hours_view, name='business_hours'),
    path('settings/backup/', settings_views.backup_settings_view, name='backup_settings'),

    # Subscription Management - Include from subscriptions app
    path('subscriptions/', include('apps.subscriptions.urls')),

    # Settings API endpoints
    path('settings/api/backup/create/', settings_views.create_backup_api, name='create_backup_api'),
    path('settings/api/backup/<str:backup_id>/download/', settings_views.download_backup, name='download_backup'),
    path('settings/api/backup/<str:backup_id>/delete/', settings_views.delete_backup_api, name='delete_backup_api'),
    path('settings/export/', settings_views.export_settings, name='export_settings'),
    path('settings/api/backup/download/<str:backup_id>/', views.download_backup, name='download_backup'),
    path('settings/api/integrations/test/<str:integration>/', views.test_integration_ajax, name='test_integration'),
]