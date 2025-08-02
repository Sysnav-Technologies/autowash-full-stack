#!/usr/bin/env python
"""
Create Employee Record for Testing
Creates an Employee record for admin user in tenant database
"""
import os
import sys
import django

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'autowash.settings')
django.setup()

from django.contrib.auth.models import User
from apps.core.tenant_models import Tenant
from apps.core.database_router import TenantDatabaseRouter
from apps.employees.models import Employee, Department, Position

def create_employee_for_admin():
    """Create Employee record for admin user in tenant database"""
    try:
        # Get the tenant
        tenant = Tenant.objects.get(name="Fresh Car Wash")
        print(f"Found tenant: {tenant.name}")
        print(f"Database: {tenant.database_name}")
        
        # Add tenant database to settings dynamically
        from django.conf import settings
        db_alias = f"tenant_{tenant.id}"
        if db_alias not in settings.DATABASES:
            settings.DATABASES[db_alias] = tenant.database_config
            print(f"✓ Tenant database added to settings")
        
        # Test database connection
        from django.db import connections
        try:
            with connections[db_alias].cursor() as cursor:
                cursor.execute("SELECT 1")
            print(f"✓ Database connection test successful")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return None
        
        # Set tenant context for database routing
        TenantDatabaseRouter.set_tenant(tenant)
        
        # Get admin user from main database
        admin_user = User.objects.using('default').get(username='admin')
        print(f"Found admin user: {admin_user.username} (ID: {admin_user.id})")
        
        # Create or get Department in tenant database
        department, dept_created = Department.objects.using(f'tenant_{tenant.id}').get_or_create(
            name="Management",
            defaults={
                'description': 'Management and Administration',
                'is_active': True
            }
        )
        if dept_created:
            print(f"✓ Created department: {department.name}")
        else:
            print(f"✓ Found existing department: {department.name}")
        
        # Create or get Position in tenant database
        position, pos_created = Position.objects.using(f'tenant_{tenant.id}').get_or_create(
            title="Business Administrator",
            defaults={
                'description': 'Administrator of the car wash business',
                'is_active': True,
                'department': department
            }
        )
        if pos_created:
            print(f"✓ Created position: {position.title}")
        else:
            print(f"✓ Found existing position: {position.title}")
        
        # Create Employee record in tenant database
        employee, emp_created = Employee.objects.using(f'tenant_{tenant.id}').get_or_create(
            user_id=admin_user.id,  # Reference to user in main database
            defaults={
                'employee_id': 'EMP001',
                'department': department,
                'position': position,
                'role': 'owner',  # Admin should be owner
                'employment_type': 'full_time',
                'hire_date': '2024-01-01',
                'is_active': True,
                'status': 'active',
                'can_login': True,
                'receive_notifications': True
            }
        )
        
        if emp_created:
            print(f"✓ Created employee record: {employee.full_name} (ID: {employee.id})")
        else:
            print(f"✓ Found existing employee record: {employee.full_name} (ID: {employee.id})")
        
        # Verify the employee record
        print(f"\nEmployee Details:")
        print(f"  - Employee ID: {employee.employee_id}")
        print(f"  - Name: {employee.full_name}")
        print(f"  - Email: {employee.email}")
        print(f"  - Department: {employee.department.name}")
        print(f"  - Position: {employee.position.title}")
        print(f"  - Role: {employee.role}")
        print(f"  - Status: {employee.status}")
        print(f"  - User ID Reference: {employee.user_id}")
        
        return employee
        
    except Tenant.DoesNotExist:
        print("❌ Tenant 'Fresh Car Wash' not found")
        return None
    except User.DoesNotExist:
        print("❌ Admin user not found")
        return None
    except Exception as e:
        print(f"❌ Error creating employee: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        # Clear tenant context
        TenantDatabaseRouter.clear_tenant()

if __name__ == "__main__":
    print("=" * 60)
    print("CREATE EMPLOYEE RECORD FOR ADMIN USER")
    print("=" * 60)
    employee = create_employee_for_admin()
    if employee:
        print("\n✅ Employee record created successfully!")
    else:
        print("\n❌ Failed to create employee record")
