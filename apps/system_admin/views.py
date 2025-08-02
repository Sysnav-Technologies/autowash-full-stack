from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import user_passes_test, login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Count, Sum, Avg
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.db import transaction
from django.core.management import call_command
from apps.core.tenant_models import Tenant
from apps.core.database_router import TenantDatabaseManager, tenant_context
from apps.subscriptions.models import Subscription, SubscriptionPlan, Payment, SubscriptionInvoice
from .models import AdminActivity
from datetime import timedelta
from decimal import Decimal
import traceback
import json
import json
import traceback

@staff_member_required
def system_dashboard(request):
    """Enhanced system admin dashboard with comprehensive statistics"""
    
    # Get comprehensive statistics
    stats = {
        'total_businesses': Tenant.objects.count(),
        'pending_approval': Tenant.objects.filter(is_approved=False, is_active=True).count(),
        'active_businesses': Tenant.objects.filter(is_approved=True, is_active=True).count(),
        'suspended_businesses': Tenant.objects.filter(is_active=False).count(),
        'total_subscriptions': Subscription.objects.filter(status='active').count(),
        'trial_subscriptions': Subscription.objects.filter(status='trial').count(),
        'expired_subscriptions': Subscription.objects.filter(status='expired').count(),
        'cancelled_subscriptions': Subscription.objects.filter(status='cancelled').count(),
    }
    
    # Revenue statistics
    current_month = timezone.now().replace(day=1)
    stats['monthly_revenue'] = Payment.objects.filter(
        status='completed',
        paid_at__gte=current_month
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Recent business applications (pending approval)
    recent_applications = Tenant.objects.filter(
        is_approved=False,
        is_active=True
    ).select_related('owner').order_by('-created_at')[:10]
    
    # Subscription distribution by plan
    subscription_stats = SubscriptionPlan.objects.annotate(
        active_count=Count('subscription', filter=Q(subscription__status='active')),
        trial_count=Count('subscription', filter=Q(subscription__status='trial')),
        total_revenue=Sum('subscription__amount', filter=Q(subscription__status='active'))
    ).order_by('-active_count')
    
    # Recent activities (you can implement a proper activity log model later)
    recent_activities = []
    
    context = {
        'stats': stats,
        'recent_applications': recent_applications,
        'subscription_stats': subscription_stats,
        'recent_activities': recent_activities,
        'title': 'System Administration Dashboard'
    }
    
    return render(request, 'system_admin/dashboard.html', context)

@staff_member_required
def approve_business(request, business_id):
    """Approve a business application with comprehensive tenant setup"""
    business = get_object_or_404(Tenant, id=business_id)
    
    if request.method == 'POST':
        # Get the subscription plan from the form
        plan_id = request.POST.get('subscription_plan')
        if plan_id:
            try:
                plan = SubscriptionPlan.objects.get(id=plan_id)
                
                # Start the approval process
                with transaction.atomic():
                    # 1. Approve the business
                    business.is_approved = True
                    business.approved_by = request.user
                    business.approved_at = timezone.now()
                    business.is_active = True
                    business.save()
                    
                    # 2. Create subscription if it doesn't exist
                    subscription = None
                    if not hasattr(business, 'subscription') or not business.subscription:
                        subscription = Subscription.objects.create(
                            business=business,
                            plan=plan,
                            status='trial',  # Start with trial
                            start_date=timezone.now().date(),
                            end_date=(timezone.now() + timezone.timedelta(days=getattr(plan, 'trial_days', 14))).date(),
                            amount=plan.price
                        )
                        business.subscription = subscription
                        business.save()
                    else:
                        subscription = business.subscription
                    
                    # 3. Setup tenant database and employee record
                    setup_success = setup_tenant_after_approval(business, request.user)
                    
                    if setup_success:
                        # Log the activity
                        AdminActivity.objects.create(
                            admin=request.user,
                            action=f"Approved business '{business.name}' with automatic tenant setup"
                        )
                        
                        messages.success(
                            request, 
                            f'Business "{business.name}" has been approved successfully! '
                            f'Tenant database created and owner employee record established.'
                        )
                        
                        # TODO: Send approval notification email/SMS
                        
                        return redirect('system_admin:dashboard')
                    else:
                        # If tenant setup failed, we still keep the business approved
                        # but show a warning
                        messages.warning(
                            request,
                            f'Business "{business.name}" has been approved, but there were issues '
                            f'setting up the tenant database. Please check the logs and complete setup manually.'
                        )
                        return redirect('system_admin:business_management')
                
            except SubscriptionPlan.DoesNotExist:
                messages.error(request, 'Invalid subscription plan selected.')
            except Exception as e:
                messages.error(request, f'Error approving business: {str(e)}')
                # Log the full error for debugging
                import traceback
                print(f"Business approval error: {traceback.format_exc()}")
        else:
            messages.error(request, 'Please select a subscription plan.')
    
    # Get available subscription plans
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price')
    
    context = {
        'business': business,
        'plans': plans,
        'title': f'Approve Business - {business.name}'
    }
    return render(request, 'system_admin/approve_business.html', context)

@staff_member_required
def reject_business(request, business_id):
    """Reject a business application with reason"""
    business = get_object_or_404(Tenant, id=business_id)
    
    if request.method == 'POST':
        rejection_reason = request.POST.get('rejection_reason', '')
        additional_comments = request.POST.get('additional_comments', '')
        combined_reason = f"{rejection_reason}: {additional_comments}" if additional_comments else rejection_reason
        
        if combined_reason:
            business.is_approved = False
            business.is_active = False
            business.rejection_reason = combined_reason
            # Note: rejected_by and rejected_at fields don't exist in model, 
            # but we can add them to the rejection_reason or handle via AdminActivity
            business.save()
            
            messages.success(request, f'Business "{business.name}" has been rejected.')
            
            # TODO: Send rejection notification email/SMS
            
            return redirect('system_admin:business_management')
        else:
            messages.error(request, 'Please provide a rejection reason.')
    
    context = {
        'business': business,
        'title': f'Reject Business - {business.name}'
    }
    return render(request, 'system_admin/reject_business.html', context)

@staff_member_required
def business_management(request):
    """Comprehensive business management view"""
    
    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    search = request.GET.get('search', '')
    business_type = request.GET.get('type', '')
    
    # Build queryset
    businesses = Tenant.objects.select_related('owner', 'subscription', 'subscription__plan')
    
    if status_filter == 'pending':
        businesses = businesses.filter(is_approved=False, is_active=True)
    elif status_filter == 'active':
        businesses = businesses.filter(is_approved=True, is_active=True)
    elif status_filter == 'suspended':
        businesses = businesses.filter(is_active=False)
    
    if search:
        businesses = businesses.filter(
            Q(name__icontains=search) |
            Q(owner__username__icontains=search) |
            Q(owner__email__icontains=search)
        )
    
    if business_type:
        businesses = businesses.filter(business_type=business_type)
    
    # Pagination
    paginator = Paginator(businesses.order_by('-created_at'), 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get business types for filter
    business_types = [
        ('car_wash', 'Car Wash'),
        ('detailing', 'Car Detailing'),
        ('full_service', 'Full Service'),
    ]
    
    context = {
        'page_obj': page_obj,
        'business_types': business_types,
        'current_status': status_filter,
        'current_search': search,
        'current_type': business_type,
        'title': 'Business Management'
    }
    
    return render(request, 'system_admin/business_management.html', context)

@staff_member_required
def subscription_management(request):
    """Enhanced subscription management with analytics"""
    
    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    plan_filter = request.GET.get('plan', '')
    search = request.GET.get('search', '')
    
    # Build queryset
    subscriptions = Subscription.objects.select_related('business', 'plan')
    
    if status_filter != 'all':
        subscriptions = subscriptions.filter(status=status_filter)
    
    if plan_filter:
        subscriptions = subscriptions.filter(plan_id=plan_filter)
    
    if search:
        subscriptions = subscriptions.filter(
            Q(business__name__icontains=search) |
            Q(subscription_id__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(subscriptions.order_by('-created_at'), 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get subscription statistics
    subscription_stats = {
        'total': Subscription.objects.count(),
        'active': Subscription.objects.filter(status='active').count(),
        'trial': Subscription.objects.filter(status='trial').count(),
        'expired': Subscription.objects.filter(status='expired').count(),
        'cancelled': Subscription.objects.filter(status='cancelled').count(),
    }
    
    # Revenue statistics
    revenue_stats = {
        'total_revenue': Payment.objects.filter(status='completed').aggregate(
            total=Sum('amount'))['total'] or 0,
        'monthly_revenue': Payment.objects.filter(
            status='completed',
            paid_at__month=timezone.now().month,
            paid_at__year=timezone.now().year
        ).aggregate(total=Sum('amount'))['total'] or 0,
    }
    
    # Available plans and status choices
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('name')
    status_choices = Subscription.STATUS_CHOICES
    
    context = {
        'page_obj': page_obj,
        'plans': plans,
        'status_choices': status_choices,
        'subscription_stats': subscription_stats,
        'revenue_stats': revenue_stats,
        'current_status': status_filter,
        'current_plan': plan_filter,
        'current_search': search,
        'title': 'Subscription Management'
    }
    
    return render(request, 'system_admin/subscription_management.html', context)

@staff_member_required
def subscription_plans(request):
    """Manage subscription plans"""
    
    plans = SubscriptionPlan.objects.annotate(
        active_subscriptions=Count('subscription', filter=Q(subscription__status='active')),
        total_revenue=Sum('subscription__amount', filter=Q(subscription__status='active'))
    ).order_by('duration_months', 'price')
    
    context = {
        'plans': plans,
        'title': 'Subscription Plans Management'
    }
    
    return render(request, 'system_admin/subscription_plans.html', context)

@staff_member_required
def create_subscription_plan(request):
    """Create a new subscription plan"""
    if request.method == 'POST':
        # Handle plan creation
        name = request.POST.get('name')
        slug = request.POST.get('slug')
        plan_type = request.POST.get('plan_type')
        description = request.POST.get('description')
        price = request.POST.get('price')
        duration_months = request.POST.get('duration_months')
        
        if name and slug and plan_type and price and duration_months:
            try:
                plan = SubscriptionPlan.objects.create(
                    name=name,
                    slug=slug,
                    plan_type=plan_type,
                    description=description,
                    price=price,
                    duration_months=duration_months,
                    is_active=True
                )
                messages.success(request, f'Subscription plan "{plan.name}" created successfully.')
                return redirect('system_admin:subscription_plans')
            except Exception as e:
                messages.error(request, f'Error creating plan: {str(e)}')
        else:
            messages.error(request, 'Please fill in all required fields.')
    
    context = {
        'title': 'Create Subscription Plan',
        'plan_types': SubscriptionPlan.PLAN_TYPES
    }
    return render(request, 'system_admin/create_subscription_plan.html', context)

@staff_member_required
def edit_subscription_plan(request, plan_id):
    """Edit an existing subscription plan"""
    plan = get_object_or_404(SubscriptionPlan, id=plan_id)
    
    if request.method == 'POST':
        # Handle plan update
        plan.name = request.POST.get('name', plan.name)
        plan.slug = request.POST.get('slug', plan.slug)
        plan.plan_type = request.POST.get('plan_type', plan.plan_type)
        plan.description = request.POST.get('description', plan.description)
        plan.price = request.POST.get('price', plan.price)
        plan.duration_months = request.POST.get('duration_months', plan.duration_months)
        plan.is_active = request.POST.get('is_active') == 'on'
        
        try:
            plan.save()
            messages.success(request, f'Subscription plan "{plan.name}" updated successfully.')
            return redirect('system_admin:subscription_plans')
        except Exception as e:
            messages.error(request, f'Error updating plan: {str(e)}')
    
    context = {
        'plan': plan,
        'title': f'Edit Plan - {plan.name}',
        'plan_types': SubscriptionPlan.PLAN_TYPES
    }
    return render(request, 'system_admin/edit_subscription_plan.html', context)

@staff_member_required
def payment_management(request):
    """Manage payments and transactions"""
    
    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    method_filter = request.GET.get('method', '')
    search = request.GET.get('search', '')
    
    # Build queryset
    payments = Payment.objects.select_related('subscription', 'subscription__business')
    
    if status_filter != 'all':
        payments = payments.filter(status=status_filter)
    
    if method_filter:
        payments = payments.filter(payment_method=method_filter)
    
    if search:
        payments = payments.filter(
            Q(payment_id__icontains=search) |
            Q(transaction_id__icontains=search) |
            Q(subscription__business__name__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(payments.order_by('-created_at'), 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Payment statistics
    payment_stats = {
        'total_payments': Payment.objects.count(),
        'completed': Payment.objects.filter(status='completed').count(),
        'pending': Payment.objects.filter(status='pending').count(),
        'failed': Payment.objects.filter(status='failed').count(),
        'total_amount': Payment.objects.filter(status='completed').aggregate(
            total=Sum('amount'))['total'] or 0,
    }
    
    context = {
        'page_obj': page_obj,
        'payment_stats': payment_stats,
        'status_choices': Payment.STATUS_CHOICES,
        'method_choices': Payment.PAYMENT_METHODS,
        'current_status': status_filter,
        'current_method': method_filter,
        'current_search': search,
        'title': 'Payment Management'
    }
    
    return render(request, 'system_admin/payment_management.html', context)

@staff_member_required
def system_analytics(request):
    """System analytics and reporting dashboard"""
    
    # Get date range parameters
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)
    
    # Business growth analytics
    business_growth = []
    for i in range(days):
        date = start_date + timedelta(days=i)
        count = Tenant.objects.filter(created_at__date=date.date()).count()
        business_growth.append({
            'date': date.strftime('%Y-%m-%d'),
            'count': count
        })
    
    # Revenue analytics
    revenue_data = []
    for i in range(days):
        date = start_date + timedelta(days=i)
        revenue = Payment.objects.filter(
            status='completed',
            paid_at__date=date.date()
        ).aggregate(total=Sum('amount'))['total'] or 0
        revenue_data.append({
            'date': date.strftime('%Y-%m-%d'),
            'revenue': float(revenue)
        })
    
    # Plan popularity
    plan_stats = SubscriptionPlan.objects.annotate(
        subscriber_count=Count('subscription'),
        total_revenue=Sum('subscription__amount')
    ).order_by('-subscriber_count')
    
    # Monthly trends
    monthly_stats = {
        'new_businesses': Tenant.objects.filter(
            created_at__gte=start_date
        ).count(),
        'new_subscriptions': Subscription.objects.filter(
            created_at__gte=start_date
        ).count(),
        'total_revenue': Payment.objects.filter(
            status='completed',
            paid_at__gte=start_date
        ).aggregate(total=Sum('amount'))['total'] or 0,
        'average_subscription_value': Subscription.objects.filter(
            created_at__gte=start_date
        ).aggregate(avg=Avg('amount'))['avg'] or 0,
    }
    
    context = {
        'business_growth': json.dumps(business_growth),
        'revenue_data': json.dumps(revenue_data),
        'plan_stats': plan_stats,
        'monthly_stats': monthly_stats,
        'days': days,
        'title': 'System Analytics'
    }
    
    return render(request, 'system_admin/analytics.html', context)

@staff_member_required
@require_http_methods(["POST"])
def bulk_approve_businesses(request):
    """Bulk approve multiple businesses with tenant setup"""
    business_ids = request.POST.getlist('business_ids')
    plan_id = request.POST.get('plan_id')
    
    if not business_ids or not plan_id:
        messages.error(request, "Please select businesses and a subscription plan.")
        return redirect('system_admin:business_management')
    
    try:
        plan = SubscriptionPlan.objects.get(id=plan_id)
        approved_count = 0
        failed_setups = []
        
        for business_id in business_ids:
            try:
                business = Tenant.objects.get(id=business_id)
                if not business.is_approved:
                    with transaction.atomic():
                        # Approve the business
                        business.is_approved = True
                        business.approved_by = request.user
                        business.approved_at = timezone.now()
                        business.is_active = True
                        business.save()
                        
                        # Create subscription if it doesn't exist
                        if not hasattr(business, 'subscription') or not business.subscription:
                            subscription = Subscription.objects.create(
                                business=business,
                                plan=plan,
                                status='trial',
                                start_date=timezone.now().date(),
                                end_date=(timezone.now() + timedelta(days=14)).date(),
                                amount=plan.price
                            )
                            business.subscription = subscription
                            business.save()
                        
                        # Setup tenant database and employee record
                        setup_success = setup_tenant_after_approval(business, request.user)
                        if not setup_success:
                            failed_setups.append(business.name)
                        
                        approved_count += 1
                        
            except Tenant.DoesNotExist:
                continue
            except Exception as e:
                print(f"Error approving business {business_id}: {e}")
                continue
        
        # Provide feedback
        if approved_count > 0:
            if failed_setups:
                messages.warning(
                    request, 
                    f"Successfully approved {approved_count} businesses. "
                    f"However, tenant setup failed for: {', '.join(failed_setups)}. "
                    f"Please complete setup manually."
                )
            else:
                messages.success(
                    request, 
                    f"Successfully approved {approved_count} businesses with complete tenant setup."
                )
        
        # Log the activity
        AdminActivity.objects.create(
            admin=request.user,
            action=f"Bulk approved {approved_count} businesses"
        )
            
    except SubscriptionPlan.DoesNotExist:
        messages.error(request, "Invalid subscription plan selected.")
    except Exception as e:
        messages.error(request, f"Error during bulk approval: {str(e)}")
    
    return redirect('system_admin:business_management')

@staff_member_required
def bulk_reject_businesses(request):
    """Bulk reject multiple businesses"""
    business_ids = request.POST.getlist('business_ids')
    rejection_reason = request.POST.get('rejection_reason', 'Bulk rejection by admin')
    
    if not business_ids:
        messages.error(request, "Please select businesses to reject.")
        return redirect('system_admin:business_management')
    
    rejected_count = 0
    
    for business_id in business_ids:
        try:
            business = Tenant.objects.get(id=business_id)
            if not business.is_approved:
                business.is_active = False
                business.save()
                
                # Log the rejection activity
                AdminActivity.objects.create(
                    user=request.user,
                    action='business_rejected',
                    description=f'Bulk rejected business: {business.name}',
                    metadata={'business_id': str(business.id), 'reason': rejection_reason}
                )
                
                rejected_count += 1
        except Tenant.DoesNotExist:
            continue
    
    messages.success(request, f"Successfully rejected {rejected_count} businesses.")
    return redirect('system_admin:business_management')

@staff_member_required
def user_management(request):
    """User management interface"""
    
    # Get filter parameters
    user_type = request.GET.get('type', 'all')
    status = request.GET.get('status', 'all')
    search = request.GET.get('search', '')
    
    # Build queryset
    users = User.objects.select_related('profile').prefetch_related('tenant_set')
    
    if user_type == 'business_owners':
        users = users.filter(tenant_set__isnull=False).distinct()
    elif user_type == 'regular_users':
        users = users.filter(tenant_set__isnull=True)
    elif user_type == 'staff':
        users = users.filter(is_staff=True)
    
    if status == 'active':
        users = users.filter(is_active=True)
    elif status == 'inactive':
        users = users.filter(is_active=False)
    
    if search:
        users = users.filter(
            Q(username__icontains=search) |
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(users.order_by('-date_joined'), 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # User statistics
    user_stats = {
        'total_users': User.objects.count(),
        'active_users': User.objects.filter(is_active=True).count(),
        'business_owners': User.objects.filter(owned_tenants__isnull=False).distinct().count(),
        'staff_users': User.objects.filter(is_staff=True).count(),
    }
    
    context = {
        'page_obj': page_obj,
        'user_stats': user_stats,
        'current_type': user_type,
        'current_status': status,
        'current_search': search,
        'title': 'User Management'
    }
    
    return render(request, 'system_admin/user_management.html', context)

@staff_member_required
@require_http_methods(["POST"])
@csrf_exempt
def update_subscription_status(request):
    """AJAX endpoint to update subscription status"""
    try:
        subscription_id = request.POST.get('subscription_id')
        new_status = request.POST.get('status')
        
        subscription = get_object_or_404(Subscription, id=subscription_id)
        subscription.status = new_status
        subscription.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Subscription status updated to {new_status}'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })

@staff_member_required
def export_data(request):
    """Export system data in various formats"""
    data_type = request.GET.get('type', 'businesses')
    format_type = request.GET.get('format', 'csv')
    
    if data_type == 'businesses':
        # Export business data
        businesses = Tenant.objects.all()
        # Implementation would generate CSV/Excel file
        pass
    elif data_type == 'subscriptions':
        # Export subscription data
        subscriptions = Subscription.objects.all()
        # Implementation would generate CSV/Excel file
        pass
    elif data_type == 'payments':
        # Export payment data
        payments = Payment.objects.all()
        # Implementation would generate CSV/Excel file
        pass
    
    # For now, return a simple response
    return HttpResponse("Export functionality will be implemented", content_type="text/plain")

@staff_member_required
def system_settings(request):
    """System-wide settings management"""
    
    if request.method == 'POST':
        # Handle settings updates
        # This would typically update a Settings model or configuration
        messages.success(request, "Settings updated successfully.")
        return redirect('system_admin:system_settings')
    
    # Get current system settings
    settings_data = {
        'business_approval_required': True,
        'trial_period_days': 14,
        'auto_suspend_expired': True,
        'payment_grace_period': 7,
        'notification_settings': {
            'email_notifications': True,
            'sms_notifications': False,
            'webhook_notifications': True
        }
    }
    
    context = {
        'settings': settings_data,
        'title': 'System Settings'
    }
    
    return render(request, 'system_admin/system_settings.html', context)


@staff_member_required
def record_payment(request, subscription_id):
    """Record a manual payment for a subscription"""
    from .forms import PaymentRecordForm
    
    subscription = get_object_or_404(Subscription, id=subscription_id)
    
    if request.method == 'POST':
        form = PaymentRecordForm(request.POST)
        if form.is_valid():
            # Create payment record
            payment = Payment.objects.create(
                subscription=subscription,
                amount=form.cleaned_data['amount'],
                payment_method=form.cleaned_data['payment_method'],
                reference_number=form.cleaned_data['reference_number'],
                status='completed',
                paid_at=form.cleaned_data['payment_date'],
                notes=form.cleaned_data['notes']
            )
            
            # Update subscription status if needed
            if subscription.status in ['expired', 'suspended']:
                subscription.status = 'active'
                subscription.save()
            
            messages.success(request, f'Payment of {payment.amount} recorded successfully for {subscription.business.name}')
            return redirect('system_admin:payment_management')
    else:
        form = PaymentRecordForm(initial={
            'subscription': subscription.id,
            'payment_date': timezone.now().date(),
            'amount': subscription.plan.price
        })
    
    context = {
        'form': form,
        'subscription': subscription,
        'title': f'Record Payment - {subscription.business.name}'
    }
    
    return render(request, 'system_admin/record_payment.html', context)


@staff_member_required
def generate_invoice(request, subscription_id):
    """Generate an invoice for a subscription"""
    from .forms import InvoiceGenerationForm
    
    subscription = get_object_or_404(Subscription, id=subscription_id)
    
    if request.method == 'POST':
        form = InvoiceGenerationForm(request.POST)
        if form.is_valid():
            # Calculate total amount
            subtotal = form.cleaned_data['subtotal']
            discount = form.cleaned_data['discount_amount']
            tax = form.cleaned_data['tax_amount']
            total = subtotal - discount + tax
            
            # Create invoice
            invoice = SubscriptionInvoice.objects.create(
                subscription=subscription,
                subtotal=subtotal,
                discount_amount=discount,
                tax_amount=tax,
                total_amount=total,
                due_date=form.cleaned_data['due_date'],
                notes=form.cleaned_data.get('notes', '')
            )
            
            # Send notification if requested
            if form.cleaned_data.get('send_notification'):
                # TODO: Implement email notification
                pass
            
            messages.success(request, f'Invoice {invoice.invoice_number} generated successfully')
            return redirect('system_admin:invoice_management')
    else:
        form = InvoiceGenerationForm(initial={
            'subscription': subscription.id,
            'subtotal': subscription.plan.price,
            'due_date': (timezone.now() + timedelta(days=30)).date()
        })
    
    context = {
        'form': form,
        'subscription': subscription,
        'title': f'Generate Invoice - {subscription.business.name}'
    }
    
    return render(request, 'system_admin/generate_invoice.html', context)


@staff_member_required
def invoice_management(request):
    """Manage all invoices"""
    
    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    search = request.GET.get('search', '')
    
    # Build queryset
    invoices = SubscriptionInvoice.objects.select_related(
        'subscription', 'subscription__business', 'payment'
    )
    
    if status_filter != 'all':
        invoices = invoices.filter(status=status_filter)
    
    if search:
        invoices = invoices.filter(
            Q(invoice_number__icontains=search) |
            Q(subscription__business__name__icontains=search) |
            Q(subscription__business__owner__email__icontains=search)
        )
    
    # Check for overdue invoices and update status
    overdue_invoices = invoices.filter(
        status__in=['sent', 'draft'],
        due_date__lt=timezone.now().date()
    )
    overdue_invoices.update(status='overdue')
    
    # Pagination
    paginator = Paginator(invoices.order_by('-created_at'), 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Invoice statistics
    invoice_stats = {
        'total': SubscriptionInvoice.objects.count(),
        'draft': SubscriptionInvoice.objects.filter(status='draft').count(),
        'sent': SubscriptionInvoice.objects.filter(status='sent').count(),
        'paid': SubscriptionInvoice.objects.filter(status='paid').count(),
        'overdue': SubscriptionInvoice.objects.filter(status='overdue').count(),
        'total_amount': SubscriptionInvoice.objects.aggregate(
            total=Sum('total_amount'))['total'] or 0,
        'paid_amount': SubscriptionInvoice.objects.filter(status='paid').aggregate(
            total=Sum('total_amount'))['total'] or 0,
    }
    
    context = {
        'page_obj': page_obj,
        'invoice_stats': invoice_stats,
        'status_choices': SubscriptionInvoice.STATUS_CHOICES,
        'current_status': status_filter,
        'current_search': search,
        'title': 'Invoice Management'
    }
    
    return render(request, 'system_admin/invoice_management.html', context)


@staff_member_required
def mark_invoice_paid(request, invoice_id):
    """Mark an invoice as paid"""
    invoice = get_object_or_404(SubscriptionInvoice, id=invoice_id)
    
    if request.method == 'POST':
        # Create a payment record
        payment = Payment.objects.create(
            subscription=invoice.subscription,
            amount=invoice.total_amount,
            payment_method=request.POST.get('payment_method', 'manual'),
            reference_number=request.POST.get('reference_number', ''),
            status='completed',
            paid_at=timezone.now(),
            notes=f'Manual payment for invoice {invoice.invoice_number}'
        )
        
        # Link payment to invoice and mark as paid
        invoice.payment = payment
        invoice.status = 'paid'
        invoice.paid_date = timezone.now().date()
        invoice.save()
        
        messages.success(request, f'Invoice {invoice.invoice_number} marked as paid')
        
    return redirect('system_admin:invoice_management')


@login_required
@user_passes_test(lambda u: u.is_superuser)
def create_user(request):
    """Create a new user"""
    if request.method == 'POST':
        try:
            # Create user
            username = request.POST.get('username')
            email = request.POST.get('email')
            password = request.POST.get('password')
            first_name = request.POST.get('first_name', '')
            last_name = request.POST.get('last_name', '')
            
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            
            # Set additional fields
            user.is_staff = bool(request.POST.get('is_staff'))
            user.is_active = bool(request.POST.get('is_active', True))
            user.save()
            
            # Log the activity
            AdminActivity.objects.create(
                admin=request.user,
                action=f"Created user '{user.username}'"
            )
            
            messages.success(request, f'User "{user.username}" created successfully!')
            return redirect('system_admin:user_management')
            
        except Exception as e:
            messages.error(request, f'Error creating user: {str(e)}')
    
    return render(request, 'system_admin/create_user.html')


@login_required
@user_passes_test(lambda u: u.is_superuser)
def edit_user(request, user_id):
    """Edit an existing user"""
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        try:
            # Update user fields
            user.username = request.POST.get('username')
            user.email = request.POST.get('email')
            user.first_name = request.POST.get('first_name', '')
            user.last_name = request.POST.get('last_name', '')
            user.is_staff = bool(request.POST.get('is_staff'))
            user.is_active = bool(request.POST.get('is_active'))
            
            # Update password if provided
            new_password = request.POST.get('new_password')
            if new_password:
                user.set_password(new_password)
            
            user.save()
            
            # Log the activity
            AdminActivity.objects.create(
                admin=request.user,
                action=f"Updated user '{user.username}'"
            )
            
            messages.success(request, f'User "{user.username}" updated successfully!')
            return redirect('system_admin:user_management')
            
        except Exception as e:
            messages.error(request, f'Error updating user: {str(e)}')
    
    context = {
        'edit_user': user,  # Using edit_user to avoid conflict with request.user
    }
    return render(request, 'system_admin/edit_user.html', context)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def toggle_user_status(request, user_id):
    """Toggle user active status via AJAX"""
    if request.method == 'POST':
        try:
            user = get_object_or_404(User, id=user_id)
            data = json.loads(request.body)
            activate = data.get('activate', True)
            
            user.is_active = activate
            user.save()
            
            # Log the activity
            action = "activated" if activate else "deactivated"
            AdminActivity.objects.create(
                admin=request.user,
                action=f"User '{user.username}' {action}"
            )
            
            return JsonResponse({
                'success': True,
                'message': f'User {action} successfully'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


def setup_tenant_after_approval(business, approving_admin):
    """
    Complete tenant setup after business approval
    - Creates tenant database
    - Runs migrations
    - Creates employee record for business owner
    - Sets up default data
    """
    try:
        print(f"Starting tenant setup for: {business.name}")
        
        # Step 1: Create tenant database
        print("Creating tenant database...")
        success = TenantDatabaseManager.create_tenant_database(business)
        
        if not success:
            print(f"Failed to create tenant database for {business.name}")
            return False
        
        print(f"✓ Tenant database created: {business.database_name}")
        
        # Step 2: Create TenantSettings record
        print("Creating tenant settings...")
        try:
            with tenant_context(business):
                from apps.core.tenant_models import TenantSettings
                # Use the correct field names for TenantSettings
                settings_obj, created = TenantSettings.objects.get_or_create(
                    tenant_id=business.id,
                    defaults={
                        'sms_notifications': True,
                        'email_notifications': True,
                        'enable_online_booking': True,
                        'primary_color': '#007bff',
                        'secondary_color': '#6c757d',
                    }
                )
                if created:
                    print(f"✓ TenantSettings created")
                else:
                    print(f"✓ TenantSettings already exists")
        
        except Exception as e:
            print(f"Error creating tenant settings: {e}")
            # Continue anyway, settings can be created later
        
        # Step 3: Create employee record for business owner
        print("Creating employee record for business owner...")
        employee_success = create_owner_employee_record(business)
        
        if not employee_success:
            print(f"Warning: Failed to create employee record for owner")
            # Don't fail the entire process for this
        
        # Step 4: Set up default data (payment methods, etc.)
        print("Setting up default tenant data...")
        try:
            setup_default_tenant_data(business)
        except Exception as e:
            print(f"Warning: Error setting up default data: {e}")
            # Continue anyway, default data can be set up later
        
        print(f"✓ Tenant setup completed successfully for: {business.name}")
        return True
        
    except Exception as e:
        print(f"Error in tenant setup: {e}")
        print(traceback.format_exc())
        return False


def create_owner_employee_record(business):
    """
    Create an Employee record for the business owner in the tenant database
    """
    try:
        print(f"Creating employee record for owner: {business.owner.username}")
        
        with tenant_context(business):
            from apps.employees.models import Employee, Department
            
            # Check if employee record already exists
            existing_employee = Employee.objects.filter(
                user_id=business.owner.id,
                is_active=True
            ).first()
            
            if existing_employee:
                print(f"Employee record already exists: {existing_employee.employee_id}")
                return True
            
            # Create or get Management department
            management_dept, dept_created = Department.objects.get_or_create(
                name='Management',
                defaults={
                    'description': 'Business management and administration',
                    'is_active': True
                }
            )
            
            if dept_created:
                print(f"✓ Created Management department")
            else:
                print(f"✓ Found existing Management department")
            
            # Generate unique employee ID
            employee_count = Employee.objects.count()
            # Use business slug or first 3 chars of name for prefix
            prefix = business.slug.upper().replace('-', '')[:3] if business.slug else business.name.upper()[:3]
            employee_id = f"EMP{prefix}{employee_count + 1:04d}"
            
            # Ensure uniqueness
            while Employee.objects.filter(employee_id=employee_id).exists():
                employee_count += 1
                employee_id = f"EMP{prefix}{employee_count + 1:04d}"
            
            # Get user profile info from public schema
            user_profile = None
            try:
                user_profile = business.owner.profile
            except:
                pass
            
            # Create employee record
            employee = Employee.objects.create(
                user_id=business.owner.id,
                employee_id=employee_id,
                role='owner',
                employment_type='full_time',
                status='active',
                department=management_dept,
                hire_date=business.created_at.date(),
                is_active=True,
                can_login=True,
                receive_notifications=True,
                phone=user_profile.phone if user_profile else business.phone,
                country=business.country or 'Kenya',
            )
            
            # Set department head
            if not management_dept.head:
                management_dept.head = employee
                management_dept.save()
            
            print(f"✓ Created employee record: {employee.employee_id} for {employee.full_name}")
            return True
            
    except Exception as e:
        print(f"Error creating employee record: {e}")
        print(traceback.format_exc())
        return False


def setup_default_tenant_data(business):
    """
    Set up default data for the tenant (payment methods, categories, etc.)
    """
    try:
        with tenant_context(business):
            # Create default payment methods
            from apps.payments.models import PaymentMethod
            
            default_payment_methods = [
                {'name': 'Cash', 'method_type': 'cash', 'is_active': True},
                {'name': 'M-Pesa', 'method_type': 'mpesa', 'is_active': True},
                {'name': 'Bank Transfer', 'method_type': 'bank', 'is_active': True},
                {'name': 'Credit Card', 'method_type': 'card', 'is_active': True},
            ]
            
            for method_data in default_payment_methods:
                PaymentMethod.objects.get_or_create(
                    name=method_data['name'],
                    defaults=method_data
                )
            
            print(f"✓ Created default payment methods")
            
            # Create default service categories
            try:
                from apps.services.models import ServiceCategory
                
                default_categories = [
                    {'name': 'Exterior Wash', 'description': 'External car washing services'},
                    {'name': 'Interior Cleaning', 'description': 'Interior car cleaning services'},
                    {'name': 'Full Service', 'description': 'Complete car wash and detailing'},
                    {'name': 'Detailing', 'description': 'Professional car detailing services'},
                ]
                
                for cat_data in default_categories:
                    ServiceCategory.objects.get_or_create(
                        name=cat_data['name'],
                        defaults=cat_data
                    )
                
                print(f"✓ Created default service categories")
                
            except Exception as e:
                print(f"Warning: Could not create service categories: {e}")
            
            # Create default expense categories
            try:
                from apps.expenses.models import ExpenseCategory
                
                default_expense_categories = [
                    {'name': 'Employee Salaries', 'description': 'Staff salary payments', 'is_auto_category': True},
                    {'name': 'Utilities', 'description': 'Water, electricity, internet'},
                    {'name': 'Supplies', 'description': 'Cleaning supplies and materials'},
                    {'name': 'Equipment', 'description': 'Equipment purchases and maintenance'},
                    {'name': 'Marketing', 'description': 'Marketing and advertising expenses'},
                ]
                
                for cat_data in default_expense_categories:
                    ExpenseCategory.objects.get_or_create(
                        name=cat_data['name'],
                        defaults=cat_data
                    )
                
                print(f"✓ Created default expense categories")
                
            except Exception as e:
                print(f"Warning: Could not create expense categories: {e}")
                
    except Exception as e:
        print(f"Error setting up default tenant data: {e}")
        raise


@login_required
@user_passes_test(lambda u: u.is_superuser)
def check_tenant_database_status(request, business_id):
    """
    Check the database status for a specific tenant
    Returns JSON with status information
    """
    try:
        business = get_object_or_404(Tenant, id=business_id)
        
        status = {
            'business_name': business.name,
            'database_exists': False,
            'database_accessible': False,
            'migrations_applied': False,
            'owner_employee_exists': False,
            'tenant_settings_exists': False,
            'error_message': None
        }
        
        try:
            # Check if database configuration exists
            from django.conf import settings
            db_alias = f"tenant_{business.id}"
            
            if db_alias in settings.DATABASES:
                status['database_exists'] = True
                
                # Check if database is accessible
                from django.db import connections
                try:
                    with connections[db_alias].cursor() as cursor:
                        cursor.execute("SELECT 1")
                    status['database_accessible'] = True
                    
                    # Check if migrations are applied (check for core tables)
                    with connections[db_alias].cursor() as cursor:
                        cursor.execute("SHOW TABLES LIKE 'django_migrations'")
                        if cursor.fetchone():
                            status['migrations_applied'] = True
                    
                    # Check if owner employee record exists
                    try:
                        with tenant_context(business):
                            from apps.employees.models import Employee
                            owner_employee = Employee.objects.filter(
                                user_id=business.owner.id,
                                is_active=True
                            ).first()
                            status['owner_employee_exists'] = bool(owner_employee)
                            
                            # Check if tenant settings exist
                            from apps.core.tenant_models import TenantSettings
                            tenant_settings = TenantSettings.objects.first()
                            status['tenant_settings_exists'] = bool(tenant_settings)
                            
                    except Exception as e:
                        status['error_message'] = f"Error checking tenant data: {str(e)}"
                        
                except Exception as e:
                    status['error_message'] = f"Database connection error: {str(e)}"
            else:
                status['error_message'] = "Database configuration not found"
                
        except Exception as e:
            status['error_message'] = f"Configuration error: {str(e)}"
        
        return JsonResponse(status)
        
    except Exception as e:
        return JsonResponse({
            'error': f"Failed to check tenant status: {str(e)}"
        }, status=500)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def repair_tenant_setup(request, business_id):
    """
    Attempt to repair/complete tenant setup for a business
    """
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('system_admin:business_management')
    
    try:
        business = get_object_or_404(Tenant, id=business_id)
        
        if not business.is_approved:
            messages.error(request, 'Business must be approved before setup can be completed.')
            return redirect('system_admin:business_management')
        
        # Attempt to complete the setup
        success = setup_tenant_after_approval(business, request.user)
        
        if success:
            # Log the activity
            AdminActivity.objects.create(
                admin=request.user,
                action=f"Repaired tenant setup for '{business.name}'"
            )
            
            messages.success(request, f'Tenant setup completed successfully for {business.name}.')
        else:
            messages.error(request, f'Failed to complete tenant setup for {business.name}.')
            
    except Exception as e:
        messages.error(request, f"Error repairing tenant setup: {str(e)}")
    
    return redirect('system_admin:business_management')


@login_required
@user_passes_test(lambda u: u.is_superuser)
def edit_business(request, business_id):
    """Edit business details"""
    business = get_object_or_404(Tenant, id=business_id)
    
    if request.method == 'POST':
        try:
            # Update business fields
            business.name = request.POST.get('name')
            business.slug = request.POST.get('slug')
            business.business_type = request.POST.get('business_type')
            business.description = request.POST.get('description', '')
            business.phone = request.POST.get('phone', '')
            business.email = request.POST.get('email', '')
            business.address = request.POST.get('address', '')
            business.city = request.POST.get('city', '')
            business.country = request.POST.get('country', '')
            business.is_approved = bool(request.POST.get('is_approved'))
            
            business.save()
            
            # Log the activity
            AdminActivity.objects.create(
                admin=request.user,
                action=f"Updated business '{business.name}'"
            )
            
            messages.success(request, f'Business "{business.name}" updated successfully!')
            return redirect('system_admin:business_management')
            
        except Exception as e:
            messages.error(request, f'Error updating business: {str(e)}')
    
    # Get business type choices (you might need to import these from the model)
    business_types = [
        ('car_wash', 'Car Wash'),
        ('detailing', 'Auto Detailing'),
        ('service_center', 'Service Center'),
        ('other', 'Other'),
    ]
    
    context = {
        'business': business,
        'business_types': business_types,
    }
    return render(request, 'system_admin/edit_business.html', context)
