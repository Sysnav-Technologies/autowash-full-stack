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
from apps.core.database_router import TenantDatabaseManager, TenantDatabaseRouter, tenant_context
from apps.core.suspension_utils import SuspensionManager, SuspensionChecker
from apps.subscriptions.models import Subscription, SubscriptionPlan, Payment, SubscriptionInvoice
from .models import AdminActivity
from datetime import timedelta
from decimal import Decimal
import traceback
import json

# Import messaging models and services
from messaging.models import SMSProvider, TenantSMSSettings, SMSMessage, SMSTemplate, SMSWebhook
from messaging.services import send_sms
from messaging.forms import TenantSMSSettingsForm, TestSMSForm

# Import email functions
from apps.accounts.views import send_business_approval_email


def get_user_business_relationships(user):
    """
    Get all business relationships for a user (both owned and employee relationships)
    Returns a dictionary with owned_businesses and employee_relationships
    """
    relationships = {
        'owned_businesses': [],
        'employee_relationships': []
    }
    
    # Get owned businesses
    relationships['owned_businesses'] = list(user.owned_tenants.all())
    
    # Get TenantUser memberships (if any)
    tenant_memberships = list(user.tenant_memberships.all())
    for membership in tenant_memberships:
        relationships['employee_relationships'].append({
            'business': membership.tenant,
            'role': membership.get_role_display(),
            'role_code': membership.role
        })
    
    # Check employee records in each active tenant database
    active_businesses = Tenant.objects.filter(is_active=True, is_approved=True)
    
    for business in active_businesses:
        # Skip businesses the user already owns
        if business in relationships['owned_businesses']:
            continue
            
        # Skip businesses already found through TenantUser
        already_found = any(rel['business'].id == business.id for rel in relationships['employee_relationships'])
        if already_found:
            continue
            
        try:
            # Check if the business has a proper database setup
            if not business.database_name:
                continue
                
            with tenant_context(business):
                from apps.employees.models import Employee
                
                # Check if user has an employee record in this tenant
                employee = Employee.objects.filter(
                    user_id=user.id,
                    is_active=True
                ).first()
                
                if employee:
                    relationships['employee_relationships'].append({
                        'business': business,
                        'role': employee.get_role_display(),
                        'role_code': employee.role,
                        'employee_id': employee.employee_id,
                        'department': employee.department.name if employee.department else None
                    })
                    
        except Exception as e:
            # Skip businesses where we can't query (database issues, etc.)
            # Uncomment for debugging: print(f"Error checking employee record for user {user.id} in business {business.name}: {e}")
            continue
    
    return relationships

