# apps/businesses/views_shifts.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db import transaction
from django.core.paginator import Paginator
from django.urls import reverse
from decimal import Decimal
import json
from datetime import date, datetime, timedelta

from apps.core.decorators import employee_required, ajax_required
from .models import Shift, ShiftAttendance


def get_business_url(request, url_name, **kwargs):
    """Helper function to generate URLs with business slug"""
    tenant_slug = request.tenant.slug
    base_url = f"/business/{tenant_slug}"
    
    url_mapping = {
        # Businesses URLs
        'businesses:shifts': f"{base_url}/shifts/",
        'businesses:shift_create': f"{base_url}/shifts/create/",
        'businesses:shift_detail': f"{base_url}/shifts/{{shift_id}}/",
        'businesses:shift_edit': f"{base_url}/shifts/{{shift_id}}/edit/",
        'businesses:shift_attendance': f"{base_url}/shifts/{{shift_id}}/attendance/",
        'businesses:dashboard': f"{base_url}/",
        'businesses:business_settings': f"{base_url}/settings/business/",
        
        # Services URLs
        'services:list': f"{base_url}/services/",
        'services:create': f"{base_url}/services/create/",
        'services:detail': f"{base_url}/services/{{pk}}/",
        'services:edit': f"{base_url}/services/{{pk}}/edit/",
        'services:delete': f"{base_url}/services/{{pk}}/delete/",
        'services:order_list': f"{base_url}/services/orders/",
        'services:order_create': f"{base_url}/services/orders/create/",
        'services:order_detail': f"{base_url}/services/orders/{{pk}}/",
        'services:order_edit': f"{base_url}/services/orders/{{pk}}/edit/",
        'services:quick_order': f"{base_url}/services/quick-order/",
        'services:queue': f"{base_url}/services/queue/",
        'services:attendant_dashboard': f"{base_url}/services/dashboard/",
        'services:pos_dashboard': f"{base_url}/services/pos/",
        'payments:create': f"{base_url}/payments/create/{{order_id}}/",
    }
    
    url = url_mapping.get(url_name, f"{base_url}/")
    
    # Replace placeholders with actual values
    for key, value in kwargs.items():
        url = url.replace(f"{{{key}}}", str(value))
    
    return url


@login_required
@employee_required(['owner', 'manager', 'supervisor'])
def shift_list_view(request):
    """List all shifts with filtering"""
    shifts = Shift.objects.select_related('created_by', 'supervisor').prefetch_related(
        'attendance_records__attendant'
    ).order_by('-date', 'start_time')
    
    # Filters
    status_filter = request.GET.get('status', 'all')
    date_filter = request.GET.get('date')
    
    if status_filter != 'all':
        shifts = shifts.filter(status=status_filter)
    
    if date_filter:
        shifts = shifts.filter(date=date_filter)
    
    # Pagination
    paginator = Paginator(shifts, 20)
    page = request.GET.get('page')
    shifts_page = paginator.get_page(page)
    
    # Get statistics
    today = date.today()
    stats = {
        'today_shifts': Shift.objects.filter(date=today).count(),
        'active_shifts': Shift.objects.filter(status='active').count(),
        'total_attendants_on_duty': ShiftAttendance.objects.filter(
            shift__status='active',
            status__in=['checked_in', 'on_break']
        ).count()
    }
    
    context = {
        'shifts': shifts_page,
        'stats': stats,
        'status_filter': status_filter,
        'date_filter': date_filter,
        'title': 'Shift Management'
    }
    
    return render(request, 'businesses/shifts/shift_list.html', context)


