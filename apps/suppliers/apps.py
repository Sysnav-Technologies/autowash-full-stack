from django.apps import AppConfig

class SuppliersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.suppliers'
    verbose_name = 'Suppliers & Procurement'
    
    def ready(self):
        # Import signals
        try:
            import apps.suppliers.signals
        except ImportError:
            pass