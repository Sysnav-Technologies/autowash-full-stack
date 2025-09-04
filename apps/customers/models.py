from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from phonenumber_field.modelfields import PhoneNumberField
from apps.core.tenant_models import TenantTimeStampedModel, TenantSoftDeleteModel
from apps.core.models import Address, ContactInfo
from apps.core.utils import upload_to_path
from decimal import Decimal
import uuid

class Customer(TenantSoftDeleteModel, Address, ContactInfo):
    """Customer model with comprehensive information - FIXED for cross-schema compatibility"""
    
    CUSTOMER_TYPE_CHOICES = [
        ('individual', 'Individual'),
        ('corporate', 'Corporate'),
        ('government', 'Government'),
    ]
    
    # Basic Information
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    company_name = models.CharField(max_length=200, blank=True)
    customer_type = models.CharField(max_length=20, choices=CUSTOMER_TYPE_CHOICES, default='individual')
    customer_id = models.CharField(max_length=20, unique=True)
    
    # Contact Information (inherited from ContactInfo)
    # Additional phone numbers
    phone_secondary = PhoneNumberField(blank=True, null=True)
    
    # Personal Information
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=10,
        choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')],
        blank=True
    )
    national_id = models.CharField(max_length=20, blank=True)
    
    # Business Information (for corporate customers)
    business_registration_number = models.CharField(max_length=100, blank=True)
    tax_number = models.CharField(max_length=100, blank=True)
    
    # Preferences
    preferred_contact_method = models.CharField(
        max_length=20,
        choices=[
            ('phone', 'Phone'),
            ('sms', 'SMS'),
            ('email', 'Email'),
            ('whatsapp', 'WhatsApp'),
        ],
        default='phone'
    )
    
    # Marketing preferences
    receive_marketing_sms = models.BooleanField(default=True)
    receive_marketing_email = models.BooleanField(default=True)
    receive_service_reminders = models.BooleanField(default=True)
    
    # Customer status
    is_active = models.BooleanField(default=True)
    is_vip = models.BooleanField(default=False)
    is_walk_in = models.BooleanField(default=False, help_text="Walk-in customer without full registration")
    credit_limit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    current_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Loyalty program
    loyalty_points = models.IntegerField(default=0)
    total_spent = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Notes
    notes = models.TextField(blank=True, help_text="Internal notes about the customer")
    
    def __str__(self):
        if self.customer_type == 'corporate' and self.company_name:
            return f"{self.company_name} ({self.customer_id})"
        return f"{self.full_name} ({self.customer_id})"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
    
    @property
    def display_name(self):
        """Display name for customer (company name for corporate, full name for individual)"""
        if self.customer_type == 'corporate' and self.company_name:
            return self.company_name
        return self.full_name
    
    @property
    def total_orders(self):
        """Get total number of orders"""
        try:
            from apps.services.models import ServiceOrder
            return ServiceOrder.objects.filter(customer=self).count()
        except ImportError:
            return 0
    
    @property
    def last_service_date(self):
        """Get last service date"""
        try:
            from apps.services.models import ServiceOrder
            last_order = ServiceOrder.objects.filter(customer=self).order_by('-created_at').first()
            return last_order.created_at.date() if last_order else None
        except ImportError:
            return None
    
    @property
    def average_order_value(self):
        """Calculate average order value"""
        try:
            from apps.services.models import ServiceOrder
            from django.db.models import Avg
            avg = ServiceOrder.objects.filter(customer=self, status='completed').aggregate(
                avg=Avg('total_amount')
            )['avg']
            return avg or Decimal('0.00')
        except ImportError:
            return Decimal('0.00')
    
    @property
    def can_place_order(self):
        """Check if customer can place new order based on credit limit"""
        if self.credit_limit <= 0:
            return True  # No credit limit
        return self.current_balance <= self.credit_limit
    
    def add_loyalty_points(self, points):
        """Add loyalty points to customer"""
        self.loyalty_points += points
        self.save(update_fields=['loyalty_points'])
    
    def redeem_loyalty_points(self, points):
        """Redeem loyalty points"""
        if self.loyalty_points >= points:
            self.loyalty_points -= points
            self.save(update_fields=['loyalty_points'])
            return True
        return False
    
    class Meta:
        verbose_name = "Customer"
        verbose_name_plural = "Customers"
        ordering = ['first_name', 'last_name']


