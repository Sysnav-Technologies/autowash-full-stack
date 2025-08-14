from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from apps.core.tenant_models import TenantTimeStampedModel, TenantSoftDeleteModel
from apps.core.utils import upload_to_path
from decimal import Decimal
import uuid
from django.utils import timezone
class InventoryCategory(TenantTimeStampedModel):
    """Categories for organizing inventory items"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='subcategories'
    )
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name
    
    @property
    def full_name(self):
        """Get full category path"""
        if self.parent:
            return f"{self.parent.full_name} > {self.name}"
        return self.name
    
    @property
    def item_count(self):
        """Get total items in this category and subcategories"""
        count = self.items.filter(is_active=True).count()
        for subcategory in self.subcategories.filter(is_active=True):
            count += subcategory.item_count
        return count
    
    class Meta:
        verbose_name = "Inventory Category"
        verbose_name_plural = "Inventory Categories"
        ordering = ['name']

class Unit(TenantTimeStampedModel):
    """Units of measurement for inventory items"""
    name = models.CharField(max_length=50, unique=True)
    abbreviation = models.CharField(max_length=10, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.name} ({self.abbreviation})"
    
    class Meta:
        verbose_name = "Unit of Measurement"
        verbose_name_plural = "Units of Measurement"
        ordering = ['name']

class InventoryItem(TenantSoftDeleteModel):
    """Inventory items/products"""
    
    ITEM_TYPES = [
        ('product', 'Finished Product'),
        ('raw_material', 'Raw Material'),
        ('consumable', 'Consumable'),
        ('equipment', 'Equipment'),
        ('spare_part', 'Spare Part'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(InventoryCategory, on_delete=models.CASCADE, related_name='items')
    item_type = models.CharField(max_length=20, choices=ITEM_TYPES, default='product')
    
    # Identification
    sku = models.CharField(max_length=50, unique=True, help_text="Stock Keeping Unit")
    barcode = models.CharField(max_length=100, blank=True, unique=True)
    
    # Measurement
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE)
    weight = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    dimensions = models.CharField(max_length=100, blank=True, help_text="Length x Width x Height")
    
    # Stock Information
    current_stock = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    minimum_stock_level = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    maximum_stock_level = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    reorder_point = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    reorder_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Pricing
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Supplier Information
    primary_supplier = models.ForeignKey(
        'suppliers.Supplier', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='primary_items'
    )
    
    # Storage Information
    storage_location = models.CharField(max_length=100, blank=True)
    storage_requirements = models.TextField(blank=True, help_text="Special storage requirements")
    
    # Status and Flags
    is_active = models.BooleanField(default=True)
    is_taxable = models.BooleanField(default=True)
    track_serial_numbers = models.BooleanField(default=False)
    track_expiry = models.BooleanField(default=False)
    
    # Quality Control
    quality_check_required = models.BooleanField(default=False)
    shelf_life_days = models.IntegerField(null=True, blank=True, help_text="Shelf life in days")
    
    # Media
    image = models.ImageField(upload_to='inventory_items/', blank=True, null=True)
    
    def __str__(self):
        return f"{self.name} ({self.sku})"
    
    @property
    def stock_value(self):
        """Calculate total stock value"""
        return self.current_stock * self.unit_cost
    
    @property
    def is_low_stock(self):
        """Check if item is below minimum stock level"""
        return self.current_stock <= self.minimum_stock_level
    
    @property
    def is_out_of_stock(self):
        """Check if item is out of stock"""
        return self.current_stock <= 0
    
    @property
    def needs_reorder(self):
        """Check if item needs to be reordered"""
        return self.current_stock <= self.reorder_point
    
    @property
    def stock_status(self):
        """Get stock status as string"""
        if self.is_out_of_stock:
            return 'out_of_stock'
        elif self.is_low_stock:
            return 'low_stock'
        elif self.current_stock >= self.maximum_stock_level:
            return 'overstock'
        else:
            return 'normal'
    
    @property
    def total_consumed(self):
        """Get total quantity consumed"""
        return self.consumption_records.aggregate(
            total=models.Sum('quantity')
        )['total'] or 0
    
    def adjust_stock(self, quantity, reason, user=None):
        """Adjust stock and create adjustment record"""
        old_stock = self.current_stock
        self.current_stock += quantity
        self.save()
        
        StockAdjustment.objects.create(
            item=self,
            adjustment_type='manual',
            quantity=quantity,
            old_stock=old_stock,
            new_stock=self.current_stock,
            reason=reason,
            created_by=user
        )
    
    class Meta:
        verbose_name = "Inventory Item"
        verbose_name_plural = "Inventory Items"
        ordering = ['name']

class StockMovement(TenantTimeStampedModel):
    """Stock movement tracking"""
    
    MOVEMENT_TYPES = [
        ('in', 'Stock In'),
        ('out', 'Stock Out'),
        ('adjustment', 'Adjustment'),
        ('transfer', 'Transfer'),
    ]
    
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='stock_movements')
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Stock levels
    old_stock = models.DecimalField(max_digits=10, decimal_places=2)
    new_stock = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Reference information
    reference_number = models.CharField(max_length=50, blank=True)
    reference_type = models.CharField(
        max_length=20,
        choices=[
            ('purchase', 'Purchase Order'),
            ('sale', 'Sale/Service'),
            ('adjustment', 'Stock Adjustment'),
            ('transfer', 'Stock Transfer'),
            ('return', 'Return'),
            ('damage', 'Damage/Loss'),
        ],
        blank=True
    )
    
    # Additional information
    reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    # Related records
    purchase_order = models.ForeignKey(
        'suppliers.PurchaseOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_movements'
    )
    service_order = models.ForeignKey(
        'services.ServiceOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_movements'
    )
    
    def __str__(self):
        return f"{self.item.name} - {self.get_movement_type_display()} ({self.quantity})"
    
    @property
    def created_by(self):
        """Get the user who created this movement"""
        if self.created_by_user_id:
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                return User.objects.get(id=self.created_by_user_id)
            except User.DoesNotExist:
                return None
        return None
    
    @property
    def total_value(self):
        """Calculate total value of movement"""
        return abs(self.quantity) * self.unit_cost
    
    class Meta:
        verbose_name = "Stock Movement"
        verbose_name_plural = "Stock Movements"
        ordering = ['-created_at']

class StockAdjustment(TenantTimeStampedModel):
    """Stock adjustments and corrections"""
    
    ADJUSTMENT_TYPES = [
        ('manual', 'Manual Adjustment'),
        ('damage', 'Damage'),
        ('theft', 'Theft'),
        ('expired', 'Expired'),
        ('found', 'Found'),
        ('cycle_count', 'Cycle Count'),
        ('return', 'Return'),
    ]
    
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='adjustments')
    adjustment_type = models.CharField(max_length=20, choices=ADJUSTMENT_TYPES)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Stock levels
    old_stock = models.DecimalField(max_digits=10, decimal_places=2)
    new_stock = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Adjustment details
    reason = models.TextField()
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Approval
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_adjustments'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.item.name} - {self.get_adjustment_type_display()} ({self.quantity})"
    
    @property
    def created_by(self):
        """Get the user who created this adjustment"""
        if self.created_by_user_id:
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                return User.objects.get(id=self.created_by_user_id)
            except User.DoesNotExist:
                return None
        return None
    
    @property
    def total_value(self):
        """Calculate total value of adjustment"""
        return abs(self.quantity) * self.unit_cost
    
    def approve(self, user):
        """Approve the adjustment"""
        self.is_approved = True
        self.approved_by = user.employee_profile if hasattr(user, 'employee_profile') else None
        self.approved_at = timezone.now()
        self.save()
        
        # Create stock movement
        stock_movement = StockMovement.objects.create(
            item=self.item,
            movement_type='adjustment',
            quantity=self.quantity,
            unit_cost=self.unit_cost,
            old_stock=self.old_stock,
            new_stock=self.new_stock,
            reference_type='adjustment',
            reason=self.reason,
        )
        # Set created_by user ID
        stock_movement.set_created_by(user)
        stock_movement.save()
    
    class Meta:
        verbose_name = "Stock Adjustment"
        verbose_name_plural = "Stock Adjustments"
        ordering = ['-created_at']

class ItemConsumption(TenantTimeStampedModel):
    """Track item consumption for services"""
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='consumption_records')
    service_order = models.ForeignKey(
        'services.ServiceOrder',
        on_delete=models.CASCADE,
        related_name='item_consumptions'
    )
    service = models.ForeignKey(
        'services.Service',
        on_delete=models.CASCADE,
        related_name='item_consumptions'
    )
    
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Staff who used the item
    used_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='item_usage'
    )
    
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.item.name} - {self.service.name} ({self.quantity})"
    
    @property
    def total_cost(self):
        """Calculate total cost of consumption"""
        return self.quantity * self.unit_cost
    
    class Meta:
        verbose_name = "Item Consumption"
        verbose_name_plural = "Item Consumptions"
        ordering = ['-created_at']

class StockTake(TenantTimeStampedModel):
    """Stock take/physical inventory count"""
    
    STATUS_CHOICES = [
        ('planned', 'Planned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned')
    
    # Scope
    categories = models.ManyToManyField(InventoryCategory, blank=True)
    items = models.ManyToManyField(InventoryItem, blank=True)
    include_all_items = models.BooleanField(default=True)
    
    # Timing
    scheduled_date = models.DateField()
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Staff
    supervisor = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supervised_stock_takes'
    )
    counters = models.ManyToManyField(
        'employees.Employee',
        blank=True,
        related_name='stock_take_counts'
    )
    
    # Results
    total_items_counted = models.IntegerField(default=0)
    discrepancies_found = models.IntegerField(default=0)
    total_variance_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    def __str__(self):
        return f"{self.name} - {self.scheduled_date}"
    
    def start_stock_take(self):
        """Start the stock take process"""
        self.status = 'in_progress'
        self.started_at = timezone.now()
        self.save()
        
        # Create count records for items
        items_to_count = self.get_items_to_count()
        for item in items_to_count:
            StockTakeCount.objects.get_or_create(
                stock_take=self,
                item=item,
                defaults={
                    'system_quantity': item.current_stock,
                    'counted_quantity': 0
                }
            )
    
    def complete_stock_take(self):
        """Complete the stock take and process results"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        
        # Calculate statistics
        counts = self.count_records.all()
        self.total_items_counted = counts.count()
        self.discrepancies_found = counts.filter(has_discrepancy=True).count()
        self.total_variance_value = sum(
            count.variance_value for count in counts if count.has_discrepancy
        )
        self.save()
        
        # Create adjustments for discrepancies
        for count in counts.filter(has_discrepancy=True):
            if count.variance_quantity != 0:
                StockAdjustment.objects.create(
                    item=count.item,
                    adjustment_type='cycle_count',
                    quantity=count.variance_quantity,
                    old_stock=count.system_quantity,
                    new_stock=count.counted_quantity,
                    reason=f"Stock take adjustment - {self.name}",
                    unit_cost=count.item.unit_cost,
                    is_approved=True,
                    approved_by=self.supervisor,
                    approved_at=timezone.now()
                )
                
                # Update item stock
                count.item.current_stock = count.counted_quantity
                count.item.save()
    
    def get_items_to_count(self):
        """Get items to be counted in this stock take"""
        if self.include_all_items:
            return InventoryItem.objects.filter(is_active=True)
        
        items = InventoryItem.objects.none()
        
        if self.categories.exists():
            items = items.union(
                InventoryItem.objects.filter(category__in=self.categories.all())
            )
        
        if self.items.exists():
            items = items.union(self.items.all())
        
        return items.distinct()
    
    class Meta:
        verbose_name = "Stock Take"
        verbose_name_plural = "Stock Takes"
        ordering = ['-created_at']

