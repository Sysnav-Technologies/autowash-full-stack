from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.tenant_models import TenantTimeStampedModel, TenantSoftDeleteModel
from apps.core.utils import generate_unique_code
from decimal import Decimal
import uuid

class PaymentMethod(TenantTimeStampedModel):
    """Payment methods configuration"""
    
    METHOD_TYPES = [
        ('cash', 'Cash'),
        ('card', 'Credit/Debit Card'),
        ('mpesa', 'M-Pesa'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('mobile_money', 'Mobile Money'),
        ('crypto', 'Cryptocurrency'),
    ]
    
    name = models.CharField(max_length=100)
    method_type = models.CharField(max_length=20, choices=METHOD_TYPES)
    description = models.TextField(blank=True)
    
    # Configuration
    is_active = models.BooleanField(default=True)
    is_online = models.BooleanField(default=False, help_text="Requires online processing")
    requires_verification = models.BooleanField(default=False)
    processing_fee_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    fixed_processing_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    # Limits
    minimum_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    maximum_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    daily_limit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Integration settings
    api_endpoint = models.URLField(blank=True)
    api_key = models.CharField(max_length=255, blank=True)
    merchant_id = models.CharField(max_length=100, blank=True)
    
    # Display
    icon = models.CharField(max_length=50, default='fas fa-credit-card')
    color = models.CharField(max_length=7, default='#007bff')
    display_order = models.IntegerField(default=0)
    
    def __str__(self):
        return self.name
    
    @property
    def total_transactions_today(self):
        """Get total transactions for today"""
        from django.utils import timezone
        today = timezone.now().date()
        return self.payments.filter(
            created_at__date=today,
            status__in=['completed', 'verified']
        ).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0')
    
    def calculate_processing_fee(self, amount):
        """FIXED: Calculate processing fee for given amount"""
        # Ensure amount is a Decimal
        if isinstance(amount, str):
            try:
                amount = Decimal(amount)
            except (TypeError, ValueError):
                amount = Decimal('0')
        elif not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        
        # Ensure fee percentages are Decimals
        fee_percentage = Decimal(str(self.processing_fee_percentage))
        fixed_fee = Decimal(str(self.fixed_processing_fee))
        
        # Calculate percentage fee
        percentage_fee = amount * (fee_percentage / Decimal('100'))
        
        # Return total fee
        return percentage_fee + fixed_fee
    
    def is_amount_valid(self, amount):
        """Check if amount is within limits"""
        # Ensure amount is a Decimal
        if isinstance(amount, str):
            try:
                amount = Decimal(amount)
            except (TypeError, ValueError):
                return False, "Invalid amount format"
        elif not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        
        if amount < self.minimum_amount:
            return False, f"Minimum amount is {self.minimum_amount}"
        
        if self.maximum_amount and amount > self.maximum_amount:
            return False, f"Maximum amount is {self.maximum_amount}"
        
        if self.daily_limit:
            today_total = self.total_transactions_today
            if today_total + amount > self.daily_limit:
                remaining = self.daily_limit - today_total
                return False, f"Daily limit exceeded. Remaining: {remaining}"
        
        return True, "Valid amount"
    
    class Meta:
        verbose_name = "Payment Method"
        verbose_name_plural = "Payment Methods"
        ordering = ['display_order', 'name']

class Payment(TenantTimeStampedModel):
    """Payment transactions - UPDATED with metadata field"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
        ('verified', 'Verified'),
    ]
    
    PAYMENT_TYPES = [
        ('service_payment', 'Service Payment'),
        ('deposit', 'Deposit'),
        ('refund', 'Refund'),
        ('adjustment', 'Adjustment'),
        ('loyalty_redemption', 'Loyalty Redemption'),
    ]
    
    # Payment identification
    payment_id = models.CharField(max_length=50, unique=True)
    reference_number = models.CharField(max_length=100, blank=True)
    
    # Related records
    service_order = models.ForeignKey(
        'services.ServiceOrder',
        on_delete=models.CASCADE,
        related_name='payments',
        null=True,
        blank=True
    )
    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.CASCADE,
        related_name='payments',
        null=True,
        blank=True
    )
    
    # Payment details
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.CASCADE, related_name='payments')
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES, default='service_payment')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    processing_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Status and timing
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    initiated_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Staff handling
    processed_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_payments'
    )
    verified_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_payments'
    )
    
    # Transaction details
    transaction_id = models.CharField(max_length=255, blank=True)
    external_reference = models.CharField(max_length=255, blank=True)
    gateway_response = models.JSONField(default=dict, blank=True)
    
    # Customer information
    customer_phone = models.CharField(max_length=20, blank=True)
    customer_email = models.EmailField(blank=True)
    
    # Notes and description
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    failure_reason = models.TextField(blank=True)

    # FIXED: Store user IDs instead of ForeignKeys to avoid cross-schema constraints
    created_by_user_id = models.IntegerField(null=True, blank=True, help_text="User ID from public schema")
    updated_by_user_id = models.IntegerField(null=True, blank=True, help_text="User ID from public schema")
    
    # ADDED: Metadata field for storing additional payment information
    metadata = models.JSONField(
        default=dict, 
        blank=True, 
        help_text="Additional payment metadata (partial payments, custom data, etc.)"
    )
    
    # ADDED: Partial payment support fields
    is_partial_payment = models.BooleanField(
        default=False, 
        help_text="Indicates if this is a partial payment"
    )
    parent_payment = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='child_payments',
        help_text="Reference to original payment if this is a follow-up partial payment"
    )
    
    def __str__(self):
        customer_name = self.customer.display_name if self.customer else "No Customer"
        partial_indicator = " (Partial)" if self.is_partial_payment else ""
        return f"Payment {self.payment_id} - {customer_name} - KES {self.amount}{partial_indicator}"
    
    def save(self, *args, **kwargs):
        # Generate payment ID if not set
        if not self.payment_id:
            self.payment_id = generate_unique_code('PAY', 10)
        
        # FIXED: Ensure amount is Decimal and calculate fees properly
        if isinstance(self.amount, str):
            self.amount = Decimal(self.amount)
        elif not isinstance(self.amount, Decimal):
            self.amount = Decimal(str(self.amount))
        
        # Calculate processing fee
        self.processing_fee = self.payment_method.calculate_processing_fee(self.amount)
        
        # Calculate net amount
        self.net_amount = self.amount - self.processing_fee
        
        super().save(*args, **kwargs)
    
    @property
    def created_by_user(self):
        """Get the user who created this payment from public schema"""
        if not self.created_by_user_id:
            return None
        try:
            return User.objects.using('default').get(id=self.created_by_user_id)
        except User.DoesNotExist:
            return None
    
    @property
    def updated_by_user(self):
        """Get the user who last updated this payment from public schema"""
        if not self.updated_by_user_id:
            return None
        try:
            return User.objects.using('default').get(id=self.updated_by_user_id)
        except User.DoesNotExist:
            return None
    
    @property
    def is_expired(self):
        """Check if payment has expired"""
        if self.expires_at:
            from django.utils import timezone
            return timezone.now() > self.expires_at
        return False
    
    @property
    def can_be_refunded(self):
        """Check if payment can be refunded"""
        if self.status not in ['completed', 'verified']:
            return False
        
        # Can be refunded if there's still refundable amount
        return self.refundable_amount > 0
    
    @property
    def total_refunded(self):
        """Get total refunded amount"""
        return self.refunds.aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0')
    
    @property
    def refundable_amount(self):
        """Get amount available for refund"""
        return self.amount - self.total_refunded
    
    @property
    def payment_type_display(self):
        """Get display name for payment type including partial payment info"""
        if self.is_partial_payment:
            if self.metadata and self.metadata.get('payment_sequence'):
                sequence = self.metadata.get('payment_sequence')
                return f"Partial Payment #{sequence}"
            return "Partial Payment"
        return self.get_payment_type_display()
    
    def get_all_related_payments(self):
        """Get all payments related to the same service order"""
        if not self.service_order:
            return Payment.objects.filter(id=self.id)
        
        return Payment.objects.filter(
            service_order=self.service_order
        ).order_by('created_at')
    
    def get_remaining_balance(self):
        """Get remaining balance for the service order"""
        if not self.service_order:
            return Decimal('0')
        
        total_paid = self.get_all_related_payments().filter(
            status__in=['completed', 'verified']
        ).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0')
        
        return self.service_order.total_amount - total_paid
    
    def complete_payment(self, transaction_id=None, user=None):
        """Mark payment as completed"""
        from django.utils import timezone
        
        self.status = 'completed'
        self.completed_at = timezone.now()
        if transaction_id:
            self.transaction_id = transaction_id
        if user:
            # Store user ID instead of user object
            self.updated_by_user_id = user.id
        self.save()
        
        # Update service order payment status
        if self.service_order:
            try:
                self.service_order.update_payment_status()
            except AttributeError:
                # Method doesn't exist, skip
                pass
        
        # Send confirmation notifications
        self.send_payment_confirmation()
    
    def fail_payment(self, reason=None):
        """Mark payment as failed"""
        self.status = 'failed'
        if reason:
            self.failure_reason = reason
        self.save()
    
    def send_payment_confirmation(self):
        """Send payment confirmation to customer with modern email template"""
        if not self.customer:
            return
            
        from apps.core.utils import send_sms_notification, send_email_notification
        from django.template.loader import render_to_string
        from apps.core.database_router import get_current_tenant
        
        try:
            # Get current tenant information
            tenant = get_current_tenant()
            tenant_info = None
            if tenant:
                tenant_info = {
                    'name': tenant.name,
                    'phone': getattr(tenant, 'phone', ''),
                    'email': getattr(tenant, 'email', ''),
                    'address': getattr(tenant, 'address', ''),
                    'website': getattr(tenant, 'website', None),
                    'logo': getattr(tenant, 'logo', None),
                }
            
            # Send SMS notification
            if self.customer.phone and getattr(self.customer, 'receive_service_reminders', True):
                payment_type = "Partial payment" if self.is_partial_payment else "Payment"
                remaining = self.get_remaining_balance()
                balance_msg = f" Balance due: KES {remaining}" if remaining > 0 else ""
                
                business_name = tenant_info['name'] if tenant_info else "Autowash"
                message = f"{payment_type} confirmed! KES {self.amount} received for order {self.service_order.order_number if self.service_order else 'N/A'}.{balance_msg} Thank you! - {business_name}"
                send_sms_notification(str(self.customer.phone), message)
        except Exception:
            pass  # Don't break if SMS fails
        
        try:
            # Send HTML email notification
            if self.customer.email and getattr(self.customer, 'receive_marketing_email', True):
                context = {
                    'payment': self,
                    'customer': self.customer,
                    'customer_name': self.customer.display_name,
                    'tenant': tenant,
                    'business_name': tenant.name if tenant else 'Autowash App',
                    'business_phone': getattr(tenant, 'phone', '') if tenant else '',
                    'business_email': getattr(tenant, 'email', '') if tenant else '',
                    'business_address': getattr(tenant, 'address', '') if tenant else '',
                    'receipt_url': None,  # Can be added if receipt generation is implemented
                }
                
                # Render HTML email
                html_message = render_to_string('emails/payment_confirmation.html', context)
                
                # Subject
                business_name = tenant.name if tenant else "Autowash App"
                subject = f"Payment Confirmation - {business_name}"
                
                # Plain text fallback
                plain_message = f"Your payment of KES {self.amount} has been confirmed for order {self.service_order.order_number if self.service_order else 'N/A'}. Thank you for choosing {business_name}!"
                
                send_email_notification(subject, plain_message, [self.customer.email], html_message=html_message)
        except Exception as e:
            print(f"Failed to send payment confirmation email: {e}")
            pass  # Don't break if email fails
    
    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        ordering = ['-created_at']

class PaymentRefund(TenantTimeStampedModel):
    """Payment refunds"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    original_payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='refunds')
    refund_id = models.CharField(max_length=50, unique=True)
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Processing details
    processed_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_refunds'
    )
    approved_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_refunds'
    )
    
    processed_at = models.DateTimeField(null=True, blank=True)
    external_refund_id = models.CharField(max_length=255, blank=True)
    gateway_response = models.JSONField(default=dict, blank=True)
    
    def __str__(self):
        return f"Refund {self.refund_id} - KES {self.amount}"
    
    def save(self, *args, **kwargs):
        if not self.refund_id:
            self.refund_id = generate_unique_code('REF', 10)
        super().save(*args, **kwargs)
    
    def process_refund(self, user=None):
        """Process the refund"""
        from django.utils import timezone
        
        self.status = 'completed'
        self.processed_at = timezone.now()
        self.save()
        
        # Send refund confirmation
        self.send_refund_confirmation()
    
    def send_refund_confirmation(self):
        """Send refund confirmation to customer"""
        try:
            from apps.core.utils import send_sms_notification
            
            customer = self.original_payment.customer
            if customer and customer.phone and getattr(customer, 'receive_service_reminders', True):
                message = f"Refund processed! KES {self.amount} will be credited back to your account. Ref: {self.refund_id}"
                send_sms_notification(str(customer.phone), message)
        except Exception:
            pass  # Don't break if SMS fails
    
    class Meta:
        verbose_name = "Payment Refund"
        verbose_name_plural = "Payment Refunds"
        ordering = ['-created_at']

