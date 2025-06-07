# autowash/routers.py

class SessionRouter:
    """
    A router to control database operations for session models.
    Forces all session operations to use the public schema.
    """
    
    session_app_labels = {'sessions'}
    
    def db_for_read(self, model, **hints):
        """Suggest the database to read from."""
        if model._meta.app_label in self.session_app_labels:
            # Force sessions to always use public schema
            from django.db import connection
            from django_tenants.utils import get_public_schema_name
            
            # Temporarily switch to public schema for session operations
            if hasattr(connection, 'set_schema_to_public'):
                connection.set_schema_to_public()
            
            return 'default'
        return None
    
    def db_for_write(self, model, **hints):
        """Suggest the database to write to."""
        if model._meta.app_label in self.session_app_labels:
            # Force sessions to always use public schema
            from django.db import connection
            from django_tenants.utils import get_public_schema_name
            
            # Temporarily switch to public schema for session operations
            if hasattr(connection, 'set_schema_to_public'):
                connection.set_schema_to_public()
                
            return 'default'
        return None
    
    def allow_relation(self, obj1, obj2, **hints):
        """Allow relations if models are in the session app."""
        db_set = {'default'}
        if obj1._state.db in db_set and obj2._state.db in db_set:
            return True
        return None
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Ensure that session models get created on the right database."""
        if app_label in self.session_app_labels:
            # Sessions should be created in public schema only
            return db == 'default'
        elif db == 'sessions':
            # Prevent other apps from migrating to session db
            return False
        return None