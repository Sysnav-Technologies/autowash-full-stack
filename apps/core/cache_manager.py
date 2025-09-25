"""
Optimized Multi-Tenant Cache Manager
Fast, responsive caching system that prevents template staleness
"""
from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from django.conf import settings
from apps.core.database_router import get_current_tenant
import logging
import time
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


class MultiTenantCacheManager:
    """
    Optimized cache manager for immediate template updates and system responsiveness
    Uses very short timeouts to prevent staleness while maintaining performance
    """
    
    # Reduced cache timeouts for immediate updates
    DEFAULT_TIMEOUT = 30  # 30 seconds instead of minutes
    SHORT_TIMEOUT = 15    # 15 seconds for frequently changing data
    LONG_TIMEOUT = 60     # 1 minute for more stable data
    
    # Cache key patterns for different data types
    CACHE_PATTERNS = {
        'orders': [
            'orders_list',
            'service_orders_list', 
            'pending_orders',
            'recent_orders',
            'dashboard_orders'
        ],
        'customers': [
            'customers_list',
            'recent_customers',
            'dashboard_customers'
        ],
        'payments': [
            'payments_list',
            'recent_payments',
            'dashboard_payments'
        ],
        'dashboard': [
            'dashboard_data',
            'dashboard_stats',
            'dashboard_metrics',
            'dashboard_charts',
            'dashboard_recent_activity'
        ],
        'templates': [
            'page_cache',
            'template_fragments',
            'view_cache'
        ]
    }
    
    @classmethod
    def get_tenant_id(cls, request=None) -> Optional[str]:
        """Get current tenant ID from request or context"""
        if request and hasattr(request, 'tenant') and request.tenant:
            return str(request.tenant.id)
        
        tenant = get_current_tenant()
        return str(tenant.id) if tenant else None
    
    @classmethod 
    def make_cache_key(cls, key: str, tenant_id: str = None, request=None) -> str:
        """Create tenant-specific cache key with version"""
        if not tenant_id:
            tenant_id = cls.get_tenant_id(request)
        
        if not tenant_id:
            return f"system:{key}"
        
        # Add cache version for cache invalidation
        cache_version = getattr(settings, 'CACHE_VERSION', '1')
        return f"tenant_{tenant_id}:v{cache_version}:{key}"
    
    @classmethod
    def invalidate_pattern_keys(cls, patterns: List[str], tenant_id: str = None, request=None) -> int:
        """Invalidate all cache keys matching patterns"""
        if not tenant_id:
            tenant_id = cls.get_tenant_id(request)
        
        if not tenant_id:
            logger.warning("Cannot invalidate cache - no tenant ID found")
            return 0
        
        invalidated = 0
        
        for pattern in patterns:
            cache_key = cls.make_cache_key(pattern, tenant_id)
            try:
                if cache.delete(cache_key):
                    invalidated += 1
                    logger.debug(f"Invalidated cache key: {cache_key}")
            except Exception as e:
                logger.error(f"Failed to invalidate cache key {cache_key}: {e}")
        
        return invalidated
    
    @classmethod
    def invalidate_order_cache(cls, order_instance=None, tenant_id: str = None, request=None) -> int:
        """Invalidate all order-related cache keys"""
        if not tenant_id:
            tenant_id = cls.get_tenant_id(request)
        
        patterns = cls.CACHE_PATTERNS['orders'][:]
        
        # Add specific order keys if order instance provided
        if order_instance:
            patterns.extend([
                f"order_{order_instance.id}",
                f"service_order_{order_instance.id}",
                f"customer_{order_instance.customer_id}_orders" if hasattr(order_instance, 'customer_id') else None,
                f"orders_{order_instance.status}" if hasattr(order_instance, 'status') else None
            ])
        
        # Filter out None values
        patterns = [p for p in patterns if p is not None]
        
        return cls.invalidate_pattern_keys(patterns, tenant_id, request)
    
    @classmethod
    def invalidate_customer_cache(cls, customer_instance=None, tenant_id: str = None, request=None) -> int:
        """Invalidate all customer-related cache keys"""
        patterns = cls.CACHE_PATTERNS['customers'][:]
        
        if customer_instance:
            patterns.extend([
                f"customer_{customer_instance.id}",
                f"customer_{customer_instance.id}_orders",
                f"customer_{customer_instance.id}_payments"
            ])
        
        return cls.invalidate_pattern_keys(patterns, tenant_id, request)
    
    @classmethod
    def invalidate_payment_cache(cls, payment_instance=None, tenant_id: str = None, request=None) -> int:
        """Invalidate all payment-related cache keys"""
        patterns = cls.CACHE_PATTERNS['payments'][:]
        
        if payment_instance:
            patterns.extend([
                f"payment_{payment_instance.id}",
                f"customer_{payment_instance.customer_id}_payments" if hasattr(payment_instance, 'customer_id') else None
            ])
        
        patterns = [p for p in patterns if p is not None]
        return cls.invalidate_pattern_keys(patterns, tenant_id, request)
    
    @classmethod
    def invalidate_dashboard_cache(cls, tenant_id: str = None, request=None) -> int:
        """Invalidate all dashboard-related cache keys"""
        patterns = cls.CACHE_PATTERNS['dashboard'][:]
        return cls.invalidate_pattern_keys(patterns, tenant_id, request)
    
    @classmethod
    def invalidate_template_cache(cls, tenant_id: str = None, request=None, template_names: List[str] = None) -> int:
        """Invalidate template fragment cache"""
        if not tenant_id:
            tenant_id = cls.get_tenant_id(request)
        
        if not tenant_id:
            return 0
        
        invalidated = 0
        
        # Invalidate generic template cache patterns
        patterns = cls.CACHE_PATTERNS['templates']
        invalidated += cls.invalidate_pattern_keys(patterns, tenant_id, request)
        
        # Invalidate specific template fragments if provided
        if template_names:
            for template_name in template_names:
                try:
                    # Django template fragment keys
                    fragment_key = make_template_fragment_key(template_name, [tenant_id])
                    if cache.delete(fragment_key):
                        invalidated += 1
                        logger.debug(f"Invalidated template fragment: {fragment_key}")
                except Exception as e:
                    logger.error(f"Failed to invalidate template fragment {template_name}: {e}")
        
        return invalidated
    
    @classmethod
    def force_cache_refresh(cls, tenant_id: str = None, request=None) -> Dict[str, int]:
        """Force refresh of all cache types for tenant"""
        if not tenant_id:
            tenant_id = cls.get_tenant_id(request)
        
        if not tenant_id:
            logger.error("Cannot force cache refresh - no tenant ID")
            return {}
        
        results = {}
        
        try:
            # Invalidate all cache patterns
            for cache_type, patterns in cls.CACHE_PATTERNS.items():
                results[cache_type] = cls.invalidate_pattern_keys(patterns, tenant_id, request)
            
            # Also clear Django's site-wide cache for this tenant
            cls._clear_site_cache(tenant_id)
            
            logger.info(f"Forced cache refresh for tenant {tenant_id}: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Failed to force cache refresh: {e}")
            return {}
    
    @classmethod
    def _clear_site_cache(cls, tenant_id: str):
        """Clear Django's full-page cache for tenant"""
        try:
            # Clear middleware cache keys that might be tenant-specific
            prefix = getattr(settings, 'CACHE_MIDDLEWARE_KEY_PREFIX', 'aw')
            
            # Common cache keys used by Django middleware
            middleware_keys = [
                f"{prefix}.cache.page.*",
                f"{prefix}.cache.header.*",
                f"views.decorators.cache.*",
                f"template.cache.*"
            ]
            
            for key_pattern in middleware_keys:
                tenant_key = f"tenant_{tenant_id}:{key_pattern}"
                cache.delete(tenant_key)
                
        except Exception as e:
            logger.error(f"Failed to clear site cache: {e}")
    
    @classmethod
    def get_cache_stats(cls, tenant_id: str = None, request=None) -> Dict[str, Any]:
        """Get cache statistics for tenant"""
        if not tenant_id:
            tenant_id = cls.get_tenant_id(request)
        
        stats = {
            'tenant_id': tenant_id,
            'timestamp': time.time(),
            'cache_backend': getattr(settings, 'CACHES', {}).get('default', {}).get('BACKEND', 'Unknown'),
            'cache_location': getattr(settings, 'CACHES', {}).get('default', {}).get('LOCATION', 'Unknown'),
            'patterns_registered': len(cls.CACHE_PATTERNS),
            'total_keys': sum(len(patterns) for patterns in cls.CACHE_PATTERNS.values())
        }
        
        return stats


# Convenience functions for backward compatibility
def refresh_order_cache(request, order_instance=None):
    """Refresh order-related cache"""
    return MultiTenantCacheManager.invalidate_order_cache(order_instance, request=request)

def refresh_customer_cache(request, customer_instance=None):
    """Refresh customer-related cache"""
    return MultiTenantCacheManager.invalidate_customer_cache(customer_instance, request=request)

def refresh_payment_cache(request, payment_instance=None):
    """Refresh payment-related cache"""
    return MultiTenantCacheManager.invalidate_payment_cache(payment_instance, request=request)

def refresh_dashboard_cache(request):
    """Refresh dashboard-related cache"""
    return MultiTenantCacheManager.invalidate_dashboard_cache(request=request)

def force_cache_refresh(request):
    """Force complete cache refresh"""
    return MultiTenantCacheManager.force_cache_refresh(request=request)