from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django_tenants.utils import schema_context, get_public_schema_name
import uuid
from phonenumber_field.modelfields import PhoneNumberField

class TimeStampedModel(models.Model):
    """Abstract base model with created and updated timestamps - FIXED for cross-schema"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # FIXED: Use integer IDs instead of foreign keys for cross-schema compatibility
    created_by_id = models.IntegerField(null=True, blank=True, help_text="User ID from public schema")
    updated_by_id = models.IntegerField(null=True, blank=True, help_text="User ID from public schema")

    class Meta:
        abstract = True
    
    @property
    def created_by(self):
        """Get the user who created this object from public schema"""
        if not self.created_by_id:
            return None
        try:
            with schema_context(get_public_schema_name()):
                return User.objects.get(id=self.created_by_id)
        except User.DoesNotExist:
            return None
    
    @created_by.setter
    def created_by(self, user):
        """Set the user who created this object"""
        if user:
            self.created_by_id = user.id
        else:
            self.created_by_id = None
    
    @property
    def updated_by(self):
        """Get the user who last updated this object from public schema"""
        if not self.updated_by_id:
            return None
        try:
            with schema_context(get_public_schema_name()):
                return User.objects.get(id=self.updated_by_id)
        except User.DoesNotExist:
            return None
    
    @updated_by.setter
    def updated_by(self, user):
        """Set the user who updated this object"""
        if user:
            self.updated_by_id = user.id
        else:
            self.updated_by_id = None


class SoftDeleteManager(models.Manager):
    """Manager that excludes soft-deleted objects by default"""
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class SoftDeleteModel(TimeStampedModel):
    """Abstract model with soft delete functionality - FIXED for cross-schema"""
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    # FIXED: Use integer ID instead of foreign key for cross-schema compatibility
    deleted_by_id = models.IntegerField(null=True, blank=True, help_text="User ID from public schema")

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True
    
    @property
    def deleted_by(self):
        """Get the user who deleted this object from public schema"""
        if not self.deleted_by_id:
            return None
        try:
            with schema_context(get_public_schema_name()):
                return User.objects.get(id=self.deleted_by_id)
        except User.DoesNotExist:
            return None
    
    @deleted_by.setter
    def deleted_by(self, user):
        """Set the user who deleted this object"""
        if user:
            self.deleted_by_id = user.id
        else:
            self.deleted_by_id = None

    def delete(self, using=None, keep_parents=False, user=None):
        """Soft delete the object"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        if user:
            self.deleted_by_id = user.id
        self.save(using=using)

    def hard_delete(self, using=None, keep_parents=False):
        """Permanently delete the object"""
        super().delete(using=using, keep_parents=keep_parents)

    def restore(self, user=None):
        """Restore a soft-deleted object"""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by_id = None
        if user:
            self.updated_by_id = user.id
        self.save()


class Address(models.Model):
    """Mixin for address fields"""
    street_address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default='Kenya')

    class Meta:
        abstract = True


class ContactInfo(models.Model):
    """Mixin for contact information"""
    email = models.EmailField(blank=True)
    phone = PhoneNumberField(blank=True, null=True)

    class Meta:
        abstract = True