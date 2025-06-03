from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Count, Sum, Q
from .models import (
    SubscriptionPlan, Subscription, Payment, SubscriptionUsage,
    SubscriptionDiscount, SubscriptionInvoice
)

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'plan_type', 'monthly_price', 'max_employees', 
        'max_customers', 'is_active', 'is_popular', 'subscription_count'
    ]
    list_filter = ['plan_type', 'is_active', 'is_popular']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['sort_order', 'monthly_price']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'plan_type', 'description', 'is_active', 'is_popular')
        }),
        ('Pricing', {
            'fields': ('monthly_price', 'quarterly_price', 'annual_price')
        }),
        ('Limits', {
            'fields': ('max_employees', 'max_customers', 'max_locations', 'max_services', 'storage_limit')
        }),
        ('Features & Trial', {
            'fields': ('features', 'trial_days')
        }),
        ('Display', {
            'fields': ('sort_order',)
        }),
    )
    
    def subscription_count(self, obj):
        count = obj.subscription_set.filter(status__in=['active', 'trial']).count()
        return format_html('<span style="color: green;">{}</span>', count)
    subscription_count.short_description = 'Active Subscriptions'

class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ['payment_id', 'created_at', 'paid_at']
    fields = ['payment_method', 'amount', 'status', 'transaction_id', 'created_at', 'paid_at']

