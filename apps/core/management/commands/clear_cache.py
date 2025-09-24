"""
Django management command to clear file-based cache and sessions
Useful for immediate cache clearing in production
"""
import os
import shutil
from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.conf import settings


class Command(BaseCommand):
    help = 'Clear file-based cache and sessions for immediate updates'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--cache-only',
            action='store_true',
            help='Clear only cache, not sessions',
        )
        parser.add_argument(
            '--sessions-only',
            action='store_true',
            help='Clear only sessions, not cache',
        )
    
    def handle(self, *args, **options):
        cleared_items = []
        
        # Clear cache
        if not options['sessions_only']:
            try:
                cache.clear()
                self.stdout.write(
                    self.style.SUCCESS('✓ Cache cleared successfully')
                )
                cleared_items.append('cache')
                
                # Also manually clear cache directory
                cache_location = getattr(settings, 'CACHES', {}).get('default', {}).get('LOCATION')
                if cache_location and os.path.exists(cache_location):
                    # Remove cache files but keep directory
                    for filename in os.listdir(cache_location):
                        if filename.startswith('.'):  # Skip hidden files
                            continue
                        file_path = os.path.join(cache_location, filename)
                        try:
                            if os.path.isfile(file_path):
                                os.remove(file_path)
                            elif os.path.isdir(file_path) and filename == 'sessions':
                                continue  # Don't delete sessions directory here
                            elif os.path.isdir(file_path):
                                shutil.rmtree(file_path)
                        except Exception as e:
                            self.stdout.write(
                                self.style.WARNING(f'Could not remove {file_path}: {e}')
                            )
                    
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Cache directory cleaned: {cache_location}')
                    )
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Failed to clear cache: {e}')
                )
        
        # Clear sessions
        if not options['cache_only']:
            try:
                session_path = getattr(settings, 'SESSION_FILE_PATH', None)
                if session_path and os.path.exists(session_path):
                    # Remove session files but keep directory
                    session_count = 0
                    for filename in os.listdir(session_path):
                        file_path = os.path.join(session_path, filename)
                        try:
                            if os.path.isfile(file_path):
                                os.remove(file_path)
                                session_count += 1
                        except Exception as e:
                            self.stdout.write(
                                self.style.WARNING(f'Could not remove session {file_path}: {e}')
                            )
                    
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Cleared {session_count} session files from {session_path}')
                    )
                    cleared_items.append('sessions')
                else:
                    self.stdout.write(
                        self.style.WARNING('Session directory not found or sessions not file-based')
                    )
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Failed to clear sessions: {e}')
                )
        
        if cleared_items:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n🎉 Production cache optimization complete!'
                    f'\nCleared: {", ".join(cleared_items)}'
                    f'\nChanges should now reflect immediately in your application.'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING('No cache or sessions were cleared.')
            )