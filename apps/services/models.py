# COMPLETE FIX: Update your Service and ServiceCategory models
# apps/services/models.py

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import TimeStampedModel, SoftDeleteModel
from apps.core.utils import generate_unique_code, upload_to_path
from django_tenants.utils import schema_context, get_public_schema_name
from decimal import Decimal
import uuid

class ServiceCategory(TimeStampedModel):
    """Service categories for organizing services"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default='fas fa-car-wash')
    color = models.CharField(max_length=7, default='#3b82f6', help_text="Hex color code")
    is_active = models.BooleanField(default=True)
    display_order = models.IntegerField(default=0)
    
    # ADDED: Cross-schema user tracking
    created_by_id = models.IntegerField(null=True, blank=True, help_text="User ID from public schema")
    
    def __str__(self):
        return self.name
    
    @property
    def service_count(self):
        return self.services.filter(is_active=True).count()
    
    @property
    def created_by(self):
        """Get the user who created this category from public schema"""
        if not self.created_by_id:
            return None
        try:
            with schema_context(get_public_schema_name()):
                return User.objects.get(id=self.created_by_id)
        except User.DoesNotExist:
            return None
    
    @created_by.setter
    def created_by(self, user):
        """Set the user who created this category"""
        if user:
            self.created_by_id = user.id
        else:
            self.created_by_id = None
    
    class Meta:
        verbose_name = "Service Category"
        verbose_name_plural = "Service Categories"
        ordering = ['display_order', 'name']

class Service(SoftDeleteModel):
    """Individual services offered"""
    name = models.CharField(max_length=100)
    description = models.TextField()
    category = models.ForeignKey(ServiceCategory, on_delete=models.CASCADE, related_name='services')
    
    # Pricing
    base_price = models.DecimalField(max_digits=8, decimal_places=2)
    min_price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    max_price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    
    # Time estimates
    estimated_duration = models.IntegerField(help_text="Estimated duration in minutes")
    min_duration = models.IntegerField(null=True, blank=True, help_text="Minimum duration in minutes")
    max_duration = models.IntegerField(null=True, blank=True, help_text="Maximum duration in minutes")
    
    # Service details
    requires_booking = models.BooleanField(default=False)
    is_popular = models.BooleanField(default=False)
    is_premium = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    # Requirements
    required_skill_level = models.CharField(
        max_length=20,
        choices=[
            ('basic', 'Basic'),
            ('intermediate', 'Intermediate'),
            ('advanced', 'Advanced'),
            ('expert', 'Expert'),
        ],
        default='basic'
    )
    
    # Vehicle compatibility
    compatible_vehicle_types = models.CharField(
        max_length=200,
        default='sedan,suv,hatchback,pickup,van',
        help_text="Comma-separated list of compatible vehicle types"
    )
    
    # Display
    image = models.ImageField(upload_to='service_images/', blank=True, null=True)
    display_order = models.IntegerField(default=0)
    
    # ADDED: Cross-schema user tracking
    created_by_id = models.IntegerField(null=True, blank=True, help_text="User ID from public schema")
    
    def __str__(self):
        return f"{self.name} - KES {self.base_price}"
    
    @property
    def created_by(self):
        """Get the user who created this service from public schema"""
        if not self.created_by_id:
            return None
        try:
            with schema_context(get_public_schema_name()):
                return User.objects.get(id=self.created_by_id)
        except User.DoesNotExist:
            return None
    
    @created_by.setter
    def created_by(self, user):
        """Set the user who created this service"""
        if user:
            self.created_by_id = user.id
        else:
            self.created_by_id = None
    
    @property
    def average_rating(self):
        """Calculate average rating from completed orders"""
        ratings = self.order_items.filter(
            order__status='completed'
        ).exclude(rating__isnull=True).values_list('rating', flat=True)
        return sum(ratings) / len(ratings) if ratings else 0
    
    @property
    def total_orders(self):
        """Get total number of times this service was ordered"""
        return self.order_items.filter(order__status='completed').count()
    
    def is_compatible_with_vehicle(self, vehicle):
        """Check if service is compatible with vehicle type"""
        compatible_types = [t.strip() for t in self.compatible_vehicle_types.split(',')]
        return vehicle.vehicle_type in compatible_types
    
    class Meta:
        verbose_name = "Service"
        verbose_name_plural = "Services"
        ordering = ['category', 'display_order', 'name']

# Keep all your other models unchanged (ServicePackage, ServiceOrder, etc.)
# They remain exactly as they are in your current file...

class ServicePackage(SoftDeleteModel):
    """Service packages (bundles of services)"""
    name = models.CharField(max_length=100)
    description = models.TextField()
    services = models.ManyToManyField(Service, through='PackageService')
    
    # Pricing
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Package details
    estimated_duration = models.IntegerField(help_text="Total estimated duration in minutes")
    is_popular = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    # Validity
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    
    # Display
    image = models.ImageField(upload_to='package_images/', blank=True, null=True)
    
    def __str__(self):
        return f"{self.name} - KES {self.total_price}"
    
    @property
    def original_price(self):
        """Calculate original price without discount"""
        if self.discount_percentage > 0:
            return self.total_price / (1 - self.discount_percentage / 100)
        return self.total_price
    
    @property
    def savings_amount(self):
        """Calculate savings amount"""
        return self.original_price - self.total_price
    
    @property
    def service_count(self):
        """Get number of services in package"""
        return self.services.count()
    
    class Meta:
        verbose_name = "Service Package"
        verbose_name_plural = "Service Packages"
        ordering = ['name']

class PackageService(models.Model):
    """Through model for service packages"""
    package = models.ForeignKey(ServicePackage, on_delete=models.CASCADE)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    custom_price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    is_optional = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['package', 'service']

class ServiceOrder(TimeStampedModel):
    """Service orders/bookings"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    # Order identification
    order_number = models.CharField(max_length=20, unique=True)
    
    # Customer and vehicle
    customer = models.ForeignKey('customers.Customer', on_delete=models.CASCADE, related_name='service_orders')
    vehicle = models.ForeignKey('customers.Vehicle', on_delete=models.CASCADE, related_name='service_orders')
    
    # Service details
    services = models.ManyToManyField(Service, through='ServiceOrderItem')
    package = models.ForeignKey(ServicePackage, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Staff assignment
    assigned_attendant = models.ForeignKey(
        'employees.Employee', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='assigned_orders'
    )
    
    # Scheduling
    scheduled_date = models.DateField(null=True, blank=True)
    scheduled_time = models.TimeField(null=True, blank=True)
    actual_start_time = models.DateTimeField(null=True, blank=True)
    actual_end_time = models.DateTimeField(null=True, blank=True)
    
    # Status and priority
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')
    
    # Pricing
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Payment
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('partial', 'Partially Paid'),
            ('paid', 'Paid'),
            ('refunded', 'Refunded'),
        ],
        default='pending'
    )
    payment_method = models.CharField(
        max_length=20,
        choices=[
            ('cash', 'Cash'),
            ('card', 'Credit/Debit Card'),
            ('mpesa', 'M-Pesa'),
            ('bank_transfer', 'Bank Transfer'),
        ],
        blank=True
    )
    
    # Additional information
    special_instructions = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    
    # Customer feedback
    customer_rating = models.IntegerField(
        null=True, 
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    customer_feedback = models.TextField(blank=True)
    
    # ADDED: Cross-schema user tracking for order creation
    created_by_id = models.IntegerField(null=True, blank=True, help_text="User ID from public schema")
    
    def __str__(self):
        return f"Order {self.order_number} - {self.customer.display_name}"
    
    @property
    def created_by(self):
        """Get the user who created this order from public schema"""
        if not self.created_by_id:
            return None
        try:
            with schema_context(get_public_schema_name()):
                return User.objects.get(id=self.created_by_id)
        except User.DoesNotExist:
            return None
    
    @created_by.setter
    def created_by(self, user):
        """Set the user who created this order"""
        if user:
            self.created_by_id = user.id
        else:
            self.created_by_id = None
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = generate_unique_code('ORD', 8)
        super().save(*args, **kwargs)
    
    @property
    def duration_minutes(self):
        """Calculate actual service duration"""
        if self.actual_start_time and self.actual_end_time:
            duration = self.actual_end_time - self.actual_start_time
            return int(duration.total_seconds() / 60)
        return 0
    
    @property
    def estimated_duration(self):
        """Calculate estimated duration from services"""
        if self.package:
            return self.package.estimated_duration
        
        total_duration = 0
        for item in self.order_items.all():
            total_duration += item.service.estimated_duration * item.quantity
        return total_duration
    
    @property
    def is_overdue(self):
        """Check if order is overdue based on estimated completion time"""
        if self.actual_start_time and not self.actual_end_time:
            from django.utils import timezone
            estimated_end = self.actual_start_time + timezone.timedelta(minutes=self.estimated_duration)
            return timezone.now() > estimated_end
        return False
    
    @property
    def can_be_cancelled(self):
        """Check if order can be cancelled"""
        return self.status in ['pending', 'confirmed']
    
    def calculate_totals(self):
        """Calculate order totals"""
        if self.package:
            self.subtotal = self.package.total_price
        else:
            items_total = sum(
                item.quantity * item.unit_price 
                for item in self.order_items.all()
            )
            self.subtotal = items_total
        
        # Apply discount
        discounted_amount = self.subtotal - self.discount_amount
        
        # Calculate tax (assuming 16% VAT for Kenya)
        self.tax_amount = discounted_amount * Decimal('0.16')
        
        # Calculate total
        self.total_amount = discounted_amount + self.tax_amount
    
    class Meta:
        verbose_name = "Service Order"
        verbose_name_plural = "Service Orders"
        ordering = ['-created_at']

class ServiceOrderItem(models.Model):
    """Individual items in a service order"""
    order = models.ForeignKey(ServiceOrder, on_delete=models.CASCADE, related_name='order_items')
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='order_items')
    
    quantity = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)
    total_price = models.DecimalField(max_digits=8, decimal_places=2)
    
    # Service execution
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    assigned_to = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='service_items'
    )
    
    # Quality control
    quality_checked = models.BooleanField(default=False)
    quality_rating = models.IntegerField(
        null=True, 
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    quality_notes = models.TextField(blank=True)
    
    # Customer rating for this specific service
    rating = models.IntegerField(
        null=True, 
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comments = models.TextField(blank=True)
    
    def save(self, *args, **kwargs):
        if not self.unit_price:
            self.unit_price = self.service.base_price
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)
    
    @property
    def duration_minutes(self):
        """Calculate actual duration for this service item"""
        if self.started_at and self.completed_at:
            duration = self.completed_at - self.started_at
            return int(duration.total_seconds() / 60)
        return 0
    
    @property
    def is_completed(self):
        """Check if service item is completed"""
        return self.completed_at is not None
    
    def __str__(self):
        return f"{self.service.name} x{self.quantity} - {self.order.order_number}"
    
    class Meta:
        unique_together = ['order', 'service']

class ServiceQueue(TimeStampedModel):
    """Service queue management"""
    
    QUEUE_STATUS_CHOICES = [
        ('waiting', 'Waiting'),
        ('in_service', 'In Service'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    order = models.OneToOneField(ServiceOrder, on_delete=models.CASCADE, related_name='queue_entry')
    queue_number = models.IntegerField()
    estimated_start_time = models.DateTimeField()
    estimated_end_time = models.DateTimeField()
    actual_start_time = models.DateTimeField(null=True, blank=True)
    actual_end_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=QUEUE_STATUS_CHOICES, default='waiting')
    
    # Service bay assignment
    service_bay = models.ForeignKey(
        'ServiceBay',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='queue_entries'
    )
    
    def __str__(self):
        return f"Queue #{self.queue_number} - {self.order.order_number}"
    
    @property
    def wait_time_minutes(self):
        """Calculate waiting time"""
        if self.actual_start_time:
            wait_time = self.actual_start_time - self.created_at
            return int(wait_time.total_seconds() / 60)
        return 0
    
    @property
    def estimated_wait_time(self):
        """Calculate estimated wait time from current time"""
        from django.utils import timezone
        if self.status == 'waiting':
            wait_time = self.estimated_start_time - timezone.now()
            return max(0, int(wait_time.total_seconds() / 60))
        return 0
    
    class Meta:
        verbose_name = "Service Queue Entry"
        verbose_name_plural = "Service Queue Entries"
        ordering = ['queue_number']

class ServiceBay(TimeStampedModel):
    """Service bays/stations for car washing"""
    name = models.CharField(max_length=50)
    bay_number = models.IntegerField(unique=True)
    description = models.TextField(blank=True)
    
    # Capacity and features
    max_vehicle_size = models.CharField(
        max_length=20,
        choices=[
            ('small', 'Small (Sedan, Hatchback)'),
            ('medium', 'Medium (SUV, Pickup)'),
            ('large', 'Large (Van, Truck)'),
            ('any', 'Any Size'),
        ],
        default='any'
    )
    
    # Equipment and features
    has_pressure_washer = models.BooleanField(default=True)
    has_vacuum = models.BooleanField(default=True)
    has_lift = models.BooleanField(default=False)
    has_drainage = models.BooleanField(default=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_occupied = models.BooleanField(default=False)
    
    # Current service
    current_order = models.ForeignKey(
        ServiceOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='current_bay'
    )
    
    def __str__(self):
        return f"Bay {self.bay_number} - {self.name}"
    
    @property
    def is_available(self):
        """Check if bay is available for service"""
        return self.is_active and not self.is_occupied
    
    def assign_order(self, order):
        """Assign an order to this bay"""
        self.current_order = order
        self.is_occupied = True
        self.save()
    
    def complete_service(self):
        """Mark service as completed and free the bay"""
        self.current_order = None
        self.is_occupied = False
        self.save()
    
    class Meta:
        verbose_name = "Service Bay"
        verbose_name_plural = "Service Bays"
        ordering = ['bay_number']