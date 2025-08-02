from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from apps.core.tenant_models import Tenant
from apps.subscriptions.models import Subscription, SubscriptionPlan

class Command(BaseCommand):
    help = 'Create system admin user and setup permissions'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, default='sysadmin', help='System admin username')
        parser.add_argument('--email', type=str, default='admin@autowash.co.ke', help='System admin email')
        parser.add_argument('--password', type=str, default='AutowashAdmin2025!', help='System admin password')

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password']
        
        # Create or get system admin user
        admin_user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': email,
                'is_staff': True,
                'is_superuser': True,
                'first_name': 'System',
                'last_name': 'Administrator'
            }
        )
        
        if created:
            admin_user.set_password(password)
            admin_user.save()
            self.stdout.write(
                self.style.SUCCESS(f'Created system admin user: {username}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'System admin user already exists: {username}')
            )
        
        # Create System Admin group
        system_admin_group, created = Group.objects.get_or_create(
            name='System Administrators'
        )
        
        if created:
            # Add permissions for system admin group
            content_types = ContentType.objects.filter(
                app_label__in=['core', 'subscriptions', 'system_admin']
            )
            
            permissions = Permission.objects.filter(
                content_type__in=content_types
            )
            
            system_admin_group.permissions.set(permissions)
            self.stdout.write(
                self.style.SUCCESS('Created System Administrators group with permissions')
            )
        
        # Add user to system admin group
        admin_user.groups.add(system_admin_group)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSystem Admin Setup Complete!'
                f'\nUsername: {username}'
                f'\nEmail: {email}'
                f'\nPassword: {password}'
                f'\n\nAccess system admin at: /system-admin/'
                f'\nAccess Django admin at: /admin/'
            )
        )
