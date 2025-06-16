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