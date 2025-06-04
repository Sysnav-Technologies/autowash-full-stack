from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django_tenants.utils import schema_context
from django.core.management import call_command
from django.utils import timezone
from django.conf import settings
from apps.accounts.models import Business, BusinessVerification

class Command(BaseCommand):
    help = 'Create schemas for verified businesses that don\'t have them yet'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Find verified businesses without schemas
        verified_businesses = Business.objects.filter(
            is_verified=True,
            verification__status='verified'
        )
        
        businesses_needing_schemas = []
        for business in verified_businesses:
            # Check if schema exists
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s",
                    [business.schema_name]
                )
                if not cursor.fetchone():
                    businesses_needing_schemas.append(business)
        
        if not businesses_needing_schemas:
            self.stdout.write(self.style.SUCCESS('All verified businesses have schemas'))
            return
        
        self.stdout.write(f"Found {len(businesses_needing_schemas)} businesses needing schemas:")
        
        for business in businesses_needing_schemas:
            self.stdout.write(f"  - {business.name} (Schema: {business.schema_name})")
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN: No schemas were created'))
            return
        
        created_count = 0
        failed_count = 0
        
        for business in businesses_needing_schemas:
            try:
                self.stdout.write(f"Creating schema for: {business.name}")
                
                # Create schema
                with connection.cursor() as cursor:
                    cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{business.schema_name}"')
                
                # Run migrations
                with schema_context(business.schema_name):
                    call_command('migrate', 
                               '--run-syncdb',
                               verbosity=0,
                               interactive=False)
                
                # Create owner employee record
                try:
                    with schema_context(business.schema_name):
                        from apps.employees.models import Employee
                        Employee.objects.get_or_create(
                            user=business.owner,
                            defaults={
                                'role': 'owner',
                                'first_name': business.owner.first_name,
                                'last_name': business.owner.last_name,
                                'email': business.owner.email,
                                'is_active': True,
                                'hire_date': timezone.now().date(),
                            }
                        )
                except Exception as emp_error:
                    self.stdout.write(
                        self.style.WARNING(f"Failed to create employee for {business.name}: {emp_error}")
                    )
                
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Schema created for: {business.name}")
                )
                
            except Exception as e:
                failed_count += 1
                self.stdout.write(
                    self.style.ERROR(f"✗ Failed to create schema for {business.name}: {e}")
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Completed: {created_count} schemas created, {failed_count} failed')
        )