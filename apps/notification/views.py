from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.generic import ListView, DetailView, UpdateView, CreateView
from django.urls import reverse_lazy
from django.db.models import Q, Count
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from datetime import datetime, timedelta
import json

from apps.core.decorators import employee_required
from .models import (
    Notification, NotificationCategory, NotificationTemplate,
    NotificationPreference, NotificationLog, NotificationDigest
)
from .forms import (
    NotificationPreferenceForm, NotificationTemplateForm,
    NotificationCategoryForm, NotificationFilterForm
)
from .utils import NotificationManager

def get_notification_urls(request):
    """Generate all notification URLs for templates with tenant slug."""
    tenant_slug = request.tenant.slug
    base_url = f"/business/{tenant_slug}/notifications"
    
    return {
        # Main URLs
        'dashboard': f"{base_url}/",
        'list': f"{base_url}/list/",
        'detail': f"{base_url}/{{}}/" ,  # Use string formatting in template
        'mark_read': f"{base_url}/{{}}/read/",
        'mark_unread': f"{base_url}/{{}}/unread/",
        'archive': f"{base_url}/{{}}/archive/",
        'delete': f"{base_url}/{{}}/delete/",
        'bulk_action': f"{base_url}/bulk-action/",
        
        # Preference URLs
        'preferences': f"{base_url}/preferences/",
        'preferences_edit': f"{base_url}/preferences/edit/",
        
        # Template URLs
        'template_list': f"{base_url}/templates/",
        'template_create': f"{base_url}/templates/create/",
        'template_edit': f"{base_url}/templates/{{}}/edit/",
        'template_delete': f"{base_url}/templates/{{}}/delete/",
        'template_preview': f"{base_url}/templates/{{}}/preview/",
        
        # Category URLs
        'category_list': f"{base_url}/categories/",
        'category_create': f"{base_url}/categories/create/",
        'category_edit': f"{base_url}/categories/{{}}/edit/",
        'category_delete': f"{base_url}/categories/{{}}/delete/",
        
        # Digest URLs
        'digest_list': f"{base_url}/digests/",
        'digest_detail': f"{base_url}/digests/{{}}/",
        'digest_settings': f"{base_url}/digests/settings/",
        
        # Log URLs
        'log_list': f"{base_url}/logs/",
        'log_detail': f"{base_url}/logs/{{}}/",
        
        # Ajax URLs
        'mark_all_read': f"{base_url}/ajax/mark-all-read/",
        'notification_count': f"{base_url}/ajax/count/",
        'test_notification': f"{base_url}/ajax/test/",
        'send_notification': f"{base_url}/ajax/send/",
        
        # Navigation
        'businesses_dashboard': f"/business/{tenant_slug}/dashboard/",
    }

@method_decorator([login_required, employee_required()], name='dispatch')
class NotificationListView(ListView):
    """List user notifications"""
    model = Notification
    template_name = 'notifications/list.html'
    context_object_name = 'notifications'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Notification.objects.filter(user_id=self.request.user.id)
        
        # Apply filters
        status = self.request.GET.get('status')
        if status == 'unread':
            queryset = queryset.filter(is_read=False)
        elif status == 'read':
            queryset = queryset.filter(is_read=True)
        elif status == 'archived':
            queryset = queryset.filter(is_archived=True)
        else:
            # Default: show non-archived notifications
            queryset = queryset.filter(is_archived=False)
        
        # Filter by type
        notification_type = self.request.GET.get('type')
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)
        
        # Filter by category
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category_id=category)
        
        # Filter by priority
        priority = self.request.GET.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | 
                Q(message__icontains=search)
            )
        
        # Exclude expired notifications
        queryset = queryset.exclude(
            expires_at__lt=timezone.now()
        ).filter(
            expires_at__isnull=True
        ).union(
            queryset.filter(expires_at__gt=timezone.now())
        )
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        user_notifications = Notification.objects.filter(user_id=self.request.user.id)
        
        context.update({
            'filter_form': NotificationFilterForm(self.request.GET),
            'categories': NotificationCategory.objects.filter(is_active=True),
            'notification_types': Notification.NOTIFICATION_TYPES,
            'priority_levels': Notification.PRIORITY_LEVELS,
            'stats': {
                'total': user_notifications.count(),
                'unread': user_notifications.filter(is_read=False).count(),
                'today': user_notifications.filter(created_at__date=timezone.now().date()).count(),
                'archived': user_notifications.filter(is_archived=True).count(),
            }
        })
        
        # Add user role context (should come from context processors, but let's ensure it's available)
        if hasattr(self.request, 'employee') and self.request.employee:
            context['user_role'] = self.request.employee.role
            context['is_owner'] = self.request.employee.role == 'owner'
            context['is_manager'] = self.request.employee.role in ['owner', 'manager']
        
        return context

