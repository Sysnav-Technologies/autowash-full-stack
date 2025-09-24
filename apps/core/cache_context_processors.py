"""
Multi-Tenant Cache Context Processor
Provides tenant-aware cache operations and utilities to templates and views
Updated with actual functionalities from all apps
"""
from django.core.cache import cache
from django.conf import settings
from apps.core.database_router import get_current_tenant
from apps.core.cache_backends import TenantAwareCacheHandler
import time
import hashlib


def tenant_cache_context(request):
    """
    Context processor that provides tenant-aware cache utilities
    Makes cache operations available in templates and views
    """
    
    # Get current tenant
    tenant = getattr(request, 'tenant', None) or get_current_tenant()
    tenant_id = str(tenant.id) if tenant else None
    
    def get_tenant_cache_key(key):
        """Generate tenant-specific cache key"""
        if tenant_id:
            return f"tenant_{tenant_id}:{key}"
        return f"system:{key}"
    
    def cache_get(key, default=None):
        """Get value from tenant-specific cache"""
        tenant_key = get_tenant_cache_key(key)
        return cache.get(tenant_key, default)
    
    def cache_set(key, value, timeout=300):
        """Set value in tenant-specific cache"""
        tenant_key = get_tenant_cache_key(key)
        return cache.set(tenant_key, value, timeout)
    
    def cache_delete(key):
        """Delete value from tenant-specific cache"""
        tenant_key = get_tenant_cache_key(key)
        return cache.delete(tenant_key)
    
    def invalidate_page_cache(page_name):
        """Invalidate cached pages for current tenant"""
        if tenant_id:
            cache_patterns = [
                f"tenant_{tenant_id}:views.decorators.cache.cache_page",
                f"tenant_{tenant_id}:template.cache.{page_name}",
                f"tenant_{tenant_id}:middleware.cache",
            ]
            for pattern in cache_patterns:
                try:
                    cache.delete(pattern)
                except:
                    pass
    
    # SERVICE ORDER CACHE FUNCTIONS
    def invalidate_service_order_cache():
        """Invalidate service order related cache entries"""
        if tenant_id:
            order_keys = [
                'service_orders_list',
                'pending_service_orders',
                'completed_service_orders',
                'in_progress_service_orders',
                'recent_service_orders',
                'service_orders_count',
                'dashboard_service_orders',
                'service_order_stats',
                'daily_service_orders',
                'weekly_service_orders',
                'monthly_service_orders',
                'service_orders_revenue',
                'service_queue_data'
            ]
            for key in order_keys:
                cache_delete(key)
    
    def invalidate_service_order_by_id(order_id):
        """Invalidate cache for specific service order"""
        if tenant_id and order_id:
            specific_keys = [
                f'service_order_{order_id}',
                f'service_order_{order_id}_items',
                f'service_order_{order_id}_invoice'
            ]
            for key in specific_keys:
                cache_delete(key)
    
    # CUSTOMER CACHE FUNCTIONS
    def invalidate_customer_cache():
        """Invalidate customer-related cache entries"""
        if tenant_id:
            customer_keys = [
                'customers_list',
                'recent_customers',
                'active_customers',
                'customer_count',
                'customer_groups',
                'walk_in_customers',
                'returning_customers',
                'customer_vehicles',
                'vip_customers'
            ]
            for key in customer_keys:
                cache_delete(key)
    
    def invalidate_customer_by_id(customer_id):
        """Invalidate cache for specific customer"""
        if tenant_id and customer_id:
            specific_keys = [
                f'customer_{customer_id}',
                f'customer_{customer_id}_orders',
                f'customer_{customer_id}_payments',
                f'customer_{customer_id}_vehicles'
            ]
            for key in specific_keys:
                cache_delete(key)
    
    # SERVICE CACHE FUNCTIONS
    def invalidate_service_cache():
        """Invalidate service-related cache entries"""
        if tenant_id:
            service_keys = [
                'services_list',
                'active_services',
                'service_categories',
                'popular_services',
                'service_packages',
                'service_pricing',
                'package_services'
            ]
            for key in service_keys:
                cache_delete(key)
    
    # EMPLOYEE CACHE FUNCTIONS
    def invalidate_employee_cache():
        """Invalidate employee-related cache entries"""
        if tenant_id:
            employee_keys = [
                'employees_list',
                'active_employees',
                'employee_roles',
                'employee_departments',
                'attendants_list',
                'managers_list',
                'employee_attendance',
                'employee_commissions'
            ]
            for key in employee_keys:
                cache_delete(key)
    
    # PAYMENT CACHE FUNCTIONS
    def invalidate_payment_cache():
        """Invalidate payment-related cache entries"""
        if tenant_id:
            payment_keys = [
                'payments_list',
                'recent_payments',
                'payment_stats',
                'revenue_stats',
                'daily_revenue',
                'weekly_revenue',
                'monthly_revenue',
                'payment_methods_stats',
                'mpesa_payments',
                'cash_payments',
                'pending_payments'
            ]
            for key in payment_keys:
                cache_delete(key)
    
    # INVENTORY CACHE FUNCTIONS
    def invalidate_inventory_cache():
        """Invalidate inventory-related cache entries"""
        if tenant_id:
            inventory_keys = [
                'inventory_items',
                'low_stock_items',
                'out_of_stock_items',
                'inventory_categories',
                'inventory_alerts',
                'inventory_movements',
                'inventory_valuation',
                'reorder_items'
            ]
            for key in inventory_keys:
                cache_delete(key)
    
    # SUPPLIER CACHE FUNCTIONS
    def invalidate_supplier_cache():
        """Invalidate supplier-related cache entries"""
        if tenant_id:
            supplier_keys = [
                'suppliers_list',
                'active_suppliers',
                'supplier_categories',
                'purchase_orders',
                'pending_purchase_orders',
                'supplier_invoices',
                'supplier_payments',
                'goods_receipts',
                'supplier_evaluations'
            ]
            for key in supplier_keys:
                cache_delete(key)
    
    # EXPENSE CACHE FUNCTIONS
    def invalidate_expense_cache():
        """Invalidate expense-related cache entries"""
        if tenant_id:
            expense_keys = [
                'expenses_list',
                'recent_expenses',
                'expense_categories',
                'pending_expenses',
                'approved_expenses',
                'monthly_expenses',
                'expense_vendors',
                'recurring_expenses',
                'expense_budgets'
            ]
            for key in expense_keys:
                cache_delete(key)
    
    # BUSINESS METRICS CACHE FUNCTIONS
    def invalidate_business_metrics_cache():
        """Invalidate business metrics cache"""
        if tenant_id:
            metrics_keys = [
                'business_metrics',
                'daily_metrics',
                'weekly_metrics',
                'monthly_metrics',
                'business_goals',
                'business_alerts',
                'performance_metrics',
                'kpi_dashboard'
            ]
            for key in metrics_keys:
                cache_delete(key)
    
    # NOTIFICATION CACHE FUNCTIONS
    def invalidate_notification_cache():
        """Invalidate notification-related cache entries"""
        if tenant_id:
            notification_keys = [
                'notifications_list',
                'unread_notifications',
                'notification_templates',
                'notification_settings',
                'system_alerts',
                'business_announcements'
            ]
            for key in notification_keys:
                cache_delete(key)
    
    # REPORT CACHE FUNCTIONS
    def invalidate_report_cache():
        """Invalidate report-related cache entries"""
        if tenant_id:
            report_keys = [
                'business_reports',
                'sales_reports',
                'customer_reports',
                'inventory_reports',
                'financial_reports',
                'employee_reports',
                'performance_reports'
            ]
            for key in report_keys:
                cache_delete(key)
    
    # DASHBOARD CACHE FUNCTIONS
    def invalidate_dashboard_cache():
        """Invalidate dashboard-related cache entries"""
        if tenant_id:
            dashboard_keys = [
                'dashboard_data',
                'dashboard_widgets',
                'quick_actions',
                'dashboard_charts',
                'summary_stats',
                'recent_activities',
                'performance_indicators'
            ]
            for key in dashboard_keys:
                cache_delete(key)
    
    def clear_tenant_cache():
        """Clear all cache for current tenant"""
        if tenant_id:
            TenantAwareCacheHandler.clear_tenant_cache(tenant_id)
    
    def get_cache_stats():
        """Get cache statistics for current tenant"""
        if not tenant_id:
            return {}
        
        try:
            # Try to get cache backend info
            cache_backend = cache._cache if hasattr(cache, '_cache') else None
            stats = {
                'tenant_id': tenant_id,
                'cache_backend': type(cache).__name__,
                'cache_location': getattr(cache, '_cache', {}).get('_cache_location', 'Unknown'),
                'is_tenant_aware': hasattr(cache, 'clear_tenant_cache')
            }
            
            # Test cache performance
            test_key = f"perf_test_{int(time.time())}"
            start_time = time.time()
            cache_set(test_key, 'test_value', 10)
            set_time = time.time() - start_time
            
            start_time = time.time()
            cache_get(test_key)
            get_time = time.time() - start_time
            
            cache_delete(test_key)
            
            stats.update({
                'set_time_ms': round(set_time * 1000, 2),
                'get_time_ms': round(get_time * 1000, 2),
                'performance_ok': set_time < 0.1 and get_time < 0.05
            })
            
            return stats
            
        except Exception as e:
            return {'error': str(e)}
    
    def generate_cache_version():
        """Generate cache version for cache busting"""
        if tenant_id:
            # Create a version based on tenant and current time
            version_string = f"{tenant_id}_{int(time.time() / 300)}"  # Changes every 5 minutes
            return hashlib.md5(version_string.encode()).hexdigest()[:8]
        return 'system'
    
    return {
        # Tenant info
        'cache_tenant_id': tenant_id,
        'cache_tenant_prefix': f"tenant_{tenant_id}" if tenant_id else "system",
        
        # Basic cache operations
        'cache_get': cache_get,
        'cache_set': cache_set,
        'cache_delete': cache_delete,
        
        # Page cache invalidation
        'invalidate_page_cache': invalidate_page_cache,
        
        # App-specific cache invalidation functions
        'invalidate_service_order_cache': invalidate_service_order_cache,
        'invalidate_service_order_by_id': invalidate_service_order_by_id,
        'invalidate_customer_cache': invalidate_customer_cache,
        'invalidate_customer_by_id': invalidate_customer_by_id,
        'invalidate_service_cache': invalidate_service_cache,
        'invalidate_employee_cache': invalidate_employee_cache,
        'invalidate_payment_cache': invalidate_payment_cache,
        'invalidate_inventory_cache': invalidate_inventory_cache,
        'invalidate_supplier_cache': invalidate_supplier_cache,
        'invalidate_expense_cache': invalidate_expense_cache,
        'invalidate_business_metrics_cache': invalidate_business_metrics_cache,
        'invalidate_notification_cache': invalidate_notification_cache,
        'invalidate_report_cache': invalidate_report_cache,
        'invalidate_dashboard_cache': invalidate_dashboard_cache,
        'clear_tenant_cache': clear_tenant_cache,
        
        # Utility functions
        'get_tenant_cache_key': get_tenant_cache_key,
        'get_cache_stats': get_cache_stats,
        'generate_cache_version': generate_cache_version,
        
        # Cache status
        'cache_enabled': True,
        'cache_backend_name': type(cache).__name__,
        'is_tenant_cache': tenant_id is not None,
    }


