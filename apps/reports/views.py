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
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics.charts.lineplots import LinePlot
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    import xlsxwriter
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False

# Local imports
from apps.services.models import ServiceOrder, ServiceOrderItem, Service
from apps.employees.models import Employee
from apps.customers.models import Customer
from apps.payments.models import Payment, PaymentMethod
from apps.inventory.models import InventoryItem, StockMovement, InventoryCategory
from apps.expenses.models import Expense, ExpenseCategory, Vendor
from apps.suppliers.models import Supplier, PurchaseOrder
from apps.subscriptions.models import Subscription
from apps.core.decorators import business_required

@method_decorator([login_required, business_required], name='dispatch')
class ReportsView(TemplateView):
    """Enhanced comprehensive reports system covering all business modules"""
    template_name = 'reports/reports.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get tenant information
        tenant = getattr(self.request, 'tenant', None)
        
        # Get request parameters
        report_type = self.request.GET.get('report_type', 'business_overview')
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        employee_id = self.request.GET.get('employee_id')
        service_id = self.request.GET.get('service_id')
        customer_id = self.request.GET.get('customer_id')
        
        # Set default date range if not provided
        if not start_date:
            start_date = (timezone.now() - timedelta(days=30)).date().isoformat()
        if not end_date:
            end_date = timezone.now().date().isoformat()
            
        # Convert dates
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Convert to datetime for filtering (includes full day)
        start_datetime = datetime.combine(start_date_obj, datetime.min.time())
        end_datetime = datetime.combine(end_date_obj, datetime.max.time())
        
        # Generate report data based on type
        report_data = self._generate_report_data(
            report_type, start_datetime, end_datetime,
            employee_id, service_id, customer_id
        )
        
        # Get dropdown data
        employees = Employee.objects.filter(is_active=True)
        services = Service.objects.filter(is_active=True)
        customers = Customer.objects.filter(is_active=True)[:100]  # Limit for performance
        
        # Define available report types
        report_types = [
            ('business_overview', 'Business Overview'),
            ('daily_summary', 'Daily Summary'),
            ('weekly_summary', 'Weekly Summary'),
            ('monthly_summary', 'Monthly Summary'),
            ('financial_summary', 'Financial Summary'),
            ('income_analysis', 'Income Analysis'),
            ('sales_analysis', 'Sales Analysis'),
            ('customer_analytics', 'Customer Analytics'),
            ('employee_performance', 'Employee Performance'),
            ('individual_employee', 'Individual Employee Report'),
            ('inventory_report', 'Inventory Analysis'),
            ('inventory_items_report', 'Inventory Items Report'),
            ('service_list_report', 'Service List Report'),
            ('vehicle_report', 'Vehicle Analysis Report'),
            ('payment_methods_report', 'Payment Methods Report'),
            ('employee_attendance_report', 'Employee Attendance & Productivity'),
            ('expense_analysis', 'Expense Analysis'),
            ('payment_analysis', 'Payment Analysis'),
            ('supplier_report', 'Supplier Performance'),
            ('tax_reconciliation', 'Tax Reconciliation (Kenya)'),
            ('credit_customers', 'Credit Customers'),
            ('service_analysis', 'Service Analysis'),
        ]
        
        context.update({
            'tenant': tenant,
            'report_type': report_type,
            'report_types': report_types,
            'start_date': start_date,
            'end_date': end_date,
            'employee_id': employee_id,
            'service_id': service_id,
            'customer_id': customer_id,
            'report_data': report_data,
            'employees': employees,
            'services': services,
            'customers': customers,
            'pdf_available': PDF_AVAILABLE,
            'excel_available': EXCEL_AVAILABLE,
        })
        
        return context
    
    def _generate_report_data(self, report_type, start_date, end_date, employee_id=None, service_id=None, customer_id=None):
        """Generate comprehensive report data based on type"""
        
        data = {
            'title': '',
            'type': report_type,
            'period': f"{start_date.strftime('%B %d, %Y')} - {end_date.strftime('%B %d, %Y')}",
            'generated_at': timezone.now(),
        }
        
        if report_type == 'business_overview':
            data.update(self._generate_business_overview(start_date, end_date))
        elif report_type in ['daily_summary', 'weekly_summary', 'monthly_summary']:
            period = report_type.replace('_summary', '')
            data.update(self._generate_period_summary(start_date, end_date, period))
        elif report_type == 'income_analysis':
            data.update(self._generate_income_analysis(start_date, end_date))
        elif report_type == 'financial_summary':
            data.update(self._generate_financial_summary(start_date, end_date))
        elif report_type == 'sales_analysis':
            data.update(self._generate_sales_analysis(start_date, end_date))
        elif report_type == 'customer_analytics':
            data.update(self._generate_customer_analytics(start_date, end_date))
        elif report_type == 'employee_performance':
            data.update(self._generate_employee_performance(start_date, end_date, employee_id))
        elif report_type == 'individual_employee':
            data.update(self._generate_individual_employee_report(start_date, end_date, employee_id))
        elif report_type == 'inventory_report':
            data.update(self._generate_inventory_report(start_date, end_date))
        elif report_type == 'expense_analysis':
            data.update(self._generate_expense_analysis(start_date, end_date))
        elif report_type == 'payment_analysis':
            data.update(self._generate_payment_analysis(start_date, end_date))
        elif report_type == 'supplier_report':
            data.update(self._generate_supplier_report(start_date, end_date))
        elif report_type == 'tax_reconciliation':
            data.update(self._generate_tax_reconciliation(start_date, end_date))
        elif report_type == 'credit_customers':
            data.update(self._generate_credit_customers_report(start_date, end_date))
        elif report_type == 'service_analysis':
            data.update(self._generate_service_analysis(start_date, end_date, service_id))
        elif report_type == 'inventory_items_report':
            data.update(self._generate_inventory_items_report(start_date, end_date))
        elif report_type == 'service_list_report':
            data.update(self._generate_service_list_report(start_date, end_date))
        elif report_type == 'vehicle_report':
            data.update(self._generate_vehicle_report(start_date, end_date))
        elif report_type == 'payment_methods_report':
            data.update(self._generate_payment_methods_report(start_date, end_date))
        elif report_type == 'employee_attendance_report':
            data.update(self._generate_employee_attendance_report(start_date, end_date))
        
        return data
    
    def _generate_business_insights(self, report_data):
        """Generate business insights and recommendations based on report data"""
        insights = []
        
        if 'summary' in report_data:
            summary = report_data['summary']
            
            # Revenue insights
            if 'total_revenue' in summary:
                revenue = summary['total_revenue']
                if revenue > 100000:  # KES 100,000
                    insights.append("Strong revenue performance indicates healthy business operations.")
                elif revenue > 50000:  # KES 50,000
                    insights.append("Moderate revenue performance. Consider marketing campaigns to boost sales.")
                else:
                    insights.append("Revenue below optimal levels. Review pricing strategy and service offerings.")
            
            # Order insights
            if 'total_orders' in summary:
                orders = summary['total_orders']
                if orders > 100:
                    insights.append("High order volume demonstrates strong customer demand.")
                elif orders > 50:
                    insights.append("Moderate order volume. Focus on customer retention strategies.")
                else:
                    insights.append("Low order volume. Implement customer acquisition campaigns.")
            
            # Completion rate insights
            if 'completion_rate' in summary:
                completion = summary['completion_rate']
                if completion > 90:
                    insights.append("Excellent service completion rate maintains customer satisfaction.")
                elif completion > 70:
                    insights.append("Good completion rate. Monitor for potential operational improvements.")
                else:
                    insights.append("Low completion rate requires immediate attention to operational processes.")
            
            # Employee performance insights
            if 'avg_rating' in summary:
                rating = summary['avg_rating']
                if rating > 4.0:
                    insights.append("High customer satisfaction ratings reflect quality service delivery.")
                elif rating > 3.0:
                    insights.append("Moderate satisfaction ratings. Consider staff training programs.")
                else:
                    insights.append("Low satisfaction ratings require immediate service quality improvements.")
        
        # Inventory insights
        if 'breakdown' in report_data and 'item_details' in report_data['breakdown']:
            low_stock_count = sum(1 for item in report_data['breakdown']['item_details'] 
                                if item.get('stock_status') == 'Low Stock')
            if low_stock_count > 5:
                insights.append("Multiple items are low on stock. Review inventory management processes.")
        
        # Payment method insights
        if 'breakdown' in report_data and 'payment_method_breakdown' in report_data['breakdown']:
            payment_methods = report_data['breakdown']['payment_method_breakdown']
            if payment_methods:
                top_method = payment_methods[0].get('payment_method', '')
                if 'mpesa' in top_method.lower():
                    insights.append("M-Pesa is the preferred payment method. Ensure system reliability.")
                elif 'cash' in top_method.lower():
                    insights.append("Cash payments dominate. Consider promoting digital payment adoption.")
        
        # Default insights if none generated
        if not insights:
            insights = [
                "Maintain regular monitoring of key performance indicators.",
                "Focus on customer satisfaction to drive repeat business.",
                "Optimize operational efficiency to reduce costs.",
                "Consider seasonal trends when planning business strategies."
            ]
        
        return insights
    
    def _generate_business_overview(self, start_date, end_date):
        """Generate comprehensive business overview"""
        orders = ServiceOrder.objects.filter(
            created_at__range=[start_date, end_date]
        )
        
        total_revenue = orders.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0')
        total_orders = orders.count()
        unique_customers = orders.values('customer').distinct().count()
        
        # Performance metrics
        previous_period_start = start_date - (end_date - start_date)
        previous_orders = ServiceOrder.objects.filter(
            created_at__range=[previous_period_start, start_date]
        )
        previous_revenue = previous_orders.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0')
        
        revenue_growth = ((total_revenue - previous_revenue) / previous_revenue * 100) if previous_revenue > 0 else 0
        
        # Top services
        top_services = (ServiceOrderItem.objects
                       .filter(order__created_at__range=[start_date, end_date])
                       .values('service__name')
                       .annotate(
                           count=Count('id'),
                           revenue=Sum(F('quantity') * F('unit_price'))
                       )
                       .order_by('-revenue')[:5])
        
        # Daily breakdown
        daily_data = (orders
                     .annotate(date=TruncDate('created_at'))
                     .values('date')
                     .annotate(
                         orders=Count('id'),
                         revenue=Sum('total_amount')
                     )
                     .order_by('date'))
        
        return {
            'title': 'Business Overview Report',
            'summary': {
                'total_revenue': total_revenue,
                'total_orders': total_orders,
                'unique_customers': unique_customers,
                'avg_order_value': total_revenue / total_orders if total_orders > 0 else Decimal('0'),
                'revenue_growth': revenue_growth,
            },
            'top_services': list(top_services),
            'daily_breakdown': list(daily_data),
        }
    
    def _generate_sales_analysis(self, start_date, end_date):
        """Generate detailed sales analysis"""
        
        orders = ServiceOrder.objects.filter(created_at__range=[start_date, end_date])
        
        # Sales summary
        total_sales = orders.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0')
        completed_sales = orders.filter(status='completed').aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0')
        pending_sales = orders.filter(status='pending').aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0')
        
        # Sales by status
        status_breakdown = (orders
                          .values('status')
                          .annotate(
                              count=Count('id'),
                              revenue=Sum('total_amount')
                          )
                          .order_by('-revenue'))
        
        # Monthly sales trend - using database-agnostic approach
        try:
            monthly_sales = (orders
                            .annotate(
                                year=Extract('created_at', 'year'),
                                month=Extract('created_at', 'month')
                            )
                            .values('year', 'month')
                            .annotate(
                                revenue=Sum('total_amount'),
                                orders=Count('id')
                            )
                            .order_by('year', 'month'))
        except Exception:
            monthly_sales = []
        
        # Sales by service
        service_sales = (ServiceOrderItem.objects
                        .filter(order__created_at__range=[start_date, end_date])
                        .values('service__name', 'service__category__name')
                        .annotate(
                            quantity=Sum('quantity'),
                            revenue=Sum('unit_price'),  # Simplified aggregation
                            orders=Count('order', distinct=True)
                        )
                        .order_by('-revenue'))
        
        return {
            'title': 'Sales Analysis Report',
            'summary': {
                'total_sales': total_sales,
                'completed_sales': completed_sales,
                'pending_sales': pending_sales,
                'conversion_rate': (completed_sales / total_sales * 100) if total_sales > 0 else 0,
            },
            'status_breakdown': list(status_breakdown),
            'monthly_trend': list(monthly_sales),
            'service_sales': list(service_sales),
        }
    
    def _generate_financial_summary(self, start_date, end_date):
        """Generate financial summary including revenue, expenses, and profit"""
        
        # Revenue analysis
        orders = ServiceOrder.objects.filter(created_at__range=[start_date, end_date])
        total_revenue = orders.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0')
        
        # Payments analysis
        payments = Payment.objects.filter(created_at__range=[start_date, end_date])
        total_payments = payments.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
        outstanding_amount = total_revenue - total_payments
        
        # Expenses analysis
        expenses = Expense.objects.filter(expense_date__range=[start_date.date(), end_date.date()])
        total_expenses = expenses.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
        
        # Expense breakdown by category
        expense_breakdown = (expenses
                           .values('category__name')
                           .annotate(amount=Sum('amount'))
                           .order_by('-amount'))
        
        # Payment method analysis
        payment_methods = (payments
                         .values('payment_method__name')
                         .annotate(
                             amount=Sum('amount'),
                             count=Count('id')
                         )
                         .order_by('-amount'))
        
        # Profit calculation
        gross_profit = total_revenue - total_expenses
        net_profit_margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0
        
        # Cash flow analysis
        cash_flow = self._calculate_cash_flow(start_date, end_date)
        
        return {
            'title': 'Financial Summary Report',
            'summary': {
                'total_revenue': total_revenue,
                'total_payments': total_payments,
                'outstanding_amount': outstanding_amount,
                'total_expenses': total_expenses,
                'gross_profit': gross_profit,
                'net_profit_margin': net_profit_margin,
            },
            'expense_breakdown': list(expense_breakdown),
            'payment_methods': list(payment_methods),
            'cash_flow': cash_flow,
        }
    
    def _generate_customer_analytics(self, start_date, end_date):
        """Generate detailed customer analytics"""
        
        # Customer segments
        customers_data = (Customer.objects
                         .annotate(
                             period_spent=Sum('service_orders__total_amount',
                                           filter=Q(service_orders__created_at__range=[start_date, end_date])),
                             order_count=Count('service_orders',
                                             filter=Q(service_orders__created_at__range=[start_date, end_date])),
                             last_order=Max('service_orders__created_at',
                                          filter=Q(service_orders__created_at__range=[start_date, end_date]))
                         )
                         .exclude(period_spent__isnull=True)
                         .order_by('-period_spent'))
        
        # Customer segmentation
        high_value = customers_data.filter(period_spent__gte=1000).count()
        medium_value = customers_data.filter(period_spent__gte=500, period_spent__lt=1000).count()
        low_value = customers_data.filter(period_spent__lt=500).count()
        
        # New vs returning customers
        new_customers = Customer.objects.filter(created_at__range=[start_date, end_date]).count()
        
        # Customer retention
        previous_period_start = start_date - (end_date - start_date)
        previous_customers = set(
            ServiceOrder.objects
            .filter(created_at__range=[previous_period_start, start_date])
            .values_list('customer_id', flat=True)
        )
        current_customers = set(
            ServiceOrder.objects
            .filter(created_at__range=[start_date, end_date])
            .values_list('customer_id', flat=True)
        )
        
        returning_customers = len(previous_customers.intersection(current_customers))
        retention_rate = (returning_customers / len(previous_customers) * 100) if previous_customers else 0
        
        # Geographic analysis
        customer_locations = (customers_data
                            .exclude(city='')
                            .values('city', 'state')
                            .annotate(count=Count('id'))
                            .order_by('-count'))
        
        return {
            'title': 'Customer Analytics Report',
            'summary': {
                'total_customers': customers_data.count(),
                'new_customers': new_customers,
                'high_value_customers': high_value,
                'medium_value_customers': medium_value,
                'low_value_customers': low_value,
                'retention_rate': retention_rate,
            },
            'top_customers': list(customers_data[:20]),
            'customer_locations': list(customer_locations),
            'customer_behavior': self._analyze_customer_behavior(start_date, end_date),
        }
    
    def _generate_employee_performance(self, start_date, end_date, employee_id=None):
        """Generate employee performance analysis"""
        
        employees_filter = Q(is_active=True)
        if employee_id:
            employees_filter &= Q(id=employee_id)
        
        employees = Employee.objects.filter(employees_filter)
        
        performance_data = []
        for employee in employees:
            # Get orders handled by this employee
            orders = ServiceOrder.objects.filter(
                assigned_attendant=employee,
                created_at__range=[start_date, end_date]
            )
            
            total_orders = orders.count()
            total_revenue = orders.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0')
            avg_order_value = total_revenue / total_orders if total_orders > 0 else Decimal('0')
            
            # Service completion metrics
            completed_orders = orders.filter(status='completed').count()
            completion_rate = (completed_orders / total_orders * 100) if total_orders > 0 else 0
            
            # Commission calculation
            commission_rate = getattr(employee, 'commission_rate', Decimal('0.05'))  # 5% default
            total_commission = total_revenue * commission_rate
            
            performance_data.append({
                'employee': employee,
                'total_orders': total_orders,
                'total_revenue': total_revenue,
                'avg_order_value': avg_order_value,
                'completion_rate': completion_rate,
                'total_commission': total_commission,
            })
        
        # Sort by revenue
        performance_data.sort(key=lambda x: x['total_revenue'], reverse=True)
        
        # Team summary
        team_summary = {
            'total_employees': len(performance_data),
            'total_team_revenue': sum(emp['total_revenue'] for emp in performance_data),
            'total_team_orders': sum(emp['total_orders'] for emp in performance_data),
            'avg_completion_rate': sum(emp['completion_rate'] for emp in performance_data) / len(performance_data) if performance_data else 0,
        }
        
        return {
            'title': 'Employee Performance Report',
            'summary': team_summary,
            'employee_performance': performance_data,
            'top_performers': performance_data[:5],
        }
    
    def _generate_inventory_report(self, start_date, end_date):
        """Generate comprehensive inventory analysis"""
        
        # Current stock status
        inventory_items = InventoryItem.objects.filter(is_active=True)
        
        stock_summary = {
            'total_items': inventory_items.count(),
            'low_stock_items': inventory_items.filter(current_stock__lte=F('minimum_stock_level')).count(),
            'out_of_stock': inventory_items.filter(current_stock=0).count(),
            'total_value': inventory_items.aggregate(
                value=Sum(F('current_stock') * F('unit_cost'))
            )['value'] or Decimal('0'),
        }
        
        # Stock movements in period
        movements = StockMovement.objects.filter(
            created_at__range=[start_date, end_date]
        )
        
        movement_summary = movements.aggregate(
            total_in=Sum('quantity', filter=Q(movement_type='in')),
            total_out=Sum('quantity', filter=Q(movement_type='out')),
            total_adjustments=Sum('quantity', filter=Q(movement_type='adjustment'))
        )
        
        # Top moving items
        top_moving = (movements
                     .values('item__name', 'item__sku')
                     .annotate(
                         total_movement=Sum('quantity'),
                         movement_count=Count('id')
                     )
                     .order_by('-total_movement')[:10])
        
        # Category analysis
        category_analysis = (InventoryCategory.objects
                           .annotate(
                               active_item_count=Count('items', filter=Q(items__is_active=True)),
                               total_stock_value=Sum(F('items__current_stock') * F('items__unit_cost'),
                                             filter=Q(items__is_active=True))
                           )
                           .order_by('-total_stock_value'))
        
        # Items needing attention
        low_stock = inventory_items.filter(current_stock__lte=F('minimum_stock_level'))[:20]
        high_value = inventory_items.annotate(
            stock_value=F('current_stock') * F('unit_cost')
        ).order_by('-stock_value')[:20]
        
        return {
            'title': 'Inventory Analysis Report',
            'summary': stock_summary,
            'movement_summary': movement_summary,
            'top_moving_items': list(top_moving),
            'category_analysis': list(category_analysis),
            'low_stock_items': low_stock,
            'high_value_items': high_value,
        }
    
    def _generate_inventory_items_report(self, start_date, end_date):
        """Generate detailed inventory items breakdown"""
        
        # Get all active inventory items with stock details
        inventory_items = InventoryItem.objects.filter(is_active=True).select_related('category')
        
        items_data = []
        for item in inventory_items:
            stock_value = item.current_stock * item.unit_cost
            stock_status = 'Out of Stock' if item.current_stock == 0 else (
                'Low Stock' if item.current_stock <= item.minimum_stock_level else 'In Stock'
            )
            
            items_data.append({
                'name': item.name,
                'category': item.category.name if item.category else 'Uncategorized',
                'current_stock': item.current_stock,
                'minimum_level': item.minimum_stock_level,
                'unit_cost': item.unit_cost,
                'stock_value': stock_value,
                'stock_status': stock_status,
                'supplier': item.primary_supplier.name if item.primary_supplier else 'N/A',
            })
        
        # Summary statistics
        summary = {
            'total_items': len(items_data),
            'total_value': sum(item['stock_value'] for item in items_data),
            'low_stock_count': sum(1 for item in items_data if item['stock_status'] == 'Low Stock'),
            'out_of_stock_count': sum(1 for item in items_data if item['stock_status'] == 'Out of Stock'),
        }
        
        return {
            'title': 'Inventory Items Report',
            'summary': summary,
            'item_details': items_data,
            'breakdown': {
                'item_details': items_data
            }
        }
    
    def _generate_service_list_report(self, start_date, end_date):
        """Generate service list with performance metrics"""
        
        # Get all active services
        services = Service.objects.filter(is_active=True)
        
        # Calculate service performance within date range
        service_data = []
        for service in services:
            orders_count = ServiceOrder.objects.filter(
                services=service,
                created_at__range=[start_date, end_date]
            ).count()
            
            total_revenue = ServiceOrder.objects.filter(
                services=service,
                created_at__range=[start_date, end_date]
            ).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0')
            
            service_data.append({
                'name': service.name,
                'category': service.category.name if service.category else 'Uncategorized',
                'price': service.base_price,
                'duration': service.estimated_duration,
                'orders_count': orders_count,
                'total_revenue': total_revenue,
                'popularity_rank': 0,  # Will be set after sorting
            })
        
        # Sort by orders count and assign popularity ranks
        service_data.sort(key=lambda x: x['orders_count'], reverse=True)
        for i, service in enumerate(service_data):
            service['popularity_rank'] = i + 1
        
        summary = {
            'total_services': len(service_data),
            'total_orders': sum(s['orders_count'] for s in service_data),
            'total_revenue': sum(s['total_revenue'] for s in service_data),
            'most_popular': service_data[0]['name'] if service_data else 'N/A',
        }
        
        return {
            'title': 'Service List Report',
            'summary': summary,
            'service_details': service_data,
            'breakdown': {
                'service_performance': service_data
            }
        }
    
    def _generate_vehicle_report(self, start_date, end_date):
        """Generate vehicle analysis report"""
        
        # Get service orders within date range
        orders = ServiceOrder.objects.filter(
            created_at__range=[start_date, end_date]
        ).select_related('customer', 'vehicle')
        
        # Vehicle type analysis
        vehicle_data = {}
        for order in orders:
            vehicle_type = order.vehicle.vehicle_type if order.vehicle else 'Unknown'
            if vehicle_type not in vehicle_data:
                vehicle_data[vehicle_type] = {
                    'count': 0,
                    'total_revenue': Decimal('0'),
                    'avg_service_value': Decimal('0'),
                }
            
            vehicle_data[vehicle_type]['count'] += 1
            vehicle_data[vehicle_type]['total_revenue'] += order.total_amount
        
        # Calculate averages
        for vehicle_type, data in vehicle_data.items():
            if data['count'] > 0:
                data['avg_service_value'] = data['total_revenue'] / data['count']
        
        # Convert to list for template
        vehicle_list = [
            {
                'type': vtype,
                'count': data['count'],
                'total_revenue': data['total_revenue'],
                'avg_service_value': data['avg_service_value'],
                'percentage': (data['count'] / len(orders) * 100) if orders else 0,
            }
            for vtype, data in vehicle_data.items()
        ]
        
        vehicle_list.sort(key=lambda x: x['count'], reverse=True)
        
        summary = {
            'total_vehicles_serviced': len(orders),
            'vehicle_types_count': len(vehicle_data),
            'most_common_type': vehicle_list[0]['type'] if vehicle_list else 'N/A',
            'highest_revenue_type': max(vehicle_list, key=lambda x: x['total_revenue'])['type'] if vehicle_list else 'N/A',
        }
        
        return {
            'title': 'Vehicle Analysis Report',
            'summary': summary,
            'vehicle_analysis': vehicle_list,
            'breakdown': {
                'vehicle_analysis': vehicle_list
            }
        }
    
    def _generate_payment_methods_report(self, start_date, end_date):
        """Generate payment methods analysis"""
        
        # Get all payments within date range
        payments = Payment.objects.filter(
            created_at__range=[start_date, end_date]
        )
        
        # Payment method breakdown
        payment_breakdown = (payments
                           .values('payment_method')
                           .annotate(
                               count=Count('id'),
                               total_amount=Sum('amount')
                           )
                           .order_by('-total_amount'))
        
        payment_list = []
        total_payments = payments.count()
        total_amount = payments.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
        
        for payment in payment_breakdown:
            payment_list.append({
                'payment_method': payment['payment_method'],
                'count': payment['count'],
                'total_amount': payment['total_amount'],
                'percentage': (payment['count'] / total_payments * 100) if total_payments else 0,
                'amount_percentage': (payment['total_amount'] / total_amount * 100) if total_amount else 0,
            })
        
        summary = {
            'total_transactions': total_payments,
            'total_amount': total_amount,
            'payment_methods_count': len(payment_list),
            'most_used_method': payment_list[0]['payment_method'] if payment_list else 'N/A',
        }
        
        return {
            'title': 'Payment Methods Report',
            'summary': summary,
            'payment_methods': payment_list,
            'breakdown': {
                'payment_method_breakdown': payment_list
            }
        }
    
    def _generate_employee_attendance_report(self, start_date, end_date):
        """Generate employee attendance analysis"""
        
        # Get all active employees
        employees = Employee.objects.filter(is_active=True)
        
        # Calculate attendance metrics for each employee
        attendance_data = []
        for employee in employees:
            # Count service orders assigned to this employee
            orders_handled = ServiceOrder.objects.filter(
                assigned_attendant=employee,
                created_at__range=[start_date, end_date]
            ).count()
            
            # Calculate total earnings (if commission-based)
            total_earnings = ServiceOrder.objects.filter(
                assigned_attendant=employee,
                created_at__range=[start_date, end_date]
            ).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0')
            
            # Calculate average rating
            avg_rating = ServiceOrder.objects.filter(
                assigned_attendant=employee,
                created_at__range=[start_date, end_date],
                customer_rating__isnull=False
            ).aggregate(Avg('customer_rating'))['customer_rating__avg'] or 0
            
            attendance_data.append({
                'name': f"{employee.first_name} {employee.last_name}",
                'employee_id': employee.employee_id,
                'position': employee.position,
                'orders_handled': orders_handled,
                'total_earnings': total_earnings,
                'avg_rating': round(avg_rating, 2) if avg_rating else 0,
                'performance_score': min(100, (orders_handled * 10) + (avg_rating * 15)),
            })
        
        # Sort by performance
        attendance_data.sort(key=lambda x: x['performance_score'], reverse=True)
        
        summary = {
            'total_employees': len(attendance_data),
            'total_orders_handled': sum(emp['orders_handled'] for emp in attendance_data),
            'avg_performance_score': sum(emp['performance_score'] for emp in attendance_data) / len(attendance_data) if attendance_data else 0,
            'top_performer': attendance_data[0]['name'] if attendance_data else 'N/A',
        }
        
        return {
            'title': 'Employee Attendance Report',
            'summary': summary,
            'employee_attendance': attendance_data,
            'breakdown': {
                'employee_performance': attendance_data
            }
        }
    
    def _generate_expense_analysis(self, start_date, end_date):
        """Generate detailed expense analysis"""
        
        expenses = Expense.objects.filter(
            expense_date__range=[start_date.date(), end_date.date()]
        )
        
        total_expenses = expenses.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
        
        # Category breakdown
        category_breakdown = (expenses
                            .values('category__name', 'category__parent__name')
                            .annotate(
                                total_amount=Sum('amount'),
                                count=Count('id')
                            )
                            .order_by('-total_amount'))
        
        # Vendor analysis
        vendor_analysis = (expenses
                         .exclude(vendor__isnull=True)
                         .values('vendor__name')
                         .annotate(
                             total_amount=Sum('amount'),
                             count=Count('id')
                         )
                         .order_by('-total_amount'))
        
        # Calculate average expense
        average_expense = total_expenses / expenses.count() if expenses.count() > 0 else Decimal('0')
        
        # Monthly trend - Fixed to use database-agnostic approach
        try:
            monthly_trend = (expenses
                           .annotate(
                               year=Extract('expense_date', 'year'),
                               month=Extract('expense_date', 'month')
                           )
                           .values('year', 'month')
                           .annotate(amount=Sum('amount'))
                           .order_by('year', 'month'))
        except Exception:
            monthly_trend = []
        
        # Payment method analysis
        payment_methods = (expenses
                         .values('payment_method')
                         .annotate(
                             amount=Sum('amount'),
                             count=Count('id')
                         )
                         .order_by('-amount'))
        
        # Expense types analysis
        expense_types = (expenses
                       .values('expense_type')
                       .annotate(
                           amount=Sum('amount'),
                           count=Count('id')
                       )
                       .order_by('-amount'))
        
        return {
            'title': 'Expense Analysis Report',
            'summary': {
                'total_expenses': total_expenses,
                'expense_count': expenses.count(),
                'avg_expense': total_expenses / expenses.count() if expenses.count() > 0 else Decimal('0'),
            },
            'category_breakdown': list(category_breakdown),
            'vendor_analysis': list(vendor_analysis),
            'monthly_trend': list(monthly_trend),
            'payment_methods': list(payment_methods),
            'expense_types': list(expense_types),
        }
    
    def _generate_payment_analysis(self, start_date, end_date):
        """Generate payment analysis report"""
        
        payments = Payment.objects.filter(
            created_at__range=[start_date, end_date]
        )
        
        total_payments = payments.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
        
        # Payment status analysis
        status_breakdown = (payments
                          .values('status')
                          .annotate(
                              amount=Sum('amount'),
                              count=Count('id')
                          )
                          .order_by('-amount'))
        
        # Payment method analysis
        method_breakdown = (payments
                          .values('payment_method__name', 'payment_method__method_type')
                          .annotate(
                              amount=Sum('amount'),
                              count=Count('id')
                          )
                          .order_by('-amount'))
        
        # Daily payment trends
        daily_payments = (payments
                        .annotate(date=TruncDate('created_at'))
                        .values('date')
                        .annotate(
                            amount=Sum('amount'),
                            count=Count('id')
                        )
                        .order_by('date'))
        
        # Outstanding payments
        outstanding_orders = ServiceOrder.objects.filter(
            created_at__range=[start_date, end_date],
            payment_status__in=['pending', 'partial']
        )
        
        outstanding_amount = (outstanding_orders
                            .aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0'))
        
        return {
            'title': 'Payment Analysis Report',
            'summary': {
                'total_payments': total_payments,
                'payment_count': payments.count(),
                'outstanding_amount': outstanding_amount,
                'collection_rate': (total_payments / (total_payments + outstanding_amount) * 100) 
                                  if (total_payments + outstanding_amount) > 0 else 0,
            },
            'status_breakdown': list(status_breakdown),
            'method_breakdown': list(method_breakdown),
            'daily_payments': list(daily_payments),
            'outstanding_orders': outstanding_orders[:20],
        }
    
    def _generate_supplier_report(self, start_date, end_date):
        """Generate supplier performance report"""
        
        suppliers = Supplier.objects.filter(is_deleted=False)
        
        # Purchase orders in period
        purchase_orders = PurchaseOrder.objects.filter(
            created_at__range=[start_date, end_date]
        )
        
        supplier_performance = []
        for supplier in suppliers:
            supplier_pos = purchase_orders.filter(supplier=supplier)
            
            total_orders = supplier_pos.count()
            total_amount = supplier_pos.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0')
            
            # Delivery performance
            delivered_on_time = supplier_pos.filter(
                status='delivered',
                delivered_date__lte=F('expected_delivery_date')
            ).count()
            
            delivery_rate = (delivered_on_time / total_orders * 100) if total_orders > 0 else 0
            
            supplier_performance.append({
                'supplier': supplier,
                'total_orders': total_orders,
                'total_amount': total_amount,
                'delivery_rate': delivery_rate,
            })
        
        supplier_performance.sort(key=lambda x: x['total_amount'], reverse=True)
        
        return {
            'title': 'Supplier Performance Report',
            'supplier_performance': supplier_performance,
            'summary': {
                'total_suppliers': len(supplier_performance),
                'total_po_amount': sum(sp['total_amount'] for sp in supplier_performance),
                'avg_delivery_rate': sum(sp['delivery_rate'] for sp in supplier_performance) / len(supplier_performance) if supplier_performance else 0,
            }
        }
    
    def _generate_tax_reconciliation(self, start_date, end_date):
        """Generate tax reconciliation report for Kenya"""
        
        # Sales tax (VAT) - 16% in Kenya
        orders = ServiceOrder.objects.filter(
            created_at__range=[start_date, end_date]
        )
        
        # Assume all orders are taxable unless specified otherwise
        taxable_sales = orders
        tax_exempt_sales = orders.filter(is_taxable=False) if hasattr(ServiceOrder, 'is_taxable') else orders.none()
        
        taxable_amount = taxable_sales.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0')
        tax_exempt_amount = tax_exempt_sales.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0')
        
        # Calculate VAT (16%)
        vat_rate = Decimal('0.16')
        gross_amount = taxable_amount / (1 + vat_rate)  # Remove VAT to get gross
        vat_amount = taxable_amount - gross_amount
        
        # Input VAT from expenses
        taxable_expenses = Expense.objects.filter(
            expense_date__range=[start_date.date(), end_date.date()]
        )
        
        if hasattr(Expense, 'is_taxable'):
            taxable_expenses = taxable_expenses.filter(is_taxable=True)
        
        input_vat = sum(
            (expense.amount * vat_rate / (1 + vat_rate))
            for expense in taxable_expenses
        )
        
        net_vat_payable = vat_amount - input_vat
        
        return {
            'title': 'Tax Reconciliation Report (Kenya)',
            'summary': {
                'taxable_sales': taxable_amount,
                'tax_exempt_sales': tax_exempt_amount,
                'gross_amount': gross_amount,
                'output_vat': vat_amount,
                'input_vat': input_vat,
                'net_vat_payable': net_vat_payable,
                'vat_rate': vat_rate * 100,
            },
            'taxable_transactions': taxable_sales[:50],
            'tax_exempt_transactions': tax_exempt_sales[:50],
        }
    
    def _generate_credit_customers_report(self, start_date, end_date):
        """Generate credit customers analysis"""
        
        # Customers with outstanding balances
        customers_with_credit = Customer.objects.annotate(
            total_orders=Sum('service_orders__total_amount',
                           filter=Q(service_orders__created_at__range=[start_date, end_date])),
            total_payments=Sum('service_orders__payments__amount',
                             filter=Q(service_orders__payments__created_at__range=[start_date, end_date])),
            outstanding_balance=F('total_orders') - F('total_payments')
        ).filter(outstanding_balance__gt=0)
        
        # Aging analysis
        aging_30 = customers_with_credit.filter(
            service_orders__created_at__gte=timezone.now() - timedelta(days=30)
        ).distinct().count()
        
        aging_60 = customers_with_credit.filter(
            service_orders__created_at__gte=timezone.now() - timedelta(days=60),
            service_orders__created_at__lt=timezone.now() - timedelta(days=30)
        ).distinct().count()
        
        aging_90 = customers_with_credit.filter(
            service_orders__created_at__lt=timezone.now() - timedelta(days=60)
        ).distinct().count()
        
        total_outstanding = customers_with_credit.aggregate(
            total=Sum('outstanding_balance')
        )['total'] or Decimal('0')
        
        return {
            'title': 'Credit Customers Report',
            'summary': {
                'total_credit_customers': customers_with_credit.count(),
                'total_outstanding': total_outstanding,
                'aging_0_30': aging_30,
                'aging_31_60': aging_60,
                'aging_60_plus': aging_90,
            },
            'credit_customers': customers_with_credit[:50],
        }
    
    def _generate_service_analysis(self, start_date, end_date, service_id=None):
        """Generate service performance analysis"""
        
        services_filter = Q()
        if service_id:
            services_filter = Q(id=service_id)
        
        services = Service.objects.filter(services_filter, is_active=True)
        
        service_performance = []
        for service in services:
            service_items = ServiceOrderItem.objects.filter(
                service=service,
                order__created_at__range=[start_date, end_date]
            )
            
            total_quantity = service_items.aggregate(Sum('quantity'))['quantity__sum'] or 0
            total_revenue = service_items.aggregate(
                revenue=Sum(F('quantity') * F('unit_price'))
            )['revenue'] or Decimal('0')
            
            avg_price = service_items.aggregate(Avg('unit_price'))['unit_price__avg'] or Decimal('0')
            
            service_performance.append({
                'service': service,
                'total_quantity': total_quantity,
                'total_revenue': total_revenue,
                'avg_price': avg_price,
                'orders_count': service_items.values('order').distinct().count(),
            })
        
        service_performance.sort(key=lambda x: x['total_revenue'], reverse=True)
        
        return {
            'title': 'Service Analysis Report',
            'service_performance': service_performance,
            'summary': {
                'total_services': len(service_performance),
                'total_service_revenue': sum(sp['total_revenue'] for sp in service_performance),
                'avg_service_price': sum(sp['avg_price'] for sp in service_performance) / len(service_performance) if service_performance else Decimal('0'),
            }
        }
    
    def _calculate_business_kpis(self, start_date, end_date):
        """Calculate key business performance indicators"""
        
        orders = ServiceOrder.objects.filter(created_at__range=[start_date, end_date])
        
        # Revenue KPIs
        total_revenue = orders.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0')
        order_count = orders.count()
        
        # Customer KPIs
        unique_customers = orders.values('customer').distinct().count()
        repeat_customers = orders.values('customer').annotate(
            order_count=Count('id')
        ).filter(order_count__gt=1).count()
        
        repeat_rate = (repeat_customers / unique_customers * 100) if unique_customers > 0 else 0
        
        # Operational KPIs
        completed_orders = orders.exclude(actual_end_time__isnull=True)
        if completed_orders.exists():
            avg_service_time = completed_orders.aggregate(
                avg_time=Avg(F('actual_end_time') - F('actual_start_time'))
            )['avg_time']
            avg_service_hours = avg_service_time.total_seconds() / 3600 if avg_service_time else 0
        else:
            avg_service_hours = 0
        
        return {
            'revenue_per_day': total_revenue / ((end_date - start_date).days + 1),
            'revenue_per_order': total_revenue / order_count if order_count > 0 else Decimal('0'),
            'orders_per_day': order_count / ((end_date - start_date).days + 1),
            'customer_repeat_rate': repeat_rate,
            'avg_service_time_hours': avg_service_hours,
        }
    
    def _calculate_cash_flow(self, start_date, end_date):
        """Calculate cash flow analysis"""
        
        # Cash inflows
        payments = Payment.objects.filter(
            created_at__range=[start_date, end_date],
            status='completed'
        )
        total_inflows = payments.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
        
        # Cash outflows
        expenses = Expense.objects.filter(
            expense_date__range=[start_date.date(), end_date.date()]
        )
        total_outflows = expenses.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
        
        net_cash_flow = total_inflows - total_outflows
        
        # Daily cash flow
        daily_inflows = (payments
                        .annotate(date=TruncDate('created_at'))
                        .values('date')
                        .annotate(amount=Sum('amount'))
                        .order_by('date'))
        
        daily_outflows = (expenses
                         .annotate(date=TruncDate('expense_date'))
                         .values('date')
                         .annotate(amount=Sum('amount'))
                         .order_by('date'))
        
        return {
            'total_inflows': total_inflows,
            'total_outflows': total_outflows,
            'net_cash_flow': net_cash_flow,
            'daily_inflows': list(daily_inflows),
            'daily_outflows': list(daily_outflows),
        }
    
    def _analyze_customer_behavior(self, start_date, end_date):
        """Analyze customer behavior patterns"""
        
        orders = ServiceOrder.objects.filter(created_at__range=[start_date, end_date])
        
        # Order timing analysis
        hourly_distribution = orders.annotate(
            hour=Extract('created_at', 'hour')
        ).values('hour').annotate(count=Count('id')).order_by('hour')
        
        # Day of week analysis
        daily_distribution = orders.annotate(
            weekday=Extract('created_at', 'week_day')
        ).values('weekday').annotate(count=Count('id')).order_by('weekday')
        
        # Service preferences
        service_preferences = (ServiceOrderItem.objects
                             .filter(order__created_at__range=[start_date, end_date])
                             .values('service__name')
                             .annotate(count=Count('id'))
                             .order_by('-count')[:10])
        
        return {
            'hourly_distribution': list(hourly_distribution),
            'daily_distribution': list(daily_distribution),
            'service_preferences': list(service_preferences),
        }

    def _generate_period_summary(self, start_date, end_date, period):
        """Generate period-based summary (daily/weekly/monthly)"""
        
        # Base period calculations
        orders = ServiceOrder.objects.filter(
            created_at__range=[start_date, end_date]
        )
        
        payments = Payment.objects.filter(
            created_at__range=[start_date, end_date]
        )
        
        expenses = Expense.objects.filter(
            expense_date__range=[start_date.date(), end_date.date()]
        )
        
        # Period grouping - using database-agnostic approach
        try:
            if period == 'daily':
                date_trunc = TruncDate('created_at')
                expense_date_trunc = TruncDate('expense_date')
            elif period == 'weekly':
                # For weekly, use year and week number
                date_trunc = TruncWeek('created_at')
                expense_date_trunc = TruncWeek('expense_date')
            else:  # monthly
                # For monthly, use Extract to avoid timezone issues
                date_trunc = None
                expense_date_trunc = None
        except Exception:
            date_trunc = TruncDate('created_at')
            expense_date_trunc = TruncDate('expense_date')
        
        # Revenue trend
        if period == 'monthly':
            try:
                revenue_trend = payments.annotate(
                    year=Extract('created_at', 'year'),
                    month=Extract('created_at', 'month')
                ).values('year', 'month').annotate(
                    revenue=Sum('amount')
                ).order_by('year', 'month')
            except Exception:
                revenue_trend = []
        else:
            revenue_trend = payments.annotate(
                period=date_trunc
            ).values('period').annotate(
                revenue=Sum('amount')
            ).order_by('period')
        
        # Order trend
        if period == 'monthly':
            try:
                order_trend = orders.annotate(
                    year=Extract('created_at', 'year'),
                    month=Extract('created_at', 'month')
                ).values('year', 'month').annotate(
                    order_count=Count('id'),
                    total_amount=Sum('total_amount')
                ).order_by('year', 'month')
            except Exception:
                order_trend = []
        else:
            order_trend = orders.annotate(
                period=date_trunc
            ).values('period').annotate(
                order_count=Count('id'),
                total_amount=Sum('total_amount')
            ).order_by('period')
        
        # Expense trend
        if period == 'monthly':
            try:
                expense_trend = expenses.annotate(
                    year=Extract('expense_date', 'year'),
                    month=Extract('expense_date', 'month')
                ).values('year', 'month').annotate(
                    expense_amount=Sum('amount')
                ).order_by('year', 'month')
            except Exception:
                expense_trend = []
        else:
            expense_trend = expenses.annotate(
                period=expense_date_trunc
            ).values('period').annotate(
                expense_amount=Sum('amount')
            ).order_by('period')
        
        return {
            'title': f'{period.title()} Summary Report',
            'period': period,
            'summary': {
                'total_revenue': payments.aggregate(Sum('amount'))['amount__sum'] or Decimal('0'),
                'total_orders': orders.count(),
                'total_expenses': expenses.aggregate(Sum('amount'))['amount__sum'] or Decimal('0'),
                'net_profit': (payments.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')) - 
                             (expenses.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')),
            },
            'trends': {
                'revenue_trend': list(revenue_trend),
                'order_trend': list(order_trend),
                'expense_trend': list(expense_trend),
            },
            'detailed_breakdown': True,
        }

    def _generate_income_analysis(self, start_date, end_date):
        """Generate comprehensive income analysis"""
        
        # Revenue streams
        service_revenue = Payment.objects.filter(
            created_at__range=[start_date, end_date],
            service_order__isnull=False
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
        
        # Revenue by service type
        revenue_by_service = Payment.objects.filter(
            created_at__range=[start_date, end_date],
            service_order__isnull=False
        ).values(
            'service_order__order_items__service__name'
        ).annotate(
            revenue=Sum('amount'),
            order_count=Count('service_order', distinct=True)
        ).order_by('-revenue')
        
        # Revenue by payment method
        revenue_by_method = Payment.objects.filter(
            created_at__range=[start_date, end_date]
        ).values('payment_method').annotate(
            revenue=Sum('amount'),
            transaction_count=Count('id')
        ).order_by('-revenue')
        
        # Monthly income trend - using database-agnostic approach with Extract
        try:
            monthly_income = Payment.objects.filter(
                created_at__range=[start_date, end_date]
            ).annotate(
                year=Extract('created_at', 'year'),
                month=Extract('created_at', 'month')
            ).values('year', 'month').annotate(
                income=Sum('amount'),
                transaction_count=Count('id')
            ).order_by('year', 'month')
        except Exception:
            # Fallback to simple grouping without month truncation
            monthly_income = []
        
        # Average transaction values
        avg_transaction = Payment.objects.filter(
            created_at__range=[start_date, end_date]
        ).aggregate(Avg('amount'))['amount__avg'] or Decimal('0')
        
        return {
            'title': 'Income Analysis Report',
            'summary': {
                'total_income': service_revenue,
                'avg_transaction': avg_transaction,
                'total_transactions': Payment.objects.filter(
                    created_at__range=[start_date, end_date]
                ).count(),
            },
            'breakdown': {
                'revenue_by_service': list(revenue_by_service),
                'revenue_by_method': list(revenue_by_method),
                'monthly_trend': list(monthly_income),
            },
            'detailed_breakdown': True,
        }

    def _generate_individual_employee_report(self, start_date, end_date, employee_id):
        """Generate detailed individual employee performance report"""
        
        if not employee_id:
            return {'title': 'Individual Employee Report', 'error': 'No employee selected'}
        
        try:
            employee = Employee.objects.get(id=employee_id)
        except Employee.DoesNotExist:
            return {'title': 'Individual Employee Report', 'error': 'Employee not found'}
        
        # Employee's service orders
        employee_orders = ServiceOrder.objects.filter(
            assigned_attendant=employee,
            created_at__range=[start_date, end_date]
        )
        
        # Performance metrics
        total_orders = employee_orders.count()
        completed_orders = employee_orders.filter(status='completed').count()
        total_revenue = employee_orders.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0')
        
        # Service breakdown - get services through order items
        service_breakdown = []
        if total_orders > 0:
            # Get services from order items
            order_items = ServiceOrderItem.objects.filter(
                order__in=employee_orders
            ).values(
                'service__name', 'service__category__name'
            ).annotate(
                service_count=Count('id'),
                total_quantity=Sum('quantity'),
                total_price=Sum('total_price')
            ).order_by('-service_count')
            
            service_breakdown = list(order_items)
        
        # Daily performance
        daily_performance = employee_orders.annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            daily_orders=Count('id'),
            daily_revenue=Sum('total_amount')
        ).order_by('date')
        
        # Customer satisfaction (using customer_rating field)
        avg_rating = employee_orders.exclude(
            customer_rating__isnull=True
        ).aggregate(Avg('customer_rating'))['customer_rating__avg']
        
        # Additional performance metrics
        avg_completion_time = None
        if completed_orders > 0:
            # Calculate average time between start and end
            completion_times = employee_orders.filter(
                status='completed',
                actual_start_time__isnull=False,
                actual_end_time__isnull=False
            ).annotate(
                duration=F('actual_end_time') - F('actual_start_time')
            ).aggregate(Avg('duration'))
            
            if completion_times['duration__avg']:
                avg_completion_time = completion_times['duration__avg'].total_seconds() / 60  # in minutes
        
        # Monthly performance trend - using database-agnostic approach
        try:
            monthly_performance = employee_orders.annotate(
                year=Extract('created_at', 'year'),
                month=Extract('created_at', 'month')
            ).values('year', 'month').annotate(
                monthly_orders=Count('id'),
                monthly_revenue=Sum('total_amount')
            ).order_by('year', 'month')
        except Exception:
            monthly_performance = []
        
        return {
            'title': f'Individual Employee Report - {employee.first_name} {employee.last_name}',
            'employee': {
                'id': str(employee.id),
                'first_name': employee.first_name,
                'last_name': employee.last_name,
                'full_name': f"{employee.first_name} {employee.last_name}",
                'employee_id': getattr(employee, 'employee_id', ''),
                'position': getattr(employee, 'position', 'Employee'),
                'department': getattr(employee, 'department', ''),
            },
            'summary': {
                'total_orders': total_orders,
                'completed_orders': completed_orders,
                'pending_orders': employee_orders.filter(status='pending').count(),
                'in_progress_orders': employee_orders.filter(status='in_progress').count(),
                'completion_rate': round((completed_orders / total_orders * 100), 2) if total_orders > 0 else 0,
                'total_revenue': total_revenue,
                'avg_order_value': round(total_revenue / total_orders, 2) if total_orders > 0 else Decimal('0'),
                'avg_rating': round(avg_rating, 2) if avg_rating else 0,
                'avg_completion_time_minutes': round(avg_completion_time, 1) if avg_completion_time else None,
            },
            'breakdown': {
                'service_breakdown': service_breakdown,
                'daily_performance': list(daily_performance),
                'monthly_performance': list(monthly_performance),
            },
            'period_info': {
                'start_date': start_date.date(),
                'end_date': end_date.date(),
                'total_days': (end_date.date() - start_date.date()).days + 1,
            },
            'detailed_breakdown': True,
        }


@method_decorator([login_required, business_required], name='dispatch')
class ReportDownloadView(View):
    """Enhanced report download with comprehensive business data"""
    
    def get(self, request, report_type):
        format_type = request.GET.get('format', 'pdf')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        employee_id = request.GET.get('employee_id')
        
        # Generate report data
        reports_view = ReportsView()
        reports_view.request = request
        
        if not start_date:
            start_date = (timezone.now() - timedelta(days=30)).date().isoformat()
        if not end_date:
            end_date = timezone.now().date().isoformat()
            
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        start_datetime = datetime.combine(start_date_obj, datetime.min.time())
        end_datetime = datetime.combine(end_date_obj, datetime.max.time())
        
        report_data = reports_view._generate_report_data(
            report_type, start_datetime, end_datetime,
            employee_id=employee_id
        )
        
        if format_type == 'pdf':
            return self._generate_pdf(report_data, request.tenant)
        elif format_type == 'excel':
            return self._generate_excel(report_data, request.tenant)
        else:
            return JsonResponse({'error': 'Invalid format'}, status=400)
    
    def _generate_pdf(self, report_data, tenant):
        """Generate enhanced PDF report"""
        if not PDF_AVAILABLE:
            return JsonResponse({'error': 'PDF generation not available'}, status=500)
        
        # Get report type early in the function
        report_type = report_data.get('type', '').lower()
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.4*inch, bottomMargin=0.4*inch)  # Reduced margins
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=18,  # Reduced from 20
            spaceAfter=0.15*inch,  # Reduced from 0.3*inch
            textColor=colors.HexColor('#1f2937'),
            alignment=TA_CENTER
        )
        
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Normal'],
            fontSize=11,  # Reduced from 12
            textColor=colors.HexColor('#6b7280'),
            alignment=TA_CENTER,
            spaceAfter=0.1*inch  # Reduced from 0.2*inch
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=13,  # Reduced from 14
            textColor=colors.HexColor('#1f2937'),
            spaceBefore=0.15*inch,  # Reduced from 0.2*inch
            spaceAfter=0.08*inch   # Reduced from 0.1*inch
        )
        
        story = []
        
        # Compact header with business info
        story.append(Paragraph(f"{tenant.name}", title_style))
        story.append(Paragraph(f"{report_data['title']}", subtitle_style))
        story.append(Paragraph(f"Period: {report_data['period']} | Generated: {timezone.now().strftime('%b %d, %Y at %I:%M %p')}", subtitle_style))
        story.append(Spacer(1, 0.1*inch))  # Reduced from 0.2*inch
        
        # Compact Business Information
        business_info = [
            ['Business:', tenant.name, 'Contact:', str(getattr(tenant, 'phone', 'N/A')) if getattr(tenant, 'phone', None) else 'N/A'],
            ['Type:', getattr(tenant, 'business_type', 'Car Wash').title(), 'Email:', getattr(tenant, 'email', 'N/A')],
            ['Address:', getattr(tenant, 'address', 'N/A'), 'Currency:', 'Kenyan Shilling (KES)'],
        ]
        
        business_table = Table(business_info, colWidths=[1.5*inch, 2*inch, 1*inch, 1.5*inch])  # 4 columns for compact layout
        business_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#374151')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),  # Reduced font size
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),  # First column bold
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),  # Third column bold
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
        ]))
        
        story.append(business_table)
        story.append(Spacer(1, 0.15*inch))  # Reduced from 0.3*inch
        
        # Compact Summary section
        if 'summary' in report_data:
            story.append(Paragraph("Executive Summary", heading_style))
            
            # Create 2-column summary layout for better space utilization
            summary_items = list(report_data['summary'].items())
            summary_data = [['Metric', 'Value', 'Metric', 'Value']]
            
            for i in range(0, len(summary_items), 2):
                row = []
                
                # First metric
                key1, value1 = summary_items[i]
                if isinstance(value1, Decimal):
                    formatted_value1 = f"KES {value1:,.0f}"  # No decimals for cleaner look
                elif isinstance(value1, (int, float)) and 'rate' in key1.lower():
                    formatted_value1 = f"{value1:.1f}%"
                else:
                    formatted_value1 = str(value1)
                
                row.extend([key1.replace('_', ' ').title(), formatted_value1])
                
                # Second metric (if exists)
                if i + 1 < len(summary_items):
                    key2, value2 = summary_items[i + 1]
                    if isinstance(value2, Decimal):
                        formatted_value2 = f"KES {value2:,.0f}"
                    elif isinstance(value2, (int, float)) and 'rate' in key2.lower():
                        formatted_value2 = f"{value2:.1f}%"
                    else:
                        formatted_value2 = str(value2)
                    
                    row.extend([key2.replace('_', ' ').title(), formatted_value2])
                else:
                    row.extend(['', ''])
                
                summary_data.append(row)
            
            summary_table = Table(summary_data, colWidths=[1.4*inch, 1.1*inch, 1.4*inch, 1.1*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),  # Reduced font size
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            story.append(summary_table)
            story.append(Spacer(1, 0.15*inch))  # Reduced from 0.2*inch
        
        # Initialize analysis tracking variable
        analysis_added = False  # Track if any analysis was added
        
        # Detailed breakdown sections with actual data lists
        # Skip general detailed analysis for individual employee reports
        if report_data.get('type', '').lower() != 'individual_employee':
            story.append(PageBreak())
            story.append(Paragraph("Detailed Analysis", heading_style))
            story.append(Spacer(1, 0.15*inch))  # Reduced spacing
        
        # Income Analysis - Show actual payments/transactions
        if 'income' in report_type or 'revenue' in report_type or 'financial' in report_type:
            story.append(Paragraph("Revenue Breakdown & Payment Transactions", heading_style))
            
            # First show revenue breakdown if available
            if 'breakdown' in report_data and report_data['breakdown']:
                breakdown = report_data['breakdown']
                
                # Revenue by service breakdown
                if 'revenue_by_service' in breakdown and breakdown['revenue_by_service']:
                    story.append(Paragraph("Revenue by Service Category", ParagraphStyle(
                        'SubHeading', parent=styles['Normal'], fontSize=11, 
                        textColor=colors.HexColor('#374151'), fontName='Helvetica-Bold',
                        spaceAfter=0.1*inch
                    )))
                    
                    revenue_data = [['Service', 'Orders', 'Total Revenue', 'Avg per Order']]
                    for service in breakdown['revenue_by_service'][:15]:  # Limit to top 15
                        service_name = service.get('service_order__order_items__service__name', 'Unknown Service')
                        order_count = service.get('order_count', 0)
                        revenue = service.get('revenue', 0)
                        avg_revenue = revenue / order_count if order_count > 0 else 0
                        
                        revenue_data.append([
                            service_name[:25] + '...' if len(service_name) > 25 else service_name,
                            str(order_count),
                            f"KES {revenue:,.2f}",
                            f"KES {avg_revenue:,.2f}"
                        ])
                    
                    revenue_table = Table(revenue_data, colWidths=[2*inch, 0.8*inch, 1.2*inch, 1.2*inch])
                    revenue_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#059669')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 0), (-1, -1), 8),
                        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ]))
                    story.append(revenue_table)
                    story.append(Spacer(1, 0.2*inch))
                    analysis_added = True
                
                # Payment method breakdown
                if 'revenue_by_method' in breakdown and breakdown['revenue_by_method']:
                    story.append(Paragraph("Revenue by Payment Method", ParagraphStyle(
                        'SubHeading', parent=styles['Normal'], fontSize=11, 
                        textColor=colors.HexColor('#374151'), fontName='Helvetica-Bold',
                        spaceAfter=0.1*inch
                    )))
                    
                    method_data = [['Payment Method', 'Transactions', 'Total Revenue', 'Avg Transaction']]
                    for method in breakdown['revenue_by_method']:
                        method_name = method.get('payment_method', 'Unknown')
                        transaction_count = method.get('transaction_count', 0)
                        revenue = method.get('revenue', 0)
                        avg_transaction = revenue / transaction_count if transaction_count > 0 else 0
                        
                        method_data.append([
                            method_name,
                            str(transaction_count),
                            f"KES {revenue:,.2f}",
                            f"KES {avg_transaction:,.2f}"
                        ])
                    
                    method_table = Table(method_data, colWidths=[1.5*inch, 1*inch, 1.2*inch, 1.2*inch])
                    method_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 0), (-1, -1), 8),
                        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
                    ]))
                    story.append(method_table)
                    story.append(Spacer(1, 0.2*inch))
                    analysis_added = True
            
            # Recent payment transactions
            from apps.payments.models import Payment
            payments = Payment.objects.filter(
                status__in=['completed', 'verified']
            ).select_related('service_order__customer', 'payment_method').order_by('-created_at')[:25]  # Reduced to 25
            
            if payments:
                story.append(Paragraph("Recent Payment Transactions", ParagraphStyle(
                    'SubHeading', parent=styles['Normal'], fontSize=11, 
                    textColor=colors.HexColor('#374151'), fontName='Helvetica-Bold',
                    spaceAfter=0.1*inch
                )))
                
                payment_data = [['Date', 'Customer', 'Amount', 'Method', 'Status']]
                for payment in payments:
                    customer_name = 'N/A'
                    if payment.service_order and payment.service_order.customer:
                        customer_name = payment.service_order.customer.display_name
                    
                    payment_data.append([
                        payment.created_at.strftime('%m/%d/%Y'),  # More compact date format
                        customer_name[:20] + '...' if len(customer_name) > 20 else customer_name,
                        f"KES {payment.amount:,.0f}",  # No decimals for cleaner look
                        str(payment.payment_method.name)[:12] if payment.payment_method else 'N/A',
                        payment.status.title()
                    ])
                
                payment_table = Table(payment_data, colWidths=[0.9*inch, 1.4*inch, 1*inch, 1*inch, 0.8*inch])
                payment_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#059669')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]))
                story.append(payment_table)
                story.append(Spacer(1, 0.2*inch))
                analysis_added = True
        
        # Customer Analytics - Show actual customers with detailed breakdown
        if 'customer' in report_type:
            story.append(Paragraph("Customer Activity Analysis", heading_style))
            
            # Use top_customers from report data that has annotations
            customers = report_data.get('top_customers', [])
            
            if customers:
                story.append(Paragraph("Top Customer Performance", ParagraphStyle(
                    'SubHeading', parent=styles['Normal'], fontSize=11, 
                    textColor=colors.HexColor('#374151'), fontName='Helvetica-Bold',
                    spaceAfter=0.1*inch
                )))
                
                customer_data = [['Customer Name', 'Contact', 'Orders', 'Total Spent', 'Avg Order']]
                for customer in customers[:20]:  # Top 20 customers
                    total_spent = getattr(customer, 'period_spent', 0) or getattr(customer, 'total_spent', 0)
                    order_count = getattr(customer, 'order_count', 0)
                    avg_order = total_spent / order_count if order_count > 0 else 0
                    
                    customer_data.append([
                        customer.display_name[:25] + '...' if len(customer.display_name) > 25 else customer.display_name,
                        str(customer.phone_number)[:12] if customer.phone_number else customer.email[:15] if customer.email else 'N/A',
                        str(order_count),
                        f"KES {total_spent:,.0f}",
                        f"KES {avg_order:,.0f}"
                    ])
                
                customer_table = Table(customer_data, colWidths=[1.8*inch, 1.2*inch, 0.7*inch, 1*inch, 1*inch])
                customer_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
                ]))
                story.append(customer_table)
                story.append(Spacer(1, 0.2*inch))
                analysis_added = True
        
        # Service Analysis with performance metrics
        if 'service' in report_type or 'business' in report_type or 'sales' in report_type or 'daily' in report_type:
            story.append(Paragraph("Service Performance Analysis", heading_style))
            
            # Service orders analysis
            from apps.services.models import ServiceOrder
            recent_orders = ServiceOrder.objects.select_related(
                'customer', 'vehicle', 'assigned_attendant'
            ).order_by('-created_at')[:30]  # Reduced to 30
            
            if recent_orders:
                story.append(Paragraph("Recent Service Orders", ParagraphStyle(
                    'SubHeading', parent=styles['Normal'], fontSize=11, 
                    textColor=colors.HexColor('#374151'), fontName='Helvetica-Bold',
                    spaceAfter=0.1*inch
                )))
                
                order_data = [['Date', 'Customer', 'Service', 'Employee', 'Status', 'Amount']]
                for order in recent_orders:
                    # Get service name from order items
                    service_name = 'N/A'
                    order_items = order.order_items.all()
                    if order_items:
                        service_name = order_items.first().service.name[:15]
                    
                    customer_name = order.customer.display_name[:15] if order.customer else 'N/A'
                    employee_name = f"{order.assigned_attendant.first_name}" if order.assigned_attendant else 'Unassigned'
                    
                    order_data.append([
                        order.created_at.strftime('%m/%d'),  # Very compact date
                        customer_name,
                        service_name,
                        employee_name[:10],
                        order.get_status_display()[:8],
                        f"KES {order.total_amount:,.0f}"
                    ])
                
                order_table = Table(order_data, colWidths=[0.7*inch, 1.2*inch, 1.2*inch, 0.8*inch, 0.8*inch, 1*inch])
                order_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f59e0b')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
                ]))
                story.append(order_table)
                story.append(Spacer(1, 0.2*inch))
                analysis_added = True
        
        # Expense Analysis - Show actual expenses with breakdown
        if 'expense' in report_type:
            story.append(Paragraph("Expense Analysis & Transactions", heading_style))
            
            # Expense breakdown by category if available
            if 'breakdown' in report_data and report_data['breakdown']:
                breakdown = report_data['breakdown']
                
                if 'category_breakdown' in breakdown and breakdown['category_breakdown']:
                    story.append(Paragraph("Expense by Category", ParagraphStyle(
                        'SubHeading', parent=styles['Normal'], fontSize=11, 
                        textColor=colors.HexColor('#374151'), fontName='Helvetica-Bold',
                        spaceAfter=0.1*inch
                    )))
                    
                    category_data = [['Category', 'Count', 'Total Amount', 'Avg Amount']]
                    for category in breakdown['category_breakdown']:
                        category_name = category.get('category__name', 'Uncategorized')
                        count = category.get('count', 0)
                        amount = category.get('amount', 0)
                        avg_amount = category.get('avg_amount', 0)
                        
                        category_data.append([
                            category_name,
                            str(count),
                            f"KES {amount:,.0f}",
                            f"KES {avg_amount:,.0f}"
                        ])
                    
                    category_table = Table(category_data, colWidths=[2*inch, 0.8*inch, 1.2*inch, 1.2*inch])
                    category_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#dc2626')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 0), (-1, -1), 8),
                        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
                    ]))
                    story.append(category_table)
                    story.append(Spacer(1, 0.2*inch))
                    analysis_added = True
            
            # Recent expense transactions
            from apps.expenses.models import Expense
            expenses = Expense.objects.select_related(
                'category', 'employee'
            ).order_by('-date')[:25]  # Reduced to 25
            
            if expenses:
                story.append(Paragraph("Recent Expense Transactions", ParagraphStyle(
                    'SubHeading', parent=styles['Normal'], fontSize=11, 
                    textColor=colors.HexColor('#374151'), fontName='Helvetica-Bold',
                    spaceAfter=0.1*inch
                )))
                
                expense_data = [['Date', 'Description', 'Category', 'Employee', 'Amount']]
                for expense in expenses:
                    description = expense.description[:25] + '...' if len(expense.description) > 25 else expense.description
                    category_name = expense.category.name if expense.category else 'N/A'
                    employee_name = f"{expense.employee.first_name}" if expense.employee else 'N/A'
                    
                    expense_data.append([
                        expense.date.strftime('%m/%d/%Y'),
                        description,
                        category_name[:12],
                        employee_name[:10],
                        f"KES {expense.amount:,.0f}"
                    ])
                
                expense_table = Table(expense_data, colWidths=[0.9*inch, 1.8*inch, 1*inch, 0.8*inch, 1*inch])
                expense_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#dc2626')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
                ]))
                story.append(expense_table)
                story.append(Spacer(1, 0.2*inch))
                analysis_added = True
        
        # Inventory Analysis - Show inventory movement
        if 'inventory' in report_type:
            story.append(Paragraph("Inventory Analysis & Items", heading_style))
            from apps.inventory.models import InventoryItem
            items = InventoryItem.objects.filter(
                is_active=True
            ).select_related('category')[:25]  # Reduced to 25
            
            if items:
                story.append(Paragraph("Current Inventory Status", ParagraphStyle(
                    'SubHeading', parent=styles['Normal'], fontSize=11, 
                    textColor=colors.HexColor('#374151'), fontName='Helvetica-Bold',
                    spaceAfter=0.1*inch
                )))
                
                inventory_data = [['Item Name', 'Category', 'Stock', 'Unit Cost', 'Stock Value']]
                for item in items:
                    item_name = item.name[:20] + '...' if len(item.name) > 20 else item.name
                    category_name = item.category.name if item.category else 'N/A'
                    stock_info = f"{item.current_stock} {item.unit.abbreviation}"
                    
                    inventory_data.append([
                        item_name,
                        category_name[:10],
                        stock_info,
                        f"KES {item.base_price:,.0f}",
                        f"KES {item.current_stock * item.base_price:,.0f}"
                    ])
                
                inventory_table = Table(inventory_data, colWidths=[1.5*inch, 1*inch, 1*inch, 1*inch, 1.2*inch])
                inventory_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7c3aed')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
                ]))
                story.append(inventory_table)
                story.append(Spacer(1, 0.2*inch))
                analysis_added = True
        
        # If no specific analysis was added, show general business metrics
        if not analysis_added:
            story.append(Paragraph("Business Performance Metrics", ParagraphStyle(
                'SubHeading', parent=styles['Normal'], fontSize=11, 
                textColor=colors.HexColor('#374151'), fontName='Helvetica-Bold',
                spaceAfter=0.1*inch
            )))
            
            # Show basic business data
            from apps.services.models import ServiceOrder
            from apps.payments.models import Payment
            
            recent_orders = ServiceOrder.objects.select_related('customer').order_by('-created_at')[:15]
            recent_payments = Payment.objects.filter(status='completed').select_related('payment_method').order_by('-created_at')[:15]
            
            if recent_orders:
                general_data = [['Type', 'Date', 'Description', 'Amount']]
                
                # Mix orders and payments for general overview
                for order in recent_orders[:10]:
                    general_data.append([
                        'Service',
                        order.created_at.strftime('%m/%d'),
                        f"{order.customer.display_name}" if order.customer else 'Unknown Customer',
                        f"KES {order.total_amount:,.0f}"
                    ])
                
                for payment in recent_payments[:10]:
                    general_data.append([
                        'Payment',
                        payment.created_at.strftime('%m/%d'),
                        str(payment.payment_method.name) if payment.payment_method else 'N/A',
                        f"KES {payment.amount:,.0f}"
                    ])
                
                general_table = Table(general_data, colWidths=[1*inch, 1*inch, 2.5*inch, 1.2*inch])
                general_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#374151')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
                ]))
                story.append(general_table)
                story.append(Spacer(1, 0.2*inch))
        
        # Inventory Items List
        if 'inventory' in report_type:
            story.append(Paragraph("Inventory Items", heading_style))
            from apps.inventory.models import InventoryItem
            items = InventoryItem.objects.filter(is_active=True).select_related('category')[:40]
            
            if items:
                inventory_data = [['Item', 'Category', 'Stock', 'Unit Cost', 'Total Value']]
                for item in items:
                    inventory_data.append([
                        item.name,
                        item.category.name if item.category else 'N/A',
                        f"{item.current_stock} {item.unit.abbreviation}",
                        f"KES {item.unit_cost:,.2f}",
                        f"KES {item.stock_value:,.2f}"
                    ])
                
                inventory_table = Table(inventory_data, colWidths=[1.5*inch, 1*inch, 1*inch, 1*inch, 1.5*inch])
                inventory_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7c3aed')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
                ]))
                story.append(inventory_table)
                story.append(Spacer(1, 0.3*inch))
        
        # End of general detailed analysis section (skip for individual employee reports)
        
        # Employee Performance - Show employee activities (but not for individual employee reports)
        if 'employee' in report_type and report_type != 'individual_employee':
            story.append(Paragraph("Employee Activities", heading_style))
            from apps.employees.models import Employee
            from apps.services.models import ServiceOrder
            employees = Employee.objects.filter(is_active=True)[:20]
            
            if employees:
                employee_data = [['Employee', 'Position', 'Orders Handled', 'Total Revenue', 'Avg Rating']]
                for employee in employees:
                    orders_count = ServiceOrder.objects.filter(assigned_attendant=employee).count()
                    total_revenue = ServiceOrder.objects.filter(assigned_attendant=employee).aggregate(
                        Sum('total_amount'))['total_amount__sum'] or Decimal('0')
                    avg_rating = ServiceOrder.objects.filter(assigned_attendant=employee, customer_rating__isnull=False).aggregate(
                        Avg('customer_rating'))['customer_rating__avg'] or 0
                    
                    employee_data.append([
                        f"{employee.first_name} {employee.last_name}",
                        employee.position or 'N/A',
                        str(orders_count),
                        f"KES {total_revenue:,.2f}",
                        f"{avg_rating:.1f}/5.0" if avg_rating else 'N/A'
                    ])
                
                employee_table = Table(employee_data, colWidths=[1.5*inch, 1*inch, 1*inch, 1.2*inch, 1.3*inch])
                employee_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#059669')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
                ]))
                story.append(employee_table)
                story.append(Spacer(1, 0.3*inch))
        
        # Individual Employee Report - Show only specific employee's data
        if report_type == 'individual_employee' and 'breakdown' in report_data and report_data['breakdown']:
            # Move to new page for individual employee data
            story.append(PageBreak())
            story.append(Paragraph(f"Individual Employee Performance Report", heading_style))
            
            # Employee information section
            if 'employee' in report_data:
                employee_info = report_data['employee']
                story.append(Paragraph(f"Employee: {employee_info.get('full_name', 'N/A')}", ParagraphStyle(
                    'EmployeeName', parent=styles['Normal'], fontSize=14, 
                    textColor=colors.HexColor('#1f2937'), fontName='Helvetica-Bold',
                    spaceAfter=0.1*inch
                )))
                
                # Employee details
                employee_data = [
                    ['Employee ID:', employee_info.get('employee_id', 'N/A'), 'Position:', employee_info.get('position', 'N/A')],
                    ['Department:', employee_info.get('department', 'N/A'), 'Report Period:', report_data.get('period', 'N/A')]
                ]
                
                employee_details_table = Table(employee_data, colWidths=[1.5*inch, 2*inch, 1.5*inch, 2*inch])
                employee_details_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
                    ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#374151')),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),  
                    ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),  
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
                ]))
                story.append(employee_details_table)
                story.append(Spacer(1, 0.2*inch))
            
            breakdown = report_data['breakdown']
            
            # Service breakdown for individual employee
            if 'service_breakdown' in breakdown and breakdown['service_breakdown']:
                story.append(Paragraph("Service Performance Breakdown", heading_style))
                service_data = [['Service', 'Category', 'Count', 'Quantity', 'Revenue']]
                
                for service in breakdown['service_breakdown']:
                    service_data.append([
                        service.get('service__name', 'N/A'),
                        service.get('service__category__name', 'N/A'),
                        str(service.get('service_count', 0)),
                        str(service.get('total_quantity', 0)),
                        f"KES {service.get('total_price', 0):,.2f}"
                    ])
                
                service_table = Table(service_data, colWidths=[1.5*inch, 1.2*inch, 0.8*inch, 0.8*inch, 1.2*inch])
                service_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8b5cf6')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
                ]))
                story.append(service_table)
                story.append(Spacer(1, 0.2*inch))
            
            # Daily performance for individual employee
            if 'daily_performance' in breakdown and breakdown['daily_performance']:
                story.append(Paragraph("Daily Performance", heading_style))
                daily_data = [['Date', 'Orders', 'Revenue']]
                
                for day in breakdown['daily_performance']:
                    daily_data.append([
                        str(day.get('date', 'N/A')),
                        str(day.get('daily_orders', 0)),
                        f"KES {day.get('daily_revenue', 0):,.2f}"
                    ])
                
                daily_table = Table(daily_data, colWidths=[2*inch, 1*inch, 1.5*inch])
                daily_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10b981')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
                ]))
                story.append(daily_table)
                story.append(Spacer(1, 0.2*inch))
            
            # Signature section
            story.append(PageBreak())
            story.append(Paragraph("Signatures", heading_style))
            story.append(Spacer(1, 0.2*inch))
            
            signature_data = [
                ['Employee Signature:', '_' * 30, 'Date:', '_' * 15],
                ['', '', '', ''],
                ['Manager/Supervisor Signature:', '_' * 30, 'Date:', '_' * 15],
            ]
            
            signature_table = Table(signature_data, colWidths=[2*inch, 2*inch, 1*inch, 1*inch])
            signature_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
                ('TOPPADDING', (0, 0), (-1, -1), 20),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 20),
            ]))
            story.append(signature_table)
        
        # Compact footer with report generation details
        story.append(Spacer(1, 0.3*inch))  # Reduced from PageBreak + 0.5*inch
        
        # Combined footer information in one line
        footer_text = f"Report Generated: {timezone.now().strftime('%B %d, %Y at %I:%M %p')} | Report Period: {report_data.get('period', 'N/A')} | Generated by AutoWash Management System"
        footer_style = ParagraphStyle(
            'FooterText',
            parent=styles['Normal'],
            fontSize=8,  # Reduced font size
            textColor=colors.HexColor('#6b7280'),
            alignment=TA_CENTER,
            spaceAfter=0.1*inch  # Reduced spacing
        )
        
        story.append(Paragraph(footer_text, footer_style))
        
        # Copyright notice
        copyright_text = "© 2025 AutoWash Management System. All rights reserved."
        copyright_style = ParagraphStyle(
            'CopyrightText',
            parent=styles['Normal'],
            fontSize=7,  # Reduced font size
            textColor=colors.HexColor('#9ca3af'),
            alignment=TA_CENTER
        )
        
        story.append(Paragraph(copyright_text, copyright_style))
        
        doc.build(story)
        
        buffer.seek(0)
        response = HttpResponse(buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{report_data.get("type", "report")}_detailed_report.pdf"'
        
        return response
    
    def _generate_excel(self, report_data, tenant):
        """Generate enhanced Excel report"""
        if not EXCEL_AVAILABLE:
            return JsonResponse({'error': 'Excel generation not available'}, status=500)
        
        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer)
        
        # Add formats
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#1f2937',
            'font_color': 'white'
        })
        
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#3b82f6',
            'font_color': 'white',
            'border': 1
        })
        
        currency_format = workbook.add_format({
            'num_format': 'KES #,##0.00',
            'border': 1
        })
        
        # Summary worksheet
        worksheet = workbook.add_worksheet('Summary')
        
        # Business header
        worksheet.merge_range('A1:E1', f"{tenant.name} - {report_data['title']}", title_format)
        worksheet.write('A2', f"Period: {report_data['period']}")
        worksheet.write('A3', f"Generated: {timezone.now().strftime('%B %d, %Y at %I:%M %p')}")
        
        row = 5
        
        # Business information
        worksheet.write(row, 0, 'Business Information', header_format)
        worksheet.write(row, 1, '', header_format)
        row += 1
        
        business_info = [
            ('Business Name', tenant.name),
            ('Business Type', getattr(tenant, 'business_type', 'Car Wash').title()),
            ('Contact', str(getattr(tenant, 'phone', 'N/A')) if getattr(tenant, 'phone', None) else 'N/A'),
            ('Email', getattr(tenant, 'email', 'N/A')),
            ('Currency', 'Kenyan Shilling (KES)')
        ]
        
        for label, value in business_info:
            worksheet.write(row, 0, label)
            worksheet.write(row, 1, str(value) if value is not None else 'N/A')
            row += 1
        
        row += 1
        
        # Summary data
        if 'summary' in report_data:
            worksheet.write(row, 0, 'Summary Metrics', header_format)
            worksheet.write(row, 1, 'Value', header_format)
            row += 1
            
            for key, value in report_data['summary'].items():
                worksheet.write(row, 0, key.replace('_', ' ').title())
                if isinstance(value, Decimal) and 'amount' in key.lower():
                    worksheet.write(row, 1, float(value), currency_format)
                else:
                    worksheet.write(row, 1, str(value) if value is not None else 'N/A')
                row += 1
        
        # Create detailed breakdown worksheets
        if 'breakdown' in report_data and report_data['breakdown']:
            breakdown = report_data['breakdown']
            report_type = report_data.get('type', '')
            
            # Individual Employee Report - Only show employee-specific data
            if report_type == 'individual_employee':
                # Employee info worksheet
                if 'employee' in report_data:
                    emp_info_ws = workbook.add_worksheet('Employee Information')
                    emp_info_ws.write(0, 0, 'Employee Information', title_format)
                    
                    employee = report_data['employee']
                    emp_info = [
                        ('Employee ID', employee.get('employee_id', 'N/A')),
                        ('Full Name', employee.get('full_name', 'N/A')),
                        ('Position', employee.get('position', 'N/A')),
                        ('Department', employee.get('department', 'N/A')),
                        ('Report Period', report_data.get('period', 'N/A'))
                    ]
                    
                    headers = ['Field', 'Value']
                    for col, header in enumerate(headers):
                        emp_info_ws.write(2, col, header, header_format)
                    
                    row = 3
                    for field, value in emp_info:
                        emp_info_ws.write(row, 0, field)
                        emp_info_ws.write(row, 1, str(value))
                        row += 1
                
                # Service breakdown worksheet for individual employee
                if 'service_breakdown' in breakdown and breakdown['service_breakdown']:
                    service_ws = workbook.add_worksheet('My Service Performance')
                    service_ws.write(0, 0, 'Individual Service Performance', title_format)
                    
                    headers = ['Service Name', 'Category', 'Usage Count', 'Total Quantity', 'Revenue']
                    for col, header in enumerate(headers):
                        service_ws.write(2, col, header, header_format)
                    
                    row = 3
                    for service in breakdown['service_breakdown']:
                        service_ws.write(row, 0, service.get('service__name', 'N/A'))
                        service_ws.write(row, 1, service.get('service__category__name', 'N/A'))
                        service_ws.write(row, 2, service.get('service_count', 0))
                        service_ws.write(row, 3, service.get('total_quantity', 0))
                        service_ws.write(row, 4, float(service.get('total_price', 0)), currency_format)
                        row += 1
                
                # Daily performance worksheet for individual employee
                if 'daily_performance' in breakdown and breakdown['daily_performance']:
                    daily_ws = workbook.add_worksheet('My Daily Performance')
                    daily_ws.write(0, 0, 'Individual Daily Performance', title_format)
                    
                    headers = ['Date', 'Orders Count', 'Revenue']
                    for col, header in enumerate(headers):
                        daily_ws.write(2, col, header, header_format)
                    
                    row = 3
                    for day in breakdown['daily_performance']:
                        daily_ws.write(row, 0, str(day.get('date', 'N/A')))
                        daily_ws.write(row, 1, day.get('daily_orders', 0))
                        daily_ws.write(row, 2, float(day.get('daily_revenue', 0)), currency_format)
                        row += 1
                
                # Performance summary worksheet for individual employee
                if 'summary' in report_data:
                    perf_ws = workbook.add_worksheet('Performance Summary')
                    perf_ws.write(0, 0, 'My Performance Summary', title_format)
                    
                    headers = ['Metric', 'Value']
                    for col, header in enumerate(headers):
                        perf_ws.write(2, col, header, header_format)
                    
                    row = 3
                    summary = report_data['summary']
                    for key, value in summary.items():
                        perf_ws.write(row, 0, key.replace('_', ' ').title())
                        if isinstance(value, Decimal):
                            perf_ws.write(row, 1, float(value), currency_format)
                        else:
                            perf_ws.write(row, 1, str(value) if value is not None else 'N/A')
                        row += 1
            
            # General Business Reports - Show all business data
            else:
                # Service breakdown worksheet
                if 'service_breakdown' in breakdown and breakdown['service_breakdown']:
                    service_ws = workbook.add_worksheet('Service Breakdown')
                    service_ws.write(0, 0, 'Service Performance Analysis', title_format)
                    
                    headers = ['Service Name', 'Category', 'Usage Count', 'Total Quantity', 'Revenue']
                    for col, header in enumerate(headers):
                        service_ws.write(2, col, header, header_format)
                    
                    row = 3
                    for service in breakdown['service_breakdown']:
                        service_ws.write(row, 0, service.get('service__name', 'N/A'))
                        service_ws.write(row, 1, service.get('service__category__name', 'N/A'))
                        service_ws.write(row, 2, service.get('service_count', 0))
                        service_ws.write(row, 3, service.get('total_quantity', 0))
                        service_ws.write(row, 4, float(service.get('total_price', 0)), currency_format)
                        row += 1
                
                # Daily performance worksheet
                if 'daily_performance' in breakdown and breakdown['daily_performance']:
                    daily_ws = workbook.add_worksheet('Daily Performance')
                    daily_ws.write(0, 0, 'Daily Performance Trend', title_format)
                    
                    headers = ['Date', 'Orders Count', 'Revenue']
                    for col, header in enumerate(headers):
                        daily_ws.write(2, col, header, header_format)
                    
                    row = 3
                    for day in breakdown['daily_performance']:
                        daily_ws.write(row, 0, str(day.get('date', 'N/A')))
                        daily_ws.write(row, 1, day.get('daily_orders', 0))
                        daily_ws.write(row, 2, float(day.get('daily_revenue', 0)), currency_format)
                        row += 1
            
            # Inventory items worksheet (only for general reports)
            if report_type != 'individual_employee' and 'item_details' in breakdown and breakdown['item_details']:
                inventory_ws = workbook.add_worksheet('Inventory Details')
                inventory_ws.write(0, 0, 'Inventory Item Analysis', title_format)
                
                headers = ['Item Name', 'Stock Status', 'Transactions In', 'Transactions Out', 'Net Movement', 'Current Value']
                for col, header in enumerate(headers):
                    inventory_ws.write(2, col, header, header_format)
                
                row = 3
                for item_stat in breakdown['item_details']:
                    item = item_stat.get('item')
                    inventory_ws.write(row, 0, getattr(item, 'name', 'N/A'))
                    inventory_ws.write(row, 1, item_stat.get('stock_status', 'N/A'))
                    inventory_ws.write(row, 2, item_stat.get('transactions_in', 0))
                    inventory_ws.write(row, 3, item_stat.get('transactions_out', 0))
                    inventory_ws.write(row, 4, item_stat.get('net_movement', 0))
                    inventory_ws.write(row, 5, float(item_stat.get('current_value', 0)), currency_format)
                    row += 1
            
            # Service details worksheet (only for general reports)
            if report_type != 'individual_employee' and 'service_details' in breakdown and breakdown['service_details']:
                service_detail_ws = workbook.add_worksheet('Service Analysis')
                service_detail_ws.write(0, 0, 'Comprehensive Service Analysis', title_format)
                
                headers = ['Service Name', 'Category', 'Usage Count', 'Revenue', 'Average Price', 'Popularity Rank']
                for col, header in enumerate(headers):
                    service_detail_ws.write(2, col, header, header_format)
                
                row = 3
                for service_stat in breakdown['service_details']:
                    service = service_stat.get('service')
                    service_detail_ws.write(row, 0, getattr(service, 'name', 'N/A'))
                    service_detail_ws.write(row, 1, service_stat.get('category', 'N/A'))
                    service_detail_ws.write(row, 2, service_stat.get('usage_count', 0))
                    service_detail_ws.write(row, 3, float(service_stat.get('revenue', 0)), currency_format)
                    service_detail_ws.write(row, 4, float(service_stat.get('avg_price', 0)), currency_format)
                    service_detail_ws.write(row, 5, service_stat.get('popularity_rank', 0))
                    row += 1
            
            # Payment methods worksheet (only for general reports)
            if report_type != 'individual_employee' and 'payment_method_breakdown' in breakdown and breakdown['payment_method_breakdown']:
                payment_ws = workbook.add_worksheet('Payment Methods')
                payment_ws.write(0, 0, 'Payment Method Analysis', title_format)
                
                headers = ['Payment Method', 'Transaction Count', 'Total Amount', 'Average Amount']
                for col, header in enumerate(headers):
                    payment_ws.write(2, col, header, header_format)
                
                row = 3
                for payment in breakdown['payment_method_breakdown']:
                    payment_ws.write(row, 0, payment.get('payment_method', 'N/A'))
                    payment_ws.write(row, 1, payment.get('transaction_count', 0))
                    payment_ws.write(row, 2, float(payment.get('total_amount', 0)), currency_format)
                    payment_ws.write(row, 3, float(payment.get('avg_amount', 0)), currency_format)
                    row += 1
            
            # Employee performance worksheet (only for general reports)
            if report_type != 'individual_employee' and 'employee_performance' in breakdown and breakdown['employee_performance']:
                emp_ws = workbook.add_worksheet('Employee Performance')
                emp_ws.write(0, 0, 'Employee Performance Analysis', title_format)
                
                headers = ['Employee Name', 'Total Orders', 'Completed Orders', 'Completion Rate (%)', 'Total Revenue', 'Average Rating', 'Avg Completion Time (min)']
                for col, header in enumerate(headers):
                    emp_ws.write(2, col, header, header_format)
                
                row = 3
                for emp_stat in breakdown['employee_performance']:
                    employee = emp_stat.get('employee')
                    emp_ws.write(row, 0, f"{getattr(employee, 'first_name', '')} {getattr(employee, 'last_name', '')}")
                    emp_ws.write(row, 1, emp_stat.get('total_orders', 0))
                    emp_ws.write(row, 2, emp_stat.get('completed_orders', 0))
                    emp_ws.write(row, 3, emp_stat.get('completion_rate', 0))
                    emp_ws.write(row, 4, float(emp_stat.get('total_revenue', 0)), currency_format)
                    emp_ws.write(row, 5, emp_stat.get('avg_rating', 0) if emp_stat.get('avg_rating') else 'N/A')
                    emp_ws.write(row, 6, emp_stat.get('avg_completion_time_minutes', 0) if emp_stat.get('avg_completion_time_minutes') else 'N/A')
                    row += 1
            
            # Vehicle details worksheet (only for general reports)
            if report_type != 'individual_employee' and 'vehicle_details' in breakdown and breakdown['vehicle_details']:
                vehicle_ws = workbook.add_worksheet('Vehicle Analysis')
                vehicle_ws.write(0, 0, 'Vehicle Performance Analysis', title_format)
                
                headers = ['Vehicle', 'Owner', 'Total Orders', 'Total Revenue', 'Average Order Value', 'Last Service']
                for col, header in enumerate(headers):
                    vehicle_ws.write(2, col, header, header_format)
                
                row = 3
                for vehicle_stat in breakdown['vehicle_details']:
                    vehicle = vehicle_stat.get('vehicle')
                    owner = vehicle_stat.get('owner')
                    last_service = vehicle_stat.get('last_service')
                    
                    vehicle_ws.write(row, 0, f"{getattr(vehicle, 'make', '')} {getattr(vehicle, 'model', '')} - {getattr(vehicle, 'plate_number', '')}")
                    vehicle_ws.write(row, 1, f"{getattr(owner, 'first_name', '')} {getattr(owner, 'last_name', '')}" if owner else 'N/A')
                    vehicle_ws.write(row, 2, vehicle_stat.get('total_orders', 0))
                    vehicle_ws.write(row, 3, float(vehicle_stat.get('total_revenue', 0)), currency_format)
                    vehicle_ws.write(row, 4, float(vehicle_stat.get('avg_order_value', 0)), currency_format)
                    vehicle_ws.write(row, 5, str(last_service.created_at.date()) if last_service else 'N/A')
                    row += 1
        
        workbook.close()
        
        buffer.seek(0)
        response = HttpResponse(
            buffer.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{report_data.get("type", "report")}_detailed_report.xlsx"'
        
        return response
    
    def _generate_business_insights(self, report_data):
        """Generate business insights and recommendations based on report data"""
        insights = []
        
        if 'summary' in report_data:
            summary = report_data['summary']
            
            # Revenue insights
            if 'total_revenue' in summary:
                revenue = summary['total_revenue']
                if revenue > 100000:  # KES 100,000
                    insights.append("Strong revenue performance indicates healthy business operations.")
                elif revenue > 50000:  # KES 50,000
                    insights.append("Moderate revenue performance. Consider marketing campaigns to boost sales.")
                else:
                    insights.append("Revenue below optimal levels. Review pricing strategy and service offerings.")
            
            # Order insights
            if 'total_orders' in summary:
                orders = summary['total_orders']
                if orders > 100:
                    insights.append("High order volume demonstrates strong customer demand.")
                elif orders > 50:
                    insights.append("Moderate order volume. Focus on customer retention strategies.")
                else:
                    insights.append("Low order volume. Implement customer acquisition campaigns.")
            
            # Completion rate insights
            if 'completion_rate' in summary:
                completion = summary['completion_rate']
                if completion > 90:
                    insights.append("Excellent service completion rate maintains customer satisfaction.")
                elif completion > 70:
                    insights.append("Good completion rate. Monitor for potential operational improvements.")
                else:
                    insights.append("Low completion rate requires immediate attention to operational processes.")
            
            # Employee performance insights
            if 'avg_rating' in summary:
                rating = summary['avg_rating']
                if rating > 4.0:
                    insights.append("High customer satisfaction ratings reflect quality service delivery.")
                elif rating > 3.0:
                    insights.append("Moderate satisfaction ratings. Consider staff training programs.")
                else:
                    insights.append("Low satisfaction ratings require immediate service quality improvements.")
        
        # Inventory insights
        if 'breakdown' in report_data and 'item_details' in report_data['breakdown']:
            low_stock_count = sum(1 for item in report_data['breakdown']['item_details'] 
                                if item.get('stock_status') == 'Low Stock')
            if low_stock_count > 5:
                insights.append("Multiple items are low on stock. Review inventory management processes.")
        
        # Payment method insights
        if 'breakdown' in report_data and 'payment_method_breakdown' in report_data['breakdown']:
            payment_methods = report_data['breakdown']['payment_method_breakdown']
            if payment_methods:
                top_method = payment_methods[0].get('payment_method', '')
                if 'mpesa' in top_method.lower():
                    insights.append("M-Pesa is the preferred payment method. Ensure system reliability.")
                elif 'cash' in top_method.lower():
                    insights.append("Cash payments dominate. Consider promoting digital payment adoption.")
        
        # Default insights if none generated
        if not insights:
            insights = [
                "Maintain regular monitoring of key performance indicators.",
                "Focus on customer satisfaction to drive repeat business.",
                "Optimize operational efficiency to reduce costs.",
                "Consider seasonal trends when planning business strategies."
            ]
        
        return insights
