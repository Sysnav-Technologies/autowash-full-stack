# subscriptions/utils.py
import requests
from django.conf import settings
from django.utils import timezone
from .models import SubscriptionDiscount
from datetime import datetime

def create_mpesa_payment(payment, phone_number):
    """
    Initiate M-Pesa STK push payment
    Returns dict with success status and message/checkout_request_id
    """
    # Example implementation - replace with actual M-Pesa API integration
    try:
        # This is a mock implementation - replace with actual API calls to M-Pesa
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        
        # In a real implementation, you would:
        # 1. Generate authentication token
        # 2. Make STK push request
        # 3. Handle the response
        
        # Mock response for demonstration
        return {
            'success': True,
            'checkout_request_id': f'ws_CO_{timestamp}_{payment.id}',
            'message': 'Payment request sent to your phone'
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': str(e)
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