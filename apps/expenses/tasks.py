from celery import shared_task
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal
import logging

from .models import (
    RecurringExpense, Expense, ExpenseBudget, ExpenseCategory
)

logger = logging.getLogger(__name__)


@shared_task
def generate_recurring_expenses():
    """
    Generate expenses from recurring expense templates
    Run this task daily to create due recurring expenses
    """
    today = timezone.now().date()
    generated_count = 0
    
    # Get all active recurring expenses that are due
    recurring_expenses = RecurringExpense.objects.filter(
        is_active=True,
        next_due_date__lte=today
    )
    
    for recurring_expense in recurring_expenses:
        try:
            # Generate the next expense
            expense = recurring_expense.generate_next_expense()
            if expense:
                generated_count += 1
                logger.info(
                    f"Generated recurring expense: {expense.title} "
                    f"for ${expense.total_amount}"
                )
        except Exception as e:
            logger.error(
                f"Error generating recurring expense {recurring_expense.id}: {e}"
            )
    
    logger.info(f"Generated {generated_count} recurring expenses")
    return generated_count


@shared_task
def update_budget_spent_amounts():
    """
    Update spent amounts for all budgets based on actual expenses
    Run this task nightly to keep budget tracking accurate
    """
    updated_count = 0
    
    # Get all budgets
    budgets = ExpenseBudget.objects.all()
    
    for budget in budgets:
        try:
            # Calculate date range for this budget
            if budget.month:
                # Monthly budget
                start_date = timezone.datetime(budget.year, budget.month, 1).date()
                if budget.month == 12:
                    end_date = timezone.datetime(budget.year + 1, 1, 1).date()
                else:
                    end_date = timezone.datetime(budget.year, budget.month + 1, 1).date()
            else:
                # Yearly budget
                start_date = timezone.datetime(budget.year, 1, 1).date()
                end_date = timezone.datetime(budget.year + 1, 1, 1).date()
            
            # Calculate spent amount for this category and period
            spent_amount = Expense.objects.filter(
                category=budget.category,
                expense_date__gte=start_date,
                expense_date__lt=end_date,
                is_active=True,
                status__in=['approved', 'paid']
            ).aggregate(
                total=Sum('total_amount')
            )['total'] or Decimal('0.00')
            
            # Update budget if spent amount changed
            if budget.spent_amount != spent_amount:
                budget.spent_amount = spent_amount
                budget.save()
                updated_count += 1
                
                logger.info(
                    f"Updated budget {budget.id}: {budget.category.name} "
                    f"spent amount to ${spent_amount}"
                )
                
        except Exception as e:
            logger.error(f"Error updating budget {budget.id}: {e}")
    
    logger.info(f"Updated {updated_count} budget spent amounts")
    return updated_count