@method_decorator([login_required, employee_required()], name='dispatch')
class NotificationDetailView(DetailView):
    """View notification details"""
    model = Notification
    template_name = 'notifications/notification_detail.html'
    context_object_name = 'notification'
    
    def get_queryset(self):
        return Notification.objects.filter(user_id=self.request.user.id)
    
    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        # Mark as read when viewed
        if not obj.is_read:
            obj.mark_as_read()
        return obj

@login_required
@employee_required()
def notification_dashboard(request):
    """Notification dashboard and overview"""
    user_notifications = Notification.objects.filter(user_id=request.user.id)
    
    # Recent notifications
    recent_notifications = user_notifications.filter(
        is_archived=False
    ).order_by('-created_at')[:10]
    
    # Statistics
    today = timezone.now().date()
    stats = {
        'total': user_notifications.count(),
        'unread': user_notifications.filter(is_read=False).count(),
        'today': user_notifications.filter(created_at__date=today).count(),
        'this_week': user_notifications.filter(
            created_at__gte=today - timedelta(days=7)
        ).count(),
        'archived': user_notifications.filter(is_archived=True).count(),
        'high_priority': user_notifications.filter(
            priority='high', 
            is_read=False
        ).count(),
        'urgent': user_notifications.filter(
            priority='urgent', 
            is_read=False
        ).count(),
    }
    
    # Notifications by type
    by_type = user_notifications.values('notification_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Notifications by category
    by_category = user_notifications.filter(
        category__isnull=False
    ).values('category__name', 'category__color').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Daily notification trend (last 30 days)
    thirty_days_ago = today - timedelta(days=30)
    daily_trend = []
    
    for i in range(30):
        date = thirty_days_ago + timedelta(days=i)
        count = user_notifications.filter(created_at__date=date).count()
        daily_trend.append({
            'date': date.strftime('%Y-%m-%d'),
            'count': count
        })
    
    context = {
        'recent_notifications': recent_notifications,
        'stats': stats,
        'by_type': by_type,
        'by_category': by_category,
        'daily_trend': daily_trend,
    }
    
    return render(request, 'notifications/dashboard.html', context)

@login_required
@employee_required()
@require_POST
def mark_notification_read(request, pk):
    """Mark single notification as read"""
    notification = get_object_or_404(
        Notification, 
        pk=pk, 
        user_id=request.user.id
    )
    
    notification.mark_as_read()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    messages.success(request, 'Notification marked as read.')
    return redirect('notifications:list')

@login_required
@employee_required()
@require_POST
def mark_notification_unread(request, pk):
    """Mark single notification as unread"""
    notification = get_object_or_404(
        Notification, 
        pk=pk, 
        user_id=request.user.id
    )
    
    notification.mark_as_unread()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    messages.success(request, 'Notification marked as unread.')
    return redirect('notifications:list')

@login_required
@employee_required()
@require_POST
def archive_notification(request, pk):
    """Archive single notification"""
    notification = get_object_or_404(
        Notification, 
        pk=pk, 
        user_id=request.user.id
    )
    
    notification.archive()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    messages.success(request, 'Notification archived.')
    return redirect('notifications:list')

@login_required
@employee_required()
@require_POST
def bulk_notification_action(request):
    """Perform bulk actions on notifications"""
    notification_ids = request.POST.getlist('notification_ids')
    action = request.POST.get('action')
    
    notifications = Notification.objects.filter(id__in=notification_ids, user_id=request.user.id)
    count = notifications.count()
    
    if not notification_ids or not action:
        messages.error(request, 'No notifications or action selected.')
    elif action == 'mark_read':
        notifications.update(is_read=True, read_at=timezone.now())
        messages.success(request, f'{count} notifications marked as read.')
    elif action == 'mark_unread':
        notifications.update(is_read=False, read_at=None)
        messages.success(request, f'{count} notifications marked as unread.')
    elif action == 'archive':
        notifications.update(is_archived=True, archived_at=timezone.now())
        messages.success(request, f'{count} notifications archived.')
    elif action == 'delete':
        notifications.delete()
        messages.success(request, f'{count} notifications deleted.')
    else:
        messages.error(request, 'Invalid action.')
    
    return redirect('notifications:list')

@login_required
@employee_required()
@require_POST
def mark_all_read(request):
    """Mark all notifications as read"""
    count = Notification.objects.filter(
        user_id=request.user.id,
        is_read=False
    ).update(is_read=True, read_at=timezone.now())
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'count': count
        })
    
    messages.success(request, f'{count} notifications marked as read.')
    return redirect('notifications:list')

