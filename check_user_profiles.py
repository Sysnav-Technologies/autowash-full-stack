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
from apps.accounts.models import UserProfile

print("=" * 60)
print("CHECKING USER PROFILES")
print("=" * 60)

# Check if admin user has a profile
admin_user = User.objects.get(username='admin')
print(f"Admin user: {admin_user.username}")

try:
    profile = admin_user.profile
    print(f"✓ Admin user has profile: {profile}")
    print(f"  Timezone: {profile.timezone}")
except UserProfile.DoesNotExist:
    print("✗ Admin user has no profile, creating one...")
    profile = UserProfile.objects.create(
        user=admin_user,
        timezone='Africa/Nairobi'
    )
    print(f"✓ Created profile for admin user")
    print(f"  Timezone: {profile.timezone}")

print(f"\nAll UserProfiles in main database:")
profiles = UserProfile.objects.all()
for profile in profiles:
    print(f"  - {profile.user.username}: {profile.timezone}")

print(f"\n✅ User profiles ready for timezone middleware")
