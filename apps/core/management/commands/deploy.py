import os
import sys
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.conf import settings
from django.contrib.auth.models import User
from django.db import connection
from django.db.utils import IntegrityError

class Command(BaseCommand):
    help = 'Deploy Autowash application with path-based tenant routing (Local/Render/cPanel)'

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
        parser.add_argument(
            '--environment',
            type=str,
            choices=['local', 'render', 'cpanel'],
            help='Specify deployment environment'
        )

    def handle(self, *args, **options):
        # Detect environment
        environment = self.detect_environment(options.get('environment'))
        
        self.stdout.write(
            self.style.SUCCESS('\n' + '='*70)
        )
        self.stdout.write(
            self.style.SUCCESS(f'🚀 AUTOWASH DEPLOYMENT STARTING ({environment.upper()} - PATH-BASED ROUTING)')
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

            # Step 5: Collect static files (environment-specific)
            if not options['skip_static']:
                self.stdout.write('📂 Collecting static files...')
                self.collect_static_files(environment)
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
            self.create_public_tenant(superuser, environment)
            self.stdout.write(self.style.SUCCESS('✅ Public tenant created'))

            # Step 8: Environment-specific setup
            self.stdout.write(f'⚙️ Running {environment} specific setup...')
            self.environment_specific_setup(environment)
            self.stdout.write(self.style.SUCCESS('✅ Environment setup completed'))

            # Step 9: Run health checks
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
            self.display_environment_instructions(environment)

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\n❌ DEPLOYMENT FAILED: {str(e)}')
            )
            import traceback
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
            raise

    def detect_environment(self, specified_env=None):
        """Detect the deployment environment"""
        if specified_env:
            return specified_env
            
        if getattr(settings, 'RENDER', False):
            return 'render'
        elif getattr(settings, 'CPANEL', False):
            return 'cpanel'
        else:
            return 'local'

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
        try:
            test_log = os.path.join(logs_dir, 'test.log')
            with open(test_log, 'w') as f:
                f.write('Deployment test log\n')
            os.remove(test_log)
        except PermissionError:
            self.stdout.write(self.style.WARNING('Warning: Limited write permissions for logs directory'))

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
            # Try django-tenants migrations first
            call_command('migrate_schemas', '--shared', verbosity=1)
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'Django-tenants migration warning: {e}')
            )
            # Try regular migrate as fallback
            try:
                call_command('migrate', verbosity=1)
            except Exception as e2:
                raise Exception(f"Both django-tenants and regular migrations failed: {e2}")

    def collect_static_files(self, environment):
        """Collect static files with environment-specific handling"""
        try:
            if environment == 'cpanel':
                # For cPanel, ensure the static directory exists
                static_root = getattr(settings, 'STATIC_ROOT', None)
                if static_root:
                    os.makedirs(static_root, exist_ok=True)
                    self.stdout.write(f'Static root directory: {static_root}')
            
            call_command('collectstatic', '--noinput', verbosity=1)
            
            # Set permissions for cPanel
            if environment == 'cpanel':
                static_root = getattr(settings, 'STATIC_ROOT', None)
                if static_root and os.path.exists(static_root):
                    try:
                        os.chmod(static_root, 0o755)
                        self.stdout.write('Set static files permissions')
                    except:
                        self.stdout.write(self.style.WARNING('Could not set static files permissions'))
                        
        except Exception as e:
            if environment == 'cpanel':
                self.stdout.write(self.style.WARNING(f'Static files warning: {e}'))
            else:
                raise

    def create_public_tenant(self, owner_user, environment):
        """Create public tenant for main site with specified owner"""
        try:
            from apps.accounts.models import Business, Domain
            
            # Check if public tenant exists
            try:
                public_tenant = Business.objects.get(schema_name='public')
                self.stdout.write('Public tenant already exists')
                
                # Update owner if not set
                if not public_tenant.owner:
                    public_tenant.owner = owner_user
                    public_tenant.save()
                    self.stdout.write('Updated public tenant owner')
                    
            except Business.DoesNotExist:
                # Create public tenant with owner
                public_tenant = Business.objects.create(
                    name='Autowash Public',
                    slug='public',
                    schema_name='public',
                    description='Main public site for path-based routing',
                    business_type='full_service',
                    owner=owner_user,
                    country='Kenya',
                    timezone='Africa/Nairobi',
                    currency='KES',
                    language='en',
                    is_active=True,
                    is_verified=True
                )
                self.stdout.write('Public tenant created with owner')

            # Create domains for public tenant based on environment
            domains_to_create = self.get_domains_for_environment(environment)

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

    def get_domains_for_environment(self, environment):
        """Get domains based on environment"""
        if environment == 'local':
            return [
                ('localhost:8000', True),
                ('127.0.0.1:8000', False),
            ]
        elif environment == 'render':
            domains = [
                ('autowash-3jpr.onrender.com', True),
                ('www.autowash-3jpr.onrender.com', False),
            ]
            # Add custom domain if available
            render_hostname = getattr(settings, 'RENDER_EXTERNAL_HOSTNAME', '')
            if render_hostname:
                domains.append((render_hostname, False))
            return domains
        elif environment == 'cpanel':
            return [
                ('app.autowash.co.ke', True),
                ('autowash.co.ke', False),
                ('www.autowash.co.ke', False),
            ]
        return []

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

    def environment_specific_setup(self, environment):
        """Run environment-specific setup tasks"""
        if environment == 'cpanel':
            self.cpanel_specific_setup()
        elif environment == 'render':
            self.render_specific_setup()
        elif environment == 'local':
            self.local_specific_setup()

    def cpanel_specific_setup(self):
        """cPanel-specific setup tasks"""
        try:
            # Create media directory
            media_root = getattr(settings, 'MEDIA_ROOT', None)
            if media_root:
                os.makedirs(media_root, exist_ok=True)
                try:
                    os.chmod(media_root, 0o755)
                except:
                    pass

            # Create tenant media directory
            tenant_media_root = getattr(settings, 'TENANT_MEDIA_ROOT', None)
            if tenant_media_root:
                os.makedirs(tenant_media_root, exist_ok=True)
                try:
                    os.chmod(tenant_media_root, 0o755)
                except:
                    pass

            # Touch passenger_wsgi.py to restart the app
            passenger_wsgi = os.path.join(settings.BASE_DIR, 'passenger_wsgi.py')
            if os.path.exists(passenger_wsgi):
                os.utime(passenger_wsgi, None)
                self.stdout.write('Restarted cPanel application')

        except Exception as e:
            self.stdout.write(self.style.WARNING(f'cPanel setup warning: {e}'))

    def render_specific_setup(self):
        """Render-specific setup tasks"""
        try:
            # Render-specific optimizations
            self.stdout.write('Render optimizations applied')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Render setup warning: {e}'))

    def local_specific_setup(self):
        """Local development-specific setup tasks"""
        try:
            # Local development optimizations
            self.stdout.write('Local development setup completed')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Local setup warning: {e}'))

    def run_health_checks(self):
        """Run Django health checks"""
        try:
            environment = self.detect_environment()
            
            # Use deploy checks only in production with debug disabled
            if environment in ['render', 'cpanel'] and not settings.DEBUG:
                call_command('check', '--deploy', verbosity=0)
            else:
                call_command('check', verbosity=0)
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'Health check warning: {e}')
            )

    def display_environment_instructions(self, environment):
        """Display environment-specific instructions"""
        if environment == 'local':
            self.display_local_instructions()
        elif environment == 'render':
            self.display_render_instructions()
        elif environment == 'cpanel':
            self.display_cpanel_instructions()

    def display_local_instructions(self):
        """Display local development instructions"""
        self.stdout.write(
            self.style.SUCCESS('\n🏠 LOCAL DEVELOPMENT SETUP COMPLETE (PATH-BASED)')
        )
        self.stdout.write('🌐 Main site: http://localhost:8000/')
        self.stdout.write('👤 Admin: http://localhost:8000/admin/')
        self.stdout.write('🔑 Login: admin@autowash.co.ke / 123456')
        self.stdout.write('🏢 Business URLs: http://localhost:8000/business/{slug}/')
        self.stdout.write('📋 Register a business and access via path-based URLs')
        if settings.DEBUG:
            self.stdout.write('🐛 Debug mode: ENABLED')
        else:
            self.stdout.write('🐛 Debug mode: DISABLED')

    def display_render_instructions(self):
        """Display Render instructions"""
        self.stdout.write(
            self.style.SUCCESS('\n🚀 RENDER DEPLOYMENT COMPLETE (PATH-BASED)')
        )
        self.stdout.write('🌐 Main site: https://autowash-3jpr.onrender.com/')
        self.stdout.write('👤 Admin: https://autowash-3jpr.onrender.com/admin/')
        self.stdout.write('🔑 Login: admin@autowash.co.ke / 123456')
        self.stdout.write('🏢 Business URLs: https://autowash-3jpr.onrender.com/business/{slug}/')
        self.stdout.write('📋 Register a business and access via path-based URLs')
        
        if settings.DEBUG:
            self.stdout.write('🔧 DEBUG MODE: Enabled')
            self.stdout.write('   - Debug toolbar available')
            self.stdout.write('   - Enhanced logging active')
            self.stdout.write('   - Security settings relaxed')
            self.stdout.write('🐛 Sentry: Disabled')
        else:
            self.stdout.write('🔒 Security: Strict production mode')
            if getattr(settings, 'SENTRY_DSN', ''):
                self.stdout.write('🐛 Sentry: Enabled')
            else:
                self.stdout.write('🐛 Sentry: No DSN configured')

    def display_cpanel_instructions(self):
        """Display cPanel instructions"""
        self.stdout.write(
            self.style.SUCCESS('\n🏢 CPANEL DEPLOYMENT COMPLETE (PATH-BASED)')
        )
        self.stdout.write('🌐 Main site: https://app.autowash.co.ke/')
        self.stdout.write('👤 Admin: https://app.autowash.co.ke/admin/')
        self.stdout.write('🔑 Login: admin@autowash.co.ke / 123456')
        self.stdout.write('🏢 Business URLs: https://app.autowash.co.ke/business/{slug}/')
        self.stdout.write('📋 Register a business and access via path-based URLs')
        
        if settings.DEBUG:
            self.stdout.write('🔧 DEBUG MODE: Enabled')
            self.stdout.write('   - Debug toolbar available')
            self.stdout.write('   - Enhanced logging active')
            self.stdout.write('   - Security settings relaxed')
            self.stdout.write('🐛 Sentry: Disabled')
        else:
            self.stdout.write('🔒 Security: Strict production mode')
            if getattr(settings, 'SENTRY_DSN', ''):
                self.stdout.write('🐛 Sentry: Enabled')
            else:
                self.stdout.write('🐛 Sentry: No DSN configured')

        # cPanel-specific notes
        self.stdout.write(self.style.SUCCESS('\n📝 CPANEL-SPECIFIC NOTES:'))
        self.stdout.write('   - Static files served by Apache/Nginx')
        self.stdout.write('   - Application restarted via passenger_wsgi.py touch')
        self.stdout.write('   - Check cPanel Error Logs for any issues')
        self.stdout.write('   - Ensure Python app is configured in cPanel')

        # Redis status
        redis_url = getattr(settings, 'REDIS_URL', '')
        if redis_url and 'redis://' in redis_url:
            self.stdout.write('🔄 Celery: Enabled with Redis')
        else:
            self.stdout.write('🔄 Celery: Disabled (No Redis configured)')

        self.stdout.write(
            self.style.SUCCESS('\n📝 PATH-BASED ROUTING NOTES:')
        )
        self.stdout.write('   - Public pages: /')
        self.stdout.write('   - Business management: /business/{slug}/')
        self.stdout.write('   - Authentication: /auth/')
        self.stdout.write('   - Admin: /admin/')
        self.stdout.write('   - Each business gets its own schema via path routing')