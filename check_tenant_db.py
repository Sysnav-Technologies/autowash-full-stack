#!/usr/bin/env python
import os
import sys
import django

# Add the project root to Python path  
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'autowash.settings')
django.setup()

from django.db import connections

print("Checking tenant database tables...")

# Check tenant database
c = connections['default'].cursor()
c.execute("SHOW TABLES FROM autowash_testcarwash LIKE '%core%'")
core_tables = c.fetchall()
print(f"Core tables in tenant DB: {core_tables}")

c.execute("SHOW TABLES FROM autowash_testcarwash")
all_tables = c.fetchall()
print(f"Total tables in tenant DB: {len(all_tables)}")
print("First 10 tables:", [t[0] for t in all_tables[:10]])
