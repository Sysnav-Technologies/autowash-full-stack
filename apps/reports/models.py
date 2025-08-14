from django.db import models
from django.contrib.auth.models import User
from apps.core.tenant_models import TenantTimeStampedModel
from django.utils import timezone
import uuid


class BusinessReport(TenantTimeStampedModel):
    """Simple business reports that are automatically generated"""
    
    REPORT_TYPES = [
        ('daily_summary', 'Daily Business Summary'),
        ('weekly_summary', 'Weekly Business Summary'),
        ('monthly_summary', 'Monthly Business Summary'),
        ('financial_overview', 'Financial Overview'),
        ('customer_analysis', 'Customer Analysis'),
        ('service_performance', 'Service Performance'),
        ('payment_summary', 'Payment Summary'),
        ('employee_performance', 'Employee Performance'),
    ]
    
    STATUS_CHOICES = [
        ('generating', 'Generating'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    FORMAT_CHOICES = [
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
        ('csv', 'CSV'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report_type = models.CharField(max_length=50, choices=REPORT_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Date range for the report
    start_date = models.DateField()
    end_date = models.DateField()
    
    # Report generation
    generated_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_reports'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='generating')
    generated_at = models.DateTimeField(null=True, blank=True)
    
    # Report data (stored as JSON for flexibility)
    report_data = models.JSONField(default=dict)
    
    # File exports
    pdf_file = models.FileField(upload_to='reports/pdf/', null=True, blank=True)
    excel_file = models.FileField(upload_to='reports/excel/', null=True, blank=True)
    csv_file = models.FileField(upload_to='reports/csv/', null=True, blank=True)
    
    # Summary metrics
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_orders = models.IntegerField(default=0)
    total_customers = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['report_type', 'start_date', 'end_date']),
            models.Index(fields=['generated_by', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.start_date} to {self.end_date})"
    
    def get_absolute_url(self):
        return f"/business/{self.tenant.slug}/reports/{self.id}/"


class ReportSchedule(TenantTimeStampedModel):
    """Automated report scheduling"""
    
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
    ]
    
    name = models.CharField(max_length=200)
    report_type = models.CharField(max_length=50, choices=BusinessReport.REPORT_TYPES)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    
    # Recipients
    email_recipients = models.JSONField(default=list, help_text="List of email addresses")
    
    # Scheduling
    is_active = models.BooleanField(default=True)
    last_run = models.DateTimeField(null=True, blank=True)
    next_run = models.DateTimeField(null=True, blank=True)
    
    # Settings
    include_pdf = models.BooleanField(default=True)
    include_excel = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} - {self.get_frequency_display()}"


class QuickInsight(TenantTimeStampedModel):
    """Quick business insights and KPIs"""
    
    INSIGHT_TYPES = [
        ('revenue_trend', 'Revenue Trend'),
        ('customer_growth', 'Customer Growth'),
        ('service_popularity', 'Service Popularity'),
        ('payment_methods', 'Payment Methods'),
        ('peak_hours', 'Peak Business Hours'),
        ('employee_performance', 'Employee Performance'),
    ]
    
    insight_type = models.CharField(max_length=50, choices=INSIGHT_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    trend = models.CharField(max_length=10, choices=[('up', 'Up'), ('down', 'Down'), ('stable', 'Stable')], null=True, blank=True)
    
    # Insight data
    data = models.JSONField(default=dict)
    chart_config = models.JSONField(default=dict)
    
    # Metadata
    date_calculated = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-date_calculated']
        unique_together = ['insight_type', 'date_calculated']
    
    def __str__(self):
        return f"{self.title} - {self.date_calculated}"


class ExportLog(TenantTimeStampedModel):
    """Track report exports and downloads"""
    
    report = models.ForeignKey(BusinessReport, on_delete=models.CASCADE, related_name='exports')
    exported_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        related_name='report_exports'
    )
    export_format = models.CharField(max_length=10, choices=BusinessReport.FORMAT_CHOICES)
    file_size = models.BigIntegerField(default=0)  # in bytes
    download_count = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.report.title} - {self.export_format.upper()} export"
