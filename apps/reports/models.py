from django.db import models
from django.contrib.auth.models import User
from django.db.models import JSONField
from apps.core.tenant_models import TenantTimeStampedModel
from django.utils import timezone
from decimal import Decimal
import uuid

class ReportTemplate(TenantTimeStampedModel):
    """Predefined report templates"""
    
    REPORT_TYPES = [
        ('financial', 'Financial Report'),
        ('sales', 'Sales Report'), 
        ('customer', 'Customer Report'),
        ('employee', 'Employee Report'),
        ('inventory', 'Inventory Report'),
        ('service', 'Service Performance'),
        ('payment', 'Payment Analysis'),
        ('operational', 'Operational Report'),
        ('custom', 'Custom Report'),
    ]
    
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
        ('custom', 'Custom Date Range'),
    ]
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    
    # Report configuration
    data_sources = models.JSONField(default=list, help_text="List of data sources/models")
    filters = models.JSONField(default=dict, help_text="Default filters for the report")
    columns = models.JSONField(default=list, help_text="Columns to include in report")
    aggregations = models.JSONField(default=dict, help_text="Aggregation functions")
    charts = models.JSONField(default=list, help_text="Chart configurations")
    
    # Scheduling
    is_scheduled = models.BooleanField(default=False)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='monthly')
    schedule_time = models.TimeField(null=True, blank=True)
    schedule_day = models.IntegerField(null=True, blank=True, help_text="Day of month for monthly reports")
    
    # Access control
    is_public = models.BooleanField(default=False)
    allowed_roles = models.JSONField(default=list, help_text="Roles that can access this report")
    
    # Settings
    is_active = models.BooleanField(default=True)
    auto_email = models.BooleanField(default=False)
    email_recipients = models.JSONField(default=list)
    
    def __str__(self):
        return self.name
    
    def can_access(self, user):
        """Check if user can access this report"""
        if self.is_public:
            return True
        
        try:
            employee = user.employee_profile
            return employee.role in self.allowed_roles
        except:
            return False
    
    class Meta:
        verbose_name = "Report Template"
        verbose_name_plural = "Report Templates"
        ordering = ['report_type', 'name']

