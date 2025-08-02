#!/usr/bin/env python
"""Test tenant creation script"""

import os
import sys
import django

# Add project root to path
sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'autowash.settings')
django.setup()

from apps.core.tenant_models import Tenant
from django.contrib.auth.models import User

def test_tenant_creation():
    print("Testing tenant creation...")
    
    # Create a test user first
    user, created = User.objects.get_or_create(
        username='testowner',
        defaults={
            'email': 'testowner@example.com',
            'first_name': 'Test',
            'last_name': 'Owner'
        }
    )
    print(f"User {'created' if created else 'found'}: {user.username}")

    # Create a test tenant
    tenant, created = Tenant.objects.get_or_create(
        subdomain='testbusiness',
        defaults={
            'name': 'Test Business',
            'slug': 'test-business',
            'database_name': 'autowash_testbusiness',
            'database_user': 'root',
            'database_password': 'password',
            'email': 'info@testbusiness.com',
            'phone': '+254712345678',
            'owner': user,
            'is_verified': True,
            'is_active': True
        }
    )
    print(f"Tenant {'created' if created else 'found'}: {tenant.name}")
    print(f"Database name: {tenant.database_name}")
    
    # Test database manager
    from apps.core.database_router import TenantDatabaseManager
    
    # Test database creation
    print("Attempting to create tenant database...")
    try:
        success = TenantDatabaseManager.create_tenant_database(tenant)
        print(f"Database creation result: {success}")
    except Exception as e:
        print(f"Database creation error: {e}")
        print(f"Error type: {type(e)}")
        import traceback
        traceback.print_exc()
    
    return tenant

if __name__ == '__main__':
    test_tenant_creation()
