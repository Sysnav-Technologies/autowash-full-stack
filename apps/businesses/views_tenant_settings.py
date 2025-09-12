from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.db import transaction
from django.utils import timezone
import json
from django.conf import settings
from apps.core.decorators import employee_required
from apps.core.tenant_models import TenantSettings, TenantBackup
from apps.core.forms import (
    TenantSettingsForm, NotificationSettingsForm, PaymentSettingsForm,
    ServiceSettingsForm, FeatureSettingsForm, BackupSettingsForm,
    BusinessHoursForm, CreateBackupForm
)
from apps.core.backup_utils import TenantBackupManager, get_selected_tables
from apps.core.database_router import tenant_context
from .models import BusinessAlert


def get_or_create_tenant_settings(business):
    """Helper function to get or create tenant settings with current business info"""
    # Get the actual tenant object if we have a simplified BusinessContext
    if hasattr(business, 'id') and not hasattr(business, 'address_line_1'):
        from apps.core.tenant_models import Tenant
        # CRITICAL: Tenant model is in default database, use explicit database routing
        business = Tenant.objects.using('default').get(id=business.id)
    
    with tenant_context(business):
        # Format the full address from Address mixin fields
        address_parts = [
            getattr(business, 'address_line_1', ''),
            getattr(business, 'address_line_2', ''),
            getattr(business, 'city', ''),
            getattr(business, 'state', ''),
            getattr(business, 'postal_code', ''),
        ]
        business_address = ', '.join([part for part in address_parts if part])
        
        tenant_settings, created = TenantSettings.objects.get_or_create(
            tenant_id=business.id,
            defaults={
                'business_name': business.name,
                'contact_phone': str(business.phone) if getattr(business, 'phone', None) else '',
                'contact_email': getattr(business, 'email', '') or '',
                'contact_address': business_address,
                'default_currency': 'KES',
                'timezone': 'Africa/Nairobi',
            }
        )
        
        # Sync with current business info if needed
        if not created:
            updated = False
            if not tenant_settings.business_name and business.name:
                tenant_settings.business_name = business.name
                updated = True
            if not tenant_settings.contact_email and getattr(business, 'email', None):
                tenant_settings.contact_email = business.email
                updated = True
            if not tenant_settings.contact_phone and getattr(business, 'phone', None):
                tenant_settings.contact_phone = str(business.phone)
                updated = True
            if not tenant_settings.contact_address and business_address:
                tenant_settings.contact_address = business_address
                updated = True
            
            if updated:
                tenant_settings.save()
        
        return tenant_settings


@login_required
@employee_required(['owner'])
def settings_overview(request):
    """Settings overview/dashboard"""
    business = request.business
    
    # Get or create tenant settings with current business info
    tenant_settings = get_or_create_tenant_settings(business)
    
    # Get settings status
    settings_status = {
        'business_complete': bool(tenant_settings.business_name and tenant_settings.contact_email),
        'payment_configured': tenant_settings.default_tax_rate > 0,
        'notifications_enabled': tenant_settings.email_notifications,
        'backup_enabled': tenant_settings.auto_backup_enabled,
        'hours_configured': bool(tenant_settings.monday_open),
    }
    
    # Recent backups (from main database)
    recent_backups = TenantBackup.objects.using('default').filter(
        tenant_id=business.id,
        status='completed'
    )[:5]
    
    # Recent activities
    recent_activities = [
        {
            'action': 'Settings updated',
            'timestamp': tenant_settings.updated_at,
            'user': 'System',
        }
    ]
    
    # Quick actions based on validation
    quick_actions = []
    
    if not settings_status['business_complete']:
        quick_actions.append({
            'title': 'Complete Business Profile',
            'description': 'Fill in missing business information',
            'url': 'businesses:business_settings',
            'icon': 'fas fa-building',
            'priority': 'high'
        })
    
    if not settings_status['payment_configured']:
        quick_actions.append({
            'title': 'Configure Payment Settings',
            'description': 'Set up tax rates and payment preferences',
            'url': 'businesses:payment_settings',
            'icon': 'fas fa-credit-card',
            'priority': 'high'
        })
    
    # Always show backup option
    quick_actions.append({
        'title': 'Create Data Backup',
        'description': 'Backup your business data for safekeeping',
        'url': 'businesses:backup_settings',
        'icon': 'fas fa-download',
        'priority': 'normal'
    })
    
    context = {
        'business': business,
        'tenant_settings': tenant_settings,
        'settings_status': settings_status,
        'recent_activities': recent_activities,
        'recent_backups': recent_backups,
        'quick_actions': quick_actions,
        'title': 'Settings Overview'
    }
    
    return render(request, 'businesses/settings/overview.html', context)


