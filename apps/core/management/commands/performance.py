from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.db import connection
from django.conf import settings


class Command(BaseCommand):
    help = 'Optimize system performance'

    def add_arguments(self, parser):
        parser.add_argument('--cache-table', action='store_true', help='Create cache table')
        parser.add_argument('--warm-cache', action='store_true', help='Warm up cache')
        parser.add_argument('--status', action='store_true', help='Show performance status')

    def handle(self, *args, **options):
        if options['cache_table']:
            self.create_cache_table()
        elif options['warm_cache']:
            self.warm_cache()
        elif options['status']:
            self.show_status()
        else:
            self.stdout.write('Use --cache-table, --warm-cache, or --status')

    def create_cache_table(self):
        try:
            from django.core.management import call_command
            call_command('createcachetable')
            self.stdout.write(self.style.SUCCESS('✓ Cache table created'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Failed: {e}'))

    def warm_cache(self):
        cache.set('static_v', str(int(__import__('time').time() / 10)), 10)  # Real-time: 10 seconds
        self.stdout.write(self.style.SUCCESS('✓ Cache warmed'))

    def show_status(self):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SHOW STATUS LIKE 'Threads_connected'")
                result = cursor.fetchone()
                threads = result[1] if result else 0
        except Exception:
            threads = 'Unknown'
        
        cache_status = 'Active' if cache.get('static_v') else 'Cold'
        
        self.stdout.write(f'DB Connections: {threads}')
        self.stdout.write(f'Cache Status: {cache_status}')
        self.stdout.write(f'Environment: {"cPanel" if settings.CPANEL else "Dev"}')
        self.stdout.write(f'Cache Backend: {settings.CACHES["default"]["BACKEND"].split(".")[-1]}')