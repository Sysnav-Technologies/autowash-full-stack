#!/usr/bin/env python
"""
cPanel Deployment Reset Script
Run this after uploading your Django application to cPanel
"""
import os
import sys
import subprocess
import django
from django.conf import settings

# Add the project directory to Python path
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'autowash.settings')

try:
    django.setup()
    from django.core.cache import cache
    from django.core.management import execute_from_command_line
    
    print("🚀 cPanel Django Application Reset")
    print("=" * 40)
    
    # Clear cache
    print("1. Clearing application cache...")
    try:
        cache.clear()
        print("   ✅ Cache cleared")
    except Exception as e:
        print(f"   ⚠️  Cache clear failed: {e}")
    
    # Create cache table
    print("2. Creating cache table...")
    try:
        execute_from_command_line(['manage.py', 'createcachetable'])
        print("   ✅ Cache table ready")
    except Exception as e:
        print(f"   ⚠️  Cache table creation failed: {e}")
    
    # Collect static files
    print("3. Collecting static files...")
    try:
        execute_from_command_line(['manage.py', 'collectstatic', '--noinput'])
        print("   ✅ Static files collected")
    except Exception as e:
        print(f"   ⚠️  Static files collection failed: {e}")
    
    # Run migrations
    print("4. Running database migrations...")
    try:
        execute_from_command_line(['manage.py', 'migrate'])
        print("   ✅ Migrations complete")
    except Exception as e:
        print(f"   ⚠️  Migrations failed: {e}")
    
    print("=" * 40)
    print("🎉 cPanel reset complete!")
    print("\nNow restart your application:")
    print("- If using Passenger: touch tmp/restart.txt")
    print("- If using supervisor: supervisorctl restart your_app")
    print("- Check your cPanel error logs for any issues")
    
except Exception as e:
    print(f"❌ Setup failed: {e}")
    print("Make sure you're running this from your Django project directory")
