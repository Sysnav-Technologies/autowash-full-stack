from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse
from apps.core.tenant_models import TenantTimeStampedModel
import uuid

class NotificationCategory(TenantTimeStampedModel):
    """Categories for organizing notifications"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default='fas fa-bell', help_text="FontAwesome icon class")
    color = models.CharField(max_length=20, default='primary', help_text="Bootstrap color class")
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Notification Category"
        verbose_name_plural = "Notification Categories"
        ordering = ['name']

class Notification(TenantTimeStampedModel):
    """User notifications and alerts"""
    
    NOTIFICATION_TYPES = [
        ('info', 'Information'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('reminder', 'Reminder'),
        ('alert', 'Alert'),
        ('system', 'System'),
    ]
    
    PRIORITY_LEVELS = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    # Identification
    notification_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    
    # Recipients
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    employee = models.ForeignKey(
        'employees.Employee', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='notifications'
    )
    
    # Content
    title = models.CharField(max_length=200)
    message = models.TextField()
    category = models.ForeignKey(
        NotificationCategory, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='notifications'
    )
    
    # Classification
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='info')
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='normal')
    
    # Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    
    # Delivery
    sent_via_email = models.BooleanField(default=False)
    sent_via_sms = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    sms_sent_at = models.DateTimeField(null=True, blank=True)
    
    # Links and Actions
    action_url = models.URLField(blank=True, help_text="URL to redirect when notification is clicked")
    action_text = models.CharField(max_length=100, blank=True, help_text="Text for action button")
    
    # Scheduling
    scheduled_for = models.DateTimeField(null=True, blank=True, help_text="When to send the notification")
    expires_at = models.DateTimeField(null=True, blank=True, help_text="When notification expires")
    
    # Related Objects (Generic Foreign Keys would be ideal here)
    related_object_type = models.CharField(max_length=50, blank=True)
    related_object_id = models.PositiveIntegerField(null=True, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional notification data")
    
    def __str__(self):
        return f"{self.title} - {self.user.get_full_name() or self.user.username}"
    
    @property
    def icon(self):
        """Get icon for notification type"""
        if self.category:
            return self.category.icon
        
        icons = {
            'info': 'fas fa-info-circle',
            'success': 'fas fa-check-circle',
            'warning': 'fas fa-exclamation-triangle',
            'error': 'fas fa-times-circle',
            'reminder': 'fas fa-clock',
            'alert': 'fas fa-exclamation',
            'system': 'fas fa-cog',
        }
        return icons.get(self.notification_type, 'fas fa-bell')
    
    @property
    def color_class(self):
        """Get Bootstrap color class"""
        if self.category:
            return self.category.color
        
        colors = {
            'info': 'info',
            'success': 'success',
            'warning': 'warning',
            'error': 'danger',
            'reminder': 'primary',
            'alert': 'warning',
            'system': 'secondary',
        }
        return colors.get(self.notification_type, 'primary')
    
    @property
    def is_expired(self):
        """Check if notification has expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    @property
    def time_since_created(self):
        """Get human-readable time since creation"""
        from django.utils.timesince import timesince
        return timesince(self.created_at)
    
    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
    
    def mark_as_unread(self):
        """Mark notification as unread"""
        if self.is_read:
            self.is_read = False
            self.read_at = None
            self.save(update_fields=['is_read', 'read_at'])
    
    def archive(self):
        """Archive notification"""
        if not self.is_archived:
            self.is_archived = True
            self.archived_at = timezone.now()
            self.save(update_fields=['is_archived', 'archived_at'])
    
    def get_absolute_url(self):
        """Get URL for notification detail"""
        return reverse('notifications:detail', kwargs={'pk': self.pk})
    
    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['employee', 'is_read']),
            models.Index(fields=['notification_type', 'priority']),
            models.Index(fields=['scheduled_for']),
        ]

