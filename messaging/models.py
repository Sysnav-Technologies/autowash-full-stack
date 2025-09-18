from django.db import models
from django.utils import timezone
from decimal import Decimal


class SMSProvider(models.Model):
    """SMS Provider configuration for multi-tenant system"""
    
    PROVIDER_CHOICES = [
        ('host_pinnacle', 'Host Pinnacle'),
        ('africas_talking', 'Africa\'s Talking'),
        ('twilio', 'Twilio'),
        ('default', 'Autowash Default'),
    ]
    
    # Basic Info
    name = models.CharField(max_length=50, unique=True)
    provider_type = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    
    # Configuration
    api_endpoint = models.URLField(blank=True, help_text="API base URL")
    rate_per_sms = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('3.00'))
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'messaging_sms_provider'
        verbose_name = 'SMS Provider'
        verbose_name_plural = 'SMS Providers'
    
    def __str__(self):
        return f"{self.name} ({self.get_provider_type_display()})"


class TenantSMSSettings(models.Model):
    """SMS settings for each tenant"""
    
    # Tenant reference (stored as UUID string to avoid cross-database FK issues)
    tenant_id = models.CharField(max_length=36, unique=True, help_text="Tenant UUID")
    tenant_name = models.CharField(max_length=200, help_text="Tenant name for display")
    
    # Provider selection
    provider = models.ForeignKey(SMSProvider, on_delete=models.CASCADE)
    
    # Host Pinnacle specific settings
    hp_instance_id = models.CharField(max_length=255, blank=True, help_text="Host Pinnacle Instance ID")
    hp_access_token = models.CharField(max_length=500, blank=True, help_text="Host Pinnacle Access Token")
    hp_webhook_url = models.URLField(blank=True, help_text="Webhook URL for delivery reports")
    
    # Africa's Talking settings
    at_api_key = models.CharField(max_length=255, blank=True, help_text="Africa's Talking API Key")
    at_username = models.CharField(max_length=100, blank=True, help_text="Africa's Talking Username")
    at_sender_id = models.CharField(max_length=11, blank=True, help_text="Sender ID")
    
    # Twilio settings
    twilio_account_sid = models.CharField(max_length=255, blank=True, help_text="Twilio Account SID")
    twilio_auth_token = models.CharField(max_length=255, blank=True, help_text="Twilio Auth Token")
    twilio_phone_number = models.CharField(max_length=20, blank=True, help_text="Twilio Phone Number")
    
    # General settings
    is_active = models.BooleanField(default=True)
    use_autowash_billing = models.BooleanField(default=True, help_text="Use Autowash billing or direct provider billing")
    
    # Limits
    daily_limit = models.IntegerField(default=1000, help_text="Daily SMS limit")
    monthly_limit = models.IntegerField(default=10000, help_text="Monthly SMS limit")
    
    # Usage tracking
    daily_usage = models.IntegerField(default=0)
    monthly_usage = models.IntegerField(default=0)
    last_reset_date = models.DateField(default=timezone.now)
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'messaging_tenant_sms_settings'
        verbose_name = 'Tenant SMS Settings'
        verbose_name_plural = 'Tenant SMS Settings'
    
    def __str__(self):
        return f"SMS Settings - {self.tenant_name}"
    
    def get_credentials(self):
        """Get provider-specific credentials"""
        if self.provider.provider_type == 'host_pinnacle':
            return {
                'instance_id': self.hp_instance_id,
                'access_token': self.hp_access_token,
                'webhook_url': self.hp_webhook_url
            }
        elif self.provider.provider_type == 'africas_talking':
            return {
                'api_key': self.at_api_key,
                'username': self.at_username,
                'sender_id': self.at_sender_id
            }
        elif self.provider.provider_type == 'twilio':
            return {
                'account_sid': self.twilio_account_sid,
                'auth_token': self.twilio_auth_token,
                'phone_number': self.twilio_phone_number
            }
        return {}
    
    def is_configured(self):
        """Check if provider is properly configured"""
        credentials = self.get_credentials()
        
        if self.provider.provider_type == 'host_pinnacle':
            return bool(credentials.get('instance_id') and credentials.get('access_token'))
        elif self.provider.provider_type == 'africas_talking':
            return bool(credentials.get('api_key') and credentials.get('username'))
        elif self.provider.provider_type == 'twilio':
            return bool(credentials.get('account_sid') and credentials.get('auth_token'))
        elif self.provider.provider_type == 'default':
            return True
        
        return False
    
    def can_send_sms(self):
        """Check if tenant can send SMS (within limits and configured)"""
        if not self.is_active or not self.is_configured():
            return False
        
        if self.daily_usage >= self.daily_limit or self.monthly_usage >= self.monthly_limit:
            return False
        
        return True


