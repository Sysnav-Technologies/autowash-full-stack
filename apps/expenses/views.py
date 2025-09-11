import csv
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.db import transaction
from django.db.models import Q, Count, Sum, Avg, F
from django.utils import timezone
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.urls import reverse
from decimal import Decimal
from datetime import datetime, timedelta
import json
import uuid

from apps.core.decorators import employee_required, ajax_required
from .models import (
    Expense, ExpenseCategory, Vendor, RecurringExpense, 
    ExpenseBudget, ExpenseApproval
)
from .forms import (
    ExpenseForm, ExpenseSearchForm, VendorForm, ExpenseCategoryForm,
    RecurringExpenseForm, ExpenseBudgetForm, ExpenseApprovalForm,
    BulkExpenseActionForm
)


def get_expense_urls(request):
    """Generate all expense URLs for templates with tenant slug."""
    tenant_slug = request.tenant.slug
    base_url = f"/business/{tenant_slug}/expenses"
    
    return {
        # Main URLs
        'dashboard': f"{base_url}/",
        'list': f"{base_url}/list/",
        'create': f"{base_url}/create/",
        'detail': f"{base_url}/{{}}/" ,  # Use string formatting in template
        'edit': f"{base_url}/{{}}/edit/",
        'delete': f"{base_url}/{{}}/delete/",
        'approve': f"{base_url}/{{}}/approve/",
        'pay': f"{base_url}/{{}}/pay/",
        'bulk_action': f"{base_url}/bulk-action/",
        
        # Vendor URLs
        'vendor_list': f"{base_url}/vendors/",
        'vendor_create': f"{base_url}/vendors/create/",
        'vendor_detail': f"{base_url}/vendors/{{}}/",
        'vendor_edit': f"{base_url}/vendors/{{}}/edit/",
        'vendor_delete': f"{base_url}/vendors/{{}}/delete/",
        
        # Category URLs  
        'category_list': f"{base_url}/categories/",
        'category_create': f"{base_url}/categories/create/",
        'category_edit': f"{base_url}/categories/{{}}/edit/",
        'category_delete': f"{base_url}/categories/{{}}/delete/",
        
        # Recurring URLs
        'recurring_list': f"{base_url}/recurring/",
        'recurring_create': f"{base_url}/recurring/create/",
        'recurring_edit': f"{base_url}/recurring/{{}}/edit/",
        'recurring_delete': f"{base_url}/recurring/{{}}/delete/",
        
        # Budget URLs
        'budget_list': f"{base_url}/budgets/",
        'budget_create': f"{base_url}/budgets/create/",
        'budget_edit': f"{base_url}/budgets/{{}}/edit/",
        'budget_delete': f"{base_url}/budgets/{{}}/delete/",
        
        # Utility URLs
        'reports': f"{base_url}/reports/",
        'export': f"{base_url}/export/",
        'auto_link_inventory': f"{base_url}/auto-link/inventory/",
        'auto_link_salaries': f"{base_url}/auto-link/salaries/",
        'auto_link_commissions': f"{base_url}/auto-link/commissions/",
        
        # Navigation
        'businesses_dashboard': f"/business/{tenant_slug}/dashboard/",
    }


def tenant_redirect(request, view_name, **kwargs):
    """Helper function to redirect to tenant-aware URLs"""
    tenant_slug = request.tenant.slug
    base_url = f"/business/{tenant_slug}/expenses"
    
    # Map old URL names to tenant-aware paths
    url_mapping = {
        'expenses:dashboard': f"{base_url}/",
        'expenses:list': f"{base_url}/",
        'expenses:create': f"{base_url}/create/",
        'expenses:detail': f"{base_url}/{{pk}}/",
        'expenses:edit': f"{base_url}/{{pk}}/edit/",
        'expenses:delete': f"{base_url}/{{pk}}/delete/",
        'expenses:vendor_list': f"{base_url}/vendors/",
        'expenses:vendor_create': f"{base_url}/vendors/create/",
        'expenses:vendor_detail': f"{base_url}/vendors/{{pk}}/",
        'expenses:vendor_edit': f"{base_url}/vendors/{{pk}}/edit/",
        'expenses:vendor_delete': f"{base_url}/vendors/{{pk}}/delete/",
        'expenses:category_list': f"{base_url}/categories/",
        'expenses:category_create': f"{base_url}/categories/create/",
        'expenses:category_edit': f"{base_url}/categories/{{pk}}/edit/",
        'expenses:category_delete': f"{base_url}/categories/{{pk}}/delete/",
        'expenses:recurring_list': f"{base_url}/recurring/",
        'expenses:recurring_create': f"{base_url}/recurring/create/",
        'expenses:recurring_edit': f"{base_url}/recurring/{{pk}}/edit/",
        'expenses:recurring_delete': f"{base_url}/recurring/{{pk}}/delete/",
        'expenses:budget_list': f"{base_url}/budgets/",
        'expenses:budget_create': f"{base_url}/budgets/create/",
        'expenses:budget_edit': f"{base_url}/budgets/{{pk}}/edit/",
        'expenses:budget_delete': f"{base_url}/budgets/{{pk}}/delete/",
    }
    
    if view_name in url_mapping:
        url = url_mapping[view_name]
        # Format with any provided kwargs (like pk)
        if kwargs:
            url = url.format(**kwargs)
        return redirect(url)
    else:
        # Fallback to dashboard if URL not found
        return redirect(f"{base_url}/")


