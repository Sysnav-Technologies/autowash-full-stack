from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.tenant_models import TenantTimeStampedModel  
from decimal import Decimal
from django.utils import timezone
import uuid


class ExpenseCategory(TenantTimeStampedModel):
    """Categories for organizing expenses"""
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
    # Track if this category is for auto-generated expenses
    is_auto_category = models.BooleanField(default=False)
    
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
    def total_expenses(self):
        """Get total expenses for this category"""
        return self.expenses.filter(is_active=True).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
    
    class Meta:
        verbose_name = "Expense Category"
        verbose_name_plural = "Expense Categories"
        ordering = ['name']


class Vendor(TenantTimeStampedModel):
    """Vendors/Suppliers for expenses"""
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    tax_number = models.CharField(max_length=50, blank=True)
    bank_account = models.CharField(max_length=100, blank=True)
    payment_terms = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name
    
    @property
    def total_expenses(self):
        """Get total expenses from this vendor"""
        return self.expenses.filter(is_active=True).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
    
    class Meta:
        ordering = ['name']


class Expense(TenantTimeStampedModel):
    """Main expense model with auto-linking capabilities"""
    
    EXPENSE_TYPE_CHOICES = [
        ('manual', 'Manual Entry'),
        ('inventory', 'Inventory Purchase'),
        ('salary', 'Employee Salary'),
        ('commission', 'Service Commission'),
        ('utility', 'Utility Bill'),
        ('rent', 'Rent Payment'),
        ('maintenance', 'Maintenance'),
        ('fuel', 'Fuel/Transportation'),
        ('marketing', 'Marketing'),
        ('insurance', 'Insurance'),
        ('tax', 'Tax Payment'),
        ('loan', 'Loan Payment'),
        ('other', 'Other'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('card', 'Card Payment'),
        ('mpesa', 'M-Pesa'),
        ('credit', 'Credit/Account'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Basic expense information
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        ExpenseCategory, 
        on_delete=models.PROTECT,
        related_name='expenses'
    )
    vendor = models.ForeignKey(
        Vendor, 
        on_delete=models.SET_NULL,
        null=True, 
        blank=True,
        related_name='expenses'
    )
    
    # Financial details
    amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    tax_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    total_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        help_text="Amount + Tax"
    )
    
    # Dates
    expense_date = models.DateField(default=timezone.now)
    due_date = models.DateField(null=True, blank=True)
    paid_date = models.DateField(null=True, blank=True)
    
    # Payment details
    payment_method = models.CharField(
        max_length=20, 
        choices=PAYMENT_METHOD_CHOICES,
        default='cash'
    )
    reference_number = models.CharField(max_length=100, blank=True)
    receipt_number = models.CharField(max_length=100, blank=True)
    
    # Status and approval
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES,
        default='pending'
    )
    expense_type = models.CharField(
        max_length=20, 
        choices=EXPENSE_TYPE_CHOICES,
        default='manual'
    )
    
    # Auto-linking fields
    is_recurring = models.BooleanField(default=False)
    recurring_frequency = models.CharField(
        max_length=20,
        choices=[
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
            ('quarterly', 'Quarterly'),
            ('yearly', 'Yearly'),
        ],
        blank=True
    )
    
    # Link to other apps
    linked_inventory_item_id = models.UUIDField(null=True, blank=True)
    linked_employee_id = models.UUIDField(null=True, blank=True)
    linked_service_id = models.UUIDField(null=True, blank=True)
    linked_service_order_item_id = models.UUIDField(null=True, blank=True)
    linked_supplier_id = models.UUIDField(null=True, blank=True)
    
    # Additional metadata
    notes = models.TextField(blank=True)
    attachments = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    
    # Approval workflow
    approved_by_user_id = models.IntegerField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    def save(self, *args, **kwargs):
        # Calculate total amount
        self.total_amount = self.amount + self.tax_amount
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.title} - ${self.total_amount}"
    
    @property
    def is_overdue(self):
        """Check if expense is overdue"""
        if self.due_date and self.status not in ['paid', 'cancelled']:
            return timezone.now().date() > self.due_date
        return False
    
    @property
    def creator_name(self):
        """Get the name of the user who created this expense"""
        if self.created_by_user_id:
            try:
                from django.contrib.auth.models import User
                creator_user = User.objects.get(id=self.created_by_user_id)
                try:
                    from apps.employees.models import Employee
                    creator_employee = Employee.objects.get(user_id=creator_user.id)
                    return creator_employee.full_name
                except Employee.DoesNotExist:
                    return creator_user.get_full_name() or creator_user.username
            except User.DoesNotExist:
                return "Unknown User"
        return "System"
    
    @property
    def linked_object_name(self):
        """Get name of linked object"""
        if self.expense_type == 'inventory' and self.linked_inventory_item_id:
            try:
                from apps.inventory.models import InventoryItem
                item = InventoryItem.objects.get(id=self.linked_inventory_item_id)
                return f"Inventory: {item.name}"
            except:
                return "Linked Inventory Item"
        elif self.expense_type == 'salary' and self.linked_employee_id:
            try:
                from apps.employees.models import Employee
                employee = Employee.objects.get(id=self.linked_employee_id)
                return f"Employee: {employee.full_name}"
            except:
                return "Linked Employee"
        elif self.expense_type == 'commission' and self.linked_service_order_item_id:
            try:
                from apps.services.models import ServiceOrderItem
                service_item = ServiceOrderItem.objects.get(id=self.linked_service_order_item_id)
                return f"Commission: {service_item.service.name} - Order #{service_item.order.order_number}"
            except:
                return "Linked Service Commission"
        elif self.expense_type == 'commission' and self.linked_service_id:
            try:
                from apps.services.models import Service
                service = Service.objects.get(id=self.linked_service_id)
                return f"Service: {service.name}"
            except:
                return "Linked Service"
        return ""
    
    class Meta:
        ordering = ['-expense_date', '-created_at']
        indexes = [
            models.Index(fields=['expense_date']),
            models.Index(fields=['status']),
            models.Index(fields=['expense_type']),
            models.Index(fields=['category']),
        ]


