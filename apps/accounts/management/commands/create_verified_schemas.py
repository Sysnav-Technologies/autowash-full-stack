from django.core.management.base import BaseCommand
from django.db import transaction
from apps.core.tenant_models import Tenant
from apps.core.database_router import TenantDatabaseManager
from django.core.management import call_command

class Command(BaseCommand):
    help = 'Create databases for verified tenants that do not have them'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-id',
            type=int,
            help='Create database for specific tenant ID only',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually doing it',
        )
        parser.add_argument(
            '--run-migrations',
            action='store_true',
            help='Run migrations after creating databases',
        )

    def handle(self, *args, **options):
        tenant_id = options.get('tenant_id')
        dry_run = options.get('dry_run', False)
        run_migrations = options.get('run_migrations', False)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        if tenant_id:
            tenants = Tenant.objects.filter(id=tenant_id, is_verified=True, is_active=True)
        else:
            tenants = Tenant.objects.filter(is_verified=True, is_active=True)
        
        if not tenants.exists():
            self.stdout.write(self.style.WARNING('No verified tenants found'))
            return
        
        db_manager = TenantDatabaseManager()
        created_count = 0
        exists_count = 0
        
        for tenant in tenants:
            try:
                db_name = tenant.get_database_name()
                
                if db_manager.database_exists(db_name):
                    self.stdout.write(f'Database already exists for tenant: {tenant.name}')
                    exists_count += 1
                    continue
                
                if not dry_run:
                    # Create the database
                    db_manager.create_database(db_name)
                    self.stdout.write(
                        self.style.SUCCESS(f'Created database for tenant: {tenant.name}')
                    )
                    
                    if run_migrations:
                        # Run migrations for the new database
                        call_command('migrate', database=db_name, verbosity=0)
                        self.stdout.write(f'Ran migrations for tenant: {tenant.name}')
                        
                        # Create default data
                        call_command('create_payment_methods', tenant_slug=tenant.schema_name, verbosity=0)
                        self.stdout.write(f'Created default data for tenant: {tenant.name}')
                    
                    created_count += 1
                else:
                    self.stdout.write(f'Would create database for tenant: {tenant.name}')
                    created_count += 1
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error processing tenant {tenant.name}: {str(e)}')
                )
        
        action = 'Would create' if dry_run else 'Created'
        self.stdout.write(
            self.style.SUCCESS(
                f'{action} {created_count} databases, {exists_count} already existed'
            )
        )
