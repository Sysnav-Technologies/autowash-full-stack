# subscriptions/urls.py
from django.urls import path
from . import views

app_name = 'subscriptions'

urlpatterns = [
    # Pricing and subscription views
    path('', views.subscription_selection_view, name='plans'),
    path('select/', views.subscription_selection_view, name='select'),
    path('subscribe/<slug:plan_slug>/', views.subscribe_view, name='subscribe'),
    
    # Payment handling
    path('payment/<uuid:payment_id>/', views.payment_view, name='payment'),
    path('payment-status/<uuid:payment_id>/', views.payment_status_view, name='payment_status'),
    
    # Subscription management
    path('manage/', views.manage_subscription_view, name='manage_subscription'),
    path('cancel/', views.cancel_subscription_view, name='cancel_subscription'),
    path('upgrade/<slug:plan_slug>/', views.upgrade_subscription_view, name='upgrade_subscription'),
    
    # Business Owner Subscription Management
    path('overview/', views.subscription_overview, name='subscription_overview'),
    path('billing/', views.billing_history, name='billing_history'),
    path('payment-methods/', views.payment_methods, name='payment_methods'),
    path('usage/', views.usage_analytics, name='usage_analytics'),
    path('settings/', views.subscription_settings, name='subscription_settings'),
    
    # Discount codes
    path('check-discount/', views.check_discount_code_view, name='check_discount'),
    
    # Invoices
    path('invoice/<uuid:invoice_id>/download/', views.download_invoice_view, name='download_invoice'),
    
    # AJAX endpoints for subscription functionality
    path('api/select-plan/', views.select_subscription_plan, name='select_subscription_plan'),
    path('api/cancel/', views.cancel_subscription_ajax, name='cancel_subscription_ajax'),
    path('api/add-payment-method/', views.add_payment_method, name='add_payment_method'),
    path('api/set-default-payment/', views.set_default_payment_method, name='set_default_payment_method'),
    path('api/remove-payment/', views.remove_payment_method, name='remove_payment_method'),
    path('api/track-download/', views.track_invoice_download, name='track_invoice_download'),
    path('api/generate-pdf/', views.generate_invoice_pdf, name='generate_invoice_pdf'),
    path('api/export-billing/', views.export_billing_history, name='export_billing_history'),
    path('api/refresh-usage/', views.refresh_usage_data, name='refresh_usage_data'),
    path('api/generate-report/', views.generate_usage_report, name='generate_usage_report'),
    
    # Callbacks
    path('mpesa-callback/', views.mpesa_callback_view, name='mpesa_callback'),
]