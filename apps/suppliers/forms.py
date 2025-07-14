from django import forms
from django.forms import inlineformset_factory
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, timedelta

from .models import (
    Supplier, SupplierCategory, PurchaseOrder, PurchaseOrderItem,
    GoodsReceipt, GoodsReceiptItem, SupplierEvaluation, SupplierPayment,
    SupplierDocument, SupplierContact, Invoice, InvoiceItem
)

class SupplierForm(forms.ModelForm):
    """Form for creating and editing suppliers"""
    
    class Meta:
        model = Supplier
        fields = [
            'name', 'supplier_code', 'category', 'supplier_type', 'business_name',
            'registration_number', 'tax_number', 'vat_number',
            'email', 'phone',  
            'primary_contact_name', 'primary_contact_title',
            'secondary_contact_name', 'secondary_contact_phone', 'secondary_contact_email',
            'city', 'state', 'postal_code', 'country', 
            'payment_terms', 'credit_limit', 'currency',
            'bank_name', 'bank_branch', 'account_number', 'account_name', 'swift_code',
            'lead_time_days', 'minimum_order_value', 'delivery_terms',
            'status', 'is_preferred', 'is_verified',
            'certifications', 'notes', 'terms_and_conditions'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Supplier name'}),
            'supplier_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Unique supplier code'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'supplier_type': forms.Select(attrs={'class': 'form-select'}),
            'business_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Legal business name'}),
            'registration_number': forms.TextInput(attrs={'class': 'form-control'}),
            'tax_number': forms.TextInput(attrs={'class': 'form-control'}),
            'vat_number': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'website': forms.URLInput(attrs={'class': 'form-control'}),
            'primary_contact_name': forms.TextInput(attrs={'class': 'form-control'}),
            'primary_contact_title': forms.TextInput(attrs={'class': 'form-control'}),
            'secondary_contact_name': forms.TextInput(attrs={'class': 'form-control'}),
            'secondary_contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'secondary_contact_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control', 'value': 'Kenya'}),
            'payment_terms': forms.Select(attrs={'class': 'form-select'}),
            'credit_limit': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'currency': forms.TextInput(attrs={'class': 'form-control', 'value': 'KES'}),
            'bank_name': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_branch': forms.TextInput(attrs={'class': 'form-control'}),
            'account_number': forms.TextInput(attrs={'class': 'form-control'}),
            'account_name': forms.TextInput(attrs={'class': 'form-control'}),
            'swift_code': forms.TextInput(attrs={'class': 'form-control'}),
            'lead_time_days': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'minimum_order_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'delivery_terms': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., FOB, CIF'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'is_preferred': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_verified': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'certifications': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'terms_and_conditions': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Generate supplier code if not provided
        if not self.instance.pk and not self.initial.get('supplier_code'):
            self.fields['supplier_code'].initial = self.generate_supplier_code()
        
        # Set categories queryset - SupplierCategory has is_active field
        self.fields['category'].queryset = SupplierCategory.objects.filter(is_active=True)
        self.fields['category'].empty_label = "Select Category"
    
    def generate_supplier_code(self):
        """Generate unique supplier code"""
        import string
        import random
        
        # Generate a random 6-character code
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        # Ensure uniqueness
        while Supplier.objects.filter(supplier_code=code).exists():
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        return code
    
    def clean_supplier_code(self):
        supplier_code = self.cleaned_data['supplier_code']
        
        # Check for uniqueness
        queryset = Supplier.objects.filter(supplier_code=supplier_code)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        
        if queryset.exists():
            raise ValidationError("Supplier code must be unique.")
        
        return supplier_code
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            # Check for uniqueness
            queryset = Supplier.objects.filter(email=email)
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            
            if queryset.exists():
                raise ValidationError("A supplier with this email already exists.")
        
        return email

