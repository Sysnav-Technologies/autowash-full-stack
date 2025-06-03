from django.apps import AppConfig

class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.notification'
    verbose_name = 'Notifications & Messaging'
    
    def ready(self):
        # Import signals
        try:
            import signals
        except ImportError:
            pass
        
        # Create default templates and categories
        self.create_defaults()
    
    def create_defaults(self):
        """Create default notification templates and categories"""
        try:
            from .utils import NotificationTemplateManager
            manager = NotificationTemplateManager()
            manager.create_default_categories()
            manager.create_default_templates()
        except Exception:
            # Fail silently during migrations
            pass