from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from apps.core.tenant_models import TenantTimeStampedModel  
from django.utils import timezone
from decimal import Decimal


class BusinessMetrics(TenantTimeStampedModel): 
    """Daily business metrics tracking"""
    date = models.DateField(unique=True)
    
    # Customer metrics
    new_customers = models.IntegerField(default=0)
    returning_customers = models.IntegerField(default=0)
    total_customers_served = models.IntegerField(default=0)
    
    # Service metrics
    total_services = models.IntegerField(default=0)
    completed_services = models.IntegerField(default=0)
    cancelled_services = models.IntegerField(default=0)
    average_service_time = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Financial metrics
    gross_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_expenses = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    profit_margin = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Payment methods
    cash_payments = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    card_payments = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    mpesa_payments = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Employee metrics
    total_employees_present = models.IntegerField(default=0)
    total_employees_absent = models.IntegerField(default=0)
    total_working_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    
    # Inventory metrics
    low_stock_items = models.IntegerField(default=0)
    out_of_stock_items = models.IntegerField(default=0)

 

    def __str__(self):
        return f"Metrics for {self.date}"
    
    @property
    def customer_retention_rate(self):
        """Calculate customer retention rate"""
        if self.total_customers_served > 0:
            return (self.returning_customers / self.total_customers_served) * 100
        return 0
    
    @property
    def service_completion_rate(self):
        """Calculate service completion rate"""
        if self.total_services > 0:
            return (self.completed_services / self.total_services) * 100
        return 0
    
    @property
    def employee_attendance_rate(self):
        """Calculate employee attendance rate"""
        total_expected = self.total_employees_present + self.total_employees_absent
        if total_expected > 0:
            return (self.total_employees_present / total_expected) * 100
        return 0
    
    class Meta:
        verbose_name = "Business Metrics"
        verbose_name_plural = "Business Metrics"
        ordering = ['-date']

class BusinessGoal(TenantTimeStampedModel): 
    """Business goals and targets"""
    
    GOAL_TYPES = [
        ('revenue', 'Revenue Target'),
        ('customers', 'Customer Target'),
        ('services', 'Service Target'),
        ('efficiency', 'Efficiency Target'),
        ('growth', 'Growth Target'),
    ]
    
    PERIOD_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    goal_type = models.CharField(max_length=20, choices=GOAL_TYPES)
    period = models.CharField(max_length=20, choices=PERIOD_CHOICES)
    
    # Target values
    target_value = models.DecimalField(max_digits=12, decimal_places=2)
    current_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Dates
    start_date = models.DateField()
    end_date = models.DateField()
    
    # Status
    is_active = models.BooleanField(default=True)
    is_achieved = models.BooleanField(default=False)
    achieved_date = models.DateField(null=True, blank=True)
    
    def __str__(self):
        return self.title
    
    @property
    def progress_percentage(self):
        """Calculate progress percentage"""
        if self.target_value > 0:
            return min((self.current_value / self.target_value) * 100, 100)
        return 0
    
    @property
    def days_remaining(self):
        """Calculate days remaining to achieve goal"""
        if self.end_date:
            return (self.end_date - timezone.now().date()).days
        return 0
    
    @property
    def is_overdue(self):
        """Check if goal is overdue"""
        return timezone.now().date() > self.end_date and not self.is_achieved
    
    def update_progress(self, value):
        """Update current progress"""
        self.current_value = value
        if value >= self.target_value and not self.is_achieved:
            self.is_achieved = True
            self.achieved_date = timezone.now().date()
        self.save()
    
    class Meta:
        verbose_name = "Business Goal"
        verbose_name_plural = "Business Goals"
        ordering = ['-created_at']

