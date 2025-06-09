# Add these URLs to your existing urlpatterns in urls.py

from django.urls import path
from . import views

app_name = 'employees'

urlpatterns = [
    # Dashboard
    path('', views.dashboard_view, name='dashboard'),
    
    # Employee Management
    path('list/', views.employee_list_view, name='list'),
    path('create/', views.employee_create_view, name='create'),
    path('<uuid:pk>/', views.employee_detail_view, name='detail'),
    path('<uuid:pk>/edit/', views.employee_edit_view, name='edit'),
    
    # Attendance
    path('attendance/', views.attendance_view, name='attendance'),
    path('attendance/checkin/', views.check_in_view, name='clock_in'),
    path('attendance/checkout/', views.check_out_view, name='clock_out'),
    
    # Break Management - ADD THESE LINES
    path('attendance/take-break/', views.take_break_view, name='take_break'),
    path('attendance/end-break/', views.end_break_view, name='end_break'),
    path('attendance/break-status/', views.break_status_view, name='break_status'),
    
    # Leave Management
    path('leave/request/', views.leave_request_view, name='leave_request'),
    path('leave/list/', views.leave_list_view, name='leave_list'),
    
    # Departments
    path('departments/', views.department_list_view, name='department_list'),
    path('departments/create/', views.department_create_view, name='department_create'),
    
    # AJAX endpoints
    path('ajax/<uuid:pk>/data/', views.get_employee_data, name='employee_data'),
]