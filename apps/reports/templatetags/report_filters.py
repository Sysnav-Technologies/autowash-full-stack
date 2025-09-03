from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def replace(value, arg):
    """
    Replace characters in a string.
    Usage: {{ value|replace:"old,new" }}
    """
    if arg and ',' in arg:
        old, new = arg.split(',', 1)
        return value.replace(old, new)
    return value

@register.filter
def format_key(value):
    """
    Format a key by replacing underscores with spaces and title-casing
    """
    return value.replace('_', ' ').title()

@register.filter
def currency_kes(value):
    """
    Format value as Kenyan Shilling currency.
    Usage: {{ value|currency_kes }}
    """
    try:
        amount = float(value)
        return f"KES {amount:,.2f}"
    except (ValueError, TypeError):
        return "KES 0.00"

@register.filter
def currency_kes_no_decimal(value):
    """
    Format value as Kenyan Shilling currency without decimals.
    Usage: {{ value|currency_kes_no_decimal }}
    """
    try:
        amount = float(value)
        return f"KES {amount:,.0f}"
    except (ValueError, TypeError):
        return "KES 0"

@register.filter
def percentage(value):
    """
    Format value as percentage.
    Usage: {{ value|percentage }}
    """
    try:
        amount = float(value)
        return f"{amount:.1f}%"
    except (ValueError, TypeError):
        return "0.0%"
