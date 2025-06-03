from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from datetime import datetime

from .models import GeneratedReport, AnalyticsEvent
from .utils import track_analytics_event, calculate_business_metrics

@receiver(post_save, sender=GeneratedReport)
def track_report_generation(sender, instance, created, **kwargs):
    """Track when reports are generated"""
    if created:
        track_analytics_event(
            event_type='report_generated',
            event_data={
                'template_name': instance.template.name,
                'template_type': instance.template.report_type,
                'date_range': f"{instance.date_from} to {instance.date_to}"
            },
            employee=instance.generated_by
        )

@receiver(post_save, sender=AnalyticsEvent)
def update_business_metrics_on_event(sender, instance, created, **kwargs):
    """Update business metrics when significant events occur"""
    if created and instance.event_type in ['service_completed', 'payment_received', 'customer_registered']:
        # Calculate metrics for today
        today = timezone.now().date()
        try:
            calculate_business_metrics(today)
        except Exception as e:
            # Log error but don't break the flow
            print(f"Error updating business metrics: {e}")

# Signal to track various business events
def track_customer_registration(sender, instance, created, **kwargs):
    """Track customer registration events"""
    if created:
        track_analytics_event(
            event_type='customer_registered',
            event_data={
                'customer_id': instance.id,
                'customer_name': instance.full_name,
                'is_vip': instance.is_vip
            },
            customer=instance
        )

def track_service_completion(sender, instance, **kwargs):
    """Track service completion events"""
    if instance.status == 'completed' and hasattr(instance, '_state') and instance._state.db:
        # Check if status changed to completed
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            if old_instance.status != 'completed':
                track_analytics_event(
                    event_type='service_completed',
                    event_data={
                        'service_id': instance.id,
                        'service_type': instance.service.name if hasattr(instance, 'service') else 'Unknown',
                        'customer_name': instance.customer.full_name if hasattr(instance, 'customer') else 'Unknown',
                        'amount': float(instance.total_amount) if hasattr(instance, 'total_amount') else 0
                    },
                    customer=getattr(instance, 'customer', None)
                )
        except sender.DoesNotExist:
            pass

def track_payment_received(sender, instance, created, **kwargs):
    """Track payment events"""
    if instance.status == 'completed':
        if created or (hasattr(instance, '_state') and instance._state.db):
            try:
                if not created:
                    old_instance = sender.objects.get(pk=instance.pk)
                    if old_instance.status == 'completed':
                        return  # Already tracked
                
                track_analytics_event(
                    event_type='payment_received',
                    event_data={
                        'payment_id': instance.id,
                        'amount': float(instance.amount),
                        'method': instance.method,
                        'customer_name': instance.customer.full_name if hasattr(instance, 'customer') and instance.customer else 'Unknown'
                    },
                    customer=getattr(instance, 'customer', None)
                )
            except sender.DoesNotExist:
                pass

# Connect signals when models are available
def connect_business_signals():
    """Connect signals to business models when they're available"""
    try:
        from apps.customers.models import Customer
        post_save.connect(track_customer_registration, sender=Customer)
    except ImportError:
        pass
    
    try:
        from apps.services.models import ServiceOrder
        post_save.connect(track_service_completion, sender=ServiceOrder)
    except ImportError:
        pass
    
    try:
        from apps.payments.models import Payment
        post_save.connect(track_payment_received, sender=Payment)
    except ImportError:
        pass

# Call this in apps.py ready() method
connect_business_signals()