from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    
    def ready(self):
        import apps.core.signals  # Register signal handlers
        
        # Auto-register tenant databases on startup
        self.register_tenant_databases()
    
    def register_tenant_databases(self):
        """Automatically register all tenant databases on Django startup"""
        try:
            # Import here to avoid circular imports
            from apps.core.tenant_models import Tenant
            from apps.core.database_router import TenantDatabaseManager
            from django.db import connection
            from django.conf import settings
            
            # Check if we can connect to the default database
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            
            # Get all approved tenants and register their databases
            tenants = Tenant.objects.filter(is_approved=True, is_active=True)
            
            for tenant in tenants:
                try:
                    db_alias = f"tenant_{tenant.id}"
                    if db_alias not in settings.DATABASES:
                        TenantDatabaseManager.add_tenant_to_settings(tenant)
                        print(f"Registered tenant database: {tenant.name}")
                except Exception as e:
                    print(f"Failed to register tenant database for {tenant.name}: {e}")
                    
        except Exception as e:
            # Silently fail if database is not ready yet (during migrations, etc.)
            pass
