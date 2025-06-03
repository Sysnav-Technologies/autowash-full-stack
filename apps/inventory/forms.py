from django import forms
from django.core.exceptions import ValidationError
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Field, HTML, Div
from crispy_forms.bootstrap import FormActions
from django.db.models import Q
from .models import (
    InventoryItem, InventoryCategory, Unit, StockAdjustment, 
    StockTake, ItemLocation
)

class InventoryCategoryForm(forms.ModelForm):
    """Inventory category form"""
    
    class Meta:
        model = InventoryCategory
        fields = ['name', 'description', 'parent', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Prevent circular parent relationships
        if self.instance and self.instance.pk:
            self.fields['parent'].queryset = InventoryCategory.objects.exclude(
                Q(pk=self.instance.pk) | Q(parent=self.instance)
            )
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'name',
            'description',
            'parent',
            'is_active',
            FormActions(
                Submit('submit', 'Save Category', css_class='btn btn-primary')
            )
        )

class UnitForm(forms.ModelForm):
    """Unit of measurement form"""
    
    class Meta:
        model = Unit
        fields = ['name', 'abbreviation', 'description', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('name', css_class='form-group col-md-8'),
                Column('abbreviation', css_class='form-group col-md-4'),
            ),
            'description',
            'is_active',
            FormActions(
                Submit('submit', 'Save Unit', css_class='btn btn-primary')
            )
        )