class GeneratedReport(TenantTimeStampedModel):
    """Generated report instances"""
    
    STATUS_CHOICES = [
        ('generating', 'Generating'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('expired', 'Expired'),
    ]
    
    template = models.ForeignKey(ReportTemplate, on_delete=models.CASCADE, related_name='generated_reports')
    report_id = models.UUIDField(default=uuid.uuid4, unique=True)
    
    # Date range
    date_from = models.DateField()
    date_to = models.DateField()
    
    # Generation details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='generating')
    generated_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_reports'
    )
    
    # Report data
    report_data = models.JSONField(default=dict)
    summary_data = models.JSONField(default=dict)
    charts_data = models.JSONField(default=dict)
    
    # File storage
    pdf_file = models.FileField(upload_to='reports/pdf/', blank=True, null=True)
    excel_file = models.FileField(upload_to='reports/excel/', blank=True, null=True)
    csv_file = models.FileField(upload_to='reports/csv/', blank=True, null=True)
    
    # Metadata
    generation_time = models.FloatField(null=True, blank=True, help_text="Time taken to generate in seconds")
    row_count = models.IntegerField(default=0)
    file_size = models.IntegerField(default=0, help_text="File size in bytes")
    
    # Expiry
    expires_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.template.name} - {self.date_from} to {self.date_to}"
    
    @property
    def is_expired(self):
        """Check if report has expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    def mark_completed(self, generation_time=None):
        """Mark report as completed"""
        self.status = 'completed'
        if generation_time:
            self.generation_time = generation_time
        self.save()
    
    def mark_failed(self, error_message=None):
        """Mark report as failed"""
        self.status = 'failed'
        if error_message:
            self.summary_data['error'] = error_message
        self.save()
    
    class Meta:
        verbose_name = "Generated Report"
        verbose_name_plural = "Generated Reports"
        ordering = ['-created_at']

class Dashboard(TenantTimeStampedModel):
    """Custom dashboards for different roles"""
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Dashboard configuration
    layout = models.JSONField(default=dict, help_text="Dashboard layout configuration")
    widgets = models.JSONField(default=list, help_text="Widget configurations")
    filters = models.JSONField(default=dict, help_text="Global dashboard filters")
    
    # Access control
    is_default = models.BooleanField(default=False)
    role = models.CharField(
        max_length=20,
        choices=[
            ('owner', 'Business Owner'),
            ('manager', 'Manager'),
            ('supervisor', 'Supervisor'),
            ('attendant', 'Attendant'),
            ('all', 'All Roles'),
        ],
        default='all'
    )
    
    # Settings
    is_active = models.BooleanField(default=True)
    auto_refresh = models.BooleanField(default=True)
    refresh_interval = models.IntegerField(default=300, help_text="Refresh interval in seconds")
    
    def __str__(self):
        return f"{self.name} ({self.get_role_display()})"
    
    class Meta:
        verbose_name = "Dashboard"
        verbose_name_plural = "Dashboards"
        ordering = ['role', 'name']

class ReportWidget(TenantTimeStampedModel):
    """Individual report widgets for dashboards"""
    
    WIDGET_TYPES = [
        ('metric', 'Single Metric'),
        ('chart', 'Chart'),
        ('table', 'Data Table'),
        ('progress', 'Progress Bar'),
        ('gauge', 'Gauge'),
        ('map', 'Map'),
        ('timeline', 'Timeline'),
        ('list', 'List'),
    ]
    
    CHART_TYPES = [
        ('line', 'Line Chart'),
        ('bar', 'Bar Chart'),
        ('pie', 'Pie Chart'),
        ('doughnut', 'Doughnut Chart'),
        ('area', 'Area Chart'),
        ('scatter', 'Scatter Plot'),
        ('radar', 'Radar Chart'),
    ]
    
    name = models.CharField(max_length=200)
    widget_type = models.CharField(max_length=20, choices=WIDGET_TYPES)
    chart_type = models.CharField(max_length=20, choices=CHART_TYPES, blank=True)
    
    # Data configuration
    data_source = models.CharField(max_length=100, help_text="Model or API endpoint")
    query_config = models.JSONField(default=dict, help_text="Query configuration and filters")
    aggregation_config = models.JSONField(default=dict, help_text="Aggregation functions")
    
    # Display configuration
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    display_config = models.JSONField(default=dict, help_text="Display settings like colors, formatting")
    
    # Layout
    grid_position = models.JSONField(default=dict, help_text="Grid position {x, y, width, height}")
    
    # Cache settings
    cache_duration = models.IntegerField(default=300, help_text="Cache duration in seconds")
    last_cached = models.DateTimeField(null=True, blank=True)
    cached_data = models.JSONField(default=dict)
    
    # Access control
    required_role = models.CharField(
        max_length=20,
        choices=[
            ('owner', 'Owner'),
            ('manager', 'Manager+'),
            ('supervisor', 'Supervisor+'),
            ('attendant', 'All Staff'),
        ],
        default='attendant'
    )
    
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.title
    
    def get_cached_data(self):
        """Get cached data if valid, else return None"""
        if self.last_cached and self.cached_data:
            cache_valid_until = self.last_cached + timezone.timedelta(seconds=self.cache_duration)
            if timezone.now() < cache_valid_until:
                return self.cached_data
        return None
    
    def update_cache(self, data):
        """Update cached data"""
        self.cached_data = data
        self.last_cached = timezone.now()
        self.save(update_fields=['cached_data', 'last_cached'])
    
    class Meta:
        verbose_name = "Report Widget"
        verbose_name_plural = "Report Widgets"
        ordering = ['name']

class BusinessMetrics(TenantTimeStampedModel):
    """Daily business metrics for reporting"""
    date = models.DateField(unique=True)
    
    # Revenue metrics
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    service_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    package_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Customer metrics
    total_customers_served = models.IntegerField(default=0)
    new_customers = models.IntegerField(default=0)
    returning_customers = models.IntegerField(default=0)
    vip_customers_served = models.IntegerField(default=0)
    
    # Service metrics
    total_services = models.IntegerField(default=0)
    completed_services = models.IntegerField(default=0)
    cancelled_services = models.IntegerField(default=0)
    average_service_time = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    
    # Payment metrics
    cash_payments = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    card_payments = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    mpesa_payments = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Employee metrics
    employees_present = models.IntegerField(default=0)
    employees_absent = models.IntegerField(default=0)
    total_working_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    # Operational metrics
    average_queue_time = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    customer_satisfaction = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    
    # Cost metrics
    inventory_consumed_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    employee_costs = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    operational_expenses = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    def __str__(self):
        return f"Business Metrics - {self.date}"
    
    @property
    def profit(self):
        """Calculate profit for the day"""
        total_costs = self.inventory_consumed_value + self.employee_costs + self.operational_expenses
        return self.total_revenue - total_costs
    
    @property
    def profit_margin(self):
        """Calculate profit margin percentage"""
        if self.total_revenue > 0:
            return (self.profit / self.total_revenue) * 100
        return 0
    
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
        total_expected = self.employees_present + self.employees_absent
        if total_expected > 0:
            return (self.employees_present / total_expected) * 100
        return 0
    
    class Meta:
        verbose_name = "Business Metrics"
        verbose_name_plural = "Business Metrics"
        ordering = ['-date']

class ReportSchedule(TenantTimeStampedModel):
    """Scheduled report generation"""
    
    template = models.ForeignKey(ReportTemplate, on_delete=models.CASCADE, related_name='schedules')
    
    # Schedule configuration
    is_active = models.BooleanField(default=True)
    frequency = models.CharField(
        max_length=20,
        choices=ReportTemplate.FREQUENCY_CHOICES,
        default='monthly'
    )
    
    # Timing
    schedule_time = models.TimeField(default='09:00')
    schedule_day = models.IntegerField(null=True, blank=True, help_text="Day of month for monthly reports")
    schedule_weekday = models.IntegerField(null=True, blank=True, help_text="Day of week for weekly reports")
    
    # Email settings
    email_enabled = models.BooleanField(default=True)
    email_recipients = models.JSONField(default=list)
    email_subject = models.CharField(max_length=200, blank=True)
    email_body = models.TextField(blank=True)
    
    # Generation history
    last_generated = models.DateTimeField(null=True, blank=True)
    next_generation = models.DateTimeField(null=True, blank=True)
    generation_count = models.IntegerField(default=0)
    
    # Error tracking
    last_error = models.TextField(blank=True)
    consecutive_failures = models.IntegerField(default=0)
    
    def __str__(self):
        return f"{self.template.name} - {self.get_frequency_display()}"
    
    def calculate_next_generation(self):
        """Calculate next generation time"""
        from datetime import timedelta
        from dateutil.relativedelta import relativedelta
        
        base_time = timezone.now().replace(
            hour=self.schedule_time.hour,
            minute=self.schedule_time.minute,
            second=0,
            microsecond=0
        )
        
        if self.frequency == 'daily':
            self.next_generation = base_time + timedelta(days=1)
        elif self.frequency == 'weekly':
            days_ahead = self.schedule_weekday - base_time.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            self.next_generation = base_time + timedelta(days=days_ahead)
        elif self.frequency == 'monthly':
            if self.schedule_day:
                next_month = base_time + relativedelta(months=1)
                self.next_generation = next_month.replace(day=min(self.schedule_day, 28))
            else:
                self.next_generation = base_time + relativedelta(months=1)
        elif self.frequency == 'quarterly':
            self.next_generation = base_time + relativedelta(months=3)
        elif self.frequency == 'yearly':
            self.next_generation = base_time + relativedelta(years=1)
        
        self.save()
    
    def is_due(self):
        """Check if report generation is due"""
        if not self.is_active or not self.next_generation:
            return False
        return timezone.now() >= self.next_generation
    
    class Meta:
        verbose_name = "Report Schedule"
        verbose_name_plural = "Report Schedules"

class ReportExport(TenantTimeStampedModel):
    """Report export history"""
    
    EXPORT_FORMATS = [
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
        ('csv', 'CSV'),
        ('json', 'JSON'),
    ]
    
    report = models.ForeignKey(GeneratedReport, on_delete=models.CASCADE, related_name='exports')
    format = models.CharField(max_length=10, choices=EXPORT_FORMATS)
    file_path = models.CharField(max_length=500)
    file_size = models.IntegerField(default=0)
    
    exported_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='report_exports'
    )
    
    download_count = models.IntegerField(default=0)
    last_downloaded = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.report.template.name} - {self.get_format_display()}"
    
    def record_download(self):
        """Record a download"""
        self.download_count += 1
        self.last_downloaded = timezone.now()
        self.save(update_fields=['download_count', 'last_downloaded'])
    
    class Meta:
        verbose_name = "Report Export"
        verbose_name_plural = "Report Exports"

class AnalyticsEvent(TenantTimeStampedModel):
    """Track analytics events for business intelligence"""
    
    EVENT_TYPES = [
        ('customer_registered', 'Customer Registered'),
        ('service_completed', 'Service Completed'),
        ('payment_received', 'Payment Received'),
        ('customer_feedback', 'Customer Feedback'),
        ('employee_login', 'Employee Login'),
        ('report_generated', 'Report Generated'),
        ('inventory_low', 'Low Inventory Alert'),
        ('goal_achieved', 'Goal Achieved'),
    ]
    
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    event_data = models.JSONField(default=dict)
    
    # Context
    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='analytics_events'
    )
    employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='analytics_events'
    )
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    session_id = models.CharField(max_length=100, blank=True)
    
    def __str__(self):
        return f"{self.get_event_type_display()} - {self.created_at}"
    
    class Meta:
        verbose_name = "Analytics Event"
        verbose_name_plural = "Analytics Events"
        ordering = ['-created_at']

class KPI(TenantTimeStampedModel):
    """Key Performance Indicators tracking"""
    
    KPI_TYPES = [
        ('revenue', 'Revenue'),
        ('customers', 'Customer Count'),
        ('satisfaction', 'Customer Satisfaction'),
        ('efficiency', 'Operational Efficiency'),
        ('growth', 'Growth Rate'),
        ('retention', 'Customer Retention'),
        ('profitability', 'Profitability'),
    ]
    
    name = models.CharField(max_length=200)
    kpi_type = models.CharField(max_length=20, choices=KPI_TYPES)
    description = models.TextField(blank=True)
    
    # Target configuration
    target_value = models.DecimalField(max_digits=15, decimal_places=2)
    current_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Calculation
    calculation_method = models.CharField(max_length=100, help_text="Method to calculate this KPI")
    data_source = models.CharField(max_length=100, help_text="Data source for calculation")
    
    # Time period
    measurement_period = models.CharField(
        max_length=20,
        choices=[
            ('daily', 'Daily'),
            ('weekly', 'Weekly'), 
            ('monthly', 'Monthly'),
            ('quarterly', 'Quarterly'),
            ('yearly', 'Yearly'),
        ],
        default='monthly'
    )
    
    # Display
    unit = models.CharField(max_length=20, default='units')
    format_string = models.CharField(max_length=50, default='{value} {unit}')
    
    # Status
    is_active = models.BooleanField(default=True)
    last_calculated = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return self.name
    
    @property
    def achievement_percentage(self):
        """Calculate achievement percentage"""
        if self.target_value > 0:
            return (self.current_value / self.target_value) * 100
        return 0
    
    @property
    def status(self):
        """Get KPI status based on achievement"""
        achievement = self.achievement_percentage
        if achievement >= 100:
            return 'excellent'
        elif achievement >= 80:
            return 'good'
        elif achievement >= 60:
            return 'average'
        else:
            return 'poor'
    
    @property
    def formatted_value(self):
        """Get formatted current value"""
        return self.format_string.format(value=self.current_value, unit=self.unit)
    
    @property
    def formatted_target(self):
        """Get formatted target value"""
        return self.format_string.format(value=self.target_value, unit=self.unit)
    
    class Meta:
        verbose_name = "KPI"
        verbose_name_plural = "KPIs"
        ordering = ['kpi_type', 'name']
