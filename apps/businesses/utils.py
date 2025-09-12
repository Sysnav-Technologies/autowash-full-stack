"""
Utility functions for business metrics and data filtering
"""
from django.utils import timezone as django_timezone
from django.apps import apps
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

def get_orders_for_date(date, status_filter=None):
    """
    Get service orders for a specific date with improved timezone handling.
    
    Args:
        date: The date to filter by
        status_filter: Optional list of statuses to filter by
        
    Returns:
        QuerySet of ServiceOrder objects
    """
    try:
        ServiceOrder = apps.get_model('services', 'ServiceOrder')
        
        # Try both date filtering methods to handle timezone issues
        # Method 1: Simple date filter
        orders_date_filter = ServiceOrder.objects.filter(created_at__date=date)
        
        # Method 2: Datetime range filter (more precise for timezone issues)
        date_start = django_timezone.make_aware(datetime.combine(date, datetime.min.time()))
        date_end = django_timezone.make_aware(datetime.combine(date, datetime.max.time()))
        orders_datetime_filter = ServiceOrder.objects.filter(
            created_at__gte=date_start, 
            created_at__lte=date_end
        )
        
        # Use whichever method finds more orders
        if orders_datetime_filter.count() > orders_date_filter.count():
            orders = orders_datetime_filter
        else:
            orders = orders_date_filter
        
        # Apply status filter if provided
        if status_filter:
            orders = orders.filter(status__in=status_filter)
        
        return orders
        
    except Exception as e:
        logger.error(f"Error getting orders for date {date}: {e}")
        # Return empty queryset on error
        try:
            ServiceOrder = apps.get_model('services', 'ServiceOrder')
            return ServiceOrder.objects.none()
        except:
            return None

def get_orders_for_date_range(start_date, end_date, status_filter=None):
    """
    Get service orders for a date range.
    
    Args:
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
        status_filter: Optional list of statuses to filter by
        
    Returns:
        QuerySet of ServiceOrder objects
    """
    try:
        ServiceOrder = apps.get_model('services', 'ServiceOrder')
        
        # Use date range filtering
        orders = ServiceOrder.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        
        # Apply status filter if provided
        if status_filter:
            orders = orders.filter(status__in=status_filter)
        
        return orders
        
    except Exception as e:
        logger.error(f"Error getting orders for date range {start_date} to {end_date}: {e}")
        # Return empty queryset on error
        try:
            ServiceOrder = apps.get_model('services', 'ServiceOrder')
            return ServiceOrder.objects.none()
        except:
            return None

def get_completed_statuses():
    """
    Get list of statuses that should be considered as completed services.
    
    Returns:
        List of status strings
    """
    return ['completed', 'confirmed']

def get_revenue_eligible_statuses():
    """
    Get list of statuses that should be considered for revenue calculation.
    Only non-cancelled orders should be eligible for revenue.
    
    Returns:
        List of status strings
    """
    return ['completed', 'confirmed', 'in_progress', 'pending']  # Exclude cancelled

def get_completely_paid_orders_for_date(date):
    """
    Get orders for a specific date that are completely paid (payment total >= order total).
    
    Args:
        date: The date to filter by
        
    Returns:
        List of order IDs that are completely paid
    """
    try:
        # Import here to avoid circular imports
        from django.db.models import Sum
        
        orders = get_orders_for_date(date)
        if not orders:
            return []
        
        # Exclude cancelled orders
        orders = orders.exclude(status='cancelled')
        
        completely_paid_order_ids = []
        
        for order in orders:
            # Get total payments for this order (excluding refunds)
            Payment = apps.get_model('payments', 'Payment')
            total_payments = Payment.objects.filter(
                service_order=order,
                status__in=['completed', 'verified']
            ).exclude(
                payment_type='refund'
            ).aggregate(Sum('amount'))['amount__sum'] or 0
            
            # Check if order is completely paid
            if total_payments >= (order.total_amount or 0):
                completely_paid_order_ids.append(order.id)
        
        return completely_paid_order_ids
        
    except Exception as e:
        logger.error(f"Error getting completely paid orders for date {date}: {e}")
        return []

def get_customers_for_date(date):
    """
    Get customers created on a specific date.
    
    Args:
        date: The date to filter by
        
    Returns:
        QuerySet of Customer objects
    """
    try:
        Customer = apps.get_model('customers', 'Customer')
        return Customer.objects.filter(created_at__date=date)
    except Exception as e:
        logger.error(f"Error getting customers for date {date}: {e}")
        return None

def get_customers_served_for_date(date):
    """
    Get count of unique customers served on a specific date (from service orders).
    
    Args:
        date: The date to filter by
        
    Returns:
        Integer count of unique customers
    """
    try:
        orders = get_orders_for_date(date, status_filter=['completed', 'confirmed', 'in_progress', 'pending'])
        if orders:
            return orders.values('customer').distinct().count()
        return 0
    except Exception as e:
        logger.error(f"Error getting customers served for date {date}: {e}")
        return 0

def get_employees_active():
    """
    Get active employees count.
    
    Returns:
        Integer count of active employees
    """
    try:
        Employee = apps.get_model('employees', 'Employee')
        return Employee.objects.filter(is_active=True).count()
    except Exception as e:
        logger.error(f"Error getting active employees: {e}")
        return 0

def get_payments_for_date(date, status_filter=None):
    """
    Get payments for a specific date.
    
    Args:
        date: The date to filter by
        status_filter: Optional list of statuses to filter by
        
    Returns:
        QuerySet of Payment objects
    """
    try:
        Payment = apps.get_model('payments', 'Payment')
        payments = Payment.objects.filter(created_at__date=date)
        
        if status_filter:
            payments = payments.filter(status__in=status_filter)
        
        return payments
    except Exception as e:
        logger.error(f"Error getting payments for date {date}: {e}")
        return None

def get_expenses_for_date(date, status_filter=None):
    """
    Get expenses for a specific date.
    
    Args:
        date: The date to filter by
        status_filter: Optional list of statuses to filter by
        
    Returns:
        QuerySet of Expense objects
    """
    try:
        Expense = apps.get_model('expenses', 'Expense')
        expenses = Expense.objects.filter(expense_date=date)
        
        if status_filter:
            expenses = expenses.filter(status__in=status_filter)
        
        return expenses
    except Exception as e:
        logger.error(f"Error getting expenses for date {date}: {e}")
        return None