class ExpenseApproval(TenantTimeStampedModel):
    """Expense approval workflow"""
    expense = models.ForeignKey(
        Expense, 
        on_delete=models.CASCADE,
        related_name='approvals'
    )
    approver_user_id = models.IntegerField()
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ],
        default='pending'
    )
    comments = models.TextField(blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.expense.title} - {self.status}"
    
    class Meta:
        ordering = ['-created_at']


class RecurringExpense(TenantTimeStampedModel):
    """Template for recurring expenses"""
    title = models.CharField(max_length=200)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT)
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    frequency = models.CharField(
        max_length=20,
        choices=[
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
            ('quarterly', 'Quarterly'),
            ('yearly', 'Yearly'),
        ]
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    next_due_date = models.DateField()
    is_active = models.BooleanField(default=True)
    auto_approve = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.title} ({self.frequency})"
    
    def generate_next_expense(self):
        """Generate the next expense from this recurring template"""
        if not self.is_active:
            return None
            
        expense = Expense.objects.create(
            title=self.title,
            category=self.category,
            vendor=self.vendor,
            amount=self.amount,
            expense_date=self.next_due_date,
            expense_type='other',
            status='approved' if self.auto_approve else 'pending',
            is_recurring=True
        )
        
        # Update next due date
        from dateutil.relativedelta import relativedelta
        if self.frequency == 'daily':
            self.next_due_date += relativedelta(days=1)
        elif self.frequency == 'weekly':
            self.next_due_date += relativedelta(weeks=1)
        elif self.frequency == 'monthly':
            self.next_due_date += relativedelta(months=1)
        elif self.frequency == 'quarterly':
            self.next_due_date += relativedelta(months=3)
        elif self.frequency == 'yearly':
            self.next_due_date += relativedelta(years=1)
        
        self.save()
        return expense
    
    class Meta:
        ordering = ['next_due_date']


class ExpenseBudget(TenantTimeStampedModel):
    """Budget tracking for expense categories"""
    category = models.ForeignKey(
        ExpenseCategory, 
        on_delete=models.CASCADE,
        related_name='budgets'
    )
    year = models.IntegerField()
    month = models.IntegerField(null=True, blank=True)  # None for yearly budget
    
    budgeted_amount = models.DecimalField(max_digits=12, decimal_places=2)
    spent_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    def __str__(self):
        period = f"{self.year}" if not self.month else f"{self.month}/{self.year}"
        return f"{self.category.name} Budget - {period}"
    
    @property
    def remaining_amount(self):
        return self.budgeted_amount - self.spent_amount
    
    @property
    def utilization_percentage(self):
        if self.budgeted_amount == 0:
            return 0
        return (self.spent_amount / self.budgeted_amount) * 100
    
    @property
    def is_over_budget(self):
        return self.spent_amount > self.budgeted_amount
    
    class Meta:
        unique_together = ['category', 'year', 'month']
        ordering = ['-year', '-month']
