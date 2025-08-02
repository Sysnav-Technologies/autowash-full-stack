#!/usr/bin/env python
import os
import sys
import django
import pymysql

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'autowash.settings')
django.setup()

from django.conf import settings

print("=" * 60)
print("COMPLETE DATABASE AND MIGRATION RESET")
print("=" * 60)

# Step 1: Drop ALL databases
print("\n1. Dropping all autowash databases...")
default_db = settings.DATABASES['default']

try:
    connection = pymysql.connect(
        host=default_db['HOST'],
        user=default_db['USER'],
        password=default_db['PASSWORD'],
        port=int(default_db['PORT'])
    )
    
    cursor = connection.cursor()
    
    # Get list of all databases that start with 'autowash'
    cursor.execute("SHOW DATABASES LIKE 'autowash%'")
    databases = [row[0] for row in cursor.fetchall()]
    
    print(f"Found databases: {databases}")
    
    for db_name in databases:
        print(f"  Dropping database: {db_name}")
        cursor.execute(f"DROP DATABASE IF EXISTS `{db_name}`")
    
    cursor.close()
    connection.close()
    
    print("✓ All autowash databases dropped successfully")
    
except Exception as e:
    print(f"✗ Error dropping databases: {e}")
    sys.exit(1)

print("\n2. Creating fresh main database...")
try:
    connection = pymysql.connect(
        host=default_db['HOST'],
        user=default_db['USER'],
        password=default_db['PASSWORD'],
        port=int(default_db['PORT'])
    )
    
    cursor = connection.cursor()
    cursor.execute(f"CREATE DATABASE `{default_db['NAME']}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    cursor.close()
    connection.close()
    
    print(f"✓ Created main database: {default_db['NAME']}")
    
except Exception as e:
    print(f"✗ Error creating main database: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("DATABASE RESET COMPLETED SUCCESSFULLY!")
print("=" * 60)
print("\nNext steps:")
print("1. Delete all migration files")
print("2. Create fresh migrations")
print("3. Apply migrations")
print("4. Create superuser")
print("5. Create test tenant")
