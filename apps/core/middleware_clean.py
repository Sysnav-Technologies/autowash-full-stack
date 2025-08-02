"""
Clean middleware for MySQL multi-tenant system
Replaces the old django-tenants middleware
"""
from django.utils import timezone
from django.contrib.auth.models import AnonymousUser
from django.conf import settings
import pytz


class TimezoneMiddleware:
    """Set timezone based on user preference or business timezone"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Get timezone from tenant or user
        tz = self.get_timezone(request)
        if tz:
            timezone.activate(pytz.timezone(tz))
        else:
            timezone.deactivate()
        
        response = self.get_response(request)
        return response
    
    def get_timezone(self, request):
        """Get appropriate timezone"""
        # Priority: User preference > Tenant timezone > Default
        if hasattr(request, 'user') and request.user.is_authenticated:
            if hasattr(request.user, 'profile') and request.user.profile.timezone:
                return request.user.profile.timezone
        
        if hasattr(request, 'tenant') and request.tenant:
            return request.tenant.timezone
        
        return settings.TIME_ZONE


class UserActivityMiddleware:
    """Track user activity"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Update last activity for authenticated users
        if hasattr(request, 'user') and request.user.is_authenticated:
            if hasattr(request.user, 'profile'):
                # Don't update on every request to avoid database hits
                # Only update if last activity is more than 5 minutes old
                profile = request.user.profile
                if not profile.updated_at or \
                   (timezone.now() - profile.updated_at).seconds > 300:
                    profile.save(update_fields=['updated_at'])
        
        response = self.get_response(request)
        return response
