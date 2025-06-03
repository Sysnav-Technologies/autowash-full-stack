from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, timedelta
import json

from .models import (
    ReportTemplate, Dashboard, ReportWidget, 
    ReportSchedule, KPI, GeneratedReport
)

class ReportTemplateForm(forms.ModelForm):
    """Form for creating and editing report templates"""
    
    class Meta:
        model = ReportTemplate
        fields = [
            'name', 'description', 'report_type', 'data_sources',
            'filters', 'columns', 'aggregations', 'charts',
            'is_scheduled', 'frequency', 'schedule_time', 'schedule_day',
            'is_public', 'allowed_roles', 'auto_email', 'email_recipients'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter report name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Report description'}),
            'report_type': forms.Select(attrs={'class': 'form-select'}),
            'frequency': forms.Select(attrs={'class': 'form-select'}),
            'schedule_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'schedule_day': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 31}),
            'data_sources': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 4,
                'placeholder': 'Enter data sources as JSON array, e.g., ["customers", "services"]'
            }),
            'filters': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 4,
                'placeholder': 'Enter default filters as JSON object, e.g., {"status": "active"}'
            }),
            'columns': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 4,
                'placeholder': 'Enter columns as JSON array, e.g., ["name", "email", "phone"]'
            }),
            'aggregations': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3,
                'placeholder': 'Enter aggregations as JSON object, e.g., {"total_revenue": "sum"}'
            }),
            'charts': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 4,
                'placeholder': 'Enter chart configurations as JSON array'
            }),
            'allowed_roles': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 2,
                'placeholder': 'Enter allowed roles as JSON array, e.g., ["owner", "manager"]'
            }),
            'email_recipients': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 2,
                'placeholder': 'Enter email addresses as JSON array'
            }),
            'is_scheduled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'auto_email': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make JSON fields more user-friendly
        if self.instance.pk:
            # Convert JSON fields to strings for editing
            json_fields = ['data_sources', 'filters', 'columns', 'aggregations', 'charts', 'allowed_roles', 'email_recipients']
            for field in json_fields:
                if hasattr(self.instance, field):
                    value = getattr(self.instance, field)
                    if value:
                        self.fields[field].initial = json.dumps(value, indent=2)
    
    def clean_data_sources(self):
        data = self.cleaned_data['data_sources']
        if data:
            try:
                parsed = json.loads(data)
                if not isinstance(parsed, list):
                    raise ValidationError("Data sources must be a JSON array")
                return parsed
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format for data sources")
        return []
    
    def clean_filters(self):
        data = self.cleaned_data['filters']
        if data:
            try:
                parsed = json.loads(data)
                if not isinstance(parsed, dict):
                    raise ValidationError("Filters must be a JSON object")
                return parsed
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format for filters")
        return {}
    
    def clean_columns(self):
        data = self.cleaned_data['columns']
        if data:
            try:
                parsed = json.loads(data)
                if not isinstance(parsed, list):
                    raise ValidationError("Columns must be a JSON array")
                return parsed
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format for columns")
        return []
    
    def clean_aggregations(self):
        data = self.cleaned_data['aggregations']
        if data:
            try:
                parsed = json.loads(data)
                if not isinstance(parsed, dict):
                    raise ValidationError("Aggregations must be a JSON object")
                return parsed
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format for aggregations")
        return {}
    
    def clean_charts(self):
        data = self.cleaned_data['charts']
        if data:
            try:
                parsed = json.loads(data)
                if not isinstance(parsed, list):
                    raise ValidationError("Charts must be a JSON array")
                return parsed
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format for charts")
        return []
    
    def clean_allowed_roles(self):
        data = self.cleaned_data['allowed_roles']
        if data:
            try:
                parsed = json.loads(data)
                if not isinstance(parsed, list):
                    raise ValidationError("Allowed roles must be a JSON array")
                return parsed
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format for allowed roles")
        return []
    
    def clean_email_recipients(self):
        data = self.cleaned_data['email_recipients']
        if data:
            try:
                parsed = json.loads(data)
                if not isinstance(parsed, list):
                    raise ValidationError("Email recipients must be a JSON array")
                # Validate email format
                for email in parsed:
                    forms.EmailField().clean(email)
                return parsed
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format for email recipients")
            except ValidationError:
                raise ValidationError("Invalid email address in recipients list")
        return []


