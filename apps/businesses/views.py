import json
from django.db import connection
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Sum, Count, Avg, Q, F
from django.utils import timezone
from datetime import datetime, timedelta
import traceback
from django.views.decorators.http import require_http_methods
from apps.core.decorators import employee_required, business_required
from apps.core.utils import get_business_performance_metrics
from apps.employees.models import Department, Employee
from .models import BusinessMetrics, BusinessGoal, BusinessAlert, QuickAction, DashboardWidget

from .views_settings import (
    settings_overview, business_settings_view, service_settings_view,
    payment_settings_view, notification_settings_view, integration_settings_view,
    backup_settings_view, security_settings_view, user_management_view,
    create_backup_ajax, download_backup, test_integration_ajax
)

def get_business_urls(request):
    """Generate all business URLs for templates with tenant slug."""
    tenant_slug = request.tenant.slug
    base_url = f"/business/{tenant_slug}"
    
    return {
        # Main Dashboard URLs
        'dashboard': f"{base_url}/dashboard/",
        'metrics': f"{base_url}/metrics/",
        'performance': f"{base_url}/performance/",
        'analytics': f"{base_url}/analytics/",
        
        # Settings URLs
        'settings': f"{base_url}/settings/",
        'business_settings': f"{base_url}/settings/business/",
        'service_settings': f"{base_url}/settings/services/",
        'payment_settings': f"{base_url}/settings/payments/",
        'notification_settings': f"{base_url}/settings/notifications/",
        'integration_settings': f"{base_url}/settings/integrations/",
        'backup_settings': f"{base_url}/settings/backup/",
        'security_settings': f"{base_url}/settings/security/",
        'user_management': f"{base_url}/settings/users/",
        
        # Goal URLs
        'goals': f"{base_url}/goals/",
        'goal_create': f"{base_url}/goals/create/",
        'goal_edit': f"{base_url}/goals/{{}}/edit/",
        'goal_delete': f"{base_url}/goals/{{}}/delete/",
        
        # Alert URLs
        'alerts': f"{base_url}/alerts/",
        'alert_create': f"{base_url}/alerts/create/",
        'alert_edit': f"{base_url}/alerts/{{}}/edit/",
        'alert_delete': f"{base_url}/alerts/{{}}/delete/",
        
        # Widget URLs
        'widgets': f"{base_url}/widgets/",
        'widget_add': f"{base_url}/widgets/add/",
        'widget_remove': f"{base_url}/widgets/{{}}/remove/",
        'widget_config': f"{base_url}/widgets/{{}}/config/",
        
        # Quick Action URLs
        'quick_actions': f"{base_url}/quick-actions/",
        'quick_action_create': f"{base_url}/quick-actions/create/",
        'quick_action_edit': f"{base_url}/quick-actions/{{}}/edit/",
        
        # Ajax URLs
        'metrics_data': f"{base_url}/ajax/metrics/",
        'performance_data': f"{base_url}/ajax/performance/",
        'dashboard_data': f"{base_url}/ajax/dashboard/",
        'widget_data': f"{base_url}/ajax/widgets/{{}}/data/",
        'test_integration': f"{base_url}/ajax/test-integration/",
        'create_backup': f"{base_url}/ajax/create-backup/",
        
        # Export URLs
        'export_data': f"{base_url}/export/",
        'download_backup': f"{base_url}/backup/download/",
        
        # Module Navigation
        'services': f"{base_url}/services/",
        'customers': f"{base_url}/customers/",
        'employees': f"{base_url}/employees/",
        'inventory': f"{base_url}/inventory/",
        'payments': f"{base_url}/payments/",
        'reports': f"{base_url}/reports/",
        'expenses': f"{base_url}/expenses/",
        'suppliers': f"{base_url}/suppliers/",
        'subscriptions': f"{base_url}/subscriptions/",
        'notifications': f"{base_url}/notifications/",
    }