@employee_required()
@login_required
def expense_dashboard_view(request):
    """Expense dashboard with overview and statistics"""
    
    # Get date ranges
    today = timezone.now().date()
    this_month_start = today.replace(day=1)
    last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)
    this_year_start = today.replace(month=1, day=1)
    
    # Basic stats
    stats = {
        # Total expenses
        'total_expenses': Expense.objects.filter(is_active=True).aggregate(
            total=Sum('total_amount')
        )['total'] or Decimal('0.00'),
        
        # This month expenses
        'this_month_expenses': Expense.objects.filter(
            expense_date__gte=this_month_start,
            is_active=True
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00'),
        
        # Pending approvals
        'pending_approvals': Expense.objects.filter(
            status='pending',
            is_active=True
        ).count(),
        
        # Overdue expenses
        'overdue_expenses': Expense.objects.filter(
            due_date__lt=today,
            status__in=['pending', 'approved'],
            is_active=True
        ).count(),
        
        # Categories count
        'total_categories': ExpenseCategory.objects.filter(is_active=True).count(),
        
        # Vendors count
        'total_vendors': Vendor.objects.filter(is_active=True).count(),
    }
    
    # Monthly trend (last 6 months)
    monthly_data = []
    for i in range(6):
        month_start = (this_month_start - timedelta(days=i*30)).replace(day=1)
        next_month = (month_start + timedelta(days=32)).replace(day=1)
        
        month_expenses = Expense.objects.filter(
            expense_date__gte=month_start,
            expense_date__lt=next_month,
            is_active=True
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        
        monthly_data.append({
            'month': month_start.strftime('%b %Y'),
            'amount': float(month_expenses)
        })
    
    monthly_data.reverse()
    
    # Top categories by spending
    top_categories = ExpenseCategory.objects.filter(
        is_active=True,
        expenses__expense_date__gte=this_month_start,
        expenses__is_active=True
    ).annotate(
        total_spent=Sum('expenses__total_amount')
    ).order_by('-total_spent')[:5]
    
    # Recent expenses
    recent_expenses = Expense.objects.filter(
        is_active=True
    ).select_related('category', 'vendor').order_by('-created_at')[:10]
    
    # Pending approvals
    pending_expenses = Expense.objects.filter(
        status='pending',
        is_active=True
    ).select_related('category', 'vendor').order_by('expense_date')[:5]
    
    # Budget status
    current_budgets = ExpenseBudget.objects.filter(
        year=today.year,
        month=today.month
    ).select_related('category')
    
    context = {
        'stats': stats,
        'monthly_data': monthly_data,
        'top_categories': top_categories,
        'recent_expenses': recent_expenses,
        'pending_expenses': pending_expenses,
        'current_budgets': current_budgets,
        'urls': get_expense_urls(request),
        'title': 'Expense Dashboard'
    }
    
    return render(request, 'expenses/dashboard.html', context)


@employee_required()
@login_required
def expense_list_view(request):
    """List all expenses with filtering and pagination"""
    
    # Base queryset
    expenses = Expense.objects.filter(is_active=True).select_related('category', 'vendor')
    
    # Filter by status
    status_filter = request.GET.get('status', 'all')
    if status_filter and status_filter != 'all':
        expenses = expenses.filter(status=status_filter)
    
    # Filter for attendants (only their own expenses)
    if hasattr(request, 'employee') and request.employee.role == 'attendant':
        expenses = expenses.filter(created_by_user_id=request.user.id)
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        expenses = expenses.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(category__name__icontains=search_query) |
            Q(vendor__name__icontains=search_query)
        )
    
    # Order by date
    expenses = expenses.order_by('-expense_date', '-created_at')
    
    # Pagination
    paginator = Paginator(expenses, 25)
    page_number = request.GET.get('page')
    expenses_page = paginator.get_page(page_number)
    
    context = {
        'expenses': expenses_page,
        'title': 'All Expenses',
        'urls': get_expense_urls(request),
        'status_filter': status_filter,
        'search_query': search_query,
    }
    
    return render(request, 'expenses/expense_list.html', context)


@employee_required()
@login_required
def expense_create_view(request):
    """Create new expense with approval workflow for attendants"""
    
    if request.method == 'POST':
        form = ExpenseForm(request.POST, user=request.user)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.set_created_by(request.user)
            
            # Calculate total amount (this should be done in model save method)
            expense.total_amount = expense.amount + (expense.tax_amount or Decimal('0.00'))
            
            # All expenses start as pending - no auto-approval
            expense.status = 'pending'
            
            expense.save()
            
            messages.success(request, f'Expense "{expense.title}" recorded successfully and sent for approval.')
            
            return redirect(f'/business/{request.tenant.slug}/expenses/')
    else:
        form = ExpenseForm(user=request.user)
    
    context = {
        'form': form,
        'title': 'Record Expense' if hasattr(request, 'employee') and request.employee.role == 'attendant' else 'Create Expense',
        'urls': get_expense_urls(request),
        'is_attendant': hasattr(request, 'employee') and request.employee.role == 'attendant',
    }
    
    return render(request, 'expenses/expense_form.html', context)


@employee_required(['owner', 'manager', 'supervisor'])
def expense_approval_list_view(request):
    """List expenses pending approval"""
    
    pending_expenses = Expense.objects.filter(
        status='pending',
        is_active=True
    ).select_related('category', 'vendor').order_by('-created_at')
    
    print(f"DEBUG: Found {pending_expenses.count()} pending expenses")
    for expense in pending_expenses[:5]:  # Show first 5
        print(f"DEBUG: Expense {expense.pk} - Status: {expense.status}, Title: {expense.title}")
    
    # Pagination
    paginator = Paginator(pending_expenses, 25)
    page_number = request.GET.get('page')
    expenses = paginator.get_page(page_number)
    
    context = {
        'expenses': expenses,
        'title': 'Pending Expense Approvals',
        'urls': get_expense_urls(request),
        'total_pending': pending_expenses.count(),
    }
    
    return render(request, 'expenses/approval_list.html', context)


@require_POST
@require_POST
@employee_required(['owner', 'manager', 'supervisor'])
def expense_approve_view(request, pk):
    """Approve an expense"""
    
    print(f"DEBUG: APPROVAL VIEW CALLED - PK: {pk}")
    
    expense = get_object_or_404(Expense, pk=pk, is_active=True)
    
    print(f"DEBUG: Found expense {expense.pk}, status: {expense.status}")
    
    if expense.status != 'pending':
        print(f"DEBUG: Expense already processed with status: {expense.status}")
        messages.error(request, f'This expense has already been processed. Current status: {expense.status}')
        return redirect(f'/business/{request.tenant.slug}/expenses/approvals/')
    
    print(f"DEBUG: Updating expense to approved")
    expense.status = 'approved'
    expense.approved_by_user_id = request.user.id
    expense.approved_at = timezone.now()
    expense.save()
    
    print(f"DEBUG: Expense saved successfully")
    messages.success(request, f'Expense "{expense.title}" has been approved.')
    return redirect(f'/business/{request.tenant.slug}/expenses/approvals/')


@require_POST
@employee_required(['owner', 'manager', 'supervisor'])
def expense_reject_view(request, pk):
    """Reject an expense"""
    
    expense = get_object_or_404(Expense, pk=pk, is_active=True)
    
    if expense.status != 'pending':
        messages.error(request, 'This expense has already been processed.')
        return redirect(f'/business/{request.tenant.slug}/expenses/approvals/')
    
    expense.status = 'rejected'
    expense.save()
    
    messages.success(request, f'Expense "{expense.title}" has been rejected.')
    return redirect(f'/business/{request.tenant.slug}/expenses/approvals/')


@employee_required(['attendant'])
def attendant_my_expenses_view(request):
    """View attendant's own expenses"""
    
    my_expenses = Expense.objects.filter(
        created_by_user_id=request.user.id,
        is_active=True
    ).select_related('category', 'vendor').order_by('-created_at')
    
    # Status filter
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        my_expenses = my_expenses.filter(status=status_filter)
    
    # Pagination
    paginator = Paginator(my_expenses, 25)
    page_number = request.GET.get('page')
    expenses = paginator.get_page(page_number)
    
    # Stats
    stats = {
        'total': my_expenses.count(),
        'pending': my_expenses.filter(status='pending').count(),
        'approved': my_expenses.filter(status='approved').count(),
        'rejected': my_expenses.filter(status='rejected').count(),
        'total_amount': my_expenses.filter(status='approved').aggregate(
            total=Sum('total_amount')
        )['total'] or Decimal('0.00')
    }
    
    context = {
        'expenses': expenses,
        'title': 'My Expenses',
        'urls': get_expense_urls(request),
        'stats': stats,
        'status_filter': status_filter,
        'status_choices': Expense.STATUS_CHOICES,
    }
    
    return render(request, 'expenses/my_expenses.html', context)


@employee_required()
@login_required
def expense_edit_view(request, pk):
    """Edit expense with role-based permissions and status checks"""
    
    expense = get_object_or_404(Expense, pk=pk, is_active=True)
    
    # Check permissions based on role and status
    can_edit = False
    edit_reason = ""
    
    if request.employee.role == 'owner':
        # Owners can edit any expense except paid ones
        can_edit = expense.status != 'paid'
        edit_reason = "Owners cannot edit paid expenses"
    elif request.employee.role in ['manager', 'supervisor']:
        # Managers can edit pending and approved expenses they didn't create
        can_edit = expense.status in ['pending', 'approved']
        edit_reason = "Managers can only edit pending or approved expenses"
    elif request.employee.role == 'attendant':
        # Attendants can only edit their own pending expenses
        can_edit = (expense.created_by_user_id == request.user.id and 
                   expense.status == 'pending')
        edit_reason = "You can only edit your own pending expenses"
    else:
        edit_reason = "You do not have permission to edit expenses"
    
    if not can_edit:
        messages.error(request, edit_reason)
        return redirect(f'/business/{request.tenant.slug}/expenses/{pk}/')
    
    if request.method == 'POST':
        form = ExpenseForm(request.POST, instance=expense, user=request.user)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.set_updated_by(request.user)
            
            # Calculate total amount
            expense.total_amount = expense.amount + (expense.tax_amount or Decimal('0.00'))
            
            # Handle status changes based on role and current status
            if expense.status == 'approved' and request.employee.role in ['manager', 'supervisor']:
                # If manager/supervisor edits approved expense, reset to pending for re-approval
                if request.employee.role != 'owner':
                    expense.status = 'pending'
                    expense.approved_by_user_id = None
                    expense.approved_at = None
                    messages.info(request, 'Expense has been reset to pending status for re-approval.')
            
            expense.save()
            
            messages.success(request, f'Expense "{expense.title}" updated successfully.')
            return redirect(f'/business/{request.tenant.slug}/expenses/{pk}/')
    else:
        form = ExpenseForm(instance=expense, user=request.user)
    
    context = {
        'form': form,
        'expense': expense,
        'title': f'Edit Expense - {expense.title}',
        'urls': get_expense_urls(request),
        'can_edit': can_edit,
    }
    
    return render(request, 'expenses/expense_edit.html', context)


@login_required
@employee_required(['owner', 'manager', 'supervisor'])
def expense_detail_view(request, pk):
    """View expense details"""
    
    expense = get_object_or_404(
        Expense.objects.select_related('category', 'vendor'),
        pk=pk,
        is_active=True
    )
    
    # Check if attendant can view this expense
    if (request.employee.role == 'attendant' and 
        expense.created_by_user_id != request.user.id):
        messages.error(request, 'You can only view your own expenses.')
        return redirect(f'/business/{request.tenant.slug}/expenses/my-expenses/')
    
    # Check permissions for editing
    can_edit = False
    edit_reason = ""
    
    if request.employee.role == 'owner':
        # Owners can edit any expense except paid ones
        can_edit = expense.status != 'paid'
        edit_reason = "Cannot edit paid expenses"
    elif request.employee.role in ['manager', 'supervisor']:
        # Managers can edit pending and approved expenses (with re-approval logic)
        can_edit = expense.status in ['pending', 'approved']
        edit_reason = "Managers can only edit pending or approved expenses"
    elif request.employee.role == 'attendant':
        # Attendants can only edit their own pending expenses
        can_edit = (expense.created_by_user_id == request.user.id and 
                   expense.status == 'pending')
        edit_reason = "You can only edit your own pending expenses"
    else:
        edit_reason = "You do not have permission to edit expenses"
    
    # Get approval history
    approvals = expense.approvals.all().order_by('-created_at')
    
    # Get approver information if expense is approved
    approver_name = None
    if expense.approved_by_user_id:
        try:
            from django.contrib.auth.models import User
            approver_user = User.objects.get(id=expense.approved_by_user_id)
            try:
                from apps.employees.models import Employee
                approver_employee = Employee.objects.get(user_id=approver_user.id)
                approver_name = approver_employee.full_name
            except Employee.DoesNotExist:
                approver_name = approver_user.get_full_name() or approver_user.username
        except User.DoesNotExist:
            approver_name = "Unknown User"
    
    context = {
        'expense': expense,
        'approvals': approvals,
        'urls': get_expense_urls(request),
        'title': f'Expense - {expense.title}',
        'can_edit': can_edit,
        'edit_reason': edit_reason,
        'approver_name': approver_name,
    }
    
    return render(request, 'expenses/expense_detail.html', context)


@employee_required()
@login_required
@employee_required(['owner', 'manager', 'supervisor'])
@employee_required()
@require_POST
@login_required
@employee_required(['owner', 'manager'])
def expense_delete_view(request, pk):
    """Soft delete expense"""
    
    expense = get_object_or_404(Expense, pk=pk, is_active=True)
    expense.is_active = False
    expense.set_updated_by(request.user)
    expense.save()
    
    messages.success(request, f'Expense "{expense.title}" deleted successfully.')
    return tenant_redirect(request, 'expenses:list')





@employee_required()
@require_POST
@login_required
@employee_required(['owner', 'manager'])
def expense_pay_view(request, pk):
    """Mark expense as paid"""
    
    expense = get_object_or_404(Expense, pk=pk, is_active=True)
    
    if expense.status in ['approved', 'pending']:
        expense.status = 'paid'
        expense.paid_date = timezone.now().date()
        expense.set_updated_by(request.user)
        expense.save()
        
        messages.success(request, f'Expense "{expense.title}" marked as paid.')
    else:
        messages.error(request, 'Expense cannot be marked as paid in its current status.')
    
    return tenant_redirect(request, 'expenses:detail', pk=expense.pk)


@employee_required()
@require_POST
@login_required
@employee_required(['owner', 'manager'])
def expense_bulk_action_view(request):
    """Handle bulk actions on expenses"""
    
    form = BulkExpenseActionForm(request.POST)
    if form.is_valid():
        action = form.cleaned_data['action']
        comments = form.cleaned_data['comments']
        expense_ids = request.POST.getlist('expense_ids')
        
        if not expense_ids:
            messages.error(request, 'No expenses selected.')
            return tenant_redirect(request, 'expenses:list')
        
        expenses = Expense.objects.filter(
            id__in=expense_ids,
            is_active=True
        )
        
        if action == 'approve':
            updated = expenses.filter(status='pending').update(
                status='approved',
                approved_by_user_id=request.user.id,
                approved_at=timezone.now()
            )
            messages.success(request, f'{updated} expenses approved.')
            
        elif action == 'reject':
            updated = expenses.filter(status='pending').update(status='rejected')
            messages.success(request, f'{updated} expenses rejected.')
            
        elif action == 'mark_paid':
            updated = expenses.filter(status__in=['approved', 'pending']).update(
                status='paid',
                paid_date=timezone.now().date()
            )
            messages.success(request, f'{updated} expenses marked as paid.')
            
        elif action == 'delete':
            updated = expenses.update(is_active=False)
            messages.success(request, f'{updated} expenses deleted.')
    
    return tenant_redirect(request, 'expenses:list')


# Vendor Views
@employee_required()
@login_required
@employee_required(['owner', 'manager', 'supervisor'])
def vendor_list_view(request):
    """List all vendors"""
    
    vendors = Vendor.objects.filter(is_active=True).annotate(
        expense_count=Count('expenses'),
        total_expense_amount=Sum('expenses__total_amount')
    ).order_by('name')
    
    context = {
        'vendors': vendors,
        'title': 'Vendors',
        'urls': get_expense_urls(request),
    }
    
    return render(request, 'expenses/vendor_list.html', context)


@employee_required()
@login_required
@employee_required(['owner', 'manager', 'supervisor'])
def vendor_create_view(request):
    """Create new vendor"""
    
    if request.method == 'POST':
        form = VendorForm(request.POST)
        if form.is_valid():
            vendor = form.save(commit=False)
            vendor.set_created_by(request.user)
            vendor.save()
            
            messages.success(request, f'Vendor "{vendor.name}" created successfully.')
            return tenant_redirect(request, 'expenses:vendor_detail', pk=vendor.pk)
    else:
        form = VendorForm()
    
    context = {
        'form': form,
        'title': 'Create Vendor',
        'urls': get_expense_urls(request),
    }
    
    return render(request, 'expenses/vendor_form.html', context)


@login_required
@employee_required(['owner', 'manager', 'supervisor'])
def vendor_detail_view(request, pk):
    """View vendor details"""
    
    vendor = get_object_or_404(Vendor, pk=pk, is_active=True)
    
    # Get vendor expenses
    expenses = vendor.expenses.filter(is_active=True).order_by('-expense_date')[:10]
    
    # Get vendor stats
    stats = vendor.expenses.filter(is_active=True).aggregate(
        total_expenses=Sum('amount'),
        expense_count=Count('id'),
        avg_expense=Avg('amount')
    )
    
    context = {
        'vendor': vendor,
        'recent_expenses': expenses,
        'total_expenses': stats['total_expenses'] or 0,
        'expense_count': stats['expense_count'] or 0,
        'business': request.tenant,
        'urls': get_expense_urls(request),
        'title': f'Vendor - {vendor.name}'
    }
    
    return render(request, 'expenses/vendor_detail.html', context)


# Auto-linking functions for integration with other apps
def create_inventory_expense(inventory_item, purchase_amount, purchase_date, supplier=None):
    """Create expense automatically when inventory is purchased"""
    try:
        # Get or create inventory category
        category, created = ExpenseCategory.objects.get_or_create(
            name='Inventory Purchases',
            defaults={
                'description': 'Automatic expenses for inventory purchases',
                'is_auto_category': True
            }
        )
        
        # Get or create vendor from supplier
        vendor = None
        if supplier:
            vendor, created = Vendor.objects.get_or_create(
                name=supplier.name,
                defaults={
                    'contact_person': supplier.contact_person or '',
                    'email': supplier.email or '',
                    'phone': supplier.phone or '',
                    'address': supplier.address or '',
                }
            )
        
        expense = Expense.objects.create(
            title=f'Inventory Purchase - {inventory_item.name}',
            description=f'Auto-generated expense for inventory purchase',
            category=category,
            vendor=vendor,
            amount=purchase_amount,
            total_amount=purchase_amount,
            expense_date=purchase_date,
            expense_type='inventory',
            status='approved',  # Auto-approve inventory expenses
            linked_inventory_item_id=inventory_item.id,
        )
        
        return expense
        
    except Exception as e:
        print(f"Error creating inventory expense: {e}")
        return None


def create_salary_expense(employee, salary_amount, pay_date):
    """Create expense automatically for employee salary"""
    try:
        # Get or create salary category
        category, created = ExpenseCategory.objects.get_or_create(
            name='Employee Salaries',
            defaults={
                'description': 'Automatic expenses for employee salaries',
                'is_auto_category': True
            }
        )
        
        expense = Expense.objects.create(
            title=f'Salary - {employee.full_name}',
            description=f'Monthly salary payment for {employee.full_name}',
            category=category,
            amount=salary_amount,
            total_amount=salary_amount,
            expense_date=pay_date,
            expense_type='salary',
            status='approved',
            linked_employee_id=employee.id,
        )
        
        return expense
        
    except Exception as e:
        print(f"Error creating salary expense: {e}")
        return None


def create_commission_expense(service_order_item):
    """Create expense automatically for service commission"""
    try:
        # Get or create commission category
        category, created = ExpenseCategory.objects.get_or_create(
            name='Service Commissions',
            defaults={
                'description': 'Automatic expenses for service commissions',
                'is_auto_category': True
            }
        )
        
        expense = Expense.objects.create(
            title=f'Commission - {service_order_item.service.name} by {service_order_item.assigned_to.full_name}',
            description=f'Service commission for {service_order_item.service.name} - Order #{service_order_item.order.order_number}',
            category=category,
            amount=service_order_item.commission_amount,
            total_amount=service_order_item.commission_amount,
            expense_date=service_order_item.completed_at.date() if service_order_item.completed_at else timezone.now().date(),
            expense_type='commission',
            status='approved',
            linked_service_id=service_order_item.service.id,
            linked_service_order_item_id=service_order_item.id,
            linked_employee_id=service_order_item.assigned_to.id,
        )
        
        return expense
        
    except Exception as e:
        print(f"Error creating commission expense: {e}")
        return None


def create_commission_expense_legacy(service, employee, commission_amount, service_date):
    """Legacy function - create expense for service commission (deprecated)"""
    try:
        # Get or create commission category
        category, created = ExpenseCategory.objects.get_or_create(
            name='Service Commissions',
            defaults={
                'description': 'Automatic expenses for service commissions',
                'is_auto_category': True
            }
        )
        
        expense = Expense.objects.create(
            title=f'Commission - {service.name} by {employee.full_name}',
            description=f'Service commission for {service.name}',
            category=category,
            amount=commission_amount,
            total_amount=commission_amount,
            expense_date=service_date,
            expense_type='commission',
            status='approved',
            linked_service_id=service.id,
            linked_employee_id=employee.id,
        )
        
        return expense
        
    except Exception as e:
        print(f"Error creating commission expense: {e}")
        return None


# Auto-linking utility views
@employee_required()
@require_POST
def auto_link_inventory_expenses(request):
    """Link inventory purchases to expenses"""
    try:
        from apps.inventory.models import InventoryTransaction
        
        # Get unlinked inventory purchases
        purchases = InventoryTransaction.objects.filter(
            transaction_type='purchase',
            linked_expense_id__isnull=True
        )
        
        created_count = 0
        for purchase in purchases:
            expense = create_inventory_expense(
                purchase.item, 
                purchase.total_cost,
                purchase.transaction_date,
                purchase.supplier
            )
            if expense:
                purchase.linked_expense_id = expense.id
                purchase.save()
                created_count += 1
        
        messages.success(request, f'{created_count} inventory expenses created.')
        
    except Exception as e:
        messages.error(request, f'Error linking inventory expenses: {e}')
    
    return tenant_redirect(request, 'expenses:dashboard')


@employee_required()
@require_POST
def auto_link_salary_expenses(request):
    """Link employee salaries to expenses"""
    try:
        from apps.employees.models import Employee, SalaryPayment
        
        # Get unlinked salary payments
        payments = SalaryPayment.objects.filter(
            linked_expense_id__isnull=True,
            status='paid'
        )
        
        created_count = 0
        for payment in payments:
            expense = create_salary_expense(
                payment.employee,
                payment.amount,
                payment.pay_date
            )
            if expense:
                payment.linked_expense_id = expense.id
                payment.save()
                created_count += 1
        
        messages.success(request, f'{created_count} salary expenses created.')
        
    except Exception as e:
        messages.error(request, f'Error linking salary expenses: {e}')
    
    return tenant_redirect(request, 'expenses:dashboard')


@employee_required()
@require_POST
def auto_link_commission_expenses(request):
    """Link service commissions to expenses"""
    try:
        from apps.services.models import ServiceOrderItem
        
        # Get completed service order items with commissions but no linked expenses
        service_items = ServiceOrderItem.objects.filter(
            commission_amount__gt=0,
            commission_paid=False,
            commission_expense_id__isnull=True,
            completed_at__isnull=False,
            assigned_to__isnull=False
        )
        
        created_count = 0
        for item in service_items:
            expense = create_commission_expense(item)
            if expense:
                item.commission_expense_id = expense.id
                item.commission_paid = True
                item.save()
                created_count += 1
        
        messages.success(request, f'{created_count} commission expenses created.')
        
    except Exception as e:
        messages.error(request, f'Error linking commission expenses: {e}')
    
    return tenant_redirect(request, 'expenses:dashboard')


# AJAX Views
@ajax_required
def expense_search_ajax(request):
    """AJAX search for expenses"""
    search = request.GET.get('search', '')
    
    expenses = Expense.objects.filter(
        Q(title__icontains=search) |
        Q(description__icontains=search) |
        Q(vendor__name__icontains=search),
        is_active=True
    ).select_related('category', 'vendor')[:10]
    
    data = [{
        'id': str(expense.id),
        'title': expense.title,
        'amount': str(expense.total_amount),
        'category': expense.category.name,
        'vendor': expense.vendor.name if expense.vendor else '',
        'date': expense.expense_date.strftime('%Y-%m-%d'),
        'status': expense.get_status_display(),
        'url': reverse('expenses:detail', kwargs={'pk': expense.pk})
    } for expense in expenses]
    
    return JsonResponse({'expenses': data})


# Export Views
@employee_required()
@login_required
@employee_required(['owner', 'manager', 'supervisor'])
def expense_export_view(request):
    """Export expenses to CSV"""
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="expenses.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Title', 'Category', 'Vendor', 'Amount', 'Tax', 'Total',
        'Date', 'Due Date', 'Status', 'Type', 'Payment Method',
        'Reference Number', 'Created At'
    ])
    
    expenses = Expense.objects.filter(is_active=True).select_related(
        'category', 'vendor'
    ).order_by('-expense_date')
    
    for expense in expenses:
        writer.writerow([
            expense.title,
            expense.category.name,
            expense.vendor.name if expense.vendor else '',
            expense.amount,
            expense.tax_amount,
            expense.total_amount,
            expense.expense_date,
            expense.due_date or '',
            expense.get_status_display(),
            expense.get_expense_type_display(),
            expense.get_payment_method_display(),
            expense.reference_number,
            expense.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    return response


# Additional views for categories, recurring expenses, budgets, and reports
# (These would be implemented similarly following the same patterns)

# Category Views
@employee_required()
@login_required
@employee_required(['owner', 'manager', 'supervisor'])
def category_list_view(request):
    """List all expense categories"""
    categories = ExpenseCategory.objects.filter(is_active=True).order_by('name')
    return render(request, 'expenses/category_list.html', {
        'categories': categories,
        'title': 'Expense Categories',
        'urls': get_expense_urls(request),
    })


@employee_required()  
@login_required
@employee_required(['owner', 'manager', 'supervisor'])
def category_create_view(request):
    """Create new expense category"""
    if request.method == 'POST':
        form = ExpenseCategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.set_created_by(request.user)
            category.save()
            messages.success(request, f'Category "{category.name}" created successfully.')
            return tenant_redirect(request, 'expenses:category_list')
    else:
        form = ExpenseCategoryForm()
    
    return render(request, 'expenses/category_form.html', {
        'form': form,
        'title': 'Create Category',
        'urls': get_expense_urls(request),
    })


# Recurring Expense Views  
@employee_required()
@login_required
@employee_required(['owner', 'manager', 'supervisor'])
def recurring_expense_list_view(request):
    """List all recurring expenses"""
    recurring_expenses = RecurringExpense.objects.filter(is_active=True).order_by('next_due_date')
    return render(request, 'expenses/recurring_list.html', {
        'recurring_expenses': recurring_expenses,
        'title': 'Recurring Expenses',
        'urls': get_expense_urls(request),
    })


# Budget Views
@employee_required()
@login_required
@employee_required(['owner', 'manager', 'supervisor'])
def budget_list_view(request):
    """List all budgets"""
    budgets = ExpenseBudget.objects.all().select_related('category').order_by('-year', '-month')
    return render(request, 'expenses/budget_list.html', {
        'budgets': budgets,
        'title': 'Expense Budgets',
        'urls': get_expense_urls(request),
    })


# Reports Views
@employee_required()
@login_required
@employee_required(['owner', 'manager', 'supervisor'])
def expense_reports_view(request):
    """Expense reports dashboard"""
    return render(request, 'expenses/reports.html', {
        'title': 'Expense Reports',
        'urls': get_expense_urls(request),
    })


# Placeholder views for remaining URL patterns
# Additional view implementations
@employee_required()
@login_required
@employee_required(['owner', 'manager', 'supervisor'])
def vendor_edit_view(request, pk):
    """Edit vendor"""
    vendor = get_object_or_404(Vendor, pk=pk, is_active=True)
    
    if request.method == 'POST':
        form = VendorForm(request.POST, instance=vendor)
        if form.is_valid():
            form.save()
            messages.success(request, f'Vendor "{vendor.name}" updated successfully.')
            return tenant_redirect(request, 'expenses:vendor_list')
    else:
        form = VendorForm(instance=vendor)
    
    context = {
        'form': form,
        'vendor': vendor,
        'title': 'Edit Vendor',
        'urls': get_expense_urls(request),
    }
    
    return render(request, 'expenses/vendor_form.html', context)


@employee_required()
@login_required
@employee_required(['owner', 'manager'])
def vendor_delete_view(request, pk):
    """Delete vendor"""
    vendor = get_object_or_404(Vendor, pk=pk, is_active=True)
    
    if request.method == 'POST':
        vendor.is_active = False
        vendor.save()
        messages.success(request, f'Vendor "{vendor.name}" deleted successfully.')
        return tenant_redirect(request, 'expenses:vendor_list')
    
    context = {
        'vendor': vendor,
        'title': 'Delete Vendor',
        'urls': get_expense_urls(request),
    }
    
    return render(request, 'expenses/vendor_confirm_delete.html', context)


@employee_required()
@login_required
@employee_required(['owner', 'manager', 'supervisor'])
def category_edit_view(request, pk):
    """Edit expense category"""
    category = get_object_or_404(ExpenseCategory, pk=pk, is_active=True)
    
    if request.method == 'POST':
        form = ExpenseCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, f'Category "{category.name}" updated successfully.')
            return tenant_redirect(request, 'expenses:category_list')
    else:
        form = ExpenseCategoryForm(instance=category)
    
    context = {
        'form': form,
        'category': category,
        'title': 'Edit Category',
        'urls': get_expense_urls(request),
    }
    
    return render(request, 'expenses/category_form.html', context)


@employee_required()
@login_required
@employee_required(['owner', 'manager'])
def category_delete_view(request, pk):
    """Delete expense category"""
    category = get_object_or_404(ExpenseCategory, pk=pk, is_active=True)
    
    if request.method == 'POST':
        category.is_active = False
        category.save()
        messages.success(request, f'Category "{category.name}" deleted successfully.')
        return tenant_redirect(request, 'expenses:category_list')
    
    context = {
        'category': category,
        'title': 'Delete Category',
        'urls': get_expense_urls(request),
    }
    
    return render(request, 'expenses/category_confirm_delete.html', context)


@employee_required()
@login_required
@employee_required(['owner', 'manager', 'supervisor'])
def recurring_expense_create_view(request):
    """Create recurring expense"""
    if request.method == 'POST':
        form = RecurringExpenseForm(request.POST)
        if form.is_valid():
            recurring_expense = form.save(commit=False)
            recurring_expense.set_created_by(request.user)
            recurring_expense.save()
            messages.success(request, f'Recurring expense "{recurring_expense.title}" created successfully.')
            return tenant_redirect(request, 'expenses:recurring_list')
    else:
        form = RecurringExpenseForm()
    
    context = {
        'form': form,
        'title': 'Create Recurring Expense',
        'urls': get_expense_urls(request),
    }
    
    return render(request, 'expenses/recurring_form.html', context)


@employee_required()
@login_required
@employee_required(['owner', 'manager', 'supervisor'])
def recurring_expense_edit_view(request, pk):
    """Edit recurring expense"""
    recurring_expense = get_object_or_404(RecurringExpense, pk=pk, is_active=True)
    
    if request.method == 'POST':
        form = RecurringExpenseForm(request.POST, instance=recurring_expense)
        if form.is_valid():
            form.save()
            messages.success(request, f'Recurring expense "{recurring_expense.title}" updated successfully.')
            return tenant_redirect(request, 'expenses:recurring_list')
    else:
        form = RecurringExpenseForm(instance=recurring_expense)
    
    context = {
        'form': form,
        'recurring_expense': recurring_expense,
        'title': 'Edit Recurring Expense',
        'urls': get_expense_urls(request),
    }
    
    return render(request, 'expenses/recurring_form.html', context)


@employee_required()
@login_required
@employee_required(['owner', 'manager'])
def recurring_expense_delete_view(request, pk):
    """Delete recurring expense"""
    recurring_expense = get_object_or_404(RecurringExpense, pk=pk, is_active=True)
    
    if request.method == 'POST':
        recurring_expense.is_active = False
        recurring_expense.save()
        messages.success(request, f'Recurring expense "{recurring_expense.title}" deleted successfully.')
        return tenant_redirect(request, 'expenses:recurring_list')
    
    context = {
        'recurring_expense': recurring_expense,
        'title': 'Delete Recurring Expense',
        'urls': get_expense_urls(request),
    }
    
    return render(request, 'expenses/recurring_confirm_delete.html', context)


@employee_required()
@login_required
@employee_required(['owner', 'manager', 'supervisor'])
def generate_recurring_expense_view(request, pk):
    """Generate expense from recurring template"""
    recurring_expense = get_object_or_404(RecurringExpense, pk=pk, is_active=True)
    
    if request.method == 'POST':
        # Create expense from recurring template
        expense = Expense.objects.create(
            title=recurring_expense.title,
            description=recurring_expense.description,
            amount=recurring_expense.amount,
            category=recurring_expense.category,
            vendor=recurring_expense.vendor,
            expense_date=timezone.now().date(),
            expense_type='recurring',
            status='pending',
            recurring_expense=recurring_expense
        )
        expense.set_created_by(request.user)
        
        # Update next occurrence
        recurring_expense.update_next_occurrence()
        
        messages.success(request, f'Expense generated from "{recurring_expense.title}" template.')
        return tenant_redirect(request, 'expenses:detail', pk=expense.pk)
    
    return tenant_redirect(request, 'expenses:recurring_list')


@employee_required()
@login_required
@employee_required(['owner', 'manager', 'supervisor'])
def budget_create_view(request):
    """Create expense budget"""
    if request.method == 'POST':
        form = ExpenseBudgetForm(request.POST)
        if form.is_valid():
            budget = form.save(commit=False)
            budget.set_created_by(request.user)
            budget.save()
            messages.success(request, f'Budget for "{budget.category.name}" created successfully.')
            return tenant_redirect(request, 'expenses:budget_list')
    else:
        form = ExpenseBudgetForm()
    
    context = {
        'form': form,
        'title': 'Create Budget',
        'urls': get_expense_urls(request),
    }
    
    return render(request, 'expenses/budget_form.html', context)


@employee_required()
@login_required
@employee_required(['owner', 'manager', 'supervisor'])
def budget_edit_view(request, pk):
    """Edit expense budget"""
    budget = get_object_or_404(ExpenseBudget, pk=pk)
    
    if request.method == 'POST':
        form = ExpenseBudgetForm(request.POST, instance=budget)
        if form.is_valid():
            form.save()
            messages.success(request, f'Budget for "{budget.category.name}" updated successfully.')
            return tenant_redirect(request, 'expenses:budget_list')
    else:
        form = ExpenseBudgetForm(instance=budget)
    
    context = {
        'form': form,
        'budget': budget,
        'title': 'Edit Budget',
        'urls': get_expense_urls(request),
    }
    
    return render(request, 'expenses/budget_form.html', context)


@employee_required()
@login_required
@employee_required(['owner', 'manager'])
def budget_delete_view(request, pk):
    """Delete expense budget"""
    budget = get_object_or_404(ExpenseBudget, pk=pk)
    
    if request.method == 'POST':
        budget.delete()
        messages.success(request, f'Budget for "{budget.category.name}" deleted successfully.')
        return tenant_redirect(request, 'expenses:budget_list')
    
    context = {
        'budget': budget,
        'title': 'Delete Budget',
        'urls': get_expense_urls(request),
    }
    
    return render(request, 'expenses/budget_confirm_delete.html', context)


# Report views (simplified implementations)
@employee_required()
@login_required
@employee_required(['owner', 'manager', 'supervisor'])
def category_expense_report_view(request):
    """Category expense report"""
    return tenant_redirect(request, 'expenses:reports')


@employee_required()
@login_required
@employee_required(['owner', 'manager', 'supervisor'])
def vendor_expense_report_view(request):
    """Vendor expense report"""
    return tenant_redirect(request, 'expenses:reports')


@employee_required()
@login_required
@employee_required(['owner', 'manager', 'supervisor'])
def monthly_expense_report_view(request):
    """Monthly expense report"""
    return tenant_redirect(request, 'expenses:reports')


@employee_required()
@login_required
@employee_required(['owner', 'manager', 'supervisor'])
def budget_analysis_report_view(request):
    """Budget analysis report"""
    return tenant_redirect(request, 'expenses:reports')


# AJAX views (simplified implementations)
@ajax_required
def category_expenses_ajax(request):
    """Get expenses for category via AJAX"""
    category_id = request.GET.get('category_id')
    if category_id:
        expenses = Expense.objects.filter(
            category_id=category_id,
            is_active=True
        ).values('id', 'title', 'amount', 'expense_date')[:10]
        return JsonResponse({'expenses': list(expenses)})
    return JsonResponse({'expenses': []})


@ajax_required
def vendor_expenses_ajax(request):
    """Get expenses for vendor via AJAX"""
    vendor_id = request.GET.get('vendor_id')
    if vendor_id:
        expenses = Expense.objects.filter(
            vendor_id=vendor_id,
            is_active=True
        ).values('id', 'title', 'amount', 'expense_date')[:10]
        return JsonResponse({'expenses': list(expenses)})
    return JsonResponse({'expenses': []})


@ajax_required
def budget_status_ajax(request):
    """Get budget status via AJAX"""
    today = timezone.now().date()
    budgets = ExpenseBudget.objects.filter(
        year=today.year,
        month=today.month
    ).select_related('category')
    
    budget_data = []
    for budget in budgets:
        budget_data.append({
            'category': budget.category.name,
            'amount': float(budget.amount),
            'spent': float(budget.spent_amount),
            'percentage': budget.utilization_percentage
        })
    
    return JsonResponse({'budgets': budget_data})


@employee_required()
@login_required
@employee_required(['owner', 'manager', 'supervisor'])
def expense_export_pdf_view(request):
    """Export expenses to PDF (placeholder)"""
    messages.info(request, 'PDF export feature coming soon!')
    return tenant_redirect(request, 'expenses:list')


@employee_required()
@login_required
@require_POST
def expense_delete_view(request, pk):
    """Delete expense with role-based permissions and status checks"""
    
    expense = get_object_or_404(Expense, pk=pk, is_active=True)
    
    # Check permissions based on role and status
    can_delete = False
    delete_reason = ""
    
    if request.employee.role == 'owner':
        # Owners can delete any expense except paid ones
        can_delete = expense.status != 'paid'
        delete_reason = "Cannot delete paid expenses"
    elif request.employee.role in ['manager', 'supervisor']:
        # Managers can delete pending and rejected expenses
        can_delete = expense.status in ['pending', 'rejected']
        delete_reason = "Managers can only delete pending or rejected expenses"
    elif request.employee.role == 'attendant':
        # Attendants can only delete their own pending expenses
        can_delete = (expense.created_by_user_id == request.user.id and 
                     expense.status == 'pending')
        delete_reason = "You can only delete your own pending expenses"
    else:
        delete_reason = "You do not have permission to delete expenses"
    
    if not can_delete:
        messages.error(request, delete_reason)
        return redirect(f'/business/{request.tenant.slug}/expenses/{pk}/')
    
    # Soft delete the expense
    expense_title = expense.title
    expense.is_active = False
    expense.save()
    
    messages.success(request, f'Expense "{expense_title}" has been deleted successfully.')
    
    # Redirect based on user role
    if request.employee.role == 'attendant':
        return redirect(f'/business/{request.tenant.slug}/expenses/my-expenses/')
    else:
        return redirect(f'/business/{request.tenant.slug}/expenses/list/')


@employee_required()
@login_required
def expense_delete_confirm_view(request, pk):
    """Confirm expense deletion"""
    
    expense = get_object_or_404(Expense, pk=pk, is_active=True)
    
    # Check permissions based on role and status
    can_delete = False
    delete_reason = ""
    
    if request.employee.role == 'owner':
        can_delete = expense.status != 'paid'
        delete_reason = "Cannot delete paid expenses"
    elif request.employee.role in ['manager', 'supervisor']:
        can_delete = expense.status in ['pending', 'rejected']
        delete_reason = "Managers can only delete pending or rejected expenses"
    elif request.employee.role == 'attendant':
        can_delete = (expense.created_by_user_id == request.user.id and 
                     expense.status == 'pending')
        delete_reason = "You can only delete your own pending expenses"
    else:
        delete_reason = "You do not have permission to delete expenses"
    
    if not can_delete:
        messages.error(request, delete_reason)
        return redirect(f'/business/{request.tenant.slug}/expenses/{pk}/')
    
    context = {
        'expense': expense,
        'title': f'Delete Expense - {expense.title}',
        'urls': get_expense_urls(request),
        'can_delete': can_delete,
        'delete_reason': delete_reason,
    }
    
    return render(request, 'expenses/expense_confirm_delete.html', context)
