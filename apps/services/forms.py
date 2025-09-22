from django import forms
from django.db import models
from django.core.exceptions import ValidationError
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Field, HTML, Div
from crispy_forms.bootstrap import FormActions
from phonenumber_field.formfields import PhoneNumberField
from .models import Service, ServiceBay, ServiceCategory, ServicePackage, ServiceOrder, ServiceOrderItem

class ServiceCategoryForm(forms.ModelForm):
    """Service category form - simplified version"""
    
    class Meta:
        model = ServiceCategory
        fields = ['name', 'description', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Briefly describe what services this category includes...'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set default values for hidden fields
        if not self.instance.pk:  # New category
            # Auto-generate display_order based on existing categories
            from .models import ServiceCategory
            max_order = ServiceCategory.objects.aggregate(max_order=models.Max('display_order'))['max_order'] or 0
            self.instance.display_order = max_order + 1
            self.instance.icon = 'fas fa-car-wash'  # Default icon
            self.instance.color = '#3b82f6'  # Default blue color
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'name',
            'description',
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

class ServiceBayForm(forms.ModelForm):
    """Service bay form"""
    
    class Meta:
        model = ServiceBay
        fields = [
            'name', 'bay_number', 'description', 'max_vehicle_size',
            'has_pressure_washer', 'has_vacuum', 'has_lift', 'has_drainage',
            'is_active'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h5>Basic Information</h5>'),
            Row(
                Column('name', css_class='form-group col-md-6'),
                Column('bay_number', css_class='form-group col-md-6'),
            ),
            'description',
            
            HTML('<h5 class="mt-4">Capacity & Features</h5>'),
            'max_vehicle_size',
            
            HTML('<h5 class="mt-4">Equipment</h5>'),
            Row(
                Column('has_pressure_washer', css_class='form-group col-md-3'),
                Column('has_vacuum', css_class='form-group col-md-3'),
                Column('has_lift', css_class='form-group col-md-3'),
                Column('has_drainage', css_class='form-group col-md-3'),
            ),
            
            'is_active',
            
            FormActions(
                Submit('submit', 'Save Service Bay', css_class='btn btn-primary')
            )
        )
    
    def clean_bay_number(self):
        bay_number = self.cleaned_data['bay_number']
        
        # Check for duplicate bay numbers
        queryset = ServiceBay.objects.filter(bay_number=bay_number)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        
        if queryset.exists():
            raise ValidationError("A service bay with this number already exists.")
        
        return bay_number

class PaymentProcessingForm(forms.Form):
    """Payment processing form"""
    
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('card', 'Credit/Debit Card'),
        ('mpesa', 'M-Pesa'),
        ('bank_transfer', 'Bank Transfer'),
    ]
    
    payment_method = forms.ChoiceField(
        choices=PAYMENT_METHODS,
        widget=forms.RadioSelect,
        label="Payment Method"
    )
    
    amount_received = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control-lg'}),
        label="Amount Received"
    )
    
    customer_notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}),
        required=False,
        label="Customer Notes"
    )
    
    def __init__(self, *args, **kwargs):
        self.order = kwargs.pop('order', None)
        super().__init__(*args, **kwargs)
        
        if self.order:
            self.fields['amount_received'].initial = self.order.total_amount
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<div class="payment-summary mb-4">'),
            HTML('<h5>Payment Summary</h5>'),
            HTML(f'<p><strong>Total Amount: KES {self.order.total_amount if self.order else "0.00"}</strong></p>'),
            HTML('</div>'),
            
            'payment_method',
            'amount_received',
            'customer_notes',
            
            FormActions(
                Submit('submit', 'Process Payment', css_class='btn btn-success btn-lg')
            )
        )
    
    def clean_amount_received(self):
        amount = self.cleaned_data['amount_received']
        
        if amount <= 0:
            raise ValidationError("Amount must be greater than zero.")
        
        return amount

