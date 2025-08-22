"""
Django management command to reset the application for cPanel deployment
"""
from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.core.management import call_command
from django.conf import settings
import os
import shutil

# Command to reset the application for cPanel deployment
class Command(BaseCommand):
    help = 'Reset Django application for cPanel deployment - clears cache, creates tables, and prepares for production'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear-cache',
            action='store_true',
            help='Clear application cache',
        )
        parser.add_argument(
            '--create-cache-table',
            action='store_true',
            help='Create cache table',
        )
        parser.add_argument(
            '--collect-static',
            action='store_true',
            help='Collect static files',
        )
        parser.add_argument(
            '--migrate',
            action='store_true',
            help='Run database migrations',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Run all reset operations',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Starting cPanel Application Reset')
        )
        self.stdout.write('=' * 50)

        # If --all is specified, enable all operations
        if options['all']:
            options['clear_cache'] = True
            options['create_cache_table'] = True
            options['collect_static'] = True
            options['migrate'] = True

        # If no specific options, run all operations
        if not any([
            options['clear_cache'],
            options['create_cache_table'], 
            options['collect_static'],
            options['migrate']
        ]):
            options['clear_cache'] = True
            options['create_cache_table'] = True
            options['collect_static'] = True
            options['migrate'] = True

        success_count = 0
        total_operations = 0

        # Clear Python bytecode cache
        self.stdout.write('🧹 Clearing Python bytecode cache...')
        try:
            self.clear_python_cache()
            self.stdout.write(
                self.style.SUCCESS('   ✅ Python cache cleared')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'   ❌ Python cache clear failed: {e}')
            )

        # Clear application cache
        if options['clear_cache']:
            total_operations += 1
            self.stdout.write('🗑️  Clearing application cache...')
            try:
                cache.clear()
                self.stdout.write(
                    self.style.SUCCESS('   ✅ Application cache cleared')
                )
                success_count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'   ❌ Cache clear failed: {e}')
                )

        # Create cache table
        if options['create_cache_table']:
            total_operations += 1
            self.stdout.write('🗄️  Creating cache table...')
            try:
                call_command('createcachetable', verbosity=0)
                self.stdout.write(
                    self.style.SUCCESS('   ✅ Cache table created/verified')
                )
                success_count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'   ❌ Cache table creation failed: {e}')
                )

        # Run migrations
        if options['migrate']:
            total_operations += 1
            self.stdout.write('🔄 Running database migrations...')
            try:
                call_command('migrate', verbosity=1)
                self.stdout.write(
                    self.style.SUCCESS('   ✅ Database migrations complete')
                )
                success_count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'   ❌ Migrations failed: {e}')
                )

        # Collect static files
        if options['collect_static']:
            total_operations += 1
            self.stdout.write('📁 Collecting static files...')
            try:
                call_command('collectstatic', interactive=False, verbosity=0)
                self.stdout.write(
                    self.style.SUCCESS('   ✅ Static files collected')
                )
                success_count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'   ❌ Static files collection failed: {e}')
                )

        # Display summary
        self.stdout.write('=' * 50)
        if success_count == total_operations:
            self.stdout.write(
                self.style.SUCCESS(f'🎉 Reset complete! ({success_count}/{total_operations} operations successful)')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'⚠️  Reset completed with issues ({success_count}/{total_operations} operations successful)')
            )

        # Display next steps
        self.stdout.write('\n📋 Next steps for cPanel:')
        self.stdout.write('1. Restart your Django application:')
        self.stdout.write('   - Passenger: touch tmp/restart.txt')
        self.stdout.write('   - Or: touch passenger_wsgi.py')
        self.stdout.write('   - Supervisor: supervisorctl restart your_app')
        self.stdout.write('2. Check error logs for any remaining issues')
        self.stdout.write('3. Test M-Pesa payments and core functionality')

        # Display configuration info
        self.stdout.write('\n⚙️  Current Configuration:')
        self.stdout.write(f'   Debug Mode: {settings.DEBUG}')
        self.stdout.write(f'   Cache Backend: {settings.CACHES["default"]["BACKEND"]}')
        if hasattr(settings, 'MPESA_ENVIRONMENT'):
            self.stdout.write(f'   M-Pesa Environment: {settings.MPESA_ENVIRONMENT}')

    def clear_python_cache(self):
        """Clear Python bytecode cache files"""
        cache_dirs_removed = 0
        pyc_files_removed = 0
        
        for root, dirs, files in os.walk('.'):
            # Remove __pycache__ directories
            if '__pycache__' in dirs:
                pycache_path = os.path.join(root, '__pycache__')
                try:
                    shutil.rmtree(pycache_path)
                    cache_dirs_removed += 1
                except (OSError, PermissionError):
                    pass  # Skip if can't remove
            
            # Remove .pyc files
            for file in files:
                if file.endswith('.pyc'):
                    pyc_path = os.path.join(root, file)
                    try:
                        os.remove(pyc_path)
                        pyc_files_removed += 1
                    except (OSError, PermissionError):
                        pass  # Skip if can't remove
        
        if cache_dirs_removed > 0 or pyc_files_removed > 0:
            self.stdout.write(f'   Removed {cache_dirs_removed} cache directories and {pyc_files_removed} .pyc files')