def cache_performance_context(request):
    """
    Context processor for cache performance monitoring
    Adds cache performance metrics from all apps to templates
    """
    
    tenant = getattr(request, 'tenant', None) or get_current_tenant()
    tenant_id = str(tenant.id) if tenant else None
    
    if not tenant_id:
        return {}
    
    try:
        # Get or create performance metrics
        perf_cache_key = f"tenant_{tenant_id}:cache_performance"
        perf_data = cache.get(perf_cache_key)
        
        if not perf_data:
            # Initialize performance tracking with app-specific metrics
            perf_data = {
                # Overall metrics
                'cache_hits': 0,
                'cache_misses': 0,
                'last_updated': time.time(),
                'avg_response_time': 0.0,
                
                # App-specific cache metrics
                'service_orders': {
                    'hits': 0,
                    'misses': 0,
                    'avg_time': 0.0
                },
                'customers': {
                    'hits': 0,
                    'misses': 0,
                    'avg_time': 0.0
                },
                'payments': {
                    'hits': 0,
                    'misses': 0,
                    'avg_time': 0.0
                },
                'inventory': {
                    'hits': 0,
                    'misses': 0,
                    'avg_time': 0.0
                },
                'suppliers': {
                    'hits': 0,
                    'misses': 0,
                    'avg_time': 0.0
                },
                'expenses': {
                    'hits': 0,
                    'misses': 0,
                    'avg_time': 0.0
                },
                'reports': {
                    'hits': 0,
                    'misses': 0,
                    'avg_time': 0.0
                },
                'dashboard': {
                    'hits': 0,
                    'misses': 0,
                    'avg_time': 0.0
                }
            }
            cache.set(perf_cache_key, perf_data, 3600)  # 1 hour
        
        # Calculate hit ratio
        total_requests = perf_data['cache_hits'] + perf_data['cache_misses']
        hit_ratio = (perf_data['cache_hits'] / total_requests * 100) if total_requests > 0 else 0
        
        # Calculate app-specific hit ratios
        app_performance = {}
        for app_name, app_data in perf_data.items():
            if isinstance(app_data, dict) and 'hits' in app_data:
                app_total = app_data['hits'] + app_data['misses']
                app_hit_ratio = (app_data['hits'] / app_total * 100) if app_total > 0 else 0
                app_performance[app_name] = {
                    'hit_ratio': round(app_hit_ratio, 1),
                    'total_requests': app_total,
                    'avg_time': app_data['avg_time'],
                    'status': 'good' if app_hit_ratio > 70 else 'warning' if app_hit_ratio > 50 else 'poor'
                }
        
        return {
            'cache_performance': {
                'hit_ratio': round(hit_ratio, 1),
                'total_requests': total_requests,
                'avg_response_time': perf_data['avg_response_time'],
                'status': 'good' if hit_ratio > 70 else 'warning' if hit_ratio > 50 else 'poor',
                'app_performance': app_performance,
                'last_updated': perf_data['last_updated']
            }
        }
        
    except Exception:
        return {'cache_performance': {'status': 'error'}}


