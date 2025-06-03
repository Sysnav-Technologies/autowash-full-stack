from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Field, HTML, Div
from crispy_forms.bootstrap import FormActions
from phonenumber_field.formfields import PhoneNumberField
from .models import UserProfile, Business, BusinessSettings, BusinessVerification

class UserRegistrationForm(UserCreationForm):
    """Enhanced user registration form"""
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'First Name'})
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'Last Name'})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'placeholder': 'Email Address'})
    )
    phone = PhoneNumberField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': '+254712345678'})
    )
    
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={'placeholder': 'Username'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('first_name', css_class='form-group col-md-6'),
                Column('last_name', css_class='form-group col-md-6'),
            ),
            Row(
                Column('username', css_class='form-group col-md-6'),
                Column('email', css_class='form-group col-md-6'),
            ),
            'phone',
            Row(
                Column('password1', css_class='form-group col-md-6'),
                Column('password2', css_class='form-group col-md-6'),
            ),
            HTML('<div class="form-check mb-3"><input class="form-check-input" type="checkbox" required id="terms"><label class="form-check-label" for="terms">I agree to the <a href="#" target="_blank">Terms of Service</a> and <a href="#" target="_blank">Privacy Policy</a></label></div>'),
            FormActions(
                Submit('submit', 'Create Account', css_class='btn btn-primary btn-block')
            )
        )
    
    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise ValidationError("Email address already exists.")
        return email

class UserProfileForm(forms.ModelForm):
    """User profile form"""
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
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'bio': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h5>Personal Information</h5>'),
            Row(
                Column('first_name', css_class='form-group col-md-6'),
                Column('last_name', css_class='form-group col-md-6'),
            ),
            Row(
                Column('email', css_class='form-group col-md-6'),
                Column('phone', css_class='form-group col-md-6'),
            ),
            Row(
                Column('date_of_birth', css_class='form-group col-md-4'),
                Column('gender', css_class='form-group col-md-4'),
                Column('avatar', css_class='form-group col-md-4'),
            ),
            'bio',
            HTML('<h5 class="mt-4">Preferences</h5>'),
            Row(
                Column('language', css_class='form-group col-md-6'),
                Column('timezone', css_class='form-group col-md-6'),
            ),
            Row(
                Column('receive_sms', css_class='form-group col-md-6'),
                Column('receive_email', css_class='form-group col-md-6'),
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
    """Minimal Business registration form for debugging"""
    
    class Meta:
        model = Business
        fields = ['name', 'business_type']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Your Business Name', 
                'class': 'form-control',
                'required': True
            }),
            'business_type': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        print(f"=== FORM INIT ===")
        print(f"Form fields: {list(self.fields.keys())}")
        
        # Make sure required fields are marked
        self.fields['name'].required = True
        self.fields['business_type'].required = True
        
        print(f"Name field: {self.fields['name']}")
        print(f"Business type field: {self.fields['business_type']}")
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        print(f"=== CLEANING NAME: {name} ===")
        if not name:
            raise ValidationError("Business name is required.")
        return name
    
    def clean(self):
        cleaned_data = super().clean()
        print(f"=== FORM CLEAN ===")
        print(f"Cleaned data: {cleaned_data}")
        return cleaned_data

class BusinessSettingsForm(forms.ModelForm):
    """Business settings form"""
    
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
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h5>Notifications</h5>'),
            Row(
                Column('sms_notifications', css_class='form-group col-md-4'),
                Column('email_notifications', css_class='form-group col-md-4'),
                Column('customer_sms_notifications', css_class='form-group col-md-4'),
            ),
            HTML('<h5 class="mt-4">Service Settings</h5>'),
            Row(
                Column('auto_assign_attendants', css_class='form-group col-md-4'),
                Column('require_customer_approval', css_class='form-group col-md-4'),
                Column('send_service_reminders', css_class='form-group col-md-4'),
            ),
            HTML('<h5 class="mt-4">Payment Settings</h5>'),
            Row(
                Column('accept_cash', css_class='form-group col-md-3'),
                Column('accept_card', css_class='form-group col-md-3'),
                Column('accept_mpesa', css_class='form-group col-md-3'),
                Column('require_payment_confirmation', css_class='form-group col-md-3'),
            ),
            HTML('<h5 class="mt-4">Inventory Settings</h5>'),
            Row(
                Column('track_inventory', css_class='form-group col-md-4'),
                Column('auto_reorder', css_class='form-group col-md-4'),
                Column('low_stock_threshold', css_class='form-group col-md-4'),
            ),
            HTML('<h5 class="mt-4">Reports</h5>'),
            Row(
                Column('daily_reports', css_class='form-group col-md-4'),
                Column('weekly_reports', css_class='form-group col-md-4'),
                Column('monthly_reports', css_class='form-group col-md-4'),
            ),
            HTML('<h5 class="mt-4">Customer Features</h5>'),
            Row(
                Column('loyalty_program', css_class='form-group col-md-4'),
                Column('customer_rating', css_class='form-group col-md-4'),
                Column('customer_feedback', css_class='form-group col-md-4'),
            ),
            FormActions(
                Submit('submit', 'Save Settings', css_class='btn btn-primary')
            )
        )

class BusinessVerificationForm(forms.ModelForm):
    """Business verification form"""
    
    class Meta:
        model = BusinessVerification
        fields = ['business_license', 'tax_certificate', 'id_document', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Additional information (optional)'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<div class="alert alert-info"><i class="fas fa-info-circle"></i> Please upload clear, legible copies of your documents. Accepted formats: PDF, JPG, PNG</div>'),
            'business_license',
            'tax_certificate',
            'id_document',
            'notes',
            FormActions(
                Submit('submit', 'Submit for Verification', css_class='btn btn-primary')
            )
        )