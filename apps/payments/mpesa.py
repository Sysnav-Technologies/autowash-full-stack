import requests
import base64
import json
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from .models import Payment, MPesaTransaction, PaymentGateway
import logging
import hashlib
import hmac

logger = logging.getLogger(__name__)

class MPesaAPI:
    """M-Pesa Daraja API Integration"""
    
    def __init__(self):
        self.gateway = PaymentGateway.objects.filter(
            gateway_type='mpesa',
            is_active=True
        ).first()
        
        if not self.gateway:
            raise ValueError("M-Pesa gateway not configured")
        
        self.consumer_key = self.gateway.consumer_key
        self.consumer_secret = self.gateway.consumer_secret
        self.passkey = self.gateway.passkey
        self.shortcode = self.gateway.shortcode
        
        # URLs based on environment
        if self.gateway.is_live:
            self.base_url = "https://api.safaricom.co.ke"
        else:
            self.base_url = "https://sandbox.safaricom.co.ke"
        
        self.access_token = None
        self.token_expires_at = None
    
    def get_access_token(self):
        """Get OAuth access token with caching"""
        cache_key = f"mpesa_access_token_{self.gateway.id}"
        token_data = cache.get(cache_key)
        
        if token_data and token_data.get('expires_at') > timezone.now():
            return token_data['token']
        
        url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
        
        # Create authorization header
        auth_string = f"{self.consumer_key}:{self.consumer_secret}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        headers = {
            'Authorization': f'Basic {auth_b64}',
            'Content-Type': 'application/json',
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            access_token = data['access_token']
            expires_in = int(data.get('expires_in', 3600))
            
            # Cache token with expiry
            expires_at = timezone.now() + timedelta(seconds=expires_in - 60)
            cache.set(cache_key, {
                'token': access_token,
                'expires_at': expires_at
            }, expires_in - 60)
            
            return access_token
            
        except requests.RequestException as e:
            logger.error(f"Failed to get M-Pesa access token: {e}")
            raise Exception(f"M-Pesa authentication failed: {e}")
    
    def generate_password(self, timestamp=None):
        """Generate password for STK push"""
        if not timestamp:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        
        password_string = f"{self.shortcode}{self.passkey}{timestamp}"
        password_bytes = password_string.encode('ascii')
        return base64.b64encode(password_bytes).decode('ascii')
    
    def initiate_stk_push(self, phone_number, amount, account_reference, transaction_desc, callback_url):
        """Initiate STK Push payment request"""
        try:
            access_token = self.get_access_token()
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            password = self.generate_password(timestamp)
            
            # Format phone number
            phone_number = self.format_phone_number(phone_number)
            
            url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
            }
            
            payload = {
                'BusinessShortCode': self.shortcode,
                'Password': password,
                'Timestamp': timestamp,
                'TransactionType': 'CustomerPayBillOnline',
                'Amount': int(float(amount)),
                'PartyA': phone_number,
                'PartyB': self.shortcode,
                'PhoneNumber': phone_number,
                'CallBackURL': callback_url,
                'AccountReference': account_reference,
                'TransactionDesc': transaction_desc
            }
            
            logger.info(f"Initiating STK Push for {phone_number}, Amount: {amount}")
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"STK Push Response: {result}")
            
            return result
            
        except requests.RequestException as e:
            logger.error(f"STK Push failed: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response content: {e.response.text}")
            raise Exception(f"Failed to initiate M-Pesa payment: {e}")
    
    def query_transaction_status(self, checkout_request_id):
        """Query the status of an STK Push transaction"""
        try:
            access_token = self.get_access_token()
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            password = self.generate_password(timestamp)
            
            url = f"{self.base_url}/mpesa/stkpushquery/v1/query"
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
            }
            
            payload = {
                'BusinessShortCode': self.shortcode,
                'Password': password,
                'Timestamp': timestamp,
                'CheckoutRequestID': checkout_request_id
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"Transaction query failed: {e}")
            raise Exception(f"Failed to query transaction status: {e}")
    
    def c2b_register_urls(self, validation_url, confirmation_url):
        """Register C2B URLs for receiving payments"""
        try:
            access_token = self.get_access_token()
            
            url = f"{self.base_url}/mpesa/c2b/v1/registerurl"
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
            }
            
            payload = {
                'ShortCode': self.shortcode,
                'ResponseType': 'Completed',  # or 'Cancelled'
                'ConfirmationURL': confirmation_url,
                'ValidationURL': validation_url
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"C2B URL registration failed: {e}")
            raise Exception(f"Failed to register C2B URLs: {e}")
    
    def process_callback(self, callback_data):
        """Process M-Pesa callback response"""
        try:
            logger.info(f"Processing M-Pesa callback: {json.dumps(callback_data, indent=2)}")
            
            body = callback_data.get('Body', {})
            stk_callback = body.get('stkCallback', {})
            
            merchant_request_id = stk_callback.get('MerchantRequestID')
            checkout_request_id = stk_callback.get('CheckoutRequestID')
            result_code = stk_callback.get('ResultCode')
            result_desc = stk_callback.get('ResultDesc')
            
            if not checkout_request_id:
                logger.error("No CheckoutRequestID in callback")
                return False, "Invalid callback data"
            
            # Find the corresponding M-Pesa transaction
            try:
                mpesa_transaction = MPesaTransaction.objects.get(
                    checkout_request_id=checkout_request_id
                )
                payment = mpesa_transaction.payment
                
                # Update transaction details
                mpesa_transaction.result_code = str(result_code)
                mpesa_transaction.result_desc = result_desc
                mpesa_transaction.callback_data = callback_data
                
                if result_code == 0:  # Success
                    # Extract transaction details from callback
                    callback_metadata = stk_callback.get('CallbackMetadata', {})
                    items = callback_metadata.get('Item', [])
                    
                    for item in items:
                        name = item.get('Name')
                        value = item.get('Value')
                        
                        if name == 'MpesaReceiptNumber':
                            mpesa_transaction.mpesa_receipt_number = str(value)
                        elif name == 'TransactionDate':
                            # Convert timestamp to datetime
                            if value:
                                try:
                                    # M-Pesa timestamp is in format: 20191219203000
                                    if len(str(value)) == 14:
                                        mpesa_transaction.transaction_date = datetime.strptime(
                                            str(value), '%Y%m%d%H%M%S'
                                        )
                                    else:
                                        # Unix timestamp
                                        mpesa_transaction.transaction_date = datetime.fromtimestamp(
                                            int(value) / 1000 if int(value) > 9999999999 else int(value)
                                        )
                                except (ValueError, TypeError) as e:
                                    logger.warning(f"Could not parse transaction date {value}: {e}")
                        elif name == 'PhoneNumber':
                            mpesa_transaction.phone_number = str(value)
                    
                    mpesa_transaction.save()
                    
                    # Complete the payment
                    payment.complete_payment(
                        transaction_id=mpesa_transaction.mpesa_receipt_number,
                        user=None
                    )
                    
                    logger.info(f"M-Pesa payment completed: {payment.payment_id}")
                    
                else:  # Failed
                    mpesa_transaction.save()
                    
                    # Map M-Pesa error codes to user-friendly messages
                    error_messages = {
                        '1': 'Insufficient funds in M-Pesa account',
                        '1032': 'Payment cancelled by user',
                        '1037': 'Payment timeout - user did not enter PIN',
                        '2001': 'Invalid PIN entered',
                        '1001': 'Unable to lock subscriber - try again',
                        '1019': 'Transaction failed - please try again'
                    }
                    
                    failure_reason = error_messages.get(str(result_code), result_desc or 'Payment failed')
                    payment.fail_payment(failure_reason)
                    
                    logger.warning(f"M-Pesa payment failed: {payment.payment_id} - {failure_reason}")
                
                return True, "Callback processed successfully"
                
            except MPesaTransaction.DoesNotExist:
                logger.error(f"M-Pesa transaction not found: {checkout_request_id}")
                return False, "Transaction not found"
                
        except Exception as e:
            logger.error(f"Callback processing failed: {e}")
            return False, str(e)
    
    def format_phone_number(self, phone_number):
        """Format phone number for M-Pesa"""
        if not phone_number:
            return None
        
        # Remove any non-digit characters
        phone = ''.join(filter(str.isdigit, str(phone_number)))
        
        # Handle Kenyan numbers
        if phone.startswith('0'):
            phone = '254' + phone[1:]
        elif phone.startswith('7') or phone.startswith('1'):
            phone = '254' + phone
        elif not phone.startswith('254'):
            phone = '254' + phone
        
        return phone
    
    def validate_callback_signature(self, payload, signature):
        """Validate M-Pesa callback signature for security"""
        if not self.gateway.webhook_secret:
            return True  # Skip validation if no secret configured
        
        expected_signature = hmac.new(
            self.gateway.webhook_secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)

