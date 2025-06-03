from django.utils import timezone
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from datetime import datetime, timedelta
import json
import logging

from .models import (
    Notification, NotificationTemplate, NotificationPreference,
    NotificationLog, NotificationDigest, NotificationCategory
)

logger = logging.getLogger(__name__)

class NotificationManager:
    """Centralized notification management"""
    
    def __init__(self):
        self.logger = logger
    
    def create_notification(self, user, title, message, **kwargs):
        """Create a new notification"""
        try:
            # Get user preferences
            preferences = self.get_user_preferences(user)
            
            # Check if user should receive this notification
            notification_type = kwargs.get('notification_type', 'info')
            category = kwargs.get('category')
            
            if not preferences.should_send_notification(notification_type, category):
                self.logger.info(f"Notification blocked by user preferences: {user.email}")
                return None
            
            # Create notification
            notification = Notification.objects.create(
                user=user,
                employee=getattr(user, 'employee_profile', None),
                title=title,
                message=message,
                **kwargs
            )
            
            # Send via other channels if enabled
            if preferences.email_notifications and kwargs.get('send_email', False):
                self.send_email_notification(notification)
            
            if preferences.sms_notifications and kwargs.get('send_sms', False):
                self.send_sms_notification(notification)
            
            self.logger.info(f"Notification created: {notification.id} for {user.email}")
            return notification
            
        except Exception as e:
            self.logger.error(f"Error creating notification: {str(e)}")
            return None
    
    def create_from_template(self, template_name, user, context=None, **kwargs):
        """Create notification from template"""
        try:
            template = NotificationTemplate.objects.get(
                name=template_name,
                is_active=True
            )
            
            notification = template.create_notification(
                user=user,
                context=context,
                **kwargs
            )
            
            return notification
            
        except NotificationTemplate.DoesNotExist:
            self.logger.error(f"Template not found: {template_name}")
            return None
        except Exception as e:
            self.logger.error(f"Error creating notification from template: {str(e)}")
            return None
    
    def trigger_event(self, event_name, context=None, **kwargs):
        """Trigger notifications based on event"""
        try:
            templates = NotificationTemplate.objects.filter(
                trigger_event=event_name,
                is_active=True
            )
            
            notifications_created = []
            
            for template in templates:
                # Determine recipients based on template settings
                recipients = self.get_template_recipients(template, context)
                
                for user in recipients:
                    notification = template.create_notification(
                        user=user,
                        context=context,
                        **kwargs
                    )
                    if notification:
                        notifications_created.append(notification)
            
            self.logger.info(f"Event '{event_name}' triggered {len(notifications_created)} notifications")
            return notifications_created
            
        except Exception as e:
            self.logger.error(f"Error triggering event '{event_name}': {str(e)}")
            return []
    
    def get_template_recipients(self, template, context=None):
        """Get recipients for a notification template"""
        recipients = []
        
        # Add specific target users
        recipients.extend(template.target_users.filter(is_active=True))
        
        # Add users by role
        if template.target_roles:
            try:
                from apps.employees.models import Employee
                employees = Employee.objects.filter(
                    role__in=template.target_roles,
                    is_active=True
                )
                recipients.extend([emp.user for emp in employees if emp.user])
            except ImportError:
                pass
        
        # Remove duplicates
        recipients = list(set(recipients))
        
        return recipients
    
    def send_email_notification(self, notification):
        """Send notification via email"""
        try:
            if not notification.user.email:
                return False
            
            # Create email log
            log = NotificationLog.objects.create(
                notification=notification,
                channel='email',
                recipient_email=notification.user.email,
                status='pending'
            )
            
            # Render email content
            context = {
                'notification': notification,
                'user': notification.user,
                'business': getattr(notification, 'business', None),
            }
            
            html_content = render_to_string('notifications/email/notification.html', context)
            text_content = render_to_string('notifications/email/notification.txt', context)
            
            # Send email
            subject = f"[Autowash] {notification.title}"
            
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[notification.user.email]
            )
            msg.attach_alternative(html_content, "text/html")
            
            msg.send()
            
            # Update log and notification
            log.mark_as_sent()
            notification.sent_via_email = True
            notification.email_sent_at = timezone.now()
            notification.save(update_fields=['sent_via_email', 'email_sent_at'])
            
            self.logger.info(f"Email sent for notification {notification.id}")
            return True
            
        except Exception as e:
            if 'log' in locals():
                log.mark_as_failed(str(e))
            self.logger.error(f"Error sending email for notification {notification.id}: {str(e)}")
            return False
    
    def send_sms_notification(self, notification):
        """Send notification via SMS"""
        try:
            # Get user's phone number
            phone = None
            if hasattr(notification.user, 'profile') and notification.user.profile.phone:
                phone = str(notification.user.profile.phone)
            elif hasattr(notification.user, 'employee_profile') and notification.user.employee_profile.phone:
                phone = str(notification.user.employee_profile.phone)
            
            if not phone:
                return False
            
            # Create SMS log
            log = NotificationLog.objects.create(
                notification=notification,
                channel='sms',
                recipient_phone=phone,
                status='pending'
            )
            
            # Prepare SMS content (limit to 160 characters)
            sms_content = f"{notification.title}: {notification.message}"
            if len(sms_content) > 160:
                sms_content = sms_content[:157] + "..."
            
            # Send SMS (implement with your SMS provider)
            # This is a placeholder - replace with actual SMS service
            success = self.send_sms_via_provider(phone, sms_content)
            
            if success:
                log.mark_as_sent()
                notification.sent_via_sms = True
                notification.sms_sent_at = timezone.now()
                notification.save(update_fields=['sent_via_sms', 'sms_sent_at'])
                
                self.logger.info(f"SMS sent for notification {notification.id}")
                return True
            else:
                log.mark_as_failed("SMS provider error")
                return False
                
        except Exception as e:
            if 'log' in locals():
                log.mark_as_failed(str(e))
            self.logger.error(f"Error sending SMS for notification {notification.id}: {str(e)}")
            return False
    
    def send_sms_via_provider(self, phone, message):
        """Send SMS via provider (implement with your SMS service)"""
        # Placeholder - implement with Africa's Talking, Twilio, etc.
        # Example for Africa's Talking:
        # from africastalking import SMS
        # sms = SMS()
        # response = sms.send(message, [phone])
        # return response['SMSMessageData']['Message'] == 'Sent'
        
        self.logger.info(f"SMS would be sent to {phone}: {message}")
        return True  # Placeholder
    
    def get_user_preferences(self, user):
        """Get or create user notification preferences"""
        preferences, created = NotificationPreference.objects.get_or_create(
            user=user
        )
        return preferences
    
    def bulk_create_notifications(self, users, title, message, **kwargs):
        """Create notifications for multiple users efficiently"""
        notifications = []
        
        for user in users:
            notification = Notification(
                user=user,
                employee=getattr(user, 'employee_profile', None),
                title=title,
                message=message,
                **kwargs
            )
            notifications.append(notification)
        
        # Bulk create for efficiency
        created_notifications = Notification.objects.bulk_create(notifications)
        
        self.logger.info(f"Bulk created {len(created_notifications)} notifications")
        return created_notifications
    
    def cleanup_old_notifications(self, days=30):
        """Clean up old notifications"""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Delete old read notifications
        deleted_count = Notification.objects.filter(
            is_read=True,
            read_at__lt=cutoff_date
        ).delete()[0]
        
        # Delete old archived notifications
        archived_deleted = Notification.objects.filter(
            is_archived=True,
            archived_at__lt=cutoff_date
        ).delete()[0]
        
        total_deleted = deleted_count + archived_deleted
        
        self.logger.info(f"Cleaned up {total_deleted} old notifications")
        return total_deleted
    
    def generate_digest(self, user, digest_type='weekly'):
        """Generate notification digest for user"""
        try:
            preferences = self.get_user_preferences(user)
            
            if preferences.digest_frequency == 'never':
                return None
            
            # Calculate period
            end_date = timezone.now()
            if digest_type == 'daily':
                start_date = end_date - timedelta(days=1)
            elif digest_type == 'weekly':
                start_date = end_date - timedelta(days=7)
            elif digest_type == 'monthly':
                start_date = end_date - timedelta(days=30)
            else:
                return None
            
            # Get notifications for period
            notifications = Notification.objects.filter(
                user=user,
                created_at__gte=start_date,
                created_at__lte=end_date,
                is_archived=False
            ).order_by('-created_at')
            
            if not notifications.exists():
                return None
            
            # Create digest
            digest = NotificationDigest.objects.create(
                user=user,
                digest_type=digest_type,
                period_start=start_date,
                period_end=end_date
            )
            
            digest.notifications.set(notifications)
            digest.generate_content()
            
            # Send digest
            if digest.send():
                self.logger.info(f"Digest sent to {user.email}")
                return digest
            else:
                self.logger.error(f"Failed to send digest to {user.email}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error generating digest for {user.email}: {str(e)}")
            return None

