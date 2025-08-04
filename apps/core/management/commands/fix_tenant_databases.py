"""
Management command to fix tenant database setup
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.core.tenant_models import Tenant
from apps.core.database_router import TenantDatabaseManager
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Fix tenant database credentials and setup'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-id',
            type=int,
            help='Specific tenant ID to fix',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Fix all tenants',
        )

    def handle(self, *args, **options):
        if options['tenant_id']:
            try:
                tenant = Tenant.objects.get(id=options['tenant_id'])
                self.fix_tenant(tenant)
            except Tenant.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Tenant with ID {options["tenant_id"]} not found')
                )
        elif options['all']:
            tenants = Tenant.objects.filter(is_active=True)
            for tenant in tenants:
                self.fix_tenant(tenant)
        else:
            self.stdout.write(
                self.style.ERROR('Please specify --tenant-id or --all')
            )

    def fix_tenant(self, tenant):
        """Fix a specific tenant"""
        self.stdout.write(f'Fixing tenant: {tenant.name}')
        
        # Get main database credentials
        main_db = settings.DATABASES['default']
        
        # Update tenant to use same credentials as main database
        tenant.database_user = main_db['USER']
        tenant.database_password = main_db['PASSWORD']
        tenant.save()
        
        self.stdout.write(f'Updated tenant credentials')
        
        # Add tenant database to settings
        TenantDatabaseManager.add_tenant_to_settings(tenant)
        self.stdout.write(f'Added tenant database to settings')
        
        # Run migrations for tenant database
        db_alias = f"tenant_{tenant.id}"
        try:
            call_command('migrate', database=db_alias, verbosity=1)
            self.stdout.write(
                self.style.SUCCESS(f'Successfully migrated tenant database: {db_alias}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to migrate tenant database: {e}')
            )
