from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Q, Count, Sum
from django.core.paginator import Paginator
from apps.core.tenant_models import Tenant
from apps.subscriptions.models import Subscription, SubscriptionPlan, Payment

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
    """Approve a business application with subscription setup"""
    business = get_object_or_404(Tenant, id=business_id)
    
    if request.method == 'POST':
        # Get the subscription plan from the form
        plan_id = request.POST.get('subscription_plan')
        if plan_id:
            try:
                plan = SubscriptionPlan.objects.get(id=plan_id)
                
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
                        status='trial',  # Start with trial
                        start_date=timezone.now().date(),
                        end_date=(timezone.now() + timezone.timedelta(days=plan.trial_days if hasattr(plan, 'trial_days') else 14)).date(),
                        amount=plan.price
                    )
                    business.subscription = subscription
                    business.save()
                
                messages.success(request, f'Business "{business.name}" has been approved and subscription activated.')
                
                # TODO: Send approval notification email/SMS
                # TODO: Setup tenant database
                
                return redirect('system_admin:dashboard')
                
            except SubscriptionPlan.DoesNotExist:
                messages.error(request, 'Invalid subscription plan selected.')
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
        if rejection_reason:
            business.is_approved = False
            business.is_active = False
            business.rejection_reason = rejection_reason
            business.rejected_by = request.user
            business.rejected_at = timezone.now()
            business.save()
            
            messages.success(request, f'Business "{business.name}" has been rejected.')
            
            # TODO: Send rejection notification email/SMS
            
            return redirect('system_admin:dashboard')
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
    business_types = Tenant.BUSINESS_TYPE_CHOICES
    
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
    subscriptions = Subscription.objects.select_related('business', 'plan').prefetch_related('payment_set')
    
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
        'method_choices': Payment.PAYMENT_METHOD_CHOICES,
        'current_status': status_filter,
        'current_method': method_filter,
        'current_search': search,
        'title': 'Payment Management'
    }
    
    return render(request, 'system_admin/payment_management.html', context)
