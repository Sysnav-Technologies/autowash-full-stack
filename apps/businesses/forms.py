from django import forms
from django.core.validators import EmailValidator, RegexValidator
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from decimal import Decimal
from apps.accounts.models import Business, BusinessSettings
from django.core.exceptions import ValidationError
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Field, HTML, Div
from crispy_forms.bootstrap import FormActions
from phonenumber_field.formfields import PhoneNumberField
from django.utils import timezone
from django.utils.text import slugify
import os
import re
from apps.accounts.models import Business
from .models import  BusinessGoal, BusinessAlert, QuickAction, DashboardWidget



class BusinessRegistrationForm(forms.ModelForm):
    """Business registration form - simplified to match actual Business model fields"""
    
    # Add custom location field since your model doesn't have address fields directly
    location = forms.CharField(
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'Business location/address',
            'class': 'form-control'
        }),
        help_text='Enter your business address or location'
    )
    
    class Meta:
        model = Business
        # Use only fields that definitely exist in the Business model
        fields = ['name', 'business_type', 'description', 'phone', 'email']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Your Business Name', 
                'class': 'form-control',
            }),
            'business_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Brief description of your business (optional)',
                'class': 'form-control'
            }),
            'phone': forms.TextInput(attrs={
                'placeholder': '+254712345678',
                'class': 'form-control'
            }),
            'email': forms.EmailInput(attrs={
                'placeholder': 'business@email.com',
                'class': 'form-control'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make required fields
        self.fields['name'].required = True
        self.fields['business_type'].required = True
        self.fields['phone'].required = True
        self.fields['email'].required = True
        self.fields['location'].required = True
        
        # Optional fields
        self.fields['description'].required = False
        
        # Set up crispy forms layout
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Field('name', css_class='mb-3'),
            Field('business_type', css_class='mb-3'),
            Field('description', css_class='mb-3'),
            Field('location', css_class='mb-3'),
            Row(
                Column('phone', css_class='form-group col-md-6 mb-3'),
                Column('email', css_class='form-group col-md-6 mb-3'),
            ),
            FormActions(
                Submit('submit', 'Register Business', css_class='btn btn-primary btn-lg w-100')
            )
        )
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name:
            raise ValidationError("Business name is required.")
        
        # Check for duplicate business names
        if Business.objects.filter(name__iexact=name).exists():
            raise ValidationError("A business with this name already exists.")
        
        return name
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and Business.objects.filter(email__iexact=email).exists():
            raise ValidationError("A business with this email already exists.")
        return email
    
    def clean(self):
        """Auto-generate subdomain from business name"""
        cleaned_data = super().clean()
        name = cleaned_data.get('name')
        
        if name:
            # Auto-generate subdomain from business name
            subdomain = slugify(name).lower()
            # Remove any characters that aren't allowed in subdomains
            subdomain = re.sub(r'[^a-z0-9-]', '', subdomain)
            if not subdomain or not subdomain[0].isalpha():
                subdomain = 'biz' + subdomain
            
            # Ensure subdomain is unique
            original_subdomain = subdomain
            counter = 1
            while Business.objects.filter(subdomain__iexact=subdomain).exists():
                subdomain = f"{original_subdomain}{counter}"
                counter += 1
            
            # Add subdomain to cleaned data
            cleaned_data['subdomain'] = subdomain
        
        return cleaned_data
    
    def save(self, commit=True):
        """Save the business and handle the location field and auto-generated subdomain"""
        business = super().save(commit=False)
        
        # Set the auto-generated subdomain
        subdomain = self.cleaned_data.get('subdomain')
        if subdomain:
            business.subdomain = subdomain
        
        # Handle location - you can store it in a field that exists in your model
        # Based on your model, it looks like you have fields from Address and ContactInfo mixins
        location = self.cleaned_data.get('location')
        if location:
            # If you have an address field in your Address mixin, use that
            # Otherwise, you might want to store it in description or create a location field
            if hasattr(business, 'address'):
                business.address = location
            elif hasattr(business, 'address_line_1'):
                business.address_line_1 = location
            # If no address field exists, you might want to add location to description
            elif location and not business.description:
                business.description = f"Location: {location}"
            elif location and business.description:
                business.description = f"{business.description}\nLocation: {location}"
        
        if commit:
            business.save()
        return business

class BusinessSettingsForm(forms.ModelForm):
    """Form for editing business profile information"""
    
    class Meta:
        model = Business
        fields = [
            'name', 'business_type', 'description', 'logo',
            'phone', 'email',
            'opening_time', 'closing_time', 'timezone'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your Business Name',
                'required': True
            }),
            'business_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Brief description of your business'
            }),
            'logo': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/jpeg,image/jpg,image/png,image/gif,image/webp'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+254712345678'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'business@email.com'
            }),
            'opening_time': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'closing_time': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'timezone': forms.Select(attrs={
                'class': 'form-select'
            })
        }
    
    # Add custom address fields since they're not directly on the model
    address_line_1 = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Street address'
        }),
        label='Street Address'
    )
    
    city = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'City'
        }),
        label='City'
    )
    
    state = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'County/State'
        }),
        label='County/State'
    )
    
    postal_code = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Postal code'
        }),
        label='Postal Code'
    )
    
    country = forms.CharField(
        max_length=100,
        required=False,
        initial='Kenya',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Country'
        }),
        label='Country'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set timezone choices
        self.fields['timezone'].choices = [
            ('Africa/Nairobi', 'Africa/Nairobi (EAT)'),
            ('Africa/Cairo', 'Africa/Cairo (EET)'),
            ('Africa/Lagos', 'Africa/Lagos (WAT)'),
            ('UTC', 'UTC'),
        ]
        
        # Make required fields
        self.fields['name'].required = True
        self.fields['phone'].required = True
        self.fields['email'].required = True
        
        # Optional fields
        self.fields['description'].required = False
        self.fields['logo'].required = False
        
        # Load address fields from business instance if editing
        if self.instance and self.instance.pk:
            # Try to get address fields from the instance if they exist
            for field_name in ['address_line_1', 'address_line_2', 'city', 'state', 'postal_code', 'country']:
                if hasattr(self.instance, field_name):
                    self.fields[field_name].initial = getattr(self.instance, field_name, '')
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            # Check for duplicate emails (excluding current instance)
            queryset = Business.objects.filter(email__iexact=email)
            if self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            
            if queryset.exists():
                raise ValidationError("A business with this email already exists.")
        return email
    
    def clean_logo(self):
        """Validate logo file"""
        logo = self.cleaned_data.get('logo')
        if logo:
            # Check file size (5MB limit)
            if logo.size > 5 * 1024 * 1024:
                raise ValidationError("Logo file size cannot exceed 5MB.")
            
            # Check file extension
            import os
            ext = os.path.splitext(logo.name)[1].lower()
            valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']
            if ext not in valid_extensions:
                raise ValidationError(f"Unsupported file extension. Please use: {', '.join(valid_extensions)}")
        
        return logo
        name = self.cleaned_data.get('name')
        if name:
            # Check for duplicate names (excluding current instance)
            queryset = Business.objects.filter(name__iexact=name)
            if self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            
            if queryset.exists():
                raise ValidationError("A business with this name already exists.")
        return name
    
    def save(self, commit=True):
        """Save the business and handle address fields"""
        business = super().save(commit=False)
        
        # Handle address fields if they exist on the model
        address_fields = ['address_line_1', 'address_line_2', 'city', 'state', 'postal_code', 'country']
        for field_name in address_fields:
            field_value = self.cleaned_data.get(field_name)
            if field_value and hasattr(business, field_name):
                setattr(business, field_name, field_value)
        
        if commit:
            business.save()
        return business

