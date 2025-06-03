from django.urls import path
from . import views

app_name = 'services'

urlpatterns = [
    # Service Management
    path('', views.service_list_view, name='list'),
    path('create/', views.service_create_view, name='create'),
    path('<uuid:pk>/', views.service_detail_view, name='detail'),
    # path('<uuid:pk>/edit/', views.service_edit_view, name='edit'),
    
    # Service Orders
    path('orders/', views.order_list_view, name='order_list'),
    path('orders/create/', views.order_create_view, name='create_order'),
    path('orders/quick/', views.quick_order_view, name='quick_order'),
    path('orders/<uuid:pk>/', views.order_detail_view, name='order_detail'),
    # path('orders/<uuid:pk>/edit/', views.order_edit_view, name='order_edit'),
    
    # Service Actions
    path('orders/<uuid:order_id>/start/', views.start_service, name='start_service'),
    path('orders/<uuid:order_id>/complete/', views.complete_service, name='complete_service'),
    # path('orders/<uuid:order_id>/cancel/', views.cancel_service, name='cancel_service'),
    
    # Queue Management
    path('queue/', views.queue_view, name='queue'),
    # path('queue/update/', views.update_queue, name='update_queue'),
    
    # # Service Packages
    # path('packages/', views.package_list_view, name='package_list'),
    # path('packages/create/', views.package_create_view, name='package_create'),
    # path('packages/<uuid:pk>/', views.package_detail_view, name='package_detail'),
    
    # # Service Bays
    # path('bays/', views.bay_list_view, name='bay_list'),
    # path('bays/create/', views.bay_create_view, name='bay_create'),
    
    # AJAX endpoints
    path('ajax/service/<uuid:service_id>/data/', views.get_service_data, name='service_data'),
    path('ajax/queue/status/', views.queue_status_ajax, name='queue_status'),
    # path('ajax/calculate-price/', views.calculate_order_price, name='calculate_price'),
    
    # # Customer Rating
    # path('orders/<uuid:order_id>/rate/', views.rate_service, name='rate_service'),
]