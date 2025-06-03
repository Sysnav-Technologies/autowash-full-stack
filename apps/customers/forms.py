from django import forms
from django.core.exceptions import ValidationError
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Field, HTML, Div
from crispy_forms.bootstrap import FormActions
from phonenumber_field.formfields import PhoneNumberField
from .models import Customer, Vehicle, CustomerNote, CustomerDocument, CustomerFeedback

class CustomerSearchForm(forms.Form):
    """Customer search and filter form"""
    search = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Search by name, ID, phone, email, or vehicle...',
            'class': 'form-control'
        })
    )
    customer_type = forms.ChoiceField(
        choices=[('', 'All Types')] + Customer.CUSTOMER_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    is_vip = forms.BooleanField(required=False, widget=forms.CheckboxInput())
    is_active = forms.BooleanField(
        required=False, 
        initial=True, 
        widget=forms.CheckboxInput()
    )

class CustomerForm(forms.ModelForm):
    """Customer creation and edit form"""
    send_welcome_message = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Send welcome SMS to customer"
    )
    
    class Meta:
        model = Customer
        fields = [
            'first_name', 'last_name', 'company_name', 'customer_type',
            'email', 'phone', 'phone_secondary', 'date_of_birth', 'gender',
            'national_id', 'business_registration_number', 'tax_number',
            'street_address', 'city', 'state', 'postal_code',
            'preferred_contact_method', 'receive_marketing_sms',
            'receive_marketing_email', 'receive_service_reminders',
            'is_vip', 'credit_limit', 'notes'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'credit_limit': forms.NumberInput(attrs={'step': '0.01'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Hide company fields for individual customers initially
        self.fields['company_name'].widget.attrs['style'] = 'display: none;'
        self.fields['business_registration_number'].widget.attrs['style'] = 'display: none;'
        self.fields['tax_number'].widget.attrs['style'] = 'display: none;'
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h5>Basic Information</h5>'),
            Row(
                Column('customer_type', css_class='form-group col-md-4'),
                Column('first_name', css_class='form-group col-md-4'),
                Column('last_name', css_class='form-group col-md-4'),
            ),
            
            # Company information (hidden by default)
            HTML('<div id="company-fields" style="display: none;">'),
            'company_name',
            Row(
                Column('business_registration_number', css_class='form-group col-md-6'),
                Column('tax_number', css_class='form-group col-md-6'),
            ),
            HTML('</div>'),
            
            HTML('<h5 class="mt-4">Contact Information</h5>'),
            Row(
                Column('email', css_class='form-group col-md-6'),
                Column('preferred_contact_method', css_class='form-group col-md-6'),
            ),
            Row(
                Column('phone', css_class='form-group col-md-6'),
                Column('phone_secondary', css_class='form-group col-md-6'),
            ),
            
            HTML('<h5 class="mt-4">Personal Information</h5>'),
            Row(
                Column('date_of_birth', css_class='form-group col-md-4'),
                Column('gender', css_class='form-group col-md-4'),
                Column('national_id', css_class='form-group col-md-4'),
            ),
            
            HTML('<h5 class="mt-4">Address</h5>'),
            'street_address',
            Row(
                Column('city', css_class='form-group col-md-4'),
                Column('state', css_class='form-group col-md-4'),
                Column('postal_code', css_class='form-group col-md-4'),
            ),
            
            HTML('<h5 class="mt-4">Preferences</h5>'),
            Row(
                Column('receive_marketing_sms', css_class='form-group col-md-4'),
                Column('receive_marketing_email', css_class='form-group col-md-4'),
                Column('receive_service_reminders', css_class='form-group col-md-4'),
            ),
            
            HTML('<h5 class="mt-4">Account Settings</h5>'),
            Row(
                Column('is_vip', css_class='form-group col-md-6'),
                Column('credit_limit', css_class='form-group col-md-6'),
            ),
            'notes',
            
            # Only show for new customers
            HTML('{% if not form.instance.pk %}'),
            'send_welcome_message',
            HTML('{% endif %}'),
            
            FormActions(
                Submit('submit', 'Save Customer', css_class='btn btn-primary'),
                Submit('create_another', 'Save & Add Another', css_class='btn btn-secondary'),
            )
        )
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone and Customer.objects.filter(phone=phone).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise ValidationError("A customer with this phone number already exists.")
        return phone
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and Customer.objects.filter(email=email).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise ValidationError("A customer with this email already exists.")
        return email

class VehicleForm(forms.ModelForm):
    """Vehicle form"""
    
    class Meta:
        model = Vehicle
        fields = [
            'registration_number', 'make', 'model', 'year', 'color',
            'vehicle_type', 'fuel_type', 'engine_size', 'transmission',
            'last_service_mileage', 'notes'
        ]
        widgets = {
            'year': forms.NumberInput(attrs={'min': 1900, 'max': 2030}),
            'registration_number': forms.TextInput(attrs={'style': 'text-transform: uppercase;'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set current year as default
        import datetime
        self.fields['year'].initial = datetime.datetime.now().year
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h6>Vehicle Details</h6>'),
            Row(
                Column('registration_number', css_class='form-group col-md-4'),
                Column('make', css_class='form-group col-md-4'),
                Column('model', css_class='form-group col-md-4'),
            ),
            Row(
                Column('year', css_class='form-group col-md-3'),
                Column('color', css_class='form-group col-md-3'),
                Column('vehicle_type', css_class='form-group col-md-3'),
                Column('fuel_type', css_class='form-group col-md-3'),
            ),
            Row(
                Column('engine_size', css_class='form-group col-md-4'),
                Column('transmission', css_class='form-group col-md-4'),
                Column('last_service_mileage', css_class='form-group col-md-4'),
            ),
            'notes',
            FormActions(
                Submit('submit', 'Save Vehicle', css_class='btn btn-primary')
            )
        )
    
    def clean_registration_number(self):
        reg_number = self.cleaned_data.get('registration_number', '').upper()
        if reg_number and Vehicle.objects.filter(
            registration_number=reg_number
        ).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise ValidationError("A vehicle with this registration number already exists.")
        return reg_number

class CustomerNoteForm(forms.ModelForm):
    """Customer note form"""
    
    class Meta:
        model = CustomerNote
        fields = [
            'note_type', 'title', 'content', 'is_private', 'is_important',
            'requires_follow_up', 'follow_up_date'
        ]
        widgets = {
            'content': forms.Textarea(attrs={'rows': 4}),
            'follow_up_date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('note_type', css_class='form-group col-md-6'),
                Column('title', css_class='form-group col-md-6'),
            ),
            'content',
            Row(
                Column('is_private', css_class='form-group col-md-4'),
                Column('is_important', css_class='form-group col-md-4'),
                Column('requires_follow_up', css_class='form-group col-md-4'),
            ),
            'follow_up_date',
            FormActions(
                Submit('submit', 'Save Note', css_class='btn btn-primary')
            )
        )

class CustomerDocumentForm(forms.ModelForm):
    """Customer document upload form"""
    
    class Meta:
        model = CustomerDocument
        fields = ['document_type', 'title', 'file', 'description', 'expiry_date']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('document_type', css_class='form-group col-md-6'),
                Column('title', css_class='form-group col-md-6'),
            ),
            'file',
            'description',
            'expiry_date',
            FormActions(
                Submit('submit', 'Upload Document', css_class='btn btn-primary')
            )
        )

class CustomerFeedbackForm(forms.ModelForm):
    """Customer feedback form"""
    
    class Meta:
        model = CustomerFeedback
        fields = [
            'overall_rating', 'service_quality', 'staff_friendliness',
            'cleanliness', 'value_for_money', 'comments', 'suggestions'
        ]
        widgets = {
            'overall_rating': forms.RadioSelect(),
            'service_quality': forms.RadioSelect(),
            'staff_friendliness': forms.RadioSelect(),
            'cleanliness': forms.RadioSelect(),
            'value_for_money': forms.RadioSelect(),
            'comments': forms.Textarea(attrs={'rows': 3}),
            'suggestions': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add CSS classes for star ratings
        rating_fields = [
            'overall_rating', 'service_quality', 'staff_friendliness',
            'cleanliness', 'value_for_money'
        ]
        
        for field in rating_fields:
            self.fields[field].widget.attrs['class'] = 'star-rating'
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h6>Rate Your Experience</h6>'),
            Row(
                Column('overall_rating', css_class='form-group col-md-12'),
            ),
            Row(
                Column('service_quality', css_class='form-group col-md-6'),
                Column('staff_friendliness', css_class='form-group col-md-6'),
            ),
            Row(
                Column('cleanliness', css_class='form-group col-md-6'),
                Column('value_for_money', css_class='form-group col-md-6'),
            ),
            HTML('<h6 class="mt-4">Comments</h6>'),
            'comments',
            'suggestions',
            FormActions(
                Submit('submit', 'Submit Feedback', css_class='btn btn-primary')
            )
        )

class QuickCustomerForm(forms.Form):
    """Quick customer registration form for service attendants"""
    first_name = forms.CharField(max_length=50)
    last_name = forms.CharField(max_length=50)
    phone = PhoneNumberField()
    email = forms.EmailField(required=False)
    
    # Vehicle information
    registration_number = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={'style': 'text-transform: uppercase;'})
    )
    make = forms.CharField(max_length=50)
    model = forms.CharField(max_length=50)
    color = forms.CharField(max_length=30)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h6>Customer Information</h6>'),
            Row(
                Column('first_name', css_class='form-group col-md-6'),
                Column('last_name', css_class='form-group col-md-6'),
            ),
            Row(
                Column('phone', css_class='form-group col-md-6'),
                Column('email', css_class='form-group col-md-6'),
            ),
            HTML('<h6 class="mt-3">Vehicle Information</h6>'),
            Row(
                Column('registration_number', css_class='form-group col-md-6'),
                Column('make', css_class='form-group col-md-6'),
            ),
            Row(
                Column('model', css_class='form-group col-md-6'),
                Column('color', css_class='form-group col-md-6'),
            ),
            FormActions(
                Submit('submit', 'Register Customer', css_class='btn btn-primary btn-lg w-100')
            )
        )