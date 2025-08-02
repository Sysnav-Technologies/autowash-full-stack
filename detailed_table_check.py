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

print("Checking tenant database tables...")
tenant = Tenant.objects.first()
print(f"Tenant: {tenant.name}")

# Add tenant database to settings
TenantDatabaseManager.add_tenant_to_settings(tenant)
db_alias = f"tenant_{tenant.id}"

# Get cursor for tenant database
tenant_cursor = connections[db_alias].cursor()

# Show all tables
print(f"\nQuerying SHOW TABLES for {db_alias}:")
tenant_cursor.execute("SHOW TABLES")
tables = tenant_cursor.fetchall()

for table in tables:
    table_name = table[0]
    print(f"  {table_name}")
    
print(f"\nTotal tables: {len(tables)}")

# Check for core_tenantsettings specifically
core_tables = [t[0] for t in tables if 'core_' in t[0]]
print(f"Core tables: {core_tables}")

# Check if we can query TenantSettings table
try:
    tenant_cursor.execute("SELECT COUNT(*) FROM core_tenantsettings")
    count = tenant_cursor.fetchone()[0]
    print(f"\nTenantSettings records: {count}")
    
    # Show structure
    tenant_cursor.execute("DESCRIBE core_tenantsettings")
    columns = tenant_cursor.fetchall()
    print("\nTenantSettings table structure:")
    for col in columns:
        print(f"  {col[0]} - {col[1]}")
        
except Exception as e:
    print(f"\nError accessing core_tenantsettings: {e}")
