from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    
    def ready(self):
        import apps.core.signals  # Register signal handlers
        
        # Note: Tenant database registration is now handled lazily in middleware
        # to avoid accessing database during app initialization