class MPesaTransaction(TenantTimeStampedModel):
    """M-Pesa specific transaction details"""
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, related_name='mpesa_details')
    
    # M-Pesa fields
    phone_number = models.CharField(max_length=15)
    mpesa_receipt_number = models.CharField(max_length=50, blank=True)
    transaction_date = models.DateTimeField(null=True, blank=True)
    
    # STK Push details
    merchant_request_id = models.CharField(max_length=100, blank=True)
    checkout_request_id = models.CharField(max_length=100, blank=True)
    result_code = models.CharField(max_length=10, blank=True)
    result_desc = models.TextField(blank=True)
    
    # Callback data
    callback_data = models.JSONField(default=dict, blank=True)
    
    def __str__(self):
        return f"M-Pesa {self.mpesa_receipt_number} - {self.phone_number}"
    
    class Meta:
        verbose_name = "M-Pesa Transaction"
        verbose_name_plural = "M-Pesa Transactions"

class CardTransaction(TenantTimeStampedModel):
    """Card payment transaction details"""
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, related_name='card_details')
    
    # Card details (masked)
    card_type = models.CharField(max_length=20, blank=True)
    masked_pan = models.CharField(max_length=20, blank=True)
    card_holder_name = models.CharField(max_length=100, blank=True)
    
    # Transaction details
    authorization_code = models.CharField(max_length=50, blank=True)
    processor_response = models.CharField(max_length=100, blank=True)
    gateway_transaction_id = models.CharField(max_length=100, blank=True)
    
    # Security
    cvv_response = models.CharField(max_length=10, blank=True)
    avs_response = models.CharField(max_length=10, blank=True)
    
    def __str__(self):
        return f"Card {self.masked_pan} - {self.card_type}"
    
    class Meta:
        verbose_name = "Card Transaction"
        verbose_name_plural = "Card Transactions"

