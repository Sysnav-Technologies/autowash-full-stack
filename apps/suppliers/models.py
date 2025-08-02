from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from phonenumber_field.modelfields import PhoneNumberField
from apps.core.tenant_models import TenantTimeStampedModel, TenantSoftDeleteModel
from apps.core.models import Address, ContactInfo
from apps.core.utils import upload_to_path
from decimal import Decimal
import uuid

class SupplierCategory(TenantTimeStampedModel):
    """Categories for organizing suppliers"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name
    
    @property
    def supplier_count(self):
        """Get count of suppliers in this category"""
        return self.suppliers.filter(is_active=True).count()
    
    class Meta:
        verbose_name = "Supplier Category"
        verbose_name_plural = "Supplier Categories"
        ordering = ['name']

class Supplier(TenantSoftDeleteModel, Address, ContactInfo):
    """Supplier/Vendor management"""
    
    SUPPLIER_TYPES = [
        ('manufacturer', 'Manufacturer'),
        ('wholesaler', 'Wholesaler'),
        ('distributor', 'Distributor'),
        ('retailer', 'Retailer'),
        ('service_provider', 'Service Provider'),
        ('contractor', 'Contractor'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('pending', 'Pending Approval'),
        ('suspended', 'Suspended'),
        ('blacklisted', 'Blacklisted'),
    ]
    
    PAYMENT_TERMS = [
        ('cod', 'Cash on Delivery'),
        ('net_15', 'Net 15 Days'),
        ('net_30', 'Net 30 Days'),
        ('net_45', 'Net 45 Days'),
        ('net_60', 'Net 60 Days'),
        ('advance', 'Advance Payment'),
        ('custom', 'Custom Terms'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=200)
    supplier_code = models.CharField(max_length=50, unique=True, help_text="Unique supplier identifier")
    category = models.ForeignKey(
        SupplierCategory, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='suppliers'
    )
    supplier_type = models.CharField(max_length=20, choices=SUPPLIER_TYPES, default='wholesaler')
    
    # Business Information
    business_name = models.CharField(max_length=200, blank=True)
    registration_number = models.CharField(max_length=100, blank=True)
    tax_number = models.CharField(max_length=100, blank=True)
    vat_number = models.CharField(max_length=100, blank=True)
    
    # Additional contact fields
    primary_contact_name = models.CharField(max_length=100, blank=True)
    primary_contact_title = models.CharField(max_length=100, blank=True)
    secondary_contact_name = models.CharField(max_length=100, blank=True)
    secondary_contact_phone = PhoneNumberField(blank=True, null=True)
    secondary_contact_email = models.EmailField(blank=True)
    
    # Financial Information
    payment_terms = models.CharField(max_length=20, choices=PAYMENT_TERMS, default='net_30')
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    current_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='KES')
    
    # Banking Information
    bank_name = models.CharField(max_length=100, blank=True)
    bank_branch = models.CharField(max_length=100, blank=True)
    account_number = models.CharField(max_length=50, blank=True)
    account_name = models.CharField(max_length=100, blank=True)
    swift_code = models.CharField(max_length=20, blank=True)
    
    # Performance Metrics
    rating = models.DecimalField(
        max_digits=3, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    total_orders = models.IntegerField(default=0)
    total_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Delivery Information
    lead_time_days = models.IntegerField(default=7, help_text="Standard delivery lead time in days")
    minimum_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_terms = models.CharField(max_length=100, blank=True, help_text="e.g., FOB, CIF, etc.")
    
    # Status and Flags
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    is_preferred = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    
    # Quality and Compliance
    quality_rating = models.DecimalField(
        max_digits=3, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    delivery_rating = models.DecimalField(
        max_digits=3, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    service_rating = models.DecimalField(
        max_digits=3, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    
    # Certifications and Documents
    certifications = models.TextField(blank=True, help_text="List of certifications")
    
    # Internal Notes
    notes = models.TextField(blank=True)
    terms_and_conditions = models.TextField(blank=True)
    
    # Dates
    first_order_date = models.DateField(null=True, blank=True)
    last_order_date = models.DateField(null=True, blank=True)
    contract_start_date = models.DateField(null=True, blank=True)
    contract_end_date = models.DateField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.name} ({self.supplier_code})"
    
    @property
    def full_name(self):
        """Get full supplier name including business name"""
        if self.business_name and self.business_name != self.name:
            return f"{self.name} ({self.business_name})"
        return self.name
    
    @property
    def outstanding_balance(self):
        """Calculate outstanding balance"""
        return abs(self.current_balance) if self.current_balance < 0 else 0
    
    @property
    def credit_available(self):
        """Calculate available credit"""
        return max(0, self.credit_limit - self.outstanding_balance)
    
    @property
    def average_rating(self):
        """Calculate average rating from all rating components"""
        ratings = [self.quality_rating, self.delivery_rating, self.service_rating]
        valid_ratings = [r for r in ratings if r > 0]
        return sum(valid_ratings) / len(valid_ratings) if valid_ratings else 0
    
    @property
    def performance_score(self):
        """Calculate overall performance score"""
        # Weighted average: Quality (40%), Delivery (30%), Service (30%)
        return (
            self.quality_rating * 0.4 + 
            self.delivery_rating * 0.3 + 
            self.service_rating * 0.3
        )
    
    @property
    def items_supplied_count(self):
        """Get count of items supplied by this supplier"""
        try:
            from apps.inventory.models import InventoryItem
            return InventoryItem.objects.filter(primary_supplier=self, is_active=True).count()
        except ImportError:
            return 0
    
    def update_performance_metrics(self):
        """Update performance metrics from purchase orders"""
        orders = self.purchase_orders.filter(status='completed')
        
        if orders.exists():
            self.total_orders = orders.count()
            self.total_value = orders.aggregate(
                total=models.Sum('total_amount')
            )['total'] or 0
            
            # Update dates
            first_order = orders.order_by('created_at').first()
            last_order = orders.order_by('-created_at').first()
            self.first_order_date = first_order.created_at.date()
            self.last_order_date = last_order.created_at.date()
            
            self.save()
    
    class Meta:
        verbose_name = "Supplier"
        verbose_name_plural = "Suppliers"
        ordering = ['name']

class SupplierContact(TenantTimeStampedModel):
    """Additional contacts for suppliers"""
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='contacts')
    
    name = models.CharField(max_length=100)
    title = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=100, blank=True)
    
    phone = PhoneNumberField(blank=True, null=True)
    email = models.EmailField(blank=True)
    mobile = PhoneNumberField(blank=True, null=True)
    
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.name} - {self.supplier.name}"
    
    class Meta:
        verbose_name = "Supplier Contact"
        verbose_name_plural = "Supplier Contacts"
        ordering = ['-is_primary', 'name']

class PurchaseOrder(TenantTimeStampedModel):
    """Purchase orders to suppliers"""
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('sent', 'Sent to Supplier'),
        ('acknowledged', 'Acknowledged by Supplier'),
        ('partially_received', 'Partially Received'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('on_hold', 'On Hold'),
    ]
    
    PRIORITY_LEVELS = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    # Identification
    po_number = models.CharField(max_length=50, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='purchase_orders')
    
    # Status and Priority
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='normal')
    
    # Dates
    order_date = models.DateField(default=timezone.now)
    expected_delivery_date = models.DateField()
    delivery_date = models.DateField(null=True, blank=True)
    
    # Financial Information
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Terms and Conditions
    payment_terms = models.CharField(max_length=20, choices=Supplier.PAYMENT_TERMS, blank=True)
    delivery_terms = models.CharField(max_length=100, blank=True)
    special_instructions = models.TextField(blank=True)
    terms_and_conditions = models.TextField(blank=True)
    
    # Delivery Information
    delivery_address = models.TextField(blank=True)
    contact_person = models.CharField(max_length=100, blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    
    # Staff Information
    requested_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requested_purchase_orders'
    )
    approved_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_purchase_orders'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Tracking
    supplier_reference = models.CharField(max_length=100, blank=True, help_text="Supplier's order reference")
    tracking_number = models.CharField(max_length=100, blank=True)
    
    # Internal Notes
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"PO-{self.po_number} - {self.supplier.name}"
    
    @property
    def is_overdue(self):
        """Check if delivery is overdue"""
        if self.status in ['completed', 'cancelled']:
            return False
        return timezone.now().date() > self.expected_delivery_date
    
    @property
    def days_overdue(self):
        """Calculate days overdue"""
        if not self.is_overdue:
            return 0
        return (timezone.now().date() - self.expected_delivery_date).days
    
    @property
    def completion_percentage(self):
        """Calculate completion percentage based on received items"""
        total_ordered = self.items.aggregate(
            total=models.Sum('quantity')
        )['total'] or 0
        
        total_received = self.items.aggregate(
            total=models.Sum('received_quantity')
        )['total'] or 0
        
        if total_ordered > 0:
            return (total_received / total_ordered) * 100
        return 0
    
    @property
    def is_fully_received(self):
        """Check if all items are fully received"""
        return self.completion_percentage >= 100
    
    def calculate_totals(self):
        """Calculate and update order totals"""
        items = self.items.all()
        
        self.subtotal = sum(item.total_amount for item in items)
        self.total_amount = self.subtotal + self.tax_amount + self.shipping_cost - self.discount_amount
        
        self.save(update_fields=['subtotal', 'total_amount'])
    
    def approve(self, user):
        """Approve the purchase order"""
        self.status = 'approved'
        if hasattr(user, 'employee_profile'):
            self.approved_by = user.employee_profile
        self.approved_at = timezone.now()
        self.save()
    
    def send_to_supplier(self):
        """Mark order as sent to supplier"""
        self.status = 'sent'
        self.save()
    
    def acknowledge_receipt(self):
        """Mark as acknowledged by supplier"""
        self.status = 'acknowledged'
        self.save()
    
    def complete_order(self):
        """Mark order as completed"""
        self.status = 'completed'
        self.delivery_date = timezone.now().date()
        self.save()
        
        # Update supplier metrics
        self.supplier.update_performance_metrics()
    
    class Meta:
        verbose_name = "Purchase Order"
        verbose_name_plural = "Purchase Orders"
        ordering = ['-created_at']

class PurchaseOrderItem(TenantTimeStampedModel):
    """Items in a purchase order"""
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey('inventory.InventoryItem', on_delete=models.CASCADE, related_name='purchase_order_items')
    
    # Quantities
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    received_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Pricing
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Item details at time of order
    item_description = models.TextField(blank=True)
    item_sku = models.CharField(max_length=50, blank=True)
    
    # Delivery
    expected_date = models.DateField(null=True, blank=True)
    received_date = models.DateField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.item.name} - {self.quantity} @ {self.unit_price}"
    
    @property
    def pending_quantity(self):
        """Calculate pending/outstanding quantity"""
        return self.quantity - self.received_quantity
    
    @property
    def is_fully_received(self):
        """Check if item is fully received"""
        return self.received_quantity >= self.quantity
    
    @property
    def receive_percentage(self):
        """Calculate receive percentage"""
        if self.quantity > 0:
            return (self.received_quantity / self.quantity) * 100
        return 0
    
    def save(self, *args, **kwargs):
        # Calculate total amount
        self.total_amount = self.quantity * self.unit_price
        
        # Store item details
        if self.item and not self.item_description:
            self.item_description = self.item.description
            self.item_sku = self.item.sku
        
        super().save(*args, **kwargs)
        
        # Update purchase order totals
        if hasattr(self, 'purchase_order'):
            self.purchase_order.calculate_totals()
    
    class Meta:
        verbose_name = "Purchase Order Item"
        verbose_name_plural = "Purchase Order Items"
        unique_together = ['purchase_order', 'item']

class GoodsReceipt(TenantTimeStampedModel):
    """Goods receipt/receiving records"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('partial', 'Partial'),
        ('completed', 'Completed'),
        ('discrepancy', 'Discrepancy'),
    ]
    
    # Reference Information
    receipt_number = models.CharField(max_length=50, unique=True)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='receipts')
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='goods_receipts')
    
    # Receipt Details
    receipt_date = models.DateField(default=timezone.now)
    delivery_note_number = models.CharField(max_length=100, blank=True)
    vehicle_number = models.CharField(max_length=50, blank=True)
    driver_name = models.CharField(max_length=100, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Quality Check
    quality_check_passed = models.BooleanField(default=True)
    quality_notes = models.TextField(blank=True)
    
    # Staff
    received_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='goods_received'
    )
    
    # Additional Information
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"GR-{self.receipt_number} - {self.supplier.name}"
    
    @property
    def total_items(self):
        """Get total number of item types received"""
        return self.items.count()
    
    @property
    def total_quantity(self):
        """Get total quantity received"""
        return self.items.aggregate(
            total=models.Sum('received_quantity')
        )['total'] or 0
    
    def complete_receipt(self):
        """Complete the goods receipt and update inventory"""
        for receipt_item in self.items.all():
            # Update inventory stock
            inventory_item = receipt_item.purchase_order_item.item
            old_stock = inventory_item.current_stock
            inventory_item.current_stock += receipt_item.received_quantity
            inventory_item.save()
            
            # Create stock movement
            try:
                from apps.inventory.models import StockMovement
                StockMovement.objects.create(
                    item=inventory_item,
                    movement_type='in',
                    quantity=receipt_item.received_quantity,
                    unit_cost=receipt_item.purchase_order_item.unit_price,
                    old_stock=old_stock,
                    new_stock=inventory_item.current_stock,
                    reference_number=self.receipt_number,
                    reference_type='purchase',
                    purchase_order=self.purchase_order,
                    reason=f"Goods receipt from {self.supplier.name}"
                )
            except ImportError:
                pass
            
            # Update purchase order item received quantity
            po_item = receipt_item.purchase_order_item
            po_item.received_quantity += receipt_item.received_quantity
            po_item.received_date = self.receipt_date
            po_item.save()
        
        # Update purchase order status
        if self.purchase_order.is_fully_received:
            self.purchase_order.complete_order()
        elif self.purchase_order.completion_percentage > 0:
            self.purchase_order.status = 'partially_received'
            self.purchase_order.save()
        
        self.status = 'completed'
        self.save()
    
    class Meta:
        verbose_name = "Goods Receipt"
        verbose_name_plural = "Goods Receipts"
        ordering = ['-receipt_date']

