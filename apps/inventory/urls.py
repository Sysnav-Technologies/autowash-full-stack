from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    # Dashboard
    path('', views.inventory_dashboard_view, name='dashboard'),
    
    # Items Management
    path('items/', views.item_list_view, name='list'),
    path('items/create/', views.item_create_view, name='item_create'),
    path('items/<uuid:pk>/', views.item_detail_view, name='item_detail'),
    path('items/<uuid:pk>/edit/', views.item_edit_view, name='item_edit'),
    
    # Stock Management
    path('stock/adjustments/', views.stock_adjustment_view, name='stock_adjustment'),
    path('stock/adjustments/<uuid:item_id>/', views.stock_adjustment_view, name='stock_adjustment_item'),
    path('stock/movements/', views.stock_movements_view, name='stock_movements'),
    
    # Stock Takes
    path('stock-takes/', views.stock_take_list_view, name='stock_take_list'),
    path('stock-takes/create/', views.stock_take_create_view, name='stock_take_create'),
    path('stock-takes/<uuid:pk>/', views.stock_take_detail_view, name='stock_take_detail'),
    path('stock-takes/<uuid:pk>/edit/', views.stock_take_edit_view, name='stock_take_edit'),
    path('stock-takes/<uuid:pk>/start/', views.start_stock_take, name='start_stock_take'),
    path('stock-takes/<uuid:pk>/complete/', views.complete_stock_take, name='complete_stock_take'),
    path('stock-takes/<uuid:stock_take_id>/count/<uuid:item_id>/', views.update_stock_count, name='update_stock_count'),
    
    # Reports
    path('reports/low-stock/', views.low_stock_report_view, name='low_stock_report'),
    path('reports/valuation/', views.inventory_valuation_report, name='valuation_report'),
    path('reports/export/csv/', views.export_inventory_csv, name='export_csv'),
    
    # Categories
    path('categories/', views.category_list_view, name='category_list'),
    path('categories/create/', views.category_create_view, name='category_create'),
    path('categories/<uuid:pk>/edit/', views.category_edit_view, name='category_edit'),
    path('categories/<uuid:pk>/delete/', views.category_delete_view, name='category_delete'),
    
    # Alerts
    path('alerts/', views.alerts_view, name='alerts'),
    path('alerts/<int:alert_id>/resolve/', views.resolve_alert, name='resolve_alert'),

    # Daily Operations
    path('daily-operations/', views.daily_operations_dashboard, name='daily_operations'),
    path('daily-operations/allocate/', views.allocate_to_bay, name='allocate_to_bay'),
    path('daily-operations/consumption/', views.record_bay_consumption, name='record_bay_consumption'),
    path('daily-operations/transfer/', views.transfer_between_bays, name='transfer_between_bays'),
    path('daily-operations/return/', views.return_to_stock, name='return_to_stock'),
    path('daily-operations/reconciliation/start/', views.start_reconciliation, name='start_reconciliation'),
    path('daily-operations/reconciliation/complete/', views.complete_reconciliation, name='complete_reconciliation'),

    # Units
    path('units/', views.unit_list_view, name='unit_list'),
    path('units/create/', views.unit_create_view, name='unit_create'),
    path('units/<uuid:pk>/', views.unit_detail_view, name='unit_detail'),
    path('units/<uuid:pk>/edit/', views.unit_edit_view, name='unit_edit'),
    path('units/<uuid:pk>/toggle/', views.unit_toggle_status, name='unit_toggle_status'),
    path('units/<uuid:pk>/delete/', views.unit_delete_view, name='unit_delete'),
    path('units/populate/', views.populate_car_wash_units_view, name='populate_car_wash_units'),
    path('ajax/units/search/', views.unit_search_ajax, name='unit_search'),
    
    # AJAX endpoints
    path('ajax/items/search/', views.item_search_ajax, name='item_search'),
    path('ajax/recent-adjustments/', views.recent_adjustments_ajax, name='recent_adjustments'),
    path('ajax/consumption/', views.item_consumption_ajax, name='item_consumption'),
    path('ajax/reconciliation/update/', views.ajax_update_reconciliation_item, name='ajax_update_reconciliation_item'),
    path('ajax/bay-status/', views.get_bay_status, name='get_bay_status'),
    path('ajax/activity-feed/', views.get_activity_feed, name='get_activity_feed'),
    path('ajax/update-target/', views.update_operations_target, name='update_operations_target'),
    path('ajax/create-purchase-orders/', views.create_purchase_orders_ajax, name='create_purchase_orders_ajax'),
    
    # API endpoints (alternative paths)
    path('api/search-items/', views.item_search_ajax, name='api_item_search'),
    # path('ajax/stock-check/', views.stock_check_ajax, name='stock_check'),
    
    # # Mobile/Quick Actions
    # path('mobile/quick-adjustment/', views.quick_stock_adjustment_view, name='quick_adjustment'),
    # path('mobile/barcode-scan/', views.barcode_scan_view, name='barcode_scan'),
]