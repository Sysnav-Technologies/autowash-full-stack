#!/usr/bin/env python
import os
import sys
import django
import pymysql

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'autowash.settings')
django.setup()

from apps.core.tenant_models import Tenant
from apps.core.database_router import TenantDatabaseManager
from django.conf import settings
from django.core.management import call_command

print("=" * 60)
print("COMPLETE TENANT DATABASE RESET")
print("=" * 60)

# Get the tenant
tenant = Tenant.objects.get(slug="fresh-carwash")
print(f"Found tenant: {tenant.name}")
print(f"Database: {tenant.database_name}")

# Drop and recreate the tenant database
print(f"\nDropping tenant database...")
default_db = settings.DATABASES['default']

try:
    connection = pymysql.connect(
        host=default_db['HOST'],
        user=default_db['USER'],
        password=default_db['PASSWORD'],
        port=int(default_db['PORT'])
    )
    
    cursor = connection.cursor()
    cursor.execute(f"DROP DATABASE IF EXISTS `{tenant.database_name}`")
    cursor.execute(f"CREATE DATABASE `{tenant.database_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    cursor.close()
    connection.close()
    
    print(f"✓ Tenant database {tenant.database_name} recreated")
    
except Exception as e:
    print(f"✗ Error recreating database: {e}")
    sys.exit(1)

# Add tenant database to settings
print(f"\nAdding tenant database to settings...")
TenantDatabaseManager.add_tenant_to_settings(tenant)

db_alias = f"tenant_{tenant.id}"
print(f"Database alias: {db_alias}")

if db_alias in settings.DATABASES:
    print("✓ Tenant database added to settings")
    
    # Test connection
    from django.db import connections
    try:
        tenant_db = connections[db_alias]
        with tenant_db.cursor() as cursor:
            cursor.execute("SELECT 1")
        print("✓ Database connection test successful")
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        sys.exit(1)
    
    # Run migrations with --run-syncdb to create tables even if migrations are already "applied"
    print(f"\nRunning migrations with --run-syncdb...")
    
    try:
        call_command('migrate', database=db_alias, verbosity=2, run_syncdb=True)
        print("✓ Migrations with syncdb completed")
        
        # Verify tables were created
        with tenant_db.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
            
        print(f"\nTables after migration ({len(tables)} total):")
        for table in sorted(tables):
            print(f"  - {table}")
            
        # Check for key tables
        key_tables = ['auth_user', 'django_session', 'businesses_business', 'django_admin_log', 'core_tenantsettings']
        missing = [t for t in key_tables if t not in tables]
        
        if missing:
            print(f"\n⚠️  Still missing: {missing}")
        else:
            print(f"\n🎉 All key tables present!")
            
        # Create TenantSettings
        if 'core_tenantsettings' in tables:
            print(f"\nCreating TenantSettings...")
            from apps.core.tenant_models import TenantSettings
            try:
                settings_obj = TenantSettings.objects.using(db_alias).create(tenant_id=tenant.id)
                print("✓ TenantSettings created successfully!")
            except Exception as e:
                print(f"Warning: TenantSettings creation failed: {e}")
            
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        
else:
    print("✗ Failed to add tenant database to settings")