class Vehicle(TenantTimeStampedModel):
    """Customer vehicle information - FIXED for cross-schema compatibility"""
    
    VEHICLE_TYPE_CHOICES = [
        ('sedan', 'Sedan'),
        ('suv', 'SUV'),
        ('hatchback', 'Hatchback'),
        ('pickup', 'Pickup Truck'),
        ('van', 'Van'),
        ('bus', 'Bus'),
        ('truck', 'Truck'),
        ('motorcycle', 'Motorcycle'),
        ('other', 'Other'),
    ]
    
    FUEL_TYPE_CHOICES = [
        ('petrol', 'Petrol'),
        ('diesel', 'Diesel'),
        ('hybrid', 'Hybrid'),
        ('electric', 'Electric'),
        ('other', 'Other'),
    ]
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='vehicles')
    
    # Vehicle details
    registration_number = models.CharField(max_length=20, unique=True)
    make = models.CharField(max_length=50)
    model = models.CharField(max_length=50)
    year = models.IntegerField()
    color = models.CharField(max_length=30)
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_TYPE_CHOICES)
    fuel_type = models.CharField(max_length=20, choices=FUEL_TYPE_CHOICES)
    
    # Technical details
    engine_size = models.CharField(max_length=20, blank=True)
    transmission = models.CharField(
        max_length=20,
        choices=[('manual', 'Manual'), ('automatic', 'Automatic')],
        blank=True
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Service history
    last_service_date = models.DateField(null=True, blank=True)
    last_service_mileage = models.IntegerField(null=True, blank=True)
    
    # Notes
    notes = models.TextField(blank=True, help_text="Special notes about the vehicle")
    
    def __str__(self):
        return f"{self.registration_number} - {self.make} {self.model} ({self.customer.display_name})"
    
    @property
    def license_plate(self):
        """Backward compatibility property for templates"""
        return self.registration_number
    
    @property
    def full_name(self):
        return f"{self.make} {self.model} {self.year}"
    
    @property
    def display_name(self):
        """Get a human-friendly display name for the vehicle"""
        if self.make or self.model:
            parts = []
            if self.make:
                parts.append(self.make)
            if self.model:
                parts.append(self.model)
            return " ".join(parts)
        elif self.registration_number:
            return self.registration_number
        else:
            return "Unknown Vehicle"
    
    @property
    def service_count(self):
        """Get total number of services for this vehicle"""
        try:
            from apps.services.models import ServiceOrder
            return ServiceOrder.objects.filter(vehicle=self).count()
        except ImportError:
            return 0
    
    @property
    def days_since_last_service(self):
        """Calculate days since last service"""
        if self.last_service_date:
            from datetime import date
            return (date.today() - self.last_service_date).days
        return None
    
    class Meta:
        verbose_name = "Vehicle"
        verbose_name_plural = "Vehicles"
        ordering = ['registration_number']


class CustomerNote(TenantTimeStampedModel):
    """Customer notes and interactions - FIXED for cross-schema compatibility"""
    
    NOTE_TYPES = [
        ('general', 'General Note'),
        ('complaint', 'Complaint'),
        ('compliment', 'Compliment'),
        ('follow_up', 'Follow Up'),
        ('reminder', 'Reminder'),
        ('payment', 'Payment Issue'),
        ('service', 'Service Note'),
    ]
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='customer_notes')
    note_type = models.CharField(max_length=20, choices=NOTE_TYPES, default='general')
    title = models.CharField(max_length=200)
    content = models.TextField()
    is_private = models.BooleanField(default=False, help_text="Only visible to staff")
    is_important = models.BooleanField(default=False)
    
    # Follow-up
    requires_follow_up = models.BooleanField(default=False)
    follow_up_date = models.DateField(null=True, blank=True)
    follow_up_completed = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.customer.display_name} - {self.title}"
    
    class Meta:
        verbose_name = "Customer Note"
        verbose_name_plural = "Customer Notes"
        ordering = ['-created_at']


class CustomerDocument(TenantTimeStampedModel):
    """Customer document storage - FIXED for cross-schema compatibility"""
    
    DOCUMENT_TYPES = [
        ('id_copy', 'ID Copy'),
        ('driving_license', 'Driving License'),
        ('insurance', 'Insurance Documents'),
        ('registration', 'Vehicle Registration'),
        ('contract', 'Service Contract'),
        ('invoice', 'Invoice'),
        ('receipt', 'Receipt'),
        ('other', 'Other'),
    ]
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to=upload_to_path)
    description = models.TextField(blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.customer.display_name} - {self.title}"
    
    @property
    def is_expired(self):
        if self.expiry_date:
            from datetime import date
            return date.today() > self.expiry_date
        return False
    
    class Meta:
        verbose_name = "Customer Document"
        verbose_name_plural = "Customer Documents"
        ordering = ['-created_at']


