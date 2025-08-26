from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Field, HTML, Div
from crispy_forms.bootstrap import FormActions
from phonenumber_field.formfields import PhoneNumberField
from .models import (
    Employee, Department, Position, Attendance, Leave, 
    PerformanceReview, Training, TrainingParticipant, Payroll, EmployeeDocument
)

class EmployeeForm(forms.ModelForm):
    """Employee creation/edit form"""
    # User fields
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    email = forms.EmailField(required=True)
    username = forms.CharField(max_length=150, required=False)
    password = forms.CharField(widget=forms.PasswordInput(), required=False)
    
    class Meta:
        model = Employee
        fields = [
            'photo', 'department', 'position', 'role', 'employment_type',
            'hire_date', 'probation_end_date', 'salary', 'hourly_rate',
            'commission_rate', 'supervisor', 'phone', 'date_of_birth',
            'gender', 'marital_status', 'national_id', 'address_line_1',
            'address_line_2', 'city', 'state', 'postal_code', 'emergency_contact_name',
            'emergency_contact_phone', 'emergency_contact_relationship',
            'is_active', 'can_login', 'receive_notifications'
        ]
        widgets = {
            'hire_date': forms.DateInput(attrs={'type': 'date'}),
            'probation_end_date': forms.DateInput(attrs={'type': 'date'}),
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'salary': forms.NumberInput(attrs={'step': '0.01'}),
            'hourly_rate': forms.NumberInput(attrs={'step': '0.01'}),
            'commission_rate': forms.NumberInput(attrs={'step': '0.01', 'max': '100'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter supervisors (only managers and supervisors)
        self.fields['supervisor'].queryset = Employee.objects.filter(
            role__in=['owner', 'manager', 'supervisor'],
            is_active=True
        )
        
        # Apply Bootstrap classes to all form fields
        bootstrap_classes = {
            'first_name': 'form-control',
            'last_name': 'form-control',
            'email': 'form-control',
            'username': 'form-control',
            'password': 'form-control',
            'photo': 'form-control',
            'department': 'form-select',
            'position': 'form-select',
            'role': 'form-select',
            'employment_type': 'form-select',
            'hire_date': 'form-control',
            'probation_end_date': 'form-control',
            'salary': 'form-control',
            'hourly_rate': 'form-control',
            'commission_rate': 'form-control',
            'supervisor': 'form-select',
            'phone': 'form-control',
            'date_of_birth': 'form-control',
            'gender': 'form-select',
            'marital_status': 'form-select',
            'national_id': 'form-control',
            'address_line_1': 'form-control',
            'address_line_2': 'form-control',
            'city': 'form-control',
            'state': 'form-control',
            'postal_code': 'form-control',
            'emergency_contact_name': 'form-control',
            'emergency_contact_phone': 'form-control',
            'emergency_contact_relationship': 'form-control',
            'is_active': 'form-check-input',
            'can_login': 'form-check-input',
            'receive_notifications': 'form-check-input',
        }
        
        # Apply CSS classes to all fields
        for field_name, css_class in bootstrap_classes.items():
            if field_name in self.fields:
                existing_class = self.fields[field_name].widget.attrs.get('class', '')
                if existing_class:
                    self.fields[field_name].widget.attrs['class'] = f"{existing_class} {css_class}"
                else:
                    self.fields[field_name].widget.attrs['class'] = css_class
                
                # Add helpful placeholders
                if field_name == 'first_name':
                    self.fields[field_name].widget.attrs['placeholder'] = 'Enter first name'
                elif field_name == 'last_name':
                    self.fields[field_name].widget.attrs['placeholder'] = 'Enter last name'
                elif field_name == 'email':
                    self.fields[field_name].widget.attrs['placeholder'] = 'Enter email address'
                elif field_name == 'username':
                    self.fields[field_name].widget.attrs['placeholder'] = 'Enter username'
                elif field_name == 'phone':
                    self.fields[field_name].widget.attrs['placeholder'] = 'Enter phone number'
                elif field_name == 'national_id':
                    self.fields[field_name].widget.attrs['placeholder'] = 'Enter national ID number'
                elif field_name == 'address_line_1':
                    self.fields[field_name].widget.attrs['placeholder'] = 'Enter street address'
                elif field_name == 'city':
                    self.fields[field_name].widget.attrs['placeholder'] = 'Enter city'
                elif field_name == 'emergency_contact_name':
                    self.fields[field_name].widget.attrs['placeholder'] = 'Enter emergency contact name'
        
        # Make username and password required for new employees
        if not self.instance.pk:
            self.fields['username'].required = True
            self.fields['password'].required = True
        else:
            # Pre-populate user fields for existing employees
            if self.instance.user:
                self.fields['first_name'].initial = self.instance.user.first_name
                self.fields['last_name'].initial = self.instance.user.last_name
                self.fields['email'].initial = self.instance.user.email
                self.fields['username'].initial = self.instance.user.username
                self.fields['password'].required = False
                self.fields['password'].help_text = "Leave blank to keep current password"
        
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
                Column('username', css_class='form-group col-md-6'),
                Column('password', css_class='form-group col-md-6'),
            ),
            Row(
                Column('date_of_birth', css_class='form-group col-md-4'),
                Column('gender', css_class='form-group col-md-4'),
                Column('marital_status', css_class='form-group col-md-4'),
            ),
            Row(
                Column('national_id', css_class='form-group col-md-6'),
                Column('photo', css_class='form-group col-md-6'),
            ),
            
            HTML('<h5 class="mt-4">Employment Information</h5>'),
            Row(
                Column('department', css_class='form-group col-md-6'),
                Column('position', css_class='form-group col-md-6'),
            ),
            Row(
                Column('role', css_class='form-group col-md-4'),
                Column('employment_type', css_class='form-group col-md-4'),
                Column('supervisor', css_class='form-group col-md-4'),
            ),
            Row(
                Column('hire_date', css_class='form-group col-md-6'),
                Column('probation_end_date', css_class='form-group col-md-6'),
            ),
            
            HTML('<h5 class="mt-4">Compensation</h5>'),
            Row(
                Column('salary', css_class='form-group col-md-4'),
                Column('hourly_rate', css_class='form-group col-md-4'),
                Column('commission_rate', css_class='form-group col-md-4'),
            ),
            
            HTML('<h5 class="mt-4">Address Information</h5>'),
            'address_line_1',
            'address_line_2',
            Row(
                Column('city', css_class='form-group col-md-4'),
                Column('state', css_class='form-group col-md-4'),
                Column('postal_code', css_class='form-group col-md-4'),
            ),
            
            HTML('<h5 class="mt-4">Emergency Contact</h5>'),
            Row(
                Column('emergency_contact_name', css_class='form-group col-md-4'),
                Column('emergency_contact_phone', css_class='form-group col-md-4'),
                Column('emergency_contact_relationship', css_class='form-group col-md-4'),
            ),
            
            HTML('<h5 class="mt-4">Settings</h5>'),
            Row(
                Column('is_active', css_class='form-group col-md-4'),
                Column('can_login', css_class='form-group col-md-4'),
                Column('receive_notifications', css_class='form-group col-md-4'),
            ),
            
            FormActions(
                Submit('submit', 'Save Employee', css_class='btn btn-primary')
            )
        )
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            # Get the user_id to exclude from the check
            exclude_user_id = None
            
            # For existing employees, get their user_id
            if self.instance.pk and self.instance.user_id:
                exclude_user_id = self.instance.user_id
            
            # Check if username already exists in User model (public schema)
            existing_user = User.objects.using('default').filter(username=username)
            if exclude_user_id:
                existing_user = existing_user.exclude(pk=exclude_user_id)
            
            if existing_user.exists():
                raise ValidationError("Username already exists.")
        
        return username
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            # Get the user_id to exclude from the check
            exclude_user_id = None
            
            # For existing employees, get their user_id
            if self.instance.pk and self.instance.user_id:
                exclude_user_id = self.instance.user_id
            
            # Check if email already exists in User model (public schema)
            existing_user = User.objects.using('default').filter(email=email)
            if exclude_user_id:
                existing_user = existing_user.exclude(pk=exclude_user_id)
            
            if existing_user.exists():
                raise ValidationError("Email already exists.")
            
        return email

class DepartmentForm(forms.ModelForm):
    """Department form"""
    
    class Meta:
        model = Department
        fields = ['name', 'description', 'head', 'is_active']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['head'].queryset = Employee.objects.filter(
            role__in=['manager', 'supervisor'],
            is_active=True
        )
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'name',
            'description',
            Row(
                Column('head', css_class='form-group col-md-6'),
                Column('is_active', css_class='form-group col-md-6'),
            ),
            FormActions(
                Submit('submit', 'Save Department', css_class='btn btn-primary')
            )
        )