class SupplierCategoryForm(forms.ModelForm):
    """Form for supplier categories"""
    
    class Meta:
        model = SupplierCategory
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class SupplierContactForm(forms.ModelForm):
    """Form for supplier contacts"""
    
    class Meta:
        model = SupplierContact
        fields = [
            'supplier', 'name', 'title', 'department', 'phone', 'email', 'mobile',
            'is_primary', 'notes'
        ]
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'mobile': forms.TextInput(attrs={'class': 'form-control'}),
            'is_primary': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class PurchaseOrderForm(forms.ModelForm):
    """Form for purchase orders"""
    
    class Meta:
        model = PurchaseOrder
        fields = [
            'supplier', 'priority', 'expected_delivery_date',
            'payment_terms', 'delivery_terms', 'special_instructions',
            'delivery_address', 'contact_person', 'contact_phone',
            'shipping_cost', 'tax_amount', 'discount_amount',
            'notes'
        ]
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'expected_delivery_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'payment_terms': forms.Select(attrs={'class': 'form-select'}),
            'delivery_terms': forms.TextInput(attrs={'class': 'form-control'}),
            'special_instructions': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'delivery_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'shipping_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'tax_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'discount_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter suppliers using is_deleted=False instead of is_active=True
        self.fields['supplier'].queryset = Supplier.objects.filter(
            is_deleted=False,  # Changed from is_active=True
            status='active'
        )
        
        # Set default expected delivery date (7 days from now)
        if not self.instance.pk:
            self.fields['expected_delivery_date'].initial = timezone.now().date() + timedelta(days=7)
    
    def clean_expected_delivery_date(self):
        delivery_date = self.cleaned_data['expected_delivery_date']
        
        if delivery_date and delivery_date < timezone.now().date():
            raise ValidationError("Expected delivery date cannot be in the past.")
        
        return delivery_date

class PurchaseOrderItemForm(forms.ModelForm):
    """Form for purchase order items"""
    
    class Meta:
        model = PurchaseOrderItem
        fields = ['item', 'quantity', 'unit_price', 'notes']
        widgets = {
            'item': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'notes': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter active inventory items
        try:
            from apps.inventory.models import InventoryItem
            self.fields['item'].queryset = InventoryItem.objects.filter(is_deleted=False)  # Changed from is_active=True
        except ImportError:
            pass

# Formset for purchase order items
PurchaseOrderItemFormSet = inlineformset_factory(
    PurchaseOrder,
    PurchaseOrderItem,
    form=PurchaseOrderItemForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True
)

class GoodsReceiptForm(forms.ModelForm):
    """Form for goods receipts"""
    
    class Meta:
        model = GoodsReceipt
        fields = [
            'purchase_order', 'supplier', 'receipt_date', 'delivery_note_number',
            'vehicle_number', 'driver_name', 'quality_check_passed', 'quality_notes',
            'notes'
        ]
        widgets = {
            'purchase_order': forms.Select(attrs={'class': 'form-select'}),
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'receipt_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'delivery_note_number': forms.TextInput(attrs={'class': 'form-control'}),
            'vehicle_number': forms.TextInput(attrs={'class': 'form-control'}),
            'driver_name': forms.TextInput(attrs={'class': 'form-control'}),
            'quality_check_passed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'quality_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter purchase orders that can receive goods
        self.fields['purchase_order'].queryset = PurchaseOrder.objects.filter(
            status__in=['approved', 'sent', 'acknowledged', 'partially_received']
        )
        
        # Filter suppliers using is_deleted=False instead of is_active=True
        self.fields['supplier'].queryset = Supplier.objects.filter(
            is_deleted=False,  # Changed from is_active=True
            status='active'
        )

class GoodsReceiptItemForm(forms.ModelForm):
    """Form for goods receipt items"""
    
    class Meta:
        model = GoodsReceiptItem
        fields = [
            'purchase_order_item', 'expected_quantity', 'received_quantity',
            'damaged_quantity', 'quality_passed', 'quality_notes',
            'lot_number', 'expiry_date', 'manufacture_date', 'notes'
        ]
        widgets = {
            'purchase_order_item': forms.Select(attrs={'class': 'form-select'}),
            'expected_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'readonly': True}),
            'received_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'damaged_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'value': '0'}),
            'quality_passed': forms.CheckboxInput(attrs={'class': 'form-check-input', 'checked': True}),
            'quality_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'lot_number': forms.TextInput(attrs={'class': 'form-control'}),
            'expiry_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'manufacture_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.TextInput(attrs={'class': 'form-control'}),
        }

# Formset for goods receipt items
GoodsReceiptItemFormSet = inlineformset_factory(
    GoodsReceipt,
    GoodsReceiptItem,
    form=GoodsReceiptItemForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True
)

