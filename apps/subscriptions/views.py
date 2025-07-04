from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from decimal import Decimal
import json
import uuid
from datetime import datetime, timedelta
from .models import (
    SubscriptionPlan, Subscription, Payment, SubscriptionUsage,
    SubscriptionDiscount, SubscriptionInvoice
)
from .forms import SubscriptionForm, PaymentForm
from .utils import create_mpesa_payment, verify_discount_code
from apps.accounts.models import Business

def pricing_view(request):
    """Display subscription plans"""
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('sort_order', 'monthly_price')
    
    # Calculate savings for annual billing
    for plan in plans:
        if plan.annual_price:
            monthly_total = plan.monthly_price * 12
            savings = monthly_total - plan.annual_price
            plan.annual_savings = round((savings / monthly_total) * 100, 1) if monthly_total > 0 else 0
        else:
            plan.annual_savings = 0
    
    context = {
        'plans': plans,
        'user_has_subscription': False
    }
    
    # Check if user has active subscription
    if request.user.is_authenticated:
        try:
            business = Business.objects.get(owner=request.user)
            if business.subscription and business.subscription.is_active:
                context['user_has_subscription'] = True
                context['current_subscription'] = business.subscription
        except Business.DoesNotExist:
            pass
    
    return render(request, 'subscriptions/pricing.html', context)

@login_required
def subscribe_view(request, plan_slug):
    """Subscribe to a plan"""
    plan = get_object_or_404(SubscriptionPlan, slug=plan_slug, is_active=True)
    
    # Check if user has a business
    try:
        business = Business.objects.get(owner=request.user)
    except Business.DoesNotExist:
        messages.error(request, "You need to register a business first.")
        return redirect('accounts:business_register')
    
    # Check if business already has active subscription
    if business.subscription and business.subscription.is_active:
        messages.warning(request, "You already have an active subscription.")
        return redirect('subscriptions:manage_subscription')
    
    if request.method == 'POST':
        form = SubscriptionForm(request.POST)
        if form.is_valid():
            billing_cycle = form.cleaned_data['billing_cycle']
            discount_code = form.cleaned_data.get('discount_code')
            
            # Calculate pricing
            amount = plan.get_price_for_cycle(billing_cycle)
            discount_amount = Decimal('0.00')
            
            # Apply discount if provided
            discount = None
            if discount_code:
                discount = verify_discount_code(discount_code, plan, amount)
                if discount:
                    discount_amount = discount.calculate_discount(amount)
                else:
                    messages.error(request, "Invalid or expired discount code.")
                    return render(request, 'subscriptions/subscribe.html', {
                        'plan': plan, 'form': form
                    })
            
            final_amount = amount - discount_amount
            
            # Create subscription
            subscription = Subscription.objects.create(
                plan=plan,
                billing_cycle=billing_cycle,
                start_date=timezone.now(),
                end_date=timezone.now() + timedelta(days=plan.trial_days),
                trial_end_date=timezone.now() + timedelta(days=plan.trial_days),
                status='trial',
                amount=final_amount
            )
            
            # Update business
            business.subscription = subscription
            business.max_employees = plan.max_employees
            business.max_customers = plan.max_customers
            business.save()
            
            # Create usage tracking
            SubscriptionUsage.objects.create(subscription=subscription)
            
            # If there's a payment required (not free trial)
            if final_amount > 0:
                payment = Payment.objects.create(
                    subscription=subscription,
                    amount=final_amount,
                    payment_method='mpesa',  # Default to M-Pesa
                    status='pending'
                )
                
                # Create invoice
                invoice = SubscriptionInvoice.objects.create(
                    subscription=subscription,
                    payment=payment,
                    subtotal=amount,
                    discount_amount=discount_amount,
                    total_amount=final_amount,
                    due_date=timezone.now().date() + timedelta(days=7),
                    discount_code=discount
                )
                
                # Use discount code
                if discount:
                    discount.use_discount()
                
                return redirect('subscriptions:payment', payment_id=payment.payment_id)
            else:
                messages.success(request, f"Welcome to {plan.name}! Your {plan.trial_days}-day trial has started.")
                return redirect('accounts:dashboard_redirect')
    else:
        form = SubscriptionForm()
    
    context = {
        'plan': plan,
        'form': form,
        'business': business
    }
    
    return render(request, 'subscriptions/subscribe.html', context)

