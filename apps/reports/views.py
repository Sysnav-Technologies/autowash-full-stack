from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q, F
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.contrib import messages
from django.core.paginator import Paginator
from django.views.generic import ListView
from django.utils.decorators import method_decorator
from apps.core.decorators import business_required, employee_required
from datetime import datetime, timedelta
from decimal import Decimal
import json

from .models import BusinessReport, QuickInsight, ReportSchedule
from apps.customers.models import Customer
from apps.payments.models import Payment
from apps.services.models import ServiceOrder, Service
from apps.employees.models import Employee


def _check_data_availability():
    """Check if there's sufficient data for generating reports"""
    data_summary = {
        'customers': Customer.objects.count(),
        'services': Service.objects.count(),
        'service_orders': ServiceOrder.objects.count(),
        'service_order_items': 0,
        'payments': Payment.objects.count(),
        'employees': Employee.objects.count(),
    }
    
    # Get ServiceOrderItem count (it's not a TenantModel so we need to import it)
    try:
        from apps.services.models import ServiceOrderItem
        data_summary['service_order_items'] = ServiceOrderItem.objects.count()
    except:
        pass
    
    return data_summary


@method_decorator([login_required, business_required], name='dispatch')
class ReportsDashboardView(ListView):
    """Main reports dashboard"""
    template_name = 'reports/dashboard.html'
    context_object_name = 'recent_reports'
    
    def get_queryset(self):
        return BusinessReport.objects.filter(status='completed')[:5]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Quick insights
        context['quick_insights'] = QuickInsight.objects.filter(is_active=True)[:6]
        
        # Report types available
        context['report_types'] = BusinessReport.REPORT_TYPES
        
        # Recent activity
        context['total_reports'] = BusinessReport.objects.count()
        context['reports_this_month'] = BusinessReport.objects.filter(
            created_at__month=timezone.now().month,
            created_at__year=timezone.now().year
        ).count()
        
        return context


@login_required
@business_required
@employee_required(['owner', 'manager'])
def generate_business_report(request):
    """Generate a new business report"""
    if request.method == 'POST':
        report_type = request.POST.get('report_type')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        if not all([report_type, start_date, end_date]):
            messages.error(request, 'Please fill in all required fields.')
            return redirect('reports:dashboard')
        
        # Create report
        report = BusinessReport.objects.create(
            report_type=report_type,
            title=f"{dict(BusinessReport.REPORT_TYPES)[report_type]} - {start_date} to {end_date}",
            start_date=start_date,
            end_date=end_date,
            generated_by=request.user.employee if hasattr(request.user, 'employee') else None
        )
        
        # Generate report data based on type
        report_data = _generate_report_data(report_type, start_date, end_date)
        
        report.report_data = report_data
        report.total_revenue = report_data.get('total_revenue', 0)
        report.total_orders = report_data.get('total_orders', 0)
        report.total_customers = report_data.get('total_customers', 0)
        report.status = 'completed'
        report.generated_at = timezone.now()
        report.save()
        
        messages.success(request, f'Report "{report.title}" generated successfully!')
        return redirect(f'/business/{request.tenant.slug}/reports/detail/{report.id}/')
    
    return redirect(f'/business/{request.tenant.slug}/reports/')


def _generate_report_data(report_type, start_date, end_date):
    """Generate report data based on type"""
    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Check data availability
    data_summary = _check_data_availability()
    
    if report_type == 'daily_summary':
        return _generate_daily_summary(start_date, end_date)
    elif report_type == 'weekly_summary':
        return _generate_weekly_summary(start_date, end_date)
    elif report_type == 'monthly_summary':
        return _generate_monthly_summary(start_date, end_date)
    elif report_type == 'financial_overview':
        return _generate_financial_overview(start_date, end_date)
    elif report_type == 'customer_analysis':
        return _generate_customer_analysis(start_date, end_date)
    elif report_type == 'service_performance':
        return _generate_service_performance(start_date, end_date)
    elif report_type == 'payment_summary':
        return _generate_payment_summary_new(start_date, end_date)
    elif report_type == 'employee_performance':
        return _generate_employee_performance(start_date, end_date)
    else:
        return {'error': f'Unknown report type: {report_type}'}