class QuickCustomerRegistrationForm(forms.Form):
    """Quick customer registration form for attendants"""
    
    # Customer Information
    first_name = forms.CharField(max_length=50, label="First Name")
    last_name = forms.CharField(max_length=50, label="Last Name")
    phone = forms.CharField(max_length=20, label="Phone Number")
    email = forms.EmailField(required=False, label="Email (Optional)")
    
    # Vehicle Information
    registration_number = forms.CharField(
        max_length=20,
        label="Registration Number",
        widget=forms.TextInput(attrs={'style': 'text-transform: uppercase;'})
    )
    make = forms.CharField(max_length=50, label="Make")
    model = forms.CharField(max_length=50, label="Model")
    color = forms.CharField(max_length=30, label="Color")
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
    year = forms.IntegerField(
        min_value=1990,
        max_value=2030,
        initial=2020,
        label="Year"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h5>Customer Information</h5>'),
            Row(
                Column('first_name', css_class='form-group col-md-6'),
                Column('last_name', css_class='form-group col-md-6'),
            ),
            Row(
                Column('phone', css_class='form-group col-md-6'),
                Column('email', css_class='form-group col-md-6'),
            ),
            
            HTML('<h5 class="mt-4">Vehicle Information</h5>'),
            Row(
                Column('registration_number', css_class='form-group col-md-4'),
                Column('make', css_class='form-group col-md-4'),
                Column('model', css_class='form-group col-md-4'),
            ),
            Row(
                Column('color', css_class='form-group col-md-4'),
                Column('vehicle_type', css_class='form-group col-md-4'),
                Column('year', css_class='form-group col-md-4'),
            ),
            
            FormActions(
                Submit('submit', 'Register Customer & Vehicle', css_class='btn btn-success btn-lg')
            )
        )
    
    def clean_phone(self):
        phone = self.cleaned_data['phone']
        
        # Basic phone validation for Kenya
        if not phone.startswith('+254') and not phone.startswith('0'):
            raise ValidationError("Please enter a valid Kenyan phone number.")
        
        return phone
    
    def clean_registration_number(self):
        registration = self.cleaned_data['registration_number'].upper()
        
        # Check if vehicle already exists
        from apps.customers.models import Vehicle
        if Vehicle.objects.filter(registration_number=registration).exists():
            raise ValidationError("A vehicle with this registration number already exists.")
        
        return registration

class ServiceAssignmentForm(forms.Form):
    """Quick service assignment form"""
    
    customer = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )
    
    vehicle = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )
    
    selected_services = forms.ModelMultipleChoiceField(
        queryset=None,
        widget=forms.CheckboxSelectMultiple,
        label="Select Services"
    )
    
    priority = forms.ChoiceField(
        choices=[
            ('normal', 'Normal'),
            ('high', 'High'),
            ('urgent', 'Urgent'),
        ],
        initial='normal',
        widget=forms.RadioSelect,
        label="Priority"
    )
    
    special_instructions = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        label="Special Instructions"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        from .models import Service
        self.fields['selected_services'].queryset = Service.objects.filter(
            is_active=True
        ).select_related('category').order_by('category__name', 'name')
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<div id="customer-vehicle-selection" class="mb-4">'),
            HTML('<h5>Customer & Vehicle Selection</h5>'),
            HTML('<div class="row">'),
            HTML('<div class="col-md-6">'),
            HTML('<label>Customer</label>'),
            HTML('<input type="text" id="customer-search" class="form-control" placeholder="Search customer...">'),
            HTML('<div id="customer-results"></div>'),
            HTML('</div>'),
            HTML('<div class="col-md-6">'),
            HTML('<label>Vehicle</label>'),
            HTML('<input type="text" id="vehicle-search" class="form-control" placeholder="Search vehicle...">'),
            HTML('<div id="vehicle-results"></div>'),
            HTML('</div>'),
            HTML('</div>'),
            HTML('</div>'),
            
            'customer',
            'vehicle',
            
            HTML('<h5>Service Selection</h5>'),
            'selected_services',
            
            HTML('<div id="service-summary" class="mt-3 p-3 bg-light rounded"></div>'),
            
            HTML('<h5 class="mt-4">Order Details</h5>'),
            'priority',
            'special_instructions',
            
            FormActions(
                Submit('submit', 'Assign Services', css_class='btn btn-primary btn-lg')
            )
        )