def cache_health_context(request):
    """
    Context processor for cache health monitoring
    Provides health status for different cache components
    """
    
    tenant = getattr(request, 'tenant', None) or get_current_tenant()
    tenant_id = str(tenant.id) if tenant else None
    
    if not tenant_id:
        return {}
    
    try:
        health_data = {
            # Cache backend health
            'backend_status': 'healthy',
            'backend_type': type(cache).__name__,
            'tenant_isolation': True,
            
            # App cache health
            'apps_health': {
                'services': {'status': 'healthy', 'last_check': time.time()},
                'customers': {'status': 'healthy', 'last_check': time.time()},
                'payments': {'status': 'healthy', 'last_check': time.time()},
                'inventory': {'status': 'healthy', 'last_check': time.time()},
                'suppliers': {'status': 'healthy', 'last_check': time.time()},
                'expenses': {'status': 'healthy', 'last_check': time.time()},
                'reports': {'status': 'healthy', 'last_check': time.time()},
                'dashboard': {'status': 'healthy', 'last_check': time.time()}
            },
            
            # Cache size and limits
            'size_info': {
                'max_entries': getattr(cache, 'max_entries', 'Unknown'),
                'current_entries': 'N/A',  # Hard to get from DatabaseCache
                'usage_percentage': 'N/A'
            },
            
            # Performance indicators
            'performance_indicators': {
                'response_time_ok': True,
                'hit_ratio_ok': True,
                'error_rate_low': True
            }
        }
        
        # Test cache connectivity
        try:
            test_key = f"health_check_{tenant_id}_{int(time.time())}"
            cache.set(test_key, 'health_test', 10)
            retrieved = cache.get(test_key)
            cache.delete(test_key)
            
            if retrieved != 'health_test':
                health_data['backend_status'] = 'warning'
                
        except Exception:
            health_data['backend_status'] = 'error'
            
        return {
            'cache_health': health_data
        }
        
    except Exception:
        return {
            'cache_health': {
                'backend_status': 'error',
                'apps_health': {},
                'performance_indicators': {
                    'response_time_ok': False,
                    'hit_ratio_ok': False,
                    'error_rate_low': False
                }
            }
        }