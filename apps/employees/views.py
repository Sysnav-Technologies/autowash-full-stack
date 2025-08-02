from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.db import transaction
from django.db.models import Q, Count, Avg, Sum
from django.utils import timezone
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.urls import reverse
# Removed django_tenants import - no longer needed
from apps.core.decorators import employee_required, manager_required, owner_required, ajax_required
from apps.core.utils import generate_unique_code, send_email_notification, send_sms_notification
from .models import (
    Employee, Department, Position, Attendance, Leave, 
    PerformanceReview, Training, TrainingParticipant, Payroll, EmployeeDocument
)
from .forms import (
    EmployeeForm, DepartmentForm, PositionForm, AttendanceForm,
    LeaveRequestForm, PerformanceReviewForm, TrainingForm, PayrollForm
)
from datetime import datetime, timedelta
import json
import uuid

# --- Tenant-aware URL helpers ---

def get_employee_urls(request):
    tenant_slug = request.tenant.slug
    base_url = f"/business/{tenant_slug}/employees"
    return {
        'dashboard': f"{base_url}/",
        'list': f"{base_url}/list/",
        'create': f"{base_url}/create/",
        'detail': f"{base_url}/{{pk}}/",
        'edit': f"{base_url}/{{pk}}/edit/",
        'attendance': f"{base_url}/attendance/",
        'clock_in': f"{base_url}/attendance/checkin/",
        'clock_out': f"{base_url}/attendance/checkout/",
        'take_break': f"{base_url}/attendance/take-break/",
        'end_break': f"{base_url}/attendance/end-break/",
        'break_status': f"{base_url}/attendance/break-status/",
        'leave_request': f"{base_url}/leave/request/",
        'leave_list': f"{base_url}/leave/list/",
        'department_list': f"{base_url}/departments/",
        'department_create': f"{base_url}/departments/create/",
        'employee_data': f"{base_url}/ajax/{{pk}}/data/",
    }

def get_business_url(request, url_name, **kwargs):
    tenant_slug = request.tenant.slug
    base_url = f"/business/{tenant_slug}/employees"
    url_mapping = {
        'employees:dashboard': f"{base_url}/",
        'employees:list': f"{base_url}/list/",
        'employees:create': f"{base_url}/create/",
        'employees:detail': f"{base_url}/{{pk}}/",
        'employees:edit': f"{base_url}/{{pk}}/edit/",
        'employees:attendance': f"{base_url}/attendance/",
        'employees:clock_in': f"{base_url}/attendance/checkin/",
        'employees:clock_out': f"{base_url}/attendance/checkout/",
        'employees:take_break': f"{base_url}/attendance/take-break/",
        'employees:end_break': f"{base_url}/attendance/end-break/",
        'employees:break_status': f"{base_url}/attendance/break-status/",
        'employees:leave_request': f"{base_url}/leave/request/",
        'employees:leave_list': f"{base_url}/leave/list/",
        'employees:department_list': f"{base_url}/departments/",
        'employees:department_create': f"{base_url}/departments/create/",
        'employees:employee_data': f"{base_url}/ajax/{{pk}}/data/",
    }
    url = url_mapping.get(url_name, f"{base_url}/")
    for key, value in kwargs.items():
        url = url.replace(f"{{{key}}}", str(value))
    return url

@login_required
@employee_required()
def dashboard_view(request):
    """Employee dashboard"""
    employee = request.employee
    today = timezone.now().date()
    attendance_today = Attendance.objects.filter(
        employee=employee, 
        date=today
    ).first()
    pending_leaves = employee.leave_requests.filter(status='pending').count()
    upcoming_trainings = Training.objects.filter(
        employees=employee,
        start_date__gte=today,
        status='scheduled'
    )[:3]
    recent_reviews = employee.performance_reviews.all()[:2]
    team_stats = {}
    if employee.role in ['owner', 'manager', 'supervisor']:
        subordinates = employee.get_subordinates()
        team_stats = {
            'total_team_members': subordinates.count(),
            'present_today': Attendance.objects.filter(
                employee__in=subordinates,
                date=today,
                status='present'
            ).count(),
            'pending_leave_requests': Leave.objects.filter(
                employee__in=subordinates,
                status='pending'
            ).count()
        }
    context = {
        'employee': employee,
        'attendance_today': attendance_today,
        'pending_leaves': pending_leaves,
        'upcoming_trainings': upcoming_trainings,
        'recent_reviews': recent_reviews,
        'team_stats': team_stats,
        'title': 'Employee Dashboard',
        'urls': get_employee_urls(request),
    }
    return render(request, 'employees/dashboard.html', context)

