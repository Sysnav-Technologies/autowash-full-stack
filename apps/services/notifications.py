"""
Service notification helper functions with HTML email support
"""
import logging
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from apps.core.database_router import get_current_tenant

logger = logging.getLogger(__name__)

def send_service_notification_email(order, notification_type, attendant_name=None):
    """
    Send HTML service notification email to customer with tenant information
    
    Args:
        order: ServiceOrder instance
        notification_type: 'started', 'completed', 'reminder', 'created'
        attendant_name: Name of attendant (optional)
    """
    if not order.customer.email:
        logger.info(f"No email address for customer {order.customer.full_name}")
        return False
    
    try:
        # Get current tenant for business information
        tenant = get_current_tenant()
        logger.info(f"Retrieved tenant: {tenant}")
        if tenant:
            logger.info(f"Tenant name: {tenant.name}")
        
        if not tenant:
            logger.error("No tenant context available for email notification")
            return False
        
        # Prepare context for email template
        context = {
            'order': order,
            'customer': order.customer,
            'customer_name': order.customer.first_name or 'Valued Customer',
            'vehicle': order.vehicle,
            'tenant': tenant,
            'notification_type': notification_type,
            'attendant_name': attendant_name or (order.assigned_attendant.full_name if order.assigned_attendant else 'Our Team'),
            'order_items': order.order_items.all().select_related('service'),
            'business_name': tenant.name if tenant else 'Autowash Service',
            'business_phone': getattr(tenant, 'phone', ''),
            'business_email': getattr(tenant, 'email', ''),
            'business_address': getattr(tenant, 'address', ''),
            'estimated_duration': order.estimated_duration,
            'total_amount': order.total_amount,
        }
        
        logger.info(f"Business name in context: {context['business_name']}")
        
        # Determine subject and template based on notification type
        if notification_type == 'started':
            subject = f'Service Started - Order {order.order_number}'
            html_template = 'emails/service_notification.html'
            text_template = 'emails/service_notification.txt'
        elif notification_type == 'completed':
            subject = f'Service Completed - Order {order.order_number}'
            html_template = 'emails/service_notification.html'
            text_template = 'emails/service_notification.txt'
        elif notification_type == 'reminder':
            subject = f'Service Reminder - Order {order.order_number}'
            html_template = 'emails/service_reminder.html'
            text_template = 'emails/service_reminder.txt'
        elif notification_type == 'created':
            subject = f'Order Confirmed - {order.order_number}'
            html_template = 'emails/service_notification.html'
            text_template = 'emails/service_notification.txt'
        else:
            subject = f'Service Update - Order {order.order_number}'
            html_template = 'emails/service_notification.html'
            text_template = 'emails/service_notification.txt'
        
        # Render email content
        html_content = render_to_string(html_template, context)
        text_content = render_to_string(text_template, context)
        
        # Create email message
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[order.customer.email],
        )
        email.attach_alternative(html_content, "text/html")
        
        # Send email
        email.send()
        logger.info(f"Service notification email sent to {order.customer.email} for order {order.order_number}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send service notification email for order {order.order_number}: {str(e)}")
        return False

def send_sms_notification(phone_number, message):
    """
    Send SMS notification (placeholder function)
    This function should be implemented with your SMS provider
    """
    try:
        # TODO: Implement actual SMS sending logic
        logger.info(f"SMS notification sent to {phone_number}: {message}")
        return True
    except Exception as e:
        logger.error(f"Failed to send SMS to {phone_number}: {str(e)}")
        return False
