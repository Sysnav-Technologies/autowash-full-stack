#!/usr/bin/env python
import os
import sys
import pymysql
from decouple import config

print("Dropping all autowash databases...")

# Get database credentials
db_host = config('DB_HOST', default='localhost')
db_port = int(config('DB_PORT', default='3306'))
db_user = config('DB_USER', default='root')
db_password = config('DB_PASSWORD', default='')

try:
    # Connect to MySQL server
    connection = pymysql.connect(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_password
    )
    
    cursor = connection.cursor()
    
    # Get all databases that start with 'autowash'
    cursor.execute("SHOW DATABASES LIKE 'autowash%'")
    databases = cursor.fetchall()
    
    print(f"Found {len(databases)} autowash databases to drop:")
    for db in databases:
        db_name = db[0]
        print(f"  - {db_name}")
        try:
            cursor.execute(f"DROP DATABASE IF EXISTS `{db_name}`")
            print(f"    ✓ Dropped {db_name}")
        except Exception as e:
            print(f"    ✗ Error dropping {db_name}: {e}")
    
    # Create fresh main database
    main_db_name = config('DB_NAME', default='autowash_main')
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{main_db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    print(f"✓ Created fresh main database: {main_db_name}")
    
    cursor.close()
    connection.close()
    
    print("Database cleanup completed successfully!")
    
except Exception as e:
    print(f"Error: {e}")
    print("Please ensure MySQL is running and credentials are correct.")
