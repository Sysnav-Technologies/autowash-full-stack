# subscriptions/utils.py
import requests
import base64
import json
import logging
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from .models import SubscriptionDiscount

logger = logging.getLogger(__name__)

def get_mpesa_access_token():
    """Get M-Pesa access token with caching"""
    cache_key = 'mpesa_subscription_token'
    
    # Try cache first
    try:
        token_data = cache.get(cache_key)
        if token_data and token_data.get('expires_at') > timezone.now():
            return token_data['token']
    except Exception as e:
        logger.warning(f"Cache get failed: {e}")
    
    try:
        # M-Pesa OAuth URL
        url = f"{settings.MPESA_BASE_URL}/oauth/v1/generate?grant_type=client_credentials"
        
        # Create auth header
        auth_string = f"{settings.MPESA_CONSUMER_KEY}:{settings.MPESA_CONSUMER_SECRET}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        headers = {
            'Authorization': f'Basic {auth_b64}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            access_token = data['access_token']
            expires_in = int(data.get('expires_in', 3600))
            
            # Cache token
            expires_at = timezone.now() + timedelta(seconds=expires_in - 60)
            try:
                cache.set(cache_key, {
                    'token': access_token,
                    'expires_at': expires_at
                }, expires_in - 60)
            except Exception as e:
                logger.warning(f"Cache set failed: {e}")
            
            return access_token
        else:
            logger.error(f"Token request failed: {response.status_code} - {response.text}")
            
            # Development fallback
            if settings.DEBUG and settings.MPESA_ENVIRONMENT == 'sandbox':
                logger.warning("Using development fallback token")
                fallback_token = "fake_development_token"
                try:
                    cache.set(cache_key, {
                        'token': fallback_token,
                        'expires_at': timezone.now() + timedelta(minutes=5)
                    }, 300)
                except Exception:
                    pass
                return fallback_token
            
            return None
            
    except Exception as e:
        logger.error(f"Error getting M-Pesa token: {e}")
        
        # Development fallback
        if settings.DEBUG and settings.MPESA_ENVIRONMENT == 'sandbox':
            logger.warning("Using development fallback token due to exception")
            fallback_token = "fake_development_token"
            try:
                cache.set(cache_key, {
                    'token': fallback_token,
                    'expires_at': timezone.now() + timedelta(minutes=5)
                }, 300)
            except Exception:
                pass
            return fallback_token
        
        return None

def create_mpesa_payment(payment, phone_number):
    """Create M-Pesa STK push payment"""
    try:
        # Get access token
        access_token = get_mpesa_access_token()
        if not access_token:
            return {
                'success': False,
                'message': 'Failed to authenticate with M-Pesa'
            }
        
        # Generate timestamp and password
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password_string = f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}"
        password = base64.b64encode(password_string.encode()).decode()
        
        # Format phone number
        if phone_number.startswith('0'):
            phone_number = '254' + phone_number[1:]
        elif phone_number.startswith('+254'):
            phone_number = phone_number[1:]
        elif not phone_number.startswith('254'):
            phone_number = '254' + phone_number
        
        # STK Push URL
        url = f"{settings.MPESA_BASE_URL}/mpesa/stkpush/v1/processrequest"
        
        # Request payload
        payload = {
            "BusinessShortCode": settings.MPESA_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(payment.amount),
            "PartyA": phone_number,
            "PartyB": settings.MPESA_SHORTCODE,
            "PhoneNumber": phone_number,
            "CallBackURL": settings.MPESA_CALLBACK_URL,
            "AccountReference": f"SUB-{payment.subscription_id}",
            "TransactionDesc": "Subscription payment"
        }
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('ResponseCode') == '0':
                return {
                    'success': True,
                    'checkout_request_id': data.get('CheckoutRequestID'),
                    'message': 'Payment request sent to your phone'
                }
            else:
                return {
                    'success': False,
                    'message': data.get('errorMessage', 'Payment failed')
                }
        else:
            logger.error(f"STK Push failed: {response.status_code} - {response.text}")
            
            # Development fallback
            if settings.DEBUG and settings.MPESA_ENVIRONMENT == 'sandbox' and 'fake' in access_token:
                import uuid
                fake_checkout_id = f"ws_co_{uuid.uuid4().hex[:20]}"
                return {
                    'success': True,
                    'checkout_request_id': fake_checkout_id,
                    'message': 'Development mode: Payment simulated'
                }
            
            return {
                'success': False,
                'message': 'Payment service unavailable'
            }
        
    except Exception as e:
        logger.error(f"Error creating M-Pesa payment: {e}")
        return {
            'success': False,
            'message': 'Payment processing error'
        }

