#!/usr/bin/env python
import os
import sys
import django

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'autowash.settings')
django.setup()

from django.conf import settings
from apps.core.database_router import TenantDatabaseRouter

print("=" * 60)
print("ANALYZING SHARED_APPS vs TENANT_APPS")
print("=" * 60)

print("SHARED_APPS:")
for app in settings.SHARED_APPS:
    print(f"  - {app}")
    
print(f"\nTENANT_APPS:")
for app in settings.TENANT_APPS:
    print(f"  - {app}")
    
print(f"\nINSTALLED_APPS:")
for app in settings.INSTALLED_APPS:
    print(f"  - {app}")

# Check which apps are in both
shared_set = set(settings.SHARED_APPS)
tenant_set = set(settings.TENANT_APPS)
both = shared_set.intersection(tenant_set)
shared_only = shared_set - tenant_set
tenant_only = tenant_set - shared_set

print(f"\nApps in BOTH SHARED_APPS and TENANT_APPS ({len(both)}):")
for app in both:
    print(f"  - {app}")
    
print(f"\nApps ONLY in SHARED_APPS ({len(shared_only)}):")
for app in shared_only:
    print(f"  - {app}")
    
print(f"\nApps ONLY in TENANT_APPS ({len(tenant_only)}):")
for app in tenant_only:
    print(f"  - {app}")

# Test router with specific apps
print(f"\n" + "=" * 40)
print("TESTING ROUTER LOGIC")
print("=" * 40)

router = TenantDatabaseRouter()
db_alias = "tenant_test"

test_cases = [
    ('auth', None),                    # Django built-in
    ('admin', None),                   # Django built-in
    ('sessions', None),                # Django built-in
    ('contenttypes', None),            # Django built-in
    ('django_celery_beat', None),      # Third party
    ('django_celery_results', None),   # Third party
    ('businesses', None),              # Custom app
    ('core', 'tenantsettings'),        # Custom core app
    ('core', 'tenant'),                # Custom core app
]

print(f"Testing allow_migrate for tenant database:")
for app_label, model_name in test_cases:
    result = router.allow_migrate(db_alias, app_label, model_name)
    status = "✓ ALLOW" if result else "✗ DENY"
    model_str = f".{model_name}" if model_name else ""
    print(f"  {status} {app_label}{model_str}")
    
    # Check if app is in our hardcoded list
    shared_and_tenant_apps = [
        'django.contrib.admin',
        'django.contrib.auth', 
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.sites',
        'allauth',
        'allauth.account',
        'allauth.socialaccount',
        'rest_framework.authtoken',
        'django_celery_beat',
        'django_celery_results',
    ]
    
    if app_label in shared_and_tenant_apps:
        print(f"    ^ In hardcoded shared_and_tenant_apps list")
    elif app_label in settings.SHARED_APPS and app_label in settings.TENANT_APPS:
        print(f"    ^ In both SHARED_APPS and TENANT_APPS")
    elif app_label in settings.SHARED_APPS:
        print(f"    ^ Only in SHARED_APPS")
    elif app_label in settings.TENANT_APPS:
        print(f"    ^ Only in TENANT_APPS")
    else:
        print(f"    ^ Not found in any app list")
