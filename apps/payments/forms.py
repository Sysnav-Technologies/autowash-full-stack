from django import forms
from django.core.exceptions import ValidationError
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Field, HTML, Div
from crispy_forms.bootstrap import FormActions
from phonenumber_field.formfields import PhoneNumberField
from .models import Payment, PaymentMethod, PaymentRefund, CashTransaction
from .mpesa import validate_mpesa_phone
from decimal import Decimal

class PaymentForm(forms.ModelForm):
    """General payment form"""
    
    class Meta:
        model = Payment
        fields = [
            'customer', 'payment_method', 'payment_type', 'amount',
            'description', 'customer_phone', 'customer_email'
        ]
        widgets = {
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'description': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter active payment methods
        self.fields['payment_method'].queryset = PaymentMethod.objects.filter(is_active=True)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('customer', css_class='form-group col-md-6'),
                Column('payment_method', css_class='form-group col-md-6'),
            ),
            Row(
                Column('payment_type', css_class='form-group col-md-6'),
                Column('amount', css_class='form-group col-md-6'),
            ),
            'description',
            Row(
                Column('customer_phone', css_class='form-group col-md-6'),
                Column('customer_email', css_class='form-group col-md-6'),
            ),
            FormActions(
                Submit('submit', 'Create Payment', css_class='btn btn-primary')
            )
        )

class CashPaymentForm(forms.Form):
    """Cash payment processing form"""
    amount_tendered = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        label="Amount Tendered",
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0'})
    )
    change_given = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        label="Change Given",
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'readonly': True})
    )
    
    # Kenyan currency denominations
    notes_1000 = forms.IntegerField(min_value=0, initial=0, label="1000 KES Notes")
    notes_500 = forms.IntegerField(min_value=0, initial=0, label="500 KES Notes")
    notes_200 = forms.IntegerField(min_value=0, initial=0, label="200 KES Notes")
    notes_100 = forms.IntegerField(min_value=0, initial=0, label="100 KES Notes")
    notes_50 = forms.IntegerField(min_value=0, initial=0, label="50 KES Notes")
    
    coins_40 = forms.IntegerField(min_value=0, initial=0, label="40 KES Coins")
    coins_20 = forms.IntegerField(min_value=0, initial=0, label="20 KES Coins")
    coins_10 = forms.IntegerField(min_value=0, initial=0, label="10 KES Coins")
    coins_5 = forms.IntegerField(min_value=0, initial=0, label="5 KES Coins")
    coins_1 = forms.IntegerField(min_value=0, initial=0, label="1 KES Coins")
    
    till_number = forms.CharField(max_length=20, required=False, label="Till Number")
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}),
        required=False,
        label="Notes"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h6>Payment Details</h6>'),
            Row(
                Column('amount_tendered', css_class='form-group col-md-6'),
                Column('change_given', css_class='form-group col-md-6'),
            ),
            
            HTML('<h6 class="mt-4">Currency Breakdown (Optional)</h6>'),
            HTML('<div class="row">'),
            HTML('<div class="col-md-6">'),
            HTML('<h7>Notes</h7>'),
            'notes_1000',
            'notes_500',
            'notes_200',
            'notes_100',
            'notes_50',
            HTML('</div>'),
            HTML('<div class="col-md-6">'),
            HTML('<h7>Coins</h7>'),
            'coins_40',
            'coins_20',
            'coins_10',
            'coins_5',
            'coins_1',
            HTML('</div>'),
            HTML('</div>'),
            
            Row(
                Column('till_number', css_class='form-group col-md-6'),
                Column('notes', css_class='form-group col-md-6'),
            ),
            
            FormActions(
                Submit('submit', 'Complete Cash Payment', css_class='btn btn-success btn-lg')
            )
        )
    
    def clean(self):
        cleaned_data = super().clean()
        amount_tendered = cleaned_data.get('amount_tendered')
        change_given = cleaned_data.get('change_given')
        
        if amount_tendered and change_given:
            # Validate that change is not more than tendered amount
            if change_given > amount_tendered:
                raise ValidationError("Change given cannot be more than amount tendered.")
        
        return cleaned_data

