from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from decimal import Decimal
import json
import uuid
import csv
import io
from datetime import datetime, timedelta
from .models import (
    SubscriptionPlan, Subscription, Payment, SubscriptionUsage,
    SubscriptionDiscount, SubscriptionInvoice
)
from .forms import SubscriptionForm, PaymentForm
from .utils import create_mpesa_payment, verify_discount_code
from apps.accounts.models import Business

def get_subscription_urls(request):
    """Generate all subscription URLs for templates with tenant slug."""
    tenant_slug = request.tenant.slug if hasattr(request, 'tenant') else None
    base_url = f"/business/{tenant_slug}/subscriptions" if tenant_slug else "/subscriptions"
    
    return {
        # Main URLs
        'pricing': "/pricing/",  # Public URL
        'current': f"{base_url}/current/",
        'upgrade': f"{base_url}/upgrade/",
        'downgrade': f"{base_url}/downgrade/",
        'cancel': f"{base_url}/cancel/",
        'reactivate': f"{base_url}/reactivate/",
        
        # Payment URLs
        'payment_create': f"{base_url}/payment/create/",
        'payment_success': f"{base_url}/payment/success/",
        'payment_failed': f"{base_url}/payment/failed/",
        'payment_callback': f"{base_url}/payment/callback/",
        
        # Plan URLs
        'plan_details': f"{base_url}/plans/{{}}/",
        'plan_compare': f"{base_url}/plans/compare/",
        
        # Invoice URLs
        'invoice_list': f"{base_url}/invoices/",
        'invoice_detail': f"{base_url}/invoices/{{}}/",
        'invoice_download': f"{base_url}/invoices/{{}}/download/",
        
        # Usage URLs
        'usage_dashboard': f"{base_url}/usage/",
        'usage_details': f"{base_url}/usage/details/",
        'usage_history': f"{base_url}/usage/history/",
        
        # Discount URLs
        'apply_discount': f"{base_url}/discount/apply/",
        'remove_discount': f"{base_url}/discount/remove/",
        
        # Ajax URLs
        'check_discount': f"{base_url}/ajax/discount/check/",
        'usage_stats': f"{base_url}/ajax/usage/stats/",
        'plan_pricing': f"{base_url}/ajax/plans/{{}}/pricing/",
        
        # Navigation
        'businesses_dashboard': f"/business/{tenant_slug}/dashboard/" if tenant_slug else "/dashboard/",
    }