class StockTakeCount(TenantTimeStampedModel):
    """Individual item counts during stock take"""
    stock_take = models.ForeignKey(StockTake, on_delete=models.CASCADE, related_name='count_records')
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE)
    
    # Quantities
    system_quantity = models.DecimalField(max_digits=10, decimal_places=2)
    counted_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Count details
    counted_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_counts'
    )
    count_date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    
    # Verification
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_counts'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.stock_take.name} - {self.item.name}"
    
    @property
    def variance_quantity(self):
        """Calculate quantity variance"""
        return self.counted_quantity - self.system_quantity
    
    @property
    def variance_value(self):
        """Calculate value variance"""
        return self.variance_quantity * self.item.unit_cost
    
    @property
    def has_discrepancy(self):
        """Check if there's a discrepancy"""
        return self.variance_quantity != 0
    
    @property
    def variance_percentage(self):
        """Calculate variance percentage"""
        if self.system_quantity > 0:
            return (self.variance_quantity / self.system_quantity) * 100
        return 0
    
    class Meta:
        unique_together = ['stock_take', 'item']
        verbose_name = "Stock Take Count"
        verbose_name_plural = "Stock Take Counts"

class InventoryAlert(TenantTimeStampedModel):
    """Inventory alerts and notifications"""
    
    ALERT_TYPES = [
        ('low_stock', 'Low Stock'),
        ('out_of_stock', 'Out of Stock'),
        ('reorder_point', 'Reorder Point Reached'),
        ('overstock', 'Overstock'),
        ('expired', 'Expired Items'),
        ('near_expiry', 'Items Near Expiry'),
    ]
    
    PRIORITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='alerts')
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    priority = models.CharField(max_length=20, choices=PRIORITY_LEVELS, default='medium')
    
    message = models.TextField()
    current_stock = models.DecimalField(max_digits=10, decimal_places=2)
    threshold_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_inventory_alerts'
    )
    
    # Notifications
    email_sent = models.BooleanField(default=False)
    sms_sent = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.item.name} - {self.get_alert_type_display()}"
    
    def resolve(self, user=None):
        """Mark alert as resolved"""
        self.is_resolved = True
        self.resolved_at = timezone.now()
        if user and hasattr(user, 'employee_profile'):
            self.resolved_by = user.employee_profile
        self.save()
    
    class Meta:
        verbose_name = "Inventory Alert"
        verbose_name_plural = "Inventory Alerts"
        ordering = ['-created_at']

