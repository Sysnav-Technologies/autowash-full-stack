from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def currency(value):
    """
    Formats a number as Kenyan Shilling currency.
    Usage: {{ amount|currency }}
    Returns: KSh 1,000
    """
    if value is None:
        return "KSh 0"
    
    try:
        # Convert to float and format with commas
        amount = float(value)
        formatted_amount = "{:,.0f}".format(amount)
        return mark_safe(f"KSh {formatted_amount}")
    except (ValueError, TypeError):
        return "KSh 0"

@register.filter
def currency_no_symbol(value):
    """
    Formats a number with commas but no currency symbol.
    Usage: {{ amount|currency_no_symbol }}
    Returns: 1,000
    """
    if value is None:
        return "0"
    
    try:
        amount = float(value)
        return "{:,.0f}".format(amount)
    except (ValueError, TypeError):
        return "0"