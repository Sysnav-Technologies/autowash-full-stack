
import csv
import io
import logging
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta
from functools import wraps
import qrcode
import base64
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_protect
from django.db import transaction, models
from django.db.models import Q, Count, Sum, Avg, F, Case, When, Value, IntegerField, Prefetch
from django.utils import timezone
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.urls import reverse
from apps.core.decorators import employee_required, ajax_required, owner_required
from apps.core.utils import generate_unique_code, send_sms_notification, send_email_notification
from apps.employees.models import Employee
from apps.payments.models import Payment
from django.views.decorators.http import require_GET

from .models import (
    Service, ServiceCategory, ServicePackage, ServiceOrder, 
    ServiceOrderItem, ServiceQueue, ServiceBay
)
from .forms import (
    ServiceForm, ServiceCategoryForm, ServicePackageForm, 
    ServiceOrderForm, QuickOrderForm, ServiceOrderItemForm, ServiceRatingForm
)
from .notifications import send_service_notification_email
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger(__name__)

def generate_qr_code_base64(data, size=3, border=1):
    """Generate QR code as base64 image string"""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=size,
            border=border,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        # Create QR code image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        return f"data:image/png;base64,{img_str}"
    except Exception as e:
        logger.error(f"QR Code generation failed: {e}")
        return None

def get_business_url(request, url_name, **kwargs):
    """Helper function to generate URLs with business slug"""
    tenant_slug = request.tenant.slug
    base_url = f"/business/{tenant_slug}"
    
    url_mapping = {
        'services:list': f"{base_url}/services/",
        'services:create': f"{base_url}/services/create/",
        'services:detail': f"{base_url}/services/{{pk}}/",
        'services:edit': f"{base_url}/services/{{pk}}/edit/",
        'services:delete': f"{base_url}/services/{{pk}}/delete/",
        'services:order_list': f"{base_url}/services/orders/",
        'services:order_create': f"{base_url}/services/orders/create/",
        'services:order_detail': f"{base_url}/services/orders/{{pk}}/",
        'services:order_edit': f"{base_url}/services/orders/{{pk}}/edit/",
        'services:quick_order': f"{base_url}/services/quick-order/",
        'services:queue': f"{base_url}/services/queue/",
        'services:category_list': f"{base_url}/services/categories/",
        'services:category_create': f"{base_url}/services/categories/create/",
        'services:category_edit': f"{base_url}/services/categories/{{pk}}/edit/",
        'services:package_list': f"{base_url}/services/packages/",
        'services:package_create': f"{base_url}/services/packages/create/",
        'services:package_detail': f"{base_url}/services/packages/{{pk}}/",
        'services:package_edit': f"{base_url}/services/packages/{{pk}}/edit/",
        'services:bay_list': f"{base_url}/services/bays/",
        'services:bay_create': f"{base_url}/services/bays/create/",
        'services:bay_edit': f"{base_url}/services/bays/{{pk}}/edit/",
        'services:attendant_dashboard': f"{base_url}/services/dashboard/",
        'services:my_services': f"{base_url}/services/my-services/",
        'services:reports': f"{base_url}/services/reports/",
        'services:daily_report': f"{base_url}/services/reports/daily/",
        'services:performance_report': f"{base_url}/services/reports/performance/",
        'services:payment_receipt': f"{base_url}/services/orders/{{order_id}}/receipt/",
        'payments:create': f"{base_url}/payments/create/{{order_id}}/",
    }
    
    url = url_mapping.get(url_name, f"{base_url}/")
    
    # Replace placeholders with actual values
    for key, value in kwargs.items():
        url = url.replace(f"{{{key}}}", str(value))
    
    return url

@login_required
@employee_required()
@require_GET
def services_list_ajax(request):
    """AJAX endpoint to return a list of all active services as JSON."""
    services = Service.objects.filter(is_active=True).select_related('category')
    services_list = []
    for s in services:
        services_list.append({
            'id': s.id,
            'name': s.name,
            'base_price': float(s.base_price) if s.base_price is not None else 0,
            'category': s.category.name if s.category else 'Uncategorized',
            'estimated_duration': s.estimated_duration if hasattr(s, 'estimated_duration') else 0
        })
    return JsonResponse({'services': services_list})

@login_required
@employee_required()
def service_list_view(request):
    """List all services with categories"""
    categories = ServiceCategory.objects.filter(is_active=True).prefetch_related('services')
    
    # Filter services
    category_id = request.GET.get('category')
    search = request.GET.get('search')
    
    services = Service.objects.filter(is_active=True)
    if category_id:
        services = services.filter(category_id=category_id)
    if search:
        services = services.filter(
            Q(name__icontains=search) |
            Q(description__icontains=search)
        )
    
    services = services.select_related('category').order_by('category', 'display_order', 'name')
    
    # Pagination
    paginator = Paginator(services, 12)
    page = request.GET.get('page')
    services_page = paginator.get_page(page)
    
    # Statistics
    stats = {
        'total_services': Service.objects.filter(is_active=True).count(),
        'total_categories': categories.count(),
        'popular_services': Service.objects.filter(is_popular=True, is_active=True).count(),
        'avg_price': Service.objects.filter(is_active=True).aggregate(
            avg_price=Avg('base_price')
        )['avg_price'] or 0,
    }
    
    context = {
        'services': services_page,
        'categories': categories,
        'stats': stats,
        'current_filters': {
            'category': category_id,
            'search': search
        },
        'title': 'Service Management'
    }
    return render(request, 'services/service_list.html', context)

@login_required
@employee_required(['owner', 'manager'])
def service_create_view(request):
    """Create new service"""
    if request.method == 'POST':
        form = ServiceForm(request.POST, request.FILES)
        if form.is_valid():
            service = form.save(commit=False)
            service.created_by = request.user
            service.save()
            
            messages.success(request, f'Service "{service.name}" created successfully!')
            return redirect(get_business_url(request, 'services:detail', pk=service.pk))
    else:
        form = ServiceForm()
    
    context = {
        'form': form,
        'title': 'Create New Service'
    }
    return render(request, 'services/service_form.html', context)