def pricing_view(request):
    """Display subscription plans"""
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('sort_order', 'price')
    
    # Calculate savings for annual billing
    for plan in plans:
        if plan.duration_months >= 12:
            monthly_equivalent = plan.price / plan.duration_months
            # Simple savings calculation - this can be enhanced later
            plan.annual_savings = 0
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
def subscription_selection_view(request):
    """Subscription selection for new businesses after registration"""
    # Check if user has a business
    try:
        business = Business.objects.get(owner=request.user)
    except Business.DoesNotExist:
        messages.error(request, "You need to register a business first.")
        return redirect('accounts:business_register')
    
    # Check if business already has active subscription
    if business.subscription and business.subscription.is_active:
        # If user has active subscription and business is verified, go to dashboard
        if business.is_verified and business.is_approved:
            messages.success(request, "You already have an active subscription.")
            return redirect(f'/business/{business.slug}/')
        else:
            # If subscription is active but business not fully verified, go to verification
            messages.info(request, "Your subscription is active. Please wait for business verification to complete.")
            return redirect('/auth/verification-pending/')
    
    # Get available plans
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('sort_order', 'price')
    
    # Calculate savings for annual billing
    for plan in plans:
        if plan.duration_months >= 12:
            monthly_equivalent = plan.price / plan.duration_months
            monthly_total = monthly_equivalent * 12
            if plan.duration_months == 12:
                # This is an annual plan
                savings = 0  # No savings calculation needed for base annual price
            else:
                # Calculate potential savings compared to monthly equivalent
                savings = 0
            plan.annual_savings = savings
        else:
            plan.annual_savings = 0
    
    context = {
        'plans': plans,
        'business': business,
        'title': 'Choose Your Subscription Plan',
        'step': 'subscription'
    }
    
    return render(request, 'subscriptions/selection.html', context)

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
        # If user has active subscription and business is verified, go to subscription management
        if business.is_verified and business.is_approved:
            messages.info(request, "You already have an active subscription.")
            return redirect('subscriptions:manage_subscription')
        else:
            # If subscription is active but business not fully verified, go to verification
            messages.info(request, "Your subscription is active. Please wait for business verification to complete.")
            return redirect('/auth/verification-pending/')
    
    if request.method == 'POST':
        form = SubscriptionForm(request.POST, plan=plan)
        if form.is_valid():
            billing_cycle = form.cleaned_data['billing_cycle']
            discount_code = form.cleaned_data.get('discount_code')
            
            # Use plan's base price
            amount = plan.price
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
                        'plan': plan, 'form': form, 'business': business
                    })
            
            final_amount = amount - discount_amount
            
            # For now, create subscription without payment requirement
            # Calculate end date based on plan duration
            if plan.duration_months:
                end_date = timezone.now() + timedelta(days=plan.duration_months * 30)
            else:
                end_date = timezone.now() + timedelta(days=30)  # Default 1 month
            
            # Create subscription
            subscription = Subscription.objects.create(
                plan=plan,
                business=business,  # Use the business object (which is a Tenant)
                start_date=timezone.now(),
                end_date=end_date,
                trial_end_date=timezone.now() + timedelta(days=7),  # 7-day trial
                status='trial',  # Start with trial
                amount=final_amount
            )
            
            # Update business
            business.subscription = subscription
            business.max_employees = plan.max_employees
            business.max_customers = plan.max_customers
            business.save()
            
            # Create usage tracking
            SubscriptionUsage.objects.create(subscription=subscription)
            
            # Send business registration email after subscription selection
            try:
                from apps.accounts.views import send_business_registration_email
                send_business_registration_email(request, business)
            except Exception as e:
                print(f"Failed to send business registration email: {e}")
            
            # Skip payment for now - directly proceed to verification
            messages.success(request, f"Welcome to {plan.name}! Your 7-day trial has started. Please complete verification to activate your account.")
            return redirect('/auth/verification-pending/')
        else:
            # Form has errors - display them
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = SubscriptionForm(plan=plan)
    
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
    new_monthly_rate = new_plan.price
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
        'is_upgrade': new_plan.price > current_subscription.plan.price
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
            discount = verify_discount_code(code, plan, plan.price)
            
            if discount:
                discount_amount = discount.calculate_discount(plan.price)
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


# Business Owner Subscription Management Views
@login_required
def subscription_overview(request):
    """Subscription overview and status."""
    try:
        # Get current subscription for the business
        business = getattr(request, 'tenant', None) or getattr(request, 'business', None)
        if not business:
            messages.error(request, 'Business context not found.')
            return redirect('/')
        
        # Use default database for subscription queries since subscriptions are in SHARED_APPS
        subscription = Subscription.objects.using('default').filter(
            business=business
        ).select_related('plan').first()
        
        # Get available plans
        available_plans = SubscriptionPlan.objects.using('default').filter(is_active=True)
        
        # Calculate usage statistics
        current_date = timezone.now()
        month_start = current_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Get usage metrics (these would come from your actual usage tracking)
        usage_stats = {
            'orders_this_month': 0,  # Replace with actual count
            'customers_count': 0,    # Replace with actual count
            'storage_used': 0,       # Replace with actual calculation
            'api_calls': 0,          # Replace with actual count
        }
        
        context = {
            'subscription': subscription,
            'available_plans': available_plans,
            'usage_stats': usage_stats,
            'current_date': current_date,
            'days_until_renewal': (subscription.end_date - current_date).days if subscription and subscription.end_date else 0,
        }
        
        return render(request, 'businesses/subscription/overview.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading subscription overview: {str(e)}')
        return redirect('/')


