"""
UUID Utilities for AutoWash System
Handles UUID validation, conversion, and error prevention
"""
import uuid
import logging

logger = logging.getLogger(__name__)


def is_valid_uuid(uuid_str, allow_none=True):
    """
    Check if a string is a valid UUID
    
    Args:
        uuid_str: String to check
        allow_none: Whether None/empty values are considered valid
        
    Returns:
        bool: True if valid UUID or allowed None, False otherwise
    """
    if uuid_str is None or uuid_str == '':
        return allow_none
    
    if isinstance(uuid_str, uuid.UUID):
        return True
    
    # Convert to string and check if it looks like a session key (not a UUID)
    str_val = str(uuid_str)
    
    # Django session keys are typically 32 characters of base64-like characters
    # If it's a session key, it's not a valid UUID
    if len(str_val) == 32 and not any(c in str_val for c in '-'):
        # Check if it contains characters that wouldn't be in a UUID
        uuid_chars = set('0123456789abcdefABCDEF-')
        if not all(c in uuid_chars for c in str_val.lower()):
            logger.debug(f"Rejecting session key as UUID: {str_val}")
            return False
        
    try:
        uuid.UUID(str_val)
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def safe_uuid_convert(uuid_str, default=None):
    """
    Safely convert a string to UUID object
    
    Args:
        uuid_str: String or UUID to convert
        default: Default value if conversion fails
        
    Returns:
        UUID object or default value
    """
    if uuid_str is None:
        return default
        
    if isinstance(uuid_str, uuid.UUID):
        return uuid_str
        
    try:
        return uuid.UUID(str(uuid_str))
    except (ValueError, TypeError, AttributeError) as e:
        logger.warning(f"Failed to convert '{uuid_str}' to UUID: {e}")
        return default


def clean_uuid_string(uuid_str):
    """
    Clean and format UUID string
    
    Args:
        uuid_str: String to clean
        
    Returns:
        str: Cleaned UUID string or None if invalid
    """
    if not uuid_str:
        return None
        
    try:
        # Convert to UUID and back to string to ensure proper formatting
        return str(uuid.UUID(str(uuid_str)))
    except (ValueError, TypeError, AttributeError):
        return None


def validate_model_uuids(model_instance, uuid_fields):
    """
    Validate all UUID fields in a model instance
    
    Args:
        model_instance: Django model instance
        uuid_fields: List of field names that should be UUIDs
        
    Returns:
        dict: Dictionary of field_name: is_valid pairs
    """
    results = {}
    
    for field_name in uuid_fields:
        try:
            value = getattr(model_instance, field_name)
            results[field_name] = is_valid_uuid(value)
        except AttributeError:
            results[field_name] = False
            
    return results


def generate_safe_uuid():
    """
    Generate a new UUID safely
    
    Returns:
        UUID: New UUID4 object
    """
    return uuid.uuid4()


def uuid_to_str(uuid_obj):
    """
    Convert UUID to string safely
    
    Args:
        uuid_obj: UUID object or string
        
    Returns:
        str: String representation of UUID or None if invalid
    """
    if uuid_obj is None:
        return None
        
    if isinstance(uuid_obj, str):
        # Validate it's a proper UUID string first
        if is_valid_uuid(uuid_obj):
            return uuid_obj
        else:
            return None
            
    try:
        return str(uuid_obj)
    except (TypeError, AttributeError):
        return None


def fix_corrupted_uuid_field(corrupted_value):
    """
    Attempt to fix corrupted UUID fields
    
    Args:
        corrupted_value: The corrupted UUID value
        
    Returns:
        str: Fixed UUID string or None if unfixable
    """
    if not corrupted_value:
        return None
        
    # If it's already valid, return as-is
    if is_valid_uuid(corrupted_value):
        return str(corrupted_value)
    
    # Log the corrupted value for debugging
    logger.error(f"Found corrupted UUID value: '{corrupted_value}' (length: {len(str(corrupted_value))})")
    
    # Try common fixes
    corrupted_str = str(corrupted_value)
    
    # Case 1: Remove non-hex characters
    hex_only = ''.join(c for c in corrupted_str if c in '0123456789abcdefABCDEF-')
    if len(hex_only) >= 32:
        try:
            # Try to format as UUID (add dashes if missing)
            if len(hex_only) == 32:
                formatted = f"{hex_only[:8]}-{hex_only[8:12]}-{hex_only[12:16]}-{hex_only[16:20]}-{hex_only[20:32]}"
                test_uuid = uuid.UUID(formatted)
                logger.info(f"Fixed UUID: '{corrupted_value}' -> '{formatted}'")
                return str(test_uuid)
        except ValueError:
            pass
    
    # Case 2: If it's too long, truncate to UUID length
    if len(corrupted_str) > 36:
        truncated = corrupted_str[:36]
        if is_valid_uuid(truncated):
            logger.info(f"Fixed UUID by truncating: '{corrupted_value}' -> '{truncated}'")
            return truncated
    
    # If we can't fix it, generate a new UUID and log the issue
    new_uuid = generate_safe_uuid()
    logger.error(f"Could not fix corrupted UUID '{corrupted_value}', generating new UUID: {new_uuid}")
    
    return str(new_uuid)