from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Authentication
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Profile
    path('profile/', views.profile_view, name='profile'),
    
    # Business Registration & Verification
    path('business/register/', views.business_register_view, name='business_register'),
    path('business/verification/', views.business_verification_view, name='business_verification'),
    path('business/settings/', views.business_settings_view, name='business_settings'),
    
    # Verification Status
    path('verification-pending/', views.verification_pending, name='verification_pending'),
    
    # AJAX endpoints
    path('ajax/check-business-name/', views.check_business_name, name='check_business_name'),
    path('ajax/verification-status/', views.check_verification_status, name='check_verification_status'),
    
    # Dashboard redirect
    path('dashboard/', views.dashboard_redirect, name='dashboard_redirect'),
]