@method_decorator([login_required, employee_required()], name='dispatch')
class NotificationPreferenceView(UpdateView):
    """Update notification preferences"""
    model = NotificationPreference
    form_class = NotificationPreferenceForm
    template_name = 'notifications/preferences.html'
    success_url = reverse_lazy('notifications:preferences')
    
    def get_object(self, queryset=None):
        obj, created = NotificationPreference.objects.get_or_create(
            user_id=self.request.user.id
        )
        return obj
    
    def form_valid(self, form):
        messages.success(self.request, 'Notification preferences updated successfully!')
        return super().form_valid(form)

@login_required
@employee_required()
def get_notifications_api(request):
    """API endpoint for getting notifications (for AJAX)"""
    notifications = Notification.objects.filter(
        user_id=request.user.id,
        is_archived=False
    ).order_by('-created_at')[:10]
    
    data = []
    for notification in notifications:
        data.append({
            'id': notification.id,
            'title': notification.title,
            'message': notification.message,
            'type': notification.notification_type,
            'priority': notification.priority,
            'is_read': notification.is_read,
            'created_at': notification.created_at.isoformat(),
            'time_since': notification.time_since_created,
            'icon': notification.icon,
            'color': notification.color_class,
            'url': notification.action_url or notification.get_absolute_url(),
        })
    
    unread_count = Notification.objects.filter(
        user_id=request.user.id,
        is_read=False,
        is_archived=False
    ).count()
    
    return JsonResponse({
        'notifications': data,
        'unread_count': unread_count,
    })

@login_required
@employee_required()
def check_notifications_api(request):
    """Simple API endpoint for checking notification count only"""
    unread_count = Notification.objects.filter(
        user_id=request.user.id,
        is_read=False,
        is_archived=False
    ).count()
    
    latest_notification = None
    if unread_count > 0:
        latest = Notification.objects.filter(
            user_id=request.user.id,
            is_read=False,
            is_archived=False
        ).order_by('-created_at').first()
        
        if latest:
            latest_notification = {
                'id': latest.id,
                'title': latest.title,
                'message': latest.message,
                'type': latest.notification_type,
                'created_at': latest.created_at.isoformat(),
            }
    
    return JsonResponse({
        'unread_count': unread_count,
        'latest_notification': latest_notification,
    })

@login_required
@employee_required()
@require_POST
def test_notification(request):
    """Create a test notification"""
    # Create test notification
    notification = Notification.objects.create(
        user_id=request.user.id,
        title="Test Notification",
        message="This is a test notification to verify the system is working correctly.",
        notification_type="info",
        priority="medium",
    )
    
    return JsonResponse({
        'success': True,
        'notification_id': notification.id,
        'message': 'Test notification created successfully.'
    })

# Management Views (for admins/managers)
@method_decorator([login_required, employee_required(['owner', 'manager'])], name='dispatch')
class NotificationTemplateListView(ListView):
    """List notification templates"""
    model = NotificationTemplate
    template_name = 'notifications/template_list.html'
    context_object_name = 'templates'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = NotificationTemplate.objects.all()
        
        # Filter by trigger event
        trigger = self.request.GET.get('trigger')
        if trigger:
            queryset = queryset.filter(trigger_event=trigger)
        
        # Filter by active status
        status = self.request.GET.get('status')
        if status == 'active':
            queryset = queryset.filter(is_active=True)
        elif status == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        return queryset.order_by('name')

@method_decorator([login_required, employee_required(['owner', 'manager'])], name='dispatch')
class NotificationTemplateCreateView(CreateView):
    """Create notification template"""
    model = NotificationTemplate
    form_class = NotificationTemplateForm
    template_name = 'notifications/template_form.html'
    success_url = reverse_lazy('notifications:template_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Notification template created successfully!')
        return super().form_valid(form)

@method_decorator([login_required, employee_required(['owner', 'manager'])], name='dispatch')
class NotificationTemplateUpdateView(UpdateView):
    """Update notification template"""
    model = NotificationTemplate
    form_class = NotificationTemplateForm
    template_name = 'notifications/template_form.html'
    success_url = reverse_lazy('notifications:template_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Notification template updated successfully!')
        return super().form_valid(form)

