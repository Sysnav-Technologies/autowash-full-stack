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
        context.update({
            'business_name': request.business.name,
            'business_logo': request.business.logo.url if request.business.logo else None,
            'business_phone': request.business.phone,
            'business_email': request.business.email,
            'business_timezone': getattr(request.business, 'timezone', 'Africa/Nairobi'),
        })
    
    return context

def notifications_context(request):
    """Add notifications context to templates"""
    context = {
        'unread_notifications_count': 0,
        'recent_notifications': [],
    }
    
    # Only for authenticated users
    if request.user.is_authenticated:
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
    
    # Only add metrics for business owners and managers
    if (hasattr(request, 'user') and request.user.is_authenticated and 
        hasattr(request, 'business') and request.business):
        
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
                })
        except:
            pass
    
    return context