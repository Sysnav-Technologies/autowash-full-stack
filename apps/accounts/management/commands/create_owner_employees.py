# apps/accounts/management/commands/create_owner_employees.py
# Create this file: apps/accounts/management/commands/create_owner_employees.py

from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django_tenants.utils import schema_context
from apps.accounts.models import Business
from django.utils import timezone

class Command(BaseCommand):
    help = 'Create owner employee records for verified businesses that do not have them'

    def add_arguments(self, parser):
        parser.add_argument(
            '--business-id',
            type=int,
            help='Create owner employee for specific business ID only',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually doing it',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n🚀 Creating Owner Employee Records\n'))
        
        dry_run = options['dry_run']
        business_id = options.get('business_id')
        
        # Get verified businesses
        if business_id:
            businesses = Business.objects.filter(id=business_id, is_verified=True)
            if not businesses.exists():
                self.stdout.write(
                    self.style.ERROR(f'❌ Business with ID {business_id} not found or not verified')
                )
                return
        else:
            businesses = Business.objects.filter(is_verified=True)
        
        self.stdout.write(f'📊 Found {businesses.count()} verified business(es) to check\n')
        
        created_count = 0
        error_count = 0
        skipped_count = 0
        
        for business in businesses:
            self.stdout.write(f'\n🏢 Processing: {business.name} (Schema: {business.schema_name})')
            
            try:
                # Check if schema exists
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s",
                        [business.schema_name]
                    )
                    if not cursor.fetchone():
                        self.stdout.write(
                            self.style.WARNING(f'⚠️  Schema does not exist for {business.name}. Skipping.')
                        )
                        skipped_count += 1
                        continue
                
                # Check if owner employee exists
                with schema_context(business.schema_name):
                    from apps.employees.models import Employee, Department
                    
                    existing_employee = Employee.objects.filter(user=business.owner, is_active=True).first()
                    if existing_employee:
                        self.stdout.write(
                            self.style.WARNING(f'⚠️  Owner employee already exists: {existing_employee.employee_id}')
                        )
                        skipped_count += 1
                        continue
                    
                    if dry_run:
                        self.stdout.write(
                            self.style.SUCCESS(f'✅ Would create owner employee for {business.name}')
                        )
                        created_count += 1
                        continue
                    
                    # Create management department if it doesn't exist
                    management_dept, created = Department.objects.get_or_create(
                        name='Management',
                        defaults={
                            'description': 'Business management and administration',
                            'is_active': True
                        }
                    )
                    
                    if created:
                        self.stdout.write(f'📁 Created Management department')
                    
                    # Generate employee ID
                    employee_count = Employee.objects.count()
                    employee_id = f"EMP{business.schema_name.upper()[:3]}{employee_count + 1:04d}"
                    
                    # Get user profile for additional info
                    user_profile = None
                    try:
                        user_profile = business.owner.profile
                    except:
                        pass
                    
                    # Create owner as employee
                    owner_employee = Employee.objects.create(
                        user=business.owner,
                        employee_id=employee_id,
                        role='owner',
                        employment_type='full_time',
                        status='active',
                        department=management_dept,
                        hire_date=business.created_at.date(),
                        is_active=True,
                        can_login=True,
                        receive_notifications=True,
                        email=business.owner.email,
                        phone=user_profile.phone if user_profile else None,
                        # Default address info
                        country='Kenya',
                        created_at=timezone.now(),
                        updated_at=timezone.now(),
                    )
                    
                    # Set department head if not already set
                    if not management_dept.head:
                        management_dept.head = owner_employee
                        management_dept.save()
                        self.stdout.write(f'👑 Set as department head')
                    
                    self.stdout.write(
                        self.style.SUCCESS(f'✅ Created owner employee: {owner_employee.employee_id}')
                    )
                    created_count += 1
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Error processing {business.name}: {str(e)}')
                )
                error_count += 1
                # Print full traceback for debugging
                import traceback
                self.stdout.write(traceback.format_exc())
        
        # Summary
        self.stdout.write(f'\n' + '='*50)
        self.stdout.write(self.style.SUCCESS(f'📊 SUMMARY'))
        self.stdout.write(f'✅ Created: {created_count}')
        self.stdout.write(f'⚠️  Skipped: {skipped_count}')
        self.stdout.write(f'❌ Errors: {error_count}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n🧪 DRY RUN - No changes were made'))
            self.stdout.write('Run without --dry-run to actually create the employee records')
        else:
            self.stdout.write(self.style.SUCCESS('\n🎉 Owner employee creation complete!'))
        
        self.stdout.write('='*50)