from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import View, TemplateView
from django.db.models import Sum, Count, Avg, Q, F, Max, Min, Value, Case, When
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek, TruncYear, Extract
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import io
import json

# Third party imports
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.units import inch
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib import colors
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False

# Model imports
from apps.services.models import Service, ServiceCategory, ServiceOrder, ServiceOrderItem, ServicePackage
from apps.employees.models import Employee, Department, Attendance, PerformanceReview
from apps.customers.models import Customer, Vehicle, LoyaltyProgram
from apps.payments.models import Payment, PaymentMethod
from apps.inventory.models import InventoryItem, StockMovement, InventoryCategory
from apps.expenses.models import Expense, ExpenseCategory, Vendor
from apps.suppliers.models import Supplier, PurchaseOrder
from apps.subscriptions.models import Subscription
from apps.core.decorators import business_required

@method_decorator([login_required, business_required], name='dispatch')
class ReportsView(TemplateView):
    """Comprehensive focused reports system showing specific report data"""
    template_name = 'reports/reports.html'
    
    def get(self, request, *args, **kwargs):
        # Check if this is an export request
        export_format = request.GET.get('export')
        if export_format in ['pdf', 'excel']:
            return self._handle_export(request, export_format)
        
        # Otherwise, render the normal template
        return super().get(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get report type from URL parameters
        report_type = self.request.GET.get('report_type', 'business_overview')
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        page = int(self.request.GET.get('page', 1))
        
        # Set default date range if not provided
        if not start_date or not end_date:
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=30)
        else:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError:
                # If date parsing fails, use default range
                end_date = timezone.now().date()
                start_date = end_date - timedelta(days=30)
        
        # Get report-specific data
        report_data = self._get_report_data(report_type, start_date, end_date, page)
        
        context.update({
            'selected_report_type': report_type,
            'start_date': start_date,
            'end_date': end_date,
            'current_page': page,
            'report_data': report_data,
            'available_reports': self._get_available_reports(),
            'pdf_available': PDF_AVAILABLE,
            'excel_available': EXCEL_AVAILABLE,
            'employees_list': self._get_employees_list() if report_type == 'individual_employee' else [],
            'selected_employee_id': self.request.GET.get('employee_id', ''),
        })
        
        return context
    
    def _get_employees_list(self):
        """Get list of employees for dropdown"""
        try:
            employees = Employee.objects.filter(is_active=True).select_related('department')
            return [(emp.id, f"{emp.full_name} - {emp.department.name if emp.department else 'No Dept'}") 
                   for emp in employees]
        except Exception as e:
            return [('', f'Error loading employees: {str(e)}')]
    
    def _get_datetime_range(self, start_date, end_date):
        """Convert date objects to proper datetime range for filtering"""
        from django.utils import timezone
        start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
        end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
        return start_datetime, end_datetime
    
    def _get_available_reports(self):
        """Get list of available report types"""
        return [
            ('business_overview', 'Business Overview'),
            ('inventory', 'Inventory Management'),
            ('services', 'Services Performance'),
            ('customers', 'Customer Analysis'),
            ('employees', 'Employee Performance'),
            ('payments', 'Payment Transactions'),
            ('expenses', 'Expense Analysis'),
            ('individual_employee', 'Individual Employee'),
            ('financial_summary', 'Financial Summary'),
            ('daily_summary', 'Daily Summary'),
            ('weekly_summary', 'Weekly Summary'),
            ('monthly_summary', 'Monthly Summary'),
            ('sales_analysis', 'Sales Analysis'),
            ('customer_analytics', 'Customer Analytics'),
            ('supplier_report', 'Supplier Performance'),
            ('vehicle_analysis', 'Vehicle Analysis'),
            ('service_packages', 'Service Packages'),
            ('loyalty_program', 'Loyalty Program'),
            ('attendance_report', 'Employee Attendance'),
            ('department_performance', 'Department Performance'),
            ('subscription_analysis', 'Subscription Analysis'),
        ]
    
    def _get_report_data(self, report_type, start_date, end_date, page):
        """Get data specific to the report type"""
        data = {
            'title': self._get_report_title(report_type),
            'type': report_type,
            'period': f"{start_date.strftime('%B %d, %Y')} - {end_date.strftime('%B %d, %Y')}",
            'items': [],
            'summary': {},
            'pagination': {},
        }
        
        try:
            if report_type == 'inventory':
                data.update(self._get_inventory_data(start_date, end_date, page))
            elif report_type == 'services':
                data.update(self._get_services_data(start_date, end_date, page))
            elif report_type == 'customers':
                data.update(self._get_customers_data(start_date, end_date, page))
            elif report_type == 'employees':
                data.update(self._get_employees_data(start_date, end_date, page))
            elif report_type == 'payments':
                data.update(self._get_payments_data(start_date, end_date, page))
            elif report_type == 'expenses':
                data.update(self._get_expenses_data(start_date, end_date, page))
            elif report_type == 'individual_employee':
                employee_id = self.request.GET.get('employee_id')
                data.update(self._get_individual_employee_data(employee_id, start_date, end_date, page))
            elif report_type == 'financial_summary':
                data.update(self._get_financial_summary_data(start_date, end_date, page))
            elif report_type == 'daily_summary':
                data.update(self._get_daily_summary_data(start_date, end_date, page))
            elif report_type == 'weekly_summary':
                data.update(self._get_weekly_summary_data(start_date, end_date, page))
            elif report_type == 'monthly_summary':
                data.update(self._get_monthly_summary_data(start_date, end_date, page))
            elif report_type == 'sales_analysis':
                data.update(self._get_sales_analysis_data(start_date, end_date, page))
            elif report_type == 'customer_analytics':
                data.update(self._get_customer_analytics_data(start_date, end_date, page))
            elif report_type == 'supplier_report':
                data.update(self._get_supplier_report_data(start_date, end_date, page))
            elif report_type == 'vehicle_analysis':
                data.update(self._get_vehicle_analysis_data(start_date, end_date, page))
            elif report_type == 'service_packages':
                data.update(self._get_service_packages_data(start_date, end_date, page))
            elif report_type == 'loyalty_program':
                data.update(self._get_loyalty_program_data(start_date, end_date, page))
            elif report_type == 'attendance_report':
                data.update(self._get_attendance_report_data(start_date, end_date, page))
            elif report_type == 'department_performance':
                data.update(self._get_department_performance_data(start_date, end_date, page))
            elif report_type == 'subscription_analysis':
                data.update(self._get_subscription_analysis_data(start_date, end_date, page))
            else:  # business_overview
                data.update(self._get_business_overview_data(start_date, end_date, page))
                
        except Exception as e:
            data['error'] = f"Error generating {report_type} report: {str(e)}"
            
        return data
    
    def _get_report_title(self, report_type):
        """Get the title for a specific report type"""
        titles = {
            'business_overview': 'Business Overview Report',
            'inventory': 'Inventory Management Report',
            'services': 'Services Performance Report',
            'customers': 'Customer Analysis Report',
            'employees': 'Employee Performance Report',
            'payments': 'Payment Transactions Report',
            'expenses': 'Expense Analysis Report',
            'individual_employee': 'Individual Employee Report',
            'financial_summary': 'Financial Summary Report',
            'daily_summary': 'Daily Summary Report',
            'weekly_summary': 'Weekly Summary Report',
            'monthly_summary': 'Monthly Summary Report',
            'sales_analysis': 'Sales Analysis Report',
            'customer_analytics': 'Customer Analytics Report',
            'supplier_report': 'Supplier Performance Report',
            'vehicle_analysis': 'Vehicle Analysis Report',
            'service_packages': 'Service Packages Report',
            'loyalty_program': 'Loyalty Program Report',
            'attendance_report': 'Employee Attendance Report',
            'department_performance': 'Department Performance Report',
            'subscription_analysis': 'Subscription Analysis Report',
        }
        return titles.get(report_type, 'Business Report')
    
    # ============== CORE REPORT DATA METHODS ==============
    
    def _get_business_overview_data(self, start_date, end_date, page):
        """Get business overview data"""
        from django.core.paginator import Paginator
        
        try:
            # Convert dates to datetime for proper filtering
            start_datetime, end_datetime = self._get_datetime_range(start_date, end_date)
            
            # Debug: Check orders without any filters first
            all_orders_count = ServiceOrder.objects.count()
            
            # Debug: Check recent orders regardless of date
            recent_orders = ServiceOrder.objects.order_by('-created_at')[:5].values('created_at', 'order_number', 'status')
            
            # Get recent orders for the overview using datetime range
            orders = ServiceOrder.objects.select_related('customer', 'assigned_attendant', 'vehicle').filter(
                created_at__range=[start_datetime, end_datetime]
            ).order_by('-created_at')
            
            # Paginate orders
            paginator = Paginator(orders, 20)
            orders_page = paginator.get_page(page)
            
            # Calculate summary metrics
            total_orders = orders.count()
            total_revenue = orders.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
            completed_orders = orders.filter(status='completed').count()
            pending_orders = orders.filter(status='pending').count()
            avg_order_value = total_revenue / max(total_orders, 1)
            
            # Debug information
            debug_info = {
                'orders_count_in_range': total_orders,
                'all_orders_count': all_orders_count,
                'revenue': total_revenue,
                'completed': completed_orders,
                'pending': pending_orders,
                'date_range': f"{start_date} to {end_date}",
                'datetime_range': f"{start_datetime} to {end_datetime}",
                'recent_orders_sample': list(recent_orders),
                'tenant_id': getattr(self.request.tenant, 'id', 'Unknown') if hasattr(self.request, 'tenant') else 'No tenant'
            }
            
            return {
                'items': orders_page,
                'summary': {
                    'total_orders': total_orders,
                    'total_revenue': total_revenue,
                    'completed_orders': completed_orders,
                    'pending_orders': pending_orders,
                    'avg_order_value': avg_order_value,
                    'completion_rate': (completed_orders / max(total_orders, 1)) * 100,
                },
                'pagination': self._get_pagination_data(orders_page, paginator),
                'debug_info': debug_info
            }
        except Exception as e:
            return {
                'items': [],
                'summary': {
                    'total_orders': 0,
                    'total_revenue': 0,
                    'completed_orders': 0,
                    'pending_orders': 0,
                    'avg_order_value': 0,
                    'completion_rate': 0,
                },
                'pagination': {},
                'error': f"Error generating business overview: {str(e)}",
                'debug_info': {'error': str(e)}
            }
    
    def _get_inventory_data(self, start_date, end_date, page):
        """Get inventory-specific data"""
        from django.core.paginator import Paginator
        
        try:
            # Convert dates to datetime for proper filtering
            start_datetime, end_datetime = self._get_datetime_range(start_date, end_date)
            
            # Get inventory items with movements in the date range
            items = InventoryItem.objects.select_related('category', 'unit').annotate(
                total_in=Sum('stock_movements__quantity', 
                            filter=Q(stock_movements__created_at__range=[start_datetime, end_datetime],
                                   stock_movements__movement_type='in')),
                total_out=Sum('stock_movements__quantity', 
                             filter=Q(stock_movements__created_at__range=[start_datetime, end_datetime],
                                    stock_movements__movement_type='out')),
                movement_count=Count('stock_movements', 
                                   filter=Q(stock_movements__created_at__range=[start_datetime, end_datetime]))
            ).order_by('-movement_count', 'name')
            
            # Paginate items
            paginator = Paginator(items, 20)
            items_page = paginator.get_page(page)
            
            # Calculate summary
            total_items = items.count()
            total_value = sum(item.current_stock * (item.unit_cost or 0) for item in items)
            low_stock_items = items.filter(current_stock__lte=F('minimum_stock_level')).count()
            
            return {
                'items': items_page,
                'summary': {
                    'total_items': total_items,
                    'total_value': total_value,
                    'low_stock_items': low_stock_items,
                    'debug_info': f"Items with movements: {items.filter(movement_count__gt=0).count()}",
                },
                'pagination': self._get_pagination_data(items_page, paginator)
            }
        except Exception as e:
            return {
                'items': [],
                'summary': {},
                'pagination': {},
                'error': f'Inventory report error: {str(e)}'
            }
    
    def _get_services_data(self, start_date, end_date, page):
        """Get services-specific data"""
        from django.core.paginator import Paginator
        
        try:
            # Convert dates to datetime for proper filtering
            start_datetime, end_datetime = self._get_datetime_range(start_date, end_date)
            
            # Get services with performance metrics
            services = Service.objects.select_related('category').annotate(
                orders_count=Count('order_items__order',
                                 filter=Q(order_items__order__created_at__range=[start_datetime, end_datetime])),
                total_revenue=Sum('order_items__total_price',
                                filter=Q(order_items__order__created_at__range=[start_datetime, end_datetime])),
                avg_rating=Avg('order_items__rating',
                             filter=Q(order_items__order__created_at__range=[start_datetime, end_datetime]))
            ).order_by('-total_revenue', 'name')
            
            # Paginate services
            paginator = Paginator(services, 20)
            services_page = paginator.get_page(page)
            
            # Calculate summary
            total_services = services.count()
            active_services = services.filter(orders_count__gt=0).count()
            total_orders = sum(s.orders_count or 0 for s in services)
            total_revenue = sum(s.total_revenue or 0 for s in services)
            
            return {
                'items': services_page,
                'summary': {
                    'total_services': total_services,
                    'active_services': active_services,
                    'total_orders': total_orders,
                    'total_revenue': total_revenue,
                    'debug_info': f"Services with orders: {active_services} out of {total_services}",
                },
                'pagination': self._get_pagination_data(services_page, paginator)
            }
        except Exception as e:
            return {
                'items': [],
                'summary': {},
                'pagination': {},
                'error': f'Services report error: {str(e)}'
            }
    
    def _get_customers_data(self, start_date, end_date, page):
        """Get customers-specific data"""
        from django.core.paginator import Paginator
        
        # Convert dates to datetime for proper filtering
        start_datetime, end_datetime = self._get_datetime_range(start_date, end_date)
        
        # Get customers with their activity in the date range
        customers = Customer.objects.annotate(
            orders_count=Count('service_orders',
                             filter=Q(service_orders__created_at__range=[start_datetime, end_datetime])),
            customer_total_spent=Sum('service_orders__total_amount',
                          filter=Q(service_orders__created_at__range=[start_datetime, end_datetime])),
            last_order=Max('service_orders__created_at',
                         filter=Q(service_orders__created_at__range=[start_datetime, end_datetime]))
        ).order_by('-customer_total_spent')
        
        # Paginate customers
        paginator = Paginator(customers, 20)
        customers_page = paginator.get_page(page)
        
        # Calculate summary
        total_customers = customers.count()
        active_customers = customers.filter(orders_count__gt=0).count()
        total_revenue = sum(c.customer_total_spent or 0 for c in customers)
        avg_order_value = total_revenue / max(sum(c.orders_count or 0 for c in customers), 1)
        
        return {
            'items': customers_page,
            'summary': {
                'total_customers': total_customers,
                'active_customers': active_customers,
                'total_revenue': total_revenue,
                'avg_order_value': avg_order_value,
            },
            'pagination': self._get_pagination_data(customers_page, paginator)
        }
    
    def _get_employees_data(self, start_date, end_date, page):
        """Get employees-specific data"""
        from django.core.paginator import Paginator
        
        # Convert dates to datetime for proper filtering
        start_datetime, end_datetime = self._get_datetime_range(start_date, end_date)
        
        # Get employees with their performance metrics
        employees = Employee.objects.select_related('department').annotate(
            orders_handled=Count('assigned_orders',
                               filter=Q(assigned_orders__created_at__range=[start_datetime, end_datetime])),
            revenue_generated=Sum('assigned_orders__total_amount',
                                filter=Q(assigned_orders__created_at__range=[start_datetime, end_datetime])),
            completed_orders=Count('assigned_orders',
                                 filter=Q(assigned_orders__created_at__range=[start_datetime, end_datetime],
                                         assigned_orders__status='completed'))
        ).order_by('-revenue_generated')
        
        # Paginate employees
        paginator = Paginator(employees, 20)
        employees_page = paginator.get_page(page)
        
        # Calculate summary
        total_employees = employees.count()
        active_employees = employees.filter(orders_handled__gt=0).count()
        total_orders = sum(e.orders_handled or 0 for e in employees)
        total_revenue = sum(e.revenue_generated or 0 for e in employees)
        
        return {
            'items': employees_page,
            'summary': {
                'total_employees': total_employees,
                'active_employees': active_employees,
                'total_orders': total_orders,
                'total_revenue': total_revenue,
            },
            'pagination': self._get_pagination_data(employees_page, paginator)
        }
    
    def _get_payments_data(self, start_date, end_date, page):
        """Get payments-specific data"""
        from django.core.paginator import Paginator
        
        # Convert dates to datetime for proper filtering
        start_datetime, end_datetime = self._get_datetime_range(start_date, end_date)
        
        # Get payments in the date range
        payments = Payment.objects.select_related('payment_method', 'service_order', 'customer').filter(
            created_at__range=[start_datetime, end_datetime]
        ).order_by('-created_at')
        
        # Paginate payments
        paginator = Paginator(payments, 20)
        payments_page = paginator.get_page(page)
        
        # Calculate summary
        total_payments = payments.aggregate(Sum('amount'))['amount__sum'] or 0
        payment_count = payments.count()
        
        # Payment method breakdown
        method_breakdown = payments.values('payment_method__name').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-total')
        
        return {
            'items': payments_page,
            'summary': {
                'total_payments': total_payments,
                'payment_count': payment_count,
                'avg_payment': total_payments / max(payment_count, 1),
                'method_breakdown': list(method_breakdown),
            },
            'pagination': self._get_pagination_data(payments_page, paginator)
        }
    
    def _get_expenses_data(self, start_date, end_date, page):
        """Get expenses-specific data"""
        from django.core.paginator import Paginator
        
        # Get expenses in the date range
        expenses = Expense.objects.select_related('category', 'vendor').filter(
            expense_date__range=[start_date, end_date]
        ).order_by('-expense_date')
        
        # Paginate expenses
        paginator = Paginator(expenses, 20)
        expenses_page = paginator.get_page(page)
        
        # Calculate summary
        total_expenses = expenses.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        expense_count = expenses.count()
        
        # Category breakdown
        category_breakdown = expenses.values('category__name').annotate(
            total=Sum('total_amount'),
            count=Count('id')
        ).order_by('-total')
        
        return {
            'items': expenses_page,
            'summary': {
                'total_expenses': total_expenses,
                'expense_count': expense_count,
                'avg_expense': total_expenses / max(expense_count, 1),
                'category_breakdown': list(category_breakdown),
            },
            'pagination': self._get_pagination_data(expenses_page, paginator)
        }
    
    def _get_individual_employee_data(self, employee_id, start_date, end_date, page):
        """Get individual employee-specific data"""
        from django.core.paginator import Paginator
        
        # Convert dates to datetime for proper filtering
        start_datetime, end_datetime = self._get_datetime_range(start_date, end_date)
        
        if not employee_id:
            return {'error': 'Employee ID is required'}
        
        try:
            employee = Employee.objects.get(id=employee_id)
        except Employee.DoesNotExist:
            return {'error': 'Employee not found'}
        
        # Get employee's orders in the date range
        orders = ServiceOrder.objects.select_related('customer').filter(
            assigned_attendant=employee,
            created_at__range=[start_datetime, end_datetime]
        ).order_by('-created_at')
        
        # Paginate orders
        paginator = Paginator(orders, 20)
        orders_page = paginator.get_page(page)
        
        # Calculate employee-specific summary
        total_orders = orders.count()
        total_revenue = orders.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        completed_orders = orders.filter(status='completed').count()
        avg_order_value = total_revenue / max(total_orders, 1)
        completion_rate = (completed_orders / max(total_orders, 1)) * 100
        
        # Get attendance data if available
        try:
            from apps.employees.models import Attendance
            attendance_records = Attendance.objects.filter(
                employee=employee,
                date__range=[start_date, end_date]
            )
            total_days = attendance_records.count()
            present_days = attendance_records.filter(status='present').count()
            attendance_rate = (present_days / max(total_days, 1)) * 100 if total_days > 0 else 0
        except:
            attendance_rate = 0
        
        return {
            'employee': employee,
            'items': orders_page,
            'summary': {
                'orders_handled': total_orders,
                'total_orders': total_orders,  # For consistency with template
                'revenue_generated': total_revenue,
                'total_revenue': total_revenue,  # For consistency with template
                'completed_orders': completed_orders,
                'avg_order_value': avg_order_value,
                'completion_rate': completion_rate,
                'attendance_rate': attendance_rate,
            },
            'pagination': self._get_pagination_data(orders_page, paginator)
        }
    
    # ============== ADVANCED REPORT DATA METHODS ==============
    
    def _get_financial_summary_data(self, start_date, end_date, page):
        """Get financial summary data"""
        from django.core.paginator import Paginator
        
        # Convert dates to datetime for proper filtering
        start_datetime, end_datetime = self._get_datetime_range(start_date, end_date)
        
        # Get revenue and expense data
        revenue = Payment.objects.filter(
            created_at__range=[start_datetime, end_datetime]
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        expenses = Expense.objects.filter(
            expense_date__range=[start_date, end_date]
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        # Get recent financial transactions
        transactions = []
        
        # Add payments as positive transactions
        payments = Payment.objects.select_related('payment_method', 'service_order').filter(
            created_at__range=[start_datetime, end_datetime]
        ).order_by('-created_at')[:50]
        
        for payment in payments:
            transactions.append({
                'type': 'Revenue',
                'amount': payment.amount,
                'description': f"Payment for Order #{payment.service_order.order_number if payment.service_order else 'N/A'}",
                'date': payment.created_at.date() if hasattr(payment.created_at, 'date') else payment.created_at,
                'category': payment.payment_method.name if payment.payment_method else 'Unknown'
            })
        
        # Add expenses as negative transactions
        expense_items = Expense.objects.select_related('category', 'vendor').filter(
            expense_date__range=[start_date, end_date]
        ).order_by('-expense_date')[:50]
        
        for expense in expense_items:
            transactions.append({
                'type': 'Expense',
                'amount': -expense.total_amount,
                'description': expense.description or f"Expense - {expense.category.name if expense.category else 'General'}",
                'date': expense.expense_date,
                'category': expense.category.name if expense.category else 'General'
            })
        
        # Sort transactions by date
        transactions.sort(key=lambda x: x['date'], reverse=True)
        
        # Paginate transactions
        paginator = Paginator(transactions, 20)
        transactions_page = paginator.get_page(page)
        
        profit = revenue - expenses
        profit_margin = (profit / max(revenue, 1)) * 100
        
        return {
            'items': transactions_page,
            'summary': {
                'total_revenue': revenue,
                'total_expenses': expenses,
                'net_profit': profit,
                'profit_margin': profit_margin,
            },
            'pagination': self._get_pagination_data(transactions_page, paginator)
        }
    
    def _get_daily_summary_data(self, start_date, end_date, page):
        """Get daily summary data"""
        from django.core.paginator import Paginator
        
        # Convert dates to datetime for proper filtering
        start_datetime, end_datetime = self._get_datetime_range(start_date, end_date)
        
        # Get daily aggregated data
        daily_data = ServiceOrder.objects.filter(
            created_at__range=[start_datetime, end_datetime]
        ).values('created_at__date').annotate(
            orders_count=Count('id'),
            revenue=Sum('total_amount'),
            completed_orders=Count('id', filter=Q(status='completed'))
        ).order_by('-created_at__date')
        
        # Convert to list for pagination
        daily_list = list(daily_data)
        
        # Paginate daily data
        paginator = Paginator(daily_list, 20)
        daily_page = paginator.get_page(page)
        
        # Calculate summary
        total_days = len(daily_list)
        avg_daily_orders = sum(day['orders_count'] for day in daily_list) / max(total_days, 1)
        avg_daily_revenue = sum(day['revenue'] or 0 for day in daily_list) / max(total_days, 1)
        
        return {
            'items': daily_page,
            'summary': {
                'total_days': total_days,
                'avg_daily_orders': avg_daily_orders,
                'avg_daily_revenue': avg_daily_revenue,
            },
            'pagination': self._get_pagination_data(daily_page, paginator)
        }
    
    def _get_weekly_summary_data(self, start_date, end_date, page):
        """Get weekly summary data"""
        from django.core.paginator import Paginator
        from datetime import datetime, timedelta
        
        try:
            # Convert dates to datetime for proper filtering
            start_datetime, end_datetime = self._get_datetime_range(start_date, end_date)
            
            # Get all orders in the date range
            orders = ServiceOrder.objects.filter(
                created_at__range=[start_datetime, end_datetime]
            ).order_by('-created_at')
            
            # Group orders by week manually
            weekly_data = {}
            for order in orders:
                # Get the start of the week (Monday)
                order_date = order.created_at.date()
                week_start = order_date - timedelta(days=order_date.weekday())
                week_key = week_start.strftime('%Y-%m-%d')
                
                if week_key not in weekly_data:
                    weekly_data[week_key] = {
                        'week': week_start,
                        'orders_count': 0,
                        'revenue': 0,
                        'completed_orders': 0
                    }
                
                weekly_data[week_key]['orders_count'] += 1
                weekly_data[week_key]['revenue'] += float(order.total_amount or 0)
                if order.status == 'completed':
                    weekly_data[week_key]['completed_orders'] += 1
            
            # Convert to list and sort by week
            weekly_list = list(weekly_data.values())
            weekly_list.sort(key=lambda x: x['week'], reverse=True)
            
            # Paginate weekly data
            paginator = Paginator(weekly_list, 20)
            weekly_page = paginator.get_page(page)
            
            # Calculate summary
            total_weeks = len(weekly_list)
            avg_weekly_orders = sum(week['orders_count'] for week in weekly_list) / max(total_weeks, 1)
            avg_weekly_revenue = sum(week['revenue'] for week in weekly_list) / max(total_weeks, 1)
            
            return {
                'items': weekly_page,
                'summary': {
                    'total_weeks': total_weeks,
                    'avg_weekly_orders': avg_weekly_orders,
                    'avg_weekly_revenue': avg_weekly_revenue,
                },
                'pagination': self._get_pagination_data(weekly_page, paginator)
            }
        except Exception as e:
            return {
                'items': [],
                'summary': {
                    'total_weeks': 0,
                    'avg_weekly_orders': 0,
                    'avg_weekly_revenue': 0,
                },
                'pagination': {},
                'error': f'Error generating weekly summary: {str(e)}'
            }
    
    def _get_monthly_summary_data(self, start_date, end_date, page):
        """Get monthly summary data"""
        from django.core.paginator import Paginator
        from datetime import datetime
        
        try:
            # Convert dates to datetime for proper filtering
            start_datetime, end_datetime = self._get_datetime_range(start_date, end_date)
            
            # Get all orders in the date range
            orders = ServiceOrder.objects.filter(
                created_at__range=[start_datetime, end_datetime]
            ).order_by('-created_at')
            
            # Group orders by month manually
            monthly_data = {}
            for order in orders:
                # Get the first day of the month
                order_date = order.created_at.date()
                month_key = order_date.strftime('%Y-%m')
                month_start = order_date.replace(day=1)
                
                if month_key not in monthly_data:
                    monthly_data[month_key] = {
                        'month': month_start,
                        'orders_count': 0,
                        'revenue': 0,
                        'completed_orders': 0
                    }
                
                monthly_data[month_key]['orders_count'] += 1
                monthly_data[month_key]['revenue'] += float(order.total_amount or 0)
                if order.status == 'completed':
                    monthly_data[month_key]['completed_orders'] += 1
            
            # Convert to list and sort by month
            monthly_list = list(monthly_data.values())
            monthly_list.sort(key=lambda x: x['month'], reverse=True)
            
            # Paginate monthly data
            paginator = Paginator(monthly_list, 20)
            monthly_page = paginator.get_page(page)
            
            # Calculate summary
            total_months = len(monthly_list)
            avg_monthly_orders = sum(month['orders_count'] for month in monthly_list) / max(total_months, 1)
            avg_monthly_revenue = sum(month['revenue'] for month in monthly_list) / max(total_months, 1)
            
            return {
                'items': monthly_page,
                'summary': {
                    'total_months': total_months,
                    'avg_monthly_orders': avg_monthly_orders,
                    'avg_monthly_revenue': avg_monthly_revenue,
                },
                'pagination': self._get_pagination_data(monthly_page, paginator)
            }
        except Exception as e:
            return {
                'items': [],
                'summary': {
                    'total_months': 0,
                    'avg_monthly_orders': 0,
                    'avg_monthly_revenue': 0,
                },
                'pagination': {},
                'error': f'Error generating monthly summary: {str(e)}'
            }
    
    def _get_sales_analysis_data(self, start_date, end_date, page):
        """Get sales analysis data"""
        from django.core.paginator import Paginator
        
        # Convert dates to datetime for proper filtering
        start_datetime, end_datetime = self._get_datetime_range(start_date, end_date)
        
        # Get sales by service
        sales_data = ServiceOrderItem.objects.filter(
            order__created_at__range=[start_datetime, end_datetime]
        ).values(
            'service__name', 'service__category__name'
        ).annotate(
            quantity_sold=Sum('quantity'),
            total_revenue=Sum('total_price'),
            orders_count=Count('order', distinct=True)
        ).order_by('-total_revenue')
        
        # Convert to list for pagination
        sales_list = list(sales_data)
        
        # Paginate sales data
        paginator = Paginator(sales_list, 20)
        sales_page = paginator.get_page(page)
        
        # Calculate summary
        total_services = len(sales_list)
        total_sales_revenue = sum(item['total_revenue'] or 0 for item in sales_list)
        total_items_sold = sum(item['quantity_sold'] or 0 for item in sales_list)
        
        return {
            'items': sales_page,
            'summary': {
                'total_services': total_services,
                'total_sales_revenue': total_sales_revenue,
                'total_items_sold': total_items_sold,
            },
            'pagination': self._get_pagination_data(sales_page, paginator)
        }
    
    def _get_customer_analytics_data(self, start_date, end_date, page):
        """Get customer analytics data"""
        from django.core.paginator import Paginator
        
        try:
            # Convert dates to datetime for proper filtering
            start_datetime, end_datetime = self._get_datetime_range(start_date, end_date)
            
            # Get customer behavior data
            customer_data = Customer.objects.annotate(
                total_orders=Count('service_orders', 
                                 filter=Q(service_orders__created_at__range=[start_datetime, end_datetime])),
                total_spent=Sum('service_orders__total_amount',
                              filter=Q(service_orders__created_at__range=[start_datetime, end_datetime])),
                avg_order_value=Avg('service_orders__total_amount',
                                  filter=Q(service_orders__created_at__range=[start_datetime, end_datetime])),
                last_order_date=Max('service_orders__created_at',
                                  filter=Q(service_orders__created_at__range=[start_datetime, end_datetime]))
            ).filter(total_orders__gt=0).order_by('-total_spent')
            
            # Paginate customer data
            paginator = Paginator(customer_data, 20)
            customer_page = paginator.get_page(page)
            
            # Calculate summary
            total_active_customers = customer_data.count()
            total_customer_value = sum(c.total_spent or 0 for c in customer_data)
            avg_customer_value = total_customer_value / max(total_active_customers, 1)
            
            # Debug information
            debug_info = {
                'customers_found': total_active_customers,
                'total_value': total_customer_value,
                'avg_value': avg_customer_value,
                'date_range': f"{start_date} to {end_date}",
                'query_filter': str(customer_data.query)
            }
            
            return {
                'items': customer_page,
                'summary': {
                    'total_active_customers': total_active_customers,
                    'total_customer_value': total_customer_value,
                    'avg_customer_value': avg_customer_value,
                },
                'pagination': self._get_pagination_data(customer_page, paginator),
                'debug_info': debug_info
            }
        except Exception as e:
            return {
                'items': [],
                'summary': {
                    'total_active_customers': 0,
                    'total_customer_value': 0,
                    'avg_customer_value': 0,
                },
                'pagination': {},
                'error': f"Error generating customer analytics: {str(e)}",
                'debug_info': {'error': str(e)}
            }
    
    def _get_supplier_report_data(self, start_date, end_date, page):
        """Get supplier report data"""
        from django.core.paginator import Paginator
        
        # Get supplier data if the model exists
        try:
            suppliers = Supplier.objects.annotate(
                orders_count=Count('purchaseorder',
                                 filter=Q(purchaseorder__created_at__range=[start_datetime, end_datetime])),
                total_purchased=Sum('purchaseorder__total_amount',
                                  filter=Q(purchaseorder__created_at__range=[start_datetime, end_datetime]))
            ).order_by('-total_purchased')
            
            # Paginate suppliers
            paginator = Paginator(suppliers, 20)
            suppliers_page = paginator.get_page(page)
            
            # Calculate summary
            total_suppliers = suppliers.count()
            active_suppliers = suppliers.filter(orders_count__gt=0).count()
            total_purchases = sum(s.total_purchased or 0 for s in suppliers)
            
            return {
                'items': suppliers_page,
                'summary': {
                    'total_suppliers': total_suppliers,
                    'active_suppliers': active_suppliers,
                    'total_purchases': total_purchases,
                },
                'pagination': self._get_pagination_data(suppliers_page, paginator)
            }
        except:
            # Return empty data if supplier model doesn't exist or has issues
            return {
                'items': [],
                'summary': {
                    'total_suppliers': 0,
                    'active_suppliers': 0,
                    'total_purchases': 0,
                },
                'pagination': {},
                'error': 'Supplier data not available'
            }
    
    # ============== NEW REPORT TYPES ==============
    
    def _get_vehicle_analysis_data(self, start_date, end_date, page):
        """Get vehicle analysis data"""
        from django.core.paginator import Paginator
        
        try:
            # Get vehicles with service frequency
            vehicles = Vehicle.objects.select_related('customer').annotate(
                service_count=Count('service_orders',
                                  filter=Q(service_orders__created_at__range=[start_datetime, end_datetime])),
                total_spent=Sum('service_orders__total_amount',
                              filter=Q(service_orders__created_at__range=[start_datetime, end_datetime])),
                last_service=Max('service_orders__created_at',
                               filter=Q(service_orders__created_at__range=[start_datetime, end_datetime]))
            ).filter(service_count__gt=0).order_by('-service_count')
            
            # Paginate vehicles
            paginator = Paginator(vehicles, 20)
            vehicles_page = paginator.get_page(page)
            
            # Calculate summary
            total_vehicles = vehicles.count()
            total_revenue = sum(v.total_spent or 0 for v in vehicles)
            avg_services_per_vehicle = sum(v.service_count or 0 for v in vehicles) / max(total_vehicles, 1)
            
            return {
                'items': vehicles_page,
                'summary': {
                    'total_vehicles': total_vehicles,
                    'total_revenue': total_revenue,
                    'avg_services_per_vehicle': avg_services_per_vehicle,
                },
                'pagination': self._get_pagination_data(vehicles_page, paginator)
            }
        except:
            return {'error': 'Vehicle data not available', 'items': [], 'summary': {}}
    
    def _get_service_packages_data(self, start_date, end_date, page):
        """Get service packages data"""
        from django.core.paginator import Paginator
        
        try:
            # Get service packages with usage statistics
            packages = ServicePackage.objects.annotate(
                orders_count=Count('serviceorder',
                                 filter=Q(serviceorder__created_at__range=[start_datetime, end_datetime])),
                total_revenue=Sum('serviceorder__total_amount',
                                filter=Q(serviceorder__created_at__range=[start_datetime, end_datetime]))
            ).order_by('-orders_count')
            
            # Paginate packages
            paginator = Paginator(packages, 20)
            packages_page = paginator.get_page(page)
            
            # Calculate summary
            total_packages = packages.count()
            active_packages = packages.filter(orders_count__gt=0).count()
            total_revenue = sum(p.total_revenue or 0 for p in packages)
            
            return {
                'items': packages_page,
                'summary': {
                    'total_packages': total_packages,
                    'active_packages': active_packages,
                    'total_revenue': total_revenue,
                },
                'pagination': self._get_pagination_data(packages_page, paginator)
            }
        except:
            return {'error': 'Service packages data not available', 'items': [], 'summary': {}}
    
    def _get_loyalty_program_data(self, start_date, end_date, page):
        """Get loyalty program data"""
        from django.core.paginator import Paginator
        
        try:
            # Get customers with loyalty points activity in the date range
            customers_with_loyalty = Customer.objects.annotate(
                orders_count=Count('service_orders',
                                 filter=Q(service_orders__created_at__range=[start_datetime, end_datetime])),
                points_earned=Sum('service_orders__total_amount',
                                filter=Q(service_orders__created_at__range=[start_datetime, end_datetime])) / 10
            ).filter(orders_count__gt=0, loyalty_points__gt=0).order_by('-loyalty_points')
            
            # Paginate customers
            paginator = Paginator(customers_with_loyalty, 20)
            loyalty_page = paginator.get_page(page)
            
            # Calculate summary
            total_members = customers_with_loyalty.count()
            total_points = sum(c.loyalty_points or 0 for c in customers_with_loyalty)
            avg_points_per_member = total_points / max(total_members, 1)
            
            return {
                'items': loyalty_page,
                'summary': {
                    'total_members': total_members,
                    'total_points': total_points,
                    'avg_points_per_member': avg_points_per_member,
                },
                'pagination': self._get_pagination_data(loyalty_page, paginator)
            }
        except:
            return {'error': 'Loyalty program data not available', 'items': [], 'summary': {}}
    
    def _get_attendance_report_data(self, start_date, end_date, page):
        """Get employee attendance data"""
        from django.core.paginator import Paginator
        
        try:
            # Get attendance records
            attendance = Attendance.objects.select_related('employee').filter(
                date__range=[start_date, end_date]
            ).order_by('-date', 'employee__employee_id')
            
            # Paginate attendance
            paginator = Paginator(attendance, 20)
            attendance_page = paginator.get_page(page)
            
            # Calculate summary
            total_records = attendance.count()
            present_count = attendance.filter(status='present').count()
            absent_count = attendance.filter(status='absent').count()
            late_count = attendance.filter(status='late').count()
            attendance_rate = (present_count / max(total_records, 1)) * 100
            
            return {
                'items': attendance_page,
                'summary': {
                    'total_records': total_records,
                    'present_count': present_count,
                    'absent_count': absent_count,
                    'late_count': late_count,
                    'attendance_rate': attendance_rate,
                },
                'pagination': self._get_pagination_data(attendance_page, paginator)
            }
        except:
            return {'error': 'Attendance data not available', 'items': [], 'summary': {}}
    
    def _get_department_performance_data(self, start_date, end_date, page):
        """Get department performance data"""
        from django.core.paginator import Paginator
        
        try:
            # Get departments with performance metrics
            departments = Department.objects.annotate(
                employee_count=Count('employees', filter=Q(employees__is_active=True)),
                orders_handled=Count('employees__assigned_orders',
                                   filter=Q(employees__assigned_orders__created_at__range=[start_datetime, end_datetime])),
                revenue_generated=Sum('employees__assigned_orders__total_amount',
                                    filter=Q(employees__assigned_orders__created_at__range=[start_datetime, end_datetime]))
            ).order_by('-revenue_generated')
            
            # Paginate departments
            paginator = Paginator(departments, 20)
            departments_page = paginator.get_page(page)
            
            # Calculate summary
            total_departments = departments.count()
            total_employees = sum(d.employee_count or 0 for d in departments)
            total_revenue = sum(d.revenue_generated or 0 for d in departments)
            
            return {
                'items': departments_page,
                'summary': {
                    'total_departments': total_departments,
                    'total_employees': total_employees,
                    'total_revenue': total_revenue,
                },
                'pagination': self._get_pagination_data(departments_page, paginator)
            }
        except:
            return {'error': 'Department data not available', 'items': [], 'summary': {}}
    
    def _get_subscription_analysis_data(self, start_date, end_date, page):
        """Get subscription analysis data"""
        from django.core.paginator import Paginator
        
        try:
            # Get subscriptions with activity
            subscriptions = Subscription.objects.select_related('customer').filter(
                created_at__range=[start_datetime, end_datetime]
            ).order_by('-created_at')
            
            # Paginate subscriptions
            paginator = Paginator(subscriptions, 20)
            subscriptions_page = paginator.get_page(page)
            
            # Calculate summary
            total_subscriptions = subscriptions.count()
            active_subscriptions = subscriptions.filter(status='active').count()
            total_revenue = subscriptions.aggregate(Sum('amount'))['amount__sum'] or 0
            
            return {
                'items': subscriptions_page,
                'summary': {
                    'total_subscriptions': total_subscriptions,
                    'active_subscriptions': active_subscriptions,
                    'total_revenue': total_revenue,
                },
                'pagination': self._get_pagination_data(subscriptions_page, paginator)
            }
        except:
            return {'error': 'Subscription data not available', 'items': [], 'summary': {}}
    
    # ============== HELPER METHODS ==============
    
    def _get_pagination_data(self, page_obj, paginator):
        """Get pagination data for templates"""
        return {
            'has_previous': page_obj.has_previous(),
            'has_next': page_obj.has_next(),
            'previous_page_number': page_obj.previous_page_number() if page_obj.has_previous() else None,
            'next_page_number': page_obj.next_page_number() if page_obj.has_next() else None,
            'num_pages': paginator.num_pages,
            'page_range': paginator.page_range,
        }
    
    # ============== EXPORT HANDLING ==============
    
    def _handle_export(self, request, export_format):
        """Handle PDF and Excel exports with focused report data"""
        report_type = request.GET.get('report_type', 'business_overview')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        # Set default date range if not provided
        if not start_date or not end_date:
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=30)
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Get all report data (not paginated for export)
        report_data = self._get_export_data(report_type, start_date, end_date)
        
        if export_format == 'pdf':
            return self._generate_pdf_export(report_data, request.tenant)
        else:  # excel
            return self._generate_excel_export(report_data, request.tenant)
    
    def _get_export_data(self, report_type, start_date, end_date):
        """Get all data for export (no pagination)"""
        # Convert dates to datetime for proper filtering
        start_datetime, end_datetime = self._get_datetime_range(start_date, end_date)
        
        data = {
            'title': self._get_report_title(report_type),
            'type': report_type,
            'period': f"{start_date.strftime('%B %d, %Y')} - {end_date.strftime('%B %d, %Y')}",
            'items': [],
            'summary': {},
        }
        
        try:
            # Get data without pagination by calling the same methods with page=1 and extracting items
            paginated_data = self._get_report_data(report_type, start_date, end_date, 1)
            
            # For export, we want all items, not just the paginated ones
            if report_type == 'business_overview':
                data['items'] = list(ServiceOrder.objects.select_related('customer', 'assigned_attendant', 'vehicle').filter(
                    created_at__range=[start_datetime, end_datetime]
                ).order_by('-created_at'))
            elif report_type == 'inventory':
                # Get inventory items with movement data
                items = InventoryItem.objects.select_related('category', 'unit').annotate(
                    total_in=Sum('stock_movements__quantity', 
                                filter=Q(stock_movements__created_at__range=[start_datetime, end_datetime],
                                       stock_movements__movement_type='in')),
                    total_out=Sum('stock_movements__quantity', 
                                 filter=Q(stock_movements__created_at__range=[start_datetime, end_datetime],
                                        stock_movements__movement_type='out')),
                    movement_count=Count('stock_movements', 
                                       filter=Q(stock_movements__created_at__range=[start_datetime, end_datetime]))
                ).order_by('-movement_count', 'name')
                data['items'] = list(items)
            elif report_type == 'services':
                # Get services with performance metrics
                services = Service.objects.select_related('category').annotate(
                    orders_count=Count('order_items__order',
                                     filter=Q(order_items__order__created_at__range=[start_datetime, end_datetime])),
                    total_revenue=Sum('order_items__total_price',
                                    filter=Q(order_items__order__created_at__range=[start_datetime, end_datetime])),
                    avg_rating=Avg('order_items__rating',
                                 filter=Q(order_items__order__created_at__range=[start_datetime, end_datetime]))
                ).order_by('-total_revenue', 'name')
                data['items'] = list(services)
            elif report_type == 'customers':
                # Get customers with their activity in the date range
                customers = Customer.objects.annotate(
                    total_orders=Count('service_orders', 
                                     filter=Q(service_orders__created_at__range=[start_datetime, end_datetime])),
                    total_spent=Sum('service_orders__total_amount',
                                  filter=Q(service_orders__created_at__range=[start_datetime, end_datetime])),
                    avg_order_value=Avg('service_orders__total_amount',
                                      filter=Q(service_orders__created_at__range=[start_datetime, end_datetime]))
                ).order_by('-total_spent')
                data['items'] = list(customers)
            elif report_type == 'employees':
                data['items'] = list(Employee.objects.select_related('department', 'position').all())
            elif report_type == 'payments':
                data['items'] = list(Payment.objects.select_related('payment_method', 'service_order', 'customer').filter(
                    created_at__range=[start_datetime, end_datetime]
                ).order_by('-created_at'))
            elif report_type == 'expenses':
                data['items'] = list(Expense.objects.select_related('category', 'vendor').filter(
                    expense_date__range=[start_date, end_date]
                ).order_by('-expense_date'))
            else:
                # For other report types, use the paginated data items
                data['items'] = list(paginated_data.get('items', []))
            
            data['summary'] = paginated_data.get('summary', {})
            
        except Exception as e:
            data['error'] = f"Error generating {report_type} export: {str(e)}"
            
        return data
    
    def _generate_pdf_export(self, report_data, tenant):
        """Generate comprehensive PDF for specific report type"""
        if not PDF_AVAILABLE:
            return JsonResponse({'error': 'PDF generation not available'}, status=500)
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.8*inch, bottomMargin=1*inch)
        styles = getSampleStyleSheet()
        story = []
        
        # Header with tenant information
        header_data = [
            [tenant.name, f"Generated: {timezone.now().strftime('%B %d, %Y at %I:%M %p')}"],
            [getattr(tenant, 'address', 'Address not available'), f"Report Period: {report_data.get('period', '')}"],
            [getattr(tenant, 'phone', ''), '']
        ]
        header_table = Table(header_data, colWidths=[4*inch, 2.5*inch])
        header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 20))
        
        # Main Title
        title = Paragraph(f"<b>{report_data.get('title', 'Business Report')}</b>", styles['Title'])
        story.append(title)
        story.append(Spacer(1, 20))
        
        # Summary section
        if report_data.get('summary'):
            summary_title = Paragraph("<b>Summary</b>", styles['Heading2'])
            story.append(summary_title)
            story.append(Spacer(1, 10))
            
            summary_data = []
            for key, value in report_data['summary'].items():
                if key != 'error' and value is not None:
                    formatted_key = key.replace('_', ' ').title()
                    if 'revenue' in key.lower() or 'profit' in key.lower() or 'value' in key.lower() or 'amount' in key.lower():
                        formatted_value = f"KES {value:,.2f}"
                    elif 'rate' in key.lower() or 'margin' in key.lower():
                        formatted_value = f"{value:.1f}%" if isinstance(value, (int, float)) else str(value)
                    else:
                        formatted_value = str(value)
                    summary_data.append([formatted_key, formatted_value])
            
            if summary_data:
                summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
                summary_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 12),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
                ]))
                story.append(summary_table)
                story.append(Spacer(1, 30))
        
        # Detailed Data Table
        if report_data.get('items'):
            data_title = Paragraph("<b>Detailed Data</b>", styles['Heading2'])
            story.append(data_title)
            story.append(Spacer(1, 10))
            
            # Generate table data based on report type
            table_data = self._generate_pdf_table_data(report_data)
            
            if table_data:
                # Create table with appropriate column widths
                col_count = len(table_data[0]) if table_data else 0
                col_width = 6.5*inch / col_count if col_count > 0 else 1*inch
                
                data_table = Table(table_data, colWidths=[col_width] * col_count)
                data_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
                ]))
                story.append(data_table)
        
        # Add signature section for individual employee reports
        if report_data.get('type') == 'individual_employee' and report_data.get('employee'):
            story.append(Spacer(1, 30))
            story.append(Paragraph("<b>Signatures</b>", styles['Heading2']))
            story.append(Spacer(1, 20))
            
            # Signature table
            signature_data = [
                ['Employee Name:', report_data['employee'].full_name, 'Supervisor:'],
                ['', '', ''],
                ['Signature: ___________________', '', 'Signature: ___________________'],
                ['', '', ''],
                [f"Date: {timezone.now().strftime('%B %d, %Y')}", '', f"Date: {timezone.now().strftime('%B %d, %Y')}"]
            ]
            signature_table = Table(signature_data, colWidths=[2.5*inch, 1*inch, 2.5*inch])
            signature_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(signature_table)
        
        # Footer
        story.append(Spacer(1, 30))
        footer_text = f"Report generated by {tenant.name} - AutoWash Management System"
        footer = Paragraph(footer_text, styles['Normal'])
        story.append(footer)
        
        doc.build(story)
        buffer.seek(0)
        
        response = HttpResponse(buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{tenant.name}_{report_data.get("type", "report")}_report.pdf"'
        return response
    
    def _generate_pdf_table_data(self, report_data):
        """Generate table data for PDF based on report type"""
        report_type = report_data.get('type')
        items = report_data.get('items', [])
        
        if not items:
            return []
        
        if report_type == 'business_overview':
            headers = ['Order #', 'Customer', 'Attendant', 'Amount', 'Status', 'Date']
            table_data = [headers]
            total_amount = 0
            for item in items[:50]:  # Limit to 50 items for PDF
                amount = float(item.total_amount or 0)
                total_amount += amount
                table_data.append([
                    item.order_number,
                    item.customer.full_name if item.customer else 'N/A',
                    item.assigned_attendant.full_name if item.assigned_attendant else 'Unassigned',
                    f"KES {amount:,.2f}",
                    item.status.title(),
                    item.created_at.strftime('%Y-%m-%d')
                ])
            # Add total row
            table_data.append(['', '', 'TOTAL:', f"KES {total_amount:,.2f}", '', ''])
                
        elif report_type == 'inventory':
            headers = ['Item Name', 'Category', 'Current Stock', 'Stock Value', 'Movements']
            table_data = [headers]
            total_value = 0
            for item in items[:50]:
                stock_value = float(item.current_stock or 0) * float(getattr(item, 'unit_cost', 0) or 0)
                total_value += stock_value
                table_data.append([
                    item.name,
                    item.category.name if item.category else 'N/A',
                    str(item.current_stock),
                    f"KES {stock_value:,.2f}",
                    str(getattr(item, 'movement_count', 0) or 0)
                ])
            # Add total row
            table_data.append(['', '', 'TOTAL VALUE:', f"KES {total_value:,.2f}", ''])
                
        elif report_type == 'services':
            headers = ['Service Name', 'Category', 'Price', 'Orders', 'Revenue']
            table_data = [headers]
            total_revenue = 0
            for item in items[:50]:
                revenue = float(getattr(item, 'total_revenue', 0) or 0)
                total_revenue += revenue
                table_data.append([
                    item.name,
                    item.category.name if item.category else 'N/A',
                    f"KES {item.base_price:,.2f}",
                    str(getattr(item, 'orders_count', 0) or 0),
                    f"KES {revenue:,.2f}"
                ])
            # Add total row
            table_data.append(['', '', '', 'TOTAL:', f"KES {total_revenue:,.2f}"])
                
        elif report_type == 'customers' or report_type == 'customer_analytics':
            headers = ['Customer Name', 'Email', 'Phone', 'Orders', 'Total Spent']
            table_data = [headers]
            total_spent = 0
            for item in items[:50]:
                spent = float(getattr(item, 'total_spent', 0) or 0)
                total_spent += spent
                table_data.append([
                    item.full_name,
                    item.email or 'N/A',
                    item.phone_number or 'N/A',
                    str(getattr(item, 'total_orders', 0) or 0),
                    f"KES {spent:,.2f}"
                ])
            # Add total row
            table_data.append(['', '', '', 'TOTAL:', f"KES {total_spent:,.2f}"])
                
        elif report_type == 'employees':
            headers = ['Employee Name', 'Department', 'Position', 'Orders', 'Revenue']
            table_data = [headers]
            total_revenue = 0
            for item in items[:50]:
                revenue = float(getattr(item, 'revenue_generated', 0) or 0)
                total_revenue += revenue
                table_data.append([
                    item.full_name,
                    item.department.name if item.department else 'N/A',
                    item.position or 'N/A',
                    str(getattr(item, 'orders_handled', 0) or 0),
                    f"KES {revenue:,.2f}"
                ])
            # Add total row
            table_data.append(['', '', '', 'TOTAL:', f"KES {total_revenue:,.2f}"])
                
        elif report_type == 'individual_employee':
            employee = report_data.get('employee')
            if employee:
                headers = ['Date', 'Order #', 'Customer', 'Service', 'Amount', 'Status']
                table_data = [headers]
                total_amount = 0
                for item in items[:50]:
                    amount = float(item.total_amount or 0)
                    total_amount += amount
                    table_data.append([
                        item.created_at.strftime('%Y-%m-%d'),
                        item.order_number,
                        item.customer.full_name if item.customer else 'N/A',
                        'Service Order',
                        f"KES {amount:,.2f}",
                        item.status.title()
                    ])
                # Add total row
                table_data.append(['', '', '', 'TOTAL:', f"KES {total_amount:,.2f}", ''])
            else:
                return []
                
        elif report_type == 'financial_summary':
            headers = ['Date', 'Type', 'Description', 'Category', 'Amount']
            table_data = [headers]
            total_revenue = 0
            total_expenses = 0
            for item in items[:50]:
                amount = float(item.get('amount', 0) or 0)
                if item.get('type') == 'Revenue':
                    total_revenue += amount
                else:
                    total_expenses += abs(amount)
                table_data.append([
                    item.get('date', '').strftime('%Y-%m-%d') if hasattr(item.get('date', ''), 'strftime') else str(item.get('date', '')),
                    item.get('type', 'N/A'),
                    item.get('description', 'N/A')[:40],
                    item.get('category', 'N/A'),
                    f"KES {amount:,.2f}"
                ])
            # Add summary rows
            table_data.append(['', '', '', 'TOTAL REVENUE:', f"KES {total_revenue:,.2f}"])
            table_data.append(['', '', '', 'TOTAL EXPENSES:', f"KES {total_expenses:,.2f}"])
            table_data.append(['', '', '', 'NET PROFIT:', f"KES {total_revenue - total_expenses:,.2f}"])
                
        elif report_type == 'payments':
            headers = ['Date', 'Order #', 'Customer', 'Method', 'Amount']
            table_data = [headers]
            total_amount = 0
            for item in items[:50]:
                amount = float(item.amount or 0)
                total_amount += amount
                table_data.append([
                    item.created_at.strftime('%Y-%m-%d %H:%M'),
                    item.service_order.order_number if item.service_order else 'N/A',
                    item.service_order.customer.full_name if item.service_order and item.service_order.customer else 'N/A',
                    item.payment_method.name if item.payment_method else 'Cash',
                    f"KES {amount:,.2f}"
                ])
            # Add total row
            table_data.append(['', '', '', 'TOTAL:', f"KES {total_amount:,.2f}"])
        
        elif report_type == 'daily_summary':
            headers = ['Date', 'Orders Count', 'Revenue', 'Completed Orders']
            table_data = [headers]
            total_revenue = 0
            for item in items[:50]:
                revenue = float(item.get('revenue', 0) or 0)
                total_revenue += revenue
                date_str = item.get('created_at__date', 'N/A')
                if hasattr(date_str, 'strftime'):
                    date_str = date_str.strftime('%Y-%m-%d')
                table_data.append([
                    str(date_str),
                    str(item.get('orders_count', 0) or 0),
                    f"KES {revenue:,.2f}",
                    str(item.get('completed_orders', 0) or 0)
                ])
            # Add total row
            table_data.append(['', 'TOTAL:', f"KES {total_revenue:,.2f}", ''])
                
        elif report_type == 'weekly_summary':
            headers = ['Week', 'Orders Count', 'Revenue', 'Completed Orders']
            table_data = [headers]
            total_revenue = 0
            for item in items[:50]:
                revenue = float(item.get('revenue', 0) or 0)
                total_revenue += revenue
                week_str = item.get('week', 'N/A')
                if hasattr(week_str, 'strftime'):
                    week_str = week_str.strftime('%Y-W%U')
                table_data.append([
                    str(week_str),
                    str(item.get('orders_count', 0) or 0),
                    f"KES {revenue:,.2f}",
                    str(item.get('completed_orders', 0) or 0)
                ])
            # Add total row
            table_data.append(['', 'TOTAL:', f"KES {total_revenue:,.2f}", ''])
                
        elif report_type == 'monthly_summary':
            headers = ['Month', 'Orders Count', 'Revenue', 'Completed Orders']
            table_data = [headers]
            total_revenue = 0
            for item in items[:50]:
                revenue = float(item.get('revenue', 0) or 0)
                total_revenue += revenue
                month_str = item.get('month', 'N/A')
                if hasattr(month_str, 'strftime'):
                    month_str = month_str.strftime('%Y-%m')
                table_data.append([
                    str(month_str),
                    str(item.get('orders_count', 0) or 0),
                    f"KES {revenue:,.2f}",
                    str(item.get('completed_orders', 0) or 0)
                ])
            # Add total row
            table_data.append(['', 'TOTAL:', f"KES {total_revenue:,.2f}", ''])
                
        elif report_type == 'sales_analysis':
            headers = ['Date', 'Service', 'Quantity', 'Revenue', 'Category']
            table_data = [headers]
            total_revenue = 0
            for item in items[:50]:
                revenue = float(item.get('total_revenue', 0) or 0)
                total_revenue += revenue
                date_str = item.get('date', 'N/A')
                if hasattr(date_str, 'strftime'):
                    date_str = date_str.strftime('%Y-%m-%d')
                table_data.append([
                    str(date_str),
                    str(item.get('service_name', item.get('name', 'N/A'))),
                    str(item.get('quantity', item.get('orders_count', 0)) or 0),
                    f"KES {revenue:,.2f}",
                    str(item.get('category', 'N/A'))
                ])
            # Add total row
            table_data.append(['', '', '', f"KES {total_revenue:,.2f}", ''])
                
        elif report_type == 'expenses':
            headers = ['Date', 'Description', 'Category', 'Vendor', 'Amount']
            table_data = [headers]
            total_amount = 0
            for item in items[:50]:
                amount = float(item.total_amount or 0)
                total_amount += amount
                table_data.append([
                    item.expense_date.strftime('%Y-%m-%d'),
                    item.description or 'N/A',
                    item.category.name if item.category else 'N/A',
                    item.vendor.name if item.vendor else 'N/A',
                    f"KES {amount:,.2f}"
                ])
            # Add total row
            table_data.append(['', '', '', 'TOTAL:', f"KES {total_amount:,.2f}"])
        
        else:
            # Generic format for other report types
            headers = ['Item', 'Details', 'Value']
            table_data = [headers]
            for item in items[:50]:
                table_data.append([
                    str(item)[:40],
                    f"{report_type.title()} data",
                    'N/A'
                ])
        
        return table_data
    
    def _generate_excel_export(self, report_data, tenant):
        """Generate comprehensive Excel for specific report type"""
        if not EXCEL_AVAILABLE:
            return JsonResponse({'error': 'Excel generation not available'}, status=500)
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = report_data.get('title', 'Report')
        
        # Header with tenant information
        ws['A1'] = tenant.name
        ws['A1'].font = Font(bold=True, size=16)
        ws['B1'] = f"Generated: {timezone.now().strftime('%B %d, %Y at %I:%M %p')}"
        ws['B1'].font = Font(size=10)
        
        ws['A2'] = getattr(tenant, 'address', 'Address not available')
        ws['B2'] = f"Report Period: {report_data.get('period', '')}"
        ws['B2'].font = Font(bold=True)
        
        # Main title
        current_row = 4
        ws[f'A{current_row}'] = report_data.get('title', 'Business Report')
        ws[f'A{current_row}'].font = Font(bold=True, size=14)
        current_row += 2
        
        # Summary section
        if report_data.get('summary'):
            ws[f'A{current_row}'] = 'SUMMARY'
            ws[f'A{current_row}'].font = Font(bold=True, size=12)
            current_row += 1
            
            # Summary headers
            ws[f'A{current_row}'] = 'Metric'
            ws[f'B{current_row}'] = 'Value'
            ws[f'A{current_row}'].font = Font(bold=True)
            ws[f'B{current_row}'].font = Font(bold=True)
            current_row += 1
            
            for key, value in report_data['summary'].items():
                if key != 'error' and value is not None:
                    formatted_key = key.replace('_', ' ').title()
                    ws[f'A{current_row}'] = formatted_key
                    if 'revenue' in key.lower() or 'profit' in key.lower() or 'value' in key.lower() or 'amount' in key.lower():
                        ws[f'B{current_row}'] = f"KES {value:,.2f}"
                    elif 'rate' in key.lower() or 'margin' in key.lower():
                        ws[f'B{current_row}'] = f"{value:.1f}%" if isinstance(value, (int, float)) else str(value)
                    else:
                        ws[f'B{current_row}'] = str(value)
                    current_row += 1
            
            current_row += 2  # Add spacing
        
        # Detailed Data section
        if report_data.get('items'):
            ws[f'A{current_row}'] = 'DETAILED DATA'
            ws[f'A{current_row}'].font = Font(bold=True, size=12)
            current_row += 1
            
            # Generate Excel table data
            table_data = self._generate_excel_table_data(report_data)
            
            if table_data:
                # Add headers
                for col_idx, header in enumerate(table_data[0], 1):
                    cell = ws.cell(row=current_row, column=col_idx, value=header)
                    cell.font = Font(bold=True)
                    cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
                    cell.font = Font(bold=True, color="FFFFFF")
                current_row += 1
                
                # Add data rows
                for row_data in table_data[1:]:
                    for col_idx, cell_value in enumerate(row_data, 1):
                        ws.cell(row=current_row, column=col_idx, value=cell_value)
                    current_row += 1
                
                # Auto-adjust column widths
                for column in ws.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    ws.column_dimensions[column_letter].width = adjusted_width
        
        # Footer
        current_row += 2
        ws[f'A{current_row}'] = f"Report generated by {tenant.name} - AutoWash Management System"
        ws[f'A{current_row}'].font = Font(italic=True, size=9)
        
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        response = HttpResponse(
            buffer.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{tenant.name}_{report_data.get("type", "report")}_report.xlsx"'
        return response
    
    def _generate_excel_table_data(self, report_data):
        """Generate table data for Excel based on report type"""
        report_type = report_data.get('type')
        items = report_data.get('items', [])
        
        if not items:
            return []
        
        if report_type == 'business_overview':
            headers = ['Order #', 'Customer', 'Attendant', 'Amount', 'Status', 'Date']
            table_data = [headers]
            total_amount = 0
            for item in items:
                amount = float(item.total_amount or 0)
                total_amount += amount
                table_data.append([
                    item.order_number,
                    item.customer.full_name if item.customer else 'N/A',
                    item.assigned_attendant.full_name if item.assigned_attendant else 'Unassigned',
                    amount,
                    item.status.title(),
                    item.created_at.strftime('%Y-%m-%d')
                ])
            # Add total row
            table_data.append(['', '', 'TOTAL:', total_amount, '', ''])
                
        elif report_type == 'inventory':
            headers = ['Item Name', 'Category', 'Current Stock', 'Unit Price', 'Stock Value', 'Movements']
            table_data = [headers]
            total_value = 0
            for item in items:
                unit_price = float(getattr(item, 'unit_cost', 0) or 0)
                stock_value = float(item.current_stock or 0) * unit_price
                total_value += stock_value
                table_data.append([
                    item.name,
                    item.category.name if item.category else 'N/A',
                    int(item.current_stock or 0),
                    unit_price,
                    stock_value,
                    int(getattr(item, 'movement_count', 0) or 0)
                ])
            # Add total row
            table_data.append(['', '', '', 'TOTAL VALUE:', total_value, ''])
                
        elif report_type == 'services':
            headers = ['Service Name', 'Category', 'Base Price', 'Orders Count', 'Total Revenue', 'Avg Rating']
            table_data = [headers]
            total_revenue = 0
            for item in items:
                revenue = float(getattr(item, 'total_revenue', 0) or 0)
                total_revenue += revenue
                table_data.append([
                    item.name,
                    item.category.name if item.category else 'N/A',
                    float(item.base_price or 0),
                    int(getattr(item, 'orders_count', 0) or 0),
                    revenue,
                    round(float(getattr(item, 'avg_rating', 0) or 0), 2)
                ])
            # Add total row
            table_data.append(['', '', '', 'TOTAL:', total_revenue, ''])
                
        elif report_type == 'customers' or report_type == 'customer_analytics':
            headers = ['Customer Name', 'Email', 'Phone', 'Total Orders', 'Total Spent', 'Avg Order Value']
            table_data = [headers]
            total_spent = 0
            for item in items:
                spent = float(getattr(item, 'total_spent', 0) or 0)
                total_spent += spent
                table_data.append([
                    item.full_name,
                    item.email or 'N/A',
                    item.phone_number or 'N/A',
                    int(getattr(item, 'total_orders', 0) or 0),
                    spent,
                    float(getattr(item, 'avg_order_value', 0) or 0)
                ])
            # Add total row
            table_data.append(['', '', '', 'TOTAL:', total_spent, ''])
                
        elif report_type == 'employees':
            headers = ['Employee Name', 'Department', 'Position', 'Orders Handled', 'Revenue Generated', 'Avg Order Value']
            table_data = [headers]
            total_revenue = 0
            for item in items:
                revenue = float(getattr(item, 'revenue_generated', 0) or 0)
                total_revenue += revenue
                table_data.append([
                    item.full_name,
                    item.department.name if item.department else 'N/A',
                    item.position or 'N/A',
                    int(getattr(item, 'orders_handled', 0) or 0),
                    revenue,
                    float(getattr(item, 'avg_order_value', 0) or 0)
                ])
            # Add total row
            table_data.append(['', '', '', 'TOTAL:', total_revenue, ''])
                
        elif report_type == 'individual_employee':
            employee = report_data.get('employee')
            if employee:
                headers = ['Date', 'Order Number', 'Customer', 'Service Type', 'Amount', 'Status']
                table_data = [headers]
                total_amount = 0
                for item in items:
                    amount = float(item.total_amount or 0)
                    total_amount += amount
                    table_data.append([
                        item.created_at.strftime('%Y-%m-%d'),
                        item.order_number,
                        item.customer.full_name if item.customer else 'N/A',
                        'Service Order',
                        amount,
                        item.status.title()
                    ])
                # Add total row
                table_data.append(['', '', '', 'TOTAL:', total_amount, ''])
            else:
                return []
                
        elif report_type == 'financial_summary':
            headers = ['Date', 'Transaction Type', 'Description', 'Category', 'Amount']
            table_data = [headers]
            total_revenue = 0
            total_expenses = 0
            for item in items:
                amount = float(item.get('amount', 0) or 0)
                if item.get('type') == 'Revenue':
                    total_revenue += amount
                else:
                    total_expenses += abs(amount)
                table_data.append([
                    item.get('date', '').strftime('%Y-%m-%d') if hasattr(item.get('date', ''), 'strftime') else str(item.get('date', '')),
                    item.get('type', 'N/A'),
                    item.get('description', 'N/A'),
                    item.get('category', 'N/A'),
                    amount
                ])
            # Add summary rows
            table_data.append(['', '', '', 'TOTAL REVENUE:', total_revenue])
            table_data.append(['', '', '', 'TOTAL EXPENSES:', total_expenses])
            table_data.append(['', '', '', 'NET PROFIT:', total_revenue - total_expenses])
                
        elif report_type == 'payments':
            headers = ['Date & Time', 'Order Number', 'Customer', 'Payment Method', 'Amount', 'Status']
            table_data = [headers]
            total_amount = 0
            for item in items:
                amount = float(item.amount or 0)
                total_amount += amount
                table_data.append([
                    item.created_at.strftime('%Y-%m-%d %H:%M'),
                    item.service_order.order_number if item.service_order else 'N/A',
                    item.service_order.customer.full_name if item.service_order and item.service_order.customer else 'N/A',
                    item.payment_method.name if item.payment_method else 'Cash',
                    amount,
                    getattr(item, 'status', 'Completed')
                ])
            # Add total row
            table_data.append(['', '', '', 'TOTAL:', total_amount, ''])
                
        elif report_type == 'expenses':
            headers = ['Date', 'Description', 'Category', 'Vendor', 'Amount', 'Reference']
            table_data = [headers]
            total_amount = 0
            for item in items:
                amount = float(item.total_amount or 0)
                total_amount += amount
                table_data.append([
                    item.expense_date.strftime('%Y-%m-%d'),
                    item.description or 'N/A',
                    item.category.name if item.category else 'N/A',
                    item.vendor.name if item.vendor else 'N/A',
                    amount,
                    getattr(item, 'reference_number', 'N/A')
                ])
            # Add total row
            table_data.append(['', '', '', '', 'TOTAL:', total_amount])
            
        elif report_type == 'daily_summary':
            headers = ['Date', 'Orders', 'Revenue', 'Expenses', 'Net Profit', 'Customers']
            table_data = [headers]
            total_revenue = 0
            total_expenses = 0
            total_orders = 0
            total_customers = 0
            for item in items:
                revenue = float(item.get('revenue', 0) or 0)
                expenses = float(item.get('expenses', 0) or 0)
                orders = int(item.get('orders', 0) or 0)
                customers = int(item.get('customers', 0) or 0)
                total_revenue += revenue
                total_expenses += expenses
                total_orders += orders
                total_customers += customers
                table_data.append([
                    item.get('date', '').strftime('%Y-%m-%d') if hasattr(item.get('date', ''), 'strftime') else str(item.get('date', '')),
                    orders,
                    revenue,
                    expenses,
                    revenue - expenses,
                    customers
                ])
            # Add total row
            table_data.append(['TOTAL:', total_orders, total_revenue, total_expenses, total_revenue - total_expenses, total_customers])
            
        elif report_type == 'weekly_summary':
            headers = ['Week Starting', 'Orders', 'Revenue', 'Expenses', 'Net Profit', 'Customers']
            table_data = [headers]
            total_revenue = 0
            total_expenses = 0
            total_orders = 0
            total_customers = 0
            for item in items:
                revenue = float(item.get('revenue', 0) or 0)
                expenses = float(item.get('expenses', 0) or 0)
                orders = int(item.get('orders', 0) or 0)
                customers = int(item.get('customers', 0) or 0)
                total_revenue += revenue
                total_expenses += expenses
                total_orders += orders
                total_customers += customers
                table_data.append([
                    item.get('week_start', '').strftime('%Y-%m-%d') if hasattr(item.get('week_start', ''), 'strftime') else str(item.get('week_start', '')),
                    orders,
                    revenue,
                    expenses,
                    revenue - expenses,
                    customers
                ])
            # Add total row
            table_data.append(['TOTAL:', total_orders, total_revenue, total_expenses, total_revenue - total_expenses, total_customers])
            
        elif report_type == 'monthly_summary':
            headers = ['Month', 'Orders', 'Revenue', 'Expenses', 'Net Profit', 'Customers']
            table_data = [headers]
            total_revenue = 0
            total_expenses = 0
            total_orders = 0
            total_customers = 0
            for item in items:
                revenue = float(item.get('revenue', 0) or 0)
                expenses = float(item.get('expenses', 0) or 0)
                orders = int(item.get('orders', 0) or 0)
                customers = int(item.get('customers', 0) or 0)
                total_revenue += revenue
                total_expenses += expenses
                total_orders += orders
                total_customers += customers
                table_data.append([
                    f"{item.get('year', '')}-{item.get('month', ''):02d}" if item.get('year') and item.get('month') else str(item.get('month', '')),
                    orders,
                    revenue,
                    expenses,
                    revenue - expenses,
                    customers
                ])
            # Add total row
            table_data.append(['TOTAL:', total_orders, total_revenue, total_expenses, total_revenue - total_expenses, total_customers])
            
        elif report_type == 'sales_analysis':
            headers = ['Date', 'Orders', 'Revenue', 'Avg Order Value', 'New Customers', 'Top Service']
            table_data = [headers]
            total_revenue = 0
            total_orders = 0
            total_customers = 0
            for item in items:
                revenue = float(item.get('revenue', 0) or 0)
                orders = int(item.get('orders', 0) or 0)
                customers = int(item.get('new_customers', 0) or 0)
                total_revenue += revenue
                total_orders += orders
                total_customers += customers
                table_data.append([
                    item.get('date', '').strftime('%Y-%m-%d') if hasattr(item.get('date', ''), 'strftime') else str(item.get('date', '')),
                    orders,
                    revenue,
                    float(item.get('avg_order_value', 0) or 0),
                    customers,
                    item.get('top_service', 'N/A')
                ])
            # Add total row
            avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
            table_data.append(['TOTAL:', total_orders, total_revenue, avg_order_value, total_customers, ''])
        
        else:
            # Generic format for other report types
            headers = ['Item', 'Description', 'Value', 'Date']
            table_data = [headers]
            for item in items:
                table_data.append([
                    str(item)[:50],
                    f"{report_type.title()} data",
                    getattr(item, 'amount', getattr(item, 'total_amount', 0)) or 0,
                    getattr(item, 'created_at', timezone.now()).strftime('%Y-%m-%d')
                ])
        
        return table_data
