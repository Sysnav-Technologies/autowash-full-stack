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
from django.core.management import call_command

print("Fixing tenant migrations...")

# Get the test tenant
try:
    tenant = Tenant.objects.get(slug="test-carwash")
    print(f"Found tenant: {tenant.name}")
    print(f"Database: {tenant.database_name}")
    
    # Add tenant database to settings
    TenantDatabaseManager.add_tenant_to_settings(tenant)
    db_alias = f"tenant_{tenant.id}"
    
    print(f"Database alias: {db_alias}")
    
    # Check if tenant database exists in settings
    from django.conf import settings
    if db_alias in settings.DATABASES:
        print("✓ Tenant database found in settings")
        print(f"  Database config: {settings.DATABASES[db_alias]}")
    else:
        print("✗ Tenant database not found in settings")
        exit(1)
    
    # Run migrations for tenant database with fixed router
    print(f"\nRunning migrations for tenant database {tenant.database_name}...")
    print("This will create all missing tables including django_session, auth tables, etc.")
    
    try:
        call_command('migrate', database=db_alias, verbosity=2)
        print("✓ Tenant migrations completed successfully!")
        
        # Verify some key tables exist
        from django.db import connections
        tenant_db = connections[db_alias]
        
        with tenant_db.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
            
        print(f"\nTables created in {tenant.database_name}:")
        for table in sorted(tables):
            print(f"  - {table}")
            
        # Check for key tables
        required_tables = [
            'django_session',
            'auth_user', 
            'core_tenantsettings',
            'businesses_business',
            'django_admin_log'
        ]
        
        missing_tables = [table for table in required_tables if table not in tables]
        if missing_tables:
            print(f"\n⚠️  Still missing tables: {missing_tables}")
        else:
            print("\n✓ All key tables created successfully!")
        
    except Exception as e:
        print(f"✗ Error running migrations: {e}")
        import traceback
        traceback.print_exc()
        
except Tenant.DoesNotExist:
    print("✗ Test tenant not found. Please create a tenant first.")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
