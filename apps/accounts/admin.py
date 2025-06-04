# apps/accounts/admin.py - FIXED VERSION

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Count, Q
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.core.mail import send_mail
from django.conf import settings
import csv
from django.http import HttpResponse

from .models import UserProfile, Business, Domain, BusinessSettings, BusinessVerification

# Unregister the default User admin
admin.site.unregister(User)

class UserProfileInline(admin.StackedInline):
    """Inline for user profile"""
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fk_name = 'user'  # FIX: Specify the foreign key field name
    fields = (
        'phone', 'avatar', 'date_of_birth', 'gender', 'bio',
        'is_verified', 'language', 'timezone',
        'receive_sms', 'receive_email'
    )
    readonly_fields = ('verification_token',)

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Enhanced User admin with profile"""
    inlines = (UserProfileInline,)
    list_display = (
        'username', 'email', 'first_name', 'last_name', 
        'is_staff', 'is_active', 'date_joined', 'owned_businesses_count',
        'profile_verified'
    )
    list_filter = (
        'is_staff', 'is_superuser', 'is_active', 'date_joined',
        'profile__is_verified', 'profile__language'
    )
    search_fields = ('username', 'first_name', 'last_name', 'email', 'profile__phone')
    ordering = ('-date_joined',)
    
    def owned_businesses_count(self, obj):
        count = obj.owned_businesses.count()
        if count > 0:
            return format_html(
                '<a href="{}?owner__id__exact={}">{} business{}</a>',
                reverse('admin:accounts_business_changelist'),
                obj.id,
                count,
                'es' if count != 1 else ''
            )
        return '0'
    owned_businesses_count.short_description = 'Businesses'
    
    def profile_verified(self, obj):
        try:
            if obj.profile.is_verified:
                return format_html('<span style="color: green;">✓ Verified</span>')
            return format_html('<span style="color: orange;">⚠ Not Verified</span>')
        except UserProfile.DoesNotExist:
            return format_html('<span style="color: red;">✗ No Profile</span>')
    profile_verified.short_description = 'Profile Status'

class DomainInline(admin.TabularInline):
    """Inline for business domains"""
    model = Domain
    extra = 0
    fields = ('domain', 'is_primary')
    readonly_fields = ('domain',)

class BusinessSettingsInline(admin.StackedInline):
    """Inline for business settings"""
    model = BusinessSettings
    can_delete = False
    fields = (
        ('sms_notifications', 'email_notifications', 'customer_sms_notifications'),
        ('auto_assign_attendants', 'require_customer_approval', 'send_service_reminders'),
        ('accept_cash', 'accept_card', 'accept_mpesa', 'require_payment_confirmation'),
        ('track_inventory', 'auto_reorder', 'low_stock_threshold'),
        ('daily_reports', 'weekly_reports', 'monthly_reports'),
        ('loyalty_program', 'customer_rating', 'customer_feedback'),
    )

class BusinessVerificationInline(admin.StackedInline):
    """Inline for business verification"""
    model = BusinessVerification
    can_delete = False
    fields = (
        'status', 'business_license', 'tax_certificate', 'id_document',
        'notes', 'rejection_reason', 'verified_by', 'verified_at'
    )
    readonly_fields = ('submitted_at', 'verified_by', 'verified_at')

@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    """Comprehensive Business admin"""
    list_display = (
        'name', 'business_type', 'owner_link', 'verification_status',
        'is_active', 'employee_count', 'customer_count',
        'created_at', 'domain_link'
    )
    # FIX: Remove the invalid subscription__is_active filter
    list_filter = (
        'business_type', 'is_active', 'is_verified', 'verification__status',
        'created_at', 'currency', 'timezone'
    )
    search_fields = (
        'name', 'slug', 'description', 'owner__username', 
        'owner__first_name', 'owner__last_name', 'owner__email',
        'registration_number', 'tax_number'
    )
    readonly_fields = (
        'slug', 'schema_name', 'created_at', 'updated_at',
        'employee_count', 'customer_count', 'domain_link'
    )
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'name', 'slug', 'description', 'logo', 'business_type'
            )
        }),
        ('Owner & Status', {
            'fields': (
                'owner', 'is_active', 'is_verified'
            )
        }),
        ('Registration Details', {
            'fields': (
                'registration_number', 'tax_number'
            ),
            'classes': ('collapse',)
        }),
        ('Contact Information', {
            'fields': (
                'phone', 'email', 'website', 'address', 'city', 'state', 'country'
            ),
            'classes': ('collapse',)
        }),
        ('Business Settings', {
            'fields': (
                'opening_time', 'closing_time', 'timezone', 'currency', 'language'
            ),
            'classes': ('collapse',)
        }),
        ('Subscription & Limits', {
            'fields': (
                'subscription', 'max_employees', 'max_customers'
            ),
            'classes': ('collapse',)
        }),
        ('Technical Details', {
            'fields': (
                'schema_name', 'employee_count', 'customer_count', 'domain_link',
                'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        }),
    )
    inlines = [DomainInline, BusinessSettingsInline, BusinessVerificationInline]
    actions = [
        'verify_businesses', 'deactivate_businesses', 'activate_businesses',
        'export_businesses_csv', 'send_verification_reminder'
    ]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'owner', 'subscription', 'verification'
        ).prefetch_related('domains')
    
    def owner_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.owner.id])
        return format_html('<a href="{}">{}</a>', url, obj.owner.get_full_name() or obj.owner.username)
    owner_link.short_description = 'Owner'
    
    def verification_status(self, obj):
        try:
            status = obj.verification.status
            colors = {
                'pending': 'orange',
                'in_review': 'blue',
                'verified': 'green',
                'rejected': 'red'
            }
            return format_html(
                '<span style="color: {}; font-weight: bold;">{}</span>',
                colors.get(status, 'gray'),
                obj.verification.get_status_display()
            )
        except BusinessVerification.DoesNotExist:
            return format_html('<span style="color: red;">No Verification</span>')
    verification_status.short_description = 'Verification'
    
    def domain_link(self, obj):
        domain = obj.domains.filter(is_primary=True).first()
        if domain:
            protocol = 'http' if settings.DEBUG else 'https'
            url = f"{protocol}://{domain.domain}"
            return format_html('<a href="{}" target="_blank">{}</a>', url, domain.domain)
        return 'No Domain'
    domain_link.short_description = 'Domain'
    
    # FIX: Add employee_count and customer_count methods with error handling
    def employee_count(self, obj):
        try:
            from apps.employees.models import Employee
            return Employee.objects.filter(is_active=True).count()
        except ImportError:
            return 'N/A'
    employee_count.short_description = 'Employees'
    
    def customer_count(self, obj):
        try:
            from apps.customers.models import Customer
            return Customer.objects.count()
        except ImportError:
            return 'N/A'
    customer_count.short_description = 'Customers'
    
    # Admin Actions
    def verify_businesses(self, request, queryset):
        """Bulk verify businesses"""
        count = 0
        for business in queryset:
            verification, created = BusinessVerification.objects.get_or_create(business=business)
            if verification.status != 'verified':
                verification.status = 'verified'
                verification.verified_by = request.user
                verification.verified_at = timezone.now()
                verification.save()
                
                business.is_verified = True
                business.save()
                count += 1
        
        self.message_user(request, f'{count} business(es) verified successfully.')
    verify_businesses.short_description = "Verify selected businesses"
    
    def deactivate_businesses(self, request, queryset):
        """Bulk deactivate businesses"""
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} business(es) deactivated.')
    deactivate_businesses.short_description = "Deactivate selected businesses"
    
    def activate_businesses(self, request, queryset):
        """Bulk activate businesses"""
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} business(es) activated.')
    activate_businesses.short_description = "Activate selected businesses"
    
    def export_businesses_csv(self, request, queryset):
        """Export businesses to CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="businesses.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Name', 'Type', 'Owner', 'Email', 'Phone', 'Status', 'Verified',
            'Created', 'Domain'
        ])
        
        for business in queryset:
            writer.writerow([
                business.name,
                business.get_business_type_display(),
                business.owner.get_full_name() or business.owner.username,
                business.owner.email,
                business.phone,
                'Active' if business.is_active else 'Inactive',
                'Yes' if business.is_verified else 'No',
                business.created_at.strftime('%Y-%m-%d'),
                business.domain_url or 'No Domain'
            ])
        
        return response
    export_businesses_csv.short_description = "Export to CSV"
    
    def send_verification_reminder(self, request, queryset):
        """Send verification reminder emails"""
        count = 0
        for business in queryset.filter(is_verified=False):
            try:
                send_mail(
                    subject=f'Complete verification for {business.name}',
                    message=f'Dear {business.owner.get_full_name()},\n\n'
                           f'Please complete the verification process for your business "{business.name}".\n\n'
                           f'Log in to your dashboard to upload the required documents.\n\n'
                           f'Best regards,\nAutowash Team',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[business.owner.email],
                    fail_silently=False,
                )
                count += 1
            except Exception as e:
                self.message_user(request, f'Failed to send email to {business.owner.email}: {e}', level=messages.ERROR)
        
        self.message_user(request, f'Verification reminders sent to {count} business owner(s).')
    send_verification_reminder.short_description = "Send verification reminders"

