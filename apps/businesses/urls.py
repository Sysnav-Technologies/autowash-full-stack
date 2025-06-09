from django.urls import path
from . import views

app_name = 'businesses'

urlpatterns = [
    # Main Dashboard
    path('', views.dashboard_view, name='dashboard'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    # Analytics
    path('analytics/', views.analytics_view, name='analytics'),
    
    # Goals Management
    path('goals/', views.goals_view, name='goals'),
    
    # Alerts Management
    path('alerts/', views.alerts_view, name='alerts'),
    path('alerts/<int:alert_id>/resolve/', views.resolve_alert, name='resolve_alert'),
    
    # API Endpoints
    path('api/dashboard-data/', views.api_dashboard_data, name='api_dashboard_data'),
    # Debug endpoints (for troubleshooting user role issues)
    path('debug/user-context/', views.debug_user_context, name='debug_user_context'),
    path('debug/fix-employee/', views.fix_user_employee_record, name='fix_user_employee'),
]