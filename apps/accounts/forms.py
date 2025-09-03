from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Field, HTML, Div
from crispy_forms.bootstrap import FormActions
from phonenumber_field.formfields import PhoneNumberField
from .models import UserProfile, Business, BusinessSettings, BusinessVerification
from apps.core.tenant_models import Tenant
from apps.core.fields import EnhancedPhoneNumberField, FlexibleUsernameField, FlexibleEmailField
from apps.core.widgets import PhoneNumberWidget
from django.utils import timezone
from django.utils.text import slugify
import re
import os
import random
import string

class UserRegistrationForm(forms.ModelForm):
    """User registration form with auto-generated username"""
    
    # Full name field - user enters their actual name
    full_name = forms.CharField(
        max_length=150,
        required=True,
        label='Full Name',
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter your full name', 
            'class': 'form-control',
            'autocomplete': 'name'
        }),
        help_text='Enter your full name (e.g., John Smith). We\'ll create a unique username for you automatically.'
    )
    
    def generate_username(self, full_name):
        """Generate a unique username with 'autowash' + name letters + random characters"""
        # Clean the full name - remove spaces and special characters, keep only letters
        clean_name = re.sub(r'[^a-zA-Z]', '', full_name.lower())
        
        # Take first 3-4 letters from the name (or all if name is short)
        name_part = clean_name[:4] if len(clean_name) >= 4 else clean_name
        
        # Generate random suffix (4 characters)
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
        
        # Create base username: autowash + name_part + random_suffix
        base_username = f"autowash{name_part}{random_suffix}"
        
        # Ensure uniqueness by checking if username exists
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            # If exists, add a number
            username = f"{base_username}{counter}"
            counter += 1
            
        return username
    
    # Use flexible email field
    email = FlexibleEmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'placeholder': 'your@email.com', 
            'class': 'form-control',
            'autocomplete': 'email'
        }),
        help_text='We\'ll send you a verification code at this email address.'
    )
    
    # Use enhanced phone number field with country code selection
    phone = EnhancedPhoneNumberField(
        required=True,
        widget=PhoneNumberWidget(),
        help_text='Select your country code and enter your phone number.'
    )
    
    # Optional fields for better user experience
    first_name = forms.CharField(
        max_length=30, 
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'First name (optional)', 
            'class': 'form-control',
            'autocomplete': 'given-name'
        }),
        help_text='Optional: If you prefer to keep names separate.'
    )
    
    last_name = forms.CharField(
        max_length=30, 
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Last name (optional)', 
            'class': 'form-control',
            'autocomplete': 'family-name'
        })
    )
    
    # Terms and conditions agreement
    terms = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'terms'
        }),
        error_messages={
            'required': 'You must agree to the Terms of Service and Privacy Policy to create an account.'
        }
    )
    
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name')  # Remove username from fields
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make form more user-friendly
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            HTML('<div class="mb-3"><small class="text-muted">All fields marked with * are required</small></div>'),
            Field('full_name', css_class='mb-3'),
            Field('email', css_class='mb-3'),
            Field('phone', css_class='mb-3'),
            Row(
                Column(Field('first_name'), css_class='col-md-6'),
                Column(Field('last_name'), css_class='col-md-6'),
                css_class='mb-3'
            ),
            Div(
                Field('terms', css_class='form-check-input'),
                HTML('<label class="form-check-label" for="terms">I agree to the <a href="/terms/" target="_blank">Terms of Service</a> and <a href="/privacy/" target="_blank">Privacy Policy</a></label>'),
                css_class='form-check mb-3'
            ),
            HTML('<div class="mb-3"><small class="text-muted">A unique username will be created for you automatically using "autowash" plus letters from your name.</small></div>'),
            FormActions(
                Submit('submit', 'Create Account', css_class='btn btn-primary btn-lg w-100')
            )
        )
    
    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise ValidationError("An account with this email address already exists.")
        return email
    
    def clean_full_name(self):
        full_name = self.cleaned_data['full_name']
        
        # Basic validation
        if not full_name:
            raise ValidationError("Full name is required.")
        
        # Trim whitespace
        full_name = full_name.strip()
        
        # Ensure it's not just spaces
        if not full_name:
            raise ValidationError('Full name cannot be empty or just spaces.')
        
        # Check length
        if len(full_name) < 2:
            raise ValidationError('Full name must be at least 2 characters long.')
        
        if len(full_name) > 150:
            raise ValidationError('Full name cannot be longer than 150 characters.')
        
        # Should contain at least some letters
        if not re.search(r'[a-zA-Z]', full_name):
            raise ValidationError('Full name must contain at least some letters.')
        
        return full_name
    
    def clean_terms(self):
        terms = self.cleaned_data.get('terms')
        if not terms:
            raise ValidationError('You must agree to the Terms of Service and Privacy Policy to create an account.')
        return terms

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            # Check if phone number is already registered
            from .models import UserProfile
            if UserProfile.objects.filter(phone=phone).exists():
                raise ValidationError("An account with this phone number already exists.")
        return phone
    
    def clean(self):
        cleaned_data = super().clean()
        full_name = cleaned_data.get('full_name')
        first_name = cleaned_data.get('first_name')
        last_name = cleaned_data.get('last_name')
        
        # Auto-populate first_name and last_name from full_name if not provided
        if full_name and full_name.strip():
            name_parts = full_name.strip().split()
            
            # If first_name and last_name are not provided, extract from full_name
            if not first_name and not last_name and len(name_parts) >= 1:
                cleaned_data['first_name'] = name_parts[0]
                if len(name_parts) > 1:
                    cleaned_data['last_name'] = ' '.join(name_parts[1:])
                else:
                    # If only one name provided, use it as first name
                    cleaned_data['last_name'] = ''
        
        return cleaned_data
    
    def save(self, commit=True):
        # Create user instance but don't save yet
        user = super().save(commit=False)
        
        # Generate username from full_name
        full_name = self.cleaned_data.get('full_name')
        if full_name:
            user.username = self.generate_username(full_name)
        
        if commit:
            user.save()
            
            # Create user profile with phone number
            phone = self.cleaned_data.get('phone')
            if phone:
                from .models import UserProfile
                UserProfile.objects.get_or_create(
                    user=user,
                    defaults={'phone': phone}
                )
            
        return user

