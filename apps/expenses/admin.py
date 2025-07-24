from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Sum
from django.utils import timezone
from .models import (
    ExpenseCategory, Vendor, Expense, ExpenseApproval,
    RecurringExpense, ExpenseBudget
)


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'total_expenses_display', 'is_active', 'is_auto_category', 'created_at')
    list_filter = ('is_active', 'is_auto_category', 'parent')
    search_fields = ('name', 'description')
    ordering = ('name',)
    list_editable = ('is_active',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'parent')
        }),
        ('Settings', {
            'fields': ('is_active', 'is_auto_category')
        }),
    )
    
    def total_expenses_display(self, obj):
        total = obj.total_expenses
        return format_html('<span class="text-danger">${:,.2f}</span>', total)
    total_expenses_display.short_description = 'Total Expenses'


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'email', 'phone', 'total_expenses_display', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'contact_person', 'email', 'phone')
    ordering = ('name',)
    list_editable = ('is_active',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'contact_person', 'email', 'phone', 'address')
        }),
        ('Financial Information', {
            'fields': ('tax_number', 'bank_account', 'payment_terms')
        }),
        ('Settings', {
            'fields': ('is_active',)
        }),
    )
    
    def total_expenses_display(self, obj):
        total = obj.total_expenses
        return format_html('<span class="text-danger">${:,.2f}</span>', total)
    total_expenses_display.short_description = 'Total Expenses'


class ExpenseApprovalInline(admin.TabularInline):
    model = ExpenseApproval
    extra = 0
    readonly_fields = ('approved_at',)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'category', 'vendor', 'amount_display', 'total_amount_display',
        'expense_date', 'status', 'expense_type', 'is_overdue_display', 'created_at'
    )
    list_filter = (
        'status', 'expense_type', 'payment_method', 'is_recurring',
        'category', 'vendor', 'expense_date', 'created_at'
    )
    search_fields = ('title', 'description', 'reference_number', 'receipt_number')
    ordering = ('-expense_date', '-created_at')
    list_editable = ('status',)
    date_hierarchy = 'expense_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'category', 'vendor', 'expense_type')
        }),
        ('Financial Details', {
            'fields': ('amount', 'tax_amount', 'total_amount')
        }),
        ('Dates', {
            'fields': ('expense_date', 'due_date', 'paid_date')
        }),
        ('Payment Information', {
            'fields': ('payment_method', 'reference_number', 'receipt_number')
        }),
        ('Status & Approval', {
            'fields': ('status', 'approved_by_user_id', 'approved_at')
        }),
        ('Recurring Settings', {
            'fields': ('is_recurring', 'recurring_frequency'),
            'classes': ('collapse',)
        }),
        ('Linking Information', {
            'fields': (
                'linked_inventory_item_id', 'linked_employee_id',
                'linked_service_id', 'linked_supplier_id'
            ),
            'classes': ('collapse',)
        }),
        ('Additional Information', {
            'fields': ('notes', 'attachments', 'is_active'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('total_amount', 'approved_at')
    inlines = [ExpenseApprovalInline]
    
    actions = ['approve_expenses', 'reject_expenses', 'mark_as_paid']
    
    def amount_display(self, obj):
        return format_html('<span class="text-danger">${:,.2f}</span>', obj.amount)
    amount_display.short_description = 'Amount'
    
    def total_amount_display(self, obj):
        return format_html('<strong class="text-danger">${:,.2f}</strong>', obj.total_amount)
    total_amount_display.short_description = 'Total Amount'
    
    def status_display(self, obj):
        colors = {
            'pending': 'warning',
            'approved': 'info',
            'paid': 'success',
            'rejected': 'danger',
            'cancelled': 'secondary'
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def is_overdue_display(self, obj):
        if obj.is_overdue:
            return format_html('<span class="text-danger">⚠️ Overdue</span>')
        return '✅'
    is_overdue_display.short_description = 'Due Status'
    
    def approve_expenses(self, request, queryset):
        updated = queryset.filter(status='pending').update(
            status='approved',
            approved_by_user_id=request.user.id,
            approved_at=timezone.now()
        )
        self.message_user(request, f'{updated} expenses approved successfully.')
    approve_expenses.short_description = 'Approve selected expenses'
    
    def reject_expenses(self, request, queryset):
        updated = queryset.filter(status='pending').update(status='rejected')
        self.message_user(request, f'{updated} expenses rejected.')
    reject_expenses.short_description = 'Reject selected expenses'
    
    def mark_as_paid(self, request, queryset):
        updated = queryset.filter(status__in=['approved', 'pending']).update(
            status='paid',
            paid_date=timezone.now().date()
        )
        self.message_user(request, f'{updated} expenses marked as paid.')
    mark_as_paid.short_description = 'Mark selected expenses as paid'


@admin.register(ExpenseApproval)
class ExpenseApprovalAdmin(admin.ModelAdmin):
    list_display = ('expense', 'approver_display', 'status', 'approved_at', 'created_at')
    list_filter = ('status', 'approved_at', 'created_at')
    search_fields = ('expense__title', 'comments')
    ordering = ('-created_at',)
    
    def approver_display(self, obj):
        return f"User ID: {obj.approver_user_id}"
    approver_display.short_description = 'Approver'


@admin.register(RecurringExpense)
class RecurringExpenseAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'category', 'vendor', 'amount_display',
        'frequency', 'next_due_date', 'is_active', 'auto_approve'
    )
    list_filter = ('frequency', 'is_active', 'auto_approve', 'category')
    search_fields = ('title',)
    ordering = ('next_due_date',)
    list_editable = ('is_active', 'auto_approve')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'category', 'vendor', 'amount')
        }),
        ('Recurrence Settings', {
            'fields': ('frequency', 'start_date', 'end_date', 'next_due_date')
        }),
        ('Options', {
            'fields': ('is_active', 'auto_approve')
        }),
    )
    
    readonly_fields = ('next_due_date',)
    
    def amount_display(self, obj):
        return format_html('<span class="text-danger">${:,.2f}</span>', obj.amount)
    amount_display.short_description = 'Amount'
    
    actions = ['generate_next_expenses']
    
    def generate_next_expenses(self, request, queryset):
        generated = 0
        for recurring_expense in queryset.filter(is_active=True):
            if recurring_expense.next_due_date <= timezone.now().date():
                expense = recurring_expense.generate_next_expense()
                if expense:
                    generated += 1
        
        self.message_user(request, f'{generated} expenses generated from recurring templates.')
    generate_next_expenses.short_description = 'Generate next expenses from selected templates'


