from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import datetime
from django.db import models

from .models import PurchaseOrder, PurchaseOrderItem, GoodsReceipt, SupplierEvaluation

@receiver(post_save, sender=PurchaseOrderItem)
def update_purchase_order_totals(sender, instance, created, **kwargs):
    """Update purchase order totals when items are added/modified"""
    if instance.purchase_order:
        instance.purchase_order.calculate_totals()

@receiver(post_delete, sender=PurchaseOrderItem)
def update_purchase_order_totals_on_delete(sender, instance, **kwargs):
    """Update purchase order totals when items are deleted"""
    if instance.purchase_order:
        instance.purchase_order.calculate_totals()

@receiver(post_save, sender=PurchaseOrder)
def update_supplier_metrics(sender, instance, created, **kwargs):
    """Update supplier performance metrics when purchase order status changes"""
    if not created and instance.status == 'completed':
        # Update supplier metrics when order is completed
        instance.supplier.update_performance_metrics()

@receiver(post_save, sender=SupplierEvaluation)
def update_supplier_ratings(sender, instance, created, **kwargs):
    """Update supplier ratings when evaluation is saved"""
    supplier = instance.supplier
    
    # Update individual ratings
    evaluations = supplier.evaluations.all()
    if evaluations.exists():
        supplier.quality_rating = evaluations.aggregate(
            avg=models.Avg('quality_rating')
        )['avg'] or 0
        supplier.delivery_rating = evaluations.aggregate(
            avg=models.Avg('delivery_rating')
        )['avg'] or 0
        supplier.service_rating = evaluations.aggregate(
            avg=models.Avg('service_rating')
        )['avg'] or 0
        supplier.rating = supplier.average_rating
        supplier.save()

@receiver(post_save, sender=GoodsReceipt)
def track_delivery_performance(sender, instance, created, **kwargs):
    """Track delivery performance when goods are received"""
    if instance.status == 'completed' and instance.purchase_order:
        po = instance.purchase_order
        supplier = instance.supplier
        
        # Check if delivery was on time
        if po.delivery_date and po.expected_delivery_date:
            is_on_time = po.delivery_date <= po.expected_delivery_date
            
            # You could create a delivery performance record here
            # or update supplier metrics directly
            
        # Update supplier's last order date
        supplier.last_order_date = instance.receipt_date
        supplier.save()

# Signal to generate automatic supplier codes
@receiver(pre_save, sender='suppliers.Supplier')
def generate_supplier_code(sender, instance, **kwargs):
    """Generate supplier code if not provided"""
    if not instance.supplier_code:
        import string
        import random
        
        # Generate a random 6-character code
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        # Ensure uniqueness
        while sender.objects.filter(supplier_code=code).exists():
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        instance.supplier_code = code