class CashTransaction(TenantTimeStampedModel):
    """Cash payment transaction details"""
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, related_name='cash_details')
    
    # Cash handling details
    amount_tendered = models.DecimalField(max_digits=10, decimal_places=2)
    change_given = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Denominations breakdown
    notes_1000 = models.IntegerField(default=0)
    notes_500 = models.IntegerField(default=0)
    notes_200 = models.IntegerField(default=0)
    notes_100 = models.IntegerField(default=0)
    notes_50 = models.IntegerField(default=0)
    coins_40 = models.IntegerField(default=0)
    coins_20 = models.IntegerField(default=0)
    coins_10 = models.IntegerField(default=0)
    coins_5 = models.IntegerField(default=0)
    coins_1 = models.IntegerField(default=0)
    
    # Till information
    till_number = models.CharField(max_length=20, blank=True)
    cashier = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cash_transactions'
    )
    
    def __str__(self):
        return f"Cash KES {self.payment.amount} - Change: {self.change_given}"
    
    @property
    def total_notes_coins(self):
        """Calculate total from denomination breakdown"""
        total = (
            self.notes_1000 * 1000 +
            self.notes_500 * 500 +
            self.notes_200 * 200 +
            self.notes_100 * 100 +
            self.notes_50 * 50 +
            self.coins_40 * 40 +
            self.coins_20 * 20 +
            self.coins_10 * 10 +
            self.coins_5 * 5 +
            self.coins_1 * 1
        )
        return Decimal(str(total))
    
    class Meta:
        verbose_name = "Cash Transaction"
        verbose_name_plural = "Cash Transactions"