@login_required
@employee_required()
def dashboard_view(request):
    """Main business dashboard"""
    today = timezone.now().date()
    business = request.business
    employee = request.employee
    
    # Get today's metrics - Use tenant-safe audit fields
    today_metrics, created = BusinessMetrics.objects.get_or_create(
        date=today,
        defaults={
            'new_customers': 0,
            'returning_customers': 0,
            'total_customers_served': 0,
            'total_services': 0,
            'completed_services': 0,
            'gross_revenue': 0,
        }
    )
    
    # Set audit fields safely for new records
    if created:
        today_metrics.set_created_by(request.user)
        today_metrics.set_updated_by(request.user)
        today_metrics.save()
    
    if created or True:  # Always update for real-time data
        update_daily_metrics(today_metrics, request.user)  # Pass user for audit trail
    
    # Quick stats for cards
    quick_stats = {
        'today_revenue': today_metrics.gross_revenue,
        'today_customers': today_metrics.total_customers_served,
        'today_services': today_metrics.completed_services,
        'employee_attendance': today_metrics.employee_attendance_rate,
    }
    
    # Get recent performance data for charts
    last_7_days = BusinessMetrics.objects.filter(
        date__gte=today - timedelta(days=7)
    ).order_by('date')
    
    # Revenue trend data
    revenue_trend = [
        {
            'date': metric.date.strftime('%Y-%m-%d'),
            'revenue': float(metric.gross_revenue),
            'customers': metric.total_customers_served
        }
        for metric in last_7_days
    ]
    
    # Active goals
    active_goals = BusinessGoal.objects.filter(
        is_active=True,
        end_date__gte=today
    ).order_by('end_date')[:3]
    
    # Recent alerts
    recent_alerts = BusinessAlert.objects.filter(
        is_active=True,
        is_resolved=False
    )
    
    # Filter alerts by role
    if employee.role == 'owner':
        recent_alerts = recent_alerts.filter(for_owners=True)
    elif employee.role == 'manager':
        recent_alerts = recent_alerts.filter(for_managers=True)
    elif recent_alerts.filter(for_all_staff=True).exists():
        recent_alerts = recent_alerts.filter(for_all_staff=True)
    else:
        recent_alerts = recent_alerts.none()
    
    recent_alerts = recent_alerts.order_by('-created_at')[:5]
    
    # Quick actions based on role
    quick_actions = QuickAction.objects.filter(
        is_active=True
    ).order_by('display_order')
    
    available_actions = [
        action for action in quick_actions 
        if action.can_access(employee)
    ][:6]
    
    # Get pending items that need attention
    pending_items = get_pending_dashboard_items(employee)
    
    # Performance comparison (this month vs last month)
    current_month_start = today.replace(day=1)
    last_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
    last_month_end = current_month_start - timedelta(days=1)
    
    current_month_metrics = BusinessMetrics.objects.filter(
        date__gte=current_month_start
    ).aggregate(
        revenue=Sum('gross_revenue'),
        customers=Sum('total_customers_served'),
        services=Sum('completed_services')
    )
    
    last_month_metrics = BusinessMetrics.objects.filter(
        date__gte=last_month_start,
        date__lte=last_month_end
    ).aggregate(
        revenue=Sum('gross_revenue'),
        customers=Sum('total_customers_served'),
        services=Sum('completed_services')
    )
    
    # Calculate percentage changes
    def calculate_change(current, previous):
        if previous and previous > 0:
            return ((current or 0) - previous) / previous * 100
        return 0
    
    performance_comparison = {
        'revenue_change': calculate_change(
            current_month_metrics['revenue'], 
            last_month_metrics['revenue']
        ),
        'customers_change': calculate_change(
            current_month_metrics['customers'], 
            last_month_metrics['customers']
        ),
        'services_change': calculate_change(
            current_month_metrics['services'], 
            last_month_metrics['services']
        ),
    }
    
    # Dashboard widgets
    dashboard_widgets = DashboardWidget.objects.filter(
        is_active=True
    ).order_by('row', 'column')
    
    visible_widgets = [
        widget for widget in dashboard_widgets 
        if widget.can_view(employee)
    ]
    
    context = {
        'today_metrics': today_metrics,
        'quick_stats': quick_stats,
        'revenue_trend': revenue_trend,
        'active_goals': active_goals,
        'recent_alerts': recent_alerts,
        'quick_actions': available_actions,
        'pending_items': pending_items,
        'performance_comparison': performance_comparison,
        'dashboard_widgets': visible_widgets,
        'title': f'{business.name} Dashboard'
    }
    
    return render(request, 'businesses/dashboard.html', context)

