"""
Django management command to reset application cache and clear issues
"""
from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.core.management import call_command
import os
import shutil


class Command(BaseCommand):
    help = 'Reset Django application - clear cache and fix common issues'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check-config',
            action='store_true',
            help='Check Django configuration after reset',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🔄 Starting Application Reset')
        )
        self.stdout.write('=' * 40)

        operations = [
            ('🧹 Clearing Python cache', self.clear_python_cache),
            ('🗑️  Clearing Django cache', self.clear_django_cache),
            ('🗄️  Creating cache table', self.create_cache_table),
        ]

        success_count = 0
        for description, operation in operations:
            self.stdout.write(description + '...')
            try:
                result = operation()
                if result:
                    self.stdout.write(f'   ✅ {result}')
                else:
                    self.stdout.write('   ✅ Complete')
                success_count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'   ❌ Failed: {e}')
                )

        # Check configuration if requested
        if options['check_config']:
            self.stdout.write('⚙️  Checking Django configuration...')
            try:
                call_command('check', verbosity=0)
                self.stdout.write(
                    self.style.SUCCESS('   ✅ Configuration is valid')
                )
                success_count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'   ❌ Configuration issues: {e}')
                )

        # Summary
        self.stdout.write('=' * 40)
        if success_count == len(operations):
            self.stdout.write(
                self.style.SUCCESS('🎉 Reset complete!')
            )
        else:
            self.stdout.write(
                self.style.WARNING('⚠️  Reset completed with some issues')
            )

        self.stdout.write('\n💡 Tip: Restart your development server to ensure all changes take effect')

    def clear_python_cache(self):
        """Clear Python bytecode cache"""
        cache_dirs = 0
        pyc_files = 0
        
        for root, dirs, files in os.walk('.'):
            if '__pycache__' in dirs:
                pycache_path = os.path.join(root, '__pycache__')
                try:
                    shutil.rmtree(pycache_path)
                    cache_dirs += 1
                except:
                    pass
            
            for file in files:
                if file.endswith('.pyc'):
                    try:
                        os.remove(os.path.join(root, file))
                        pyc_files += 1
                    except:
                        pass
        
        return f"Removed {cache_dirs} cache dirs, {pyc_files} .pyc files"

    def clear_django_cache(self):
        """Clear Django application cache"""
        cache.clear()
        return "Django cache cleared"

    def create_cache_table(self):
        """Create cache table"""
        call_command('createcachetable', verbosity=0)
        return "Cache table verified/created"
