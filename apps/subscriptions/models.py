from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import TimeStampedModel  # Changed to use global models for system-wide subscriptions
from decimal import Decimal
import uuid

class SubscriptionPlan(TimeStampedModel):
    """Global subscription plans available for all businesses"""
    
    PLAN_TYPES = [
        ('monthly', 'Monthly Plan'),
        ('quarterly', 'Quarterly Plan'),
        ('semi_annual', 'Semi-Annual Plan'),
        ('annual', 'Annual Plan'),
        ('one_time', 'One Off Plan'),
    ]
    
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPES)
    description = models.TextField()
    
    # Pricing - KES amounts from your specification
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    duration_months = models.IntegerField(help_text="Duration in months")
    
    # Features included
    features = models.JSONField(default=list, help_text="List of features included")
    
    # Limits
    max_employees = models.IntegerField(default=5, help_text="Use -1 for unlimited")
    max_customers = models.IntegerField(default=100, help_text="Use -1 for unlimited")
    max_locations = models.IntegerField(default=1, help_text="Use -1 for unlimited")
    max_services = models.IntegerField(default=10, help_text="Use -1 for unlimited")
    
    # Storage limits (in MB)
    storage_limit = models.IntegerField(default=1000, help_text="Storage limit in MB, -1 for unlimited")
    
    # Status
    is_active = models.BooleanField(default=True)
    is_popular = models.BooleanField(default=False)
    
    # Support levels
    support_level = models.CharField(max_length=50, default='Basic')
    network_monitoring = models.BooleanField(default=True)
    helpdesk_support = models.CharField(max_length=100, default='Limited Hours')
    cybersecurity_level = models.CharField(max_length=50, default='Basic')
    backup_recovery = models.BooleanField(default=False)
    onsite_support = models.BooleanField(default=False)
    
    # Trial
    trial_days = models.IntegerField(default=7)
    
    # Display order
    sort_order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['duration_months', 'price']
        verbose_name = "Subscription Plan"
        verbose_name_plural = "Subscription Plans"
    
    def __str__(self):
        return f"{self.name} - KES {self.price}"
    
    def get_price_for_cycle(self, billing_cycle):
        """Get price for specific billing cycle"""
        # Since we have different plans for different durations,
        # this method returns the plan's base price
        return self.price
    
    def get_discount_percentage(self, billing_cycle):
        """Calculate discount percentage for longer billing cycles"""
        # Since we have separate plans for different durations,
        # discount calculation should be handled at the plan level
        return 0
        actual_price = self.get_price_for_cycle(billing_cycle)
        
        if monthly_total > actual_price:
            return round(((monthly_total - actual_price) / monthly_total) * 100, 1)
        return 0

class Subscription(TimeStampedModel):
    """Active subscriptions for businesses"""
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('trial', 'Trial'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
        ('suspended', 'Suspended'),
        ('pending', 'Pending Payment'),
    ]
    
    # Subscription details
    subscription_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    business = models.ForeignKey('core.Tenant', on_delete=models.CASCADE, related_name='subscriptions')  # Link to business
    
    # Dates
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    trial_end_date = models.DateTimeField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='trial')
    is_auto_renew = models.BooleanField(default=True)
    
    # Pricing (stored for historical purposes)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='KES')
    
    # Cancellation
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    
    # Grace period for expired subscriptions
    grace_period_end = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subscriptions_created'  # Changed from 'payment_created'
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subscriptions_updated'  # Changed from 'payment_updated'
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Subscription"
        verbose_name_plural = "Subscriptions"
    
    def __str__(self):
        try:
            # Avoid cross-database queries by using plan_id instead of plan.name
            return f"Subscription {self.subscription_id} - {self.get_status_display()}"
        except:
            return f"Subscription {self.subscription_id}"
    
    @property
    def is_active(self):
        """Check if subscription is currently active"""
        now = timezone.now()
        
        if self.status == 'active':
            # For active subscriptions, only check end_date
            return self.end_date > now
        elif self.status == 'trial':
            # For trial subscriptions, check both end_date and trial_end_date
            return (
                self.end_date > now and 
                (not self.trial_end_date or self.trial_end_date > now)
            )
        else:
            # For other statuses (expired, cancelled, etc.), not active
            return False
    
    @property
    def is_trial(self):
        """Check if subscription is in trial period"""
        if not self.trial_end_date:
            return False
        return timezone.now() < self.trial_end_date and self.status == 'trial'
    
    @property
    def days_remaining(self):
        """Get days remaining in subscription"""
        if not self.is_active:
            return 0
        return (self.end_date - timezone.now()).days
    
    @property
    def trial_days_remaining(self):
        """Get trial days remaining"""
        if not self.trial_end_date or not self.is_trial:
            return 0
        return max(0, (self.trial_end_date - timezone.now()).days)
    
    def extend_subscription(self, days):
        """Extend subscription by specified days"""
        from datetime import timedelta
        self.end_date += timedelta(days=days)
        self.save()
    
    def cancel_subscription(self, reason=""):
        """Cancel subscription"""
        self.status = 'cancelled'
        self.cancelled_at = timezone.now()
        self.cancellation_reason = reason
        self.is_auto_renew = False
        self.save()
    
    def reactivate_subscription(self):
        """Reactivate cancelled subscription if within grace period"""
        if self.status == 'cancelled' and timezone.now() < self.end_date:
            self.status = 'active'
            self.cancelled_at = None
            self.cancellation_reason = ""
            self.is_auto_renew = True
            self.save()
            return True
        return False