@login_required
def billing_history(request):
    """Billing history and invoices."""
    try:
        business = getattr(request, 'tenant', None) or getattr(request, 'business', None)
        if not business:
            messages.error(request, 'Business context not found.')
            return redirect('/')
        
        # Get billing history
        invoices = SubscriptionInvoice.objects.using('default').filter(
            subscription__business=business
        ).select_related('subscription__plan').order_by('-created_at')
        
        # Pagination could be added here
        
        context = {
            'invoices': invoices,
        }
        
        return render(request, 'businesses/subscription/billing_history.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading billing history: {str(e)}')
        return redirect('subscriptions:subscription_overview')


@login_required
def payment_methods(request):
    """Manage payment methods."""
    try:
        business = getattr(request, 'tenant', None) or getattr(request, 'business', None)
        if not business:
            messages.error(request, 'Business context not found.')
            return redirect('/')
        
        # Get payment methods (you'll need to create this model)
        # payment_methods = PaymentMethod.objects.filter(
        #     business=business
        # ).order_by('-is_default', '-created_at')
        
        context = {
            'payment_methods': [],  # Replace with actual payment methods
        }
        
        return render(request, 'businesses/subscription/payment_methods.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading payment methods: {str(e)}')
        return redirect('subscriptions:subscription_overview')


@login_required
def usage_analytics(request):
    """Usage analytics and limits."""
    try:
        business = getattr(request, 'tenant', None) or getattr(request, 'business', None)
        if not business:
            messages.error(request, 'Business context not found.')
            return redirect('/')
        
        # Get current subscription
        subscription = Subscription.objects.using('default').filter(
            business=business
        ).select_related('plan').first()
        
        # Get usage metrics for the current month
        current_date = timezone.now()
        month_start = current_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        usage_metrics = SubscriptionUsage.objects.using('default').filter(
            subscription=subscription,
            created_at__gte=month_start
        ).order_by('-created_at') if subscription else []
        
        # Calculate totals and percentages
        usage_summary = {
            'orders': {
                'used': sum(getattr(metric, 'orders_count', 0) for metric in usage_metrics),
                'limit': subscription.plan.max_services if subscription else 1000,  # Using max_services as orders proxy
            },
            'customers': {
                'used': sum(getattr(metric, 'customers_count', 0) for metric in usage_metrics),
                'limit': subscription.plan.max_customers if subscription else 500,
            },
            'storage': {
                'used': sum(getattr(metric, 'storage_mb', 0) for metric in usage_metrics),
                'limit': subscription.plan.storage_limit if subscription else 1024,  # Using storage_limit
            },
            'api_calls': {
                'used': sum(getattr(metric, 'api_calls', 0) for metric in usage_metrics),
                'limit': subscription.plan.max_employees * 1000 if subscription else 10000,  # Using max_employees as API proxy
            },
        }
        
        # Calculate percentages
        for key, values in usage_summary.items():
            values['percentage'] = (values['used'] / values['limit']) * 100 if values['limit'] > 0 else 0
            values['percentage'] = min(values['percentage'], 100)  # Cap at 100%
        
        context = {
            'subscription': subscription,
            'usage_metrics': usage_metrics[:30],  # Last 30 days
            'usage_summary': usage_summary,
            'current_month': current_date.strftime('%B %Y'),
        }
        
        return render(request, 'businesses/subscription/usage_analytics.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading usage analytics: {str(e)}')
        return redirect('subscriptions:subscription_overview')


@login_required
def subscription_settings(request):
    """Subscription settings and preferences."""
    try:
        business = getattr(request, 'tenant', None) or getattr(request, 'business', None)
        if not business:
            messages.error(request, 'Business context not found.')
            return redirect('/')
        
        # Get current subscription
        subscription = Subscription.objects.using('default').filter(
            business=business
        ).select_related('plan').first()
        
        if request.method == 'POST':
            # Handle subscription settings updates
            auto_renewal = request.POST.get('auto_renewal') == 'on'
            billing_notifications = request.POST.get('billing_notifications') == 'on'
            usage_notifications = request.POST.get('usage_notifications') == 'on'
            
            if subscription:
                subscription.auto_renewal = auto_renewal
                # subscription.billing_notifications = billing_notifications
                # subscription.usage_notifications = usage_notifications
                subscription.save()
                
                messages.success(request, 'Subscription settings updated successfully!')
            else:
                messages.warning(request, 'No active subscription found.')
            
            return redirect('subscriptions:subscription_settings')
        
        context = {
            'subscription': subscription,
        }
        
        return render(request, 'businesses/subscription/settings.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading subscription settings: {str(e)}')
        return redirect('subscriptions:subscription_overview')


