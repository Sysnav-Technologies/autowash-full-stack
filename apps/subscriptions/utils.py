# subscriptions/utils.py
import requests
import base64
from django.conf import settings
from django.utils import timezone
from .models import SubscriptionDiscount
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

def get_mpesa_access_token():
    """
    Get M-Pesa Daraja API access token
    """
    try:
        # Create basic auth string
        consumer_key = settings.MPESA_CONSUMER_KEY
        consumer_secret = settings.MPESA_CONSUMER_SECRET
        
        if not consumer_key or not consumer_secret:
            logger.error("M-Pesa consumer key or secret not configured")
            return None
            
        api_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials" if settings.MPESA_ENVIRONMENT == 'sandbox' else "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
        
        # Create basic auth string
        auth_string = f"{consumer_key}:{consumer_secret}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        
        headers = {
            'Authorization': f'Basic {encoded_auth}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(api_url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('access_token')
        else:
            logger.error(f"Failed to get M-Pesa access token: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting M-Pesa access token: {str(e)}")
        return None

def create_mpesa_payment(payment, phone_number):
    """
    Initiate M-Pesa STK push payment using Daraja API
    Returns dict with success status and message/checkout_request_id
    """
    try:
        # Get access token
        access_token = get_mpesa_access_token()
        if not access_token:
            return {
                'success': False,
                'message': 'Failed to authenticate with M-Pesa API'
            }
        
        # Generate timestamp and password
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        shortcode = settings.MPESA_SHORTCODE
        passkey = settings.MPESA_PASSKEY
        
        if not shortcode or not passkey:
            return {
                'success': False,
                'message': 'M-Pesa configuration incomplete'
            }
        
        # Generate password
        password_string = f"{shortcode}{passkey}{timestamp}"
        password = base64.b64encode(password_string.encode()).decode()
        
        # STK Push endpoint
        api_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest" if settings.MPESA_ENVIRONMENT == 'sandbox' else "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
        
        # Format phone number (ensure it starts with 254)
        if phone_number.startswith('0'):
            phone_number = '254' + phone_number[1:]
        elif phone_number.startswith('+254'):
            phone_number = phone_number[1:]
        elif not phone_number.startswith('254'):
            phone_number = '254' + phone_number
        
        # Prepare callback URL - Safaricom doesn't allow query parameters in callback URL
        callback_url = settings.MPESA_CALLBACK_URL
        
        # Get subscription and plan data from default database to avoid tenant database issues
        from .models import Subscription, SubscriptionPlan
        subscription = Subscription.objects.using('default').filter(id=payment.subscription_id).first()
        if subscription and subscription.plan_id:
            plan = SubscriptionPlan.objects.using('default').filter(id=subscription.plan_id).first()
            plan_name = plan.name if plan else "Subscription Plan"
        else:
            plan_name = "Subscription Plan"
        
        # Request payload
        payload = {
            "BusinessShortCode": shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(payment.amount),  # M-Pesa expects integer
            "PartyA": phone_number,
            "PartyB": shortcode,
            "PhoneNumber": phone_number,
            "CallBackURL": callback_url,
            "AccountReference": f"SUB-{payment.subscription_id}",
            "TransactionDesc": f"Subscription payment for {plan_name}"
        }
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Make STK push request
        response = requests.post(api_url, json=payload, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('ResponseCode') == '0':
                checkout_request_id = data.get('CheckoutRequestID')
                return {
                    'success': True,
                    'checkout_request_id': checkout_request_id,
                    'message': 'Payment request sent to your phone'
                }
            else:
                return {
                    'success': False,
                    'message': data.get('errorMessage', 'Failed to initiate payment')
                }
        else:
            logger.error(f"M-Pesa STK Push failed: {response.status_code} - {response.text}")
            return {
                'success': False,
                'message': 'Payment service temporarily unavailable'
            }
        
    except Exception as e:
        logger.error(f"Error creating M-Pesa payment: {str(e)}")
        return {
            'success': False,
            'message': 'Payment processing error occurred'
        }

def process_mpesa_callback(callback_data):
    """
    Process M-Pesa callback response
    Returns dict with success status and payment details
    """
    try:
        # Extract data from callback
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
                    payment_details['mpesa_receipt'] = value
                elif name == 'TransactionDate':
                    payment_details['transaction_date'] = value
                elif name == 'PhoneNumber':
                    payment_details['phone_number'] = value
            
            return {
                'success': True,
                'checkout_request_id': checkout_request_id,
                'payment_details': payment_details
            }
        else:
            # Payment failed
            result_desc = stk_callback.get('ResultDesc', 'Payment failed')
            return {
                'success': False,
                'checkout_request_id': checkout_request_id,
                'message': result_desc
            }
            
    except Exception as e:
        logger.error(f"Error processing M-Pesa callback: {str(e)}")
        return {
            'success': False,
            'message': 'Callback processing error'
        }

def verify_discount_code(code, plan, amount):
    """
    Verify if a discount code is valid for the given plan and amount
    Returns the SubscriptionDiscount object if valid, None otherwise
    """
    try:
        discount = SubscriptionDiscount.objects.get(
            code=code,
            is_active=True,
            valid_from__lte=timezone.now(),
            valid_to__gte=timezone.now()
        )
        
        # Check if discount applies to this plan
        if discount.applies_to_all or discount.plans.filter(id=plan.id).exists():
            # Check minimum amount requirement if any
            if discount.minimum_amount and amount < discount.minimum_amount:
                return None
                
            return discount
            
    except SubscriptionDiscount.DoesNotExist:
        pass
        
    return None