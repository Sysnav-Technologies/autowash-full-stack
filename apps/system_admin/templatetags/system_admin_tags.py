"""
Custom template tags and filters for system_admin app
"""
from django import template

register = template.Library()


@register.filter
def subtract(value, arg):
    """
    Subtract the arg from the value.
    Usage: {{ value|subtract:arg }}
    """
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def multiply(value, arg):
    """
    Multiply the value by the arg.
    Usage: {{ value|multiply:arg }}
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter  
def divide(value, arg):
    """
    Divide the value by the arg.
    Usage: {{ value|divide:arg }}
    """
    try:
        if float(arg) == 0:
            return 0
        return float(value) / float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def percentage(value, total):
    """
    Calculate percentage of value from total.
    Usage: {{ value|percentage:total }}
    """
    try:
        if float(total) == 0:
            return 0
        return (float(value) / float(total)) * 100
    except (ValueError, TypeError):
        return 0


@register.filter
def format_bytes(bytes_value):
    """
    Format bytes into human readable format.
    Usage: {{ bytes_value|format_bytes }}
    """
    try:
        bytes_value = float(bytes_value)
        if bytes_value == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB", "PB"]
        i = 0
        while bytes_value >= 1024.0 and i < len(size_names) - 1:
            bytes_value /= 1024.0
            i += 1
        
        return f"{bytes_value:.1f} {size_names[i]}"
    except (ValueError, TypeError):
        return "0 B"


@register.filter
def format_duration(seconds):
    """
    Format seconds into human readable duration.
    Usage: {{ seconds|format_duration }}
    """
    try:
        seconds = int(float(seconds))
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes}m {secs}s"
        elif seconds < 86400:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"
        else:
            days = seconds // 86400
            hours = (seconds % 86400) // 3600
            return f"{days}d {hours}h"
    except (ValueError, TypeError):
        return "0s"


@register.filter
def safe_round(value, places=2):
    """
    Safely round a value to specified decimal places.
    Usage: {{ value|safe_round:2 }}
    """
    try:
        return round(float(value), int(places))
    except (ValueError, TypeError):
        return 0


@register.filter
def status_class(value, thresholds="70,90"):
    """
    Return CSS class based on value and thresholds.
    Usage: {{ cpu_percent|status_class:"70,90" }}
    Returns: 'optimal', 'warning', or 'critical'
    """
    try:
        value = float(value)
        warning_threshold, critical_threshold = map(float, thresholds.split(','))
        
        if value < warning_threshold:
            return 'optimal'
        elif value < critical_threshold:
            return 'warning'
        else:
            return 'critical'
    except (ValueError, TypeError):
        return 'unknown'


@register.filter
def get_item(dictionary, key):
    """
    Get item from dictionary by key.
    Usage: {{ dict|get_item:key }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None


@register.simple_tag
def calculate_free_percentage(used_percent):
    """
    Calculate free percentage from used percentage.
    Usage: {% calculate_free_percentage memory_info.usage_percent %}
    """
    try:
        return 100 - float(used_percent)
    except (ValueError, TypeError):
        return 0