@login_required
@manager_required
def employee_list_view(request):
    """List all employees - FIXED to remove user select_related"""
    employees = Employee.objects.select_related(
        'department', 'position', 'supervisor'
    ).all()
    department_id = request.GET.get('department')
    role = request.GET.get('role')
    status = request.GET.get('status', 'active')
    search = request.GET.get('search')
    if department_id:
        employees = employees.filter(department_id=department_id)
    if role:
        employees = employees.filter(role=role)
    if status:
        employees = employees.filter(status=status)
    if search:
        employees = employees.filter(
            Q(employee_id__icontains=search) |
            Q(email__icontains=search) |
            Q(phone__icontains=search)
        )
        if search:
            matching_users = User.objects.using('default').filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                    Q(username__icontains=search)
                ).values_list('id', flat=True)
            if matching_users:
                employees = employees.filter(
                    Q(user_id__in=matching_users) |
                    Q(employee_id__icontains=search) |
                    Q(email__icontains=search) |
                    Q(phone__icontains=search)
                ).distinct()
    paginator = Paginator(employees, 20)
    page = request.GET.get('page')
    employees_page = paginator.get_page(page)
    departments = Department.objects.filter(is_active=True)
    role_choices = Employee.ROLE_CHOICES
    status_choices = Employee.STATUS_CHOICES
    context = {
        'employees': employees_page,
        'departments': departments,
        'role_choices': role_choices,
        'status_choices': status_choices,
        'current_filters': {
            'department': department_id,
            'role': role,
            'status': status,
            'search': search
        },
        'title': 'Employee Management',
        'urls': get_employee_urls(request),
    }
    return render(request, 'employees/employee_list.html', context)

@login_required
@manager_required
def employee_create_view(request):
    """Create new employee - FIXED for user_id approach"""
    if request.method == 'POST':
        form = EmployeeForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user_data = form.cleaned_data
                    user = User.objects.using('default').create_user(
                        username=user_data['username'],
                        email=user_data['email'],
                        first_name=user_data['first_name'],
                        last_name=user_data['last_name'],
                        password=user_data['password']
                    )
                    employee = form.save(commit=False)
                    employee.user_id = user.id
                    employee.employee_id = generate_unique_code('EMP', 6)
                    while Employee.objects.filter(employee_id=employee.employee_id).exists():
                        employee.employee_id = generate_unique_code('EMP', 6)
                    employee.save()
                    if employee.email:
                        send_email_notification(
                            subject='Welcome to the Team!',
                            message=f'Welcome {employee.full_name}! Your employee ID is {employee.employee_id}.',
                            recipient_list=[employee.email]
                        )
                    messages.success(request, f'Employee {employee.full_name} created successfully!')
                    return redirect(get_business_url(request, 'employees:detail', pk=employee.pk))
            except Exception as e:
                messages.error(request, f'Error creating employee: {str(e)}')
    else:
        form = EmployeeForm()
    context = {
        'form': form,
        'title': 'Add New Employee',
        'urls': get_employee_urls(request),
    }
    return render(request, 'employees/employee_form.html', context)

@login_required
@employee_required()
def employee_detail_view(request, pk):
    """Employee detail view"""
    employee = get_object_or_404(Employee, pk=pk)
    if not request.employee.can_manage_employee(employee) and request.employee != employee:
        messages.error(request, 'You do not have permission to view this employee.')
        return redirect(get_business_url(request, 'employees:list'))
    recent_attendance = employee.attendance_records.all()[:10]
    recent_leaves = employee.leave_requests.all()[:5]
    documents = employee.documents.all()
    trainings = employee.trainings.all()[:5]
    performance_reviews = employee.performance_reviews.all()[:3]
    avg_rating = employee.performance_reviews.aggregate(
        avg_rating=Avg('overall_rating')
    )['avg_rating'] or 0
    context = {
        'employee': employee,
        'recent_attendance': recent_attendance,
        'recent_leaves': recent_leaves,
        'documents': documents,
        'trainings': trainings,
        'performance_reviews': performance_reviews,
        'avg_rating': avg_rating,
        'title': f'Employee - {employee.full_name}',
        'urls': get_employee_urls(request),    
        'edit_url': get_employee_urls(request)['edit'].replace('{pk}', str(employee.pk)),

    }
    return render(request, 'employees/employee_detail.html', context)