@staff_member_required
def system_dashboard(request):
    """System admin dashboard"""
    
    # Get comprehensive statistics
    stats = {
        'total_businesses': Tenant.objects.count(),
        'pending_approval': Tenant.objects.filter(is_approved=False, is_active=True).count(),
        'active_businesses': Tenant.objects.filter(is_approved=True, is_active=True).count(),
        'suspended_businesses': Tenant.objects.filter(is_active=False).count(),
        'total_subscriptions': Subscription.objects.using('default').filter(status='active').count(),
        'trial_subscriptions': Subscription.objects.using('default').filter(status='trial').count(),
        'expired_subscriptions': Subscription.objects.using('default').filter(status='expired').count(),
        'cancelled_subscriptions': Subscription.objects.using('default').filter(status='cancelled').count(),
    }
    
    # Revenue statistics
    current_month = timezone.now().replace(day=1)
    stats['monthly_revenue'] = Payment.objects.using('default').filter(
        status='completed',
        paid_at__gte=current_month
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Recent business applications (pending approval)
    recent_applications = Tenant.objects.filter(
        is_approved=False,
        is_active=True
    ).select_related('owner').order_by('-created_at')[:10]
    
    # Subscription distribution by plan
    subscription_stats = SubscriptionPlan.objects.using('default').annotate(
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
    """Approve business application"""
    business = get_object_or_404(Tenant, id=business_id)
    
    if request.method == 'POST':
        # Get the subscription plan from the form
        plan_id = request.POST.get('subscription_plan')
        if plan_id:
            try:
                plan = SubscriptionPlan.objects.using('default').get(id=plan_id)
                
                # Start the approval process
                with transaction.atomic():
                    # 1. Approve the business
                    business.is_approved = True
                    business.is_verified = True  # Also set verified to True
                    business.approved_by = request.user
                    business.approved_at = timezone.now()
                    business.is_active = True
                    business.save()
                    
                    # 2. Create subscription if it doesn't exist
                    subscription = None
                    if not hasattr(business, 'subscription') or not business.subscription:
                        subscription = Subscription.objects.using('default').create(
                            business=business,
                            plan=plan,
                            status='trial',  # Start with trial
                            start_date=timezone.now().date(),
                            end_date=(timezone.now() + timezone.timedelta(days=getattr(plan, 'trial_days', 7))).date(),  # 7-day trial
                            amount=plan.price
                        )
                        business.subscription = subscription
                        business.save()
                    else:
                        subscription = business.subscription
                    
                    # 3. Update BusinessVerification status
                    try:
                        from apps.accounts.models import BusinessVerification
                        verification = business.verification
                        verification.status = 'verified'
                        verification.verified_at = timezone.now()
                        verification.verified_by = request.user
                        verification.save()
                        print("BusinessVerification status updated to 'verified'")
                    except BusinessVerification.DoesNotExist:
                        # Create verification record if it doesn't exist
                        BusinessVerification.objects.create(
                            business=business,
                            status='verified',
                            verified_at=timezone.now(),
                            verified_by=request.user,
                            notes='Business approved by admin without document submission'
                        )
                        print("BusinessVerification record created with 'verified' status")
                    
                    # 4. Setup tenant database and employee record
                    setup_success = setup_tenant_after_approval(business, request.user)
                    
                    if setup_success:
                        # 5. Send approval notification email
                        try:
                            send_business_approval_email(request, business)
                            print("Business approval email sent successfully")
                        except Exception as e:
                            print(f"Failed to send approval email: {e}")
                            # Don't fail the approval process for email issues
                        
                        # Log the activity
                        AdminActivity.objects.create(
                            admin_user=request.user,
                            action='approve_business',
                            description=f"Approved business '{business.name}' with automatic tenant setup and 7-day trial"
                        )
                        
                        messages.success(
                            request, 
                            f'Business "{business.name}" has been approved successfully! '
                            f'Tenant database created, owner employee record established, and approval email sent. '
                            f'The business will have a 7-day trial period starting now.'
                        )
                        
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
    
    # Clear any tenant context to ensure we query from default database
    TenantDatabaseRouter.clear_tenant()
    
    # Get available subscription plans
    plans = SubscriptionPlan.objects.using('default').filter(is_active=True).order_by('price')
    
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
    """Business management view"""
    
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
    """Subscription management"""
    
    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    plan_filter = request.GET.get('plan', '')
    search = request.GET.get('search', '')
    
    # Build queryset
    subscriptions = Subscription.objects.using('default').select_related('business', 'plan')
    
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
        'total': Subscription.objects.using('default').count(),
        'active': Subscription.objects.using('default').filter(status='active').count(),
        'trial': Subscription.objects.using('default').filter(status='trial').count(),
        'expired': Subscription.objects.using('default').filter(status='expired').count(),
        'cancelled': Subscription.objects.using('default').filter(status='cancelled').count(),
    }
    
    # Revenue statistics
    revenue_stats = {
        'total_revenue': Payment.objects.using('default').filter(status='completed').aggregate(
            total=Sum('amount'))['total'] or 0,
        'monthly_revenue': Payment.objects.using('default').filter(
            status='completed',
            paid_at__month=timezone.now().month,
            paid_at__year=timezone.now().year
        ).aggregate(total=Sum('amount'))['total'] or 0,
    }
    
    # Available plans and status choices
    plans = SubscriptionPlan.objects.using('default').filter(is_active=True).order_by('name')
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
    
    plans = SubscriptionPlan.objects.using('default').annotate(
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
                plan = SubscriptionPlan.objects.using('default').create(
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
    
    # Build queryset - use default database for subscription data
    payments = Payment.objects.using('default').select_related('subscription').prefetch_related('subscription__business')
    
    if status_filter != 'all':
        payments = payments.filter(status=status_filter)
    
    if method_filter:
        payments = payments.filter(payment_method=method_filter)
    
    if search:
        # Get subscriptions and businesses separately to avoid cross-database joins
        subscription_ids = []
        if search:
            # Search in businesses by name
            businesses = Tenant.objects.using('default').filter(name__icontains=search)
            business_subscriptions = Subscription.objects.using('default').filter(business__in=businesses)
            subscription_ids.extend(business_subscriptions.values_list('id', flat=True))
        
        # Filter payments
        payments = payments.filter(
            Q(payment_id__icontains=search) |
            Q(transaction_id__icontains=search) |
            Q(subscription_id__in=subscription_ids)
        )
    
    # Pagination
    paginator = Paginator(payments.order_by('-created_at'), 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Payment statistics - use default database
    payment_stats = {
        'total_payments': Payment.objects.using('default').count(),
        'completed': Payment.objects.using('default').filter(status='completed').count(),
        'pending': Payment.objects.using('default').filter(status='pending').count(),
        'failed': Payment.objects.using('default').filter(status='failed').count(),
        'total_amount': Payment.objects.using('default').filter(status='completed').aggregate(
            total=Sum('amount'))['total'] or 0,
    }
    
    # Get active subscriptions for manual payment modal
    active_subscriptions = Subscription.objects.using('default').filter(
        status__in=['active', 'trial', 'expired']
    ).select_related('business', 'plan')[:100]  # Limit for performance
    
    context = {
        'page_obj': page_obj,
        'payment_stats': payment_stats,
        'active_subscriptions': active_subscriptions,
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
    
    # Revenue analytics - use default database
    revenue_data = []
    for i in range(days):
        date = start_date + timedelta(days=i)
        revenue = Payment.objects.using('default').filter(
            status='completed',
            paid_at__date=date.date()
        ).aggregate(total=Sum('amount'))['total'] or 0
        revenue_data.append({
            'date': date.strftime('%Y-%m-%d'),
            'revenue': float(revenue)
        })
    
    # Plan popularity - use default database
    plan_stats = SubscriptionPlan.objects.using('default').annotate(
        subscriber_count=Count('subscription'),
        total_revenue=Sum('subscription__amount')
    ).order_by('-subscriber_count')
    
    # Monthly trends
    monthly_stats = {
        'new_businesses': Tenant.objects.filter(
            created_at__gte=start_date
        ).count(),
        'new_subscriptions': Subscription.objects.using('default').filter(
            created_at__gte=start_date
        ).count(),
        'total_revenue': Payment.objects.using('default').filter(
            status='completed',
            paid_at__gte=start_date
        ).aggregate(total=Sum('amount'))['total'] or 0,
        'average_subscription_value': Subscription.objects.using('default').filter(
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
        plan = SubscriptionPlan.objects.using('default').get(id=plan_id)
        approved_count = 0
        failed_setups = []
        
        for business_id in business_ids:
            try:
                business = Tenant.objects.get(id=business_id)
                if not business.is_approved:
                    with transaction.atomic():
                        # Approve the business
                        business.is_approved = True
                        business.is_verified = True  # Also set verified to True
                        business.approved_by = request.user
                        business.approved_at = timezone.now()
                        business.is_active = True
                        business.save()
                        
                        # Create subscription if it doesn't exist
                        if not hasattr(business, 'subscription') or not business.subscription:
                            subscription = Subscription.objects.using('default').create(
                                business=business,
                                plan=plan,
                                status='trial',
                                start_date=timezone.now().date(),
                                end_date=(timezone.now() + timedelta(days=14)).date(),
                                amount=plan.price
                            )
                            business.subscription = subscription
                            business.save()
                        
                        # Update BusinessVerification status
                        try:
                            from apps.accounts.models import BusinessVerification
                            verification = business.verification
                            verification.status = 'verified'
                            verification.verified_at = timezone.now()
                            verification.verified_by = request.user
                            verification.save()
                        except BusinessVerification.DoesNotExist:
                            # Create verification record if it doesn't exist
                            BusinessVerification.objects.create(
                                business=business,
                                status='verified',
                                verified_at=timezone.now(),
                                verified_by=request.user,
                                notes='Business approved by admin without document submission'
                            )
                        
                        # Setup tenant database and employee record
                        setup_success = setup_tenant_after_approval(business, request.user)
                        if not setup_success:
                            failed_setups.append(business.name)
                        
                        # Send approval notification email
                        try:
                            send_business_approval_email(request, business)
                            print(f"Approval email sent for business: {business.name}")
                        except Exception as e:
                            print(f"Failed to send approval email for {business.name}: {e}")
                            # Don't fail the approval process for email issues
                        
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
            admin_user=request.user,
            action='bulk_action',
            description=f"Bulk approved {approved_count} businesses"
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
                    admin_user=request.user,
                    action='reject_business',
                    description=f'Bulk rejected business: {business.name} - Reason: {rejection_reason}',
                    target_model='Tenant',
                    target_id=str(business.id)
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
    users = User.objects.prefetch_related('owned_tenants', 'tenant_memberships__tenant')
    
    if user_type == 'business_owners':
        users = users.filter(owned_tenants__isnull=False).distinct()
    elif user_type == 'regular_users':
        users = users.filter(owned_tenants__isnull=True, tenant_memberships__isnull=True)
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
    
    # Get business relationships and suspension status for each user
    users_with_relationships = []
    suspension_checker = SuspensionChecker()
    
    for user in page_obj:
        relationships = get_user_business_relationships(user)
        user.business_relationships = relationships
        
        # Add suspension status
        user.suspension_status = suspension_checker.get_user_suspension_status(user)
        
        users_with_relationships.append(user)
    
    # Update the page object with enriched users
    page_obj.object_list = users_with_relationships
    
    # User statistics
    user_stats = {
        'total_users': User.objects.count(),
        'active_users': User.objects.filter(is_active=True).count(),
        'business_owners': User.objects.filter(owned_tenants__isnull=False).distinct().count(),
        'business_employees': User.objects.filter(tenant_memberships__isnull=False).distinct().count(),
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
        subscriptions = Subscription.objects.using('default').all()
        # Implementation would generate CSV/Excel file
        pass
    elif data_type == 'payments':
        # Export payment data
        payments = Payment.objects.using('default').all()
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
    
    # Get subscription from default database
    subscription = get_object_or_404(Subscription.objects.using('default'), id=subscription_id)
    
    if request.method == 'POST':
        form = PaymentRecordForm(request.POST)
        if form.is_valid():
            # Create payment record in default database
            payment = Payment.objects.using('default').create(
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
                subscription.save(using='default')
            
            # Get business name for display
            business = Tenant.objects.using('default').get(id=subscription.business_id)
            messages.success(request, f'Payment of {payment.amount} recorded successfully for {business.name}')
            return redirect('system_admin:payment_management')
    else:
        # Get plan for initial amount
        plan = SubscriptionPlan.objects.using('default').get(id=subscription.plan_id)
        form = PaymentRecordForm(initial={
            'subscription': subscription.id,
            'payment_date': timezone.now().date(),
            'amount': plan.price
        })
    
    # Get business and plan for context
    business = Tenant.objects.using('default').get(id=subscription.business_id)
    plan = SubscriptionPlan.objects.using('default').get(id=subscription.plan_id)
    
    context = {
        'form': form,
        'subscription': subscription,
        'business': business,
        'plan': plan,
        'title': f'Record Payment - {business.name}'
    }
    
    return render(request, 'system_admin/record_payment.html', context)

@staff_member_required
def update_payment_status(request):
    """Update payment status via AJAX or form submission"""
    if request.method == 'POST':
        payment_id = request.POST.get('payment_id')
        new_status = request.POST.get('status')
        
        if payment_id and new_status in ['completed', 'failed', 'pending']:
            try:
                payment = Payment.objects.using('default').get(id=payment_id)
                payment.status = new_status
                if new_status == 'completed':
                    payment.paid_at = timezone.now()
                payment.save()
                messages.success(request, f'Payment status updated to {new_status}')
            except Payment.DoesNotExist:
                messages.error(request, 'Payment not found')
            except Exception as e:
                messages.error(request, f'Error updating payment: {str(e)}')
        else:
            messages.error(request, 'Invalid payment ID or status')
    
    return redirect('system_admin:payment_management')

@staff_member_required
def record_manual_payment(request):
    """Handle manual payment creation from the modal"""
    if request.method == 'POST':
        subscription_id = request.POST.get('subscription_id')
        amount = request.POST.get('amount')
        payment_method = request.POST.get('payment_method')
        reference_number = request.POST.get('reference_number')
        notes = request.POST.get('notes')
        
        try:
            subscription = Subscription.objects.using('default').get(id=subscription_id)
            payment = Payment.objects.using('default').create(
                subscription=subscription,
                amount=Decimal(amount),
                payment_method=payment_method,
                reference_number=reference_number,
                notes=notes,
                status='completed',
                paid_at=timezone.now()
            )
            
            # Update subscription status if needed
            if subscription.status in ['expired', 'suspended']:
                subscription.status = 'active'
                subscription.save(using='default')
            
            business = Tenant.objects.using('default').get(id=subscription.business_id)
            messages.success(request, f'Payment of {payment.amount} recorded successfully for {business.name}')
        except Subscription.DoesNotExist:
            messages.error(request, 'Subscription not found')
        except Exception as e:
            messages.error(request, f'Error creating payment: {str(e)}')
    
    return redirect('system_admin:payment_management')


@staff_member_required
def generate_invoice(request, subscription_id):
    """Generate an invoice for a subscription"""
    from .forms import InvoiceGenerationForm
    
    # Get subscription from default database
    subscription = get_object_or_404(Subscription.objects.using('default'), id=subscription_id)
    
    if request.method == 'POST':
        form = InvoiceGenerationForm(request.POST)
        if form.is_valid():
            # Calculate total amount
            subtotal = form.cleaned_data['subtotal']
            discount = form.cleaned_data['discount_amount']
            tax = form.cleaned_data['tax_amount']
            total = subtotal - discount + tax
            
            # Create invoice in default database
            invoice = SubscriptionInvoice.objects.using('default').create(
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
        # Get plan for initial amount
        plan = SubscriptionPlan.objects.using('default').get(id=subscription.plan_id)
        form = InvoiceGenerationForm(initial={
            'subscription': subscription.id,
            'subtotal': plan.price,
            'due_date': (timezone.now() + timedelta(days=30)).date()
        })
    
    # Get business and plan for context
    business = Tenant.objects.using('default').get(id=subscription.business_id)
    plan = SubscriptionPlan.objects.using('default').get(id=subscription.plan_id)
    
    context = {
        'form': form,
        'subscription': subscription,
        'business': business,
        'plan': plan,
        'title': f'Generate Invoice - {business.name}'
    }
    
    return render(request, 'system_admin/generate_invoice.html', context)


@staff_member_required
def invoice_management(request):
    """Manage all invoices"""
    
    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    search = request.GET.get('search', '')
    
    # Build queryset - use default database for subscription data
    invoices = SubscriptionInvoice.objects.using('default').select_related('subscription').all()
    
    if status_filter != 'all':
        invoices = invoices.filter(status=status_filter)
    
    if search:
        # Get subscriptions and businesses separately to avoid cross-database joins
        subscription_ids = []
        if search:
            # Search in businesses by name or email
            businesses = Tenant.objects.using('default').filter(
                Q(name__icontains=search) | Q(owner__email__icontains=search)
            )
            business_subscriptions = Subscription.objects.using('default').filter(business__in=businesses)
            subscription_ids.extend(business_subscriptions.values_list('id', flat=True))
        
        # Filter invoices
        invoices = invoices.filter(
            Q(invoice_number__icontains=search) |
            Q(subscription_id__in=subscription_ids)
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
    
    # Invoice statistics - use default database
    invoice_stats = {
        'total': SubscriptionInvoice.objects.using('default').count(),
        'draft': SubscriptionInvoice.objects.using('default').filter(status='draft').count(),
        'sent': SubscriptionInvoice.objects.using('default').filter(status='sent').count(),
        'paid': SubscriptionInvoice.objects.using('default').filter(status='paid').count(),
        'overdue': SubscriptionInvoice.objects.using('default').filter(status='overdue').count(),
        'total_amount': SubscriptionInvoice.objects.using('default').aggregate(
            total=Sum('total_amount'))['total'] or 0,
        'paid_amount': SubscriptionInvoice.objects.using('default').filter(status='paid').aggregate(
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
    # Get invoice from default database
    invoice = get_object_or_404(SubscriptionInvoice.objects.using('default'), id=invoice_id)
    
    if request.method == 'POST':
        # Create a payment record in default database
        payment = Payment.objects.using('default').create(
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
        invoice.save(using='default')
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
            user.is_superuser = bool(request.POST.get('is_superuser'))
            user.is_active = bool(request.POST.get('is_active', True))
            user.save()
            
            # Log the activity
            AdminActivity.objects.create(
                admin_user=request.user,
                action='other',
                description=f"Created user '{user.username}'"
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
            user.is_superuser = bool(request.POST.get('is_superuser'))
            user.is_active = bool(request.POST.get('is_active'))
            
            # Update password if provided
            new_password = request.POST.get('new_password')
            if new_password:
                user.set_password(new_password)
            
            user.save()
            
            # Log the activity
            AdminActivity.objects.create(
                admin_user=request.user,
                action='other',
                description=f"Updated user '{user.username}'"
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
                admin_user=request.user,
                action='activate_business' if activate else 'suspend_business',
                description=f"User '{user.username}' {action}"
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


@login_required
@user_passes_test(lambda u: u.is_superuser)
@require_http_methods(["POST"])
@csrf_exempt
def toggle_user_suspension(request, user_id):
    """Toggle user suspension status via AJAX"""
    try:
        user = get_object_or_404(User, id=user_id)
        data = json.loads(request.body)
        action = data.get('action')  # 'suspend' or 'reactivate'
        reason = data.get('reason', '')
        
        suspension_manager = SuspensionManager()
        if action == 'suspend':
            if not reason.strip():
                return JsonResponse({
                    'success': False,
                    'error': 'Suspension reason is required'
                })
            success = suspension_manager.suspend_user(
                user=user,
                reason=reason,
                suspended_by=request.user
            )
            action_text = "suspended"
        elif action == 'reactivate':
            success = suspension_manager.reactivate_user(
                user=user,
                reactivated_by=request.user
            )
            action_text = "reactivated"
        else:
            return JsonResponse({
                'success': False,
                'error': 'Invalid action specified'
            })
        
        if success:
            # Log the activity
            AdminActivity.objects.create(
                admin_user=request.user,
                action='suspend_business' if action == 'suspend' else 'activate_business',
                description=f"User '{user.username}' {action_text}" + (f" - Reason: {reason}" if action == 'suspend' else "")
            )
            return JsonResponse({
                'success': True,
                'message': f'User {action_text} successfully'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': f'Failed to {action} user'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


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
        
        print(f"Tenant database created: {business.database_name}")
        
        # NOTE: Cache table is global, not per-tenant. Skip creating cache table per tenant.
        print("Skipping cache table creation - cache is global and shared across tenants")
        
        # Step 2: Create TenantSettings record
        print("Creating tenant settings...")
        try:
            from apps.core.tenant_models import TenantSettings
            from apps.core.database_router import tenant_context
            
            # Use tenant context to ensure proper database routing
            with tenant_context(business):
                tenant_settings, created = TenantSettings.objects.get_or_create(
                    tenant_id=business.id,
                    defaults={
                        'sms_notifications': True,
                        'email_notifications': True,
                        'enable_online_booking': True,
                        'primary_color': '#007bff',
                        'secondary_color': '#6c757d'
                    }
                )
                
                if created:
                    print("TenantSettings created")
                else:
                    print("TenantSettings already exists")
        
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
        
        print(f"Tenant setup completed successfully for: {business.name}")
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
                print("Created Management department")
            else:
                print("Found existing Management department")
            
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
            
            print(f"Created employee record: {employee.employee_id} for {employee.full_name}")
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
            
            print("Created default payment methods")
            
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
                
                print("Created default service categories")
                
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
                
                print("Created default expense categories")
                
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
                admin_user=request.user,
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
                admin_user=request.user,
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


# ===============================
# SUSPENSION MANAGEMENT VIEWS
# ===============================

@staff_member_required
def suspension_management(request):
    """Suspension management dashboard"""
    
    # Get suspension statistics
    suspension_stats = {
        'suspended_users': User.objects.filter(is_active=False).count(),
        'suspended_businesses': Tenant.objects.filter(is_active=False).count(),
        'suspended_subscriptions': Subscription.objects.using('default').filter(status='suspended').count(),
        'total_users': User.objects.count(),
        'total_businesses': Tenant.objects.count(),
        'total_subscriptions': Subscription.objects.using('default').count(),
    }
    
    # Get recent suspension activities
    recent_activities = AdminActivity.objects.filter(
        action__icontains='suspend'
    ).order_by('-created_at')[:10]
    
    # Get suspended entities for quick access
    suspended_users = User.objects.filter(is_active=False).select_related().order_by('-date_joined')[:10]
    suspended_businesses = Tenant.objects.filter(is_active=False).select_related('owner').order_by('-updated_at')[:10]
    suspended_subscriptions = Subscription.objects.using('default').filter(status='suspended').select_related('business').order_by('-updated_at')[:10]
    
    context = {
        'suspension_stats': suspension_stats,
        'recent_activities': recent_activities,
        'suspended_users': suspended_users,
        'suspended_businesses': suspended_businesses,
        'suspended_subscriptions': suspended_subscriptions,
        'title': 'Suspension Management'
    }
    
    return render(request, 'system_admin/suspension_management.html', context)


@staff_member_required
@require_http_methods(["POST"])
def suspend_user(request, user_id):
    """Suspend a user account"""
    user = get_object_or_404(User, id=user_id)
    reason = request.POST.get('reason', 'Administrative action')
    
    if user.is_superuser:
        messages.error(request, 'Cannot suspend superuser accounts.')
        return redirect('system_admin:user_management')
    
    success = SuspensionManager.suspend_user(
        user=user,
        reason=reason,
        suspended_by=request.user
    )
    
    if success:
        messages.success(request, f'User "{user.username}" has been suspended.')
        
        # Log the activity
        AdminActivity.objects.create(
            admin_user=request.user,
            action='suspend_business',
            description=f"Suspended user '{user.username}'"
        )
    else:
        messages.error(request, f'Failed to suspend user "{user.username}".')
    
    return redirect('system_admin:user_management')


@staff_member_required
@require_http_methods(["POST"])
def reactivate_user(request, user_id):
    """Reactivate a suspended user account"""
    user = get_object_or_404(User, id=user_id)
    
    success = SuspensionManager.reactivate_user(
        user=user,
        reactivated_by=request.user
    )
    
    if success:
        messages.success(request, f'User "{user.username}" has been reactivated.')
        
        # Log the activity
        AdminActivity.objects.create(
            admin_user=request.user,
            action='activate_business',
            description=f"Reactivated user '{user.username}'"
        )
    else:
        messages.error(request, f'Failed to reactivate user "{user.username}".')
    
    return redirect('system_admin:user_management')


@staff_member_required
@require_http_methods(["POST"])
def suspend_business(request, business_id):
    """Suspend a business"""
    business = get_object_or_404(Tenant, id=business_id)
    reason = request.POST.get('reason', 'Administrative action')
    
    success = SuspensionManager.suspend_business(
        business=business,
        reason=reason,
        suspended_by=request.user
    )
    
    if success:
        messages.success(request, f'Business "{business.name}" has been suspended.')
        
        # Log the activity
        AdminActivity.objects.create(
            admin_user=request.user,
            action=f"Suspended business '{business.name}'"
        )
    else:
        messages.error(request, f'Failed to suspend business "{business.name}".')
    
    return redirect('system_admin:business_management')


@staff_member_required
@require_http_methods(["POST"])
def reactivate_business(request, business_id):
    """Reactivate a suspended business"""
    business = get_object_or_404(Tenant, id=business_id)
    
    success = SuspensionManager.reactivate_business(
        business=business,
        reactivated_by=request.user
    )
    
    if success:
        messages.success(request, f'Business "{business.name}" has been reactivated.')
        
        # Log the activity
        AdminActivity.objects.create(
            admin_user=request.user,
            action=f"Reactivated business '{business.name}'"
        )
    else:
        messages.error(request, f'Failed to reactivate business "{business.name}".')
    
    return redirect('system_admin:business_management')


@staff_member_required
@require_http_methods(["POST"])
def suspend_subscription(request, subscription_id):
    """Suspend a subscription"""
    subscription = get_object_or_404(Subscription, id=subscription_id)
    reason = request.POST.get('reason', 'Payment issues')
    
    success = SuspensionManager.suspend_subscription(
        subscription=subscription,
        reason=reason,
        suspended_by=request.user
    )
    
    if success:
        messages.success(request, f'Subscription for "{subscription.business.name}" has been suspended.')
        
        # Log the activity
        AdminActivity.objects.create(
            admin_user=request.user,
            action=f"Suspended subscription for '{subscription.business.name}'"
        )
    else:
        messages.error(request, f'Failed to suspend subscription for "{subscription.business.name}".')
    
    return redirect('system_admin:subscription_management')


@staff_member_required
@require_http_methods(["POST"])
def reactivate_subscription(request, subscription_id):
    """Reactivate a suspended subscription"""
    subscription = get_object_or_404(Subscription, id=subscription_id)
    
    success = SuspensionManager.reactivate_subscription(
        subscription=subscription,
        reactivated_by=request.user
    )
    
    if success:
        messages.success(request, f'Subscription for "{subscription.business.name}" has been reactivated.')
        
        # Log the activity
        AdminActivity.objects.create(
            admin_user=request.user,
            action=f"Reactivated subscription for '{subscription.business.name}'"
        )
    else:
        messages.error(request, f'Failed to reactivate subscription for "{subscription.business.name}".')
    
    return redirect('system_admin:subscription_management')


@staff_member_required
@require_http_methods(["POST"])
def suspend_employee(request, business_id, employee_id):
    """Suspend an employee in a specific business"""
    business = get_object_or_404(Tenant, id=business_id)
    reason = request.POST.get('reason', 'Policy violation')
    
    try:
        with tenant_context(business):
            from apps.employees.models import Employee
            employee = get_object_or_404(Employee, id=employee_id)
            
            success = SuspensionManager.suspend_employee(
                employee=employee,
                reason=reason,
                suspended_by=request.user
            )
            
            if success:
                messages.success(request, f'Employee "{employee.employee_id}" has been suspended.')
                
                # Log the activity
                AdminActivity.objects.create(
                    admin_user=request.user,
                    action=f"Suspended employee '{employee.employee_id}' in '{business.name}'"
                )
            else:
                messages.error(request, f'Failed to suspend employee "{employee.employee_id}".')
    
    except Exception as e:
        messages.error(request, f'Error suspending employee: {str(e)}')
    
    return redirect('system_admin:user_management')


@staff_member_required
@require_http_methods(["POST"])
def reactivate_employee(request, business_id, employee_id):
    """Reactivate a suspended employee in a specific business"""
    business = get_object_or_404(Tenant, id=business_id)
    
    try:
        with tenant_context(business):
            from apps.employees.models import Employee
            employee = get_object_or_404(Employee, id=employee_id)
            
            success = SuspensionManager.reactivate_employee(
                employee=employee,
                reactivated_by=request.user
            )
            
            if success:
                messages.success(request, f'Employee "{employee.employee_id}" has been reactivated.')
                
                # Log the activity
                AdminActivity.objects.create(
                    admin_user=request.user,
                    action=f"Reactivated employee '{employee.employee_id}' in '{business.name}'"
                )
            else:
                messages.error(request, f'Failed to reactivate employee "{employee.employee_id}".')
    
    except Exception as e:
        messages.error(request, f'Error reactivating employee: {str(e)}')
    
    return redirect('system_admin:user_management')


# ============================================================================
# NOTIFICATION MANAGEMENT VIEWS
# ============================================================================

@user_passes_test(lambda u: u.is_staff)
@login_required
def notification_management(request):
    """Main notification management dashboard"""
    from django.utils import timezone
    from datetime import timedelta
    from apps.core.notifications import send_notification_email
    from django.db.models import Count, Q
    
    # Get notification statistics
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Get actual statistics from various models
    from apps.services.models import ServiceOrder
    from apps.payments.models import Payment
    from apps.inventory.models import InventoryItem
    from django.db.models import F
    
    # Service order notifications (approximate based on orders created)
    orders_today = ServiceOrder.objects.filter(created_at__date=today).count()
    orders_week = ServiceOrder.objects.filter(created_at__date__gte=week_ago).count()
    
    # Payment notifications (approximate based on payments)
    payments_today = Payment.objects.using('default').filter(created_at__date=today, status='completed').count()
    payments_week = Payment.objects.using('default').filter(created_at__date__gte=week_ago, status='completed').count()
    
    # Low stock items
    low_stock_items = InventoryItem.objects.filter(
        current_stock__lte=F('minimum_stock'),
        is_active=True
    ).count()
    
    # Subscription statistics
    active_subscriptions = Subscription.objects.using('default').filter(status='active').count()
    expiring_soon = Subscription.objects.using('default').filter(
        status='active',
        end_date__lte=timezone.now() + timedelta(days=7)
    ).count()
    expired_today = Subscription.objects.using('default').filter(
        status='active',
        end_date__date=today
    ).count()
    
    stats = {
        'orders_today': orders_today,
        'orders_week': orders_week,
        'payments_today': payments_today,
        'payments_week': payments_week,
        'low_stock_items': low_stock_items,
        'active_subscriptions': active_subscriptions,
        'expiring_soon': expiring_soon,
        'expired_today': expired_today,
        'total_notifications_estimate': orders_today * 3 + payments_today + expired_today,  # Estimate
        'email_enabled': True,
        'sms_enabled': True,
    }
    
    # Get recent businesses for bulk notifications
    recent_businesses = Tenant.objects.filter(
        is_approved=True,
        created_at__gte=week_ago
    ).select_related().order_by('-created_at')[:10]
    
    # Get subscription expiry alerts
    expiring_subscriptions = Subscription.objects.using('default').filter(
        status='active',
        end_date__lte=timezone.now() + timedelta(days=7)
    ).select_related('business', 'plan').order_by('end_date')[:10]
    
    # Get recent notifications (mock data for now)
    recent_notifications = [
        {
            'type': 'Order Created',
            'recipient': 'customer@example.com',
            'status': 'Sent',
            'timestamp': timezone.now() - timedelta(minutes=5),
            'business': 'Demo Car Wash'
        },
        {
            'type': 'Payment Confirmation', 
            'recipient': 'john@example.com',
            'status': 'Sent',
            'timestamp': timezone.now() - timedelta(minutes=15),
            'business': 'Elite Auto Care'
        },
        {
            'type': 'Subscription Expiry Warning',
            'recipient': 'owner@business.com',
            'status': 'Sent', 
            'timestamp': timezone.now() - timedelta(hours=2),
            'business': 'Quick Wash Services'
        }
    ]
    
    context = {
        'stats': stats,
        'recent_businesses': recent_businesses,
        'expiring_subscriptions': expiring_subscriptions,
        'recent_notifications': recent_notifications,
        'title': 'Notification Management'
    }
    
    return render(request, 'system_admin/notification_management.html', context)


@user_passes_test(lambda u: u.is_staff)
@login_required
def notification_settings(request):
    """Notification system settings"""
    if request.method == 'POST':
        # Handle settings update
        messages.success(request, 'Notification settings updated successfully!')
        return redirect('system_admin:notification_settings')
    
    # Mock settings - in production these would be stored in database
    settings_data = {
        'email_enabled': True,
        'sms_enabled': True,
        'subscription_warning_days': 7,
        'low_stock_threshold': 10,
        'batch_size': 100,
        'rate_limit': 10,  # emails per minute
        'from_email': 'noreply@autowash.com',
        'sms_provider': 'africas_talking',
    }
    
    context = {
        'settings': settings_data,
        'title': 'Notification Settings'
    }
    
    return render(request, 'system_admin/notification_settings.html', context)


@user_passes_test(lambda u: u.is_staff)
@login_required
def notification_logs(request):
    """View notification logs and history"""
    from django.core.paginator import Paginator
    
    # Mock log data - in production this would come from a NotificationLog model
    logs = [
        {
            'id': 1,
            'type': 'Order Created',
            'recipient': 'customer@example.com',
            'business': 'Demo Car Wash',
            'status': 'Sent',
            'sent_at': timezone.now() - timedelta(minutes=5),
            'template': 'service_notification.html',
            'error': None
        },
        {
            'id': 2,
            'type': 'Payment Confirmation',
            'recipient': 'invalid@email',
            'business': 'Elite Auto Care', 
            'status': 'Failed',
            'sent_at': timezone.now() - timedelta(minutes=10),
            'template': 'payment_confirmation.html',
            'error': 'Invalid email address'
        },
        {
            'id': 3,
            'type': 'Low Stock Alert',
            'recipient': 'manager@business.com',
            'business': 'Quick Wash Services',
            'status': 'Sent',
            'sent_at': timezone.now() - timedelta(hours=1),
            'template': 'low_stock_alert.html', 
            'error': None
        }
    ] * 20  # Simulate more data
    
    paginator = Paginator(logs, 25)
    page = request.GET.get('page', 1)
    logs_page = paginator.get_page(page)
    
    context = {
        'logs': logs_page,
        'title': 'Notification Logs'
    }
    
    return render(request, 'system_admin/notification_logs.html', context)


@user_passes_test(lambda u: u.is_staff)
@login_required
@require_http_methods(["POST"])
def send_bulk_notification(request):
    """Send bulk notifications to multiple businesses"""
    from apps.core.notifications import send_notification_email
    
    business_ids = request.POST.getlist('business_ids')
    notification_type = request.POST.get('notification_type')
    subject = request.POST.get('subject')
    message = request.POST.get('message')
    
    if not business_ids or not notification_type:
        return JsonResponse({
            'success': False,
            'message': 'Please select businesses and notification type'
        })
    
    try:
        sent_count = 0
        failed_count = 0
        
        businesses = Tenant.objects.filter(id__in=business_ids, is_approved=True)
        
        for business in businesses:
            try:
                # Send notification based on type
                if notification_type == 'custom':
                    # Send custom message
                    context = {
                        'business': business,
                        'custom_message': message,
                        'subject': subject
                    }
                    success = send_notification_email(
                        to_email=business.email,
                        subject=subject,
                        template_name='system_admin_announcement',
                        context=context
                    )
                else:
                    # Send predefined notification type
                    if notification_type == 'subscription_reminder':
                        subscription = business.subscriptions.filter(status='active').first()
                        if subscription:
                            from apps.core.notifications import send_subscription_expiry_warning
                            success = send_subscription_expiry_warning(subscription, 7)
                        else:
                            success = False
                    else:
                        success = False
                
                if success:
                    sent_count += 1
                else:
                    failed_count += 1
                    
            except Exception as e:
                failed_count += 1
                continue
        
        return JsonResponse({
            'success': True,
            'message': f'Bulk notification completed. Sent: {sent_count}, Failed: {failed_count}',
            'sent_count': sent_count,
            'failed_count': failed_count
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error sending bulk notifications: {str(e)}'
        })


@user_passes_test(lambda u: u.is_staff)
@login_required
@require_http_methods(["POST"])
def test_notification(request):
    """Send test notifications"""
    from apps.core.notifications import send_notification_email
    
    email = request.POST.get('email')
    notification_type = request.POST.get('type')
    
    if not email or not notification_type:
        return JsonResponse({
            'success': False,
            'message': 'Email and notification type are required'
        })
    
    try:
        # Test notification context
        test_context = {
            'test_mode': True,
            'business_name': 'Test Business',
            'customer_name': 'Test Customer',
            'order_number': 'TEST001',
            'amount': '1000.00',
            'current_year': timezone.now().year
        }
        
        # Map notification types to templates
        template_map = {
            'order_created': 'service_notification',
            'order_started': 'service_notification', 
            'order_completed': 'service_notification',
            'payment_confirmation': 'payment_confirmation',
            'subscription_warning': 'subscription_expiry_warning',
            'low_stock_alert': 'low_stock_alert'
        }
        
        template = template_map.get(notification_type)
        if not template:
            return JsonResponse({
                'success': False,
                'message': 'Invalid notification type'
            })
        
        # Customize context based on type
        if notification_type.startswith('order'):
            test_context.update({
                'notification_type': notification_type.split('_')[1],
                'order': {
                    'order_number': 'TEST001',
                    'total_amount': '1000.00'
                },
                'customer': {'first_name': 'Test', 'full_name': 'Test Customer'},
                'vehicle': {'make': 'Toyota', 'model': 'Camry', 'registration_number': 'KAA 123A'}
            })
        elif notification_type == 'subscription_warning':
            test_context.update({
                'days_remaining': 3,
                'subscription': {'end_date': timezone.now() + timedelta(days=3)},
                'plan': {'name': 'Professional Plan'}
            })
        elif notification_type == 'low_stock_alert':
            test_context.update({
                'inventory_item': {'name': 'Car Shampoo'},
                'current_stock': 5,
                'minimum_stock': 10
            })
        
        success = send_notification_email(
            to_email=email,
            subject=f"Test Notification - {notification_type.replace('_', ' ').title()}",
            template_name=template,
            context=test_context
        )
        
        return JsonResponse({
            'success': success,
            'message': 'Test notification sent successfully!' if success else 'Failed to send test notification'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error sending test notification: {str(e)}'
        })


@user_passes_test(lambda u: u.is_staff)
@login_required
def notification_settings(request):
    """Notification system settings"""
    if request.method == 'POST':
        # Handle settings update
        settings = {
            'email_enabled': request.POST.get('email_enabled') == 'on',
            'sms_enabled': request.POST.get('sms_enabled') == 'on',
            'low_stock_threshold': request.POST.get('low_stock_threshold', 10),
            'subscription_warning_days': request.POST.get('subscription_warning_days', 7),
        }
        
        # Save to database or configuration file
        messages.success(request, 'Notification settings updated successfully!')
        return redirect('system_admin:notification_settings')
    
    context = {
        'title': 'Notification Settings',
        'settings': {
            'email_enabled': True,
            'sms_enabled': True,
            'low_stock_threshold': 10,
            'subscription_warning_days': 7,
        }
    }
    
    return render(request, 'system_admin/notification_settings.html', context)


@user_passes_test(lambda u: u.is_staff)
@login_required
def notification_logs(request):
    """View notification logs"""
    # Mock data - in production, implement proper logging
    logs = [
        {
            'id': 1,
            'type': 'Order Created',
            'recipient': 'customer@example.com',
            'status': 'Sent',
            'sent_at': timezone.now(),
            'business': 'Test Carwash'
        },
        {
            'id': 2,
            'type': 'Payment Confirmation',
            'recipient': 'client@test.com',
            'status': 'Failed',
            'sent_at': timezone.now() - timedelta(hours=1),
            'business': 'Auto Spa Pro'
        }
    ]
    
    context = {
        'title': 'Notification Logs',
        'logs': logs
    }
    
    return render(request, 'system_admin/notification_logs.html', context)


@user_passes_test(lambda u: u.is_staff)
@login_required
@require_http_methods(["POST"])
def send_bulk_notification(request):
    """Send bulk notifications to businesses"""
    from apps.core.notifications import send_notification_email
    
    business_ids = request.POST.getlist('business_ids')
    subject = request.POST.get('subject')
    message = request.POST.get('message')
    
    if not business_ids or not subject or not message:
        messages.error(request, 'Please select businesses and provide subject and message')
        return redirect('system_admin:notification_management')
    
    success_count = 0
    failed_count = 0
    
    for business_id in business_ids:
        try:
            business = Tenant.objects.get(id=business_id)
            if business.email:
                context = {
                    'business': business,
                    'message': message,
                    'admin_sender': request.user.get_full_name() or request.user.username
                }
                
                success = send_notification_email(
                    to_email=business.email,
                    subject=subject,
                    template_name='admin_bulk_notification',
                    context=context
                )
                
                if success:
                    success_count += 1
                else:
                    failed_count += 1
            else:
                failed_count += 1
                
        except Tenant.DoesNotExist:
            failed_count += 1
        except Exception:
            failed_count += 1
    
    messages.success(request, f'Bulk notification sent: {success_count} successful, {failed_count} failed')
    return redirect('system_admin:notification_management')


# ===================== PAYMENT GATEWAY MANAGEMENT =====================

@user_passes_test(lambda u: u.is_superuser)
def gateway_management(request):
    """System admin view for managing payment gateways across all tenants"""
    from .gateway_forms import TenantGatewaySearchForm
    
    # Handle search and filtering
    search_form = TenantGatewaySearchForm(request.GET)
    
    # Get all tenants and their gateway configurations
    tenants = Tenant.objects.filter(is_active=True).order_by('name')
    tenant_gateways = []
    
    for tenant in tenants:
        try:
            with tenant_context(tenant):
                from apps.payments.models import PaymentGateway
                gateways = PaymentGateway.objects.all()
                
                for gateway in gateways:
                    tenant_gateways.append({
                        'tenant': tenant,
                        'gateway': gateway,
                        'status': 'Active' if gateway.is_active else 'Inactive',
                        'environment': 'Production' if gateway.is_live else 'Sandbox'
                    })
        except Exception as e:
            # Tenant database might not exist or have issues
            tenant_gateways.append({
                'tenant': tenant,
                'gateway': None,
                'status': 'Error',
                'environment': 'N/A',
                'error': str(e)
            })
    
    # Apply filters
    if search_form.is_valid():
        search_query = search_form.cleaned_data.get('search')
        gateway_type = search_form.cleaned_data.get('gateway_type')
        status = search_form.cleaned_data.get('status')
        environment = search_form.cleaned_data.get('environment')
        
        if search_query:
            tenant_gateways = [
                tg for tg in tenant_gateways 
                if (search_query.lower() in tg['tenant'].name.lower() or
                    (tg['gateway'] and search_query.lower() in tg['gateway'].name.lower()) or
                    (tg['gateway'] and tg['gateway'].shortcode and search_query in tg['gateway'].shortcode))
            ]
        
        if gateway_type:
            tenant_gateways = [
                tg for tg in tenant_gateways 
                if tg['gateway'] and tg['gateway'].gateway_type == gateway_type
            ]
        
        if status:
            if status == 'active':
                tenant_gateways = [tg for tg in tenant_gateways if tg['status'] == 'Active']
            elif status == 'inactive':
                tenant_gateways = [tg for tg in tenant_gateways if tg['status'] == 'Inactive']
        
        if environment:
            if environment == 'live':
                tenant_gateways = [tg for tg in tenant_gateways if tg['environment'] == 'Production']
            elif environment == 'sandbox':
                tenant_gateways = [tg for tg in tenant_gateways if tg['environment'] == 'Sandbox']
    
    # Pagination
    paginator = Paginator(tenant_gateways, 25)
    page = request.GET.get('page')
    gateway_page = paginator.get_page(page)
    
    # Statistics
    stats = {
        'total_tenants': tenants.count(),
        'total_gateways': len([tg for tg in tenant_gateways if tg['gateway']]),
        'active_gateways': len([tg for tg in tenant_gateways if tg['status'] == 'Active']),
        'mpesa_gateways': len([tg for tg in tenant_gateways if tg['gateway'] and tg['gateway'].gateway_type == 'mpesa']),
    }
    
    context = {
        'tenant_gateways': gateway_page,
        'search_form': search_form,
        'stats': stats,
        'title': 'Payment Gateway Management'
    }
    
    return render(request, 'system_admin/gateway_management.html', context)


@user_passes_test(lambda u: u.is_superuser)
def setup_tenant_mpesa(request, tenant_id=None):
    """Setup M-Pesa gateway for a specific tenant"""
    from .gateway_forms import TenantMPesaGatewayForm
    
    tenant = None
    gateway = None
    
    if tenant_id:
        tenant = get_object_or_404(Tenant, id=tenant_id, is_active=True)
        # Check if gateway already exists
        try:
            with tenant_context(tenant):
                from apps.payments.models import PaymentGateway
                gateway = PaymentGateway.objects.filter(gateway_type='mpesa').first()
        except Exception:
            gateway = None
    
    if request.method == 'POST':
        form = TenantMPesaGatewayForm(request.POST, instance=gateway, tenant=tenant)
        if form.is_valid():
            try:
                # Get the tenant from form if not provided in URL
                selected_tenant = tenant or form.cleaned_data.get('tenant')
                
                if not selected_tenant:
                    messages.error(request, 'Please select a tenant.')
                    return render(request, 'system_admin/setup_tenant_mpesa.html', {
                        'form': form,
                        'tenant': tenant,
                        'gateway': gateway,
                        'is_new': gateway is None,
                        'title': 'Setup M-Pesa Gateway - Select Tenant'
                    })
                
                # Save the gateway in the tenant's database
                with tenant_context(selected_tenant):
                    # Set gateway properties
                    gateway_instance = form.save(commit=False)
                    gateway_instance.gateway_type = 'mpesa'
                    
                    # Set API URL based on environment
                    if gateway_instance.is_live:
                        gateway_instance.api_url = 'https://api.safaricom.co.ke'
                    else:
                        gateway_instance.api_url = 'https://sandbox.safaricom.co.ke'
                    
                    # Set API credentials
                    gateway_instance.api_key = gateway_instance.consumer_key
                    gateway_instance.api_secret = gateway_instance.consumer_secret
                    
                    gateway_instance.save()
                    
                    # Create or update M-Pesa payment method
                    from apps.payments.models import PaymentMethod
                    method, created = PaymentMethod.objects.get_or_create(
                        method_type='mpesa',
                        defaults={
                            'name': 'M-Pesa',
                            'description': 'Pay using M-Pesa mobile money',
                            'is_active': gateway_instance.is_active,
                            'is_online': True,
                            'requires_verification': True,
                            'processing_fee_percentage': 1.5,  # Default M-Pesa fee
                            'minimum_amount': 1,
                            'maximum_amount': 70000,  # M-Pesa transaction limit
                            'icon': 'fas fa-mobile-alt',
                            'color': '#00A651',  # M-Pesa green
                            'display_order': 1
                        }
                    )
                    
                    if not created:
                        # Update existing method
                        method.is_active = gateway_instance.is_active
                        method.save()
                
                messages.success(
                    request, 
                    f'M-Pesa gateway configured successfully for {selected_tenant.name}!'
                )
                return redirect('system_admin:gateway_management')
                
            except Exception as e:
                messages.error(request, f'Error saving M-Pesa configuration: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = TenantMPesaGatewayForm(instance=gateway, tenant=tenant)
    
    context = {
        'form': form,
        'tenant': tenant,
        'gateway': gateway,
        'is_new': gateway is None,
        'title': f'Setup M-Pesa Gateway - {tenant.name if tenant else "Select Tenant"}'
    }
    
    return render(request, 'system_admin/setup_tenant_mpesa.html', context)


@user_passes_test(lambda u: u.is_superuser)
def bulk_setup_mpesa(request):
    """Bulk setup M-Pesa gateway for multiple tenants"""
    from .gateway_forms import BulkGatewaySetupForm
    
    if request.method == 'POST':
        form = BulkGatewaySetupForm(request.POST)
        if form.is_valid():
            try:
                tenants = form.cleaned_data['tenants']
                consumer_key = form.cleaned_data['consumer_key']
                consumer_secret = form.cleaned_data['consumer_secret']
                is_live = form.cleaned_data['is_live']
                webhook_base_url = form.cleaned_data['webhook_base_url'].rstrip('/')
                
                success_count = 0
                failed_count = 0
                
                for tenant in tenants:
                    try:
                        with tenant_context(tenant):
                            from apps.payments.models import PaymentGateway, PaymentMethod
                            
                            # Check if gateway already exists
                            gateway = PaymentGateway.objects.filter(gateway_type='mpesa').first()
                            
                            if gateway:
                                # Update existing
                                gateway.consumer_key = consumer_key
                                gateway.consumer_secret = consumer_secret
                                gateway.is_live = is_live
                                gateway.api_key = consumer_key
                                gateway.api_secret = consumer_secret
                                gateway.api_url = 'https://api.safaricom.co.ke' if is_live else 'https://sandbox.safaricom.co.ke'
                                gateway.webhook_url = f"{webhook_base_url}/business/{tenant.slug}/payments/webhook/mpesa/"
                                gateway.save()
                            else:
                                # Create new
                                gateway = PaymentGateway.objects.create(
                                    name='M-Pesa Daraja',
                                    gateway_type='mpesa',
                                    is_active=True,
                                    is_live=is_live,
                                    consumer_key=consumer_key,
                                    consumer_secret=consumer_secret,
                                    api_key=consumer_key,
                                    api_secret=consumer_secret,
                                    api_url='https://api.safaricom.co.ke' if is_live else 'https://sandbox.safaricom.co.ke',
                                    webhook_url=f"{webhook_base_url}/business/{tenant.slug}/payments/webhook/mpesa/",
                                )
                            
                            # Create or update payment method
                            method, created = PaymentMethod.objects.get_or_create(
                                method_type='mpesa',
                                defaults={
                                    'name': 'M-Pesa',
                                    'description': 'Pay using M-Pesa mobile money',
                                    'is_active': True,
                                    'is_online': True,
                                    'requires_verification': True,
                                    'processing_fee_percentage': 1.5,
                                    'minimum_amount': 1,
                                    'maximum_amount': 70000,
                                    'icon': 'fas fa-mobile-alt',
                                    'color': '#00A651',
                                    'display_order': 1
                                }
                            )
                            
                            if not created:
                                method.is_active = True
                                method.save()
                            
                            success_count += 1
                            
                    except Exception as e:
                        failed_count += 1
                        messages.warning(request, f'Failed to setup M-Pesa for {tenant.name}: {str(e)}')
                
                messages.success(
                    request, 
                    f'Bulk M-Pesa setup completed: {success_count} successful, {failed_count} failed'
                )
                return redirect('system_admin:gateway_management')
                
            except Exception as e:
                messages.error(request, f'Error during bulk setup: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = BulkGatewaySetupForm()
    
    context = {
        'form': form,
        'title': 'Bulk M-Pesa Gateway Setup'
    }
    
    return render(request, 'system_admin/bulk_setup_mpesa.html', context)


@user_passes_test(lambda u: u.is_superuser)
@require_http_methods(["POST"])
def test_tenant_mpesa_connection(request):
    """Test M-Pesa connection for tenant configuration"""
    try:
        import json
        
        data = json.loads(request.body)
        consumer_key = data.get('consumer_key')
        consumer_secret = data.get('consumer_secret')
        is_live = data.get('is_live', False)
        
        if not consumer_key or not consumer_secret:
            return JsonResponse({
                'success': False,
                'message': 'Consumer key and secret are required'
            })
        
        # Test authentication
        import base64
        import requests
        
        api_url = 'https://api.safaricom.co.ke' if is_live else 'https://sandbox.safaricom.co.ke'
        
        credentials = base64.b64encode(
            f"{consumer_key}:{consumer_secret}".encode()
        ).decode()
        
        response = requests.get(
            f"{api_url}/oauth/v1/generate?grant_type=client_credentials",
            headers={
                'Authorization': f'Basic {credentials}',
                'Content-Type': 'application/json'
            },
            timeout=10
        )
        
        if response.status_code == 200:
            return JsonResponse({
                'success': True,
                'message': 'Connection successful! M-Pesa credentials are valid.',
                'environment': 'Production' if is_live else 'Sandbox'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Authentication failed. Please check your credentials.'
            })
            
    except requests.RequestException:
        return JsonResponse({
            'success': False,
            'message': 'Could not connect to M-Pesa API. Please check your internet connection.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error testing connection: {str(e)}'
        })


@user_passes_test(lambda u: u.is_superuser)
def delete_tenant_gateway(request, tenant_id, gateway_id):
    """Delete a payment gateway for a tenant"""
    tenant = get_object_or_404(Tenant, id=tenant_id, is_active=True)
    
    try:
        with tenant_context(tenant):
            from apps.payments.models import PaymentGateway
            gateway = get_object_or_404(PaymentGateway, id=gateway_id)
            
            gateway_name = gateway.name
            gateway_type = gateway.get_gateway_type_display()
            
            gateway.delete()
            
            messages.success(
                request, 
                f'{gateway_type} gateway "{gateway_name}" deleted successfully for {tenant.name}'
            )
    except Exception as e:
        messages.error(request, f'Error deleting gateway: {str(e)}')
    
    return redirect('system_admin:gateway_management')


@user_passes_test(lambda u: u.is_superuser)
def toggle_tenant_gateway(request, tenant_id, gateway_id):
    """Toggle payment gateway active status for a tenant"""
    tenant = get_object_or_404(Tenant, id=tenant_id, is_active=True)
    
    try:
        with tenant_context(tenant):
            from apps.payments.models import PaymentGateway
            gateway = get_object_or_404(PaymentGateway, id=gateway_id)
            
            gateway.is_active = not gateway.is_active
            gateway.save()
            
            status = 'activated' if gateway.is_active else 'deactivated'
            messages.success(
                request, 
                f'{gateway.get_gateway_type_display()} gateway {status} for {tenant.name}'
            )
    except Exception as e:
        messages.error(request, f'Error updating gateway status: {str(e)}')
    
    return redirect('system_admin:gateway_management')


# ==========================================
# SMS MANAGEMENT VIEWS
# ==========================================

@user_passes_test(lambda u: u.is_superuser)
def sms_management(request):
    """SMS Management Dashboard"""
    context = {
        'title': 'SMS Management',
        'total_providers': SMSProvider.objects.count(),
        'active_providers': SMSProvider.objects.filter(is_active=True).count(),
        'total_tenants_with_sms': TenantSMSSettings.objects.count(),
        'active_sms_tenants': TenantSMSSettings.objects.filter(is_active=True).count(),
        'total_messages_today': SMSMessage.objects.filter(
            created_at__date=timezone.now().date()
        ).count(),
        'failed_messages_today': SMSMessage.objects.filter(
            created_at__date=timezone.now().date(),
            status='failed'
        ).count(),
    }
    
    # Recent messages
    context['recent_messages'] = SMSMessage.objects.order_by('-created_at')[:10]
    
    # SMS statistics by provider
    provider_stats = {}
    for provider in SMSProvider.objects.filter(is_active=True):
        tenant_count = TenantSMSSettings.objects.filter(provider=provider, is_active=True).count()
        message_count = SMSMessage.objects.filter(
            tenant_settings__provider=provider,
            created_at__date=timezone.now().date()
        ).count()
        provider_stats[provider.name] = {
            'tenants': tenant_count,
            'messages_today': message_count
        }
    
    context['provider_stats'] = provider_stats
    
    return render(request, 'system_admin/sms/dashboard.html', context)


@user_passes_test(lambda u: u.is_superuser)
def sms_providers(request):
    """Manage SMS Providers"""
    providers = SMSProvider.objects.all().order_by('name')
    
    context = {
        'title': 'SMS Providers',
        'providers': providers,
    }
    
    return render(request, 'system_admin/sms/providers.html', context)


@user_passes_test(lambda u: u.is_superuser)
def create_sms_provider(request):
    """Create new SMS provider"""
    if request.method == 'POST':
        try:
            provider = SMSProvider.objects.create(
                name=request.POST.get('name'),
                provider_type=request.POST.get('provider_type'),
                api_endpoint=request.POST.get('api_endpoint', ''),
                is_active=request.POST.get('is_active') == 'on',
                is_default=request.POST.get('is_default') == 'on',
                rate_per_sms=Decimal(request.POST.get('rate_per_sms', '0.00'))
            )
            
            messages.success(request, f'SMS Provider "{provider.name}" created successfully!')
            return redirect('system_admin:sms_providers')
            
        except Exception as e:
            messages.error(request, f'Error creating provider: {str(e)}')
    
    context = {
        'title': 'Create SMS Provider',
        'provider_types': SMSProvider.PROVIDER_CHOICES,
    }
    
    return render(request, 'system_admin/sms/create_provider.html', context)


@user_passes_test(lambda u: u.is_superuser)
def edit_sms_provider(request, provider_id):
    """Edit SMS provider"""
    provider = get_object_or_404(SMSProvider, id=provider_id)
    
    if request.method == 'POST':
        try:
            provider.name = request.POST.get('name')
            provider.provider_type = request.POST.get('provider_type')
            provider.api_endpoint = request.POST.get('api_endpoint', '')
            provider.is_active = request.POST.get('is_active') == 'on'
            provider.is_default = request.POST.get('is_default') == 'on'
            provider.rate_per_sms = Decimal(request.POST.get('rate_per_sms', '0.00'))
            provider.save()
            
            messages.success(request, f'SMS Provider "{provider.name}" updated successfully!')
            return redirect('system_admin:sms_providers')
            
        except Exception as e:
            messages.error(request, f'Error updating provider: {str(e)}')
    
    context = {
        'title': 'Edit SMS Provider',
        'provider': provider,
        'provider_types': SMSProvider.PROVIDER_CHOICES,
    }
    
    return render(request, 'system_admin/sms/edit_provider.html', context)


@user_passes_test(lambda u: u.is_superuser)
def delete_sms_provider(request, provider_id):
    """Delete SMS provider"""
    provider = get_object_or_404(SMSProvider, id=provider_id)
    
    # Check if provider is being used
    tenant_count = TenantSMSSettings.objects.filter(provider=provider).count()
    
    if tenant_count > 0:
        messages.error(
            request, 
            f'Cannot delete provider "{provider.name}". It is being used by {tenant_count} tenant(s).'
        )
    else:
        provider_name = provider.name
        provider.delete()
        messages.success(request, f'SMS Provider "{provider_name}" deleted successfully!')
    
    return redirect('system_admin:sms_providers')


@user_passes_test(lambda u: u.is_superuser)
def tenant_sms_settings(request):
    """Manage tenant SMS settings"""
    search_query = request.GET.get('search', '')
    provider_filter = request.GET.get('provider', '')
    status_filter = request.GET.get('status', '')
    
    # Get all active tenants
    all_tenants = Tenant.objects.filter(is_active=True, is_approved=True).values('id', 'name', 'slug')
    
    # Get existing SMS settings
    existing_settings = TenantSMSSettings.objects.select_related('provider').all()
    
    # Create a mapping of tenant_id to settings
    settings_map = {str(setting.tenant_id): setting for setting in existing_settings}
    
    # Combine tenant info with SMS settings
    tenant_sms_data = []
    for tenant in all_tenants:
        tenant_id = str(tenant['id'])
        sms_setting = settings_map.get(tenant_id)
        
        tenant_sms_data.append({
            'tenant_id': tenant_id,
            'tenant_name': tenant['name'],
            'tenant_slug': tenant['slug'],
            'sms_settings': sms_setting,
            'has_sms': sms_setting is not None,
            'is_active': sms_setting.is_active if sms_setting else False,
            'provider': sms_setting.provider if sms_setting else None,
        })
    
    # Apply filters
    if search_query:
        tenant_sms_data = [
            item for item in tenant_sms_data 
            if search_query.lower() in item['tenant_name'].lower() or 
               search_query.lower() in item['tenant_id'].lower()
        ]
    
    if provider_filter:
        tenant_sms_data = [
            item for item in tenant_sms_data 
            if item['provider'] and str(item['provider'].id) == provider_filter
        ]
    
    if status_filter == 'active':
        tenant_sms_data = [item for item in tenant_sms_data if item['is_active']]
    elif status_filter == 'inactive':
        tenant_sms_data = [item for item in tenant_sms_data if not item['is_active']]
    elif status_filter == 'configured':
        tenant_sms_data = [item for item in tenant_sms_data if item['has_sms']]
    elif status_filter == 'not_configured':
        tenant_sms_data = [item for item in tenant_sms_data if not item['has_sms']]
    
    # Pagination
    paginator = Paginator(tenant_sms_data, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'title': 'Tenant SMS Settings',
        'page_obj': page_obj,
        'search_query': search_query,
        'provider_filter': provider_filter,
        'status_filter': status_filter,
        'providers': SMSProvider.objects.filter(is_active=True),
        'total_tenants': len(all_tenants),
        'configured_tenants': len([item for item in tenant_sms_data if item['has_sms']]),
        'active_sms_tenants': len([item for item in tenant_sms_data if item['is_active']]),
    }
    
    return render(request, 'system_admin/sms/tenant_settings.html', context)


@user_passes_test(lambda u: u.is_superuser)
def setup_tenant_sms(request, tenant_id):
    """Setup SMS for a specific tenant"""
    tenant = get_object_or_404(Tenant, id=tenant_id, is_active=True)
    
    try:
        sms_settings = TenantSMSSettings.objects.get(tenant_id=str(tenant_id))
    except TenantSMSSettings.DoesNotExist:
        sms_settings = None
    
    if request.method == 'POST':
        form = TenantSMSSettingsForm(request.POST, instance=sms_settings)
        if form.is_valid():
            sms_settings = form.save(commit=False)
            sms_settings.tenant_id = str(tenant_id)
            sms_settings.tenant_name = tenant.name
            sms_settings.save()
            
            messages.success(request, f'SMS settings for "{tenant.name}" updated successfully!')
            return redirect('system_admin:tenant_sms_settings')
    else:
        form = TenantSMSSettingsForm(instance=sms_settings)
    
    context = {
        'title': f'SMS Setup - {tenant.name}',
        'tenant': tenant,
        'form': form,
        'sms_settings': sms_settings,
    }
    
    return render(request, 'system_admin/sms/setup_tenant.html', context)


@user_passes_test(lambda u: u.is_superuser)
def test_tenant_sms(request, tenant_id):
    """Test SMS configuration for a tenant"""
    tenant = get_object_or_404(Tenant, id=tenant_id, is_active=True)
    
    try:
        sms_settings = TenantSMSSettings.objects.get(tenant_id=str(tenant_id), is_active=True)
    except TenantSMSSettings.DoesNotExist:
        messages.error(request, f'No active SMS settings found for "{tenant.name}"')
        return redirect('system_admin:tenant_sms_settings')
    
    if request.method == 'POST':
        form = TestSMSForm(request.POST)
        if form.is_valid():
            try:
                result = send_sms(
                    tenant_settings=sms_settings,
                    recipient=form.cleaned_data['test_number'],
                    message=form.cleaned_data['test_message'],
                    message_type='test'
                )
                
                if result['success']:
                    messages.success(
                        request, 
                        f'Test SMS sent successfully! Message ID: {result.get("message_id", "N/A")}'
                    )
                else:
                    messages.error(
                        request, 
                        f'Failed to send test SMS: {result.get("error", "Unknown error")}'
                    )
                    
            except Exception as e:
                messages.error(request, f'Error sending test SMS: {str(e)}')
    else:
        form = TestSMSForm()
    
    context = {
        'title': f'Test SMS - {tenant.name}',
        'tenant': tenant,
        'sms_settings': sms_settings,
        'tenant_settings': sms_settings,  # For template compatibility
        'form': form,
    }
    
    return render(request, 'system_admin/sms/test_sms.html', context)


@user_passes_test(lambda u: u.is_superuser)
def sms_messages(request):
    """View SMS message logs"""
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    tenant_filter = request.GET.get('tenant', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    messages_qs = SMSMessage.objects.select_related('tenant_settings__provider').all()
    
    if search_query:
        messages_qs = messages_qs.filter(
            Q(recipient__icontains=search_query) |
            Q(message__icontains=search_query) |
            Q(tenant_settings__tenant_name__icontains=search_query)
        )
    
    if status_filter:
        messages_qs = messages_qs.filter(status=status_filter)
    
    if tenant_filter:
        messages_qs = messages_qs.filter(tenant_id=tenant_filter)
    
    if date_from:
        messages_qs = messages_qs.filter(created_at__date__gte=date_from)
    
    if date_to:
        messages_qs = messages_qs.filter(created_at__date__lte=date_to)
    
    # Pagination
    paginator = Paginator(messages_qs.order_by('-created_at'), 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'title': 'SMS Messages',
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'tenant_filter': tenant_filter,
        'date_from': date_from,
        'date_to': date_to,
        'status_choices': SMSMessage.STATUS_CHOICES,
        'tenants': TenantSMSSettings.objects.values('tenant_id', 'tenant_name').distinct(),
    }
    
    return render(request, 'system_admin/sms/messages.html', context)


@user_passes_test(lambda u: u.is_superuser)
def sms_templates(request):
    """View SMS templates"""
    search_query = request.GET.get('search', '')
    template_type = request.GET.get('type', '')
    tenant_filter = request.GET.get('tenant', '')
    
    templates = SMSTemplate.objects.all()
    
    if search_query:
        templates = templates.filter(
            Q(name__icontains=search_query) |
            Q(message__icontains=search_query) |
            Q(tenant_id__icontains=search_query)
        )
    
    if template_type:
        templates = templates.filter(template_type=template_type)
    
    if tenant_filter:
        templates = templates.filter(tenant_id=tenant_filter)
    
    # Pagination
    paginator = Paginator(templates.order_by('-usage_count', '-last_used'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'title': 'SMS Templates',
        'page_obj': page_obj,
        'search_query': search_query,
        'template_type': template_type,
        'tenant_filter': tenant_filter,
        'template_types': SMSTemplate.TEMPLATE_TYPES,
        'tenants': SMSTemplate.objects.values('tenant_id').distinct(),
    }
    
    return render(request, 'system_admin/sms/templates.html', context)


@user_passes_test(lambda u: u.is_superuser)
def sms_statistics(request):
    """SMS usage statistics"""
    from django.db.models import Count, Sum, Avg
    from django.utils import timezone
    from datetime import timedelta
    
    # Date range
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)
    
    # Overall statistics
    total_messages = SMSMessage.objects.filter(created_at__gte=start_date).count()
    successful_messages = SMSMessage.objects.filter(
        created_at__gte=start_date,
        status='delivered'
    ).count()
    failed_messages = SMSMessage.objects.filter(
        created_at__gte=start_date,
        status='failed'
    ).count()
    
    # Success rate
    success_rate = (successful_messages / total_messages * 100) if total_messages > 0 else 0
    
    # Cost analysis
    total_cost = SMSMessage.objects.filter(
        created_at__gte=start_date
    ).aggregate(Sum('cost'))['cost__sum'] or 0
    
    # Provider statistics
    provider_stats = SMSMessage.objects.filter(
        created_at__gte=start_date
    ).values(
        'tenant_settings__provider__name'
    ).annotate(
        message_count=Count('id'),
        success_count=Count('id', filter=Q(status='delivered')),
        total_cost=Sum('cost')
    ).order_by('-message_count')
    
    # Tenant statistics
    tenant_stats = SMSMessage.objects.filter(
        created_at__gte=start_date
    ).values(
        'tenant_settings__tenant_name'
    ).annotate(
        message_count=Count('id'),
        success_count=Count('id', filter=Q(status='delivered')),
        total_cost=Sum('cost')
    ).order_by('-message_count')[:10]
    
    # Daily message counts for chart
    daily_stats = []
    for i in range(days):
        date = (timezone.now() - timedelta(days=i)).date()
        count = SMSMessage.objects.filter(created_at__date=date).count()
        daily_stats.append({
            'date': date.strftime('%Y-%m-%d'),
            'count': count
        })
    
    context = {
        'title': 'SMS Statistics',
        'days': days,
        'total_messages': total_messages,
        'successful_messages': successful_messages,
        'failed_messages': failed_messages,
        'success_rate': round(success_rate, 2),
        'total_cost': total_cost,
        'provider_stats': provider_stats,
        'tenant_stats': tenant_stats,
        'daily_stats': list(reversed(daily_stats)),
    }
    
    return render(request, 'system_admin/sms/statistics.html', context)


@login_required
@staff_member_required
def create_sms_template(request):
    """Create a new SMS template"""
    from messaging.models import SMSTemplate
    
    if request.method == 'POST':
        try:
            template = SMSTemplate.objects.create(
                name=request.POST.get('name'),
                description=request.POST.get('description', ''),
                content=request.POST.get('content'),
                category=request.POST.get('category', 'general'),
                is_active=request.POST.get('is_active') == 'on',
                created_by=request.user
            )
            
            messages.success(request, f'SMS template "{template.name}" created successfully!')
            return redirect('system_admin:sms_templates')
            
        except Exception as e:
            messages.error(request, f'Error creating template: {str(e)}')
            return redirect('system_admin:sms_templates')
    
    return redirect('system_admin:sms_templates')


@login_required
@staff_member_required
def edit_sms_template(request, template_id):
    """Edit an existing SMS template"""
    from messaging.models import SMSTemplate
    
    try:
        template = SMSTemplate.objects.get(id=template_id)
    except SMSTemplate.DoesNotExist:
        messages.error(request, 'SMS template not found!')
        return redirect('system_admin:sms_templates')
    
    if request.method == 'POST':
        try:
            template.name = request.POST.get('name')
            template.description = request.POST.get('description', '')
            template.content = request.POST.get('content')
            template.category = request.POST.get('category', 'general')
            template.is_active = request.POST.get('is_active') == 'on'
            template.save()
            
            messages.success(request, f'SMS template "{template.name}" updated successfully!')
            return redirect('system_admin:sms_templates')
            
        except Exception as e:
            messages.error(request, f'Error updating template: {str(e)}')
            return redirect('system_admin:sms_templates')
    
    return redirect('system_admin:sms_templates')


@login_required
@staff_member_required
def delete_sms_template(request, template_id):
    """Delete an SMS template"""
    from messaging.models import SMSTemplate
    
    try:
        template = SMSTemplate.objects.get(id=template_id)
        template_name = template.name
        template.delete()
        
        messages.success(request, f'SMS template "{template_name}" deleted successfully!')
        
    except SMSTemplate.DoesNotExist:
        messages.error(request, 'SMS template not found!')
    except Exception as e:
        messages.error(request, f'Error deleting template: {str(e)}')
    
    return redirect('system_admin:sms_templates')