class ServiceSettingsForm(forms.Form):
    """Form for service-related settings"""
    
    default_service_duration = forms.IntegerField(
        initial=30,
        min_value=1,
        max_value=480,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Duration in minutes'
        }),
        help_text='Default duration for new services (in minutes)'
    )
    
    auto_assign_services = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text='Automatically assign services to available attendants'
    )
    
    require_customer_approval = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text='Require customer approval before starting service'
    )
    
    send_service_reminders = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text='Send automatic service reminders to customers'
    )
    
    service_quality_check = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text='Require quality check before completing service'
    )
    
    allow_service_rating = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text='Allow customers to rate completed services'
    )

class PaymentSettingsForm(forms.Form):
    """Form for payment and financial settings"""
    
    default_tax_rate = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        initial=16.00,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0',
            'max': '100'
        }),
        help_text='Default tax rate percentage (e.g., 16.00 for 16%)'
    )
    
    currency = forms.CharField(
        max_length=3,
        initial='KES',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'readonly': True
        }),
        help_text='Business currency'
    )
    
    payment_terms = forms.CharField(
        max_length=200,
        required=False,
        initial='Payment due upon service completion',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Payment terms and conditions'
        })
    )
    
    late_payment_fee = forms.DecimalField(
        max_digits=8,
        decimal_places=2,
        initial=0,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0'
        }),
        help_text='Late payment fee amount'
    )
    
    auto_send_receipts = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text='Automatically send receipts after payment'
    )
    
    require_payment_confirmation = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text='Require manager confirmation for large payments'
    )
    
    large_payment_threshold = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        initial=10000,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0'
        }),
        help_text='Amount threshold for large payment confirmation'
    )