class NotificationTemplateManager:
    """Manage notification templates"""
    
    def __init__(self):
        self.logger = logger
    
    def create_default_templates(self):
        """Create default notification templates"""
        templates = [
            {
                'name': 'Order Completed',
                'trigger_event': 'order_completed',
                'title_template': 'Order {{order_number}} Completed',
                'message_template': 'Your car wash order {{order_number}} has been completed successfully. Thank you for choosing our service!',
                'notification_type': 'success',
                'priority': 'normal',
                'send_email': True,
            },
            {
                'name': 'Payment Received',
                'trigger_event': 'payment_received',
                'title_template': 'Payment Received',
                'message_template': 'We have received your payment of KES {{amount}} for order {{order_number}}. Thank you!',
                'notification_type': 'success',
                'priority': 'normal',
                'send_email': True,
            },
            {
                'name': 'Low Inventory Alert',
                'trigger_event': 'inventory_low',
                'title_template': 'Low Inventory Alert',
                'message_template': 'Item {{item_name}} is running low. Current stock: {{current_stock}}. Please reorder soon.',
                'notification_type': 'warning',
                'priority': 'high',
                'target_roles': ['owner', 'manager'],
                'send_email': True,
            },
            {
                'name': 'Service Reminder',
                'trigger_event': 'service_reminder',
                'title_template': 'Service Reminder',
                'message_template': 'Hi {{customer_name}}, it\'s time for your regular car wash service. Book your appointment today!',
                'notification_type': 'reminder',
                'priority': 'normal',
                'send_email': True,
                'send_sms': True,
            },
        ]
        
        created_count = 0
        for template_data in templates:
            template, created = NotificationTemplate.objects.get_or_create(
                name=template_data['name'],
                defaults=template_data
            )
            if created:
                created_count += 1
        
        self.logger.info(f"Created {created_count} default notification templates")
        return created_count
    
    def create_default_categories(self):
        """Create default notification categories"""
        categories = [
            {
                'name': 'Orders',
                'description': 'Order related notifications',
                'icon': 'fas fa-shopping-cart',
                'color': 'primary',
            },
            {
                'name': 'Payments',
                'description': 'Payment related notifications',
                'icon': 'fas fa-credit-card',
                'color': 'success',
            },
            {
                'name': 'Inventory',
                'description': 'Inventory and stock notifications',
                'icon': 'fas fa-boxes',
                'color': 'warning',
            },
            {
                'name': 'System',
                'description': 'System and maintenance notifications',
                'icon': 'fas fa-cog',
                'color': 'secondary',
            },
            {
                'name': 'Reminders',
                'description': 'Reminders and scheduled notifications',
                'icon': 'fas fa-clock',
                'color': 'info',
            },
        ]
        
        created_count = 0
        for category_data in categories:
            category, created = NotificationCategory.objects.get_or_create(
                name=category_data['name'],
                defaults=category_data
            )
            if created:
                created_count += 1
        
        self.logger.info(f"Created {created_count} default notification categories")
        return created_count