class PaymentGateway(TenantTimeStampedModel):
    """Payment gateway configurations"""
    
    GATEWAY_TYPES = [
        ('mpesa', 'M-Pesa Daraja'),
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal'),
        ('flutterwave', 'Flutterwave'),
        ('pesapal', 'PesaPal'),
        ('ipay', 'iPay'),
    ]
    
    name = models.CharField(max_length=100)
    gateway_type = models.CharField(max_length=20, choices=GATEWAY_TYPES)
    
    # Configuration
    is_active = models.BooleanField(default=True)
    is_live = models.BooleanField(default=False, help_text="Live mode vs Test mode")
    
    # API Configuration
    api_url = models.URLField()
    api_key = models.CharField(max_length=255)
    api_secret = models.CharField(max_length=255)
    merchant_id = models.CharField(max_length=100, blank=True)
    
    # M-Pesa specific
    consumer_key = models.CharField(max_length=255, blank=True)
    consumer_secret = models.CharField(max_length=255, blank=True)
    passkey = models.CharField(max_length=255, blank=True)
    shortcode = models.CharField(max_length=20, blank=True)
    
    # Webhook configuration
    webhook_url = models.URLField(blank=True)
    webhook_secret = models.CharField(max_length=255, blank=True)
    
    # Supported payment methods
    supported_methods = models.ManyToManyField(PaymentMethod, blank=True)
    
    def __str__(self):
        return f"{self.name} ({'Live' if self.is_live else 'Test'})"
    
    class Meta:
        verbose_name = "Payment Gateway"
        verbose_name_plural = "Payment Gateways"

