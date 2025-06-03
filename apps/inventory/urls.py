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
    # path('items/<uuid:pk>/edit/', views.item_edit_view, name='item_edit'),
    
    # Stock Management
    path('stock/adjustments/', views.stock_adjustment_view, name='stock_adjustment'),
    path('stock/adjustments/<uuid:item_id>/', views.stock_adjustment_view, name='stock_adjustment_item'),
    path('stock/movements/', views.stock_movements_view, name='stock_movements'),
    
    # Stock Takes
    path('stock-takes/', views.stock_take_list_view, name='stock_take_list'),
    path('stock-takes/create/', views.stock_take_create_view, name='stock_take_create'),
    path('stock-takes/<uuid:pk>/', views.stock_take_detail_view, name='stock_take_detail'),
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
    # path('categories/<uuid:pk>/edit/', views.category_edit_view, name='category_edit'),
    
    # Alerts
    path('alerts/', views.alerts_view, name='alerts'),
    path('alerts/<int:alert_id>/resolve/', views.resolve_alert, name='resolve_alert'),
    
    # AJAX endpoints
    path('ajax/items/search/', views.item_search_ajax, name='item_search'),
    path('ajax/consumption/', views.item_consumption_ajax, name='item_consumption'),
    # path('ajax/stock-check/', views.stock_check_ajax, name='stock_check'),
    
    # # Mobile/Quick Actions
    # path('mobile/quick-adjustment/', views.quick_stock_adjustment_view, name='quick_adjustment'),
    # path('mobile/barcode-scan/', views.barcode_scan_view, name='barcode_scan'),
]