class PositionForm(forms.ModelForm):
    """Position form"""
    
    class Meta:
        model = Position
        fields = ['title', 'department', 'description', 'requirements', 'min_salary', 'max_salary', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'requirements': forms.Textarea(attrs={'rows': 3}),
            'min_salary': forms.NumberInput(attrs={'step': '0.01'}),
            'max_salary': forms.NumberInput(attrs={'step': '0.01'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('title', css_class='form-group col-md-8'),
                Column('department', css_class='form-group col-md-4'),
            ),
            'description',
            'requirements',
            Row(
                Column('min_salary', css_class='form-group col-md-4'),
                Column('max_salary', css_class='form-group col-md-4'),
                Column('is_active', css_class='form-group col-md-4'),
            ),
            FormActions(
                Submit('submit', 'Save Position', css_class='btn btn-primary')
            )
        )

class AttendanceForm(forms.ModelForm):
    """Attendance form"""
    
    class Meta:
        model = Attendance
        fields = ['employee', 'date', 'status', 'check_in_time', 'check_out_time', 'overtime_hours', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'check_in_time': forms.TimeInput(attrs={'type': 'time'}),
            'check_out_time': forms.TimeInput(attrs={'type': 'time'}),
            'overtime_hours': forms.NumberInput(attrs={'step': '0.5'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('employee', css_class='form-group col-md-6'),
                Column('date', css_class='form-group col-md-6'),
            ),
            Row(
                Column('status', css_class='form-group col-md-4'),
                Column('check_in_time', css_class='form-group col-md-4'),
                Column('check_out_time', css_class='form-group col-md-4'),
            ),
            Row(
                Column('overtime_hours', css_class='form-group col-md-6'),
                Column('notes', css_class='form-group col-md-6'),
            ),
            FormActions(
                Submit('submit', 'Save Attendance', css_class='btn btn-primary')
            )
        )

class LeaveRequestForm(forms.ModelForm):
    """Leave request form"""
    
    class Meta:
        model = Leave
        fields = [
            'leave_type', 'start_date', 'end_date', 'reason', 
            'medical_certificate', 'supporting_document'
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'reason': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'leave_type',
            Row(
                Column('start_date', css_class='form-group col-md-6'),
                Column('end_date', css_class='form-group col-md-6'),
            ),
            'reason',
            HTML('<h6 class="mt-3">Supporting Documents (Optional)</h6>'),
            Row(
                Column('medical_certificate', css_class='form-group col-md-6'),
                Column('supporting_document', css_class='form-group col-md-6'),
            ),
            FormActions(
                Submit('submit', 'Submit Leave Request', css_class='btn btn-primary')
            )
        )
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date:
            if start_date > end_date:
                raise ValidationError("Start date cannot be after end date.")
            
            # Calculate days requested
            days_requested = (end_date - start_date).days + 1
            cleaned_data['days_requested'] = days_requested
        
        return cleaned_data

class PerformanceReviewForm(forms.ModelForm):
    """Performance review form"""
    
    class Meta:
        model = PerformanceReview
        fields = [
            'employee', 'review_type', 'review_period_start', 'review_period_end',
            'quality_of_work', 'punctuality', 'teamwork', 'communication',
            'initiative', 'customer_service', 'strengths', 'areas_for_improvement',
            'goals_for_next_period', 'additional_comments', 'follow_up_required',
            'follow_up_date'
        ]
        widgets = {
            'review_period_start': forms.DateInput(attrs={'type': 'date'}),
            'review_period_end': forms.DateInput(attrs={'type': 'date'}),
            'follow_up_date': forms.DateInput(attrs={'type': 'date'}),
            'strengths': forms.Textarea(attrs={'rows': 3}),
            'areas_for_improvement': forms.Textarea(attrs={'rows': 3}),
            'goals_for_next_period': forms.Textarea(attrs={'rows': 3}),
            'additional_comments': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h5>Review Information</h5>'),
            Row(
                Column('employee', css_class='form-group col-md-6'),
                Column('review_type', css_class='form-group col-md-6'),
            ),
            Row(
                Column('review_period_start', css_class='form-group col-md-6'),
                Column('review_period_end', css_class='form-group col-md-6'),
            ),
            
            HTML('<h5 class="mt-4">Performance Ratings</h5>'),
            Row(
                Column('quality_of_work', css_class='form-group col-md-4'),
                Column('punctuality', css_class='form-group col-md-4'),
                Column('teamwork', css_class='form-group col-md-4'),
            ),
            Row(
                Column('communication', css_class='form-group col-md-4'),
                Column('initiative', css_class='form-group col-md-4'),
                Column('customer_service', css_class='form-group col-md-4'),
            ),
            
            HTML('<h5 class="mt-4">Comments</h5>'),
            'strengths',
            'areas_for_improvement',
            'goals_for_next_period',
            'additional_comments',
            
            HTML('<h5 class="mt-4">Follow-up</h5>'),
            Row(
                Column('follow_up_required', css_class='form-group col-md-6'),
                Column('follow_up_date', css_class='form-group col-md-6'),
            ),
            
            FormActions(
                Submit('submit', 'Save Review', css_class='btn btn-primary')
            )
        )

class TrainingForm(forms.ModelForm):
    """Training form"""
    
    class Meta:
        model = Training
        fields = [
            'title', 'description', 'training_type', 'trainer', 'location',
            'start_date', 'end_date', 'duration_hours', 'cost_per_participant',
            'materials', 'status'
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'duration_hours': forms.NumberInput(attrs={'step': '0.5'}),
            'cost_per_participant': forms.NumberInput(attrs={'step': '0.01'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'title',
            'description',
            Row(
                Column('training_type', css_class='form-group col-md-6'),
                Column('trainer', css_class='form-group col-md-6'),
            ),
            'location',
            Row(
                Column('start_date', css_class='form-group col-md-4'),
                Column('end_date', css_class='form-group col-md-4'),
                Column('duration_hours', css_class='form-group col-md-4'),
            ),
            Row(
                Column('cost_per_participant', css_class='form-group col-md-6'),
                Column('status', css_class='form-group col-md-6'),
            ),
            'materials',
            FormActions(
                Submit('submit', 'Save Training', css_class='btn btn-primary')
            )
        )

class PayrollForm(forms.ModelForm):
    """Payroll form"""
    
    class Meta:
        model = Payroll
        fields = [
            'employee', 'pay_period_start', 'pay_period_end', 'basic_salary',
            'hourly_rate', 'hours_worked', 'overtime_hours', 'overtime_rate',
            'transport_allowance', 'meal_allowance', 'housing_allowance',
            'other_allowances', 'commission', 'bonus', 'tax_deduction',
            'nhif_deduction', 'nssf_deduction', 'loan_deduction',
            'advance_deduction', 'other_deductions', 'payment_method', 'notes'
        ]
        widgets = {
            'pay_period_start': forms.DateInput(attrs={'type': 'date'}),
            'pay_period_end': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add step attribute to all decimal fields
        decimal_fields = [
            'basic_salary', 'hourly_rate', 'hours_worked', 'overtime_hours',
            'overtime_rate', 'transport_allowance', 'meal_allowance',
            'housing_allowance', 'other_allowances', 'commission', 'bonus',
            'tax_deduction', 'nhif_deduction', 'nssf_deduction',
            'loan_deduction', 'advance_deduction', 'other_deductions'
        ]
        
        for field in decimal_fields:
            self.fields[field].widget.attrs['step'] = '0.01'
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h5>Payroll Information</h5>'),
            Row(
                Column('employee', css_class='form-group col-md-4'),
                Column('pay_period_start', css_class='form-group col-md-4'),
                Column('pay_period_end', css_class='form-group col-md-4'),
            ),
            
            HTML('<h5 class="mt-4">Basic Pay</h5>'),
            Row(
                Column('basic_salary', css_class='form-group col-md-6'),
                Column('hourly_rate', css_class='form-group col-md-6'),
            ),
            Row(
                Column('hours_worked', css_class='form-group col-md-4'),
                Column('overtime_hours', css_class='form-group col-md-4'),
                Column('overtime_rate', css_class='form-group col-md-4'),
            ),
            
            HTML('<h5 class="mt-4">Allowances & Bonuses</h5>'),
            Row(
                Column('transport_allowance', css_class='form-group col-md-4'),
                Column('meal_allowance', css_class='form-group col-md-4'),
                Column('housing_allowance', css_class='form-group col-md-4'),
            ),
            Row(
                Column('other_allowances', css_class='form-group col-md-4'),
                Column('commission', css_class='form-group col-md-4'),
                Column('bonus', css_class='form-group col-md-4'),
            ),
            
            HTML('<h5 class="mt-4">Deductions</h5>'),
            Row(
                Column('tax_deduction', css_class='form-group col-md-4'),
                Column('nhif_deduction', css_class='form-group col-md-4'),
                Column('nssf_deduction', css_class='form-group col-md-4'),
            ),
            Row(
                Column('loan_deduction', css_class='form-group col-md-4'),
                Column('advance_deduction', css_class='form-group col-md-4'),
                Column('other_deductions', css_class='form-group col-md-4'),
            ),
            
            HTML('<h5 class="mt-4">Payment Details</h5>'),
            Row(
                Column('payment_method', css_class='form-group col-md-6'),
                Column('notes', css_class='form-group col-md-6'),
            ),
            
            FormActions(
                Submit('submit', 'Save Payroll', css_class='btn btn-primary')
            )
        )