@login_required
@employee_required()
def service_detail_view(request, pk):
    """Service detail view"""
    service = get_object_or_404(Service, pk=pk)
    
    # Get recent orders for this service
    recent_orders = ServiceOrderItem.objects.filter(
        service=service
    ).select_related('order', 'order__customer').order_by('-order__created_at')[:10]
    
    # Calculate statistics
    stats = {
        'total_orders': service.total_orders,
        'average_rating': service.average_rating,
        'total_revenue': ServiceOrderItem.objects.filter(
            service=service,
            order__status='completed'
        ).aggregate(total=Sum('total_price'))['total'] or 0,
        # FIXED: Calculate average duration using raw SQL for MySQL compatibility
        'avg_duration': 0,  # We'll calculate this separately
    }
    
    # Calculate average duration using tenant-aware database connection
    from django.db import connections
    from apps.core.database_router import get_current_tenant
    
    # Get the current tenant and use the appropriate database connection
    current_tenant = get_current_tenant()
    if current_tenant:
        db_alias = f"tenant_{current_tenant.id}"
        # Ensure tenant database is added to settings
        if db_alias not in connections.databases:
            from apps.core.database_router import TenantDatabaseManager
            TenantDatabaseManager.add_tenant_to_settings(current_tenant)
        
        # Use tenant database connection for raw SQL
        with connections[db_alias].cursor() as cursor:
            cursor.execute("""
                SELECT AVG(TIMESTAMPDIFF(MINUTE, started_at, completed_at)) as avg_duration
                FROM services_serviceorderitem 
                WHERE service_id = %s 
                AND completed_at IS NOT NULL 
                AND started_at IS NOT NULL
            """, [service.id])
            result = cursor.fetchone()
            if result and result[0]:
                stats['avg_duration'] = float(result[0])
    else:
        # Fallback: use default connection if no tenant context
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT AVG(TIMESTAMPDIFF(MINUTE, started_at, completed_at)) as avg_duration
                FROM services_serviceorderitem 
                WHERE service_id = %s 
                AND completed_at IS NOT NULL 
                AND started_at IS NOT NULL
            """, [service.id])
            result = cursor.fetchone()
            if result and result[0]:
                stats['avg_duration'] = float(result[0])
    
    # ADDED: Split compatible vehicle types for template
    compatible_vehicle_types = []
    if service.compatible_vehicle_types:
        compatible_vehicle_types = [
            vehicle_type.strip().title() 
            for vehicle_type in service.compatible_vehicle_types.split(',')
            if vehicle_type.strip()
        ]
    
    context = {
        'service': service,
        'recent_orders': recent_orders,
        'stats': stats,
        'compatible_vehicle_types': compatible_vehicle_types,  # Added this
        'title': f'Service - {service.name}'
    }
    return render(request, 'services/service_detail.html', context)
@login_required
@employee_required()
def order_list_view(request):
    """List service orders"""
    orders = ServiceOrder.objects.all().select_related(
        'customer', 'vehicle', 'assigned_attendant'
    ).prefetch_related('order_items__service')
    
    # Filters
    status = request.GET.get('status')
    attendant_id = request.GET.get('attendant')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    search = request.GET.get('search')
    
    # Clean up None values and empty strings
    if status and status.lower() in ['none', '']:
        status = None
    if attendant_id and attendant_id.lower() in ['none', '']:
        attendant_id = None
    if date_from and date_from.lower() in ['none', '']:
        date_from = None
    if date_to and date_to.lower() in ['none', '']:
        date_to = None
    if search and search.lower() in ['none', '']:
        search = None
    
    # Apply filters
    if status:
        orders = orders.filter(status=status)
        
    if attendant_id:
        try:
            attendant_id_int = int(attendant_id)
            orders = orders.filter(assigned_attendant_id=attendant_id_int)
        except (ValueError, TypeError):
            # Invalid attendant ID, ignore filter
            attendant_id = None
            
    if date_from:
        try:
            from datetime import datetime
            date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d').date()
            orders = orders.filter(created_at__date__gte=date_from_parsed)
        except (ValueError, TypeError):
            # Invalid date format, ignore filter
            date_from = None
            
    if date_to:
        try:
            from datetime import datetime
            date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d').date()
            orders = orders.filter(created_at__date__lte=date_to_parsed)
        except (ValueError, TypeError):
            # Invalid date format, ignore filter
            date_to = None
    if search:
        orders = orders.filter(
            Q(order_number__icontains=search) |
            Q(customer__first_name__icontains=search) |
            Q(customer__last_name__icontains=search) |
            Q(vehicle__registration_number__icontains=search)
        )
    
    # Sort by priority and creation date
    orders = orders.order_by(
        Case(
            When(priority='urgent', then=Value(1)),
            When(priority='high', then=Value(2)),
            When(priority='normal', then=Value(3)),
            When(priority='low', then=Value(4)),
            default=Value(3),
            output_field=IntegerField(),
        ),
        '-created_at'
    )
    
    # Pagination
    paginator = Paginator(orders, 20)
    page = request.GET.get('page')
    orders_page = paginator.get_page(page)
    
    # Get attendants for filter
    from apps.employees.models import Employee
    attendants = Employee.objects.filter(
        role__in=['attendant', 'supervisor', 'manager', 'cleaner'],
        is_active=True
    )
    
    # Statistics - focus on today's data with additional metrics
    today = timezone.now().date()
    
    # Get ALL today's orders (unfiltered) for statistics using improved date filtering
    # Method 1: Simple date filter
    orders_date_filter = ServiceOrder.objects.filter(created_at__date=today)
    
    # Method 2: Datetime range filter (more precise for timezone issues)
    from datetime import datetime
    date_start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
    date_end = timezone.make_aware(datetime.combine(today, datetime.max.time()))
    orders_datetime_filter = ServiceOrder.objects.filter(
        created_at__gte=date_start, 
        created_at__lte=date_end
    )
    
    # Use whichever method finds more orders (same as businesses/utils.py)
    if orders_datetime_filter.count() > orders_date_filter.count():
        all_today_orders = orders_datetime_filter
    else:
        all_today_orders = orders_date_filter
    # Revenue calculation for today (completely paid orders only)
    today_revenue = Decimal('0.00')
    try:
        from apps.payments.models import Payment
        
        for order in all_today_orders.exclude(status='cancelled'):
            # Get total payments for this order (excluding refunds)
            total_payments = Payment.objects.filter(
                service_order=order,
                status__in=['completed', 'verified', 'paid', 'success']
            ).exclude(
                payment_type='refund'
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
            
            # Check if order is completely paid
            order_total = order.total_amount or Decimal('0.00')
            if total_payments >= order_total:
                today_revenue += order_total
    except Exception as e:
        # Fallback to completed orders total
        today_revenue = all_today_orders.filter(status='completed').aggregate(
            total=Sum('total_amount')
        )['total'] or Decimal('0.00')
    
    # Calculate statistics breakdown
    pending_count = all_today_orders.filter(status='pending').count()
    in_progress_count = all_today_orders.filter(status='in_progress').count()
    completed_count = all_today_orders.filter(status='completed').count()
    
    stats = {
        # Today's core metrics (unfiltered)
        'total_orders_today': all_today_orders.count(),
        'pending_orders': pending_count,
        'in_progress_orders': in_progress_count,
        'completed_today': completed_count,
        'cancelled_today': all_today_orders.filter(status='cancelled').count(),
        'today_revenue': today_revenue,
        
        # Overall metrics for context (filtered)
        'total_orders': orders.count(),
        'active_orders': orders.filter(status__in=['pending', 'in_progress']).count(),
        
        # Average metrics
        'avg_order_value': today_revenue / max(all_today_orders.exclude(status='cancelled').count(), 1),
        'completion_rate': (completed_count / max(all_today_orders.exclude(status='cancelled').count(), 1)) * 100,
    }
    
    context = {
        'orders': orders_page,
        'attendants': attendants,
        'stats': stats,
        'status_choices': ServiceOrder.STATUS_CHOICES,
        'current_filters': {
            'status': status or '',
            'attendant': attendant_id or '',
            'date_from': date_from or '',
            'date_to': date_to or '',
            'search': search or ''
        },
        'title': 'Service Orders'
    }
    return render(request, 'services/order_list.html', context)

@login_required
@employee_required()
def order_create_view(request):
    """Create new service order"""
    if request.method == 'POST':
        form = ServiceOrderForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    order = form.save(commit=False)
                    order.created_by = request.user
                    order.save()
                    
                    # Add services to order
                    services_data = json.loads(request.POST.get('services_data', '[]'))
                    total_amount = 0
                    
                    for service_data in services_data:
                        service = Service.objects.get(id=service_data['service_id'])
                        quantity = service_data['quantity']
                        unit_price = service_data.get('unit_price', service.base_price)
                        
                        ServiceOrderItem.objects.create(
                            order=order,
                            service=service,
                            quantity=quantity,
                            unit_price=unit_price
                        )
                        total_amount += quantity * unit_price
                    
                    # Calculate totals
                    order.subtotal = total_amount
                    order.calculate_totals()
                    order.save()
                    
                    # Add to queue if needed
                    if order.status == 'confirmed':
                        add_order_to_queue(order)
                    
                    # Send notifications
                    # Ensure tenant context is set from request
                    from apps.core.database_router import set_current_tenant
                    if hasattr(request, 'tenant') and request.tenant:
                        set_current_tenant(request.tenant)
                    
                    # Send order created notification
                    from apps.core.notifications import send_order_created_notification
                    send_order_created_notification(
                        order=order,
                        tenant=request.tenant if hasattr(request, 'tenant') else None
                    )
                    
                    messages.success(request, f'Order {order.order_number} created successfully!')
                    return redirect(get_business_url(request, 'services:order_detail', pk=order.pk))
                    
            except Exception as e:
                messages.error(request, f'Error creating order: {str(e)}')
    else:
        form = ServiceOrderForm()
    
    # Get services and categories for the form
    categories = ServiceCategory.objects.filter(is_active=True).prefetch_related('services')
    
    # Get employees for assignment
    from apps.employees.models import Employee
    employees = Employee.objects.filter(
        role__in=['attendant', 'supervisor', 'manager', 'cleaner'],
        is_active=True
    )
    
    context = {
        'form': form,
        'categories': categories,
        'employees': employees,
        'title': 'Create Service Order'
    }
    return render(request, 'services/order_form.html', context)

@csrf_protect
@employee_required()
@require_http_methods(["GET", "POST"])
def quick_order_view(request):
    """Quick order creation"""
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Log the incoming data for debugging
                logger.info(f"Quick order POST data: {request.POST}")
                
                # Import here to avoid circular imports
                from apps.customers.models import Customer, Vehicle
                
                # Step 1: Handle Vehicle (optional when selling inventory items only)
                existing_vehicle_id = request.POST.get('selected_vehicle_id')
                vehicle = None
                skip_vehicle = request.POST.get('skip_vehicle', 'false') == 'true'
                
                # Initialize vehicle variables to avoid UnboundLocalError
                vehicle_registration = ''
                vehicle_make = 'Unknown'
                vehicle_model = 'Unknown'
                vehicle_color = 'Unknown'
                vehicle_type = 'car'
                vehicle_year = '2020'
                
                # Check if only inventory items are being sold (no services)
                selected_services = request.POST.getlist('selected_services')
                selected_inventory_items = request.POST.getlist('selected_inventory_items')
                inventory_only = not selected_services and selected_inventory_items
                
                if skip_vehicle or inventory_only:
                    # Skip vehicle creation for inventory-only orders
                    vehicle = None
                elif existing_vehicle_id:
                    # Existing vehicle selected
                    try:
                        vehicle = Vehicle.objects.get(id=existing_vehicle_id, is_active=True)
                        logger.info(f"Using existing vehicle: {vehicle.registration_number}")
                    except Vehicle.DoesNotExist:
                        error_msg = 'Selected vehicle not found'
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({
                                'success': False,
                                'message': error_msg,
                                'errors': {'vehicle': ['Vehicle not found']}
                            })
                        else:
                            messages.error(request, error_msg)
                            return redirect(get_business_url(request, 'services:quick_order'))
                else:
                    # New vehicle - validate required fields (only registration is required)
                    vehicle_registration = request.POST.get('vehicle_registration', '').strip().upper()
                    vehicle_make = request.POST.get('vehicle_make', '').strip() or 'Unknown'
                    vehicle_model = request.POST.get('vehicle_model', '').strip() or 'Unknown'
                    vehicle_color = request.POST.get('vehicle_color', '').strip() or 'Unknown'
                    vehicle_type = request.POST.get('vehicle_type', '').strip() or 'car'
                    vehicle_year = request.POST.get('vehicle_year', '') or '2020'
                    
                    if not vehicle_registration:
                        error_msg = 'Vehicle registration number is required'
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({
                                'success': False,
                                'message': error_msg,
                                'errors': {'vehicle': ['Vehicle registration number is required']}
                            })
                        else:
                            messages.error(request, error_msg)
                            return redirect(get_business_url(request, 'services:quick_order'))
                    
                    # Check if vehicle already exists
                    if Vehicle.objects.filter(registration_number=vehicle_registration).exists():
                        error_msg = f'Vehicle {vehicle_registration} already exists'
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({
                                'success': False,
                                'message': error_msg,
                                'errors': {'vehicle_registration': ['Vehicle already exists']}
                            })
                        else:
                            messages.error(request, error_msg)
                            return redirect(get_business_url(request, 'services:quick_order'))
                
                # Step 2: Handle Customer
                is_walk_in = request.POST.get('is_walk_in_customer', 'false') == 'true'
                existing_customer_id = request.POST.get('selected_customer_id')
                customer = None
                
                if is_walk_in:
                    # Walk-in customer - create minimal customer record or use anonymous
                    customer_name = request.POST.get('customer_name', '').strip()
                    customer_phone = request.POST.get('customer_phone', '').strip()
                    
                    if customer_name or customer_phone:
                        # Create customer with provided details
                        name_parts = customer_name.split(' ', 1) if customer_name else ['Walk-in', 'Customer']
                        first_name = name_parts[0]
                        last_name = name_parts[1] if len(name_parts) > 1 else ''
                        
                        customer = Customer.objects.create(
                            first_name=first_name,
                            last_name=last_name,
                            phone=customer_phone if customer_phone else None,
                            email=request.POST.get('customer_email', '').strip(),
                            customer_id=generate_unique_code('WALK', 6),
                            is_walk_in=True,
                            created_by_user_id=request.user.id
                        )
                        logger.info(f"Created walk-in customer: {customer.full_name}")
                    else:
                        # Create anonymous walk-in customer
                        customer = Customer.objects.create(
                            first_name='Walk-in',
                            last_name='Customer',
                            customer_id=generate_unique_code('WALK', 6),
                            is_walk_in=True,
                            created_by_user_id=request.user.id
                        )
                        logger.info("Created anonymous walk-in customer")
                        
                elif existing_customer_id:
                    # Existing customer selected
                    try:
                        customer = Customer.objects.get(id=existing_customer_id)
                        logger.info(f"Using existing customer: {customer.full_name}")
                    except Customer.DoesNotExist:
                        error_msg = 'Selected customer not found'
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({
                                'success': False,
                                'message': error_msg,
                                'errors': {'customer': ['Customer not found']}
                            })
                        else:
                            messages.error(request, error_msg)
                            return redirect(get_business_url(request, 'services:quick_order'))
                            
                elif vehicle and hasattr(vehicle, 'customer'):
                    # Use vehicle's existing customer
                    customer = vehicle.customer
                    logger.info(f"Using vehicle's customer: {customer.full_name}")
                    
                else:
                    # New customer registration
                    customer_name = request.POST.get('customer_name', '').strip()
                    customer_phone = request.POST.get('customer_phone', '').strip()
                    
                    if not customer_name or not customer_phone:
                        error_msg = 'Customer name and phone are required for new customers'
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({
                                'success': False,
                                'message': error_msg,
                                'errors': {
                                    'customer_name': ['Name is required'] if not customer_name else [],
                                    'customer_phone': ['Phone is required'] if not customer_phone else []
                                }
                            })
                        else:
                            messages.error(request, error_msg)
                            return redirect(get_business_url(request, 'services:quick_order'))
                    
                    # Create new customer
                    name_parts = customer_name.split(' ', 1)
                    first_name = name_parts[0]
                    last_name = name_parts[1] if len(name_parts) > 1 else ''
                    
                    customer = Customer.objects.create(
                        first_name=first_name,
                        last_name=last_name,
                        phone=customer_phone,
                        email=request.POST.get('customer_email', '').strip(),
                        customer_id=generate_unique_code('CUST', 6),
                        created_by_user_id=request.user.id
                    )
                    logger.info(f"Created new customer: {customer.full_name}")
                
                # If skipping vehicle and no customer specified, create walk-in customer
                if (skip_vehicle or inventory_only) and not customer:
                    customer = Customer.objects.create(
                        first_name='Walk-in',
                        last_name='Customer',
                        customer_id=generate_unique_code('WALK', 6),
                        is_walk_in=True,
                        created_by_user_id=request.user.id
                    )
                    logger.info("Created walk-in customer for inventory-only order")
                
                # Create vehicle if it's new and assign to customer (only if not skipping vehicle)
                if not vehicle and not skip_vehicle and not inventory_only and vehicle_registration:
                    vehicle = Vehicle.objects.create(
                        customer=customer,
                        registration_number=vehicle_registration,
                        make=vehicle_make,
                        model=vehicle_model,
                        color=vehicle_color,
                        vehicle_type=vehicle_type,
                        year=int(vehicle_year),
                        created_by_user_id=request.user.id
                    )
                    logger.info(f"Created new vehicle: {vehicle.registration_number}")
                elif not skip_vehicle and not inventory_only and request.POST.get('add_vehicle_to_customer') == 'on' and vehicle and customer != vehicle.customer:
                    # Add existing vehicle to new customer (transfer ownership)
                    old_customer = vehicle.customer
                    vehicle.customer = customer
                    vehicle.save()
                    logger.info(f"Transferred vehicle {vehicle.registration_number} from {old_customer.full_name} to {customer.full_name}")
                
                # Create the service order
                order = ServiceOrder.objects.create(
                    customer=customer,
                    vehicle=vehicle,
                    assigned_attendant=getattr(request, 'employee', None),
                    status='confirmed',
                    priority=request.POST.get('priority', 'normal'),
                    special_instructions=request.POST.get('special_instructions', '').strip(),
                    created_by_id=request.user.id
                )
                logger.info(f"Created order: {order.order_number}")
                
                # Handle service selection
                service_type = request.POST.get('service_type', 'individual')
                total_amount = Decimal('0')
                
                if service_type == 'package':
                    # Handle service package with custom price
                    selected_package_id = request.POST.get('selected_package')
                    if not selected_package_id:
                        raise ValueError("Package must be selected")
                    
                    try:
                        package = ServicePackage.objects.get(id=selected_package_id, is_active=True)
                        order.package = package
                        
                        # Get custom price if provided
                        package_custom_price = request.POST.get('package_custom_price')
                        if package_custom_price:
                            try:
                                custom_price = Decimal(str(package_custom_price))
                                # Validate custom price is not below minimum
                                if custom_price < package.minimum_price:
                                    logger.warning(f"Custom price {custom_price} for package {package.name} is below minimum {package.minimum_price}")
                                    total_amount = package.minimum_price
                                else:
                                    total_amount = custom_price
                                logger.info(f"Applied custom price {total_amount} to package {package.name}")
                            except (ValueError, TypeError):
                                logger.warning(f"Invalid custom price for package, using base price")
                                total_amount = package.total_price
                        else:
                            total_amount = package.total_price
                        
                        # Add individual services from the package
                        for package_service in package.packageservice_set.all():
                            ServiceOrderItem.objects.create(
                                order=order,
                                service=package_service.service,
                                quantity=package_service.quantity,
                                unit_price=package_service.custom_price or package_service.service.base_price,
                                assigned_to=getattr(request, 'employee', None)
                            )
                        logger.info(f"Added package services: {package.name}")
                    except ServicePackage.DoesNotExist:
                        raise ValueError("Selected package not found")
                else:
                    # Handle individual services, inventory items, and customer parts
                    selected_services = request.POST.getlist('selected_services')
                    selected_inventory_items = request.POST.getlist('selected_inventory_items')
                    customer_parts_data = request.POST.get('customer_parts', '[]')
                    
                    # Parse customer parts data from JSON
                    try:
                        import json
                        customer_parts = json.loads(customer_parts_data) if customer_parts_data else []
                    except (json.JSONDecodeError, TypeError):
                        customer_parts = []
                    
                    # Parse services custom prices from JSON
                    services_custom_prices_data = request.POST.get('services_custom_prices', '{}')
                    try:
                        services_custom_prices = json.loads(services_custom_prices_data) if services_custom_prices_data else {}
                    except (json.JSONDecodeError, TypeError):
                        services_custom_prices = {}
                    
                    # Validate that at least one service, inventory item, or customer part is selected
                    if not selected_services and not selected_inventory_items and not customer_parts:
                        raise ValueError("At least one service, inventory item, or customer part must be selected")
                    
                    # Process selected services with custom prices
                    for service_id in selected_services:
                        try:
                            service = Service.objects.get(id=service_id, is_active=True)
                            
                            # Get custom price if provided
                            custom_price = services_custom_prices.get(str(service_id))
                            unit_price = Decimal(str(custom_price)) if custom_price else service.base_price
                            
                            # Validate custom price is not below minimum
                            if custom_price and unit_price < service.minimum_price:
                                logger.warning(f"Custom price {unit_price} for service {service.name} is below minimum {service.minimum_price}")
                                unit_price = service.minimum_price
                            
                            ServiceOrderItem.objects.create(
                                order=order,
                                service=service,
                                quantity=1,
                                unit_price=unit_price,
                                assigned_to=getattr(request, 'employee', None)
                            )
                            total_amount += unit_price
                            logger.info(f"Added service: {service.name} at price {unit_price}")
                        except Service.DoesNotExist:
                            logger.warning(f"Service {service_id} not found, skipping")
                            continue
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Invalid custom price for service {service_id}: {e}")
                            # Fall back to base price
                            try:
                                service = Service.objects.get(id=service_id, is_active=True)
                                ServiceOrderItem.objects.create(
                                    order=order,
                                    service=service,
                                    quantity=1,
                                    unit_price=service.base_price,
                                    assigned_to=getattr(request, 'employee', None)
                                )
                                total_amount += service.base_price
                                logger.info(f"Added service: {service.name} at base price")
                            except Service.DoesNotExist:
                                continue
                
                # Handle inventory items with custom prices
                selected_inventory_items = request.POST.getlist('selected_inventory_items')
                if selected_inventory_items:
                    from apps.inventory.models import InventoryItem, StockMovement
                    
                    # Parse inventory custom prices from JSON
                    inventory_custom_prices_data = request.POST.get('inventory_custom_prices', '{}')
                    try:
                        inventory_custom_prices = json.loads(inventory_custom_prices_data) if inventory_custom_prices_data else {}
                    except (json.JSONDecodeError, TypeError):
                        inventory_custom_prices = {}
                    
                    for item_id in selected_inventory_items:
                        try:
                            inventory_item = InventoryItem.objects.get(id=item_id, is_active=True)
                            quantity_field = f'inventory_quantity_{item_id}'
                            quantity = Decimal(request.POST.get(quantity_field, '1'))
                            
                            # Check stock availability
                            if inventory_item.current_stock < quantity:
                                logger.warning(f"Insufficient stock for {inventory_item.name}")
                                continue
                            
                            # Get custom price if provided
                            custom_price = inventory_custom_prices.get(str(item_id))
                            unit_price = Decimal(str(custom_price)) if custom_price else (inventory_item.selling_price or inventory_item.unit_cost)
                            
                            # Validate custom price is not below minimum (unit cost)
                            minimum_price = inventory_item.unit_cost
                            if custom_price and unit_price < minimum_price:
                                logger.warning(f"Custom price {unit_price} for inventory {inventory_item.name} is below minimum {minimum_price}")
                                unit_price = minimum_price
                            
                            # Create service order item for inventory item
                            ServiceOrderItem.objects.create(
                                order=order,
                                inventory_item=inventory_item,
                                quantity=quantity,
                                unit_price=unit_price,
                                assigned_to=getattr(request, 'employee', None)
                            )
                            
                            # Note: Stock deduction timing depends on order type:
                            # - Service orders: Deducted immediately after order creation (old flow)
                            # - Inventory-only orders: Deducted when payment is completed (new flow)
                            
                            total_amount += unit_price * quantity
                            logger.info(f"Added inventory item: {inventory_item.name} x{quantity} at price {unit_price}")
                            
                        except (InventoryItem.DoesNotExist, ValueError, TypeError) as e:
                            logger.warning(f"Inventory item {item_id} not found or invalid: {e}, skipping")
                            continue
                
                # Handle customer parts (manual entries)
                if customer_parts:
                    for part_data in customer_parts:
                        try:
                            part_name = part_data.get('name', '').strip()
                            part_quantity = Decimal(str(part_data.get('quantity', 1)))
                            
                            if not part_name:
                                logger.warning("Customer part without name, skipping")
                                continue
                            
                            # Create service order item for customer part
                            ServiceOrderItem.objects.create(
                                order=order,
                                description=f"Customer Part: {part_name}",
                                quantity=part_quantity,
                                unit_price=Decimal('0'),  # Customer parts are free
                                total_price=Decimal('0'),  # Explicitly set total price
                                is_customer_provided=True,
                                assigned_to=getattr(request, 'employee', None)
                            )
                            
                            logger.info(f"Added customer part: {part_name} x{part_quantity}")
                            
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Invalid customer part data: {e}, skipping")
                            continue
                
                # Calculate totals
                order.subtotal = total_amount
                order.calculate_totals()
                order.save()
                
                # Check if this is an inventory-only order
                is_inventory_only = order.is_inventory_only
                
                # Handle inventory deduction based on order type
                # INVENTORY DEDUCTION LOGIC:
                # 1. Service orders (mixed): Deduct inventory IMMEDIATELY at order creation
                # 2. Inventory-only orders: Deduct inventory AT PAYMENT COMPLETION
                if order.has_services and order.has_inventory_items:
                    # Mixed order (services + inventory): Deduct inventory immediately (old flow)
                    logger.info(f"Order {order.order_number} contains services. Deducting inventory immediately (old flow).")
                    _process_order_inventory_deduction(order, request.user)
                elif is_inventory_only:
                    # Inventory-only order: Deduct on payment completion (new flow)
                    logger.info(f"Inventory-only order {order.order_number} created, inventory will be deducted on payment completion")
                
                # For inventory-only orders, we can proceed directly to payment
                if is_inventory_only:
                    # No need to add to service queue for inventory-only orders
                    logger.info(f"Inventory-only order {order.order_number} created, ready for payment")
                else:
                    # Add service orders to queue
                    add_order_to_queue(order)
                
                # Send order created notification
                from apps.core.database_router import set_current_tenant
                from apps.core.notifications import send_order_created_notification
                
                if hasattr(request, 'tenant') and request.tenant:
                    set_current_tenant(request.tenant)
                
                send_order_created_notification(
                    order=order,
                    tenant=request.tenant if hasattr(request, 'tenant') else None
                )
                
                logger.info(f"Order {order.order_number} created successfully")
                
                # Return appropriate response
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    response_data = {
                        'success': True,
                        'message': f'Order {order.order_number} created successfully!',
                        'order_id': str(order.id),
                        'order_number': order.order_number,
                        'is_inventory_only': is_inventory_only,
                        'redirect_url': get_business_url(request, 'services:order_detail', pk=order.id)
                    }
                    
                    # For inventory-only orders, update the message
                    if is_inventory_only:
                        response_data['message'] = f'Inventory order {order.order_number} created successfully!'
                    
                    return JsonResponse(response_data)
                else:
                    if is_inventory_only:
                        messages.success(request, f'Inventory order {order.order_number} created successfully!')
                    else:
                        messages.success(request, f'Quick order {order.order_number} created successfully!')
                    return redirect(get_business_url(request, 'services:order_detail', pk=order.pk))
                
        except ValueError as e:
            error_msg = str(e)
            logger.error(f"ValueError in quick order creation: {error_msg}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': error_msg,
                    'errors': {'general': [error_msg]}
                })
            else:
                messages.error(request, error_msg)
                return redirect(get_business_url(request, 'services:quick_order'))
        except Exception as e:
            error_msg = f'Error creating quick order: {str(e)}'
            logger.error(f"Exception in quick order creation: {error_msg}", exc_info=True)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': 'An unexpected error occurred. Please try again.',
                    'errors': {'general': [str(e)]}
                })
            else:
                messages.error(request, error_msg)
                return redirect(get_business_url(request, 'services:quick_order'))
    
    # GET request - show the form
    # Get popular services for quick selection, fallback to all active services if no popular ones
    popular_services = Service.objects.filter(
        is_active=True,
        is_popular=True
    ).order_by('display_order')[:8]
    
    # If no popular services, show all active services
    if not popular_services.exists():
        popular_services = Service.objects.filter(
            is_active=True
        ).order_by('display_order', 'name')[:8]

    # Get all active services for category filtering
    all_services = Service.objects.filter(is_active=True).select_related('category')

    # Get service packages
    service_packages = ServicePackage.objects.filter(
        is_active=True
    ).order_by('-is_popular', 'name')[:8]

    # Get service categories with their active services
    categories = ServiceCategory.objects.filter(is_active=True).prefetch_related(
        'services__category'
    ).annotate(
        active_service_count=models.Count('services', filter=models.Q(services__is_active=True))
    ).filter(active_service_count__gt=0)
    
    # Handle inventory items integration
    from apps.inventory.models import InventoryItem, Unit
    selected_items = []
    selected_unit = None
    
    # Check for add_item parameter
    add_item_id = request.GET.get('add_item')
    if add_item_id:
        try:
            item = InventoryItem.objects.get(id=add_item_id, is_active=True)
            selected_items.append(item)
        except InventoryItem.DoesNotExist:
            messages.warning(request, 'Selected inventory item not found.')
    
    # Check for add_unit parameter
    add_unit_id = request.GET.get('add_unit')
    if add_unit_id:
        try:
            selected_unit = Unit.objects.get(id=add_unit_id, is_active=True)
        except Unit.DoesNotExist:
            messages.warning(request, 'Selected unit not found.')
    
    # Get available inventory items for the quick order
    from django.core.paginator import Paginator
    
    all_inventory_items = InventoryItem.objects.filter(
        is_active=True,
        current_stock__gt=0  # Only show items with stock
    ).select_related('category', 'unit').order_by('name')
    
    # Add pagination for inventory items
    paginator = Paginator(all_inventory_items, 50)  # Show 50 items per page
    page_number = request.GET.get('page', 1)
    inventory_items = paginator.get_page(page_number)
    
    # Get inventory categories that have items with stock
    from apps.inventory.models import InventoryCategory
    inventory_categories = InventoryCategory.objects.filter(
        items__is_active=True,
        items__current_stock__gt=0
    ).distinct().order_by('name')
    
    context = {
        'popular_services': popular_services,
        'all_services': all_services,
        'categories': categories,
        'service_packages': service_packages,
        'inventory_items': inventory_items,
        'inventory_categories': inventory_categories,
        'selected_items': selected_items,
        'selected_unit': selected_unit,
        'title': 'Quick Order (Walk-in Customer)'
    }
    return render(request, 'services/quick_order.html', context)

"""
INVENTORY DEDUCTION FLOW DOCUMENTATION

The system implements a dual inventory deduction flow based on order type:

1. SERVICE ORDERS (Mixed - contains both services and inventory):
   - TIMING: Inventory deducted IMMEDIATELY at ORDER CREATION
   - LOCATION: _process_order_inventory_deduction() function
   - REASON: Maintains old flow where inventory is reserved upfront for service work
   - CANCELLATION: Inventory restored via _restore_order_inventory()

2. INVENTORY-ONLY ORDERS (No services, only inventory items):
   - TIMING: Inventory deducted AT PAYMENT COMPLETION
   - LOCATION: Payment._process_inventory_deduction() method
   - REASON: Customer must pay first before receiving inventory items
   - CANCELLATION: Inventory restored only if payment was completed

3. CANCELLATION HANDLING:
   - Service orders: Always restore inventory (was deducted at creation)
   - Inventory-only: Restore only if payment was completed
   - Restoration creates stock movement records for audit trail

