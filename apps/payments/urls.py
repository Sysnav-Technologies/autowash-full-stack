from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Payment Dashboard
    path('', views.payment_dashboard_view, name='dashboard'),
    path('list/', views.payment_list_view, name='list'),
    path('<str:payment_id>/', views.payment_detail_view, name='detail'),
    
    # Payment Processing
    path('process/', views.process_payment_view, name='process'),
    path('process/<uuid:order_id>/', views.process_payment_view, name='process_order'),
    path('<str:payment_id>/cash/', views.process_cash_payment_view, name='process_cash'),
    path('<str:payment_id>/mpesa/', views.process_mpesa_payment_view, name='process_mpesa'),
    # path('<str:payment_id>/card/', views.process_card_payment_view, name='process_card'),
    
    # Payment Status & Actions
    path('<str:payment_id>/status/', views.mpesa_payment_status_view, name='mpesa_status'),
    path('<str:payment_id>/verify/', views.verify_payment, name='verify'),
    path('<str:payment_id>/refund/', views.payment_refund_view, name='refund'),
    path('<str:payment_id>/receipt/', views.payment_receipt_view, name='receipt'),
    path('<str:payment_id>/success/', views.payment_success_view, name='success'),
    
    # Partial Payments - Fixed URLs
    path('partial/create/<uuid:order_id>/', views.create_partial_payment_view, name='create_partial'),
    path('partial/<str:partial_id>/process/', views.process_partial_payment, name='process_partial'),
    path('partial/history/<uuid:order_id>/', views.partial_payment_history, name='partial_history'),
    
    # AJAX Endpoints
    path('ajax/<str:payment_id>/mpesa-status/', views.check_mpesa_status_ajax, name='check_mpesa_status'),
    path('ajax/summary/', views.payment_summary_ajax, name='payment_summary'),
    path('ajax/bulk-process/', views.process_bulk_payments, name='bulk_process'),
    
    # M-Pesa Webhook
    path('webhook/mpesa/', views.mpesa_callback_view, name='mpesa_callback'),
    
    # Reports & Management
    path('methods/', views.payment_methods_view, name='methods'),
    path('reports/', views.payment_reports_view, name='reports'),
    path('reconciliation/', views.reconciliation_view, name='reconciliation'),
    path('settings/', views.payment_settings_view, name='settings'),
    path('export/', views.export_payments_csv, name='export_csv'),
]