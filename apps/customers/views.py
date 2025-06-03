from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.db import transaction
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.urls import reverse
from apps.core.decorators import employee_required, ajax_required
from apps.core.utils import generate_unique_code, send_sms_notification, send_email_notification
from .models import (
    Customer, Vehicle, CustomerNote, CustomerDocument, 
    CustomerFeedback, LoyaltyProgram
)
from .forms import (
    CustomerForm, VehicleForm, CustomerNoteForm, 
    CustomerDocumentForm, CustomerFeedbackForm, CustomerSearchForm
)
import json

@login_required
@employee_required()
def customer_list_view(request):
    """List all customers with search and filtering"""
    customers = Customer.objects.all().select_related().prefetch_related('vehicles')
    
    # Search and filters
    search_form = CustomerSearchForm(request.GET)
    if search_form.is_valid():
        search_query = search_form.cleaned_data.get('search')
        customer_type = search_form.cleaned_data.get('customer_type')
        is_vip = search_form.cleaned_data.get('is_vip')
        is_active = search_form.cleaned_data.get('is_active')
        
        if search_query:
            customers = customers.filter(
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(company_name__icontains=search_query) |
                Q(customer_id__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(phone__icontains=search_query) |
                Q(vehicles__registration_number__icontains=search_query)
            ).distinct()
        
        if customer_type:
            customers = customers.filter(customer_type=customer_type)
        
        if is_vip is not None:
            customers = customers.filter(is_vip=is_vip)
        
        if is_active is not None:
            customers = customers.filter(is_active=is_active)
    
    # Sorting
    sort_by = request.GET.get('sort', 'created_at')
    if sort_by in ['first_name', 'last_name', 'created_at', 'total_spent', 'loyalty_points']:
        if request.GET.get('order') == 'desc':
            sort_by = f'-{sort_by}'
        customers = customers.order_by(sort_by)
    
    # Pagination
    paginator = Paginator(customers, 20)
    page = request.GET.get('page')
    customers_page = paginator.get_page(page)
    
    # Statistics
    stats = {
        'total_customers': Customer.objects.count(),
        'active_customers': Customer.objects.filter(is_active=True).count(),
        'vip_customers': Customer.objects.filter(is_vip=True).count(),
        'new_this_month': Customer.objects.filter(
            created_at__month=timezone.now().month,
            created_at__year=timezone.now().year
        ).count(),
    }
    
    context = {
        'customers': customers_page,
        'search_form': search_form,
        'stats': stats,
        'title': 'Customer Management'
    }
    return render(request, 'customers/customer_list.html', context)

@login_required
@employee_required()
def customer_create_view(request):
    """Create new customer"""
    if request.method == 'POST':
        customer_form = CustomerForm(request.POST)
        vehicle_form = VehicleForm(request.POST) if request.POST.get('add_vehicle') else None
        
        if customer_form.is_valid() and (not vehicle_form or vehicle_form.is_valid()):
            try:
                with transaction.atomic():
                    # Create customer
                    customer = customer_form.save(commit=False)
                    customer.customer_id = generate_unique_code('CUST', 6)
                    customer.created_by = request.user
                    customer.save()
                    
                    # Create vehicle if provided
                    if vehicle_form and vehicle_form.is_valid():
                        vehicle = vehicle_form.save(commit=False)
                        vehicle.customer = customer
                        vehicle.created_by = request.user
                        vehicle.save()
                    
                    # Send welcome message if requested
                    if customer_form.cleaned_data.get('send_welcome_message'):
                        if customer.phone:
                            send_sms_notification(
                                phone_number=str(customer.phone),
                                message=f"Welcome to {request.business.name}! Your customer ID is {customer.customer_id}."
                            )
                    
                    messages.success(request, f'Customer {customer.display_name} created successfully!')
                    
                    # Redirect based on request
                    if request.POST.get('create_another'):
                        return redirect('customers:create')
                    else:
                        return redirect('customers:detail', pk=customer.pk)
                        
            except Exception as e:
                messages.error(request, f'Error creating customer: {str(e)}')
    else:
        customer_form = CustomerForm()
        vehicle_form = VehicleForm()
    
    context = {
        'customer_form': customer_form,
        'vehicle_form': vehicle_form,
        'title': 'Add New Customer'
    }
    return render(request, 'customers/customer_form.html', context)

@login_required
@employee_required()
def customer_detail_view(request, pk):
    """Customer detail view with complete information"""
    customer = get_object_or_404(Customer, pk=pk)
    
    # Get related data
    vehicles = customer.vehicles.filter(is_active=True)
    recent_orders = None  # Will be populated when services app is ready
    notes = customer.notes.all()[:5]
    documents = customer.documents.all()
    feedback = customer.feedback.all()[:3]
    
    # Calculate customer statistics
    from apps.services.models import ServiceOrder
    try:
        order_stats = ServiceOrder.objects.filter(customer=customer).aggregate(
            total_orders=Count('id'),
            total_spent=Sum('total_amount'),
            avg_order_value=Avg('total_amount')
        )
        recent_orders = ServiceOrder.objects.filter(customer=customer).order_by('-created_at')[:5]
    except:
        order_stats = {'total_orders': 0, 'total_spent': 0, 'avg_order_value': 0}
        recent_orders = []
    
    # Loyalty program info
    loyalty_program = LoyaltyProgram.objects.filter(is_active=True).first()
    customer_tier = None
    if loyalty_program:
        customer_tier = loyalty_program.get_customer_tier(customer)
    
    context = {
        'customer': customer,
        'vehicles': vehicles,
        'recent_orders': recent_orders,
        'notes': notes,
        'documents': documents,
        'feedback': feedback,
        'order_stats': order_stats,
        'loyalty_program': loyalty_program,
        'customer_tier': customer_tier,
        'title': f'Customer - {customer.display_name}'
    }
    return render(request, 'customers/customer_detail.html', context)

@login_required
@employee_required()
def customer_edit_view(request, pk):
    """Edit customer information"""
    customer = get_object_or_404(Customer, pk=pk)
    
    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.updated_by = request.user
            customer.save()
            
            messages.success(request, f'Customer {customer.display_name} updated successfully!')
            return redirect('customers:detail', pk=customer.pk)
    else:
        form = CustomerForm(instance=customer)
    
    context = {
        'form': form,
        'customer': customer,
        'title': f'Edit Customer - {customer.display_name}'
    }
    return render(request, 'customers/customer_edit.html', context)

@login_required
@employee_required()
def vehicle_create_view(request, customer_pk):
    """Add vehicle to customer"""
    customer = get_object_or_404(Customer, pk=customer_pk)
    
    if request.method == 'POST':
        form = VehicleForm(request.POST)
        if form.is_valid():
            vehicle = form.save(commit=False)
            vehicle.customer = customer
            vehicle.created_by = request.user
            vehicle.save()
            
            messages.success(request, f'Vehicle {vehicle.registration_number} added successfully!')
            return redirect('customers:detail', pk=customer.pk)
    else:
        form = VehicleForm()
    
    context = {
        'form': form,
        'customer': customer,
        'title': f'Add Vehicle - {customer.display_name}'
    }
    return render(request, 'customers/vehicle_form.html', context)

@login_required
@employee_required()
def vehicle_edit_view(request, pk):
    """Edit vehicle information"""
    vehicle = get_object_or_404(Vehicle, pk=pk)
    
    if request.method == 'POST':
        form = VehicleForm(request.POST, instance=vehicle)
        if form.is_valid():
            vehicle = form.save(commit=False)
            vehicle.updated_by = request.user
            vehicle.save()
            
            messages.success(request, f'Vehicle {vehicle.registration_number} updated successfully!')
            return redirect('customers:detail', pk=vehicle.customer.pk)
    else:
        form = VehicleForm(instance=vehicle)
    
    context = {
        'form': form,
        'vehicle': vehicle,
        'title': f'Edit Vehicle - {vehicle.registration_number}'
    }
    return render(request, 'customers/vehicle_form.html', context)

@login_required
@employee_required()
def customer_note_create_view(request, customer_pk):
    """Add note to customer"""
    customer = get_object_or_404(Customer, pk=customer_pk)
    
    if request.method == 'POST':
        form = CustomerNoteForm(request.POST)
        if form.is_valid():
            note = form.save(commit=False)
            note.customer = customer
            note.created_by = request.user
            note.save()
            
            messages.success(request, 'Note added successfully!')
            return redirect('customers:detail', pk=customer.pk)
    else:
        form = CustomerNoteForm()
    
    context = {
        'form': form,
        'customer': customer,
        'title': f'Add Note - {customer.display_name}'
    }
    return render(request, 'customers/note_form.html', context)

@login_required
@employee_required()
@ajax_required
def customer_search_ajax(request):
    """AJAX customer search for quick lookups"""
    query = request.GET.get('q', '').strip()
    customers = []
    
    if len(query) >= 2:
        customer_qs = Customer.objects.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(company_name__icontains=query) |
            Q(customer_id__icontains=query) |
            Q(phone__icontains=query) |
            Q(vehicles__registration_number__icontains=query)
        ).distinct()[:10]
        
        customers = [
            {
                'id': customer.id,
                'customer_id': customer.customer_id,
                'name': customer.display_name,
                'phone': str(customer.phone) if customer.phone else '',
                'email': customer.email,
                'is_vip': customer.is_vip,
                'vehicles': [
                    {
                        'id': vehicle.id,
                        'registration': vehicle.registration_number,
                        'make_model': f"{vehicle.make} {vehicle.model}",
                        'year': vehicle.year
                    }
                    for vehicle in customer.vehicles.filter(is_active=True)
                ]
            }
            for customer in customer_qs
        ]
    
    return JsonResponse({'customers': customers})

