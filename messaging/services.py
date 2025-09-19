"""
SMS Services for different providers
"""
import requests
import json
from django.conf import settings
from django.utils import timezone
from .models import SMSMessage, TenantSMSSettings
import logging

logger = logging.getLogger(__name__)


class BaseSMSService:
    """Base SMS service class"""
    
    def __init__(self, tenant_settings):
        self.tenant_settings = tenant_settings
        self.credentials = tenant_settings.get_credentials()
    
    def send_sms(self, recipient, message, sender_id=None):
        """Send SMS - to be implemented by subclasses"""
        raise NotImplementedError
    
    def get_delivery_status(self, message_id):
        """Get delivery status - to be implemented by subclasses"""
        raise NotImplementedError
    
    def calculate_sms_count(self, message):
        """Calculate number of SMS parts"""
        # Basic calculation - 160 chars per SMS
        return max(1, len(message) // 160 + (1 if len(message) % 160 > 0 else 0))


class HostPinnacleSMSService(BaseSMSService):
    """Host Pinnacle SMS service"""
    
    def __init__(self, tenant_settings):
        super().__init__(tenant_settings)
        self.api_url = "https://api.hostpinnacle.co.ke/v1/sms/send"
        self.status_url = "https://api.hostpinnacle.co.ke/v1/sms/status"
    
    def send_sms(self, recipient, message, sender_id=None):
        """Send SMS via Host Pinnacle"""
        try:
            # Prepare payload
            payload = {
                "instance_id": self.credentials.get('instance_id'),
                "access_token": self.credentials.get('access_token'),
                "recipient": recipient,
                "message": message
            }
            
            if sender_id:
                payload['sender_id'] = sender_id
            
            # Create SMS message record
            sms_message = SMSMessage.objects.create(
                tenant_settings=self.tenant_settings,
                recipient=recipient,
                message=message,
                sender_id=sender_id or '',
                status='pending',
                sms_count=self.calculate_sms_count(message),
                cost=self.tenant_settings.provider.rate_per_sms * self.calculate_sms_count(message)
            )
            
            # Send request
            response = requests.post(
                self.api_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            response_data = response.json()
            
            # Update message record
            sms_message.provider_response = response_data
            
            if response.status_code == 200 and response_data.get('status') == 'success':
                sms_message.status = 'sent'
                sms_message.provider_message_id = response_data.get('message_id', '')
                sms_message.sent_at = timezone.now()
                
                # Update usage counters
                self.tenant_settings.daily_usage += 1
                self.tenant_settings.monthly_usage += 1
                self.tenant_settings.save()
                
                logger.info(f"SMS sent successfully via Host Pinnacle: {sms_message.id}")
                
            else:
                sms_message.status = 'failed'
                sms_message.error_message = response_data.get('message', 'Unknown error')
                logger.error(f"Failed to send SMS via Host Pinnacle: {response_data}")
            
            sms_message.save()
            return sms_message
            
        except requests.RequestException as e:
            logger.error(f"Host Pinnacle API error: {str(e)}")
            sms_message.status = 'failed'
            sms_message.error_message = f"API error: {str(e)}"
            sms_message.save()
            return sms_message
        
        except Exception as e:
            logger.error(f"Unexpected error sending SMS: {str(e)}")
            if 'sms_message' in locals():
                sms_message.status = 'failed'
                sms_message.error_message = f"Unexpected error: {str(e)}"
                sms_message.save()
                return sms_message
            return None
    
    def get_delivery_status(self, message_id):
        """Get delivery status from Host Pinnacle"""
        try:
            payload = {
                "instance_id": self.credentials.get('instance_id'),
                "access_token": self.credentials.get('access_token'),
                "message_id": message_id
            }
            
            response = requests.post(
                self.status_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            
        except Exception as e:
            logger.error(f"Error getting delivery status: {str(e)}")
        
        return None


class AfricasTalkingSMSService(BaseSMSService):
    """Africa's Talking SMS service"""
    
    def __init__(self, tenant_settings):
        super().__init__(tenant_settings)
        self.api_url = "https://api.africastalking.com/version1/messaging"
    
    def send_sms(self, recipient, message, sender_id=None):
        """Send SMS via Africa's Talking"""
        try:
            # Prepare headers and payload
            headers = {
                'apiKey': self.credentials.get('api_key'),
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            payload = {
                'username': self.credentials.get('username'),
                'to': recipient,
                'message': message
            }
            
            if sender_id:
                payload['from'] = sender_id
            elif self.credentials.get('sender_id'):
                payload['from'] = self.credentials.get('sender_id')
            
            # Create SMS message record
            sms_message = SMSMessage.objects.create(
                tenant_settings=self.tenant_settings,
                recipient=recipient,
                message=message,
                sender_id=sender_id or self.credentials.get('sender_id', ''),
                status='pending',
                sms_count=self.calculate_sms_count(message),
                cost=self.tenant_settings.provider.rate_per_sms * self.calculate_sms_count(message)
            )
            
            # Send request
            response = requests.post(
                self.api_url,
                data=payload,
                headers=headers,
                timeout=30
            )
            
            response_data = response.json()
            
            # Update message record
            sms_message.provider_response = response_data
            
            if response.status_code == 201:
                recipients = response_data.get('SMSMessageData', {}).get('Recipients', [])
                if recipients and recipients[0].get('status') == 'Success':
                    sms_message.status = 'sent'
                    sms_message.provider_message_id = recipients[0].get('messageId', '')
                    sms_message.sent_at = timezone.now()
                    
                    # Update usage counters
                    self.tenant_settings.daily_usage += 1
                    self.tenant_settings.monthly_usage += 1
                    self.tenant_settings.save()
                    
                    logger.info(f"SMS sent successfully via Africa's Talking: {sms_message.id}")
                else:
                    sms_message.status = 'failed'
                    sms_message.error_message = recipients[0].get('status', 'Unknown error') if recipients else 'No recipients data'
            else:
                sms_message.status = 'failed'
                sms_message.error_message = f"API error: {response.status_code}"
            
            sms_message.save()
            return sms_message
            
        except Exception as e:
            logger.error(f"Africa's Talking error: {str(e)}")
            if 'sms_message' in locals():
                sms_message.status = 'failed'
                sms_message.error_message = f"Error: {str(e)}"
                sms_message.save()
                return sms_message
            return None


class TwilioSMSService(BaseSMSService):
    """Twilio SMS service"""
    
    def __init__(self, tenant_settings):
        super().__init__(tenant_settings)
        try:
            from twilio.rest import Client
            self.client = Client(
                self.credentials.get('account_sid'),
                self.credentials.get('auth_token')
            )
        except ImportError:
            logger.error("Twilio library not installed. Run: pip install twilio")
            self.client = None
    
    def send_sms(self, recipient, message, sender_id=None):
        """Send SMS via Twilio"""
        if not self.client:
            return None
        
        try:
            # Create SMS message record
            sms_message = SMSMessage.objects.create(
                tenant_settings=self.tenant_settings,
                recipient=recipient,
                message=message,
                sender_id=sender_id or self.credentials.get('phone_number', ''),
                status='pending',
                sms_count=self.calculate_sms_count(message),
                cost=self.tenant_settings.provider.rate_per_sms * self.calculate_sms_count(message)
            )
            
            # Send via Twilio
            twilio_message = self.client.messages.create(
                body=message,
                from_=sender_id or self.credentials.get('phone_number'),
                to=recipient
            )
            
            # Update message record
            sms_message.provider_message_id = twilio_message.sid
            sms_message.status = 'sent'
            sms_message.sent_at = timezone.now()
            sms_message.provider_response = {
                'sid': twilio_message.sid,
                'status': twilio_message.status,
                'price': str(twilio_message.price) if twilio_message.price else None
            }
            
            # Update usage counters
            self.tenant_settings.daily_usage += 1
            self.tenant_settings.monthly_usage += 1
            self.tenant_settings.save()
            
            sms_message.save()
            logger.info(f"SMS sent successfully via Twilio: {sms_message.id}")
            return sms_message
            
        except Exception as e:
            logger.error(f"Twilio error: {str(e)}")
            if 'sms_message' in locals():
                sms_message.status = 'failed'
                sms_message.error_message = f"Twilio error: {str(e)}"
                sms_message.save()
                return sms_message
            return None


class AutowashDefaultSMSService(BaseSMSService):
    """Default Autowash SMS service (uses configured default provider)"""
    
    def send_sms(self, recipient, message, sender_id=None):
        """Send SMS via default Autowash provider"""
        # This would integrate with your default SMS provider
        # For now, create a pending message that can be processed by admin
        
        sms_message = SMSMessage.objects.create(
            tenant_settings=self.tenant_settings,
            recipient=recipient,
            message=message,
            sender_id=sender_id or 'AUTOWASH',
            status='queued',  # Will be processed by admin system
            sms_count=self.calculate_sms_count(message),
            cost=self.tenant_settings.provider.rate_per_sms * self.calculate_sms_count(message),
            message_type='tenant_default'
        )
        
        logger.info(f"SMS queued for admin processing: {sms_message.id}")
        return sms_message


def get_sms_service(tenant_settings):
    """Factory function to get appropriate SMS service"""
    provider_type = tenant_settings.provider.provider_type
    
    if provider_type == 'host_pinnacle':
        return HostPinnacleSMSService(tenant_settings)
    elif provider_type == 'africas_talking':
        return AfricasTalkingSMSService(tenant_settings)
    elif provider_type == 'twilio':
        return TwilioSMSService(tenant_settings)
    elif provider_type == 'default':
        return AutowashDefaultSMSService(tenant_settings)
    else:
        raise ValueError(f"Unknown SMS provider: {provider_type}")


def send_sms(tenant_id, recipient, message, sender_id=None, message_type='general'):
    """
    Main function to send SMS
    
    Args:
        tenant_id (str): UUID of the tenant
        recipient (str): Phone number with country code
        message (str): SMS message content
        sender_id (str, optional): Sender ID override
        message_type (str): Type of message for categorization
    
    Returns:
        SMSMessage: The created SMS message object
    """
    try:
        # Get tenant SMS settings
        tenant_settings = TenantSMSSettings.objects.get(tenant_id=tenant_id, is_active=True)
        
        # Check if tenant can send SMS
        if not tenant_settings.can_send_sms():
            logger.warning(f"Tenant {tenant_id} cannot send SMS (limits exceeded or not configured)")
            return None
        
        # Get appropriate service
        service = get_sms_service(tenant_settings)
        
        # Send SMS
        sms_message = service.send_sms(recipient, message, sender_id)
        
        if sms_message:
            sms_message.message_type = message_type
            sms_message.save()
        
        return sms_message
        
    except TenantSMSSettings.DoesNotExist:
        logger.error(f"No SMS settings found for tenant {tenant_id}")
        return None
    except Exception as e:
        logger.error(f"Error sending SMS for tenant {tenant_id}: {str(e)}")
        return None