@login_required
def payment_view(request, payment_id):
    """Handle payment for subscription"""
    payment = get_object_or_404(Payment, payment_id=payment_id, status='pending')
    
    # Ensure the payment belongs to user's business
    try:
        business = Business.objects.get(owner=request.user, subscription=payment.subscription)
    except Business.DoesNotExist:
        messages.error(request, "Payment not found.")
        return redirect('subscriptions:pricing')
    
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment_method = form.cleaned_data['payment_method']
            phone_number = form.cleaned_data.get('phone_number')
            
            payment.payment_method = payment_method
            payment.save()
            
            if payment_method == 'mpesa':
                # Initiate M-Pesa payment
                result = create_mpesa_payment(payment, phone_number)
                if result['success']:
                    payment.status = 'processing'
                    payment.transaction_id = result['checkout_request_id']
                    payment.save()
                    
                    messages.success(request, "Payment request sent to your phone. Please complete the payment.")
                    return redirect('subscriptions:payment_status', payment_id=payment.payment_id)
                else:
                    messages.error(request, f"Payment failed: {result['message']}")
            
            elif payment_method == 'bank_transfer':
                # For bank transfer, mark as pending and send instructions
                messages.info(request, "Bank transfer instructions have been sent to your email.")
                # Send email with bank details
                send_payment_instructions_email(business.owner.email, payment)
                return redirect('subscriptions:payment_status', payment_id=payment.payment_id)
    else:
        form = PaymentForm()
    
    context = {
        'payment': payment,
        'form': form,
        'business': business
    }
    
    return render(request, 'subscriptions/payment.html', context)

@login_required
def payment_status_view(request, payment_id):
    """Check payment status"""
    payment = get_object_or_404(Payment, payment_id=payment_id)
    
    # Ensure the payment belongs to user's business
    try:
        business = Business.objects.get(owner=request.user, subscription=payment.subscription)
    except Business.DoesNotExist:
        messages.error(request, "Payment not found.")
        return redirect('subscriptions:pricing')
    
    context = {
        'payment': payment,
        'business': business
    }
    
    return render(request, 'subscriptions/payment_status.html', context)

@login_required
def manage_subscription_view(request):
    """Manage current subscription"""
    try:
        business = Business.objects.get(owner=request.user)
        subscription = business.subscription
    except (Business.DoesNotExist, AttributeError):
        messages.error(request, "No active subscription found.")
        return redirect('subscriptions:pricing')
    
    if not subscription:
        return redirect('subscriptions:pricing')
    
    # Get subscription usage
    usage = getattr(subscription, 'usage', None)
    if not usage:
        usage = SubscriptionUsage.objects.create(subscription=subscription)
    
    # Get recent payments
    recent_payments = subscription.payments.order_by('-created_at')[:5]
    
    # Get invoices
    invoices = subscription.invoices.order_by('-created_at')[:10]
    
    context = {
        'business': business,
        'subscription': subscription,
        'usage': usage,
        'recent_payments': recent_payments,
        'invoices': invoices,
        'can_upgrade': True,  # Logic for upgrade availability
        'available_plans': SubscriptionPlan.objects.filter(is_active=True).exclude(id=subscription.plan.id)
    }
    
    return render(request, 'subscriptions/manage.html', context)

@login_required
@require_POST
def cancel_subscription_view(request):
    """Cancel subscription"""
    try:
        business = Business.objects.get(owner=request.user)
        subscription = business.subscription
    except (Business.DoesNotExist, AttributeError):
        return JsonResponse({'success': False, 'message': 'No subscription found'})
    
    if not subscription or not subscription.is_active:
        return JsonResponse({'success': False, 'message': 'No active subscription'})
    
    reason = request.POST.get('reason', '')
    subscription.cancel_subscription(reason)
    
    # Send cancellation email
    send_cancellation_email(business.owner.email, subscription)
    
    return JsonResponse({'success': True, 'message': 'Subscription cancelled successfully'})

@login_required
def upgrade_subscription_view(request, plan_slug):
    """Upgrade to a different plan"""
    new_plan = get_object_or_404(SubscriptionPlan, slug=plan_slug, is_active=True)
    
    try:
        business = Business.objects.get(owner=request.user)
        current_subscription = business.subscription
    except (Business.DoesNotExist, AttributeError):
        messages.error(request, "No current subscription found.")
        return redirect('subscriptions:pricing')
    
    if not current_subscription or not current_subscription.is_active:
        messages.error(request, "No active subscription to upgrade.")
        return redirect('subscriptions:pricing')
    
    # Calculate prorated amount
    days_remaining = current_subscription.days_remaining
    current_daily_rate = current_subscription.amount / 30  # Approximate
    new_monthly_rate = new_plan.monthly_price
    new_daily_rate = new_monthly_rate / 30
    
    prorated_credit = current_daily_rate * days_remaining
    upgrade_cost = (new_daily_rate * days_remaining) - prorated_credit
    
    if request.method == 'POST':
        if upgrade_cost > 0:
            # Create payment for upgrade
            payment = Payment.objects.create(
                subscription=current_subscription,
                amount=upgrade_cost,
                payment_method='mpesa',
                status='pending'
            )
            return redirect('subscriptions:payment', payment_id=payment.payment_id)
        else:
            # Immediate upgrade (downgrade or equal cost)
            current_subscription.plan = new_plan
            current_subscription.save()
            
            # Update business limits
            business.max_employees = new_plan.max_employees
            business.max_customers = new_plan.max_customers
            business.save()
            
            messages.success(request, f"Successfully upgraded to {new_plan.name}!")
            return redirect('subscriptions:manage_subscription')
    
    context = {
        'current_subscription': current_subscription,
        'new_plan': new_plan,
        'upgrade_cost': max(0, upgrade_cost),
        'prorated_credit': prorated_credit,
        'is_upgrade': new_plan.monthly_price > current_subscription.plan.monthly_price
    }
    
    return render(request, 'subscriptions/upgrade.html', context)

