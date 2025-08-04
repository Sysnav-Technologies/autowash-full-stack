from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid
from phonenumber_field.modelfields import PhoneNumberField

class TimeStampedModel(models.Model):
    """Abstract base model with created and updated timestamps"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Use integer IDs for cross-database compatibility
    created_by_id = models.IntegerField(null=True, blank=True, help_text="User ID from main database")
    updated_by_id = models.IntegerField(null=True, blank=True, help_text="User ID from main database")

    class Meta:
        abstract = True
    
    def set_created_by(self, user):
        """Set the user who created this object"""
        if user:
            self.created_by_id = user.id
        else:
            self.created_by_id = None
    
    def set_updated_by(self, user):
        """Set the user who last updated this object"""
        if user:
            self.updated_by_id = user.id
        else:
            self.updated_by_id = None


class SoftDeleteManager(models.Manager):
    """Manager that excludes soft-deleted objects by default"""
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class SoftDeleteModel(TimeStampedModel):
    """Abstract model with soft delete functionality"""
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by_id = models.IntegerField(null=True, blank=True, help_text="User ID from main database")

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

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

    def set_deleted_by(self, user):
        """Set the user who deleted this object"""
        if user:
            self.deleted_by_id = user.id
        else:
            self.deleted_by_id = None


class Address(models.Model):
    """Abstract model for address information"""
    address_line_1 = models.CharField(max_length=255, blank=True)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=2, default='KE', help_text="ISO country code")

    class Meta:
        abstract = True

    @property
    def full_address(self):
        """Get formatted full address"""
        parts = [
            self.address_line_1,
            self.address_line_2,
            self.city,
            self.state,
            self.postal_code,
        ]
        return ', '.join(filter(None, parts))


class ContactInfo(models.Model):
    """Abstract model for contact information"""
    phone = PhoneNumberField(blank=True, null=True)
    email = models.EmailField(blank=True)

    class Meta:
        abstract = True
