from django.urls import path
from . import views

app_name = 'expenses'

urlpatterns = [
    # Dashboard
    path('', views.expense_dashboard_view, name='dashboard'),
    
    # Expense Management
    path('list/', views.expense_list_view, name='list'),
    path('create/', views.expense_create_view, name='create'),
    path('<uuid:pk>/', views.expense_detail_view, name='detail'),
    path('<uuid:pk>/edit/', views.expense_edit_view, name='edit'),
    path('<uuid:pk>/delete/', views.expense_delete_view, name='delete'),
    path('<uuid:pk>/approve/', views.expense_approve_view, name='approve'),
    path('<uuid:pk>/pay/', views.expense_pay_view, name='pay'),
    
    # Bulk Actions
    path('bulk-action/', views.expense_bulk_action_view, name='bulk_action'),
    
    # Vendor Management
    path('vendors/', views.vendor_list_view, name='vendor_list'),
    path('vendors/create/', views.vendor_create_view, name='vendor_create'),
    path('vendors/<uuid:pk>/', views.vendor_detail_view, name='vendor_detail'),
    path('vendors/<uuid:pk>/edit/', views.vendor_edit_view, name='vendor_edit'),
    path('vendors/<uuid:pk>/delete/', views.vendor_delete_view, name='vendor_delete'),
    
    # Category Management
    path('categories/', views.category_list_view, name='category_list'),
    path('categories/create/', views.category_create_view, name='category_create'),
    path('categories/<uuid:pk>/edit/', views.category_edit_view, name='category_edit'),
    path('categories/<uuid:pk>/delete/', views.category_delete_view, name='category_delete'),
    
    # Recurring Expenses
    path('recurring/', views.recurring_expense_list_view, name='recurring_list'),
    path('recurring/create/', views.recurring_expense_create_view, name='recurring_create'),
    path('recurring/<uuid:pk>/edit/', views.recurring_expense_edit_view, name='recurring_edit'),
    path('recurring/<uuid:pk>/delete/', views.recurring_expense_delete_view, name='recurring_delete'),
    path('recurring/<uuid:pk>/generate/', views.generate_recurring_expense_view, name='recurring_generate'),
    
    # Budget Management
    path('budgets/', views.budget_list_view, name='budget_list'),
    path('budgets/create/', views.budget_create_view, name='budget_create'),
    path('budgets/<uuid:pk>/edit/', views.budget_edit_view, name='budget_edit'),
    path('budgets/<uuid:pk>/delete/', views.budget_delete_view, name='budget_delete'),
    
    # Reports
    path('reports/', views.expense_reports_view, name='reports'),
    path('reports/category/', views.category_expense_report_view, name='category_report'),
    path('reports/vendor/', views.vendor_expense_report_view, name='vendor_report'),
    path('reports/monthly/', views.monthly_expense_report_view, name='monthly_report'),
    path('reports/budget-analysis/', views.budget_analysis_report_view, name='budget_analysis'),
    
    # AJAX endpoints
    path('ajax/search/', views.expense_search_ajax, name='search_ajax'),
    path('ajax/category-expenses/', views.category_expenses_ajax, name='category_expenses_ajax'),
    path('ajax/vendor-expenses/', views.vendor_expenses_ajax, name='vendor_expenses_ajax'),
    path('ajax/budget-status/', views.budget_status_ajax, name='budget_status_ajax'),
    
    # Export
    path('export/', views.expense_export_view, name='export'),
    path('export/pdf/', views.expense_export_pdf_view, name='export_pdf'),
    
    # Auto-linking utilities
    path('auto-link/inventory/', views.auto_link_inventory_expenses, name='auto_link_inventory'),
    path('auto-link/salaries/', views.auto_link_salary_expenses, name='auto_link_salaries'),
    path('auto-link/commissions/', views.auto_link_commission_expenses, name='auto_link_commissions'),
]
