#!/usr/bin/env python
import os
import sys
import django

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'autowash.settings')
django.setup()

from apps.core.tenant_models import Tenant
from apps.core.database_router import TenantDatabaseManager
from django.contrib.auth.models import User

print("=" * 60)
print("CREATING TENANT USER ACCOUNTS")
print("=" * 60)

# Get the tenant
tenant = Tenant.objects.get(slug="fresh-carwash")
print(f"Found tenant: {tenant.name}")

# Add tenant database to settings
TenantDatabaseManager.add_tenant_to_settings(tenant)
db_alias = f"tenant_{tenant.id}"

print(f"Database alias: {db_alias}")

if db_alias in tenant.settings.DATABASES:
    print("✓ Tenant database found in settings")
    
    # Create a tenant manager user
    print(f"\nCreating tenant manager user...")
    try:
        manager_user = User.objects.using(db_alias).create_user(
            username='manager',
            email='manager@freshcarwash.com',
            password='manager123',
            first_name='John',
            last_name='Manager',
            is_staff=True,
            is_active=True
        )
        print("✓ Tenant manager created successfully!")
        print(f"  Username: manager")
        print(f"  Password: manager123")
        print(f"  Email: {manager_user.email}")
        
    except Exception as e:
        print(f"Manager creation error: {e}")
    
    # Create a tenant employee user
    print(f"\nCreating tenant employee user...")
    try:
        employee_user = User.objects.using(db_alias).create_user(
            username='employee',
            email='employee@freshcarwash.com', 
            password='employee123',
            first_name='Jane',
            last_name='Employee',
            is_active=True
        )
        print("✓ Tenant employee created successfully!")
        print(f"  Username: employee")
        print(f"  Password: employee123")
        print(f"  Email: {employee_user.email}")
        
    except Exception as e:
        print(f"Employee creation error: {e}")
        
    # List all users in tenant database
    print(f"\nAll users in tenant database:")
    all_users = User.objects.using(db_alias).all()
    for user in all_users:
        status = "Staff" if user.is_staff else "Regular"
        print(f"  - {user.username} ({user.first_name} {user.last_name}) - {status}")
        
else:
    print("✗ Tenant database not found in settings")

print(f"\n" + "=" * 60)
print("COMPLETE LOGIN CREDENTIALS")
print("=" * 60)
print(f"🌐 MAIN ADMIN:")
print(f"   URL: http://localhost:8000/admin/")
print(f"   Username: admin")
print(f"   Password: admin123")
print(f"")
print(f"🏢 TENANT LOGIN (Fresh Car Wash):")
print(f"   URL: http://localhost:8000/business/fresh-carwash/")
print(f"   Manager: manager / manager123")
print(f"   Employee: employee / employee123")
print("=" * 60)
