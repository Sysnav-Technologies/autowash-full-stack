"""
Cache Management Command for AutoWash Multi-Tenant System
=========================================================

Django management command for cache operations including:
- Cache clearing and warming
- Tenant-specific cache management  
- Cache statistics and health checks
- Static file versioning for browser cache invalidation

Usage Examples:
  python manage.py cache_manager --clear-all
  python manage.py cache_manager --clear-tenant=public
  python manage.py cache_manager --warm-cache
  python manage.py cache_manager --stats
  python manage.py cache_manager --update-static-version
  python manage.py cache_manager --health-check
"""

from django.core.management.base import BaseCommand, CommandError
from django.core.cache import cache
from django.conf import settings
from django.db import connection
from django.contrib.staticfiles import finders
from django.contrib.staticfiles.storage import staticfiles_storage
import os
import time
import hashlib
import json
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Manage cache system for AutoWash multi-tenant application'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear-all',
            action='store_true',
            help='Clear all cache entries across all tenants',
        )
        
        parser.add_argument(
            '--clear-tenant',
            type=str,
            help='Clear cache for specific tenant (schema name)',
        )
        
        parser.add_argument(
            '--warm-cache',
            action='store_true',
            help='Pre-populate cache with frequently accessed data',
        )
        
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Display cache statistics and health information',
        )
        
        parser.add_argument(
            '--health-check',
            action='store_true',
            help='Perform comprehensive cache health check',
        )
        
        parser.add_argument(
            '--update-static-version',
            action='store_true',
            help='Update static file version for browser cache invalidation',
        )
        
        parser.add_argument(
            '--create-cache-table',
            action='store_true',
            help='Create database cache table if using database cache',
        )
        
        parser.add_argument(
            '--test-performance',
            action='store_true',
            help='Run cache performance tests',
        )

    def handle(self, *args, **options):
        """Main command handler"""
        
        if options['clear_all']:
            self.clear_all_cache()
        
        elif options['clear_tenant']:
            self.clear_tenant_cache(options['clear_tenant'])
        
        elif options['warm_cache']:
            self.warm_cache()
        
        elif options['stats']:
            self.show_cache_stats()
        
        elif options['health_check']:
            self.health_check()
        
        elif options['update_static_version']:
            self.update_static_version()
        
        elif options['create_cache_table']:
            self.create_cache_table()
        
        elif options['test_performance']:
            self.test_cache_performance()
        
        else:
            self.stdout.write(
                self.style.WARNING('No action specified. Use --help for available options.')
            )

    def clear_all_cache(self):
        """Clear all cache entries"""
        self.stdout.write('Clearing all cache entries...')
        
        try:
            cache.clear()
            
            # If using hybrid cache, try to clear tenant-specific method
            if hasattr(cache, 'clear_tenant_cache'):
                self.stdout.write('Clearing tenant-aware cache...')
            
            self.stdout.write(
                self.style.SUCCESS('✓ All cache entries cleared successfully')
            )
            
        except Exception as e:
            raise CommandError(f'Failed to clear cache: {e}')

    def clear_tenant_cache(self, tenant_schema):
        """Clear cache for specific tenant"""
        self.stdout.write(f'Clearing cache for tenant: {tenant_schema}')
        
        try:
            # Check if we have tenant-aware cache backend
            if hasattr(cache, 'clear_tenant_cache'):
                cache.clear_tenant_cache(tenant_schema)
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Cache cleared for tenant: {tenant_schema}')
                )
            else:
                # Fallback: clear keys with tenant prefix
                from apps.core.cache_utils import TenantCache
                tenant_cache = TenantCache()
                
                # This is a simplified approach - in production you might want
                # more sophisticated pattern-based clearing
                self.stdout.write(
                    self.style.WARNING(
                        f'Cache backend does not support tenant-specific clearing. '
                        f'Consider upgrading to HybridCacheBackend.'
                    )
                )
                
        except Exception as e:
            raise CommandError(f'Failed to clear tenant cache: {e}')

    def warm_cache(self):
        """Pre-populate cache with frequently accessed data"""
        self.stdout.write('Warming cache with frequently accessed data...')
        
        try:
            from apps.core.cache_utils import TenantCache
            
            warmed_items = 0
            
            # Cache common business settings
            try:
                from apps.businesses.models import Business
                businesses = Business.objects.select_related().all()[:10]  # Top 10 businesses
                
                for business in businesses:
                    cache_key = f"business:settings:{business.pk}"
                    if not cache.get(cache_key):
                        # Cache business settings
                        settings_data = {
                            'name': business.name,
                            'timezone': getattr(business, 'timezone', 'UTC'),
                            'currency': getattr(business, 'currency', 'USD'),
                        }
                        cache.set(cache_key, settings_data, timeout=3600)  # 1 hour
                        warmed_items += 1
                        
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'Could not warm business cache: {e}')
                )
            
            # Cache service categories
            try:
                from apps.services.models import ServiceCategory
                categories = ServiceCategory.objects.all()
                
                cache_key = "services:categories:all"
                if not cache.get(cache_key):
                    categories_data = list(categories.values('id', 'name', 'description'))
                    cache.set(cache_key, categories_data, timeout=7200)  # 2 hours
                    warmed_items += 1
                    
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'Could not warm service categories cache: {e}')
                )
            
            # Cache system settings
            system_settings = {
                'version': getattr(settings, 'VERSION', '1.0.0'),
                'debug': settings.DEBUG,
                'static_url': settings.STATIC_URL,
            }
            cache.set('system:settings', system_settings, timeout=86400)  # 24 hours
            warmed_items += 1
            
            self.stdout.write(
                self.style.SUCCESS(f'✓ Cache warmed with {warmed_items} items')
            )
            
        except Exception as e:
            raise CommandError(f'Failed to warm cache: {e}')

    def show_cache_stats(self):
        """Display cache statistics"""
        self.stdout.write('Cache Statistics:')
        self.stdout.write('=' * 50)
        
        try:
            # Basic cache info
            cache_config = getattr(settings, 'CACHES', {}).get('default', {})
            backend = cache_config.get('BACKEND', 'Unknown')
            
            self.stdout.write(f'Backend: {backend}')
            
            # Test cache connectivity
            test_key = 'cache_test_' + str(int(time.time()))
            test_value = 'test_value'
            
            try:
                cache.set(test_key, test_value, timeout=10)
                retrieved_value = cache.get(test_key)
                cache.delete(test_key)
                
                if retrieved_value == test_value:
                    self.stdout.write(
                        self.style.SUCCESS('✓ Cache connectivity: OK')
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR('✗ Cache connectivity: FAILED (value mismatch)')
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Cache connectivity: FAILED ({e})')
                )
            
            # If using hybrid cache, get detailed stats
            if hasattr(cache, 'get_cache_stats'):
                stats = cache.get_cache_stats()
                self.stdout.write('\nDetailed Statistics:')
                self.stdout.write(f'Total Keys: {stats.get("total_keys", "Unknown")}')
                
                for backend_name, backend_stats in stats.get('backends', {}).items():
                    self.stdout.write(f'\n{backend_name.title()} Backend:')
                    if backend_stats.get('available'):
                        self.stdout.write(f'  Keys: {backend_stats.get("keys", "Unknown")}')
                        if 'error' in backend_stats:
                            self.stdout.write(f'  Error: {backend_stats["error"]}')
                    else:
                        self.stdout.write('  Status: Unavailable')
            
            # Database cache table info (if applicable)
            if 'database' in backend.lower() or 'db' in backend.lower():
                try:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT COUNT(*) FROM cache_table")
                        count = cursor.fetchone()[0]
                        self.stdout.write(f'Database cache entries: {count}')
                except Exception as e:
                    self.stdout.write(f'Database cache info unavailable: {e}')
            
        except Exception as e:
            raise CommandError(f'Failed to get cache stats: {e}')

    def health_check(self):
        """Perform comprehensive cache health check"""
        self.stdout.write('Cache Health Check:')
        self.stdout.write('=' * 50)
        
        issues_found = 0
        
        # Test basic cache operations
        operations_to_test = [
            ('set', lambda: cache.set('health_test', 'value', timeout=30)),
            ('get', lambda: cache.get('health_test')),
            ('delete', lambda: cache.delete('health_test')),
            ('has_key', lambda: cache.has_key('health_test')),
        ]
        
        for op_name, op_func in operations_to_test:
            try:
                result = op_func()
                self.stdout.write(
                    self.style.SUCCESS(f'✓ {op_name} operation: OK')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ {op_name} operation: FAILED ({e})')
                )
                issues_found += 1
        
        # Test tenant isolation (if available)
        try:
            from apps.core.cache_utils import TenantCache
            tenant_cache = TenantCache()
            
            # Test tenant key generation
            test_key = tenant_cache.get_key('test_key')
            if ':tenant:' in test_key or test_key.startswith('tenant:'):
                self.stdout.write(
                    self.style.SUCCESS('✓ Tenant isolation: OK')
                )
            else:
                self.stdout.write(
                    self.style.WARNING('? Tenant isolation: May not be working properly')
                )
                issues_found += 1
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Tenant isolation test: FAILED ({e})')
            )
            issues_found += 1
        
        # Performance test
        try:
            start_time = time.time()
            for i in range(100):
                cache.set(f'perf_test_{i}', f'value_{i}', timeout=60)
            
            mid_time = time.time()
            for i in range(100):
                cache.get(f'perf_test_{i}')
            
            end_time = time.time()
            
            # Cleanup
            for i in range(100):
                cache.delete(f'perf_test_{i}')
            
            set_time = (mid_time - start_time) * 1000  # Convert to ms
            get_time = (end_time - mid_time) * 1000
            
            self.stdout.write(f'Performance (100 ops):')
            self.stdout.write(f'  SET: {set_time:.2f}ms ({set_time/100:.2f}ms per op)')
            self.stdout.write(f'  GET: {get_time:.2f}ms ({get_time/100:.2f}ms per op)')
            
            if set_time > 1000 or get_time > 500:  # Arbitrary thresholds
                self.stdout.write(
                    self.style.WARNING('? Performance seems slow')
                )
                issues_found += 1
            else:
                self.stdout.write(
                    self.style.SUCCESS('✓ Performance: Acceptable')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Performance test: FAILED ({e})')
            )
            issues_found += 1
        
        # Summary
        self.stdout.write('\n' + '=' * 50)
        if issues_found == 0:
            self.stdout.write(
                self.style.SUCCESS(f'✓ Cache system is healthy!')
            )
        else:
            self.stdout.write(
                self.style.ERROR(f'✗ Found {issues_found} issues with cache system')
            )

    def update_static_version(self):
        """Update static file version for browser cache invalidation"""
        self.stdout.write('Updating static file version...')
        
        try:
            # Generate new version hash based on current timestamp and settings
            version_string = f"{time.time()}-{settings.SECRET_KEY[:10]}"
            new_version = hashlib.md5(version_string.encode()).hexdigest()[:12]
            
            # Store in cache for template access
            cache.set('static:version', new_version, timeout=None)  # Never expires
            
            # Also store in a file for persistence across cache clears
            version_file = os.path.join(settings.BASE_DIR, 'static', 'version.txt')
            try:
                os.makedirs(os.path.dirname(version_file), exist_ok=True)
                with open(version_file, 'w') as f:
                    f.write(new_version)
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'Could not write version file: {e}')
                )
            
            self.stdout.write(
                self.style.SUCCESS(f'✓ Static version updated to: {new_version}')
            )
            self.stdout.write(
                'Add ?v={{ static_version }} to your static file URLs in templates'
            )
            
        except Exception as e:
            raise CommandError(f'Failed to update static version: {e}')

    def create_cache_table(self):
        """Create database cache table if needed in the default database"""
        self.stdout.write('Creating database cache table in default database...')
        
        try:
            from django.core.management import call_command
            # Ensure cache table is created in the default database (main database)
            # This is critical for multi-tenant setup - cache is shared across tenants
            call_command('createcachetable', '--database=default')
            
            self.stdout.write(
                self.style.SUCCESS('✓ Database cache table created successfully in default database')
            )
            
        except Exception as e:
            raise CommandError(f'Failed to create cache table: {e}')

    def test_cache_performance(self):
        """Run comprehensive cache performance tests"""
        self.stdout.write('Running cache performance tests...')
        self.stdout.write('=' * 50)
        
        test_sizes = [
            ('Small (1KB)', 'x' * 1024),
            ('Medium (10KB)', 'x' * (10 * 1024)),
            ('Large (100KB)', 'x' * (100 * 1024)),
        ]
        
        test_counts = [10, 100, 1000]
        
        for size_name, test_data in test_sizes:
            self.stdout.write(f'\nTesting {size_name} objects:')
            
            for count in test_counts:
                # SET test
                start_time = time.time()
                for i in range(count):
                    cache.set(f'perf_{size_name}_{i}', test_data, timeout=300)
                set_duration = time.time() - start_time
                
                # GET test
                start_time = time.time()
                for i in range(count):
                    cache.get(f'perf_{size_name}_{i}')
                get_duration = time.time() - start_time
                
                # Cleanup
                for i in range(count):
                    cache.delete(f'perf_{size_name}_{i}')
                
                self.stdout.write(
                    f'  {count:4d} ops: SET {set_duration*1000:6.1f}ms '
                    f'({set_duration*1000/count:5.2f}ms/op), '
                    f'GET {get_duration*1000:6.1f}ms '
                    f'({get_duration*1000/count:5.2f}ms/op)'
                )
        
        self.stdout.write(
            self.style.SUCCESS('\n✓ Performance tests completed')
        )