@login_required
@employee_required(['owner', 'manager', 'supervisor'])
def shift_create_view(request):
    """Create new shift"""
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            date_str = request.POST.get('date')
            start_time = request.POST.get('start_time')
            end_time = request.POST.get('end_time')
            supervisor_id = request.POST.get('supervisor_id')
            attendant_ids = request.POST.getlist('attendant_ids')
            target_orders = int(request.POST.get('target_orders', 0))
            target_revenue = Decimal(request.POST.get('target_revenue', '0'))
            notes = request.POST.get('notes', '')
            
            # Validate required fields
            if not all([name, date_str, start_time, end_time]):
                messages.error(request, 'Please fill in all required fields.')
                return render(request, 'businesses/shifts/shift_form.html', {
                    'title': 'Create Shift',
                    'form_data': request.POST
                })
            
            # Parse date
            shift_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # Get supervisor
            supervisor = None
            if supervisor_id:
                from apps.employees.models import Employee
                supervisor = Employee.objects.get(
                    id=supervisor_id,
                    role__in=['owner', 'manager', 'supervisor']
                )
            
            with transaction.atomic():
                # Create shift
                shift = Shift.objects.create(
                    name=name,
                    date=shift_date,
                    start_time=start_time,
                    end_time=end_time,
                    supervisor=supervisor,
                    created_by=request.employee,
                    target_orders=target_orders,
                    target_revenue=target_revenue,
                    notes=notes
                )
                
                # Assign attendants
                if attendant_ids:
                    from apps.employees.models import Employee
                    attendants = Employee.objects.filter(
                        id__in=attendant_ids,
                        role='attendant',
                        is_active=True
                    )
                    
                    for attendant in attendants:
                        ShiftAttendance.objects.create(
                            shift=shift,
                            attendant=attendant,
                            status='scheduled'
                        )
                
                # Send notifications to assigned attendants
                try:
                    from apps.notification.utils import notify_user
                    for attendance in shift.attendance_records.all():
                        if attendance.attendant.user:
                            notify_user(
                                attendance.attendant.user,
                                'Shift Assignment',
                                f'You have been assigned to {shift.name} on {shift.date} from {shift.start_time} to {shift.end_time}',
                                notification_type='info',
                                action_url=f'/business/shifts/{shift.id}/'
                            )
                except ImportError:
                    pass
            
            messages.success(request, f'Shift "{name}" created successfully!')
            return redirect(get_business_url(request, 'businesses:shift_detail', shift_id=shift.id))
            
        except Exception as e:
            messages.error(request, f'Error creating shift: {str(e)}')
    
    # Get available attendants and supervisors
    try:
        from apps.employees.models import Employee
        attendants = Employee.objects.filter(role='attendant', is_active=True)
        supervisors = Employee.objects.filter(
            role__in=['owner', 'manager', 'supervisor'],
            is_active=True
        )
    except ImportError:
        attendants = []
        supervisors = []
    
    context = {
        'attendants': attendants,
        'supervisors': supervisors,
        'title': 'Create Shift',
        'form_data': getattr(request, 'POST', {})
    }
    
    return render(request, 'businesses/shifts/shift_form.html', context)


@login_required
@employee_required(['owner', 'manager', 'supervisor', 'attendant'])
def shift_detail_view(request, pk):
    """Shift detail view with attendance management"""
    shift = get_object_or_404(Shift, pk=pk)
    attendance_records = shift.attendance_records.select_related('attendant').all()
    
    # Check if current user can manage this shift
    can_manage = request.employee.role in ['owner', 'manager', 'supervisor'] or \
                request.employee == shift.supervisor
    
    # Check if current user is assigned to this shift
    user_attendance = None
    if request.employee.role == 'attendant':
        try:
            user_attendance = attendance_records.get(attendant=request.employee)
        except ShiftAttendance.DoesNotExist:
            pass
    
    # Get shift performance if completed
    performance = {}
    if shift.status == 'completed':
        performance = shift.calculate_performance()
    
    context = {
        'shift': shift,
        'attendance_records': attendance_records,
        'can_manage': can_manage,
        'user_attendance': user_attendance,
        'performance': performance,
        'title': f'Shift: {shift.name}'
    }
    
    return render(request, 'businesses/shifts/shift_detail.html', context)


