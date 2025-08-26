"""
Custom widgets for the Autowash application
"""
from django import forms
from django.forms.widgets import Select, TextInput
from django.utils.html import format_html
from django.urls import reverse_lazy
import phonenumbers


class PhoneNumberWidget(forms.MultiWidget):
    """
    A widget that splits phone number input into country code and number
    """
    
    # Country codes with visible country names for searchability
    COUNTRY_CHOICES = [
        ('KE', '🇰🇪 +254 Kenya'),
        ('UG', '🇺🇬 +256 Uganda'),
        ('TZ', '🇹🇿 +255 Tanzania'),
        ('RW', '🇷🇼 +250 Rwanda'),
        ('ET', '🇪🇹 +251 Ethiopia'),
        ('SO', '🇸🇴 +252 Somalia'),
        ('SS', '🇸🇸 +211 South Sudan'),
        ('US', '🇺🇸 +1 United States'),
        ('GB', '🇬🇧 +44 United Kingdom'),
        ('CA', '🇨🇦 +1 Canada'),
        ('AU', '🇦🇺 +61 Australia'),
        ('IN', '🇮🇳 +91 India'),
        ('CN', '🇨🇳 +86 China'),
        ('JP', '🇯🇵 +81 Japan'),
        ('DE', '🇩🇪 +49 Germany'),
        ('FR', '🇫🇷 +33 France'),
        ('IT', '🇮🇹 +39 Italy'),
        ('ES', '🇪🇸 +34 Spain'),
        ('BR', '🇧🇷 +55 Brazil'),
        ('MX', '🇲🇽 +52 Mexico'),
        ('AR', '🇦🇷 +54 Argentina'),
        ('EG', '🇪🇬 +20 Egypt'),
        ('NG', '🇳🇬 +234 Nigeria'),
        ('ZA', '🇿🇦 +27 South Africa'),
        ('GH', '🇬🇭 +233 Ghana'),
        ('MA', '🇲🇦 +212 Morocco'),
        ('AE', '🇦🇪 +971 UAE'),
        ('SA', '🇸🇦 +966 Saudi Arabia'),
        ('PK', '🇵🇰 +92 Pakistan'),
        ('BD', '🇧🇩 +880 Bangladesh'),
        ('LK', '🇱🇰 +94 Sri Lanka'),
        ('MY', '🇲🇾 +60 Malaysia'),
        ('SG', '🇸🇬 +65 Singapore'),
        ('TH', '🇹🇭 +66 Thailand'),
        ('VN', '🇻🇳 +84 Vietnam'),
        ('ID', '🇮🇩 +62 Indonesia'),
        ('PH', '🇵🇭 +63 Philippines'),
        ('KR', '🇰🇷 +82 South Korea'),
        ('TR', '🇹🇷 +90 Turkey'),
        ('RU', '🇷🇺 +7 Russia'),
        ('UA', '🇺🇦 +380 Ukraine'),
        ('PL', '🇵🇱 +48 Poland'),
        ('NL', '🇳🇱 +31 Netherlands'),
        ('BE', '🇧🇪 +32 Belgium'),
        ('CH', '🇨🇭 +41 Switzerland'),
        ('AT', '🇦🇹 +43 Austria'),
        ('SE', '🇸🇪 +46 Sweden'),
        ('NO', '🇳🇴 +47 Norway'),
        ('DK', '🇩🇰 +45 Denmark'),
        ('FI', '🇫🇮 +358 Finland'),
        ('IE', '🇮🇪 +353 Ireland'),
        ('PT', '🇵🇹 +351 Portugal'),
        ('GR', '🇬🇷 +30 Greece'),
        ('CZ', '🇨🇿 +420 Czech Republic'),
        ('HU', '🇭🇺 +36 Hungary'),
        ('RO', '🇷🇴 +40 Romania'),
        ('BG', '🇧🇬 +359 Bulgaria'),
        ('HR', '🇭🇷 +385 Croatia'),
        ('SI', '🇸🇮 +386 Slovenia'),
        ('SK', '🇸🇰 +421 Slovakia'),
        ('LT', '🇱🇹 +370 Lithuania'),
        ('LV', '🇱🇻 +371 Latvia'),
        ('EE', '🇪🇪 +372 Estonia'),
    ]
    
    def __init__(self, attrs=None):
        widgets = [
            Select(choices=self.COUNTRY_CHOICES, attrs={
                'class': 'form-select country-select'
            }),
            TextInput(attrs={
                'class': 'form-control phone-number',
                'placeholder': '712345678'
            })
        ]
        super().__init__(widgets, attrs)
    
    def decompress(self, value):
        if value:
            # Try to parse the phone number
            try:
                parsed_number = phonenumbers.parse(str(value), None)
                country_code = phonenumbers.region_code_for_number(parsed_number)
                national_number = str(parsed_number.national_number)
                return [country_code, national_number]
            except:
                # If parsing fails, try to extract manually
                value_str = str(value)
                if value_str.startswith('+'):
                    # Find matching country code
                    for code, display in self.COUNTRY_CHOICES:
                        country_calling_code = phonenumbers.country_code_for_region(code)
                        if value_str.startswith(f'+{country_calling_code}'):
                            number = value_str[len(f'+{country_calling_code}'):].strip()
                            return [code, number]
                return ['KE', value_str]  # Default to Kenya
        return ['KE', '']  # Default to Kenya with empty number
    
    def value_from_datadict(self, data, files, name):
        country_code = data.get(name + '_0')
        phone_number = data.get(name + '_1')
        
        if country_code and phone_number:
            try:
                # Get the country calling code
                calling_code = phonenumbers.country_code_for_region(country_code)
                # Format as international number
                full_number = f'+{calling_code}{phone_number}'
                
                # Validate the number
                parsed_number = phonenumbers.parse(full_number, None)
                if phonenumbers.is_valid_number(parsed_number):
                    return phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164)
                else:
                    return full_number  # Return as-is if validation fails
            except:
                return f'+{phonenumbers.country_code_for_region(country_code or "KE")}{phone_number}'
        
        return None
    
    def format_output(self, rendered_widgets):
        return format_html(
            '<div class="phone-number-widget d-flex gap-2">{}{}</div>',
            rendered_widgets[0],
            rendered_widgets[1]
        )
    
    class Media:
        css = {
            'all': ('css/phone-widget.css',)
        }
        js = ('js/phone-widget.js',)


class SimplePhoneNumberWidget(TextInput):
    """
    A simpler phone number widget with country code prefix
    """
    def __init__(self, country_code='+254', attrs=None):
        if attrs is None:
            attrs = {}
        attrs.update({
            'class': 'form-control',
            'placeholder': f'{country_code}712345678',
            'pattern': r'\+[1-9]\d{1,14}',
            'title': 'Enter phone number with country code (e.g., +254712345678)'
        })
        self.country_code = country_code
        super().__init__(attrs)
    
    def format_value(self, value):
        if value and not str(value).startswith('+'):
            return f'{self.country_code}{value}'
        return value or ''
