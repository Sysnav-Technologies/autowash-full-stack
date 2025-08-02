from django.urls import path
from . import views

app_name = 'system_admin'

urlpatterns = [
    path('', views.system_dashboard, name='dashboard'),
    
    # Business Management
    path('businesses/', views.business_management, name='business_management'),
    path('approve/<uuid:business_id>/', views.approve_business, name='approve_business'),
    path('reject/<uuid:business_id>/', views.reject_business, name='reject_business'),
    path('businesses/bulk-approve/', views.bulk_approve_businesses, name='bulk_approve_businesses'),
    
    # Subscription Management
    path('subscriptions/', views.subscription_management, name='subscription_management'),
    path('subscription-plans/', views.subscription_plans, name='subscription_plans'),
    path('subscriptions/update-status/', views.update_subscription_status, name='update_subscription_status'),
    
    # Payment Management
    path('payments/', views.payment_management, name='payment_management'),
    
    # User Management
    path('users/', views.user_management, name='user_management'),
    
    # Analytics
    path('analytics/', views.system_analytics, name='analytics'),
    
    # Settings & Tools
    path('settings/', views.system_settings, name='system_settings'),
    path('export/', views.export_data, name='export_data'),
]
