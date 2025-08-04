"""
Management command to migrate tenant databases
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
from apps.core.tenant_models import Tenant
from apps.core.database_router import TenantDatabaseManager


class Command(BaseCommand):
    help = 'Run migrations on tenant databases'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant',
            type=str,
            help='Specific tenant slug to migrate (migrates all if not specified)'
        )
        parser.add_argument(
            '--app',
            type=str,
            help='Specific app to migrate'
        )

    def handle(self, *args, **options):
        if options.get('tenant'):
            # Migrate specific tenant
            try:
                tenant = Tenant.objects.get(slug=options['tenant'])
                self.migrate_tenant(tenant, options.get('app'))
            except Tenant.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"Tenant '{options['tenant']}' not found")
                )
        else:
            # Migrate all tenants
            tenants = Tenant.objects.filter(is_active=True)
            self.stdout.write(f"Migrating {tenants.count()} tenant databases...")
            
            for tenant in tenants:
                self.migrate_tenant(tenant, options.get('app'))

    def migrate_tenant(self, tenant, app=None):
        """Migrate a specific tenant database"""
        self.stdout.write(f"Migrating tenant: {tenant.name} ({tenant.slug})")
        
        # Ensure tenant database is in settings
        TenantDatabaseManager.add_tenant_to_settings(tenant)
        
        db_alias = f"tenant_{tenant.id}"
        
        try:
            # Run migrations
            if app:
                call_command('migrate', app, database=db_alias, verbosity=1)
            else:
                call_command('migrate', database=db_alias, verbosity=1)
            
            self.stdout.write(
                self.style.SUCCESS(f"✓ Successfully migrated {tenant.name}")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Error migrating {tenant.name}: {str(e)}")
            )
