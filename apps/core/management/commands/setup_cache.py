from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import connection
from django.conf import settings


class Command(BaseCommand):
    help = 'Create cache table for database cache backend'

    def handle(self, *args, **options):
        cache_config = settings.CACHES.get('default', {})
        
        if 'DatabaseCache' not in cache_config.get('BACKEND', ''):
            self.stdout.write(
                self.style.WARNING('Database cache not configured. Skipping table creation.')
            )
            return
        
        try:
            call_command('createcachetable')
            self.stdout.write(
                self.style.SUCCESS('Successfully created cache table')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to create cache table: {e}')
            )