class ReportWidgetForm(forms.ModelForm):
    """Form for creating and editing report widgets"""
    
    class Meta:
        model = ReportWidget
        fields = [
            'name', 'widget_type', 'chart_type', 'title', 'description',
            'data_source', 'query_config', 'aggregation_config', 
            'display_config', 'grid_position', 'cache_duration',
            'required_role', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter widget name'
            }),
            'widget_type': forms.Select(attrs={
                'class': 'form-control',
                'id': 'widget-type-select'
            }),
            'chart_type': forms.Select(attrs={
                'class': 'form-control',
                'id': 'chart-type-select'
            }),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Display title for the widget'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Widget description (optional)'
            }),
            'data_source': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., customers.Customer, services.Service'
            }),
            'query_config': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'JSON configuration for data queries'
            }),
            'aggregation_config': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'JSON configuration for aggregations'
            }),
            'display_config': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'JSON configuration for display settings'
            }),
            'grid_position': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': '{"x": 0, "y": 0, "width": 4, "height": 3}'
            }),
            'cache_duration': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 60,
                'max': 86400,
                'step': 60
            }),
            'required_role': forms.Select(attrs={
                'class': 'form-control'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
        help_texts = {
            'cache_duration': 'Cache duration in seconds (60-86400)',
            'query_config': 'JSON object with filters and query parameters',
            'aggregation_config': 'JSON object with aggregation functions (sum, avg, count, etc.)',
            'display_config': 'JSON object with colors, formatting, and styling options',
            'grid_position': 'JSON object with x, y, width, height for dashboard grid'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set initial values for JSON fields
        json_fields = ['query_config', 'aggregation_config', 'display_config', 'grid_position']
        for field_name in json_fields:
            if self.instance and self.instance.pk:
                field_value = getattr(self.instance, field_name)
                if field_value:
                    self.fields[field_name].initial = json.dumps(field_value, indent=2)
                else:
                    self.fields[field_name].initial = '{}'
            else:
                self.fields[field_name].initial = '{}'
        
        # Set default grid position for new widgets
        if not self.instance.pk:
            self.fields['grid_position'].initial = '{"x": 0, "y": 0, "width": 4, "height": 3}'

    def clean_query_config(self):
        """Validate query_config is valid JSON"""
        data = self.cleaned_data['query_config']
        if data:
            try:
                json.loads(data)
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format for query configuration")
        return data

    def clean_aggregation_config(self):
        """Validate aggregation_config is valid JSON"""
        data = self.cleaned_data['aggregation_config']
        if data:
            try:
                json.loads(data)
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format for aggregation configuration")
        return data

    def clean_display_config(self):
        """Validate display_config is valid JSON"""
        data = self.cleaned_data['display_config']
        if data:
            try:
                json.loads(data)
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format for display configuration")
        return data

    def clean_grid_position(self):
        """Validate grid_position is valid JSON with required fields"""
        data = self.cleaned_data['grid_position']
        if data:
            try:
                position = json.loads(data)
                required_fields = ['x', 'y', 'width', 'height']
                for field in required_fields:
                    if field not in position:
                        raise ValidationError(f"Grid position must include '{field}' field")
                    if not isinstance(position[field], int) or position[field] < 0:
                        raise ValidationError(f"Grid position '{field}' must be a non-negative integer")
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format for grid position")
        return data

    def clean(self):
        """Additional form validation"""
        cleaned_data = super().clean()
        widget_type = cleaned_data.get('widget_type')
        chart_type = cleaned_data.get('chart_type')
        
        # Chart type is required for chart widgets
        if widget_type == 'chart' and not chart_type:
            raise ValidationError("Chart type is required for chart widgets")
        
        return cleaned_data

    def save(self, commit=True):
        """Save the form and convert JSON strings to objects"""
        instance = super().save(commit=False)
        
        # Convert JSON strings to objects
        json_fields = ['query_config', 'aggregation_config', 'display_config', 'grid_position']
        for field_name in json_fields:
            field_value = self.cleaned_data.get(field_name)
            if field_value:
                try:
                    setattr(instance, field_name, json.loads(field_value))
                except json.JSONDecodeError:
                    setattr(instance, field_name, {})
            else:
                setattr(instance, field_name, {})
        
        if commit:
            instance.save()
        return instance


class ReportScheduleForm(forms.ModelForm):
    """Form for creating and editing report schedules"""
    
    class Meta:
        model = ReportSchedule
        fields = [
            'template', 'is_active', 'frequency', 'schedule_time', 
            'schedule_day', 'schedule_weekday', 'email_enabled',
            'email_recipients', 'email_subject', 'email_body'
        ]
        widgets = {
            'template': forms.Select(attrs={
                'class': 'form-control'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'frequency': forms.Select(attrs={
                'class': 'form-control',
                'id': 'frequency-select'
            }),
            'schedule_time': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'schedule_day': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 28,
                'placeholder': 'Day of month (1-28)'
            }),
            'schedule_weekday': forms.Select(attrs={
                'class': 'form-control'
            }, choices=[
                ('', 'Select day of week'),
                (0, 'Monday'),
                (1, 'Tuesday'),
                (2, 'Wednesday'),
                (3, 'Thursday'),
                (4, 'Friday'),
                (5, 'Saturday'),
                (6, 'Sunday'),
            ]),
            'email_enabled': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'email_recipients': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'JSON array of email addresses'
            }),
            'email_subject': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email subject template'
            }),
            'email_body': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Email body template'
            })
        }
        help_texts = {
            'schedule_day': 'For monthly reports, specify day of month (1-28)',
            'schedule_weekday': 'For weekly reports, specify day of week',
            'email_recipients': 'JSON array of email addresses, e.g., ["user1@example.com", "user2@example.com"]',
            'email_subject': 'Subject line for scheduled report emails',
            'email_body': 'Email body content for scheduled reports'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter templates to only active ones
        self.fields['template'].queryset = ReportTemplate.objects.filter(is_active=True)
        
        # Set initial values
        if self.instance and self.instance.pk and self.instance.email_recipients:
            self.fields['email_recipients'].initial = json.dumps(self.instance.email_recipients, indent=2)
        else:
            self.fields['email_recipients'].initial = '[]'

    def clean_schedule_day(self):
        """Validate schedule day is within valid range"""
        day = self.cleaned_data.get('schedule_day')
        if day and (day < 1 or day > 28):
            raise ValidationError("Schedule day must be between 1 and 28")
        return day

    def clean_email_recipients(self):
        """Validate email recipients is valid JSON array"""
        data = self.cleaned_data['email_recipients']
        if data:
            try:
                recipients = json.loads(data)
                if not isinstance(recipients, list):
                    raise ValidationError("Email recipients must be a JSON array")
                
                # Validate email addresses
                from django.core.validators import validate_email
                for email in recipients:
                    validate_email(email)
                    
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format for email recipients")
            except forms.ValidationError:
                raise ValidationError("Invalid email address in recipients list")
        return data

    def clean(self):
        """Additional form validation"""
        cleaned_data = super().clean()
        frequency = cleaned_data.get('frequency')
        schedule_day = cleaned_data.get('schedule_day')
        schedule_weekday = cleaned_data.get('schedule_weekday')
        
        # Validate schedule parameters based on frequency
        if frequency == 'monthly' and not schedule_day:
            raise ValidationError("Schedule day is required for monthly reports")
        
        if frequency == 'weekly' and schedule_weekday is None:
            raise ValidationError("Schedule weekday is required for weekly reports")
        
        return cleaned_data

    def save(self, commit=True):
        """Save the form and convert JSON strings to objects"""
        instance = super().save(commit=False)
        
        # Convert email recipients JSON to list
        email_recipients_data = self.cleaned_data.get('email_recipients')
        if email_recipients_data:
            try:
                instance.email_recipients = json.loads(email_recipients_data)
            except json.JSONDecodeError:
                instance.email_recipients = []
        else:
            instance.email_recipients = []
        
        if commit:
            instance.save()
            # Calculate next generation time
            instance.calculate_next_generation()
        
        return instance


class KPIForm(forms.ModelForm):
    """Form for creating and editing KPIs"""
    
    class Meta:
        model = KPI
        fields = [
            'name', 'kpi_type', 'description', 'target_value', 'current_value',
            'calculation_method', 'data_source', 'measurement_period',
            'unit', 'format_string', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter KPI name'
            }),
            'kpi_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe what this KPI measures'
            }),
            'target_value': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Target value to achieve'
            }),
            'current_value': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Current value'
            }),
            'calculation_method': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., sum_revenue_daily, count_customers_monthly'
            }),
            'data_source': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., BusinessMetrics, customers.Customer'
            }),
            'measurement_period': forms.Select(attrs={
                'class': 'form-control'
            }),
            'unit': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., KES, customers, %, hours'
            }),
            'format_string': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '{value} {unit}'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
        help_texts = {
            'calculation_method': 'Method used to calculate this KPI automatically',
            'data_source': 'Primary data source for this KPI calculation',
            'format_string': 'Format template for displaying values. Use {value} and {unit} placeholders',
            'target_value': 'The goal value you want to achieve for this KPI',
            'current_value': 'Current actual value of this KPI'
        }

    def clean_target_value(self):
        """Validate target value is positive"""
        value = self.cleaned_data.get('target_value')
        if value is not None and value <= 0:
            raise ValidationError("Target value must be greater than zero")
        return value

    def clean_current_value(self):
        """Validate current value is not negative"""
        value = self.cleaned_data.get('current_value')
        if value is not None and value < 0:
            raise ValidationError("Current value cannot be negative")
        return value

    def clean_format_string(self):
        """Validate format string contains required placeholders"""
        format_str = self.cleaned_data.get('format_string')
        if format_str and '{value}' not in format_str:
            raise ValidationError("Format string must contain {value} placeholder")
        return format_str