class GoodsReceiptItem(TenantTimeStampedModel):
    """Items in a goods receipt"""
    goods_receipt = models.ForeignKey(GoodsReceipt, on_delete=models.CASCADE, related_name='items')
    purchase_order_item = models.ForeignKey(PurchaseOrderItem, on_delete=models.CASCADE)
    
    # Quantities
    expected_quantity = models.DecimalField(max_digits=10, decimal_places=2)
    received_quantity = models.DecimalField(max_digits=10, decimal_places=2)
    damaged_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Quality Information
    quality_passed = models.BooleanField(default=True)
    quality_notes = models.TextField(blank=True)
    
    # Lot/Batch Information
    lot_number = models.CharField(max_length=100, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    manufacture_date = models.DateField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.purchase_order_item.item.name} - {self.received_quantity}"
    
    @property
    def variance_quantity(self):
        """Calculate quantity variance"""
        return self.received_quantity - self.expected_quantity
    
    @property
    def has_discrepancy(self):
        """Check if there's a quantity discrepancy"""
        return self.variance_quantity != 0 or self.damaged_quantity > 0 or not self.quality_passed
    
    def save(self, *args, **kwargs):
        # Set expected quantity from purchase order item
        if not self.expected_quantity and self.purchase_order_item:
            self.expected_quantity = self.purchase_order_item.pending_quantity
        
        super().save(*args, **kwargs)
        
        # Update goods receipt status if there are discrepancies
        if self.has_discrepancy:
            self.goods_receipt.status = 'discrepancy'
            self.goods_receipt.save()
    
    class Meta:
        verbose_name = "Goods Receipt Item"
        verbose_name_plural = "Goods Receipt Items"