class MPesaPaymentForm(forms.Form):
    """M-Pesa payment form"""
    phone_number = forms.CharField(
        max_length=15,
        required=False,
        label="M-Pesa Phone Number (Optional)",
        widget=forms.TextInput(attrs={
            'placeholder': '+254712345678',
            'pattern': r'(\+254|0)[17]\d{8}',
            'title': 'Enter a valid Kenyan mobile number',
            'class': 'form-control form-control-lg'
        }),
        help_text="Enter the customer's M-Pesa registered phone number (required for automatic payments)"
    )
    
    # Optional payment code field for businesses without gateway
    payment_code = forms.CharField(
        max_length=50,
        required=False,
        label="M-Pesa Payment Code (Optional)",
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g. NLJ7RT61SX',
            'class': 'form-control form-control-lg'
        }),
        help_text="Enter the M-Pesa transaction code if payment was made manually"
    )
    
    def __init__(self, *args, **kwargs):
        # Extract initial phone number if provided
        initial_phone = kwargs.pop('initial_phone', None)
        super().__init__(*args, **kwargs)
        
        # Set initial value if provided
        if initial_phone:
            self.fields['phone_number'].initial = initial_phone
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Field('phone_number', css_class='mb-3'),
            Field('payment_code', css_class='mb-3'),
            HTML('<div class="alert alert-info mt-3 mb-4">'),
            HTML('<i class="fas fa-info-circle me-2"></i> '),
            HTML('<strong>Two payment options:</strong><br>'),
            HTML('• <strong>With Gateway:</strong> Leave payment code empty - customer will receive M-Pesa prompt<br>'),
            HTML('• <strong>Manual Payment:</strong> Ask customer to pay to your till number, then enter the M-Pesa code here'),
            HTML('</div>'),
            FormActions(
                Submit('submit', 'Process M-Pesa Payment', css_class='btn btn-success btn-lg w-100 py-3'),
                HTML('<a href="javascript:history.back()" class="btn btn-outline-secondary mt-2 w-100">Cancel</a>')
            )
        )
    
    def clean_phone_number(self):
        phone_number = self.cleaned_data['phone_number']
        
        # If phone number is empty, it's okay for manual payments
        if not phone_number:
            return phone_number
        
        is_valid, result = validate_mpesa_phone(phone_number)
        
        if not is_valid:
            raise ValidationError(result)
        
        return result

