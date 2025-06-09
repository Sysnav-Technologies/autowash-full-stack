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

@login_required
@employee_required()
def dashboard_view(request):
    """Employee dashboard"""
    employee = request.employee
    
    # Get today's attendance
    today = timezone.now().date()
    attendance_today = Attendance.objects.filter(
        employee=employee, 
        date=today
    ).first()
    
    # Get pending leave requests
    pending_leaves = employee.leave_requests.filter(status='pending').count()
    
    # Get upcoming trainings
    upcoming_trainings = Training.objects.filter(
        employees=employee,
        start_date__gte=today,
        status='scheduled'
    )[:3]
    
    # Get recent performance reviews
    recent_reviews = employee.performance_reviews.all()[:2]
    
    # Team statistics (for managers/supervisors)
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
        'title': 'Employee Dashboard'
    }
    return render(request, 'employees/dashboard.html', context)

@login_required
@manager_required
def employee_list_view(request):
    """List all employees"""
    employees = Employee.objects.all().select_related(
        'user', 'department', 'position', 'supervisor'
    )
    
    # Filters
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
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__email__icontains=search) |
            Q(employee_id__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(employees, 20)
    page = request.GET.get('page')
    employees_page = paginator.get_page(page)
    
    # Context data
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
        'title': 'Employee Management'
    }
    return render(request, 'employees/employee_list.html', context)

@login_required
@manager_required
def employee_create_view(request):
    """Create new employee"""
    if request.method == 'POST':
        form = EmployeeForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Create user account
                    user_data = form.cleaned_data
                    user = User.objects.create_user(
                        username=user_data['username'],
                        email=user_data['email'],
                        first_name=user_data['first_name'],
                        last_name=user_data['last_name'],
                        password=user_data['password']
                    )
                    
                    # Create employee profile
                    employee = form.save(commit=False)
                    employee.user = user
                    employee.employee_id = generate_unique_code('EMP', 6)
                    employee.created_by = request.user
                    employee.save()
                    
                    # Send welcome email/SMS
                    if employee.email:
                        send_email_notification(
                            subject='Welcome to the Team!',
                            message=f'Welcome {employee.full_name}! Your employee ID is {employee.employee_id}.',
                            recipient_list=[employee.email]
                        )
                    
                    messages.success(request, f'Employee {employee.full_name} created successfully!')
                    return redirect('employees:detail', pk=employee.pk)
                    
            except Exception as e:
                messages.error(request, f'Error creating employee: {str(e)}')
    else:
        form = EmployeeForm()
    
    context = {
        'form': form,
        'title': 'Add New Employee'
    }
    return render(request, 'employees/employee_form.html', context)

@login_required
@employee_required()
def employee_detail_view(request, pk):
    """Employee detail view"""
    employee = get_object_or_404(Employee, pk=pk)
    
    # Check permissions
    if not request.employee.can_manage_employee(employee) and request.employee != employee:
        messages.error(request, 'You do not have permission to view this employee.')
        return redirect('employees:list')
    
    # Get related data
    recent_attendance = employee.attendance_records.all()[:10]
    recent_leaves = employee.leave_requests.all()[:5]
    documents = employee.documents.all()
    trainings = employee.trainings.all()[:5]
    
    # Performance data
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
        'title': f'Employee - {employee.full_name}'
    }
    return render(request, 'employees/employee_detail.html', context)

@login_required
@manager_required
def employee_edit_view(request, pk):
    """Edit employee"""
    employee = get_object_or_404(Employee, pk=pk)
    
    if request.method == 'POST':
        form = EmployeeForm(request.POST, request.FILES, instance=employee)
        if form.is_valid():
            employee = form.save(commit=False)
            employee.updated_by = request.user
            employee.save()
            
            # Update user information
            user = employee.user
            user.first_name = form.cleaned_data['first_name']
            user.last_name = form.cleaned_data['last_name']
            user.email = form.cleaned_data['email']
            user.save()
            
            messages.success(request, f'Employee {employee.full_name} updated successfully!')
            return redirect('employees:detail', pk=employee.pk)
    else:
        # Pre-populate form with user data
        initial_data = {
            'first_name': employee.user.first_name,
            'last_name': employee.user.last_name,
            'email': employee.user.email,
        }
        form = EmployeeForm(instance=employee, initial=initial_data)
    
    context = {
        'form': form,
        'employee': employee,
        'title': f'Edit Employee - {employee.full_name}'
    }
    return render(request, 'employees/employee_form.html', context)