class BusinessAlert(TenantTimeStampedModel):  
    """Business alerts and notifications"""
    
    ALERT_TYPES = [
        ('info', 'Information'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('success', 'Success'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    title = models.CharField(max_length=200)
    message = models.TextField()
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES, default='info')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    
    # Target audience
    for_owners = models.BooleanField(default=True)
    for_managers = models.BooleanField(default=True)
    for_all_staff = models.BooleanField(default=False)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    # Changed to use Employee ID instead of FK to avoid cross-schema issues
    resolved_by_employee_id = models.IntegerField(null=True, blank=True)
    
    # Auto-expire
    expires_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return self.title
    
    @property
    def is_expired(self):
        """Check if alert is expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    @property
    def resolved_by(self):
        """Get the Employee object that resolved this alert"""
        if not self.resolved_by_employee_id:
            return None
        try:
            from apps.employees.models import Employee
            return Employee.objects.get(id=self.resolved_by_employee_id)
        except Employee.DoesNotExist:
            return None
    
    def resolve(self, user=None, employee=None):
        """Mark alert as resolved"""
        self.is_resolved = True
        self.resolved_at = timezone.now()
        if employee:
            self.resolved_by_employee_id = employee.id
        elif user and hasattr(user, 'employee_profile'):
            self.resolved_by_employee_id = user.employee_profile.id
        self.save()
    
    class Meta:
        verbose_name = "Business Alert"
        verbose_name_plural = "Business Alerts"
        ordering = ['-created_at']

class QuickAction(TenantTimeStampedModel): 
    """Quick actions for dashboard"""
    
    ACTION_TYPES = [
        ('link', 'Link'),
        ('form', 'Form'),
        ('modal', 'Modal'),
        ('api', 'API Call'),
    ]
    
    title = models.CharField(max_length=100)
    description = models.CharField(max_length=200, blank=True)
    icon = models.CharField(max_length=50, default='fas fa-plus')
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES, default='link')
    
    # Action configuration
    url = models.CharField(max_length=200, blank=True)
    css_class = models.CharField(max_length=100, default='btn-primary')
    
    # Permissions
    required_role = models.CharField(
        max_length=20,
        choices=[
            ('all', 'All Staff'),
            ('attendant', 'Attendants+'),
            ('supervisor', 'Supervisors+'),
            ('manager', 'Managers+'),
            ('owner', 'Owner Only'),
        ],
        default='all'
    )
    
    # Display settings
    is_active = models.BooleanField(default=True)
    display_order = models.IntegerField(default=0)
    
    def __str__(self):
        return self.title
    
    def can_access(self, employee):
        """Check if employee can access this action"""
        role_hierarchy = {
            'attendant': 1,
            'supervisor': 2,
            'manager': 3,
            'owner': 4
        }
        
        required_level = role_hierarchy.get(self.required_role.replace('+', ''), 0)
        employee_level = role_hierarchy.get(employee.role, 0)
        
        return employee_level >= required_level or self.required_role == 'all'
    
    class Meta:
        verbose_name = "Quick Action"
        verbose_name_plural = "Quick Actions"
        ordering = ['display_order', 'title']

class DashboardWidget(TenantTimeStampedModel):  
    """Customizable dashboard widgets"""
    
    WIDGET_TYPES = [
        ('stat_card', 'Statistics Card'),
        ('chart', 'Chart'),
        ('table', 'Data Table'),
        ('list', 'Item List'),
        ('progress', 'Progress Bar'),
        ('calendar', 'Calendar'),
    ]
    
    title = models.CharField(max_length=100)
    widget_type = models.CharField(max_length=20, choices=WIDGET_TYPES)
    
    # Layout
    row = models.IntegerField(default=1)
    column = models.IntegerField(default=1)
    width = models.IntegerField(default=3, help_text="Bootstrap column width (1-12)")
    height = models.IntegerField(default=300, help_text="Height in pixels")
    
    # Data configuration
    data_source = models.CharField(max_length=100, blank=True)
    refresh_interval = models.IntegerField(default=300, help_text="Refresh interval in seconds")
    
    # Permissions
    visible_to_roles = models.CharField(
        max_length=200,
        default='owner,manager,supervisor,attendant',
        help_text="Comma-separated list of roles"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.title
    
    def can_view(self, employee):
        """Check if employee can view this widget"""
        visible_roles = [role.strip() for role in self.visible_to_roles.split(',')]
        return employee.role in visible_roles
    
    class Meta:
        verbose_name = "Dashboard Widget"
        verbose_name_plural = "Dashboard Widgets"
        ordering = ['row', 'column']


class Shift(TenantTimeStampedModel):
    """Shift management for staff scheduling"""
    
    STATUS_CHOICES = [
        ('planned', 'Planned'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    name = models.CharField(max_length=100)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    
    # Staff assignment
    supervisor = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supervised_shifts',
        limit_choices_to={'role__in': ['owner', 'manager', 'supervisor']}
    )
    created_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_shifts'
    )
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned')
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    
    # Performance targets
    target_orders = models.PositiveIntegerField(default=0)
    target_revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    actual_orders = models.PositiveIntegerField(default=0)
    actual_revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Notes
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.name} - {self.date}"
    
    @property
    def duration_hours(self):
        """Calculate shift duration in hours"""
        from datetime import datetime, timedelta
        start_dt = datetime.combine(self.date, self.start_time)
        end_dt = datetime.combine(self.date, self.end_time)
        
        # Handle overnight shifts
        if end_dt < start_dt:
            end_dt += timedelta(days=1)
        
        duration = end_dt - start_dt
        return duration.total_seconds() / 3600
    
    @property
    def checked_in_count(self):
        """Count of checked-in attendants"""
        return self.attendance_records.filter(status='checked_in').count()
    
    @property
    def is_active(self):
        """Check if shift is currently active"""
        return self.status == 'active'
    
    @property
    def can_start(self):
        """Check if shift can be started"""
        now = timezone.now()
        shift_start = timezone.make_aware(
            timezone.datetime.combine(self.date, self.start_time)
        )
        return (
            self.status == 'planned' and
            now >= shift_start - timezone.timedelta(minutes=15)  # Allow 15min early start
        )
    
    @property
    def can_end(self):
        """Check if shift can be ended"""
        return self.status == 'active'
    
    def start_shift(self, user=None):
        """Start the shift"""
        if not self.can_start:
            raise ValidationError("Shift cannot be started at this time")
        
        self.status = 'active'
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at'])
        
        # Create notification
        try:
            from apps.notification.utils import notify_role
            notify_role(
                'attendant',
                'Shift Started',
                f'{self.name} has started. Please check in for duty.',
                notification_type='info',
                action_url=f'/business/shifts/{self.id}/'
            )
        except ImportError:
            pass
    
    def end_shift(self, user=None):
        """End the shift"""
        if not self.can_end:
            raise ValidationError("Shift is not active")
        
        self.status = 'completed'
        self.ended_at = timezone.now()
        self.save(update_fields=['status', 'ended_at'])
        
        # Auto check out any remaining attendants
        for attendance in self.attendance_records.filter(status__in=['checked_in', 'on_break']):
            attendance.check_out()
        
        # Update performance metrics
        self.update_performance_metrics()
    
    def update_performance_metrics(self):
        """Update shift performance metrics"""
        from apps.services.models import ServiceOrder
        
        # Get orders processed during this shift
        shift_orders = ServiceOrder.objects.filter(
            created_at__date=self.date,
            created_at__gte=self.started_at,
            status='completed'
        )
        
        if self.ended_at:
            shift_orders = shift_orders.filter(created_at__lte=self.ended_at)
        
        self.actual_orders = shift_orders.count()
        self.actual_revenue = sum(order.total_amount for order in shift_orders)
        self.save(update_fields=['actual_orders', 'actual_revenue'])
    
    def calculate_performance(self):
        """Calculate shift performance metrics"""
        performance = {
            'orders_completion': 0,
            'revenue_achievement': 0,
            'attendance_rate': 0,
            'efficiency_score': 0
        }
        
        # Orders completion rate
        if self.target_orders > 0:
            performance['orders_completion'] = min((self.actual_orders / self.target_orders) * 100, 100)
        
        # Revenue achievement rate
        if self.target_revenue > 0:
            performance['revenue_achievement'] = min((self.actual_revenue / self.target_revenue) * 100, 100)
        
        # Attendance rate
        total_assigned = self.attendance_records.count()
        checked_in = self.attendance_records.filter(check_in_time__isnull=False).count()
        if total_assigned > 0:
            performance['attendance_rate'] = (checked_in / total_assigned) * 100
        
        # Overall efficiency score
        scores = [
            performance['orders_completion'],
            performance['revenue_achievement'],
            performance['attendance_rate']
        ]
        performance['efficiency_score'] = sum(scores) / len(scores) if scores else 0
        
        return performance
    
    class Meta:
        verbose_name = "Shift"
        verbose_name_plural = "Shifts"
        ordering = ['-date', 'start_time']


class ShiftAttendance(TenantTimeStampedModel):
    """Track attendant attendance for shifts"""
    
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('checked_in', 'Checked In'),
        ('on_break', 'On Break'),
        ('checked_out', 'Checked Out'),
        ('absent', 'Absent'),
    ]
    
    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, related_name='attendance_records')
    attendant = models.ForeignKey(
        'employees.Employee',
        on_delete=models.CASCADE,
        related_name='shift_attendance',
        limit_choices_to={'role': 'attendant'}
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    
    # Time tracking
    check_in_time = models.DateTimeField(null=True, blank=True)
    check_out_time = models.DateTimeField(null=True, blank=True)
    break_start_time = models.DateTimeField(null=True, blank=True)
    break_end_time = models.DateTimeField(null=True, blank=True)
    
    # Performance tracking
    orders_handled = models.PositiveIntegerField(default=0)
    total_commission = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Notes
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.attendant.get_full_name()} - {self.shift.name} ({self.shift.date})"
    
    @property
    def hours_worked(self):
        """Calculate hours worked"""
        if not self.check_in_time or not self.check_out_time:
            return 0
        
        total_time = self.check_out_time - self.check_in_time
        
        # Subtract break time if applicable
        if self.break_start_time and self.break_end_time:
            break_duration = self.break_end_time - self.break_start_time
            total_time -= break_duration
        
        return total_time.total_seconds() / 3600
    
    @property
    def is_checked_in(self):
        """Check if attendant is currently checked in"""
        return self.status in ['checked_in', 'on_break']
    
    def check_in(self):
        """Check in attendant for shift"""
        if self.status != 'scheduled':
            raise ValidationError("Attendant is not scheduled or already checked in")
        
        self.status = 'checked_in'
        self.check_in_time = timezone.now()
        self.save(update_fields=['status', 'check_in_time'])
    
    def check_out(self):
        """Check out attendant from shift"""
        if self.status not in ['checked_in', 'on_break']:
            raise ValidationError("Attendant is not checked in")
        
        self.status = 'checked_out'
        self.check_out_time = timezone.now()
        
        # If on break, end the break first
        if self.status == 'on_break' and self.break_start_time and not self.break_end_time:
            self.break_end_time = timezone.now()
        
        self.save(update_fields=['status', 'check_out_time', 'break_end_time'])
        
        # Update performance metrics
        self.update_performance_metrics()
    
    def start_break(self):
        """Start break"""
        if self.status != 'checked_in':
            raise ValidationError("Attendant must be checked in to start break")
        
        self.status = 'on_break'
        self.break_start_time = timezone.now()
        self.save(update_fields=['status', 'break_start_time'])
    
    def end_break(self):
        """End break"""
        if self.status != 'on_break':
            raise ValidationError("Attendant is not on break")
        
        self.status = 'checked_in'
        self.break_end_time = timezone.now()
        self.save(update_fields=['status', 'break_end_time'])
    
    def update_performance_metrics(self):
        """Update performance metrics for this shift"""
        if not self.check_in_time or not self.check_out_time:
            return
        
        # Get orders handled by this attendant during this shift
        try:
            from apps.services.models import ServiceOrder
            shift_orders = ServiceOrder.objects.filter(
                assigned_attendant=self.attendant,
                created_at__date=self.shift.date,
                created_at__gte=self.check_in_time,
                created_at__lte=self.check_out_time,
                status='completed'
            )
            
            self.orders_handled = shift_orders.count()
            
            # Calculate commission from completed orders
            total_commission = 0
            for order in shift_orders:
                for item in order.order_items.all():
                    service = item.service
                    if service.commission_type == 'percentage' and service.commission_rate > 0:
                        commission = (item.unit_price * item.quantity) * (service.commission_rate / 100)
                        total_commission += commission
                    elif service.commission_type == 'fixed' and service.fixed_commission > 0:
                        commission = service.fixed_commission * item.quantity
                        total_commission += commission
            
            self.total_commission = total_commission
            self.save(update_fields=['orders_handled', 'total_commission'])
        except ImportError:
            # ServiceOrder model not available
            pass
    
    class Meta:
        verbose_name = "Shift Attendance"
        verbose_name_plural = "Shift Attendance"
        unique_together = ['shift', 'attendant']
        ordering = ['shift__date', 'shift__start_time', 'attendant__employee_id']