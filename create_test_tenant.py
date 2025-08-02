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

print("Creating a new test tenant...")

# Get the admin user as owner
admin_user = User.objects.get(username='admin')

# Create a test tenant
tenant = Tenant.objects.create(
    name="Test Car Wash",
    slug="test-carwash",
    description="Test car wash business",
    subdomain="testcarwash",
    owner=admin_user,
    email="test@carwash.com",
    phone="+254700000000",
    city="Nairobi",
    country="KE",  # Use 2-letter country code
    is_active=True,
    is_verified=True,
    database_name="autowash_testcarwash",
    database_host="localhost",
    database_port=3306,
    database_user="root",
    database_password="Brandon",  # Use the correct password
)

print(f"✓ Created tenant: {tenant.name}")
print(f"  - ID: {tenant.id}")
print(f"  - Slug: {tenant.slug}")
print(f"  - Subdomain: {tenant.subdomain}")
print(f"  - Database: {tenant.database_name}")

# Create tenant database
print("\nCreating tenant database...")
success = TenantDatabaseManager.create_tenant_database(tenant)

if success:
    print("✓ Tenant database created successfully!")
    print(f"  - Database name: {tenant.database_name}")
    
    # Test if we can migrate the tenant database
    print("\nRunning tenant migrations...")
    from django.core.management import call_command
    
    try:
        # Add tenant database to settings first
        TenantDatabaseManager.add_tenant_to_settings(tenant)
        db_alias = f"tenant_{tenant.id}"
        
        # Run migrations for tenant database
        call_command('migrate', database=db_alias, verbosity=1)
        print("✓ Tenant migrations completed successfully!")
        
        # Create TenantSettings record
        from apps.core.tenant_models import TenantSettings
        settings_obj = TenantSettings.objects.using(db_alias).create(tenant_id=tenant.id)
        print("✓ Tenant settings created successfully!")
        
    except Exception as e:
        print(f"✗ Error with tenant migrations: {e}")
        import traceback
        traceback.print_exc()
else:
    print("✗ Failed to create tenant database")

print(f"\nTenant setup completed!")
print(f"Access URL: http://localhost:8000/business/{tenant.slug}/")