class OrderCancellationForm(forms.Form):
    """Order cancellation form"""
    
    reason = forms.ChoiceField(
        choices=[
            ('customer_request', 'Customer Request'),
            ('vehicle_issue', 'Vehicle Issue'),
            ('equipment_failure', 'Equipment Failure'),
            ('staff_unavailable', 'Staff Unavailable'),
            ('weather', 'Weather Conditions'),
            ('other', 'Other'),
        ],
        widget=forms.RadioSelect,
        label="Cancellation Reason"
    )
    
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4}),
        label="Additional Notes",
        help_text="Please provide details about the cancellation"
    )
    
    refund_amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        initial=0,
        widget=forms.NumberInput(attrs={'step': '0.01'}),
        label="Refund Amount (if applicable)"
    )
    
    def __init__(self, *args, **kwargs):
        self.order = kwargs.pop('order', None)
        super().__init__(*args, **kwargs)
        
        if self.order and self.order.payment_status == 'paid':
            self.fields['refund_amount'].initial = self.order.total_amount
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'reason',
            'notes',
            'refund_amount',
            
            FormActions(
                Submit('submit', 'Cancel Order', css_class='btn btn-danger'),
                HTML('<a href="{% url "services:order_detail" pk=order.pk %}" class="btn btn-secondary ml-2">Go Back</a>')
            )
        )

class QueueManagementForm(forms.Form):
    """Queue management form"""
    
    queue_entries = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<div id="sortable-queue">'),
            HTML('<!-- Queue entries will be populated by JavaScript -->'),
            HTML('</div>'),
            
            'queue_entries',
            
            FormActions(
                Submit('submit', 'Update Queue Order', css_class='btn btn-primary')
            )
        )

class ServiceReportForm(forms.Form):
    """Service report generation form"""
    
    REPORT_TYPES = [
        ('daily', 'Daily Report'),
        ('weekly', 'Weekly Report'),
        ('monthly', 'Monthly Report'),
        ('custom', 'Custom Date Range'),
        ('service_performance', 'Service Performance'),
        ('employee_performance', 'Employee Performance'),
        ('customer_analysis', 'Customer Analysis'),
    ]
    
    report_type = forms.ChoiceField(
        choices=REPORT_TYPES,
        widget=forms.RadioSelect,
        label="Report Type"
    )
    
    date_from = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=False,
        label="From Date"
    )
    
    date_to = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=False,
        label="To Date"
    )
    
    service_category = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="All Categories",
        label="Service Category"
    )
    
    employee = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="All Employees",
        label="Employee"
    )
    
    format = forms.ChoiceField(
        choices=[
            ('html', 'View in Browser'),
            ('pdf', 'Download PDF'),
            ('excel', 'Download Excel'),
            ('csv', 'Download CSV'),
        ],
        initial='html',
        label="Report Format"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        from .models import ServiceCategory
        from apps.employees.models import Employee
        
        self.fields['service_category'].queryset = ServiceCategory.objects.filter(is_active=True)
        self.fields['employee'].queryset = Employee.objects.filter(
            is_active=True,
            role__in=['attendant', 'supervisor', 'manager']
        )
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'report_type',
            
            HTML('<div id="date-range-fields" style="display: none;">'),
            Row(
                Column('date_from', css_class='form-group col-md-6'),
                Column('date_to', css_class='form-group col-md-6'),
            ),
            HTML('</div>'),
            
            HTML('<div id="filter-fields">'),
            Row(
                Column('service_category', css_class='form-group col-md-6'),
                Column('employee', css_class='form-group col-md-6'),
            ),
            HTML('</div>'),
            
            'format',
            
            FormActions(
                Submit('submit', 'Generate Report', css_class='btn btn-primary')
            )
        )

