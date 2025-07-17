from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Authentication
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Password Reset
    path('password-reset/', views.password_reset_view, name='password_reset'),
    
    # Dashboard redirect
    path('dashboard/', views.dashboard_redirect, name='dashboard_redirect'),
    
    # Business management
    path('business/register/', views.business_register_view, name='business_register'),
    path('business/verification/', views.business_verification_view, name='business_verification'),
    path('business/settings/', views.business_settings_view, name='business_settings'),
    path('verification-pending/', views.verification_pending, name='verification_pending'),
    
    # User profile
    path('profile/', views.profile_view, name='profile'),
    
    # Business switching and management
    path('switch-business/', views.switch_business, name='switch_business'),
    path('business-dashboard/<slug:slug>/', views.business_dashboard_redirect, name='business_dashboard_redirect'),
    
    # AJAX endpoints
    path('api/check-verification/', views.check_verification_status, name='check_verification_status'),
    path('api/check-business-name/', views.check_business_name, name='check_business_name'),
    path('api/business-info/<slug:slug>/', views.business_info_api, name='business_info_api'),
    
    # Admin functions
    path('admin/create-schema/', views.create_business_schema, name='create_business_schema'),
]