def update_daily_metrics(metrics, user=None):
    """Update daily metrics with real-time data"""
    from apps.customers.models import Customer
    from apps.employees.models import Employee, Attendance
    
    today = metrics.date
    
    # Customer metrics
    try:
        new_customers_today = Customer.objects.filter(
            created_at__date=today
        ).count()
        metrics.new_customers = new_customers_today
    except:
        pass  # Customer app might not be ready
    
    # Employee attendance
    try:
        attendance_today = Attendance.objects.filter(date=today)
        present_count = attendance_today.filter(status='present').count()
        total_employees = Employee.objects.filter(is_active=True).count()
        absent_count = total_employees - present_count
        
        metrics.total_employees_present = present_count
        metrics.total_employees_absent = absent_count
        
        # Calculate working hours
        total_hours = 0
        for attendance in attendance_today.filter(check_in_time__isnull=False):
            total_hours += attendance.hours_worked
        metrics.total_working_hours = total_hours
    except:
        pass  # Some fields might not exist yet
    
    # Additional metrics would be calculated here from other apps
    # This will be completed when services and payments apps are ready
    
    # Set updated_by safely when saving
    if user:
        metrics.set_updated_by(user)
    metrics.save()

def get_pending_dashboard_items(employee):
    """Get pending items that need attention"""
    pending_items = []
    
    # Pending leave requests (for managers and owners)
    if employee.role in ['owner', 'manager']:
        try:
            from apps.employees.models import Leave
            pending_leaves = Leave.objects.filter(status='pending').count()
            if pending_leaves > 0:
                pending_items.append({
                    'title': f'{pending_leaves} Pending Leave Request{"s" if pending_leaves > 1 else ""}',
                    'url': '/employees/leave/pending/',
                    'icon': 'fas fa-calendar-alt',
                    'type': 'warning'
                })
        except:
            pass  # Leave model might not be ready
    
    # Low stock items
    try:
        from apps.inventory.models import InventoryItem
        low_stock_count = InventoryItem.objects.filter(
            current_stock__lte=F('minimum_stock_level')
        ).count()
        if low_stock_count > 0:
            pending_items.append({
                'title': f'{low_stock_count} Low Stock Alert{"s" if low_stock_count > 1 else ""}',
                'url': '/inventory/low-stock/',
                'icon': 'fas fa-exclamation-triangle',
                'type': 'danger'
            })
    except:
        pass  # Inventory app might not be ready
    
    # Overdue goals
    try:
        overdue_goals = BusinessGoal.objects.filter(
            is_active=True,
            end_date__lt=timezone.now().date(),
            is_achieved=False
        ).count()
        
        if overdue_goals > 0:
            pending_items.append({
                'title': f'{overdue_goals} Overdue Goal{"s" if overdue_goals > 1 else ""}',
                'url': '/business/goals/',
                'icon': 'fas fa-target',
                'type': 'warning'
            })
    except:
        pass  # BusinessGoal might not be ready
    
    return pending_items

