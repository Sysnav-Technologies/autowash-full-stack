"""
Tenant Admin Configuration
Individual admin interfaces for each tenant/business
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.urls import reverse


def setup_tenant_admin():
    """Setup admin for tenant-specific models"""
    
    # Import tenant-specific models
    try:
        from apps.businesses.models import Business, BusinessSettings
        from apps.employees.models import Employee, EmployeeRole
        from apps.customers.models import Customer, CustomerGroup
        from apps.services.models import Service, ServiceCategory, Package
        from apps.inventory.models import Product, ProductCategory, Stock
        from apps.payments.models import Payment, PaymentMethod
        from apps.expenses.models import Expense, ExpenseCategory
        from apps.reports.models import Report
    except ImportError:
        # Handle case where models don't exist yet
        pass
    
    # Business Admin
    try:
        @admin.register(Business)
        class BusinessAdmin(admin.ModelAdmin):
            """Admin for business settings in tenant"""
            
            list_display = ('name', 'business_type', 'is_active', 'created_at')
            list_filter = ('business_type', 'is_active', 'created_at')
            search_fields = ('name', 'email', 'phone_number')
            
            fieldsets = (
                ('Basic Information', {
                    'fields': ('name', 'description', 'business_type')
                }),
                ('Contact Information', {
                    'fields': ('email', 'phone_number', 'address', 'city', 'state', 'country', 'postal_code')
                }),
                ('Business Details', {
                    'fields': ('registration_number', 'tax_number', 'opening_time', 'closing_time')
                }),
                ('Settings', {
                    'fields': ('timezone', 'currency', 'language')
                }),
                ('Status', {
                    'fields': ('is_active', 'logo')
                })
            )
    except:
        pass
    
    # Employee Admin
    try:
        @admin.register(Employee)
        class EmployeeAdmin(admin.ModelAdmin):
            """Admin for employees in tenant"""
            
            list_display = ('user', 'role', 'is_active', 'hire_date', 'phone_number')
            list_filter = ('role', 'is_active', 'hire_date', 'department')
            search_fields = ('user__username', 'user__first_name', 'user__last_name', 'user__email', 'phone_number')
            
            fieldsets = (
                ('User Information', {
                    'fields': ('user', 'employee_id')
                }),
                ('Employment Details', {
                    'fields': ('role', 'department', 'hire_date', 'salary', 'commission_rate')
                }),
                ('Contact Information', {
                    'fields': ('phone_number', 'address', 'emergency_contact_name', 'emergency_contact_phone')
                }),
                ('Status', {
                    'fields': ('is_active', 'photo')
                })
            )
    except:
        pass
    
    # Customer Admin
    try:
        @admin.register(Customer)
        class CustomerAdmin(admin.ModelAdmin):
            """Admin for customers in tenant"""
            
            list_display = ('full_name', 'email', 'phone_number', 'customer_group', 'total_visits', 'created_at')
            list_filter = ('customer_group', 'created_at', 'gender')
            search_fields = ('first_name', 'last_name', 'email', 'phone_number', 'license_plate')
            
            fieldsets = (
                ('Personal Information', {
                    'fields': ('first_name', 'last_name', 'email', 'phone_number', 'date_of_birth', 'gender')
                }),
                ('Vehicle Information', {
                    'fields': ('license_plate', 'vehicle_make', 'vehicle_model', 'vehicle_year', 'vehicle_color')
                }),
                ('Customer Details', {
                    'fields': ('customer_group', 'address', 'notes')
                }),
                ('Status', {
                    'fields': ('is_active', 'photo')
                })
            )
    except:
        pass
    
    # Service Admin
    try:
        @admin.register(Service)
        class ServiceAdmin(admin.ModelAdmin):
            """Admin for services in tenant"""
            
            list_display = ('name', 'category', 'price', 'duration', 'is_active')
            list_filter = ('category', 'is_active', 'created_at')
            search_fields = ('name', 'description')
            
            fieldsets = (
                ('Service Information', {
                    'fields': ('name', 'description', 'category')
                }),
                ('Pricing & Duration', {
                    'fields': ('price', 'duration', 'commission_rate')
                }),
                ('Status', {
                    'fields': ('is_active', 'image')
                })
            )
    except:
        pass
    
    # Product/Inventory Admin
    try:
        @admin.register(Product)
        class ProductAdmin(admin.ModelAdmin):
            """Admin for inventory products in tenant"""
            
            list_display = ('name', 'category', 'quantity', 'price', 'low_stock_threshold', 'is_active')
            list_filter = ('category', 'is_active', 'created_at')
            search_fields = ('name', 'sku', 'description')
            
            fieldsets = (
                ('Product Information', {
                    'fields': ('name', 'description', 'category', 'sku')
                }),
                ('Inventory', {
                    'fields': ('quantity', 'low_stock_threshold', 'unit_of_measure')
                }),
                ('Pricing', {
                    'fields': ('cost_price', 'selling_price', 'price')
                }),
                ('Status', {
                    'fields': ('is_active', 'image')
                })
            )
    except:
        pass
    
    # Payment Admin
    try:
        @admin.register(Payment)
        class PaymentAdmin(admin.ModelAdmin):
            """Admin for payments in tenant"""
            
            list_display = ('payment_id', 'customer', 'amount', 'method', 'status', 'created_at')
            list_filter = ('method', 'status', 'created_at')
            search_fields = ('payment_id', 'customer__first_name', 'customer__last_name', 'reference_number')
            readonly_fields = ('payment_id', 'created_at')
            
            fieldsets = (
                ('Payment Information', {
                    'fields': ('payment_id', 'customer', 'amount', 'method')
                }),
                ('Transaction Details', {
                    'fields': ('reference_number', 'mpesa_code', 'notes')
                }),
                ('Status', {
                    'fields': ('status', 'created_at')
                })
            )
    except:
        pass
    
    # Expense Admin
    try:
        @admin.register(Expense)
        class ExpenseAdmin(admin.ModelAdmin):
            """Admin for expenses in tenant"""
            
            list_display = ('description', 'category', 'amount', 'date', 'employee')
            list_filter = ('category', 'date', 'employee')
            search_fields = ('description', 'notes')
            
            fieldsets = (
                ('Expense Information', {
                    'fields': ('description', 'category', 'amount', 'date')
                }),
                ('Details', {
                    'fields': ('employee', 'notes', 'receipt')
                })
            )
    except:
        pass
    
    # Customize tenant admin site
    admin.site.site_header = 'Business Management'
    admin.site.site_title = 'Business Admin'
    admin.site.index_title = 'Business Administration'


# Call setup function
setup_tenant_admin()
