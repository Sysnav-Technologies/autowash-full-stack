
from django import forms
from django.core.exceptions import ValidationError
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Field, HTML, Div
from crispy_forms.bootstrap import FormActions
from phonenumber_field.formfields import PhoneNumberField
from .models import Customer, Vehicle, CustomerNote, CustomerDocument, CustomerFeedback
import datetime
import json

class CustomerSearchForm(forms.Form):
    """Customer search and filter form"""
    search = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Search by name, ID, phone, email, or vehicle...',
            'class': 'form-control',
            'id': 'customer-search-input'
        })
    )
    customer_type = forms.ChoiceField(
        choices=[('', 'All Types')] + Customer.CUSTOMER_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    is_vip = forms.NullBooleanField(
        required=False,
        widget=forms.Select(
            choices=[('', 'All'), (True, 'VIP Only'), (False, 'Regular Only')],
            attrs={'class': 'form-select'}
        )
    )
    is_active = forms.NullBooleanField(
        required=False,
        widget=forms.Select(
            choices=[('', 'All'), (True, 'Active Only'), (False, 'Inactive Only')],
            attrs={'class': 'form-select'}
        ),
        initial=True
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'GET'
        self.helper.form_class = 'form-inline'
        self.helper.layout = Layout(
            Row(
                Column('search', css_class='form-group col-md-4'),
                Column('customer_type', css_class='form-group col-md-2'),
                Column('is_vip', css_class='form-group col-md-2'),
                Column('is_active', css_class='form-group col-md-2'),
                Column(
                    Submit('submit', 'Search', css_class='btn btn-primary'),
                    css_class='form-group col-md-2'
                ),
            )
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
            'address_line_1', 'address_line_2', 'city', 'state', 'postal_code',
            'preferred_contact_method', 'receive_marketing_sms',
            'receive_marketing_email', 'receive_service_reminders',
            'is_vip', 'credit_limit', 'notes'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control'}
            ),
            'notes': forms.Textarea(
                attrs={'rows': 3, 'class': 'form-control'}
            ),
            'credit_limit': forms.NumberInput(
                attrs={'step': '0.01', 'class': 'form-control', 'min': '0'}
            ),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'customer_type': forms.Select(attrs={'class': 'form-select'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone_secondary': forms.TextInput(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'national_id': forms.TextInput(attrs={'class': 'form-control'}),
            'business_registration_number': forms.TextInput(attrs={'class': 'form-control'}),
            'tax_number': forms.TextInput(attrs={'class': 'form-control'}),
            'address_line_1': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Street Address'}),
            'address_line_2': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apartment, Suite, etc. (optional)'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control'}),
            'preferred_contact_method': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make first_name and last_name required
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        
        # Set conditional requirements
        self.fields['company_name'].required = False
        self.fields['business_registration_number'].required = False
        self.fields['tax_number'].required = False
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('''
                <script>
                document.addEventListener('DOMContentLoaded', function() {
                    const customerTypeField = document.getElementById('id_customer_type');
                    const companyFields = document.getElementById('company-fields');
                    
                    function toggleCompanyFields() {
                        if (customerTypeField && companyFields) {
                            if (customerTypeField.value === 'corporate') {
                                companyFields.style.display = 'block';
                            } else {
                                companyFields.style.display = 'none';
                            }
                        }
                    }
                    
                    if (customerTypeField) {
                        customerTypeField.addEventListener('change', toggleCompanyFields);
                        toggleCompanyFields(); // Run on page load
                    }
                });
                </script>
            '''),
            HTML('<h5 class="mb-3">Basic Information</h5>'),
            Row(
                Column('customer_type', css_class='form-group col-md-4 mb-3'),
                Column('first_name', css_class='form-group col-md-4 mb-3'),
                Column('last_name', css_class='form-group col-md-4 mb-3'),
            ),
            
            # Company information (hidden by default)
            HTML('<div id="company-fields" style="display: none;">'),
            'company_name',
            Row(
                Column('business_registration_number', css_class='form-group col-md-6 mb-3'),
                Column('tax_number', css_class='form-group col-md-6 mb-3'),
            ),
            HTML('</div>'),
            
            HTML('<h5 class="mt-4 mb-3">Contact Information</h5>'),
            Row(
                Column('email', css_class='form-group col-md-6 mb-3'),
                Column('preferred_contact_method', css_class='form-group col-md-6 mb-3'),
            ),
            Row(
                Column('phone', css_class='form-group col-md-6 mb-3'),
                Column('phone_secondary', css_class='form-group col-md-6 mb-3'),
            ),
            
            HTML('<h5 class="mt-4 mb-3">Personal Information</h5>'),
            Row(
                Column('date_of_birth', css_class='form-group col-md-4 mb-3'),
                Column('gender', css_class='form-group col-md-4 mb-3'),
                Column('national_id', css_class='form-group col-md-4 mb-3'),
            ),
            
            HTML('<h5 class="mt-4 mb-3">Address</h5>'),
            'address_line_1',
            'address_line_2',
            Row(
                Column('city', css_class='form-group col-md-4 mb-3'),
                Column('state', css_class='form-group col-md-4 mb-3'),
                Column('postal_code', css_class='form-group col-md-4 mb-3'),
            ),
            
            HTML('<h5 class="mt-4 mb-3">Communication Preferences</h5>'),
            Row(
                Column('receive_marketing_sms', css_class='form-group col-md-4 mb-3'),
                Column('receive_marketing_email', css_class='form-group col-md-4 mb-3'),
                Column('receive_service_reminders', css_class='form-group col-md-4 mb-3'),
            ),
            
            HTML('<h5 class="mt-4 mb-3">Account Settings</h5>'),
            Row(
                Column('is_vip', css_class='form-group col-md-6 mb-3'),
                Column('credit_limit', css_class='form-group col-md-6 mb-3'),
            ),
            'notes',
            
            # Only show for new customers
            HTML('{% if not form.instance.pk %}'),
            'send_welcome_message',
            HTML('{% endif %}'),
            
            HTML('<div class="mt-4">'),
            FormActions(
                Submit('submit', 'Save Customer', css_class='btn btn-primary me-2'),
                Submit('create_another', 'Save & Add Another', css_class='btn btn-secondary'),
            ),
            HTML('</div>')
        )
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            phone_str = str(phone)
            existing_customer = Customer.objects.filter(phone=phone_str).exclude(
                pk=self.instance.pk if self.instance.pk else None
            ).first()
            if existing_customer:
                raise ValidationError("A customer with this phone number already exists.")
        return phone
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            existing_customer = Customer.objects.filter(email=email).exclude(
                pk=self.instance.pk if self.instance.pk else None
            ).first()
            if existing_customer:
                raise ValidationError("A customer with this email already exists.")
        return email
    
    def clean(self):
        cleaned_data = super().clean()
        customer_type = cleaned_data.get('customer_type')
        company_name = cleaned_data.get('company_name')
        
        # Validate company fields for corporate customers
        if customer_type == 'corporate' and not company_name:
            self.add_error('company_name', 'Company name is required for corporate customers.')
        
        return cleaned_data

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
            'year': forms.NumberInput(attrs={
                'min': 1900, 
                'max': datetime.datetime.now().year + 1,
                'class': 'form-control'
            }),
            'registration_number': forms.TextInput(attrs={
                'style': 'text-transform: uppercase;',
                'class': 'form-control'
            }),
            'notes': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'make': forms.TextInput(attrs={'class': 'form-control'}),
            'model': forms.TextInput(attrs={'class': 'form-control'}),
            'color': forms.TextInput(attrs={'class': 'form-control'}),
            'vehicle_type': forms.Select(attrs={'class': 'form-select'}),
            'fuel_type': forms.Select(attrs={'class': 'form-select'}),
            'engine_size': forms.TextInput(attrs={'class': 'form-control'}),
            'transmission': forms.Select(attrs={'class': 'form-select'}),
            'last_service_mileage': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set current year as default
        self.fields['year'].initial = datetime.datetime.now().year
        
        # Make required fields explicit
        self.fields['registration_number'].required = True
        self.fields['make'].required = True
        self.fields['model'].required = True
        self.fields['year'].required = True
        self.fields['color'].required = True
        self.fields['vehicle_type'].required = True
        self.fields['fuel_type'].required = True
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h6 class="mb-3">Vehicle Details</h6>'),
            Row(
                Column('registration_number', css_class='form-group col-md-4 mb-3'),
                Column('make', css_class='form-group col-md-4 mb-3'),
                Column('model', css_class='form-group col-md-4 mb-3'),
            ),
            Row(
                Column('year', css_class='form-group col-md-3 mb-3'),
                Column('color', css_class='form-group col-md-3 mb-3'),
                Column('vehicle_type', css_class='form-group col-md-3 mb-3'),
                Column('fuel_type', css_class='form-group col-md-3 mb-3'),
            ),
            Row(
                Column('engine_size', css_class='form-group col-md-4 mb-3'),
                Column('transmission', css_class='form-group col-md-4 mb-3'),
                Column('last_service_mileage', css_class='form-group col-md-4 mb-3'),
            ),
            'notes',
            HTML('<div class="mt-4">'),
            FormActions(
                Submit('submit', 'Save Vehicle', css_class='btn btn-primary')
            ),
            HTML('</div>')
        )
    
    def clean_registration_number(self):
        reg_number = self.cleaned_data.get('registration_number', '').upper()
        if reg_number:
            existing_vehicle = Vehicle.objects.filter(
                registration_number=reg_number
            ).exclude(pk=self.instance.pk if self.instance.pk else None).first()
            if existing_vehicle:
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
            'content': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'follow_up_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'note_type': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['title'].required = True
        self.fields['content'].required = True
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('note_type', css_class='form-group col-md-6 mb-3'),
                Column('title', css_class='form-group col-md-6 mb-3'),
            ),
            'content',
            Row(
                Column('is_private', css_class='form-group col-md-4 mb-3'),
                Column('is_important', css_class='form-group col-md-4 mb-3'),
                Column('requires_follow_up', css_class='form-group col-md-4 mb-3'),
            ),
            'follow_up_date',
            HTML('<div class="mt-4">'),
            FormActions(
                Submit('submit', 'Save Note', css_class='btn btn-primary')
            ),
            HTML('</div>')
        )
    
    def clean_follow_up_date(self):
        follow_up_date = self.cleaned_data.get('follow_up_date')
        requires_follow_up = self.cleaned_data.get('requires_follow_up')
        
        if requires_follow_up and not follow_up_date:
            raise ValidationError("Follow-up date is required when follow-up is needed.")
        
        if follow_up_date and follow_up_date < datetime.date.today():
            raise ValidationError("Follow-up date cannot be in the past.")
        
        return follow_up_date