@login_required
@employee_required()
def analytics_view(request):
    """Business analytics and reporting dashboard"""
    period = request.GET.get('period', 'month')  # day, week, month, quarter, year
    
    # Calculate date range based on period
    today = timezone.now().date()
    if period == 'day':
        start_date = today
        end_date = today
    elif period == 'week':
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
    elif period == 'month':
        start_date = today.replace(day=1)
        end_date = (start_date + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    elif period == 'quarter':
        quarter = (today.month - 1) // 3 + 1
        start_date = today.replace(month=(quarter - 1) * 3 + 1, day=1)
        end_date = (start_date + timedelta(days=95)).replace(day=1) - timedelta(days=1)
    else:  # year
        start_date = today.replace(month=1, day=1)
        end_date = today.replace(month=12, day=31)
    
    # Get metrics for the period
    period_metrics = BusinessMetrics.objects.filter(
        date__gte=start_date,
        date__lte=end_date
    ).order_by('date')
    
    # Aggregate data
    totals = period_metrics.aggregate(
        total_revenue=Sum('gross_revenue'),
        total_customers=Sum('total_customers_served'),
        total_services=Sum('completed_services'),
        total_expenses=Sum('total_expenses'),
        avg_service_time=Avg('average_service_time'),
        avg_attendance=Avg('employee_attendance_rate')
    )
    
    # Calculate profit
    profit = (totals['total_revenue'] or 0) - (totals['total_expenses'] or 0)
    profit_margin = (profit / (totals['total_revenue'] or 1)) * 100 if totals['total_revenue'] else 0
    
    # Trend data for charts
    trend_data = [
        {
            'date': metric.date.strftime('%Y-%m-%d'),
            'revenue': float(metric.gross_revenue),
            'expenses': float(metric.total_expenses),
            'profit': float(metric.gross_revenue - metric.total_expenses),
            'customers': metric.total_customers_served,
            'services': metric.completed_services,
            'attendance': float(metric.employee_attendance_rate)
        }
        for metric in period_metrics
    ]
    
    # Payment method breakdown
    payment_breakdown = period_metrics.aggregate(
        cash=Sum('cash_payments'),
        card=Sum('card_payments'),
        mpesa=Sum('mpesa_payments')
    )
    
    # Top performing days
    top_days = period_metrics.order_by('-gross_revenue')[:5]
    
    context = {
        'period': period,
        'start_date': start_date,
        'end_date': end_date,
        'totals': totals,
        'profit': profit,
        'profit_margin': profit_margin,
        'trend_data': trend_data,
        'payment_breakdown': payment_breakdown,
        'top_days': top_days,
        'title': 'Business Analytics'
    }
    
    return render(request, 'businesses/analytics.html', context)

@login_required
@employee_required(['owner', 'manager'])
def goals_view(request):
    """Business goals management"""
    active_goals = BusinessGoal.objects.filter(is_active=True).order_by('end_date')
    completed_goals = BusinessGoal.objects.filter(is_achieved=True).order_by('-achieved_date')[:5]
    
    # Update goal progress (this would typically be done via scheduled tasks)
    for goal in active_goals:
        if goal.goal_type == 'revenue':
            # Calculate current revenue based on goal period
            current_value = calculate_goal_progress(goal)
            goal.update_progress(current_value)
    
    context = {
        'active_goals': active_goals,
        'completed_goals': completed_goals,
        'title': 'Business Goals'
    }
    
    return render(request, 'businesses/goals.html', context)

def calculate_goal_progress(goal):
    """Calculate current progress for a goal"""
    # This is a simplified implementation
    # In a real application, this would calculate based on goal type and period
    
    if goal.goal_type == 'revenue':
        metrics = BusinessMetrics.objects.filter(
            date__gte=goal.start_date,
            date__lte=min(goal.end_date, timezone.now().date())
        )
        return metrics.aggregate(total=Sum('gross_revenue'))['total'] or 0
    
    elif goal.goal_type == 'customers':
        try:
            from apps.customers.models import Customer
            return Customer.objects.filter(
                created_at__date__gte=goal.start_date,
                created_at__date__lte=min(goal.end_date, timezone.now().date())
            ).count()
        except:
            return 0
    
    elif goal.goal_type == 'services':
        metrics = BusinessMetrics.objects.filter(
            date__gte=goal.start_date,
            date__lte=min(goal.end_date, timezone.now().date())
        )
        return metrics.aggregate(total=Sum('completed_services'))['total'] or 0
    
    return goal.current_value

@login_required
@employee_required()
def alerts_view(request):
    """Business alerts management"""
    employee = request.employee
    
    # Get alerts based on role
    alerts = BusinessAlert.objects.filter(is_active=True)
    
    if employee.role == 'owner':
        alerts = alerts.filter(for_owners=True)
    elif employee.role == 'manager':
        alerts = alerts.filter(Q(for_managers=True) | Q(for_all_staff=True))
    else:
        alerts = alerts.filter(for_all_staff=True)
    
    unread_alerts = alerts.filter(is_resolved=False).order_by('-created_at')
    resolved_alerts = alerts.filter(is_resolved=True).order_by('-resolved_at')[:10]
    
    context = {
        'unread_alerts': unread_alerts,
        'resolved_alerts': resolved_alerts,
        'title': 'Business Alerts'
    }
    
    return render(request, 'businesses/alerts.html', context)

@login_required
@employee_required()
def resolve_alert(request, alert_id):
    """Resolve a business alert"""
    alert = get_object_or_404(BusinessAlert, id=alert_id)
    alert.resolve(request.user)
    
    messages.success(request, f'Alert "{alert.title}" has been resolved.')
    return redirect('businesses:alerts')

@login_required
@employee_required()
def api_dashboard_data(request):
    """API endpoint for dashboard data (for AJAX updates)"""
    today = timezone.now().date()
    employee = request.employee
    
    # Get today's key metrics - Use tenant-safe audit approach
    try:
        today_metrics = BusinessMetrics.objects.get(date=today)
        update_daily_metrics(today_metrics, request.user)
    except BusinessMetrics.DoesNotExist:
        today_metrics = BusinessMetrics.objects.create(date=today)
        today_metrics.set_created_by(request.user)
        today_metrics.set_updated_by(request.user)
        today_metrics.save()
        update_daily_metrics(today_metrics, request.user)
    
    data = {
        'today_revenue': float(today_metrics.gross_revenue),
        'today_customers': today_metrics.total_customers_served,
        'today_services': today_metrics.completed_services,
        'employee_attendance': float(today_metrics.employee_attendance_rate),
        'timestamp': timezone.now().isoformat()
    }
    
    return JsonResponse(data)



# Replace the debug_user_context function in apps/businesses/views.py with this fixed version:

@login_required
def debug_user_context(request):
    """
    Debug view to show user context and help diagnose role issues
    Access via: /business/your-business-slug/debug/user-context/
    FIXED: Handle cross-schema User access properly
    """
    context = {
        'debug_mode': True,
        'debug_info': {},
        'title': 'User Context Debug'
    }
    
    # Basic user info
    context['debug_info']['user'] = {
        'id': request.user.id,
        'username': request.user.username,
        'email': request.user.email,
        'full_name': request.user.get_full_name(),
        'is_authenticated': request.user.is_authenticated,
        'is_superuser': request.user.is_superuser,
        'is_staff': request.user.is_staff,
    }
    
    # Add current business info if available
    if hasattr(request, 'tenant') and request.tenant:
        business = request.tenant
        
        # Get owner info directly (no schema context needed)
        try:
            owner = business.owner
            owner_username = owner.username
            owner_email = owner.email
            is_current_user_owner = owner.id == request.user.id
        except Exception as e:
            print(f"Error getting owner info: {e}")
            # Fallback values
            owner_id = getattr(business, 'owner_id', 'Unknown')
            owner_username = 'Error accessing owner'
            owner_email = 'Error accessing owner'
            is_current_user_owner = False
        
        context['debug_info']['business'] = {
            'name': business.name,
            'id': business.id,
            'slug': business.slug,
            'schema_name': business.schema_name,
            'is_verified': business.is_verified,
            'is_active': business.is_active,
            'owner_id': owner_id,
            'owner_username': owner_username,
            'owner_email': owner_email,
            'current_user_id': request.user.id,
            'is_current_user_owner': is_current_user_owner,
        }
        
        # Check schema existence
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s",
                    [business.schema_name]
                )
                schema_exists = bool(cursor.fetchone())
                context['debug_info']['schema_exists'] = schema_exists
        except Exception as e:
            context['debug_info']['schema_exists'] = False
            context['debug_info']['schema_error'] = str(e)
        
        # Check if employee record exists in current tenant schema
        try:
            employee = Employee.objects.get(user_id=request.user.id, is_active=True)
            context['debug_info']['employee'] = {
                'exists': True,
                'employee_id': employee.employee_id,
                'role': employee.role,
                'role_display': employee.get_role_display(),
                'user_id': employee.user_id,
                'department': employee.department.name if employee.department else None,
                'is_active': employee.is_active,
                'can_login': employee.can_login,
                'employment_type': employee.employment_type,
                'status': employee.status,
                'hire_date': employee.hire_date.strftime('%Y-%m-%d') if employee.hire_date else None,
            }
        except Employee.DoesNotExist:
            context['debug_info']['employee'] = {
                'exists': False,
                'error': 'No employee record found for this user in this business',
                'user_id_searched': request.user.id,
                'business_schema': business.schema_name,
            }
            
            # Check if there are any employees in this business
            try:
                all_employees = Employee.objects.filter(is_active=True).values(
                    'id', 'employee_id', 'user_id', 'role'
                )
                context['debug_info']['similar_employees'] = list(all_employees)
            except Exception as e:
                context['debug_info']['similar_employees_error'] = str(e)
            
        except Employee.MultipleObjectsReturned:
            context['debug_info']['employee'] = {
                'exists': True,
                'error': 'Multiple employee records found (this should not happen)',
                'multiple_records': True,
            }
            
            # Get all matching employees
            try:
                multiple_employees = Employee.objects.filter(
                    user_id=request.user.id, is_active=True
                ).values('id', 'employee_id', 'role', 'department__name')
                context['debug_info']['multiple_employee_records'] = list(multiple_employees)
            except Exception as e:
                context['debug_info']['multiple_employees_error'] = str(e)
                
        except Exception as e:
            context['debug_info']['employee'] = {
                'exists': False,
                'error': f'Error checking employee: {str(e)}',
                'exception_type': type(e).__name__,
            }
        
        # Get all employees in this business for reference
        try:
            all_employees = Employee.objects.filter(is_active=True).values(
                'employee_id', 'user_id', 'role', 'department__name'
            )
            context['debug_info']['all_employees'] = list(all_employees)
            context['debug_info']['total_employees'] = len(context['debug_info']['all_employees'])
        except Exception as e:
            context['debug_info']['all_employees_error'] = str(e)
            context['debug_info']['all_employees'] = []
            context['debug_info']['total_employees'] = 0
        
        # Check departments
        try:
            departments = Department.objects.filter(is_active=True).values(
                'name', 'head__employee_id', 'head__user_id', 'employee_count'
            )
            context['debug_info']['departments'] = list(departments)
        except Exception as e:
            context['debug_info']['departments_error'] = str(e)
            context['debug_info']['departments'] = []
    else:
        context['debug_info']['business'] = {
            'error': 'No business context available',
            'request_has_business': hasattr(request, 'business'),
            'business_value': str(getattr(request, 'business', None)),
            'request_path': request.path,
        }
    
    # Get context processor values for comparison
    try:
        from apps.core.context_processors import user_role_context
        role_context = user_role_context(request)
        context['debug_info']['context_processor_output'] = role_context
    except Exception as e:
        context['debug_info']['context_processor_error'] = str(e)
        context['debug_info']['context_processor_output'] = {}
    
    # Additional debug info
    context['debug_info']['request_info'] = {
        'path': request.path,
        'path_info': request.path_info,
        'method': request.method,
        'user_agent': request.META.get('HTTP_USER_AGENT', 'Unknown')[:100],
        'session_key': request.session.session_key if hasattr(request, 'session') else None,
        'csrf_token': request.META.get('CSRF_COOKIE', 'Not available'),
    }
    
    # Schema info
    context['debug_info']['schema_info'] = {
        'current_database': connection.settings_dict.get('NAME', 'Unknown'),
        'is_tenant_context': hasattr(request, 'tenant') and request.tenant is not None,
        'tenant_slug': getattr(request, 'tenant_slug', None),
    }
    
    return render(request, 'debug_user_context.html', context)

