from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from apps.core.models import TimeStampedModel


class SystemSettings(TimeStampedModel):
    """System-wide configuration settings"""
    
    # Business management settings
    business_approval_required = models.BooleanField(default=True, 
        help_text="Require admin approval for new business registrations")
    trial_period_days = models.IntegerField(default=14,
        help_text="Default trial period in days for new subscriptions")
    auto_suspend_expired = models.BooleanField(default=True,
        help_text="Automatically suspend expired subscriptions")
    payment_grace_period = models.IntegerField(default=7,
        help_text="Grace period in days for overdue payments")
    
    # Notification settings
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    webhook_notifications = models.BooleanField(default=True)
    
    # System limits
    max_employees_per_business = models.IntegerField(default=1000,
        help_text="Maximum employees per business")
    max_customers_per_business = models.IntegerField(default=10000,
        help_text="Maximum customers per business")
    
    # Maintenance
    maintenance_mode = models.BooleanField(default=False,
        help_text="Enable maintenance mode to prevent user access")
    maintenance_message = models.TextField(blank=True,
        help_text="Message to display during maintenance")
    
    class Meta:
        verbose_name = "System Settings"
        verbose_name_plural = "System Settings"
    
    def __str__(self):
        return f"System Settings - Updated {self.updated_at.date()}"
    
    @classmethod
    def get_settings(cls):
        """Get or create system settings"""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings


class AdminActivity(TimeStampedModel):
    """Track admin activities for audit purposes"""
    
    ACTION_CHOICES = [
        ('approve_business', 'Approved Business'),
        ('reject_business', 'Rejected Business'),
        ('suspend_business', 'Suspended Business'),
        ('activate_business', 'Activated Business'),
        ('update_subscription', 'Updated Subscription'),
        ('process_payment', 'Processed Payment'),
        ('update_settings', 'Updated Settings'),
        ('export_data', 'Exported Data'),
        ('bulk_action', 'Bulk Action'),
        ('other', 'Other'),
    ]
    
    admin_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='admin_activities')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    description = models.TextField()
    target_model = models.CharField(max_length=100, blank=True, 
        help_text="Model affected by the action")
    target_id = models.CharField(max_length=100, blank=True,
        help_text="ID of the affected object")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Admin Activity"
        verbose_name_plural = "Admin Activities"
    
    def __str__(self):
        return f"{self.admin_user.username} - {self.get_action_display()} - {self.created_at}"


class SystemAlert(TimeStampedModel):
    """System alerts and notifications for admins"""
    
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
    is_read = models.BooleanField(default=False)
    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='resolved_alerts')
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Auto-generated alerts
    is_auto_generated = models.BooleanField(default=False)
    trigger_condition = models.CharField(max_length=100, blank=True)
    
    class Meta:
        ordering = ['-priority', '-created_at']
        verbose_name = "System Alert"
        verbose_name_plural = "System Alerts"
    
    def __str__(self):
        return f"{self.title} ({self.get_priority_display()})"
    
    def mark_as_resolved(self, user):
        """Mark alert as resolved"""
        self.is_resolved = True
        self.resolved_by = user
        self.resolved_at = timezone.now()
        self.save()


class SystemMetrics(TimeStampedModel):
    """Store system performance metrics"""
    
    # Business metrics
    total_businesses = models.IntegerField(default=0)
    active_businesses = models.IntegerField(default=0)
    pending_businesses = models.IntegerField(default=0)
    
    # Subscription metrics
    total_subscriptions = models.IntegerField(default=0)
    active_subscriptions = models.IntegerField(default=0)
    trial_subscriptions = models.IntegerField(default=0)
    expired_subscriptions = models.IntegerField(default=0)
    
    # Revenue metrics
    daily_revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    monthly_revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # System performance
    avg_response_time = models.FloatField(default=0,
        help_text="Average response time in milliseconds")
    error_rate = models.FloatField(default=0,
        help_text="Error rate as percentage")
    uptime_percentage = models.FloatField(default=100,
        help_text="System uptime as percentage")
    
    # Date for metrics
    metric_date = models.DateField(default=timezone.now)
    
    class Meta:
        ordering = ['-metric_date']
        unique_together = ['metric_date']
        verbose_name = "System Metrics"
        verbose_name_plural = "System Metrics"
    
    def __str__(self):
        return f"Metrics for {self.metric_date}"


class DataExportRequest(TimeStampedModel):
    """Track data export requests"""
    
    EXPORT_TYPES = [
        ('businesses', 'Businesses'),
        ('subscriptions', 'Subscriptions'),
        ('payments', 'Payments'),
        ('users', 'Users'),
        ('analytics', 'Analytics'),
    ]
    
    FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('json', 'JSON'),
        ('pdf', 'PDF'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('expired', 'Expired'),
    ]
    
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='export_requests')
    export_type = models.CharField(max_length=20, choices=EXPORT_TYPES)
    export_format = models.CharField(max_length=20, choices=FORMAT_CHOICES, default='csv')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Filter parameters (stored as JSON)
    filter_params = models.JSONField(default=dict, blank=True)
    
    # Export details
    total_records = models.IntegerField(default=0)
    file_size = models.BigIntegerField(default=0, help_text="File size in bytes")
    download_url = models.URLField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Processing details
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Data Export Request"
        verbose_name_plural = "Data Export Requests"
    
    def __str__(self):
        return f"{self.get_export_type_display()} export by {self.requested_by.username}"
    
    def is_expired(self):
        """Check if export file has expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
