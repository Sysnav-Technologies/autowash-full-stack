import os
import uuid
import random
import string
from datetime import datetime, timedelta
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import requests
import json

def generate_random_string(length=8):
    """Generate a random string of specified length"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def generate_unique_code(prefix='', length=6):
    """Generate a unique code with optional prefix"""
    code = generate_random_string(length)
    return f"{prefix}{code}" if prefix else code

def upload_to_path(instance, filename):
    """Generate upload path for files"""
    ext = filename.split('.')[-1]
    # Convert UUID to string to avoid serialization issues
    unique_filename = f"{str(uuid.uuid4())}.{ext}"
    return os.path.join(
        instance.__class__.__name__.lower(),
        str(instance.id) if instance.id else 'temp',
        unique_filename
    )

def send_email_notification(subject, message, recipient_list, html_message=None):
    """Send email notification"""
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Email sending failed: {e}")
        return False

def send_sms_notification(phone_number, message):
    """Send SMS notification using Africa's Talking API"""
    try:
        import africastalking
        
        # Initialize SDK
        username = settings.SMS_USERNAME
        api_key = settings.SMS_API_KEY
        
        if not api_key:
            return False
            
        africastalking.initialize(username, api_key)
        sms = africastalking.SMS
        
        # Send SMS
        response = sms.send(message, [phone_number])
        return response['SMSMessageData']['Recipients'][0]['status'] == 'Success'
        
    except Exception as e:
        print(f"SMS sending failed: {e}")
        return False

def format_currency(amount, currency='KES'):
    """Format currency amount"""
    return f"{currency} {amount:,.2f}"

def format_phone_number(phone_number):
    """Format phone number to international format"""
    if not phone_number:
        return None
        
    # Remove any non-digit characters
    phone = ''.join(filter(str.isdigit, phone_number))
    
    # Handle Kenyan numbers
    if phone.startswith('0'):
        phone = '254' + phone[1:]
    elif phone.startswith('7') or phone.startswith('1'):
        phone = '254' + phone
    elif not phone.startswith('254'):
        phone = '254' + phone
        
    return f"+{phone}"

def calculate_business_hours(start_time, end_time):
    """Calculate business hours between two times"""
    if not start_time or not end_time:
        return 0
        
    start = datetime.combine(datetime.today(), start_time)
    end = datetime.combine(datetime.today(), end_time)
    
    if end < start:
        end += timedelta(days=1)
        
    return (end - start).total_seconds() / 3600

def get_next_business_day(date=None):
    """Get next business day (Monday-Saturday)"""
    if not date:
        date = timezone.now().date()
        
    next_day = date + timedelta(days=1)
    while next_day.weekday() == 6:  # Sunday
        next_day += timedelta(days=1)
        
    return next_day

def generate_invoice_number(business_id):
    """Generate unique invoice number"""
    now = timezone.now()
    return f"INV-{business_id}-{now.strftime('%Y%m%d')}-{generate_random_string(4)}"

def generate_receipt_number(business_id):
    """Generate unique receipt number"""
    now = timezone.now()
    return f"RCP-{business_id}-{now.strftime('%Y%m%d')}-{generate_random_string(4)}"

def sanitize_filename(filename):
    """Sanitize filename for safe storage"""
    # Remove or replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename

def compress_image(image_path, quality=85):
    """Compress image file"""
    try:
        from PIL import Image
        
        with Image.open(image_path) as img:
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # Resize if too large
            max_size = (1920, 1080)
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
                # Save with compression
            img.save(image_path, 'JPEG', quality=quality, optimize=True)
            
        return True
    except Exception as e:
        print(f"Image compression failed: {e}")
        return False

def validate_kenyan_phone(phone_number):
    """Validate Kenyan phone number"""
    if not phone_number:
        return False
        
    # Remove any non-digit characters
    phone = ''.join(filter(str.isdigit, phone_number))
    
    # Check if it's a valid Kenyan number
    valid_prefixes = ['254701', '254702', '254703', '254704', '254705', '254706', '254707', '254708', '254709',
                     '254710', '254711', '254712', '254713', '254714', '254715', '254716', '254717', '254718', '254719',
                     '254720', '254721', '254722', '254723', '254724', '254725', '254726', '254727', '254728', '254729',
                     '254730', '254731', '254732', '254733', '254734', '254735', '254736', '254737', '254738', '254739',
                     '254740', '254741', '254742', '254743', '254744', '254745', '254746', '254747', '254748', '254749',
                     '254750', '254751', '254752', '254753', '254754', '254755', '254756', '254757', '254758', '254759',
                     '254760', '254761', '254762', '254763', '254764', '254765', '254766', '254767', '254768', '254769']
    
    if phone.startswith('0'):
        phone = '254' + phone[1:]
    elif phone.startswith('7') or phone.startswith('1'):
        phone = '254' + phone
        
    return any(phone.startswith(prefix) for prefix in valid_prefixes) and len(phone) == 12

def calculate_service_duration(start_time, end_time):
    """Calculate service duration in minutes"""
    if not start_time or not end_time:
        return 0
        
    duration = end_time - start_time
    return int(duration.total_seconds() / 60)

