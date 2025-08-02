# apps/accounts/admin.py - Fixed FK constraint issues

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
from django.db import connection, transaction
import csv
from django.http import HttpResponse

from .models import UserProfile
from apps.core.tenant_models import Tenant, TenantSettings

# Comment out old model imports temporarily
# from .models import Business, Domain, BusinessSettings, BusinessVerification

# Unregister the default User admin
admin.site.unregister(User)

class UserProfileInline(admin.StackedInline):
    """Inline for user profile"""
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fk_name = 'user'
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
    """Comprehensive Business admin - FIXED field references"""
    list_display = (
        'name', 'business_type', 'owner_link', 'verification_status',
        'is_active', 'is_verified', 'schema_status', 'owner_employee_status',
        'created_at', 'domain_link'
    )
    list_filter = (
        'business_type', 'is_active', 'is_verified', 
        'created_at', 'currency', 'timezone'
    )
    search_fields = (
        'name', 'slug', 'description', 'owner__username', 
        'owner__first_name', 'owner__last_name', 'owner__email',
        'registration_number', 'tax_number', 'phone', 'email'
    )
    readonly_fields = (
        'slug', 'schema_name', 'created_at', 'updated_at',
        'domain_link', 'schema_status', 'owner_employee_status'
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
                'phone', 'email', 'website'
            ),
            'classes': ('collapse',)
        }),
        ('Business Operations', {
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
                'schema_name', 'schema_status', 'owner_employee_status', 'domain_link',
                'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        }),
    )
    inlines = [DomainInline, BusinessSettingsInline, BusinessVerificationInline]
    actions = [
        'verify_businesses', 'deactivate_businesses', 'activate_businesses',
        'export_businesses_csv', 'send_verification_reminder', 'create_owner_employees'
    ]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'owner', 'subscription'
        ).prefetch_related('domains')
    
    def owner_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.owner.id])
        return format_html('<a href="{}">{}</a>', url, obj.owner.get_full_name() or obj.owner.username)
    owner_link.short_description = 'Owner'
    
    def verification_status(self, obj):
        try:
            verification = BusinessVerification.objects.get(business=obj)
            status = verification.status
            colors = {
                'pending': 'orange',
                'in_review': 'blue',
                'verified': 'green',
                'rejected': 'red'
            }
            return format_html(
                '<span style="color: {}; font-weight: bold;">{}</span>',
                colors.get(status, 'gray'),
                verification.get_status_display()
            )
        except BusinessVerification.DoesNotExist:
            return format_html('<span style="color: red;">No Verification</span>')
    verification_status.short_description = 'Verification'
    
    def schema_status(self, obj):
        """Check if schema exists"""
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s",
                    [obj.schema_name]
                )
                if cursor.fetchone():
                    return format_html('<span style="color: green;">✓ Created</span>')
                else:
                    return format_html('<span style="color: orange;">⚠ Not Created</span>')
        except:
            return format_html('<span style="color: red;">✗ Error</span>')
    schema_status.short_description = 'Schema'
    
    def owner_employee_status(self, obj):
        """Check if owner has employee record in tenant schema using user_id"""
        if not obj.is_verified:
            return format_html('<span style="color: gray;">N/A (Not Verified)</span>')
            
        try:
            # Check if schema exists first
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s",
                    [obj.schema_name]
                )
                if not cursor.fetchone():
                    return format_html('<span style="color: red;">✗ No Schema</span>')
            
            # Check if owner employee exists using user_id
            from django_tenants.utils import schema_context
            with schema_context(obj.schema_name):
                from apps.employees.models import Employee
                try:
                    employee = Employee.objects.get(user_id=obj.owner.id, is_active=True)
                    return format_html('<span style="color: green;">✓ Employee ({} - {})</span>', 
                                     employee.employee_id, employee.get_role_display())
                except Employee.DoesNotExist:
                    return format_html('<span style="color: red;">✗ No Employee Record</span>')
                except Employee.MultipleObjectsReturned:
                    return format_html('<span style="color: orange;">⚠ Multiple Records</span>')
        except Exception as e:
            return format_html('<span style="color: red;">✗ Error: {}</span>', str(e)[:30])
    owner_employee_status.short_description = 'Owner Employee'
    
    def domain_link(self, obj):
        domain = obj.domains.filter(is_primary=True).first()
        if domain:
            protocol = 'http' if settings.DEBUG else 'https'
            url = f"{protocol}://{domain.domain}"
            return format_html('<a href="{}" target="_blank">{}</a>', url, domain.domain)
        return 'No Domain'
    domain_link.short_description = 'Domain'
    
    # NEW ACTION: Create owner employees for verified businesses
    def create_owner_employees(self, request, queryset):
        """Create owner employee records for verified businesses that don't have them"""
        count = 0
        failed = 0
        
        verified_businesses = queryset.filter(is_verified=True)
        
        for business in verified_businesses:
            try:
                # Check if schema exists
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s",
                        [business.schema_name]
                    )
                    if not cursor.fetchone():
                        self.message_user(request, 
                                        f'Schema does not exist for {business.name}. Create schema first.',
                                        level=messages.WARNING)
                        continue
                
                # Check if owner employee already exists
                from django_tenants.utils import schema_context
                with schema_context(business.schema_name):
                    from apps.employees.models import Employee, Department
                    
                    # Check if owner already has employee record using user_id
                    existing_employee = Employee.objects.filter(user_id=business.owner.id, is_active=True).first()
                    if existing_employee:
                        print(f"Owner employee already exists for {business.name}: {existing_employee.employee_id}")
                        continue
                    
                    # Also check for employees with old user relationship that need conversion
                    try:
                        old_employee = Employee.objects.filter(user_id__isnull=True).first()
                        if old_employee and hasattr(old_employee, 'user') and old_employee.user and old_employee.user.id == business.owner.id:
                            # Convert old employee record
                            old_employee.user_id = business.owner.id
                            old_employee.save()
                            print(f"Converted existing employee record for {business.name}: {old_employee.employee_id}")
                            continue
                    except Exception as convert_error:
                        print(f"Error during conversion check: {convert_error}")
                        pass
                        print(f"Owner employee already exists for {business.name}: {existing_employee.employee_id}")
                        continue
                    
                    # Create management department if it doesn't exist
                    management_dept, created = Department.objects.get_or_create(
                        name='Management',
                        defaults={
                            'description': 'Business management and administration',
                            'is_active': True
                        }
                    )
                    
                    # Generate employee ID
                    employee_count = Employee.objects.count()
                    employee_id = f"EMP{business.schema_name.upper()[:3]}{employee_count + 1:04d}"
                    
                    # Get user profile for additional info from public schema
                    user_profile = None
                    try:
                        with schema_context('public'):
                            user_profile = business.owner.profile
                    except:
                        pass
                    
                    # Create owner as employee using user_id
                    owner_employee = Employee.objects.create(
                        user_id=business.owner.id,  # Use user_id instead of user object
                        employee_id=employee_id,
                        role='owner',
                        employment_type='full_time',
                        status='active',
                        department=management_dept,
                        hire_date=business.created_at.date(),
                        is_active=True,
                        can_login=True,
                        receive_notifications=True,
                        # REMOVED: email=business.owner.email,  # This causes the error
                        phone=user_profile.phone if user_profile else None,
                        # Default address info
                        country='Kenya',
                    )
                    
                    # Set department head if not already set
                    if not management_dept.head:
                        management_dept.head = owner_employee
                        management_dept.save()
                    
                    print(f"Created owner employee for {business.name}: {owner_employee.employee_id}")
                    count += 1
                    
            except Exception as e:
                failed += 1
                print(f"Failed to create owner employee for {business.name}: {str(e)}")
                import traceback
                traceback.print_exc()
        
        if count > 0:
            self.message_user(request, f'{count} owner employee record(s) created successfully.')
        if failed > 0:
            self.message_user(request, f'{failed} owner employee creation(s) failed.', level=messages.ERROR)
    create_owner_employees.short_description = "👤 Create owner employee records"
    
    # Admin Actions
    def verify_businesses(self, request, queryset):
        """Bulk verify businesses WITHOUT creating schemas"""
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
        
        self.message_user(request, f'{count} business(es) verified successfully. Use "Approve and Create Schema" action in BusinessVerification to create tenant schemas.')
    verify_businesses.short_description = "✅ Verify businesses (no schema)"
    
    def deactivate_businesses(self, request, queryset):
        """Bulk deactivate businesses"""
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} business(es) deactivated.')
    deactivate_businesses.short_description = "❌ Deactivate selected businesses"
    
    def activate_businesses(self, request, queryset):
        """Bulk activate businesses"""
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} business(es) activated.')
    activate_businesses.short_description = "✅ Activate selected businesses"
    
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
                business.phone or '',
                'Active' if business.is_active else 'Inactive',
                'Yes' if business.is_verified else 'No',
                business.created_at.strftime('%Y-%m-%d'),
                business.domain_url or 'No Domain'
            ])
        
        return response
    export_businesses_csv.short_description = "📁 Export to CSV"
    
    def send_verification_reminder(self, request, queryset):
        """Send verification reminder emails"""
        count = 0
        for business in queryset.filter(is_verified=False):
            try:
                send_mail(
                    subject=f'Complete verification for {business.name}',
                    message=f'Dear {business.owner.get_full_name() or business.owner.username},\n\n'
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
    send_verification_reminder.short_description = "📧 Send verification reminders"

@admin.register(BusinessVerification)
class BusinessVerificationAdmin(admin.ModelAdmin):
    """Dedicated admin for business verification management"""
    list_display = (
        'business_link', 'status', 'submitted_at', 'verified_by', 'verified_at',
        'has_documents', 'business_owner', 'schema_exists', 'owner_employee_exists'
    )
    list_filter = (
        'status', 'submitted_at', 'verified_at', 'verified_by'
    )
    search_fields = (
        'business__name', 'business__owner__username', 
        'business__owner__email', 'notes', 'rejection_reason'
    )
    readonly_fields = ('submitted_at', 'business_owner', 'schema_exists', 'owner_employee_exists')
    fieldsets = (
        ('Business Information', {
            'fields': ('business', 'business_owner', 'status', 'schema_exists', 'owner_employee_exists')
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
        'approve_verifications', 
        'approve_and_create_schema',  # MAIN ACTION
        'reject_verifications', 
        'mark_in_review',
        'send_approval_emails', 
        'send_rejection_emails'
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
    
    def schema_exists(self, obj):
        """Check if schema exists for this business"""
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s",
                    [obj.business.schema_name]
                )
                if cursor.fetchone():
                    return format_html('<span style="color: green;">✓ Schema Created</span>')
                else:
                    return format_html('<span style="color: orange;">⚠ No Schema</span>')
        except:
            return format_html('<span style="color: red;">✗ Error</span>')
    schema_exists.short_description = 'Schema Status'
    
    def owner_employee_exists(self, obj):
        """Check if owner employee exists in tenant schema using user_id"""
        if obj.status != 'verified':
            return format_html('<span style="color: gray;">N/A (Not Verified)</span>')
            
        try:
            # Check if schema exists first
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s",
                    [obj.business.schema_name]
                )
                if not cursor.fetchone():
                    return format_html('<span style="color: red;">✗ No Schema</span>')
            
            # Check if owner employee exists using user_id
            from django_tenants.utils import schema_context
            with schema_context(obj.business.schema_name):
                from apps.employees.models import Employee
                try:
                    employee = Employee.objects.get(user_id=obj.business.owner.id, is_active=True)
                    return format_html('<span style="color: green;">✓ Employee Exists ({})</span>', 
                                     employee.employee_id)
                except Employee.DoesNotExist:
                    return format_html('<span style="color: red;">✗ No Employee Record</span>')
                except Employee.MultipleObjectsReturned:
                    return format_html('<span style="color: orange;">⚠ Multiple Records</span>')
        except Exception as e:
            return format_html('<span style="color: red;">✗ Error</span>')
    owner_employee_exists.short_description = 'Owner Employee'
    
    # ENHANCED MAIN ADMIN ACTION for verification with owner employee creation
    def approve_and_create_schema(self, request, queryset):
        """Approve verifications, create tenant schemas, and ensure owner employee exists"""
        count = 0
        failed = 0
        
        for verification in queryset.exclude(status='verified'):
            try:
                with transaction.atomic():
                    # Update verification
                    verification.status = 'verified'
                    verification.verified_by = request.user
                    verification.verified_at = timezone.now()
                    verification.save()
                    
                    # Update business
                    business = verification.business
                    business.is_verified = True
                    business.save()
                    
                    # Check if schema already exists
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s",
                            [business.schema_name]
                        )
                        schema_exists = cursor.fetchone()
                        
                        if schema_exists:
                            print(f"Schema already exists for: {business.name}")
                        else:
                            # Create the tenant schema
                            print(f"Creating schema for business: {business.name}")
                            
                            # Create schema
                            cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{business.schema_name}"')
                            
                            # Run migrations in the new schema
                            from django_tenants.utils import schema_context
                            from django.core.management import call_command
                            
                            with schema_context(business.schema_name):
                                call_command('migrate', 
                                           '--run-syncdb',
                                           verbosity=0,
                                           interactive=False)
                            
                            print(f"Schema created successfully for: {business.name}")
                    
                    # IMPORTANT: Create owner employee record using user_id
                    from django_tenants.utils import schema_context
                    with schema_context(business.schema_name):
                        from apps.employees.models import Employee, Department
                        
                        # Check if owner employee already exists using user_id
                        existing_employee = Employee.objects.filter(user_id=business.owner.id, is_active=True).first()
                        if not existing_employee:
                            # Create management department
                            management_dept, created = Department.objects.get_or_create(
                                name='Management',
                                defaults={
                                    'description': 'Business management and administration',
                                    'is_active': True
                                }
                            )
                            
                            # Generate employee ID
                            employee_count = Employee.objects.count()
                            employee_id = f"EMP{business.schema_name.upper()[:3]}{employee_count + 1:04d}"
                            
                            # Get user profile for additional info from public schema
                            user_profile = None
                            try:
                                with schema_context('public'):
                                    user_profile = business.owner.profile
                            except:
                                pass
                            
                            # Create owner as employee using user_id directly
                            owner_employee = Employee.objects.create(
                                user_id=business.owner.id,  # Use user_id instead of user object
                                employee_id=employee_id,
                                role='owner',
                                employment_type='full_time',
                                status='active',
                                department=management_dept,
                                hire_date=business.created_at.date(),
                                is_active=True,
                                can_login=True,
                                receive_notifications=True,
                                # REMOVED: email=business.owner.email,  # This causes the error
                                phone=user_profile.phone if user_profile else None,
                                country='Kenya',
                            )
                            
                            # Set department head
                            management_dept.head = owner_employee
                            management_dept.save()
                            
                            print(f"Created owner employee: {owner_employee.employee_id}")
                        else:
                            print(f"Owner employee already exists: {existing_employee.employee_id}")
                    
                    # Send approval email
                    try:
                        domain = business.domains.filter(is_primary=True).first()
                        dashboard_url = f"http{'s' if not settings.DEBUG else ''}://{domain.domain}/" if domain else ""
                        
                        send_mail(
                            subject=f'🎉 {business.name} has been verified!',
                            message=f'''Congratulations! Your business "{business.name}" has been successfully verified.

You can now:
✅ Access your business dashboard: {dashboard_url}
✅ Start managing your operations
✅ Add employees and customers

Thank you for choosing Autowash!

Best regards,
The Autowash Team''',
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[business.owner.email],
                            fail_silently=True,
                        )
                        print(f"Approval email sent to: {business.owner.email}")
                    except Exception as email_error:
                        print(f"Failed to send email: {email_error}")
                    
                    count += 1
                    
            except Exception as e:
                failed += 1
                print(f"Failed to approve business {verification.business.name}: {str(e)}")
                import traceback
                traceback.print_exc()
                
                # Mark as failed
                verification.status = 'rejected'
                verification.rejection_reason = f"Technical error during approval: {str(e)}"
                verification.save()
        
        if count > 0:
            self.message_user(request, f'{count} business(es) verified, schemas created, and owner employees set up successfully.')
        if failed > 0:
            self.message_user(request, f'{failed} business(es) failed to process.', level=messages.ERROR)

    approve_and_create_schema.short_description = "🚀 Approve, create schema & owner employee"
    
    def approve_verifications(self, request, queryset):
        """Bulk approve verifications WITHOUT creating schemas"""
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
        
        self.message_user(request, f'{count} verification(s) approved. Use "Approve and Create Schema" to create tenant schemas.')
    approve_verifications.short_description = "✅ Approve verifications (no schema)"
    
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
    reject_verifications.short_description = "❌ Reject selected verifications"
    
    def mark_in_review(self, request, queryset):
        """Mark verifications as in review"""
        count = queryset.update(status='in_review')
        self.message_user(request, f'{count} verification(s) marked as in review.')
    mark_in_review.short_description = "👀 Mark as in review"
    
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
    send_approval_emails.short_description = "📧 Send approval emails"
    
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
    send_rejection_emails.short_description = "📧 Send rejection emails"

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