from django.conf import settings
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from phonenumber_field.modelfields import PhoneNumberField
from apps.core.models import TimeStampedModel, Address, ContactInfo
from apps.core.utils import upload_to_path
import uuid
import os

class UserProfile(TimeStampedModel):
    """Extended user profile"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = PhoneNumberField(blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(
        max_length=10,
        choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')],
        blank=True
    )
    bio = models.TextField(blank=True)
    is_verified = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=100, blank=True)
    
    # Preferences
    language = models.CharField(max_length=10, default='en')
    timezone = models.CharField(max_length=50, default='Africa/Nairobi')
    receive_sms = models.BooleanField(default=True)
    receive_email = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} Profile"
    
    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"


# Import the new Tenant model as Business for backward compatibility
from apps.core.tenant_models import Tenant as Business, TenantUser as BusinessUser, TenantSettings as BusinessSettings

# Legacy Domain model (no longer needed but kept for migration compatibility)
class Domain(models.Model):
    """Legacy domain model - replaced by Tenant model"""
    domain = models.CharField(max_length=253, unique=True)
    is_primary = models.BooleanField(default=True)
    
    # Link to new Tenant model
    tenant = models.ForeignKey(
        Business, 
        on_delete=models.CASCADE, 
        related_name='legacy_domains',
        null=True, 
        blank=True
    )
    
    class Meta:
        verbose_name = "Legacy Domain"
        verbose_name_plural = "Legacy Domains"
    
    def __str__(self):
        return self.domain


class BusinessVerification(TimeStampedModel):
    """Business verification records"""
    business = models.OneToOneField(Business, on_delete=models.CASCADE, related_name='verification')
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_review', 'In Review'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    submitted_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='verified_businesses'
    )
    
    # Documents
    business_license = models.FileField(upload_to='verification/licenses/', blank=True)
    tax_certificate = models.FileField(upload_to='verification/tax/', blank=True)
    id_document = models.FileField(upload_to='verification/ids/', blank=True)
    
    notes = models.TextField(blank=True, help_text="Verification notes")
    rejection_reason = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.business.name} Verification"
    
    class Meta:
        verbose_name = "Business Verification"
        verbose_name_plural = "Business Verifications"
