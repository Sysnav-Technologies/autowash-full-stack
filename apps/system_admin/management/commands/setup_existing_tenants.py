"""
Management command to setup tenant databases for approved businesses
This is useful for businesses that were approved before the automatic setup was implemented
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.core.tenant_models import Tenant
from apps.system_admin.views import setup_tenant_after_approval
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Setup tenant databases for approved businesses that need it'

    def add_arguments(self, parser):
        parser.add_argument(
            '--business-id',
            type=str,
            help='Specific business ID to setup',
        )
        parser.add_argument(
            '--all-approved',
            action='store_true',
            help='Setup all approved businesses that need it',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually doing it',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🏗️  TENANT DATABASE SETUP TOOL')
        )
        self.stdout.write('=' * 60)

        if options['business_id']:
            try:
                business = Tenant.objects.get(id=options['business_id'])
                self.setup_single_business(business, options['dry_run'])
            except Tenant.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'❌ Business with ID {options["business_id"]} not found')
                )
        elif options['all_approved']:
            self.setup_all_approved_businesses(options['dry_run'])
        else:
            self.stdout.write(
                self.style.ERROR('❌ Please specify --business-id or --all-approved')
            )

    def setup_single_business(self, business, dry_run=False):
        """Setup a single business"""
        self.stdout.write(f'\n📋 Checking business: {business.name}')
        
        needs_setup = self.check_if_needs_setup(business)
        
        if not needs_setup:
            self.stdout.write(
                self.style.WARNING(f'⚠️  Business "{business.name}" appears to already be set up')
            )
            return
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'🔍 DRY RUN: Would setup tenant database for "{business.name}"')
            )
            return
        
        self.stdout.write(f'🚀 Setting up tenant database for: {business.name}')
        
        # Get admin user for the setup
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            self.stdout.write(
                self.style.ERROR('❌ No superuser found to perform setup')
            )
            return
        
        try:
            success = setup_tenant_after_approval(business, admin_user)
            
            if success:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Successfully setup tenant for: {business.name}')
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f'❌ Failed to setup tenant for: {business.name}')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error setting up {business.name}: {str(e)}')
            )

    def setup_all_approved_businesses(self, dry_run=False):
        """Setup all approved businesses that need it"""
        
        # Get all approved businesses
        approved_businesses = Tenant.objects.filter(
            is_approved=True,
            is_active=True
        ).order_by('created_at')
        
        self.stdout.write(f'\n📊 Found {approved_businesses.count()} approved businesses')
        
        businesses_needing_setup = []
        
        for business in approved_businesses:
            if self.check_if_needs_setup(business):
                businesses_needing_setup.append(business)
        
        if not businesses_needing_setup:
            self.stdout.write(
                self.style.SUCCESS('✅ All approved businesses are already set up!')
            )
            return
        
        self.stdout.write(f'\n🔧 Found {len(businesses_needing_setup)} businesses needing setup:')
        
        for business in businesses_needing_setup:
            self.stdout.write(f'  - {business.name} (ID: {business.id})')
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('\n🔍 DRY RUN: No actual setup performed')
            )
            return
        
        # Get admin user for the setup
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            self.stdout.write(
                self.style.ERROR('❌ No superuser found to perform setup')
            )
            return
        
        self.stdout.write('\n🚀 Starting tenant setup process...')
        
        success_count = 0
        failed_count = 0
        
        for business in businesses_needing_setup:
            self.stdout.write(f'\n📋 Setting up: {business.name}')
            
            try:
                success = setup_tenant_after_approval(business, admin_user)
                
                if success:
                    self.stdout.write(
                        self.style.SUCCESS(f'  ✅ Success: {business.name}')
                    )
                    success_count += 1
                else:
                    self.stdout.write(
                        self.style.ERROR(f'  ❌ Failed: {business.name}')
                    )
                    failed_count += 1
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  ❌ Error: {business.name} - {str(e)}')
                )
                failed_count += 1
        
        # Summary
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(
            self.style.SUCCESS(f'📈 SETUP COMPLETE')
        )
        self.stdout.write(f'✅ Successful setups: {success_count}')
        self.stdout.write(f'❌ Failed setups: {failed_count}')
        self.stdout.write('=' * 60)

    def check_if_needs_setup(self, business):
        """Check if a business needs tenant database setup"""
        try:
            # Check if database exists in Django settings
            from django.conf import settings
            db_alias = f"tenant_{business.id}"
            
            # Basic check - if database alias doesn't exist, needs setup
            if db_alias not in settings.DATABASES:
                return True
            
            # Check if we can connect to the tenant database
            from django.db import connections
            try:
                with connections[db_alias].cursor() as cursor:
                    cursor.execute("SELECT 1")
                
                # If connection works, check if employee record exists
                from apps.core.database_router import tenant_context
                with tenant_context(business):
                    from apps.employees.models import Employee
                    owner_employee = Employee.objects.filter(
                        user_id=business.owner.id,
                        is_active=True
                    ).first()
                    
                    # If no owner employee record, needs setup
                    if not owner_employee:
                        return True
                        
                return False  # Everything looks good
                
            except Exception:
                return True  # Connection failed, needs setup
                
        except Exception as e:
            self.stdout.write(f'  ⚠️  Error checking setup status: {e}')
            return True  # When in doubt, assume needs setup
