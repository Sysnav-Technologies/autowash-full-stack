from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Dashboard
    path('', views.payment_dashboard_view, name='dashboard'),
    
    # Payments
    path('list/', views.payment_list_view, name='list'),
    path('<str:payment_id>/', views.payment_detail_view, name='detail'),
    path('create/', views.process_payment_view, name='create'),
    path('create/<uuid:order_id>/', views.process_payment_view, name='create_for_order'),
    
    # Payment Processing
    path('<str:payment_id>/cash/', views.process_cash_payment_view, name='process_cash'),
    # path('<str:payment_id>/card/', views.process_card_payment_view, name='process_card'),
    path('<str:payment_id>/mpesa/', views.process_mpesa_payment_view, name='process_mpesa'),
    path('<str:payment_id>/mpesa/status/', views.mpesa_payment_status_view, name='mpesa_status'),
    
    # Payment Actions
    path('<str:payment_id>/verify/', views.verify_payment, name='verify'),
    path('<str:payment_id>/refund/', views.payment_refund_view, name='refund'),
    
    # Reports & Analytics
    path('reports/', views.payment_reports_view, name='reports'),
    path('reports/export/csv/', views.export_payments_csv, name='export_csv'),
    path('reconciliation/', views.reconciliation_view, name='reconciliation'),
    
    # Management
    path('methods/', views.payment_methods_view, name='methods'),
    path('settings/', views.payment_settings_view, name='settings'),
    
    # AJAX endpoints
    path('ajax/mpesa-status/<str:payment_id>/', views.check_mpesa_status_ajax, name='mpesa_status_ajax'),
    path('ajax/summary/', views.payment_summary_ajax, name='summary_ajax'),
    path('ajax/bulk-process/', views.process_bulk_payments, name='bulk_process'),
    
    # Webhooks
    path('webhooks/mpesa/callback/', views.mpesa_callback_view, name='mpesa_callback'),
]