class MPesaService:
    """High-level M-Pesa service for payment processing"""
    
    def __init__(self):
        self.api = MPesaAPI()
    
    def create_payment_request(self, payment_id, phone_number, amount, description=None):
        """Create M-Pesa payment request"""
        try:
            payment = Payment.objects.get(payment_id=payment_id)
            
            # Validate amount limits
            if amount < 1:
                return False, "Minimum amount is KES 1"
            if amount > 150000:
                return False, "Maximum amount is KES 150,000"
            
            # Create M-Pesa transaction record
            mpesa_transaction = MPesaTransaction.objects.create(
                payment=payment,
                phone_number=self.api.format_phone_number(phone_number)
            )
            
            # Prepare callback URL
            callback_url = f"{settings.MPESA_CALLBACK_URL}?payment_id={payment_id}"
            
            # Initiate STK push
            response = self.api.initiate_stk_push(
                phone_number=phone_number,
                amount=amount,
                account_reference=payment.payment_id,
                transaction_desc=description or f"Payment for {payment.service_order.order_number if payment.service_order else 'service'}",
                callback_url=callback_url
            )
            
            # Check response
            if response.get('ResponseCode') == '0':
                # Update transaction with response details
                mpesa_transaction.merchant_request_id = response.get('MerchantRequestID')
                mpesa_transaction.checkout_request_id = response.get('CheckoutRequestID')
                mpesa_transaction.save()
                
                # Update payment status
                payment.status = 'processing'
                payment.transaction_id = mpesa_transaction.checkout_request_id
                payment.save()
                
                return True, {
                    'checkout_request_id': mpesa_transaction.checkout_request_id,
                    'merchant_request_id': mpesa_transaction.merchant_request_id,
                    'customer_message': response.get('CustomerMessage', 'Please check your phone and enter your M-Pesa PIN to complete the payment.')
                }
            else:
                error_msg = response.get('ResponseDescription', 'Failed to initiate payment')
                payment.fail_payment(error_msg)
                return False, error_msg
            
        except Payment.DoesNotExist:
            return False, "Payment not found"
        except Exception as e:
            logger.error(f"M-Pesa payment request failed: {e}")
            return False, str(e)
    
    def check_payment_status(self, payment_id):
        """Check M-Pesa payment status"""
        try:
            payment = Payment.objects.get(payment_id=payment_id)
            
            if not hasattr(payment, 'mpesa_details'):
                return False, "M-Pesa transaction details not found"
            
            mpesa_transaction = payment.mpesa_details
            
            if not mpesa_transaction.checkout_request_id:
                return False, "No checkout request ID found"
            
            # If we already have a result, return it
            if mpesa_transaction.result_code:
                if mpesa_transaction.result_code == '0':
                    if payment.status != 'completed':
                        payment.complete_payment(
                            transaction_id=mpesa_transaction.mpesa_receipt_number
                        )
                    return True, "Payment completed successfully"
                else:
                    return False, mpesa_transaction.result_desc or "Payment failed"
            
            # Query M-Pesa API for status
            response = self.api.query_transaction_status(
                mpesa_transaction.checkout_request_id
            )
            
            result_code = response.get('ResultCode')
            result_desc = response.get('ResultDesc')
            
            # Update transaction with query result
            mpesa_transaction.result_code = str(result_code)
            mpesa_transaction.result_desc = result_desc
            mpesa_transaction.save()
            
            if result_code == '0':
                # Payment successful
                if payment.status != 'completed':
                    payment.complete_payment()
                return True, "Payment completed successfully"
            elif result_code == '1032':
                # Payment cancelled by user
                payment.fail_payment("Payment cancelled by user")
                return False, "Payment was cancelled"
            elif result_code == '1':
                # Insufficient funds
                payment.fail_payment("Insufficient funds")
                return False, "Insufficient funds in M-Pesa account"
            elif result_code == '1037':
                # Timeout
                payment.fail_payment("Payment timeout")
                return False, "Payment timeout - please try again"
            else:
                # Other error
                payment.fail_payment(result_desc)
                return False, result_desc or "Payment failed"
            
        except Payment.DoesNotExist:
            return False, "Payment not found"
        except Exception as e:
            logger.error(f"Payment status check failed: {e}")
            return False, str(e)
    
    def process_webhook_callback(self, request_data):
        """Process M-Pesa webhook callback"""
        return self.api.process_callback(request_data)
    
    def register_callback_urls(self, validation_url, confirmation_url):
        """Register callback URLs with M-Pesa"""
        try:
            return self.api.c2b_register_urls(validation_url, confirmation_url)
        except Exception as e:
            logger.error(f"Failed to register callback URLs: {e}")
            return False

