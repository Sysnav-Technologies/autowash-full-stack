"""
Management command to create a new tenant database
"""
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from apps.core.tenant_models import Tenant
from apps.core.database_router import TenantDatabaseManager
import secrets
import string


class Command(BaseCommand):
    help = 'Create a new tenant database'

    def add_arguments(self, parser):
        parser.add_argument('tenant_slug', type=str, help='Tenant slug/identifier')
        parser.add_argument('--name', type=str, help='Business name', required=True)
        parser.add_argument('--owner-id', type=int, help='Owner user ID', required=True)
        parser.add_argument('--subdomain', type=str, help='Subdomain (defaults to slug)')
        parser.add_argument('--db-name', type=str, help='Database name (auto-generated if not provided)')
        parser.add_argument('--db-user', type=str, help='Database user (auto-generated if not provided)')
        parser.add_argument('--db-password', type=str, help='Database password (auto-generated if not provided)')
        parser.add_argument('--db-host', type=str, default='localhost', help='Database host')
        parser.add_argument('--db-port', type=int, default=3306, help='Database port')

    def handle(self, *args, **options):
        tenant_slug = options['tenant_slug']
        
        # Check if tenant already exists
        if Tenant.objects.filter(slug=tenant_slug).exists():
            raise CommandError(f"Tenant with slug '{tenant_slug}' already exists")
        
        # Get owner
        from django.contrib.auth.models import User
        try:
            owner = User.objects.get(id=options['owner_id'])
        except User.DoesNotExist:
            raise CommandError(f"User with ID {options['owner_id']} does not exist")
        
        # Generate database credentials if not provided
        db_name = options.get('db_name') or f"autowash_{tenant_slug.replace('-', '_')}"
        db_user = options.get('db_user') or f"user_{tenant_slug.replace('-', '_')}"[:16]
        
        if not options.get('db_password'):
            # Generate secure password
            alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
            db_password = ''.join(secrets.choice(alphabet) for _ in range(16))
        else:
            db_password = options['db_password']
        
        self.stdout.write(f"Creating tenant: {options['name']}")
        self.stdout.write(f"Slug: {tenant_slug}")
        self.stdout.write(f"Database: {db_name}")
        self.stdout.write(f"DB User: {db_user}")
        self.stdout.write(f"DB Host: {options['db_host']}:{options['db_port']}")
        
        # Create tenant object
        tenant = Tenant(
            name=options['name'],
            slug=tenant_slug,
            subdomain=options.get('subdomain') or tenant_slug,
            database_name=db_name,
            database_user=db_user,
            database_password=db_password,
            database_host=options['db_host'],
            database_port=options['db_port'],
            owner=owner,
        )
        
        try:
            # Save tenant (this will generate slug if needed)
            tenant.save()
            
            # Create the actual database
            self.stdout.write("Creating database...")
            if TenantDatabaseManager.create_tenant_database(tenant):
                self.stdout.write(
                    self.style.SUCCESS(f"Successfully created tenant '{tenant.name}'")
                )
                
                # Display connection info
                self.stdout.write("\n" + "="*50)
                self.stdout.write("TENANT DATABASE DETAILS:")
                self.stdout.write("="*50)
                self.stdout.write(f"Tenant ID: {tenant.id}")
                self.stdout.write(f"Business Name: {tenant.name}")
                self.stdout.write(f"Slug: {tenant.slug}")
                self.stdout.write(f"Subdomain: {tenant.subdomain}")
                self.stdout.write(f"Database Name: {tenant.database_name}")
                self.stdout.write(f"Database User: {tenant.database_user}")
                self.stdout.write(f"Database Password: {tenant.database_password}")
                self.stdout.write(f"Database Host: {tenant.database_host}")
                self.stdout.write(f"Database Port: {tenant.database_port}")
                self.stdout.write("\nACCESS URLs:")
                self.stdout.write(f"Path-based: /business/{tenant.slug}/")
                if hasattr(settings, 'MAIN_DOMAIN'):
                    self.stdout.write(f"Subdomain: {tenant.subdomain}.{settings.MAIN_DOMAIN}")
                self.stdout.write("="*50)
                
            else:
                # If database creation failed, delete the tenant object
                tenant.delete()
                raise CommandError("Failed to create tenant database")
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error creating tenant: {str(e)}")
            )
            # Clean up if something went wrong
            if tenant.id:
                tenant.delete()
            raise CommandError(f"Failed to create tenant: {str(e)}")
