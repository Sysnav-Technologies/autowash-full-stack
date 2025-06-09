from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.db import transaction, models  # Added models import here
from django.db.models import Q, Count, Sum, Avg, F, Case, When, Value, IntegerField  # Added missing imports
from django.utils import timezone
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.urls import reverse
from apps.core.decorators import employee_required, ajax_required
from apps.core.utils import generate_unique_code, send_sms_notification, send_email_notification
from .models import (
    Service, ServiceCategory, ServicePackage, ServiceOrder, 
    ServiceOrderItem, ServiceQueue, ServiceBay
)
from .forms import (
    ServiceForm, ServiceCategoryForm, ServicePackageForm, 
    ServiceOrderForm, QuickOrderForm, ServiceOrderItemForm
)
from datetime import datetime, timedelta
import json

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
            return redirect('services:detail', pk=service.pk)
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
        'avg_duration': ServiceOrderItem.objects.filter(
            service=service,
            completed_at__isnull=False
        ).exclude(started_at__isnull=True).extra(
            select={'duration': 'EXTRACT(EPOCH FROM (completed_at - started_at))/60'}
        ).aggregate(avg=Avg('duration'))['avg'] or 0,
    }
    
    context = {
        'service': service,
        'recent_orders': recent_orders,
        'stats': stats,
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
                    return redirect('services:order_detail', pk=order.pk)
                    
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

@login_required
@employee_required()
def quick_order_view(request):
    """Quick order creation for walk-in customers"""
    if request.method == 'POST':
        form = QuickOrderForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Create or get customer
                    from apps.customers.models import Customer, Vehicle
                    
                    customer_data = form.cleaned_data
                    customer, created = Customer.objects.get_or_create(
                        phone=customer_data['customer_phone'],
                        defaults={
                            'first_name': customer_data['customer_name'].split()[0],
                            'last_name': ' '.join(customer_data['customer_name'].split()[1:]),
                            'customer_id': generate_unique_code('CUST', 6),
                            'created_by': request.user
                        }
                    )
                    
                    # Create or get vehicle
                    vehicle, created = Vehicle.objects.get_or_create(
                        registration_number=customer_data['vehicle_registration'].upper(),
                        defaults={
                            'customer': customer,
                            'make': customer_data['vehicle_make'],
                            'model': customer_data['vehicle_model'],
                            'color': customer_data['vehicle_color'],
                            'vehicle_type': customer_data.get('vehicle_type', 'sedan'),
                            'year': customer_data.get('vehicle_year', timezone.now().year),
                            'created_by': request.user
                        }
                    )
                    
                    # Create order
                    order = ServiceOrder.objects.create(
                        customer=customer,
                        vehicle=vehicle,
                        assigned_attendant=request.employee,
                        status='confirmed',
                        priority='normal',
                        created_by=request.user
                    )
                    
                    # Add selected services
                    service_ids = form.cleaned_data['selected_services']
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
                    
                    messages.success(request, f'Quick order {order.order_number} created successfully!')
                    return redirect('services:order_detail', pk=order.pk)
                    
            except Exception as e:
                messages.error(request, f'Error creating quick order: {str(e)}')
    else:
        form = QuickOrderForm()
    
    # Get popular services for quick selection
    popular_services = Service.objects.filter(
        is_active=True,
        is_popular=True
    ).order_by('display_order')[:8]
    
    context = {
        'form': form,
        'popular_services': popular_services,
        'title': 'Quick Order (Walk-in Customer)'
    }
    return render(request, 'services/quick_order.html', context)

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
    
    context = {
        'order': order,
        'order_items': order_items,
        'queue_entry': queue_entry,
        'available_bays': available_bays,
        'available_attendants': available_attendants,
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
        return redirect('services:order_detail', pk=order.pk)
    
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
        queue_entry.status = 'in_service'
        queue_entry.actual_start_time = timezone.now()
        queue_entry.save()
    
    # Assign service bay if provided
    bay_id = request.POST.get('service_bay')
    if bay_id:
        try:
            bay = ServiceBay.objects.get(id=bay_id)
            bay.assign_order(order)
        except ServiceBay.DoesNotExist:
            pass
    
    messages.success(request, f'Service started for order {order.order_number}')
    return redirect('services:order_detail', pk=order.pk)

@login_required
@employee_required()
@require_POST
def complete_service(request, order_id):
    """Complete service for an order"""
    order = get_object_or_404(ServiceOrder, id=order_id)
    
    # Check if order can be completed
    if order.status != 'in_progress':
        messages.error(request, 'Order is not in progress.')
        return redirect('services:order_detail', pk=order.pk)
    
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
    if order.current_bay.exists():
        bay = order.current_bay.first()
        bay.complete_service()
    
    # Send completion notification
    if order.customer.phone and order.customer.receive_service_reminders:
        send_sms_notification(
            phone_number=str(order.customer.phone),
            message=f"Your service is complete! Order {order.order_number}. Total: KES {order.total_amount}. Thank you for choosing us!"
        )
    
    messages.success(request, f'Service completed for order {order.order_number}')
    return redirect('services:order_detail', pk=order.pk)

@login_required
@employee_required()
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