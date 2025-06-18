from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.urls import reverse
from django.conf import settings
from apps.core.decorators import employee_required, ajax_required
from apps.core.utils import send_sms_notification, send_email_notification
from .models import (
    Payment, PaymentMethod, PaymentRefund, MPesaTransaction,
    CardTransaction, CashTransaction, PaymentGateway
)
from .forms import (
    PaymentForm, CashPaymentForm, CardPaymentForm, MPesaPaymentForm,
    PaymentRefundForm, PaymentMethodForm
)
from .mpesa import MPesaService, validate_mpesa_phone
import json
import logging

logger = logging.getLogger(__name__)

@login_required
# Owner or manager required for payment dashboard
@employee_required(['owner', 'manager'])
def payment_dashboard_view(request):
    """Payment dashboard with key metrics"""
    today = timezone.now().date()
    
    # Today's statistics
    today_payments = Payment.objects.filter(
        created_at__date=today,
        status__in=['completed', 'verified']
    )
    
    today_stats = {
        'total_amount': today_payments.aggregate(Sum('amount'))['amount__sum'] or 0,
        'total_count': today_payments.count(),
        'cash_amount': today_payments.filter(payment_method__method_type='cash').aggregate(Sum('amount'))['amount__sum'] or 0,
        'card_amount': today_payments.filter(payment_method__method_type='card').aggregate(Sum('amount'))['amount__sum'] or 0,
        'mpesa_amount': today_payments.filter(payment_method__method_type='mpesa').aggregate(Sum('amount'))['amount__sum'] or 0,
    }
    
    # Pending payments
    pending_payments = Payment.objects.filter(
        status__in=['pending', 'processing']
    ).order_by('-created_at')[:10]
    
    # Recent transactions
    recent_payments = Payment.objects.filter(
        status__in=['completed', 'verified']
    ).select_related('customer', 'service_order', 'payment_method').order_by('-completed_at')[:15]
    
    # Payment method breakdown (this month)
    current_month = timezone.now().replace(day=1)
    method_stats = PaymentMethod.objects.filter(
        is_active=True
    ).annotate(
        this_month_count=Count(
            'payments',
            filter=Q(payments__created_at__gte=current_month, payments__status__in=['completed', 'verified'])
        ),
        this_month_amount=Sum(
            'payments__amount',
            filter=Q(payments__created_at__gte=current_month, payments__status__in=['completed', 'verified'])
        )
    )
    
    # Failed payments that need attention
    failed_payments = Payment.objects.filter(
        status='failed',
        created_at__date=today
    ).count()
    
    context = {
        'today_stats': today_stats,
        'pending_payments': pending_payments,
        'recent_payments': recent_payments,
        'method_stats': method_stats,
        'failed_payments': failed_payments,
        'title': 'Payments Dashboard'
    }
    
    return render(request, 'payments/dashboard.html', context)

