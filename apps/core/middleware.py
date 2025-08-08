"""
Clean middleware for MySQL multi-tenant system
Replaces the old django-tenants middleware
"""
from django.utils import timezone
from django.contrib.auth.models import AnonymousUser
from django.conf import settings
from django.shortcuts import redirect
from django.contrib import messages
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


class BusinessStatusMiddleware:
    """
    Check business status and enforce proper authentication flow
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.exempt_paths = [
            '/auth/login/',
            '/auth/logout/',
            '/auth/register/',
            '/auth/verify-email/',
            '/auth/password-reset/',
            '/auth/business/register/',
            '/auth/verification-pending/',
            '/auth/dashboard/',
            '/subscriptions/select/',
            '/static/',
            '/media/',
            '/admin/',
            '/system-admin/',
        ]
    
    def __call__(self, request):
        # Skip if not authenticated or on exempt paths
        if not request.user.is_authenticated or self.is_exempt_path(request.path):
            response = self.get_response(request)
            return response
        
        # Skip email verification check - handled by dashboard_redirect
        if not request.user.is_active:
            response = self.get_response(request)
            return response
        
        # Check if user owns a business
        business = request.user.owned_tenants.first()
        
        if business:
            # Check the business authentication flow
            if not self.is_business_ready(business) and not self.is_exempt_path(request.path):
                # Redirect to appropriate step in the flow
                redirect_url = self.get_flow_redirect_url(business)
                if redirect_url and request.path != redirect_url:
                    return redirect(redirect_url)
        
        response = self.get_response(request)
        return response
    
    def is_exempt_path(self, path):
        """Check if path is exempt from business status checks"""
        return any(path.startswith(exempt) for exempt in self.exempt_paths)
    
    def is_business_ready(self, business):
        """Check if business is ready for normal operation"""
        return (
            business.is_approved and 
            business.is_verified and 
            business.is_active and
            hasattr(business, 'subscription') and 
            business.subscription and
            business.subscription.is_active
        )
    
    def get_flow_redirect_url(self, business):
        """Get the appropriate redirect URL based on business status"""
        # Business registration incomplete
        if not business.name or not business.phone or not business.email:
            return '/auth/business/register/'
        
        # No subscription selected
        if not hasattr(business, 'subscription') or not business.subscription:
            return '/subscriptions/select/'
        
        # Not approved by admin
        if not business.is_approved:
            return '/auth/verification-pending/'
        
        # Subscription not active (trial expired)
        if not business.subscription.is_active:
            # Check if trial period has started
            from datetime import timedelta
            from django.utils import timezone
            
            if business.approved_at:
                trial_end = business.approved_at + timedelta(days=7)
                if timezone.now() > trial_end:
                    return '/subscriptions/upgrade/'
            
            return '/auth/verification-pending/'
        
        # Not verified (database setup incomplete)
        if not business.is_verified:
            return '/auth/verification-pending/'
        
        return None
