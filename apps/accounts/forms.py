from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Field, HTML, Div
from crispy_forms.bootstrap import FormActions
from phonenumber_field.formfields import PhoneNumberField
from .models import UserProfile, Business, BusinessSettings, BusinessVerification
from django.utils import timezone
import os

class UserRegistrationForm(UserCreationForm):
    """Enhanced user registration form"""
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'First Name', 'class': 'form-control'})
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'Last Name', 'class': 'form-control'})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'placeholder': 'Email Address', 'class': 'form-control'})
    )
    phone = PhoneNumberField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': '+254712345678', 'class': 'form-control'})
    )
    
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={'placeholder': 'Username', 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add CSS classes to password fields
        self.fields['password1'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Password'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Confirm Password'})
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('first_name', css_class='form-group col-md-6 mb-3'),
                Column('last_name', css_class='form-group col-md-6 mb-3'),
            ),
            Row(
                Column('username', css_class='form-group col-md-6 mb-3'),
                Column('email', css_class='form-group col-md-6 mb-3'),
            ),
            Field('phone', css_class='mb-3'),
            Row(
                Column('password1', css_class='form-group col-md-6 mb-3'),
                Column('password2', css_class='form-group col-md-6 mb-3'),
            ),
            HTML('<div class="form-check mb-3"><input class="form-check-input" type="checkbox" required id="terms"><label class="form-check-label" for="terms">I agree to the <a href="#" target="_blank">Terms of Service</a> and <a href="#" target="_blank">Privacy Policy</a></label></div>'),
            FormActions(
                Submit('submit', 'Create Account', css_class='btn btn-primary btn-lg w-100')
            )
        )
    
    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise ValidationError("Email address already exists.")
        return email

class UserProfileForm(forms.ModelForm):
    """User profile form - aligned with UserProfile model"""
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    email = forms.EmailField(required=True)
    
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
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email
        
        # Update widget attributes for phone field
        if hasattr(self.fields['phone'], 'widget'):
            self.fields['phone'].widget.attrs.update({'class': 'form-control'})
        
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
        fields = ['name', 'business_type', 'description', 'phone', 'email', 'website']
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
            'website': forms.URLInput(attrs={
                'placeholder': 'https://yourwebsite.com (optional)',
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
        self.fields['website'].required = False
        
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
            Field('website', css_class='mb-3'),
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
    
    def save(self, commit=True):
        """Save the business and handle the location field"""
        business = super().save(commit=False)
        
        # Handle location - you can store it in a field that exists in your model
        # Based on your model, it looks like you have fields from Address and ContactInfo mixins
        location = self.cleaned_data.get('location')
        if location:
            # If you have an address field in your Address mixin, use that
            # Otherwise, you might want to store it in description or create a location field
            if hasattr(business, 'address'):
                business.address = location
            elif hasattr(business, 'street_address'):
                business.street_address = location
            # If no address field exists, you might want to add location to description
            elif location and not business.description:
                business.description = f"Location: {location}"
            elif location and business.description:
                business.description = f"{business.description}\nLocation: {location}"
        
        if commit:
            business.save()
        return business

class BusinessSettingsForm(forms.ModelForm):
    """Business settings form - aligned with BusinessSettings model"""
    
    class Meta:
        model = BusinessSettings
        fields = [
            'sms_notifications', 'email_notifications', 'customer_sms_notifications',
            'auto_assign_attendants', 'require_customer_approval', 'send_service_reminders',
            'accept_cash', 'accept_card', 'accept_mpesa', 'require_payment_confirmation',
            'track_inventory', 'auto_reorder', 'low_stock_threshold',
            'daily_reports', 'weekly_reports', 'monthly_reports',
            'loyalty_program', 'customer_rating', 'customer_feedback'
        ]
        widgets = {
            'low_stock_threshold': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
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
                Column('sms_notifications', css_class='form-group col-md-4 mb-3'),
                Column('email_notifications', css_class='form-group col-md-4 mb-3'),
                Column('customer_sms_notifications', css_class='form-group col-md-4 mb-3'),
            ),
            HTML('<h5 class="mt-4 mb-3">Service Settings</h5>'),
            Row(
                Column('auto_assign_attendants', css_class='form-group col-md-4 mb-3'),
                Column('require_customer_approval', css_class='form-group col-md-4 mb-3'),
                Column('send_service_reminders', css_class='form-group col-md-4 mb-3'),
            ),
            HTML('<h5 class="mt-4 mb-3">Payment Settings</h5>'),
            Row(
                Column('accept_cash', css_class='form-group col-md-3 mb-3'),
                Column('accept_card', css_class='form-group col-md-3 mb-3'),
                Column('accept_mpesa', css_class='form-group col-md-3 mb-3'),
                Column('require_payment_confirmation', css_class='form-group col-md-3 mb-3'),
            ),
            HTML('<h5 class="mt-4 mb-3">Inventory Settings</h5>'),
            Row(
                Column('track_inventory', css_class='form-group col-md-4 mb-3'),
                Column('auto_reorder', css_class='form-group col-md-4 mb-3'),
                Column('low_stock_threshold', css_class='form-group col-md-4 mb-3'),
            ),
            HTML('<h5 class="mt-4 mb-3">Reports</h5>'),
            Row(
                Column('daily_reports', css_class='form-group col-md-4 mb-3'),
                Column('weekly_reports', css_class='form-group col-md-4 mb-3'),
                Column('monthly_reports', css_class='form-group col-md-4 mb-3'),
            ),
            HTML('<h5 class="mt-4 mb-3">Customer Features</h5>'),
            Row(
                Column('loyalty_program', css_class='form-group col-md-4 mb-3'),
                Column('customer_rating', css_class='form-group col-md-4 mb-3'),
                Column('customer_feedback', css_class='form-group col-md-4 mb-3'),
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