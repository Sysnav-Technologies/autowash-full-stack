#!/usr/bin/env python
"""
Test script for tenant setup and database configuration
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'autowash.settings')
django.setup()

from apps.core.tenant_models import Tenant, TenantUser
from django.contrib.auth.models import User
from django.db import connection, connections
from django.conf import settings

def test_main_database():
    """Test main database connection"""
    print("=" * 50)
    print("TESTING MAIN DATABASE CONNECTION")
    print("=" * 50)
    
    try:
        # Test main database connection
        print(f"Database: {connection.settings_dict['NAME']}")
        print(f"User: {connection.settings_dict['USER']}")
        print(f"Host: {connection.settings_dict['HOST']}")
        print(f"Port: {connection.settings_dict['PORT']}")
        
        # Test query
        cursor = connection.cursor()
        cursor.execute("SELECT 1 as test")
        result = cursor.fetchone()
        print(f"Connection test result: {result}")
        
        # Check database tables
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print(f"Number of tables: {len(tables)}")
        
        return True
    except Exception as e:
        print(f"Main database connection failed: {e}")
        return False

def test_tenant_models():
    """Test tenant model operations"""
    print("\n" + "=" * 50)
    print("TESTING TENANT MODELS")
    print("=" * 50)
    
    try:
        # Check if any tenants exist
        tenant_count = Tenant.objects.count()
        print(f"Number of tenants: {tenant_count}")
        
        # List all tenants
        tenants = Tenant.objects.all()
        for tenant in tenants:
            print(f"Tenant: {tenant.name} (slug: {tenant.slug}, active: {tenant.is_active})")
            print(f"  Database: {tenant.database_name}")
            print(f"  Owner: {tenant.owner.username}")
            print(f"  Subdomain: {tenant.subdomain}")
        
        return True
    except Exception as e:
        print(f"Tenant model test failed: {e}")
        return False

def test_user_creation():
    """Test user and tenant creation"""
    print("\n" + "=" * 50)
    print("TESTING USER AND TENANT CREATION")
    print("=" * 50)
    
    try:
        # Check if test user exists
        test_username = "testbusiness"
        test_email = "test@business.com"
        
        try:
            user = User.objects.get(username=test_username)
            print(f"Test user already exists: {user.username}")
        except User.DoesNotExist:
            user = User.objects.create_user(
                username=test_username,
                email=test_email,
                password="testpass123"
            )
            print(f"Created test user: {user.username}")
        
        # Check if test tenant exists
        test_tenant_name = "Test Business"
        
        try:
            tenant = Tenant.objects.get(name=test_tenant_name)
            print(f"Test tenant already exists: {tenant.name}")
        except Tenant.DoesNotExist:
            tenant = Tenant(
                name=test_tenant_name,
                description="Test business for development",
                owner=user,
                database_user="root",  # Use same credentials for testing
                database_password="Brandon",
                business_type="car_wash",
                email="test@business.com",
                phone_number="+254700000000"
            )
            tenant.save()
            print(f"Created test tenant: {tenant.name}")
            print(f"Tenant slug: {tenant.slug}")
            print(f"Tenant database: {tenant.database_name}")
        
        return tenant
    except Exception as e:
        print(f"User/tenant creation failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_tenant_database_creation(tenant):
    """Test tenant database creation"""
    print("\n" + "=" * 50)
    print("TESTING TENANT DATABASE CREATION")
    print("=" * 50)
    
    if not tenant:
        print("No tenant provided for database creation test")
        return False
    
    try:
        from apps.core.database_router import TenantDatabaseManager
        
        print(f"Creating database for tenant: {tenant.name}")
        print(f"Database name: {tenant.database_name}")
        
        success = TenantDatabaseManager.create_tenant_database(tenant)
        
        if success:
            print("Tenant database created successfully!")
            
            # Test connection to tenant database
            db_alias = f"tenant_{tenant.id}"
            if db_alias in settings.DATABASES:
                print(f"Tenant database configuration added: {db_alias}")
                
                # Try to connect to tenant database
                tenant_conn = connections[db_alias]
                cursor = tenant_conn.cursor()
                cursor.execute("SELECT 1 as test")
                result = cursor.fetchone()
                print(f"Tenant database connection test: {result}")
                
                # Check tenant database tables
                cursor.execute("SHOW TABLES")
                tables = cursor.fetchall()
                print(f"Tenant database tables: {len(tables)}")
                
                return True
            else:
                print("Tenant database configuration not found in settings")
                return False
        else:
            print("Tenant database creation failed")
            return False
            
    except Exception as e:
        print(f"Tenant database creation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_admin_setup():
    """Test admin setup for both main and tenant"""
    print("\n" + "=" * 50)
    print("TESTING ADMIN SETUP")
    print("=" * 50)
    
    try:
        # Check if superuser exists
        superuser_count = User.objects.filter(is_superuser=True).count()
        print(f"Number of superusers: {superuser_count}")
        
        if superuser_count == 0:
            print("Creating superuser for main admin...")
            superuser = User.objects.create_superuser(
                username="admin",
                email="admin@autowash.co.ke",
                password="admin123"
            )
            print(f"Created superuser: {superuser.username}")
        else:
            superusers = User.objects.filter(is_superuser=True)
            for su in superusers:
                print(f"Existing superuser: {su.username}")
        
        return True
    except Exception as e:
        print(f"Admin setup test failed: {e}")
        return False

def main():
    """Main test function"""
    print("AUTOWASH MULTI-TENANT SETUP TEST")
    print("=" * 50)
    
    # Test main database
    if not test_main_database():
        print("Main database test failed. Cannot proceed.")
        return
    
    # Test tenant models
    if not test_tenant_models():
        print("Tenant models test failed. Cannot proceed.")
        return
    
    # Test user and tenant creation
    tenant = test_user_creation()
    
    # Test tenant database creation
    if tenant:
        test_tenant_database_creation(tenant)
    
    # Test admin setup
    test_admin_setup()
    
    print("\n" + "=" * 50)
    print("TEST COMPLETE")
    print("=" * 50)

if __name__ == "__main__":
    main()
