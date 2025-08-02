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

print("Checking tenants...")
tenants = Tenant.objects.all()
print(f"Total tenants: {tenants.count()}")

for tenant in tenants:
    print(f"ID: {tenant.id}")
    print(f"Slug: {tenant.slug}")
    print(f"Name: {tenant.name}")
    print(f"Database ID: tenant_{tenant.id}")
    print("---")