class SupplierEvaluation(TenantTimeStampedModel):
    """Supplier performance evaluations"""
    
    EVALUATION_PERIODS = [
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('annual', 'Annual'),
        ('order_based', 'Order Based'),
    ]
    
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='evaluations')
    purchase_order = models.ForeignKey(
        PurchaseOrder, 
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='evaluations'
    )
    
    # Evaluation Period
    evaluation_period = models.CharField(max_length=20, choices=EVALUATION_PERIODS, default='order_based')
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Ratings (1-5 scale)
    quality_rating = models.DecimalField(
        max_digits=3, 
        decimal_places=2,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    delivery_rating = models.DecimalField(
        max_digits=3, 
        decimal_places=2,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    service_rating = models.DecimalField(
        max_digits=3, 
        decimal_places=2,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    price_rating = models.DecimalField(
        max_digits=3, 
        decimal_places=2,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    communication_rating = models.DecimalField(
        max_digits=3, 
        decimal_places=2,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    
    # Overall Rating
    overall_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    
    # Comments
    quality_comments = models.TextField(blank=True)
    delivery_comments = models.TextField(blank=True)
    service_comments = models.TextField(blank=True)
    general_comments = models.TextField(blank=True)
    
    # Recommendations
    recommendations = models.TextField(blank=True)
    continue_partnership = models.BooleanField(default=True)
    
    # Evaluator
    evaluated_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supplier_evaluations'
    )
    
    def __str__(self):
        return f"{self.supplier.name} - {self.period_start} to {self.period_end}"
    
    @property
    def weighted_score(self):
        """Calculate weighted overall score"""
        # Quality: 30%, Delivery: 25%, Service: 20%, Price: 15%, Communication: 10%
        return (
            self.quality_rating * 0.30 +
            self.delivery_rating * 0.25 +
            self.service_rating * 0.20 +
            self.price_rating * 0.15 +
            self.communication_rating * 0.10
        )
    
    def save(self, *args, **kwargs):
        # Calculate overall rating as average
        ratings = [
            self.quality_rating,
            self.delivery_rating,
            self.service_rating,
            self.price_rating,
            self.communication_rating
        ]
        self.overall_rating = sum(ratings) / len(ratings)
        
        super().save(*args, **kwargs)
        
        # Update supplier ratings
        self.supplier.update_performance_metrics()
    
    class Meta:
        verbose_name = "Supplier Evaluation"
        verbose_name_plural = "Supplier Evaluations"
        ordering = ['-period_end']

class SupplierPayment(TenantTimeStampedModel):
    """Payments made to suppliers"""
    
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('mobile_money', 'Mobile Money'),
        ('card', 'Card Payment'),
        ('online', 'Online Payment'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Reference Information
    payment_number = models.CharField(max_length=50, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='payments')
    purchase_orders = models.ManyToManyField(PurchaseOrder, blank=True, related_name='payments')
    
    # Payment Details
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    payment_date = models.DateField(default=timezone.now)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Transaction Details
    reference_number = models.CharField(max_length=100, blank=True)
    transaction_id = models.CharField(max_length=100, blank=True)
    
    # Bank Details (for transfers)
    bank_name = models.CharField(max_length=100, blank=True)
    account_number = models.CharField(max_length=50, blank=True)
    
    # Cheque Details
    cheque_number = models.CharField(max_length=50, blank=True)
    cheque_date = models.DateField(null=True, blank=True)
    
    # Processing
    processed_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_supplier_payments'
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # Additional Information
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"Payment {self.payment_number} - {self.supplier.name} - KES {self.amount}"
    
    def process_payment(self, user=None):
        """Process the payment"""
        self.status = 'processing'
        if user and hasattr(user, 'employee_profile'):
            self.processed_by = user.employee_profile
            self.processed_at = timezone.now()
        self.save()
    
    def complete_payment(self):
        """Complete the payment and update supplier balance"""
        self.status = 'completed'
        self.save()
        
        # Update supplier balance
        self.supplier.current_balance += self.amount
        self.supplier.save()
    
    def fail_payment(self, reason=""):
        """Mark payment as failed"""
        self.status = 'failed'
        if reason:
            self.notes = f"{self.notes}\nFailed: {reason}".strip()
        self.save()
    
    class Meta:
        verbose_name = "Supplier Payment"
        verbose_name_plural = "Supplier Payments"
        ordering = ['-payment_date']

class SupplierDocument(TenantTimeStampedModel):
    """Documents related to suppliers"""
    
    DOCUMENT_TYPES = [
        ('contract', 'Contract'),
        ('certificate', 'Certificate'),
        ('license', 'License'),
        ('tax_document', 'Tax Document'),
        ('bank_details', 'Bank Details'),
        ('insurance', 'Insurance'),
        ('quality_cert', 'Quality Certificate'),
        ('catalog', 'Product Catalog'),
        ('price_list', 'Price List'),
        ('other', 'Other'),
    ]
    
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='documents')
    
    # Document Information
    name = models.CharField(max_length=200)
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    description = models.TextField(blank=True)
    
    # File
    file = models.FileField(upload_to='supplier_documents/')
    file_size = models.IntegerField(default=0, help_text="File size in bytes")
    
    # Validity
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_supplier_documents'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Upload Information
    uploaded_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_supplier_documents'
    )
    
    def __str__(self):
        return f"{self.supplier.name} - {self.name}"
    
    @property
    def is_expired(self):
        """Check if document is expired"""
        if self.expiry_date:
            return timezone.now().date() > self.expiry_date
        return False
    
    @property
    def days_to_expiry(self):
        """Calculate days until expiry"""
        if self.expiry_date:
            delta = self.expiry_date - timezone.now().date()
            return delta.days
        return None
    
    @property
    def is_expiring_soon(self):
        """Check if document expires within 30 days"""
        days = self.days_to_expiry
        return days is not None and 0 <= days <= 30
    
    def verify_document(self, user):
        """Verify the document"""
        self.is_verified = True
        if hasattr(user, 'employee_profile'):
            self.verified_by = user.employee_profile
        self.verified_at = timezone.now()
        self.save()
    
    def save(self, *args, **kwargs):
        # Set file size
        if self.file:
            self.file_size = self.file.size
        
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = "Supplier Document"
        verbose_name_plural = "Supplier Documents"
        ordering = ['-created_at']

class Invoice(TenantTimeStampedModel):
    """Invoices from suppliers"""
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('received', 'Received'),
        ('verified', 'Verified'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('partial', 'Partially Paid'),
        ('paid', 'Fully Paid'),
        ('overdue', 'Overdue'),
    ]
    
    # Reference Information
    invoice_number = models.CharField(max_length=50, unique=True)
    supplier_invoice_number = models.CharField(max_length=100, help_text="Supplier's invoice number")
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='invoices')
    purchase_order = models.ForeignKey(
        PurchaseOrder, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='invoices'
    )
    
    # Dates
    invoice_date = models.DateField()
    due_date = models.DateField()
    received_date = models.DateField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='received')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    
    # Financial Information
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Currency
    currency = models.CharField(max_length=3, default='KES')
    
    # Additional Information
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    # Verification
    verified_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_invoices'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Approval
    approved_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_invoices'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # File attachment
    invoice_file = models.FileField(
        upload_to='invoices/',
        null=True,
        blank=True,
        help_text="Upload the original invoice file"
    )
    
    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.supplier.name}"
    
    @property
    def outstanding_amount(self):
        """Calculate outstanding amount"""
        return self.total_amount - self.paid_amount
    
    @property
    def is_overdue(self):
        """Check if invoice is overdue"""
        return timezone.now().date() > self.due_date and self.payment_status != 'paid'
    
    @property
    def days_overdue(self):
        """Calculate days overdue"""
        if not self.is_overdue:
            return 0
        return (timezone.now().date() - self.due_date).days
    
    @property
    def payment_percentage(self):
        """Calculate payment percentage"""
        if self.total_amount > 0:
            return (self.paid_amount / self.total_amount) * 100
        return 0
    
    def verify_invoice(self, user):
        """Verify the invoice"""
        self.status = 'verified'
        if hasattr(user, 'employee_profile'):
            self.verified_by = user.employee_profile
        self.verified_at = timezone.now()
        self.save()
    
    def approve_invoice(self, user):
        """Approve the invoice for payment"""
        self.status = 'approved'
        if hasattr(user, 'employee_profile'):
            self.approved_by = user.employee_profile
        self.approved_at = timezone.now()
        self.save()
    
    def mark_paid(self, amount=None):
        """Mark invoice as paid"""
        if amount is None:
            amount = self.outstanding_amount
        
        self.paid_amount += amount
        
        if self.paid_amount >= self.total_amount:
            self.payment_status = 'paid'
            self.status = 'paid'
        else:
            self.payment_status = 'partial'
        
        self.save()
    
    class Meta:
        verbose_name = "Invoice"
        verbose_name_plural = "Invoices"
        ordering = ['-invoice_date']


class InvoiceItem(TenantTimeStampedModel):
    """Items in an invoice"""
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    purchase_order_item = models.ForeignKey(
        PurchaseOrderItem, 
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoice_items'
    )
    
    # Item details
    description = models.TextField()
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Additional info
    item_code = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.description} - {self.quantity} @ {self.unit_price}"
    
    def save(self, *args, **kwargs):
        # Calculate total amount
        self.total_amount = self.quantity * self.unit_price
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = "Invoice Item"
        verbose_name_plural = "Invoice Items"
