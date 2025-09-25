from django.urls import path
from . import views

app_name = 'services'

urlpatterns = [
    # Service Management
    path('', views.service_list_view, name='list'),
    path('create/', views.service_create_view, name='create'),
    path('<uuid:pk>/', views.service_detail_view, name='detail'),
    path('<uuid:pk>/edit/', views.service_edit_view, name='edit'),
    path('<uuid:pk>/delete/', views.service_delete_view, name='delete'),
    
    # Service Categories
    path('categories/', views.category_list_view, name='category_list'),
    path('categories/create/', views.category_create_view, name='category_create'),
    path('categories/<uuid:pk>/edit/', views.category_edit_view, name='category_edit'),
    path('categories/<uuid:pk>/toggle-status/', views.category_toggle_status, name='category_toggle_status'),
    path('categories/<uuid:pk>/delete/', views.category_delete, name='category_delete'),
    
    # Service Orders
    path('orders/', views.order_list_view, name='order_list'),
    path('orders/create/', views.quick_order_view, name='create_order'),
    path('orders/quick/', views.quick_order_view, name='quick_order'),
    path('orders/<uuid:pk>/', views.order_detail_view, name='order_detail'),
    path('orders/<uuid:pk>/edit/', views.order_edit_view, name='order_edit'),
    path('orders/<uuid:pk>/delete/', views.order_delete_view, name='order_delete'),
    path('orders/<uuid:pk>/print/', views.order_print_view, name='order_print'),
    path('orders/<uuid:pk>/receipt/', views.order_receipt_view, name='order_receipt'),
    path('orders/<uuid:pk>/receipt/print/', views.order_receipt_print_view, name='order_receipt_print'),
    
    # Service Actions
    path('orders/<uuid:order_id>/start/', views.start_service, name='start_service'),
    path('orders/<uuid:order_id>/complete/', views.complete_service, name='complete_service'),
    path('orders/<uuid:order_id>/cancel/', views.cancel_service, name='cancel_service'),
    path('orders/<uuid:order_id>/pause/', views.pause_service, name='pause_service'),
    path('orders/<uuid:order_id>/resume/', views.resume_service, name='resume_service'),
    
    # Payment Management
    path('orders/<uuid:order_id>/process-payment/', views.process_payment, name='process_payment'),
    path('orders/<uuid:order_id>/receipt/', views.payment_receipt, name='payment_receipt'),
    
    # Queue Management
    path('queue/', views.queue_view, name='queue'),
    path('queue/update/', views.update_queue, name='update_queue'),
    path('queue/<uuid:queue_id>/priority/', views.update_queue_priority, name='update_priority'),
    
    # Service Packages
    path('packages/', views.package_list_view, name='package_list'),
    path('packages/create/', views.package_create_view, name='package_create'),
    path('packages/<uuid:pk>/', views.package_detail_view, name='package_detail'),
    path('packages/<uuid:pk>/edit/', views.package_edit_view, name='package_edit'),
    
    # Service Bays
    path('bays/', views.bay_list_view, name='bay_list'),
    path('bays/create/', views.bay_create_view, name='bay_create'),
    path('bays/<uuid:pk>/edit/', views.bay_edit_view, name='bay_edit'),
    path('bays/<uuid:pk>/assign/', views.assign_bay, name='assign_bay'),
    path('orders/<uuid:order_id>/assign-bay/', views.assign_bay_to_order, name='assign_bay_to_order'),
    
    # Customer Rating & Feedback
    path('orders/<uuid:order_id>/rate/', views.rate_service, name='rate_service'),
    path('orders/<uuid:order_id>/feedback/', views.service_feedback, name='service_feedback'),
    
    # Reports & Analytics
    path('reports/', views.service_reports_view, name='reports'),
    path('reports/daily/', views.daily_service_report, name='daily_report'),
    path('reports/performance/', views.service_performance_report, name='performance_report'),
    
    # AJAX endpoints
    path('ajax/service/<uuid:service_id>/data/', views.get_service_data, name='service_data'),
    path('ajax/queue/status/', views.queue_status_ajax, name='queue_status'),
    path('ajax/queue/statistics/', views.queue_statistics_ajax, name='queue_statistics'),
    path('ajax/calculate-price/', views.calculate_order_price, name='calculate_price'),
    path('ajax/customer/search/', views.customer_search_ajax, name='customer_search'),
    path('ajax/vehicle/search/', views.vehicle_search_ajax, name='vehicle_search'),
    path('ajax/vehicle/customer/', views.vehicle_customer_ajax, name='vehicle_customer'),
    path('ajax/start-next/', views.start_next_service, name='start_next_service'),
    path('ajax/current-service/', views.get_current_service, name='current_service'),
    path('ajax/bay/status/', views.bay_status_ajax, name='bay_status'),
    path('ajax/services-list/', views.services_list_ajax, name='services_list_ajax'),
    path('ajax/attendance-status/', views.attendance_status_ajax, name='attendance_status'),
    
    # Attendant Dashboard
    path('dashboard/', views.attendant_dashboard, name='attendant_dashboard'),
    path('my-services/', views.my_services_view, name='my_services'),
    
    # Quick Actions
    path('quick/customer-register/', views.quick_customer_register, name='quick_customer_register'),
    path('quick/service-assign/', views.quick_service_assign, name='quick_service_assign'),
    
    # Export & Import
    path('export/', views.service_export_view, name='export'),
    path('import/', views.service_import_view, name='import'),
    
    # Invoice Management
    path('orders/<uuid:order_id>/generate-invoice/', views.generate_invoice, name='generate_invoice'),
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('invoices/<uuid:invoice_id>/', views.invoice_preview, name='invoice_preview'),
    path('invoices/<uuid:invoice_id>/print/', views.invoice_print, name='invoice_print'),
    path('invoices/<uuid:invoice_id>/pdf/', views.invoice_pdf, name='invoice_pdf'),
    path('invoices/<uuid:invoice_id>/mark-sent/', views.invoice_mark_sent, name='invoice_mark_sent'),
    path('invoices/<uuid:invoice_id>/mark-paid/', views.invoice_mark_paid, name='invoice_mark_paid'),
    
    # Quotation Management
    path('quotations/', views.quotation_list, name='quotation_list'),
    path('quotations/create/', views.quotation_create, name='quotation_create'),
    path('quotations/quick/', views.quick_quotation_view, name='quick_quotation'),
    path('quotations/<uuid:quotation_id>/', views.quotation_detail, name='quotation_detail'),
    path('quotations/<uuid:quotation_id>/edit/', views.quotation_edit, name='quotation_edit'),
    path('quotations/<uuid:quotation_id>/print/', views.quotation_print, name='quotation_print'),
    path('quotations/<uuid:quotation_id>/pdf/', views.quotation_pdf, name='quotation_pdf'),
    path('quotations/<uuid:quotation_id>/send/', views.quotation_send, name='quotation_send'),
    path('quotations/<uuid:quotation_id>/accept/', views.quotation_accept, name='quotation_accept'),
    path('quotations/<uuid:quotation_id>/reject/', views.quotation_reject, name='quotation_reject'),
    path('quotations/<uuid:quotation_id>/convert/', views.quotation_convert_to_order, name='quotation_convert'),
]