@login_required
@employee_required()
def payment_list_view(request):
    """List payments with filtering"""
    payments = Payment.objects.select_related(
        'customer', 'service_order', 'payment_method', 'processed_by'
    ).order_by('-created_at')
    
    # Filters
    status = request.GET.get('status')
    method_id = request.GET.get('method')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    search = request.GET.get('search')
    
    if status:
        payments = payments.filter(status=status)
    if method_id:
        payments = payments.filter(payment_method_id=method_id)
    if date_from:
        payments = payments.filter(created_at__date__gte=date_from)
    if date_to:
        payments = payments.filter(created_at__date__lte=date_to)
    if search:
        payments = payments.filter(
            Q(payment_id__icontains=search) |
            Q(customer__first_name__icontains=search) |
            Q(customer__last_name__icontains=search) |
            Q(reference_number__icontains=search) |
            Q(transaction_id__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(payments, 25)
    page = request.GET.get('page')
    payments_page = paginator.get_page(page)
    
    # Get payment methods for filter
    payment_methods = PaymentMethod.objects.filter(is_active=True)
    
    # Calculate totals for filtered results
    totals = payments.aggregate(
        total_amount=Sum('amount'),
        completed_amount=Sum('amount', filter=Q(status__in=['completed', 'verified'])),
        pending_amount=Sum('amount', filter=Q(status__in=['pending', 'processing']))
    )
    
    context = {
        'payments': payments_page,
        'payment_methods': payment_methods,
        'totals': totals,
        'current_filters': {
            'status': status,
            'method': method_id,
            'date_from': date_from,
            'date_to': date_to,
            'search': search
        },
        'status_choices': Payment.STATUS_CHOICES,
        'title': 'Payments'
    }
    
    return render(request, 'payments/payment_list.html', context)

@login_required
@employee_required()
def payment_detail_view(request, payment_id):
    """Payment detail view"""
    payment = get_object_or_404(Payment, payment_id=payment_id)
    
    # Get related transaction details
    transaction_details = None
    if payment.payment_method.method_type == 'mpesa' and hasattr(payment, 'mpesa_details'):
        transaction_details = payment.mpesa_details
    elif payment.payment_method.method_type == 'card' and hasattr(payment, 'card_details'):
        transaction_details = payment.card_details
    elif payment.payment_method.method_type == 'cash' and hasattr(payment, 'cash_details'):
        transaction_details = payment.cash_details
    
    # Get refunds
    refunds = payment.refunds.all().order_by('-created_at')
    
    # Check if refund is possible
    can_refund = payment.can_be_refunded and request.employee.role in ['owner', 'manager']
    
    context = {
        'payment': payment,
        'transaction_details': transaction_details,
        'refunds': refunds,
        'can_refund': can_refund,
        'title': f'Payment {payment.payment_id}'
    }
    
    return render(request, 'payments/payment_detail.html', context)

@login_required
@employee_required()
def process_payment_view(request, order_id=None):
    """Process payment for service order"""
    from apps.services.models import ServiceOrder
    
    service_order = None
    if order_id:
        service_order = get_object_or_404(ServiceOrder, pk=order_id)
    
    if request.method == 'POST':
        payment_method_id = request.POST.get('payment_method')
        payment_method = get_object_or_404(PaymentMethod, id=payment_method_id)
        
        try:
            with transaction.atomic():
                # Create payment record
                payment = Payment.objects.create(
                    service_order=service_order,
                    customer=service_order.customer if service_order else None,
                    payment_method=payment_method,
                    amount=request.POST.get('amount'),
                    description=request.POST.get('description', ''),
                    customer_phone=request.POST.get('customer_phone', ''),
                    customer_email=request.POST.get('customer_email', ''),
                    processed_by=request.employee,
                    created_by=request.user
                )
                
                # Get tenant slug for proper URL routing
                tenant_slug = request.tenant.slug
                
                # Process based on payment method type with proper business slug
                if payment_method.method_type == 'cash':
                    return redirect(f'/business/{tenant_slug}/payments/{payment.payment_id}/cash/')
                elif payment_method.method_type == 'card':
                    return redirect(f'/business/{tenant_slug}/payments/{payment.payment_id}/card/')
                elif payment_method.method_type == 'mpesa':
                    return redirect(f'/business/{tenant_slug}/payments/{payment.payment_id}/mpesa/')
                else:
                    # Default to manual processing
                    payment.status = 'completed'
                    payment.completed_at = timezone.now()
                    payment.save()
                    
                    messages.success(request, f'Payment {payment.payment_id} processed successfully!')
                    # ✅ Fixed payment details redirect with business slug
                    return redirect(f'/business/{tenant_slug}/payments/{payment.payment_id}/')
                    
        except Exception as e:
            messages.error(request, f'Error processing payment: {str(e)}')
    
    # Get active payment methods
    payment_methods = PaymentMethod.objects.filter(is_active=True).order_by('display_order')
    
    context = {
        'service_order': service_order,
        'payment_methods': payment_methods,
        'title': 'Process Payment'
    }
    
    return render(request, 'payments/process_payment.html', context)
@login_required
@employee_required()
def process_cash_payment_view(request, payment_id):
    """Process cash payment"""
    payment = get_object_or_404(Payment, payment_id=payment_id)
    
    if request.method == 'POST':
        form = CashPaymentForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Create cash transaction details
                    cash_details = CashTransaction.objects.create(
                        payment=payment,
                        amount_tendered=form.cleaned_data['amount_tendered'],
                        change_given=form.cleaned_data['change_given'],
                        cashier=request.employee,
                        **{f"notes_{denom}": form.cleaned_data.get(f'notes_{denom}', 0) for denom in ['1000', '500', '200', '100', '50']},
                        **{f"coins_{denom}": form.cleaned_data.get(f'coins_{denom}', 0) for denom in ['40', '20', '10', '5', '1']}
                    )
                    
                    # Complete payment
                    payment.complete_payment(user=request.user)
                    
                    messages.success(request, f'Cash payment {payment.payment_id} completed successfully!')
                    return redirect('payments:detail', payment_id=payment.payment_id)
                    
            except Exception as e:
                messages.error(request, f'Error processing cash payment: {str(e)}')
    else:
        # Pre-fill form with payment amount
        initial_data = {
            'amount_tendered': payment.amount,
            'change_given': 0
        }
        form = CashPaymentForm(initial=initial_data)
    
    context = {
        'payment': payment,
        'form': form,
        'title': f'Cash Payment - {payment.payment_id}'
    }
    
    return render(request, 'payments/process_cash.html', context)

@login_required
@employee_required()
def process_mpesa_payment_view(request, payment_id):
    """Process M-Pesa payment"""
    payment = get_object_or_404(Payment, payment_id=payment_id)
    
    if request.method == 'POST':
        form = MPesaPaymentForm(request.POST)
        if form.is_valid():
            phone_number = form.cleaned_data['phone_number']
            
            # Validate phone number
            is_valid, formatted_phone = validate_mpesa_phone(phone_number)
            if not is_valid:
                messages.error(request, formatted_phone)
                return render(request, 'payments/process_mpesa.html', {
                    'payment': payment,
                    'form': form,
                    'title': f'M-Pesa Payment - {payment.payment_id}'
                })
            
            try:
                # Initialize M-Pesa service
                mpesa_service = MPesaService()
                
                # Create payment request
                success, result = mpesa_service.create_payment_request(
                    payment_id=payment.payment_id,
                    phone_number=formatted_phone,
                    amount=payment.amount,
                    description=f"Payment for {payment.description}"
                )
                
                if success:
                    messages.success(request, result['customer_message'])
                    return redirect('payments:mpesa_status', payment_id=payment.payment_id)
                else:
                    messages.error(request, f'M-Pesa payment failed: {result}')
                    
            except Exception as e:
                messages.error(request, f'Error initiating M-Pesa payment: {str(e)}')
                logger.error(f"M-Pesa payment error for {payment_id}: {e}")
    else:
        # Pre-fill with customer phone if available
        initial_phone = ''
        if payment.customer and payment.customer.phone:
            initial_phone = str(payment.customer.phone)
        
        form = MPesaPaymentForm(initial={'phone_number': initial_phone})
    
    context = {
        'payment': payment,
        'form': form,
        'title': f'M-Pesa Payment - {payment.payment_id}'
    }
    
    return render(request, 'payments/process_mpesa.html', context)

@login_required
@employee_required()
def mpesa_payment_status_view(request, payment_id):
    """M-Pesa payment status checking page"""
    payment = get_object_or_404(Payment, payment_id=payment_id)
    
    context = {
        'payment': payment,
        'title': f'M-Pesa Payment Status - {payment.payment_id}'
    }
    
    return render(request, 'payments/mpesa_status.html', context)

@login_required
@employee_required()
@ajax_required
def check_mpesa_status_ajax(request, payment_id):
    """AJAX endpoint to check M-Pesa payment status"""
    try:
        payment = Payment.objects.get(payment_id=payment_id)
        
        if payment.status in ['completed', 'verified']:
            return JsonResponse({
                'status': 'completed',
                'message': 'Payment completed successfully',
                'payment_status': payment.status,
                'completed_at': payment.completed_at.isoformat() if payment.completed_at else None
            })
        elif payment.status == 'failed':
            return JsonResponse({
                'status': 'failed',
                'message': payment.failure_reason or 'Payment failed',
                'payment_status': payment.status
            })
        else:
            # Check with M-Pesa API
            mpesa_service = MPesaService()
            success, result = mpesa_service.check_payment_status(payment_id)
            
            return JsonResponse({
                'status': 'completed' if success else 'pending',
                'message': result,
                'payment_status': payment.status
            })
            
    except Payment.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Payment not found'
        }, status=404)
    except Exception as e:
        logger.error(f"M-Pesa status check error: {e}")
        return JsonResponse({
            'status': 'error',
            'message': 'Error checking payment status'
        }, status=500)