@login_required
@employee_required()
@ajax_required
def vehicle_search_ajax(request):
    """AJAX vehicle search by registration number"""
    query = request.GET.get('q', '').strip()
    vehicles = []
    
    if len(query) >= 2:
        vehicle_qs = Vehicle.objects.select_related('customer').filter(
            registration_number__icontains=query,
            is_active=True
        )[:10]
        
        vehicles = [
            {
                'id': vehicle.id,
                'registration_number': vehicle.registration_number,
                'make_model': f"{vehicle.make} {vehicle.model} ({vehicle.year})",
                'color': vehicle.color,
                'customer': {
                    'id': vehicle.customer.id,
                    'name': vehicle.customer.display_name,
                    'customer_id': vehicle.customer.customer_id,
                    'phone': str(vehicle.customer.phone) if vehicle.customer.phone else '',
                }
            }
            for vehicle in vehicle_qs
        ]
    
    return JsonResponse({'vehicles': vehicles})

@login_required
@employee_required()
def customer_feedback_view(request, customer_pk):
    """View customer feedback"""
    customer = get_object_or_404(Customer, pk=customer_pk)
    feedback_list = customer.feedback.all().order_by('-created_at')
    
    # Pagination
    paginator = Paginator(feedback_list, 10)
    page = request.GET.get('page')
    feedback_page = paginator.get_page(page)
    
    # Calculate average ratings
    if feedback_list.exists():
        avg_ratings = feedback_list.aggregate(
            overall=Avg('overall_rating'),
            service_quality=Avg('service_quality'),
            staff_friendliness=Avg('staff_friendliness'),
            cleanliness=Avg('cleanliness'),
            value_for_money=Avg('value_for_money')
        )
    else:
        avg_ratings = {}
    
    context = {
        'customer': customer,
        'feedback': feedback_page,
        'avg_ratings': avg_ratings,
        'title': f'Feedback - {customer.display_name}'
    }
    return render(request, 'customers/customer_feedback.html', context)