class ItemLocation(TenantTimeStampedModel):
    """Track item locations within warehouse/storage"""
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='locations')
    
    # Location details
    warehouse = models.CharField(max_length=100, default='Main Warehouse')
    zone = models.CharField(max_length=50, blank=True)
    aisle = models.CharField(max_length=20, blank=True)
    shelf = models.CharField(max_length=20, blank=True)
    bin = models.CharField(max_length=20, blank=True)
    
    # Quantity at this location
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Location properties
    is_primary = models.BooleanField(default=False)
    is_picking_location = models.BooleanField(default=True)
    
    def __str__(self):
        location_parts = [self.warehouse]
        if self.zone:
            location_parts.append(self.zone)
        if self.aisle:
            location_parts.append(f"Aisle {self.aisle}")
        if self.shelf:
            location_parts.append(f"Shelf {self.shelf}")
        if self.bin:
            location_parts.append(f"Bin {self.bin}")
        
        return f"{self.item.name} - {' > '.join(location_parts)}"
    
    @property
    def full_location(self):
        """Get full location string"""
        location_parts = []
        if self.zone:
            location_parts.append(self.zone)
        if self.aisle:
            location_parts.append(f"A{self.aisle}")
        if self.shelf:
            location_parts.append(f"S{self.shelf}")
        if self.bin:
            location_parts.append(f"B{self.bin}")
        
        return '-'.join(location_parts) if location_parts else self.warehouse
    
    class Meta:
        unique_together = ['item', 'warehouse', 'zone', 'aisle', 'shelf', 'bin']
        verbose_name = "Item Location"
        verbose_name_plural = "Item Locations"

