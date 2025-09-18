from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone
from django.conf import settings
import json
import logging

from .models import SMSMessage, SMSTemplate, TenantSMSSettings, SMSProvider, SMSWebhook
from .services import send_sms

logger = logging.getLogger(__name__)


# Webhook Views for SMS Delivery Status Updates
@method_decorator(csrf_exempt, name='dispatch')
class HostPinnacleWebhookView(View):
    """Handle Host Pinnacle WhatsApp delivery status webhooks"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            
            # Log webhook data
            SMSWebhook.objects.create(
                provider_type='host_pinnacle',
                webhook_data=data,
                received_at=timezone.now()
            )
            
            # Process delivery status
            message_id = data.get('messageId') or data.get('id')
            status = data.get('status', '').lower()
            
            if message_id:
                try:
                    sms_message = SMSMessage.objects.get(provider_message_id=message_id)
                    
                    # Map Host Pinnacle status to our status
                    status_mapping = {
                        'sent': 'sent',
                        'delivered': 'delivered',
                        'read': 'delivered',
                        'failed': 'failed',
                        'error': 'failed'
                    }
                    
                    new_status = status_mapping.get(status)
                    if new_status and sms_message.status != new_status:
                        sms_message.status = new_status
                        if new_status == 'delivered':
                            sms_message.delivered_at = timezone.now()
                        sms_message.save()
                        
                        logger.info(f"Updated SMS {message_id} status to {new_status}")
                        
                except SMSMessage.DoesNotExist:
                    logger.warning(f"SMS message {message_id} not found for Host Pinnacle webhook")
            
            return JsonResponse({'status': 'success'})
            
        except Exception as e:
            logger.error(f"Host Pinnacle webhook error: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@method_decorator(csrf_exempt, name='dispatch')
class AfricasTalkingWebhookView(View):
    """Handle Africa's Talking SMS delivery status webhooks"""
    
    def post(self, request):
        try:
            # Africa's Talking sends form data
            message_id = request.POST.get('id')
            status = request.POST.get('status', '').lower()
            failure_reason = request.POST.get('failureReason', '')
            
            # Log webhook data
            SMSWebhook.objects.create(
                provider_type='africas_talking',
                webhook_data=request.POST.dict(),
                received_at=timezone.now()
            )
            
            if message_id:
                try:
                    sms_message = SMSMessage.objects.get(provider_message_id=message_id)
                    
                    # Map Africa's Talking status to our status
                    status_mapping = {
                        'success': 'delivered',
                        'sent': 'sent',
                        'submitted': 'sent',
                        'buffered': 'sent',
                        'rejected': 'failed',
                        'failed': 'failed'
                    }
                    
                    new_status = status_mapping.get(status)
                    if new_status and sms_message.status != new_status:
                        sms_message.status = new_status
                        if new_status == 'delivered':
                            sms_message.delivered_at = timezone.now()
                        elif new_status == 'failed' and failure_reason:
                            sms_message.error_message = failure_reason
                        sms_message.save()
                        
                        logger.info(f"Updated SMS {message_id} status to {new_status}")
                        
                except SMSMessage.DoesNotExist:
                    logger.warning(f"SMS message {message_id} not found for Africa's Talking webhook")
            
            return JsonResponse({'status': 'success'})
            
        except Exception as e:
            logger.error(f"Africa's Talking webhook error: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@method_decorator(csrf_exempt, name='dispatch')
class TwilioWebhookView(View):
    """Handle Twilio SMS delivery status webhooks"""
    
    def post(self, request):
        try:
            # Twilio sends form data
            message_sid = request.POST.get('MessageSid')
            message_status = request.POST.get('MessageStatus', '').lower()
            error_code = request.POST.get('ErrorCode')
            error_message = request.POST.get('ErrorMessage')
            
            # Log webhook data
            SMSWebhook.objects.create(
                provider_type='twilio',
                webhook_data=request.POST.dict(),
                received_at=timezone.now()
            )
            
            if message_sid:
                try:
                    sms_message = SMSMessage.objects.get(provider_message_id=message_sid)
                    
                    # Map Twilio status to our status
                    status_mapping = {
                        'queued': 'pending',
                        'sending': 'pending',
                        'sent': 'sent',
                        'delivered': 'delivered',
                        'undelivered': 'failed',
                        'failed': 'failed'
                    }
                    
                    new_status = status_mapping.get(message_status)
                    if new_status and sms_message.status != new_status:
                        sms_message.status = new_status
                        if new_status == 'delivered':
                            sms_message.delivered_at = timezone.now()
                        elif new_status == 'failed' and error_message:
                            sms_message.error_message = f"Error {error_code}: {error_message}"
                        sms_message.save()
                        
                        logger.info(f"Updated SMS {message_sid} status to {new_status}")
                        
                except SMSMessage.DoesNotExist:
                    logger.warning(f"SMS message {message_sid} not found for Twilio webhook")
            
            return JsonResponse({'status': 'success'})
            
        except Exception as e:
            logger.error(f"Twilio webhook error: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@method_decorator(csrf_exempt, name='dispatch')
class GeneralSMSWebhookView(View):
    """Handle general SMS provider webhooks"""
    
    def post(self, request, provider_type):
        try:
            data = json.loads(request.body) if request.content_type == 'application/json' else request.POST.dict()
            
            # Log webhook data
            SMSWebhook.objects.create(
                provider_type=provider_type,
                webhook_data=data,
                received_at=timezone.now()
            )
            
            return JsonResponse({'status': 'success'})
            
        except Exception as e:
            logger.error(f"General webhook error for {provider_type}: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


# Tenant SMS Views
class SMSListView(LoginRequiredMixin, ListView):
    """List SMS messages for current tenant"""
    model = SMSMessage
    template_name = 'messaging/sms_list.html'
    context_object_name = 'messages'
    paginate_by = 25
    
    def get_queryset(self):
        # Get tenant SMS settings
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return SMSMessage.objects.none()
            
        try:
            tenant_settings = TenantSMSSettings.objects.get(tenant_id=str(tenant.id))
            queryset = SMSMessage.objects.filter(tenant_settings=tenant_settings)
            
            # Apply filters
            status_filter = self.request.GET.get('status')
            if status_filter:
                queryset = queryset.filter(status=status_filter)
                
            search_query = self.request.GET.get('search')
            if search_query:
                queryset = queryset.filter(
                    Q(recipient__icontains=search_query) |
                    Q(message__icontains=search_query)
                )
                
            return queryset.order_by('-created_at')
            
        except TenantSMSSettings.DoesNotExist:
            return SMSMessage.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = SMSMessage.STATUS_CHOICES
        context['search_query'] = self.request.GET.get('search', '')
        context['status_filter'] = self.request.GET.get('status', '')
        return context


class SendSMSView(LoginRequiredMixin, View):
    """Send individual SMS"""
    template_name = 'messaging/send_sms.html'
    
    def get(self, request):
        tenant = getattr(request, 'tenant', None)
        templates = []
        
        if tenant:
            templates = SMSTemplate.objects.filter(
                Q(tenant_id=str(tenant.id)) | Q(tenant_id__isnull=True),
                is_active=True
            )
        
        context = {
            'templates': templates,
        }
        return render(request, self.template_name, context)
    
    def post(self, request):
        recipient = request.POST.get('recipient')
        message = request.POST.get('message')
        sender_id = request.POST.get('sender_id', '')
        
        try:
            # Send SMS using the service
            tenant = getattr(request, 'tenant', None)
            tenant_id = str(tenant.id) if tenant else None
            result = send_sms(
                tenant_id=tenant_id,
                recipient=recipient,
                message=message,
                sender_id=sender_id
            )
            
            if result and result.status in ['sent', 'pending']:
                messages.success(request, f'SMS sent successfully! Message ID: {result.id}')
            elif result:
                messages.error(request, f'Failed to send SMS: {result.error_message or "Unknown error"}')
            else:
                messages.error(request, 'Failed to send SMS: No SMS settings configured for your business')
                
        except Exception as e:
            messages.error(request, f'Error sending SMS: {str(e)}')
        
        return redirect('messaging:send_sms')


class BulkSMSView(LoginRequiredMixin, View):
    """Send bulk SMS messages"""
    template_name = 'messaging/bulk_sms.html'
    
    def get(self, request):
        tenant = getattr(request, 'tenant', None)
        templates = []
        
        if tenant:
            templates = SMSTemplate.objects.filter(
                Q(tenant_id=str(tenant.id)) | Q(tenant_id__isnull=True),
                is_active=True
            )
        
        context = {
            'templates': templates,
        }
        return render(request, self.template_name, context)
    
    def post(self, request):
        recipients = request.POST.get('recipients', '').split('\n')
        message = request.POST.get('message')
        sender_id = request.POST.get('sender_id', '')
        
        success_count = 0
        failed_count = 0
        
        for recipient in recipients:
            recipient = recipient.strip()
            if recipient:
                try:
                    tenant = getattr(request, 'tenant', None)
                    tenant_id = str(tenant.id) if tenant else None
                    result = send_sms(
                        tenant_id=tenant_id,
                        recipient=recipient,
                        message=message,
                        sender_id=sender_id
                    )
                    
                    if result and result.status in ['sent', 'pending']:
                        success_count += 1
                    else:
                        failed_count += 1
                        
                except Exception:
                    failed_count += 1
        
        if success_count > 0:
            messages.success(request, f'Successfully sent {success_count} SMS messages.')
        if failed_count > 0:
            messages.warning(request, f'{failed_count} SMS messages failed to send.')
        
        return redirect('messaging:bulk_sms')


class SMSTemplateListView(LoginRequiredMixin, ListView):
    """List SMS templates for current tenant"""
    model = SMSTemplate
    template_name = 'messaging/template_list.html'
    context_object_name = 'templates'
    paginate_by = 20
    
    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return SMSTemplate.objects.none()
            
        return SMSTemplate.objects.filter(
            Q(tenant_id=str(tenant.id)) | Q(tenant_id__isnull=True)
        ).order_by('-created_at')


class CreateTemplateView(LoginRequiredMixin, CreateView):
    """Create new SMS template"""
    model = SMSTemplate
    template_name = 'messaging/create_template.html'
    fields = ['name', 'template_type', 'subject', 'message', 'variables', 'is_active']
    
    def form_valid(self, form):
        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            form.instance.tenant_id = str(tenant.id)
        return super().form_valid(form)


class EditTemplateView(LoginRequiredMixin, UpdateView):
    """Edit SMS template"""
    model = SMSTemplate
    template_name = 'messaging/edit_template.html'
    fields = ['name', 'template_type', 'subject', 'message', 'variables', 'is_active']
    
    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return SMSTemplate.objects.none()
        return SMSTemplate.objects.filter(tenant_id=str(tenant.id))


class DeleteTemplateView(LoginRequiredMixin, DeleteView):
    """Delete SMS template"""
    model = SMSTemplate
    template_name = 'messaging/delete_template.html'
    
    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return SMSTemplate.objects.none()
        return SMSTemplate.objects.filter(tenant_id=str(tenant.id))


class SMSSettingsView(LoginRequiredMixin, View):
    """View SMS settings for tenant (read-only)"""
    template_name = 'messaging/sms_settings.html'
    
    def get(self, request):
        tenant = getattr(request, 'tenant', None)
        settings_obj = None
        
        # Debug logging
        logger.info(f"SMS Settings Debug - Tenant: {tenant}")
        if tenant:
            logger.info(f"Tenant ID: {tenant.id}, Tenant Name: {getattr(tenant, 'name', 'N/A')}")
        
        if tenant:
            try:
                settings_obj = TenantSMSSettings.objects.get(tenant_id=str(tenant.id))
                logger.info(f"Found SMS settings for tenant {tenant.id}")
            except TenantSMSSettings.DoesNotExist:
                logger.warning(f"No SMS settings found for tenant {tenant.id}")
                pass
        else:
            logger.warning("No tenant found in request")
        
        context = {
            'settings': settings_obj,
            'can_edit': False,  # Only system admin can edit
            'debug_tenant': tenant,  # Add for debugging
        }
        return render(request, self.template_name, context)


class TestSMSView(LoginRequiredMixin, View):
    """Test SMS functionality"""
    template_name = 'messaging/test_sms.html'
    
    def get(self, request):
        return render(request, self.template_name)
    
    def post(self, request):
        phone_number = request.POST.get('phone_number')
        test_message = request.POST.get('message', 'This is a test message from Autowash.')
        
        try:
            tenant = getattr(request, 'tenant', None)
            tenant_id = str(tenant.id) if tenant else None
            result = send_sms(
                tenant_id=tenant_id,
                recipient=phone_number,
                message=test_message
            )
            
            if result and result.status in ['sent', 'pending']:
                messages.success(request, f'Test SMS sent successfully! Message ID: {result.id}')
            elif result:
                messages.error(request, f'Test SMS failed: {result.error_message or "Unknown error"}')
            else:
                messages.error(request, 'Test SMS failed: No SMS settings configured for your business')
                
        except Exception as e:
            messages.error(request, f'Error sending test SMS: {str(e)}')
        
        return redirect('messaging:test_sms')


# API Views
class MessageStatusAPIView(LoginRequiredMixin, View):
    """Get SMS message status via API"""
    
    def get(self, request, pk):
        try:
            message = get_object_or_404(SMSMessage, pk=pk)
            
            # Check if user has access to this message
            tenant = getattr(request, 'tenant', None)
            if tenant and message.tenant_settings.tenant_id != str(tenant.id):
                return JsonResponse({'error': 'Access denied'}, status=403)
            
            return JsonResponse({
                'status': message.status,
                'created_at': message.created_at.isoformat(),
                'sent_at': message.sent_at.isoformat() if message.sent_at else None,
                'delivered_at': message.delivered_at.isoformat() if message.delivered_at else None,
                'error_message': message.error_message,
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


class SMSStatisticsAPIView(LoginRequiredMixin, View):
    """Get SMS statistics for tenant"""
    
    def get(self, request):
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return JsonResponse({'error': 'No tenant context'}, status=400)
        
        try:
            tenant_settings = TenantSMSSettings.objects.get(tenant_id=str(tenant.id))
            messages_qs = SMSMessage.objects.filter(tenant_settings=tenant_settings)
            
            # Get statistics
            total_messages = messages_qs.count()
            delivered = messages_qs.filter(status='delivered').count()
            failed = messages_qs.filter(status='failed').count()
            pending = messages_qs.filter(status='pending').count()
            
            # Monthly usage
            from datetime import datetime, timedelta
            month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            monthly_messages = messages_qs.filter(created_at__gte=month_start).count()
            
            return JsonResponse({
                'total_messages': total_messages,
                'delivered': delivered,
                'failed': failed,
                'pending': pending,
                'monthly_messages': monthly_messages,
                'monthly_limit': tenant_settings.monthly_limit,
                'daily_usage': tenant_settings.daily_usage,
                'daily_limit': tenant_settings.daily_limit,
            })
            
        except TenantSMSSettings.DoesNotExist:
            return JsonResponse({'error': 'SMS not configured for this tenant'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