class SupplierEvaluationForm(forms.ModelForm):
    """Form for supplier evaluations"""
    
    class Meta:
        model = SupplierEvaluation
        fields = [
            'supplier', 'purchase_order', 'evaluation_period', 'period_start', 'period_end',
            'quality_rating', 'delivery_rating', 'service_rating', 'price_rating', 'communication_rating',
            'quality_comments', 'delivery_comments', 'service_comments', 'general_comments',
            'recommendations', 'continue_partnership'
        ]
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'purchase_order': forms.Select(attrs={'class': 'form-select'}),
            'evaluation_period': forms.Select(attrs={'class': 'form-select'}),
            'period_start': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'period_end': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'quality_rating': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '5', 'step': '0.1'}),
            'delivery_rating': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '5', 'step': '0.1'}),
            'service_rating': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '5', 'step': '0.1'}),
            'price_rating': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '5', 'step': '0.1'}),
            'communication_rating': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '5', 'step': '0.1'}),
            'quality_comments': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'delivery_comments': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'service_comments': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'general_comments': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'recommendations': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'continue_partnership': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter suppliers using is_deleted=False instead of is_active=True
        self.fields['supplier'].queryset = Supplier.objects.filter(is_deleted=False)  # Changed from is_active=True
        
        # Filter completed purchase orders
        self.fields['purchase_order'].queryset = PurchaseOrder.objects.filter(
            status='completed'
        )
        self.fields['purchase_order'].required = False

