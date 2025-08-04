from django.urls import path
from . import views

app_name = 'system_admin'

urlpatterns = [
    path('', views.system_dashboard, name='dashboard'),
    
    # Business Management
    path('businesses/', views.business_management, name='business_management'),
    path('businesses/<uuid:business_id>/edit/', views.edit_business, name='edit_business'),
    path('businesses/<uuid:business_id>/check-status/', views.check_tenant_database_status, name='check_tenant_status'),
    path('businesses/<uuid:business_id>/repair-setup/', views.repair_tenant_setup, name='repair_tenant_setup'),
    path('approve/<uuid:business_id>/', views.approve_business, name='approve_business'),
    path('reject/<uuid:business_id>/', views.reject_business, name='reject_business'),
    path('businesses/bulk-approve/', views.bulk_approve_businesses, name='bulk_approve_businesses'),
    path('businesses/bulk-reject/', views.bulk_reject_businesses, name='bulk_reject_businesses'),
    
    # Subscription Management
    path('subscriptions/', views.subscription_management, name='subscription_management'),
    path('subscription-plans/', views.subscription_plans, name='subscription_plans'),
    path('subscription-plans/create/', views.create_subscription_plan, name='create_subscription_plan'),
    path('subscription-plans/edit/<uuid:plan_id>/', views.edit_subscription_plan, name='edit_subscription_plan'),
    path('subscriptions/update-status/', views.update_subscription_status, name='update_subscription_status'),
    
    # Payment Management
    path('payments/', views.payment_management, name='payment_management'),
    path('payments/record/<uuid:subscription_id>/', views.record_payment, name='record_payment'),
    
    # Invoice Management
    path('invoices/', views.invoice_management, name='invoice_management'),
    path('invoices/generate/<uuid:subscription_id>/', views.generate_invoice, name='generate_invoice'),
    path('invoices/mark-paid/<int:invoice_id>/', views.mark_invoice_paid, name='mark_invoice_paid'),
    
    # User Management
    path('users/', views.user_management, name='user_management'),
    path('users/create/', views.create_user, name='create_user'),
    path('users/<int:user_id>/edit/', views.edit_user, name='edit_user'),
    path('users/<int:user_id>/toggle-status/', views.toggle_user_status, name='toggle_user_status'),
    path('users/<int:user_id>/toggle-suspension/', views.toggle_user_suspension, name='toggle_user_suspension'),
    
    # Suspension Management
    path('suspensions/', views.suspension_management, name='suspension_management'),
    path('suspensions/user/<int:user_id>/suspend/', views.suspend_user, name='suspend_user'),
    path('suspensions/user/<int:user_id>/reactivate/', views.reactivate_user, name='reactivate_user'),
    path('suspensions/business/<uuid:business_id>/suspend/', views.suspend_business, name='suspend_business'),
    path('suspensions/business/<uuid:business_id>/reactivate/', views.reactivate_business, name='reactivate_business'),
    path('suspensions/subscription/<uuid:subscription_id>/suspend/', views.suspend_subscription, name='suspend_subscription'),
    path('suspensions/subscription/<uuid:subscription_id>/reactivate/', views.reactivate_subscription, name='reactivate_subscription'),
    path('suspensions/employee/<uuid:business_id>/<uuid:employee_id>/suspend/', views.suspend_employee, name='suspend_employee'),
    path('suspensions/employee/<uuid:business_id>/<uuid:employee_id>/reactivate/', views.reactivate_employee, name='reactivate_employee'),
    
    # Analytics
    path('analytics/', views.system_analytics, name='analytics'),
    
    # Settings & Tools
    path('settings/', views.system_settings, name='system_settings'),
    path('export/', views.export_data, name='export_data'),
]