class CustomerFeedback(TenantTimeStampedModel):
    """Customer feedback and ratings - FIXED for cross-schema compatibility"""
    
    RATING_CHOICES = [
        (1, '1 - Very Poor'),
        (2, '2 - Poor'),
        (3, '3 - Average'),
        (4, '4 - Good'),
        (5, '5 - Excellent'),
    ]
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='feedback')
    service_order = models.ForeignKey(
        'services.ServiceOrder', 
        on_delete=models.CASCADE, 
        related_name='feedback',
        null=True,
        blank=True
    )
    
    # Ratings
    overall_rating = models.IntegerField(choices=RATING_CHOICES)
    service_quality = models.IntegerField(choices=RATING_CHOICES, null=True, blank=True)
    staff_friendliness = models.IntegerField(choices=RATING_CHOICES, null=True, blank=True)
    cleanliness = models.IntegerField(choices=RATING_CHOICES, null=True, blank=True)
    value_for_money = models.IntegerField(choices=RATING_CHOICES, null=True, blank=True)
    
    # Comments
    comments = models.TextField(blank=True)
    suggestions = models.TextField(blank=True)
    
    # Status
    is_published = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    
    # Response - FIXED: Use integer ID for cross-schema compatibility
    response = models.TextField(blank=True, help_text="Management response to feedback")
    responded_at = models.DateTimeField(null=True, blank=True)
    responded_by_id = models.IntegerField(null=True, blank=True, help_text="Employee ID who responded")
    
    def __str__(self):
        return f"{self.customer.display_name} - {self.overall_rating}/5 stars"
    
    @property
    def responded_by(self):
        """Get the employee who responded from employees app"""
        if not self.responded_by_id:
            return None
        try:
            from apps.employees.models import Employee
            return Employee.objects.get(id=self.responded_by_id)
        except (ImportError, Employee.DoesNotExist):
            return None
    
    @responded_by.setter
    def responded_by(self, employee):
        """Set the employee who responded"""
        if employee:
            self.responded_by_id = employee.id
        else:
            self.responded_by_id = None
    
    @property
    def average_rating(self):
        """Calculate average rating across all categories"""
        ratings = [
            self.overall_rating,
            self.service_quality or 0,
            self.staff_friendliness or 0,
            self.cleanliness or 0,
            self.value_for_money or 0
        ]
        valid_ratings = [r for r in ratings if r > 0]
        return sum(valid_ratings) / len(valid_ratings) if valid_ratings else 0
    
    class Meta:
        verbose_name = "Customer Feedback"
        verbose_name_plural = "Customer Feedback"
        ordering = ['-created_at']


class LoyaltyProgram(TenantTimeStampedModel):
    """Loyalty program configuration - FIXED for cross-schema compatibility"""
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    is_active = models.BooleanField(default=True)
    
    # Points configuration
    points_per_currency_unit = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=1,
        help_text="Points earned per currency unit spent"
    )
    minimum_order_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text="Minimum order amount to earn points"
    )
    
    # Redemption
    points_to_currency_ratio = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0.01,
        help_text="Currency value per loyalty point"
    )
    minimum_redemption_points = models.IntegerField(
        default=100,
        help_text="Minimum points required for redemption"
    )
    
    # Tiers
    bronze_threshold = models.IntegerField(default=0)
    silver_threshold = models.IntegerField(default=1000)
    gold_threshold = models.IntegerField(default=5000)
    platinum_threshold = models.IntegerField(default=10000)
    
    # Multipliers
    silver_multiplier = models.DecimalField(max_digits=3, decimal_places=2, default=1.2)
    gold_multiplier = models.DecimalField(max_digits=3, decimal_places=2, default=1.5)
    platinum_multiplier = models.DecimalField(max_digits=3, decimal_places=2, default=2.0)
    
    def __str__(self):
        return self.name
    
    def get_customer_tier(self, customer):
        """Get customer's loyalty tier"""
        points = customer.loyalty_points
        if points >= self.platinum_threshold:
            return 'platinum'
        elif points >= self.gold_threshold:
            return 'gold'
        elif points >= self.silver_threshold:
            return 'silver'
        else:
            return 'bronze'
    
    def get_points_multiplier(self, customer):
        """Get points multiplier for customer's tier"""
        tier = self.get_customer_tier(customer)
        multipliers = {
            'bronze': 1.0,
            'silver': float(self.silver_multiplier),
            'gold': float(self.gold_multiplier),
            'platinum': float(self.platinum_multiplier),
        }
        return multipliers.get(tier, 1.0)
    
    def calculate_points(self, amount, customer):
        """Calculate points for an order amount"""
        if amount < self.minimum_order_amount:
            return 0
        
        base_points = float(amount) * float(self.points_per_currency_unit)
        multiplier = self.get_points_multiplier(customer)
        return int(base_points * multiplier)
    
    class Meta:
        verbose_name = "Loyalty Program"
        verbose_name_plural = "Loyalty Programs"