@login_required
@employee_required(['owner', 'manager', 'supervisor'])
@require_http_methods(["POST"])
def start_shift(request, pk):
    """Start a shift"""
    shift = get_object_or_404(Shift, pk=pk)
    
    try:
        shift.start_shift(request.user)
        messages.success(request, f'Shift "{shift.name}" has been started!')
    except Exception as e:
        messages.error(request, f'Error starting shift: {str(e)}')
    
    return redirect(get_business_url(request, 'businesses:shift_detail', shift_id=pk))


@login_required
@employee_required(['owner', 'manager', 'supervisor'])
@require_http_methods(["POST"])
def end_shift(request, pk):
    """End a shift"""
    shift = get_object_or_404(Shift, pk=pk)
    
    try:
        shift.end_shift(request.user)
        messages.success(request, f'Shift "{shift.name}" has been ended!')
    except Exception as e:
        messages.error(request, f'Error ending shift: {str(e)}')
    
    return redirect(get_business_url(request, 'businesses:shift_detail', shift_id=pk))


@login_required
@employee_required()
@require_http_methods(["POST"])
def attendant_check_in(request, pk):
    """Attendant check in to shift"""
    shift = get_object_or_404(Shift, pk=pk)
    
    try:
        attendance = ShiftAttendance.objects.get(
            shift=shift,
            attendant=request.employee
        )
        attendance.check_in()
        messages.success(request, 'Successfully checked in!')
    except ShiftAttendance.DoesNotExist:
        messages.error(request, 'You are not assigned to this shift.')
    except Exception as e:
        messages.error(request, f'Error checking in: {str(e)}')
    
    return redirect(get_business_url(request, 'businesses:shift_detail', shift_id=pk))


@login_required
@employee_required()
@require_http_methods(["POST"])
def attendant_check_out(request, pk):
    """Attendant check out from shift"""
    shift = get_object_or_404(Shift, pk=pk)
    
    try:
        attendance = ShiftAttendance.objects.get(
            shift=shift,
            attendant=request.employee
        )
        attendance.check_out()
        messages.success(request, 'Successfully checked out!')
    except ShiftAttendance.DoesNotExist:
        messages.error(request, 'You are not assigned to this shift.')
    except Exception as e:
        messages.error(request, f'Error checking out: {str(e)}')
    
    return redirect(get_business_url(request, 'businesses:shift_detail', shift_id=pk))


@login_required
@employee_required()
@require_http_methods(["POST"])
def attendant_start_break(request, pk):
    """Start break"""
    shift = get_object_or_404(Shift, pk=pk)
    
    try:
        attendance = ShiftAttendance.objects.get(
            shift=shift,
            attendant=request.employee
        )
        attendance.start_break()
        messages.success(request, 'Break started!')
    except ShiftAttendance.DoesNotExist:
        messages.error(request, 'You are not assigned to this shift.')
    except Exception as e:
        messages.error(request, f'Error starting break: {str(e)}')
    
    return redirect(get_business_url(request, 'businesses:shift_detail', shift_id=pk))


@login_required
@employee_required()
@require_http_methods(["POST"])
def attendant_end_break(request, pk):
    """End break"""
    shift = get_object_or_404(Shift, pk=pk)
    
    try:
        attendance = ShiftAttendance.objects.get(
            shift=shift,
            attendant=request.employee
        )
        attendance.end_break()
        messages.success(request, 'Break ended!')
    except ShiftAttendance.DoesNotExist:
        messages.error(request, 'You are not assigned to this shift.')
    except Exception as e:
        messages.error(request, f'Error ending break: {str(e)}')
    
    return redirect(get_business_url(request, 'businesses:shift_detail', shift_id=pk))


