"""
Signal handlers for automatic notifications throughout the application.
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from apps.services.models import ServiceOrder
from apps.payments.models import Payment
from apps.suppliers.models import PurchaseOrder
from apps.subscriptions.models import Subscription
from apps.inventory.models import InventoryItem
from apps.core.notifications import (
    send_purchase_order_notification,
    send_subscription_renewal_confirmation,
    send_low_stock_alert
)
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=PurchaseOrder)
def handle_purchase_order_status_change(sender, instance, created, **kwargs):
    """Send notifications when purchase order status changes"""
    if created:
        # Send creation notification to supplier
        send_purchase_order_notification(
            purchase_order=instance,
            notification_type='created'
        )
        logger.info(f"Purchase order created notification sent for {instance.po_number}")
    
    elif hasattr(instance, '_status_changed'):
        # Check if status changed (this flag should be set by views when status changes)
        old_status = getattr(instance, '_old_status', None)
        new_status = instance.status
        
        if old_status != new_status:
            notification_type_map = {
                'approved': 'approved',
                'sent': 'sent',
                'cancelled': 'cancelled'
            }
            
            notification_type = notification_type_map.get(new_status)
            if notification_type:
                send_purchase_order_notification(
                    purchase_order=instance,
                    notification_type=notification_type
                )
                logger.info(f"Purchase order {notification_type} notification sent for {instance.po_number}")

@receiver(post_save, sender=Subscription)
def handle_subscription_renewal(sender, instance, created, **kwargs):
    """Send notification when subscription is renewed"""
    if not created and hasattr(instance, '_was_renewed'):
        # This flag should be set when subscription is renewed
        send_subscription_renewal_confirmation(subscription=instance)
        logger.info(f"Subscription renewal notification sent for {instance.business.name}")

@receiver(pre_save, sender=InventoryItem)
def check_low_stock_alert(sender, instance, **kwargs):
    """Check if stock is running low and send alert"""
    if instance.pk:  # Only for existing items
        try:
            old_instance = InventoryItem.objects.get(pk=instance.pk)
            
            # Check if stock changed and is now below minimum
            if (old_instance.current_stock != instance.current_stock and 
                instance.current_stock <= instance.minimum_stock and
                old_instance.current_stock > instance.minimum_stock):
                
                # Send low stock alert
                send_low_stock_alert(
                    inventory_item=instance,
                    current_stock=instance.current_stock,
                    minimum_stock=instance.minimum_stock
                )
                logger.info(f"Low stock alert sent for {instance.name}")
                
        except InventoryItem.DoesNotExist:
            pass