# Convenience functions for common notification patterns
def notify_user(user, title, message, **kwargs):
    """Quick function to notify a single user"""
    manager = NotificationManager()
    return manager.create_notification(user, title, message, **kwargs)

def notify_role(role, title, message, **kwargs):
    """Notify all users with a specific role"""
    try:
        from apps.employees.models import Employee
        employees = Employee.objects.filter(role=role, is_active=True)
        users = [emp.user for emp in employees if emp.user]
        
        manager = NotificationManager()
        return manager.bulk_create_notifications(users, title, message, **kwargs)
    except ImportError:
        return []

def notify_all_staff(title, message, **kwargs):
    """Notify all active staff members"""
    try:
        from apps.employees.models import Employee
        employees = Employee.objects.filter(is_active=True)
        users = [emp.user for emp in employees if emp.user]
        
        manager = NotificationManager()
        return manager.bulk_create_notifications(users, title, message, **kwargs)
    except ImportError:
        return []

def trigger_notification_event(event_name, context=None, **kwargs):
    """Trigger notification event"""
    manager = NotificationManager()
    return manager.trigger_event(event_name, context, **kwargs)

# Scheduled tasks (to be used with Celery or cron)
def send_scheduled_notifications():
    """Send notifications that are scheduled"""
    now = timezone.now()
    
    scheduled_notifications = Notification.objects.filter(
        scheduled_for__lte=now,
        scheduled_for__isnull=False,
        is_read=False,
        is_archived=False
    )
    
    manager = NotificationManager()
    sent_count = 0
    
    for notification in scheduled_notifications:
        # Clear scheduled_for to prevent re-sending
        notification.scheduled_for = None
        notification.save(update_fields=['scheduled_for'])
        
        # Send via enabled channels
        preferences = manager.get_user_preferences(notification.user)
        
        if preferences.email_notifications:
            manager.send_email_notification(notification)
            sent_count += 1
        
        if preferences.sms_notifications:
            manager.send_sms_notification(notification)
    
    logger.info(f"Sent {sent_count} scheduled notifications")
    return sent_count

def cleanup_notifications():
    """Clean up old notifications"""
    manager = NotificationManager()
    return manager.cleanup_old_notifications()

def generate_notification_digests():
    """Generate and send notification digests"""
    from django.contrib.auth.models import User
    
    manager = NotificationManager()
    sent_count = 0
    
    # Get users who want digests
    preferences = NotificationPreference.objects.exclude(digest_frequency='never')
    
    for pref in preferences:
        try:
            digest = manager.generate_digest(pref.user, pref.digest_frequency)
            if digest:
                sent_count += 1
        except Exception as e:
            logger.error(f"Error generating digest for {pref.user.email}: {str(e)}")
    
    logger.info(f"Generated {sent_count} notification digests")
    return sent_count