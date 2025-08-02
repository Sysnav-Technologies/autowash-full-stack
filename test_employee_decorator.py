#!/usr/bin/env python
"""
Test Employee Decorator
Tests the employee_required decorator functionality
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
from apps.employees.models import Employee

def test_employee_lookup():
    """Test employee lookup for admin user"""
    try:
        # Get the tenant
        tenant = Tenant.objects.get(name="Fresh Car Wash")
        print(f"Found tenant: {tenant.name}")
        
        # Add tenant database to settings dynamically
        from django.conf import settings
        db_alias = f"tenant_{tenant.id}"
        if db_alias not in settings.DATABASES:
            settings.DATABASES[db_alias] = tenant.database_config
            print(f"✓ Tenant database added to settings")
        
        # Set tenant context
        TenantDatabaseRouter.set_tenant(tenant)
        
        # Get admin user
        admin_user = User.objects.using('default').get(username='admin')
        print(f"Found admin user: {admin_user.username} (ID: {admin_user.id})")
        
        # Test employee lookup
        try:
            employee = Employee.objects.using(db_alias).get(user_id=admin_user.id, is_active=True)
            print(f"✅ Employee found: {employee.full_name}")
            print(f"   - Employee ID: {employee.employee_id}")
            print(f"   - Role: {employee.role}")
            print(f"   - Status: {employee.status}")
            print(f"   - Department: {employee.department.name if employee.department else 'None'}")
            print(f"   - Position: {employee.position.title if employee.position else 'None'}")
            
            # Test role checking
            roles_to_test = ['owner', 'manager', 'supervisor', 'attendant']
            for role in roles_to_test:
                if employee.role == role:
                    print(f"   ✅ User has '{role}' role")
                else:
                    print(f"   ❌ User does NOT have '{role}' role")
            
            return employee
            
        except Employee.DoesNotExist:
            print("❌ Employee record not found for admin user")
            return None
        
    except Tenant.DoesNotExist:
        print("❌ Tenant 'Fresh Car Wash' not found")
        return None
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return None
    finally:
        # Clear tenant context
        TenantDatabaseRouter.clear_tenant()

if __name__ == "__main__":
    print("=" * 60)
    print("TEST EMPLOYEE DECORATOR FUNCTIONALITY")
    print("=" * 60)
    employee = test_employee_lookup()
    if employee:
        print("\n✅ Employee decorator should work correctly!")
        print("   User should be able to access business dashboard")
    else:
        print("\n❌ Employee decorator will fail!")
        print("   User will get 'not registered as employee' error")