@csrf_exempt
@require_POST
def mpesa_callback_view(request):
    """M-Pesa callback endpoint"""
    try:
        callback_data = json.loads(request.body.decode('utf-8'))
        
        # Process the callback
        mpesa_service = MPesaService()
        success, message = mpesa_service.process_webhook_callback(callback_data)
        
        if success:
            logger.info(f"M-Pesa callback processed successfully: {message}")
            return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Success'})
        else:
            logger.error(f"M-Pesa callback processing failed: {message}")
            return JsonResponse({'ResultCode': 1, 'ResultDesc': message})
            
    except json.JSONDecodeError:
        logger.error("Invalid JSON in M-Pesa callback")
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Invalid JSON'})
    except Exception as e:
        logger.error(f"M-Pesa callback error: {e}")
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Internal error'})

@login_required
@employee_required(['owner', 'manager'])
def payment_refund_view(request, payment_id):
    """Create payment refund"""
    payment = get_object_or_404(Payment, payment_id=payment_id)
    
    if not payment.can_be_refunded:
        messages.error(request, 'This payment cannot be refunded.')
        return redirect('payments:detail', payment_id=payment_id)
    
    if request.method == 'POST':
        form = PaymentRefundForm(request.POST, payment=payment)
        if form.is_valid():
            try:
                with transaction.atomic():
                    refund = form.save(commit=False)
                    refund.original_payment = payment
                    refund.processed_by = request.employee
                    refund.save()
                    
                    # Process refund (this would integrate with payment gateways)
                    refund.process_refund(request.user)
                    
                    messages.success(request, f'Refund {refund.refund_id} processed successfully!')
                    return redirect('payments:detail', payment_id=payment_id)
                    
            except Exception as e:
                messages.error(request, f'Error processing refund: {str(e)}')
    else:
        # Pre-fill with payment amount
        form = PaymentRefundForm(payment=payment, initial={'amount': payment.amount})
    
    context = {
        'payment': payment,
        'form': form,
        'title': f'Refund Payment - {payment.payment_id}'
    }
    
    return render(request, 'payments/payment_refund.html', context)

