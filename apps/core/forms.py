from django import forms
from django.core.validators import EmailValidator
from apps.core.tenant_models import TenantSettings
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Field, HTML, Div, Fieldset
from crispy_forms.bootstrap import FormActions

# Import SMS form from messaging app
try:
    from messaging.forms import TenantSMSSettingsForm
except ImportError:
    # Fallback if messaging app is not available
    TenantSMSSettingsForm = None


# Create alias for SMS settings form
SMSManagementForm = TenantSMSSettingsForm


class TenantSettingsForm(forms.ModelForm):
    """Form for tenant settings"""
    
    class Meta:
        model = TenantSettings
        fields = [
            # Basic Business Settings
            'business_name', 'tagline', 'default_currency', 'timezone', 'tax_number',
            
            # Contact Settings
            'contact_phone', 'contact_email', 'contact_address', 'po_box', 'website_url',
            
            # Social Media
            'facebook_url', 'instagram_url', 'twitter_url',
            
            # Invoice Customization
            'invoice_terms_and_conditions', 'invoice_payment_details',
            
            # Branding
            'primary_color', 'secondary_color', 'logo_url', 'business_logo', 'receipt_footer',
        ]
        
        widgets = {
            'business_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your Business Name'
            }),
            'tagline': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your business tagline or slogan'
            }),
            'default_currency': forms.Select(attrs={'class': 'form-select'}),
            'timezone': forms.Select(attrs={'class': 'form-select'}),
            'tax_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'KRA PIN / Tax Number'
            }),
            'contact_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+254712345678'
            }),
            'contact_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'contact@yourbusiness.com'
            }),
            'contact_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Your business address'
            }),
            'po_box': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'P.O. BOX 1267-30100'
            }),
            'website_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://yourwebsite.com'
            }),
            'facebook_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://facebook.com/yourpage'
            }),
            'instagram_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://instagram.com/yourprofile'
            }),
            'twitter_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://twitter.com/yourprofile'
            }),
            'invoice_terms_and_conditions': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Terms and conditions for invoices, receipts, and quotations'
            }),
            'invoice_payment_details': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Payment details and bank information'
            }),
            'primary_color': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'color'
            }),
            'secondary_color': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'color'
            }),
            'logo_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://yourlogo.com/logo.png'
            }),
            'business_logo': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'receipt_footer': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Custom footer text for receipts and invoices (e.g., Thank you for your business!)'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set comprehensive timezone choices
        timezone_choices = [
            # Africa
            ('Africa/Abidjan', 'Africa/Abidjan (GMT)'),
            ('Africa/Accra', 'Africa/Accra (GMT)'),
            ('Africa/Addis_Ababa', 'Africa/Addis_Ababa (EAT)'),
            ('Africa/Algiers', 'Africa/Algiers (CET)'),
            ('Africa/Cairo', 'Africa/Cairo (EET)'),
            ('Africa/Casablanca', 'Africa/Casablanca (WET)'),
            ('Africa/Dar_es_Salaam', 'Africa/Dar_es_Salaam (EAT)'),
            ('Africa/Johannesburg', 'Africa/Johannesburg (SAST)'),
            ('Africa/Kampala', 'Africa/Kampala (EAT)'),
            ('Africa/Khartoum', 'Africa/Khartoum (CAT)'),
            ('Africa/Lagos', 'Africa/Lagos (WAT)'),
            ('Africa/Nairobi', 'Africa/Nairobi (EAT)'),
            ('Africa/Tunis', 'Africa/Tunis (CET)'),
            
            # Asia
            ('Asia/Bahrain', 'Asia/Bahrain (AST)'),
            ('Asia/Bangkok', 'Asia/Bangkok (ICT)'),
            ('Asia/Dubai', 'Asia/Dubai (GST)'),
            ('Asia/Hong_Kong', 'Asia/Hong_Kong (HKT)'),
            ('Asia/Jakarta', 'Asia/Jakarta (WIB)'),
            ('Asia/Kolkata', 'Asia/Kolkata (IST)'),
            ('Asia/Kuala_Lumpur', 'Asia/Kuala_Lumpur (MYT)'),
            ('Asia/Manila', 'Asia/Manila (PHT)'),
            ('Asia/Riyadh', 'Asia/Riyadh (AST)'),
            ('Asia/Shanghai', 'Asia/Shanghai (CST)'),
            ('Asia/Singapore', 'Asia/Singapore (SGT)'),
            ('Asia/Tokyo', 'Asia/Tokyo (JST)'),
            
            # Europe
            ('Europe/Amsterdam', 'Europe/Amsterdam (CET)'),
            ('Europe/Berlin', 'Europe/Berlin (CET)'),
            ('Europe/Brussels', 'Europe/Brussels (CET)'),
            ('Europe/London', 'Europe/London (GMT)'),
            ('Europe/Madrid', 'Europe/Madrid (CET)'),
            ('Europe/Paris', 'Europe/Paris (CET)'),
            ('Europe/Rome', 'Europe/Rome (CET)'),
            ('Europe/Stockholm', 'Europe/Stockholm (CET)'),
            ('Europe/Zurich', 'Europe/Zurich (CET)'),
            
            # Americas
            ('America/New_York', 'America/New_York (EST)'),
            ('America/Chicago', 'America/Chicago (CST)'),
            ('America/Denver', 'America/Denver (MST)'),
            ('America/Los_Angeles', 'America/Los_Angeles (PST)'),
            ('America/Toronto', 'America/Toronto (EST)'),
            ('America/Vancouver', 'America/Vancouver (PST)'),
            ('America/Sao_Paulo', 'America/Sao_Paulo (BRT)'),
            ('America/Mexico_City', 'America/Mexico_City (CST)'),
            
            # Pacific/Oceania
            ('Pacific/Auckland', 'Pacific/Auckland (NZST)'),
            ('Australia/Sydney', 'Australia/Sydney (AEST)'),
            ('Australia/Melbourne', 'Australia/Melbourne (AEST)'),
            ('Australia/Perth', 'Australia/Perth (AWST)'),
            
            # UTC
            ('UTC', 'UTC (Coordinated Universal Time)'),
        ]
        
        self.fields['timezone'].choices = timezone_choices
        
        # Set currency choices
        currency_choices = [
            ('KES', 'Kenyan Shilling (KES)'),
            ('USD', 'US Dollar (USD)'),
            ('EUR', 'Euro (EUR)'),
            ('GBP', 'British Pound (GBP)'),
            ('ZAR', 'South African Rand (ZAR)'),
            ('NGN', 'Nigerian Naira (NGN)'),
            ('GHS', 'Ghanaian Cedi (GHS)'),
            ('UGX', 'Ugandan Shilling (UGX)'),
            ('TZS', 'Tanzanian Shilling (TZS)'),
            ('RWF', 'Rwandan Franc (RWF)'),
            ('ETB', 'Ethiopian Birr (ETB)'),
            ('MAD', 'Moroccan Dirham (MAD)'),
            ('EGP', 'Egyptian Pound (EGP)'),
        ]
        
        self.fields['default_currency'].choices = currency_choices


