from django.urls import path
from . import views, views_shifts
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
    path('api/dashboard-data/', views.api_dashboard_data, name='api_dashboard_data'),
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

    # Settings API endpoints
    path('settings/api/backup/create/', views.create_backup_ajax, name='create_backup'),
    path('settings/api/backup/download/<str:backup_id>/', views.download_backup, name='download_backup'),
    path('settings/api/integrations/test/<str:integration>/', views.test_integration_ajax, name='test_integration'),
    
    # Shift Management (Business Owners/Managers only)
    path('shifts/', views_shifts.shift_list_view, name='shifts'),
    path('shifts/create/', views_shifts.shift_create_view, name='shift_create'),
    path('shifts/<uuid:shift_id>/', views_shifts.shift_detail_view, name='shift_detail'),
    path('shifts/<uuid:shift_id>/edit/', views_shifts.shift_edit_view, name='shift_edit'),
    path('shifts/<uuid:shift_id>/end/', views_shifts.end_shift_ajax, name='end_shift'),
    path('shifts/<uuid:shift_id>/attendance/', views_shifts.shift_attendance_view, name='shift_attendance'),
    path('shifts/my-stats/', views_shifts.attendant_shift_statistics, name='attendant_shift_stats'),
    
    # Shift Management API
    path('api/shifts/check-in/', views_shifts.check_in_ajax, name='shift_check_in'),
    path('api/shifts/check-out/', views_shifts.check_out_ajax, name='shift_check_out'),
    path('api/shifts/break-start/', views_shifts.break_start_ajax, name='shift_break_start'),
    path('api/shifts/break-end/', views_shifts.break_end_ajax, name='shift_break_end'),
    path('api/shifts/current/', views_shifts.current_shift_ajax, name='current_shift'),
    path('api/shifts/active/', views_shifts.active_shifts_ajax, name='active_shifts'),
]