# AJAX endpoints for subscription functionality
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import datetime, timedelta
import json
import csv
import io

@login_required
@require_http_methods(["POST"])
def select_subscription_plan(request):
    """AJAX endpoint for plan selection"""
    try:
        plan_id = request.POST.get('plan_id')
        if not plan_id:
            return JsonResponse({'success': False, 'error': 'Plan ID required'})
        
        # Get the business
        business = get_object_or_404(Business, slug=request.tenant.slug)
        
        # Get the plan
        plan = get_object_or_404(SubscriptionPlan.objects.using('default'), id=plan_id)
        
        # Check if business already has a subscription
        existing_subscription = Subscription.objects.using('default').filter(
            business=business,
            status__in=['active', 'trialing']
        ).first()
        
        if existing_subscription:
            # Create upgrade/downgrade logic
            existing_subscription.plan = plan
            existing_subscription.save()
            return JsonResponse({
                'success': True, 
                'message': 'Plan updated successfully',
                'redirect_url': f'/business/{business.slug}/subscriptions/overview/'
            })
        else:
            # Create new subscription
            subscription = Subscription.objects.using('default').create(
                business=business,
                plan=plan,
                status='pending',
                current_period_start=timezone.now(),
                current_period_end=timezone.now() + timedelta(days=30)
            )
            return JsonResponse({
                'success': True, 
                'message': 'Plan selected successfully',
                'redirect_url': f'/business/{business.slug}/subscriptions/payment/'
            })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def cancel_subscription_ajax(request):
    """AJAX endpoint for subscription cancellation"""
    try:
        reason = request.POST.get('reason', '')
        feedback = request.POST.get('feedback', '')
        
        # Get the business
        business = get_object_or_404(Business, slug=request.tenant.slug)
        
        # Get active subscription
        subscription = Subscription.objects.using('default').filter(
            business=business,
            status='active'
        ).first()
        
        if not subscription:
            return JsonResponse({'success': False, 'error': 'No active subscription found'})
        
        # Update subscription status
        subscription.status = 'cancelled'
        subscription.canceled_at = timezone.now()
        subscription.cancellation_reason = reason
        subscription.cancellation_feedback = feedback
        subscription.save()
        
        # Send cancellation email
        send_cancellation_email(business.email, subscription)
        
        return JsonResponse({
            'success': True, 
            'message': 'Subscription cancelled successfully'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def add_payment_method(request):
    """AJAX endpoint for adding payment method"""
    try:
        card_number = request.POST.get('card_number')
        expiry_date = request.POST.get('expiry_date')
        cvv = request.POST.get('cvv')
        cardholder_name = request.POST.get('cardholder_name')
        set_default = request.POST.get('set_default') == 'true'
        
        # Get the business
        business = get_object_or_404(Business, slug=request.tenant.slug)
        
        # Validate card number (basic validation)
        if not card_number or len(card_number.replace(' ', '')) < 13:
            return JsonResponse({'success': False, 'error': 'Invalid card number'})
        
        # Validate expiry date
        if not expiry_date or len(expiry_date) != 5:
            return JsonResponse({'success': False, 'error': 'Invalid expiry date'})
        
        month, year = expiry_date.split('/')
        if int(month) < 1 or int(month) > 12:
            return JsonResponse({'success': False, 'error': 'Invalid expiry month'})
        
        # Create payment method (in real implementation, you'd use a payment processor)
        # For now, we'll create a mock payment method record
        payment_method = {
            'id': f"pm_{timezone.now().timestamp()}",
            'business': business,
            'card_type': 'visa',  # You'd detect this from card number
            'last_four': card_number.replace(' ', '')[-4:],
            'expiry_month': month,
            'expiry_year': year,
            'cardholder_name': cardholder_name,
            'is_default': set_default,
            'created_at': timezone.now()
        }
        
        # In real implementation, save to database
        # PaymentMethod.objects.create(**payment_method)
        
        return JsonResponse({
            'success': True, 
            'message': 'Payment method added successfully'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def set_default_payment_method(request):
    """AJAX endpoint for setting default payment method"""
    try:
        payment_method_id = request.POST.get('payment_method_id')
        if not payment_method_id:
            return JsonResponse({'success': False, 'error': 'Payment method ID required'})
        
        # Get the business
        business = get_object_or_404(Business, slug=request.tenant.slug)
        
        # In real implementation, you'd update the payment methods
        # PaymentMethod.objects.filter(business=business).update(is_default=False)
        # PaymentMethod.objects.filter(id=payment_method_id, business=business).update(is_default=True)
        
        return JsonResponse({
            'success': True, 
            'message': 'Default payment method updated'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def remove_payment_method(request):
    """AJAX endpoint for removing payment method"""
    try:
        payment_method_id = request.POST.get('payment_method_id')
        if not payment_method_id:
            return JsonResponse({'success': False, 'error': 'Payment method ID required'})
        
        # Get the business
        business = get_object_or_404(Business, slug=request.tenant.slug)
        
        # In real implementation, you'd remove the payment method
        # payment_method = PaymentMethod.objects.filter(id=payment_method_id, business=business).first()
        # if payment_method:
        #     payment_method.delete()
        
        return JsonResponse({
            'success': True, 
            'message': 'Payment method removed successfully'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def track_invoice_download(request):
    """AJAX endpoint for tracking invoice downloads"""
    try:
        invoice_id = request.POST.get('invoice_id')
        if not invoice_id:
            return JsonResponse({'success': False, 'error': 'Invoice ID required'})
        
        # Get the business
        business = get_object_or_404(Business, slug=request.tenant.slug)
        
        # Track download (you could create a DownloadLog model)
        # DownloadLog.objects.create(
        #     business=business,
        #     invoice_id=invoice_id,
        #     downloaded_at=timezone.now(),
        #     downloaded_by=request.user
        # )
        
        return JsonResponse({
            'success': True, 
            'message': 'Download tracked'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def generate_invoice_pdf(request):
    """AJAX endpoint for generating invoice PDF"""
    try:
        invoice_id = request.POST.get('invoice_id')
        if not invoice_id:
            return JsonResponse({'success': False, 'error': 'Invoice ID required'})
        
        # Get the business
        business = get_object_or_404(Business, slug=request.tenant.slug)
        
        # In real implementation, you'd generate the PDF
        # from reportlab.pdfgen import canvas
        # from reportlab.lib.pagesizes import letter
        
        # For now, return success
        return JsonResponse({
            'success': True, 
            'message': 'PDF generated successfully',
            'pdf_url': f'/media/invoices/invoice_{invoice_id}.pdf'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["GET"])
def export_billing_history(request):
    """Export billing history as CSV/Excel"""
    try:
        format_type = request.GET.get('format', 'csv')
        date_range = request.GET.get('date_range', 'all')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        # Get the business
        business = get_object_or_404(Business, slug=request.tenant.slug)
        
        # Get subscription and related data
        subscription = Subscription.objects.using('default').filter(business=business).first()
        
        # Create date filter
        date_filter = {}
        if date_range == 'current_year':
            date_filter['created_at__year'] = timezone.now().year
        elif date_range == 'last_year':
            date_filter['created_at__year'] = timezone.now().year - 1
        elif date_range == 'last_6_months':
            date_filter['created_at__gte'] = timezone.now() - timedelta(days=180)
        elif date_range == 'custom' and start_date and end_date:
            date_filter['created_at__gte'] = start_date
            date_filter['created_at__lte'] = end_date
        
        # Get billing data (mock data for now)
        billing_data = [
            {
                'date': timezone.now().date(),
                'description': f'{subscription.plan.name} Plan' if subscription else 'Subscription',
                'amount': subscription.plan.price if subscription else 0,
                'status': 'Paid'
            }
        ]
        
        if format_type == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="billing_history_{timezone.now().strftime("%Y%m%d")}.csv"'
            
            writer = csv.writer(response)
            writer.writerow(['Date', 'Description', 'Amount (KES)', 'Status'])
            
            for item in billing_data:
                writer.writerow([
                    item['date'],
                    item['description'],
                    f"KES {item['amount']:.2f}",
                    item['status']
                ])
            
            return response
        
        # For other formats, return JSON for now
        return JsonResponse({'success': False, 'error': 'Format not supported yet'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def refresh_usage_data(request):
    """AJAX endpoint for refreshing usage data"""
    try:
        # Get the business
        business = get_object_or_404(Business, slug=request.tenant.slug)
        
        # Get current subscription
        subscription = Subscription.objects.using('default').filter(business=business).first()
        
        if not subscription:
            return JsonResponse({'success': False, 'error': 'No active subscription found'})
        
        # Calculate real usage data
        from apps.services.models import Service
        from apps.customers.models import Customer
        from apps.employees.models import Employee
        
        # Get current usage using tenant database
        current_services = Service.objects.using(request.tenant.db_name).count()
        current_customers = Customer.objects.using(request.tenant.db_name).count()
        current_employees = Employee.objects.using(request.tenant.db_name).count()
        
        # Calculate storage usage (mock for now)
        storage_used = 150  # MB
        
        # Calculate percentages
        plan = subscription.plan
        usage_summary = {
            'services': {
                'current': current_services,
                'limit': plan.max_services,
                'percentage': (current_services / plan.max_services * 100) if plan.max_services else 0
            },
            'customers': {
                'current': current_customers,
                'limit': plan.max_customers,
                'percentage': (current_customers / plan.max_customers * 100) if plan.max_customers else 0
            },
            'storage': {
                'current': storage_used,
                'limit': plan.storage_limit,
                'percentage': (storage_used / plan.storage_limit * 100) if plan.storage_limit else 0
            },
            'employees': {
                'current': current_employees,
                'limit': plan.max_employees,
                'percentage': (current_employees / plan.max_employees * 100) if plan.max_employees else 0
            }
        }
        
        return JsonResponse({
            'success': True, 
            'usage_summary': usage_summary
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["GET"])
def generate_usage_report(request):
    """Generate usage reports in various formats"""
    try:
        report_type = request.GET.get('report_type', 'summary')
        date_range = request.GET.get('date_range', 'last_30_days')
        
        # Get the business
        business = get_object_or_404(Business, slug=request.tenant.slug)
        
        # Get usage data for the specified period
        from apps.services.models import Service
        from apps.customers.models import Customer
        from apps.employees.models import Employee
        
        # Calculate date range
        end_date = timezone.now()
        if date_range == 'last_7_days':
            start_date = end_date - timedelta(days=7)
        elif date_range == 'last_30_days':
            start_date = end_date - timedelta(days=30)
        elif date_range == 'last_90_days':
            start_date = end_date - timedelta(days=90)
        else:  # current_year
            start_date = timezone.now().replace(month=1, day=1)
        
        # Generate daily usage data
        usage_data = []
        current_date = start_date.date()
        while current_date <= end_date.date():
            # In real implementation, you'd query actual daily metrics
            usage_data.append({
                'date': current_date,
                'services': Service.objects.using(request.tenant.db_name).count(),
                'customers': Customer.objects.using(request.tenant.db_name).count(),
                'storage': 150,  # Mock storage usage
                'employees': Employee.objects.using(request.tenant.db_name).count()
            })
            current_date += timedelta(days=1)
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="usage_report_{report_type}_{timezone.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Date', 'Services', 'Customers', 'Storage (MB)', 'Employees'])
        
        for data in usage_data:
            writer.writerow([
                data['date'],
                data['services'],
                data['customers'],
                data['storage'],
                data['employees']
            ])
        
        return response
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})