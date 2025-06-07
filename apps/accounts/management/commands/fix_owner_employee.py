# apps/accounts/management/commands/fix_owner_employee.py
# Quick fix for the current user

from django.core.management.base import BaseCommand
from django.db import connection
from django_tenants.utils import schema_context, get_public_schema_name
from django.contrib.auth.models import User
from apps.accounts.models import Business

class Command(BaseCommand):
    help = 'Fix owner employee for specific user and business'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            required=True,
            help='Username of the business owner',
        )
        parser.add_argument(
            '--business-slug',
            type=str,
            required=True,
            help='Business slug',
        )

    def handle(self, *args, **options):
        username = options['username']
        business_slug = options['business_slug']
        
        self.stdout.write(f'🔧 Fixing owner employee for {username} in business {business_slug}')
        
        try:
            # Get user and business from public schema
            with schema_context(get_public_schema_name()):
                user = User.objects.get(username=username)
                business = Business.objects.get(slug=business_slug, is_verified=True)
                
                self.stdout.write(f'✅ Found user: {user.username} ({user.email})')
                self.stdout.write(f'✅ Found business: {business.name} (Schema: {business.schema_name})')
            
            # Check if schema exists
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s",
                    [business.schema_name]
                )
                if not cursor.fetchone():
                    self.stdout.write(
                        self.style.ERROR(f'❌ Schema {business.schema_name} does not exist')
                    )
                    return
            
            # Now work in the tenant schema
            with schema_context(business.schema_name):
                from apps.employees.models import Employee, Department
                
                # Check if employee already exists
                existing = Employee.objects.filter(user_id=user.id, is_active=True).first()
                if existing:
                    self.stdout.write(
                        self.style.WARNING(f'⚠️ Employee already exists: {existing.employee_id}')
                    )
                    return
                
                # Create management department
                management_dept, created = Department.objects.get_or_create(
                    name='Management',
                    defaults={
                        'description': 'Business management and administration',
                        'is_active': True
                    }
                )
                
                if created:
                    self.stdout.write('📁 Created Management department')
                
                # Generate employee ID
                employee_count = Employee.objects.count()
                employee_id = f"EMP{business.schema_name.upper()[:3]}{employee_count + 1:04d}"
                
                # Get user profile from public schema
                user_phone = None
                try:
                    with schema_context(get_public_schema_name()):
                        user_profile = user.profile
                        user_phone = user_profile.phone
                except Exception as e:
                    self.stdout.write(f'⚠️ Could not get user profile: {e}')
                
                # Create employee using user_id directly
                self.stdout.write(f'🔧 Creating employee with user_id: {user.id}')
                
                # IMPORTANT: Use user_id instead of user object to avoid FK constraint
                employee = Employee.objects.create(
                    user_id=user.id,  # Use ID directly
                    employee_id=employee_id,
                    role='owner',
                    employment_type='full_time',
                    status='active',
                    department=management_dept,
                    hire_date=business.created_at.date(),
                    is_active=True,
                    can_login=True,
                    receive_notifications=True,
                    email=user.email,
                    phone=user_phone,
                    country='Kenya',
                )
                
                # Set department head
                management_dept.head = employee
                management_dept.save()
                
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Created owner employee: {employee.employee_id}')
                )
                self.stdout.write(
                    self.style.SUCCESS(f'👑 Set as department head')
                )
                
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'❌ User {username} not found')
            )
        except Business.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'❌ Business {business_slug} not found or not verified')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error: {e}')
            )
            import traceback
            self.stdout.write(traceback.format_exc())