@csrf_exempt
def mpesa_callback_view(request):
    """Handle M-Pesa payment callbacks"""
    if request.method == 'POST':
        try:
            callback_data = json.loads(request.body)
            
            # Extract transaction details from callback
            checkout_request_id = callback_data.get('Body', {}).get('stkCallback', {}).get('CheckoutRequestID')
            result_code = callback_data.get('Body', {}).get('stkCallback', {}).get('ResultCode')
            
            if checkout_request_id:
                try:
                    payment = Payment.objects.get(transaction_id=checkout_request_id)
                    
                    if result_code == 0:  # Success
                        # Extract transaction details
                        callback_metadata = callback_data.get('Body', {}).get('stkCallback', {}).get('CallbackMetadata', {}).get('Item', [])
                        mpesa_receipt_number = None
                        
                        for item in callback_metadata:
                            if item.get('Name') == 'MpesaReceiptNumber':
                                mpesa_receipt_number = item.get('Value')
                                break
                        
                        payment.mark_as_completed(
                            transaction_id=mpesa_receipt_number or checkout_request_id,
                            notes="M-Pesa payment completed"
                        )
                        
                        # Send success email
                        send_payment_success_email(payment)
                        
                    else:
                        # Payment failed
                        result_desc = callback_data.get('Body', {}).get('stkCallback', {}).get('ResultDesc', 'Payment failed')
                        payment.mark_as_failed(result_desc)
                        
                except Payment.DoesNotExist:
                    pass
                    
        except json.JSONDecodeError:
            pass
    
    return HttpResponse('OK')

def check_discount_code_view(request):
    """AJAX endpoint to verify discount codes"""
    if request.method == 'GET':
        code = request.GET.get('code')
        plan_id = request.GET.get('plan_id')
        
        if not code or not plan_id:
            return JsonResponse({'valid': False, 'message': 'Missing parameters'})
        
        try:
            plan = SubscriptionPlan.objects.get(id=plan_id)
            discount = verify_discount_code(code, plan, plan.monthly_price)
            
            if discount:
                discount_amount = discount.calculate_discount(plan.monthly_price)
                return JsonResponse({
                    'valid': True,
                    'discount_amount': float(discount_amount),
                    'discount_percentage': discount.discount_value if discount.discount_type == 'percentage' else 0,
                    'message': f"Discount applied: {discount.name}"
                })
            else:
                return JsonResponse({'valid': False, 'message': 'Invalid or expired discount code'})
                
        except SubscriptionPlan.DoesNotExist:
            return JsonResponse({'valid': False, 'message': 'Plan not found'})
    
    return JsonResponse({'valid': False, 'message': 'Invalid request'})

@login_required
def download_invoice_view(request, invoice_id):
    """Download invoice PDF"""
    invoice = get_object_or_404(SubscriptionInvoice, id=invoice_id)
    
    # Ensure invoice belongs to user's business
    try:
        business = Business.objects.get(owner=request.user, subscription=invoice.subscription)
    except Business.DoesNotExist:
        messages.error(request, "Invoice not found.")
        return redirect('subscriptions:manage_subscription')
    
    # Generate PDF (you'll need to implement PDF generation)
    # For now, return a simple HTML view
    context = {
        'invoice': invoice,
        'business': business
    }
    
    return render(request, 'subscriptions/invoice_pdf.html', context)

# Utility functions
def send_payment_instructions_email(email, payment):
    """Send bank transfer instructions"""
    subject = f"Payment Instructions - Invoice #{payment.subscription.invoices.first().invoice_number}"
    context = {
        'payment': payment,
        'bank_details': {
            'bank_name': 'Example Bank',
            'account_number': '1234567890',
            'account_name': 'Autowash Technologies',
            'reference': str(payment.payment_id)
        }
    }
    
    html_message = render_to_string('subscriptions/emails/payment_instructions.html', context)
    
    send_mail(
        subject=subject,
        message='',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        html_message=html_message
    )

def send_payment_success_email(payment):
    """Send payment success notification"""
    business = Business.objects.get(subscription=payment.subscription)
    
    subject = "Payment Successful - Subscription Activated"
    context = {
        'payment': payment,
        'business': business,
        'subscription': payment.subscription
    }
    
    html_message = render_to_string('subscriptions/emails/payment_success.html', context)
    
    send_mail(
        subject=subject,
        message='',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[business.owner.email],
        html_message=html_message
    )

def send_cancellation_email(email, subscription):
    """Send subscription cancellation confirmation"""
    subject = "Subscription Cancelled"
    context = {
        'subscription': subscription
    }
    
    html_message = render_to_string('subscriptions/emails/cancellation.html', context)
    
    send_mail(
        subject=subject,
        message='',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        html_message=html_message
    )