class NotificationSettingsForm(forms.Form):
    """Form for notification settings"""
    
    sms_notifications_enabled = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text='Enable SMS notifications'
    )
    
    email_notifications_enabled = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text='Enable email notifications'
    )
    
    notification_sender_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Business Name'
        }),
        help_text='Name to display as sender in notifications'
    )
    
    sms_signature = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'SMS signature (optional)'
        }),
        help_text='Signature to append to SMS messages'
    )
    
    send_booking_confirmations = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text='Send booking confirmation messages'
    )
    
    send_service_updates = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text='Send service status updates'
    )
    
    send_payment_confirmations = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text='Send payment confirmation messages'
    )
    
    send_reminder_notifications = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text='Send appointment reminders'
    )
    
    reminder_time_hours = forms.IntegerField(
        initial=24,
        min_value=1,
        max_value=72,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '1',
            'max': '72'
        }),
        help_text='Hours before appointment to send reminder'
    )

class IntegrationSettingsForm(forms.Form):
    """Form for third-party integrations"""
    
    mpesa_enabled = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text='Enable M-Pesa payments'
    )
    
    mpesa_business_shortcode = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter M-Pesa shortcode'
        }),
        help_text='M-Pesa business shortcode'
    )
    
    mpesa_consumer_key = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter consumer key'
        }),
        help_text='M-Pesa consumer key'
    )
    
    mpesa_consumer_secret = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter consumer secret'
        }),
        help_text='M-Pesa consumer secret'
    )
    
    mpesa_environment = forms.ChoiceField(
        choices=[
            ('sandbox', 'Sandbox (Testing)'),
            ('production', 'Production (Live)')
        ],
        initial='sandbox',
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        help_text='M-Pesa environment'
    )
    
    sms_provider = forms.ChoiceField(
        choices=[
            ('africastalking', 'Africa\'s Talking'),
            ('twilio', 'Twilio'),
            ('custom', 'Custom Provider')
        ],
        initial='africastalking',
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        help_text='SMS service provider'
    )
    
    sms_api_key = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter SMS API key'
        }),
        help_text='SMS provider API key'
    )
    
    sms_username = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'SMS username'
        }),
        help_text='SMS provider username'
    )
    
    email_provider = forms.ChoiceField(
        choices=[
            ('smtp', 'SMTP'),
            ('sendgrid', 'SendGrid'),
            ('mailgun', 'Mailgun')
        ],
        initial='smtp',
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        help_text='Email service provider'
    )
    
    smtp_host = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'smtp.gmail.com'
        }),
        help_text='SMTP server host'
    )
    
    smtp_port = forms.IntegerField(
        initial=587,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '1',
            'max': '65535'
        }),
        help_text='SMTP server port'
    )
    
    smtp_username = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email username'
        }),
        help_text='SMTP username'
    )
    
    smtp_password = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email password'
        }),
        help_text='SMTP password'
    )

