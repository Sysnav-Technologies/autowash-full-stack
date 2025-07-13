from django.conf import settings
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django_tenants.models import TenantMixin, DomainMixin
from phonenumber_field.modelfields import PhoneNumberField
from apps.core.models import TimeStampedModel, Address, ContactInfo
from apps.core.utils import upload_to_path
import uuid
import os

class UserProfile(TimeStampedModel):
    """Extended user profile"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = PhoneNumberField(blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(
        max_length=10,
        choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')],
        blank=True
    )
    bio = models.TextField(blank=True)
    is_verified = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=100, blank=True)
    
    # Preferences
    language = models.CharField(max_length=10, default='en')
    timezone = models.CharField(max_length=50, default='Africa/Nairobi')
    receive_sms = models.BooleanField(default=True)
    receive_email = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} Profile"
    
    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"


def business_logo_upload(instance, filename):
    """Simple upload function for business logos"""
    import os
    from django.utils.text import slugify
    
    # Get file extension
    name, ext = os.path.splitext(filename)
    ext = ext.lower()
    
    # Create safe filename
    safe_name = slugify(instance.name) if instance.name else 'business'
    new_filename = f"{safe_name}_logo{ext}"
    
    # Return path
    return f"business_logos/{new_filename}"

class Business(TenantMixin, TimeStampedModel, Address, ContactInfo):
    """Business model with multi-tenancy support"""
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to=business_logo_upload, blank=True, null=True)
    
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
    
    # Contact information (inherited from ContactInfo)
    website = models.URLField(blank=True)
    
    # Business hours
    opening_time = models.TimeField(default='08:00')
    closing_time = models.TimeField(default='18:00')
    
    # Settings
    timezone = models.CharField(max_length=50, default='Africa/Nairobi')
    currency = models.CharField(max_length=3, default='KES')
    language = models.CharField(max_length=10, default='en')
    
    # Status
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    
    # Subscription
    subscription = models.ForeignKey(
        'subscriptions.Subscription', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    
    # Owner
    owner = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='owned_businesses'
    )
    
    # Limits based on subscription
    max_employees = models.IntegerField(default=5)
    max_customers = models.IntegerField(default=100)
    
    # Auto-generated fields for tenancy
    auto_create_schema = True
    auto_drop_schema = True
    
    def __str__(self):
        return self.name
    
    @property
    def domain_url(self):
        """Get the primary domain URL"""
        domain = self.domains.filter(is_primary=True).first()
        return domain.domain if domain else None
    
    @domain_url.setter
    def domain_url(self, value):
        """Set the primary domain URL"""
        domain, created = self.domains.get_or_create(
            is_primary=True,
            defaults={'domain': value}
        )
        if not created and domain.domain != value:
            domain.domain = value
            domain.save()
    
    @property
    def employee_count(self):
        """Get current employee count"""
        from apps.employees.models import Employee
        return Employee.objects.filter(is_active=True).count()
    
    @property
    def customer_count(self):
        """Get current customer count"""
        from apps.customers.models import Customer
        return Customer.objects.count()
    
    def can_add_employee(self):
        """Check if business can add more employees"""
        if self.max_employees == -1:  # Unlimited
            return True
        return self.employee_count < self.max_employees
    
    def can_add_customer(self):
        """Check if business can add more customers"""
        if self.max_customers == -1:  # Unlimited
            return True
        return self.customer_count < self.max_customers
    
    # Update your Business model save method in apps/accounts/models.py

    def save(self, *args, **kwargs):
        """Override save to handle logo and ensure slug"""
        # Generate slug if not present
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
            
            # Ensure unique slug
            original_slug = self.slug
            counter = 1
            while Business.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        
        # Handle logo file if it exists
        if self.logo:
            # Ensure the upload directory exists
            import os
            upload_dir = os.path.join(settings.MEDIA_ROOT, 'business_logos', self.slug)
            os.makedirs(upload_dir, exist_ok=True)
        
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = "Business"
        verbose_name_plural = "Businesses"

class Domain(DomainMixin):
    """Domain model for multi-tenancy"""
    pass

class BusinessSettings(TimeStampedModel):
    """Business-specific settings"""
    business = models.OneToOneField(Business, on_delete=models.CASCADE, related_name='settings')
    
    # Notification settings
    sms_notifications = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=True)
    customer_sms_notifications = models.BooleanField(default=True)
    
    # Service settings
    auto_assign_attendants = models.BooleanField(default=False)
    require_customer_approval = models.BooleanField(default=True)
    send_service_reminders = models.BooleanField(default=True)
    
    # Payment settings
    accept_cash = models.BooleanField(default=True)
    accept_card = models.BooleanField(default=True)
    accept_mpesa = models.BooleanField(default=True)
    require_payment_confirmation = models.BooleanField(default=True)
    
    # Inventory settings
    track_inventory = models.BooleanField(default=True)
    auto_reorder = models.BooleanField(default=False)
    low_stock_threshold = models.IntegerField(default=10)
    
    # Report settings
    daily_reports = models.BooleanField(default=True)
    weekly_reports = models.BooleanField(default=True)
    monthly_reports = models.BooleanField(default=True)
    
    # Customer settings
    loyalty_program = models.BooleanField(default=False)
    customer_rating = models.BooleanField(default=True)
    customer_feedback = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.business.name} Settings"
    
    class Meta:
        verbose_name = "Business Settings"
        verbose_name_plural = "Business Settings"

class BusinessVerification(TimeStampedModel):
    """Business verification records"""
    business = models.OneToOneField(Business, on_delete=models.CASCADE, related_name='verification')
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_review', 'In Review'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    submitted_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='verified_businesses'
    )
    
    # Documents
    business_license = models.FileField(upload_to='verification/licenses/', blank=True)
    tax_certificate = models.FileField(upload_to='verification/tax/', blank=True)
    id_document = models.FileField(upload_to='verification/ids/', blank=True)
    
    notes = models.TextField(blank=True, help_text="Verification notes")
    rejection_reason = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.business.name} - {self.get_status_display()}"
    
    class Meta:
        verbose_name = "Business Verification"
        verbose_name_plural = "Business Verifications"