class ItemSerial(TenantTimeStampedModel):
    """Serial number tracking for items"""
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='serials')
    serial_number = models.CharField(max_length=100, unique=True)
    
    # Status
    STATUS_CHOICES = [
        ('in_stock', 'In Stock'),
        ('sold', 'Sold'),
        ('damaged', 'Damaged'),
        ('returned', 'Returned'),
        ('reserved', 'Reserved'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_stock')
    
    # Purchase information
    purchase_date = models.DateField(null=True, blank=True)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    supplier = models.ForeignKey(
        'suppliers.Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Sale/usage information
    sold_date = models.DateField(null=True, blank=True)
    sold_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    service_order = models.ForeignKey(
        'services.ServiceOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='serial_items'
    )
    
    # Warranty information
    warranty_start = models.DateField(null=True, blank=True)
    warranty_end = models.DateField(null=True, blank=True)
    
    # Location
    location = models.ForeignKey(
        ItemLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.item.name} - {self.serial_number}"
    
    @property
    def is_under_warranty(self):
        """Check if item is still under warranty"""
        if self.warranty_end:
            from django.utils import timezone
            return timezone.now().date() <= self.warranty_end
        return False
    
    class Meta:
        verbose_name = "Item Serial Number"
        verbose_name_plural = "Item Serial Numbers"
        ordering = ['serial_number']

class ItemExpiry(TenantTimeStampedModel):
    """Track expiry dates for items"""
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='expiry_records')
    batch_number = models.CharField(max_length=100, blank=True)
    
    # Quantities
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    remaining_quantity = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Dates
    manufacture_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField()
    
    # Status
    is_expired = models.BooleanField(default=False)
    is_disposed = models.BooleanField(default=False)
    disposed_date = models.DateField(null=True, blank=True)
    disposed_reason = models.TextField(blank=True)
    
    # Location
    location = models.ForeignKey(
        ItemLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    def __str__(self):
        return f"{self.item.name} - Exp: {self.expiry_date}"
    
    @property
    def days_to_expiry(self):
        """Calculate days until expiry"""
        from django.utils import timezone
        delta = self.expiry_date - timezone.now().date()
        return delta.days
    
    @property
    def is_near_expiry(self):
        """Check if item is near expiry (within 30 days)"""
        return 0 <= self.days_to_expiry <= 30
    
    def mark_expired(self):
        """Mark batch as expired"""
        self.is_expired = True
        self.save()
        
        # Create alert
        InventoryAlert.objects.create(
            item=self.item,
            alert_type='expired',
            priority='high',
            message=f"Batch {self.batch_number} of {self.item.name} has expired",
            current_stock=self.item.current_stock
        )
    
    class Meta:
        verbose_name = "Item Expiry Record"
        verbose_name_plural = "Item Expiry Records"
        ordering = ['expiry_date']


class DailyOperations(TenantTimeStampedModel):
    """Daily operations tracking for inventory management"""
    operation_date = models.DateField(unique=True)
    
    # Shift information
    SHIFT_CHOICES = [
        ('morning', 'Morning Shift'),
        ('afternoon', 'Afternoon Shift'),
        ('evening', 'Evening Shift'),
        ('night', 'Night Shift'),
    ]
    current_shift = models.CharField(max_length=20, choices=SHIFT_CHOICES, default='morning')
    
    # Staff assignments
    shift_supervisor = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supervised_operations'
    )
    
    # Operation status
    STATUS_CHOICES = [
        ('planning', 'Planning'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('reconciled', 'Reconciled'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planning')
    
    # Daily targets
    target_services = models.IntegerField(default=0)
    actual_services = models.IntegerField(default=0)
    
    # Reconciliation
    reconciled_at = models.DateTimeField(null=True, blank=True)
    reconciled_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reconciled_operations'
    )
    
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"Operations - {self.operation_date}"
    
    @property
    def service_completion_rate(self):
        """Calculate service completion rate"""
        if self.target_services == 0:
            return 0
        return (self.actual_services / self.target_services) * 100
    
    @property
    def total_consumption_value(self):
        """Get total value of items consumed today"""
        from django.db.models import Sum, F
        return self.bay_consumptions.aggregate(
            total=Sum(F('quantity') * F('unit_cost'))
        )['total'] or 0
    
    class Meta:
        verbose_name = "Daily Operations"
        verbose_name_plural = "Daily Operations"
        ordering = ['-operation_date']


class BayConsumption(TenantTimeStampedModel):
    """Track inventory consumption by wash bays"""
    daily_operations = models.ForeignKey(
        DailyOperations,
        on_delete=models.CASCADE,
        related_name='bay_consumptions'
    )
    
    # Bay information
    bay = models.ForeignKey(
        'services.ServiceBay',
        on_delete=models.CASCADE,
        related_name='consumptions'
    )
    
    # Item consumption
    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.CASCADE,
        related_name='bay_consumptions'
    )
    
    # Consumption details
    quantity_allocated = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Quantity transferred to bay"
    )
    quantity_used = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text="Actual quantity consumed"
    )
    quantity_remaining = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text="Quantity remaining at bay"
    )
    
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Transfer details
    transferred_at = models.DateTimeField(auto_now_add=True)
    transferred_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        related_name='bay_transfers'
    )
    
    # Usage tracking
    last_updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        related_name='bay_updates'
    )
    
    # Status
    STATUS_CHOICES = [
        ('transferred', 'Transferred to Bay'),
        ('in_use', 'In Use'),
        ('completed', 'Completed'),
        ('returned', 'Returned to Stock'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='transferred')
    
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.item.name} - Bay {self.bay.bay_number} ({self.daily_operations.operation_date})"
    
    @property
    def total_allocated_value(self):
        """Calculate total allocated value"""
        return self.quantity_allocated * self.unit_cost
    
    @property
    def total_used_value(self):
        """Calculate total used value"""
        return self.quantity_used * self.unit_cost
    
    @property
    def wastage(self):
        """Calculate wastage"""
        return self.quantity_allocated - self.quantity_used - self.quantity_remaining
    
    @property
    def wastage_value(self):
        """Calculate wastage value"""
        return self.wastage * self.unit_cost
    
    def save(self, *args, **kwargs):
        # Auto-calculate remaining quantity
        self.quantity_remaining = self.quantity_allocated - self.quantity_used
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = "Bay Consumption"
        verbose_name_plural = "Bay Consumptions"
        unique_together = ['daily_operations', 'bay', 'item']
        ordering = ['-daily_operations__operation_date', 'bay__bay_number']