@admin.register(BusinessVerification)
class BusinessVerificationAdmin(admin.ModelAdmin):
    """Dedicated admin for business verification management"""
    list_display = (
        'business_link', 'status', 'submitted_at', 'verified_by', 'verified_at',
        'has_documents', 'business_owner'
    )
    list_filter = (
        'status', 'submitted_at', 'verified_at', 'verified_by'
    )
    search_fields = (
        'business__name', 'business__owner__username', 
        'business__owner__email', 'notes', 'rejection_reason'
    )
    readonly_fields = ('submitted_at', 'business_owner')
    fieldsets = (
        ('Business Information', {
            'fields': ('business', 'business_owner', 'status')
        }),
        ('Verification Details', {
            'fields': (
                'submitted_at', 'verified_at', 'verified_by',
                'notes', 'rejection_reason'
            )
        }),
        ('Documents', {
            'fields': (
                'business_license', 'tax_certificate', 'id_document'
            )
        }),
    )
    actions = [
        'approve_verifications', 'reject_verifications', 'mark_in_review',
        'send_approval_emails', 'send_rejection_emails'
    ]
    
    def business_link(self, obj):
        url = reverse('admin:accounts_business_change', args=[obj.business.id])
        return format_html('<a href="{}">{}</a>', url, obj.business.name)
    business_link.short_description = 'Business'
    
    def business_owner(self, obj):
        user = obj.business.owner
        url = reverse('admin:auth_user_change', args=[user.id])
        return format_html('<a href="{}">{} ({})</a>', url, user.get_full_name() or user.username, user.email)
    business_owner.short_description = 'Owner'
    
    def has_documents(self, obj):
        docs = [obj.business_license, obj.tax_certificate, obj.id_document]
        uploaded = sum(1 for doc in docs if doc)
        if uploaded == 3:
            return format_html('<span style="color: green;">✓ Complete ({}/3)</span>', uploaded)
        elif uploaded > 0:
            return format_html('<span style="color: orange;">⚠ Partial ({}/3)</span>', uploaded)
        return format_html('<span style="color: red;">✗ None (0/3)</span>')
    has_documents.short_description = 'Documents'
    
    # Admin Actions
    def approve_verifications(self, request, queryset):
        """Bulk approve verifications"""
        count = 0
        for verification in queryset.exclude(status='verified'):
            verification.status = 'verified'
            verification.verified_by = request.user
            verification.verified_at = timezone.now()
            verification.save()
            
            # Update business
            verification.business.is_verified = True
            verification.business.save()
            count += 1
        
        self.message_user(request, f'{count} verification(s) approved.')
    approve_verifications.short_description = "Approve selected verifications"
    
    def reject_verifications(self, request, queryset):
        """Bulk reject verifications"""
        count = queryset.exclude(status='rejected').update(
            status='rejected',
            verified_at=None,
            verified_by=None
        )
        
        # Update businesses
        for verification in queryset:
            verification.business.is_verified = False
            verification.business.save()
        
        self.message_user(request, f'{count} verification(s) rejected.')
    reject_verifications.short_description = "Reject selected verifications"
    
    def mark_in_review(self, request, queryset):
        """Mark verifications as in review"""
        count = queryset.update(status='in_review')
        self.message_user(request, f'{count} verification(s) marked as in review.')
    mark_in_review.short_description = "Mark as in review"
    
    def send_approval_emails(self, request, queryset):
        """Send approval notification emails"""
        count = 0
        for verification in queryset.filter(status='verified'):
            try:
                send_mail(
                    subject=f'Business verification approved - {verification.business.name}',
                    message=f'Congratulations! Your business "{verification.business.name}" has been verified.\n\n'
                           f'You can now access all features of your account.\n\n'
                           f'Best regards,\nAutowash Team',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[verification.business.owner.email],
                    fail_silently=False,
                )
                count += 1
            except Exception as e:
                self.message_user(request, f'Failed to send email: {e}', level=messages.ERROR)
        
        self.message_user(request, f'Approval emails sent to {count} business owner(s).')
    send_approval_emails.short_description = "Send approval emails"
    
    def send_rejection_emails(self, request, queryset):
        """Send rejection notification emails"""
        count = 0
        for verification in queryset.filter(status='rejected'):
            try:
                reason = verification.rejection_reason or 'Please review your documents and resubmit.'
                send_mail(
                    subject=f'Business verification requires attention - {verification.business.name}',
                    message=f'Your business verification for "{verification.business.name}" requires attention.\n\n'
                           f'Reason: {reason}\n\n'
                           f'Please log in to your account and resubmit the required documents.\n\n'
                           f'Best regards,\nAutowash Team',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[verification.business.owner.email],
                    fail_silently=False,
                )
                count += 1
            except Exception as e:
                self.message_user(request, f'Failed to send email: {e}', level=messages.ERROR)
        
        self.message_user(request, f'Rejection emails sent to {count} business owner(s).')
    send_rejection_emails.short_description = "Send rejection emails"

@admin.register(BusinessSettings)
class BusinessSettingsAdmin(admin.ModelAdmin):
    """Admin for business settings"""
    list_display = ('business', 'sms_notifications', 'email_notifications', 'track_inventory')
    list_filter = (
        'sms_notifications', 'email_notifications', 'track_inventory',
        'auto_assign_attendants', 'loyalty_program'
    )
    search_fields = ('business__name', 'business__owner__username')

@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    """Admin for domains"""
    list_display = ('domain', 'tenant', 'is_primary')
    list_filter = ('is_primary',)
    search_fields = ('domain', 'tenant__name')
    readonly_fields = ('tenant',)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Admin for user profiles"""
    list_display = ('user', 'phone', 'is_verified', 'language', 'timezone')
    list_filter = ('is_verified', 'language', 'timezone', 'gender')
    search_fields = ('user__username', 'user__email', 'phone')
    readonly_fields = ('verification_token',)

# Customize admin site headers
admin.site.site_header = "Autowash Platform Administration"
admin.site.site_title = "Autowash Admin"
admin.site.index_title = "Welcome to Autowash Administration"