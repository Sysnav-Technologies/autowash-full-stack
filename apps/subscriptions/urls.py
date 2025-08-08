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
    
    # Discount codes
    path('check-discount/', views.check_discount_code_view, name='check_discount'),
    
    # Invoices
    path('invoice/<uuid:invoice_id>/download/', views.download_invoice_view, name='download_invoice'),
    
    # Callbacks
    path('mpesa-callback/', views.mpesa_callback_view, name='mpesa_callback'),
]