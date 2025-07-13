from django.urls import path
from . import views

app_name = 'suppliers'

urlpatterns = [
    # Dashboard
    path('', views.supplier_dashboard, name='dashboard'),
    
    # Suppliers - Change <int:pk> to <uuid:pk>
    path('list/', views.SupplierListView.as_view(), name='list'),
    path('create/', views.SupplierCreateView.as_view(), name='create'),
    path('<uuid:pk>/', views.SupplierDetailView.as_view(), name='detail'),
    path('<uuid:pk>/edit/', views.SupplierUpdateView.as_view(), name='edit'),
    path('<uuid:pk>/delete/', views.SupplierDeleteView.as_view(), name='delete'),
    
    # Supplier Categories
    path('categories/', views.supplier_categories, name='categories'),
    
    # Supplier Contacts - Change <int:supplier_id> to <uuid:supplier_id>
    path('<uuid:supplier_id>/contacts/add/', views.SupplierContactCreateView.as_view(), name='contact_add'),
    
    # Purchase Orders - Change <int:pk> to <uuid:pk>
    path('orders/', views.PurchaseOrderListView.as_view(), name='purchase_order_list'),
    path('orders/create/', views.PurchaseOrderCreateView.as_view(), name='purchase_order_create'),
    path('orders/<uuid:pk>/', views.PurchaseOrderDetailView.as_view(), name='purchase_order_detail'),
    # path('orders/<uuid:pk>/edit/', views.PurchaseOrderUpdateView.as_view(), name='purchase_order_edit'),
    path('orders/<uuid:pk>/approve/', views.approve_purchase_order, name='purchase_order_approve'),
    path('orders/<uuid:pk>/send/', views.send_purchase_order, name='purchase_order_send'),
    
    # Goods Receipts - Change <int:pk> to <uuid:pk>
    path('receipts/', views.GoodsReceiptListView.as_view(), name='goods_receipt_list'),
    path('receipts/create/', views.GoodsReceiptCreateView.as_view(), name='goods_receipt_create'),
    path('receipts/<uuid:pk>/', views.GoodsReceiptDetailView.as_view(), name='goods_receipt_detail'),
    path('receipts/<uuid:pk>/complete/', views.complete_goods_receipt, name='goods_receipt_complete'),
    
    # Supplier Evaluations - Change <int:pk> to <uuid:pk>
    path('evaluations/', views.SupplierEvaluationListView.as_view(), name='evaluation_list'),
    path('evaluations/create/', views.SupplierEvaluationCreateView.as_view(), name='evaluation_create'),
    
    # Supplier Payments - Change <int:pk> to <uuid:pk>
    path('payments/', views.SupplierPaymentListView.as_view(), name='payment_list'),
    path('payments/create/', views.SupplierPaymentCreateView.as_view(), name='payment_create'),
    path('payments/<uuid:pk>/', views.SupplierPaymentDetailView.as_view(), name='payment_detail'),
    path('payments/<uuid:pk>/process/', views.process_payment, name='payment_process'),
    
    # Supplier Documents
    path('documents/', views.SupplierDocumentListView.as_view(), name='document_list'),
    path('documents/upload/', views.SupplierDocumentCreateView.as_view(), name='document_upload'),
    
    # Reports and Analytics
    path('performance/', views.supplier_performance_report, name='performance_report'),
    path('export/', views.export_suppliers, name='export'),
    
    # AJAX Endpoints
    path('ajax/purchase-order-items/', views.ajax_purchase_order_items, name='ajax_purchase_order_items'),
]