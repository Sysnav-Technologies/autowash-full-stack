# apps/core/context_processors.py - Updated version

from django.conf import settings
from django.utils import timezone
from apps.core.utils import get_business_performance_metrics

def business_context(request):
    """Add business context to templates"""
    context = {
        'business': getattr(request, 'business', None),
        'current_year': timezone.now().year,
        'app_name': 'Autowash',
        'company_name': 'Autowash Technologies',
    }
    
    # Add business-specific context if we're in a tenant schema
    if hasattr(request, 'business') and request.business:
        # Check if business is verified
        is_verified = getattr(request.business, 'is_verified', False)
        
        context.update({
            'business_name': request.business.name,
            'business_logo': request.business.logo.url if request.business.logo else None,
            'business_phone': request.business.phone,
            'business_email': request.business.email,
            'business_timezone': getattr(request.business, 'timezone', 'Africa/Nairobi'),
            'business_verified': is_verified,
            'business_slug': request.business.slug,
        })
        
        # Add verification status if not verified
        if not is_verified:
            try:
                verification = request.business.verification
                context.update({
                    'verification_status': verification.status,
                    'verification_submitted': verification.submitted_at,
                })
            except:
                context.update({
                    'verification_status': 'pending',
                    'verification_submitted': None,
                })
    
    return context

def notifications_context(request):
    """Add notifications context to templates"""
    context = {
        'unread_notifications_count': 0,
        'recent_notifications': [],
    }
    
    # Only for authenticated users in verified businesses
    if (request.user.is_authenticated and 
        hasattr(request, 'business') and request.business and 
        getattr(request.business, 'is_verified', False)):
        try:
            from apps.notification.models import Notification
            notifications = Notification.objects.filter(
                user=request.user,
                is_read=False
            )[:5]
            
            context.update({
                'unread_notifications_count': notifications.count(),
                'recent_notifications': notifications,
            })
        except:
            pass
    
    return context

def performance_context(request):
    """Add performance metrics context for dashboard"""
    context = {}
    
    # Only add metrics for business owners and managers in verified businesses
    if (hasattr(request, 'user') and request.user.is_authenticated and 
        hasattr(request, 'business') and request.business and
        getattr(request.business, 'is_verified', False)):
        
        try:
            from apps.employees.models import Employee
            employee = Employee.objects.get(user=request.user)
            
            if employee.role in ['owner', 'manager']:
                # Get today's metrics
                today_metrics = get_business_performance_metrics(request.business, 'day')
                context.update({
                    'today_revenue': today_metrics['total_revenue'],
                    'today_orders': today_metrics['total_orders'],
                    'today_customers': today_metrics['new_customers'],
                    'employee_role': employee.role,
                })
        except:
            pass
    
    return context

def verification_context(request):
    """Add verification-specific context"""
    context = {
        'requires_verification': False,
        'verification_complete': False,
    }
    
    # Check if user owns a business that needs verification
    if request.user.is_authenticated:
        try:
            business = request.user.owned_businesses.first()
            if business:
                context.update({
                    'user_business': business,
                    'requires_verification': not business.is_verified,
                    'verification_complete': business.is_verified,
                })
                
                # Add verification details if business exists
                try:
                    verification = business.verification
                    context.update({
                        'verification_status': verification.status,
                        'verification_submitted_at': verification.submitted_at,
                        'verification_documents_uploaded': bool(
                            verification.business_license and 
                            verification.tax_certificate and 
                            verification.id_document
                        ),
                    })
                except:
                    context.update({
                        'verification_status': 'pending',
                        'verification_submitted_at': None,
                        'verification_documents_uploaded': False,
                    })
        except:
            pass
    
    return context

def user_role_context(request):
    """Add user role context for permission checks"""
    context = {
        'user_role': None,
        'is_owner': False,
        'is_manager': False,
        'is_employee': False,
        'can_manage_business': False,
    }
    
    # Only for authenticated users in tenant schemas
    if (request.user.is_authenticated and 
        hasattr(request, 'business') and request.business):
        try:
            from apps.employees.models import Employee
            employee = Employee.objects.get(user=request.user, is_active=True)
            
            context.update({
                'user_role': employee.role,
                'is_owner': employee.role == 'owner',
                'is_manager': employee.role == 'manager',
                'is_employee': employee.role == 'employee',
                'can_manage_business': employee.role in ['owner', 'manager'],
                'employee': employee,
            })
        except Employee.DoesNotExist:
            # User is not an employee in this business
            pass
        except:
            pass
    
    return context