class SMSMessage(models.Model):
    """SMS message log and queue"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('queued', 'Queued'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    # Message details
    tenant_settings = models.ForeignKey(TenantSMSSettings, on_delete=models.CASCADE)
    recipient = models.CharField(max_length=20, help_text="Phone number with country code")
    message = models.TextField(help_text="SMS message content")
    sender_id = models.CharField(max_length=11, blank=True, help_text="Sender ID override")
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    
    # Provider response
    provider_message_id = models.CharField(max_length=255, blank=True)
    provider_response = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    
    # Timing
    scheduled_at = models.DateTimeField(null=True, blank=True, help_text="When to send the message")
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    # Billing
    sms_count = models.IntegerField(default=1, help_text="Number of SMS parts")
    cost = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    
    # Metadata
    message_type = models.CharField(max_length=50, default='general', help_text="Type of message for categorization")
    reference = models.CharField(max_length=100, blank=True, help_text="External reference")
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'messaging_sms_message'
        verbose_name = 'SMS Message'
        verbose_name_plural = 'SMS Messages'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant_settings', 'status']),
            models.Index(fields=['status', 'scheduled_at']),
            models.Index(fields=['provider_message_id']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"SMS to {self.recipient} ({self.status}) - {self.tenant_settings.tenant_name}"
    
    @property
    def is_billable(self):
        """Check if this message should be billed"""
        return self.status in ['sent', 'delivered'] and self.cost > 0


class SMSTemplate(models.Model):
    """Reusable SMS templates for tenants"""
    
    TEMPLATE_TYPES = [
        ('appointment_reminder', 'Appointment Reminder'),
        ('payment_confirmation', 'Payment Confirmation'),
        ('service_completion', 'Service Completion'),
        ('marketing', 'Marketing'),
        ('alert', 'Alert'),
        ('custom', 'Custom'),
    ]
    
    # Template details
    tenant_id = models.CharField(max_length=36, help_text="Tenant UUID")
    name = models.CharField(max_length=100)
    template_type = models.CharField(max_length=30, choices=TEMPLATE_TYPES)
    subject = models.CharField(max_length=100, blank=True, help_text="Template description")
    
    # Content
    message = models.TextField(help_text="SMS message template with placeholders like {customer_name}")
    variables = models.JSONField(default=list, help_text="List of available variables")
    
    # Settings
    is_active = models.BooleanField(default=True)
    auto_send = models.BooleanField(default=False, help_text="Automatically send this template for triggers")
    
    # Usage tracking
    usage_count = models.IntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'messaging_sms_template'
        verbose_name = 'SMS Template'
        verbose_name_plural = 'SMS Templates'
        unique_together = ['tenant_id', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"


class SMSWebhook(models.Model):
    """Store webhook data from SMS providers"""
    
    # Webhook details
    provider = models.CharField(max_length=20)
    message = models.ForeignKey(SMSMessage, on_delete=models.CASCADE, null=True, blank=True)
    
    # Webhook data
    webhook_data = models.JSONField(default=dict)
    processed = models.BooleanField(default=False)
    
    # Status info
    delivery_status = models.CharField(max_length=20, blank=True)
    error_code = models.CharField(max_length=10, blank=True)
    error_description = models.TextField(blank=True)
    
    # Timestamps
    received_at = models.DateTimeField(default=timezone.now)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'messaging_sms_webhook'
        verbose_name = 'SMS Webhook'
        verbose_name_plural = 'SMS Webhooks'
        ordering = ['-received_at']
    
    def __str__(self):
        return f"Webhook from {self.provider} at {self.received_at}"
