"""
Suspension Utilities
Helper functions for managing and checking suspension states
"""
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from apps.core.tenant_models import Tenant
from apps.subscriptions.models import Subscription
import logging

logger = logging.getLogger(__name__)


class SuspensionManager:
    """Centralized manager for suspension operations"""
    
    @staticmethod
    def suspend_user(user, reason="Administrative action", suspended_by=None):
        """
        Suspend a user account
        Args:
            user: User instance to suspend
            reason: Reason for suspension
            suspended_by: User who performed the suspension
        """
        try:
            user.is_active = False
            user.save()
            
            # Log the suspension
            logger.info(f"User {user.username} suspended by {suspended_by}. Reason: {reason}")
            
            # Send notification email
            SuspensionManager._send_suspension_notification(
                user=user,
                suspension_type="user_account",
                reason=reason
            )
            
            return True
        except Exception as e:
            logger.error(f"Error suspending user {user.username}: {e}")
            return False
    
    @staticmethod
    def suspend_business(business, reason="Administrative action", suspended_by=None):
        """
        Suspend a business (tenant)
        Args:
            business: Tenant instance to suspend
            reason: Reason for suspension
            suspended_by: User who performed the suspension
        """
        try:
            business.is_active = False
            business.rejection_reason = reason
            business.save()
            
            # Log the suspension
            logger.info(f"Business {business.name} suspended by {suspended_by}. Reason: {reason}")
            
            # Send notification email to business owner
            if business.owner:
                SuspensionManager._send_suspension_notification(
                    user=business.owner,
                    suspension_type="business",
                    reason=reason,
                    business=business
                )
            
            return True
        except Exception as e:
            logger.error(f"Error suspending business {business.name}: {e}")
            return False
    
    @staticmethod
    def suspend_subscription(subscription, reason="Payment issues", suspended_by=None):
        """
        Suspend a subscription
        Args:
            subscription: Subscription instance to suspend
            reason: Reason for suspension
            suspended_by: User who performed the suspension
        """
        try:
            subscription.status = 'suspended'
            subscription.cancellation_reason = reason
            subscription.save()
            
            # Log the suspension
            logger.info(f"Subscription {subscription.subscription_id} suspended by {suspended_by}. Reason: {reason}")
            
            # Send notification email to business owner
            if subscription.business and subscription.business.owner:
                SuspensionManager._send_suspension_notification(
                    user=subscription.business.owner,
                    suspension_type="subscription",
                    reason=reason,
                    business=subscription.business,
                    subscription=subscription
                )
            
            return True
        except Exception as e:
            logger.error(f"Error suspending subscription {subscription.subscription_id}: {e}")
            return False
    
    @staticmethod
    def suspend_employee(employee, reason="Policy violation", suspended_by=None):
        """
        Suspend an employee
        Args:
            employee: Employee instance to suspend
            reason: Reason for suspension
            suspended_by: User who performed the suspension
        """
        try:
            from apps.employees.models import Employee
            
            employee.status = 'suspended'
            employee.can_login = False
            employee.save()
            
            # Log the suspension
            logger.info(f"Employee {employee.employee_id} suspended by {suspended_by}. Reason: {reason}")
            
            # Send notification email to employee
            try:
                from django.contrib.auth.models import User
                user = User.objects.get(id=employee.user_id)
                SuspensionManager._send_suspension_notification(
                    user=user,
                    suspension_type="employee",
                    reason=reason,
                    employee=employee
                )
            except User.DoesNotExist:
                logger.warning(f"Could not find user for employee {employee.employee_id}")
            
            return True
        except Exception as e:
            logger.error(f"Error suspending employee {employee.employee_id}: {e}")
            return False
    
    @staticmethod
    def reactivate_user(user, reactivated_by=None):
        """Reactivate a suspended user"""
        try:
            user.is_active = True
            user.save()
            
            logger.info(f"User {user.username} reactivated by {reactivated_by}")
            
            # Send reactivation notification
            SuspensionManager._send_reactivation_notification(user, "user_account")
            
            return True
        except Exception as e:
            logger.error(f"Error reactivating user {user.username}: {e}")
            return False
    
    @staticmethod
    def reactivate_business(business, reactivated_by=None):
        """Reactivate a suspended business"""
        try:
            business.is_active = True
            business.rejection_reason = ""
            business.save()
            
            logger.info(f"Business {business.name} reactivated by {reactivated_by}")
            
            # Send reactivation notification
            if business.owner:
                SuspensionManager._send_reactivation_notification(business.owner, "business", business=business)
            
            return True
        except Exception as e:
            logger.error(f"Error reactivating business {business.name}: {e}")
            return False
    
    @staticmethod
    def reactivate_subscription(subscription, reactivated_by=None):
        """Reactivate a suspended subscription"""
        try:
            subscription.status = 'active'
            subscription.cancellation_reason = ""
            subscription.save()
            
            logger.info(f"Subscription {subscription.subscription_id} reactivated by {reactivated_by}")
            
            # Send reactivation notification
            if subscription.business and subscription.business.owner:
                SuspensionManager._send_reactivation_notification(
                    subscription.business.owner, 
                    "subscription", 
                    business=subscription.business,
                    subscription=subscription
                )
            
            return True
        except Exception as e:
            logger.error(f"Error reactivating subscription {subscription.subscription_id}: {e}")
            return False
    
    @staticmethod
    def reactivate_employee(employee, reactivated_by=None):
        """Reactivate a suspended employee"""
        try:
            from apps.employees.models import Employee
            
            employee.status = 'active'
            employee.can_login = True
            employee.save()
            
            logger.info(f"Employee {employee.employee_id} reactivated by {reactivated_by}")
            
            # Send reactivation notification
            try:
                from django.contrib.auth.models import User
                user = User.objects.get(id=employee.user_id)
                SuspensionManager._send_reactivation_notification(user, "employee", employee=employee)
            except User.DoesNotExist:
                logger.warning(f"Could not find user for employee {employee.employee_id}")
            
            return True
        except Exception as e:
            logger.error(f"Error reactivating employee {employee.employee_id}: {e}")
            return False
    
    @staticmethod
    def _send_suspension_notification(user, suspension_type, reason, business=None, subscription=None, employee=None):
        """Send email notification about suspension"""
        try:
            subject_map = {
                'user_account': 'Your AutoWash Account Has Been Suspended',
                'business': 'Your Business Has Been Suspended',
                'subscription': 'Your Subscription Has Been Suspended',
                'employee': 'Your Employee Account Has Been Suspended'
            }
            
            subject = subject_map.get(suspension_type, 'Account Suspended')
            
            message = f"""
            Dear {user.get_full_name() or user.username},
            
            Your {suspension_type.replace('_', ' ')} has been suspended.
            
            Reason: {reason}
            
            """
            
            if business:
                message += f"Business: {business.name}\n"
            
            if subscription:
                message += f"Subscription: {subscription.plan.name}\n"
            
            if employee:
                message += f"Employee ID: {employee.employee_id}\n"
            
            message += """
            If you believe this is an error, please contact our support team.
            
            Support Email: support@autowash.co.ke
            Support Phone: +254 700 000 000
            
            Best regards,
            AutoWash Support Team
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True
            )
            
        except Exception as e:
            logger.error(f"Error sending suspension notification to {user.email}: {e}")
    
    @staticmethod
    def _send_reactivation_notification(user, suspension_type, business=None, subscription=None, employee=None):
        """Send email notification about reactivation"""
        try:
            subject_map = {
                'user_account': 'Your AutoWash Account Has Been Reactivated',
                'business': 'Your Business Has Been Reactivated',
                'subscription': 'Your Subscription Has Been Reactivated',
                'employee': 'Your Employee Account Has Been Reactivated'
            }
            
            subject = subject_map.get(suspension_type, 'Account Reactivated')
            
            message = f"""
            Dear {user.get_full_name() or user.username},
            
            Good news! Your {suspension_type.replace('_', ' ')} has been reactivated.
            
            """
            
            if business:
                message += f"Business: {business.name}\n"
                message += f"You can now access your business at: /business/{business.slug}/\n"
            
            if subscription:
                message += f"Subscription: {subscription.plan.name}\n"
            
            if employee:
                message += f"Employee ID: {employee.employee_id}\n"
            
            message += """
            You can now resume using all services and features.
            
            If you have any questions, please contact our support team.
            
            Support Email: support@autowash.co.ke
            Support Phone: +254 700 000 000
            
            Best regards,
            AutoWash Support Team
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True
            )
            
        except Exception as e:
            logger.error(f"Error sending reactivation notification to {user.email}: {e}")


