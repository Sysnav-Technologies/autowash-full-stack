from django import forms
from .models import TenantSMSSettings, SMSMessage, SMSTemplate


class TenantSMSSettingsForm(forms.ModelForm):
    """Form for tenant SMS settings"""
    
    class Meta:
        model = TenantSMSSettings
        exclude = ['tenant_id', 'tenant_name', 'daily_usage', 'monthly_usage', 'last_reset_date', 'created_at', 'updated_at']
        widgets = {
            'provider': forms.Select(attrs={'class': 'form-select', 'onchange': 'toggleProviderFields()'}),
            'hp_instance_id': forms.TextInput(attrs={'class': 'form-control'}),
            'hp_access_token': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'hp_webhook_url': forms.URLInput(attrs={'class': 'form-control'}),
            'at_api_key': forms.TextInput(attrs={'class': 'form-control'}),
            'at_username': forms.TextInput(attrs={'class': 'form-control'}),
            'at_sender_id': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 11}),
            'twilio_account_sid': forms.TextInput(attrs={'class': 'form-control'}),
            'twilio_auth_token': forms.TextInput(attrs={'class': 'form-control'}),
            'twilio_phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'use_autowash_billing': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'daily_limit': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'monthly_limit': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        provider = cleaned_data.get('provider')
        
        if provider:
            # Validate provider-specific fields
            if provider.provider_type == 'host_pinnacle':
                if not cleaned_data.get('hp_instance_id'):
                    raise forms.ValidationError("Host Pinnacle Instance ID is required")
                if not cleaned_data.get('hp_access_token'):
                    raise forms.ValidationError("Host Pinnacle Access Token is required")
            
            elif provider.provider_type == 'africas_talking':
                if not cleaned_data.get('at_api_key'):
                    raise forms.ValidationError("Africa's Talking API Key is required")
                if not cleaned_data.get('at_username'):
                    raise forms.ValidationError("Africa's Talking Username is required")
            
            elif provider.provider_type == 'twilio':
                if not cleaned_data.get('twilio_account_sid'):
                    raise forms.ValidationError("Twilio Account SID is required")
                if not cleaned_data.get('twilio_auth_token'):
                    raise forms.ValidationError("Twilio Auth Token is required")
                if not cleaned_data.get('twilio_phone_number'):
                    raise forms.ValidationError("Twilio Phone Number is required")
        
        return cleaned_data


class SendSMSForm(forms.ModelForm):
    """Form for sending individual SMS"""
    
    class Meta:
        model = SMSMessage
        fields = ['recipient', 'message', 'sender_id', 'priority', 'scheduled_at', 'message_type']
        widgets = {
            'recipient': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+254712345678',
                'pattern': r'^\+[1-9]\d{1,14}$'
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'maxlength': 1000,
                'onkeyup': 'updateCharCount(this)'
            }),
            'sender_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'AUTOWASH',
                'maxlength': 11
            }),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'scheduled_at': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'message_type': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'general'
            })
        }
    
    def clean_recipient(self):
        recipient = self.cleaned_data.get('recipient')
        if recipient:
            # Basic phone number validation
            if not recipient.startswith('+'):
                raise forms.ValidationError("Phone number must start with country code (e.g., +254)")
            if len(recipient) < 10:
                raise forms.ValidationError("Phone number is too short")
        return recipient
    
    def clean_message(self):
        message = self.cleaned_data.get('message')
        if message and len(message.strip()) == 0:
            raise forms.ValidationError("Message cannot be empty")
        return message


class BulkSMSForm(forms.Form):
    """Form for sending bulk SMS"""
    
    recipients = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 6,
            'placeholder': 'Enter phone numbers, one per line:\n+254712345678\n+254723456789\n+254734567890'
        }),
        help_text="Enter phone numbers, one per line. Each number should include country code (e.g., +254712345678)"
    )
    
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'maxlength': 1000,
            'onkeyup': 'updateCharCount(this)'
        })
    )
    
    sender_id = forms.CharField(
        required=False,
        max_length=11,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'AUTOWASH'
        })
    )
    
    priority = forms.ChoiceField(
        choices=SMSMessage.PRIORITY_CHOICES,
        initial='normal',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    scheduled_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        }),
        help_text="Leave empty to send immediately"
    )
    
    def clean_recipients(self):
        recipients_text = self.cleaned_data.get('recipients', '')
        recipients = []
        
        for line in recipients_text.strip().split('\n'):
            phone = line.strip()
            if phone:
                if not phone.startswith('+'):
                    raise forms.ValidationError(f"Phone number '{phone}' must start with country code (e.g., +254)")
                if len(phone) < 10:
                    raise forms.ValidationError(f"Phone number '{phone}' is too short")
                recipients.append(phone)
        
        if not recipients:
            raise forms.ValidationError("At least one valid phone number is required")
        
        if len(recipients) > 1000:
            raise forms.ValidationError("Maximum 1000 recipients allowed per bulk send")
        
        return recipients


class SMSTemplateForm(forms.ModelForm):
    """Form for SMS templates"""
    
    class Meta:
        model = SMSTemplate
        exclude = ['tenant_id', 'usage_count', 'last_used', 'created_at', 'updated_at']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'template_type': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.TextInput(attrs={'class': 'form-control'}),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Hello {customer_name}, your appointment at {business_name} is scheduled for {appointment_time}.'
            }),
            'variables': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'customer_name, business_name, appointment_time'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'auto_send': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
    
    def clean_variables(self):
        variables = self.cleaned_data.get('variables', '')
        if isinstance(variables, str):
            # Convert comma-separated string to list
            return [var.strip() for var in variables.split(',') if var.strip()]
        return variables


class TestSMSForm(forms.Form):
    """Form for testing SMS configuration"""
    
    test_number = forms.CharField(
        max_length=20,
        required=True,
        label="Phone Number",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+254712345678',
            'required': True
        }),
        help_text="Your phone number to receive the test SMS"
    )
    
    test_message = forms.CharField(
        required=True,
        label="Test Message",
        initial="This is a test message from Autowash SMS system.",
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'required': True,
            'maxlength': 160
        }),
        help_text="Message content (max 160 characters for single SMS)"
    )
    
    def clean_test_number(self):
        number = self.cleaned_data.get('test_number')
        if number and not number.startswith('+'):
            raise forms.ValidationError("Phone number must include country code (e.g., +254)")
        return number
    
    def clean_test_message(self):
        message = self.cleaned_data.get('test_message')
        if message and len(message) > 160:
            raise forms.ValidationError("Message cannot exceed 160 characters for standard SMS")
        return message