@login_required
@employee_required(['owner'])
def business_settings_view(request):
    """Business profile and basic settings"""
    business = request.business
    
    # Get or create tenant settings with current business info
    tenant_settings = get_or_create_tenant_settings(business)
    
    if request.method == 'POST':
        form = TenantSettingsForm(request.POST, instance=tenant_settings)
        if form.is_valid():
            try:
                with transaction.atomic():
                    with tenant_context(business):
                        updated_settings = form.save()
                    
                    # Log the update
                    BusinessAlert.objects.create(
                        title="Business Settings Updated",
                        message=f"Business profile was updated by {request.user.get_full_name()}",
                        alert_type="info",
                        priority="low",
                        for_owners=True,
                        for_managers=True
                    )
                    
                messages.success(request, 'Business settings updated successfully!')
                return redirect('businesses:business_settings')
            except Exception as e:
                messages.error(request, f'Error updating settings: {str(e)}')
    else:
        form = TenantSettingsForm(instance=tenant_settings)
    
    context = {
        'form': form,
        'business': business,
        'tenant_settings': tenant_settings,
        'title': 'Business Settings'
    }
    
    return render(request, 'businesses/settings/business.html', context)


@login_required
@employee_required(['owner'])
def notification_settings_view(request):
    """Notification settings"""
    business = request.business
    
    # Get or create tenant settings
    with tenant_context(business):
        tenant_settings, created = TenantSettings.objects.get_or_create(
            tenant_id=business.id,
            defaults={'default_currency': 'KES', 'timezone': 'Africa/Nairobi'}
        )
    
    if request.method == 'POST':
        form = NotificationSettingsForm(request.POST, instance=tenant_settings)
        if form.is_valid():
            try:
                with transaction.atomic():
                    with tenant_context(business):
                        form.save()
                    
                messages.success(request, 'Notification settings updated successfully!')
                return redirect('businesses:notification_settings')
            except Exception as e:
                messages.error(request, f'Error updating notification settings: {str(e)}')
    else:
        form = NotificationSettingsForm(instance=tenant_settings)
    
    context = {
        'form': form,
        'business': business,
        'tenant_settings': tenant_settings,
        'title': 'Notification Settings'
    }
    
    return render(request, 'businesses/settings/notifications.html', context)


@login_required
@employee_required(['owner'])
def payment_settings_view(request):
    """Payment settings"""
    business = request.business
    
    # Get or create tenant settings
    with tenant_context(business):
        tenant_settings, created = TenantSettings.objects.get_or_create(
            tenant_id=business.id,
            defaults={'default_currency': 'KES', 'timezone': 'Africa/Nairobi'}
        )
    
    if request.method == 'POST':
        form = PaymentSettingsForm(request.POST, instance=tenant_settings)
        if form.is_valid():
            try:
                with transaction.atomic():
                    with tenant_context(business):
                        form.save()
                    
                messages.success(request, 'Payment settings updated successfully!')
                return redirect('businesses:payment_settings')
            except Exception as e:
                messages.error(request, f'Error updating payment settings: {str(e)}')
    else:
        form = PaymentSettingsForm(instance=tenant_settings)
    
    context = {
        'form': form,
        'business': business,
        'tenant_settings': tenant_settings,
        'title': 'Payment Settings'
    }
    
    return render(request, 'businesses/settings/payments.html', context)