class InventoryItemForm(forms.ModelForm):
    """Inventory item form"""
    
    class Meta:
        model = InventoryItem
        fields = [
            'name', 'description', 'category', 'item_type', 'sku', 'barcode',
            'unit', 'weight', 'dimensions', 'current_stock', 'minimum_stock_level',
            'maximum_stock_level', 'reorder_point', 'reorder_quantity',
            'unit_cost', 'selling_price', 'primary_supplier', 'storage_location',
            'storage_requirements', 'is_taxable', 'track_serial_numbers',
            'track_expiry', 'quality_check_required', 'shelf_life_days',
            'image', 'is_active'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'storage_requirements': forms.Textarea(attrs={'rows': 2}),
            'current_stock': forms.NumberInput(attrs={'step': '0.01'}),
            'minimum_stock_level': forms.NumberInput(attrs={'step': '0.01'}),
            'maximum_stock_level': forms.NumberInput(attrs={'step': '0.01'}),
            'reorder_point': forms.NumberInput(attrs={'step': '0.01'}),
            'reorder_quantity': forms.NumberInput(attrs={'step': '0.01'}),
            'unit_cost': forms.NumberInput(attrs={'step': '0.01'}),
            'selling_price': forms.NumberInput(attrs={'step': '0.01'}),
            'weight': forms.NumberInput(attrs={'step': '0.001'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter active categories and units
        self.fields['category'].queryset = InventoryCategory.objects.filter(is_active=True)
        self.fields['unit'].queryset = Unit.objects.filter(is_active=True)
        
        # Filter active suppliers
        try:
            from apps.suppliers.models import Supplier
            self.fields['primary_supplier'].queryset = Supplier.objects.filter(is_active=True)
        except ImportError:
            self.fields['primary_supplier'].widget = forms.HiddenInput()
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h5>Basic Information</h5>'),
            Row(
                Column('name', css_class='form-group col-md-8'),
                Column('category', css_class='form-group col-md-4'),
            ),
            'description',
            Row(
                Column('item_type', css_class='form-group col-md-4'),
                Column('sku', css_class='form-group col-md-4'),
                Column('barcode', css_class='form-group col-md-4'),
            ),
            'image',
            
            HTML('<h5 class="mt-4">Measurement & Physical Properties</h5>'),
            Row(
                Column('unit', css_class='form-group col-md-4'),
                Column('weight', css_class='form-group col-md-4'),
                Column('dimensions', css_class='form-group col-md-4'),
            ),
            
            HTML('<h5 class="mt-4">Stock Levels</h5>'),
            Row(
                Column('current_stock', css_class='form-group col-md-6'),
                Column('minimum_stock_level', css_class='form-group col-md-6'),
            ),
            Row(
                Column('maximum_stock_level', css_class='form-group col-md-6'),
                Column('reorder_point', css_class='form-group col-md-6'),
            ),
            'reorder_quantity',
            
            HTML('<h5 class="mt-4">Pricing</h5>'),
            Row(
                Column('unit_cost', css_class='form-group col-md-6'),
                Column('selling_price', css_class='form-group col-md-6'),
            ),
            
            HTML('<h5 class="mt-4">Supplier & Storage</h5>'),
            Row(
                Column('primary_supplier', css_class='form-group col-md-6'),
                Column('storage_location', css_class='form-group col-md-6'),
            ),
            'storage_requirements',
            
            HTML('<h5 class="mt-4">Settings & Tracking</h5>'),
            Row(
                Column('is_taxable', css_class='form-group col-md-3'),
                Column('track_serial_numbers', css_class='form-group col-md-3'),
                Column('track_expiry', css_class='form-group col-md-3'),
                Column('quality_check_required', css_class='form-group col-md-3'),
            ),
            Row(
                Column('shelf_life_days', css_class='form-group col-md-6'),
                Column('is_active', css_class='form-group col-md-6'),
            ),
            
            FormActions(
                Submit('submit', 'Save Item', css_class='btn btn-primary')
            )
        )
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Validate stock levels
        current_stock = cleaned_data.get('current_stock', 0)
        min_stock = cleaned_data.get('minimum_stock_level', 0)
        max_stock = cleaned_data.get('maximum_stock_level', 0)
        reorder_point = cleaned_data.get('reorder_point', 0)
        
        if min_stock > max_stock:
            raise ValidationError("Maximum stock level must be greater than minimum stock level.")
        
        if reorder_point > max_stock:
            raise ValidationError("Reorder point cannot be greater than maximum stock level.")
        
        # Validate pricing
        unit_cost = cleaned_data.get('unit_cost', 0)
        selling_price = cleaned_data.get('selling_price', 0)
        
        if selling_price > 0 and unit_cost > 0 and selling_price < unit_cost:
            self.add_error('selling_price', 'Selling price should not be less than unit cost.')
        
        # Validate expiry tracking
        track_expiry = cleaned_data.get('track_expiry', False)
        shelf_life_days = cleaned_data.get('shelf_life_days')
        
        if track_expiry and not shelf_life_days:
            raise ValidationError("Shelf life days is required when tracking expiry.")
        
        return cleaned_data

class StockAdjustmentForm(forms.ModelForm):
    """Stock adjustment form"""
    
    class Meta:
        model = StockAdjustment
        fields = ['item', 'adjustment_type', 'quantity', 'reason', 'unit_cost']
        widgets = {
            'quantity': forms.NumberInput(attrs={'step': '0.01'}),
            'unit_cost': forms.NumberInput(attrs={'step': '0.01'}),
            'reason': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        initial_item = kwargs.pop('initial_item', None)
        super().__init__(*args, **kwargs)
        
        # Filter to active items
        self.fields['item'].queryset = InventoryItem.objects.filter(is_active=True)
        
        # Set initial item if provided
        if initial_item:
            self.fields['item'].initial = initial_item
            self.fields['unit_cost'].initial = initial_item.unit_cost
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('item', css_class='form-group col-md-6'),
                Column('adjustment_type', css_class='form-group col-md-6'),
            ),
            Row(
                Column('quantity', css_class='form-group col-md-6'),
                Column('unit_cost', css_class='form-group col-md-6'),
            ),
            'reason',
            HTML('<div class="alert alert-info"><i class="fas fa-info-circle"></i> Positive quantity increases stock, negative quantity decreases stock.</div>'),
            FormActions(
                Submit('submit', 'Create Adjustment', css_class='btn btn-primary')
            )
        )
    
    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        if quantity == 0:
            raise ValidationError("Quantity cannot be zero.")
        return quantity

class StockTakeForm(forms.ModelForm):
    """Stock take form"""
    
    class Meta:
        model = StockTake
        fields = [
            'name', 'description', 'scheduled_date', 'include_all_items',
            'categories', 'items', 'counters'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'scheduled_date': forms.DateInput(attrs={'type': 'date'}),
            'categories': forms.CheckboxSelectMultiple(),
            'items': forms.CheckboxSelectMultiple(),
            'counters': forms.CheckboxSelectMultiple(),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter active items and categories
        self.fields['categories'].queryset = InventoryCategory.objects.filter(is_active=True)
        self.fields['items'].queryset = InventoryItem.objects.filter(is_active=True)
        
        # Filter active employees for counters
        try:
            from apps.employees.models import Employee
            self.fields['counters'].queryset = Employee.objects.filter(
                is_active=True,
                role__in=['attendant', 'supervisor', 'manager']
            )
        except ImportError:
            self.fields['counters'].widget = forms.HiddenInput()
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h5>Stock Take Information</h5>'),
            Row(
                Column('name', css_class='form-group col-md-8'),
                Column('scheduled_date', css_class='form-group col-md-4'),
            ),
            'description',
            
            HTML('<h5 class="mt-4">Scope</h5>'),
            'include_all_items',
            HTML('<div id="scope-selection" style="display: none;">'),
            'categories',
            'items',
            HTML('</div>'),
            
            HTML('<h5 class="mt-4">Staff Assignment</h5>'),
            'counters',
            
            FormActions(
                Submit('submit', 'Create Stock Take', css_class='btn btn-primary')
            )
        )
    
    def clean(self):
        cleaned_data = super().clean()
        include_all_items = cleaned_data.get('include_all_items')
        categories = cleaned_data.get('categories')
        items = cleaned_data.get('items')
        
        if not include_all_items and not categories and not items:
            raise ValidationError("Please select categories or items, or choose to include all items.")
        
        return cleaned_data

class ItemSearchForm(forms.Form):
    """Item search and filter form"""
    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Search by name, SKU, or barcode...',
            'class': 'form-control'
        })
    )
    category = forms.ModelChoiceField(
        queryset=InventoryCategory.objects.filter(is_active=True),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    stock_status = forms.ChoiceField(
        choices=[
            ('', 'All Stock Levels'),
            ('normal', 'Normal Stock'),
            ('low_stock', 'Low Stock'),
            ('out_of_stock', 'Out of Stock'),
            ('overstock', 'Overstock'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    item_type = forms.ChoiceField(
        choices=[('', 'All Types')] + InventoryItem.ITEM_TYPES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

class ItemLocationForm(forms.ModelForm):
    """Item location form"""
    
    class Meta:
        model = ItemLocation
        fields = [
            'item', 'warehouse', 'zone', 'aisle', 'shelf', 'bin',
            'quantity', 'is_primary', 'is_picking_location'
        ]
        widgets = {
            'quantity': forms.NumberInput(attrs={'step': '0.01'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter to active items
        self.fields['item'].queryset = InventoryItem.objects.filter(is_active=True)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'item',
            Row(
                Column('warehouse', css_class='form-group col-md-4'),
                Column('zone', css_class='form-group col-md-4'),
                Column('quantity', css_class='form-group col-md-4'),
            ),
            Row(
                Column('aisle', css_class='form-group col-md-4'),
                Column('shelf', css_class='form-group col-md-4'),
                Column('bin', css_class='form-group col-md-4'),
            ),
            Row(
                Column('is_primary', css_class='form-group col-md-6'),
                Column('is_picking_location', css_class='form-group col-md-6'),
            ),
            FormActions(
                Submit('submit', 'Save Location', css_class='btn btn-primary')
            )
        )

class QuickStockAdjustmentForm(forms.Form):
    """Quick stock adjustment form for mobile/tablet use"""
    item = forms.ModelChoiceField(
        queryset=InventoryItem.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    adjustment_type = forms.ChoiceField(
        choices=StockAdjustment.ADJUSTMENT_TYPES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    quantity = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'})
    )
    reason = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Reason for adjustment'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'item',
            Row(
                Column('adjustment_type', css_class='form-group col-md-6'),
                Column('quantity', css_class='form-group col-md-6'),
            ),
            'reason',
            FormActions(
                Submit('submit', 'Adjust Stock', css_class='btn btn-primary btn-lg w-100')
            )
        )

class BulkItemUpdateForm(forms.Form):
    """Bulk update form for multiple items"""
    items = forms.ModelMultipleChoiceField(
        queryset=InventoryItem.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple
    )
    
    # Fields to update
    update_category = forms.BooleanField(required=False, label="Update Category")
    new_category = forms.ModelChoiceField(
        queryset=InventoryCategory.objects.filter(is_active=True),
        required=False
    )
    
    update_supplier = forms.BooleanField(required=False, label="Update Primary Supplier")
    new_supplier = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=False
    )
    
    update_storage_location = forms.BooleanField(required=False, label="Update Storage Location")
    new_storage_location = forms.CharField(max_length=100, required=False)
    
    update_minimum_stock = forms.BooleanField(required=False, label="Update Minimum Stock Level")
    new_minimum_stock = forms.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False,
        widget=forms.NumberInput(attrs={'step': '0.01'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set supplier queryset
        try:
            from apps.suppliers.models import Supplier
            self.fields['new_supplier'].queryset = Supplier.objects.filter(is_active=True)
        except ImportError:
            del self.fields['update_supplier']
            del self.fields['new_supplier']
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h6>Select Items to Update</h6>'),
            'items',
            
            HTML('<h6 class="mt-4">Updates to Apply</h6>'),
            Row(
                Column('update_category', css_class='form-group col-md-6'),
                Column('new_category', css_class='form-group col-md-6'),
            ),
            Row(
                Column('update_supplier', css_class='form-group col-md-6'),
                Column('new_supplier', css_class='form-group col-md-6'),
            ),
            Row(
                Column('update_storage_location', css_class='form-group col-md-6'),
                Column('new_storage_location', css_class='form-group col-md-6'),
            ),
            Row(
                Column('update_minimum_stock', css_class='form-group col-md-6'),
                Column('new_minimum_stock', css_class='form-group col-md-6'),
            ),
            
            FormActions(
                Submit('submit', 'Update Selected Items', css_class='btn btn-warning')
            )
        )
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Check that at least one update is selected
        update_fields = [
            'update_category', 'update_supplier', 
            'update_storage_location', 'update_minimum_stock'
        ]
        
        if not any(cleaned_data.get(field, False) for field in update_fields):
            raise ValidationError("Please select at least one field to update.")
        
        # Validate that corresponding new values are provided
        validations = [
            ('update_category', 'new_category'),
            ('update_supplier', 'new_supplier'),
            ('update_storage_location', 'new_storage_location'),
            ('update_minimum_stock', 'new_minimum_stock'),
        ]
        
        for update_field, value_field in validations:
            if cleaned_data.get(update_field) and not cleaned_data.get(value_field):
                raise ValidationError(f"Please provide a value for {value_field.replace('_', ' ')}")
        
        return cleaned_data