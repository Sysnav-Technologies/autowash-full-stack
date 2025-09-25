from django import template
from django.conf import settings
from django.templatetags.static import static
from django.utils.safestring import mark_safe
import os

register = template.Library()

@register.simple_tag
def media_url(file_field):
    """
    Generate the correct media URL based on the deployment environment.
    
    For cPanel deployment, explicitly includes public_html prefix in URL
    since Apache serves from the public_html directory structure.
    For local development, uses standard /media/ URL.
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
    
    # For cPanel, explicitly add public_html prefix to URL
    if getattr(settings, 'CPANEL', False):
        return mark_safe(f"/public_html/media/{clean_path}")
    else:
        # For local development and other environments
        media_url_setting = getattr(settings, 'MEDIA_URL', '/media/')
        if not media_url_setting.endswith('/'):
            media_url_setting += '/'
        return mark_safe(f"{media_url_setting}{clean_path}")

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