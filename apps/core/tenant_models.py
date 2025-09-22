"""
MySQL-based Multi-Tenant Models
Database-per-tenant approach for MySQL compatibility
"""
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.utils.text import slugify
from django.utils import timezone as django_timezone
from phonenumber_field.modelfields import PhoneNumberField
from apps.core.models import TimeStampedModel, Address, ContactInfo
import uuid


class TenantManager(models.Manager):
    """Manager for tenant operations"""
    
    def get_by_subdomain(self, subdomain):
        """Get tenant by subdomain"""
        try:
            return self.get(subdomain=subdomain, is_active=True)
        except self.model.DoesNotExist:
            return None
    
    def get_by_domain(self, domain):
        """Get tenant by custom domain"""
        try:
            return self.get(custom_domain=domain, is_active=True)
        except self.model.DoesNotExist:
            return None


class Tenant(TimeStampedModel, Address, ContactInfo):
    """
    Tenant model for database-per-tenant architecture
    Each tenant gets its own MySQL database
    """
    # Basic information
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    
    # Domain configuration
    subdomain = models.CharField(
        max_length=63,
        unique=True,
        validators=[RegexValidator(
            regex=r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$',
            message='Subdomain must contain only lowercase letters, numbers, and hyphens'
        )]
    )
    custom_domain = models.CharField(max_length=255, blank=True, unique=True, null=True)
    
    # Database configuration
    database_name = models.CharField(max_length=63, unique=True)
    database_host = models.CharField(max_length=255, default='localhost')
    database_port = models.IntegerField(default=3306)
    database_user = models.CharField(max_length=63)
    database_password = models.CharField(max_length=255)
    
    # Business details
    business_type = models.CharField(
        max_length=50,
        choices=[
            ('car_wash', 'Car Wash'),
            ('detailing', 'Car Detailing'),
            ('full_service', 'Full Service'),
        ],
        default='car_wash'
    )
    
    # Registration details
    registration_number = models.CharField(max_length=100, blank=True)
    tax_number = models.CharField(max_length=100, blank=True)
    
    # Settings
    timezone = models.CharField(max_length=50, default='Africa/Nairobi')
    currency = models.CharField(max_length=3, default='KES')
    language = models.CharField(max_length=10, default='en')
    
    # Business hours
    opening_time = models.TimeField(default='08:00')
    closing_time = models.TimeField(default='18:00')
    
    # Status
    is_active = models.BooleanField(default=False)  # Changed default to False - requires approval
    is_verified = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)  # New approval status
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_tenants')
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, help_text="Reason for rejection if applicable")
    
    # Subscription requirement - every business must have a subscription
    subscription = models.ForeignKey(
        'subscriptions.Subscription', 
        on_delete=models.PROTECT, 
        null=True, 
        blank=True,
        related_name='tenant'
    )
    
    # Owner
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='owned_tenants'
    )
    
    # Subscription limits
    max_employees = models.IntegerField(default=5)
    max_customers = models.IntegerField(default=100)
    
    # Logo
    logo = models.ImageField(upload_to='tenant_logos/', blank=True, null=True)
    
    # Additional settings 
    api_key = models.CharField(max_length=255, blank=True, help_text='API key for third-party integrations')
    auto_backup_enabled = models.BooleanField(default=True, help_text='Enable automatic backups')
    auto_payment_confirmation = models.BooleanField(default=False, help_text='Automatically confirm payments')
    default_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=16.0, help_text='Default tax rate percentage')
    last_backup_date = models.DateTimeField(null=True, blank=True, help_text='Last backup timestamp')
    
    objects = TenantManager()
    
    class Meta:
        verbose_name = "Tenant"
        verbose_name_plural = "Tenants"
        db_table = 'core_tenant'
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        """Override save to generate slug and database name"""
        if not self.slug:
            self.slug = slugify(self.name)
            
            # Ensure unique slug
            original_slug = self.slug
            counter = 1
            while Tenant.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        
        if not self.database_name:
            # Generate safe database name with autowash_ prefix
            db_slug = self.slug.replace('-', '_')
            if not db_slug.startswith('autowash_'):
                self.database_name = f"autowash_{db_slug}"
            else:
                self.database_name = db_slug
            # Truncate to MySQL max length
            self.database_name = self.database_name[:63]
        
        if not self.subdomain:
            self.subdomain = self.slug
        
        super().save(*args, **kwargs)
    
    @property
    def database_config(self):
        """Get database configuration for this tenant"""
        from django.conf import settings
        # Base configuration on the default database but with tenant-specific values
        config = settings.DATABASES['default'].copy()
        config.update({
            'NAME': self.database_name,
            'USER': self.database_user,
            'PASSWORD': self.database_password,
            'HOST': self.database_host,
            'PORT': self.database_port,
        })
        return config
    
    @property
    def primary_domain(self):
        """Get the primary domain for this tenant"""
        if self.custom_domain:
            return self.custom_domain
        return f"{self.subdomain}.autowash.co.ke"
    
    def get_absolute_url(self):
        """Get the URL for this tenant"""
        from django.urls import reverse
        return reverse('tenant_dashboard', kwargs={'tenant_slug': self.slug})
    
    def tenant_database_exists(self):
        """Check if the tenant database exists"""
        try:
            from apps.core.database_router import TenantDatabaseManager
            manager = TenantDatabaseManager()
            return manager.database_exists(self.database_name)
        except Exception as e:
            print(f"Error checking tenant database existence for {self.name}: {e}")
            return False