class ReportFilterForm(forms.Form):
    """Form for filtering report generation parameters"""
    
    date_from = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        help_text='Start date for the report'
    )
    
    date_to = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        help_text='End date for the report'
    )
    
    format_type = forms.ChoiceField(
        choices=[
            ('pdf', 'PDF'),
            ('excel', 'Excel'),
            ('csv', 'CSV'),
        ],
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input'
        }),
        initial='pdf',
        help_text='Select output format for the report'
    )
    
    include_charts = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text='Include charts and graphs in the report'
    )
    
    include_summary = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text='Include executive summary in the report'
    )

    def __init__(self, *args, **kwargs):
        self.template = kwargs.pop('template', None)
        super().__init__(*args, **kwargs)
        
        # Set default date range (last 30 days)
        today = timezone.now().date()
        self.fields['date_to'].initial = today
        self.fields['date_from'].initial = today - timezone.timedelta(days=30)
        
        # Add dynamic filters based on template
        if self.template:
            self.add_template_specific_filters()

    def add_template_specific_filters(self):
        """Add filters specific to the report template"""
        if not self.template or not self.template.filters:
            return
        
        # Add customer filter for customer reports
        if self.template.report_type == 'customer':
            from apps.customers.models import Customer
            self.fields['customer_type'] = forms.ChoiceField(
                choices=[
                    ('', 'All Customers'),
                    ('regular', 'Regular Customers'),
                    ('vip', 'VIP Customers'),
                ],
                required=False,
                widget=forms.Select(attrs={'class': 'form-control'})
            )
        
        # Add employee filter for employee reports
        elif self.template.report_type == 'employee':
            from apps.employees.models import Employee
            self.fields['employee_role'] = forms.ChoiceField(
                choices=[
                    ('', 'All Employees'),
                    ('owner', 'Owner'),
                    ('manager', 'Manager'),
                    ('supervisor', 'Supervisor'),
                    ('attendant', 'Attendant'),
                ],
                required=False,
                widget=forms.Select(attrs={'class': 'form-control'})
            )
        
        # Add service filter for service reports
        elif self.template.report_type == 'service':
            from apps.services.models import Service
            self.fields['service_category'] = forms.ModelChoiceField(
                queryset=Service.objects.filter(is_active=True),
                required=False,
                empty_label='All Services',
                widget=forms.Select(attrs={'class': 'form-control'})
            )

    def clean(self):
        """Validate form data"""
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        
        if date_from and date_to:
            # Ensure date_from is not after date_to
            if date_from > date_to:
                raise ValidationError("Start date must be before or equal to end date")
            
            # Ensure date range is not too large (max 1 year)
            if (date_to - date_from).days > 365:
                raise ValidationError("Date range cannot exceed 1 year")
            
            # Ensure dates are not in the future
            today = timezone.now().date()
            if date_from > today:
                raise ValidationError("Start date cannot be in the future")
            if date_to > today:
                raise ValidationError("End date cannot be in the future")
        
        return cleaned_data

    def get_filter_params(self):
        """Get filter parameters for report generation"""
        if not self.is_valid():
            return {}
        
        params = {
            'date_from': self.cleaned_data['date_from'],
            'date_to': self.cleaned_data['date_to'],
            'format_type': self.cleaned_data['format_type'],
            'include_charts': self.cleaned_data['include_charts'],
            'include_summary': self.cleaned_data['include_summary'],
        }
        
        # Add template-specific filters
        if self.template:
            if self.template.report_type == 'customer' and 'customer_type' in self.cleaned_data:
                params['customer_type'] = self.cleaned_data['customer_type']
            elif self.template.report_type == 'employee' and 'employee_role' in self.cleaned_data:
                params['employee_role'] = self.cleaned_data['employee_role']
            elif self.template.report_type == 'service' and 'service_category' in self.cleaned_data:
                params['service_category'] = self.cleaned_data['service_category']
        
        return params

