"""
Custom form fields for the Autowash application
"""
from django import forms
from django.core.exceptions import ValidationError
from phonenumber_field.formfields import PhoneNumberField as BasePhoneNumberField
from phonenumber_field.phonenumber import PhoneNumber
from .widgets import PhoneNumberWidget, SimplePhoneNumberWidget
import phonenumbers
import re


class EnhancedPhoneNumberField(BasePhoneNumberField):
    """
    Enhanced phone number field with country code selection
    """
    widget = PhoneNumberWidget
    
    def __init__(self, *args, **kwargs):
        # Allow simple widget if specified
        if kwargs.get('widget') == 'simple':
            kwargs['widget'] = SimplePhoneNumberWidget()
        elif 'widget' not in kwargs:
            kwargs['widget'] = PhoneNumberWidget()
        
        super().__init__(*args, **kwargs)
    
    def clean(self, value):
        # More lenient validation
        if not value and not self.required:
            return None
        
        if not value and self.required:
            raise ValidationError(self.error_messages['required'])
        
        try:
            # Try to parse and validate
            phone_number = PhoneNumber.from_string(value)
            if not phone_number.is_valid():
                # Still allow if it looks like a phone number
                if self._looks_like_phone_number(value):
                    return PhoneNumber.from_string(value, None)
                raise ValidationError('Enter a valid phone number.')
            return phone_number
        except Exception:
            # Fallback validation - just check if it looks reasonable
            if self._looks_like_phone_number(value):
                try:
                    return PhoneNumber.from_string(value, None)
                except:
                    raise ValidationError('Enter a valid phone number.')
            raise ValidationError('Enter a valid phone number.')
    
    def _looks_like_phone_number(self, value):
        """
        Basic check if value looks like a phone number
        """
        if not value:
            return False
        
        # Remove spaces, dashes, parentheses
        cleaned = re.sub(r'[\s\-\(\)]', '', str(value))
        
        # Should start with + and have at least 7 digits
        if cleaned.startswith('+'):
            digits = re.sub(r'[^\d]', '', cleaned[1:])
            return len(digits) >= 7 and len(digits) <= 15
        
        # Or just be a reasonable number of digits
        digits = re.sub(r'[^\d]', '', cleaned)
        return len(digits) >= 7 and len(digits) <= 15


class FlexibleUsernameField(forms.CharField):
    """
    Username field that allows spaces and is more flexible
    """
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 150)
        kwargs.setdefault('help_text', 'You can use your full name or a username. Most characters are allowed.')
        super().__init__(*args, **kwargs)
    
    def clean(self, value):
        value = super().clean(value)
        if not value:
            return value
        
        # Trim whitespace
        value = value.strip()
        
        # Ensure it's not just spaces
        if not value:
            raise ValidationError('Username cannot be empty or just spaces.')
        
        # Very permissive validation - allow letters, digits, spaces, and common punctuation
        # Exclude only potentially problematic characters for usernames
        if re.search(r'[<>"\\/|*?:;]', value):
            raise ValidationError(
                'Username contains invalid characters. Please avoid < > " \\ / | * ? : ;'
            )
        
        # Check for reasonable length
        if len(value) < 2:
            raise ValidationError('Username must be at least 2 characters long.')
        
        if len(value) > 150:
            raise ValidationError('Username cannot be longer than 150 characters.')
        
        return value


class FlexibleEmailField(forms.EmailField):
    """
    More lenient email field
    """
    def clean(self, value):
        value = super().clean(value)
        if value:
            value = value.lower().strip()
        return value
