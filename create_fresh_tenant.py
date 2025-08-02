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
print("CREATING FRESH TEST TENANT")
print("=" * 60)

# Get the admin user as owner
admin_user = User.objects.get(username='admin')
print(f"✓ Found admin user: {admin_user.username}")

# Create a test tenant
tenant = Tenant.objects.create(
    name="Fresh Car Wash",
    slug="fresh-carwash", 
    description="Fresh test car wash business",
    subdomain="freshcarwash",
    owner=admin_user,
    email="fresh@carwash.com",
    phone="+254700000001",
    city="Nairobi",
    country="KE",
    is_active=True,
    is_verified=True,
    database_name="autowash_freshcarwash",
    database_host="localhost",
    database_port=3306,
    database_user="root",
    database_password="Brandon",
)

print(f"✓ Created tenant: {tenant.name}")
print(f"  - ID: {tenant.id}")
print(f"  - Slug: {tenant.slug}")
print(f"  - Subdomain: {tenant.subdomain}")
print(f"  - Database: {tenant.database_name}")

# Create tenant database
print(f"\n" + "=" * 40)
print("CREATING TENANT DATABASE")
print("=" * 40)

success = TenantDatabaseManager.create_tenant_database(tenant)

if success:
    print("✓ Tenant database created successfully!")
    
    # Verify tenant database has all tables
    from django.db import connections
    from django.conf import settings
    
    db_alias = f"tenant_{tenant.id}"
    
    if db_alias in settings.DATABASES:
        tenant_db = connections[db_alias]
        
        with tenant_db.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
            
        print(f"\n✓ Tables in {tenant.database_name} ({len(tables)} total):")
        
        # Check key tables
        key_tables = [
            'auth_user',
            'django_session', 
            'core_tenantsettings',
            'businesses_business',
            'django_admin_log',
            'customers_customer',
            'services_service',
            'employees_employee'
        ]
        
        present_tables = []
        missing_tables = []
        
        for table in key_tables:
            if table in tables:
                present_tables.append(table)
            else:
                missing_tables.append(table)
        
        print(f"\n✓ Key tables present ({len(present_tables)}):")
        for table in present_tables:
            print(f"  ✓ {table}")
            
        if missing_tables:
            print(f"\n✗ Missing tables ({len(missing_tables)}):")
            for table in missing_tables:
                print(f"  ✗ {table}")
        else:
            print("\n🎉 ALL KEY TABLES PRESENT!")
            
        # Create TenantSettings for this tenant
        print(f"\nCreating TenantSettings...")
        try:
            from apps.core.tenant_models import TenantSettings
            settings_obj = TenantSettings.objects.using(db_alias).create(tenant_id=tenant.id)
            print("✓ TenantSettings created successfully!")
        except Exception as e:
            print(f"✗ Error creating TenantSettings: {e}")
            
    else:
        print("✗ Tenant database not found in settings")
        
else:
    print("✗ Failed to create tenant database")

print(f"\n" + "=" * 60)
print("SETUP COMPLETED!")
print("=" * 60)
print(f"🌐 Main site: http://localhost:8000/")
print(f"🏢 Tenant site: http://localhost:8000/business/{tenant.slug}/")
print(f"👨‍💼 Admin: http://localhost:8000/admin/ (admin/admin123)")
print("=" * 60)