def get_business_performance_metrics(business, period='month'):
    """Get business performance metrics for a given period"""
    from datetime import datetime, timedelta
    from django.db.models import Sum, Count, Avg
    
    now = timezone.now()
    
    if period == 'day':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'week':
        start_date = now - timedelta(days=now.weekday())
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'month':
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == 'year':
        start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start_date = now - timedelta(days=30)
    
    # Import here to avoid circular imports
    from apps.services.models import ServiceOrder
    from apps.customers.models import Customer
    
    orders = ServiceOrder.objects.filter(
        created_at__gte=start_date,
        status__in=['completed', 'paid']
    )
    
    metrics = {
        'total_revenue': orders.aggregate(Sum('total_amount'))['total_amount__sum'] or 0,
        'total_orders': orders.count(),
        'average_order_value': orders.aggregate(Avg('total_amount'))['total_amount__avg'] or 0,
        'new_customers': Customer.objects.filter(created_at__gte=start_date).count(),
        'period': period,
        'start_date': start_date,
        'end_date': now
    }
    
    return metrics


# Add these functions to your existing apps/core/utils.py file

def send_test_sms(phone_number, message=None):
    """Send a test SMS to verify SMS functionality"""
    try:
        if not message:
            message = "Test SMS from your business management system. SMS notifications are working correctly!"
        
        return send_sms_notification(phone_number, message)
    except Exception as e:
        print(f"Test SMS failed: {e}")
        return False

def send_test_email(email_address, subject=None, message=None):
    """Send a test email to verify email functionality"""
    try:
        if not subject:
            subject = "Test Email - Business Management System"
        
        if not message:
            message = """
            This is a test email from your business management system.
            
            Your email notifications are configured correctly and working as expected.
            
            If you received this email, your email settings are properly configured.
            
            Best regards,
            Your Business Management System
            """
        
        return send_email_notification(
            subject=subject,
            message=message,
            recipient_list=[email_address]
        )
    except Exception as e:
        print(f"Test email failed: {e}")
        return False

def validate_business_settings(business):
    """Validate business configuration completeness"""
    validation_results = {
        'is_complete': True,
        'missing_fields': [],
        'warnings': [],
        'recommendations': []
    }
    
    # Required fields check - using actual Business model field names
    required_fields = {
        'name': 'Business name is required',
        'phone': 'Business phone number is required',
        'email': 'Business email address is required'
    }
    
    for field, message in required_fields.items():
        field_value = getattr(business, field, None)
        if not field_value or (hasattr(field_value, '__len__') and len(str(field_value).strip()) == 0):
            validation_results['missing_fields'].append(message)
            validation_results['is_complete'] = False
    
    # Optional but recommended fields - using actual Business model field names
    recommended_fields = {
        'logo': 'Consider adding a business logo for better branding',
        'website': 'Adding a website URL can help customers find you online',
        'description': 'A business description helps customers understand your services'
    }
    
    for field, message in recommended_fields.items():
        field_value = getattr(business, field, None)
        if not field_value or (hasattr(field_value, '__len__') and len(str(field_value).strip()) == 0):
            validation_results['recommendations'].append(message)
    
    # Business hours validation - using correct field names from Business model
    if not business.opening_time or not business.closing_time:
        validation_results['warnings'].append('Business hours are not set')
    
    # Address validation - check if any address fields exist and are populated
    address_fields = ['address', 'city', 'state', 'country']  # Based on Address mixin
    has_address = False
    for field in address_fields:
        if hasattr(business, field):
            field_value = getattr(business, field, None)
            if field_value and len(str(field_value).strip()) > 0:
                has_address = True
                break
    
    if not has_address:
        validation_results['recommendations'].append('Adding business address information helps with location-based services')
    
    return validation_results

def get_system_health_status():
    """Get overall system health status"""
    from django.db import connection
    
    health_status = {
        'database': 'healthy',
        'email': 'unknown',
        'sms': 'unknown',
        'storage': 'healthy',
        'overall': 'healthy'
    }
    
    # Check database connection
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        health_status['database'] = 'healthy'
    except Exception:
        health_status['database'] = 'unhealthy'
        health_status['overall'] = 'unhealthy'
    
    # Check email configuration
    try:
        from django.core.mail import get_connection
        connection = get_connection()
        connection.open()
        connection.close()
        health_status['email'] = 'healthy'
    except Exception:
        health_status['email'] = 'unhealthy'
    
    # Check SMS configuration
    if hasattr(settings, 'SMS_API_KEY') and settings.SMS_API_KEY:
        health_status['sms'] = 'configured'
    else:
        health_status['sms'] = 'not_configured'
    
    return health_status

