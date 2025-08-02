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
from django.conf import settings
from django.core.management import call_command

print("=" * 60)
print("MANUALLY MIGRATING TENANT DATABASE")
print("=" * 60)

# Get the tenant
tenant = Tenant.objects.get(slug="fresh-carwash")
print(f"Found tenant: {tenant.name}")
print(f"Database: {tenant.database_name}")

# Add tenant database to settings manually
print(f"\nAdding tenant database to settings...")
TenantDatabaseManager.add_tenant_to_settings(tenant)

db_alias = f"tenant_{tenant.id}"
print(f"Database alias: {db_alias}")

if db_alias in settings.DATABASES:
    print("✓ Tenant database added to settings")
    print(f"Database config: {settings.DATABASES[db_alias]}")
    
    # Test the database connection
    from django.db import connections
    try:
        tenant_db = connections[db_alias]
        with tenant_db.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
        print("✓ Database connection test successful")
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        sys.exit(1)
    
    # Now run migrations with explicit database parameter
    print(f"\nRunning migrations specifically for {db_alias}...")
    
    try:
        # First check what migrations need to be applied
        from django.db.migrations.executor import MigrationExecutor
        executor = MigrationExecutor(connections[db_alias])
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        
        if plan:
            print(f"Migrations to apply: {len(plan)}")
            for migration, backwards in plan:
                print(f"  - {migration}")
        else:
            print("No migrations to apply")
            
        # Force apply migrations
        call_command('migrate', database=db_alias, verbosity=2, fake=False)
        print("✓ Migrations completed")
        
        # Verify tables were created
        with tenant_db.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
            
        print(f"\nTables after migration ({len(tables)} total):")
        for table in sorted(tables):
            print(f"  - {table}")
            
        # Check for key tables
        key_tables = ['auth_user', 'django_session', 'businesses_business', 'django_admin_log']
        missing = [t for t in key_tables if t not in tables]
        
        if missing:
            print(f"\n⚠️  Still missing: {missing}")
        else:
            print(f"\n🎉 All key tables present!")
            
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        
else:
    print("✗ Failed to add tenant database to settings")
