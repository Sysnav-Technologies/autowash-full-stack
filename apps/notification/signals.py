from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Notification, NotificationPreference
from .utils import trigger_notification_event

@receiver(post_save, sender=User)
def create_notification_preferences(sender, instance, created, **kwargs):
    """Create notification preferences for new users"""
    if created:
        NotificationPreference.objects.get_or_create(user=instance)

@receiver(post_save, sender=Notification)
def log_notification_creation(sender, instance, created, **kwargs):
    """Log notification creation for analytics"""
    if created:
        # You could add logging or analytics tracking here
        pass

# Business event signals
def trigger_order_completed_notification(sender, instance, **kwargs):
    """Trigger notification when order is completed"""
    if instance.status == 'completed' and hasattr(instance, '_state') and instance._state.db:
        try:
            # Check if status changed to completed
            old_instance = sender.objects.get(pk=instance.pk)
            if old_instance.status != 'completed':
                trigger_notification_event('order_completed', {
                    'order_number': getattr(instance, 'order_number', instance.id),
                    'customer_name': getattr(instance.customer, 'full_name', 'Customer'),
                    'total_amount': getattr(instance, 'total_amount', 0),
                })
        except sender.DoesNotExist:
            # New instance
            trigger_notification_event('order_completed', {
                'order_number': getattr(instance, 'order_number', instance.id),
                'customer_name': getattr(instance.customer, 'full_name', 'Customer'),
                'total_amount': getattr(instance, 'total_amount', 0),
            })

def trigger_payment_received_notification(sender, instance, **kwargs):
    """Trigger notification when payment is received"""
    if instance.status == 'completed':
        if hasattr(instance, '_state') and instance._state.db:
            try:
                old_instance = sender.objects.get(pk=instance.pk)
                if old_instance.status != 'completed':
                    trigger_notification_event('payment_received', {
                        'amount': instance.amount,
                        'payment_method': getattr(instance, 'method', 'Payment'),
                        'customer_name': getattr(instance.customer, 'full_name', 'Customer') if hasattr(instance, 'customer') else 'Customer',
                    })
            except sender.DoesNotExist:
                trigger_notification_event('payment_received', {
                    'amount': instance.amount,
                    'payment_method': getattr(instance, 'method', 'Payment'),
                    'customer_name': getattr(instance.customer, 'full_name', 'Customer') if hasattr(instance, 'customer') else 'Customer',
                })

def trigger_low_inventory_notification(sender, instance, **kwargs):
    """Trigger notification for low inventory"""
    if hasattr(instance, 'current_stock') and hasattr(instance, 'minimum_stock_level'):
        if instance.current_stock <= instance.minimum_stock_level:
            trigger_notification_event('inventory_low', {
                'item_name': instance.name,
                'current_stock': instance.current_stock,
                'minimum_level': instance.minimum_stock_level,
            })

def trigger_employee_absent_notification(sender, instance, **kwargs):
    """Trigger notification when employee is absent"""
    if hasattr(instance, 'status') and instance.status == 'absent':
        trigger_notification_event('employee_absent', {
            'employee_name': getattr(instance.employee, 'full_name', 'Employee'),
            'date': instance.date,
            'reason': getattr(instance, 'reason', 'Not specified'),
        })

# Connect signals when models are available
def connect_business_signals():
    """Connect signals to business models when they're available"""
    try:
        # Service/Order signals
        from apps.services.models import ServiceOrder
        post_save.connect(trigger_order_completed_notification, sender=ServiceOrder)
    except ImportError:
        pass
    
    try:
        # Payment signals  
        from apps.payments.models import Payment
        post_save.connect(trigger_payment_received_notification, sender=Payment)
    except ImportError:
        pass
    
    try:
        # Inventory signals
        from apps.inventory.models import InventoryItem
        post_save.connect(trigger_low_inventory_notification, sender=InventoryItem)
    except ImportError:
        pass
    
    try:
        # Employee attendance signals
        from apps.employees.models import Attendance
        post_save.connect(trigger_employee_absent_notification, sender=Attendance)
    except ImportError:
        pass

# Call this in apps.py ready() method
connect_business_signals()

# Signal for customer birthday reminders
@receiver(post_save, sender=User)
def schedule_birthday_reminder(sender, instance, created, **kwargs):
    """Schedule birthday reminder for customers"""
    if created and hasattr(instance, 'customer_profile'):
        customer = instance.customer_profile
        if customer.date_of_birth:
            # Calculate next birthday
            from datetime import date, timedelta
            today = date.today()
            next_birthday = customer.date_of_birth.replace(year=today.year)
            
            if next_birthday < today:
                next_birthday = next_birthday.replace(year=today.year + 1)
            
            # Schedule reminder 7 days before birthday
            reminder_date = next_birthday - timedelta(days=7)
            
            if reminder_date > today:
                trigger_notification_event('birthday_reminder', {
                    'customer_name': customer.full_name,
                    'birthday_date': next_birthday,
                }, scheduled_for=timezone.make_aware(
                    timezone.datetime.combine(reminder_date, timezone.datetime.min.time())
                ))

# Automatic cleanup signals
@receiver(post_save, sender=Notification)
def auto_expire_notifications(sender, instance, created, **kwargs):
    """Auto-expire old notifications"""
    if created and not instance.expires_at:
        # Set default expiry (30 days from creation)
        from datetime import timedelta
        instance.expires_at = instance.created_at + timedelta(days=30)
        instance.save(update_fields=['expires_at'])