def _generate_daily_summary(start_date, end_date):
    """Generate daily business summary"""
    try:
        from apps.services.models import ServiceOrderItem
        
        # Get payments in the date range - try multiple date fields
        payments_by_completed = Payment.objects.filter(
            status__in=['completed', 'verified'],
            completed_at__date__gte=start_date,
            completed_at__date__lte=end_date
        )
        
        payments_by_created = Payment.objects.filter(
            status__in=['completed', 'verified'],
            initiated_at__date__gte=start_date,
            initiated_at__date__lte=end_date
        )
        
        # Also try filtering by completed payments regardless of date, then filter by created date
        payments_completed_in_period = Payment.objects.filter(
            status__in=['completed', 'verified']
        ).extra(
            where=["DATE(initiated_at) >= %s AND DATE(initiated_at) <= %s"],
            params=[start_date, end_date]
        )
        
        # Use whichever gives us more results
        payment_counts = [
            ('completed_at', payments_by_completed.count()),
            ('initiated_at', payments_by_created.count()), 
            ('initiated_at_extra', payments_completed_in_period.count())
        ]
        
        best_payment_filter = max(payment_counts, key=lambda x: x[1])
        
        if best_payment_filter[0] == 'completed_at':
            payments = payments_by_completed
        elif best_payment_filter[0] == 'initiated_at':
            payments = payments_by_created
        else:
            payments = payments_completed_in_period
        
        # Enhanced date filtering for orders - try multiple date fields
        base_orders = ServiceOrder.objects.all()
        
        order_filters = [
            Q(completed_at__date__gte=start_date, completed_at__date__lte=end_date),
            Q(created_at__date__gte=start_date, created_at__date__lte=end_date),
            Q(updated_at__date__gte=start_date, updated_at__date__lte=end_date),
        ]
        
        orders = None
        orders_count = 0
        
        # Try each order filter and use the one that returns data
        for i, order_filter in enumerate(order_filters):
            try:
                filtered_orders = base_orders.filter(order_filter)
                count = filtered_orders.count()
                
                if count > orders_count:
                    orders = filtered_orders
                    orders_count = count
                    best_order_filter = ('completed_at' if i==0 else 'created_at' if i==1 else 'updated_at')
            except Exception as filter_error:
                continue
        
        # If no specific filter worked, use all orders
        if orders is None or orders_count == 0:
            orders = base_orders
            best_order_filter = 'created_at'
        
        # Enhanced date filtering for customers - try multiple date fields  
        base_customers = Customer.objects.all()
        
        customer_filters = [
            Q(created_at__date__gte=start_date, created_at__date__lte=end_date),
            Q(updated_at__date__gte=start_date, updated_at__date__lte=end_date),
        ]
        
        customers = None
        customers_count = 0
        
        # Try each customer filter
        for i, customer_filter in enumerate(customer_filters):
            try:
                filtered_customers = base_customers.filter(customer_filter)
                count = filtered_customers.count()
                
                if count > customers_count:
                    customers = filtered_customers
                    customers_count = count
                    best_customer_filter = ('created_at' if i==0 else 'updated_at')
            except Exception as filter_error:
                continue
        
        # If no specific filter worked, use all customers
        if customers is None or customers_count == 0:
            customers = base_customers
            best_customer_filter = 'created_at'
        
        # Get completed orders
        completed_orders = orders.filter(status='completed')
        
        # Try both payment revenue and order revenue
        payment_revenue = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        order_revenue = completed_orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        
        # Use the higher revenue figure
        total_revenue = max(payment_revenue, order_revenue)
        
    except Exception as e:
        # Return empty data structure if there's an error
        return {
            'total_revenue': 0.0,
            'total_orders': 0,
            'total_customers': 0,
            'daily_breakdown': [],
            'average_daily_revenue': 0.0,
            'average_order_value': 0.0,
            'error': str(e)
        }
    
    # Daily breakdown with timezone-aware filtering
    daily_data = []
    current_date = start_date
    while current_date <= end_date:
        # Create timezone-aware datetime range for the day
        from datetime import datetime
        from django.utils import timezone
        start_datetime = timezone.make_aware(datetime.combine(current_date, datetime.min.time()))
        end_datetime = timezone.make_aware(datetime.combine(current_date, datetime.max.time()))
        
        # Use the same filtering logic as we used for the main payment filtering
        if best_payment_filter[0] == 'completed_at':
            day_revenue = Payment.objects.filter(
                status__in=['completed', 'verified'],
                completed_at__range=[start_datetime, end_datetime]
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        elif best_payment_filter[0] == 'initiated_at':
            day_revenue = Payment.objects.filter(
                status__in=['completed', 'verified'],
                initiated_at__range=[start_datetime, end_datetime]
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        else:
            # Use initiated_at_extra approach
            day_revenue = Payment.objects.filter(
                status__in=['completed', 'verified']
            ).extra(
                where=["DATE(initiated_at) = %s"],
                params=[current_date]
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # For orders, use datetime range instead of __date filter
        day_orders = ServiceOrder.objects.filter(
            created_at__range=[start_datetime, end_datetime]
        ).count()
        
        # For customers, use datetime range instead of __date filter  
        day_customers = Customer.objects.filter(
            created_at__range=[start_datetime, end_datetime]
        ).count()
        
        daily_data.append({
            'date': current_date.strftime('%Y-%m-%d'),
            'day_name': current_date.strftime('%a'),
            'revenue': float(day_revenue),
            'orders': day_orders,
            'new_customers': day_customers
        })
        current_date += timedelta(days=1)
    
    # Use the best filtering results for final totals (should match date range)
    # For consistency with other reports, calculate revenue from service order items
    start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
    end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
    
    total_revenue_from_items = ServiceOrderItem.objects.filter(
        order__created_at__range=[start_datetime, end_datetime],
        order__status='completed'
    ).aggregate(total=Sum('total_price'))['total'] or Decimal('0')
    
    # Use service order item totals for consistency with other reports
    total_revenue = total_revenue_from_items
    
    total_orders = ServiceOrder.objects.filter(
        created_at__range=[start_datetime, end_datetime]
    ).count()
    
    total_customers = Customer.objects.filter(
        created_at__range=[start_datetime, end_datetime]
    ).count()
    
    return {
        'total_revenue': float(total_revenue),
        'total_orders': total_orders,
        'total_customers': total_customers,
        'daily_breakdown': daily_data,
        'average_daily_revenue': float(total_revenue / max(1, (end_date - start_date).days + 1)),
        'average_order_value': float(total_revenue / max(1, total_orders)) if total_orders > 0 else 0
    }


def _generate_financial_overview(start_date, end_date):
    """Generate financial overview report"""
    try:
        # Enhanced date filtering - try multiple date fields for payments
        base_payments = Payment.objects.all().select_related('payment_method')
        
        # Try different date field combinations for payments
        payment_filters = [
            Q(completed_at__date__gte=start_date, completed_at__date__lte=end_date),
            Q(created_at__date__gte=start_date, created_at__date__lte=end_date),
            Q(updated_at__date__gte=start_date, updated_at__date__lte=end_date),
        ]
        
        payments = None
        payments_count = 0
        
        # Try each filter and use the one that returns data
        for i, payment_filter in enumerate(payment_filters):
            try:
                filtered_payments = base_payments.filter(payment_filter)
                count = filtered_payments.count()
                
                if count > payments_count:
                    payments = filtered_payments
                    payments_count = count
            except Exception as filter_error:
                continue
        
        # If no specific filter worked, use all payments
        if payments is None or payments_count == 0:
            payments = base_payments
        
        # Enhanced date filtering for orders
        base_orders = ServiceOrder.objects.all()
        
        order_filters = [
            Q(completed_at__date__gte=start_date, completed_at__date__lte=end_date, status='completed'),
            Q(created_at__date__gte=start_date, created_at__date__lte=end_date, status='completed'),
            Q(updated_at__date__gte=start_date, updated_at__date__lte=end_date, status='completed'),
        ]
        
        completed_orders = None
        orders_count = 0
        
        # Try each order filter
        for i, order_filter in enumerate(order_filters):
            try:
                filtered_orders = base_orders.filter(order_filter)
                count = filtered_orders.count()
                
                if count > orders_count:
                    completed_orders = filtered_orders
                    orders_count = count
            except Exception as filter_error:
                continue
        
        # If no specific filter worked, use all completed orders
        if completed_orders is None or orders_count == 0:
            completed_orders = base_orders.filter(status='completed')
        
        # Get completed payments only for revenue calculation
        completed_payments = payments.filter(status__in=['completed', 'verified'])
        
        # Calculate revenue from both sources
        payment_revenue = completed_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        order_revenue = completed_orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        total_fees = completed_payments.aggregate(total=Sum('processing_fee'))['total'] or Decimal('0')
        
        # Use the higher revenue figure
        total_revenue = max(payment_revenue, order_revenue)
        net_revenue = total_revenue - total_fees
        
        # Payment method breakdown
        try:
            payment_methods = payments.values('payment_method__name').annotate(
                total=Sum('amount'),
                count=Count('id')
            ).order_by('-total')
        except Exception as e:
            payment_methods = []
        
        # Monthly trend - use manual grouping to avoid timezone issues
        monthly_trend = []
        
        # Get payments and group by month manually
        if payments.exists():
            from collections import defaultdict
            grouped_payments = defaultdict(lambda: {'revenue': 0, 'orders': 0})
            
            for payment in payments:
                # Try different date fields
                payment_date = None
                if hasattr(payment, 'completed_at') and payment.completed_at:
                    payment_date = payment.completed_at
                elif payment.created_at:
                    payment_date = payment.created_at
                elif hasattr(payment, 'updated_at') and payment.updated_at:
                    payment_date = payment.updated_at
                
                if payment_date:
                    month_str = payment_date.strftime('%Y-%m')
                    grouped_payments[month_str]['revenue'] += float(payment.amount or 0)
                    grouped_payments[month_str]['orders'] += 1
            
            # Convert to list format, sorted by month
            monthly_trend = [
                {
                    'month': month_str,
                    'revenue': data['revenue'],
                    'orders': data['orders']
                }
                for month_str, data in sorted(grouped_payments.items())
            ]
        
        result = {
            'total_revenue': float(total_revenue),
            'total_fees': float(total_fees),
            'net_revenue': float(net_revenue),
            'payment_methods': [
                {
                    'payment_method__name': item['payment_method__name'],
                    'total': float(item['total']) if item['total'] else 0,
                    'count': item['count']
                }
                for item in payment_methods
            ],
            'monthly_trend': monthly_trend,
            'total_transactions': payments.count()
        }
        
        return result
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            'total_revenue': 0.0,
            'total_fees': 0.0,
            'net_revenue': 0.0,
            'payment_methods': [],
            'monthly_trend': [],
            'total_transactions': 0,
            'error': str(e)
        }


def _generate_customer_analysis(start_date, end_date):
    """Generate customer analysis report"""
    try:
        from apps.services.models import ServiceOrderItem
        
        customers = Customer.objects.filter(is_active=True)
        new_customers = customers.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        
        # Customer spending analysis - use ServiceOrderItem totals for consistency
        customer_spending = customers.annotate(
            period_spent=Sum('service_orders__order_items__total_price', filter=Q(
                service_orders__status='completed',
                service_orders__created_at__date__gte=start_date,
                service_orders__created_at__date__lte=end_date
            )),
            order_count=Count('service_orders', filter=Q(
                service_orders__created_at__date__gte=start_date,
                service_orders__created_at__date__lte=end_date
            ))
        ).filter(period_spent__gt=0).order_by('-period_spent')
        
    except Exception as e:
        return {
            'total_customers': 0,
            'new_customers': 0,
            'active_customers': 0,
            'returning_customers': 0,
            'retention_rate': 0.0,
            'growth_rate': 0.0,
            'avg_customer_value': 0.0,
            'average_customer_value': 0.0,
            'avg_orders_per_customer': 0.0,
            'avg_visit_frequency': 0.0,
            'customer_segments': {},
            'customer_types': [],
            'customer_locations': [],
            'top_customers': [],
            'error': str(e)
        }
    
    # Customer types
    customer_types = customers.values('customer_type').annotate(
        count=Count('id'),
        revenue=Sum('payments__amount', filter=Q(
            payments__status__in=['completed', 'verified'],
            payments__completed_at__date__gte=start_date,
            payments__completed_at__date__lte=end_date
        ))
    )
    
    # Top customers
    top_customers = customer_spending[:10]
    
    # Customer segments analysis
    customer_segments = {
        'new_customers': new_customers.count(),
        'returning_customers': customers.exclude(
            id__in=new_customers.values_list('id', flat=True)
        ).count(),
        'vip_customers': customers.filter(is_vip=True).count(),
        'one_time_customers': customers.annotate(
            order_count=Count('service_orders')
        ).filter(order_count=1).count()
    }
    
    # Calculate additional metrics
    total_customers_count = customers.count()
    new_customers_count = new_customers.count()
    returning_customers_count = customer_segments['returning_customers']
    retention_rate = (customer_spending.count() / max(1, total_customers_count)) * 100 if total_customers_count > 0 else 0
    
    # Growth rate calculation (percentage of new customers)
    growth_rate = (new_customers_count / max(1, total_customers_count)) * 100 if total_customers_count > 0 else 0
    
    # Average customer value
    avg_customer_value = customer_spending.aggregate(avg=Avg('period_spent'))['avg'] or 0
    
    # Average orders per customer
    avg_orders_per_customer = customer_spending.aggregate(avg=Avg('order_count'))['avg'] or 0
    
    # Average visit frequency (orders per month)
    months_in_period = max(1, (end_date - start_date).days / 30)
    avg_visit_frequency = avg_orders_per_customer / months_in_period if avg_orders_per_customer > 0 else 0
    
    # Geographic analysis if location data exists - use service order item totals for consistency
    customer_locations = customers.values('city', 'state').annotate(
        count=Count('id'),
        revenue=Sum('service_orders__order_items__total_price', filter=Q(
            service_orders__status='completed',
            service_orders__created_at__date__gte=start_date,
            service_orders__created_at__date__lte=end_date
        ))
    ).filter(count__gt=0).order_by('-count')

    return {
        'total_customers': customers.count(),
        'new_customers': new_customers.count(),
        'active_customers': customer_spending.count(),
        'returning_customers': returning_customers_count,
        'retention_rate': float(retention_rate),
        'growth_rate': float(growth_rate),
        'avg_customer_value': float(avg_customer_value),
        'average_customer_value': float(avg_customer_value),  # Keep both names for compatibility
        'avg_orders_per_customer': float(avg_orders_per_customer),
        'avg_visit_frequency': float(avg_visit_frequency),
        'customer_segments': customer_segments,
        'customer_types': [
            {
                'customer_type': item['customer_type'],
                'count': item['count'],
                'revenue': float(item['revenue']) if item['revenue'] else 0
            }
            for item in customer_types
        ],
        'customer_locations': [
            {
                'city': item['city'] or 'Unknown',
                'state': item['state'] or 'Unknown',
                'count': item['count'],
                'revenue': float(item['revenue']) if item['revenue'] else 0
            }
            for item in customer_locations[:10]
        ],
        'top_customers': [
            {
                'name': customer.display_name,
                'customer_id': customer.customer_id,
                'period_spent': float(customer.period_spent or 0),
                'order_count': getattr(customer, 'order_count', 0) or 0,
                'is_vip': customer.is_vip,
                'customer_type': customer.customer_type,
                'last_visit': customer.updated_at.strftime('%Y-%m-%d') if customer.updated_at else 'Unknown'
            }
            for customer in top_customers
        ]
    }


def _generate_service_performance(start_date, end_date):
    """Generate service performance report"""
    try:
        # Get all active services with proper annotations
        services = Service.objects.filter(is_active=True).annotate(
            orders_count=Count('order_items', filter=Q(
                order_items__order__created_at__date__gte=start_date,
                order_items__order__created_at__date__lte=end_date
            )),
            revenue=Sum('order_items__total_price', filter=Q(
                order_items__order__created_at__date__gte=start_date,
                order_items__order__created_at__date__lte=end_date,
                order_items__order__status='completed'
            )),
            total_quantity=Sum('order_items__quantity', filter=Q(
                order_items__order__created_at__date__gte=start_date,
                order_items__order__created_at__date__lte=end_date
            ))
        ).order_by('-orders_count')
        
        # Get order statistics using timezone-aware datetime ranges
        start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
        end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
        
        all_orders = ServiceOrder.objects.filter(
            created_at__gte=start_datetime,
            created_at__lte=end_datetime
        )
        
        total_orders = all_orders.count()
        completed_orders_queryset = all_orders.filter(status='completed')
        completed_orders = completed_orders_queryset.count()
        
        # Get distinct services that have been ordered
        services_with_orders = services.filter(orders_count__gt=0)
        
        # Check service order items directly
        from apps.services.models import ServiceOrderItem
        service_items_in_period = ServiceOrderItem.objects.filter(
            order__created_at__gte=start_datetime,
            order__created_at__lte=end_datetime
        )
        
        # Get services with enhanced statistics
        services_with_stats = Service.objects.annotate(
            # Count service order items for this service in the date range
            items_count=Count('order_items', filter=Q(
                order_items__order__created_at__gte=start_datetime,
                order_items__order__created_at__lte=end_datetime
            )),
            # Sum quantity of service items
            total_quantity=Sum('order_items__quantity', filter=Q(
                order_items__order__created_at__gte=start_datetime,
                order_items__order__created_at__lte=end_datetime
            )),
            # Calculate revenue from service items using total_price
            total_revenue=Sum('order_items__total_price', filter=Q(
                order_items__order__created_at__gte=start_datetime,
                order_items__order__created_at__lte=end_datetime,
                order_items__order__status='completed'
            )),
            # Count unique orders that included this service
            unique_orders=Count('order_items__order', distinct=True, filter=Q(
                order_items__order__created_at__gte=start_datetime,
                order_items__order__created_at__lte=end_datetime
            ))
        ).filter(items_count__gt=0).order_by('-total_revenue')
        
        # Get category performance
        from apps.services.models import ServiceCategory
        category_performance = ServiceCategory.objects.annotate(
            # Count services in this category that were ordered
            services_ordered=Count('services__order_items__order', distinct=True, filter=Q(
                services__order_items__order__created_at__gte=start_datetime,
                services__order_items__order__created_at__lte=end_datetime
            )),
            # Sum revenue for this category using total_price
            category_revenue=Sum('services__order_items__total_price', filter=Q(
                services__order_items__order__created_at__gte=start_datetime,
                services__order_items__order__created_at__lte=end_datetime,
                services__order_items__order__status='completed'
            )),
            # Count total service items in this category
            total_items=Count('services__order_items', filter=Q(
                services__order_items__order__created_at__gte=start_datetime,
                services__order_items__order__created_at__lte=end_datetime
            ))
        ).filter(total_items__gt=0).order_by('-category_revenue')
        
        # Calculate total revenue consistently from service items (not orders)
        total_revenue_from_items = ServiceOrderItem.objects.filter(
            order__created_at__gte=start_datetime,
            order__created_at__lte=end_datetime,
            order__status='completed'
        ).aggregate(
            total=Sum('total_price')
        )['total'] or 0
        
        # For comparison, also calculate from completed orders
        total_revenue_from_orders = completed_orders_queryset.aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        
        # Use service items total for consistency with individual service calculations
        total_revenue = total_revenue_from_items
        
        # Calculate average order value
        avg_order_value = total_revenue / max(1, completed_orders)
        
        # Get top performing services (top 10)
        top_services = services_with_stats[:10]
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            'total_orders': 0,
            'completed_orders': 0,
            'completion_rate': 0,
            'total_revenue': 0,
            'avg_order_value': 0,
            'services': [],
            'categories': [],
            'service_items_count': 0,
            'error': str(e)
        }

    return {
        'total_orders': total_orders,
        'completed_orders': completed_orders,
        'completion_rate': (completed_orders / max(1, total_orders)) * 100,
        'total_revenue': float(total_revenue),
        'avg_order_value': float(avg_order_value),
        'service_items_count': service_items_in_period.count(),
        'services': [
            {
                'id': str(service.id),
                'name': service.name,
                'description': service.description,
                'base_price': float(service.base_price),
                'category': service.category.name if service.category else 'Uncategorized',
                'category_id': str(service.category.id) if service.category else None,
                'items_count': service.items_count or 0,
                'total_quantity': service.total_quantity or 0,
                'total_revenue': float(service.total_revenue or 0),
                'unique_orders': service.unique_orders or 0,
                'avg_price_per_item': float(service.total_revenue or 0) / max(1, service.total_quantity or 1),
                'is_active': service.is_active,
                'duration_minutes': service.duration_minutes if hasattr(service, 'duration_minutes') else None
            }
            for service in top_services
        ],
        'categories': [
            {
                'id': str(category.id),
                'name': category.name,
                'description': category.description if hasattr(category, 'description') else '',
                'services_ordered': category.services_ordered or 0,
                'category_revenue': float(category.category_revenue or 0),
                'total_items': category.total_items or 0,
                'avg_revenue_per_service': float(category.category_revenue or 0) / max(1, category.services_ordered or 1)
            }
            for category in category_performance
        ]
    }


def _generate_payment_summary_new(start_date, end_date):
    """Generate comprehensive payment summary report"""
    try:
        from datetime import datetime
        from django.utils import timezone
        from django.db.models import Sum, Count, Avg, Q
        from decimal import Decimal
        
        # Create timezone-aware datetime ranges
        start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
        end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
        
        # Get payments in the date range (prioritize completed_at, fallback to created_at)
        payments = Payment.objects.filter(
            Q(completed_at__gte=start_datetime, completed_at__lte=end_datetime) |
            Q(completed_at__isnull=True, created_at__gte=start_datetime, created_at__lte=end_datetime)
        )
        
        # Basic counts and amounts
        total_count = payments.count()
        total_amount = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Status-based breakdowns
        completed_payments = payments.filter(status__in=['completed', 'verified'])
        pending_payments = payments.filter(status='pending')
        failed_payments = payments.filter(status='failed')
        
        completed_count = completed_payments.count()
        completed_amount = completed_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        pending_count = pending_payments.count()
        pending_amount = pending_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        failed_count = failed_payments.count()
        failed_amount = failed_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Payment methods breakdown with enhanced data
        payment_methods_raw = payments.values('payment_method__name').annotate(
            count=Count('id'),
            amount=Sum('amount')
        ).order_by('-amount')
        
        # Process payment methods with colors and percentages
        colors = ['#007bff', '#28a745', '#ffc107', '#dc3545', '#6c757d', '#17a2b8', '#fd7e14', '#6f42c1']
        payment_methods_processed = []
        
        for i, item in enumerate(payment_methods_raw):
            method_amount = float(item['amount'] or 0)
            payment_methods_processed.append({
                'name': item['payment_method__name'] or 'Unknown',
                'count': item['count'],
                'amount': method_amount,
                'color': colors[i % len(colors)],
                'percentage': round((method_amount / float(total_amount) * 100), 1) if total_amount > 0 else 0
            })
        
        # Daily trend analysis
        daily_payments = []
        from collections import defaultdict
        grouped_payments = defaultdict(lambda: {'count': 0, 'amount': Decimal('0')})
        
        for payment in completed_payments:
            payment_date = payment.completed_at or payment.created_at
            if payment_date:
                date_str = payment_date.date().strftime('%Y-%m-%d')
                grouped_payments[date_str]['count'] += 1
                grouped_payments[date_str]['amount'] += payment.amount or Decimal('0')
        
        daily_payments = [
            {
                'date': date_str,
                'count': data['count'],
                'amount': float(data['amount'])
            }
            for date_str, data in sorted(grouped_payments.items())
        ]
        
        # Calculate metrics
        success_rate = (completed_count / total_count * 100) if total_count > 0 else 0
        avg_payment = float(total_amount / total_count) if total_count > 0 else 0
        daily_avg = completed_count / len(daily_payments) if daily_payments else 0
        
        # Recent payments for display
        recent_payments = payments.order_by('-created_at')[:10]
        payment_list = []
        for payment in recent_payments:
            payment_list.append({
                'id': str(payment.id),
                'amount': float(payment.amount),
                'status': payment.status,
                'payment_method': payment.payment_method.name if payment.payment_method else 'Unknown',
                'created_at': payment.created_at.strftime('%Y-%m-%d %H:%M') if payment.created_at else '',
                'reference_number': payment.reference_number or '',
                'customer_phone': payment.customer_phone or ''
            })
        
        result = {
            # Basic metrics
            'total_count': total_count,
            'total_amount': float(total_amount),
            'completed_count': completed_count,
            'completed_amount': float(completed_amount),
            'pending_count': pending_count,
            'pending_amount': float(pending_amount),
            'failed_count': failed_count,
            'failed_amount': float(failed_amount),
            
            # Calculated metrics
            'success_rate': round(success_rate, 1),
            'avg_payment': round(avg_payment, 2),
            'daily_avg': round(daily_avg, 1),
            
            # Detailed data
            'payment_methods': payment_methods_processed,
            'daily_data': daily_payments,
            'payments': payment_list,
            
            # Status breakdown for charts
            'status_breakdown': [
                {'status': 'completed', 'count': completed_count, 'amount': float(completed_amount)},
                {'status': 'pending', 'count': pending_count, 'amount': float(pending_amount)},
                {'status': 'failed', 'count': failed_count, 'amount': float(failed_amount)},
            ],
            
            # Legacy fields for compatibility
            'total_payments': total_count,
            'successful_payments': completed_count,
            'failed_payments': failed_count,
            'pending_payments': pending_count,
            'daily_trend': daily_payments
        }
        
        return result
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            'total_count': 0,
            'total_amount': 0,
            'completed_count': 0,
            'completed_amount': 0,
            'pending_count': 0,
            'pending_amount': 0,
            'failed_count': 0,
            'failed_amount': 0,
            'success_rate': 0,
            'avg_payment': 0,
            'daily_avg': 0,
            'payment_methods': [],
            'daily_data': [],
            'payments': [],
            'status_breakdown': [],
            'error': str(e)
        }