@shared_task
def auto_link_inventory_expenses():
    """
    Automatically create expenses for inventory purchases
    """
    try:
        from apps.inventory.models import InventoryTransaction
        from .views import create_inventory_expense
        
        # Get unlinked inventory purchases from the last 7 days
        cutoff_date = timezone.now().date() - timezone.timedelta(days=7)
        
        purchases = InventoryTransaction.objects.filter(
            transaction_type='purchase',
            linked_expense_id__isnull=True,
            transaction_date__gte=cutoff_date,
            total_cost__gt=0
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
                
                logger.info(
                    f"Created inventory expense: {expense.title} "
                    f"for ${expense.total_amount}"
                )
        
        logger.info(f"Auto-linked {created_count} inventory expenses")
        return created_count
        
    except ImportError:
        logger.warning("Inventory app not available for auto-linking")
        return 0
    except Exception as e:
        logger.error(f"Error auto-linking inventory expenses: {e}")
        return 0


@shared_task
def auto_link_salary_expenses():
    """
    Automatically create expenses for employee salary payments
    
    NOTE: This task is disabled because SalaryPayment model doesn't exist.
    This prevents duplicate expense/payment creation issues.
    """
    logger.warning("Auto-link salary expenses task is disabled - SalaryPayment model not found")
    return 0
    
    # COMMENTED OUT - Only enable after creating SalaryPayment model
    # try:
    #     from apps.employees.models import SalaryPayment
    #     from .views import create_salary_expense
    #     
    #     # Get unlinked salary payments from the last 30 days
    #     cutoff_date = timezone.now().date() - timezone.timedelta(days=30)
    #     
    #     payments = SalaryPayment.objects.filter(
    #         linked_expense_id__isnull=True,
    #         pay_date__gte=cutoff_date,
    #         status='paid',
    #         amount__gt=0
    #     )
    #     
    #     created_count = 0
    #     for payment in payments:
    #         expense = create_salary_expense(
    #             payment.employee,
    #             payment.amount,
    #             payment.pay_date
    #         )
    #         if expense:
    #             payment.linked_expense_id = expense.id
    #             payment.save()
    #             created_count += 1
    #             
    #             logger.info(
    #                 f"Created salary expense: {expense.title} "
    #                 f"for ${expense.total_amount}"
    #             )
    #     
    #     logger.info(f"Auto-linked {created_count} salary expenses")
    #     return created_count
    #     
    # except ImportError:
    #     logger.warning("Employees app not available for auto-linking")
    #     return 0
    # except Exception as e:
    #     logger.error(f"Error auto-linking salary expenses: {e}")
    #     return 0


@shared_task
def auto_link_commission_expenses():
    """
    Automatically create expenses for service commissions
    """
    try:
        from apps.services.models import ServiceRecord
        from .views import create_commission_expense
        
        # Get service records with commissions from the last 7 days
        cutoff_date = timezone.now().date() - timezone.timedelta(days=7)
        
        service_records = ServiceRecord.objects.filter(
            commission_amount__gt=0,
            linked_commission_expense_id__isnull=True,
            service_date__gte=cutoff_date,
            status='completed'
        ).select_related('service', 'assigned_employee')
        
        created_count = 0
        for record in service_records:
            if record.assigned_employee and record.commission_amount:
                expense = create_commission_expense(
                    record.service,
                    record.assigned_employee,
                    record.commission_amount,
                    record.service_date
                )
                if expense:
                    record.linked_commission_expense_id = expense.id
                    record.save()
                    created_count += 1
                    
                    logger.info(
                        f"Created commission expense: {expense.title} "
                        f"for ${expense.total_amount}"
                    )
        
        logger.info(f"Auto-linked {created_count} commission expenses")
        return created_count
        
    except ImportError:
        logger.warning("Services app not available for auto-linking")
        return 0
    except Exception as e:
        logger.error(f"Error auto-linking commission expenses: {e}")
        return 0


@shared_task
def check_overdue_expenses():
    """
    Check for overdue expenses and send notifications
    """
    today = timezone.now().date()
    
    # Get overdue expenses
    overdue_expenses = Expense.objects.filter(
        due_date__lt=today,
        status__in=['pending', 'approved'],
        is_active=True
    ).select_related('category', 'vendor')
    
    if overdue_expenses.exists():
        # You can implement notification logic here
        # For example, send email to business owner/manager
        logger.warning(f"Found {overdue_expenses.count()} overdue expenses")
        
        for expense in overdue_expenses:
            logger.warning(
                f"Overdue expense: {expense.title} - "
                f"${expense.total_amount} due {expense.due_date}"
            )
    
    return overdue_expenses.count()


@shared_task
def generate_monthly_expense_report():
    """
    Generate monthly expense report and send to management
    Run this task on the first day of each month
    """
    try:
        from django.template.loader import render_to_string
        from django.core.mail import send_mail
        from django.conf import settings
        
        # Get last month's data
        today = timezone.now().date()
        last_month = today.replace(day=1) - timezone.timedelta(days=1)
        month_start = last_month.replace(day=1)
        month_end = today.replace(day=1)
        
        # Calculate monthly statistics
        monthly_expenses = Expense.objects.filter(
            expense_date__gte=month_start,
            expense_date__lt=month_end,
            is_active=True
        )
        
        stats = {
            'total_expenses': monthly_expenses.aggregate(
                total=Sum('total_amount')
            )['total'] or Decimal('0.00'),
            'expense_count': monthly_expenses.count(),
            'by_category': {},
            'by_type': {},
            'period': last_month.strftime('%B %Y')
        }
        
        # Group by category
        category_stats = monthly_expenses.values('category__name').annotate(
            total=Sum('total_amount'),
            count=Sum('id')
        ).order_by('-total')
        
        for stat in category_stats:
            stats['by_category'][stat['category__name']] = {
                'total': stat['total'],
                'count': stat['count']
            }
        
        # Group by type
        type_stats = monthly_expenses.values('expense_type').annotate(
            total=Sum('total_amount'),
            count=Sum('id')
        ).order_by('-total')
        
        for stat in type_stats:
            stats['by_type'][stat['expense_type']] = {
                'total': stat['total'],
                'count': stat['count']
            }
        
        logger.info(f"Generated monthly expense report for {stats['period']}")
        return stats
        
    except Exception as e:
        logger.error(f"Error generating monthly expense report: {e}")
        return None


@shared_task
def cleanup_old_expense_data():
    """
    Cleanup old expense data (soft-deleted expenses older than 1 year)
    """
    cutoff_date = timezone.now().date() - timezone.timedelta(days=365)
    
    # Hard delete soft-deleted expenses older than 1 year
    old_expenses = Expense.objects.filter(
        is_active=False,
        updated_at__date__lt=cutoff_date
    )
    
    deleted_count = old_expenses.count()
    old_expenses.delete()
    
    logger.info(f"Cleaned up {deleted_count} old expense records")
    return deleted_count