This dual flow ensures:
- Service customers can start service immediately (old behavior preserved)
- Inventory-only customers must pay first (new requirement)
- Proper inventory tracking and restoration on cancellations
"""

def _process_order_inventory_deduction(order, user=None):
    """
    Process immediate inventory deduction for orders containing services (old flow).
    
    Business Logic:
    - Called ONLY for service orders (mixed orders with services + inventory)
    - Deducts inventory immediately at ORDER CREATION (before payment)
    - This maintains the old flow for service orders where inventory is deducted upfront
    - Inventory-only orders use payment-time deduction (handled in Payment model)
    """
    from apps.inventory.models import StockMovement
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Process inventory items in the order
    inventory_items = order.order_items.filter(inventory_item__isnull=False)
    
    if not inventory_items.exists():
        logger.info(f"No inventory items to deduct for order {order.order_number}")
        return
    
    logger.info(f"Processing immediate inventory deduction for order {order.order_number} (service-containing order)")
    
    for order_item in inventory_items:
        try:
            inventory_item = order_item.inventory_item
            quantity = order_item.quantity
            
            # Check if we have enough stock
            if inventory_item.current_stock < quantity:
                logger.warning(
                    f"Insufficient stock for {inventory_item.name}. "
                    f"Available: {inventory_item.current_stock}, Required: {quantity}"
                )
                # Adjust quantity to available stock
                quantity = inventory_item.current_stock
                order_item.quantity = quantity
                order_item.save()
            
            # Deduct from inventory stock
            old_stock = inventory_item.current_stock
            inventory_item.current_stock -= quantity
            inventory_item.save()
            
            # Create stock movement record
            StockMovement.objects.create(
                item=inventory_item,
                movement_type='out',
                quantity=quantity,
                unit_cost=inventory_item.unit_cost,
                old_stock=old_stock,
                new_stock=inventory_item.current_stock,
                reference_type='sale',
                reference_number=order.order_number,
                service_order=order,
                reason=f'Sold in order {order.order_number} - Service order (immediate deduction)',
                created_by_user_id=user.id if user else None
            )
            
            logger.info(
                f"Deducted {quantity} of {inventory_item.name} from stock immediately. "
                f"New stock: {inventory_item.current_stock}"
            )
            
        except Exception as e:
            logger.error(
                f"Error processing inventory deduction for item {order_item.id}: {str(e)}"
            )

def _restore_order_inventory(order, user=None, reason="Order cancelled"):
    """
    Restore inventory items when an order is cancelled.
    
    Business Logic:
    - Service orders (mixed): Inventory was deducted at order creation, restore it
    - Inventory-only orders: Only restore if payment was completed (inventory was deducted)
    """
    from apps.inventory.models import StockMovement
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Get inventory items from the order
    inventory_items = order.order_items.filter(inventory_item__isnull=False)
    
    if not inventory_items.exists():
        logger.info(f"No inventory items to restore for order {order.order_number}")
        return
    
    # Check if we need to restore inventory
    should_restore = False
    
    if order.has_services:
        # Service orders: inventory was deducted at order creation, always restore
        should_restore = True
        logger.info(f"Service order {order.order_number} - restoring inventory (was deducted at order creation)")
    elif order.is_inventory_only:
        # Inventory-only orders: only restore if payment was completed
        completed_payments = order.payments.filter(status='completed').exists()
        if completed_payments:
            should_restore = True
            logger.info(f"Inventory-only order {order.order_number} - restoring inventory (payment was completed)")
        else:
            logger.info(f"Inventory-only order {order.order_number} - no payment completed, no inventory to restore")
    
    if not should_restore:
        return
    
    # Restore inventory for each item
    for order_item in inventory_items:
        try:
            inventory_item = order_item.inventory_item
            quantity = order_item.quantity
            
            # Restore inventory stock
            old_stock = inventory_item.current_stock
            inventory_item.current_stock += quantity
            inventory_item.save()
            
            # Create stock movement record for the restoration
            StockMovement.objects.create(
                item=inventory_item,
                movement_type='in',
                quantity=quantity,
                unit_cost=inventory_item.unit_cost,
                old_stock=old_stock,
                new_stock=inventory_item.current_stock,
                reference_type='cancellation',
                reference_number=order.order_number,
                service_order=order,
                reason=f'Restored from cancelled order {order.order_number} - {reason}',
                created_by_user_id=user.id if user else None
            )
            
            logger.info(
                f"Restored {quantity} of {inventory_item.name} to stock. "
                f"New stock: {inventory_item.current_stock}"
            )
            
        except Exception as e:
            logger.error(
                f"Error restoring inventory for item {order_item.id}: {str(e)}"
            )

def add_order_to_queue(order):
    """Add order to service queue"""
    try:
        from .models import ServiceQueue
        from django.db import models
        from django.utils import timezone
        from datetime import timedelta
        
        # Get next queue number
        last_queue_number = ServiceQueue.objects.filter(
            created_at__date=timezone.now().date()
        ).aggregate(max_num=models.Max('queue_number'))['max_num'] or 0
        
        # Calculate estimated times
        estimated_duration = order.estimated_duration
        estimated_start_time = timezone.now()
        
        # Check for orders ahead in queue
        waiting_orders = ServiceQueue.objects.filter(status='waiting').count()
        if waiting_orders > 0:
            # Add buffer time based on queue length
            estimated_start_time += timedelta(minutes=waiting_orders * 30)  # 30 min average per order
        
        estimated_end_time = estimated_start_time + timedelta(minutes=estimated_duration)
        
        ServiceQueue.objects.create(
            order=order,
            queue_number=last_queue_number + 1,
            estimated_start_time=estimated_start_time,
            estimated_end_time=estimated_end_time
        )
        logger.info(f"Added order {order.order_number} to queue")
    except Exception as e:
        logger.error(f"Error adding order to queue: {str(e)}", exc_info=True)

@login_required
@employee_required()
def order_detail_view(request, pk):
    """Service order detail view"""
    order = get_object_or_404(ServiceOrder, pk=pk)
    
    # Get order items
    order_items = order.order_items.all().select_related('service', 'assigned_to')
    
    # Get queue entry if exists
    queue_entry = getattr(order, 'queue_entry', None)
    
    # Get available service bays (filter by actual fields, not the property)
    available_bays = ServiceBay.objects.filter(is_active=True, is_occupied=False)
    
    # Get available attendants (all service-related roles)
    from apps.employees.models import Employee
    available_attendants = Employee.objects.filter(
        role__in=['attendant', 'supervisor', 'cleaner', 'manager'],
        is_active=True
    )

    # Get latest completed payment for this order
    payment = None
    payment_id = None
    try:
        payment = Payment.objects.filter(
            service_order=order,
            status__in=['completed', 'verified']
        ).order_by('-completed_at').first()
        payment_id = payment.payment_id if payment else None
    except ImportError:
        payment = None
        payment_id = None

    # Parse timeline events from internal notes
    timeline_events = []
    if order.internal_notes:
        lines = order.internal_notes.split('\n')
        for line in lines:
            line = line.strip()
            if 'Paused by' in line and 'at' in line:
                # Extract pause event: "Paused by John Doe at 2025-09-21 12:30:45..."
                try:
                    parts = line.split(' at ')
                    if len(parts) >= 2:
                        employee_part = parts[0].replace('Paused by', '').strip()
                        datetime_part = parts[1].split('+')[0].strip()  # Remove timezone
                        from datetime import datetime
                        event_time = datetime.strptime(datetime_part, '%Y-%m-%d %H:%M:%S.%f')
                        timeline_events.append({
                            'type': 'pause',
                            'title': 'Service Paused',
                            'time': event_time,
                            'employee': employee_part,
                            'icon': 'fas fa-pause-circle',
                            'color': 'warning'
                        })
                except Exception:
                    pass
            elif 'Resumed by' in line and 'at' in line:
                # Extract resume event: "Resumed by John Doe at 2025-09-21 13:00:15..."
                try:
                    parts = line.split(' at ')
                    if len(parts) >= 2:
                        employee_part = parts[0].replace('Resumed by', '').strip()
                        datetime_part = parts[1].split('+')[0].strip()  # Remove timezone
                        from datetime import datetime
                        event_time = datetime.strptime(datetime_part, '%Y-%m-%d %H:%M:%S.%f')
                        timeline_events.append({
                            'type': 'resume',
                            'title': 'Service Resumed',
                            'time': event_time,
                            'employee': employee_part,
                            'icon': 'fas fa-play-circle',
                            'color': 'success'
                        })
                except Exception:
                    pass
    
    # Sort timeline events by time
    timeline_events.sort(key=lambda x: x['time'])

    context = {
        'order': order,
        'order_items': order_items,
        'queue_entry': queue_entry,
        'available_bays': available_bays,
        'available_attendants': available_attendants,
        'payment': payment,
        'payment_id': payment_id,
        'timeline_events': timeline_events,
        'title': f'Order {order.order_number}'
    }
    return render(request, 'services/order_detail.html', context)

@login_required
@employee_required()
@require_POST
def start_service(request, order_id):
    """Start service for an order"""
    order = get_object_or_404(ServiceOrder, id=order_id)
    
    # Check if order can be started
    if order.status not in ['confirmed', 'pending']:
        messages.error(request, 'Order cannot be started.')
        return redirect(get_business_url(request, 'services:order_detail', pk=order.pk))
    
    # Validate that an attendant is assigned (either from form or already assigned)
    assigned_attendant_id = request.POST.get('assigned_attendant')
    if not assigned_attendant_id and not order.assigned_attendant:
        messages.error(request, 'An employee must be assigned before starting the service.')
        return redirect(get_business_url(request, 'services:order_detail', pk=order.pk))
    
    # Update order status
    order.status = 'in_progress'
    order.actual_start_time = timezone.now()
    
    # Assign attendant from form or current user as fallback
    assigned_attendant_id = request.POST.get('assigned_attendant')
    if assigned_attendant_id:
        try:
            from apps.employees.models import Employee
            attendant = Employee.objects.get(id=assigned_attendant_id)
            order.assigned_attendant = attendant
        except Employee.DoesNotExist:
            # Fall back to current user if selected attendant doesn't exist
            if hasattr(request, 'employee') and request.employee:
                order.assigned_attendant = request.employee
    elif not order.assigned_attendant:
        # Assign current user if no attendant specified and none already assigned
        if hasattr(request, 'employee') and request.employee:
            order.assigned_attendant = request.employee
    
    order.save()
    
    # Update queue entry
    if hasattr(order, 'queue_entry'):
        queue_entry = order.queue_entry
        queue_entry.status = 'in_service'  # Fixed: should be 'in_service', not 'completed'
        queue_entry.actual_start_time = timezone.now()  # Fixed: should be start_time, not end_time
        queue_entry.save()
    
    # Assign service bay if provided
    bay_id = request.POST.get('service_bay')
    if bay_id:
        try:
            bay = ServiceBay.objects.get(id=bay_id)
            bay.assign_order(order)
        except ServiceBay.DoesNotExist:
            pass
    
    # Send service start notification
    # Ensure tenant context is set from request
    from apps.core.database_router import set_current_tenant
    from apps.core.notifications import send_order_started_notification
    
    if hasattr(request, 'tenant') and request.tenant:
        set_current_tenant(request.tenant)
    
    send_order_started_notification(
        order=order,
        attendant_name=order.assigned_attendant.full_name if order.assigned_attendant else None,
        tenant=request.tenant if hasattr(request, 'tenant') else None
    )
    
    messages.success(request, f'Service started for order {order.order_number}')
    
    # Handle AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': f'Service started for order {order.order_number}',
            'order_id': str(order.id),
            'status': order.status
        })
    
    return redirect(get_business_url(request, 'services:order_detail', pk=order.pk))
@login_required
@employee_required()
@require_POST
def complete_service(request, order_id):
    """Complete service for an order"""
    order = get_object_or_404(ServiceOrder, id=order_id)
    
    # Check if order can be completed
    if order.status != 'in_progress':
        messages.error(request, 'Order is not in progress.')
        return redirect(get_business_url(request, 'services:order_detail', pk=order.pk))
    
    # Update order status
    order.status = 'completed'
    order.actual_end_time = timezone.now()
    order.save()
    
    for item in order.order_items.all():
        if not item.completed_at:
            item.completed_at = timezone.now()
            if not item.started_at:
                item.started_at = order.actual_start_time
            item.save()
    
    # Update queue entry
    if hasattr(order, 'queue_entry'):
        queue_entry = order.queue_entry
        queue_entry.status = 'completed'
        queue_entry.actual_end_time = timezone.now()
        queue_entry.save()
    
    # Free service bay
    if hasattr(order, 'current_bay') and order.current_bay.exists():
        bay = order.current_bay.first()
        bay.complete_service()
    
    # Send completion notification
    # Send service completion notification
    # Ensure tenant context is set from request
    from apps.core.database_router import set_current_tenant
    from apps.core.notifications import send_order_completed_notification
    
    if hasattr(request, 'tenant') and request.tenant:
        set_current_tenant(request.tenant)
    
    send_order_completed_notification(
        order=order,
        attendant_name=order.assigned_attendant.full_name if order.assigned_attendant else None,
        tenant=request.tenant if hasattr(request, 'tenant') else None
    )
    
    messages.success(request, f'Service completed for order {order.order_number}')
    
    # Handle AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': f'Service completed for order {order.order_number}',
            'order_id': str(order.id),
            'status': order.status
        })
    
    return redirect(get_business_url(request, 'services:order_detail', pk=order.pk))

@login_required
# Owner or manager required for queue management
@employee_required(['owner', 'manager', 'attendant'])
def queue_view(request):
    """Service queue management"""
    # Get current queue
    queue_entries = ServiceQueue.objects.filter(
        status__in=['waiting', 'in_service']
    ).select_related('order', 'order__customer', 'order__vehicle', 'service_bay').order_by('queue_number')
    
    # Get available service bays
    service_bays = ServiceBay.objects.all().order_by('bay_number')
    
    # Calculate average wait time manually
    completed_entries = ServiceQueue.objects.filter(
        status='in_service',
        actual_start_time__isnull=False
    )
    
    total_wait_time = 0
    wait_time_count = 0
    
    for entry in completed_entries:
        if entry.actual_start_time and entry.created_at:
            wait_time = (entry.actual_start_time - entry.created_at).total_seconds() / 60
            total_wait_time += wait_time
            wait_time_count += 1
    
    avg_wait_time = total_wait_time / wait_time_count if wait_time_count > 0 else 0
    
    # Queue statistics
    stats = {
        'waiting_count': queue_entries.filter(status='waiting').count(),
        'in_service_count': queue_entries.filter(status='in_service').count(),
        'avg_wait_time': avg_wait_time,
        'available_bays': service_bays.filter(is_active=True, is_occupied=False).count(),
    }
    
    context = {
        'queue_entries': queue_entries,
        'service_bays': service_bays,
        'stats': stats,
        'title': 'Service Queue'
    }
    return render(request, 'services/queue.html', context)

def add_order_to_queue(order):
    """Add order to service queue"""
    # Get next queue number
    last_queue_number = ServiceQueue.objects.filter(
        created_at__date=timezone.now().date()
    ).aggregate(max_num=models.Max('queue_number'))['max_num'] or 0
    
    # Calculate estimated times
    estimated_duration = order.estimated_duration
    estimated_start_time = timezone.now()
    
    # Check for orders ahead in queue
    waiting_orders = ServiceQueue.objects.filter(status='waiting').count()
    if waiting_orders > 0:
        # Add buffer time based on queue length
        estimated_start_time += timedelta(minutes=waiting_orders * 30)  # 30 min average per order
    
    estimated_end_time = estimated_start_time + timedelta(minutes=estimated_duration)
    
    ServiceQueue.objects.create(
        order=order,
        queue_number=last_queue_number + 1,
        estimated_start_time=estimated_start_time,
        estimated_end_time=estimated_end_time
    )

@login_required
@employee_required()
@ajax_required
def get_service_data(request, service_id):
    """Get service data for AJAX requests"""
    service = get_object_or_404(Service, id=service_id)
    
    data = {
        'id': service.id,
        'name': service.name,
        'description': service.description,
        'base_price': float(service.base_price),
        'estimated_duration': service.estimated_duration,
        'category': service.category.name,
        'is_popular': service.is_popular,
        'compatible_vehicles': service.compatible_vehicle_types.split(',')
    }
    
    return JsonResponse(data)

@login_required
@employee_required()
@ajax_required
def queue_status_ajax(request):
    """Get current queue status for AJAX updates"""
    queue_entries = ServiceQueue.objects.filter(
        status__in=['waiting', 'in_service']
    ).select_related('order', 'order__customer').order_by('queue_number')
    
    data = {
        'queue': [
            {
                'queue_id': entry.id,
                'queue_number': entry.queue_number,
                'order_id': entry.order.id,
                'order_number': entry.order.order_number,
                'customer_name': entry.order.customer.full_name,
                'status': entry.status,
                'estimated_wait_time': entry.estimated_wait_time,
                'service_bay': entry.service_bay.name if entry.service_bay else None
            }
            for entry in queue_entries
        ],
        'timestamp': timezone.now().isoformat()
    }
    
    return JsonResponse(data)


@login_required
@employee_required()
@ajax_required
def queue_statistics_ajax(request):
    """Get queue statistics for AJAX updates"""
    today = timezone.now().date()
    
    # Calculate statistics
    total_processed = ServiceOrder.objects.filter(
        status='completed',
        actual_end_time__date=today
    ).count()
    
    # Average wait time calculation
    completed_orders = ServiceOrder.objects.filter(
        status='completed',
        actual_start_time__isnull=False,
        actual_end_time__date=today
    )
    
    total_wait_time = 0
    wait_count = 0
    for order in completed_orders:
        if order.created_at and order.actual_start_time:
            wait_time = (order.actual_start_time - order.created_at).total_seconds() / 60
            total_wait_time += wait_time
            wait_count += 1
    
    avg_wait_time = round(total_wait_time / wait_count if wait_count > 0 else 0, 1)
    
    # Efficiency calculation (services completed vs planned)
    planned_services = ServiceOrder.objects.filter(
        created_at__date=today
    ).count()
    efficiency = round((total_processed / planned_services * 100) if planned_services > 0 else 0, 1)
    
    # Customer satisfaction (average rating)
    ratings = ServiceOrder.objects.filter(
        actual_end_time__date=today,
        customer_rating__isnull=False
    ).values_list('customer_rating', flat=True)
    
    avg_rating = round(sum(ratings) / len(ratings) if ratings else 0, 1)
    satisfaction = f"{avg_rating}/5" if avg_rating > 0 else "N/A"
    
    # Current queue counts
    waiting_count = ServiceQueue.objects.filter(status='waiting').count()
    in_service_count = ServiceQueue.objects.filter(status='in_service').count()
    
    data = {
        'total_processed': total_processed,
        'avg_wait_time': avg_wait_time,
        'efficiency': efficiency,
        'satisfaction': satisfaction,
        'waiting_count': waiting_count,
        'in_service_count': in_service_count,
        'timestamp': timezone.now().isoformat()
    }
    
    return JsonResponse(data)


# Additional views to complete the services functionality

@login_required
@employee_required(['owner', 'manager'])
def service_edit_view(request, pk):
    """Edit service"""
    service = get_object_or_404(Service, pk=pk)
    
    if request.method == 'POST':
        form = ServiceForm(request.POST, request.FILES, instance=service)
        if form.is_valid():
            service = form.save()
            messages.success(request, f'Service "{service.name}" updated successfully!')
            return redirect(get_business_url(request, 'services:detail', pk=service.pk))
    else:
        form = ServiceForm(instance=service)
    
    context = {
        'form': form,
        'service': service,
        'title': f'Edit Service - {service.name}'
    }
    return render(request, 'services/service_form.html', context)

@login_required
@employee_required(['owner', 'manager'])
def service_delete_view(request, pk):
    """Delete service with proper validation"""
    service = get_object_or_404(Service, pk=pk)
    
    if request.method == 'POST':
        # Check if service is used in any active/pending orders
        active_order_items = ServiceOrderItem.objects.filter(
            service=service,
            order__status__in=['pending', 'confirmed', 'in_progress', 'paused']
        )
        active_count = active_order_items.count()
        
        # Check total usage for information
        total_order_items = ServiceOrderItem.objects.filter(service=service).count()
        
        if active_count > 0:
            # Get the order statuses for better error message
            active_orders = active_order_items.values_list('order__order_number', 'order__status').distinct()[:5]
            order_info = ', '.join([f"{order[0]} ({order[1]})" for order in active_orders])
            if active_count > 5:
                order_info += f" and {active_count - 5} more"
                
            messages.error(
                request, 
                f'Cannot delete "{service.name}" because it is used in {active_count} active order(s): {order_info}. '
                'Complete or cancel these orders first.'
            )
        else:
            # Safe to delete
            service_name = service.name
            service.delete()  # Soft delete
            
            if total_order_items > 0:
                messages.success(
                    request, 
                    f'Service "{service_name}" deleted successfully! '
                    f'Note: This service was used in {total_order_items} completed order(s) which remain in history.'
                )
            else:
                messages.success(request, f'Service "{service_name}" deleted successfully!')
        
        return redirect(get_business_url(request, 'services:list'))
    
    # Check order usage for display
    active_order_items = ServiceOrderItem.objects.filter(
        service=service,
        order__status__in=['pending', 'confirmed', 'in_progress', 'paused']
    ).count()
    total_order_items = ServiceOrderItem.objects.filter(service=service).count()
    completed_order_items = total_order_items - active_order_items
    
    context = {
        'service': service,
        'title': f'Delete Service - {service.name}',
        'active_order_items': active_order_items,
        'total_order_items': total_order_items,
        'completed_order_items': completed_order_items,
        'can_delete': active_order_items == 0
    }
    return render(request, 'services/service_confirm_delete.html', context)

@login_required
@employee_required(['owner', 'manager'])
def category_list_view(request):
    """List service categories"""
    categories = ServiceCategory.objects.filter(is_active=True).annotate(
        service_count=Count('services', filter=Q(services__is_active=True))
    ).order_by('display_order', 'name')
    
    context = {
        'categories': categories,
        'title': 'Service Categories'
    }
    return render(request, 'services/category_list.html', context)

@login_required
@employee_required(['owner', 'manager'])
def category_create_view(request):
    """Create service category"""
    if request.method == 'POST':
        form = ServiceCategoryForm(request.POST)
        if form.is_valid():
            category = form.save()
            messages.success(request, f'Category "{category.name}" created successfully!')
            return redirect(get_business_url(request, 'services:category_list'))
    else:
        form = ServiceCategoryForm()
    
    context = {
        'form': form,
        'title': 'Create Service Category'
    }
    return render(request, 'services/category_form.html', context)

@login_required
@employee_required(['owner', 'manager'])
def category_edit_view(request, pk):
    """Edit service category"""
    category = get_object_or_404(ServiceCategory, pk=pk)
    
    if request.method == 'POST':
        form = ServiceCategoryForm(request.POST, instance=category)
        if form.is_valid():
            category = form.save()
            messages.success(request, f'Category "{category.name}" updated successfully!')
            return redirect(get_business_url(request, 'services:category_list'))
    else:
        form = ServiceCategoryForm(instance=category)
    
    context = {
        'form': form,
        'category': category,
        'title': f'Edit Category - {category.name}'
    }
    return render(request, 'services/category_form.html', context)

@login_required
@employee_required()
@require_POST
def cancel_service(request, order_id):
    """Cancel service order and restore inventory if needed"""
    order = get_object_or_404(ServiceOrder, id=order_id)
    
    if not order.can_be_cancelled:
        messages.error(request, 'This order cannot be cancelled.')
        return redirect(get_business_url(request, 'services:order_detail', pk=order.pk))
    
    cancellation_reason = request.POST.get('reason', '')
    
    # Restore inventory before cancelling the order
    _restore_order_inventory(order, request.user, cancellation_reason)
    
    order.status = 'cancelled'
    order.internal_notes += f"\nCancelled by {request.employee.full_name}: {cancellation_reason}"
    order.save()
    
    # Free service bay if assigned
    if hasattr(order, 'queue_entry') and order.queue_entry.service_bay:
        bay = order.queue_entry.service_bay
        bay.complete_service()
    
    # Update queue entry
    if hasattr(order, 'queue_entry'):
        queue_entry = order.queue_entry
        queue_entry.status = 'cancelled'
        queue_entry.save()
    
    messages.success(request, f'Order {order.order_number} cancelled successfully.')
    return redirect(get_business_url(request, 'services:order_detail', pk=order.pk))

@login_required
@employee_required()
@require_POST
def pause_service(request, order_id):
    """Pause service - AJAX only"""
    # Force AJAX-only response
    is_ajax = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
        request.POST.get('ajax') == '1'
    )
    
    if not is_ajax:
        return JsonResponse({
            'success': False,
            'message': 'AJAX request required'
        }, status=400)
    
    order = get_object_or_404(ServiceOrder, id=order_id)
    
    if order.status != 'in_progress':
        return JsonResponse({
            'success': False,
            'message': 'Service is not in progress.'
        })
    
    # Change status to paused and record pause time in internal notes
    order.status = 'paused'
    order.internal_notes += f"\nPaused by {request.employee.full_name} at {timezone.now()}"
    order.save()

    return JsonResponse({
        'success': True,
        'message': 'Service paused.',
        'order_id': str(order.id),
        'status': order.status
    })

@employee_required()
@require_POST
def resume_service(request, order_id):
    """Resume paused service - AJAX only"""
    # Force AJAX-only response
    is_ajax = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
        request.POST.get('ajax') == '1'
    )
    
    if not is_ajax:
        return JsonResponse({
            'success': False,
            'message': 'AJAX request required'
        }, status=400)
    
    order = get_object_or_404(ServiceOrder, id=order_id)
    
    if order.status != 'paused':
        return JsonResponse({
            'success': False,
            'message': 'Service is not paused.'
        })
    
    # Change status back to in_progress and record resume time in internal notes
    order.status = 'in_progress'
    order.internal_notes += f"\nResumed by {request.employee.full_name} at {timezone.now()}"
    order.save()

    return JsonResponse({
        'success': True,
        'message': 'Service resumed.',
        'order_id': str(order.id),
        'status': order.status
    })

@login_required
@employee_required()
def process_payment(request, order_id):
    """Redirect to payments app for payment processing"""
    order = get_object_or_404(ServiceOrder, id=order_id)
    
    # Check if payment can be processed
    if not order.can_process_payment():
        messages.error(request, 'Payment cannot be processed for this order.')
    return redirect(get_business_url(request, 'services:order_detail', pk=order.id))
    
    # Get tenant slug for proper URL routing
    tenant_slug = request.tenant.slug
    
    # Redirect with business slug
    return redirect(get_business_url(request, 'payments:create', order_id=order.id))

@login_required
@employee_required()
def payment_receipt(request, order_id):
    """Generate payment receipt"""
    order = get_object_or_404(ServiceOrder, id=order_id)
    
    # Update payment status before showing receipt
    order.update_payment_status()
    
    # Get the latest completed payment
    latest_payment = order.latest_payment
        
    # If no payment found, redirect to payment processing
    if not latest_payment:
        messages.warning(request, 'No completed payment found for this order.')
        tenant_slug = request.tenant.slug
    return redirect(get_business_url(request, 'payments:create', order_id=order.id))
    
    context = {
        'order': order,
        'payment': latest_payment,
        'payment_summary': order.get_payment_summary(),
        'title': f'Receipt - {order.order_number}',
        'print_mode': request.GET.get('print') == 'true'
    }
    
    return render(request, 'services/payment_receipt_print.html', context)

# ✅ Updated ServiceOrder model method
def update_payment_status(self):
    """Update order payment status"""
    try:
        from apps.payments.models import Payment
        from decimal import Decimal
        from django.db import transaction
        
        # Use transaction to ensure consistency
        with transaction.atomic():
            # Get all completed payments for this order
            completed_payments = Payment.objects.filter(
                service_order=self,
                status__in=['completed', 'verified']
            )
            
            total_paid = completed_payments.aggregate(
                total=models.Sum('amount')
            )['total'] or Decimal('0')
            
            # Store previous status for comparison
            old_status = self.payment_status
            
            # Update payment status
            if total_paid >= self.total_amount:
                self.payment_status = 'paid'
            elif total_paid > 0:
                self.payment_status = 'partial'
            else:
                self.payment_status = 'pending'
            
            # Set payment method from latest payment
            latest_payment = completed_payments.order_by('-completed_at').first()
            if latest_payment:
                self.payment_method = latest_payment.payment_method.method_type
                
                # Update payment date when status changes to paid
                if self.payment_status == 'paid' and old_status != 'paid':
                    self.payment_date = latest_payment.completed_at
            
            # Save with specific fields to avoid conflicts
            self.save(update_fields=['payment_status', 'payment_method', 'payment_date'])
            
            # ✅ Trigger any post-payment processing
            if self.payment_status == 'paid' and old_status != 'paid':
                self._handle_payment_completion()
        
        return True
        
    except ImportError:
        # Payments app not available
        return False
    except Exception as e:
        # Log error but don't crash
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error updating payment status for order {self.id}: {str(e)}")
        return False

def _handle_payment_completion(self):
    """Handle actions when payment is completed"""
    try:
        # Update order status if needed
        if self.status == 'pending':
            self.status = 'in_progress'
            self.save(update_fields=['status'])
        
        # Send notifications, update inventory, etc.
        # Add your business logic here
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in payment completion handler for order {self.id}: {str(e)}")

@login_required
@employee_required()
def attendant_dashboard(request):
    """Attendant dashboard with comprehensive service data"""
    from apps.businesses.utils import get_orders_for_date
    
    today = timezone.now().date()
    employee = request.employee
    
    # Get orders assigned to this attendant OR created by them
    my_orders = ServiceOrder.objects.filter(
        Q(assigned_attendant=employee) | Q(created_by_id=request.user.id),
        status__in=['confirmed', 'in_progress']
    ).select_related('customer', 'vehicle', 'assigned_attendant').order_by('-created_at')
    
    # Get queue entries for today
    today_queue = ServiceQueue.objects.filter(
        created_at__date=today,
        status__in=['waiting', 'in_service']
    ).select_related('order', 'order__customer').order_by('queue_number')
    
    # Get my service items in progress (services specifically assigned to me)
    my_service_items = ServiceOrderItem.objects.filter(
        assigned_to=employee,
        completed_at__isnull=True
    ).select_related('order', 'service', 'order__customer', 'order__vehicle').order_by('started_at', 'order__created_at')
    
    # Enhanced Statistics - Show both personal and overall data
    today_orders = get_orders_for_date(today)
    
    # Personal stats (orders I created or am assigned to) - use datetime range to avoid timezone issues
    from django.utils import timezone as tz
    today_start = tz.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + tz.timedelta(days=1)
    
    my_orders_today = ServiceOrder.objects.filter(
        Q(assigned_attendant=employee) | Q(created_by_id=request.user.id),
        created_at__range=[today_start, today_end]
    )
    
    # Overall business stats for today (more relevant for dashboard)
    stats = {
        # Personal metrics
        'orders_today': my_orders_today.count(),
        'completed_today': my_orders_today.filter(
            status='completed',
            actual_end_time__range=[today_start, today_end]
        ).count(),
        'in_progress_today': my_orders.filter(status='in_progress').count(),
        
        # Business-wide revenue (more meaningful than just personal revenue)
        'total_revenue_today': today_orders.filter(
            status__in=['completed', 'confirmed']
        ).aggregate(total=Sum('total_amount'))['total'] or 0,
        
        # Additional useful stats
        'my_service_items_pending': my_service_items.count(),
        'queue_length': today_queue.count(),
        
        # Overall business metrics for context
        'total_orders_today': today_orders.count(),
        'total_completed_today': today_orders.filter(status='completed').count(),
        'total_in_progress': today_orders.filter(status='in_progress').count()
    }
    
    # Get current hour for greeting
    current_hour = timezone.now().hour
    if current_hour < 12:
        greeting_time = "Morning"
    elif current_hour < 17:
        greeting_time = "Afternoon"
    else:
        greeting_time = "Evening"
    
    context = {
        'my_orders': my_orders,
        'today_queue': today_queue,
        'my_service_items': my_service_items,
        'stats': stats,
        'greeting_time': greeting_time,
        'title': 'My Dashboard'
    }
    return render(request, 'services/attendant_dashboard.html', context)

@login_required
@employee_required()
def my_services_view(request):
    """View services/orders created by the current employee"""
    # Filter orders created by the current employee (not assigned to them)
    my_orders = ServiceOrder.objects.filter(
        created_by_id=request.user.id
    ).select_related('customer', 'vehicle', 'assigned_attendant').order_by('-created_at')
    
    # Filters
    status = request.GET.get('status')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if status:
        my_orders = my_orders.filter(status=status)
    if date_from:
        my_orders = my_orders.filter(created_at__date__gte=date_from)
    if date_to:
        my_orders = my_orders.filter(created_at__date__lte=date_to)
    
    # Pagination
    paginator = Paginator(my_orders, 20)
    page = request.GET.get('page')
    orders_page = paginator.get_page(page)
    
    context = {
        'orders': orders_page,
        'status_choices': ServiceOrder.STATUS_CHOICES,
        'current_filters': {
            'status': status,
            'date_from': date_from,
            'date_to': date_to
        },
        'title': 'My Services'
    }
    return render(request, 'services/my_services.html', context)

@login_required
@employee_required()
@ajax_required
def quick_customer_register(request):
    """Quick customer registration via AJAX"""
    if request.method == 'POST':
        try:
            from apps.customers.models import Customer, Vehicle
            
            # Customer data
            first_name = request.POST.get('first_name')
            last_name = request.POST.get('last_name')
            phone = request.POST.get('phone')
            
            # Vehicle data
            registration = request.POST.get('registration')
            make = request.POST.get('make')
            model = request.POST.get('model')
            color = request.POST.get('color')
            vehicle_type = request.POST.get('vehicle_type', 'sedan')
            
            with transaction.atomic():
                # Create customer
                customer = Customer.objects.create(
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone,
                    customer_id=generate_unique_code('CUST', 6),
                    created_by=request.user
                )
                
                # Create vehicle
                vehicle = Vehicle.objects.create(
                    customer=customer,
                    registration_number=registration.upper(),
                    make=make,
                    model=model,
                    color=color,
                    vehicle_type=vehicle_type,
                    year=timezone.now().year,
                    created_by=request.user
                )
                
                return JsonResponse({
                    'success': True,
                    'customer': {
                        'id': str(customer.id),
                        'name': customer.full_name,
                        'phone': str(customer.phone)
                    },
                    'vehicle': {
                        'id': str(vehicle.id),
                        'registration': vehicle.registration_number,
                        'full_name': vehicle.full_name
                    }
                })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
@employee_required()
@ajax_required
def customer_search_ajax(request):
    """Search customers via AJAX"""
    query = request.GET.get('q', '')
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    from apps.customers.models import Customer
    
    customers = Customer.objects.filter(
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(phone__icontains=query) |
        Q(customer_id__icontains=query),
        is_active=True
    )[:10]
    
    results = [
        {
            'id': str(customer.id),
            'text': f"{customer.full_name} - {customer.phone}",
            'name': customer.full_name,
            'phone': str(customer.phone),
            'customer_id': customer.customer_id
        }
        for customer in customers
    ]
    
    return JsonResponse({'results': results})

@login_required
@employee_required()
@ajax_required
def vehicle_search_ajax(request):
    """Search vehicles via AJAX"""
    query = request.GET.get('q', '')
    customer_id = request.GET.get('customer_id')
    
    from apps.customers.models import Vehicle
    
    vehicles = Vehicle.objects.filter(is_active=True)
    
    if customer_id:
        vehicles = vehicles.filter(customer_id=customer_id)
    
    if query:
        vehicles = vehicles.filter(
            Q(registration_number__icontains=query) |
            Q(make__icontains=query) |
            Q(model__icontains=query)
        )
    
    vehicles = vehicles.select_related('customer')[:10]
    
    results = [
        {
            'id': str(vehicle.id),
            'text': f"{vehicle.registration_number} - {vehicle.full_name}",
            'registration': vehicle.registration_number,
            'make': vehicle.make,
            'model': vehicle.model,
            'color': vehicle.color,
            'customer_name': vehicle.customer.full_name
        }
        for vehicle in vehicles
    ]
    
    return JsonResponse({'results': results})

@login_required
@employee_required()
@ajax_required
def start_next_service(request):
    """Start next service in queue"""
    if request.method == 'POST':
        # Get next waiting order for this attendant or any unassigned order
        next_order = ServiceOrder.objects.filter(
            Q(assigned_attendant=request.employee) | Q(assigned_attendant__isnull=True),
            status='confirmed'
        ).order_by('priority', 'created_at').first()
        
        if next_order:
            next_order.status = 'in_progress'
            next_order.actual_start_time = timezone.now()
            next_order.assigned_attendant = request.employee
            next_order.save()
            
            # Update queue entry
            if hasattr(next_order, 'queue_entry'):
                queue_entry = next_order.queue_entry
                queue_entry.status = 'in_service'
                queue_entry.actual_start_time = timezone.now()
                queue_entry.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Started service for order {next_order.order_number}',
                'redirect_url': reverse('services:order_detail', kwargs={'pk': next_order.pk})
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'No orders in queue'
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
@employee_required()
@ajax_required
def get_current_service(request):
    """Get current service for attendant"""
    current_service = ServiceOrder.objects.filter(
        assigned_attendant=request.employee,
        status='in_progress'
    ).first()
    
    if current_service:
        return JsonResponse({
            'current_service': {
                'id': str(current_service.id),
                'order_number': current_service.order_number,
                'customer_name': current_service.customer.full_name
            }
        })
    else:
        return JsonResponse({'current_service': None})

@login_required
@employee_required()
@ajax_required
def calculate_order_price(request):
    """Calculate order price via AJAX"""
    service_ids = request.POST.getlist('service_ids[]')
    quantities = request.POST.getlist('quantities[]')
    
    total_price = 0
    estimated_duration = 0
    
    for i, service_id in enumerate(service_ids):
        try:
            service = Service.objects.get(id=service_id)
            quantity = Decimal(str(quantities[i])) if i < len(quantities) else Decimal('1')
            
            total_price += service.base_price * quantity
            estimated_duration += service.estimated_duration * quantity
        except (Service.DoesNotExist, ValueError, InvalidOperation):
            continue
    
    # Prices are VAT inclusive (16% VAT for Kenya)
    # Calculate VAT amount from inclusive price
    tax_amount = total_price * Decimal('0.16') / Decimal('1.16')
    subtotal = total_price - tax_amount
    
    return JsonResponse({
        'subtotal': float(subtotal),
        'tax_amount': float(tax_amount),
        'total_amount': float(total_price),  # This is already VAT inclusive
        'estimated_duration': estimated_duration
    })

@login_required
@employee_required(['owner', 'manager'])
def service_reports_view(request):
    """Service reports and analytics"""
    # Date range filters
    date_from = request.GET.get('date_from', (timezone.now() - timedelta(days=30)).date())
    date_to = request.GET.get('date_to', timezone.now().date())
    
    # Service performance
    service_performance = Service.objects.filter(
        is_active=True
    ).annotate(
        total_orders=Count('order_items'),
        total_revenue=Sum('order_items__total_price'),
        avg_rating=Avg('order_items__rating')
    ).order_by('-total_revenue')
    
    # Daily revenue
    daily_revenue = ServiceOrder.objects.filter(
        status='completed',
        actual_end_time__date__range=[date_from, date_to]
    ).extra(
        select={'day': 'DATE(actual_end_time)'}
    ).values('day').annotate(
        revenue=Sum('total_amount'),
        orders=Count('id')
    ).order_by('day')
    
    # Top customers
    top_customers = ServiceOrder.objects.filter(
        status='completed',
        created_at__date__range=[date_from, date_to]
    ).values(
        'customer__first_name',
        'customer__last_name'
    ).annotate(
        total_spent=Sum('total_amount'),
        order_count=Count('id')
    ).order_by('-total_spent')[:10]
    
    context = {
        'service_performance': service_performance,
        'daily_revenue': daily_revenue,
        'top_customers': top_customers,
        'date_from': date_from,
        'date_to': date_to,
        'title': 'Service Reports'
    }
    return render(request, 'services/reports.html', context)


# Service Management Views
@login_required
@employee_required(['owner', 'manager'])
def service_edit_view(request, pk):
    """Edit service"""
    service = get_object_or_404(Service, pk=pk)
    
    if request.method == 'POST':
        form = ServiceForm(request.POST, request.FILES, instance=service)
        if form.is_valid():
            service = form.save()
            messages.success(request, f'Service "{service.name}" updated successfully!')
            return redirect(get_business_url(request, 'services:detail', pk=service.pk))
    else:
        form = ServiceForm(instance=service)
    
    context = {
        'form': form,
        'service': service,
        'title': f'Edit Service - {service.name}'
    }
    return render(request, 'services/service_form.html', context)

@login_required
@employee_required(['owner', 'manager'])
# Category Management Views

@login_required
@employee_required(['owner', 'manager'])
def category_list_view(request):
    categories = ServiceCategory.objects.filter(is_active=True).annotate(
        total_services=Count('services', filter=Q(services__is_active=True)),
        active_services_count=Count('services', filter=Q(services__is_active=True))
    ).order_by('display_order', 'name')
    
    # Calculate overall statistics
    total_categories = categories.count()
    total_services = Service.objects.filter(is_active=True, category__in=categories).count()
    
    context = {
        'categories': categories,
        'total_categories': total_categories,
        'total_services': total_services,
        'title': 'Service Categories'
    }
    return render(request, 'services/category_list.html', context)

@login_required
@employee_required(['owner', 'manager'])
def category_create_view(request):
    """Create service category"""
    if request.method == 'POST':
        form = ServiceCategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.created_by = request.user
            category.save()
            messages.success(request, f'Category "{category.name}" created successfully!')
            return redirect(get_business_url(request, 'services:category_list'))
    else:
        form = ServiceCategoryForm()
    
    context = {
        'form': form,
        'title': 'Create Service Category'
    }
    return render(request, 'services/category_form.html', context)

@login_required
@employee_required(['owner', 'manager'])
def category_edit_view(request, pk):
    """Edit service category"""
    category = get_object_or_404(ServiceCategory, pk=pk)
    
    if request.method == 'POST':
        form = ServiceCategoryForm(request.POST, instance=category)
        if form.is_valid():
            category = form.save()
            messages.success(request, f'Category "{category.name}" updated successfully!')
            return redirect(get_business_url(request, 'services:category_list'))
    else:
        form = ServiceCategoryForm(instance=category)
    
    # Get category statistics
    category.total_services = category.services.filter(is_active=True).count()
    category.active_services_count = category.services.filter(is_active=True).count()
    
    context = {
        'form': form,
        'category': category,
        'title': f'Edit Category - {category.name}'
    }
    return render(request, 'services/category_form.html', context)

@login_required
@employee_required(['owner', 'manager'])
@require_POST
@ajax_required
def category_toggle_status(request, pk):
    """Toggle category active status"""
    category = get_object_or_404(ServiceCategory, pk=pk)
    
    try:
        data = json.loads(request.body)
        category.is_active = data.get('is_active', not category.is_active)
        category.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Category {"activated" if category.is_active else "deactivated"} successfully'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })

@login_required
@employee_required(['owner', 'manager'])
@require_POST
@ajax_required
def category_delete(request, pk):
    """Delete service category (only if no services)"""
    category = get_object_or_404(ServiceCategory, pk=pk)
    
    # Check if category has services
    if category.services.exists():
        return JsonResponse({
            'success': False,
            'message': 'Cannot delete category with existing services'
        })
    
    try:
        category_name = category.name
        category.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Category "{category_name}" deleted successfully'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })
# Order Management Views
@login_required
@employee_required()
@login_required
@employee_required()
def order_edit_view(request, pk):
    """Edit service order - handles both services and inventory items"""
    order = get_object_or_404(ServiceOrder, pk=pk)
    
    # Only allow editing pending/confirmed orders
    if order.status not in ['pending', 'confirmed']:
        messages.error(request, 'This order cannot be edited.')
        return redirect('/business/{}/services/orders/{}/'.format(request.tenant.slug, order.pk))
    
    if request.method == 'POST':
        try:
            # Update basic order fields
            order.priority = request.POST.get('priority', 'normal')
            order.special_instructions = request.POST.get('special_instructions', '').strip()
            
            # Handle assigned attendant
            attendant_id = request.POST.get('assigned_attendant')
            if attendant_id:
                try:
                    from apps.employees.models import Employee
                    order.assigned_attendant = Employee.objects.get(id=attendant_id)
                except Employee.DoesNotExist:
                    order.assigned_attendant = None
            else:
                order.assigned_attendant = None
            
            # Handle scheduled date and time
            scheduled_date = request.POST.get('scheduled_date')
            scheduled_time = request.POST.get('scheduled_time')
            if scheduled_date:
                order.scheduled_date = scheduled_date
            if scheduled_time:
                order.scheduled_time = scheduled_time
            
            # Clear existing order items (both services and inventory)
            order.order_items.all().delete()
            
            total_amount = Decimal('0')
            
            # Handle services selection with custom pricing and quantities
            selected_services = request.POST.getlist('services')
            if selected_services:
                for service_id in selected_services:
                    try:
                        service = Service.objects.get(id=service_id)
                        
                        # Get custom quantity and price for this service
                        quantity_key = f'service_quantity_{service_id}'
                        price_key = f'service_price_{service_id}'
                        
                        quantity = Decimal(str(request.POST.get(quantity_key, '1')))
                        custom_price = request.POST.get(price_key)
                        unit_price = Decimal(str(custom_price)) if custom_price else service.base_price
                        
                        # Validate custom price is not below minimum if set
                        if custom_price and unit_price < service.minimum_price:
                            logger.warning(f"Custom price {unit_price} for service {service.name} is below minimum {service.minimum_price}")
                            unit_price = service.minimum_price
                        
                        item_total = unit_price * quantity
                        ServiceOrderItem.objects.create(
                            order=order,
                            service=service,
                            quantity=quantity,
                            unit_price=unit_price,
                            total_price=item_total
                        )
                        total_amount += item_total
                    except (Service.DoesNotExist, ValueError, InvalidOperation):
                        continue
            
            # Handle inventory items selection with custom pricing and decimal quantities
            selected_inventory = request.POST.getlist('inventory_items')
            if selected_inventory:
                from apps.inventory.models import InventoryItem
                for inventory_id in selected_inventory:
                    try:
                        inventory_item = InventoryItem.objects.get(id=inventory_id)
                        
                        # Get quantity and custom price for this inventory item
                        quantity_key = f'inventory_quantity_{inventory_id}'
                        price_key = f'inventory_price_{inventory_id}'
                        
                        quantity = Decimal(str(request.POST.get(quantity_key, '1')))
                        custom_price = request.POST.get(price_key)
                        unit_price = Decimal(str(custom_price)) if custom_price else inventory_item.selling_price
                        
                        # Check stock availability for decimal quantities
                        if inventory_item.current_stock >= quantity:
                            item_total = unit_price * quantity
                            ServiceOrderItem.objects.create(
                                order=order,
                                inventory_item=inventory_item,
                                quantity=quantity,
                                unit_price=unit_price,
                                total_price=item_total
                            )
                            total_amount += item_total
                        else:
                            messages.warning(request, f'Insufficient stock for {inventory_item.name}. Available: {inventory_item.current_stock}')
                    except (InventoryItem.DoesNotExist, ValueError, InvalidOperation):
                        continue
            
            # Calculate totals (VAT inclusive pricing)
            if total_amount > 0:
                # Price includes VAT - extract it
                vat_amount = total_amount * Decimal('0.16') / Decimal('1.16')
                subtotal = total_amount - vat_amount
                
                order.subtotal = subtotal
                order.tax_amount = vat_amount
                order.total_amount = total_amount
            else:
                order.subtotal = Decimal('0')
                order.tax_amount = Decimal('0')
                order.total_amount = Decimal('0')
            
            order.save()
            
            messages.success(request, f'Order {order.order_number} updated successfully!')
            return redirect('/business/{}/services/orders/{}/'.format(request.tenant.slug, order.pk))
            
        except Exception as e:
            logger.error(f"Exception in order edit: {str(e)}")
            messages.error(request, f'Error updating order: {str(e)}')
    
    # Get data for template
    service_categories = ServiceCategory.objects.filter(is_active=True).prefetch_related(
        'services'
    ).annotate(
        services_count=Count('services', filter=Q(services__is_active=True))
    ).filter(services_count__gt=0)
    
    # Get inventory items for selection
    from apps.inventory.models import InventoryItem, InventoryCategory
    inventory_categories = InventoryCategory.objects.filter(is_active=True).prefetch_related(
        'items'
    ).annotate(
        items_count=Count('items', filter=Q(items__is_active=True, items__current_stock__gt=0))
    ).filter(items_count__gt=0)
    
    # Get employees for assignment
    from apps.employees.models import Employee
    employees = Employee.objects.filter(
        role__in=['attendant', 'supervisor', 'manager', 'cleaner'],
        is_active=True
    )
    
    context = {
        'order': order,
        'service_categories': service_categories,
        'inventory_categories': inventory_categories,
        'employees': employees,
        'title': f'Edit Order - {order.order_number}'
    }
    return render(request, 'services/order_form.html', context)

@login_required
@employee_required()
def order_print_view(request, pk):
    """Print order details"""
    order = get_object_or_404(ServiceOrder, pk=pk)
    order_items = order.order_items.all().select_related('service')
    
    # Generate QR code for order details URL
    business_slug = request.tenant.slug
    order_detail_url = f"{request.scheme}://{request.get_host()}/business/{business_slug}/services/orders/{order.id}/"
    qr_code_image = generate_qr_code_base64(order_detail_url, size=2, border=1)
    
    context = {
        'order': order,
        'order_items': order_items,
        'qr_code_image': qr_code_image,
        'order_detail_url': order_detail_url,
        'title': f'Print Order - {order.order_number}'
    }
    return render(request, 'services/order_print.html', context)

# Service Action Views
@login_required
@employee_required()
@require_POST
def cancel_service(request, order_id):
    """Cancel service order and restore inventory if needed"""
    order = get_object_or_404(ServiceOrder, id=order_id)
    
    if not order.can_be_cancelled:
        messages.error(request, 'This order cannot be cancelled.')
        return redirect(get_business_url(request, 'services:order_detail', pk=order.pk))
    
    cancellation_reason = request.POST.get('reason', '')
    
    # Restore inventory before cancelling the order
    _restore_order_inventory(order, request.user, cancellation_reason)
    
    order.status = 'cancelled'
    order.internal_notes += f"\nCancelled by {request.employee.full_name}: {cancellation_reason}"
    order.save()
    
    # Free service bay if assigned
    if hasattr(order, 'current_bay') and order.current_bay.exists():
        bay = order.current_bay.first()
        bay.complete_service()
    
    # Update queue entry
    if hasattr(order, 'queue_entry'):
        queue_entry = order.queue_entry
        queue_entry.status = 'cancelled'
        queue_entry.save()
    
    messages.success(request, f'Order {order.order_number} cancelled successfully.')
    return redirect(get_business_url(request, 'services:order_detail', pk=order.pk))

@login_required
@employee_required()
@require_POST
def resume_service(request, order_id):
    """Resume paused service"""
    order = get_object_or_404(ServiceOrder, id=order_id)
    
    if order.status != 'in_progress':
        messages.error(request, 'Service is not paused.')
        return redirect(get_business_url(request, 'services:order_detail', pk=order.pk))
    
    order.internal_notes += f"\nResumed by {request.employee.full_name} at {timezone.now()}"
    order.save()
    
    messages.success(request, 'Service resumed.')
    return redirect(get_business_url(request, 'services:order_detail', pk=order.pk))

# Payment Views
@login_required
@employee_required()
def process_payment(request, order_id):
    """Process payment for order"""
    order = get_object_or_404(ServiceOrder, id=order_id)
    
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        amount_received = Decimal(request.POST.get('amount_received', '0'))
        
        if amount_received >= order.total_amount:
            order.payment_status = 'paid'
            order.payment_method = payment_method
            order.save()
            
            messages.success(request, 'Payment processed successfully!')
            return redirect('services:payment_receipt', order_id=order.id)
        else:
            order.payment_status = 'partial'
            order.save()
            messages.warning(request, f'Partial payment received. Balance: KES {order.total_amount - amount_received}')
    
    context = {
        'order': order,
        'title': f'Process Payment - {order.order_number}'
    }
    return render(request, 'services/process_payment.html', context)

@login_required
@employee_required()
def payment_receipt(request, order_id):
    """Generate payment receipt"""
    order = get_object_or_404(ServiceOrder, id=order_id)
    
    context = {
        'order': order,
        'title': f'Receipt - {order.order_number}',
        'print_mode': request.GET.get('print') == 'true'
    }
    return render(request, 'services/payment_receipt.html', context)

# Queue Management Views
@login_required
@employee_required()
@require_POST
def update_queue(request):
    """Update queue order"""
    queue_entries = request.POST.getlist('queue_order[]')
    
    for index, queue_id in enumerate(queue_entries):
        try:
            queue_entry = ServiceQueue.objects.get(id=queue_id)
            queue_entry.queue_number = index + 1
            queue_entry.save()
        except ServiceQueue.DoesNotExist:
            continue
    
    messages.success(request, 'Queue order updated successfully!')
    return redirect('services:queue')

@login_required
@employee_required()
@require_POST
def update_queue_priority(request, queue_id):
    """Update queue entry priority"""
    queue_entry = get_object_or_404(ServiceQueue, id=queue_id)
    priority = request.POST.get('priority')
    
    if priority in ['low', 'normal', 'high', 'urgent']:
        queue_entry.order.priority = priority
        queue_entry.order.save()
        messages.success(request, 'Priority updated successfully!')
    else:
        messages.error(request, 'Invalid priority level.')
    
    return redirect('services:queue')

# Service Package Views
@login_required
@employee_required(['owner', 'manager'])
def package_list_view(request):
    """List service packages"""
    packages = ServicePackage.objects.filter(is_active=True).prefetch_related(
        'services'  
    ).order_by('name')
    
    context = {
        'packages': packages,
        'title': 'Service Packages'
    }
    return render(request, 'services/package_list.html', context)
@login_required
@employee_required(['owner', 'manager'])
def package_create_view(request):
    """Create service package"""
    if request.method == 'POST':
        form = ServicePackageForm(request.POST, request.FILES)
        if form.is_valid():
            package = form.save()
            messages.success(request, f'Package "{package.name}" created successfully!')
            return redirect(get_business_url(request, 'services:package_detail', pk=package.pk))
    else:
        form = ServicePackageForm()
    
    context = {
        'form': form,
        'title': 'Create Service Package'
    }
    return render(request, 'services/package_form.html', context)

@login_required
@employee_required()
def package_detail_view(request, pk):
    """Service package detail"""
    package = get_object_or_404(ServicePackage, pk=pk)
    package_services = package.packageservice_set.all().select_related('service')
    
    context = {
        'package': package,
        'package_services': package_services,
        'title': f'Package - {package.name}'
    }
    return render(request, 'services/package_detail.html', context)

@login_required
@employee_required(['owner', 'manager'])
def package_edit_view(request, pk):
    """Edit service package"""
    package = get_object_or_404(ServicePackage, pk=pk)
    
    if request.method == 'POST':
        form = ServicePackageForm(request.POST, request.FILES, instance=package)
        if form.is_valid():
            package = form.save()
            messages.success(request, f'Package "{package.name}" updated successfully!')
            return redirect(get_business_url(request, 'services:package_detail', pk=package.pk))
    else:
        form = ServicePackageForm(instance=package)
    
    context = {
        'form': form,
        'package': package,
        'title': f'Edit Package - {package.name}'
    }
    return render(request, 'services/package_form.html', context)

# Service Bay Views
@login_required
@employee_required(['owner', 'manager'])
def bay_list_view(request):
    """List service bays"""
    bays = ServiceBay.objects.all().order_by('bay_number')
    
    context = {
        'bays': bays,
        'title': 'Service Bays'
    }
    return render(request, 'services/bay_list.html', context)

@login_required
@employee_required(['owner', 'manager'])
def bay_create_view(request):
    """Create service bay"""
    if request.method == 'POST':
        # Simple form handling - you might want to create a proper form class
        name = request.POST.get('name')
        bay_number = request.POST.get('bay_number')
        description = request.POST.get('description', '')
        max_vehicle_size = request.POST.get('max_vehicle_size', 'any')
        
        try:
            bay = ServiceBay.objects.create(
                name=name,
                bay_number=int(bay_number),
                description=description,
                max_vehicle_size=max_vehicle_size,
                has_pressure_washer=request.POST.get('has_pressure_washer') == 'on',
                has_vacuum=request.POST.get('has_vacuum') == 'on',
                has_lift=request.POST.get('has_lift') == 'on',
                has_drainage=request.POST.get('has_drainage') == 'on'
            )
            messages.success(request, f'Service bay "{bay.name}" created successfully!')
           
            return redirect(get_business_url(request, 'services:bay_list'))
        except Exception as e:
            messages.error(request, f'Error creating service bay: {str(e)}')
    
    context = {
        'title': 'Create Service Bay'
    }
    return render(request, 'services/bay_form.html', context)

@login_required
@employee_required(['owner', 'manager'])
def bay_edit_view(request, pk):
    """Edit service bay"""
    bay = get_object_or_404(ServiceBay, pk=pk)
    
    if request.method == 'POST':
        bay.name = request.POST.get('name', bay.name)
        bay.description = request.POST.get('description', bay.description)
        bay.max_vehicle_size = request.POST.get('max_vehicle_size', bay.max_vehicle_size)
        bay.has_pressure_washer = request.POST.get('has_pressure_washer') == 'on'
        bay.has_vacuum = request.POST.get('has_vacuum') == 'on'
        bay.has_lift = request.POST.get('has_lift') == 'on'
        bay.has_drainage = request.POST.get('has_drainage') == 'on'
        bay.is_active = request.POST.get('is_active') == 'on'
        bay.save()
        
        messages.success(request, f'Service bay "{bay.name}" updated successfully!')
        return redirect(get_business_url(request, 'services:bay_list'))

    
    context = {
        'bay': bay,
        'title': f'Edit Service Bay - {bay.name}'
    }
    return render(request, 'services/bay_form.html', context)

@login_required
@employee_required()
@require_POST
def assign_bay(request, pk):
    """Assign service bay to order"""
    bay = get_object_or_404(ServiceBay, pk=pk)
    order_id = request.POST.get('order_id')
    
    if not order_id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Order ID is required'})
        messages.error(request, 'Order ID is required.')
        return redirect('services:queue')
    
    if not bay.is_available:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Service bay is not available'})
        messages.error(request, 'Service bay is not available.')
        return redirect('services:queue')
    
    try:
        order = ServiceOrder.objects.get(id=order_id)
        bay.assign_order(order)
        
        # Update queue entry if exists
        if hasattr(order, 'queue_entry'):
            queue_entry = order.queue_entry
            queue_entry.service_bay = bay
            queue_entry.save()
        
        message = f'Order {order.order_number} assigned to {bay.name}'
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': message})
        
        messages.success(request, message)
        return redirect(get_business_url(request, 'services:order_detail', pk=order.pk))
        
    except ServiceOrder.DoesNotExist:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Order not found'})
        messages.error(request, 'Order not found.')
        return redirect('services:queue')
    except Exception as e:
        logger.error(f"Error assigning bay: {str(e)}", exc_info=True)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'An error occurred while assigning the bay'})
        messages.error(request, 'An error occurred while assigning the bay.')
        return redirect('services:queue')
    
# Assign Bay to Order View
@login_required
@employee_required()
@require_POST  
def assign_bay_to_order(request, order_id):
    """Assign service bay to a specific order"""
    order = get_object_or_404(ServiceOrder, id=order_id)
    bay_id = request.POST.get('bay_id')
    
    if not bay_id:
        return JsonResponse({'success': False, 'message': 'Bay ID is required'})
    
    try:
        bay = ServiceBay.objects.get(id=bay_id, is_active=True, is_occupied=False)
        bay.assign_order(order)
        
        # Update queue entry if exists
        if hasattr(order, 'queue_entry'):
            queue_entry = order.queue_entry
            queue_entry.service_bay = bay
            queue_entry.save()
        
        return JsonResponse({
            'success': True, 
            'message': f'Order {order.order_number} assigned to {bay.name}'
        })
        
    except ServiceBay.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Service bay not found or unavailable'})
    except Exception as e:
        logger.error(f"Error assigning bay to order: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'message': 'An error occurred while assigning the bay'})

# Rating and Feedback Views
@login_required
@employee_required()
def rate_service(request, order_id):
    """Rate completed service"""
    order = get_object_or_404(ServiceOrder, id=order_id)
    
    if order.status != 'completed':
        messages.error(request, 'Order must be completed to rate.')
        return redirect(get_business_url(request, 'services:order_detail', pk=order.pk))
    
    if request.method == 'POST':
        form = ServiceRatingForm(request.POST)
        if form.is_valid():
            order.customer_rating = form.cleaned_data['overall_rating']
            order.customer_feedback = form.cleaned_data.get('comments', '')
            order.save()
            
            messages.success(request, 'Thank you for your feedback!')
            return redirect(get_business_url(request, 'services:order_detail', pk=order.pk))
    else:
        form = ServiceRatingForm()
    
    context = {
        'form': form,
        'order': order,
        'title': f'Rate Service - {order.order_number}'
    }
    return render(request, 'services/rate_service.html', context)

@login_required
@employee_required()
def service_feedback(request, order_id):
    """View service feedback"""
    order = get_object_or_404(ServiceOrder, id=order_id)
    
    context = {
        'order': order,
        'title': f'Feedback - {order.order_number}'
    }
    return render(request, 'services/service_feedback.html', context)

# Reports and Analytics Views
@login_required
@employee_required(['owner', 'manager'])
def service_reports_view(request):
    """Service reports and analytics"""
    date_from = request.GET.get('date_from', (timezone.now() - timedelta(days=30)).date())
    date_to = request.GET.get('date_to', timezone.now().date())
    
    # Service performance
    service_performance = Service.objects.filter(
        is_active=True
    ).annotate(
        total_orders=Count('order_items'),
        total_revenue=Sum('order_items__total_price'),
        avg_rating=Avg('order_items__rating')
    ).order_by('-total_revenue')
    
    # Daily revenue
    daily_revenue = ServiceOrder.objects.filter(
        status='completed',
        actual_end_time__date__range=[date_from, date_to]
    ).extra(
        select={'day': 'DATE(actual_end_time)'}
    ).values('day').annotate(
        revenue=Sum('total_amount'),
        orders=Count('id')
    ).order_by('day')
    
    context = {
        'service_performance': service_performance,
        'daily_revenue': daily_revenue,
        'date_from': date_from,
        'date_to': date_to,
        'title': 'Service Reports'
    }
    return render(request, 'services/reports.html', context)

@login_required
@employee_required(['owner', 'manager'])
def daily_service_report(request):
    """Daily service report"""
    date = request.GET.get('date', timezone.now().date())
    
    # Filter out cancelled orders
    orders = ServiceOrder.objects.filter(
        created_at__date=date
    ).exclude(status='cancelled').select_related('customer', 'vehicle', 'assigned_attendant')
    
    # Calculate revenue from completely paid orders only
    total_revenue = Decimal('0.00')
    
    try:
        from apps.payments.models import Payment
        
        for order in orders:
            # Get total payments for this order (excluding refunds)
            total_payments = Payment.objects.filter(
                service_order=order,
                status__in=['completed', 'verified', 'paid', 'success']
            ).exclude(
                payment_type='refund'
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
            
            # Check if order is completely paid
            order_total = order.total_amount or Decimal('0.00')
            if total_payments >= order_total:
                total_revenue += order_total
    except:
        # Fallback to completed orders if Payment model not available
        total_revenue = orders.filter(status='completed').aggregate(
            total=Sum('total_amount')
        )['total'] or 0
    
    stats = {
        'total_orders': orders.count(),
        'completed_orders': orders.filter(status='completed').count(),
        'total_revenue': total_revenue,
        'avg_service_time': orders.filter(
            status='completed',
            actual_start_time__isnull=False,
            actual_end_time__isnull=False
        ).extra(
            select={'duration_minutes': "TIMESTAMPDIFF(MINUTE, actual_start_time, actual_end_time)"}
        ).aggregate(
            avg=Avg('duration_minutes')
        )['avg']
    }
    
    context = {
        'orders': orders,
        'stats': stats,
        'date': date,
        'title': f'Daily Report - {date}'
    }
    return render(request, 'services/daily_report.html', context)

@login_required
@employee_required(['owner', 'manager'])
def service_performance_report(request):
    """Service performance report"""
    date_from = request.GET.get('date_from', (timezone.now() - timedelta(days=30)).date())
    date_to = request.GET.get('date_to', timezone.now().date())
    
    # Employee performance - exclude cancelled orders
    completed_orders = ServiceOrder.objects.filter(
        status='completed',
        actual_end_time__date__range=[date_from, date_to]
    ).exclude(status='cancelled')
    
    # Calculate revenue per employee from completely paid orders only
    employee_performance = []
    
    try:
        from apps.payments.models import Payment
        
        # Group by employee
        employees = completed_orders.values(
            'assigned_attendant__employee_id',
            'assigned_attendant__first_name',
            'assigned_attendant__last_name'
        ).distinct()
        
        for emp in employees:
            if not emp['assigned_attendant__employee_id']:
                continue
                
            emp_orders = completed_orders.filter(
                assigned_attendant__employee_id=emp['assigned_attendant__employee_id']
            )
            
            # Calculate revenue from completely paid orders only
            emp_revenue = Decimal('0.00')
            for order in emp_orders:
                # Get total payments for this order (excluding refunds)
                total_payments = Payment.objects.filter(
                    service_order=order,
                    status__in=['completed', 'verified', 'paid', 'success']
                ).exclude(
                    payment_type='refund'
                ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
                
                # Check if order is completely paid
                order_total = order.total_amount or Decimal('0.00')
                if total_payments >= order_total:
                    emp_revenue += order_total
            
            # Calculate other metrics
            emp_performance = {
                'assigned_attendant__employee_id': emp['assigned_attendant__employee_id'],
                'assigned_attendant__first_name': emp['assigned_attendant__first_name'],
                'assigned_attendant__last_name': emp['assigned_attendant__last_name'],
                'orders_completed': emp_orders.count(),
                'total_revenue': emp_revenue,
                'avg_rating': emp_orders.aggregate(avg=Avg('customer_rating'))['avg'],
            }
            
            # Calculate average service time
            duration_orders = emp_orders.filter(
                actual_start_time__isnull=False,
                actual_end_time__isnull=False
            ).extra(
                select={'duration_minutes': "TIMESTAMPDIFF(MINUTE, actual_start_time, actual_end_time)"}
            )
            if duration_orders.exists():
                avg_duration = duration_orders.aggregate(avg=Avg('duration_minutes'))['avg']
                emp_performance['avg_service_time'] = avg_duration
            else:
                emp_performance['avg_service_time'] = None
                
            employee_performance.append(emp_performance)
            
        # Sort by orders completed
        employee_performance.sort(key=lambda x: x['orders_completed'], reverse=True)
        
    except Exception as e:
        # Fallback to simple aggregation if Payment model not available
        employee_performance = completed_orders.extra(
            select={'duration_minutes': "TIMESTAMPDIFF(MINUTE, actual_start_time, actual_end_time)"}
        ).values(
            'assigned_attendant__employee_id',
            'assigned_attendant__first_name',
            'assigned_attendant__last_name'
        ).annotate(
            orders_completed=Count('id'),
            total_revenue=Sum('total_amount'),
            avg_rating=Avg('customer_rating'),
            avg_service_time=Avg('duration_minutes')
        ).order_by('-orders_completed')
    
    context = {
        'employee_performance': employee_performance,
        'date_from': date_from,
        'date_to': date_to,
        'title': 'Performance Report'
    }
    return render(request, 'services/performance_report.html', context)

# Quick Action Views
@login_required
@employee_required()
def quick_customer_register(request):
    """Quick customer registration"""
    if request.method == 'POST':
        try:
            from apps.customers.models import Customer, Vehicle
            
            with transaction.atomic():
                # Customer data from form
                customer_type = request.POST.get('customer_type', 'individual')
                first_name = request.POST.get('first_name')
                last_name = request.POST.get('last_name')
                company_name = request.POST.get('company_name', '')
                phone = request.POST.get('phone')
                email = request.POST.get('email', '')
                preferred_contact_method = request.POST.get('preferred_contact_method', 'phone')
                
                # Address data
                address = request.POST.get('address', '')
                city = request.POST.get('city', 'Nairobi')
                county = request.POST.get('county', 'Nairobi')
                
                # Preferences
                receive_marketing_sms = request.POST.get('receive_marketing_sms') == 'on'
                receive_marketing_email = request.POST.get('receive_marketing_email') == 'on'
                receive_service_reminders = request.POST.get('receive_service_reminders') == 'on'
                
                # Create customer
                customer = Customer.objects.create(
                    customer_type=customer_type,
                    first_name=first_name,
                    last_name=last_name,
                    company_name=company_name,
                    phone=phone,
                    email=email,
                    preferred_contact_method=preferred_contact_method,
                    street_address=address,
                    city=city,
                    state=county,  # Using state field for county
                    receive_marketing_sms=receive_marketing_sms,
                    receive_marketing_email=receive_marketing_email,
                    receive_service_reminders=receive_service_reminders,
                    customer_id=generate_unique_code('CUST', 6),
                    created_by_user_id=request.user.id
                )
                
                # Create vehicles from the form
                vehicle_count = 0
                i = 0
                while request.POST.get(f'vehicles[{i}][registration_number]'):
                    registration = request.POST.get(f'vehicles[{i}][registration_number]', '').upper()
                    if registration:
                        vehicle = Vehicle.objects.create(
                            customer=customer,
                            registration_number=registration,
                            make=request.POST.get(f'vehicles[{i}][make]', ''),
                            model=request.POST.get(f'vehicles[{i}][model]', ''),
                            year=int(request.POST.get(f'vehicles[{i}][year]', timezone.now().year)),
                            color=request.POST.get(f'vehicles[{i}][color]', ''),
                            vehicle_type=request.POST.get(f'vehicles[{i}][vehicle_type]', 'sedan'),
                            fuel_type=request.POST.get(f'vehicles[{i}][fuel_type]', 'petrol'),
                            transmission=request.POST.get(f'vehicles[{i}][transmission]', 'manual'),
                            created_by_user_id=request.user.id
                        )
                        vehicle_count += 1
                    i += 1
                
                # Check if this is an AJAX request
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'message': 'Customer registered successfully!',
                        'customer_id': str(customer.id),
                        'customer': {
                            'id': str(customer.id),
                            'name': customer.full_name,
                            'phone': str(customer.phone),
                            'customer_id': customer.customer_id
                        },
                        'vehicle_count': vehicle_count
                    })
                else:
                    create_order = request.POST.get('create_order') == 'true'
                    messages.success(request, f'Customer {customer.full_name} registered successfully!')
                    
                    if create_order:
                        return redirect('services:create_order') + f'?customer={customer.id}'
                    else:
                        return redirect('services:dashboard')
                        
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': f'Error registering customer: {str(e)}',
                    'errors': {}
                })
            else:
                messages.error(request, f'Error registering customer: {str(e)}')
    
    context = {
        'title': 'Quick Customer Registration'
    }
    return render(request, 'services/quick_customer_register.html', context)
@login_required
@employee_required()
def quick_service_assign(request):
    """Quick service assignment"""
    if request.method == 'POST':
        try:
            customer_id = request.POST.get('customer_id')
            vehicle_id = request.POST.get('vehicle_id')
            service_ids = request.POST.getlist('service_ids[]')
            
            from apps.customers.models import Customer, Vehicle
            
            customer = Customer.objects.get(id=customer_id)
            vehicle = Vehicle.objects.get(id=vehicle_id)
            
            with transaction.atomic():
                # Create order
                order = ServiceOrder.objects.create(
                    customer=customer,
                    vehicle=vehicle,
                    assigned_attendant=request.employee,
                    status='confirmed',
                    priority='normal',
                    created_by=request.user
                )
                
                # Add services
                total_amount = 0
                for service_id in service_ids:
                    service = Service.objects.get(id=service_id)
                    ServiceOrderItem.objects.create(
                        order=order,
                        service=service,
                        quantity=1,
                        unit_price=service.base_price,
                        assigned_to=request.employee
                    )
                    total_amount += service.base_price
                
                # Calculate totals
                order.subtotal = total_amount
                order.calculate_totals()
                order.save()
                
                # Add to queue
                add_order_to_queue(order)
                
                messages.success(request, f'Service assigned successfully! Order: {order.order_number}')
                return redirect(get_business_url(request, 'services:order_detail', pk=order.pk))
                
        except Exception as e:
            messages.error(request, f'Error assigning service: {str(e)}')
    
    # Get recent customers and popular services for quick selection
    from apps.customers.models import Customer
    recent_customers = Customer.objects.filter(is_active=True).order_by('-created_at')[:10]
    popular_services = Service.objects.filter(is_active=True, is_popular=True).order_by('display_order')
    
    context = {
        'recent_customers': recent_customers,
        'popular_services': popular_services,
        'title': 'Quick Service Assignment'
    }
    return render(request, 'services/quick_service_assign.html', context)

# Export and Import Views
@login_required
@employee_required(['owner', 'manager'])
def service_export_view(request):
    """Export services to CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="services_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Name', 'Category', 'Description', 'Base Price', 'Estimated Duration',
        'Required Skill Level', 'Compatible Vehicles', 'Is Popular', 'Is Premium', 'Is Active'
    ])
    
    services = Service.objects.select_related('category').order_by('category', 'name')
    
    for service in services:
        writer.writerow([
            service.name,
            service.category.name if service.category else '',
            service.description,
            service.base_price,
            service.estimated_duration,
            service.required_skill_level,
            service.compatible_vehicle_types,
            service.is_popular,
            service.is_premium,
            service.is_active
        ])
    
    return response

