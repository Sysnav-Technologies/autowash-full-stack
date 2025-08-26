"""
Form utilities for consistent Bootstrap styling across all apps
"""

from django import forms


def apply_bootstrap_classes(form_instance, custom_classes=None):
    """
    Apply Bootstrap classes to all form fields for consistent styling.
    
    Args:
        form_instance: The form instance to apply classes to
        custom_classes: Dict of field_name: css_class to override defaults
    """
    
    # Default Bootstrap classes for different field types
    default_classes = {
        # Text inputs
        forms.TextInput: 'form-control',
        forms.EmailInput: 'form-control',
        forms.URLInput: 'form-control',
        forms.PasswordInput: 'form-control',
        forms.NumberInput: 'form-control',
        forms.DateInput: 'form-control',
        forms.DateTimeInput: 'form-control',
        forms.TimeInput: 'form-control',
        forms.Textarea: 'form-control',
        
        # Select inputs
        forms.Select: 'form-select',
        forms.SelectMultiple: 'form-select',
        
        # File inputs
        forms.FileInput: 'form-control',
        forms.ClearableFileInput: 'form-control',
        
        # Checkbox and radio
        forms.CheckboxInput: 'form-check-input',
        forms.RadioSelect: 'form-check-input',
        forms.CheckboxSelectMultiple: 'form-check-input',
    }
    
    # Apply classes to all fields
    for field_name, field in form_instance.fields.items():
        widget_class = type(field.widget)
        
        # Use custom class if provided, otherwise use default
        if custom_classes and field_name in custom_classes:
            css_class = custom_classes[field_name]
        elif widget_class in default_classes:
            css_class = default_classes[widget_class]
        else:
            # Default to form-control for unknown widgets
            css_class = 'form-control'
        
        # Apply the CSS class
        existing_class = field.widget.attrs.get('class', '')
        if existing_class:
            if css_class not in existing_class:
                field.widget.attrs['class'] = f"{existing_class} {css_class}"
        else:
            field.widget.attrs['class'] = css_class


def apply_form_placeholders(form_instance, placeholders=None):
    """
    Apply helpful placeholder text to form fields.
    
    Args:
        form_instance: The form instance to apply placeholders to
        placeholders: Dict of field_name: placeholder_text
    """
    
    # Default placeholders for common field names
    default_placeholders = {
        'name': 'Enter name',
        'first_name': 'Enter first name',
        'last_name': 'Enter last name',
        'email': 'Enter email address',
        'phone': 'Enter phone number',
        'address': 'Enter address',
        'city': 'Enter city',
        'description': 'Enter description',
        'notes': 'Enter notes',
        'amount': 'Enter amount',
        'price': 'Enter price',
        'quantity': 'Enter quantity',
        'username': 'Enter username',
        'password': 'Enter password',
        'website': 'https://example.com',
        'url': 'https://example.com',
    }
    
    # Merge custom placeholders with defaults
    if placeholders:
        default_placeholders.update(placeholders)
    
    # Apply placeholders
    for field_name, placeholder in default_placeholders.items():
        if field_name in form_instance.fields:
            field = form_instance.fields[field_name]
            # Only apply placeholder to text-like inputs
            if isinstance(field.widget, (
                forms.TextInput, forms.EmailInput, forms.URLInput,
                forms.NumberInput, forms.Textarea
            )):
                field.widget.attrs['placeholder'] = placeholder


def setup_crispy_form_helper(form_instance, submit_text='Save', submit_class='btn btn-primary'):
    """
    Set up a basic crispy form helper for consistent form rendering.
    
    Args:
        form_instance: The form instance to set up crispy helper for
        submit_text: Text for the submit button
        submit_class: CSS class for the submit button
    """
    try:
        from crispy_forms.helper import FormHelper
        from crispy_forms.layout import Submit
        from crispy_forms.bootstrap import FormActions
        
        form_instance.helper = FormHelper()
        form_instance.helper.form_method = 'post'
        form_instance.helper.add_input(Submit('submit', submit_text, css_class=submit_class))
        
    except ImportError:
        # Crispy forms not available, skip
        pass


def enhance_form(form_instance, custom_classes=None, placeholders=None, 
                use_crispy=True, submit_text='Save', submit_class='btn btn-primary'):
    """
    Comprehensive form enhancement with Bootstrap classes, placeholders, and crispy forms.
    
    Args:
        form_instance: The form instance to enhance
        custom_classes: Dict of field_name: css_class to override defaults
        placeholders: Dict of field_name: placeholder_text
        use_crispy: Whether to set up crispy forms helper
        submit_text: Text for the submit button
        submit_class: CSS class for the submit button
    """
    
    # Apply Bootstrap classes
    apply_bootstrap_classes(form_instance, custom_classes)
    
    # Apply placeholders
    apply_form_placeholders(form_instance, placeholders)
    
    # Set up crispy forms if requested
    if use_crispy:
        setup_crispy_form_helper(form_instance, submit_text, submit_class)


# Field validation helpers
def validate_phone_number(value):
    """Validate phone number format"""
    import re
    
    # Remove any spaces, dashes, or parentheses
    cleaned = re.sub(r'[\s\-\(\)]', '', value)
    
    # Check if it's a valid format (simple validation)
    if not re.match(r'^(\+254|254|0)[17]\d{8}$', cleaned):
        raise forms.ValidationError('Enter a valid phone number (e.g., +254712345678 or 0712345678)')
    
    return cleaned


def validate_email_address(value):
    """Enhanced email validation"""
    from django.core.validators import EmailValidator
    from django.core.exceptions import ValidationError
    
    validator = EmailValidator()
    try:
        validator(value)
    except ValidationError:
        raise forms.ValidationError('Enter a valid email address')
    
    return value.lower()


def validate_positive_number(value):
    """Validate that a number is positive"""
    if value <= 0:
        raise forms.ValidationError('This value must be greater than zero')
    return value


def validate_non_negative_number(value):
    """Validate that a number is not negative"""
    if value < 0:
        raise forms.ValidationError('This value cannot be negative')
    return value
