from django import forms
from django.core.exceptions import ValidationError
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Field, HTML, Div
from crispy_forms.bootstrap import FormActions
from decimal import Decimal
from django.utils import timezone
from .models import (
    Expense, ExpenseCategory, Vendor, RecurringExpense, 
    ExpenseBudget, ExpenseApproval
)
import datetime


class ExpenseSearchForm(forms.Form):
    """Expense search and filter form"""
    search = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Search by title, description, vendor...',
            'class': 'form-control',
            'id': 'expense-search-input'
        })
    )
    
    category = forms.ModelChoiceField(
        queryset=ExpenseCategory.objects.filter(is_active=True),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    expense_type = forms.ChoiceField(
        choices=[('', 'All Types')] + Expense.EXPENSE_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    status = forms.ChoiceField(
        choices=[('', 'All Status')] + Expense.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    vendor = forms.ModelChoiceField(
        queryset=Vendor.objects.filter(is_active=True),
        required=False,
        empty_label="All Vendors",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    
    amount_min = forms.DecimalField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Min Amount',
            'step': '0.01'
        })
    )
    
    amount_max = forms.DecimalField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Max Amount',
            'step': '0.01'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'GET'
        self.helper.form_class = 'expense-filter-form'
        self.helper.layout = Layout(
            Row(
                Column('search', css_class='form-group col-md-3'),
                Column('category', css_class='form-group col-md-2'),
                Column('expense_type', css_class='form-group col-md-2'),
                Column('status', css_class='form-group col-md-2'),
                Column('vendor', css_class='form-group col-md-3'),
            ),
            Row(
                Column('date_from', css_class='form-group col-md-2'),
                Column('date_to', css_class='form-group col-md-2'),
                Column('amount_min', css_class='form-group col-md-2'),
                Column('amount_max', css_class='form-group col-md-2'),
                Column(
                    Submit('submit', 'Filter', css_class='btn btn-primary mt-4'),
                    HTML('<a href="?" class="btn btn-outline-secondary mt-4 ms-2">Clear</a>'),
                    css_class='form-group col-md-4'
                ),
            )
        )


class ExpenseForm(forms.ModelForm):
    """Expense creation and edit form"""
    
    class Meta:
        model = Expense
        fields = [
            'title', 'description', 'category', 'vendor', 'amount', 'tax_amount',
            'expense_date', 'due_date', 'payment_method', 'reference_number',
            'receipt_number', 'expense_type', 'is_recurring', 'recurring_frequency',
            'notes'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'vendor': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01'
            }),
            'tax_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'expense_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'due_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'reference_number': forms.TextInput(attrs={'class': 'form-control'}),
            'receipt_number': forms.TextInput(attrs={'class': 'form-control'}),
            'expense_type': forms.Select(attrs={'class': 'form-select'}),
            'recurring_frequency': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter active categories and vendors
        self.fields['category'].queryset = ExpenseCategory.objects.filter(is_active=True)
        self.fields['vendor'].queryset = Vendor.objects.filter(is_active=True)
        
        # Set default expense date to today
        if not self.instance.pk:
            self.fields['expense_date'].initial = timezone.now().date()
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h5 class="border-bottom pb-2 mb-3">Basic Information</h5>'),
            Row(
                Column('title', css_class='form-group col-md-6'),
                Column('category', css_class='form-group col-md-6'),
            ),
            'description',
            Row(
                Column('vendor', css_class='form-group col-md-6'),
                Column('expense_type', css_class='form-group col-md-6'),
            ),
            
            HTML('<h5 class="border-bottom pb-2 mb-3 mt-4">Financial Details</h5>'),
            Row(
                Column('amount', css_class='form-group col-md-4'),
                Column('tax_amount', css_class='form-group col-md-4'),
                Column(
                    HTML('''
                    <label class="form-label">Total Amount</label>
                    <input type="text" class="form-control" id="total_amount" readonly>
                    '''),
                    css_class='form-group col-md-4'
                ),
            ),
            
            HTML('<h5 class="border-bottom pb-2 mb-3 mt-4">Dates & Payment</h5>'),
            Row(
                Column('expense_date', css_class='form-group col-md-4'),
                Column('due_date', css_class='form-group col-md-4'),
                Column('payment_method', css_class='form-group col-md-4'),
            ),
            Row(
                Column('reference_number', css_class='form-group col-md-6'),
                Column('receipt_number', css_class='form-group col-md-6'),
            ),
            
            HTML('<h5 class="border-bottom pb-2 mb-3 mt-4">Recurring Settings</h5>'),
            Row(
                Column(
                    Field('is_recurring', wrapper_class='form-check'),
                    css_class='form-group col-md-6'
                ),
                Column('recurring_frequency', css_class='form-group col-md-6'),
            ),
            
            'notes',
            
            FormActions(
                Submit('save', 'Save Expense', css_class='btn btn-primary'),
                HTML('<a href="{% url "expenses:list" %}" class="btn btn-secondary ms-2">Cancel</a>')
            )
        )

    def clean(self):
        cleaned_data = super().clean()
        is_recurring = cleaned_data.get('is_recurring')
        recurring_frequency = cleaned_data.get('recurring_frequency')
        
        if is_recurring and not recurring_frequency:
            raise ValidationError("Recurring frequency is required for recurring expenses.")
        
        return cleaned_data


