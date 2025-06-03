from django import forms
from django.core.exceptions import ValidationError
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Field, HTML, Div
from crispy_forms.bootstrap import FormActions
from phonenumber_field.formfields import PhoneNumberField
from .models import Service, ServiceCategory, ServicePackage, ServiceOrder, ServiceOrderItem

class ServiceCategoryForm(forms.ModelForm):
    """Service category form"""
    
    class Meta:
        model = ServiceCategory
        fields = ['name', 'description', 'icon', 'color', 'display_order', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'color': forms.TextInput(attrs={'type': 'color'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'name',
            'description',
            Row(
                Column('icon', css_class='form-group col-md-4'),
                Column('color', css_class='form-group col-md-4'),
                Column('display_order', css_class='form-group col-md-4'),
            ),
            'is_active',
            FormActions(
                Submit('submit', 'Save Category', css_class='btn btn-primary')
            )
        )

class ServiceForm(forms.ModelForm):
    """Service form"""
    
    class Meta:
        model = Service
        fields = [
            'name', 'description', 'category', 'base_price', 'min_price', 'max_price',
            'estimated_duration', 'min_duration', 'max_duration', 'requires_booking',
            'is_popular', 'is_premium', 'required_skill_level', 'compatible_vehicle_types',
            'image', 'display_order', 'is_active'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'base_price': forms.NumberInput(attrs={'step': '0.01'}),
            'min_price': forms.NumberInput(attrs={'step': '0.01'}),
            'max_price': forms.NumberInput(attrs={'step': '0.01'}),
            'compatible_vehicle_types': forms.TextInput(attrs={
                'placeholder': 'sedan,suv,hatchback,pickup,van',
                'help_text': 'Comma-separated vehicle types'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h5>Basic Information</h5>'),
            Row(
                Column('name', css_class='form-group col-md-8'),
                Column('category', css_class='form-group col-md-4'),
            ),
            'description',
            'image',
            
            HTML('<h5 class="mt-4">Pricing</h5>'),
            Row(
                Column('base_price', css_class='form-group col-md-4'),
                Column('min_price', css_class='form-group col-md-4'),
                Column('max_price', css_class='form-group col-md-4'),
            ),
            
            HTML('<h5 class="mt-4">Duration</h5>'),
            Row(
                Column('estimated_duration', css_class='form-group col-md-4'),
                Column('min_duration', css_class='form-group col-md-4'),
                Column('max_duration', css_class='form-group col-md-4'),
            ),
            
            HTML('<h5 class="mt-4">Requirements & Compatibility</h5>'),
            Row(
                Column('required_skill_level', css_class='form-group col-md-6'),
                Column('compatible_vehicle_types', css_class='form-group col-md-6'),
            ),
            
            HTML('<h5 class="mt-4">Settings</h5>'),
            Row(
                Column('requires_booking', css_class='form-group col-md-3'),
                Column('is_popular', css_class='form-group col-md-3'),
                Column('is_premium', css_class='form-group col-md-3'),
                Column('is_active', css_class='form-group col-md-3'),
            ),
            'display_order',
            
            FormActions(
                Submit('submit', 'Save Service', css_class='btn btn-primary')
            )
        )
    
    def clean(self):
        cleaned_data = super().clean()
        base_price = cleaned_data.get('base_price')
        min_price = cleaned_data.get('min_price')
        max_price = cleaned_data.get('max_price')
        
        if min_price and max_price and min_price > max_price:
            raise ValidationError("Minimum price cannot be greater than maximum price.")
        
        if min_price and base_price and min_price > base_price:
            raise ValidationError("Minimum price cannot be greater than base price.")
        
        if max_price and base_price and max_price < base_price:
            raise ValidationError("Maximum price cannot be less than base price.")
        
        # Duration validation
        estimated_duration = cleaned_data.get('estimated_duration')
        min_duration = cleaned_data.get('min_duration')
        max_duration = cleaned_data.get('max_duration')
        
        if min_duration and max_duration and min_duration > max_duration:
            raise ValidationError("Minimum duration cannot be greater than maximum duration.")
        
        return cleaned_data

class ServicePackageForm(forms.ModelForm):
    """Service package form"""
    
    class Meta:
        model = ServicePackage
        fields = [
            'name', 'description', 'total_price', 'discount_percentage',
            'estimated_duration', 'is_popular', 'valid_from', 'valid_until',
            'image', 'is_active'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'total_price': forms.NumberInput(attrs={'step': '0.01'}),
            'discount_percentage': forms.NumberInput(attrs={'step': '0.01', 'max': '100'}),
            'valid_from': forms.DateInput(attrs={'type': 'date'}),
            'valid_until': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h5>Package Information</h5>'),
            'name',
            'description',
            'image',
            
            HTML('<h5 class="mt-4">Pricing</h5>'),
            Row(
                Column('total_price', css_class='form-group col-md-6'),
                Column('discount_percentage', css_class='form-group col-md-6'),
            ),
            'estimated_duration',
            
            HTML('<h5 class="mt-4">Validity</h5>'),
            Row(
                Column('valid_from', css_class='form-group col-md-6'),
                Column('valid_until', css_class='form-group col-md-6'),
            ),
            
            HTML('<h5 class="mt-4">Settings</h5>'),
            Row(
                Column('is_popular', css_class='form-group col-md-6'),
                Column('is_active', css_class='form-group col-md-6'),
            ),
            
            FormActions(
                Submit('submit', 'Save Package', css_class='btn btn-primary')
            )
        )

class ServiceOrderForm(forms.ModelForm):
    """Service order form"""
    
    class Meta:
        model = ServiceOrder
        fields = [
            'customer', 'vehicle', 'package', 'assigned_attendant',
            'scheduled_date', 'scheduled_time', 'priority', 'special_instructions'
        ]
        widgets = {
            'scheduled_date': forms.DateInput(attrs={'type': 'date'}),
            'scheduled_time': forms.TimeInput(attrs={'type': 'time'}),
            'special_instructions': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter attendants to only show active ones
        from apps.employees.models import Employee
        self.fields['assigned_attendant'].queryset = Employee.objects.filter(
            role__in=['attendant', 'supervisor', 'manager'],
            is_active=True
        )
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h5>Customer & Vehicle</h5>'),
            Row(
                Column('customer', css_class='form-group col-md-6'),
                Column('vehicle', css_class='form-group col-md-6'),
            ),
            
            HTML('<h5 class="mt-4">Service Details</h5>'),
            'package',
            HTML('<div id="services-selection" style="margin: 20px 0;"></div>'),
            
            HTML('<h5 class="mt-4">Assignment & Scheduling</h5>'),
            Row(
                Column('assigned_attendant', css_class='form-group col-md-4'),
                Column('scheduled_date', css_class='form-group col-md-4'),
                Column('scheduled_time', css_class='form-group col-md-4'),
            ),
            'priority',
            'special_instructions',
            
            FormActions(
                Submit('submit', 'Create Order', css_class='btn btn-primary')
            )
        )

class QuickOrderForm(forms.Form):
    """Quick order form for walk-in customers"""
    # Customer information
    customer_name = forms.CharField(max_length=100, label="Customer Name")
    customer_phone = PhoneNumberField(label="Phone Number")
    
    # Vehicle information
    vehicle_registration = forms.CharField(
        max_length=20, 
        label="Registration Number",
        widget=forms.TextInput(attrs={'style': 'text-transform: uppercase;'})
    )
    vehicle_make = forms.CharField(max_length=50, label="Make")
    vehicle_model = forms.CharField(max_length=50, label="Model")
    vehicle_color = forms.CharField(max_length=30, label="Color")
    vehicle_type = forms.ChoiceField(
        choices=[
            ('sedan', 'Sedan'),
            ('suv', 'SUV'),
            ('hatchback', 'Hatchback'),
            ('pickup', 'Pickup'),
            ('van', 'Van'),
        ],
        initial='sedan',
        label="Vehicle Type"
    )
    vehicle_year = forms.IntegerField(
        min_value=1990,
        max_value=2030,
        initial=2020,
        label="Year"
    )
    
    # Services
    selected_services = forms.ModelMultipleChoiceField(
        queryset=Service.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        label="Select Services"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Group services by category for better display
        self.fields['selected_services'].queryset = Service.objects.filter(
            is_active=True
        ).select_related('category').order_by('category__name', 'name')
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h5>Customer Information</h5>'),
            Row(
                Column('customer_name', css_class='form-group col-md-6'),
                Column('customer_phone', css_class='form-group col-md-6'),
            ),
            
            HTML('<h5 class="mt-4">Vehicle Information</h5>'),
            Row(
                Column('vehicle_registration', css_class='form-group col-md-4'),
                Column('vehicle_make', css_class='form-group col-md-4'),
                Column('vehicle_model', css_class='form-group col-md-4'),
            ),
            Row(
                Column('vehicle_color', css_class='form-group col-md-4'),
                Column('vehicle_type', css_class='form-group col-md-4'),
                Column('vehicle_year', css_class='form-group col-md-4'),
            ),
            
            HTML('<h5 class="mt-4">Select Services</h5>'),
            'selected_services',
            
            HTML('<div id="order-summary" class="mt-4"></div>'),
            
            FormActions(
                Submit('submit', 'Create Order', css_class='btn btn-success btn-lg')
            )
        )

class ServiceOrderItemForm(forms.ModelForm):
    """Service order item form"""
    
    class Meta:
        model = ServiceOrderItem
        fields = ['service', 'quantity', 'unit_price', 'assigned_to']
        widgets = {
            'unit_price': forms.NumberInput(attrs={'step': '0.01'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter services to active ones
        self.fields['service'].queryset = Service.objects.filter(is_active=True)
        
        # Filter assignees to attendants
        from apps.employees.models import Employee
        self.fields['assigned_to'].queryset = Employee.objects.filter(
            role__in=['attendant', 'supervisor'],
            is_active=True
        )

class ServiceRatingForm(forms.Form):
    """Service rating form for customers"""
    overall_rating = forms.ChoiceField(
        choices=[(i, i) for i in range(1, 6)],
        widget=forms.RadioSelect(attrs={'class': 'star-rating'}),
        label="Overall Rating"
    )
    service_quality = forms.ChoiceField(
        choices=[(i, i) for i in range(1, 6)],
        widget=forms.RadioSelect(attrs={'class': 'star-rating'}),
        label="Service Quality",
        required=False
    )
    staff_friendliness = forms.ChoiceField(
        choices=[(i, i) for i in range(1, 6)],
        widget=forms.RadioSelect(attrs={'class': 'star-rating'}),
        label="Staff Friendliness",
        required=False
    )
    timeliness = forms.ChoiceField(
        choices=[(i, i) for i in range(1, 6)],
        widget=forms.RadioSelect(attrs={'class': 'star-rating'}),
        label="Timeliness",
        required=False
    )
    value_for_money = forms.ChoiceField(
        choices=[(i, i) for i in range(1, 6)],
        widget=forms.RadioSelect(attrs={'class': 'star-rating'}),
        label="Value for Money",
        required=False
    )
    comments = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4}),
        required=False,
        label="Comments"
    )
    would_recommend = forms.BooleanField(
        required=False,
        label="Would you recommend us to others?"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h6>Please rate your experience</h6>'),
            'overall_rating',
            Row(
                Column('service_quality', css_class='form-group col-md-6'),
                Column('staff_friendliness', css_class='form-group col-md-6'),
            ),
            Row(
                Column('timeliness', css_class='form-group col-md-6'),
                Column('value_for_money', css_class='form-group col-md-6'),
            ),
            'comments',
            'would_recommend',
            FormActions(
                Submit('submit', 'Submit Rating', css_class='btn btn-primary')
            )
        )

class ServiceSearchForm(forms.Form):
    """Service search form"""
    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Search services...',
            'class': 'form-control'
        })
    )
    category = forms.ModelChoiceField(
        queryset=ServiceCategory.objects.filter(is_active=True),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    price_range = forms.ChoiceField(
        choices=[
            ('', 'Any Price'),
            ('0-500', 'Under KES 500'),
            ('500-1000', 'KES 500 - 1000'),
            ('1000-2000', 'KES 1000 - 2000'),
            ('2000+', 'Over KES 2000'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    duration_range = forms.ChoiceField(
        choices=[
            ('', 'Any Duration'),
            ('0-30', 'Under 30 minutes'),
            ('30-60', '30 - 60 minutes'),
            ('60-120', '1 - 2 hours'),
            ('120+', 'Over 2 hours'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    popular_only = forms.BooleanField(
        required=False,
        label="Popular services only",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )