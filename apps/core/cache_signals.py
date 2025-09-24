"""
Cache Invalidation Signals for Multi-Tenant System
Automatically invalidates cache when tenant data is modified
"""
from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.core.cache import cache
from apps.core.database_router import get_current_tenant
from apps.core.cache_backends import TenantAwareCacheHandler
import logging

logger = logging.getLogger(__name__)


def get_tenant_id_from_instance(instance):
    """Extract tenant ID from model instance"""
    # Try different ways to get tenant ID
    if hasattr(instance, 'tenant_id') and instance.tenant_id:
        return str(instance.tenant_id)
    elif hasattr(instance, 'tenant') and instance.tenant:
        return str(instance.tenant.id)
    elif hasattr(instance, 'customer') and hasattr(instance.customer, 'tenant_id'):
        return str(instance.customer.tenant_id)
    else:
        # Fallback to current tenant
        tenant = get_current_tenant()
        return str(tenant.id) if tenant else None


def invalidate_tenant_cache_keys(tenant_id, cache_keys):
    """Invalidate specific cache keys for a tenant"""
    if not tenant_id:
        return
    
    try:
        for key in cache_keys:
            tenant_key = f"tenant_{tenant_id}:{key}"
            cache.delete(tenant_key)
            logger.debug(f"Invalidated cache key: {tenant_key}")
    except Exception as e:
        logger.error(f"Failed to invalidate cache keys: {e}")


# Service Order Signals
@receiver(post_save, sender='services.ServiceOrder')
def invalidate_service_order_cache(sender, instance, created, **kwargs):
    """Invalidate cache when service orders are created or updated"""
    tenant_id = get_tenant_id_from_instance(instance)
    if not tenant_id:
        return
    
    # Cache keys to invalidate
    cache_keys = [
        'orders_list',
        'pending_orders', 
        'recent_orders',
        'orders_count',
        'dashboard_orders',
        'order_stats',
        'daily_orders',
        'weekly_orders',
        'monthly_orders',
        f'order_{instance.id}',
        f'customer_{instance.customer_id}_orders',
    ]
    
    # Add status-specific keys
    if instance.status:
        cache_keys.extend([
            f'orders_{instance.status}',
            f'orders_status_{instance.status}',
        ])
    
    # Add date-specific keys
    if instance.scheduled_date:
        cache_keys.extend([
            f'orders_date_{instance.scheduled_date}',
            f'scheduled_orders_{instance.scheduled_date}',
        ])
    
    invalidate_tenant_cache_keys(tenant_id, cache_keys)
    
    # Also invalidate middleware page cache
    try:
        cache.delete(f"tenant_{tenant_id}:views.decorators.cache")
        cache.delete(f"tenant_{tenant_id}:middleware.cache")
    except Exception as e:
        logger.error(f"Failed to invalidate middleware cache: {e}")


@receiver(post_delete, sender='services.ServiceOrder')
def invalidate_service_order_cache_on_delete(sender, instance, **kwargs):
    """Invalidate cache when service orders are deleted"""
    tenant_id = get_tenant_id_from_instance(instance)
    if not tenant_id:
        return
    
    cache_keys = [
        'orders_list',
        'orders_count',
        'dashboard_orders',
        'order_stats',
        f'order_{instance.id}',
    ]
    
    invalidate_tenant_cache_keys(tenant_id, cache_keys)


# Service Order Item Signals
@receiver(post_save, sender='services.ServiceOrderItem')
def invalidate_order_item_cache(sender, instance, created, **kwargs):
    """Invalidate cache when order items are modified"""
    if hasattr(instance, 'service_order'):
        tenant_id = get_tenant_id_from_instance(instance.service_order)
        if tenant_id:
            cache_keys = [
                f'order_{instance.service_order.id}',
                f'order_{instance.service_order.id}_items',
                'orders_list',
                'dashboard_orders',
            ]
            invalidate_tenant_cache_keys(tenant_id, cache_keys)


# Purchase Order Signals (if they exist)
@receiver(post_save, sender='suppliers.PurchaseOrder')
def invalidate_purchase_order_cache(sender, instance, created, **kwargs):
    """Invalidate cache when purchase orders are created or updated"""
    tenant_id = get_tenant_id_from_instance(instance)
    if not tenant_id:
        return
    
    cache_keys = [
        'purchase_orders',
        'supplier_orders',
        'inventory_orders',
        f'purchase_order_{instance.id}',
        'dashboard_purchase_orders',
    ]
    
    invalidate_tenant_cache_keys(tenant_id, cache_keys)


# Customer Signals
@receiver(post_save, sender='customers.Customer')
def invalidate_customer_cache(sender, instance, created, **kwargs):
    """Invalidate cache when customers are created or updated"""
    tenant_id = get_tenant_id_from_instance(instance)
    if not tenant_id:
        return
    
    cache_keys = [
        'customers_list',
        'recent_customers',
        'customer_count',
        'active_customers',
        f'customer_{instance.id}',
        'dashboard_customers',
    ]
    
    invalidate_tenant_cache_keys(tenant_id, cache_keys)


# Service Signals
@receiver(post_save, sender='services.Service')
def invalidate_service_cache(sender, instance, created, **kwargs):
    """Invalidate cache when services are created or updated"""
    tenant_id = get_tenant_id_from_instance(instance)
    if not tenant_id:
        return
    
    cache_keys = [
        'services_list',
        'active_services', 
        'popular_services',
        f'service_{instance.id}',
        'service_categories',
        'dashboard_services',
    ]
    
    invalidate_tenant_cache_keys(tenant_id, cache_keys)


# Employee Signals
@receiver(post_save, sender='employees.Employee')
def invalidate_employee_cache(sender, instance, created, **kwargs):
    """Invalidate cache when employees are created or updated"""
    tenant_id = get_tenant_id_from_instance(instance)
    if not tenant_id:
        return
    
    cache_keys = [
        'employees_list',
        'active_employees',
        f'employee_{instance.id}',
        'dashboard_employees',
    ]
    
    invalidate_tenant_cache_keys(tenant_id, cache_keys)


# Payment Signals
@receiver(post_save, sender='payments.Payment')
def invalidate_payment_cache(sender, instance, created, **kwargs):
    """Invalidate cache when payments are created or updated"""
    tenant_id = get_tenant_id_from_instance(instance)
    if not tenant_id:
        return
    
    cache_keys = [
        'payments_list',
        'recent_payments',
        'payment_stats',
        f'payment_{instance.id}',
        'dashboard_payments',
        'revenue_stats',
    ]
    
    invalidate_tenant_cache_keys(tenant_id, cache_keys)


# Generic signal for any tenant model changes
@receiver(post_save)
def invalidate_generic_tenant_cache(sender, instance, created, **kwargs):
    """Generic cache invalidation for tenant models"""
    # Only apply to tenant-specific models
    if not hasattr(instance, '_meta') or not hasattr(instance._meta, 'app_label'):
        return
    
    # Skip models that have specific handlers
    skip_models = {
        'services.ServiceOrder',
        'services.ServiceOrderItem', 
        'services.Service',
        'suppliers.PurchaseOrder',
        'customers.Customer',
        'employees.Employee',
        'payments.Payment',
    }
    
    model_name = f"{instance._meta.app_label}.{instance._meta.model_name}"
    if model_name in skip_models:
        return
    
    # Get tenant ID
    tenant_id = get_tenant_id_from_instance(instance)
    if not tenant_id:
        return
    
    # Invalidate general cache keys
    cache_keys = [
        'dashboard_data',
        'navigation_cache',
        'sidebar_cache',
    ]
    
    invalidate_tenant_cache_keys(tenant_id, cache_keys)


# Utility function to manually clear tenant cache
def clear_all_tenant_cache(tenant_id):
    """Manually clear all cache for a specific tenant"""
    try:
        TenantAwareCacheHandler.clear_tenant_cache(tenant_id)
        logger.info(f"Cleared all cache for tenant: {tenant_id}")
    except Exception as e:
        logger.error(f"Failed to clear cache for tenant {tenant_id}: {e}")


# Utility function to warm up cache
def warm_tenant_cache(tenant_id):
    """Pre-populate cache with frequently accessed data"""
    try:
        # This could be expanded to pre-load common queries
        cache_keys_to_warm = [
            'services_list',
            'active_services',
            'recent_orders',
            'dashboard_data',
        ]
        
        logger.info(f"Cache warming initiated for tenant: {tenant_id}")
        # Implementation would depend on specific data loading needs
        
    except Exception as e:
        logger.error(f"Failed to warm cache for tenant {tenant_id}: {e}")