class UserProfileForm(forms.ModelForm):
    """User profile form - aligned with UserProfile model"""
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    email = FlexibleEmailField(required=True)
    
    class Meta:
        model = UserProfile
        fields = [
            'phone', 'avatar', 'date_of_birth', 'gender', 'bio',
            'language', 'timezone', 'receive_sms', 'receive_email'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'language': forms.TextInput(attrs={'class': 'form-control'}),
            'timezone': forms.TextInput(attrs={'class': 'form-control'}),
            'avatar': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }
        field_classes = {
            'phone': EnhancedPhoneNumberField,
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email
        
        # Use enhanced phone number widget
        self.fields['phone'].widget = PhoneNumberWidget()
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h5 class="mb-3">Personal Information</h5>'),
            Row(
                Column('first_name', css_class='form-group col-md-6 mb-3'),
                Column('last_name', css_class='form-group col-md-6 mb-3'),
            ),
            Row(
                Column('email', css_class='form-group col-md-6 mb-3'),
                Column('phone', css_class='form-group col-md-6 mb-3'),
            ),
            Row(
                Column('date_of_birth', css_class='form-group col-md-4 mb-3'),
                Column('gender', css_class='form-group col-md-4 mb-3'),
                Column('avatar', css_class='form-group col-md-4 mb-3'),
            ),
            Field('bio', css_class='mb-3'),
            HTML('<h5 class="mt-4 mb-3">Preferences</h5>'),
            Row(
                Column('language', css_class='form-group col-md-6 mb-3'),
                Column('timezone', css_class='form-group col-md-6 mb-3'),
            ),
            Row(
                Column('receive_sms', css_class='form-group col-md-6 mb-3'),
                Column('receive_email', css_class='form-group col-md-6 mb-3'),
            ),
            FormActions(
                Submit('submit', 'Update Profile', css_class='btn btn-primary')
            )
        )
    
    def save(self, commit=True):
        profile = super().save(commit=commit)
        if commit:
            # Update User model fields
            profile.user.first_name = self.cleaned_data['first_name']
            profile.user.last_name = self.cleaned_data['last_name']
            profile.user.email = self.cleaned_data['email']
            profile.user.save()
        return profile