class SecuritySettingsForm(forms.Form):
    """Form for security settings"""
    
    require_strong_passwords = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text='Require strong passwords for all users'
    )
    
    password_min_length = forms.IntegerField(
        initial=8,
        min_value=6,
        max_value=20,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '6',
            'max': '20'
        }),
        help_text='Minimum password length'
    )
    
    session_timeout = forms.IntegerField(
        initial=480,
        min_value=30,
        max_value=1440,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '30',
            'max': '1440'
        }),
        help_text='Session timeout in minutes'
    )
    
    failed_login_attempts = forms.IntegerField(
        initial=5,
        min_value=3,
        max_value=10,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '3',
            'max': '10'
        }),
        help_text='Maximum failed login attempts before lockout'
    )
    
    lockout_duration = forms.IntegerField(
        initial=15,
        min_value=5,
        max_value=60,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '5',
            'max': '60'
        }),
        help_text='Account lockout duration in minutes'
    )
    
    enable_two_factor = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'disabled': True
        }),
        help_text='Enable two-factor authentication (coming soon)'
    )
    
    log_user_activity = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text='Log user activity for security auditing'
    )
    
    require_logout_confirmation = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text='Require confirmation before logging out'
    )
    
    auto_logout_inactive = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text='Automatically log out inactive users'
    )

class BusinessGoalForm(forms.ModelForm):
    """Form for creating/editing business goals"""
    
    class Meta:
        model = BusinessGoal
        fields = [
            'title', 'description', 'goal_type', 'period',
            'target_value', 'start_date', 'end_date'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter goal title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe your goal...'
            }),
            'goal_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'period': forms.Select(attrs={
                'class': 'form-select'
            }),
            'target_value': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'end_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            })
        }

class BusinessAlertForm(forms.ModelForm):
    """Form for creating business alerts"""
    
    class Meta:
        model = BusinessAlert
        fields = [
            'title', 'message', 'alert_type', 'priority',
            'for_owners', 'for_managers', 'for_all_staff',
            'expires_at'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Alert title'
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Alert message...'
            }),
            'alert_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'priority': forms.Select(attrs={
                'class': 'form-select'
            }),
            'expires_at': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            })
        }

class QuickActionForm(forms.ModelForm):
    """Form for creating quick actions"""
    
    class Meta:
        model = QuickAction
        fields = [
            'title', 'description', 'icon', 'action_type',
            'url', 'css_class', 'required_role', 'display_order'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Action title'
            }),
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Brief description'
            }),
            'icon': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'fas fa-plus'
            }),
            'action_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'url': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '/path/to/action'
            }),
            'css_class': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'btn-primary'
            }),
            'required_role': forms.Select(attrs={
                'class': 'form-select'
            }),
            'display_order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            })
        }

class DashboardWidgetForm(forms.ModelForm):
    """Form for dashboard widgets"""
    
    class Meta:
        model = DashboardWidget
        fields = [
            'title', 'widget_type', 'row', 'column', 'width', 'height',
            'data_source', 'refresh_interval', 'visible_to_roles'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Widget title'
            }),
            'widget_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'row': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'column': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'width': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '12'
            }),
            'height': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '100'
            }),
            'data_source': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Data source URL or method'
            }),
            'refresh_interval': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '30'
            }),
            'visible_to_roles': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'owner,manager,supervisor'
            })
        }