@login_required
@employee_required(['owner'])
def service_settings_view(request):
    """Service settings"""
    business = request.business
    
    # Get or create tenant settings
    with tenant_context(business):
        tenant_settings, created = TenantSettings.objects.get_or_create(
            tenant_id=business.id,
            defaults={'default_currency': 'KES', 'timezone': 'Africa/Nairobi'}
        )
    
    if request.method == 'POST':
        form = ServiceSettingsForm(request.POST, instance=tenant_settings)
        if form.is_valid():
            try:
                with transaction.atomic():
                    with tenant_context(business):
                        form.save()
                    
                messages.success(request, 'Service settings updated successfully!')
                return redirect('businesses:service_settings')
            except Exception as e:
                messages.error(request, f'Error updating service settings: {str(e)}')
    else:
        form = ServiceSettingsForm(instance=tenant_settings)
    
    context = {
        'form': form,
        'business': business,
        'tenant_settings': tenant_settings,
        'title': 'Service Settings'
    }
    
    return render(request, 'businesses/settings/services.html', context)


@login_required
@employee_required(['owner'])
def feature_settings_view(request):
    """Feature settings"""
    business = request.business
    
    # Get or create tenant settings
    with tenant_context(business):
        tenant_settings, created = TenantSettings.objects.get_or_create(
            tenant_id=business.id,
            defaults={'default_currency': 'KES', 'timezone': 'Africa/Nairobi'}
        )
    
    if request.method == 'POST':
        form = FeatureSettingsForm(request.POST, instance=tenant_settings)
        if form.is_valid():
            try:
                with transaction.atomic():
                    with tenant_context(business):
                        form.save()
                    
                messages.success(request, 'Feature settings updated successfully!')
                return redirect('businesses:feature_settings')
            except Exception as e:
                messages.error(request, f'Error updating feature settings: {str(e)}')
    else:
        form = FeatureSettingsForm(instance=tenant_settings)
    
    context = {
        'form': form,
        'business': business,
        'tenant_settings': tenant_settings,
        'title': 'Feature Settings'
    }
    
    return render(request, 'businesses/settings/features.html', context)


@login_required
@employee_required(['owner'])
def business_hours_view(request):
    """Business hours settings"""
    business = request.business
    
    # Get or create tenant settings
    with tenant_context(business):
        tenant_settings, created = TenantSettings.objects.get_or_create(
            tenant_id=business.id,
            defaults={'default_currency': 'KES', 'timezone': 'Africa/Nairobi'}
        )
    
    if request.method == 'POST':
        form = BusinessHoursForm(request.POST, instance=tenant_settings)
        if form.is_valid():
            try:
                with transaction.atomic():
                    with tenant_context(business):
                        form.save()
                    
                messages.success(request, 'Business hours updated successfully!')
                return redirect('businesses:business_hours')
            except Exception as e:
                messages.error(request, f'Error updating business hours: {str(e)}')
    else:
        form = BusinessHoursForm(instance=tenant_settings)
    
    context = {
        'form': form,
        'business': business,
        'tenant_settings': tenant_settings,
        'title': 'Business Hours'
    }
    
    return render(request, 'businesses/settings/hours.html', context)


@login_required
@employee_required(['owner'])
def backup_settings_view(request):
    """Data backup and export settings"""
    business = request.business
    
    # Get or create tenant settings
    with tenant_context(business):
        tenant_settings, created = TenantSettings.objects.get_or_create(
            tenant_id=business.id,
            defaults={'default_currency': 'KES', 'timezone': 'Africa/Nairobi'}
        )
    
    # Get recent backups (from main database)
    recent_backups = TenantBackup.objects.using('default').filter(
        tenant_id=business.id
    ).order_by('-created_at')[:10]
    
    # Handle backup settings form
    if request.method == 'POST' and 'backup_settings' in request.POST:
        form = BackupSettingsForm(request.POST, instance=tenant_settings)
        if form.is_valid():
            try:
                with transaction.atomic():
                    with tenant_context(business):
                        form.save()
                
                messages.success(request, 'Backup settings updated successfully!')
                return redirect('businesses:backup_settings')
            except Exception as e:
                messages.error(request, f'Error updating backup settings: {str(e)}')
    else:
        form = BackupSettingsForm(instance=tenant_settings)
    
    # Handle create backup form
    create_form = CreateBackupForm()
    
    context = {
        'form': form,
        'create_form': create_form,
        'business': business,
        'tenant_settings': tenant_settings,
        'recent_backups': recent_backups,
        'title': 'Backup & Export'
    }
    
    return render(request, 'businesses/settings/backup.html', context)


