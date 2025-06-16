# apps/reports/utils.py - FIXED VERSION (key parts only)

import json
import uuid
from decimal import Decimal
from datetime import datetime, date
from django.utils import timezone
from django.contrib.auth.models import User

def safe_serialize_for_json(obj):
    """Safely serialize any object for JSON storage"""
    if isinstance(obj, uuid.UUID):
        return str(obj)
    elif isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif hasattr(obj, 'pk'):  # Django model instance
        return str(obj.pk)
    elif isinstance(obj, dict):
        return {k: safe_serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [safe_serialize_for_json(item) for item in obj]
    else:
        return obj

def track_analytics_event(event_type, event_data=None, employee=None, customer=None, **kwargs):
    """
    Track analytics events with proper UUID serialization
    
    Args:
        event_type (str): Type of event being tracked
        event_data (dict): Additional data about the event
        employee: Employee instance (optional)
        customer: Customer instance (optional)
        **kwargs: Additional keyword arguments
    """
    try:
        from .models import AnalyticsEvent
        
        # Safely serialize all event data
        safe_event_data = safe_serialize_for_json(event_data or {})
        
        # Prepare the data dictionary
        data = {
            'event_type': event_type,
            'timestamp': timezone.now().isoformat(),
        }
        
        # Add employee information if provided
        if employee:
            data.update({
                'employee_id': str(employee.id) if hasattr(employee, 'id') else str(employee.pk),
                'employee_name': str(employee) if hasattr(employee, '__str__') else 'Unknown',
            })
        
        # Add customer information if provided
        if customer:
            data.update({
                'customer_id': str(customer.id) if hasattr(customer, 'id') else str(customer.pk),
                'customer_name': customer.display_name if hasattr(customer, 'display_name') else str(customer),
                'customer_type': getattr(customer, 'customer_type', 'unknown'),
                'is_vip': getattr(customer, 'is_vip', False),
            })
        
        # Add session information if available from kwargs
        if 'session_id' in kwargs:
            data['session_id'] = str(kwargs['session_id'])
        
        # Merge event_data into the main data dict
        data.update(safe_event_data)
        
        # Ensure the final data is JSON serializable
        serialized_data = safe_serialize_for_json(data)
        
        # Create the analytics event
        analytics_event = AnalyticsEvent.objects.create(
            event_type=event_type,
            event_data=serialized_data,  # This should now be safely serialized
            employee_id=employee.id if employee and hasattr(employee, 'id') else None,
            customer_id=customer.id if customer and hasattr(customer, 'id') else None,
            session_id=kwargs.get('session_id', '')
        )
        
        return analytics_event
        
    except Exception as e:
        # Log the error but don't break the main flow
        print(f"Error tracking analytics event '{event_type}': {e}")
        print(f"Event data: {event_data}")
        import traceback
        traceback.print_exc()
        return None

def calculate_business_metrics(date_for_calculation=None):
    """
    Calculate business metrics for a given date
    
    Args:
        date_for_calculation: Date to calculate metrics for (defaults to today)
    """
    if date_for_calculation is None:
        date_for_calculation = timezone.now().date()
    
    try:
        from .models import BusinessMetrics, AnalyticsEvent
        from django.db.models import Count, Sum, Avg
        
        # Get or create metrics for the date
        metrics, created = BusinessMetrics.objects.get_or_create(
            date=date_for_calculation,
            defaults={
                'total_revenue': 0,
                'total_orders': 0,
                'new_customers': 0,
                'avg_order_value': 0,
                'total_customers': 0,
            }
        )
        
        # Calculate metrics from analytics events
        events_for_date = AnalyticsEvent.objects.filter(
            created_at__date=date_for_calculation
        )
        
        # Count different event types
        new_customers = events_for_date.filter(event_type='customer_registered').count()
        completed_services = events_for_date.filter(event_type='service_completed').count()
        
        # Calculate revenue from payments
        payment_events = events_for_date.filter(event_type='payment_received')
        total_revenue = 0
        for payment in payment_events:
            try:
                amount = payment.event_data.get('amount', 0)
                if isinstance(amount, (int, float)):
                    total_revenue += amount
                elif isinstance(amount, str):
                    total_revenue += float(amount)
            except (ValueError, TypeError):
                continue
        
        # Calculate average order value
        avg_order_value = total_revenue / completed_services if completed_services > 0 else 0
        
        # Get total customers count
        try:
            from apps.customers.models import Customer
            total_customers = Customer.objects.filter(is_active=True).count()
        except ImportError:
            total_customers = 0
        
        # Update metrics
        metrics.total_revenue = total_revenue
        metrics.total_orders = completed_services
        metrics.new_customers = new_customers
        metrics.avg_order_value = avg_order_value
        metrics.total_customers = total_customers
        metrics.save()
        
        return metrics
        
    except Exception as e:
        print(f"Error calculating business metrics: {e}")
        import traceback
        traceback.print_exc()
        return None

# Additional utility functions for reports

def generate_customer_analytics_data(customer):
    """Generate analytics data for a customer"""
    try:
        return {
            'customer_id': str(customer.id),
            'customer_code': customer.customer_id,
            'name': customer.display_name,
            'email': customer.email,
            'phone': str(customer.phone) if customer.phone else '',
            'customer_type': customer.customer_type,
            'is_vip': customer.is_vip,
            'is_active': customer.is_active,
            'city': customer.city,
            'created_at': customer.created_at.isoformat() if customer.created_at else None,
            'total_orders': customer.total_orders,
            'total_spent': float(customer.total_spent) if customer.total_spent else 0,
            'loyalty_points': customer.loyalty_points,
        }
    except Exception as e:
        print(f"Error generating customer analytics data: {e}")
        return {
            'customer_id': str(customer.id),
            'error': 'data_generation_failed'
        }

def generate_service_analytics_data(service_order):
    """Generate analytics data for a service order"""
    try:
        return {
            'order_id': str(service_order.id),
            'customer_id': str(service_order.customer.id),
            'customer_name': service_order.customer.display_name,
            'service_type': service_order.service.name if hasattr(service_order, 'service') else 'Unknown',
            'status': service_order.status,
            'total_amount': float(service_order.total_amount) if service_order.total_amount else 0,
            'created_at': service_order.created_at.isoformat() if service_order.created_at else None,
            'completed_at': service_order.completed_at.isoformat() if hasattr(service_order, 'completed_at') and service_order.completed_at else None,
        }
    except Exception as e:
        print(f"Error generating service analytics data: {e}")
        return {
            'order_id': str(service_order.id),
            'error': 'data_generation_failed'
        }