class TenantUser(models.Model):
    """
    Association between users and tenants
    Allows users to be members of multiple tenants
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tenant_memberships')
    
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('admin', 'Administrator'),
        ('manager', 'Manager'),
        ('employee', 'Employee'),
        ('viewer', 'Viewer'),
    ]
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='employee')
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('tenant', 'user')
        verbose_name = "Tenant User"
        verbose_name_plural = "Tenant Users"
    
    def __str__(self):
        return f"{self.user.username} - {self.tenant.name} ({self.role})"


class TenantSettings(models.Model):
    """Settings specific to each tenant"""
    tenant_id = models.UUIDField(unique=True, help_text="ID of the tenant this settings belongs to")
    
    # Basic Business Settings
    business_name = models.CharField(max_length=200, blank=True)
    tagline = models.CharField(max_length=500, blank=True, help_text="Business tagline or slogan")
    default_currency = models.CharField(max_length=3, default='KES', choices=[
        ('KES', 'Kenyan Shilling'),
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
        ('GBP', 'British Pound'),
    ])
    timezone = models.CharField(max_length=50, default='Africa/Nairobi')
    
    # Notification Settings
    sms_notifications = models.BooleanField(default=True, help_text="Send SMS notifications to customers")
    email_notifications = models.BooleanField(default=True, help_text="Send email notifications")
    whatsapp_notifications = models.BooleanField(default=False, help_text="Send WhatsApp notifications")
    push_notifications = models.BooleanField(default=False, help_text="Send push notifications")
    
    # Customer Notifications
    customer_booking_confirmations = models.BooleanField(default=True)
    customer_payment_receipts = models.BooleanField(default=True)
    customer_service_reminders = models.BooleanField(default=True)
    customer_marketing_messages = models.BooleanField(default=False)
    notify_booking_confirmation = models.BooleanField(default=True, help_text="Notify customers when booking is confirmed")
    notify_service_reminder = models.BooleanField(default=True, help_text="Send service reminders to customers")
    notify_service_complete = models.BooleanField(default=True, help_text="Notify customers when service is complete")
    
    # Staff Notifications
    staff_new_bookings = models.BooleanField(default=True)
    staff_payment_alerts = models.BooleanField(default=True)
    staff_daily_summaries = models.BooleanField(default=True)
    
    # Feature Flags
    enable_loyalty_program = models.BooleanField(default=False)
    enable_online_booking = models.BooleanField(default=True)
    enable_mobile_app = models.BooleanField(default=False)
    enable_pos_integration = models.BooleanField(default=False)
    enable_inventory_tracking = models.BooleanField(default=True)
    enable_employee_attendance = models.BooleanField(default=True)
    
    # Payment Settings
    auto_payment_confirmation = models.BooleanField(default=True)
    require_payment_before_service = models.BooleanField(default=False)
    default_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    mpesa_auto_confirm = models.BooleanField(default=True)
    tax_number = models.CharField(max_length=100, blank=True, help_text="Business tax/VAT number")
    tax_inclusive_pricing = models.BooleanField(default=True, help_text="Include tax in displayed prices")
    accept_cash = models.BooleanField(default=True, help_text="Accept cash payments")
    accept_mpesa = models.BooleanField(default=True, help_text="Accept M-Pesa payments")
    accept_card = models.BooleanField(default=False, help_text="Accept card payments")
    accept_bank_transfer = models.BooleanField(default=False, help_text="Accept bank transfers")
    
    # Service Settings
    auto_assign_services = models.BooleanField(default=False)
    require_service_confirmation = models.BooleanField(default=True)
    service_buffer_time = models.IntegerField(default=15, help_text="Buffer time between services in minutes")
    default_service_duration = models.IntegerField(default=30, help_text="Default service duration in minutes")
    max_advance_booking_days = models.IntegerField(default=30, help_text="Maximum days customers can book in advance")
    min_advance_booking_hours = models.IntegerField(default=2, help_text="Minimum hours notice required for booking")
    allow_online_booking = models.BooleanField(default=True, help_text="Enable online booking system")
    require_customer_phone = models.BooleanField(default=True, help_text="Require phone number for all bookings")
    allow_same_day_booking = models.BooleanField(default=True, help_text="Allow bookings for the same day")
    auto_confirm_bookings = models.BooleanField(default=False, help_text="Automatically confirm new bookings")
    
    # Backup Settings
    auto_backup_enabled = models.BooleanField(default=True)
    backup_frequency = models.CharField(max_length=20, default='weekly', choices=[
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ])
    backup_retention_days = models.IntegerField(default=30)
    backup_email_notifications = models.BooleanField(default=True)
    backup_to_email = models.EmailField(blank=True, help_text="Email address to send backups to")
    backup_to_cloud = models.BooleanField(default=False)
    
    # Branding
    primary_color = models.CharField(max_length=7, default='#007bff')
    secondary_color = models.CharField(max_length=7, default='#6c757d')
    logo_url = models.URLField(blank=True)
    business_logo = models.ImageField(upload_to='business_logos/', blank=True, null=True, help_text="Upload your business logo")
    receipt_footer = models.TextField(blank=True, help_text="Custom footer text for receipts and invoices")
    
    # Business Hours
    monday_is_open = models.BooleanField(default=True)
    monday_open = models.TimeField(null=True, blank=True)
    monday_close = models.TimeField(null=True, blank=True)
    tuesday_is_open = models.BooleanField(default=True)
    tuesday_open = models.TimeField(null=True, blank=True)
    tuesday_close = models.TimeField(null=True, blank=True)
    wednesday_is_open = models.BooleanField(default=True)
    wednesday_open = models.TimeField(null=True, blank=True)
    wednesday_close = models.TimeField(null=True, blank=True)
    thursday_is_open = models.BooleanField(default=True)
    thursday_open = models.TimeField(null=True, blank=True)
    thursday_close = models.TimeField(null=True, blank=True)
    friday_is_open = models.BooleanField(default=True)
    friday_open = models.TimeField(null=True, blank=True)
    friday_close = models.TimeField(null=True, blank=True)
    saturday_is_open = models.BooleanField(default=True)
    saturday_open = models.TimeField(null=True, blank=True)
    saturday_close = models.TimeField(null=True, blank=True)
    sunday_is_open = models.BooleanField(default=False)
    sunday_open = models.TimeField(null=True, blank=True)
    sunday_close = models.TimeField(null=True, blank=True)
    
    # Contact Settings
    contact_phone = models.CharField(max_length=20, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_address = models.TextField(blank=True)
    website_url = models.URLField(blank=True)
    
    # Social Media
    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(default=django_timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Tenant Settings"
        verbose_name_plural = "Tenant Settings"
    
    def __str__(self):
        return f"Settings for {self.business_name or self.tenant_id}"
    
    def is_open_now(self):
        """Check if business is currently open"""
        from datetime import datetime
        import pytz
        
        try:
            tz = pytz.timezone(self.timezone)
            now = datetime.now(tz)
            current_day = now.strftime('%A').lower()
            current_time = now.time()
            
            open_field = f"{current_day}_open"
            close_field = f"{current_day}_close"
            
            open_time = getattr(self, open_field)
            close_time = getattr(self, close_field)
            
            if open_time and close_time:
                return open_time <= current_time <= close_time
            return False
        except:
            return False


class TenantBackup(models.Model):
    """Model to track tenant database backups"""
    tenant_id = models.UUIDField(help_text="ID of the tenant this backup belongs to")
    backup_id = models.CharField(max_length=100, unique=True)
    
    # Backup details
    backup_type = models.CharField(max_length=20, choices=[
        ('full', 'Full Backup'),
        ('partial', 'Partial Backup'),
        ('scheduled', 'Scheduled Backup'),
    ], default='full')
    
    backup_format = models.CharField(max_length=10, choices=[
        ('sql', 'SQL Dump'),
        ('json', 'JSON Export'),
        ('excel', 'Excel Export'),
        ('csv', 'CSV Export'),
    ], default='sql')
    
    # File information
    file_name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    file_size = models.BigIntegerField(default=0, help_text="File size in bytes")
    
    # Backup content
    included_tables = models.JSONField(default=list, help_text="List of tables included in backup")
    record_counts = models.JSONField(default=dict, help_text="Number of records per table")
    
    # Status
    status = models.CharField(max_length=20, choices=[
        ('creating', 'Creating'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('expired', 'Expired'),
    ], default='creating')
    
    error_message = models.TextField(blank=True)
    
    # Sharing options
    emailed_to = models.EmailField(blank=True, help_text="Email address backup was sent to")
    cloud_storage_url = models.URLField(blank=True, help_text="Cloud storage download URL")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # User who created the backup
    created_by_user_id = models.IntegerField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Tenant Backup"
        verbose_name_plural = "Tenant Backups"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Backup {self.backup_id} for tenant {self.tenant_id}"
    
    @property
    def file_size_formatted(self):
        """Return formatted file size"""
        if self.file_size == 0:
            return "0 B"
        
        size = float(self.file_size)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def is_expired(self):
        """Check if backup has expired"""
        if not self.expires_at:
            return False
        from django.utils import timezone
        return timezone.now() > self.expires_at
    
    def get_download_url(self):
        """Get the download URL for this backup"""
        return f"/api/backups/{self.backup_id}/download/"


# Base models for tenant databases
class TenantTimeStampedModel(models.Model):
    """
    TimeStamped model for tenant databases
    Uses integer fields to store user IDs instead of foreign keys
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Store user IDs instead of FK relationships to avoid cross-database constraints
    created_by_user_id = models.IntegerField(null=True, blank=True)
    updated_by_user_id = models.IntegerField(null=True, blank=True)

    class Meta:
        abstract = True

    def set_created_by(self, user):
        """Set the created_by user ID"""
        if user and user.id:
            self.created_by_user_id = user.id

    def set_updated_by(self, user):
        """Set the updated_by user ID"""
        if user and user.id:
            self.updated_by_user_id = user.id


class TenantSoftDeleteManager(models.Manager):
    """Manager that excludes soft-deleted objects by default"""
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class TenantSoftDeleteModel(TenantTimeStampedModel):
    """Soft delete model for tenant databases"""
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by_user_id = models.IntegerField(null=True, blank=True)

    objects = TenantSoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False, user=None):
        """Soft delete the object"""
        from django.utils import timezone
        self.is_deleted = True
        self.deleted_at = timezone.now()
        if user and user.id:
            self.deleted_by_user_id = user.id
        self.save(using=using)

    def hard_delete(self, using=None, keep_parents=False):
        """Permanently delete the object"""
        super().delete(using=using, keep_parents=keep_parents)

    def restore(self, user=None):
        """Restore a soft-deleted object"""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by_user_id = None
        if user and user.id:
            self.updated_by_user_id = user.id
        self.save()

    def set_deleted_by(self, user):
        """Set the deleted_by user ID"""
        if user and user.id:
            self.deleted_by_user_id = user.id