@login_required
@employee_required(['owner'])
@require_POST
def create_backup_api(request):
    """API endpoint to create a backup"""
    business = request.business
    
    try:
        # Convert BusinessContext to full Tenant object for backup operations
        if hasattr(business, 'id') and not hasattr(business, 'database_config'):
            from apps.core.tenant_models import Tenant
            business = Tenant.objects.using('default').get(id=business.id)
        
        import json
        data = json.loads(request.body)
        
        backup_type = data.get('backup_type', 'full')
        backup_format = data.get('backup_format', 'sql')
        email_to = data.get('email_address') if data.get('email_backup') else None
        
        # Get selected tables for partial backup
        selected_tables = None
        if backup_type == 'partial':
            selected_tables = get_selected_tables(data)
        
        # Create backup
        backup_manager = TenantBackupManager(business)
        backup = backup_manager.create_backup(
            backup_type=backup_type,
            backup_format=backup_format,
            selected_tables=selected_tables,
            email_to=email_to,
            user=request.user
        )
        
        return JsonResponse({
            'success': True,
            'backup_id': backup.backup_id,
            'size': backup.file_size_formatted,
            'download_url': backup.get_download_url()
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@employee_required(['owner'])
def download_backup(request, backup_id):
    """Download a backup file"""
    business = request.business
    
    try:
        # Convert BusinessContext to full Tenant object for backup operations
        if hasattr(business, 'id') and not hasattr(business, 'database_config'):
            from apps.core.tenant_models import Tenant
            business = Tenant.objects.using('default').get(id=business.id)
        
        backup_manager = TenantBackupManager(business)
        return backup_manager.get_backup_download_response(backup_id)
    except Exception as e:
        messages.error(request, f'Error downloading backup: {str(e)}')
        return redirect('businesses:backup_settings')


@login_required
@employee_required(['owner'])
@require_POST
def delete_backup_api(request, backup_id):
    """API endpoint to delete a backup"""
    business = request.business
    
    try:
        # Convert BusinessContext to full Tenant object for backup operations
        if hasattr(business, 'id') and not hasattr(business, 'database_config'):
            from apps.core.tenant_models import Tenant
            business = Tenant.objects.using('default').get(id=business.id)
        
        backup_manager = TenantBackupManager(business)
        success = backup_manager.delete_backup(backup_id)
        
        if success:
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'Backup not found'}, status=404)
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@employee_required(['owner'])
def export_settings(request):
    """Export current settings as JSON"""
    business = request.business
    
    try:
        with tenant_context(business):
            tenant_settings = TenantSettings.objects.get(tenant_id=business.id)
            
            # Create settings export
            settings_data = {
                'business_name': tenant_settings.business_name,
                'tagline': tenant_settings.tagline,
                'default_currency': tenant_settings.default_currency,
                'timezone': tenant_settings.timezone,
                'contact_phone': tenant_settings.contact_phone,
                'contact_email': tenant_settings.contact_email,
                'contact_address': tenant_settings.contact_address,
                'website_url': tenant_settings.website_url,
                'facebook_url': tenant_settings.facebook_url,
                'instagram_url': tenant_settings.instagram_url,
                'twitter_url': tenant_settings.twitter_url,
                'primary_color': tenant_settings.primary_color,
                'secondary_color': tenant_settings.secondary_color,
                'sms_notifications': tenant_settings.sms_notifications,
                'email_notifications': tenant_settings.email_notifications,
                'auto_payment_confirmation': tenant_settings.auto_payment_confirmation,
                'default_tax_rate': str(tenant_settings.default_tax_rate),
                'service_buffer_time': tenant_settings.service_buffer_time,
                'backup_frequency': tenant_settings.backup_frequency,
                'backup_retention_days': tenant_settings.backup_retention_days,
                'exported_at': timezone.now().isoformat(),
                'exported_by': request.user.username,
            }
            
            # Create response
            response = JsonResponse(settings_data, json_dumps_params={'indent': 2})
            response['Content-Disposition'] = f'attachment; filename="settings_{business.slug}_{timezone.now().strftime("%Y%m%d")}.json"'
            
            return response
            
    except TenantSettings.DoesNotExist:
        messages.error(request, 'Settings not found')
        return redirect('businesses:settings_overview')
    except Exception as e:
        messages.error(request, f'Error exporting settings: {str(e)}')
        return redirect('businesses:settings_overview')
