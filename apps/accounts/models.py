from django.conf import settings
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from phonenumber_field.modelfields import PhoneNumberField
from apps.core.models import TimeStampedModel, Address, ContactInfo
from apps.core.utils import upload_to_path
from django.utils import timezone
from datetime import timedelta
import uuid
import os
import random
import string

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
    receive_login_notifications = models.BooleanField(default=True, help_text="Receive email notifications when you sign in")
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} Profile"
    
    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"


class EmailOTP(TimeStampedModel):
    """OTP model for email verification"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_otps')
    email = models.EmailField()
    otp_code = models.CharField(max_length=6)
    purpose = models.CharField(
        max_length=20,
        choices=[
            ('registration', 'Registration'),
            ('login', 'Login'),
            ('password_reset', 'Password Reset'),
            ('email_change', 'Email Change'),
        ],
        default='registration'
    )
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    
    class Meta:
        verbose_name = "Email OTP"
        verbose_name_plural = "Email OTPs"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"OTP for {self.email} - {self.otp_code}"
    
    @classmethod
    def generate_otp(cls, user, email, purpose='registration', expires_in_minutes=10):
        """Generate a new OTP for user"""
        # Generate 6-digit OTP
        otp_code = ''.join(random.choices(string.digits, k=6))
        
        # Set expiration time
        expires_at = timezone.now() + timedelta(minutes=expires_in_minutes)
        
        # Invalidate any existing OTPs for this user and purpose
        cls.objects.filter(
            user=user, 
            purpose=purpose, 
            is_used=False,
            expires_at__gt=timezone.now()
        ).update(is_used=True)
        
        # Create new OTP
        otp = cls.objects.create(
            user=user,
            email=email,
            otp_code=otp_code,
            purpose=purpose,
            expires_at=expires_at
        )
        
        return otp
    
    def is_valid(self):
        """Check if OTP is still valid"""
        return (
            not self.is_used and 
            timezone.now() <= self.expires_at
        )
    
    def mark_as_used(self):
        """Mark OTP as used"""
        self.is_used = True
        self.save(update_fields=['is_used'])


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