@admin.register(ExpenseBudget)
class ExpenseBudgetAdmin(admin.ModelAdmin):
    list_display = (
        'category', 'period_display', 'budgeted_amount_display',
        'spent_amount_display', 'remaining_amount_display',
        'utilization_display', 'is_over_budget_display'
    )
    list_filter = ('year', 'month', 'category')
    search_fields = ('category__name',)
    ordering = ('-year', '-month')
    
    fieldsets = (
        ('Budget Information', {
            'fields': ('category', 'year', 'month', 'budgeted_amount')
        }),
        ('Tracking', {
            'fields': ('spent_amount',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('spent_amount',)
    
    def period_display(self, obj):
        if obj.month:
            return f"{obj.month:02d}/{obj.year}"
        return f"Year {obj.year}"
    period_display.short_description = 'Period'
    
    def budgeted_amount_display(self, obj):
        return format_html('<span class="text-primary">${:,.2f}</span>', obj.budgeted_amount)
    budgeted_amount_display.short_description = 'Budgeted'
    
    def spent_amount_display(self, obj):
        return format_html('<span class="text-danger">${:,.2f}</span>', obj.spent_amount)
    spent_amount_display.short_description = 'Spent'
    
    def remaining_amount_display(self, obj):
        remaining = obj.remaining_amount
        color = 'success' if remaining >= 0 else 'danger'
        return format_html('<span class="text-{}">${:,.2f}</span>', color, remaining)
    remaining_amount_display.short_description = 'Remaining'
    
    def utilization_display(self, obj):
        percentage = obj.utilization_percentage
        if percentage <= 70:
            color = 'success'
        elif percentage <= 90:
            color = 'warning'
        else:
            color = 'danger'
        
        return format_html(
            '<span class="text-{}">{:.1f}%</span>',
            color, percentage
        )
    utilization_display.short_description = 'Utilization'
    
    def is_over_budget_display(self, obj):
        if obj.is_over_budget:
            return format_html('<span class="text-danger">⚠️ Over Budget</span>')
        return '✅'
    is_over_budget_display.short_description = 'Budget Status'
