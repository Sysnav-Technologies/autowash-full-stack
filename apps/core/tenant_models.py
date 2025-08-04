"""
MySQL-based Multi-Tenant Models
Database-per-tenant approach for MySQL compatibility
"""
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.utils.text import slugify
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
    
    # Notification settings
    sms_notifications = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=True)
    
    # Feature flags
    enable_loyalty_program = models.BooleanField(default=False)
    enable_online_booking = models.BooleanField(default=True)
    enable_mobile_app = models.BooleanField(default=False)
    
    # Branding
    primary_color = models.CharField(max_length=7, default='#007bff')
    secondary_color = models.CharField(max_length=7, default='#6c757d')
    
    class Meta:
        verbose_name = "Tenant Settings"
        verbose_name_plural = "Tenant Settings"
    
    def __str__(self):
        return f"Settings for tenant {self.tenant_id}"


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