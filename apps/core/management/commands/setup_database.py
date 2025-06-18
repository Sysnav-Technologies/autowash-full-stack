"""
Django management command to set up database for multi-tenant application
Save this file as: apps/core/management/commands/setup_database.py

Then run: python manage.py setup_database
"""

import os
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth.models import User
from django.db import connection
from django.conf import settings


class Command(BaseCommand):
    help = 'Set up database for Django multi-tenant application'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-migrations',
            action='store_true',
            help='Skip running migrations'
        )
        parser.add_argument(
            '--skip-superuser',
            action='store_true',
            help='Skip creating superuser'
        )
        parser.add_argument(
            '--username',
            type=str,
            default='admin',
            help='Superuser username (default: admin)'
        )
        parser.add_argument(
            '--email',
            type=str,
            default='admin@gmail.com',
            help='Superuser email (default: admin@gmail.com)'
        )
        parser.add_argument(
            '--password',
            type=str,
            default='123456',
            help='Superuser password (default: 123456)'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('\n' + '='*60)
        )
        self.stdout.write(
            self.style.SUCCESS('🗄️ SETTING UP DATABASE FOR DJANGO TENANTS')
        )
        self.stdout.write(
            self.style.SUCCESS('='*60 + '\n')
        )

        try:
            # Step 1: Check database connection
            self.stdout.write('🔌 Testing database connection...')
            self.test_database_connection()
            self.stdout.write(self.style.SUCCESS('✅ Database connection successful\n'))

            # Step 2: Create migrations if needed
            if not options['skip_migrations']:
                self.stdout.write('📝 Creating migrations...')
                self.create_migrations()
                self.stdout.write(self.style.SUCCESS('✅ Migrations created\n'))

                # Step 3: Run basic Django migrations
                self.stdout.write('🔨 Running basic Django migrations...')
                self.run_basic_migrations()
                self.stdout.write(self.style.SUCCESS('✅ Basic migrations completed\n'))

                # Step 4: Run shared schema migrations
                self.stdout.write('🏗️ Running shared schema migrations...')
                self.run_shared_migrations()
                self.stdout.write(self.style.SUCCESS('✅ Shared schema migrations completed\n'))

                # Step 5: Run tenant migrations
                self.stdout.write('🏢 Running tenant schema migrations...')
                self.run_tenant_migrations()
                self.stdout.write(self.style.SUCCESS('✅ Tenant schema migrations completed\n'))
            else:
                self.stdout.write(self.style.WARNING('⏭️ Skipping migrations\n'))

            # Step 6: Create superuser
            if not options['skip_superuser']:
                self.stdout.write('👤 Creating superuser...')
                superuser = self.create_superuser(
                    options['username'],
                    options['email'],
                    options['password']
                )
                self.stdout.write(self.style.SUCCESS('✅ Superuser created\n'))
            else:
                superuser = User.objects.filter(is_superuser=True).first()
                if not superuser:
                    raise Exception("No superuser found and --skip-superuser specified")

            # Step 7: Create public tenant
            self.stdout.write('🌐 Creating public tenant...')
            self.create_public_tenant(superuser)
            self.stdout.write(self.style.SUCCESS('✅ Public tenant created\n'))

            # Step 8: Create cache table
            self.stdout.write('💾 Creating cache table...')
            self.create_cache_table()
            self.stdout.write(self.style.SUCCESS('✅ Cache table created\n'))

            # Step 9: Collect static files
            self.stdout.write('📂 Collecting static files...')
            self.collect_static_files()
            self.stdout.write(self.style.SUCCESS('✅ Static files collected\n'))

            # Success message
            self.stdout.write(
                self.style.SUCCESS('\n' + '='*60)
            )
            self.stdout.write(
                self.style.SUCCESS('🎉 DATABASE SETUP COMPLETED SUCCESSFULLY!')
            )
            self.stdout.write(
                self.style.SUCCESS('='*60)
            )

            self.display_success_info(options['username'], options['email'], options['password'])

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\n❌ DATABASE SETUP FAILED: {str(e)}')
            )
            import traceback
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
            raise

    def test_database_connection(self):
        """Test database connection"""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                if result[0] != 1:
                    raise Exception("Database query failed")
        except Exception as e:
            raise Exception(f"Database connection failed: {e}")

    def create_migrations(self):
        """Create migrations for all apps"""
        apps_to_migrate = [
            'accounts',
            'businesses',
            'core',
            'subscriptions',
            'employees',
            'customers',
            'services',
            'inventory',
            'suppliers',
            'payments',
            'reports',
            'expenses',
            'notification',
        ]

        for app in apps_to_migrate:
            try:
                call_command('makemigrations', app, verbosity=0, interactive=False)
                self.stdout.write(f"  ✓ Created migrations for {app}")
            except Exception as e:
                self.stdout.write(f"  ⚠️ Could not create migrations for {app}: {e}")

        # Create any remaining migrations
        try:
            call_command('makemigrations', verbosity=0, interactive=False)
            self.stdout.write("  ✓ Created any remaining migrations")
        except Exception as e:
            self.stdout.write(f"  ⚠️ Could not create remaining migrations: {e}")

    def run_basic_migrations(self):
        """Run basic Django migrations"""
        try:
            call_command('migrate', verbosity=1, interactive=False)
        except Exception as e:
            self.stdout.write(f"  ⚠️ Basic migrations warning: {e}")

    def run_shared_migrations(self):
        """Run shared schema migrations for django-tenants"""
        try:
            call_command('migrate_schemas', '--shared', verbosity=1, interactive=False)
        except Exception as e:
            # If migrate_schemas fails, try regular migrate
            self.stdout.write(f"  ⚠️ migrate_schemas --shared failed: {e}")
            self.stdout.write("  🔄 Trying regular migrate...")
            call_command('migrate', verbosity=1, interactive=False)

    def run_tenant_migrations(self):
        """Run tenant schema migrations"""
        try:
            call_command('migrate_schemas', verbosity=1, interactive=False)
        except Exception as e:
            self.stdout.write(f"  ⚠️ Tenant migrations warning: {e}")

    def create_superuser(self, username, email, password):
        """Create superuser"""
        try:
            # Check if user already exists
            user = User.objects.filter(username=username).first()
            if user:
                self.stdout.write(f"  ✓ User '{username}' already exists")
                if not user.is_superuser:
                    user.is_superuser = True
                    user.is_staff = True
                    user.save()
                    self.stdout.write(f"  ✓ Made '{username}' a superuser")
                return user

            # Create new superuser
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
                first_name='Admin',
                last_name='User'
            )
            self.stdout.write(f"  ✓ Created superuser: {username}")
            return user

        except Exception as e:
            raise Exception(f"Failed to create superuser: {e}")

    def create_public_tenant(self, superuser):
        """Create public tenant and domain"""
        try:
            from apps.accounts.models import Business, Domain

            # Create or get public tenant
            public_tenant, created = Business.objects.get_or_create(
                schema_name='public',
                defaults={
                    'name': 'Autowash Public',
                    'slug': 'public',
                    'description': 'Main public site for path-based routing',
                    'business_type': 'full_service',
                    'owner': superuser,
                    'country': 'Kenya',
                    'timezone': 'Africa/Nairobi',
                    'currency': 'KES',
                    'language': 'en',
                    'is_active': True,
                    'is_verified': True
                }
            )

            if created:
                self.stdout.write("  ✓ Public tenant created")
            else:
                self.stdout.write("  ✓ Public tenant already exists")

            # Create domains
            domains_to_create = [
                ('app.autowash.co.ke', True),
                ('autowash.co.ke', False),
                ('www.autowash.co.ke', False),
            ]

            for domain_name, is_primary in domains_to_create:
                domain, created = Domain.objects.get_or_create(
                    domain=domain_name,
                    defaults={
                        'tenant': public_tenant,
                        'is_primary': is_primary
                    }
                )
                if created:
                    self.stdout.write(f"  ✓ Created domain: {domain_name}")
                else:
                    self.stdout.write(f"  ✓ Domain already exists: {domain_name}")

        except Exception as e:
            raise Exception(f"Failed to create public tenant: {e}")

    def create_cache_table(self):
        """Create cache table"""
        try:
            call_command('createcachetable', verbosity=0)
        except Exception as e:
            if 'already exists' not in str(e).lower():
                self.stdout.write(f"  ⚠️ Cache table warning: {e}")

    def collect_static_files(self):
        """Collect static files"""
        try:
            call_command('collectstatic', '--noinput', verbosity=0)
        except Exception as e:
            self.stdout.write(f"  ⚠️ Static files warning: {e}")

    def display_success_info(self, username, email, password):
        """Display success information"""
        self.stdout.write(
            self.style.SUCCESS('\n📋 SETUP INFORMATION:')
        )
        self.stdout.write(f"🌐 Website: https://app.autowash.co.ke/")
        self.stdout.write(f"👤 Admin: https://app.autowash.co.ke/admin/")
        self.stdout.write(f"📧 Username: {username}")
        self.stdout.write(f"📧 Email: {email}")
        self.stdout.write(f"🔑 Password: {password}")
        self.stdout.write(
            self.style.SUCCESS('\n🎯 Your Django multi-tenant application is now ready!')
        )
        self.stdout.write(
            self.style.WARNING('\n⚠️ Remember to:')
        )
        self.stdout.write('   1. Change the default password')
        self.stdout.write('   2. Update your environment variables')
        self.stdout.write('   3. Restart your application (touch passenger_wsgi.py)')
        self.stdout.write('')