class NotificationSettingsForm(forms.ModelForm):
    """Form for notification settings"""
    
    class Meta:
        model = TenantSettings
        fields = [
            # General Notification Settings
            'sms_notifications', 'email_notifications', 'whatsapp_notifications', 'push_notifications',
            
            # Customer Notifications
            'customer_booking_confirmations', 'customer_payment_receipts',
            'customer_service_reminders', 'customer_marketing_messages',
            'notify_booking_confirmation', 'notify_service_reminder', 'notify_service_complete',
            
            # Staff Notifications
            'staff_new_bookings', 'staff_payment_alerts', 'staff_daily_summaries',
            
            # Auto actions
            'auto_payment_confirmation',
        ]
        
        widgets = {
            'sms_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'whatsapp_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'push_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'customer_booking_confirmations': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'customer_payment_receipts': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'customer_service_reminders': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'customer_marketing_messages': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_booking_confirmation': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_service_reminder': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_service_complete': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'staff_new_bookings': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'staff_payment_alerts': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'staff_daily_summaries': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'auto_payment_confirmation': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class PaymentSettingsForm(forms.ModelForm):
    """Form for payment settings"""
    
    class Meta:
        model = TenantSettings
        fields = [
            'auto_payment_confirmation', 'require_payment_before_service',
            'default_tax_rate', 'mpesa_auto_confirm', 'tax_number', 'tax_inclusive_pricing',
            'accept_cash', 'accept_mpesa', 'accept_card', 'accept_bank_transfer',
        ]
        
        widgets = {
            'auto_payment_confirmation': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'require_payment_before_service': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'mpesa_auto_confirm': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'tax_inclusive_pricing': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'accept_cash': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'accept_mpesa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'accept_card': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'accept_bank_transfer': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'default_tax_rate': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '100',
                'step': '0.01',
                'placeholder': '16.00'
            }),
            'tax_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your business tax/VAT number'
            }),
        }


