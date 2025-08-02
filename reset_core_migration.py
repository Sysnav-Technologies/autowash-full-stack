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

print("Resetting core migration for tenant...")
tenant = Tenant.objects.first()
print(f"Tenant: {tenant.name}")

# Add tenant database to settings
TenantDatabaseManager.add_tenant_to_settings(tenant)
db_alias = f"tenant_{tenant.id}"

# Get cursor for tenant database
tenant_cursor = connections[db_alias].cursor()

print("Deleting core migration record...")
try:
    tenant_cursor.execute("DELETE FROM django_migrations WHERE app = 'core'")
    print("Core migration record deleted")
except Exception as e:
    print(f"Error deleting migration record: {e}")

# Check remaining migrations
tenant_cursor.execute("SELECT COUNT(*) FROM django_migrations")
remaining = tenant_cursor.fetchone()[0]
print(f"Remaining migration records: {remaining}")

tenant_cursor.close()
