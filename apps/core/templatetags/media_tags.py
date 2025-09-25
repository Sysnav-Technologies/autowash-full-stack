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
    
    For cPanel deployments, media files are stored in public_html/media/ 
    Since public_html is the document root, they are accessible at /media/
    """
    if not file_field:
        return ''
    
    # Get the file path relative to MEDIA_ROOT
    file_path = str(file_field)
    
    if settings.CPANEL:
        # On cPanel, files are stored in public_html/media/ 
        # Since public_html is the document root, they're accessible at /media/
        return f'/media/{file_path}'
    else:
        # For local development and other environments, use the standard approach
        return file_field.url

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
        return tenant_settings.logo_url
    else:
        return ''

@register.filter
def cpanel_media_url(file_field):
    """
    Filter version of media_url for use in templates like {{ image|cpanel_media_url }}
    """
    return media_url(file_field)