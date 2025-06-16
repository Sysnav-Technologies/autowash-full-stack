# apps/customers/urls.py - COMPLETE VERSION with Django's built-in UUID converter

from django.urls import path
from . import views

app_name = 'customers'

urlpatterns = [
    # Customer Management
    path('', views.customer_list_view, name='list'),
    path('create/', views.customer_create_view, name='create'),
    path('<uuid:pk>/', views.customer_detail_view, name='detail'),
    path('<uuid:pk>/edit/', views.customer_edit_view, name='edit'),
    
    # Customer Actions
    path('<uuid:pk>/toggle-vip/', views.toggle_customer_vip, name='toggle_vip'),
    path('<uuid:pk>/deactivate/', views.deactivate_customer, name='deactivate'),
    
    # Vehicle Management
    path('<uuid:customer_pk>/vehicles/add/', views.vehicle_create_view, name='vehicle_create'),
    path('vehicles/<uuid:pk>/edit/', views.vehicle_edit_view, name='vehicle_edit'),
    
    # Notes and Documents
    path('<uuid:customer_pk>/notes/add/', views.customer_note_create_view, name='note_create'),
    path('<uuid:customer_pk>/documents/', views.customer_documents_view, name='documents'),
    path('<uuid:customer_pk>/feedback/', views.customer_feedback_view, name='feedback'),
    
    # AJAX endpoints
    path('ajax/search/', views.customer_search_ajax, name='search_ajax'),
    path('ajax/vehicles/search/', views.vehicle_search_ajax, name='vehicle_search_ajax'),
    
    # Loyalty Program
    path('loyalty/', views.loyalty_dashboard_view, name='loyalty_dashboard'),
    
    # Export
    path('export/', views.customer_export_view, name='export'),
]