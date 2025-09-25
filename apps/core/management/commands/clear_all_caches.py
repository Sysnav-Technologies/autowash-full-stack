"""
Django management command to clear all caches and force immediate template refresh
"""
from django.core.management.base import BaseCommand
from django.core.cache import cache, caches
from django.conf import settings
import shutil
import os


class Command(BaseCommand):
    help = 'Clear all caches to ensure immediate template refresh and system responsiveness'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force clear all cache directories and files',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting cache cleanup...'))
        
        # Clear Django's default cache
        try:
            cache.clear()
            self.stdout.write(self.style.SUCCESS('✓ Default cache cleared'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Warning: Could not clear default cache: {e}'))
        
        # Clear all configured caches
        for cache_name in settings.CACHES.keys():
            try:
                caches[cache_name].clear()
                self.stdout.write(self.style.SUCCESS(f'✓ Cache "{cache_name}" cleared'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Warning: Could not clear cache "{cache_name}": {e}'))
        
        # Clear file-based cache directories if they exist
        cache_dirs = [
            settings.BASE_DIR / 'cache',
            settings.BASE_DIR / 'tmp',
            settings.BASE_DIR / 'cache' / 'sessions',
            settings.BASE_DIR / 'cache' / 'persistent',
        ]
        
        for cache_dir in cache_dirs:
            if options['force'] and cache_dir.exists():
                try:
                    shutil.rmtree(cache_dir)
                    self.stdout.write(self.style.SUCCESS(f'✓ Cache directory removed: {cache_dir}'))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'Warning: Could not remove {cache_dir}: {e}'))
        
        # Clear sessions to force fresh user sessions
        try:
            from django.contrib.sessions.models import Session
            Session.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('✓ All sessions cleared'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Warning: Could not clear sessions: {e}'))
        
        self.stdout.write(
            self.style.SUCCESS(
                '\n🎉 Cache cleanup complete! Templates should now refresh immediately.\n'
                'Please restart your development server for full effect.'
            )
        )