class SuspensionChecker:
    """Utility class for checking suspension states"""
    
    @staticmethod
    def is_user_suspended(user):
        """Check if user is suspended"""
        return not user.is_active
    
    @staticmethod
    def is_business_suspended(business):
        """Check if business is suspended"""
        return not business.is_active
    
    @staticmethod
    def is_subscription_suspended(subscription):
        """Check if subscription is suspended"""
        return subscription.status == 'suspended'
    
    @staticmethod
    def is_employee_suspended(employee):
        """Check if employee is suspended"""
        return employee.status == 'suspended'
    
    @staticmethod
    def get_user_suspension_status(user):
        """Get comprehensive suspension status for a user"""
        status = {
            'user_suspended': SuspensionChecker.is_user_suspended(user),
            'businesses': [],
            'employee_accounts': []
        }
        
        # Check owned businesses
        for business in user.owned_tenants.all():
            business_status = {
                'business': business,
                'suspended': SuspensionChecker.is_business_suspended(business),
                'subscription_suspended': False
            }
            
            if hasattr(business, 'subscription') and business.subscription:
                business_status['subscription_suspended'] = SuspensionChecker.is_subscription_suspended(business.subscription)
            
            status['businesses'].append(business_status)
        
        # Check employee accounts across all active businesses
        try:
            from apps.employees.models import Employee
            from apps.core.database_router import tenant_context
            
            active_businesses = Tenant.objects.filter(is_active=True, is_approved=True)
            
            for business in active_businesses:
                try:
                    with tenant_context(business):
                        employee = Employee.objects.filter(
                            user_id=user.id,
                            is_active=True
                        ).first()
                        
                        if employee:
                            status['employee_accounts'].append({
                                'business': business,
                                'employee': employee,
                                'suspended': SuspensionChecker.is_employee_suspended(employee)
                            })
                except Exception:
                    continue
        except Exception:
            pass
        
        return status