@login_required
@employee_required()
def customer_documents_view(request, customer_pk):
    """View customer documents"""
    customer = get_object_or_404(Customer, pk=customer_pk)
    
    if request.method == 'POST':
        form = CustomerDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.customer = customer
            document.created_by = request.user
            document.save()
            
            messages.success(request, 'Document uploaded successfully!')
            return redirect('customers:documents', customer_pk=customer.pk)
    else:
        form = CustomerDocumentForm()
    
    documents = customer.documents.all().order_by('-created_at')
    
    context = {
        'customer': customer,
        'documents': documents,
        'form': form,
        'title': f'Documents - {customer.display_name}'
    }
    return render(request, 'customers/customer_documents.html', context)

@login_required
@employee_required()
def loyalty_dashboard_view(request):
    """Loyalty program dashboard"""
    loyalty_program = LoyaltyProgram.objects.filter(is_active=True).first()
    
    if not loyalty_program:
        messages.info(request, 'No active loyalty program found.')
        return redirect('customers:list')
    
    # Get customers by tier
    customers = Customer.objects.filter(is_active=True)
    tier_stats = {
        'bronze': 0,
        'silver': 0,
        'gold': 0,
        'platinum': 0
    }
    
    for customer in customers:
        tier = loyalty_program.get_customer_tier(customer)
        tier_stats[tier] += 1
    
    # Top customers by points
    top_customers = customers.order_by('-loyalty_points')[:10]
    
    # Recent activity (would need to implement loyalty transactions)
    recent_activity = []
    
    context = {
        'loyalty_program': loyalty_program,
        'tier_stats': tier_stats,
        'top_customers': top_customers,
        'recent_activity': recent_activity,
        'total_customers': customers.count(),
        'title': 'Loyalty Program Dashboard'
    }
    return render(request, 'customers/loyalty_dashboard.html', context)

@login_required
@employee_required()
@require_POST
def toggle_customer_vip(request, pk):
    """Toggle customer VIP status"""
    customer = get_object_or_404(Customer, pk=pk)
    customer.is_vip = not customer.is_vip
    customer.save(update_fields=['is_vip'])
    
    status = 'VIP' if customer.is_vip else 'regular'
    messages.success(request, f'{customer.display_name} is now a {status} customer.')
    
    return redirect('customers:detail', pk=customer.pk)

@login_required
@employee_required()
@require_POST
def deactivate_customer(request, pk):
    """Deactivate customer account"""
    customer = get_object_or_404(Customer, pk=pk)
    customer.is_active = False
    customer.save(update_fields=['is_active'])
    
    messages.success(request, f'{customer.display_name} account has been deactivated.')
    return redirect('customers:detail', pk=customer.pk)

@login_required
@employee_required()
def customer_export_view(request):
    """Export customer data to CSV/Excel"""
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="customers.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Customer ID', 'Name', 'Type', 'Email', 'Phone', 'City', 
        'Total Orders', 'Total Spent', 'Loyalty Points', 'VIP Status', 
        'Active Status', 'Created Date'
    ])
    
    customers = Customer.objects.all().select_related()
    for customer in customers:
        writer.writerow([
            customer.customer_id,
            customer.display_name,
            customer.get_customer_type_display(),
            customer.email,
            str(customer.phone) if customer.phone else '',
            customer.city,
            customer.total_orders,
            customer.total_spent,
            customer.loyalty_points,
            'Yes' if customer.is_vip else 'No',
            'Yes' if customer.is_active else 'No',
            customer.created_at.strftime('%Y-%m-%d')
        ])
    
    return response