class VendorForm(forms.ModelForm):
    """Vendor creation and edit form"""
    
    class Meta:
        model = Vendor
        fields = [
            'name', 'contact_person', 'email', 'phone', 'address',
            'tax_number', 'bank_account', 'payment_terms'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'tax_number': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_account': forms.TextInput(attrs={'class': 'form-control'}),
            'payment_terms': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('name', css_class='form-group col-md-6'),
                Column('contact_person', css_class='form-group col-md-6'),
            ),
            Row(
                Column('email', css_class='form-group col-md-6'),
                Column('phone', css_class='form-group col-md-6'),
            ),
            'address',
            Row(
                Column('tax_number', css_class='form-group col-md-6'),
                Column('bank_account', css_class='form-group col-md-6'),
            ),
            'payment_terms',
            FormActions(
                Submit('save', 'Save Vendor', css_class='btn btn-primary'),
                HTML('<a href="{% url "expenses:vendor_list" %}" class="btn btn-secondary ms-2">Cancel</a>')
            )
        )


class ExpenseCategoryForm(forms.ModelForm):
    """Expense category creation and edit form"""
    
    class Meta:
        model = ExpenseCategory
        fields = ['name', 'description', 'parent', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'parent': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Exclude the current category from parent choices to prevent circular references
        if self.instance.pk:
            self.fields['parent'].queryset = ExpenseCategory.objects.filter(
                is_active=True
            ).exclude(pk=self.instance.pk)
        else:
            self.fields['parent'].queryset = ExpenseCategory.objects.filter(is_active=True)
        
        # Set labels
        self.fields['is_active'].label = 'Active'
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('name', css_class='col-md-6'),
                Column('parent', css_class='col-md-6'),
            ),
            'description',
            Field('is_active', css_class='form-check'),
            FormActions(
                Submit('save', 'Save Category', css_class='btn btn-primary'),
                HTML('<a href="{% url "expenses:category_list" %}" class="btn btn-secondary ms-2">Cancel</a>')
            )
        )


class RecurringExpenseForm(forms.ModelForm):
    """Recurring expense template form"""
    
    class Meta:
        model = RecurringExpense
        fields = [
            'title', 'category', 'vendor', 'amount', 'frequency',
            'start_date', 'end_date', 'auto_approve'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'vendor': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01'
            }),
            'frequency': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'end_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['category'].queryset = ExpenseCategory.objects.filter(is_active=True)
        self.fields['vendor'].queryset = Vendor.objects.filter(is_active=True)
        
        if not self.instance.pk:
            self.fields['start_date'].initial = timezone.now().date()
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'title',
            Row(
                Column('category', css_class='form-group col-md-6'),
                Column('vendor', css_class='form-group col-md-6'),
            ),
            Row(
                Column('amount', css_class='form-group col-md-6'),
                Column('frequency', css_class='form-group col-md-6'),
            ),
            Row(
                Column('start_date', css_class='form-group col-md-6'),
                Column('end_date', css_class='form-group col-md-6'),
            ),
            Field('auto_approve', wrapper_class='form-check'),
            FormActions(
                Submit('save', 'Save Recurring Expense', css_class='btn btn-primary'),
                HTML('<a href="{% url "expenses:recurring_list" %}" class="btn btn-secondary ms-2">Cancel</a>')
            )
        )


class ExpenseApprovalForm(forms.ModelForm):
    """Expense approval form"""
    
    class Meta:
        model = ExpenseApproval
        fields = ['status', 'comments']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'comments': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'status',
            'comments',
            FormActions(
                Submit('save', 'Submit Approval', css_class='btn btn-primary'),
            )
        )


class ExpenseBudgetForm(forms.ModelForm):
    """Budget form"""
    
    class Meta:
        model = ExpenseBudget
        fields = ['category', 'year', 'month', 'budgeted_amount']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'year': forms.NumberInput(attrs={'class': 'form-control'}),
            'month': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '12'
            }),
            'budgeted_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['category'].queryset = ExpenseCategory.objects.filter(is_active=True)
        
        if not self.instance.pk:
            self.fields['year'].initial = timezone.now().year
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'category',
            Row(
                Column('year', css_class='form-group col-md-6'),
                Column('month', css_class='form-group col-md-6'),
            ),
            'budgeted_amount',
            HTML('<small class="form-text text-muted">Leave month blank for yearly budget</small>'),
            FormActions(
                Submit('save', 'Save Budget', css_class='btn btn-primary'),
                HTML('<a href="{% url "expenses:budget_list" %}" class="btn btn-secondary ms-2">Cancel</a>')
            )
        )


class BulkExpenseActionForm(forms.Form):
    """Form for bulk actions on expenses"""
    action = forms.ChoiceField(
        choices=[
            ('approve', 'Approve Selected'),
            ('reject', 'Reject Selected'),
            ('mark_paid', 'Mark as Paid'),
            ('delete', 'Delete Selected'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    comments = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Optional comments for bulk action'
        })
    )
