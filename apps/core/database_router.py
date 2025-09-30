"""
MySQL Database Router for Multi-Tenant Architecture
Routes database queries to appropriate tenant databases
"""
from django.conf import settings
from django.core.cache import cache
import threading


class TenantDatabaseRouter:
    """
    Database router for MySQL multi-tenant architecture
    Routes queries to appropriate tenant databases based on current tenant
    """
    
    # Thread-local storage for current tenant
    _local = threading.local()
    
    @classmethod
    def set_tenant(cls, tenant):
        """Set the current tenant for this thread"""
        cls._local.tenant = tenant
        
        # Lightweight tenant config caching for performance
        # Uses the new optimized cache system that prevents template staleness
        if tenant:
            try:
                # Handle both Tenant objects and BusinessContext objects
                database_config = None
                if hasattr(tenant, 'database_config'):
                    database_config = tenant.database_config
                elif hasattr(tenant, 'id'):
                    # If it's a BusinessContext, get the full Tenant object
                    from apps.core.tenant_models import Tenant
                    full_tenant = Tenant.objects.using('default').get(id=tenant.id)
                    database_config = full_tenant.database_config
                
                if database_config:
                    # Use optimized cache system with very short timeout to prevent staleness
                    from django.core.cache import caches
                    main_cache = caches['default']
                    cache_key = f"tenant_db_{tenant.id}"
                    
                    # Cache for only 30 seconds to ensure fresh data
                    try:
                        main_cache.set(cache_key, database_config, 30)
                        # Removed debug print to reduce log noise
                    except Exception:
                        # Silent fail - caching is not critical for functionality
                        pass
                        
            except Exception:
                # Silent fail - tenant setup should work without caching
                pass
    
    @classmethod
    def get_tenant(cls):
        """Get the current tenant for this thread"""
        return getattr(cls._local, 'tenant', None)
    
    @classmethod
    def clear_tenant(cls):
        """Clear the current tenant for this thread"""
        cls._local.tenant = None
    
    def db_for_read(self, model, **hints):
        """Suggest the database to read from"""
        # Legacy: Cache table routing (not currently used but kept for compatibility)
        if hasattr(model._meta, 'db_table') and model._meta.db_table == 'django_cache_table':
            return 'default'
        
        # CRITICAL: Always use default database for sessions, auth, and accounts
        # This ensures users stay logged in when switching between main and tenant areas
        if model._meta.app_label in ['sessions', 'auth', 'accounts']:
            return 'default'
        
        # Always use default for public/shared models
        if self._is_public_model(model):
            return 'default'
        
        # Use tenant database for tenant-specific models
        tenant = self.get_tenant()
        if tenant:
            return f"tenant_{tenant.id}"
        
        # Fallback to default if no tenant is set
        return 'default'
    
    def db_for_write(self, model, **hints):
        """Suggest the database to write to"""
        # Legacy: Cache table routing (not currently used but kept for compatibility)
        if hasattr(model._meta, 'db_table') and model._meta.db_table == 'django_cache_table':
            return 'default'
        
        # CRITICAL: Always use default database for sessions, auth, and accounts
        # This ensures users stay logged in when switching between main and tenant areas
        if model._meta.app_label in ['sessions', 'auth', 'accounts']:
            return 'default'
        
        # Always use default for public/shared models
        if self._is_public_model(model):
            return 'default'
        
        # Use tenant database for tenant-specific models
        tenant = self.get_tenant()
        if tenant:
            return f"tenant_{tenant.id}"
        
        # Fallback to default if no tenant is set
        return 'default'
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Determine if migration should run on this database"""
        
        # CRITICAL: Cache table should ONLY exist in main database
        if getattr(hints.get('model'), '_meta', None):
            table_name = hints['model']._meta.db_table
            if table_name == 'django_cache_table':
                return db == 'default'
        
        # Special handling for core app - some models in shared, some in tenant
        if app_label == 'core':
            # TenantSettings goes to tenant databases only
            if model_name == 'tenantsettings':
                return db.startswith('tenant_')
            # All other core models go to shared database only
            else:
                return db == 'default'
        
        # Accounts app should only be in main database (user profiles, etc.)
        if app_label == 'accounts':
            return db == 'default'
        
        # Handle Django built-in apps that appear in both SHARED_APPS and TENANT_APPS
        # These need to exist in both databases (using Django's short app labels)
        django_builtin_apps = [
            'admin',                    # django.contrib.admin
            'auth',                     # django.contrib.auth
            'contenttypes',             # django.contrib.contenttypes
            'sessions',                 # django.contrib.sessions
            'messages',                 # django.contrib.messages
            'sites',                    # django.contrib.sites
            'account',                  # allauth.account
            'socialaccount',            # allauth.socialaccount
            'authtoken',                # rest_framework.authtoken
            'django_celery_beat',       # django_celery_beat
            'django_celery_results',    # django_celery_results
        ]
        
        if app_label in django_builtin_apps:
            # These apps migrate to both default and tenant databases
            return True
        
        # Map short app labels to full app names for comparison with settings
        tenant_only_apps = [
            'businesses', 'employees', 'customers', 'services', 
            'inventory', 'suppliers', 'payments', 'reports', 
            'expenses', 'notification'
        ]
        
        # Check if this is a tenant-only app
        if app_label in tenant_only_apps:
            return db.startswith('tenant_')
        
        # For full app name comparison with settings
        full_app_name = app_label
        if app_label.startswith('apps.'):
            full_app_name = app_label  # Already full name
        elif '.' not in app_label:
            # Try to map common Django apps to full names
            app_mapping = {
                'allauth': 'allauth',
            }
            full_app_name = app_mapping.get(app_label, app_label)
        
        # Apps that are only in SHARED_APPS go to default database only
        if full_app_name in settings.SHARED_APPS and full_app_name not in settings.TENANT_APPS:
            return db == 'default'
        
        # Apps that are only in TENANT_APPS go to tenant databases only
        if full_app_name in settings.TENANT_APPS and full_app_name not in settings.SHARED_APPS:
            return db.startswith('tenant_')
        
        # Apps that are in both (like allauth) go to both databases
        if full_app_name in settings.SHARED_APPS and full_app_name in settings.TENANT_APPS:
            return True
        
        # Default behavior for other apps - go to default database
        return db == 'default'
    
    def allow_relation(self, obj1, obj2, **hints):
        """Allow relations if objects are in the same database"""
        db_set = {'default'}
        
        # Add current tenant database if available
        tenant = self.get_tenant()
        if tenant:
            db_set.add(f"tenant_{tenant.id}")
        
        # Check if both objects are in allowed databases
        if obj1._state.db in db_set and obj2._state.db in db_set:
            return True
        
        return None
    
    def _is_public_model(self, model):
        """Check if model belongs to public/shared apps"""
        return model._meta.app_label in getattr(settings, 'SHARED_APPS', [])


class TenantDatabaseManager:
    """
    Manager for tenant database operations
    Handles creation and configuration of tenant databases
    """
    
    @staticmethod
    def create_tenant_database(tenant):
        """Create a new database for a tenant"""
        from django.db import connections
        from django.core.management import call_command
        import pymysql
        
        # Get default connection to create new database
        default_db = settings.DATABASES['default']
        
        try:
            print(f"Starting database creation for tenant: {tenant.name}")
            
            # Always use main database credentials for simplicity and reliability
            tenant.database_user = default_db['USER']
            tenant.database_password = default_db['PASSWORD']
            tenant.save()
            print(f"Updated tenant to use main database credentials")
            
            # Connect to MySQL server (without database name to create it)
            connection = pymysql.connect(
                host=tenant.database_host,
                user=default_db['USER'],
                password=default_db['PASSWORD'],
                port=tenant.database_port
            )
            
            cursor = connection.cursor()
            
            # Create database
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{tenant.database_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            print(f"Database {tenant.database_name} created successfully")
            
            cursor.close()
            connection.close()
            
            # Add tenant database to settings
            print(f"Adding tenant database to settings...")
            TenantDatabaseManager.add_tenant_to_settings(tenant)
            print(f"Tenant database added to settings successfully")
            
            # Run migrations for tenant database
            print(f"Running migrations for tenant database...")
            try:
                call_command('migrate', database=f"tenant_{tenant.id}", verbosity=1)
                print(f"Migrations completed successfully")
            except Exception as migration_error:
                print(f"Migration error: {migration_error}")
                # Try to re-add to settings and retry
                TenantDatabaseManager.add_tenant_to_settings(tenant)
                call_command('migrate', database=f"tenant_{tenant.id}", verbosity=1)
                print(f"Migrations completed successfully on retry")
            
            return True
            
        except Exception as e:
            print(f"Error creating database for tenant {tenant.name}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    @staticmethod
    def add_tenant_to_settings(tenant):
        """Add tenant database configuration to Django settings using unified config approach"""
        from apps.core.config_utils import ConfigManager
        
        db_alias = f"tenant_{tenant.id}"
        
        # Don't add if already exists
        if db_alias in settings.DATABASES:
            return
        
        # Use unified config approach for consistency
        db_config = ConfigManager.get_db_config(
            name=tenant.database_name,
            user=tenant.database_user,
            password=tenant.database_password,
            host=tenant.database_host,
            port=tenant.database_port
        )
        
        settings.DATABASES[db_alias] = db_config
        
        # Update connections registry if available
        from django.db import connections
        if hasattr(connections, '_databases'):
            connections._databases = settings.DATABASES
    
    @staticmethod
    def remove_tenant_database(tenant):
        """Remove tenant database (use with caution!)"""
        from django.db import connections
        import pymysql
        
        default_db = settings.DATABASES['default']
        
        try:
            # Connect to MySQL server
            connection = pymysql.connect(
                host=tenant.database_host,
                user=default_db['USER'],
                password=default_db['PASSWORD'],
                port=tenant.database_port
            )
            
            cursor = connection.cursor()
            
            # Drop database
            cursor.execute(f"DROP DATABASE IF EXISTS `{tenant.database_name}`")
            
            # Drop user if different from default
            if tenant.database_user != default_db['USER']:
                cursor.execute(f"DROP USER IF EXISTS '{tenant.database_user}'@'%'")
            
            cursor.close()
            connection.close()
            
            # Remove from Django settings
            db_alias = f"tenant_{tenant.id}"
            if db_alias in settings.DATABASES:
                del settings.DATABASES[db_alias]
            
            return True
            
        except Exception as e:
            print(f"Error removing database for tenant {tenant.name}: {e}")
            return False
    
    @staticmethod
    def database_exists(database_name):
        """Check if a database exists"""
        import pymysql
        
        default_db = settings.DATABASES['default']
        
        try:
            # Connect to MySQL server
            connection = pymysql.connect(
                host=default_db['HOST'],
                user=default_db['USER'],
                password=default_db['PASSWORD'],
                port=int(default_db.get('PORT', 3306))
            )
            
            cursor = connection.cursor()
            
            # Check if database exists
            cursor.execute("SHOW DATABASES LIKE %s", (database_name,))
            result = cursor.fetchone()
            
            cursor.close()
            connection.close()
            
            return bool(result)
            
        except Exception as e:
            print(f"Error checking database existence for {database_name}: {e}")
            return False


# Utility functions for tenant context management
def tenant_context(tenant):
    """Context manager for tenant operations"""
    class TenantContext:
        def __init__(self, tenant):
            self.tenant = tenant
            self.previous_tenant = None
            self.db_alias = f"tenant_{tenant.id}"
            self.db_added = False
        
        def __enter__(self):
            from django.db import connections
            from django.conf import settings
            
            self.previous_tenant = TenantDatabaseRouter.get_tenant()
            TenantDatabaseRouter.set_tenant(self.tenant)
            
            # Add tenant database to Django settings if not already present
            if self.db_alias not in settings.DATABASES:
                settings.DATABASES[self.db_alias] = self.tenant.database_config
                self.db_added = True
                
                # Ensure the connection object is aware of the new database
                if hasattr(connections, '_databases'):
                    connections._databases = settings.DATABASES
            
            return self.tenant
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            from django.db import connections
            from django.conf import settings
            
            # Clean up: remove the database setting if we added it
            if self.db_added and self.db_alias in settings.DATABASES:
                del settings.DATABASES[self.db_alias]
                
                # Update connections object
                if hasattr(connections, '_databases'):
                    connections._databases = settings.DATABASES
            
            TenantDatabaseRouter.set_tenant(self.previous_tenant)
    
    return TenantContext(tenant)


def get_current_tenant():
    """Get the current tenant from router"""
    return TenantDatabaseRouter.get_tenant()


def set_current_tenant(tenant):
    """Set the current tenant in router"""
    TenantDatabaseRouter.set_tenant(tenant)
