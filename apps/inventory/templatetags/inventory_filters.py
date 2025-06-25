# Create this file: apps/inventory/templatetags/inventory_filters.py

from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def sum_reorder_value(items):
    """Calculate total reorder value for a list of items"""
    total = Decimal('0')
    for item in items:
        if hasattr(item, 'suggested_order_value'):
            total += item.suggested_order_value or 0
        elif hasattr(item, 'reorder_quantity') and hasattr(item, 'unit_cost'):
            reorder_qty = item.reorder_quantity or 0
            unit_cost = item.unit_cost or 0
            total += reorder_qty * unit_cost
    return total

@register.filter
def sum_stock_value(items):
    """Calculate total stock value for a list of items"""
    total = Decimal('0')
    for item in items:
        if hasattr(item, 'stock_value'):
            total += item.stock_value or 0
        elif hasattr(item, 'current_stock') and hasattr(item, 'unit_cost'):
            stock = item.current_stock or 0
            cost = item.unit_cost or 0
            total += stock * cost
    return total

@register.filter
def sum_quantity(items):
    """Calculate total quantity for a list of items"""
    total = Decimal('0')
    for item in items:
        if hasattr(item, 'current_stock'):
            total += item.current_stock or 0
    return total

@register.filter
def sum_reorder_quantity(items):
    """Calculate total reorder quantity for a list of items"""
    total = Decimal('0')
    for item in items:
        if hasattr(item, 'suggested_order_qty'):
            total += item.suggested_order_qty or 0
        elif hasattr(item, 'reorder_quantity'):
            total += item.reorder_quantity or 0
    return total

@register.filter
def currency_format(value, currency='KES'):
    """Format currency with proper formatting"""
    try:
        value = float(value)
        if value >= 1000000:
            return f"{currency} {value/1000000:.1f}M"
        elif value >= 1000:
            return f"{currency} {value/1000:.1f}K"
        else:
            return f"{currency} {value:,.0f}"
    except (ValueError, TypeError):
        return f"{currency} 0"

@register.filter
def percentage(value, total):
    """Calculate percentage"""
    try:
        if total and total > 0:
            return (float(value) / float(total)) * 100
        return 0
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

@register.filter
def stock_status_color(status):
    """Get color class for stock status"""
    status_colors = {
        'normal': 'success',
        'low_stock': 'warning',
        'out_of_stock': 'danger',
        'overstock': 'info'
    }
    return status_colors.get(status, 'secondary')

@register.filter
def multiply(value, arg):
    """Multiply two values"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def subtract(value, arg):
    """Subtract two values"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def days_ago(date_value):
    """Calculate days ago from a date"""
    from django.utils import timezone
    from datetime import datetime
    
    try:
        if isinstance(date_value, datetime):
            delta = timezone.now() - date_value
            return delta.days
        return 0
    except:
        return 0