@login_required
@employee_required(['owner', 'manager'])
def service_import_view(request):
    """Import services from CSV"""
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        
        try:
            # Read CSV file
            decoded_file = csv_file.read().decode('utf-8')
            csv_data = csv.DictReader(decoded_file.splitlines())
            
            imported_count = 0
            errors = []
            
            for row_num, row in enumerate(csv_data, start=2):
                try:
                    # Get or create category
                    category_name = row.get('Category', '').strip()
                    category = None
                    if category_name:
                        category, created = ServiceCategory.objects.get_or_create(
                            name=category_name,
                            defaults={'created_by': request.user}
                        )
                    
                    # Create service
                    service, created = Service.objects.get_or_create(
                        name=row['Name'].strip(),
                        defaults={
                            'category': category,
                            'description': row.get('Description', '').strip(),
                            'base_price': Decimal(row.get('Base Price', '0')),
                            'estimated_duration': int(row.get('Estimated Duration', '30')),
                            'required_skill_level': row.get('Required Skill Level', 'basic').lower(),
                            'compatible_vehicle_types': row.get('Compatible Vehicles', 'sedan,suv,hatchback'),
                            'is_popular': row.get('Is Popular', '').lower() in ['true', '1', 'yes'],
                            'is_premium': row.get('Is Premium', '').lower() in ['true', '1', 'yes'],
                            'is_active': row.get('Is Active', 'true').lower() in ['true', '1', 'yes'],
                            'created_by': request.user
                        }
                    )
                    
                    if created:
                        imported_count += 1
                    
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
            
            if imported_count > 0:
                messages.success(request, f'Successfully imported {imported_count} services.')
            
            if errors:
                error_message = "Errors encountered:\n" + "\n".join(errors[:5])
                if len(errors) > 5:
                    error_message += f"\n... and {len(errors) - 5} more errors."
                messages.warning(request, error_message)
                
        except Exception as e:
            messages.error(request, f'Error processing CSV file: {str(e)}')
    
    context = {
        'title': 'Import Services'
    }
    return render(request, 'services/service_import.html', context)