class DashboardForm(forms.ModelForm):
    """Form for creating and editing dashboards"""
    
    class Meta:
        model = Dashboard
        fields = [
            'name', 'description', 'layout', 'widgets', 'filters',
            'is_default', 'role', 'auto_refresh', 'refresh_interval'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter dashboard name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'refresh_interval': forms.NumberInput(attrs={'class': 'form-control', 'min': 30}),
            'layout': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 4,
                'placeholder': 'Enter layout configuration as JSON'
            }),
            'widgets': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3,
                'placeholder': 'Enter widget IDs as JSON array'
            }),
            'filters': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3,
                'placeholder': 'Enter global filters as JSON'
            }),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'auto_refresh': forms.CheckboxInput(attrs={'class': 'form-check-input'}),   
        }
    def __init__(self, *args, **kwargs):    
        super().__init__(*args, **kwargs)

        # Make JSON fields more user-friendly
        if self.instance.pk:
            # Convert JSON fields to strings for editing
            json_fields = ['layout', 'widgets', 'filters']
            for field in json_fields:
                if hasattr(self.instance, field):
                    value = getattr(self.instance, field)
                    if value:
                        self.fields[field].initial = json.dumps(value, indent=2)
    def clean_layout(self):
        data = self.cleaned_data['layout']
        if data:
            try:
                parsed = json.loads(data)
                if not isinstance(parsed, dict):
                    raise ValidationError("Layout must be a JSON object")
                return parsed
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format for layout")
        return {}
    def clean_widgets(self):
        data = self.cleaned_data['widgets']
        if data:
            try:
                parsed = json.loads(data)
                if not isinstance(parsed, list):
                    raise ValidationError("Widgets must be a JSON array")
                return parsed
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format for widgets")