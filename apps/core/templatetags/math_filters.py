# apps/core/templatetags/math_filters.py

from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()

@register.filter
def mul(value, arg):
    """Multiply the value by the argument."""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter  
def div(value, arg):
    """Divide the value by the argument."""
    try:
        arg = float(arg)
        if arg == 0:
            return 0
        return float(value) / arg
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

@register.filter
def sub(value, arg):
    """Subtract the argument from the value."""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def add_num(value, arg):
    """Add the argument to the value (alternative to built-in add for numbers)."""
    try:
        return float(value) + float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def percentage(value, total):
    """Calculate percentage of value relative to total."""
    try:
        total = float(total)
        if total == 0:
            return 0
        return (float(value) / total) * 100
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

@register.filter
def abs_value(value):
    """Return absolute value."""
    try:
        return abs(float(value))
    except (ValueError, TypeError):
        return 0

@register.filter
def to_int(value):
    """Convert value to integer."""
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return 0

@register.filter
def to_float(value):
    """Convert value to float."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0

@register.filter
def currency(value, currency_code="KES"):
    """Format value as currency."""
    try:
        amount = float(value)
        if currency_code.upper() == "KES":
            return f"KES {amount:,.2f}"
        elif currency_code.upper() == "USD":
            return f"${amount:,.2f}"
        else:
            return f"{currency_code} {amount:,.2f}"
    except (ValueError, TypeError):
        return f"{currency_code} 0.00"

@register.filter
def format_number(value, decimals=0):
    """Format number with specified decimal places and thousand separators."""
    try:
        num = float(value)
        if decimals == 0:
            return f"{int(num):,}"
        else:
            return f"{num:,.{int(decimals)}f}"
    except (ValueError, TypeError):
        return "0"

@register.filter
def range_filter(value):
    """Create a range for use in templates."""
    try:
        return range(int(value))
    except (ValueError, TypeError):
        return range(0)

@register.filter
def get_item(dictionary, key):
    """Get item from dictionary by key."""
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None

@register.filter
def calculate_growth(current, previous):
    """Calculate growth percentage between two values."""
    try:
        current = float(current)
        previous = float(previous)
        if previous == 0:
            return 100 if current > 0 else 0
        return ((current - previous) / previous) * 100
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

@register.filter
def format_duration(seconds):
    """Format seconds into human readable duration."""
    try:
        seconds = int(seconds)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    except (ValueError, TypeError):
        return "0s"