# AJAX Endpoints
@login_required
@employee_required()
@ajax_required  
def customer_search_ajax(request):
    """AJAX endpoint for customer search"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'customers': []})  
    
    try:
        from apps.customers.models import Customer
        
        customers = Customer.objects.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(phone__icontains=query) |
            Q(customer_id__icontains=query) |
            Q(company_name__icontains=query)
        ).select_related().prefetch_related('vehicles')[:10]
        
        # Format the results
        results = []
        for customer in customers:
            full_name = f"{customer.first_name} {customer.last_name}".strip()
            if customer.customer_type == 'corporate' and customer.company_name:
                full_name = customer.company_name
            
            results.append({
                'id': str(customer.id),
                'full_name': full_name,
                'phone': str(customer.phone) if customer.phone else '',
                'customer_id': customer.customer_id,
                'vehicle_count': customer.vehicles.count()
            })
        
        return JsonResponse({'customers': results})  # <-- Change 'results' to 'customers'
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@employee_required()
@ajax_required
def vehicle_search_ajax(request):
    """Search vehicles via AJAX"""
    query = request.GET.get('q', '')
    customer_id = request.GET.get('customer_id')
    
    from apps.customers.models import Vehicle
    
    vehicles = Vehicle.objects.filter(is_active=True)
    
    if customer_id:
        vehicles = vehicles.filter(customer_id=customer_id)
    
    if query:
        vehicles = vehicles.filter(
            Q(registration_number__icontains=query) |
            Q(make__icontains=query) |
            Q(model__icontains=query)
        )
    
    vehicles = vehicles.select_related('customer')[:10]
    
    results = [
        {
            'id': str(vehicle.id),
            'text': f"{vehicle.registration_number} - {vehicle.full_name}",
            'registration': vehicle.registration_number,
            'make': vehicle.make,
            'model': vehicle.model,
            'color': vehicle.color,
            'customer_name': vehicle.customer.full_name
        }
        for vehicle in vehicles
    ]
    
    return JsonResponse({'results': results})

@login_required
@employee_required()
@ajax_required
def start_next_service(request):
    """Start next service in queue"""
    if request.method == 'POST':
        # Get next waiting order for this attendant or any unassigned order
        next_order = ServiceOrder.objects.filter(
            Q(assigned_attendant=request.employee) | Q(assigned_attendant__isnull=True),
            status='confirmed'
        ).order_by('priority', 'created_at').first()
        
        if next_order:
            next_order.status = 'in_progress'
            next_order.actual_start_time = timezone.now()
            next_order.assigned_attendant = request.employee
            next_order.save()
            
            # Update queue entry
            if hasattr(next_order, 'queue_entry'):
                queue_entry = next_order.queue_entry
                queue_entry.status = 'in_service'
                queue_entry.actual_start_time = timezone.now()
                queue_entry.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Started service for order {next_order.order_number}',
                'redirect_url': reverse('services:order_detail', kwargs={'pk': next_order.pk})
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'No orders in queue'
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
@employee_required()
@ajax_required
def get_current_service(request):
    """Get current service for attendant"""
    current_service = ServiceOrder.objects.filter(
        assigned_attendant=request.employee,
        status='in_progress'
    ).first()
    
    if current_service:
        return JsonResponse({
            'current_service': {
                'id': str(current_service.id),
                'order_number': current_service.order_number,
                'customer_name': current_service.customer.full_name
            }
        })
    else:
        return JsonResponse({'current_service': None})

@login_required
@employee_required()
@ajax_required
def bay_status_ajax(request):
    """Get service bay status"""
    bays = ServiceBay.objects.all().order_by('bay_number')
    
    bay_data = []
    for bay in bays:
        bay_info = {
            'id': str(bay.id),
            'name': bay.name,
            'bay_number': bay.bay_number,
            'is_available': bay.is_available,
            'is_occupied': bay.is_occupied,
            'current_order': None
        }
        
        if bay.current_order:
            bay_info['current_order'] = {
                'order_number': bay.current_order.order_number,
                'customer_name': bay.current_order.customer.full_name,
                'start_time': bay.current_order.actual_start_time.isoformat() if bay.current_order.actual_start_time else None
            }
        
        bay_data.append(bay_info)
    
    return JsonResponse({
        'bays': bay_data,
        'timestamp': timezone.now().isoformat()
    })


@login_required
@employee_required()
@ajax_required
def attendance_status_ajax(request):
    """Get employee attendance status"""
    try:
        # Get the current employee
        employee = Employee.objects.get(user=request.user)
        
        # Get today's attendance record if it exists
        today = timezone.now().date()
        attendance = None
        
        # Check if there's an attendance model
        try:
            from apps.employees.models import Attendance
            attendance = Attendance.objects.filter(
                employee=employee,
                date=today
            ).first()
        except ImportError:
            # If no attendance model exists, return basic info
            pass
        
        data = {
            'employee_name': f"{employee.first_name} {employee.last_name}",
            'role': employee.role,
            'check_in_time': None,
            'check_out_time': None,
            'hours_worked': '0.0',
            'is_checked_in': False,
            'timestamp': timezone.now().isoformat()
        }
        
        if attendance:
            data.update({
                'check_in_time': attendance.check_in_time.strftime('%H:%M') if attendance.check_in_time else None,
                'check_out_time': attendance.check_out_time.strftime('%H:%M') if attendance.check_out_time else None,
                'hours_worked': str(attendance.hours_worked) if hasattr(attendance, 'hours_worked') else '0.0',
                'is_checked_in': attendance.check_in_time and not attendance.check_out_time,
            })
        
        return JsonResponse(data)
        
    except Employee.DoesNotExist:
        return JsonResponse({
            'error': 'Employee record not found',
            'employee_name': 'Unknown',
            'role': 'unknown',
            'check_in_time': None,
            'check_out_time': None,
            'hours_worked': '0.0',
            'is_checked_in': False,
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'error': f'Error retrieving attendance: {str(e)}',
            'employee_name': 'Error',
            'role': 'unknown',
            'check_in_time': None,
            'check_out_time': None,
            'hours_worked': '0.0',
            'is_checked_in': False,
        }, status=500)


# Helper Functions
def add_order_to_queue(order):
    """Add order to service queue"""
    # Get next queue number
    last_queue_number = ServiceQueue.objects.filter(
        created_at__date=timezone.now().date()
    ).aggregate(max_num=models.Max('queue_number'))['max_num'] or 0
    
    # Calculate estimated times
    estimated_duration = int(order.estimated_duration)  # Ensure it's an integer for timedelta
    estimated_start_time = timezone.now()
    
    # Check for orders ahead in queue
    waiting_orders = ServiceQueue.objects.filter(status='waiting').count()
    if waiting_orders > 0:
        # Add buffer time based on queue length
        estimated_start_time += timedelta(minutes=waiting_orders * 30)  # 30 min average per order
    
    # Calculate estimated end time
    estimated_end_time = estimated_start_time + timedelta(minutes=estimated_duration)
    
    ServiceQueue.objects.create(
        order=order,
        queue_number=last_queue_number + 1,
        estimated_start_time=estimated_start_time,
        estimated_end_time=estimated_end_time
    )


@login_required
@employee_required()
def order_receipt_view(request, pk):
    """Service order receipt"""
    order = get_object_or_404(ServiceOrder, id=pk)
    
    # Get business profile and tenant settings
    from apps.core.tenant_models import TenantSettings
    from apps.businesses.views_tenant_settings import get_or_create_tenant_settings
    
    business = request.business
    tenant_settings = get_or_create_tenant_settings(business)
    
    # Get all payments for this order
    payments = order.payments.filter(
        status__in=['completed', 'verified']
    ).order_by('created_at')
    
    # Calculate totals
    total_paid = sum(payment.amount for payment in payments)
    balance_due = order.total_amount - total_paid
    
    context = {
        'order': order,
        'service_order': order,
        'business': business,
        'tenant_settings': tenant_settings,
        'payments': payments,
        'total_paid': total_paid,
        'balance_due': balance_due,
        'is_fully_paid': balance_due <= 0,
        'title': f'Order Receipt - {order.order_number}'
    }
    
    return render(request, 'services/order_receipt.html', context)


@login_required
@employee_required()
def order_receipt_print_view(request, pk):
    """Service order thermal print receipt"""
    order = get_object_or_404(ServiceOrder, id=pk)
    
    # Get business profile and tenant settings
    from apps.core.tenant_models import TenantSettings
    from apps.businesses.views_tenant_settings import get_or_create_tenant_settings
    
    business = request.business
    tenant_settings = get_or_create_tenant_settings(business)
    
    # Get all payments for this order
    payments = order.payments.filter(
        status__in=['completed', 'verified']
    ).order_by('created_at')
    
    # Calculate totals
    total_paid = sum(payment.amount for payment in payments)
    balance_due = order.total_amount - total_paid
    
    # Generate QR code for order details URL
    business_slug = request.tenant.slug
    order_detail_url = f"{request.scheme}://{request.get_host()}/business/{business_slug}/services/orders/{order.id}/"
    qr_code_image = generate_qr_code_base64(order_detail_url, size=2, border=1)
    
    context = {
        'order': order,
        'service_order': order,
        'business': business,
        'tenant_settings': tenant_settings,
        'payments': payments,
        'total_paid': total_paid,
        'balance_due': balance_due,
        'is_fully_paid': balance_due <= 0,
        'qr_code_image': qr_code_image,
        'order_detail_url': order_detail_url,
        'title': f'Print Receipt - {order.order_number}'
    }
    
    return render(request, 'services/order_receipt_print.html', context)


@login_required
@employee_required()
@ajax_required
def vehicle_customer_ajax(request):
    """Get vehicles for a customer or customer details for a vehicle"""
    vehicle_id = request.GET.get('vehicle_id')
    customer_id = request.GET.get('customer_id')
    
    # Add debugging
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"vehicle_customer_ajax called with vehicle_id={vehicle_id}, customer_id={customer_id}")
    
    # Handle getting vehicles for a customer
    if customer_id:
        try:
            from apps.customers.models import Vehicle, Customer
            customer = Customer.objects.get(id=customer_id, is_active=True)
            vehicles = Vehicle.objects.filter(customer=customer, is_active=True)
            
            logger.info(f"Found {vehicles.count()} vehicles for customer {customer.full_name}")
            
            vehicles_data = []
            for vehicle in vehicles:
                vehicles_data.append({
                    'id': vehicle.id,
                    'make': vehicle.make,
                    'model': vehicle.model,
                    'license_plate': vehicle.registration_number,
                    'year': vehicle.year,
                    'color': vehicle.color,
                    'customer_name': customer.full_name,
                    'customer_phone': str(customer.phone) if customer.phone else ''
                })
            
            logger.info(f"Returning vehicles data: {vehicles_data}")
            
            return JsonResponse({
                'success': True,
                'vehicles': vehicles_data
            })
            
        except Customer.DoesNotExist:
            logger.error(f"Customer with id {customer_id} not found")
            return JsonResponse({'success': False, 'error': 'Customer not found'})
        except Exception as e:
            logger.error(f"Error in vehicle_customer_ajax: {str(e)}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    # Handle getting customer details for a vehicle (original functionality)
    elif vehicle_id:
        try:
            from apps.customers.models import Vehicle
            vehicle = Vehicle.objects.select_related('customer').get(id=vehicle_id, is_active=True)
            
            customer_data = {
                'id': str(vehicle.customer.id),
                'name': vehicle.customer.full_name,
                'full_name': vehicle.customer.full_name,
                'phone': str(vehicle.customer.phone) if vehicle.customer.phone else '',
                'customer_id': vehicle.customer.customer_id,
                'email': vehicle.customer.email or '',
                'is_walk_in': vehicle.customer.is_walk_in
            }
            
            return JsonResponse({
                'success': True,
                'customer': customer_data
            })
            
        except Vehicle.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Vehicle not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    else:
        return JsonResponse({'success': False, 'error': 'Either vehicle_id or customer_id is required'})


@login_required
@employee_required()
@require_GET
def payment_status_ajax(request):
    """Check payment status for walk-in customer notifications"""
    order_id = request.GET.get('order_id')
    
    if not order_id:
        return JsonResponse({'success': False, 'error': 'Order ID required'})
    
    try:
        order = ServiceOrder.objects.get(order_id=order_id)
        
        # Get the latest payment for this order
        payment = Payment.objects.filter(service_order=order).order_by('-created_at').first()
        
        if not payment:
            return JsonResponse({'success': False, 'error': 'No payment found'})
        
        # Check if customer is walk-in
        customer_is_walk_in = (
            payment.customer and 
            hasattr(payment.customer, 'is_walk_in') and 
            payment.customer.is_walk_in
        )
        
        payment_data = {
            'id': str(payment.id),
            'status': payment.status,
            'method': payment.method,
            'amount': float(payment.amount),
            'customer_phone': payment.customer_phone,
            'customer_is_walk_in': customer_is_walk_in
        }
        
        return JsonResponse({
            'success': True,
            'payment': payment_data
        })
        
    except ServiceOrder.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Order not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ================================
# INVOICE MANAGEMENT VIEWS
# ================================

@login_required
@employee_required()
def generate_invoice(request, order_id):
    """Generate invoice for a service order"""
    from .models import ServiceInvoice
    
    order = get_object_or_404(ServiceOrder, pk=order_id)
    
    if request.method == 'POST':
        invoice_type = request.POST.get('invoice_type')
        notes = request.POST.get('notes', '')
        
        if invoice_type not in ['credit', 'cash']:
            messages.error(request, 'Invalid invoice type selected.')
            return redirect('services:order_detail', pk=order_id)
        
        try:
            with transaction.atomic():
                # Ensure order totals are calculated
                if order.total_amount == 0:
                    order.calculate_totals()
                    order.save()
                
                # Create the invoice with amounts from order
                invoice = ServiceInvoice.objects.create(
                    service_order=order,
                    invoice_type=invoice_type,
                    subtotal=order.subtotal,
                    discount_amount=order.discount_amount,
                    tax_amount=order.tax_amount,
                    total_amount=order.total_amount,
                    notes=notes,
                    created_by=request.user
                )
                
                messages.success(
                    request, 
                    f'{invoice_type.title()} Invoice {invoice.invoice_number} generated successfully.'
                )
                
                # Redirect to invoice preview using manual tenant slug format
                return redirect(f'/business/{request.tenant.slug}/services/invoices/{invoice.id}/')
                
        except Exception as e:
            messages.error(request, f'Error generating invoice: {str(e)}')
            return redirect(f'/business/{request.tenant.slug}/services/orders/{order_id}/')
    
    # Check if order already has invoices
    existing_invoices = order.invoices.all()
    
    context = {
        'order': order,
        'existing_invoices': existing_invoices,
        'has_credit_invoice': existing_invoices.filter(invoice_type='credit').exists(),
        'has_cash_invoice': existing_invoices.filter(invoice_type='cash').exists(),
    }
    
    return render(request, 'services/generate_invoice.html', context)


@login_required
@employee_required()
def invoice_preview(request, invoice_id):
    """Preview invoice before sending/printing"""
    from .models import ServiceInvoice
    
    invoice = get_object_or_404(ServiceInvoice, pk=invoice_id)
    
    # Get business information and tenant settings for invoice header
    from apps.core.tenant_models import TenantSettings
    from apps.businesses.views_tenant_settings import get_or_create_tenant_settings
    
    business = request.business if hasattr(request, 'business') else request.tenant
    tenant_settings = get_or_create_tenant_settings(business)
    
    # Get invoice items
    invoice_items = invoice.get_invoice_items()
    
    context = {
        'invoice': invoice,
        'business': business,
        'tenant_settings': tenant_settings,
        'order': invoice.service_order,
        'customer': invoice.service_order.customer,
        'vehicle': invoice.service_order.vehicle,
        'invoice_items': invoice_items,
        'current_date': timezone.now().date(),
    }
    
    return render(request, 'services/invoice_preview.html', context)


@login_required
@employee_required()
def invoice_print(request, invoice_id):
    """Print-friendly invoice view"""
    from .models import ServiceInvoice
    
    invoice = get_object_or_404(ServiceInvoice, pk=invoice_id)
    
    # Get business information and tenant settings for invoice header
    from apps.core.tenant_models import TenantSettings
    from apps.businesses.views_tenant_settings import get_or_create_tenant_settings
    
    business = request.business if hasattr(request, 'business') else request.tenant
    tenant_settings = get_or_create_tenant_settings(business)
    
    # Get invoice items
    invoice_items = invoice.get_invoice_items()
    
    context = {
        'invoice': invoice,
        'business': business,
        'tenant_settings': tenant_settings,
        'order': invoice.service_order,
        'customer': invoice.service_order.customer,
        'vehicle': invoice.service_order.vehicle,
        'invoice_items': invoice_items,
        'current_date': timezone.now().date(),
        'print_mode': True,
    }
    
    return render(request, 'services/invoice_print.html', context)


@login_required
@employee_required()
def invoice_pdf(request, invoice_id):
    """Generate and download invoice as PDF"""
    from .models import ServiceInvoice
    from django.http import FileResponse
    import os
    
    invoice = get_object_or_404(ServiceInvoice, pk=invoice_id)
    
    # Check if PDF already exists
    if invoice.pdf_file and os.path.exists(invoice.pdf_file.path):
        return FileResponse(
            invoice.pdf_file,
            as_attachment=True,
            filename=f'Invoice_{invoice.invoice_number}.pdf'
        )
    
    # Generate PDF if it doesn't exist
    try:
        # Get tenant settings for comprehensive business info
        from apps.core.tenant_models import TenantSettings
        from apps.businesses.views_tenant_settings import get_or_create_tenant_settings
        business = request.business if hasattr(request, 'business') else request.tenant
        tenant_settings = get_or_create_tenant_settings(business)
        
        pdf_content = generate_invoice_pdf(invoice, business, tenant_settings)
        
        # Save PDF to file
        pdf_filename = f'invoice_{invoice.invoice_number}.pdf'
        pdf_path = f'invoices/pdf/{pdf_filename}'
        
        # Save the PDF content to the file field
        from django.core.files.base import ContentFile
        invoice.pdf_file.save(
            pdf_filename,
            ContentFile(pdf_content),
            save=True
        )
        
        invoice.pdf_generated = True
        invoice.save()
        
        return FileResponse(
            invoice.pdf_file,
            as_attachment=True,
            filename=f'Invoice_{invoice.invoice_number}.pdf'
        )
        
    except Exception as e:
        messages.error(request, f'Error generating PDF: {str(e)}')
        return redirect(f'/business/{request.tenant.slug}/services/invoices/{invoice_id}/')


@login_required
@employee_required()
def invoice_list(request):
    """List all invoices with filtering and search"""
    from .models import ServiceInvoice
    
    # Get filter parameters
    status = request.GET.get('status', '')
    invoice_type = request.GET.get('type', '')
    search = request.GET.get('search', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Base queryset
    invoices = ServiceInvoice.objects.select_related(
        'service_order', 
        'service_order__customer'
    ).order_by('-created_at')
    
    # Apply filters
    if status:
        invoices = invoices.filter(status=status)
    
    if invoice_type:
        invoices = invoices.filter(invoice_type=invoice_type)
    
    if search:
        invoices = invoices.filter(
            Q(invoice_number__icontains=search) |
            Q(service_order__customer__first_name__icontains=search) |
            Q(service_order__customer__last_name__icontains=search) |
            Q(service_order__order_number__icontains=search)
        )
    
    if date_from:
        invoices = invoices.filter(issue_date__gte=date_from)
    
    if date_to:
        invoices = invoices.filter(issue_date__lte=date_to)
    
    # Pagination
    paginator = Paginator(invoices, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Summary statistics
    stats = {
        'total_invoices': invoices.count(),
        'total_amount': invoices.aggregate(Sum('total_amount'))['total_amount__sum'] or 0,
        'draft_count': invoices.filter(status='draft').count(),
        'sent_count': invoices.filter(status='sent').count(),
        'paid_count': invoices.filter(status='paid').count(),
        'overdue_count': invoices.filter(status='overdue').count(),
    }
    
    context = {
        'page_obj': page_obj,
        'invoices': page_obj,
        'stats': stats,
        'current_status': status,
        'current_type': invoice_type,
        'current_search': search,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'services/invoice_list.html', context)


@login_required
@employee_required()
@require_POST
def invoice_mark_sent(request, invoice_id):
    """Mark invoice as sent"""
    from .models import ServiceInvoice
    
    invoice = get_object_or_404(ServiceInvoice, pk=invoice_id)
    
    try:
        invoice.mark_as_sent(request.user)
        messages.success(request, f'Invoice {invoice.invoice_number} marked as sent.')
    except Exception as e:
        messages.error(request, f'Error marking invoice as sent: {str(e)}')
    
    return redirect(f'/business/{request.tenant.slug}/services/invoices/{invoice_id}/')


@login_required
@employee_required()
@require_POST
def invoice_mark_paid(request, invoice_id):
    """Mark invoice as paid"""
    from .models import ServiceInvoice
    
    invoice = get_object_or_404(ServiceInvoice, pk=invoice_id)
    
    try:
        payment_date = request.POST.get('payment_date')
        if payment_date:
            from datetime import datetime
            payment_date = datetime.strptime(payment_date, '%Y-%m-%d').date()
        
        invoice.mark_as_paid(payment_date)
        messages.success(request, f'Invoice {invoice.invoice_number} marked as paid.')
    except Exception as e:
        messages.error(request, f'Error marking invoice as paid: {str(e)}')
    
    return redirect(f'/business/{request.tenant.slug}/services/invoices/{invoice_id}/')


def generate_invoice_pdf(invoice, business, tenant_settings):
    """Generate PDF content for invoice"""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm, inch
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
        import io
        
        buffer = io.BytesIO()
        
        # Create PDF document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=20*mm,
            leftMargin=20*mm,
            topMargin=20*mm,
            bottomMargin=20*mm
        )
        
        # Container for the 'Flowable' objects
        elements = []
        
        # Add company name first
        elements.extend(story)
        
        # Define styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=10*mm,
            alignment=TA_CENTER,
            textColor=colors.black
        )
        
        company_style = ParagraphStyle(
            'Company',
            parent=styles['Normal'],
            fontSize=14,
            spaceBefore=5*mm,
            spaceAfter=5*mm,
            alignment=TA_LEFT,
            fontName='Helvetica-Bold'
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=3*mm,
            alignment=TA_LEFT
        )
        
        # Header Section - Company Name First Row
        story = []
        
        # Company Name - Top Row Alone
        company_name_style = ParagraphStyle(
            'CompanyName',
            parent=styles['Normal'],
            fontSize=24,
            alignment=TA_CENTER,
            spaceAfter=10*mm,
            fontName='Helvetica-Bold'
        )
        
        story.append(Paragraph(business.name.upper(), company_name_style))
        
        # Second Row - Logo, Business Details, Invoice Type
        header_data = []
        
        # Business details for center
        business_details = f"""
        {tenant_settings.contact_address if tenant_settings.contact_address else (f'{business.city}, {business.state}' if business.city else '')}<br/>
        {f'TEL NO: {tenant_settings.contact_phone}' if tenant_settings.contact_phone else (f'TEL NO: {business.phone}' if business.phone else '')}<br/>
        {f'E-MAIL: {tenant_settings.contact_email}' if tenant_settings.contact_email else (f'E-MAIL: {business.email}' if business.email else '')}<br/>
        {f'PIN No: {tenant_settings.tax_number}' if tenant_settings.tax_number else ''}
        """
        
        invoice_title = f"""
        <b style="font-size:18pt">{invoice.get_invoice_type_display().upper()} INVOICE</b>
        """
        
        header_data.append([
            Paragraph("", normal_style),  # Logo space (empty for now)
            Paragraph(business_details, ParagraphStyle('BusinessDetails', parent=styles['Normal'], fontSize=10, alignment=TA_CENTER)),
            Paragraph(invoice_title, ParagraphStyle('InvoiceTitle', parent=styles['Normal'], fontSize=18, alignment=TA_RIGHT))
        ])
        
        header_table = Table(header_data, colWidths=[1.5*inch, 3*inch, 2.5*inch])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LINEBELOW', (0, 0), (-1, 0), 2, colors.black),
            ('SPACEAFTER', (0, 0), (-1, -1), 15*mm),
        ]))
        
        elements.append(header_table)
        elements.append(Spacer(1, 10*mm))
        
        # Customer and Invoice Info
        customer_invoice_data = []
        
        customer_info = f"""
        <b>TO:</b> {invoice.service_order.customer.display_name.upper()}<br/>
        <b>REG NO:</b> {invoice.service_order.vehicle.registration_number.upper() if invoice.service_order.vehicle else '-'}<br/>
        <b>VEH TYPE:</b> {f"{invoice.service_order.vehicle.make.upper()} {invoice.service_order.vehicle.model.upper()}" if invoice.service_order.vehicle else '-'}
        """
        
        invoice_info = f"""
        <b>INVOICE NO:</b> {invoice.invoice_number}<br/>
        <b>DATE:</b> {invoice.issue_date.strftime('%d %b %Y')}<br/>
        <b>SALES PERSON:</b> {invoice.created_by.get_full_name().upper() if invoice.created_by else 'SYSTEM'}
        """
        
        customer_invoice_data.append([
            Paragraph(customer_info, normal_style),
            Paragraph(invoice_info, normal_style)
        ])
        
        customer_invoice_table = Table(customer_invoice_data, colWidths=[3*inch, 3*inch])
        customer_invoice_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('INNERGRID', (0, 0), (-1, -1), 1, colors.black),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        elements.append(customer_invoice_table)
        elements.append(Spacer(1, 10*mm))
        
        # Items Table
        items_data = [['DESCRIPTION', 'QTY', 'RATE (KSh)', 'DISCOUNT', 'AMOUNT (KSh)']]
        
        # Get invoice items
        invoice_items = invoice.get_invoice_items()
        
        for item in invoice_items:
            if item['type'] == 'customer_part':
                items_data.append([
                    f"{item['description'].upper()}\n(CUSTOMER PROVIDED - NO CHARGE)",
                    str(item['quantity']),
                    '-',
                    '-',
                    '-'
                ])
            else:
                items_data.append([
                    item['description'].upper(),
                    str(item['quantity']),
                    f"{item['unit_price']:.2f}",
                    '-',
                    f"{item['total_price']:.2f}"
                ])
        
        # Add empty rows to match the image format
        for _ in range(5):
            items_data.append(['', '', '', '', ''])
        
        items_table = Table(items_data, colWidths=[2.5*inch, 0.8*inch, 1*inch, 1*inch, 1*inch])
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),  # Description column left-aligned
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('INNERGRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        elements.append(items_table)
        elements.append(Spacer(1, 10*mm))
        
        # Totals Table (right-aligned)
        totals_data = [
            ['NET AMOUNT (KSh)', f'{invoice.subtotal:.2f}'],
            ['VAT 16%', f'{invoice.tax_amount:.2f}'],
            ['TOTAL AMOUNT (KSh)', f'{invoice.total_amount:.2f}']
        ]
        
        totals_table = Table(totals_data, colWidths=[1.5*inch, 1*inch])
        totals_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 2), (-1, 2), colors.lightgrey),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('INNERGRID', (0, 0), (-1, -1), 1, colors.black),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        # Create a table to position totals on the right
        totals_position_data = [['', totals_table]]
        totals_position_table = Table(totals_position_data, colWidths=[4*inch, 2.5*inch])
        totals_position_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        elements.append(totals_position_table)
        elements.append(Spacer(1, 15*mm))
        
        # Footer Section
        footer_text = f"""
        <b>WITH THANKS</b><br/><br/>
        
        _____________________<br/>
        {invoice.created_by.get_full_name().upper() if invoice.created_by else 'AUTHORIZED SIGNATURE'}<br/>
        <b>SIGNATURE</b>
        """
        
        elements.append(Paragraph(footer_text, normal_style))
        elements.append(Spacer(1, 10*mm))
        
        # Terms and Conditions
        terms_text = f"""
        <b>TERMS AND CONDITIONS:</b><br/>
        {invoice.terms_and_conditions}
        """
        
        if invoice.notes:
            terms_text += f"<br/><br/><b>Notes:</b> {invoice.notes}"
        
        terms_para = Paragraph(terms_text, ParagraphStyle('Terms', parent=styles['Normal'], fontSize=8, leftIndent=10))
        
        # Create terms box
        terms_data = [[terms_para]]
        terms_table = Table(terms_data, colWidths=[6*inch])
        terms_table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        
        elements.append(terms_table)
        
        # Payment Details if available
        if hasattr(business, 'bank_details') and business.bank_details:
            elements.append(Spacer(1, 5*mm))
            payment_text = f"""
            <b>PAYMENT DETAILS:</b><br/>
            {business.bank_details}
            """
            elements.append(Paragraph(payment_text, ParagraphStyle('Payment', parent=styles['Normal'], fontSize=8)))
        
        # Build PDF
        doc.build(elements)
        
        buffer.seek(0)
        return buffer.getvalue()
        
    except ImportError:
        # Fallback if reportlab is not installed
        raise Exception("PDF generation library not available. Please install reportlab.")
    except Exception as e:
        raise Exception(f"Error generating PDF: {str(e)}")


# ===== QUOTATION VIEWS =====

@login_required
@employee_required()
def quotation_list(request):
    """List all quotations"""
    from .models import Quotation
    
    quotations = Quotation.objects.all().select_related('customer', 'vehicle')
    
    # Filters
    status = request.GET.get('status')
    customer = request.GET.get('customer')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    search = request.GET.get('search')
    
    if status:
        quotations = quotations.filter(status=status)
    
    if customer:
        quotations = quotations.filter(customer_name__icontains=customer)
    
    if date_from:
        try:
            from datetime import datetime
            date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d').date()
            quotations = quotations.filter(created_at__date__gte=date_from_parsed)
        except ValueError:
            pass
    
    if date_to:
        try:
            from datetime import datetime
            date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d').date()
            quotations = quotations.filter(created_at__date__lte=date_to_parsed)
        except ValueError:
            pass
    
    if search:
        quotations = quotations.filter(
            Q(quotation_number__icontains=search) |
            Q(customer_name__icontains=search) |
            Q(customer_email__icontains=search) |
            Q(customer_phone__icontains=search)
        )
    
    # Sort by status priority and creation date
    quotations = quotations.order_by(
        Case(
            When(status='draft', then=Value(1)),
            When(status='sent', then=Value(2)),
            When(status='accepted', then=Value(3)),
            When(status='expired', then=Value(4)),
            When(status='rejected', then=Value(5)),
            When(status='converted', then=Value(6)),
            default=Value(3),
            output_field=IntegerField(),
        ),
        '-created_at'
    )
    
    # Pagination
    paginator = Paginator(quotations, 20)
    page = request.GET.get('page')
    quotations_page = paginator.get_page(page)
    
    # Statistics
    today = timezone.now().date()
    stats = {
        'total_quotations': quotations.count(),
        'draft_quotations': quotations.filter(status='draft').count(),
        'sent_quotations': quotations.filter(status='sent').count(),
        'accepted_quotations': quotations.filter(status='accepted').count(),
        'conversion_rate': 0,
    }
    
    # Calculate conversion rate
    sent_count = quotations.filter(status__in=['sent', 'accepted', 'converted']).count()
    converted_count = quotations.filter(status__in=['accepted', 'converted']).count()
    if sent_count > 0:
        stats['conversion_rate'] = (converted_count / sent_count) * 100
    
    context = {
        'quotations': quotations_page,
        'stats': stats,
        'status_choices': Quotation.STATUS_CHOICES,
        'current_filters': {
            'status': status or '',
            'customer': customer or '',
            'date_from': date_from or '',
            'date_to': date_to or '',
            'search': search or ''
        },
        'title': 'Quotations'
    }
    return render(request, 'services/quotation_list.html', context)


@login_required
@employee_required()
def quotation_create(request):
    """Create new quotation"""
    from .forms import QuotationForm
    from .models import Quotation
    
    if request.method == 'POST':
        form = QuotationForm(request.POST)
        if form.is_valid():
            quotation = form.save(commit=False)
            quotation.created_by = request.user
            quotation.save()
            
            messages.success(request, f'Quotation {quotation.quotation_number} created successfully!')
            return redirect(get_business_url(request, 'services:quotation_detail', quotation_id=quotation.pk))
    else:
        form = QuotationForm()
    
    # Get services and categories for selection
    categories = ServiceCategory.objects.filter(is_active=True).prefetch_related('services')
    
    # Get inventory items for selection
    from apps.inventory.models import InventoryItem
    inventory_items = InventoryItem.objects.filter(is_active=True, current_stock__gt=0)
    
    context = {
        'form': form,
        'categories': categories,
        'inventory_items': inventory_items,
        'title': 'Create Quotation'
    }
    return render(request, 'services/quotation_form.html', context)


@csrf_protect
@employee_required()
@require_http_methods(["GET", "POST"])
def quick_quotation_view(request):
    """Quick quotation creation similar to quick order"""
    from .forms import QuickQuotationForm
    from .models import Quotation, QuotationItem
    import json
    from decimal import Decimal
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                logger.info(f"Quick quotation POST data: {request.POST}")
                
                # Handle customer data - either from existing customer or manual entry
                customer_id = request.POST.get('customer')
                selected_customer = None
                
                if customer_id:
                    # Use existing customer
                    from apps.customers.models import Customer
                    try:
                        selected_customer = Customer.objects.get(id=customer_id)
                        quotation = Quotation.objects.create(
                            customer=selected_customer,
                            customer_name=f"{selected_customer.first_name} {selected_customer.last_name}",
                            customer_email=selected_customer.email,
                            customer_phone=selected_customer.phone,
                            vehicle_registration=request.POST.get('vehicle_registration', '').strip().upper(),
                            vehicle_make=request.POST.get('vehicle_make', '').strip(),
                            vehicle_model=request.POST.get('vehicle_model', '').strip(),
                            quotation_type=request.POST.get('quotation_type', 'standard'),
                            description=request.POST.get('description', '').strip(),
                            created_by=request.user
                        )
                    except Customer.DoesNotExist:
                        # Fallback to manual entry
                        quotation = Quotation.objects.create(
                            customer_name=request.POST.get('customer_name', '').strip(),
                            customer_email=request.POST.get('customer_email', '').strip(),
                            customer_phone=request.POST.get('customer_phone', '').strip(),
                            vehicle_registration=request.POST.get('vehicle_registration', '').strip().upper(),
                            vehicle_make=request.POST.get('vehicle_make', '').strip(),
                            vehicle_model=request.POST.get('vehicle_model', '').strip(),
                            quotation_type=request.POST.get('quotation_type', 'standard'),
                            description=request.POST.get('description', '').strip(),
                            created_by=request.user
                        )
                else:
                    # Use manual customer entry
                    quotation = Quotation.objects.create(
                        customer_name=request.POST.get('customer_name', '').strip(),
                        customer_email=request.POST.get('customer_email', '').strip(),
                        customer_phone=request.POST.get('customer_phone', '').strip(),
                        vehicle_registration=request.POST.get('vehicle_registration', '').strip().upper(),
                        vehicle_make=request.POST.get('vehicle_make', '').strip(),
                        vehicle_model=request.POST.get('vehicle_model', '').strip(),
                        quotation_type=request.POST.get('quotation_type', 'standard'),
                        description=request.POST.get('description', '').strip(),
                        created_by=request.user
                    )
                
                total_amount = Decimal('0.00')
                
                # Process selected services
                selected_services = request.POST.getlist('selected_services')
                service_quantities = request.POST.getlist('service_quantities[]')
                services_custom_prices_data = request.POST.get('services_custom_prices', '{}')
                try:
                    services_custom_prices = json.loads(services_custom_prices_data) if services_custom_prices_data else {}
                except (json.JSONDecodeError, TypeError):
                    services_custom_prices = {}
                
                for i, service_id in enumerate(selected_services):
                    try:
                        service = Service.objects.get(id=service_id, is_active=True)
                        
                        # Get quantity from array (default to 1 if not provided)
                        quantity = Decimal(service_quantities[i]) if i < len(service_quantities) else Decimal('1')
                        
                        # Get custom price if provided
                        custom_price = services_custom_prices.get(str(service_id))
                        unit_price = Decimal(str(custom_price)) if custom_price else service.base_price
                        
                        QuotationItem.objects.create(
                            quotation=quotation,
                            service=service,
                            quantity=quantity,
                            unit_price=unit_price,
                            item_type='service'
                        )
                        total_amount += quantity * unit_price
                        logger.info(f"Added service to quotation: {service.name} x{quantity} at price {unit_price}")
                    except Service.DoesNotExist:
                        logger.warning(f"Service {service_id} not found, skipping")
                        continue
                
                # Process selected inventory items
                selected_inventory_items = request.POST.getlist('selected_inventory_items')
                inventory_quantities = request.POST.getlist('inventory_quantities[]')
                inventory_custom_prices_data = request.POST.get('inventory_custom_prices', '{}')
                try:
                    inventory_custom_prices = json.loads(inventory_custom_prices_data) if inventory_custom_prices_data else {}
                except (json.JSONDecodeError, TypeError):
                    inventory_custom_prices = {}
                
                if selected_inventory_items:
                    from apps.inventory.models import InventoryItem
                    
                    for i, item_id in enumerate(selected_inventory_items):
                        try:
                            inventory_item = InventoryItem.objects.get(id=item_id, is_active=True)
                            # Get quantity from array (default to 1 if not provided)
                            quantity = Decimal(inventory_quantities[i]) if i < len(inventory_quantities) else Decimal('1')
                            
                            # Get custom price if provided
                            custom_price = inventory_custom_prices.get(str(item_id))
                            unit_price = Decimal(str(custom_price)) if custom_price else (inventory_item.selling_price or inventory_item.unit_cost)
                            
                            QuotationItem.objects.create(
                                quotation=quotation,
                                inventory_item=inventory_item,
                                quantity=quantity,
                                unit_price=unit_price,
                                item_type='inventory'
                            )
                            total_amount += quantity * unit_price
                            logger.info(f"Added inventory item to quotation: {inventory_item.name} x{quantity} at price {unit_price}")
                        except InventoryItem.DoesNotExist:
                            logger.warning(f"Inventory item {item_id} not found, skipping")
                            continue
                
                # Process customer parts
                customer_parts_data = request.POST.get('customer_parts', '[]')
                try:
                    customer_parts = json.loads(customer_parts_data) if customer_parts_data else []
                except (json.JSONDecodeError, TypeError):
                    customer_parts = []
                
                for part in customer_parts:
                    if isinstance(part, dict) and part.get('name'):
                        QuotationItem.objects.create(
                            quotation=quotation,
                            description=part['name'],
                            quantity=Decimal(str(part.get('quantity', 1))),
                            unit_price=Decimal('0.00'),  # Customer parts are free
                            item_type='custom'
                        )
                        logger.info(f"Added customer part to quotation: {part['name']}")
                
                # Calculate totals with proper VAT
                quotation.tax_percentage = Decimal('16.00')  # Set 16% VAT
                quotation.calculate_totals()
                
                success_message = f'Quotation {quotation.quotation_number} created successfully!'
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'message': success_message,
                        'quotation_id': str(quotation.id),
                        'quotation_number': quotation.quotation_number,
                        'redirect_url': get_business_url(request, 'services:quotation_detail', quotation_id=quotation.pk)
                    })
                else:
                    messages.success(request, success_message)
                    return redirect(get_business_url(request, 'services:quotation_detail', quotation_id=quotation.pk))
                    
        except Exception as e:
            logger.error(f"Exception in quick quotation creation: {str(e)}")
            error_message = f'Error creating quotation: {str(e)}'
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': error_message,
                    'errors': {'general': [error_message]}
                })
            else:
                messages.error(request, error_message)
                return redirect(get_business_url(request, 'services:quick_quotation'))
    
    # GET request - show the form
    form = QuickQuotationForm()
    
    # Get customers
    from apps.customers.models import Customer
    customers = Customer.objects.filter(is_active=True).order_by('first_name', 'last_name')
    
    # Get services organized by category
    categories = ServiceCategory.objects.filter(is_active=True).prefetch_related(
        Prefetch('services', queryset=Service.objects.filter(is_active=True))
    ).order_by('display_order', 'name')
    
    # Get all active services for dropdown
    services = Service.objects.filter(is_active=True).select_related('category').order_by('category__name', 'name')
    
    # Get service packages
    packages = ServicePackage.objects.filter(is_active=True).order_by('name')
    
    # Get inventory items organized by category
    from apps.inventory.models import InventoryCategory, InventoryItem
    inventory_categories = InventoryCategory.objects.filter(is_active=True).prefetch_related(
        Prefetch('items', queryset=InventoryItem.objects.filter(is_active=True, current_stock__gt=0))
    ).order_by('name')
    
    # Get inventory items for dropdown
    inventory_items = InventoryItem.objects.filter(
        is_active=True, 
        current_stock__gt=0
    ).select_related('category', 'unit').order_by('category__name', 'name')
    
    context = {
        'form': form,
        'customers': customers,
        'categories': categories,
        'services': services,
        'packages': packages,
        'inventory_categories': inventory_categories,
        'inventory_items': inventory_items,
        'title': 'Quick Quotation'
    }
    return render(request, 'services/quick_quotation.html', context)


@login_required
@employee_required()
def quotation_detail(request, quotation_id):
    """Quotation detail view"""
    from .models import Quotation
    
    quotation = get_object_or_404(Quotation, pk=quotation_id)
    quotation_items = quotation.quotation_items.all().select_related('service', 'inventory_item')
    
    # Get business information and tenant settings
    from apps.core.tenant_models import TenantSettings
    from apps.businesses.views_tenant_settings import get_or_create_tenant_settings
    
    business = request.business if hasattr(request, 'business') else request.tenant
    tenant_settings = get_or_create_tenant_settings(business)
    
    context = {
        'quotation': quotation,
        'quotation_items': quotation_items,
        'business': business,
        'tenant_settings': tenant_settings,
        'title': 'Quotation ' + str(quotation.quotation_number)
    }
    return render(request, 'services/quotation_detail.html', context)


@login_required
@employee_required()
def quotation_edit(request, quotation_id):
    """Edit quotation"""
    from .models import Quotation
    from .forms import QuotationForm
    
    quotation = get_object_or_404(Quotation, pk=quotation_id)
    
    if request.method == 'POST':
        form = QuotationForm(request.POST, instance=quotation)
        if form.is_valid():
            form.save()
            messages.success(request, f'Quotation {quotation.quotation_number} updated successfully!')
            return redirect(get_business_url(request, 'services:quotation_detail', quotation_id=quotation.pk))
    else:
        form = QuotationForm(instance=quotation)
    
    context = {
        'form': form,
        'quotation': quotation,
        'title': f'Edit Quotation {quotation.quotation_number}'
    }
    return render(request, 'services/quotation_form.html', context)


@login_required
@employee_required()
def quotation_print(request, quotation_id):
    """Print quotation"""
    from .models import Quotation
    
    quotation = get_object_or_404(Quotation, pk=quotation_id)
    quotation_items = quotation.quotation_items.all().select_related('service', 'inventory_item')
    
    # Get business information and tenant settings for quotation header
    from apps.core.tenant_models import TenantSettings
    from apps.businesses.views_tenant_settings import get_or_create_tenant_settings
    
    business = request.business if hasattr(request, 'business') else request.tenant
    tenant_settings = get_or_create_tenant_settings(business)
    
    context = {
        'quotation': quotation,
        'quotation_items': quotation_items,
        'business': business,
        'tenant_settings': tenant_settings,
        'customer': quotation.customer,
        'vehicle': quotation.vehicle if hasattr(quotation, 'vehicle') else None,
        'current_date': timezone.now().date(),
        'today': timezone.now().date(),
        'title': f'Quotation {quotation.quotation_number}'
    }
    return render(request, 'services/quotation_print.html', context)


@login_required
@employee_required()
def quotation_pdf(request, quotation_id):
    """Generate quotation PDF"""
    from .models import Quotation
    from django.http import HttpResponse
    
    quotation = get_object_or_404(Quotation, pk=quotation_id)
    
    try:
        pdf_content = generate_quotation_pdf(quotation, request.tenant)
        
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="quotation_{quotation.quotation_number}.pdf"'
        
        return response
    except Exception as e:
        messages.error(request, f'Error generating PDF: {str(e)}')
        return redirect(get_business_url(request, 'services:quotation_detail', quotation_id=quotation.pk))


@login_required
@employee_required()
@require_POST
def quotation_send(request, quotation_id):
    """Send quotation to customer"""
    from .models import Quotation
    
    quotation = get_object_or_404(Quotation, pk=quotation_id)
    
    try:
        quotation.mark_as_sent()
        messages.success(request, f'Quotation {quotation.quotation_number} marked as sent.')
    except Exception as e:
        messages.error(request, f'Error sending quotation: {str(e)}')
    
    return redirect(get_business_url(request, 'services:quotation_detail', quotation_id=quotation.pk))


@login_required
@employee_required()
@require_POST
def quotation_accept(request, quotation_id):
    """Accept quotation"""
    from .models import Quotation
    
    quotation = get_object_or_404(Quotation, pk=quotation_id)
    
    try:
        quotation.mark_as_accepted()
        messages.success(request, f'Quotation {quotation.quotation_number} marked as accepted.')
    except Exception as e:
        messages.error(request, f'Error accepting quotation: {str(e)}')
    
    return redirect(get_business_url(request, 'services:quotation_detail', quotation_id=quotation.pk))


@login_required
@employee_required()
@require_POST
def quotation_reject(request, quotation_id):
    """Reject quotation"""
    from .models import Quotation
    
    quotation = get_object_or_404(Quotation, pk=quotation_id)
    
    try:
        quotation.mark_as_rejected()
        messages.success(request, f'Quotation {quotation.quotation_number} marked as rejected.')
    except Exception as e:
        messages.error(request, f'Error rejecting quotation: {str(e)}')
    
    return redirect(get_business_url(request, 'services:quotation_detail', quotation_id=quotation.pk))


@login_required
@employee_required()
@require_POST
def quotation_convert_to_order(request, quotation_id):
    """Convert quotation to service order"""
    from .models import Quotation
    
    quotation = get_object_or_404(Quotation, pk=quotation_id)
    
    try:
        order = quotation.convert_to_order()
        messages.success(request, f'Quotation {quotation.quotation_number} converted to order {order.order_number}.')
        return redirect(get_business_url(request, 'services:order_detail', pk=order.pk))
    except Exception as e:
        messages.error(request, f'Error converting quotation: {str(e)}')
        return redirect(get_business_url(request, 'services:quotation_detail', quotation_id=quotation.pk))


def generate_quotation_pdf(quotation, business):
    """Generate PDF content for quotation"""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm, inch
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
        from reportlab.lib.colors import HexColor
        import io
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm)
        
        elements = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=HexColor('#2563eb'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        # Title
        elements.append(Paragraph(f"QUOTATION {quotation.quotation_number}", title_style))
        elements.append(Spacer(1, 20))
        
        # Business and customer info table
        info_data = [
            ['From:', 'To:'],
            [f'{business.name}', f'{quotation.customer_name}'],
            [f'{business.address or ""}', f'{quotation.customer_email or ""}'],
            [f'{business.phone or ""}', f'{quotation.customer_phone or ""}'],
        ]
        
        info_table = Table(info_data, colWidths=[3*inch, 3*inch])
        info_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 20))
        
        # Quotation details
        details_data = [
            ['Quotation Date:', quotation.created_at.strftime('%B %d, %Y')],
            ['Valid Until:', quotation.valid_until.strftime('%B %d, %Y')],
            ['Status:', quotation.get_status_display()],
        ]
        
        if quotation.vehicle_registration:
            details_data.append(['Vehicle:', f'{quotation.vehicle_registration} - {quotation.vehicle_make} {quotation.vehicle_model}'])
        
        details_table = Table(details_data, colWidths=[2*inch, 4*inch])
        details_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(details_table)
        elements.append(Spacer(1, 30))
        
        # Items table
        items_data = [['Description', 'Quantity', 'Unit Price', 'Total']]
        
        for item in quotation.quotation_items.all():
            if item.service:
                description = item.service.name
            elif item.inventory_item:
                description = item.inventory_item.name
            else:
                description = item.description
            
            items_data.append([
                description,
                str(item.quantity),
                f'KES {item.unit_price:,.2f}',
                f'KES {item.total_price:,.2f}'
            ])
        
        items_table = Table(items_data, colWidths=[3*inch, 1*inch, 1.5*inch, 1.5*inch])
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#f3f4f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(items_table)
        elements.append(Spacer(1, 20))
        
        # Totals table
        totals_data = [
            ['Subtotal:', f'KES {quotation.subtotal:,.2f}'],
        ]
        
        if quotation.discount_amount > 0:
            totals_data.append(['Discount:', f'-KES {quotation.discount_amount:,.2f}'])
        
        if quotation.tax_amount > 0:
            totals_data.append(['Tax:', f'KES {quotation.tax_amount:,.2f}'])
        
        totals_data.append(['Total:', f'KES {quotation.total_amount:,.2f}'])
        
        totals_table = Table(totals_data, colWidths=[4*inch, 2*inch])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(totals_table)
        elements.append(Spacer(1, 30))
        
        # Terms and conditions
        if quotation.terms_and_conditions:
            elements.append(Paragraph('Terms and Conditions:', styles['Heading3']))
            elements.append(Paragraph(quotation.terms_and_conditions, styles['Normal']))
        
        # Build PDF
        doc.build(elements)
        
        buffer.seek(0)
        return buffer.getvalue()
        
    except ImportError:
        raise Exception("PDF generation library not available. Please install reportlab.")
    except Exception as e:
        raise Exception(f"Error generating PDF: {str(e)}")