class ServiceSettingsForm(forms.ModelForm):
    """Form for service settings"""
    
    class Meta:
        model = TenantSettings
        fields = [
            'auto_assign_services', 'require_service_confirmation', 'service_buffer_time',
            'default_service_duration', 'max_advance_booking_days', 'min_advance_booking_hours',
            'allow_online_booking', 'require_customer_phone', 'allow_same_day_booking', 
            'auto_confirm_bookings',
        ]
        
        widgets = {
            'auto_assign_services': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'require_service_confirmation': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'service_buffer_time': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '120',
                'placeholder': '15'
            }),
            'default_service_duration': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '5',
                'max': '480',
                'placeholder': '30'
            }),
            'max_advance_booking_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '365',
                'placeholder': '30'
            }),
            'min_advance_booking_hours': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '72',
                'placeholder': '2'
            }),
            'allow_online_booking': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'require_customer_phone': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'allow_same_day_booking': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'auto_confirm_bookings': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class FeatureSettingsForm(forms.ModelForm):
    """Form for feature flags"""
    
    class Meta:
        model = TenantSettings
        fields = [
            'enable_loyalty_program', 'enable_online_booking', 'enable_mobile_app',
            'enable_pos_integration', 'enable_inventory_tracking', 'enable_employee_attendance',
        ]
        
        widgets = {
            'enable_loyalty_program': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'enable_online_booking': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'enable_mobile_app': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'enable_pos_integration': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'enable_inventory_tracking': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'enable_employee_attendance': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class BackupSettingsForm(forms.ModelForm):
    """Form for backup settings"""
    
    class Meta:
        model = TenantSettings
        fields = [
            'auto_backup_enabled', 'backup_frequency', 'backup_retention_days',
            'backup_email_notifications', 'backup_to_email', 'backup_to_cloud',
        ]
        
        widgets = {
            'auto_backup_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'backup_frequency': forms.Select(attrs={'class': 'form-select'}),
            'backup_retention_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '365',
                'placeholder': '30'
            }),
            'backup_email_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'backup_to_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'backup@yourbusiness.com'
            }),
            'backup_to_cloud': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class BusinessHoursForm(forms.ModelForm):
    """Form for business hours"""
    
    class Meta:
        model = TenantSettings
        fields = [
            'monday_is_open', 'monday_open', 'monday_close',
            'tuesday_is_open', 'tuesday_open', 'tuesday_close',
            'wednesday_is_open', 'wednesday_open', 'wednesday_close',
            'thursday_is_open', 'thursday_open', 'thursday_close',
            'friday_is_open', 'friday_open', 'friday_close',
            'saturday_is_open', 'saturday_open', 'saturday_close',
            'sunday_is_open', 'sunday_open', 'sunday_close',
        ]
        
        widgets = {
            'monday_is_open': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'monday_open': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'monday_close': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'tuesday_is_open': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'tuesday_open': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'tuesday_close': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'wednesday_is_open': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'wednesday_open': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'wednesday_close': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'thursday_is_open': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'thursday_open': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'thursday_close': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'friday_is_open': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'friday_open': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'friday_close': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'saturday_is_open': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'saturday_open': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'saturday_close': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'sunday_is_open': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'sunday_open': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'sunday_close': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
        }


class CreateBackupForm(forms.Form):
    """Form for creating a backup"""
    backup_type = forms.ChoiceField(
        choices=[
            ('full', 'Full Backup'),
            ('partial', 'Partial Backup'),
        ],
        widget=forms.RadioSelect(),
        initial='full'
    )
    
    backup_format = forms.ChoiceField(
        choices=[
            ('sql', 'SQL Database Dump'),
            ('json', 'JSON Export'),
            ('excel', 'Excel Spreadsheet'),
            ('csv', 'CSV Files'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'}),
        initial='sql'
    )
    
    # For partial backups
    include_customers = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    include_services = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    include_payments = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    include_employees = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    include_inventory = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    # Email backup
    email_backup = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    email_address = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'your@email.com'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        email_backup = cleaned_data.get('email_backup')
        email_address = cleaned_data.get('email_address')
        
        if email_backup and not email_address:
            raise forms.ValidationError("Email address is required when email backup is enabled.")
        
        # For partial backups, at least one table must be selected
        backup_type = cleaned_data.get('backup_type')
        if backup_type == 'partial':
            partial_fields = [
                'include_customers', 'include_services', 'include_payments',
                'include_employees', 'include_inventory'
            ]
            if not any(cleaned_data.get(field) for field in partial_fields):
                raise forms.ValidationError("For partial backups, you must select at least one data type to include.")
        
        return cleaned_data
