"""
Core notification system for the entire application.
Centralizes all email and SMS notifications with proper tenant context.
"""

import logging
from typing import Optional, Dict, Any
from decimal import Decimal
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from apps.core.database_router import get_current_tenant

logger = logging.getLogger(__name__)

def send_notification_email(
    to_email: str,
    subject: str,
    template_name: str,
    context: Dict[str, Any],
    tenant=None
) -> bool:
    """
    Send notification email with tenant context.
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        template_name: Template name (without .html extension)
        context: Template context dictionary
        tenant: Tenant object (auto-detected if not provided)
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Get tenant context
        if not tenant:
            tenant = get_current_tenant()
        
        if tenant:
            context.update({
                'tenant': tenant,
                'business_name': tenant.name,
                'business_phone': tenant.phone,
                'business_email': tenant.email,
            })
        
        # Add common context
        context.update({
            'current_year': timezone.now().year,
            'app_name': getattr(settings, 'APP_NAME', 'Autowash'),
        })
        
        # Render email content
        html_message = render_to_string(f'emails/{template_name}.html', context)
        
        # Try to render text version if exists
        try:
            plain_message = render_to_string(f'emails/{template_name}.txt', context)
        except:
            plain_message = None
        
        logger.info(f"Sending email to {to_email} with subject: {subject}")
        
        send_mail(
            subject=subject,
            message=plain_message or '',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to_email],
            html_message=html_message,
            fail_silently=False
        )
        
        logger.info(f"Email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}", exc_info=True)
        return False

def send_sms_notification(phone_number: str, message: str) -> bool:
    """
    Send SMS notification.
    
    Args:
        phone_number: Recipient phone number
        message: SMS message text
    
    Returns:
        bool: True if SMS sent successfully, False otherwise
    """
    try:
        # TODO: Integrate with SMS provider (e.g., Africa's Talking, Twilio)
        logger.info(f"SMS notification would be sent to {phone_number}: {message}")
        # Placeholder for actual SMS implementation
        return True
        
    except Exception as e:
        logger.error(f"Failed to send SMS to {phone_number}: {str(e)}")
        return False

# Service Order Notifications
def send_order_created_notification(order, tenant=None):
    """Send notification when service order is created"""
    if not order.customer.email:
        logger.info(f"No email for customer {order.customer.full_name}, skipping order created email")
        return False
    
    context = {
        'order': order,
        'customer': order.customer,
        'vehicle': order.vehicle,
        'services': order.order_items.all(),
        'notification_type': 'created'
    }
    
    subject = f"Order Confirmation - {order.order_number}"
    
    success = send_notification_email(
        to_email=order.customer.email,
        subject=subject,
        template_name='service_notification',
        context=context,
        tenant=tenant
    )
    
    # Also send SMS if customer has phone and preferences allow
    if order.customer.phone and getattr(order.customer, 'receive_service_reminders', True):
        tenant_name = tenant.name if tenant else "Autowash"
        sms_message = f"Hi {order.customer.first_name}, your service order {order.order_number} has been created at {tenant_name}. Total: KES {order.total_amount}. Thank you!"
        send_sms_notification(str(order.customer.phone), sms_message)
    
    return success

def send_order_started_notification(order, attendant_name=None, tenant=None):
    """Send notification when service order is started"""
    if not order.customer.email:
        logger.info(f"No email for customer {order.customer.full_name}, skipping order started email")
        return False
    
    context = {
        'order': order,
        'customer': order.customer,
        'vehicle': order.vehicle,
        'services': order.order_items.all(),
        'attendant_name': attendant_name,
        'notification_type': 'started'
    }
    
    subject = f"Service Started - {order.order_number}"
    
    success = send_notification_email(
        to_email=order.customer.email,
        subject=subject,
        template_name='service_notification',
        context=context,
        tenant=tenant
    )
    
    # Also send SMS
    if order.customer.phone and getattr(order.customer, 'receive_service_reminders', True):
        tenant_name = tenant.name if tenant else "Autowash"
        sms_message = f"Hi {order.customer.first_name}, your service {order.order_number} has started at {tenant_name}. Our team is working on your {order.vehicle.make} {order.vehicle.model}."
        send_sms_notification(str(order.customer.phone), sms_message)
    
    return success

def send_order_completed_notification(order, attendant_name=None, tenant=None):
    """Send notification when service order is completed"""
    if not order.customer.email:
        logger.info(f"No email for customer {order.customer.full_name}, skipping order completed email")
        return False
    
    context = {
        'order': order,
        'customer': order.customer,
        'vehicle': order.vehicle,
        'services': order.order_items.all(),
        'attendant_name': attendant_name,
        'notification_type': 'completed'
    }
    
    subject = f"Service Completed - {order.order_number}"
    
    success = send_notification_email(
        to_email=order.customer.email,
        subject=subject,
        template_name='service_notification',
        context=context,
        tenant=tenant
    )
    
    # Also send SMS
    if order.customer.phone and getattr(order.customer, 'receive_service_reminders', True):
        tenant_name = tenant.name if tenant else "Autowash"
        sms_message = f"Hi {order.customer.first_name}, your service {order.order_number} is complete at {tenant_name}! Please collect your {order.vehicle.make} {order.vehicle.model}. Total: KES {order.total_amount}"
        send_sms_notification(str(order.customer.phone), sms_message)
    
    return success

# Payment Notifications
def send_payment_confirmation_notification(payment, tenant=None):
    """Send notification when payment is confirmed"""
    order = payment.service_order
    if not order or not order.customer.email:
        logger.info(f"No email for payment confirmation, skipping")
        return False
    
    context = {
        'payment': payment,
        'order': order,
        'customer': order.customer,
        'vehicle': order.vehicle,
        'remaining_balance': order.remaining_balance,
        'is_fully_paid': order.is_fully_paid
    }
    
    subject = f"Payment Confirmation - {payment.payment_id}"
    
    success = send_notification_email(
        to_email=order.customer.email,
        subject=subject,
        template_name='service_payment_confirmation',
        context=context,
        tenant=tenant
    )
    
    # Also send SMS
    if order.customer.phone:
        tenant_name = tenant.name if tenant else "Autowash"
        if order.is_fully_paid:
            sms_message = f"Hi {order.customer.first_name}, payment of KES {payment.amount} received for order {order.order_number} at {tenant_name}. Payment complete. Thank you!"
        else:
            sms_message = f"Hi {order.customer.first_name}, payment of KES {payment.amount} received for order {order.order_number} at {tenant_name}. Balance: KES {order.remaining_balance}"
        send_sms_notification(str(order.customer.phone), sms_message)
    
    return success

# Subscription Notifications  
def send_subscription_expiry_warning(subscription, days_remaining, tenant=None):
    """Send warning when subscription is about to expire"""
    if not subscription.business.email:
        logger.info(f"No email for business {subscription.business.name}, skipping expiry warning")
        return False
    
    context = {
        'subscription': subscription,
        'business': subscription.business,
        'days_remaining': days_remaining,
        'plan': subscription.plan
    }
    
    subject = f"Subscription Expiring Soon - {days_remaining} Days Remaining"
    
    return send_notification_email(
        to_email=subscription.business.email,
        subject=subject,
        template_name='subscription_expiry_warning',
        context=context,
        tenant=tenant
    )

def send_subscription_expired_notification(subscription, tenant=None):
    """Send notification when subscription has expired"""
    if not subscription.business.email:
        logger.info(f"No email for business {subscription.business.name}, skipping expired notification")
        return False
    
    context = {
        'subscription': subscription,
        'business': subscription.business,
        'plan': subscription.plan
    }
    
    subject = f"Subscription Expired - Action Required"
    
    return send_notification_email(
        to_email=subscription.business.email,
        subject=subject,
        template_name='subscription_expired',
        context=context,
        tenant=tenant
    )

def send_subscription_renewal_confirmation(subscription, tenant=None):
    """Send confirmation when subscription is renewed"""
    if not subscription.business.email:
        logger.info(f"No email for business {subscription.business.name}, skipping renewal confirmation")
        return False
    
    context = {
        'subscription': subscription,
        'business': subscription.business,
        'plan': subscription.plan
    }
    
    subject = f"Subscription Renewed Successfully"
    
    return send_notification_email(
        to_email=subscription.business.email,
        subject=subject,
        template_name='subscription_renewed',
        context=context,
        tenant=tenant
    )

# Purchase Order Notifications
def send_purchase_order_notification(purchase_order, notification_type, tenant=None):
    """Send purchase order notifications to suppliers"""
    if not purchase_order.supplier.email:
        logger.info(f"No email for supplier {purchase_order.supplier.name}, skipping PO notification")
        return False
    
    context = {
        'purchase_order': purchase_order,
        'supplier': purchase_order.supplier,
        'notification_type': notification_type,
        'business': tenant or get_current_tenant()
    }
    
    subject_map = {
        'created': f"New Purchase Order - {purchase_order.po_number}",
        'approved': f"Purchase Order Approved - {purchase_order.po_number}",
        'sent': f"Purchase Order - {purchase_order.po_number}",
        'cancelled': f"Purchase Order Cancelled - {purchase_order.po_number}"
    }
    
    subject = subject_map.get(notification_type, f"Purchase Order Update - {purchase_order.po_number}")
    
    return send_notification_email(
        to_email=purchase_order.supplier.email,
        subject=subject,
        template_name='purchase_order_notification',
        context=context,
        tenant=tenant
    )

# Employee Notifications
def send_employee_task_assignment(employee, task_description, tenant=None):
    """Send notification when employee is assigned a task"""
    if not employee.email:
        logger.info(f"No email for employee {employee.full_name}, skipping task assignment")
        return False
    
    context = {
        'employee': employee,
        'task_description': task_description,
        'business': tenant or get_current_tenant()
    }
    
    subject = f"New Task Assignment"
    
    return send_notification_email(
        to_email=employee.email,
        subject=subject,
        template_name='task_assignment',
        context=context,
        tenant=tenant
    )

# Low Stock Notifications
def send_low_stock_alert(inventory_item, current_stock, minimum_stock, tenant=None):
    """Send alert when inventory is running low"""
    # Send to business owner/managers
    business = tenant or get_current_tenant()
    if not business or not business.email:
        logger.info("No business email for low stock alert")
        return False
    
    context = {
        'inventory_item': inventory_item,
        'current_stock': current_stock,
        'minimum_stock': minimum_stock,
        'business': business
    }
    
    subject = f"Low Stock Alert - {inventory_item.name}"
    
    return send_notification_email(
        to_email=business.email,
        subject=subject,
        template_name='low_stock_alert',
        context=context,
        tenant=tenant
    )