@login_required
@employee_required()
@ajax_required
def get_available_workers_ajax(request):
    """Get available workers for assignment (AJAX)"""
    try:
        from apps.employees.models import Employee
        
        # Get attendants who are currently checked in
        on_duty_attendants = ShiftAttendance.objects.filter(
            shift__status='active',
            status__in=['checked_in', 'on_break']
        ).select_related('attendant')
        
        workers = []
        for attendance in on_duty_attendants:
            workers.append({
                'id': attendance.attendant.id,
                'name': attendance.attendant.full_name,
                'shift': attendance.shift.name,
                'status': attendance.get_status_display()
            })
        
        return JsonResponse({
            'success': True,
            'workers': workers
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


@login_required
@employee_required(['owner', 'manager', 'supervisor'])
def shift_reports_view(request):
    """Shift performance reports"""
    # Date range filter
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if date_from:
        start_date = datetime.strptime(date_from, '%Y-%m-%d').date()
    if date_to:
        end_date = datetime.strptime(date_to, '%Y-%m-%d').date()
    
    # Get shifts in date range
    shifts = Shift.objects.filter(
        date__gte=start_date,
        date__lte=end_date,
        status='completed'
    ).select_related('supervisor').prefetch_related('attendance_records__attendant')
    
    # Calculate summary statistics
    total_shifts = shifts.count()
    total_hours = sum(shift.duration_hours for shift in shifts)
    
    # Attendance statistics
    attendance_records = ShiftAttendance.objects.filter(
        shift__in=shifts,
        status='checked_out'
    ).select_related('attendant')
    
    total_attendance_hours = sum(record.hours_worked for record in attendance_records)
    total_commission_paid = sum(record.total_commission for record in attendance_records)
    
    # Top performers
    from django.db.models import Sum, Avg, Count
    top_performers = attendance_records.values(
        'attendant__employee_id',
        'attendant__user_id'
    ).annotate(
        total_orders=Sum('orders_handled'),
        total_commission=Sum('total_commission'),
        total_hours=Sum('orders_handled'),  # This should be calculated properly
        shifts_worked=Count('shift', distinct=True)
    ).order_by('-total_orders')[:10]
    
    # Add names to top performers (since we can't query properties directly)
    for performer in top_performers:
        if performer['attendant__user_id']:
            try:
                from django.contrib.auth.models import User
                user = User.objects.get(id=performer['attendant__user_id'])
                performer['attendant_name'] = user.get_full_name() or user.username
            except User.DoesNotExist:
                performer['attendant_name'] = f"Employee {performer['attendant__employee_id']}"
        else:
            performer['attendant_name'] = f"Employee {performer['attendant__employee_id']}"
    
    context = {
        'shifts': shifts,
        'start_date': start_date,
        'end_date': end_date,
        'stats': {
            'total_shifts': total_shifts,
            'total_hours': total_hours,
            'total_attendance_hours': total_attendance_hours,
            'total_commission_paid': total_commission_paid,
            'avg_hours_per_shift': total_hours / total_shifts if total_shifts > 0 else 0,
        },
        'top_performers': top_performers,
        'title': 'Shift Reports'
    }
    
    return render(request, 'businesses/shifts/shift_reports.html', context)


@login_required
@employee_required(['owner', 'manager', 'supervisor'])
def shift_edit_view(request, shift_id):
    """Edit a shift"""
    shift = get_object_or_404(Shift, id=shift_id)
    
    if request.method == 'POST':
        try:
            # Update shift details
            shift.name = request.POST.get('name', shift.name)
            shift.date = request.POST.get('date', shift.date)
            shift.start_time = request.POST.get('start_time', shift.start_time)
            shift.end_time = request.POST.get('end_time', shift.end_time)
            
            # Update attendants
            selected_attendant_ids = request.POST.getlist('attendants')
            
            # Remove attendants not selected anymore
            shift.attendance_records.exclude(attendant_id__in=selected_attendant_ids).delete()
            
            # Add new attendants
            for attendant_id in selected_attendant_ids:
                ShiftAttendance.objects.get_or_create(
                    shift=shift,
                    attendant_id=attendant_id,
                    defaults={'status': 'not_checked_in'}
                )
            
            shift.save()
            messages.success(request, f'Shift "{shift.name}" updated successfully!')
            return redirect(get_business_url(request, 'businesses:shift_detail', shift_id=shift.id))
            
        except Exception as e:
            messages.error(request, f'Error updating shift: {str(e)}')
    
    # Get available attendants
    try:
        from apps.employees.models import Employee
        available_attendants = Employee.objects.filter(role='attendant', is_active=True)
        selected_attendants = [att.attendant.id for att in shift.attendance_records.all()]
    except ImportError:
        available_attendants = []
        selected_attendants = []
    
    context = {
        'shift': shift,
        'available_attendants': available_attendants,
        'selected_attendants': selected_attendants,
        'title': f'Edit Shift - {shift.name}'
    }
    return render(request, 'businesses/shifts/form.html', context)


@login_required
@employee_required(['owner', 'manager', 'supervisor'])
def shift_attendance_view(request, shift_id):
    """View shift attendance details"""
    shift = get_object_or_404(Shift, id=shift_id)
    attendance_records = shift.attendance_records.select_related('attendant').all()
    
    # Calculate attendance summary
    checked_in_count = attendance_records.filter(status='checked_in').count()
    on_break_count = attendance_records.filter(status='on_break').count()
    checked_out_count = attendance_records.filter(status='checked_out').count()
    
    context = {
        'shift': shift,
        'attendance_records': attendance_records,
        'checked_in_count': checked_in_count,
        'on_break_count': on_break_count,
        'checked_out_count': checked_out_count,
        'title': f'{shift.name} - Attendance'
    }
    return render(request, 'businesses/shifts/attendance.html', context)


@login_required
@employee_required(['owner', 'manager', 'supervisor'])
@ajax_required
def end_shift_ajax(request, shift_id):
    """End a shift via AJAX"""
    if request.method == 'POST':
        shift = get_object_or_404(Shift, id=shift_id)
        
        try:
            shift.end_shift(request.user)
            return JsonResponse({
                'success': True,
                'message': f'Shift "{shift.name}" has been ended successfully!'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
@employee_required()
@ajax_required
def check_in_ajax(request):
    """Check in attendant via AJAX"""
    if request.method == 'POST':
        attendance_id = request.POST.get('attendance_id')
        
        try:
            attendance = get_object_or_404(ShiftAttendance, id=attendance_id)
            attendance.check_in()
            
            return JsonResponse({
                'success': True,
                'message': 'Successfully checked in!'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
@employee_required()
@ajax_required
def check_out_ajax(request):
    """Check out attendant via AJAX"""
    if request.method == 'POST':
        attendance_id = request.POST.get('attendance_id')
        
        try:
            attendance = get_object_or_404(ShiftAttendance, id=attendance_id)
            attendance.check_out()
            
            return JsonResponse({
                'success': True,
                'message': 'Successfully checked out!'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
@employee_required()
@ajax_required
def break_start_ajax(request):
    """Start break via AJAX"""
    if request.method == 'POST':
        attendance_id = request.POST.get('attendance_id')
        
        try:
            attendance = get_object_or_404(ShiftAttendance, id=attendance_id)
            attendance.start_break()
            
            return JsonResponse({
                'success': True,
                'message': 'Break started!'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
@employee_required()
@ajax_required
def break_end_ajax(request):
    """End break via AJAX"""
    if request.method == 'POST':
        attendance_id = request.POST.get('attendance_id')
        
        try:
            attendance = get_object_or_404(ShiftAttendance, id=attendance_id)
            attendance.end_break()
            
            return JsonResponse({
                'success': True,
                'message': 'Break ended!'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
@employee_required()
@ajax_required
def current_shift_ajax(request):
    """Get current shift for attendant"""
    try:
        current_shift = Shift.objects.filter(
            attendance_records__attendant=request.employee,
            status='active'
        ).first()
        
        if current_shift:
            attendance = current_shift.attendance_records.filter(attendant=request.employee).first()
            return JsonResponse({
                'success': True,
                'shift': {
                    'id': current_shift.id,
                    'name': current_shift.name,
                    'status': current_shift.status,
                    'attendance_status': attendance.status if attendance else 'not_checked_in'
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'No active shift found'
            })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


@login_required
@employee_required()
@ajax_required
def active_shifts_ajax(request):
    """Get all active shifts"""
    try:
        active_shifts = Shift.objects.filter(status='active').select_related('created_by')
        
        shifts_data = []
        for shift in active_shifts:
            shifts_data.append({
                'id': shift.id,
                'name': shift.name,
                'date': shift.date.isoformat(),
                'start_time': shift.start_time.strftime('%H:%M'),
                'end_time': shift.end_time.strftime('%H:%M'),
                'attendant_count': shift.attendance_records.count(),
                'checked_in_count': shift.checked_in_count
            })
        
        return JsonResponse({
            'success': True,
            'shifts': shifts_data
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


@login_required
@employee_required()
def attendant_shift_statistics(request):
    """View for attendants to see their shift statistics and performance"""
    from .utils import ShiftManager
    from django.db.models import Sum, Count, Avg
    from apps.services.models import ServiceOrder, ServiceOrderItem
    
    employee = request.employee
    
    # Get date range from request
    date_range = request.GET.get('range', 'week')  # today, week, month
    
    # Get shift statistics
    try:
        shift_stats = ShiftManager.get_shift_statistics(employee, date_range)
        shift_status = ShiftManager.get_shift_status(employee)
    except Exception as e:
        shift_stats = {}
        shift_status = {'has_active_shift': False}
    
    # Get performance data
    today = timezone.now().date()
    if date_range == 'today':
        start_date = today
    elif date_range == 'week':
        start_date = today - timedelta(days=today.weekday())
    elif date_range == 'month':
        start_date = today.replace(day=1)
    else:
        start_date = today
    
    # Service performance
    my_orders = ServiceOrder.objects.filter(
        assigned_attendant=employee,
        created_at__date__gte=start_date,
        created_at__date__lte=today
    )
    
    completed_orders = my_orders.filter(status='completed')
    
    # Commission calculation
    completed_items = ServiceOrderItem.objects.filter(
        order__assigned_attendant=employee,
        order__status='completed',
        order__actual_end_time__date__gte=start_date,
        order__actual_end_time__date__lte=today
    ).select_related('service')
    
    total_commission = Decimal('0')
    for item in completed_items:
        if item.service.commission_type == 'percentage' and item.service.commission_rate:
            commission = (item.total_price * item.service.commission_rate) / 100
            total_commission += commission
        elif item.service.commission_type == 'fixed' and item.service.fixed_commission:
            commission = item.service.fixed_commission * item.quantity
            total_commission += commission
    
    # Performance metrics
    performance_data = {
        'orders': my_orders.count(),
        'completed_orders': completed_orders.count(),
        'revenue': completed_orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0'),
        'commission': total_commission,
        'avg_order_value': completed_orders.aggregate(avg=Avg('total_amount'))['avg'] or Decimal('0'),
        'completion_rate': (completed_orders.count() / my_orders.count() * 100) if my_orders.count() > 0 else 0,
    }
    
    # Get my shifts in the date range
    my_shifts = Shift.objects.filter(
        attendance_records__attendant=employee,
        date__gte=start_date,
        date__lte=today
    ).distinct().order_by('-date')
    
    # Paginate shifts
    paginator = Paginator(my_shifts, 10)
    page_number = request.GET.get('page')
    shifts_page = paginator.get_page(page_number)
    
    context = {
        'employee': employee,
        'date_range': date_range,
        'shift_stats': shift_stats,
        'shift_status': shift_status,
        'performance_data': performance_data,
        'my_shifts': shifts_page,
        'business_urls': {
            'pos_dashboard': f"/business/{request.tenant.slug}/services/pos/",
            'shifts': f"/business/{request.tenant.slug}/shifts/",
            'dashboard': f"/business/{request.tenant.slug}/",
        },
        'title': 'My Shift Statistics'
    }
    
    return render(request, 'businesses/attendant_shift_stats.html', context)