class SubscriptionUsageInline(admin.StackedInline):
    model = SubscriptionUsage
    extra = 0
    readonly_fields = ['last_updated']

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        'subscription_id', 'plan', 'status', 'billing_cycle', 
        'start_date', 'end_date', 'days_remaining_display', 'total_paid'
    ]
    list_filter = ['status', 'billing_cycle', 'plan', 'is_auto_renew', 'created_at']
    search_fields = ['subscription_id']
    readonly_fields = ['subscription_id', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    inlines = [PaymentInline, SubscriptionUsageInline]
    
    fieldsets = (
        ('Subscription Details', {
            'fields': ('subscription_id', 'plan', 'billing_cycle', 'amount', 'currency')
        }),
        ('Dates', {
            'fields': ('start_date', 'end_date', 'trial_end_date', 'grace_period_end')
        }),
        ('Status', {
            'fields': ('status', 'is_auto_renew')
        }),
        ('Cancellation', {
            'fields': ('cancelled_at', 'cancellation_reason'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def days_remaining_display(self, obj):
        days = obj.days_remaining
        if days > 30:
            color = 'green'
        elif days > 7:
            color = 'orange'
        else:
            color = 'red'
        return format_html('<span style="color: {};">{} days</span>', color, days)
    days_remaining_display.short_description = 'Days Remaining'
    
    def total_paid(self, obj):
        total = obj.payments.filter(status='completed').aggregate(Sum('amount'))['amount__sum'] or 0
        return f"KES {total:,.2f}"
    total_paid.short_description = 'Total Paid'
    
    actions = ['cancel_subscriptions', 'extend_subscriptions']
    
    def cancel_subscriptions(self, request, queryset):
        count = 0
        for subscription in queryset:
            if subscription.status in ['active', 'trial']:
                subscription.cancel_subscription("Cancelled by admin")
                count += 1
        self.message_user(request, f"Cancelled {count} subscriptions.")
    cancel_subscriptions.short_description = "Cancel selected subscriptions"
    
    def extend_subscriptions(self, request, queryset):
        # This would open a form to specify extension days
        # For simplicity, extending by 30 days
        for subscription in queryset:
            if subscription.status in ['active', 'trial']:
                subscription.extend_subscription(30)
        self.message_user(request, "Extended selected subscriptions by 30 days.")
    extend_subscriptions.short_description = "Extend selected subscriptions by 30 days"

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'payment_id', 'subscription', 'amount', 'payment_method', 
        'status', 'created_at', 'paid_at'
    ]
    list_filter = ['status', 'payment_method', 'created_at']
    search_fields = ['payment_id', 'transaction_id', 'reference_number']
    readonly_fields = ['payment_id', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Payment Details', {
            'fields': ('payment_id', 'subscription', 'amount', 'currency', 'payment_method')
        }),
        ('Status', {
            'fields': ('status', 'paid_at', 'failed_at')
        }),
        ('External References', {
            'fields': ('transaction_id', 'reference_number', 'gateway_response')
        }),
        ('Notes', {
            'fields': ('notes', 'failure_reason')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_completed', 'mark_as_failed']
    
    def mark_as_completed(self, request, queryset):
        count = queryset.filter(status='pending').count()
        for payment in queryset.filter(status='pending'):
            payment.mark_as_completed(notes="Marked as completed by admin")
        self.message_user(request, f"Marked {count} payments as completed.")
    mark_as_completed.short_description = "Mark selected payments as completed"
    
    def mark_as_failed(self, request, queryset):
        count = queryset.filter(status='pending').count()
        for payment in queryset.filter(status='pending'):
            payment.mark_as_failed("Marked as failed by admin")
        self.message_user(request, f"Marked {count} payments as failed.")
    mark_as_failed.short_description = "Mark selected payments as failed"

@admin.register(SubscriptionUsage)
class SubscriptionUsageAdmin(admin.ModelAdmin):
    list_display = [
        'subscription', 'employees_count', 'customers_count', 
        'storage_used', 'last_updated'
    ]
    list_filter = ['last_updated']
    search_fields = ['subscription__subscription_id']
    readonly_fields = ['last_updated']

@admin.register(SubscriptionDiscount)
class SubscriptionDiscountAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'name', 'discount_type', 'discount_value', 
        'current_uses', 'max_uses', 'valid_until', 'is_active'
    ]
    list_filter = ['discount_type', 'is_active', 'valid_from', 'valid_until']
    search_fields = ['code', 'name']
    filter_horizontal = ['applicable_plans']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('code', 'name', 'description', 'is_active')
        }),
        ('Discount Details', {
            'fields': ('discount_type', 'discount_value', 'applicable_plans')
        }),
        ('Usage Limits', {
            'fields': ('max_uses', 'current_uses')
        }),
        ('Validity', {
            'fields': ('valid_from', 'valid_until')
        }),
        ('Restrictions', {
            'fields': ('minimum_amount', 'first_time_users_only')
        }),
    )

@admin.register(SubscriptionInvoice)
class SubscriptionInvoiceAdmin(admin.ModelAdmin):
    list_display = [
        'invoice_number', 'subscription', 'total_amount', 
        'status', 'issue_date', 'due_date', 'paid_date'
    ]
    list_filter = ['status', 'issue_date', 'due_date']
    search_fields = ['invoice_number']
    readonly_fields = ['invoice_number', 'created_at', 'updated_at']
    date_hierarchy = 'issue_date'
    
    fieldsets = (
        ('Invoice Details', {
            'fields': ('invoice_number', 'subscription', 'payment', 'status')
        }),
        ('Amounts', {
            'fields': ('subtotal', 'discount_amount', 'tax_amount', 'total_amount')
        }),
        ('Dates', {
            'fields': ('issue_date', 'due_date', 'paid_date')
        }),
        ('Discount', {
            'fields': ('discount_code',)
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

# Add some custom admin views for analytics
class SubscriptionAnalyticsAdmin(admin.ModelAdmin):
    """Custom admin for subscription analytics"""
    
    def changelist_view(self, request, extra_context=None):
        # Add analytics data to the context
        extra_context = extra_context or {}
        
        # Total subscriptions by status
        status_counts = Subscription.objects.values('status').annotate(count=Count('id'))
        
        # Revenue this month
        current_month = timezone.now().replace(day=1)
        monthly_revenue = Payment.objects.filter(
            status='completed',
            paid_at__gte=current_month
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Popular plans
        popular_plans = SubscriptionPlan.objects.annotate(
            active_subs=Count('subscription', filter=Q(subscription__status__in=['active', 'trial']))
        ).order_by('-active_subs')[:5]
        
        extra_context.update({
            'status_counts': list(status_counts),
            'monthly_revenue': monthly_revenue,
            'popular_plans': popular_plans,
        })
        
        return super().changelist_view(request, extra_context)

# Custom admin site configuration
admin.site.site_header = "Autowash Subscriptions"
admin.site.site_title = "Subscriptions"
admin.site.index_title = "Subscription Management"