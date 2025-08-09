from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Authentication
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Email verification
    path('verify-email/<str:uidb64>/<str:token>/', views.verify_email, name='verify_email'),
    path('resend-verification/', views.resend_verification_email, name='resend_verification'),
    path('email-verification-sent/', views.email_verification_sent, name='email_verification_sent'),
    path('email-verification-success/', views.email_verification_success_view, name='email_verification_success'),

    # Password Reset
    path('password-reset/', views.password_reset_view, name='password_reset'),
    path('password-reset-done/', views.password_reset_done_view, name='password_reset_done'),
    path('password-reset-confirm/<str:uidb64>/<str:token>/', views.password_reset_confirm_view, name='password_reset_confirm'),
    path('password-reset-complete/', views.password_reset_complete_view, name='password_reset_complete'),
    
    # Password Change
    path('password/change/', views.password_change_view, name='password_change'),
    path('password/change/done/', views.password_change_done_view, name='password_change_done'),
    

    # Dashboard redirect
    path('dashboard/', views.dashboard_redirect, name='dashboard_redirect'),
    
    # Business management
    path('business/register/', views.business_register_view, name='business_register'),
    path('business/verification/', views.business_verification_view, name='business_verification'),
    path('business/settings/', views.business_settings_view, name='business_settings'),
    path('verification-pending/', views.verification_pending, name='verification_pending'),
    
    # User profile
    path('profile/', views.profile_view, name='profile'),
    path('profile/photo/', views.profile_photo_upload, name='profile_photo_upload'),
    
    # Business switching and management
    path('switch-business/', views.switch_business, name='switch_business'),
    path('business-dashboard/<slug:slug>/', views.business_dashboard_redirect, name='business_dashboard_redirect'),
    
    # AJAX endpoints
    path('api/check-verification/', views.check_verification_status, name='check_verification_status'),
    path('api/check-business-name/', views.check_business_name, name='check_business_name'),
    path('api/notifications/check/', views.check_notifications_api, name='check_notifications'),
    path('business/register/api/notifications/check/', views.check_notifications_api, name='register_check_notifications'),
    path('api/business-info/<slug:slug>/', views.business_info_api, name='business_info_api'),
    
    # Admin functions - Legacy URL commented out for MySQL multi-tenant system
    # path('admin/create-schema/', views.create_business_schema, name='create_business_schema'),
]