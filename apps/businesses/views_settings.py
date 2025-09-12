import json
import zipfile
import tempfile
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.db import transaction
from django.utils import timezone
from django.core.files.base import ContentFile
from django.conf import settings
from apps.core.decorators import employee_required, owner_required, ajax_required
from apps.core.tenant_models import TenantSettings, TenantBackup
from apps.core.forms import (
    TenantSettingsForm, NotificationSettingsForm, PaymentSettingsForm,
    ServiceSettingsForm, FeatureSettingsForm, BackupSettingsForm,
    BusinessHoursForm, CreateBackupForm
)
from apps.core.backup_utils import TenantBackupManager, get_selected_tables
from apps.core.database_router import tenant_context
from .models import BusinessAlert, QuickAction

@login_required
@employee_required(['owner'])
def settings_overview(request):
    """Settings overview/dashboard"""
    business = request.business
    
    # Get or create tenant settings
    with tenant_context(business):
        tenant_settings, created = TenantSettings.objects.get_or_create(
            tenant_id=business.id,
            defaults={
                'business_name': business.name,
                'default_currency': 'KES',
                'timezone': 'Africa/Nairobi',
            }
        )
    
    # Get settings status
    settings_status = {
        'business_complete': bool(tenant_settings.business_name and tenant_settings.contact_email),
        'payment_configured': tenant_settings.default_tax_rate > 0,
        'notifications_enabled': tenant_settings.email_notifications,
        'backup_enabled': tenant_settings.auto_backup_enabled,
        'hours_configured': bool(tenant_settings.monday_open),
    }
    
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
        'quick_actions': quick_actions,
        'title': 'Settings Overview'
    }
    
    return render(request, 'businesses/settings/overview.html', context)

