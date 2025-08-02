from django.contrib import admin
from django.contrib.admin import AdminSite
from django.utils.html import format_html
from django.urls import reverse
from apps.core.tenant_models import Tenant
from apps.subscriptions.models import SubscriptionPlan, Subscription

# Create a custom admin site for system administration
class SystemAdminSite(AdminSite):
    site_header = "Autowash System Administration"
    site_title = "System Admin"
    index_title = "System Administration Panel"

# Create an instance of the custom admin site
system_admin_site = SystemAdminSite(name='system_admin')

class SystemTenantAdmin(admin.ModelAdmin):
    """System Admin interface for managing business applications"""
    
    list_display = (
        'name', 'business_type', 'owner', 'subscription_status', 
        'is_approved', 'is_active', 'created_at', 'approval_actions'
    )
    list_filter = (
        'business_type', 'is_approved', 'is_active', 'is_verified', 
        'created_at'
    )
    search_fields = ('name', 'slug', 'owner__username', 'owner__email', 'email')
    readonly_fields = (
        'slug', 'database_name', 'created_at', 'updated_at', 
        'subscription_details', 'business_metrics'
    )
    
    fieldsets = (
        ('Business Application', {
            'fields': ('name', 'slug', 'description', 'business_type', 'owner')
        }),
        ('Contact Information', {
            'fields': ('email', 'phone', 'address_line_1', 'city', 'country')
        }),
        ('Approval Status', {
            'fields': ('is_approved', 'approved_by', 'approved_at', 'rejection_reason'),
            'classes': ('wide',)
        }),
        ('Subscription', {
            'fields': ('subscription', 'subscription_details'),
            'classes': ('wide',)
        }),
        ('System Status', {
            'fields': ('is_active', 'is_verified', 'database_name')
        }),
        ('Business Metrics', {
            'fields': ('business_metrics',),
            'classes': ('collapse',)
        })
    )
    
    actions = ['approve_businesses', 'reject_businesses', 'activate_businesses', 'deactivate_businesses']
    
    def subscription_status(self, obj):
        """Show subscription status"""
        if obj.subscription:
            status = obj.subscription.status
            color = {
                'active': 'green',
                'trial': 'orange', 
                'expired': 'red',
                'cancelled': 'red',
                'suspended': 'orange'
            }.get(status, 'gray')
            return format_html(
                '<span style="color: {}; font-weight: bold;">{}</span>',
                color, status.title()
            )
        return format_html('<span style="color: red;">No Subscription</span>')
    subscription_status.short_description = 'Subscription'
    
    def subscription_details(self, obj):
        """Show detailed subscription information"""
        if obj.subscription:
            sub = obj.subscription
            return format_html(
                """
                <strong>Plan:</strong> {}<br>
                <strong>Status:</strong> {}<br>
                <strong>Start:</strong> {}<br>
                <strong>End:</strong> {}<br>
                <strong>Amount:</strong> KES {}<br>
                """,
                sub.plan.name,
                sub.status.title(),
                sub.start_date.strftime('%Y-%m-%d'),
                sub.end_date.strftime('%Y-%m-%d'),
                sub.amount
            )
        return "No active subscription"
    subscription_details.short_description = 'Subscription Details'
    
    def business_metrics(self, obj):
        """Show business performance metrics"""
        # This would connect to tenant database and show key metrics
        return "Metrics: Revenue, Customers, Services (Implementation needed)"
    business_metrics.short_description = 'Performance Metrics'
    
    def approval_actions(self, obj):
        """Show approval action buttons"""
        if not obj.is_approved and obj.is_active:
            return format_html('<span style="color: orange;">Pending Review</span>')
        elif obj.is_approved:
            return format_html('<span style="color: green;">✓ Approved</span>')
        else:
            return format_html('<span style="color: gray;">Inactive</span>')
    approval_actions.short_description = 'Status'
    
    def approve_businesses(self, request, queryset):
        """Approve selected businesses"""
        from django.utils import timezone
        updated = queryset.update(
            is_approved=True,
            approved_by=request.user,
            approved_at=timezone.now(),
            is_active=True
        )
        self.message_user(request, f'{updated} businesses approved.')
    approve_businesses.short_description = 'Approve selected businesses'
    
    def reject_businesses(self, request, queryset):
        """Reject selected businesses"""
        updated = queryset.update(is_approved=False, is_active=False)
        self.message_user(request, f'{updated} businesses rejected.')
    reject_businesses.short_description = 'Reject selected businesses'


class SystemSubscriptionPlanAdmin(admin.ModelAdmin):
    """System admin interface for subscription plans"""
    
    list_display = ('name', 'plan_type', 'price', 'duration_months', 'is_popular', 'is_active')
    list_filter = ('plan_type', 'is_popular', 'is_active')
    search_fields = ('name', 'description')


class SystemSubscriptionAdmin(admin.ModelAdmin):
    """System admin interface for active subscriptions"""
    
    list_display = ('business', 'plan', 'status', 'start_date', 'end_date', 'amount')
    list_filter = ('status', 'plan__name', 'start_date', 'end_date')
    search_fields = ('business__name', 'plan__name')
    readonly_fields = ('subscription_id', 'created_at', 'updated_at')


# Register models with the custom admin site
system_admin_site.register(Tenant, SystemTenantAdmin)
system_admin_site.register(SubscriptionPlan, SystemSubscriptionPlanAdmin)
system_admin_site.register(Subscription, SystemSubscriptionAdmin)
