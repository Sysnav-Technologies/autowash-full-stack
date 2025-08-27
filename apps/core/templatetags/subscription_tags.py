from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.simple_tag(takes_context=True)
def get_business_subscription(context):
    """
    Safely get business subscription from middleware cache
    """
    request = context.get('request')
    if not request:
        return None
    
    # Check if subscription is cached on the request
    if hasattr(request, 'subscription_cache'):
        return request.subscription_cache
    
    return None

@register.simple_tag(takes_context=True)
def subscription_is_active(context):
    """
    Check if business subscription is active
    """
    request = context.get('request')
    if not request:
        return False
    
    # Use cached value from middleware
    if hasattr(request, 'subscription_is_active'):
        return request.subscription_is_active
    
    return False

@register.simple_tag(takes_context=True)
def subscription_is_expired(context):
    """
    Check if business subscription is expired
    """
    request = context.get('request')
    if not request:
        return True
    
    # Use cached value from middleware
    if hasattr(request, 'subscription_is_expired'):
        return request.subscription_is_expired
    
    return True
