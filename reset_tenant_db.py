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
from django.db import connections

print("Completely resetting tenant database...")
tenant = Tenant.objects.first()
print(f"Tenant: {tenant.name}")

# Add tenant database to settings
TenantDatabaseManager.add_tenant_to_settings(tenant)
db_alias = f"tenant_{tenant.id}"

# Get cursor for tenant database
tenant_cursor = connections[db_alias].cursor()

print("Dropping all tables except django_migrations...")
try:
    # Get all tables
    tenant_cursor.execute("SHOW TABLES")
    tables = [table[0] for table in tenant_cursor.fetchall()]
    
    for table in tables:
        if table != 'django_migrations':
            print(f"Dropping table: {table}")
            tenant_cursor.execute(f"DROP TABLE IF EXISTS `{table}`")
    
    print("All non-migration tables dropped")
    
    # Clear all migration records
    print("Clearing all migration records...")
    tenant_cursor.execute("DELETE FROM django_migrations")
    print("All migration records cleared")
    
except Exception as e:
    print(f"Error resetting database: {e}")

tenant_cursor.close()
