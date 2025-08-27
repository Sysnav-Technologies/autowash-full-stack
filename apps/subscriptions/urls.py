# subscriptions/urls.py
from django.urls import path
from . import views

app_name = 'subscriptions'

urlpatterns = [
    # Pricing and subscription views (public/initial subscription)
    path('', views.subscription_selection_view, name='plans'),
    path('select/', views.subscription_selection_view, name='select'),
    path('subscribe/<slug:plan_slug>/', views.subscribe_view, name='subscribe'),
    
    # Payment handling (initial subscription payments)
    path('payment/<uuid:payment_id>/', views.payment_view, name='payment'),
    path('payment/', views.subscription_payment_view, name='subscription_payment'),
    path('payment-status/<uuid:payment_id>/', views.payment_status_view, name='payment_status'),
    
    # Subscription management (business tenant context)
    path('overview/', views.subscription_overview, name='subscription_overview'),
    path('billing/', views.billing_history, name='billing_history'),
    path('payment-methods/', views.payment_methods, name='payment_methods'),
    path('usage/', views.usage_analytics, name='usage_analytics'),
    path('settings/', views.subscription_settings, name='subscription_settings'),
    path('upgrade/', views.upgrade_view, name='upgrade'),
    path('manage/', views.manage_subscription_view, name='manage_subscription'),
    path('cancel/', views.cancel_subscription_view, name='cancel_subscription'),
    path('upgrade/<slug:plan_slug>/', views.upgrade_subscription_view, name='upgrade_subscription'),
    
    # Discount codes (public)
    path('check-discount/', views.check_discount_code_view, name='check_discount'),
    
    # Invoices (public access)
    path('invoice/<uuid:invoice_id>/download/', views.download_invoice_view, name='download_invoice'),
    
    # AJAX endpoints for subscription functionality (that exist in subscriptions app)
    path('api/select-plan/', views.select_subscription_plan, name='select_subscription_plan'),
    path('api/cancel/', views.cancel_subscription_ajax, name='cancel_subscription_ajax'),
    path('api/payment-status/<uuid:payment_id>/', views.payment_status_api_view, name='payment_status_api'),
    path('api/add-payment-method/', views.add_payment_method, name='add_payment_method'),
    path('api/set-default-payment/', views.set_default_payment_method, name='set_default_payment_method'),
    path('api/remove-payment/', views.remove_payment_method, name='remove_payment_method'),
    path('api/track-download/', views.track_invoice_download, name='track_invoice_download'),
    path('api/generate-pdf/', views.generate_invoice_pdf, name='generate_invoice_pdf'),
    path('api/export-billing/', views.export_billing_history, name='export_billing_history'),
    path('api/refresh-usage/', views.refresh_usage_data, name='refresh_usage_data'),
    path('api/generate-report/', views.generate_usage_report, name='generate_usage_report'),
    
    # Callbacks (external services)
    path('mpesa-callback/', views.mpesa_callback_view, name='mpesa_callback'),
]