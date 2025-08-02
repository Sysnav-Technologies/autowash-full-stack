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
from django.conf import settings
import pymysql

print("Testing tenant database connection...")
tenant = Tenant.objects.first()
print(f"Tenant: {tenant.name}")
print(f"Database name: {tenant.database_name}")
print(f"Database host: {tenant.database_host}")
print(f"Database port: {tenant.database_port}")
print(f"Database user: {tenant.database_user}")

# Add tenant database to settings
TenantDatabaseManager.add_tenant_to_settings(tenant)
db_alias = f"tenant_{tenant.id}"
print(f"Database alias: {db_alias}")

# Check if database config was added
if db_alias in settings.DATABASES:
    db_config = settings.DATABASES[db_alias]
    print(f"Database config: {db_config}")
else:
    print("ERROR: Database config not found in settings!")

# Test direct connection
try:
    print("\nTesting direct MySQL connection...")
    connection = pymysql.connect(
        host=tenant.database_host,
        user=tenant.database_user,
        password=tenant.database_password,
        database=tenant.database_name,
        port=tenant.database_port
    )
    cursor = connection.cursor()
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()
    print(f"Direct connection successful. Tables found: {len(tables)}")
    for table in tables:
        print(f"  {table[0]}")
    cursor.close()
    connection.close()
except Exception as e:
    print(f"Direct connection failed: {e}")

# Test Django connection
try:
    print("\nTesting Django database connection...")
    django_conn = connections[db_alias]
    with django_conn.cursor() as cursor:
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print(f"Django connection successful. Tables found: {len(tables)}")
        for table in tables:
            print(f"  {table[0]}")
except Exception as e:
    print(f"Django connection failed: {e}")
