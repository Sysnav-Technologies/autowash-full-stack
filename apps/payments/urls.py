from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Payment Dashboard
    path('', views.payment_dashboard_view, name='dashboard'),
    path('list/', views.payment_list_view, name='list'),
    
    # Payment Processing - specific URLs first
    path('process/', views.process_payment_view, name='process'),
    path('process/<uuid:order_id>/', views.process_payment_view, name='process_order'),
    
    # Reports & Management - specific URLs must come before generic patterns
    path('methods/', views.payment_methods_view, name='methods'),
    path('methods/toggle/', views.toggle_payment_method, name='toggle_method'),
    path('methods/<int:method_id>/config/', views.get_payment_method_config, name='method_config'),
    path('reports/', views.payment_reports_view, name='reports'),
    path('reconciliation/', views.reconciliation_view, name='reconciliation'),
    path('settings/', views.payment_settings_view, name='settings'),
    path('setup-mpesa/', views.setup_mpesa_gateway_view, name='setup_mpesa'),
    path('configure-mpesa-method/', views.configure_mpesa_method_view, name='configure_mpesa_method'),
    path('test-mpesa-connection/', views.test_mpesa_connection, name='test_mpesa_connection'),
    path('export/', views.export_payments_csv, name='export_csv'),
    
    # Partial Payments - Fixed URLs
    path('partial/create/<uuid:order_id>/', views.create_partial_payment_view, name='create_partial'),
    path('partial/<str:partial_id>/process/', views.process_partial_payment, name='process_partial'),
    path('partial/history/<uuid:order_id>/', views.partial_payment_history, name='partial_history'),
    
    # AJAX Endpoints
    path('ajax/<str:payment_id>/mpesa-status/', views.check_mpesa_status_ajax, name='check_mpesa_status'),
    path('ajax/summary/', views.payment_summary_ajax, name='payment_summary'),
    path('ajax/bulk-process/', views.process_bulk_payments, name='bulk_process'),
    path('ajax/status/', views.payment_status_ajax, name='payment_status_ajax'),
    
    # M-Pesa Webhook
    path('webhook/mpesa/', views.mpesa_callback_view, name='mpesa_callback'),
    
    # Generic patterns - must come LAST to avoid conflicts
    path('<str:payment_id>/', views.payment_detail_view, name='detail'),
    path('<str:payment_id>/cash/', views.process_cash_payment_view, name='process_cash'),
    path('<str:payment_id>/mpesa/', views.process_mpesa_payment_view, name='process_mpesa'),
    # path('<str:payment_id>/card/', views.process_card_payment_view, name='process_card'),
    
    # Payment Status & Actions - specific payment ID patterns
    path('<str:payment_id>/status/', views.mpesa_payment_status_view, name='mpesa_status'),
    path('<str:payment_id>/verify/', views.verify_payment, name='verify'),
    path('<str:payment_id>/refund/', views.payment_refund_view, name='refund'),
    path('<str:payment_id>/print/', views.payment_receipt_print_view, name='receipt_print'),
    path('<str:payment_id>/receipt/', views.payment_receipt_view, name='receipt'),
    path('<str:payment_id>/success/', views.payment_success_view, name='success'),
]