def _generate_employee_performance(start_date, end_date):
    """Generate employee performance report"""
    try:
        # Create timezone-aware datetime ranges
        start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
        end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
        
        # Deduplicate by user to avoid ambiguous data - keep the most recent employee record per user
        from django.db.models import Max
        # Get the latest employee record per user_id to avoid duplicates
        latest_employee_per_user = Employee.objects.filter(is_active=True).values('user_id').annotate(
            latest_id=Max('id')
        ).values_list('latest_id', flat=True)
        
        # Get deduplicated employees FIRST, then calculate annotations
        employees = Employee.objects.filter(id__in=latest_employee_per_user).annotate(
            # Count orders assigned to this employee IN THE PERIOD - using distinct to avoid duplicates
            orders_handled=Count('assigned_orders__id', filter=Q(
                assigned_orders__created_at__gte=start_datetime,
                assigned_orders__created_at__lte=end_datetime
            ), distinct=True),
            # Count service items they worked on directly IN THE PERIOD - using distinct
            service_items_handled=Count('service_items__id', filter=Q(
                service_items__order__created_at__gte=start_datetime,
                service_items__order__created_at__lte=end_datetime
            ), distinct=True),
        )
        
        # Calculate revenue and commission separately to avoid JOIN issues
        for employee in employees:
            # Calculate revenue from assigned orders
            employee_revenue = employee.assigned_orders.filter(
                created_at__gte=start_datetime,
                created_at__lte=end_datetime,
                status='completed'
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            
            # Calculate commission from service items
            employee_commission = employee.service_items.filter(
                order__created_at__gte=start_datetime,
                order__created_at__lte=end_datetime,
                completed_at__isnull=False
            ).aggregate(total=Sum('commission_amount'))['total'] or 0
            
            # Attach to employee object
            employee.revenue_generated = employee_revenue
            employee.commission_earned = employee_commission
        
        # Filter to only employees with some activity
        active_employees = [emp for emp in employees if emp.orders_handled > 0 or emp.service_items_handled > 0]
        
        # Sort by revenue (Python sorting since revenue is not a DB field anymore)
        active_employees.sort(key=lambda emp: emp.revenue_generated or 0, reverse=True)
        
        # Check all orders to see if any have assigned attendants
        all_orders = ServiceOrder.objects.filter(
            created_at__gte=start_datetime,
            created_at__lte=end_datetime
        )
        orders_with_attendants = all_orders.exclude(assigned_attendant__isnull=True)
        
        # DEBUG: Detailed analysis of the counting issue
        print(f"DEBUG: Total orders in period: {all_orders.count()}")
        
        # Check how many orders actually have assigned attendants
        orders_with_assigned = all_orders.filter(assigned_attendant__isnull=False)
        print(f"DEBUG: Orders with assigned attendants: {orders_with_assigned.count()}")
        
        # Check for all active employee records
        all_active_employees = Employee.objects.filter(is_active=True)
        print(f"DEBUG: Total active employee records: {all_active_employees.count()}")
        
        # Check for duplicate user_ids
        from django.db.models import Count as DjangoCount
        duplicate_user_ids = all_active_employees.values('user_id').annotate(
            count=DjangoCount('id')
        ).filter(count__gt=1)
        
        print(f"DEBUG: Duplicate user_ids found: {duplicate_user_ids.count()}")
        for dup in duplicate_user_ids:
            user_id = dup['user_id']
            count = dup['count']
            print(f"  user_id {user_id} has {count} employee records")
            
            # Show details of duplicate records
            dupes = all_active_employees.filter(user_id=user_id)
            for emp in dupes:
                orders_count = emp.assigned_orders.filter(
                    created_at__gte=start_datetime,
                    created_at__lte=end_datetime
                ).count()
                print(f"    ID={emp.id}, user_id={emp.user_id}, orders={orders_count}")
        
        # Check the actual deduplication list
        dedup_ids = list(latest_employee_per_user)
        print(f"DEBUG: Deduplicated employee IDs: {dedup_ids}")
        
        # Check each employee's assigned orders after deduplication
        total_employee_orders = sum([emp.orders_handled for emp in active_employees])
        print(f"DEBUG: Total employee orders handled (sum after fix): {total_employee_orders}")
        
        print("DEBUG: Individual employee breakdown:")
        for emp in active_employees:
            # Check actual orders assigned to this employee
            actual_orders = emp.assigned_orders.filter(
                created_at__gte=start_datetime,
                created_at__lte=end_datetime
            )
            actual_count = actual_orders.count()
            
            print(f"  Employee ID {emp.id} (user_id: {emp.user_id}):")
            print(f"    Annotated orders_handled: {emp.orders_handled}")
            print(f"    Actual assigned orders: {actual_count}")
            
            # Show the actual order IDs
            order_ids = list(actual_orders.values_list('id', flat=True))
            print(f"    Order IDs: {order_ids}")
            
            # Check actual revenue for this employee
            actual_revenue = actual_orders.filter(status='completed').aggregate(
                total=Sum('total_amount')
            )['total'] or 0
            
            print(f"    Annotated revenue_generated: KES {emp.revenue_generated or 0}")
            print(f"    Actual revenue from completed orders: KES {actual_revenue}")
            
            if emp.orders_handled != actual_count:
                print(f"    ⚠️  ORDER MISMATCH: Annotation={emp.orders_handled}, Actual={actual_count}")
            
            if abs((emp.revenue_generated or 0) - actual_revenue) > 0.01:
                print(f"    ⚠️  REVENUE MISMATCH: Annotation=KES {emp.revenue_generated or 0}, Actual=KES {actual_revenue}")
        
        # Let's also check if there are any orders assigned to the same employee multiple times
        print("\nDEBUG: Checking for orders assigned to multiple employees:")
        orders_with_multiple_assignments = all_orders.filter(
            assigned_attendant__isnull=False
        ).annotate(
            assignment_count=Count('assigned_attendant')
        ).filter(assignment_count__gt=1)
        
        print(f"Orders with multiple assignments: {orders_with_multiple_assignments.count()}")
        
        # Check the actual assignment distribution
        assignment_distribution = {}
        for order in all_orders.filter(assigned_attendant__isnull=False):
            emp_id = order.assigned_attendant.id
            if emp_id not in assignment_distribution:
                assignment_distribution[emp_id] = []
            assignment_distribution[emp_id].append(order.id)
        
        print("DEBUG: Assignment distribution:")
        for emp_id, order_ids in assignment_distribution.items():
            print(f"  Employee {emp_id}: {len(order_ids)} orders {order_ids}")
            
        total_assignments = sum(len(orders) for orders in assignment_distribution.values())
        print(f"DEBUG: Total assignments across all employees: {total_assignments}")
        
        # Check service items
        from apps.services.models import ServiceOrderItem
        service_items = ServiceOrderItem.objects.filter(
            order__created_at__gte=start_datetime,
            order__created_at__lte=end_datetime
        )
        service_items_with_assignment = service_items.exclude(assigned_to__isnull=True)
        
        # If no employees have activity, return all employees with zero values
        if len(active_employees) == 0:
            active_employees = list(employees[:10])  # Return first 10 employees
        
        return {
            'total_employees': Employee.objects.filter(is_active=True).count(),
            'active_employees': len(active_employees),
            'total_orders_in_period': all_orders.count(),
            'orders_with_attendants': orders_with_attendants.count(),
            'service_items_in_period': service_items.count(),
            'service_items_with_assignment': service_items_with_assignment.count(),
            'employees': [
                {
                    'name': getattr(emp, 'full_name', f"Employee {emp.employee_id}"),
                    'employee_id': emp.employee_id,
                    'user_id': str(emp.user_id) if emp.user_id else None,
                    'email': getattr(emp, 'email', None),
                    'role': emp.get_role_display(),
                    'department': emp.department.name if emp.department else 'No Department',
                    'orders_handled': emp.orders_handled or 0,
                    'service_items_handled': emp.service_items_handled or 0,
                    'revenue_generated': float(emp.revenue_generated or 0),
                    'commission_earned': float(emp.commission_earned or 0),
                    'avg_revenue_per_order': float(emp.revenue_generated or 0) / max(1, emp.orders_handled or 1),
                    'productivity_score': min(100, ((emp.service_items_handled or 0) * 10) + ((emp.orders_handled or 0) * 5)),
                    'is_primary_record': True  # Since we're now using latest record per user
                }
                for emp in active_employees[:15]
            ]
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            'total_employees': 0,
            'active_employees': 0,
            'employees': [],
            'error': str(e)
        }


def _generate_weekly_summary(start_date, end_date):
    """Generate weekly business summary"""
    return _generate_daily_summary(start_date, end_date)


def _generate_monthly_summary(start_date, end_date):
    """Generate monthly business summary"""
    return _generate_daily_summary(start_date, end_date)


@login_required
@business_required
def report_detail(request, report_id):
    """View a specific report with specialized templates"""
    report = get_object_or_404(BusinessReport, id=report_id)
    
    # Get report data from JSONField
    report_data = report.report_data if report.report_data else {}
    
    # Determine template based on report type
    template_mapping = {
        'employee_performance': 'reports/employee_performance_detail.html',
        'service_performance': 'reports/service_performance_detail.html', 
        'payment_summary': 'reports/payment_summary_new.html',
        'customer_analysis': 'reports/customer_analysis_detail.html',
    }
    
    template_name = template_mapping.get(report.report_type, 'reports/report_detail.html')
    
    context = {
        'report': report,
        'report_data': report_data
    }
    
    return render(request, template_name, context)


@login_required
@business_required
def reports_list(request):
    """List all generated reports with enhanced filtering"""
    reports = BusinessReport.objects.filter(status='completed').order_by('-created_at')
    
    # Filter by type if specified
    report_type = request.GET.get('type')
    if report_type:
        reports = reports.filter(report_type=report_type)
    
    # Filter by date range if specified
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
            reports = reports.filter(created_at__date__gte=from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
            reports = reports.filter(created_at__date__lte=to_date)
        except ValueError:
            pass
    
    # Pagination with increased items per page for grid layout
    paginator = Paginator(reports, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'report_types': BusinessReport.REPORT_TYPES,
        'current_type': report_type
    }
    return render(request, 'reports/reports_list.html', context)


@login_required
@business_required
@employee_required(['owner', 'manager'])
def analytics_dashboard(request):
    """Enhanced analytics dashboard with real-time insights"""
    from decimal import Decimal
    import json
    
    # Get date range (default to last 30 days)
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    # Get date range from request if provided
    date_range = request.GET.get('date_range', '30')
    if date_range == '7':
        start_date = end_date - timedelta(days=7)
    elif date_range == '90':
        start_date = end_date - timedelta(days=90)
    elif date_range == '365':
        start_date = end_date - timedelta(days=365)
    
    # Generate comprehensive analytics data
    analytics_data = _generate_daily_summary(start_date, end_date)
    financial_data = _generate_financial_overview(start_date, end_date)
    customer_data = _generate_customer_analysis(start_date, end_date)
    service_data = _generate_service_performance(start_date, end_date)
    
    # Calculate growth rates (compare with previous period)
    period_length = (end_date - start_date).days
    prev_start = start_date - timedelta(days=period_length)
    prev_end = start_date - timedelta(days=1)
    
    prev_analytics = _generate_daily_summary(prev_start, prev_end)
    
    revenue_growth = 0
    if prev_analytics['total_revenue'] > 0:
        revenue_growth = ((analytics_data['total_revenue'] - prev_analytics['total_revenue']) / prev_analytics['total_revenue']) * 100
    
    customer_growth = 0
    if prev_analytics['total_customers'] > 0:
        customer_growth = ((analytics_data['total_customers'] - prev_analytics['total_customers']) / prev_analytics['total_customers']) * 100
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'date_range': date_range,
        'period_length': period_length,
        
        # Combined data
        'total_revenue': analytics_data['total_revenue'],
        'total_orders': analytics_data['total_orders'],
        'new_customers': analytics_data['total_customers'],
        'total_customers': customer_data['total_customers'],
        'avg_order_value': analytics_data['average_order_value'],
        'completion_rate': service_data['completion_rate'],
        
        # Growth indicators
        'revenue_growth': revenue_growth,
        'customer_growth': customer_growth,
        'order_growth': 0,  # Can be calculated if needed
        
        # Chart data
        'daily_revenue': analytics_data['daily_breakdown'],
        'revenue_by_method': financial_data['payment_methods'],
        'monthly_revenue': financial_data['monthly_trend'],
        'customer_acquisition_by_day': analytics_data['daily_breakdown'],  # Reuse for customer chart
        'top_customers': customer_data['top_customers'],
        'service_performance': service_data['services'][:10],
        
        # Indicators
        'has_data': analytics_data['total_revenue'] > 0 or analytics_data['total_orders'] > 0 or customer_data['total_customers'] > 0,
    }
    
    return render(request, 'reports/analytics_dashboard.html', context)


@login_required
@business_required
def export_report(request, report_id, format_type):
    """Export report in different formats"""
    from django.template.loader import render_to_string
    from django.conf import settings
    import tempfile
    import os
    from datetime import datetime
    from django.utils import timezone
    
    report = get_object_or_404(BusinessReport, id=report_id)
    
    if format_type == 'pdf':
        try:
            # Get the report data
            if report.report_type == 'payment_summary':
                report_data = _generate_payment_summary_new(report.start_date, report.end_date)
            elif report.report_type == 'financial_overview':
                report_data = _generate_financial_overview(report.start_date, report.end_date)
            elif report.report_type == 'employee_performance':
                report_data = _generate_employee_performance(report.start_date, report.end_date)
            else:
                # Default to daily summary
                report_data = _generate_daily_summary(report.start_date, report.end_date)
            
            # Prepare context for PDF template
            context = {
                'report': report,
                'report_data': report_data,
                'business_name': request.tenant.name or 'AutoWash Business',
                'business_address': getattr(request.tenant, 'address_line_1', ''),
                'business_phone': getattr(request.tenant, 'phone', ''),
                'business_email': getattr(request.tenant, 'email', ''),
                'start_date': report.start_date,
                'end_date': report.end_date,
                'current_date': timezone.now(),
            }
            
            # Select appropriate template based on report type
            if report.report_type == 'payment_summary':
                template_name = 'reports/payment_summary_pdf.html'
            else:
                # For other reports, use a generic PDF template (to be created)
                template_name = 'reports/generic_report_pdf.html'
            
            # Render HTML
            html_string = render_to_string(template_name, context, request=request)
            
            # Create PDF using ReportLab (more reliable on Windows)
            try:
                from reportlab.lib.pagesizes import letter, A4
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.lib.units import inch
                from reportlab.lib import colors
                from io import BytesIO
                
                # Create PDF with ReportLab
                buffer = BytesIO()
                doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*inch)
                
                # Styles
                styles = getSampleStyleSheet()
                title_style = ParagraphStyle(
                    'CustomTitle',
                    parent=styles['Heading1'],
                    fontSize=18,
                    spaceAfter=30,
                    alignment=1,  # Center
                    textColor=colors.HexColor('#007bff')
                )
                
                # Build PDF content
                story = []
                
                # Title
                story.append(Paragraph(f"{context['business_name']}", title_style))
                story.append(Paragraph(f"Payment Summary Report", styles['Heading2']))
                story.append(Paragraph(f"Period: {report.start_date} to {report.end_date}", styles['Normal']))
                story.append(Spacer(1, 20))
                
                # Summary data
                if report.report_type == 'payment_summary':
                    summary_data = [
                        ['Metric', 'Value'],
                        ['Total Amount', f"KES {report_data.get('total_amount', 0):,.2f}"],
                        ['Total Transactions', str(report_data.get('total_count', 0))],
                        ['Successful Payments', f"KES {report_data.get('completed_amount', 0):,.2f}"],
                        ['Success Rate', f"{report_data.get('success_rate', 0)}%"],
                        ['Average Payment', f"KES {report_data.get('avg_payment', 0):,.2f}"],
                    ]
                    
                    # Create table
                    table = Table(summary_data, colWidths=[3*inch, 3*inch])
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#007bff')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 12),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black)
                    ]))
                    
                    story.append(table)
                    story.append(Spacer(1, 20))
                    
                    # Payment methods breakdown
                    if report_data.get('payment_methods'):
                        story.append(Paragraph("Payment Methods Breakdown", styles['Heading3']))
                        
                        method_data = [['Payment Method', 'Count', 'Amount', 'Percentage']]
                        for method in report_data['payment_methods']:
                            method_data.append([
                                method['name'],
                                str(method['count']),
                                f"KES {method['amount']:,.2f}",
                                f"{method.get('percentage', 0)}%"
                            ])
                        
                        method_table = Table(method_data, colWidths=[2*inch, 1*inch, 2*inch, 1*inch])
                        method_table.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#28a745')),
                            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                            ('FONTSIZE', (0, 0), (-1, 0), 10),
                            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                            ('GRID', (0, 0), (-1, -1), 1, colors.black)
                        ]))
                        
                        story.append(method_table)
                
                # Footer
                story.append(Spacer(1, 50))
                story.append(Paragraph(f"Generated on {timezone.now().strftime('%B %d, %Y at %I:%M %p')}", styles['Normal']))
                story.append(Paragraph("Confidential Business Document", styles['Italic']))
                
                # Build PDF
                doc.build(story)
                
                # Return response
                pdf_data = buffer.getvalue()
                buffer.close()
                
                response = HttpResponse(pdf_data, content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="{report.title}_{report.start_date}_{report.end_date}.pdf"'
                return response
                
            except Exception as pdf_error:
                # If ReportLab also fails, return error
                messages.error(request, f'Error generating PDF with ReportLab: {str(pdf_error)}')
                return redirect(f'/business/{request.tenant.slug}/reports/detail/{report_id}/')
        
        except Exception as e:
            # If PDF generation fails, return an error message
            messages.error(request, f'Error generating PDF: {str(e)}')
            return redirect(f'/business/{request.tenant.slug}/reports/detail/{report_id}/')
    
    elif format_type == 'excel':
        # Generate Excel using openpyxl
        try:
            import openpyxl
            from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
            from openpyxl.utils import get_column_letter
            
            # Create workbook
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Payment Summary"
            
            # Get report data
            if report.report_type == 'payment_summary':
                report_data = _generate_payment_summary_new(report.start_date, report.end_date)
            else:
                report_data = _generate_daily_summary(report.start_date, report.end_date)
            
            # Styles
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="007bff", end_color="007bff", fill_type="solid")
            border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                          top=Side(style='thin'), bottom=Side(style='thin'))
            
            # Title and headers
            ws.merge_cells('A1:F1')
            ws['A1'] = f"{request.tenant.name} - Payment Summary Report"
            ws['A1'].font = Font(bold=True, size=16)
            ws['A1'].alignment = Alignment(horizontal='center')
            
            ws.merge_cells('A2:F2')
            ws['A2'] = f"Period: {report.start_date} to {report.end_date}"
            ws['A2'].alignment = Alignment(horizontal='center')
            
            # Summary section
            row = 4
            ws[f'A{row}'] = "SUMMARY METRICS"
            ws[f'A{row}'].font = header_font
            ws[f'A{row}'].fill = header_fill
            ws.merge_cells(f'A{row}:B{row}')
            
            row += 1
            summary_items = [
                ('Total Amount', f"KES {report_data.get('total_amount', 0):,.2f}"),
                ('Total Transactions', str(report_data.get('total_count', 0))),
                ('Successful Amount', f"KES {report_data.get('completed_amount', 0):,.2f}"),
                ('Success Rate', f"{report_data.get('success_rate', 0)}%"),
                ('Average Payment', f"KES {report_data.get('avg_payment', 0):,.2f}"),
            ]
            
            for item, value in summary_items:
                ws[f'A{row}'] = item
                ws[f'B{row}'] = value
                ws[f'A{row}'].border = border
                ws[f'B{row}'].border = border
                row += 1
            
            # Payment methods section
            if report_data.get('payment_methods'):
                row += 2
                ws[f'A{row}'] = "PAYMENT METHODS"
                ws[f'A{row}'].font = header_font
                ws[f'A{row}'].fill = header_fill
                ws.merge_cells(f'A{row}:D{row}')
                
                row += 1
                headers = ['Payment Method', 'Count', 'Amount', 'Percentage']
                for col, header in enumerate(headers, 1):
                    cell = ws.cell(row=row, column=col, value=header)
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.border = border
                
                row += 1
                for method in report_data['payment_methods']:
                    ws[f'A{row}'] = method['name']
                    ws[f'B{row}'] = method['count']
                    ws[f'C{row}'] = f"KES {method['amount']:,.2f}"
                    ws[f'D{row}'] = f"{method.get('percentage', 0)}%"
                    
                    for col in range(1, 5):
                        ws.cell(row=row, column=col).border = border
                    row += 1
            
            # Auto-adjust column widths
            for column_cells in ws.columns:
                length = max(len(str(cell.value or "")) for cell in column_cells)
                ws.column_dimensions[get_column_letter(column_cells[0].column)].width = length + 2
            
            # Save to response
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename="{report.title}_{report.start_date}_{report.end_date}.xlsx"'
            wb.save(response)
            return response
            
        except ImportError:
            messages.error(request, 'Excel export not available. Please install openpyxl.')
            return redirect(f'/business/{request.tenant.slug}/reports/detail/{report_id}/')
        except Exception as e:
            messages.error(request, f'Error generating Excel: {str(e)}')
            return redirect(f'/business/{request.tenant.slug}/reports/detail/{report_id}/')
    
    elif format_type == 'csv':
        # Generate CSV
        import csv
        from django.http import HttpResponse
        
        try:
            if report.report_type == 'payment_summary':
                report_data = _generate_payment_summary_new(report.start_date, report.end_date)
            else:
                report_data = _generate_daily_summary(report.start_date, report.end_date)
            
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{report.title}_{report.start_date}_{report.end_date}.csv"'
            
            writer = csv.writer(response)
            
            # Header
            writer.writerow([f"{request.tenant.name} - Payment Summary Report"])
            writer.writerow([f"Period: {report.start_date} to {report.end_date}"])
            writer.writerow([])
            
            # Summary
            writer.writerow(['SUMMARY METRICS'])
            writer.writerow(['Metric', 'Value'])
            writer.writerow(['Total Amount', f"KES {report_data.get('total_amount', 0):,.2f}"])
            writer.writerow(['Total Transactions', str(report_data.get('total_count', 0))])
            writer.writerow(['Successful Amount', f"KES {report_data.get('completed_amount', 0):,.2f}"])
            writer.writerow(['Success Rate', f"{report_data.get('success_rate', 0)}%"])
            writer.writerow(['Average Payment', f"KES {report_data.get('avg_payment', 0):,.2f}"])
            writer.writerow([])
            
            # Payment methods
            if report_data.get('payment_methods'):
                writer.writerow(['PAYMENT METHODS'])
                writer.writerow(['Payment Method', 'Count', 'Amount', 'Percentage'])
                for method in report_data['payment_methods']:
                    writer.writerow([
                        method['name'],
                        method['count'],
                        f"KES {method['amount']:,.2f}",
                        f"{method.get('percentage', 0)}%"
                    ])
            
            return response
            
        except Exception as e:
            messages.error(request, f'Error generating CSV: {str(e)}')
            return redirect(f'/business/{request.tenant.slug}/reports/detail/{report_id}/')
    
    return redirect(f'/business/{request.tenant.slug}/reports/detail/{report_id}/')