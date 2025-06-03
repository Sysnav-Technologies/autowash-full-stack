from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
import json

from .models import (
    Notification, NotificationCategory, NotificationTemplate,
    NotificationPreference
)

class NotificationPreferenceForm(forms.ModelForm):
    """Form for user notification preferences"""
    
    class Meta:
        model = NotificationPreference
        fields = [
            'email_notifications', 'sms_notifications', 'push_notifications',
            'receive_order_notifications', 'receive_payment_notifications',
            'receive_inventory_alerts', 'receive_system_notifications',
            'receive_reminders', 'receive_reports',
            'quiet_hours_start', 'quiet_hours_end', 'timezone',
            'digest_frequency', 'muted_categories'
        ]
        widgets = {
            'email_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'sms_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'push_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'receive_order_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'receive_payment_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'receive_inventory_alerts': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'receive_system_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'receive_reminders': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'receive_reports': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'quiet_hours_start': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'quiet_hours_end': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'timezone': forms.Select(attrs={'class': 'form-select'}),
            'digest_frequency': forms.Select(attrs={'class': 'form-select'}),
            'muted_categories': forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Timezone choices
        import pytz
        timezone_choices = [(tz, tz) for tz in pytz.common_timezones]
        self.fields['timezone'].widget = forms.Select(
            choices=timezone_choices,
            attrs={'class': 'form-select'}
        )
        
        # Set initial timezone
        if not self.instance.pk:
            self.fields['timezone'].initial = 'Africa/Nairobi'

class NotificationTemplateForm(forms.ModelForm):
    """Form for notification templates"""
    
    class Meta:
        model = NotificationTemplate
        fields = [
            'name', 'description', 'trigger_event', 'title_template', 'message_template',
            'notification_type', 'priority', 'category', 'send_email', 'send_sms',
            'email_template', 'sms_template', 'target_roles', 'target_users',
            'delay_minutes', 'expires_after_hours', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Template name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'trigger_event': forms.Select(attrs={'class': 'form-select'}),
            'title_template': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Use {{variable}} for dynamic content'
            }),
            'message_template': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 4,
                'placeholder': 'Use {{variable}} for dynamic content'
            }),
            'notification_type': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'send_email': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'send_sms': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_template': forms.Textarea(attrs={'class': 'form-control', 'rows': 6}),
            'sms_template': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '160'}),
            'target_roles': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 2,
                'placeholder': 'JSON array: ["owner", "manager"]'
            }),
            'target_users': forms.SelectMultiple(attrs={'class': 'form-select', 'size': '5'}),
            'delay_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'expires_after_hours': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set queryset for categories
        self.fields['category'].queryset = NotificationCategory.objects.filter(is_active=True)
        self.fields['category'].empty_label = "Select Category"
        
        # Set queryset for users
        self.fields['target_users'].queryset = User.objects.filter(is_active=True)
        
        # Convert target_roles from JSON to string for editing
        if self.instance.pk and self.instance.target_roles:
            self.fields['target_roles'].initial = json.dumps(self.instance.target_roles)
    
    def clean_target_roles(self):
        target_roles = self.cleaned_data['target_roles']
        if target_roles:
            try:
                parsed = json.loads(target_roles)
                if not isinstance(parsed, list):
                    raise ValidationError("Target roles must be a JSON array")
                return parsed
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format for target roles")
        return []
    
    def clean_sms_template(self):
        sms_template = self.cleaned_data['sms_template']
        if sms_template and len(sms_template) > 160:
            raise ValidationError("SMS template cannot exceed 160 characters")
        return sms_template

class NotificationCategoryForm(forms.ModelForm):
    """Form for notification categories"""
    
    class Meta:
        model = NotificationCategory
        fields = ['name', 'description', 'icon', 'color']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'icon': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'FontAwesome class (e.g., fas fa-bell)'
            }),
            'color': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Color choices for Bootstrap
        color_choices = [
            ('primary', 'Primary (Blue)'),
            ('secondary', 'Secondary (Gray)'),
            ('success', 'Success (Green)'),
            ('danger', 'Danger (Red)'),
            ('warning', 'Warning (Yellow)'),
            ('info', 'Info (Cyan)'),
            ('light', 'Light'),
            ('dark', 'Dark'),
        ]
        
        self.fields['color'].widget = forms.Select(
            choices=color_choices,
            attrs={'class': 'form-select'}
        )

class NotificationFilterForm(forms.Form):
    """Form for filtering notifications"""
    
    STATUS_CHOICES = [
        ('', 'All Notifications'),
        ('unread', 'Unread'),
        ('read', 'Read'),
        ('archived', 'Archived'),
    ]
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    type = forms.ChoiceField(
        choices=[('', 'All Types')] + Notification.NOTIFICATION_TYPES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    priority = forms.ChoiceField(
        choices=[('', 'All Priorities')] + Notification.PRIORITY_LEVELS,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    category = forms.ModelChoiceField(
        queryset=NotificationCategory.objects.filter(is_active=True),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search notifications...'
        })
    )

class BulkNotificationForm(forms.Form):
    """Form for sending bulk notifications"""
    
    RECIPIENT_TYPES = [
        ('all_employees', 'All Employees'),
        ('role_based', 'By Role'),
        ('specific_users', 'Specific Users'),
    ]
    
    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Notification title'})
    )
    
    message = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Notification message'})
    )
    
    notification_type = forms.ChoiceField(
        choices=Notification.NOTIFICATION_TYPES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    priority = forms.ChoiceField(
        choices=Notification.PRIORITY_LEVELS,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    recipient_type = forms.ChoiceField(
        choices=RECIPIENT_TYPES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    role = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-select', 'size': '8'})
    )
    
    send_email = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    send_sms = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    action_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Optional action URL'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set role choices if Employee model is available
        try:
            from apps.employees.models import Employee
            if hasattr(Employee, 'ROLE_CHOICES'):
                role_choices = [('', 'Select Role')] + list(Employee.ROLE_CHOICES)
                self.fields['role'].widget = forms.Select(
                    choices=role_choices,
                    attrs={'class': 'form-select'}
                )
        except ImportError:
            pass
    
    def clean(self):
        cleaned_data = super().clean()
        recipient_type = cleaned_data.get('recipient_type')
        role = cleaned_data.get('role')
        users = cleaned_data.get('users')
        
        if recipient_type == 'role_based' and not role:
            raise ValidationError("Role is required when sending to role-based recipients.")
        
        if recipient_type == 'specific_users' and not users:
            raise ValidationError("Users must be selected when sending to specific users.")
        
        return cleaned_data

class QuickNotificationForm(forms.Form):
    """Simple form for quick notifications"""
    
    recipient = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Quick message title'})
    )
    
    message = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Your message'})
    )
    
    priority = forms.ChoiceField(
        choices=Notification.PRIORITY_LEVELS,
        initial='normal',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

class NotificationSearchForm(forms.Form):
    """Advanced search form for notifications"""
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search title or message...'
        })
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    type = forms.MultipleChoiceField(
        choices=Notification.NOTIFICATION_TYPES,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    
    priority = forms.MultipleChoiceField(
        choices=Notification.PRIORITY_LEVELS,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    
    is_read = forms.ChoiceField(
        choices=[
            ('', 'Any'),
            ('true', 'Read'),
            ('false', 'Unread'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    has_action = forms.ChoiceField(
        choices=[
            ('', 'Any'),
            ('true', 'With Action'),
            ('false', 'Without Action'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )