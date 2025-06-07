from django.db import models
from django.contrib.auth.models import User
from apps.core.tenant_models import TenantTimeStampedModel  # Changed import
from django.utils import timezone
from decimal import Decimal


class BusinessMetrics(TenantTimeStampedModel):  # Changed base class
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

    # REMOVED: Problematic FK fields that cause cross-schema constraints
    # created_by = models.ForeignKey(User, related_name='business_metrics_created', on_delete=models.CASCADE)
    # updated_by = models.ForeignKey(User, related_name='business_metrics_updated', on_delete=models.CASCADE)

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

class BusinessGoal(TenantTimeStampedModel):  # Changed base class
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

class BusinessAlert(TenantTimeStampedModel):  # Changed base class
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

class QuickAction(TenantTimeStampedModel):  # Changed base class
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

class DashboardWidget(TenantTimeStampedModel):  # Changed base class
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