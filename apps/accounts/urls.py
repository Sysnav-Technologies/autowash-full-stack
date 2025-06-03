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
    
    # Business
    path('business/register/', views.business_register_view, name='business_register'),
    path('business/settings/', views.business_settings_view, name='business_settings'),
    path('business/verification/', views.business_verification_view, name='business_verification'),
    
    # AJAX endpoints
    path('ajax/check-business-name/', views.check_business_name, name='check_business_name'),
    
    # Dashboard redirect
    path('dashboard/', views.dashboard_redirect, name='dashboard_redirect'),
]