@login_required
@employee_required()
def attendance_view(request):
    """Attendance management"""
    employee = request.employee
    
    # Get current month attendance
    today = timezone.now().date()
    start_date = today.replace(day=1)
    
    attendance_records = Attendance.objects.filter(
        employee=employee,
        date__gte=start_date,
        date__lte=today
    ).order_by('-date')
    
    # Monthly statistics
    total_days = attendance_records.count()
    present_days = attendance_records.filter(status='present').count()
    late_days = attendance_records.filter(status='late').count()
    absent_days = attendance_records.filter(status='absent').count()
    
    # Check if already checked in today
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
        'title': 'My Attendance'
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
    
    # Check if already checked in
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
    
    return redirect('employees:attendance')

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
    
    return redirect('employees:attendance')

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
            
            # Notify supervisor/manager
            if request.employee.supervisor:
                send_email_notification(
                    subject='New Leave Request',
                    message=f'{request.employee.full_name} has submitted a leave request.',
                    recipient_list=[request.employee.supervisor.email]
                )
            
            messages.success(request, 'Leave request submitted successfully!')
            return redirect('employees:leave_list')
    else:
        form = LeaveRequestForm()
    
    context = {
        'form': form,
        'title': 'Request Leave'
    }
    return render(request, 'employees/leave_request.html', context)

@login_required
@employee_required()
def leave_list_view(request):
    """List employee's leave requests"""
    leaves = request.employee.leave_requests.all().order_by('-created_at')
    
    # Pagination
    paginator = Paginator(leaves, 10)
    page = request.GET.get('page')
    leaves_page = paginator.get_page(page)
    
    context = {
        'leaves': leaves_page,
        'title': 'My Leave Requests'
    }
    return render(request, 'employees/leave_list.html', context)

@login_required
@manager_required
def department_list_view(request):
    """List departments"""
    departments = Department.objects.all().annotate(
        employee_count=Count('employees', filter=Q(employees__is_active=True))
    ).order_by('name')
    
    context = {
        'departments': departments,
        'title': 'Departments'
    }
    return render(request, 'employees/department_list.html', context)

@login_required
@manager_required
def department_create_view(request):
    """Create department"""
    if request.method == 'POST':
        form = DepartmentForm(request.POST)
        if form.is_valid():
            department = form.save(commit=False)
            department.created_by = request.user
            department.save()
            
            messages.success(request, f'Department {department.name} created successfully!')
            return redirect('employees:department_list')
    else:
        form = DepartmentForm()
    
    context = {
        'form': form,
        'title': 'Create Department'
    }
    return render(request, 'employees/department_form.html', context)

@login_required
@ajax_required
def get_employee_data(request, pk):
    """Get employee data for AJAX requests"""
    employee = get_object_or_404(Employee, pk=pk)
    
    # Check permissions
    if not request.employee.can_manage_employee(employee) and request.employee != employee:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    data = {
        'id': employee.id,
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
        # Get today's attendance record
        attendance = Attendance.objects.get(employee=employee, date=today)
        
        # Check if employee is checked in
        if not attendance.check_in_time:
            return JsonResponse({
                'success': False,
                'message': 'Please check in first before taking a break.'
            }, status=400)
        
        # Check if employee is already on break
        if hasattr(attendance, 'break_start_time') and attendance.break_start_time and not getattr(attendance, 'break_end_time', None):
            return JsonResponse({
                'success': False,
                'message': 'You are already on break.'
            }, status=400)
        
        # Start break (you might need to add these fields to your Attendance model)
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
        # Get today's attendance record
        attendance = Attendance.objects.get(employee=employee, date=today)
        
        # Check if employee is on break
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
        
        # End break
        attendance.break_end_time = current_time
        
        # Calculate break duration
        break_duration = current_time - attendance.break_start_time
        if hasattr(attendance, 'total_break_duration'):
            attendance.total_break_duration = break_duration
        
        attendance.save()
        
        # Format break duration for display
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
        
        # Check break status
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