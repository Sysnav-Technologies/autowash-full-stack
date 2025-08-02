from celery import shared_task
from django.db import connection, connections
from django.core.management import call_command
from apps.core.tenant_models import Tenant, TenantSettings
import logging
import time

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def setup_new_tenant(self, tenant_id):
    """
    Setup a new tenant after creation
    Creates the database and runs initial setup
    """
    try:
        tenant = Tenant.objects.get(id=tenant_id)
        logger.info(f"Setting up new tenant: {tenant.schema_name}")
        
        # Create the tenant database
        from apps.core.database_router import TenantDatabaseManager
        db_manager = TenantDatabaseManager()
        
        # Create database if it doesn't exist
        if not db_manager.database_exists(tenant.get_database_name()):
            db_manager.create_database(tenant.get_database_name())
            logger.info(f"Created database for tenant: {tenant.schema_name}")
        
        # Run migrations for the tenant database
        db_alias = tenant.get_database_name()
        call_command('migrate', database=db_alias, verbosity=0)
        logger.info(f"Ran migrations for tenant: {tenant.schema_name}")
        
        # Create tenant settings
        TenantSettings.objects.using(db_alias).get_or_create(tenant=tenant)
        
        # Setup default data for the tenant
        call_command('create_payment_methods', tenant_slug=tenant.schema_name, verbosity=0)
        logger.info(f"Created default payment methods for tenant: {tenant.schema_name}")
        
        logger.info(f"Successfully setup tenant: {tenant.schema_name}")
        return f"Tenant {tenant.schema_name} setup completed"
        
    except Tenant.DoesNotExist:
        logger.error(f"Tenant with id {tenant_id} does not exist")
        raise self.retry(countdown=60)
    except Exception as e:
        logger.error(f"Error setting up tenant {tenant_id}: {str(e)}")
        raise self.retry(countdown=60, exc=e)

@shared_task(bind=True, max_retries=3)
def initialize_tenant_data(self, tenant_id):
    """
    Initialize basic data for a tenant
    """
    try:
        tenant = Tenant.objects.get(id=tenant_id)
        db_alias = tenant.get_database_name()
        
        logger.info(f"Initializing data for tenant: {tenant.schema_name}")
        
        # Create settings record
        TenantSettings.objects.using(db_alias).get_or_create(
            tenant=tenant,
            defaults={
                'business_name': tenant.name,
                'is_active': True,
                'timezone': 'Africa/Nairobi',
                'currency': 'KES',
            }
        )
        
        logger.info(f"Initialized data for tenant: {tenant.schema_name}")
        return f"Data initialization completed for {tenant.schema_name}"
        
    except Tenant.DoesNotExist:
        logger.error(f"Tenant with id {tenant_id} does not exist")
        raise self.retry(countdown=60)
    except Exception as e:
        logger.error(f"Error initializing data for tenant {tenant_id}: {str(e)}")
        raise self.retry(countdown=60, exc=e)

@shared_task
def cleanup_inactive_tenants():
    """
    Cleanup inactive tenants (marked for deletion)
    """
    try:
        # Find tenants marked for deletion older than 30 days
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=30)
        inactive_tenants = Tenant.objects.filter(
            is_active=False,
            updated_at__lt=cutoff_date
        )
        
        cleaned_count = 0
        for tenant in inactive_tenants:
            try:
                # Drop the tenant database
                from apps.core.database_router import TenantDatabaseManager
                db_manager = TenantDatabaseManager()
                
                if db_manager.database_exists(tenant.get_database_name()):
                    db_manager.drop_database(tenant.get_database_name())
                    logger.info(f"Dropped database for inactive tenant: {tenant.schema_name}")
                
                # Delete the tenant record
                tenant.delete()
                cleaned_count += 1
                
            except Exception as e:
                logger.error(f"Error cleaning up tenant {tenant.schema_name}: {str(e)}")
        
        logger.info(f"Cleaned up {cleaned_count} inactive tenants")
        return f"Cleaned up {cleaned_count} inactive tenants"
        
    except Exception as e:
        logger.error(f"Error in cleanup task: {str(e)}")
        raise

@shared_task
def tenant_health_check():
    """
    Perform health checks on all tenants
    """
    try:
        healthy_count = 0
        unhealthy_count = 0
        
        for tenant in Tenant.objects.filter(is_active=True):
            try:
                # Check if tenant database is accessible
                db_alias = tenant.get_database_name()
                connection = connections[db_alias]
                
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    
                healthy_count += 1
                
            except Exception as e:
                logger.warning(f"Tenant {tenant.schema_name} health check failed: {str(e)}")
                unhealthy_count += 1
        
        logger.info(f"Tenant health check: {healthy_count} healthy, {unhealthy_count} unhealthy")
        return f"Health check completed: {healthy_count} healthy, {unhealthy_count} unhealthy"
        
    except Exception as e:
        logger.error(f"Error in health check task: {str(e)}")
        raise