# Keep the same fix_user_employee_record function, just make sure it's also properly handling cross-schema access:

@login_required
@require_http_methods(["POST"])
def fix_user_employee_record(request):
    """
    AJAX endpoint to fix missing employee record
    Called from the debug page when user clicks "Fix Employee Record"
    FIXED: Handle cross-schema business owner access
    """
    try:
        # Parse JSON data
        data = json.loads(request.body)
        force_recreate = data.get('force_recreate', False)
        
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    
    if not (hasattr(request, 'business') and request.business):
        return JsonResponse({'error': 'No business context available'}, status=400)
    
    business = request.business
    user = request.user
    
    try:
        # Check if employee already exists
        existing_employee = Employee.objects.filter(user_id=user.id, is_active=True).first()
        if existing_employee and not force_recreate:
            return JsonResponse({
                'success': True,
                'message': f'Employee record already exists: {existing_employee.employee_id}',
                'employee_id': existing_employee.employee_id,
                'role': existing_employee.role,
                'role_display': existing_employee.get_role_display(),
                'already_existed': True
            })
        
        if existing_employee and force_recreate:
            # Deactivate existing record
            existing_employee.is_active = False
            existing_employee.save()
        
        # Create or get management department
        management_dept, dept_created = Department.objects.get_or_create(
            name='Management',
            defaults={
                'description': 'Business management and administration',
                'is_active': True
            }
        )
        
        # Generate unique employee ID
        employee_count = Employee.objects.count()
        employee_id = f"EMP{business.schema_name.upper()[:3]}{employee_count + 1:04d}"
        
        # Ensure uniqueness
        while Employee.objects.filter(employee_id=employee_id).exists():
            employee_count += 1
            employee_id = f"EMP{business.schema_name.upper()[:3]}{employee_count + 1:04d}"
        
        # Get user profile for additional info from public schema
        user_profile = None
        try:
            user_profile = user.profile
        except Exception as profile_error:
            print(f"Could not get user profile: {profile_error}")
        
        # Determine role based on business ownership 
        try:
            is_business_owner = business.owner.id == user.id
        except Exception:
            # Fallback check using owner_id field
            is_business_owner = getattr(business, 'owner_id', None) == user.id
        
        role = 'owner' if is_business_owner else 'manager'
        
        # Create employee record
        employee = Employee.objects.create(
            user_id=user.id,
            employee_id=employee_id,
            role=role,
            employment_type='full_time',
            status='active',
            department=management_dept,
            hire_date=business.created_at.date(),
            is_active=True,
            can_login=True,
            receive_notifications=True,
            phone=user_profile.phone if user_profile else None,
            country='Kenya',  # Default country
        )
        
        # Set department head if this is owner and no head exists
        if role == 'owner' and not management_dept.head:
            management_dept.head = employee
            management_dept.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Employee record created successfully!',
            'employee_id': employee.employee_id,
            'role': employee.role,
            'role_display': employee.get_role_display(),
            'department': management_dept.name,
            'department_created': dept_created,
            'is_department_head': management_dept.head == employee,
            'created_new': True,
            'user_id': employee.user_id,
            'is_business_owner': is_business_owner,
        })
        
    except Exception as e:
        error_details = {
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__,
            'traceback': traceback.format_exc() if request.user.is_superuser else None
        }
        
        print(f"Error creating employee record: {e}")
        print(traceback.format_exc())
        
        return JsonResponse(error_details, status=500)