# Utility functions for M-Pesa integration

def validate_mpesa_phone(phone_number):
    """Validate if phone number is valid for M-Pesa"""
    if not phone_number:
        return False, "Phone number is required"
    
    # Remove any non-digit characters
    phone = ''.join(filter(str.isdigit, str(phone_number)))
    
    # Handle Kenyan numbers
    if phone.startswith('0'):
        phone = '254' + phone[1:]
    elif phone.startswith('7') or phone.startswith('1'):
        phone = '254' + phone
    elif not phone.startswith('254'):
        phone = '254' + phone
    
    # Check if it's a valid Kenyan mobile number
    valid_prefixes = [
        '254701', '254702', '254703', '254704', '254705', '254706', '254707', '254708', '254709',
        '254710', '254711', '254712', '254713', '254714', '254715', '254716', '254717', '254718', '254719',
        '254720', '254721', '254722', '254723', '254724', '254725', '254726', '254727', '254728', '254729',
        '254730', '254731', '254732', '254733', '254734', '254735', '254736', '254737', '254738', '254739',
        '254740', '254741', '254742', '254743', '254744', '254745', '254746', '254747', '254748', '254749',
        '254750', '254751', '254752', '254753', '254754', '254755', '254756', '254757', '254758', '254759',
        '254760', '254761', '254762', '254763', '254764', '254765', '254766', '254767', '254768', '254769'
    ]
    
    if not any(phone.startswith(prefix) for prefix in valid_prefixes):
        return False, "Phone number is not valid for M-Pesa"
    
    if len(phone) != 12:
        return False, "Phone number must be 12 digits"
    
    return True, phone