class NotificationTemplate(TenantTimeStampedModel):
    """Templates for automated notifications"""
    
    TRIGGER_EVENTS = [
        ('user_registered', 'User Registered'),
        ('order_created', 'Order Created'),
        ('order_completed', 'Order Completed'),
        ('payment_received', 'Payment Received'),
        ('payment_failed', 'Payment Failed'),
        ('inventory_low', 'Low Inventory'),
        ('inventory_out', 'Out of Stock'),
        ('supplier_order_due', 'Supplier Order Due'),
        ('employee_absent', 'Employee Absent'),
        ('service_reminder', 'Service Reminder'),
        ('birthday_reminder', 'Birthday Reminder'),
        ('subscription_expiring', 'Subscription Expiring'),
        ('report_generated', 'Report Generated'),
        ('system_maintenance', 'System Maintenance'),
        ('custom', 'Custom Event'),
    ]
    
    # Template Details
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    trigger_event = models.CharField(max_length=50, choices=TRIGGER_EVENTS)
    
    # Content Templates
    title_template = models.CharField(max_length=200, help_text="Use {{variable}} for dynamic content")
    message_template = models.TextField(help_text="Use {{variable}} for dynamic content")
    
    # Settings
    notification_type = models.CharField(max_length=20, choices=Notification.NOTIFICATION_TYPES, default='info')
    priority = models.CharField(max_length=10, choices=Notification.PRIORITY_LEVELS, default='normal')
    category = models.ForeignKey(NotificationCategory, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Delivery Settings
    send_email = models.BooleanField(default=False)
    send_sms = models.BooleanField(default=False)
    email_template = models.TextField(blank=True, help_text="HTML email template")
    sms_template = models.CharField(max_length=160, blank=True, help_text="SMS message template")
    
    # Targeting
    target_roles = models.JSONField(default=list, help_text="Employee roles to notify")
    target_users = models.ManyToManyField(User, blank=True, help_text="Specific users to notify")
    
    # Timing
    delay_minutes = models.PositiveIntegerField(default=0, help_text="Delay in minutes before sending")
    expires_after_hours = models.PositiveIntegerField(default=24, help_text="Hours until notification expires")
    
    # Status
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_trigger_event_display()})"
    
    def render_title(self, context=None):
        """Render title template with context"""
        if context:
            try:
                from django.template import Template, Context
                template = Template(self.title_template)
                return template.render(Context(context))
            except:
                pass
        return self.title_template
    
    def render_message(self, context=None):
        """Render message template with context"""
        if context:
            try:
                from django.template import Template, Context
                template = Template(self.message_template)
                return template.render(Context(context))
            except:
                pass
        return self.message_template
    
    def create_notification(self, user, context=None, **kwargs):
        """Create notification from template"""
        # Calculate scheduled time
        scheduled_for = timezone.now()
        if self.delay_minutes > 0:
            from datetime import timedelta
            scheduled_for += timedelta(minutes=self.delay_minutes)
        
        # Calculate expiry
        expires_at = None
        if self.expires_after_hours > 0:
            from datetime import timedelta
            expires_at = scheduled_for + timedelta(hours=self.expires_after_hours)
        
        # Create notification
        notification = Notification.objects.create(
            user=user,
            employee=getattr(user, 'employee_profile', None),
            title=self.render_title(context),
            message=self.render_message(context),
            category=self.category,
            notification_type=self.notification_type,
            priority=self.priority,
            scheduled_for=scheduled_for,
            expires_at=expires_at,
            **kwargs
        )
        
        return notification
    
    class Meta:
        verbose_name = "Notification Template"
        verbose_name_plural = "Notification Templates"
        ordering = ['name']

class NotificationPreference(TenantTimeStampedModel):
    """User notification preferences"""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preferences')
    
    # General Preferences
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=True)
    push_notifications = models.BooleanField(default=True)
    
    # Notification Types
    receive_order_notifications = models.BooleanField(default=True)
    receive_payment_notifications = models.BooleanField(default=True)
    receive_inventory_alerts = models.BooleanField(default=True)
    receive_system_notifications = models.BooleanField(default=True)
    receive_reminders = models.BooleanField(default=True)
    receive_reports = models.BooleanField(default=False)
    
    # Delivery Preferences
    quiet_hours_start = models.TimeField(default='22:00', help_text="Start of quiet hours")
    quiet_hours_end = models.TimeField(default='08:00', help_text="End of quiet hours")
    timezone = models.CharField(max_length=50, default='Africa/Nairobi')
    
    # Frequency Settings
    digest_frequency = models.CharField(
        max_length=20,
        choices=[
            ('never', 'Never'),
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
        ],
        default='weekly'
    )
    
    # Categories to mute
    muted_categories = models.ManyToManyField(NotificationCategory, blank=True)
    
    def __str__(self):
        return f"Preferences for {self.user.get_full_name() or self.user.username}"
    
    @property
    def is_quiet_time(self):
        """Check if it's currently quiet hours for this user"""
        from datetime import time
        import pytz
        
        try:
            tz = pytz.timezone(self.timezone)
            now = timezone.now().astimezone(tz).time()
            
            if self.quiet_hours_start <= self.quiet_hours_end:
                # Same day quiet hours (e.g., 22:00 to 23:59)
                return self.quiet_hours_start <= now <= self.quiet_hours_end
            else:
                # Overnight quiet hours (e.g., 22:00 to 08:00)
                return now >= self.quiet_hours_start or now <= self.quiet_hours_end
        except:
            return False
    
    def should_send_notification(self, notification_type, category=None):
        """Check if notification should be sent based on preferences"""
        # Check if category is muted
        if category and category in self.muted_categories.all():
            return False
        
        # Check type-specific preferences
        type_preferences = {
            'order': self.receive_order_notifications,
            'payment': self.receive_payment_notifications,
            'inventory': self.receive_inventory_alerts,
            'system': self.receive_system_notifications,
            'reminder': self.receive_reminders,
            'report': self.receive_reports,
        }
        
        return type_preferences.get(notification_type, True)
    
    class Meta:
        verbose_name = "Notification Preference"
        verbose_name_plural = "Notification Preferences"

