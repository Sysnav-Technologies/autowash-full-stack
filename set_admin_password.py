#!/usr/bin/env python
import os
import sys
import django

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'autowash.settings')
django.setup()

from django.contrib.auth.models import User

# Set superuser password
admin_user = User.objects.get(username='admin')
admin_user.set_password('admin123')
admin_user.save()

print("✓ Superuser password set to 'admin123'")
print(f"✓ Superuser: {admin_user.username} / admin123")
print(f"✓ Email: {admin_user.email}")
