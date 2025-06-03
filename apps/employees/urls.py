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
    path('attendance/checkin/', views.check_in_view, name='check_in'),
    path('attendance/checkout/', views.check_out_view, name='check_out'),
    
    # Leave Management
    path('leave/request/', views.leave_request_view, name='leave_request'),
    path('leave/list/', views.leave_list_view, name='leave_list'),
    
    # Departments
    path('departments/', views.department_list_view, name='department_list'),
    path('departments/create/', views.department_create_view, name='department_create'),
    
    # AJAX endpoints
    path('ajax/<uuid:pk>/data/', views.get_employee_data, name='employee_data'),
]