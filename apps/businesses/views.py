from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Sum, Count, Avg, Q, F
from django.utils import timezone
from datetime import datetime, timedelta
from apps.core.decorators import employee_required, business_required
from apps.core.utils import get_business_performance_metrics
from .models import BusinessMetrics, BusinessGoal, BusinessAlert, QuickAction, DashboardWidget

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
    
    # Update metrics with real-time data
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