@login_required
@employee_required()
@employee_required(['owner', 'manager'])
def notification_analytics(request):
    """Notification analytics and insights"""
    # Date range
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    if request.GET.get('start_date'):
        start_date = datetime.strptime(request.GET.get('start_date'), '%Y-%m-%d').date()
    if request.GET.get('end_date'):
        end_date = datetime.strptime(request.GET.get('end_date'), '%Y-%m-%d').date()
    
    # Get all notifications in date range
    notifications = Notification.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    )
    
    # Basic stats
    stats = {
        'total_sent': notifications.count(),
        'total_read': notifications.filter(is_read=True).count(),
        'total_unread': notifications.filter(is_read=False).count(),
        'total_archived': notifications.filter(is_archived=True).count(),
    }
    
    # Read rate
    if stats['total_sent'] > 0:
        stats['read_rate'] = (stats['total_read'] / stats['total_sent']) * 100
    else:
        stats['read_rate'] = 0
    
    # Notifications by type
    by_type = notifications.values('notification_type').annotate(
        count=Count('id'),
        read_count=Count('id', filter=Q(is_read=True))
    ).order_by('-count')
    
    # Notifications by priority
    by_priority = notifications.values('priority').annotate(
        count=Count('id'),
        read_count=Count('id', filter=Q(is_read=True))
    ).order_by('-count')
    
    # Daily trend
    daily_stats = []
    current_date = start_date
    while current_date <= end_date:
        day_notifications = notifications.filter(created_at__date=current_date)
        daily_stats.append({
            'date': current_date.strftime('%Y-%m-%d'),
            'sent': day_notifications.count(),
            'read': day_notifications.filter(is_read=True).count(),
        })
        current_date += timedelta(days=1)
    
    # Top users by notification count
    top_users = notifications.values(
        'user__first_name', 'user__last_name', 'user__email'
    ).annotate(
        count=Count('id'),
        read_count=Count('id', filter=Q(is_read=True))
    ).order_by('-count')[:10]
    
    # Delivery performance
    delivery_logs = NotificationLog.objects.filter(
        notification__created_at__date__gte=start_date,
        notification__created_at__date__lte=end_date
    )
    
    delivery_stats = delivery_logs.values('channel', 'status').annotate(
        count=Count('id')
    )
    
    context = {
        'stats': stats,
        'by_type': by_type,
        'by_priority': by_priority,
        'daily_stats': daily_stats,
        'top_users': top_users,
        'delivery_stats': delivery_stats,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    return render(request, 'notifications/analytics.html', context)

@login_required
@employee_required()
@employee_required(['owner', 'manager'])
def send_bulk_notification(request):
    """Send notification to multiple users"""
    if request.method == 'POST':
        title = request.POST.get('title')
        message = request.POST.get('message')
        notification_type = request.POST.get('notification_type', 'info')
        priority = request.POST.get('priority', 'normal')
        recipient_type = request.POST.get('recipient_type')
        
        if not title or not message:
            messages.error(request, 'Title and message are required.')
            return redirect('notifications:send_bulk')
        
        # Determine recipients
        recipients = []
        
        if recipient_type == 'all_employees':
            from apps.employees.models import Employee
            employees = Employee.objects.filter(is_active=True)
            recipients = [emp.user for emp in employees if emp.user]
        
        elif recipient_type == 'role_based':
            role = request.POST.get('role')
            if role:
                from apps.employees.models import Employee
                employees = Employee.objects.filter(role=role, is_active=True)
                recipients = [emp.user for emp in employees if emp.user]
        
        elif recipient_type == 'specific_users':
            user_ids = request.POST.getlist('user_ids')
            from django.contrib.auth.models import User
            recipients = User.objects.filter(id__in=user_ids)
        
        # Create notifications
        created_count = 0
        manager = NotificationManager()
        
        for user in recipients:
            try:
                manager.create_notification(
                    user=user,
                    title=title,
                    message=message,
                    notification_type=notification_type,
                    priority=priority,
                )
                created_count += 1
            except Exception as e:
                continue
        
        messages.success(request, f'Successfully sent {created_count} notifications.')
        return redirect('notifications:send_bulk')
    
    # GET request - show form
    from apps.employees.models import Employee
    from django.contrib.auth.models import User
    
    context = {
        'notification_types': Notification.NOTIFICATION_TYPES,
        'priority_levels': Notification.PRIORITY_LEVELS,
        'roles': Employee.ROLE_CHOICES if hasattr(Employee, 'ROLE_CHOICES') else [],
        'users': User.objects.filter(is_active=True),
    }
    
    return render(request, 'notifications/send_bulk.html', context)

@login_required
@employee_required()
def notification_settings(request):
    """General notification settings"""
    if request.method == 'POST':
        # Update global notification settings
        # This could include business-wide notification preferences
        messages.success(request, 'Notification settings updated successfully!')
        return redirect('notifications:settings')
    
    context = {
        'categories': NotificationCategory.objects.filter(is_active=True),
        'templates': NotificationTemplate.objects.filter(is_active=True),
    }
    
    return render(request, 'notifications/settings.html', context)

@login_required
@employee_required()
def notification_redirect(request, pk):
    """Redirect to notification action URL and mark as read"""
    notification = get_object_or_404(
        Notification, 
        pk=pk, 
        user_id=request.user.id
    )
    
    # Mark as read
    if not notification.is_read:
        notification.mark_as_read()
    
    # Log click if there's a delivery log
    log = NotificationLog.objects.filter(
        notification=notification,
        channel='web'
    ).first()
    
    if log:
        log.mark_as_clicked()
    
    # Redirect to action URL or detail page
    if notification.action_url:
        return redirect(notification.action_url)
    else:
        return redirect('notifications:detail', pk=pk)

# Additional API endpoints for the new templates
@login_required
@employee_required()
@require_POST
def archive_old_notifications(request):
    """Archive notifications older than specified days"""
    days = request.POST.get('days', 30)
    try:
        days = int(days)
    except ValueError:
        days = 30
    
    cutoff_date = timezone.now() - timedelta(days=days)
    count = Notification.objects.filter(
        user_id=request.user.id,
        created_at__lt=cutoff_date,
        is_archived=False
    ).update(is_archived=True, archived_at=timezone.now())
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'count': count
        })
    
    messages.success(request, f'{count} old notifications archived.')
    return redirect('notifications:list')