@login_required
@manager_required
def employee_edit_view(request, pk):
    """Edit employee - FIXED for user_id approach"""
    employee = get_object_or_404(Employee, pk=pk)
    if request.method == 'POST':
        form = EmployeeForm(request.POST, request.FILES, instance=employee)
        if form.is_valid():
            try:
                with transaction.atomic():
                    employee = form.save(commit=False)
                    if employee.user_id:
                        try:
                            user = User.objects.using('default').get(id=employee.user_id)
                            user.first_name = form.cleaned_data['first_name']
                            user.last_name = form.cleaned_data['last_name']
                            user.email = form.cleaned_data['email']
                            if form.cleaned_data.get('username'):
                                user.username = form.cleaned_data['username']
                            if form.cleaned_data.get('password'):
                                user.set_password(form.cleaned_data['password'])
                            user.save()
                        except User.DoesNotExist:
                            messages.warning(request, 'Associated user account not found.')
                    employee.save()
                    messages.success(request, f'Employee {employee.full_name} updated successfully!')
                    return redirect(get_business_url(request, 'employees:detail', pk=employee.pk))
            except Exception as e:
                messages.error(request, f'Error updating employee: {str(e)}')
    else:
        initial_data = {}
        if employee.user_id:
            try:
                user = User.objects.using('default').get(id=employee.user_id)
                initial_data = {
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'email': user.email,
                    'username': user.username,
                }
            except User.DoesNotExist:
                    pass
        form = EmployeeForm(instance=employee, initial=initial_data)
    context = {
        'form': form,
        'employee': employee,
        'title': f'Edit Employee - {employee.full_name}',
        'urls': get_employee_urls(request),
    }
    return render(request, 'employees/employee_form.html', context)

@login_required
@employee_required()
def attendance_view(request):
    """Attendance management"""
    employee = request.employee
    today = timezone.now().date()
    start_date = today.replace(day=1)
    attendance_records = Attendance.objects.filter(
        employee=employee,
        date__gte=start_date,
        date__lte=today
    ).order_by('-date')
    total_days = attendance_records.count()
    present_days = attendance_records.filter(status='present').count()
    late_days = attendance_records.filter(status='late').count()
    absent_days = attendance_records.filter(status='absent').count()
    today_attendance = attendance_records.filter(date=today).first()
    context = {
        'attendance_records': attendance_records,
        'today_attendance': today_attendance,
        'stats': {
            'total_days': total_days,
            'present_days': present_days,
            'late_days': late_days,
            'absent_days': absent_days,
            'attendance_rate': (present_days / total_days * 100) if total_days > 0 else 0
        },
        'title': 'My Attendance',
        'urls': get_employee_urls(request),
    }
    return render(request, 'employees/attendance.html', context)

@login_required
@employee_required()
@require_POST
def check_in_view(request):
    """Employee check-in"""
    employee = request.employee
    today = timezone.now().date()
    current_time = timezone.now().time()
    attendance, created = Attendance.objects.get_or_create(
        employee=employee,
        date=today,
        defaults={
            'check_in_time': current_time,
            'status': 'present'
        }
    )
    if created:
        messages.success(request, f'Checked in at {current_time.strftime("%H:%M")}')
    else:
        messages.warning(request, 'You have already checked in today.')
    return redirect(get_business_url(request, 'employees:attendance'))

@login_required
@employee_required()
@require_POST
def check_out_view(request):
    """Employee check-out"""
    employee = request.employee
    today = timezone.now().date()
    current_time = timezone.now().time()
    try:
        attendance = Attendance.objects.get(employee=employee, date=today)
        if attendance.check_out_time:
            messages.warning(request, 'You have already checked out today.')
        else:
            attendance.check_out_time = current_time
            attendance.save()
            messages.success(request, f'Checked out at {current_time.strftime("%H:%M")}')
    except Attendance.DoesNotExist:
        messages.error(request, 'Please check in first.')
    return redirect(get_business_url(request, 'employees:attendance'))

@login_required
@employee_required()
def leave_request_view(request):
    """Leave request form"""
    if request.method == 'POST':
        form = LeaveRequestForm(request.POST, request.FILES)
        if form.is_valid():
            leave_request = form.save(commit=False)
            leave_request.employee = request.employee
            leave_request.save()
            if request.employee.supervisor:
                if request.employee.supervisor.user_id:
                    try:
                        supervisor_user = User.objects.using('default').get(id=request.employee.supervisor.user_id)
                        send_email_notification(
                            subject='New Leave Request',
                            message=f'{request.employee.full_name} has submitted a leave request.',
                            recipient_list=[supervisor_user.email]
                        )
                    except User.DoesNotExist:
                        pass
            messages.success(request, 'Leave request submitted successfully!')
            return redirect(get_business_url(request, 'employees:leave_list'))
    else:
        form = LeaveRequestForm()
    context = {
        'form': form,
        'title': 'Request Leave',
        'urls': get_employee_urls(request),
    }
    return render(request, 'employees/leave_request.html', context)

@login_required
@employee_required()
def leave_list_view(request):
    """List employee's leave requests"""
    leaves = request.employee.leave_requests.all().order_by('-created_at')
    paginator = Paginator(leaves, 10)
    page = request.GET.get('page')
    leaves_page = paginator.get_page(page)
    context = {
        'leaves': leaves_page,
        'title': 'My Leave Requests',
        'urls': get_employee_urls(request),
    }
    return render(request, 'employees/leave_list.html', context)

