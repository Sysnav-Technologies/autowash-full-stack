from django import forms
from django.core.validators import RegexValidator
from phonenumber_field.formfields import PhoneNumberField
from .models import Subscription, Payment, SubscriptionDiscount

class SubscriptionForm(forms.ModelForm):
    """Form for subscribing to a plan"""
    
    BILLING_CYCLE_CHOICES = [
        ('monthly', 'Monthly'),
        ('semi_annual', 'Semi-Annual'),
        ('annual', 'Annual'),
    ]
    
    billing_cycle = forms.ChoiceField(
        choices=BILLING_CYCLE_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        initial='monthly'
    )
    
    discount_code = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter discount code (optional)',
            'id': 'discount-code-input'
        }),
        help_text="Enter a discount code if you have one"
    )
    
    agree_terms = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="I agree to the Terms of Service and Privacy Policy"
    )
    
    class Meta:
        model = Subscription
        fields = []
    
    def __init__(self, *args, **kwargs):
        self.plan = kwargs.pop('plan', None)
        super().__init__(*args, **kwargs)
        
        if self.plan:
            # Simplified billing cycle choices based on plan type
            choices = [(self.plan.plan_type, f'{self.plan.get_plan_type_display()} - KES {self.plan.price:,.0f}')]
            self.fields['billing_cycle'].choices = choices
            self.fields['billing_cycle'].initial = self.plan.plan_type

class PaymentForm(forms.ModelForm):
    """Form for processing payments"""
    
    PAYMENT_METHOD_CHOICES = [
        ('mpesa', 'M-Pesa'),
        ('card', 'Credit/Debit Card'),
        ('bank_transfer', 'Bank Transfer'),
    ]
    
    payment_method = forms.ChoiceField(
        choices=PAYMENT_METHOD_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input payment-method-radio'}),
        initial='mpesa'
    )
    
    phone_number = PhoneNumberField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '254712345678',
            'id': 'phone-number-input'
        }),
        help_text="Required for M-Pesa payments"
    )
    
    card_number = forms.CharField(
        max_length=19,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '1234 5678 9012 3456',
            'id': 'card-number-input',
            'data-mask': '0000 0000 0000 0000'
        }),
        validators=[
            RegexValidator(
                regex=r'^\d{4}\s?\d{4}\s?\d{4}\s?\d{4}$',
                message='Enter a valid card number'
            )
        ]
    )
    
    card_expiry = forms.CharField(
        max_length=5,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'MM/YY',
            'id': 'card-expiry-input',
            'data-mask': '00/00'
        }),
        validators=[
            RegexValidator(
                regex=r'^\d{2}\/\d{2}$',
                message='Enter expiry date in MM/YY format'
            )
        ]
    )
    
    card_cvv = forms.CharField(
        max_length=4,
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '123',
            'id': 'card-cvv-input',
            'maxlength': '4'
        }),
        validators=[
            RegexValidator(
                regex=r'^\d{3,4}$',
                message='Enter a valid CVV'
            )
        ]
    )
    
    cardholder_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'John Doe',
            'id': 'cardholder-name-input'
        })
    )
    
    class Meta:
        model = Payment
        fields = ['payment_method']
    
    def clean(self):
        cleaned_data = super().clean()
        payment_method = cleaned_data.get('payment_method')
        
        if payment_method == 'mpesa':
            phone_number = cleaned_data.get('phone_number')
            if not phone_number:
                raise forms.ValidationError("Phone number is required for M-Pesa payments")
        
        elif payment_method == 'card':
            required_fields = ['card_number', 'card_expiry', 'card_cvv', 'cardholder_name']
            for field in required_fields:
                if not cleaned_data.get(field):
                    raise forms.ValidationError(f"{field.replace('_', ' ').title()} is required for card payments")
        
        return cleaned_data

class DiscountCodeForm(forms.Form):
    """Form for applying discount codes"""
    
    code = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter discount code',
            'style': 'text-transform: uppercase;'
        })
    )
    
    def clean_code(self):
        code = self.cleaned_data['code'].upper()
        
        try:
            discount = SubscriptionDiscount.objects.get(code=code, is_active=True)
            if not discount.is_valid:
                raise forms.ValidationError("This discount code has expired or reached its usage limit")
            return code
        except SubscriptionDiscount.DoesNotExist:
            raise forms.ValidationError("Invalid discount code")

class CancelSubscriptionForm(forms.Form):
    """Form for cancelling subscriptions"""
    
    CANCELLATION_REASONS = [
        ('too_expensive', 'Too expensive'),
        ('not_using', 'Not using the service'),
        ('missing_features', 'Missing features I need'),
        ('found_alternative', 'Found a better alternative'),
        ('business_closed', 'Business closed'),
        ('technical_issues', 'Technical issues'),
        ('other', 'Other'),
    ]
    
    reason = forms.ChoiceField(
        choices=CANCELLATION_REASONS,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        label="Why are you cancelling?"
    )
    
    feedback = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Please tell us more about your experience (optional)'
        }),
        required=False,
        label="Additional feedback"
    )
    
    confirm_cancellation = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="I understand that my subscription will be cancelled and I will lose access to premium features"
    )

class UpgradeSubscriptionForm(forms.Form):
    """Form for upgrading subscriptions"""
    
    confirm_upgrade = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="I confirm that I want to upgrade my subscription"
    )
    
    payment_method = forms.ChoiceField(
        choices=PaymentForm.PAYMENT_METHOD_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        initial='mpesa',
        required=False
    )
    
    def __init__(self, *args, **kwargs):
        self.upgrade_cost = kwargs.pop('upgrade_cost', 0)
        super().__init__(*args, **kwargs)
        
        # Hide payment method if no payment required
        if self.upgrade_cost <= 0:
            del self.fields['payment_method']

class BusinessSettingsForm(forms.Form):
    """Form for business subscription settings"""
    
    auto_renew = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Automatically renew subscription"
    )
    
    payment_reminders = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Send payment reminders",
        initial=True
    )
    
    usage_alerts = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Send usage limit alerts",
        initial=True
    )
    
    invoice_email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'billing@example.com'
        }),
        label="Invoice email address",
        help_text="Leave blank to use account email"
    )

class ManualPaymentForm(forms.ModelForm):
    """Form for admin to manually record payments"""
    
    class Meta:
        model = Payment
        fields = [
            'subscription', 'amount', 'payment_method', 
            'transaction_id', 'reference_number', 'notes'
        ]
        widgets = {
            'subscription': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'transaction_id': forms.TextInput(attrs={'class': 'form-control'}),
            'reference_number': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def save(self, commit=True):
        payment = super().save(commit=False)
        payment.status = 'completed'
        payment.paid_at = timezone.now()
        
        if commit:
            payment.save()
            # Update subscription status if needed
            if payment.subscription.status == 'pending':
                payment.subscription.status = 'active'
                payment.subscription.save()
        
        return payment