class InventoryReconciliation(TenantTimeStampedModel):
    """Daily inventory reconciliation records"""
    daily_operations = models.OneToOneField(
        DailyOperations,
        on_delete=models.CASCADE,
        related_name='reconciliation'
    )
    
    # Reconciliation summary
    total_items_checked = models.IntegerField(default=0)
    total_discrepancies = models.IntegerField(default=0)
    total_variance_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Reconciliation status
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Approval
    is_approved = models.BooleanField(default=False)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_reconciliations'
    )
    
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"Reconciliation - {self.daily_operations.operation_date}"
    
    @property
    def accuracy_rate(self):
        """Calculate reconciliation accuracy rate"""
        if self.total_items_checked == 0:
            return 100
        return ((self.total_items_checked - self.total_discrepancies) / self.total_items_checked) * 100
    
    class Meta:
        verbose_name = "Inventory Reconciliation"
        verbose_name_plural = "Inventory Reconciliations"
        ordering = ['-daily_operations__operation_date']


class ReconciliationItem(TenantTimeStampedModel):
    """Individual item reconciliation records"""
    reconciliation = models.ForeignKey(
        InventoryReconciliation,
        on_delete=models.CASCADE,
        related_name='item_records'
    )
    
    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.CASCADE,
        related_name='reconciliation_records'
    )
    
    # Stock levels
    system_stock = models.DecimalField(max_digits=10, decimal_places=2)
    physical_stock = models.DecimalField(max_digits=10, decimal_places=2)
    variance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    variance_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Reconciliation details
    has_discrepancy = models.BooleanField(default=False)
    reason = models.TextField(blank=True)
    action_taken = models.TextField(blank=True)
    
    # Bay usage breakdown
    bay_usage = models.JSONField(default=dict, blank=True)  # {'bay_1': 5.5, 'bay_2': 3.2}
    
    verified_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    def save(self, *args, **kwargs):
        # Calculate variance
        self.variance = self.physical_stock - self.system_stock
        self.variance_value = self.variance * self.item.unit_cost
        self.has_discrepancy = abs(self.variance) > 0.01  # Allow for small rounding differences
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.item.name} - {self.reconciliation.daily_operations.operation_date}"
    
    class Meta:
        verbose_name = "Reconciliation Item"
        verbose_name_plural = "Reconciliation Items"
        unique_together = ['reconciliation', 'item']
        ordering = ['item__name']
