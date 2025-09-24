from django import template
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
import time

register = template.Library()

@register.simple_tag
def cache_bust():
    """Generate a cache-busting parameter."""
    return int(time.time())

@register.simple_tag
def order_cache_key(order_id, tenant_id=None):
    """Generate unique cache key for order data."""
    if tenant_id:
        return f"order_{tenant_id}_{order_id}_{int(time.time() / 30)}"  # 30-second window
    return f"order_{order_id}_{int(time.time() / 30)}"

@register.simple_tag(takes_context=True)
def clear_order_cache(context, order_id=None):
    """Clear order-related cache."""
    request = context.get('request')
    tenant_id = getattr(request, 'tenant', None) and request.tenant.id
    
    if tenant_id and order_id:
        # Clear specific order cache
        cache_keys = [
            f"order_{tenant_id}_{order_id}",
            f"order_detail_{tenant_id}_{order_id}",
            f"order_list_{tenant_id}",
        ]
        cache.delete_many(cache_keys)
    elif tenant_id:
        # Clear all order cache for tenant
        cache.delete(f"order_list_{tenant_id}")
    
    return ""  # Template tag returns empty string

@register.simple_tag
def now_timestamp():
    """Get current timestamp for cache busting."""
    return int(time.time())

@register.simple_tag  
def cache_buster():
    """Simple cache busting tag - returns current timestamp"""
    return int(time.time())

@register.simple_tag
def version_cache_bust():
    """Cache bust using version from settings"""
    return getattr(settings, 'STATIC_VERSION', int(time.time()))