class CustomerDocumentForm(forms.ModelForm):
    """Customer document upload form"""
    
    class Meta:
        model = CustomerDocument
        fields = ['document_type', 'title', 'file', 'description', 'expiry_date']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'expiry_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'document_type': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['title'].required = True
        self.fields['file'].required = True
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('document_type', css_class='form-group col-md-6 mb-3'),
                Column('title', css_class='form-group col-md-6 mb-3'),
            ),
            'file',
            'description',
            'expiry_date',
            HTML('<div class="mt-4">'),
            FormActions(
                Submit('submit', 'Upload Document', css_class='btn btn-primary')
            ),
            HTML('</div>')
        )
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            # Limit file size to 10MB
            if file.size > 10 * 1024 * 1024:
                raise ValidationError("File size cannot exceed 10MB.")
            
            # Check file extension
            allowed_extensions = ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png']
            file_extension = file.name.lower().split('.')[-1]
            if f'.{file_extension}' not in allowed_extensions:
                raise ValidationError(
                    f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"
                )
        
        return file

class CustomerFeedbackForm(forms.ModelForm):
    """Customer feedback form"""
    
    class Meta:
        model = CustomerFeedback
        fields = [
            'overall_rating', 'service_quality', 'staff_friendliness',
            'cleanliness', 'value_for_money', 'comments', 'suggestions'
        ]
        widgets = {
            'overall_rating': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'service_quality': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'staff_friendliness': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'cleanliness': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'value_for_money': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'comments': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'suggestions': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['overall_rating'].required = True
        
        # Add CSS classes for star ratings
        rating_fields = [
            'overall_rating', 'service_quality', 'staff_friendliness',
            'cleanliness', 'value_for_money'
        ]
        
        for field in rating_fields:
            self.fields[field].widget.attrs['class'] = 'star-rating'
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h6 class="mb-3">Rate Your Experience</h6>'),
            Row(
                Column('overall_rating', css_class='form-group col-md-12 mb-3'),
            ),
            Row(
                Column('service_quality', css_class='form-group col-md-6 mb-3'),
                Column('staff_friendliness', css_class='form-group col-md-6 mb-3'),
            ),
            Row(
                Column('cleanliness', css_class='form-group col-md-6 mb-3'),
                Column('value_for_money', css_class='form-group col-md-6 mb-3'),
            ),
            HTML('<h6 class="mt-4 mb-3">Comments</h6>'),
            'comments',
            'suggestions',
            HTML('<div class="mt-4">'),
            FormActions(
                Submit('submit', 'Submit Feedback', css_class='btn btn-primary')
            ),
            HTML('</div>')
        )