class NotificationLog(TenantTimeStampedModel):
    """Log of notification delivery attempts"""
    
    DELIVERY_STATUS = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('bounced', 'Bounced'),
        ('clicked', 'Clicked'),
    ]
    
    DELIVERY_CHANNELS = [
        ('web', 'Web Notification'),
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('push', 'Push Notification'),
    ]
    
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name='delivery_logs')
    
    # Delivery Details
    channel = models.CharField(max_length=20, choices=DELIVERY_CHANNELS)
    status = models.CharField(max_length=20, choices=DELIVERY_STATUS, default='pending')
    
    # Recipient Details
    recipient_email = models.EmailField(blank=True)
    recipient_phone = models.CharField(max_length=20, blank=True)
    
    # Delivery Tracking
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    
    # Error Handling
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    
    # External IDs
    external_id = models.CharField(max_length=100, blank=True, help_text="ID from email/SMS provider")
    
    def __str__(self):
        return f"{self.notification.title} - {self.get_channel_display()} - {self.get_status_display()}"
    
    def mark_as_sent(self):
        """Mark as sent"""
        self.status = 'sent'
        self.sent_at = timezone.now()
        self.save(update_fields=['status', 'sent_at'])
    
    def mark_as_delivered(self):
        """Mark as delivered"""
        self.status = 'delivered'
        self.delivered_at = timezone.now()
        self.save(update_fields=['status', 'delivered_at'])
    
    def mark_as_clicked(self):
        """Mark as clicked"""
        self.status = 'clicked'
        self.clicked_at = timezone.now()
        self.save(update_fields=['status', 'clicked_at'])
    
    def mark_as_failed(self, error_message=""):
        """Mark as failed"""
        self.status = 'failed'
        self.error_message = error_message
        self.retry_count += 1
        
        # Schedule retry if under limit
        if self.retry_count < 3:
            from datetime import timedelta
            self.next_retry_at = timezone.now() + timedelta(minutes=self.retry_count * 30)
        
        self.save(update_fields=['status', 'error_message', 'retry_count', 'next_retry_at'])
    
    class Meta:
        verbose_name = "Notification Log"
        verbose_name_plural = "Notification Logs"
        ordering = ['-created_at']

class NotificationDigest(TenantTimeStampedModel):
    """Periodic notification digests"""
    
    DIGEST_TYPES = [
        ('daily', 'Daily Digest'),
        ('weekly', 'Weekly Digest'),
        ('monthly', 'Monthly Digest'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notification_digests')
    digest_type = models.CharField(max_length=20, choices=DIGEST_TYPES)
    
    # Period Covered
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    
    # Content
    subject = models.CharField(max_length=200)
    html_content = models.TextField()
    text_content = models.TextField()
    
    # Notifications Included
    notifications = models.ManyToManyField(Notification, blank=True)
    notification_count = models.PositiveIntegerField(default=0)
    
    # Delivery
    sent_at = models.DateTimeField(null=True, blank=True)
    is_sent = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.get_digest_type_display()} for {self.user.get_full_name() or self.user.username}"
    
    def generate_content(self):
        """Generate digest content"""
        notifications = self.notifications.all().order_by('-created_at')
        
        # Generate subject
        self.subject = f"{self.get_digest_type_display()} - {notifications.count()} notifications"
        
        # Generate HTML content
        from django.template.loader import render_to_string
        self.html_content = render_to_string('notifications/digest_email.html', {
            'user': self.user,
            'digest': self,
            'notifications': notifications,
        })
        
        # Generate text content
        self.text_content = render_to_string('notifications/digest_email.txt', {
            'user': self.user,
            'digest': self,
            'notifications': notifications,
        })
        
        self.notification_count = notifications.count()
        self.save()
    
    def send(self):
        """Send digest email"""
        if not self.is_sent:
            from django.core.mail import EmailMultiAlternatives
            from django.conf import settings
            
            msg = EmailMultiAlternatives(
                subject=self.subject,
                body=self.text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[self.user.email]
            )
            msg.attach_alternative(self.html_content, "text/html")
            
            try:
                msg.send()
                self.is_sent = True
                self.sent_at = timezone.now()
                self.save(update_fields=['is_sent', 'sent_at'])
                return True
            except Exception as e:
                return False
        
        return False
    
    class Meta:
        verbose_name = "Notification Digest"
        verbose_name_plural = "Notification Digests"
        ordering = ['-period_end']