@login_required
@employee_required()
def payment_methods_view(request):
    """Manage payment methods"""
    payment_methods = PaymentMethod.objects.all().order_by('display_order')
    
    context = {
        'payment_methods': payment_methods,
        'title': 'Payment Methods'
    }
    
    return render(request, 'payments/payment_methods.html', context)

@login_required
@employee_required()
def payment_reports_view(request):
    """Payment reports and analytics"""
    # Date range
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if not date_from:
        date_from = timezone.now().replace(day=1).date()  # First day of current month
    if not date_to:
        date_to = timezone.now().date()
    
    # Base queryset
    payments = Payment.objects.filter(
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
        status__in=['completed', 'verified']
    )
    
    # Summary statistics
    summary = payments.aggregate(
        total_amount=Sum('amount'),
        total_count=Count('id'),
        avg_amount=Avg('amount'),
        total_fees=Sum('processing_fee')
    )
    
    # Payment method breakdown
    method_breakdown = payments.values(
        'payment_method__name',
        'payment_method__method_type'
    ).annotate(
        count=Count('id'),
        total_amount=Sum('amount'),
        avg_amount=Avg('amount')
    ).order_by('-total_amount')
    
    # Daily totals
    daily_totals = payments.extra(
        select={'day': 'DATE(created_at)'}
    ).values('day').annotate(
        count=Count('id'),
        total_amount=Sum('amount')
    ).order_by('day')
    
    # Top customers by payment volume
    top_customers = payments.values(
        'customer__first_name',
        'customer__last_name',
        'customer__customer_id'
    ).annotate(
        total_payments=Count('id'),
        total_amount=Sum('amount')
    ).order_by('-total_amount')[:10]
    
    # Failed payments analysis
    failed_payments = Payment.objects.filter(
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
        status='failed'
    ).values(
        'payment_method__name',
        'failure_reason'
    ).annotate(
        count=Count('id')
    ).order_by('-count')
    
    context = {
        'date_from': date_from,
        'date_to': date_to,
        'summary': summary,
        'method_breakdown': method_breakdown,
        'daily_totals': list(daily_totals),
        'top_customers': top_customers,
        'failed_payments': failed_payments,
        'title': 'Payment Reports'
    }
    
    return render(request, 'payments/reports.html', context)

@login_required
@employee_required()
def export_payments_csv(request):
    """Export payments to CSV"""
    import csv
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="payments_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Payment ID', 'Date', 'Customer', 'Amount', 'Method', 'Status',
        'Service Order', 'Transaction ID', 'Processing Fee', 'Net Amount'
    ])
    
    # Get date range
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    payments = Payment.objects.select_related('customer', 'payment_method', 'service_order')
    
    if date_from:
        payments = payments.filter(created_at__date__gte=date_from)
    if date_to:
        payments = payments.filter(created_at__date__lte=date_to)
    
    for payment in payments.order_by('-created_at'):
        writer.writerow([
            payment.payment_id,
            payment.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            payment.customer.display_name if payment.customer else 'N/A',
            payment.amount,
            payment.payment_method.name,
            payment.get_status_display(),
            payment.service_order.order_number if payment.service_order else 'N/A',
            payment.transaction_id,
            payment.processing_fee,
            payment.net_amount
        ])
    
    return response