def format_phone_number(phone_number):
    """Format phone number for M-Pesa"""
    api = MPesaAPI()
    return api.format_phone_number(phone_number)

# Management command helpers

def setup_mpesa_gateway():
    """Setup M-Pesa gateway configuration"""
    gateway, created = PaymentGateway.objects.get_or_create(
        gateway_type='mpesa',
        defaults={
            'name': 'M-Pesa Daraja',
            'is_active': True,
            'is_live': getattr(settings, 'MPESA_ENVIRONMENT', 'sandbox') == 'production',
            'api_url': 'https://api.safaricom.co.ke' if getattr(settings, 'MPESA_ENVIRONMENT', 'sandbox') == 'production' else 'https://sandbox.safaricom.co.ke',
            'consumer_key': getattr(settings, 'MPESA_CONSUMER_KEY', ''),
            'consumer_secret': getattr(settings, 'MPESA_CONSUMER_SECRET', ''),
            'shortcode': getattr(settings, 'MPESA_SHORTCODE', ''),
            'passkey': getattr(settings, 'MPESA_PASSKEY', ''),
            'webhook_url': getattr(settings, 'MPESA_CALLBACK_URL', ''),
        }
    )
    
    if created:
        logger.info("M-Pesa gateway configuration created")
    else:
        logger.info("M-Pesa gateway configuration already exists")
    
    return gateway