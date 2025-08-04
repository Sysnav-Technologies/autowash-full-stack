from django import forms
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.tenant_models import Tenant
from apps.subscriptions.models import SubscriptionPlan
from .models import SystemSettings, AdminActivity, SystemAlert


class BusinessApprovalForm(forms.Form):
    """Form for approving business applications"""
    
    subscription_plan = forms.ModelChoiceField(
        queryset=SubscriptionPlan.objects.filter(is_active=True),
        empty_label="Select a subscription plan...",
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Choose the initial subscription plan for this business"
    )
    
    approval_notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Optional notes about the approval...'
        }),
        required=False,
        help_text="Internal notes about the approval decision"
    )
    
    send_notification = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Send approval notification to business owner"
    )


class BusinessRejectionForm(forms.Form):
    """Form for rejecting business applications"""
    
    REJECTION_REASONS = [
        ('incomplete_information', 'Incomplete Information'),
        ('invalid_documents', 'Invalid Documents'),
        ('business_type_not_supported', 'Business Type Not Supported'),
        ('duplicate_application', 'Duplicate Application'),
        ('non_compliance', 'Non-Compliance with Terms'),
        ('geographic_restrictions', 'Geographic Restrictions'),
        ('other', 'Other (please specify)'),
    ]
    
    rejection_reason = forms.ChoiceField(
        choices=REJECTION_REASONS,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Select the primary reason for rejection"
    )
    
    additional_comments = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Provide detailed feedback to help the business owner...'
        }),
        help_text="This message will be sent to the business owner"
    )
    
    send_notification = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Send rejection notification to business owner"
    )


class BulkBusinessActionForm(forms.Form):
    """Form for bulk actions on businesses"""
    
    ACTION_CHOICES = [
        ('approve', 'Approve Selected Businesses'),
        ('reject', 'Reject Selected Businesses'),
        ('suspend', 'Suspend Selected Businesses'),
        ('activate', 'Activate Selected Businesses'),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    
    business_ids = forms.CharField(
        widget=forms.HiddenInput(),
        help_text="Comma-separated list of business IDs"
    )
    
    subscription_plan = forms.ModelChoiceField(
        queryset=SubscriptionPlan.objects.filter(is_active=True),
        required=False,
        empty_label="Select a subscription plan...",
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Required for approval actions"
    )
    
    reason = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Reason for this bulk action...'
        }),
        required=False,
        help_text="Optional reason for the bulk action"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        business_ids = cleaned_data.get('business_ids')
        subscription_plan = cleaned_data.get('subscription_plan')
        
        if not business_ids:
            raise forms.ValidationError("No businesses selected.")
        
        if action == 'approve' and not subscription_plan:
            raise forms.ValidationError("Subscription plan is required for approval.")
        
        return cleaned_data


class SystemSettingsForm(forms.ModelForm):
    """Form for system settings management"""
    
    class Meta:
        model = SystemSettings
        fields = [
            'business_approval_required', 'trial_period_days', 'auto_suspend_expired',
            'payment_grace_period', 'email_notifications', 'sms_notifications',
            'webhook_notifications', 'max_employees_per_business',
            'max_customers_per_business', 'maintenance_mode', 'maintenance_message'
        ]
        widgets = {
            'trial_period_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'max': 365
            }),
            'payment_grace_period': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'max': 30
            }),
            'max_employees_per_business': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1
            }),
            'max_customers_per_business': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1
            }),
            'maintenance_message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Message to display during maintenance...'
            }),
            'business_approval_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'auto_suspend_expired': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'sms_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'webhook_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'maintenance_mode': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class AdminActivityForm(forms.ModelForm):
    """Form for logging admin activities"""
    
    class Meta:
        model = AdminActivity
        fields = ['action', 'description', 'target_model', 'target_id']
        widgets = {
            'action': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
            'target_model': forms.TextInput(attrs={'class': 'form-control'}),
            'target_id': forms.TextInput(attrs={'class': 'form-control'}),
        }


class SystemAlertForm(forms.ModelForm):
    """Form for creating system alerts"""
    
    class Meta:
        model = SystemAlert
        fields = ['title', 'message', 'alert_type', 'priority']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Alert title...'
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Alert message...'
            }),
            'alert_type': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
        }


class DataExportForm(forms.Form):
    """Form for data export requests"""
    
    EXPORT_TYPES = [
        ('businesses', 'Businesses'),
        ('subscriptions', 'Subscriptions'),
        ('payments', 'Payments'),
        ('users', 'Users'),
        ('analytics', 'Analytics Report'),
    ]
    
    FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('json', 'JSON'),
    ]
    
    export_type = forms.ChoiceField(
        choices=EXPORT_TYPES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Select the type of data to export"
    )
    
    export_format = forms.ChoiceField(
        choices=FORMAT_CHOICES,
        initial='csv',
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Select the export format"
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        help_text="Filter data from this date (optional)"
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        help_text="Filter data to this date (optional)"
    )
    
    include_inactive = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include inactive/deleted records"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        
        if date_from and date_to and date_from > date_to:
            raise forms.ValidationError("'Date from' must be before 'Date to'.")
        
        return cleaned_data


class AdvancedSearchForm(forms.Form):
    """Advanced search form for admin interfaces"""
    
    search_query = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search...'
        })
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All Statuses')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    sort_by = forms.ChoiceField(
        required=False,
        choices=[
            ('created_at', 'Created Date'),
            ('updated_at', 'Updated Date'),
            ('name', 'Name'),
        ],
        initial='created_at',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    sort_order = forms.ChoiceField(
        required=False,
        choices=[
            ('desc', 'Descending'),
            ('asc', 'Ascending'),
        ],
        initial='desc',
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class PaymentRecordForm(forms.Form):
    """Form for recording manual payments"""
    
    subscription = forms.CharField(
        widget=forms.HiddenInput()
    )
    
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': '0.00'
        }),
        help_text="Payment amount in currency"
    )
    
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('check', 'Check'),
        ('mobile_money', 'Mobile Money'),
        ('other', 'Other'),
    ]
    
    payment_method = forms.ChoiceField(
        choices=PAYMENT_METHOD_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Method of payment"
    )
    
    reference_number = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Transaction reference number...'
        }),
        help_text="Bank reference, check number, or transaction ID"
    )
    
    payment_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        help_text="Date when payment was received"
    )
    
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Additional notes about the payment...'
        }),
        help_text="Optional notes about the payment"
    )


class InvoiceGenerationForm(forms.Form):
    """Form for generating subscription invoices"""
    
    subscription = forms.CharField(
        widget=forms.HiddenInput()
    )
    
    subtotal = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': '0.00'
        }),
        help_text="Invoice subtotal amount"
    )
    
    discount_amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        initial=0,
        validators=[MinValueValidator(0)],
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': '0.00'
        }),
        help_text="Discount amount (if any)"
    )
    
    tax_amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        initial=0,
        validators=[MinValueValidator(0)],
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': '0.00'
        }),
        help_text="Tax amount"
    )
    
    due_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        help_text="Payment due date"
    )
    
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Additional notes...'
        }),
        help_text="Optional invoice notes"
    )
    
    send_notification = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Send invoice notification to business owner"
    )