class QuickCustomerForm(forms.Form):
    """Quick customer registration form for service attendants"""
    first_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    phone = PhoneNumberField(
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    
    # Vehicle information
    registration_number = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'style': 'text-transform: uppercase;',
            'class': 'form-control'
        })
    )
    make = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    model = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    color = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h6 class="mb-3">Customer Information</h6>'),
            Row(
                Column('first_name', css_class='form-group col-md-6 mb-3'),
                Column('last_name', css_class='form-group col-md-6 mb-3'),
            ),
            Row(
                Column('phone', css_class='form-group col-md-6 mb-3'),
                Column('email', css_class='form-group col-md-6 mb-3'),
            ),
            HTML('<h6 class="mt-3 mb-3">Vehicle Information</h6>'),
            Row(
                Column('registration_number', css_class='form-group col-md-6 mb-3'),
                Column('make', css_class='form-group col-md-6 mb-3'),
            ),
            Row(
                Column('model', css_class='form-group col-md-6 mb-3'),
                Column('color', css_class='form-group col-md-6 mb-3'),
            ),
            HTML('<div class="mt-4">'),
            FormActions(
                Submit('submit', 'Register Customer', css_class='btn btn-primary btn-lg w-100')
            ),
            HTML('</div>')
        )
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            phone_str = str(phone)
            if Customer.objects.filter(phone=phone_str).exists():
                raise ValidationError("A customer with this phone number already exists.")
        return phone
    
    def clean_registration_number(self):
        reg_number = self.cleaned_data.get('registration_number', '').upper()
        if reg_number and Vehicle.objects.filter(registration_number=reg_number).exists():
            raise ValidationError("A vehicle with this registration number already exists.")
        return reg_number

# Additional form for customer feedback response
class FeedbackResponseForm(forms.ModelForm):
    """Form for management to respond to customer feedback"""
    
    class Meta:
        model = CustomerFeedback
        fields = ['response']
        widgets = {
            'response': forms.Textarea(attrs={
                'rows': 4,
                'class': 'form-control',
                'placeholder': 'Enter your response to this feedback...'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['response'].required = True
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'response',
            HTML('<div class="mt-3">'),
            FormActions(
                Submit('submit', 'Submit Response', css_class='btn btn-primary')
            ),
            HTML('</div>')
        )

# Form for bulk customer operations
class BulkCustomerActionForm(forms.Form):
    """Form for bulk actions on customers"""
    
    ACTION_CHOICES = [
        ('', 'Select Action'),
        ('activate', 'Activate'),
        ('deactivate', 'Deactivate'),
        ('make_vip', 'Make VIP'),
        ('remove_vip', 'Remove VIP'),
        ('export', 'Export Selected'),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    customer_ids = forms.CharField(
        widget=forms.HiddenInput()
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('action', css_class='form-group col-md-8'),
                Column(
                    Submit('submit', 'Apply Action', css_class='btn btn-warning'),
                    css_class='form-group col-md-4'
                ),
            ),
            'customer_ids'
        )
    
    def clean_customer_ids(self):
        customer_ids = self.cleaned_data.get('customer_ids', '')
        if customer_ids:
            try:
                # Convert comma-separated string to list and validate UUIDs
                id_list = [id.strip() for id in customer_ids.split(',') if id.strip()]
                # Validate that these are valid customer IDs
                valid_customers = Customer.objects.filter(
                    pk__in=id_list
                ).values_list('pk', flat=True)
                return [str(pk) for pk in valid_customers]
            except Exception as e:
                raise ValidationError("Invalid customer IDs provided.")
        return []