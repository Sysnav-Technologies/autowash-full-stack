from celery import shared_task
from django.db import connection
from django_tenants.utils import schema_context
from django.core.management import call_command
from .models import Business, BusinessSettings, BusinessVerification
import logging
import time

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def setup_business_schema(self, business_id):
    """Create business schema and run migrations in background"""
    try:
        business = Business.objects.get(id=business_id)
        
        logger.info(f"Starting schema setup for business: {business.name}")
        
        # Add a small delay to ensure business is saved properly
        time.sleep(2)
        
        # Create schema
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{business.schema_name}"')
        
        logger.info(f"Schema created: {business.schema_name}")
        
        # Run migrations in the new schema with reduced verbosity
        with schema_context(business.schema_name):
            call_command('migrate', 
                        '--run-syncdb',
                        verbosity=0,
                        interactive=False)
        
        logger.info(f"Migrations completed for: {business.schema_name}")
        
        # Create related objects in public schema
        BusinessSettings.objects.get_or_create(business=business)
        BusinessVerification.objects.get_or_create(business=business)
        
        # Mark business as ready
        business.is_active = True
        business.save()
        
        logger.info(f"Business setup completed: {business.name}")
        
        # Optional: Send notification to user
        try:
            send_business_ready_notification.delay(business.id)
        except:
            pass  # Notification is optional
        
        return f"Business setup completed for {business.name}"
        
    except Exception as exc:
        logger.error(f"Business setup failed for business_id {business_id}: {exc}")
        # Don't retry more than 3 times, and wait longer between retries
        raise self.retry(countdown=60 * (self.request.retries + 1), exc=exc)

@shared_task
def send_business_ready_notification(business_id):
    """Send notification when business is ready"""
    try:
        business = Business.objects.get(id=business_id)
        
        # You can implement email notification here
        # For now, just log it
        logger.info(f"Business {business.name} is ready for user {business.owner.email}")
        
        # Example email notification (uncomment if you want to use it):
        # from django.core.mail import send_mail
        # from django.conf import settings
        # 
        # send_mail(
        #     subject=f'Your business "{business.name}" is ready!',
        #     message=f'Congratulations! Your business setup is complete. You can now access your dashboard.',
        #     from_email=settings.DEFAULT_FROM_EMAIL,
        #     recipient_list=[business.owner.email],
        #     fail_silently=True,
        # )
        
        return f"Notification sent for {business.name}"
        
    except Exception as exc:
        logger.error(f"Failed to send notification for business_id {business_id}: {exc}")
        return f"Failed to send notification: {exc}"

@shared_task
def cleanup_failed_businesses():
    """Clean up businesses that failed to set up properly"""
    try:
        # Find businesses older than 1 hour that are still not active
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_time = timezone.now() - timedelta(hours=1)
        failed_businesses = Business.objects.filter(
            is_active=False,
            created_at__lt=cutoff_time
        )
        
        for business in failed_businesses:
            logger.warning(f"Found failed business setup: {business.name} (ID: {business.id})")
            
            # You could either:
            # 1. Retry the setup
            # setup_business_schema.delay(business.id)
            
            # 2. Or mark for manual review
            # business.needs_manual_review = True
            # business.save()
            
            # 3. Or send alert to admin
            # send_admin_alert.delay(f"Business setup failed: {business.name}")
        
        return f"Processed {failed_businesses.count()} failed businesses"
        
    except Exception as exc:
        logger.error(f"Failed to cleanup businesses: {exc}")
        return f"Cleanup failed: {exc}"