class BusinessRegistrationForm(forms.ModelForm):
    """Business registration form with account password setup"""
    
    # Add account password field (since it wasn't set during registration)
    account_password = forms.CharField(
        max_length=128,
        required=True,
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Create your account password',
            'class': 'form-control',
            'autocomplete': 'new-password'
        }),
        help_text='This will be your login password'
    )
    
    account_password_confirm = forms.CharField(
        max_length=128,
        required=True,
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Confirm account password',
            'class': 'form-control',
            'autocomplete': 'new-password'
        })
    )
    
    # Override phone field to use PhoneNumberField
    phone = PhoneNumberField(
        region='KE',  # Kenya region
        widget=forms.TextInput(attrs={
            'placeholder': '712345678',
            'class': 'form-control'
        })
    )
    
    class Meta:
        model = Tenant
        fields = ['name', 'business_type', 'phone', 'email']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Your Business Name', 
                'class': 'form-control',
            }),
            'business_type': forms.Select(attrs={'class': 'form-select'}),
            'email': forms.EmailInput(attrs={
                'placeholder': 'business@email.com',
                'class': 'form-control'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make all fields required
        for field_name in self.fields:
            self.fields[field_name].required = True
        
        # Set up crispy forms layout
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Field('name', css_class='mb-3'),
            Field('business_type', css_class='mb-3'),
            Row(
                Column('phone', css_class='form-group col-md-6 mb-3'),
                Column('email', css_class='form-group col-md-6 mb-3'),
            ),
            HTML('<hr class="my-4"><h6 class="text-muted mb-3">Set Your Account Password</h6>'),
            Field('account_password', css_class='mb-3'),
            Field('account_password_confirm', css_class='mb-3'),
            FormActions(
                Submit('submit', 'Complete Registration', css_class='btn btn-primary btn-lg w-100')
            )
        )
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name:
            raise ValidationError("Business name is required.")
        # Relaxed validation - just check if name is too similar, not exact match
        return name
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        # Relaxed validation - allow same email for different businesses
        return email
    
    def clean_account_password(self):
        password = self.cleaned_data.get('account_password')
        if password and len(password) < 6:
            raise ValidationError("Account password must be at least 6 characters.")
        return password
    
    def clean_account_password_confirm(self):
        password = self.cleaned_data.get('account_password')
        password_confirm = self.cleaned_data.get('account_password_confirm')
        if password and password_confirm and password != password_confirm:
            raise ValidationError("Account passwords don't match.")
        return password_confirm
    
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
            while Tenant.objects.filter(subdomain__iexact=subdomain).exists():
                subdomain = f"{original_subdomain}{counter}"
                counter += 1
            
            # Add subdomain to cleaned data
            cleaned_data['subdomain'] = subdomain
        
        return cleaned_data
        
    def save(self, commit=True):
        """Save the tenant and handle auto-generated fields"""
        tenant = super().save(commit=False)
        
        # Set the auto-generated subdomain
        subdomain = self.cleaned_data.get('subdomain')
        if subdomain:
            tenant.subdomain = subdomain
        
        # Set default values for other fields
        if not tenant.description:
            tenant.description = f"{tenant.name} - {tenant.get_business_type_display()}"
        
        if commit:
            tenant.save()
        return tenant

class BusinessSettingsForm(forms.ModelForm):
    """Business settings form - aligned with TenantSettings model"""
    
    class Meta:
        model = BusinessSettings  # This is aliased to TenantSettings
        fields = [
            'sms_notifications', 'email_notifications',
            'enable_loyalty_program', 'enable_online_booking', 'enable_mobile_app',
            'primary_color', 'secondary_color'
        ]
        widgets = {
            'primary_color': forms.TextInput(attrs={'type': 'color', 'class': 'form-control'}),
            'secondary_color': forms.TextInput(attrs={'type': 'color', 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add Bootstrap classes to all boolean fields
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-check-input'})
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h5 class="mb-3">Notifications</h5>'),
            Row(
                Column('sms_notifications', css_class='form-group col-md-6 mb-3'),
                Column('email_notifications', css_class='form-group col-md-6 mb-3'),
            ),
            HTML('<h5 class="mt-4 mb-3">Feature Settings</h5>'),
            Row(
                Column('enable_loyalty_program', css_class='form-group col-md-4 mb-3'),
                Column('enable_online_booking', css_class='form-group col-md-4 mb-3'),
                Column('enable_mobile_app', css_class='form-group col-md-4 mb-3'),
            ),
            HTML('<h5 class="mt-4 mb-3">Branding</h5>'),
            Row(
                Column('primary_color', css_class='form-group col-md-6 mb-3'),
                Column('secondary_color', css_class='form-group col-md-6 mb-3'),
            ),
            FormActions(
                Submit('submit', 'Save Settings', css_class='btn btn-primary')
            )
        )


def validate_file_size(value):
    """Validate that file size is not larger than 5MB"""
    limit = 5 * 1024 * 1024  # 5MB
    if value.size > limit:
        raise ValidationError('File too large. Size should not exceed 5MB.')

def validate_file_extension(value):
    """Validate file extension"""
    ext = os.path.splitext(value.name)[1].lower()
    valid_extensions = ['.pdf', '.jpg', '.jpeg', '.png']
    if ext not in valid_extensions:
        raise ValidationError('Unsupported file extension. Please upload PDF, JPG, or PNG files.')

class BusinessVerificationForm(forms.ModelForm):
    """Business verification form - aligned with BusinessVerification model"""
    
    business_license = forms.FileField(
        required=True,
        validators=[validate_file_size, validate_file_extension],
        widget=forms.FileInput(attrs={
            'accept': '.pdf,.jpg,.jpeg,.png',
            'class': 'form-control'
        }),
        help_text='Upload your business license or certificate of incorporation (PDF, JPG, PNG - Max 5MB)'
    )
    
    tax_certificate = forms.FileField(
        required=True,
        validators=[validate_file_size, validate_file_extension],
        widget=forms.FileInput(attrs={
            'accept': '.pdf,.jpg,.jpeg,.png',
            'class': 'form-control'
        }),
        help_text='Upload your KRA PIN certificate (PDF, JPG, PNG - Max 5MB)'
    )
    
    id_document = forms.FileField(
        required=True,
        validators=[validate_file_size, validate_file_extension],
        widget=forms.FileInput(attrs={
            'accept': '.pdf,.jpg,.jpeg,.png',
            'class': 'form-control'
        }),
        help_text='Upload a valid ID document - National ID, Passport, or Driver\'s License (PDF, JPG, PNG - Max 5MB)'
    )
    
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3, 
            'placeholder': 'Any additional information you\'d like to provide (optional)',
            'class': 'form-control'
        }),
        help_text='Optional additional information about your business'
    )
    
    class Meta:
        model = BusinessVerification
        fields = ['business_license', 'tax_certificate', 'id_document', 'notes']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # If instance exists and has files, make them not required for update
        if self.instance and self.instance.pk:
            if self.instance.business_license:
                self.fields['business_license'].required = False
                self.fields['business_license'].help_text = f'Current: {self.instance.business_license.name} (upload new file to replace)'
            
            if self.instance.tax_certificate:
                self.fields['tax_certificate'].required = False
                self.fields['tax_certificate'].help_text = f'Current: {self.instance.tax_certificate.name} (upload new file to replace)'
            
            if self.instance.id_document:
                self.fields['id_document'].required = False
                self.fields['id_document'].help_text = f'Current: {self.instance.id_document.name} (upload new file to replace)'
        
        # Set up crispy forms layout
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_enctype = 'multipart/form-data'
        self.helper.layout = Layout(
            HTML('<div class="alert alert-info mb-4"><i class="fas fa-info-circle"></i> Please upload clear, legible copies of your documents. Accepted formats: PDF, JPG, PNG (Max 5MB each)</div>'),
            Field('business_license', css_class='mb-4'),
            Field('tax_certificate', css_class='mb-4'),
            Field('id_document', css_class='mb-4'),
            Field('notes', css_class='mb-4'),
            FormActions(
                Submit('submit', 'Submit for Verification', css_class='btn btn-primary btn-lg')
            )
        )
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Ensure at least the required documents are present (either existing or new)
        required_fields = ['business_license', 'tax_certificate', 'id_document']
        
        for field_name in required_fields:
            # Check if we have either a new file or existing file
            new_file = cleaned_data.get(field_name)
            existing_file = getattr(self.instance, field_name, None) if self.instance else None
            
            if not new_file and not existing_file:
                self.add_error(field_name, f'{field_name.replace("_", " ").title()} is required.')
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Update status when files are uploaded
        if any([self.cleaned_data.get('business_license'),
                self.cleaned_data.get('tax_certificate'),
                self.cleaned_data.get('id_document')]):
            instance.status = 'in_review'
            if not instance.submitted_at:
                instance.submitted_at = timezone.now()
        
        if commit:
            instance.save()
        
        return instance