@login_required
@employee_required()
@require_POST
def verify_payment(request, payment_id):
    """Verify a completed payment"""
    payment = get_object_or_404(Payment, payment_id=payment_id)
    
    if payment.status == 'completed':
        payment.status = 'verified'
        payment.verified_by = request.employee
        payment.save()
        
        messages.success(request, f'Payment {payment.payment_id} has been verified.')
    else:
        messages.error(request, 'Only completed payments can be verified.')
    
    return redirect('payments:detail', payment_id=payment_id)

@login_required
@employee_required()
@ajax_required
def payment_summary_ajax(request):
    """AJAX endpoint for payment summary data"""
    today = timezone.now().date()
    
    # Today's summary
    today_payments = Payment.objects.filter(
        created_at__date=today,
        status__in=['completed', 'verified']
    )
    
    # This week's summary
    week_start = today - timezone.timedelta(days=today.weekday())
    week_payments = Payment.objects.filter(
        created_at__date__gte=week_start,
        status__in=['completed', 'verified']
    )
    
    # This month's summary
    month_start = today.replace(day=1)
    month_payments = Payment.objects.filter(
        created_at__date__gte=month_start,
        status__in=['completed', 'verified']
    )
    
    data = {
        'today': {
            'count': today_payments.count(),
            'amount': float(today_payments.aggregate(Sum('amount'))['amount__sum'] or 0)
        },
        'week': {
            'count': week_payments.count(),
            'amount': float(week_payments.aggregate(Sum('amount'))['amount__sum'] or 0)
        },
        'month': {
            'count': month_payments.count(),
            'amount': float(month_payments.aggregate(Sum('amount'))['amount__sum'] or 0)
        },
        'pending_count': Payment.objects.filter(status__in=['pending', 'processing']).count()
    }
    
    return JsonResponse(data)

@login_required
@employee_required()
@ajax_required
def process_bulk_payments(request):
    """Process multiple payments at once"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            payment_ids = data.get('payment_ids', [])
            action = data.get('action')  # 'verify', 'cancel', etc.
            
            payments = Payment.objects.filter(payment_id__in=payment_ids)
            updated_count = 0
            
            with transaction.atomic():
                for payment in payments:
                    if action == 'verify' and payment.status == 'completed':
                        payment.status = 'verified'
                        payment.verified_by = request.employee
                        payment.save()
                        updated_count += 1
                    elif action == 'cancel' and payment.status in ['pending', 'processing']:
                        payment.status = 'cancelled'
                        payment.save()
                        updated_count += 1
            
            return JsonResponse({
                'success': True,
                'updated_count': updated_count,
                'message': f'{updated_count} payments {action}ed successfully'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=500)
    
    return JsonResponse({'success': False, 'message': 'Invalid request'}, status=400)

@login_required
@employee_required()
def payment_settings_view(request):
    """Payment settings and configuration"""
    gateways = PaymentGateway.objects.all()
    payment_methods = PaymentMethod.objects.all().order_by('display_order')
    
    context = {
        'gateways': gateways,
        'payment_methods': payment_methods,
        'title': 'Payment Settings'
    }
    
    return render(request, 'payments/settings.html', context)

@login_required
@employee_required()
def reconciliation_view(request):
    """Payment reconciliation dashboard"""
    today = timezone.now().date()
    
    # Get unreconciled payments
    unreconciled = Payment.objects.filter(
        status='completed',
        created_at__date=today
    ).exclude(
        status='verified'
    )
    
    # Cash reconciliation
    cash_payments = Payment.objects.filter(
        payment_method__method_type='cash',
        created_at__date=today,
        status__in=['completed', 'verified']
    )
    
    cash_total = cash_payments.aggregate(Sum('amount'))['amount__sum'] or 0
    
    # M-Pesa reconciliation
    mpesa_payments = Payment.objects.filter(
        payment_method__method_type='mpesa',
        created_at__date=today,
        status__in=['completed', 'verified']
    )
    
    mpesa_total = mpesa_payments.aggregate(Sum('amount'))['amount__sum'] or 0
    
    # Card reconciliation
    card_payments = Payment.objects.filter(
        payment_method__method_type='card',
        created_at__date=today,
        status__in=['completed', 'verified']
    )
    
    card_total = card_payments.aggregate(Sum('amount'))['amount__sum'] or 0
    
    context = {
        'unreconciled': unreconciled,
        'cash_payments': cash_payments,
        'cash_total': cash_total,
        'mpesa_payments': mpesa_payments,
        'mpesa_total': mpesa_total,
        'card_payments': card_payments,
        'card_total': card_total,
        'title': 'Payment Reconciliation'
    }
    
    return render(request, 'payments/reconciliation.html', context)