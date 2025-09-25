from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    
    def ready(self):
        import apps.core.signals  # Register signal handlers
        
        # Simple logging - system ready
        print("AutoWash Cache System: Optimized Fast Cache (Template Responsive)")
        print("AutoWash Core System: READY")
        
        # Note: Tenant database registration is now handled lazily in middleware
        # to avoid accessing database during app initialization