@login_required
@manager_required
def department_list_view(request):
    departments = Department.objects.annotate(num_employees=Count('employees'))
    context = {
        'departments': departments,
        'urls': get_employee_urls(request),
    }
    return render(request, 'employees/department_list.html', context)
@login_required
@manager_required
def department_create_view(request):
    """Create department"""
    if request.method == 'POST':
        form = DepartmentForm(request.POST)
        if form.is_valid():
            department = form.save()
            messages.success(request, f'Department {department.name} created successfully!')
            return redirect(get_business_url(request, 'employees:department_list'))
    else:
        form = DepartmentForm()
    context = {
        'form': form,
        'title': 'Create Department',
        'urls': get_employee_urls(request),
    }
    return render(request, 'employees/department_form.html', context)

@login_required
@ajax_required
def get_employee_data(request, pk):
    """Get employee data for AJAX requests"""
    employee = get_object_or_404(Employee, pk=pk)
    if not request.employee.can_manage_employee(employee) and request.employee != employee:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    data = {
        'id': str(employee.id),
        'name': employee.full_name,
        'employee_id': employee.employee_id,
        'email': employee.email,
        'phone': str(employee.phone) if employee.phone else '',
        'department': employee.department.name if employee.department else '',
        'position': employee.position.title if employee.position else '',
        'role': employee.get_role_display(),
        'status': employee.get_status_display(),
        'hire_date': employee.hire_date.isoformat(),
        'performance_rating': float(employee.performance_rating),
    }
    return JsonResponse(data)

@login_required
@employee_required()
@require_POST
@ajax_required
def take_break_view(request):
    """Start employee break"""
    employee = request.employee
    today = timezone.now().date()
    current_time = timezone.now()
    try:
        attendance = Attendance.objects.get(employee=employee, date=today)
        if not attendance.check_in_time:
            return JsonResponse({
                'success': False,
                'message': 'Please check in first before taking a break.'
            }, status=400)
        if hasattr(attendance, 'break_start_time') and attendance.break_start_time and not getattr(attendance, 'break_end_time', None):
            return JsonResponse({
                'success': False,
                'message': 'You are already on break.'
            }, status=400)
        attendance.break_start_time = current_time
        attendance.save()
        return JsonResponse({
            'success': True,
            'message': f'Break started at {current_time.strftime("%H:%M")}',
            'break_start_time': current_time.strftime("%H:%M")
        })
    except Attendance.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Please check in first.'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error starting break: {str(e)}'
        }, status=500)

@login_required
@employee_required()
@require_POST
@ajax_required
def end_break_view(request):
    """End employee break"""
    employee = request.employee
    today = timezone.now().date()
    current_time = timezone.now()
    try:
        attendance = Attendance.objects.get(employee=employee, date=today)
        if not hasattr(attendance, 'break_start_time') or not attendance.break_start_time:
            return JsonResponse({
                'success': False,
                'message': 'You are not currently on break.'
            }, status=400)
        if hasattr(attendance, 'break_end_time') and attendance.break_end_time:
            return JsonResponse({
                'success': False,
                'message': 'Break has already been ended.'
            }, status=400)
        attendance.break_end_time = current_time
        break_duration = current_time - attendance.break_start_time
        if hasattr(attendance, 'total_break_duration'):
            attendance.total_break_duration = break_duration
        attendance.save()
        duration_minutes = int(break_duration.total_seconds() / 60)
        return JsonResponse({
            'success': True,
            'message': f'Break ended at {current_time.strftime("%H:%M")}. Duration: {duration_minutes} minutes',
            'break_end_time': current_time.strftime("%H:%M"),
            'break_duration': duration_minutes
        })
    except Attendance.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Please check in first.'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error ending break: {str(e)}'
        }, status=500)

@login_required
@employee_required()
@ajax_required
def break_status_view(request):
    """Get current break status"""
    employee = request.employee
    today = timezone.now().date()
    try:
        attendance = Attendance.objects.get(employee=employee, date=today)
        on_break = False
        break_start_time = None
        break_duration = 0
        if hasattr(attendance, 'break_start_time') and attendance.break_start_time:
            if not hasattr(attendance, 'break_end_time') or not attendance.break_end_time:
                on_break = True
                break_start_time = attendance.break_start_time.strftime("%H:%M")
                break_duration = int((timezone.now() - attendance.break_start_time).total_seconds() / 60)
        return JsonResponse({
            'success': True,
            'on_break': on_break,
            'break_start_time': break_start_time,
            'break_duration': break_duration
        })
    except Attendance.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'No attendance record found for today.'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error getting break status: {str(e)}'
        }, status=500)