def create_system_backup_data(business):
    """Create a dictionary of business data for backup"""
    backup_data = {
        'metadata': {
            'business_name': business.name,
            'business_id': str(business.id),
            'backup_date': timezone.now().isoformat(),
            'version': '1.0'
        },
        'business': {
            'name': business.name,
            'business_type': business.business_type,
            'description': business.description,
            'phone': str(business.phone) if business.phone else None,
            'email': business.email,
            'website': business.website,
            'address': business.address,
            'city': business.city,
            'state': business.state,
            'postal_code': business.postal_code,
            'country': business.country,
            'created_at': business.created_at.isoformat(),
        }
    }
    
    # Add customers data if available
    try:
        from apps.customers.models import Customer
        customers = Customer.objects.filter(is_active=True)
        backup_data['customers'] = []
        
        for customer in customers:
            customer_data = {
                'customer_id': customer.customer_id,
                'first_name': customer.first_name,
                'last_name': customer.last_name,
                'phone': str(customer.phone) if customer.phone else None,
                'email': customer.email,
                'customer_type': customer.customer_type,
                'created_at': customer.created_at.isoformat(),
            }
            backup_data['customers'].append(customer_data)
    except ImportError:
        pass
    
    # Add services data if available
    try:
        from apps.services.models import Service, ServiceCategory
        
        # Service categories
        categories = ServiceCategory.objects.filter(is_active=True)
        backup_data['service_categories'] = []
        
        for category in categories:
            category_data = {
                'name': category.name,
                'description': category.description,
                'icon': category.icon,
                'color': category.color,
            }
            backup_data['service_categories'].append(category_data)
        
        # Services
        services = Service.objects.filter(is_active=True)
        backup_data['services'] = []
        
        for service in services:
            service_data = {
                'name': service.name,
                'description': service.description,
                'category': service.category.name if service.category else None,
                'base_price': float(service.base_price),
                'estimated_duration': service.estimated_duration,
                'is_popular': service.is_popular,
                'is_premium': service.is_premium,
            }
            backup_data['services'].append(service_data)
    except ImportError:
        pass
    
    return backup_data

def export_data_to_format(data, format_type='json'):
    """Export data to specified format"""
    if format_type.lower() == 'json':
        return json.dumps(data, indent=2, default=str)
    
    elif format_type.lower() == 'csv':
        import csv
        import io
        
        output = io.StringIO()
        
        # Export customers if available
        if 'customers' in data:
            writer = csv.writer(output)
            writer.writerow(['Customer ID', 'First Name', 'Last Name', 'Phone', 'Email', 'Type', 'Created Date'])
            
            for customer in data['customers']:
                writer.writerow([
                    customer.get('customer_id', ''),
                    customer.get('first_name', ''),
                    customer.get('last_name', ''),
                    customer.get('phone', ''),
                    customer.get('email', ''),
                    customer.get('customer_type', ''),
                    customer.get('created_at', ''),
                ])
        
        return output.getvalue()
    
    elif format_type.lower() == 'excel':
        try:
            import pandas as pd
            import io
            
            output = io.BytesIO()
            
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Export customers
                if 'customers' in data:
                    customers_df = pd.DataFrame(data['customers'])
                    customers_df.to_excel(writer, sheet_name='Customers', index=False)
                
                # Export services
                if 'services' in data:
                    services_df = pd.DataFrame(data['services'])
                    services_df.to_excel(writer, sheet_name='Services', index=False)
                
                # Export business info
                business_df = pd.DataFrame([data['business']])
                business_df.to_excel(writer, sheet_name='Business Info', index=False)
            
            return output.getvalue()
        
        except ImportError:
            # Fallback to CSV if pandas not available
            return export_data_to_format(data, 'csv')
    
    return str(data)

def generate_backup_filename(business, format_type='json'):
    """Generate a unique backup filename"""
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    business_slug = getattr(business, 'slug', str(business.id))
    
    return f"backup_{business_slug}_{timestamp}.{format_type.lower()}"

def calculate_backup_size_estimate(business):
    """Estimate backup file size"""
    size_estimate = {
        'customers': 0,
        'services': 0,
        'payments': 0,
        'media': 0,
        'total': 0
    }
    
    try:
        # Estimate customer data size (rough calculation)
        from apps.customers.models import Customer
        customer_count = Customer.objects.count()
        size_estimate['customers'] = customer_count * 1024  # ~1KB per customer
    except ImportError:
        pass
    
    try:
        # Estimate service data size
        from apps.services.models import Service
        service_count = Service.objects.count()
        size_estimate['services'] = service_count * 512  # ~0.5KB per service
    except ImportError:
        pass
    
    try:
        # Estimate payment data size
        from apps.payments.models import Payment
        payment_count = Payment.objects.count()
        size_estimate['payments'] = payment_count * 256  # ~0.25KB per payment
    except ImportError:
        pass
    
    # Calculate total
    size_estimate['total'] = sum([
        size_estimate['customers'],
        size_estimate['services'],
        size_estimate['payments'],
        size_estimate['media']
    ])
    
    return size_estimate

def format_file_size(size_in_bytes):
    """Format file size in human readable format"""
    if size_in_bytes < 1024:
        return f"{size_in_bytes} B"
    elif size_in_bytes < 1024 * 1024:
        return f"{size_in_bytes / 1024:.1f} KB"
    elif size_in_bytes < 1024 * 1024 * 1024:
        return f"{size_in_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_in_bytes / (1024 * 1024 * 1024):.1f} GB"