class PaymentSplit(TenantTimeStampedModel):
    """Payment splitting for commission/revenue sharing"""
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='splits')
    
    # Split details
    recipient_type = models.CharField(
        max_length=20,
        choices=[
            ('employee', 'Employee Commission'),
            ('business', 'Business Revenue'),
            ('platform', 'Platform Fee'),
            ('tax', 'Tax'),
            ('other', 'Other'),
        ]
    )
    recipient_id = models.CharField(max_length=50, blank=True)
    percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    description = models.CharField(max_length=200, blank=True)
    
    def __str__(self):
        return f"{self.get_recipient_type_display()} - {self.percentage}% (KES {self.amount})"
    
    class Meta:
        verbose_name = "Payment Split"
        verbose_name_plural = "Payment Splits"

class RecurringPayment(TenantTimeStampedModel):
    """Recurring payment subscriptions"""
    
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ]
    
    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.CASCADE,
        related_name='recurring_payments'
    )
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.CASCADE)
    
    # Subscription details
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    
    # Schedule
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    next_payment_date = models.DateField()
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    total_payments_made = models.IntegerField(default=0)
    total_amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Retry configuration
    max_retry_attempts = models.IntegerField(default=3)
    current_retry_count = models.IntegerField(default=0)
    
    def __str__(self):
        return f"{self.customer.display_name} - {self.name} ({self.frequency})"
    
    def calculate_next_payment_date(self):
        """Calculate the next payment date based on frequency"""
        from datetime import timedelta
        from dateutil.relativedelta import relativedelta
        
        if self.frequency == 'daily':
            return self.next_payment_date + timedelta(days=1)
        elif self.frequency == 'weekly':
            return self.next_payment_date + timedelta(weeks=1)
        elif self.frequency == 'monthly':
            return self.next_payment_date + relativedelta(months=1)
        elif self.frequency == 'quarterly':
            return self.next_payment_date + relativedelta(months=3)
        elif self.frequency == 'yearly':
            return self.next_payment_date + relativedelta(years=1)
        
        return self.next_payment_date
    
    def process_payment(self):
        """Process the recurring payment"""
        if self.status != 'active':
            return False, "Subscription is not active"
        
        try:
            # Create payment record
            payment = Payment.objects.create(
                customer=self.customer,
                payment_method=self.payment_method,
                payment_type='service_payment',  # Changed from 'subscription'
                amount=self.amount,
                description=f"Recurring payment - {self.name}"
            )
            
            # Process payment through gateway
            # This would integrate with actual payment processors
            
            # Update recurring payment
            self.total_payments_made += 1
            self.total_amount_paid += self.amount
            self.next_payment_date = self.calculate_next_payment_date()
            self.current_retry_count = 0
            self.save()
            
            return True, payment
            
        except Exception as e:
            self.current_retry_count += 1
            if self.current_retry_count >= self.max_retry_attempts:
                self.status = 'paused'
            self.save()
            
            return False, str(e)
    
    class Meta:
        verbose_name = "Recurring Payment"
        verbose_name_plural = "Recurring Payments"
