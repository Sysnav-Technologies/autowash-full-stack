#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'autowash.settings')
django.setup()

from apps.services.models import Service
from django.db.models import Count
from django_tenants.utils import tenant_context, get_public_schema_name
from django_tenants.models import TenantMixin

def fix_duplicate_services():
    """Fix duplicate service names by appending numbers"""
    
    # Get all tenants
    from apps.businesses.models import Business
    tenants = Business.objects.all()
    
    for tenant in tenants:
        print(f"Checking tenant: {tenant.schema_name}")
        
        with tenant_context(tenant):
            # Find duplicates
            duplicates = Service.objects.values('name').annotate(
                name_count=Count('name')
            ).filter(name_count__gt=1)
            
            print(f"Found duplicates: {list(duplicates)}")
            
            for duplicate in duplicates:
                name = duplicate['name']
                services = Service.objects.filter(name=name).order_by('id')
                
                # Keep the first one, rename the rest
                for i, service in enumerate(services[1:], start=2):
                    new_name = f"{name} ({i})"
                    print(f"Renaming '{service.name}' to '{new_name}'")
                    service.name = new_name
                    service.save()

if __name__ == '__main__':
    fix_duplicate_services()
    print("Duplicate services fixed!")
