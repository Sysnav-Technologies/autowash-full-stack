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
from django.db import connections
from django.conf import settings

print("=" * 60)
print("DEBUGGING TENANT DATABASE TABLES")
print("=" * 60)

# Get the tenant
tenant = Tenant.objects.get(slug="fresh-carwash")
db_alias = f"tenant_{tenant.id}"

print(f"Tenant: {tenant.name}")
print(f"Database: {tenant.database_name}")
print(f"DB Alias: {db_alias}")

# Check if database is in settings
if db_alias in settings.DATABASES:
    print(f"✓ Database config found in settings")
    
    tenant_db = connections[db_alias]
    
    with tenant_db.cursor() as cursor:
        # Show all tables
        cursor.execute("SHOW TABLES")
        tables = [row[0] for row in cursor.fetchall()]
        
        print(f"\nAll tables in {tenant.database_name} ({len(tables)} total):")
        for table in sorted(tables):
            print(f"  - {table}")
            
        # Check django_migrations table to see what migrations were applied
        print(f"\nChecking django_migrations table...")
        cursor.execute("SELECT app, name FROM django_migrations ORDER BY app, id")
        migrations = cursor.fetchall()
        
        if migrations:
            print(f"Applied migrations ({len(migrations)} total):")
            current_app = None
            for app, name in migrations:
                if app != current_app:
                    print(f"\n  {app}:")
                    current_app = app
                print(f"    - {name}")
        else:
            print("No migrations found in django_migrations table")
            
else:
    print(f"✗ Database config NOT found in settings")
    
# Also check the database router logic
print(f"\n" + "=" * 40)
print("TESTING DATABASE ROUTER")
print("=" * 40)

from apps.core.database_router import TenantDatabaseRouter

router = TenantDatabaseRouter()

# Test some key apps
test_apps = [
    ('django.contrib.auth', 'user'),
    ('django.contrib.sessions', 'session'), 
    ('django.contrib.admin', 'logentry'),
    ('apps.core', 'tenantsettings'),
    ('apps.businesses', 'business'),
    ('apps.customers', 'customer'),
]

print(f"Testing allow_migrate for {db_alias}:")
for app_label, model_name in test_apps:
    result = router.allow_migrate(db_alias, app_label, model_name)
    status = "✓ ALLOW" if result else "✗ DENY"
    print(f"  {status} {app_label}.{model_name}")
    
print(f"\nTesting allow_migrate for 'default':")
for app_label, model_name in test_apps:
    result = router.allow_migrate('default', app_label, model_name)
    status = "✓ ALLOW" if result else "✗ DENY"
    print(f"  {status} {app_label}.{model_name}")