def check_mpesa_payment_status(payment_id):
    """Check M-Pesa payment status"""
    try:
        from .models import Payment
        
        # Try to get payment by payment_id (UUID field) first, then by id
        try:
            payment = Payment.objects.using('default').get(payment_id=payment_id)
        except Payment.DoesNotExist:
            payment = Payment.objects.using('default').get(id=payment_id)
        
        access_token = get_mpesa_access_token()
        logger.info(f"Payment status check - Payment ID: {payment_id}, Token: {access_token}, Debug: {settings.DEBUG}, Environment: {getattr(settings, 'MPESA_ENVIRONMENT', 'not_set')}")
        
        if not access_token:
            logger.warning("No access token available for payment status check")
            return {'success': False, 'message': 'Could not authenticate'}
        
        # Enhanced development fallback - check multiple conditions
        is_development = (
            settings.DEBUG and 
            (
                getattr(settings, 'MPESA_ENVIRONMENT', '') == 'sandbox' or
                'fake' in access_token or
                'development' in access_token.lower()
            )
        )
        
        if is_development:
            logger.info("Development mode detected: Simulating payment completion")
            # Update payment status immediately in development
            payment.status = 'completed'
            payment.completed_at = timezone.now()
            payment.mpesa_receipt_number = f"DEV{str(payment_id)[:8]}"
            payment.save(using='default')
            
            return {
                'success': True,
                'message': 'Development mode: Payment completed',
                'development_mode': True
            }
        
        # In production, you would query M-Pesa transaction status API here
        # For now, return pending status
        logger.info("Production mode: Returning pending status")
        return {
            'success': False,
            'message': 'Payment status query in progress'
        }
        
    except Exception as e:
        logger.error(f"Error checking payment status: {e}")
        return {'success': False, 'message': 'Status check failed'}

def process_mpesa_callback(callback_data):
    """Process M-Pesa callback"""
    try:
        # Extract callback data
        stk_callback = callback_data.get('Body', {}).get('stkCallback', {})
        result_code = stk_callback.get('ResultCode')
        checkout_request_id = stk_callback.get('CheckoutRequestID')
        
        if result_code == 0:
            # Payment successful
            callback_metadata = stk_callback.get('CallbackMetadata', {}).get('Item', [])
            
            payment_details = {}
            for item in callback_metadata:
                name = item.get('Name')
                value = item.get('Value')
                
                if name == 'Amount':
                    payment_details['amount'] = value
                elif name == 'MpesaReceiptNumber':
                    payment_details['receipt_number'] = value
                elif name == 'PhoneNumber':
                    payment_details['phone_number'] = value
            
            return {
                'success': True,
                'payment_details': payment_details,
                'checkout_request_id': checkout_request_id
            }
        else:
            # Payment failed
            result_desc = stk_callback.get('ResultDesc', 'Payment failed')
            return {
                'success': False,
                'message': result_desc,
                'checkout_request_id': checkout_request_id
            }
        
    except Exception as e:
        logger.error(f"Error processing M-Pesa callback: {e}")
        return {
            'success': False,
            'message': 'Callback processing error'
        }

def verify_discount_code(code, plan):
    """Verify discount code"""
    try:
        discount = SubscriptionDiscount.objects.filter(
            code=code,
            is_active=True,
            valid_from__lte=timezone.now(),
            valid_until__gte=timezone.now()
        ).first()
        
        if not discount:
            return {'valid': False, 'message': 'Invalid or expired discount code'}
        
        # Check usage limit
        if discount.usage_limit and discount.times_used >= discount.usage_limit:
            return {'valid': False, 'message': 'Discount code usage limit exceeded'}
        
        # Check if applicable to plan
        if discount.applicable_plans.exists() and plan not in discount.applicable_plans.all():
            return {'valid': False, 'message': 'Discount code not applicable to this plan'}
        
        return {
            'valid': True,
            'discount': discount,
            'message': f'{discount.discount_percentage}% discount applied'
        }
        
    except Exception as e:
        logger.error(f"Error verifying discount code: {e}")
        return {'valid': False, 'message': 'Error verifying discount code'}