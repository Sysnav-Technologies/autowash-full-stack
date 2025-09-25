"""
Template tags for handling media URLs correctly across different environments (local, cPanel, etc.)
"""
from django import template
from django.conf import settings
import os

register = template.Library()

@register.simple_tag
def media_url(file_field):
    """
    Generate the correct media URL based on the deployment environment.
    
    This works exactly like Django's {% static %} tag but for media files.
    It uses Django's MEDIA_URL setting to construct URLs, ensuring
    consistency across all environments.
    """
    if not file_field:
        return ''
    
    # Get the file path relative to MEDIA_ROOT
    if hasattr(file_field, 'name'):
        file_path = file_field.name
    else:
        file_path = str(file_field)
    
    # Clean the file path - remove leading slashes
    clean_path = file_path.lstrip('/')
    
    # Use Django's MEDIA_URL setting directly (just like {% static %} uses STATIC_URL)
    # This ensures consistency with how Django handles static files
    media_url_setting = getattr(settings, 'MEDIA_URL', '/media/')
    
    # Ensure media_url ends with /
    if not media_url_setting.endswith('/'):
        media_url_setting += '/'
    
    # Construct the full URL - this works for all environments
    return f"{media_url_setting}{clean_path}"

@register.simple_tag
def business_logo_url(tenant_settings):
    """
    Generate the correct business logo URL based on the deployment environment.
    
    This tag handles the specific case of business logos that are used in
    invoices, quotations, and service points.
    """
    if hasattr(tenant_settings, 'business_logo') and tenant_settings.business_logo:
        return media_url(tenant_settings.business_logo)
    elif hasattr(tenant_settings, 'logo_url') and tenant_settings.logo_url:
        # If there's a custom logo_url, use it as-is
        return tenant_settings.logo_url
    else:
        return ''

@register.filter
def cpanel_media_url(file_field):
    """
    Filter version of media_url for use in templates like {{ image|cpanel_media_url }}
    Works exactly like Django's static filter for media files.
    """
    return media_url(file_field)