class ServiceImportForm(forms.Form):
    """Service import form"""
    
    csv_file = forms.FileField(
        label="CSV File",
        help_text="Upload a CSV file with service data. Download the template for proper format."
    )
    
    update_existing = forms.BooleanField(
        required=False,
        initial=False,
        label="Update existing services",
        help_text="If checked, existing services with the same name will be updated"
    )
    
    create_categories = forms.BooleanField(
        required=False,
        initial=True,
        label="Auto-create categories",
        help_text="Automatically create service categories if they don't exist"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<div class="alert alert-info">'),
            HTML('<h6>Import Instructions</h6>'),
            HTML('<ul>'),
            HTML('<li>CSV file should contain columns: Name, Category, Description, Base Price, Estimated Duration</li>'),
            HTML('<li>Additional columns: Required Skill Level, Compatible Vehicles, Is Popular, Is Premium, Is Active</li>'),
            HTML('<li>Download the template file for the correct format</li>'),
            HTML('</ul>'),
            HTML('<a href="{% url "services:import_template" %}" class="btn btn-sm btn-outline-primary">Download Template</a>'),
            HTML('</div>'),
            
            'csv_file',
            'update_existing',
            'create_categories',
            
            FormActions(
                Submit('submit', 'Import Services', css_class='btn btn-success')
            )
        )
    
    def clean_csv_file(self):
        csv_file = self.cleaned_data['csv_file']
        
        if not csv_file.name.endswith('.csv'):
            raise ValidationError("Please upload a CSV file.")
        
        if csv_file.size > 5 * 1024 * 1024:  # 5MB limit
            raise ValidationError("File size cannot exceed 5MB.")
        
        return csv_file

class AttendanceCheckForm(forms.Form):
    """Attendance check-in/out form for employees"""
    
    action = forms.ChoiceField(
        choices=[
            ('check_in', 'Check In'),
            ('check_out', 'Check Out'),
            ('break_start', 'Start Break'),
            ('break_end', 'End Break'),
        ],
        widget=forms.RadioSelect,
        label="Action"
    )
    
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}),
        required=False,
        label="Notes (Optional)"
    )
    
    def __init__(self, *args, **kwargs):
        self.employee = kwargs.pop('employee', None)
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<div class="attendance-info mb-3">'),
            HTML('<h6>Current Time: <span id="current-time"></span></h6>'),
            HTML('</div>'),
            
            'action',
            'notes',
            
            FormActions(
                Submit('submit', 'Submit', css_class='btn btn-primary')
            )
        )

class NotificationPreferencesForm(forms.Form):
    """Notification preferences form"""
    
    service_reminders = forms.BooleanField(
        required=False,
        initial=True,
        label="Service Reminders",
        help_text="Receive reminders about upcoming services"
    )
    
    payment_notifications = forms.BooleanField(
        required=False,
        initial=True,
        label="Payment Notifications",
        help_text="Receive notifications about payments and receipts"
    )
    
    order_updates = forms.BooleanField(
        required=False,
        initial=True,
        label="Order Updates",
        help_text="Receive updates about order status changes"
    )
    
    marketing_messages = forms.BooleanField(
        required=False,
        initial=False,
        label="Marketing Messages",
        help_text="Receive promotional offers and marketing messages"
    )
    
    sms_notifications = forms.BooleanField(
        required=False,
        initial=True,
        label="SMS Notifications",
        help_text="Receive notifications via SMS"
    )
    
    email_notifications = forms.BooleanField(
        required=False,
        initial=True,
        label="Email Notifications",
        help_text="Receive notifications via email"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h5>Notification Types</h5>'),
            'service_reminders',
            'payment_notifications',
            'order_updates',
            'marketing_messages',
            
            HTML('<h5 class="mt-4">Delivery Methods</h5>'),
            'sms_notifications',
            'email_notifications',
            
            FormActions(
                Submit('submit', 'Save Preferences', css_class='btn btn-primary')
            )
        )