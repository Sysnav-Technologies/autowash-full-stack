#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'autowash.settings')
django.setup()

from django.db import connections
from django.conf import settings
from apps.core.tenant_models import Tenant
from apps.core.database_router import TenantDatabaseManager

try:
    t = Tenant.objects.get(slug='test-business')
    db_alias = f'tenant_{t.id}'
    
    print(f"Tenant: {t.name}")
    print(f"Database alias: {db_alias}")
    
    # Add tenant database to settings if not present
    if db_alias not in settings.DATABASES:
        print("Adding tenant database to settings...")
        TenantDatabaseManager.add_tenant_to_settings(t)
    
    print(f"Available databases: {list(settings.DATABASES.keys())}")
    
    cursor = connections[db_alias].cursor()
    cursor.execute('SHOW TABLES')
    tables = cursor.fetchall()
    
    print(f"Total tables: {len(tables)}")
    
    # Check for core tables
    core_tables = [table[0] for table in tables if 'core' in table[0]]
    print(f"Core tables: {core_tables}")
    
    # Check for TenantSettings table specifically
    settings_tables = [table[0] for table in tables if 'tenantsettings' in table[0].lower()]
    print(f"TenantSettings tables: {settings_tables}")
    
    # List all tables
    print("\nAll tables:")
    for table in tables:
        print(f"  - {table[0]}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
