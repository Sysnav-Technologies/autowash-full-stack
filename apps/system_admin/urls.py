from django.urls import path
from . import views

app_name = 'system_admin'

urlpatterns = [
    path('', views.system_dashboard, name='dashboard'),
    
    # Business Management
    path('businesses/', views.business_management, name='business_management'),
    path('approve/<uuid:business_id>/', views.approve_business, name='approve_business'),
    path('reject/<uuid:business_id>/', views.reject_business, name='reject_business'),
    
    # Subscription Management
    path('subscriptions/', views.subscription_management, name='subscription_management'),
    path('subscription-plans/', views.subscription_plans, name='subscription_plans'),
    
    # Payment Management
    path('payments/', views.payment_management, name='payment_management'),
]
