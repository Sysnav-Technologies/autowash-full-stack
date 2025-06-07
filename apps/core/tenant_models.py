# apps/core/tenant_models.py
from django.db import models
from django.utils import timezone
import uuid

class TenantTimeStampedModel(models.Model):
    """
    TimeStamped model for tenant schemas that avoids cross-schema FK constraints
    Uses integer fields to store user IDs instead of foreign keys
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Store user IDs instead of FK relationships to avoid cross-schema constraints
    created_by_user_id = models.IntegerField(null=True, blank=True)
    updated_by_user_id = models.IntegerField(null=True, blank=True)

    class Meta:
        abstract = True

    def set_created_by(self, user):
        """Set the created_by user ID"""
        if user and user.id:
            self.created_by_user_id = user.id

    def set_updated_by(self, user):
        """Set the updated_by user ID"""
        if user and user.id:
            self.updated_by_user_id = user.id

    @property
    def created_by(self):
        """Get the User object from public schema (read-only)"""
        if not self.created_by_user_id:
            return None
        try:
            from django.contrib.auth.models import User
            from django_tenants.utils import schema_context, get_public_schema_name
            with schema_context(get_public_schema_name()):
                return User.objects.get(id=self.created_by_user_id)
        except:
            return None

    @property
    def updated_by(self):
        """Get the User object from public schema (read-only)"""
        if not self.updated_by_user_id:
            return None
        try:
            from django.contrib.auth.models import User
            from django_tenants.utils import schema_context, get_public_schema_name
            with schema_context(get_public_schema_name()):
                return User.objects.get(id=self.updated_by_user_id)
        except:
            return None

class TenantSoftDeleteManager(models.Manager):
    """Manager that excludes soft-deleted objects by default"""
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

class TenantSoftDeleteModel(TenantTimeStampedModel):
    """Soft delete model for tenant schemas"""
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by_user_id = models.IntegerField(null=True, blank=True)

    objects = TenantSoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False, user=None):
        """Soft delete the object"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        if user and user.id:
            self.deleted_by_user_id = user.id
        self.save(using=using)

    def hard_delete(self, using=None, keep_parents=False):
        """Permanently delete the object"""
        super().delete(using=using, keep_parents=keep_parents)

    def restore(self, user=None):
        """Restore a soft-deleted object"""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by_user_id = None
        if user and user.id:
            self.updated_by_user_id = user.id
        self.save()

    def set_deleted_by(self, user):
        """Set the deleted_by user ID"""
        if user and user.id:
            self.deleted_by_user_id = user.id

    @property
    def deleted_by(self):
        """Get the User object from public schema (read-only)"""
        if not self.deleted_by_user_id:
            return None
        try:
            from django.contrib.auth.models import User
            from django_tenants.utils import schema_context, get_public_schema_name
            with schema_context(get_public_schema_name()):
                return User.objects.get(id=self.deleted_by_user_id)
        except:
            return None