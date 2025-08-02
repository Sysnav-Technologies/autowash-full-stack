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
from django.db import connection

print("Checking migration status...")
tenant = Tenant.objects.first()
print(f"Tenant: {tenant.name}")

# Add tenant database to settings
TenantDatabaseManager.add_tenant_to_settings(tenant)
db_alias = f"tenant_{tenant.id}"

# Get cursor for tenant database
from django.db import connections
tenant_cursor = connections[db_alias].cursor()

print(f"\nChecking django_migrations table in {db_alias}:")
tenant_cursor.execute("SELECT app, name, applied FROM django_migrations ORDER BY applied DESC")
migrations = tenant_cursor.fetchall()

for app, name, applied in migrations:
    print(f"  {app}.{name} - {applied}")
    
print(f"\nTotal migrations applied: {len(migrations)}")

# Check specifically for core migrations
core_migrations = [m for m in migrations if m[0] == 'core']
print(f"Core migrations applied: {len(core_migrations)}")
