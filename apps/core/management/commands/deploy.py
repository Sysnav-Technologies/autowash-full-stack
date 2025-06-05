import os
import sys
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.conf import settings
from django.contrib.auth.models import User
from django.db import connection
from django.db.utils import IntegrityError

class Command(BaseCommand):
    help = 'Deploy Autowash application with initial setup'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-migrations',
            action='store_true',
            help='Skip database migrations'
        )
        parser.add_argument(
            '--skip-superuser',
            action='store_true', 
            help='Skip superuser creation'
        )
        parser.add_argument(
            '--skip-static',
            action='store_true',
            help='Skip static files collection'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('\n' + '='*70)
        )
        self.stdout.write(
            self.style.SUCCESS('🚀 AUTOWASH DEPLOYMENT STARTING')
        )
        self.stdout.write(
            self.style.SUCCESS('='*70 + '\n')
        )

        try:
            # Step 1: Check database connection
            self.stdout.write('🔌 Checking database connection...')
            self.check_database_connection()
            self.stdout.write(self.style.SUCCESS('✅ Database connection successful'))

            # Step 2: Create logs directory
            self.stdout.write('📁 Creating logs directory...')
            self.create_logs_directory()
            self.stdout.write(self.style.SUCCESS('✅ Logs directory created'))

            # Step 3: Create cache table
            self.stdout.write('💾 Creating cache table...')
            self.create_cache_table()
            self.stdout.write(self.style.SUCCESS('✅ Cache table created'))

            # Step 4: Run migrations for shared schema
            if not options['skip_migrations']:
                self.stdout.write('🔄 Running shared schema migrations...')
                self.run_shared_migrations()
                self.stdout.write(self.style.SUCCESS('✅ Shared schema migrations completed'))
            else:
                self.stdout.write(self.style.WARNING('⏭️ Skipping migrations'))

            # Step 5: Collect static files
            if not options['skip_static']:
                self.stdout.write('📂 Collecting static files...')
                self.collect_static_files()
                self.stdout.write(self.style.SUCCESS('✅ Static files collected'))
            else:
                self.stdout.write(self.style.WARNING('⏭️ Skipping static files'))

            # Step 6: Create superuser FIRST (required for public tenant)
            if not options['skip_superuser']:
                self.stdout.write('👤 Creating superuser...')
                superuser = self.create_superuser()
                self.stdout.write(self.style.SUCCESS('✅ Superuser created'))
            else:
                self.stdout.write(self.style.WARNING('⏭️ Skipping superuser creation'))
                # Get existing superuser for public tenant
                try:
                    superuser = User.objects.filter(is_superuser=True).first()
                    if not superuser:
                        raise Exception("No superuser found. Cannot create public tenant without an owner.")
                except Exception as e:
                    raise Exception(f"Failed to find superuser for public tenant: {e}")

            # Step 7: Create public tenant (with superuser as owner)
            self.stdout.write('🏢 Creating public tenant...')
            self.create_public_tenant(superuser)
            self.stdout.write(self.style.SUCCESS('✅ Public tenant created'))

            # Step 8: Run health checks
            self.stdout.write('🏥 Running health checks...')
            self.run_health_checks()
            self.stdout.write(self.style.SUCCESS('✅ Health checks passed'))

            # Success message
            self.stdout.write(
                self.style.SUCCESS('\n' + '='*70)
            )
            self.stdout.write(
                self.style.SUCCESS('🎉 DEPLOYMENT COMPLETED SUCCESSFULLY!')
            )
            self.stdout.write(
                self.style.SUCCESS('='*70)
            )
            
            # Environment-specific instructions
            if not settings.RENDER:
                self.stdout.write(
                    self.style.SUCCESS('\n🏠 LOCAL DEVELOPMENT SETUP COMPLETE')
                )
                self.stdout.write('🌐 Main site: http://localhost:8000')
                self.stdout.write('👤 Admin: http://localhost:8000/admin/')
                self.stdout.write('🔑 Login: admin@autowash.co.ke / 123456')
                self.stdout.write('📋 Test business registration and check subdomains')
                if settings.DEBUG:
                    self.stdout.write('🐛 Debug mode: ENABLED')
                else:
                    self.stdout.write('🐛 Debug mode: DISABLED')
            else:
                self.stdout.write(
                    self.style.SUCCESS('\n🚀 RENDER DEPLOYMENT COMPLETE')
                )
                self.stdout.write('🌐 Main site: https://autowash-3jpr.onrender.com')
                self.stdout.write('👤 Admin: https://autowash-3jpr.onrender.com/admin/')
                self.stdout.write('🔑 Login: admin@autowash.co.ke / 123456')
                self.stdout.write('📋 Test business registration and check subdomains')
                if settings.DEBUG:
                    self.stdout.write('🐛 Debug mode: ENABLED')
                    self.stdout.write('   - Debug toolbar available')
                    self.stdout.write('   - Enhanced logging active')
                    self.stdout.write('   - Security settings relaxed')
                else:
                    self.stdout.write('🐛 Debug mode: DISABLED')
                    self.stdout.write('   - Production security active')
                    if getattr(settings, 'SENTRY_DSN', ''):
                        self.stdout.write('   - Sentry monitoring enabled')

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\n❌ DEPLOYMENT FAILED: {str(e)}')
            )
            raise

    def check_database_connection(self):
        """Check if database connection is working"""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                if result[0] != 1:
                    raise Exception("Database query failed")
        except Exception as e:
            raise Exception(f"Database connection failed: {e}")

    def create_logs_directory(self):
        """Create logs directory if it doesn't exist"""
        logs_dir = os.path.join(settings.BASE_DIR, 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        
        # Create a test log file to ensure permissions
        test_log = os.path.join(logs_dir, 'test.log')
        with open(test_log, 'w') as f:
            f.write('Deployment test log\n')
        os.remove(test_log)

    def create_cache_table(self):
        """Create cache table for database cache"""
        try:
            call_command('createcachetable', verbosity=0)
        except Exception as e:
            # Table might already exist
            if 'already exists' not in str(e).lower():
                raise

    def run_shared_migrations(self):
        """Run migrations for shared schema"""
        try:
            call_command('migrate_schemas', '--shared', verbosity=1)
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'Migration warning: {e}')
            )
            # Try regular migrate as fallback
            call_command('migrate', verbosity=1)

    def collect_static_files(self):
        """Collect static files"""
        call_command('collectstatic', '--noinput', verbosity=1)

    def create_public_tenant(self, owner_user):
        """Create public tenant for main site with specified owner"""
        try:
            from apps.accounts.models import Business, Domain
            
            # Check if public tenant exists
            try:
                public_tenant = Business.objects.get(schema_name='public')
                self.stdout.write('Public tenant already exists')
            except Business.DoesNotExist:
                # Create public tenant with owner
                public_tenant = Business.objects.create(
                    name='Autowash Public',
                    slug='public',
                    schema_name='public',
                    description='Main public site',
                    business_type='full_service',
                    owner=owner_user,  # THIS IS THE KEY FIX
                    # Optional: Set other required fields
                    country='Kenya',
                    timezone='Africa/Nairobi',
                    currency='KES',
                    language='en',
                    is_active=True,
                    is_verified=True  # Public tenant should be verified
                )
                self.stdout.write('Public tenant created with owner')

            # Create domains for public tenant based on environment
            if not settings.RENDER:
                # Local development domains
                domains_to_create = [
                    ('127.0.0.1:8000', True),
                    ('localhost:8000', False),
                ]
            else:
                # Render production domains
                domains_to_create = [
                    ('autowash-3jpr.onrender.com', True),
                    ('www.autowash-3jpr.onrender.com', False),
                ]
                
                # Add custom domain if available
                # Uncomment when custom domain is configured:
                # domains_to_create.extend([
                #     ('autowash.co.ke', False),
                #     ('www.autowash.co.ke', False),
                # ])

            for domain_name, is_primary in domains_to_create:
                domain, created = Domain.objects.get_or_create(
                    domain=domain_name,
                    defaults={
                        'tenant': public_tenant,
                        'is_primary': is_primary
                    }
                )
                if created:
                    self.stdout.write(f'Created domain: {domain_name}')
                else:
                    self.stdout.write(f'Domain already exists: {domain_name}')

        except Exception as e:
            raise Exception(f"Failed to create public tenant: {e}")

    def create_superuser(self):
        """Create superuser with predefined credentials"""
        try:
            # Check if superuser exists
            superuser = User.objects.filter(email='admin@autowash.co.ke').first()
            if superuser:
                self.stdout.write('Superuser already exists')
                return superuser

            # Create superuser
            superuser = User.objects.create_superuser(
                username='autowash',
                email='admin@autowash.co.ke',
                password='123456',
                first_name='Admin',
                last_name='User'
            )
            self.stdout.write('Superuser created successfully')
            return superuser

        except IntegrityError:
            # Handle case where username might exist but not email
            try:
                superuser = User.objects.get(username='autowash')
                self.stdout.write('Superuser already exists (found by username)')
                return superuser
            except User.DoesNotExist:
                raise Exception("IntegrityError but superuser not found")
        except Exception as e:
            raise Exception(f"Failed to create superuser: {e}")

    def run_health_checks(self):
        """Run Django health checks"""
        try:
            # Use deploy checks only on Render with debug disabled
            if settings.RENDER and not settings.DEBUG:
                call_command('check', '--deploy', verbosity=0)
            else:
                call_command('check', verbosity=0)
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'Health check warning: {e}')
            )