class SupplierPaymentForm(forms.ModelForm):
    """Form for supplier payments"""
    
    class Meta:
        model = SupplierPayment
        fields = [
            'supplier', 'purchase_orders', 'amount', 'payment_method', 'payment_date',
            'reference_number', 'transaction_id', 'bank_name', 'account_number',
            'cheque_number', 'cheque_date', 'description', 'notes'
        ]
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'purchase_orders': forms.SelectMultiple(attrs={'class': 'form-select', 'size': '5'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'payment_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'reference_number': forms.TextInput(attrs={'class': 'form-control'}),
            'transaction_id': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_name': forms.TextInput(attrs={'class': 'form-control'}),
            'account_number': forms.TextInput(attrs={'class': 'form-control'}),
            'cheque_number': forms.TextInput(attrs={'class': 'form-control'}),
            'cheque_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter suppliers using is_deleted=False instead of is_active=True
        self.fields['supplier'].queryset = Supplier.objects.filter(is_deleted=False)  # Changed from is_active=True
        
        # Filter completed purchase orders
        self.fields['purchase_orders'].queryset = PurchaseOrder.objects.filter(
            status='completed'
        )
        
        # Set default payment date to today
        if not self.instance.pk:
            self.fields['payment_date'].initial = timezone.now().date()

class SupplierDocumentForm(forms.ModelForm):
    """Form for supplier documents"""
    
    class Meta:
        model = SupplierDocument
        fields = [
            'supplier', 'name', 'document_type', 'description', 'file',
            'issue_date', 'expiry_date'
        ]
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'document_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'issue_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter suppliers using is_deleted=False instead of is_active=True
        self.fields['supplier'].queryset = Supplier.objects.filter(is_deleted=False)  # Changed from is_active=True
    
    def clean_expiry_date(self):
        issue_date = self.cleaned_data.get('issue_date')
        expiry_date = self.cleaned_data.get('expiry_date')
        
        if issue_date and expiry_date and expiry_date <= issue_date:
            raise ValidationError("Expiry date must be after issue date.")
        
        return expiry_date

class SupplierFilterForm(forms.Form):
    """Form for filtering suppliers"""
    
    category = forms.ModelChoiceField(
        queryset=SupplierCategory.objects.filter(is_active=True),  # SupplierCategory has is_active field
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    supplier_type = forms.ChoiceField(
        choices=[('', 'All Types')] + Supplier.SUPPLIER_TYPES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    status = forms.ChoiceField(
        choices=[('', 'All Status')] + Supplier.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search suppliers...'
        })
    )
    
    sort = forms.ChoiceField(
        choices=[
            ('name', 'Name A-Z'),
            ('-name', 'Name Z-A'),
            ('rating', 'Rating Low-High'),
            ('-rating', 'Rating High-Low'),
            ('total_orders', 'Orders Low-High'),
            ('-total_orders', 'Orders High-Low'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

class PurchaseOrderFilterForm(forms.Form):
    """Form for filtering purchase orders"""
    
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.filter(is_deleted=False, status='active'),  # Changed from is_active=True
        required=False,
        empty_label="All Suppliers",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    status = forms.ChoiceField(
        choices=[('', 'All Status')] + PurchaseOrder.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    priority = forms.ChoiceField(
        choices=[('', 'All Priorities')] + PurchaseOrder.PRIORITY_LEVELS,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search orders...'
        })
    )

class GoodsReceiptFilterForm(forms.Form):
    """Form for filtering goods receipts"""
    
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.filter(is_deleted=False, status='active'),  # Changed from is_active=True
        required=False,
        empty_label="All Suppliers",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    status = forms.ChoiceField(
        choices=[('', 'All Status')] + GoodsReceipt.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search receipts...'
        })
    )

class QuickSupplierForm(forms.ModelForm):
    """Simplified form for quick supplier creation"""
    
    class Meta:
        model = Supplier
        fields = [
            'name', 'supplier_code', 'category', 'supplier_type',
            'email', 'phone', 'payment_terms', 'lead_time_days'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Supplier name'}),
            'supplier_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Unique code'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'supplier_type': forms.Select(attrs={'class': 'form-select'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'payment_terms': forms.Select(attrs={'class': 'form-select'}),
            'lead_time_days': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'value': '7'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Generate supplier code if not provided
        if not self.instance.pk and not self.initial.get('supplier_code'):
            self.fields['supplier_code'].initial = self.generate_supplier_code()
        
        # Set categories queryset - SupplierCategory has is_active field
        self.fields['category'].queryset = SupplierCategory.objects.filter(is_active=True)
        self.fields['category'].empty_label = "Select Category"
    
    def generate_supplier_code(self):
        """Generate unique supplier code"""
        import string
        import random
        
        # Generate a random 6-character code
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        # Ensure uniqueness
        while Supplier.objects.filter(supplier_code=code).exists():
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        return code

# Invoice Forms
class InvoiceForm(forms.ModelForm):
    """Form for creating and editing invoices"""
    
    class Meta:
        model = Invoice
        fields = [
            'supplier', 'purchase_order', 'supplier_invoice_number',
            'invoice_date', 'due_date', 'total_amount', 'currency',
            'subtotal', 'tax_amount', 'shipping_cost', 'discount_amount',
            'description', 'notes', 'invoice_file'
        ]
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'purchase_order': forms.Select(attrs={'class': 'form-select'}),
            'supplier_invoice_number': forms.TextInput(attrs={'class': 'form-control'}),
            'invoice_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'total_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'currency': forms.TextInput(attrs={'class': 'form-control', 'value': 'KES'}),
            'subtotal': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'tax_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'shipping_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'discount_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'invoice_file': forms.FileInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter suppliers using is_deleted=False instead of is_active=True
        self.fields['supplier'].queryset = Supplier.objects.filter(
            is_deleted=False,  # Changed from is_active=True
            status='active'
        )
        
        # Filter completed purchase orders
        self.fields['purchase_order'].queryset = PurchaseOrder.objects.filter(
            status='completed'
        )
        self.fields['purchase_order'].required = False
        
        # Set default dates
        if not self.instance.pk:
            self.fields['invoice_date'].initial = timezone.now().date()
            self.fields['due_date'].initial = timezone.now().date() + timedelta(days=30)
    
    def clean_due_date(self):
        invoice_date = self.cleaned_data.get('invoice_date')
        due_date = self.cleaned_data.get('due_date')
        
        if invoice_date and due_date and due_date < invoice_date:
            raise ValidationError("Due date cannot be before invoice date.")
        
        return due_date

class InvoiceItemForm(forms.ModelForm):
    """Form for invoice items"""
    
    class Meta:
        model = InvoiceItem
        fields = ['description', 'quantity', 'unit_price', 'item_code', 'notes']
        widgets = {
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'item_code': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.TextInput(attrs={'class': 'form-control'}),
        }

# Formset for invoice items
InvoiceItemFormSet = inlineformset_factory(
    Invoice,
    InvoiceItem,
    form=InvoiceItemForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True
)

class InvoiceFilterForm(forms.Form):
    """Form for filtering invoices"""
    
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.filter(is_deleted=False, status='active'),
        required=False,
        empty_label="All Suppliers",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    status = forms.ChoiceField(
        choices=[('', 'All Status')] + Invoice.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    payment_status = forms.ChoiceField(
        choices=[('', 'All Payment Status')] + Invoice.PAYMENT_STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search invoices...'
        })
    )