class Payment(TimeStampedModel):
    """Payment records for subscriptions"""
    
    PAYMENT_METHODS = [
        ('mpesa', 'M-Pesa'),
        ('card', 'Credit/Debit Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('cash', 'Cash'),
        ('free', 'Free/Promotional'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]
    
    # Payment details
    payment_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='payments')
    
    # Amount
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='KES')
    
    # Payment method
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # External references
    transaction_id = models.CharField(max_length=100, blank=True, help_text="External payment gateway transaction ID")
    reference_number = models.CharField(max_length=100, blank=True)
    
    # Payment gateway response
    gateway_response = models.JSONField(default=dict, blank=True)
    
    # Dates
    paid_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    failure_reason = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
    
    def __str__(self):
        return f"Payment {self.payment_id} - KES {self.amount}"
    
    def mark_as_completed(self, transaction_id="", notes=""):
        """Mark payment as completed"""
        self.status = 'completed'
        self.paid_at = timezone.now()
        self.transaction_id = transaction_id
        if notes:
            self.notes = notes
        self.save()
        
        # Update subscription status if it was pending
        if self.subscription.status == 'pending':
            self.subscription.status = 'active'
            self.subscription.save()
    
    def mark_as_failed(self, reason=""):
        """Mark payment as failed"""
        self.status = 'failed'
        self.failed_at = timezone.now()
        self.failure_reason = reason
        self.save()

class SubscriptionUsage(TimeStampedModel):
    """Track subscription usage and limits"""
    
    subscription = models.OneToOneField(Subscription, on_delete=models.CASCADE, related_name='usage')
    
    # Current usage
    employees_count = models.IntegerField(default=0)
    customers_count = models.IntegerField(default=0)
    locations_count = models.IntegerField(default=1)
    services_count = models.IntegerField(default=0)
    
    # Storage usage (in MB)
    storage_used = models.IntegerField(default=0)
    
    # API usage (for enterprise plans)
    api_calls_this_month = models.IntegerField(default=0)
    
    # Last updated
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Subscription Usage"
        verbose_name_plural = "Subscription Usage"
    
    def __str__(self):
        return f"{self.subscription} - Usage"
    
    def update_usage(self):
        """Update usage statistics"""
        # This would be called periodically to update usage stats
        # Implementation depends on your business models
        pass
    
    def is_over_limit(self, resource_type):
        """Check if usage is over limit for specific resource"""
        plan = self.subscription.plan
        
        limits = {
            'employees': (self.employees_count, plan.max_employees),
            'customers': (self.customers_count, plan.max_customers),
            'locations': (self.locations_count, plan.max_locations),
            'services': (self.services_count, plan.max_services),
            'storage': (self.storage_used, plan.storage_limit),
        }
        
        if resource_type not in limits:
            return False
        
        current, limit = limits[resource_type]
        return limit != -1 and current >= limit

class SubscriptionDiscount(TimeStampedModel):
    """Discount codes for subscriptions"""
    
    DISCOUNT_TYPES = [
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
        ('free_trial', 'Free Trial Extension'),
    ]
    
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Discount details
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPES)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Applicable plans
    applicable_plans = models.ManyToManyField(SubscriptionPlan, blank=True)
    
    # Usage limits
    max_uses = models.IntegerField(null=True, blank=True, help_text="Leave blank for unlimited")
    current_uses = models.IntegerField(default=0)
    
    # Validity
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField()
    
    # Restrictions
    minimum_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    first_time_users_only = models.BooleanField(default=False)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Subscription Discount"
        verbose_name_plural = "Subscription Discounts"
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    @property
    def is_valid(self):
        """Check if discount is currently valid"""
        now = timezone.now()
        return (
            self.is_active and 
            self.valid_from <= now <= self.valid_until and
            (not self.max_uses or self.current_uses < self.max_uses)
        )
    
    def calculate_discount(self, amount):
        """Calculate discount amount"""
        if not self.is_valid or amount < self.minimum_amount:
            return Decimal('0.00')
        
        if self.discount_type == 'percentage':
            return (amount * self.discount_value / 100).quantize(Decimal('0.01'))
        elif self.discount_type == 'fixed':
            return min(self.discount_value, amount)
        
        return Decimal('0.00')
    
    def use_discount(self):
        """Mark discount as used"""
        self.current_uses += 1
        self.save()

class SubscriptionInvoice(TimeStampedModel):
    """Invoices for subscription payments"""
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Invoice details
    invoice_number = models.CharField(max_length=50, unique=True)
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='invoices')
    payment = models.OneToOneField(Payment, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Amounts
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Dates
    issue_date = models.DateField(default=timezone.now)
    due_date = models.DateField()
    paid_date = models.DateField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Applied discount
    discount_code = models.ForeignKey(SubscriptionDiscount, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Subscription Invoice"
        verbose_name_plural = "Subscription Invoices"
    
    def __str__(self):
        return f"Invoice {self.invoice_number}"
    
    def save(self, *args, **kwargs):
        if not self.invoice_number:
            # Generate invoice number
            import datetime
            today = datetime.date.today()
            prefix = f"INV-{today.strftime('%Y%m')}"
            last_invoice = SubscriptionInvoice.objects.filter(
                invoice_number__startswith=prefix
            ).order_by('-invoice_number').first()
            
            if last_invoice:
                last_num = int(last_invoice.invoice_number.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.invoice_number = f"{prefix}-{new_num:04d}"
        
        super().save(*args, **kwargs)
