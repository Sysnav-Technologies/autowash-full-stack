import csv
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_protect
from django.db import transaction, models
from django.db.models import Q, Count, Sum, Avg, F, Case, When, Value, IntegerField
from django.utils import timezone
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.urls import reverse
from apps.core.decorators import employee_required, ajax_required, owner_required
from apps.core.utils import generate_unique_code, send_sms_notification, send_email_notification
from django.db.models.functions import Extract
from apps.payments.models import Payment
from .models import (
    Service, ServiceCategory, ServicePackage, ServiceOrder, 
    ServiceOrderItem, ServiceQueue, ServiceBay
)
from .forms import (
    ServiceForm, ServiceCategoryForm, ServicePackageForm, 
    ServiceOrderForm, QuickOrderForm, ServiceOrderItemForm, ServiceRatingForm
)
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger(__name__)

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
        # FIXED: Calculate average duration using database fields
        'avg_duration': ServiceOrderItem.objects.filter(
            service=service,
            completed_at__isnull=False,
            started_at__isnull=False
        ).aggregate(
            avg=Avg(
                Extract(F('completed_at') - F('started_at'), 'epoch') / 60.0
            )
        )['avg'] or 0,
    }
    
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
    
    if status:
        orders = orders.filter(status=status)
    if attendant_id:
        orders = orders.filter(assigned_attendant_id=attendant_id)
    if date_from:
        orders = orders.filter(created_at__date__gte=date_from)
    if date_to:
        orders = orders.filter(created_at__date__lte=date_to)
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
        role__in=['attendant', 'supervisor', 'manager'],
        is_active=True
    )
    
    # Statistics
    stats = {
        'total_orders': orders.count(),
        'pending_orders': orders.filter(status='pending').count(),
        'in_progress_orders': orders.filter(status='in_progress').count(),
        'completed_today': orders.filter(
            status='completed',
            actual_end_time__date=timezone.now().date()
        ).count(),
    }
    
    context = {
        'orders': orders_page,
        'attendants': attendants,
        'stats': stats,
        'status_choices': ServiceOrder.STATUS_CHOICES,
        'current_filters': {
            'status': status,
            'attendant': attendant_id,
            'date_from': date_from,
            'date_to': date_to,
            'search': search
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
                    if order.customer.phone and order.customer.receive_service_reminders:
                        send_sms_notification(
                            phone_number=str(order.customer.phone),
                            message=f"Your service order {order.order_number} has been created. Total: KES {order.total_amount}"
                        )
                    
                    messages.success(request, f'Order {order.order_number} created successfully!')
                    return redirect(get_business_url(request, 'services:order_detail', pk=order.pk))
                    
            except Exception as e:
                messages.error(request, f'Error creating order: {str(e)}')
    else:
        form = ServiceOrderForm()
    
    # Get services and categories for the form
    categories = ServiceCategory.objects.filter(is_active=True).prefetch_related('services')
    
    context = {
        'form': form,
        'categories': categories,
        'title': 'Create Service Order'
    }
    return render(request, 'services/order_form.html', context)

@csrf_protect
@employee_required()
@require_http_methods(["GET", "POST"])
def quick_order_view(request):
    """Quick order creation for walk-in customers"""
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Log the incoming data for debugging
                logger.info(f"Quick order POST data: {request.POST}")
                
                # Import here to avoid circular imports
                from apps.customers.models import Customer, Vehicle
                
                # Determine if this is an existing customer or new customer
                existing_customer_id = request.POST.get('existing_customer_id')
                customer = None
                
                if existing_customer_id:
                    # Existing customer
                    try:
                        customer = Customer.objects.get(id=existing_customer_id)
                        logger.info(f"Using existing customer: {customer.full_name}")
                    except Customer.DoesNotExist:
                        logger.error(f"Customer with ID {existing_customer_id} not found")
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({
                                'success': False,
                                'message': 'Selected customer not found',
                                'errors': {'customer': ['Customer not found']}
                            })
                        else:
                            messages.error(request, 'Selected customer not found')
                            return redirect(get_business_url(request, 'services:quick_order'))
                else:
                    # New customer - validate required fields
                    customer_name = request.POST.get('customer_name', '').strip()
                    customer_phone = request.POST.get('customer_phone', '').strip()
                    
                    if not customer_name or not customer_phone:
                        error_msg = 'Customer name and phone are required'
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
                        created_by_id=request.user.id
                    )
                    logger.info(f"Created new customer: {customer.full_name}")
                
                # Handle vehicle selection/creation
                existing_vehicle_id = request.POST.get('existing_vehicle_id')
                vehicle = None
                
                if existing_vehicle_id:
                    # Existing vehicle
                    try:
                        vehicle = Vehicle.objects.get(id=existing_vehicle_id, customer=customer)
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
                    # New vehicle - validate required fields
                    vehicle_registration = request.POST.get('vehicle_registration', '').strip().upper()
                    vehicle_make = request.POST.get('vehicle_make', '').strip()
                    vehicle_model = request.POST.get('vehicle_model', '').strip()
                    vehicle_color = request.POST.get('vehicle_color', '').strip()
                    vehicle_type = request.POST.get('vehicle_type', '').strip()
                    
                    if not all([vehicle_registration, vehicle_make, vehicle_model, vehicle_color, vehicle_type]):
                        error_msg = 'All vehicle fields are required'
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({
                                'success': False,
                                'message': error_msg,
                                'errors': {'vehicle': ['All vehicle information is required']}
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
                    
                    # Create new vehicle
                    vehicle = Vehicle.objects.create(
                        customer=customer,
                        registration_number=vehicle_registration,
                        make=vehicle_make,
                        model=vehicle_model,
                        color=vehicle_color,
                        vehicle_type=vehicle_type,
                        year=int(request.POST.get('vehicle_year', 2020)),
                        created_by_id=request.user.id
                    )
                    logger.info(f"Created new vehicle: {vehicle.registration_number}")
                
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
                    # Handle service package
                    selected_package_id = request.POST.get('selected_package')
                    if not selected_package_id:
                        raise ValueError("Package must be selected")
                    
                    try:
                        package = ServicePackage.objects.get(id=selected_package_id, is_active=True)
                        order.package = package
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
                    # Handle individual services
                    selected_services = request.POST.getlist('selected_services')
                    if not selected_services:
                        raise ValueError("At least one service must be selected")
                    
                    for service_id in selected_services:
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
                            logger.info(f"Added service: {service.name}")
                        except Service.DoesNotExist:
                            logger.warning(f"Service {service_id} not found, skipping")
                            continue
                
                # Calculate totals
                order.subtotal = total_amount
                order.calculate_totals()
                order.save()
                
                # Add to queue
                add_order_to_queue(order)
                
                logger.info(f"Order {order.order_number} created successfully")
                
                # Return appropriate response
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'message': f'Order {order.order_number} created successfully!',
                        'order_id': str(order.id),
                        'order_number': order.order_number,
                        'redirect_url': get_business_url(request, 'services:order_detail', pk=order.id)
                    })
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
    # Get popular services for quick selection
    popular_services = Service.objects.filter(
        is_active=True,
        is_popular=True
    ).order_by('display_order')[:8]

    # Get service packages
    service_packages = ServicePackage.objects.filter(
        is_active=True
    ).order_by('-is_popular', 'name')[:8]

    # Get service categories
    categories = ServiceCategory.objects.filter(is_active=True).prefetch_related('services')
    
    context = {
        'popular_services': popular_services,
        'categories': categories,
        'service_packages': service_packages, 
        'title': 'Quick Order (Walk-in Customer)'
    }
    return render(request, 'services/quick_order.html', context)

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
    
    # Get available attendants
    from apps.employees.models import Employee
    available_attendants = Employee.objects.filter(
        role__in=['attendant', 'supervisor'],
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

    context = {
        'order': order,
        'order_items': order_items,
        'queue_entry': queue_entry,
        'available_bays': available_bays,
        'available_attendants': available_attendants,
        'payment': payment,
        'payment_id': payment_id,
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
    
    # Update order status
    order.status = 'in_progress'
    order.actual_start_time = timezone.now()
    
    # Assign attendant if not already assigned
    if not order.assigned_attendant:
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
    if (hasattr(order.customer, 'phone') and order.customer.phone and 
        hasattr(order.customer, 'receive_service_reminders') and 
        order.customer.receive_service_reminders):
        try:
            send_sms_notification(
                phone_number=str(order.customer.phone),
                message=f"Your service has started! Order {order.order_number}. We'll notify you when complete."
            )
        except Exception as e:
            logger.error(f"Failed to send start SMS for order {order.order_number}: {str(e)}")
    
    messages.success(request, f'Service started for order {order.order_number}')
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
    
    # Complete all order items
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
    if (hasattr(order.customer, 'phone') and order.customer.phone and 
        hasattr(order.customer, 'receive_service_reminders') and 
        order.customer.receive_service_reminders):
        try:
            send_sms_notification(
                phone_number=str(order.customer.phone),
                message=f"Your service is complete! Order {order.order_number}. Total: KES {order.total_amount}. Thank you for choosing us!"
            )
        except Exception as e:
            logger.error(f"Failed to send completion SMS for order {order.order_number}: {str(e)}")
    
    messages.success(request, f'Service completed for order {order.order_number}')
    return redirect(get_business_url(request, 'services:order_detail', pk=order.pk))

@login_required
# Owner or manager required for queue management
@employee_required(['owner', 'manager'])
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
                'queue_number': entry.queue_number,
                'order_number': entry.order.order_number,
                'customer_name': entry.order.customer.display_name,
                'status': entry.status,
                'estimated_wait_time': entry.estimated_wait_time,
                'service_bay': entry.service_bay.name if entry.service_bay else None
            }
            for entry in queue_entries
        ],
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
            return redirect('services:detail', pk=service.pk)
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
    """Delete service (soft delete)"""
    service = get_object_or_404(Service, pk=pk)
    
    if request.method == 'POST':
        service.delete()  # Soft delete
        messages.success(request, f'Service "{service.name}" deleted successfully!')
        return redirect('services:list')
    
    context = {
        'service': service,
        'title': f'Delete Service - {service.name}'
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
            return redirect('services:category_list')
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
            return redirect('services:category_list')
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
    """Cancel service order"""
    order = get_object_or_404(ServiceOrder, id=order_id)
    
    if not order.can_be_cancelled:
        messages.error(request, 'This order cannot be cancelled.')
        return redirect('services:order_detail', pk=order.pk)
    
    cancellation_reason = request.POST.get('reason', '')
    
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
    return redirect('services:order_detail', pk=order.pk)

@login_required
@employee_required()
@require_POST
def pause_service(request, order_id):
    """Pause service"""
    order = get_object_or_404(ServiceOrder, id=order_id)
    
    if order.status != 'in_progress':
        messages.error(request, 'Service is not in progress.')
        return redirect('services:order_detail', pk=order.pk)
    
    # Record pause time in internal notes
    order.internal_notes += f"\nPaused by {request.employee.full_name} at {timezone.now()}"
    order.save()
    
    messages.success(request, 'Service paused.')
    return redirect('services:order_detail', pk=order.pk)

@login_required
@employee_required()
@require_POST
def resume_service(request, order_id):
    """Resume paused service"""
    order = get_object_or_404(ServiceOrder, id=order_id)
    
    if order.status != 'in_progress':
        messages.error(request, 'Service is not paused.')
        return redirect('services:order_detail', pk=order.pk)
    
    # Record resume time in internal notes
    order.internal_notes += f"\nResumed by {request.employee.full_name} at {timezone.now()}"
    order.save()
    
    messages.success(request, 'Service resumed.')
    return redirect('services:order_detail', pk=order.pk)

@login_required
@employee_required()
def process_payment(request, order_id):
    """Redirect to payments app for payment processing"""
    order = get_object_or_404(ServiceOrder, id=order_id)
    
    # Check if payment can be processed
    if not order.can_process_payment():
        messages.error(request, 'Payment cannot be processed for this order.')
        return redirect('services:order_detail', order_id=order.id)
    
    # Get tenant slug for proper URL routing
    tenant_slug = request.tenant.slug
    
    # Redirect with business slug
    return redirect(f'/business/{tenant_slug}/payments/create/{order.id}/')

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
        return redirect(f'/business/{tenant_slug}/payments/create/{order.id}/')
    
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
    """Update order payment status based on payments - with real-time updates"""
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
    """Attendant dashboard with current assignments"""
    # Get attendant's current assignments
    my_orders = ServiceOrder.objects.filter(
        assigned_attendant=request.employee,
        status__in=['confirmed', 'in_progress']
    ).select_related('customer', 'vehicle').order_by('-created_at')
    
    # Get queue entries for today
    today_queue = ServiceQueue.objects.filter(
        created_at__date=timezone.now().date(),
        status__in=['waiting', 'in_service']
    ).select_related('order', 'order__customer').order_by('queue_number')
    
    # Get my service items in progress
    my_service_items = ServiceOrderItem.objects.filter(
        assigned_to=request.employee,
        completed_at__isnull=True
    ).select_related('order', 'service')
    
    # Statistics
    stats = {
        'orders_today': ServiceOrder.objects.filter(
            assigned_attendant=request.employee,
            created_at__date=timezone.now().date()
        ).count(),
        'completed_today': ServiceOrder.objects.filter(
            assigned_attendant=request.employee,
            status='completed',
            actual_end_time__date=timezone.now().date()
        ).count(),
        'in_progress': my_orders.filter(status='in_progress').count(),
        'total_revenue_today': ServiceOrder.objects.filter(
            assigned_attendant=request.employee,
            status='completed',
            actual_end_time__date=timezone.now().date()
        ).aggregate(total=Sum('total_amount'))['total'] or 0
    }
    
    context = {
        'my_orders': my_orders,
        'today_queue': today_queue,
        'my_service_items': my_service_items,
        'stats': stats,
        'title': 'My Dashboard'
    }
    return render(request, 'services/attendant_dashboard.html', context)

@login_required
@employee_required()
def my_services_view(request):
    """View attendant's assigned services"""
    my_orders = ServiceOrder.objects.filter(
        assigned_attendant=request.employee
    ).select_related('customer', 'vehicle').order_by('-created_at')
    
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
            quantity = int(quantities[i]) if i < len(quantities) else 1
            
            total_price += service.base_price * quantity
            estimated_duration += service.estimated_duration * quantity
        except (Service.DoesNotExist, ValueError):
            continue
    
    # Calculate tax (16% VAT for Kenya)
    tax_amount = total_price * Decimal('0.16')
    total_with_tax = total_price + tax_amount
    
    return JsonResponse({
        'subtotal': float(total_price),
        'tax_amount': float(tax_amount),
        'total_amount': float(total_with_tax),
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
            return redirect('services:detail', pk=service.pk)
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
    """Delete service (soft delete)"""
    service = get_object_or_404(Service, pk=pk)
    
    if request.method == 'POST':
        service.delete()  # Soft delete
        messages.success(request, f'Service "{service.name}" deleted successfully!')
        return redirect('services:list')
    
    context = {
        'service': service,
        'title': f'Delete Service - {service.name}'
    }
    return render(request, 'services/service_confirm_delete.html', context)

# Category Management Views
# Complete fixed category views for services/views.py

@login_required
@employee_required(['owner', 'manager'])
def category_list_view(request):
    """List service categories"""
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
            return redirect('services:category_list')
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
            return redirect('services:category_list')
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
def order_edit_view(request, pk):
    """Edit service order"""
    order = get_object_or_404(ServiceOrder, pk=pk)
    
    # Only allow editing pending/confirmed orders
    if order.status not in ['pending', 'confirmed']:
        messages.error(request, 'This order cannot be edited.')
        return redirect('services:order_detail', pk=order.pk)
    
    if request.method == 'POST':
        form = ServiceOrderForm(request.POST, instance=order)
        if form.is_valid():
            order = form.save()
            
            # Recalculate totals if services changed
            order.calculate_totals()
            order.save()
            
            messages.success(request, f'Order {order.order_number} updated successfully!')
            return redirect('services:order_detail', pk=order.pk)
    else:
        form = ServiceOrderForm(instance=order)
    
    context = {
        'form': form,
        'order': order,
        'title': f'Edit Order - {order.order_number}'
    }
    return render(request, 'services/order_form.html', context)

@login_required
@employee_required()
def order_print_view(request, pk):
    """Print order details"""
    order = get_object_or_404(ServiceOrder, pk=pk)
    order_items = order.order_items.all().select_related('service')
    
    context = {
        'order': order,
        'order_items': order_items,
        'title': f'Print Order - {order.order_number}'
    }
    return render(request, 'services/order_print.html', context)

# Service Action Views
@login_required
@employee_required()
@require_POST
def cancel_service(request, order_id):
    """Cancel service order"""
    order = get_object_or_404(ServiceOrder, id=order_id)
    
    if not order.can_be_cancelled:
        messages.error(request, 'This order cannot be cancelled.')
        return redirect('services:order_detail', pk=order.pk)
    
    cancellation_reason = request.POST.get('reason', '')
    
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
    return redirect('services:order_detail', pk=order.pk)

@login_required
@employee_required()
@require_POST
def pause_service(request, order_id):
    """Pause service"""
    order = get_object_or_404(ServiceOrder, id=order_id)
    
    if order.status != 'in_progress':
        messages.error(request, 'Service is not in progress.')
        return redirect('services:order_detail', pk=order.pk)
    
    order.internal_notes += f"\nPaused by {request.employee.full_name} at {timezone.now()}"
    order.save()
    
    messages.success(request, 'Service paused.')
    return redirect('services:order_detail', pk=order.pk)

@login_required
@employee_required()
@require_POST
def resume_service(request, order_id):
    """Resume paused service"""
    order = get_object_or_404(ServiceOrder, id=order_id)
    
    if order.status != 'in_progress':
        messages.error(request, 'Service is not paused.')
        return redirect('services:order_detail', pk=order.pk)
    
    order.internal_notes += f"\nResumed by {request.employee.full_name} at {timezone.now()}"
    order.save()
    
    messages.success(request, 'Service resumed.')
    return redirect('services:order_detail', pk=order.pk)

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
    packages = ServicePackage.objects.filter(is_active=True).annotate(
        service_count=Count('services')
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
            return redirect('services:package_detail', pk=package.pk)
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
            return redirect('services:package_detail', pk=package.pk)
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
            return redirect('services:bay_list')
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
        return redirect('services:bay_list')
    
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
        return redirect('services:order_detail', pk=order.pk)
        
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
        return redirect('services:order_detail', pk=order.pk)
    
    if request.method == 'POST':
        form = ServiceRatingForm(request.POST)
        if form.is_valid():
            order.customer_rating = form.cleaned_data['overall_rating']
            order.customer_feedback = form.cleaned_data.get('comments', '')
            order.save()
            
            messages.success(request, 'Thank you for your feedback!')
            return redirect('services:order_detail', pk=order.pk)
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
    
    orders = ServiceOrder.objects.filter(
        created_at__date=date
    ).select_related('customer', 'vehicle', 'assigned_attendant')
    
    stats = {
        'total_orders': orders.count(),
        'completed_orders': orders.filter(status='completed').count(),
        'total_revenue': orders.filter(status='completed').aggregate(
            total=Sum('total_amount')
        )['total'] or 0,
        'avg_service_time': orders.filter(
            status='completed',
            actual_start_time__isnull=False,
            actual_end_time__isnull=False
        ).aggregate(
            avg=Avg(F('actual_end_time') - F('actual_start_time'))
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
    
    # Employee performance
    employee_performance = ServiceOrder.objects.filter(
        status='completed',
        actual_end_time__date__range=[date_from, date_to]
    ).values(
        'assigned_attendant__employee_id',
        'assigned_attendant__first_name',
        'assigned_attendant__last_name'
    ).annotate(
        orders_completed=Count('id'),
        total_revenue=Sum('total_amount'),
        avg_rating=Avg('customer_rating'),
        avg_service_time=Avg(F('actual_end_time') - F('actual_start_time'))
    ).order_by('-orders_completed')
    
    context = {
        'employee_performance': employee_performance,
        'date_from': date_from,
        'date_to': date_to,
        'title': 'Performance Report'
    }
    return render(request, 'services/performance_report.html', context)

# Attendant Dashboard Views
@login_required
@employee_required()
def attendant_dashboard(request):
    """Attendant dashboard with current assignments"""
    my_orders = ServiceOrder.objects.filter(
        assigned_attendant=request.employee,
        status__in=['confirmed', 'in_progress']
    ).select_related('customer', 'vehicle').order_by('-created_at')
    
    today_queue = ServiceQueue.objects.filter(
        created_at__date=timezone.now().date(),
        status__in=['waiting', 'in_service']
    ).select_related('order', 'order__customer').order_by('queue_number')
    
    my_service_items = ServiceOrderItem.objects.filter(
        assigned_to=request.employee,
        completed_at__isnull=True
    ).select_related('order', 'service')
    
    # Statistics
    stats = {
        'orders_today': ServiceOrder.objects.filter(
            assigned_attendant=request.employee,
            created_at__date=timezone.now().date()
        ).count(),
        'completed_today': ServiceOrder.objects.filter(
            assigned_attendant=request.employee,
            status='completed',
            actual_end_time__date=timezone.now().date()
        ).count(),
        'in_progress': my_orders.filter(status='in_progress').count(),
        'total_revenue_today': ServiceOrder.objects.filter(
            assigned_attendant=request.employee,
            status='completed',
            actual_end_time__date=timezone.now().date()
        ).aggregate(total=Sum('total_amount'))['total'] or 0
    }
    
    context = {
        'my_orders': my_orders,
        'today_queue': today_queue,
        'my_service_items': my_service_items,
        'stats': stats,
        'title': 'My Dashboard'
    }
    return render(request, 'services/attendant_dashboard.html', context)

@login_required
@employee_required()
def my_services_view(request):
    """View attendant's assigned services"""
    my_orders = ServiceOrder.objects.filter(
        assigned_attendant=request.employee
    ).select_related('customer', 'vehicle').order_by('-created_at')
    
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
                    created_by_id=request.user.id
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
                            created_by_id=request.user.id
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
                return redirect('services:order_detail', pk=order.pk)
                
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
def calculate_order_price(request):
    """Calculate order price via AJAX"""
    service_ids = request.POST.getlist('service_ids[]')
    quantities = request.POST.getlist('quantities[]')
    
    total_price = 0
    estimated_duration = 0
    
    for i, service_id in enumerate(service_ids):
        try:
            service = Service.objects.get(id=service_id)
            quantity = int(quantities[i]) if i < len(quantities) else 1
            
            total_price += service.base_price * quantity
            estimated_duration += service.estimated_duration * quantity
        except (Service.DoesNotExist, ValueError):
            continue
    
    # Calculate tax (16% VAT for Kenya)
    tax_amount = total_price * Decimal('0.16')
    total_with_tax = total_price + tax_amount
    
    return JsonResponse({
        'subtotal': float(total_price),
        'tax_amount': float(tax_amount),
        'total_amount': float(total_with_tax),
        'estimated_duration': estimated_duration
    })

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

# Helper Functions
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