@login_required
@employee_required()
@employee_required(['owner', 'manager'])
@require_POST
def send_notification_api(request):
    """API endpoint to send notifications"""
    try:
        data = json.loads(request.body)
        title = data.get('title')
        message = data.get('message')
        priority = data.get('priority', 'medium')
        recipient = data.get('recipient', 'self')
        
        if not title or not message:
            return JsonResponse({'success': False, 'error': 'Title and message required'})
        
        # Determine recipients
        recipients = []
        if recipient == 'all':
            from apps.employees.models import Employee
            employees = Employee.objects.filter(is_active=True)
            recipients = [emp.user for emp in employees if emp.user]
        elif recipient == 'managers':
            from apps.employees.models import Employee
            employees = Employee.objects.filter(role__in=['owner', 'manager'], is_active=True)
            recipients = [emp.user for emp in employees if emp.user]
        else:  # self
            recipients = [request.user]
        
        # Create notifications
        created_count = 0
        for user in recipients:
            try:
                Notification.objects.create(
                    user=user,
                    title=title,
                    message=message,
                    priority=priority,
                    notification_type='info'
                )
                created_count += 1
            except Exception:
                continue
        
        return JsonResponse({
            'success': True,
            'count': created_count
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@employee_required()
@employee_required(['owner', 'manager'])
@require_POST
def bulk_mark_read(request):
    """Mark multiple notifications as read"""
    try:
        data = json.loads(request.body)
        ids = data.get('ids', [])
        
        count = Notification.objects.filter(
            id__in=ids,
            user_id=request.user.id
        ).update(is_read=True, read_at=timezone.now())
        
        return JsonResponse({
            'success': True,
            'count': count
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@employee_required()
@employee_required(['owner', 'manager'])
@require_POST
def bulk_archive(request):
    """Archive multiple notifications"""
    try:
        data = json.loads(request.body)
        ids = data.get('ids', [])
        
        count = Notification.objects.filter(
            id__in=ids,
            user_id=request.user.id
        ).update(is_archived=True, archived_at=timezone.now())
        
        return JsonResponse({
            'success': True,
            'count': count
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@employee_required()
@employee_required(['owner', 'manager'])
@require_POST
def bulk_delete(request):
    """Delete multiple notifications"""
    try:
        data = json.loads(request.body)
        ids = data.get('ids', [])
        
        count = Notification.objects.filter(
            id__in=ids,
            user_id=request.user.id
        ).delete()[0]
        
        return JsonResponse({
            'success': True,
            'count': count
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