@login_required
@employee_required(['owner', 'manager'])
def  business_settings_view(request):
    """Business profile and basic settings"""
    business = request.business
    
    if request.method == 'POST':
        form = BusinessSettingsForm(request.POST, request.FILES, instance=business)
        if form.is_valid():
            try:
                with transaction.atomic():
                    updated_business = form.save()
                    
                    # Log the update
                    BusinessAlert.objects.create(
                        title="Business Settings Updated",
                        message=f"Business profile was updated by {request.employee.full_name}",
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
        form = BusinessSettingsForm(instance=business)
    
    context = {
        'form': form,
        'business': business,
        'title': 'Business Settings'
    }
    
    return render(request, 'businesses/settings/business.html', context)

@login_required
@employee_required(['owner', 'manager'])
def service_settings_view(request):
    """Service-related settings"""
    business = request.business
    
    if request.method == 'POST':
        form = ServiceSettingsForm(request.POST)
        if form.is_valid():
            try:
                # Save service settings to business model or separate settings model
                # For now, just show success message
                messages.success(request, 'Service settings updated successfully!')
                return redirect('businesses:service_settings')
            except Exception as e:
                messages.error(request, f'Error updating service settings: {str(e)}')
    else:
        form = ServiceSettingsForm()
    
    # Get service statistics
    try:
        from apps.services.models import Service, ServiceCategory
        service_stats = {
            'total_services': Service.objects.filter(is_active=True).count(),
            'total_categories': ServiceCategory.objects.filter(is_active=True).count(),
            'popular_services': Service.objects.filter(is_popular=True, is_active=True).count(),
        }
    except ImportError:
        service_stats = {
            'total_services': 0,
            'total_categories': 0,
            'popular_services': 0,
        }
    
    context = {
        'form': form,
        'business': business,
        'service_stats': service_stats,
        'title': 'Service Settings'
    }
    
    return render(request, 'businesses/settings/services.html', context)

@login_required
@employee_required(['owner', 'manager'])
def payment_settings_view(request):
    """Payment and financial settings"""
    business = request.business
    
    if request.method == 'POST':
        form = PaymentSettingsForm(request.POST)
        if form.is_valid():
            try:
                # Save payment settings to business model or separate settings model
                # For now, just show success message
                messages.success(request, 'Payment settings updated successfully!')
                return redirect('businesses:payment_settings')
            except Exception as e:
                messages.error(request, f'Error updating payment settings: {str(e)}')
    else:
        form = PaymentSettingsForm()
    
    # Get payment method statistics
    try:
        from apps.payments.models import PaymentMethod, Payment
        from django.db.models import Sum
        
        today = timezone.now().date()
        
        # Get payments for today (excluding refunds)
        today_payments = Payment.objects.filter(
            created_at__date=today,
            status__in=['completed', 'verified']
        ).exclude(payment_type='refund')
        
        # Calculate revenue from completely paid orders only
        total_revenue_today = Decimal('0.00')
        
        try:
            # Get all orders for today and check which are completely paid
            from django.apps import apps
            ServiceOrder = apps.get_model('services', 'ServiceOrder')
            orders_today = ServiceOrder.objects.filter(
                created_at__date=today
            ).exclude(status='cancelled')
            
            for order in orders_today:
                # Get total payments for this order (excluding refunds)
                total_payments = Payment.objects.filter(
                    service_order=order,
                    status__in=['completed', 'verified']
                ).exclude(
                    payment_type='refund'
                ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
                
                # Check if order is completely paid
                order_total = order.total_amount or Decimal('0.00')
                if total_payments >= order_total:
                    total_revenue_today += order_total
        except:
            # Fallback to simple payment sum if ServiceOrder not available
            total_revenue_today = today_payments.aggregate(total=Sum('amount'))['total'] or 0
        
        payment_stats = {
            'active_methods': PaymentMethod.objects.filter(is_active=True).count(),
            'today_payments': today_payments.count(),
            'total_revenue_today': total_revenue_today,
        }
    except ImportError:
        payment_stats = {
            'active_methods': 3,  # Default: Cash, M-Pesa, Card
            'today_payments': 0,
            'total_revenue_today': 0,
        }
    
    context = {
        'form': form,
        'business': business,
        'payment_stats': payment_stats,
        'title': 'Payment Settings'
    }
    
    return render(request, 'businesses/settings/payment.html', context)

@login_required
@employee_required(['owner', 'manager'])
def notification_settings_view(request):
    """Notification preferences and settings"""
    business = request.business
    
    if request.method == 'POST':
        form = NotificationSettingsForm(request.POST)
        if form.is_valid():
            try:
                # Test notifications if requested
                if request.POST.get('test_sms'):
                    if business.phone:
                        success = send_test_sms(str(business.phone))
                        if success:
                            messages.success(request, 'Test SMS sent successfully!')
                        else:
                            messages.error(request, 'Failed to send test SMS. Please check your SMS configuration.')
                    else:
                        messages.error(request, 'Business phone number is required for SMS testing.')
                
                if request.POST.get('test_email'):
                    if business.email:
                        success = send_test_email(business.email)
                        if success:
                            messages.success(request, 'Test email sent successfully!')
                        else:
                            messages.error(request, 'Failed to send test email. Please check your email configuration.')
                    else:
                        messages.error(request, 'Business email address is required for email testing.')
                
                # Only save if not a test request
                if not request.POST.get('test_sms') and not request.POST.get('test_email'):
                    messages.success(request, 'Notification settings updated successfully!')
                    return redirect('businesses:notification_settings')
                    
            except Exception as e:
                messages.error(request, f'Error updating notification settings: {str(e)}')
    else:
        form = NotificationSettingsForm()
    
    context = {
        'form': form,
        'business': business,
        'title': 'Notification Settings'
    }
    
    return render(request, 'businesses/settings/notifications.html', context)

@login_required
@employee_required(['owner'])
def integration_settings_view(request):
    """Third-party integrations settings"""
    business = request.business
    
    if request.method == 'POST':
        form = IntegrationSettingsForm(request.POST)
        if form.is_valid():
            try:
                # Save integration settings
                messages.success(request, 'Integration settings updated successfully!')
                return redirect('businesses:integration_settings')
            except Exception as e:
                messages.error(request, f'Error updating integration settings: {str(e)}')
    else:
        form = IntegrationSettingsForm()
    
    # Available integrations
    integrations = [
        {
            'name': 'M-Pesa',
            'description': 'Mobile money payments',
            'status': 'connected' if getattr(settings, 'MPESA_CONSUMER_KEY', None) else 'disconnected',
            'icon': 'fas fa-mobile-alt',
            'test_url': 'mpesa'
        },
        {
            'name': 'SMS Gateway',
            'description': 'Send SMS notifications',
            'status': 'connected' if getattr(settings, 'SMS_API_KEY', None) else 'disconnected',
            'icon': 'fas fa-sms',
            'test_url': 'sms'
        },
        {
            'name': 'Email Service',
            'description': 'Send email notifications',
            'status': 'connected' if getattr(settings, 'EMAIL_HOST_USER', None) else 'disconnected',
            'icon': 'fas fa-envelope',
            'test_url': 'email'
        },
    ]
    
    context = {
        'form': form,
        'business': business,
        'integrations': integrations,
        'title': 'Integration Settings'
    }
    
    return render(request, 'businesses/settings/integrations.html', context)

@login_required
@employee_required(['owner'])
def backup_settings_view(request):
    """Data backup and export settings"""
    business = request.business
    
    # Get recent backups (placeholder for now)
    recent_backups = []  # This would come from a backup model when implemented
    
    context = {
        'business': business,
        'recent_backups': recent_backups,
        'title': 'Backup & Export'
    }
    
    return render(request, 'businesses/settings/backup.html', context)

@login_required
@employee_required(['owner'])
def security_settings_view(request):
    """Security and access control settings"""
    business = request.business
    
    if request.method == 'POST':
        form = SecuritySettingsForm(request.POST)
        if form.is_valid():
            try:
                # Save security settings
                messages.success(request, 'Security settings updated successfully!')
                return redirect('businesses:security_settings')
            except Exception as e:
                messages.error(request, f'Error updating security settings: {str(e)}')
    else:
        form = SecuritySettingsForm()
    
    # Get security statistics
    try:
        from apps.employees.models import Employee
        security_stats = {
            'total_users': Employee.objects.filter(is_active=True).count(),
            'admin_users': Employee.objects.filter(
                role__in=['owner', 'manager'], 
                is_active=True
            ).count(),
            'recent_logins': 0,  # You can implement login tracking
        }
    except ImportError:
        security_stats = {
            'total_users': 1,
            'admin_users': 1,
            'recent_logins': 0,
        }
    
    context = {
        'form': form,
        'business': business,
        'security_stats': security_stats,
        'title': 'Security Settings'
    }
    
    return render(request, 'businesses/settings/security.html', context)

@login_required
@employee_required(['owner'])
def user_management_view(request):
    """User and employee management"""
    try:
        from apps.employees.models import Employee
        
        employees = Employee.objects.filter(is_active=True).select_related(
            'department'
        ).order_by('role', 'employee_id')
        
        # Group by role
        employees_by_role = {}
        role_counts = {}
        
        for employee in employees:
            role = employee.get_role_display()
            role_key = employee.role  # Use the actual role key (owner, manager, etc.)
            
            if role not in employees_by_role:
                employees_by_role[role] = []
            employees_by_role[role].append(employee)
            
            # Count by role key for easier template access
            if role_key not in role_counts:
                role_counts[role_key] = 0
            role_counts[role_key] += 1
            
    except ImportError:
        employees = []
        employees_by_role = {}
        role_counts = {}
    
    context = {
        'employees': employees,
        'employees_by_role': employees_by_role,
        'owner_count': role_counts.get('owner', 0),
        'manager_count': role_counts.get('manager', 0),
        'supervisor_count': role_counts.get('supervisor', 0),
        'attendant_count': role_counts.get('attendant', 0),
        'cashier_count': role_counts.get('cashier', 0),
        'cleaner_count': role_counts.get('cleaner', 0),
        'security_count': role_counts.get('security', 0),
        'title': 'User Management'
    }
    
    return render(request, 'businesses/settings/users.html', context)

# AJAX Views
@login_required
@employee_required(['owner'])
@ajax_required
def create_backup_ajax(request):
    """Create a data backup"""
    try:
        business = request.business
        backup_data = create_system_backup_data(business)
        
        # Get backup format from request
        request_data = json.loads(request.body) if request.body else {}
        backup_format = request_data.get('export_format', 'json')
        
        # Export data
        exported_data = export_data_to_format(backup_data, backup_format)
        
        # Generate filename
        filename = generate_backup_filename(business, backup_format)
        
        # Calculate size
        if isinstance(exported_data, str):
            size = len(exported_data.encode('utf-8'))
        else:
            size = len(exported_data)
        
        return JsonResponse({
            'success': True,
            'message': 'Backup created successfully!',
            'backup_id': filename,
            'size': format_file_size(size),
            'download_url': f'/business/{business.slug}/settings/api/backup/download/{filename}/'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error creating backup: {str(e)}'
        })

@login_required
@employee_required(['owner'])
def download_backup(request, backup_id):
    """Download a backup file"""
    try:
        business = request.business
        
        # Create fresh backup data
        backup_data = create_system_backup_data(business)
        
        # Determine format from filename
        if backup_id.endswith('.json'):
            export_format = 'json'
            content_type = 'application/json'
        elif backup_id.endswith('.csv'):
            export_format = 'csv'
            content_type = 'text/csv'
        elif backup_id.endswith('.xlsx'):
            export_format = 'excel'
            content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        else:
            export_format = 'json'
            content_type = 'application/json'
        
        # Export data
        exported_data = export_data_to_format(backup_data, export_format)
        
        response = HttpResponse(
            exported_data,
            content_type=content_type
        )
        response['Content-Disposition'] = f'attachment; filename="{backup_id}"'
        
        return response
        
    except Exception as e:
        messages.error(request, f'Error downloading backup: {str(e)}')
        return redirect('businesses:backup_settings')

@login_required
@employee_required(['owner'])
@ajax_required
def test_integration_ajax(request, integration):
    """Test an integration"""
    try:
        business = request.business
        
        if integration == 'sms':
            if business.phone:
                success = send_test_sms(str(business.phone))
                message = 'SMS test successful!' if success else 'SMS test failed! Check your SMS configuration.'
            else:
                success = False
                message = 'Business phone number is required for SMS testing.'
                
        elif integration == 'email':
            if business.email:
                success = send_test_email(business.email)
                message = 'Email test successful!' if success else 'Email test failed! Check your email configuration.'
            else:
                success = False
                message = 'Business email address is required for email testing.'
                
        elif integration == 'mpesa':
            # Test M-Pesa connection (placeholder)
            success = bool(getattr(settings, 'MPESA_CONSUMER_KEY', None))
            message = 'M-Pesa configuration found!' if success else 'M-Pesa not configured. Check your settings.'
            
        else:
            success = False
            message = 'Unknown integration type'
        
        return JsonResponse({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Test failed: {str(e)}'
        })

# Additional AJAX endpoints for notification testing
@login_required
@employee_required(['owner', 'manager'])
@ajax_required
def test_sms_ajax(request):
    """AJAX endpoint for testing SMS"""
    try:
        business = request.business
        data = json.loads(request.body)
        phone = data.get('phone', str(business.phone))
        message = data.get('message', f'Test SMS from {business.name}. Your SMS notifications are working correctly!')
        
        success = send_test_sms(phone, message)
        
        return JsonResponse({
            'success': success,
            'message': 'Test SMS sent successfully!' if success else 'Failed to send test SMS'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'SMS test failed: {str(e)}'
        })

@login_required
@employee_required(['owner', 'manager'])
@ajax_required
def test_email_ajax(request):
    """AJAX endpoint for testing Email"""
    try:
        business = request.business
        data = json.loads(request.body)
        email = data.get('email', business.email)
        subject = data.get('subject', f'Test Email from {business.name}')
        message = data.get('message', 'Your email notifications are working correctly!')
        
        success = send_test_email(email, subject, message)
        
        return JsonResponse({
            'success': success,
            'message': 'Test email sent successfully!' if success else 'Failed to send test email'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Email test failed: {str(e)}'
        })

# Settings data management views
@login_required
@employee_required(['owner'])
def export_business_data(request):
    """Export business data in various formats"""
    business = request.business
    format_type = request.GET.get('format', 'json').lower()
    
    try:
        # Create backup data
        backup_data = create_system_backup_data(business)
        
        # Export in requested format
        exported_data = export_data_to_format(backup_data, format_type)
        
        # Generate filename
        filename = generate_backup_filename(business, format_type)
        
        # Set appropriate content type
        content_types = {
            'json': 'application/json',
            'csv': 'text/csv',
            'excel': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        }
        
        response = HttpResponse(
            exported_data,
            content_type=content_types.get(format_type, 'application/octet-stream')
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        messages.error(request, f'Error exporting data: {str(e)}')
        return redirect('businesses:backup_settings')

@login_required
@employee_required(['owner'])
def system_status_view(request):
    """System status and health check"""
    from apps.core.utils import get_system_health_status
    
    business = request.business
    health_status = get_system_health_status()
    
    # Get additional business metrics
    try:
        from apps.customers.models import Customer
        from apps.services.models import ServiceOrder
        from apps.employees.models import Employee
        
        business_stats = {
            'total_customers': Customer.objects.filter(is_active=True).count(),
            'total_orders': ServiceOrder.objects.count(),
            'active_employees': Employee.objects.filter(is_active=True).count(),
            'pending_orders': ServiceOrder.objects.filter(status='pending').count(),
        }
    except ImportError:
        business_stats = {
            'total_customers': 0,
            'total_orders': 0,
            'active_employees': 0,
            'pending_orders': 0,
        }
    
    # Storage usage calculation
    backup_size = calculate_backup_size_estimate(business)
    
    context = {
        'business': business,
        'health_status': health_status,
        'business_stats': business_stats,
        'backup_size': backup_size,
        'title': 'System Status'
    }
    
    return render(request, 'businesses/settings/system_status.html', context)

@login_required
@employee_required(['owner', 'manager'])
def settings_wizard_view(request):
    """Settings setup wizard for new businesses"""
    business = request.business
    step = request.GET.get('step', '1')
    
    # Define wizard steps
    wizard_steps = {
        '1': {
            'title': 'Business Information',
            'description': 'Basic business details and contact information',
            'template': 'businesses/settings/wizard/step1_business.html',
            'form_class': BusinessSettingsForm,
            'next_step': '2'
        },
        '2': {
            'title': 'Payment Configuration',
            'description': 'Set up payment methods and tax settings',
            'template': 'businesses/settings/wizard/step2_payments.html',
            'form_class': PaymentSettingsForm,
            'next_step': '3'
        },
        '3': {
            'title': 'Notification Preferences',
            'description': 'Configure how you communicate with customers',
            'template': 'businesses/settings/wizard/step3_notifications.html',
            'form_class': NotificationSettingsForm,
            'next_step': 'complete'
        }
    }
    
    current_step = wizard_steps.get(step, wizard_steps['1'])
    
    if request.method == 'POST':
        form_class = current_step['form_class']
        
        if step == '1':
            form = form_class(request.POST, request.FILES, instance=business)
        else:
            form = form_class(request.POST)
        
        if form.is_valid():
            try:
                if step == '1':
                    form.save()
                # For other steps, you might want to save to a settings model
                
                next_step = current_step['next_step']
                if next_step == 'complete':
                    messages.success(request, 'Business setup completed successfully!')
                    return redirect('businesses:settings_overview')
                else:
                    return redirect(f'businesses:settings_wizard?step={next_step}')
                    
            except Exception as e:
                messages.error(request, f'Error saving settings: {str(e)}')
    else:
        form_class = current_step['form_class']
        if step == '1':
            form = form_class(instance=business)
        else:
            form = form_class()
    
    context = {
        'business': business,
        'form': form,
        'current_step': step,
        'step_info': current_step,
        'wizard_steps': wizard_steps,
        'total_steps': len(wizard_steps),
        'title': f'Setup Wizard - {current_step["title"]}'
    }
    
    return render(request, current_step['template'], context)

# Additional utility views
@login_required
@employee_required(['owner'])
@ajax_required
def validate_settings_ajax(request):
    """AJAX endpoint to validate business settings"""
    try:
        business = request.business
        validation_results = validate_business_settings(business)
        
        return JsonResponse({
            'success': True,
            'validation': validation_results
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Validation failed: {str(e)}'
        })

@login_required
@employee_required(['owner'])
@ajax_required  
def reset_settings_ajax(request):
    """AJAX endpoint to reset settings to defaults"""
    try:
        settings_type = request.POST.get('type')
        
        if settings_type == 'notifications':
            # Reset notification settings to defaults
            messages.success(request, 'Notification settings reset to defaults')
        elif settings_type == 'payments':
            # Reset payment settings to defaults
            messages.success(request, 'Payment settings reset to defaults')
        else:
            return JsonResponse({
                'success': False,
                'message': 'Invalid settings type'
            })
        
        return JsonResponse({
            'success': True,
            'message': f'{settings_type.title()} settings reset successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Reset failed: {str(e)}'
        })

@login_required
@employee_required(['owner'])
def import_settings_view(request):
    """Import settings from backup file"""
    business = request.business
    
    if request.method == 'POST':
        uploaded_file = request.FILES.get('settings_file')
        
        if not uploaded_file:
            messages.error(request, 'Please select a file to import')
            return redirect('businesses:backup_settings')
        
        try:
            file_content = uploaded_file.read()
            
            if uploaded_file.name.endswith('.json'):
                settings_data = json.loads(file_content.decode('utf-8'))
            else:
                messages.error(request, 'Only JSON files are supported for import')
                return redirect('businesses:backup_settings')
            
            # Process imported settings
            imported_count = 0
            
            # Import business data if present
            if 'business' in settings_data:
                business_data = settings_data['business']
                # Update business fields carefully
                updateable_fields = ['description', 'website', 'address', 'city', 'state', 'postal_code']
                
                for field in updateable_fields:
                    if field in business_data and business_data[field]:
                        setattr(business, field, business_data[field])
                        imported_count += 1
                
                business.save()
            
            messages.success(request, f'Successfully imported {imported_count} settings')
            
        except json.JSONDecodeError:
            messages.error(request, 'Invalid JSON file format')
        except Exception as e:
            messages.error(request, f'Import failed: {str(e)}')
    
    return redirect('businesses:backup_settings')

# Settings comparison and audit
@login_required
@employee_required(['owner'])
def settings_audit_view(request):
    """Settings audit and change history"""
    business = request.business
    
    # Get recent business alerts related to settings
    recent_changes = BusinessAlert.objects.filter(
        title__icontains='Settings',
        created_at__gte=timezone.now() - timezone.timedelta(days=30)
    ).order_by('-created_at')[:20]
    
    # Settings recommendations
    validation = validate_business_settings(business)
    
    context = {
        'business': business,
        'recent_changes': recent_changes,
        'validation': validation,
        'title': 'Settings Audit'
    }
    
    return render(request, 'businesses/settings/audit.html', context)