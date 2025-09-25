"""
Subscription status middleware for handling subscription-based access control
"""
from django.shortcuts import redirect
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class SubscriptionMiddleware:
    """
    Middleware to handle subscription status and enforce proper access control
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.exempt_paths = [
            '/auth/',
            '/subscriptions/',
            '/static/',
            '/media/',
            '/admin/',
            '/system-admin/',
            '/public/',
            '/health/',
            '/api/mpesa/',
        ]
        
        # Paths that should be accessible even with expired subscriptions
        self.subscription_management_paths = [
            '/subscriptions/manage/',
            '/subscriptions/upgrade/',
            '/subscriptions/payment/',
            '/subscriptions/billing/',
            '/subscriptions/cancel/',
            '/subscriptions/payment-status/',
            '/subscriptions/ajax/',
        ]
    
    def __call__(self, request):
        # Skip if not authenticated or on exempt paths
        if not request.user.is_authenticated or self.is_exempt_path(request.path):
            response = self.get_response(request)
            return response
        
        # Skip for superusers
        if request.user.is_superuser:
            response = self.get_response(request)
            return response
        
        # Prevent redirect loops by tracking attempts
        redirect_key = f'subscription_redirects_{request.user.id}'
        if not hasattr(request, 'session'):
            # If no session, continue without subscription checks to prevent errors
            response = self.get_response(request)
            return response
            
        redirect_count = request.session.get(redirect_key, 0)
        
        # If we've already redirected too many times, skip to prevent infinite loops
        if redirect_count >= 5:
            logger.warning(f"Subscription redirect loop detected for user {request.user.id} on path {request.path}, skipping checks")
            # Reset counter after skipping
            request.session[redirect_key] = 0
            response = self.get_response(request)
            return response
        
        # Check subscription status
        redirect_url = self.check_subscription_status(request)
        if redirect_url and request.path != redirect_url and not request.path.startswith(redirect_url):
            # Increment redirect counter
            request.session[redirect_key] = redirect_count + 1
            return redirect(redirect_url)
        else:
            # Reset counter on successful page load
            request.session[redirect_key] = 0
        
        response = self.get_response(request)
        return response
    
    def is_exempt_path(self, path):
        """Check if path is exempt from subscription checks"""
        return any(path.startswith(exempt) for exempt in self.exempt_paths)
    
    def is_subscription_management_path(self, path):
        """Check if path is for subscription management"""
        # Check direct subscription paths
        if any(path.startswith(mgmt_path) for mgmt_path in self.subscription_management_paths):
            return True
        
        # Check business context subscription paths like /business/{slug}/subscriptions/
        import re
        business_subscription_pattern = r'^/business/[^/]+/subscriptions/'
        if re.match(business_subscription_pattern, path):
            return True
            
        return False
    
    def check_subscription_status(self, request):
        """
        Check subscription status and return redirect URL if needed
        """
        try:
            # Import here to avoid circular imports
            from apps.core.tenant_models import Tenant
            from apps.core.uuid_utils import is_valid_uuid, safe_uuid_convert
            
            # Get user's business using explicit database routing with UUID validation
            try:
                business = Tenant.objects.using('default').filter(owner=request.user).first()
                
                # Validate business UUID if found
                if business and hasattr(business, 'id'):
                    if not is_valid_uuid(business.id):
                        logger.error(f"Business owner {request.user.id} has business with invalid UUID: {business.id}")
                        business = None
                        
            except Exception as db_error:
                logger.error(f"Database error getting business for user {request.user.id}: {db_error}")
                business = None
            
            if not business:
                # User doesn't own a business - check if they're an employee
                try:
                    # Check if user is an employee of any verified business
                    verified_businesses = Tenant.objects.using('default').filter(
                        is_verified=True, 
                        is_active=True, 
                        is_approved=True
                    )
                    
                    employee_business = None
                    for tenant in verified_businesses:
                        try:
                            from apps.employees.models import Employee
                            from apps.core.database_router import TenantDatabaseManager
                            
                            # Ensure tenant database is registered
                            TenantDatabaseManager.add_tenant_to_settings(tenant)
                            db_alias = f"tenant_{tenant.id}"
                            
                            employee = Employee.objects.using(db_alias).filter(
                                user_id=request.user.id, 
                                is_active=True
                            ).first()
                            
                            if employee:
                                employee_business = tenant
                                break
                                
                        except Exception:
                            continue  # Skip tenant if there's an error
                    
                    if employee_business:
                        # User is an employee - use the employee's business for subscription check
                        business = employee_business
                        # Mark that this user is an employee for later checks
                        request.is_employee_access = True
                    else:
                        # User is neither owner nor employee - redirect to business registration
                        return '/auth/business/register/'
                        
                except Exception:
                    # If there's an error checking employee status, redirect to registration
                    return '/auth/business/register/'
            else:
                # User owns a business - mark as owner access
                request.is_employee_access = False
            
            # Check if business is properly set up (only for business owners, not employees)
            if not getattr(request, 'is_employee_access', False):
                if not business.is_approved or not business.is_verified or not business.is_active:
                    return '/auth/verification-pending/'
            
            # Check subscription using explicit database routing
            from apps.subscriptions.models import Subscription
            subscription = None
            
            try:
                # Import UUID utilities
                from apps.core.uuid_utils import is_valid_uuid
                
                # Force subscription queries to use default database explicitly
                # We need to refetch the business from default database to access subscription
                business_from_default = Tenant.objects.using('default').get(id=business.id)
                
                # Get subscription_id directly to avoid cross-database FK access
                subscription_id = getattr(business_from_default, 'subscription_id', None)
                
                if subscription_id:
                    # Validate subscription UUID before querying
                    if is_valid_uuid(subscription_id):
                        subscription = Subscription.objects.using('default').filter(
                            id=subscription_id
                        ).first()
                    else:
                        logger.warning(f"Invalid subscription UUID for business {business.id}: {subscription_id}")
                        subscription = None
                else:
                    # Try to find any active subscription for this business
                    subscription = Subscription.objects.using('default').filter(
                        business=business_from_default
                    ).first()
            except Exception as e:
                logger.warning(f"Error accessing subscription for business {business.id}: {e}")
                subscription = None
            
            if not subscription:
                # No subscription - only redirect business owners, not employees
                if not getattr(request, 'is_employee_access', False):
                    if business.is_verified and business.is_approved:
                        # Business is verified, go to subscription upgrade/selection
                        return f'/business/{business.slug}/subscriptions/upgrade/'
                    else:
                        # Business not verified yet, go to subscription selection
                        return '/subscriptions/select/'
                # Employees can continue working even without business subscription
                return None
            
            # Check subscription status (only enforce for business owners, not employees)
            if not subscription.is_active and not getattr(request, 'is_employee_access', False):
                # Allow access to subscription management paths
                if self.is_subscription_management_path(request.path):
                    return None
                
                # Handle different subscription statuses
                if subscription.status == 'trial':
                    # Check if trial has expired
                    if subscription.trial_end_date and timezone.now() > subscription.trial_end_date:
                        # Update status and redirect
                        subscription.status = 'expired'
                        subscription.save(using='default')
                        
                        # Allow access to subscription management paths even after expiry
                        if self.is_subscription_management_path(request.path):
                            return None
                            
                        try:
                            messages.warning(request, "Your trial period has expired. Please upgrade to continue using the service.")
                        except Exception:
                            pass  # Messages framework may not be available
                        # Redirect to upgrade page in business context if verified
                        if business.is_verified and business.is_approved:
                            return f'/business/{business.slug}/subscriptions/upgrade/'
                        else:
                            return '/subscriptions/upgrade/'
                    else:
                        # Trial is still active but waiting for verification
                        return None
                
                elif subscription.status == 'expired':
                    # Allow access to subscription management paths
                    if self.is_subscription_management_path(request.path):
                        return None
                    
                    try:
                        messages.warning(request, "Your subscription has expired. Please renew to continue using the service.")
                    except Exception:
                        pass  # Messages framework may not be available
                    # Redirect to upgrade instead of select to avoid verification loop
                    if business.is_verified and business.is_approved:
                        return f'/business/{business.slug}/subscriptions/upgrade/'
                    else:
                        return '/subscriptions/upgrade/'
                
                elif subscription.status == 'cancelled':
                    # Allow access to subscription management paths
                    if self.is_subscription_management_path(request.path):
                        return None
                    
                    try:
                        messages.info(request, "Your subscription has been cancelled. You can reactivate it anytime.")
                    except Exception:
                        pass  # Messages framework may not be available
                    # Redirect to manage page in business context if verified
                    if business.is_verified and business.is_approved:
                        return f'/business/{business.slug}/subscriptions/manage/'
                    else:
                        return '/subscriptions/manage/'
                
                elif subscription.status == 'suspended':
                    # Allow access to subscription management paths
                    if self.is_subscription_management_path(request.path):
                        return None
                    
                    try:
                        messages.warning(request, "Your subscription has been suspended. Please contact support.")
                    except Exception:
                        pass  # Messages framework may not be available
                    # Redirect to manage page in business context if verified
                    if business.is_verified and business.is_approved:
                        return f'/business/{business.slug}/subscriptions/manage/'
                    else:
                        return '/subscriptions/manage/'
                
                elif subscription.status == 'pending':
                    # Allow access to subscription management paths
                    if self.is_subscription_management_path(request.path):
                        return None
                    
                    try:
                        messages.info(request, "Your subscription is pending payment. Please complete payment to activate.")
                    except Exception:
                        pass  # Messages framework may not be available
                    # Redirect to manage/payment page in business context if verified
                    if business.is_verified and business.is_approved:
                        return f'/business/{business.slug}/subscriptions/manage/'
                    else:
                        return '/subscriptions/manage/'
            
            # Check for upcoming expiry (7 days)
            if subscription.is_active and subscription.end_date:
                days_until_expiry = (subscription.end_date - timezone.now()).days
                
                if days_until_expiry <= 7 and days_until_expiry > 0:
                    # Show warning but don't redirect
                    if not hasattr(request, '_expiry_warning_shown'):
                        try:
                            messages.warning(
                                request, 
                                f"Your subscription expires in {days_until_expiry} day{'s' if days_until_expiry != 1 else ''}. "
                                f"<a href='/subscriptions/manage/'>Manage subscription</a>"
                            )
                        except Exception:
                            pass  # Messages framework may not be available
                        request._expiry_warning_shown = True
                
                elif days_until_expiry <= 0:
                    # Subscription has expired
                    subscription.status = 'expired'
                    subscription.save(using='default')
                    
                    # Allow access to subscription management paths even after expiry
                    if self.is_subscription_management_path(request.path):
                        return None
                    
                    try:
                        messages.error(request, "Your subscription has expired. Please renew to continue using the service.")
                    except Exception:
                        pass  # Messages framework may not be available
                    # Redirect to upgrade page in business context if verified
                    if business.is_verified and business.is_approved:
                        return f'/business/{business.slug}/subscriptions/upgrade/'
                    else:
                        return '/subscriptions/upgrade/'
            
            # All checks passed
            return None
            
        except Exception as e:
            logger.error(f"Error in subscription middleware: {str(e)}")
            # Log the exception type and details for debugging
            import traceback
            logger.error(f"Subscription middleware traceback: {traceback.format_exc()}")
            return None
