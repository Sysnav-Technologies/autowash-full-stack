"""
Timezone utilities for AutoWash system
Ensures consistent timezone handling across the application
"""
import pytz
from django.conf import settings
from django.utils import timezone
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def get_kenya_timezone():
    """Get Kenya timezone (EAT - East Africa Time)"""
    return pytz.timezone('Africa/Nairobi')


def get_current_kenya_time():
    """Get current time in Kenya timezone"""
    kenya_tz = get_kenya_timezone()
    utc_now = timezone.now()
    return utc_now.astimezone(kenya_tz)


def convert_to_kenya_time(dt):
    """Convert a datetime to Kenya timezone"""
    if dt is None:
        return None
    
    kenya_tz = get_kenya_timezone()
    
    # If datetime is naive, make it timezone aware (assume it's in Django's TIME_ZONE)
    if dt.tzinfo is None:
        dt = timezone.make_aware(dt)
    
    return dt.astimezone(kenya_tz)


def format_kenya_time(dt, format_string="%Y-%m-%d %H:%M:%S %Z"):
    """Format datetime in Kenya timezone"""
    if dt is None:
        return None
    
    kenya_time = convert_to_kenya_time(dt)
    return kenya_time.strftime(format_string)


def is_timezone_aware(dt):
    """Check if datetime is timezone aware"""
    return dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None


def debug_timezone_info():
    """Debug timezone configuration - useful for troubleshooting"""
    info = {
        'django_timezone': settings.TIME_ZONE,
        'django_use_tz': settings.USE_TZ,
        'current_utc': timezone.now(),
        'current_kenya': get_current_kenya_time(),
        'kenya_offset': get_kenya_timezone().utcoffset(datetime.now()),
    }
    
    logger.info(f"Timezone debug info: {info}")
    return info


def safe_timezone_conversion(dt_value, target_tz='Africa/Nairobi'):
    """
    Safely convert datetime value to target timezone
    Handles corrupted or malformed datetime fields
    """
    if dt_value is None:
        return None
    
    try:
        # If it's already a datetime object
        if isinstance(dt_value, datetime):
            target_timezone = pytz.timezone(target_tz)
            
            # Make timezone aware if it isn't
            if dt_value.tzinfo is None:
                dt_value = timezone.make_aware(dt_value)
            
            # Convert to target timezone
            return dt_value.astimezone(target_timezone)
        
        # If it's a string, try to parse it first
        elif isinstance(dt_value, str):
            # Try Django's timezone parsing
            parsed_dt = timezone.datetime.fromisoformat(dt_value.replace('Z', '+00:00'))
            return safe_timezone_conversion(parsed_dt, target_tz)
        
        else:
            logger.warning(f"Unexpected datetime type: {type(dt_value)}")
            return None
            
    except Exception as e:
        logger.error(f"Error converting datetime to timezone {target_tz}: {e}")
        return None


class TimezoneMiddleware:
    """
    Middleware to ensure consistent timezone handling
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Set timezone context for this request
        request.kenya_time = get_current_kenya_time()
        
        response = self.get_response(request)
        return response