from django import forms
from django.core.exceptions import ValidationError
from apps.payments.models import PaymentGateway, PaymentMethod
from apps.core.tenant_models import Tenant
from apps.core.database_router import tenant_context
import requests


class TenantMPesaGatewayForm(forms.ModelForm):
    """Form for system admin to configure M-Pesa gateway for tenants"""
    
    tenant = forms.ModelChoiceField(
        queryset=Tenant.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="Select the tenant business to configure M-Pesa for",
        empty_label="Select a tenant business..."
    )
    
    test_connection = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Test the connection before saving"
    )
    
    class Meta:
        model = PaymentGateway
        fields = [
            'name',
            'is_active',
            'is_live',
            'consumer_key',
            'consumer_secret',
            'shortcode',
            'passkey',
            'webhook_url',
        ]
        
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'M-Pesa Gateway Name',
                'value': 'M-Pesa Daraja'
            }),
            'consumer_key': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter Consumer Key from Safaricom Daraja'
            }),
            'consumer_secret': forms.PasswordInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter Consumer Secret'
            }),
            'shortcode': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Business Shortcode (e.g., 174379)'
            }),
            'passkey': forms.PasswordInput(attrs={
                'class': 'form-control',
                'placeholder': 'Lipa Na M-Pesa Online Passkey'
            }),
            'webhook_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://your-domain.com/payments/webhook/mpesa/'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_live': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        
        labels = {
            'tenant': 'Business/Tenant',
            'name': 'Gateway Name',
            'consumer_key': 'Consumer Key',
            'consumer_secret': 'Consumer Secret',
            'shortcode': 'Business Shortcode',
            'passkey': 'Lipa Na M-Pesa Online Passkey',
            'webhook_url': 'Webhook URL',
            'is_active': 'Enable M-Pesa Payments',
            'is_live': 'Production Mode (Live Environment)',
        }
        
        help_texts = {
            'consumer_key': 'Get this from Safaricom Daraja app',
            'consumer_secret': 'Get this from Safaricom Daraja app',
            'shortcode': 'Business shortcode from Safaricom',
            'passkey': 'Lipa Na M-Pesa Online passkey from Safaricom',
            'webhook_url': 'URL where M-Pesa will send payment notifications',
            'is_live': 'Uncheck for sandbox/testing, check for production',
        }
    
    def __init__(self, *args, **kwargs):
        self.selected_tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        # If editing existing gateway and we know the tenant, hide tenant selection
        if self.instance.pk and self.selected_tenant:
            # Hide tenant field when editing (can't change tenant)
            self.fields['tenant'].widget = forms.HiddenInput()
            self.fields['tenant'].initial = self.selected_tenant
            self.fields['tenant'].required = False
        elif self.selected_tenant:
            # Pre-select tenant if provided
            self.fields['tenant'].initial = self.selected_tenant
        
        # Set default values for new instances
        if not self.instance.pk:
            self.fields['name'].initial = 'M-Pesa Daraja'
    
    def clean_shortcode(self):
        shortcode = self.cleaned_data.get('shortcode')
        if shortcode and not shortcode.isdigit():
            raise ValidationError("Shortcode must contain only numbers")
        if shortcode and len(shortcode) < 5:
            raise ValidationError("Shortcode must be at least 5 digits long")
        return shortcode
    
    def clean_consumer_key(self):
        consumer_key = self.cleaned_data.get('consumer_key')
        if consumer_key and len(consumer_key) < 10:
            raise ValidationError("Consumer key appears to be too short")
        return consumer_key
    
    def clean_webhook_url(self):
        webhook_url = self.cleaned_data.get('webhook_url')
        if webhook_url:
            # Allow HTTP for localhost/development environments
            if webhook_url.startswith('http://localhost') or webhook_url.startswith('http://127.0.0.1'):
                return webhook_url
            elif not webhook_url.startswith('https://'):
                raise ValidationError("Webhook URL must use HTTPS for security (HTTP is only allowed for localhost)")
        return webhook_url
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Check if M-Pesa gateway already exists for this tenant
        tenant = cleaned_data.get('tenant')
        if tenant and not self.instance.pk:
            with tenant_context(tenant):
                existing_gateway = PaymentGateway.objects.filter(gateway_type='mpesa').first()
                if existing_gateway:
                    raise ValidationError(
                        f"M-Pesa gateway already exists for {tenant.name}. "
                        f"Please edit the existing gateway instead."
                    )
        
        # Test connection if requested
        if cleaned_data.get('test_connection'):
            self._test_mpesa_connection(cleaned_data)
        
        return cleaned_data
    
    def _test_mpesa_connection(self, data):
        """Test M-Pesa connection with provided credentials"""
        try:
            consumer_key = data.get('consumer_key')
            consumer_secret = data.get('consumer_secret')
            is_live = data.get('is_live', False)
            
            if not all([consumer_key, consumer_secret]):
                return
            
            # Test authentication
            import base64
            credentials = base64.b64encode(
                f"{consumer_key}:{consumer_secret}".encode()
            ).decode()
            
            api_url = 'https://api.safaricom.co.ke' if is_live else 'https://sandbox.safaricom.co.ke'
            
            response = requests.get(
                f"{api_url}/oauth/v1/generate?grant_type=client_credentials",
                headers={
                    'Authorization': f'Basic {credentials}',
                    'Content-Type': 'application/json'
                },
                timeout=10
            )
            
            if response.status_code != 200:
                raise ValidationError(
                    "Failed to authenticate with M-Pesa. Please check the credentials."
                )
                
        except requests.RequestException:
            raise ValidationError(
                "Could not connect to M-Pesa API. Please check your internet connection."
            )
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Set gateway type and API details
        instance.gateway_type = 'mpesa'
        
        # Set API URL based on environment
        if instance.is_live:
            instance.api_url = 'https://api.safaricom.co.ke'
        else:
            instance.api_url = 'https://sandbox.safaricom.co.ke'
        
        # Set API credentials
        instance.api_key = instance.consumer_key
        instance.api_secret = instance.consumer_secret
        
        # Only save if commit is True and we're in the right context
        if commit:
            instance.save()
        
        return instance


class BulkGatewaySetupForm(forms.Form):
    """Form for setting up M-Pesa gateway for multiple tenants"""
    
    tenants = forms.ModelMultipleChoiceField(
        queryset=Tenant.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        help_text="Select tenants to configure M-Pesa for"
    )
    
    consumer_key = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter Consumer Key from Safaricom Daraja'
        }),
        help_text='Same consumer key will be used for all selected tenants'
    )
    
    consumer_secret = forms.CharField(
        max_length=255,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter Consumer Secret'
        }),
        help_text='Same consumer secret will be used for all selected tenants'
    )
    
    is_live = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Production Mode',
        help_text='Use production environment for all tenants'
    )
    
    webhook_base_url = forms.URLField(
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://your-domain.com'
        }),
        help_text='Base URL for webhook. Each tenant will get /business/{slug}/payments/webhook/mpesa/'
    )


class TenantGatewaySearchForm(forms.Form):
    """Form for searching and filtering tenant gateways"""
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by tenant name, gateway name, or shortcode...'
        })
    )
    
    gateway_type = forms.ChoiceField(
        required=False,
        choices=[('', 'All Gateway Types')] + PaymentGateway.GATEWAY_TYPES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    status = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'All Statuses'),
            ('active', 'Active'),
            ('inactive', 'Inactive'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    environment = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'All Environments'),
            ('live', 'Production'),
            ('sandbox', 'Sandbox'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