class CardPaymentForm(forms.Form):
    """Card payment form"""
    card_number = forms.CharField(
        max_length=19,
        label="Card Number",
        widget=forms.TextInput(attrs={
            'placeholder': '**** **** **** 1234',
            'autocomplete': 'cc-number'
        })
    )
    card_holder_name = forms.CharField(
        max_length=100,
        label="Card Holder Name",
        widget=forms.TextInput(attrs={'autocomplete': 'cc-name'})
    )
    expiry_month = forms.ChoiceField(
        choices=[(i, f"{i:02d}") for i in range(1, 13)],
        label="Expiry Month"
    )
    expiry_year = forms.ChoiceField(
        choices=[(i, str(i)) for i in range(2024, 2035)],
        label="Expiry Year"
    )
    cvv = forms.CharField(
        max_length=4,
        label="CVV",
        widget=forms.PasswordInput(attrs={'autocomplete': 'cc-csc'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'card_number',
            'card_holder_name',
            Row(
                Column('expiry_month', css_class='form-group col-md-4'),
                Column('expiry_year', css_class='form-group col-md-4'),
                Column('cvv', css_class='form-group col-md-4'),
            ),
            HTML('<div class="alert alert-warning mt-3">'),
            HTML('<i class="fas fa-shield-alt"></i> '),
            HTML('Card information is processed securely and not stored on our servers.'),
            HTML('</div>'),
            FormActions(
                Submit('submit', 'Process Card Payment', css_class='btn btn-primary btn-lg')
            )
        )

class PaymentRefundForm(forms.ModelForm):
    """Payment refund form"""
    
    class Meta:
        model = PaymentRefund
        fields = ['amount', 'reason']
        widgets = {
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'reason': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        self.payment = kwargs.pop('payment', None)
        super().__init__(*args, **kwargs)
        
        if self.payment:
            # Set maximum refund amount
            max_refund = self.payment.amount - self.payment.total_refunded
            self.fields['amount'].widget.attrs['max'] = str(max_refund)
            self.fields['amount'].help_text = f"Maximum refund amount: KES {max_refund}"
            
            # Auto-fill with full refundable amount if not already set
            if not self.data and not self.initial.get('amount'):
                self.fields['amount'].initial = max_refund
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'amount',
            'reason',
            HTML('<div class="alert alert-warning mt-3">'),
            HTML('<i class="fas fa-exclamation-triangle"></i> '),
            HTML('Refunds cannot be reversed once processed. Please verify the amount and reason.'),
            HTML('</div>'),
            FormActions(
                Submit('submit', 'Process Refund', css_class='btn btn-warning')
            )
        )
    
    def clean_amount(self):
        amount = self.cleaned_data['amount']
        
        if self.payment:
            max_refund = self.payment.amount - self.payment.total_refunded
            if amount > max_refund:
                raise ValidationError(f"Refund amount cannot exceed KES {max_refund}")
        
        if amount <= 0:
            raise ValidationError("Refund amount must be greater than zero.")
        
        return amount

class PaymentMethodForm(forms.ModelForm):
    """Payment method configuration form"""
    
    class Meta:
        model = PaymentMethod
        fields = [
            'name', 'method_type', 'description', 'is_active', 'is_online',
            'requires_verification', 'processing_fee_percentage', 'fixed_processing_fee',
            'minimum_amount', 'maximum_amount', 'daily_limit', 'icon', 'color',
            'display_order'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'processing_fee_percentage': forms.NumberInput(attrs={'step': '0.01'}),
            'fixed_processing_fee': forms.NumberInput(attrs={'step': '0.01'}),
            'minimum_amount': forms.NumberInput(attrs={'step': '0.01'}),
            'maximum_amount': forms.NumberInput(attrs={'step': '0.01'}),
            'daily_limit': forms.NumberInput(attrs={'step': '0.01'}),
            'color': forms.TextInput(attrs={'type': 'color'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h5>Basic Information</h5>'),
            Row(
                Column('name', css_class='form-group col-md-8'),
                Column('method_type', css_class='form-group col-md-4'),
            ),
            'description',
            
            HTML('<h5 class="mt-4">Configuration</h5>'),
            Row(
                Column('is_active', css_class='form-group col-md-3'),
                Column('is_online', css_class='form-group col-md-3'),
                Column('requires_verification', css_class='form-group col-md-3'),
                Column('display_order', css_class='form-group col-md-3'),
            ),
            
            HTML('<h5 class="mt-4">Fees</h5>'),
            Row(
                Column('processing_fee_percentage', css_class='form-group col-md-6'),
                Column('fixed_processing_fee', css_class='form-group col-md-6'),
            ),
            
            HTML('<h5 class="mt-4">Limits</h5>'),
            Row(
                Column('minimum_amount', css_class='form-group col-md-4'),
                Column('maximum_amount', css_class='form-group col-md-4'),
                Column('daily_limit', css_class='form-group col-md-4'),
            ),
            
            HTML('<h5 class="mt-4">Display</h5>'),
            Row(
                Column('icon', css_class='form-group col-md-6'),
                Column('color', css_class='form-group col-md-6'),
            ),
            
            FormActions(
                Submit('submit', 'Save Payment Method', css_class='btn btn-primary')
            )
        )

class QuickPaymentForm(forms.Form):
    """Quick payment form for mobile/tablet use"""
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        label="Amount",
        widget=forms.NumberInput(attrs={
            'step': '0.01',
            'min': '0',
            'class': 'form-control form-control-lg'
        })
    )
    payment_method = forms.ModelChoiceField(
        queryset=PaymentMethod.objects.filter(is_active=True),
        widget=forms.RadioSelect,
        label="Payment Method"
    )
    customer_phone = forms.CharField(
        max_length=15,
        required=False,
        label="Customer Phone (for receipts)",
        widget=forms.TextInput(attrs={
            'placeholder': '+254712345678',
            'class': 'form-control'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'amount',
            'payment_method',
            'customer_phone',
            FormActions(
                Submit('submit', 'Process Payment', css_class='btn btn-success btn-lg w-100')
            )
        )

class PaymentSearchForm(forms.Form):
    """Payment search form"""
    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Search by payment ID, customer, transaction ID...',
            'class': 'form-control'
        })
    )
    status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + Payment.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    payment_method = forms.ModelChoiceField(
        queryset=PaymentMethod.objects.filter(is_active=True),
        required=False,
        empty_label="All Methods",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    amount_min = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'})
    )
    amount_max = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'})
    )