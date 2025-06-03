from django.urls import path
from . import views

app_name = 'suppliers'

urlpatterns = [
    # Dashboard
    path('', views.supplier_dashboard, name='dashboard'),
    
    # Suppliers
    path('list/', views.SupplierListView.as_view(), name='list'),
    path('create/', views.SupplierCreateView.as_view(), name='create'),
    path('<int:pk>/', views.SupplierDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.SupplierUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', views.SupplierDeleteView.as_view(), name='delete'),
    
    # Supplier Categories
    path('categories/', views.supplier_categories, name='categories'),
    
    # Supplier Contacts
    path('<int:supplier_id>/contacts/add/', views.SupplierContactCreateView.as_view(), name='contact_add'),
    
    # Purchase Orders
    path('orders/', views.PurchaseOrderListView.as_view(), name='purchase_order_list'),
    path('orders/create/', views.PurchaseOrderCreateView.as_view(), name='purchase_order_create'),
    path('orders/<int:pk>/', views.PurchaseOrderDetailView.as_view(), name='purchase_order_detail'),
    path('orders/<int:pk>/edit/', views.PurchaseOrderUpdateView.as_view(), name='purchase_order_edit'),
    path('orders/<int:pk>/approve/', views.approve_purchase_order, name='purchase_order_approve'),
    path('orders/<int:pk>/send/', views.send_purchase_order, name='purchase_order_send'),
    
    # Goods Receipts
    path('receipts/', views.GoodsReceiptListView.as_view(), name='goods_receipt_list'),
    path('receipts/create/', views.GoodsReceiptCreateView.as_view(), name='goods_receipt_create'),
    path('receipts/<int:pk>/', views.GoodsReceiptDetailView.as_view(), name='goods_receipt_detail'),
    path('receipts/<int:pk>/complete/', views.complete_goods_receipt, name='goods_receipt_complete'),
    
    # Supplier Evaluations
    path('evaluations/', views.SupplierEvaluationListView.as_view(), name='evaluation_list'),
    path('evaluations/create/', views.SupplierEvaluationCreateView.as_view(), name='evaluation_create'),
    
    # Supplier Payments
    path('payments/', views.SupplierPaymentListView.as_view(), name='payment_list'),
    path('payments/create/', views.SupplierPaymentCreateView.as_view(), name='payment_create'),
    path('payments/<int:pk>/', views.SupplierPaymentDetailView.as_view(), name='payment_detail'),
    path('payments/<int:pk>/process/', views.process_payment, name='payment_process'),
    
    # Supplier Documents
    path('documents/', views.SupplierDocumentListView.as_view(), name='document_list'),
    path('documents/upload/', views.SupplierDocumentCreateView.as_view(), name='document_upload'),
    
    # Reports and Analytics
    path('performance/', views.supplier_performance_report, name='performance_report'),
    path('export/', views.export_suppliers, name='export'),
    
    # AJAX Endpoints
    path('ajax/purchase-order-items/', views.ajax_purchase_order_items, name='ajax_purchase_order_items'),
]