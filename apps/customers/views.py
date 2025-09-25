import csv
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
from apps.core.logging_utils import AutoWashLogger
from .models import (
    Customer, Vehicle, CustomerNote, CustomerDocument, 
    CustomerFeedback, LoyaltyProgram
)
from .forms import (
    CustomerForm, VehicleForm, CustomerNoteForm, 
    CustomerDocumentForm, CustomerFeedbackForm, CustomerSearchForm
)
import json
import uuid

def _convert_uuid(pk):
    """Convert string UUID to UUID object if needed"""
    try:
        if isinstance(pk, str):
            return uuid.UUID(pk)
    except (ValueError, TypeError):
        pass
    return pk

def get_customer_urls(request):
    """Generate all customer URLs for templates with tenant slug."""
    tenant_slug = request.tenant.slug
    base_url = f"/business/{tenant_slug}/customers"
    return {
        'list': f"{base_url}/",
        'create': f"{base_url}/create/",
        'detail': f"{base_url}/{{pk}}/",
        'edit': f"{base_url}/{{pk}}/edit/",
        'toggle_vip': f"{base_url}/{{pk}}/toggle-vip/",
        'deactivate': f"{base_url}/{{pk}}/deactivate/",
        'vehicle_create': f"{base_url}/{{customer_pk}}/vehicles/add/",
        'vehicle_edit': f"{base_url}/vehicles/{{pk}}/edit/",
        'note_create': f"{base_url}/{{customer_pk}}/notes/add/",
        'documents': f"{base_url}/{{customer_pk}}/documents/",
        'feedback': f"{base_url}/{{customer_pk}}/feedback/",
        'search_ajax': f"{base_url}/ajax/search/",
        'vehicle_search_ajax': f"{base_url}/ajax/vehicles/search/",
        'loyalty_dashboard': f"{base_url}/loyalty/",
        'export': f"{base_url}/export/",
        'import': f"{base_url}/import/",
    }

def get_business_url(request, url_name, **kwargs):
    """Helper to generate URLs with business slug for customers."""
    tenant_slug = request.tenant.slug
    base_url = f"/business/{tenant_slug}/customers"
    url_mapping = {
        'customers:list': f"{base_url}/",
        'customers:create': f"{base_url}/create/",
        'customers:detail': f"{base_url}/{{pk}}/",
        'customers:edit': f"{base_url}/{{pk}}/edit/",
        'customers:toggle_vip': f"{base_url}/{{pk}}/toggle-vip/",
        'customers:deactivate': f"{base_url}/{{pk}}/deactivate/",
        'customers:vehicle_create': f"{base_url}/{{customer_pk}}/vehicles/add/",
        'customers:vehicle_edit': f"{base_url}/vehicles/{{pk}}/edit/",
        'customers:note_create': f"{base_url}/{{customer_pk}}/notes/add/",
        'customers:documents': f"{base_url}/{{customer_pk}}/documents/",
        'customers:feedback': f"{base_url}/{{customer_pk}}/feedback/",
        'customers:search_ajax': f"{base_url}/ajax/search/",
        'customers:vehicle_search_ajax': f"{base_url}/ajax/vehicles/search/",
        'customers:loyalty_dashboard': f"{base_url}/loyalty/",
        'customers:export': f"{base_url}/export/",
        'customers:import': f"{base_url}/import/",
    }
    url = url_mapping.get(url_name, f"{base_url}/")
    for key, value in kwargs.items():
        url = url.replace(f"{{{key}}}", str(value))
    return url

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
        'title': 'Customer Management',
        'urls': get_customer_urls(request),
    }
    return render(request, 'customers/customer_list.html', context)

@login_required
@employee_required()
def customer_create_view(request):
    """Create new customer - FIXED UUID serialization"""
    if request.method == 'POST':
        customer_form = CustomerForm(request.POST)
        vehicle_form = VehicleForm(request.POST) if request.POST.get('add_vehicle') else None
        
        if customer_form.is_valid() and (not vehicle_form or vehicle_form.is_valid()):
            try:
                with transaction.atomic():
                    # Create customer
                    customer = customer_form.save(commit=False)
                    customer.customer_id = generate_unique_code('CUST', 6)
                    customer.created_by = request.user  # Use user object directly
                    customer.save()
                    
                    # Log customer creation
                    AutoWashLogger.log_business_event(
                        event_type='customer_created',
                        customer=customer,
                        details={
                            'customer_id': customer.customer_id,
                            'customer_name': customer.display_name,
                            'created_by': request.user.username,
                            'employee_id': getattr(request, 'employee', None).employee_id if getattr(request, 'employee', None) else None,
                            'has_vehicle': bool(vehicle_form and vehicle_form.is_valid())
                        },
                        request=request
                    )
                    
                    # Log tenant activity
                    AutoWashLogger.log_tenant_action(
                        action='customer_created',
                        user=request.user,
                        details={
                            'customer_id': customer.customer_id,
                            'customer_name': customer.display_name
                        },
                        request=request
                    )
                    
                    # Create vehicle if provided
                    if vehicle_form and vehicle_form.is_valid():
                        vehicle = vehicle_form.save(commit=False)
                        vehicle.customer = customer
                        vehicle.created_by = request.user  # Use user object directly
                        vehicle.save()
                    
                    # Send welcome message if requested
                    if customer_form.cleaned_data.get('send_welcome_message'):
                        if customer.phone:
                            try:
                                send_sms_notification(
                                    phone_number=str(customer.phone),
                                    message=f"Welcome to {request.business.name}! Your customer ID is {customer.customer_id}."
                                )
                            except Exception as sms_error:
                                # Don't fail the whole operation if SMS fails
                                messages.warning(request, f'Customer created but SMS failed: {str(sms_error)}')
                    
                    # Success message with string conversion
                    success_message = f'Customer {customer.display_name} created successfully!'
                    messages.success(request, success_message)
                    
                    # Redirect based on request - Django handles UUID automatically
                    if request.POST.get('create_another'):
                        return redirect(get_business_url(request, 'customers:create'))
                    else:
                        return redirect(get_business_url(request, 'customers:detail', pk=customer.pk))
                        
            except Exception as e:
                # Handle any other errors
                error_message = f'Error creating customer: {str(e)}'
                messages.error(request, error_message)
                print(f"Customer creation error: {e}")  # For debugging
    else:
        customer_form = CustomerForm()
        vehicle_form = VehicleForm()
    
    context = {
        'customer_form': customer_form,
        'vehicle_form': vehicle_form,
        'title': 'Add New Customer',
        'urls': get_customer_urls(request),
    }
    return render(request, 'customers/customer_form.html', context)

@login_required
@employee_required()
def customer_detail_view(request, pk):
    """Customer detail view with complete information - FIXED UUID handling"""
    try:
        if isinstance(pk, str):
            pk = uuid.UUID(pk)
    except (ValueError, TypeError):
        pass
    
    customer = get_object_or_404(Customer, pk=pk)
    
    # Get related data
    vehicles = customer.vehicles.filter(is_active=True)
    notes = customer.customer_notes.all()[:5]  # Updated to use correct related name
    documents = customer.documents.all()
    feedback = customer.feedback.all()[:3]
    
    # Calculate customer statistics - Handle import errors gracefully
    try:
        from apps.services.models import ServiceOrder
        order_stats = ServiceOrder.objects.filter(customer=customer).aggregate(
            total_orders=Count('id'),
            total_spent=Sum('total_amount'),
            avg_order_value=Avg('total_amount')
        )
        recent_orders = ServiceOrder.objects.filter(customer=customer).order_by('-created_at')[:5]
    except ImportError:
        order_stats = {'total_orders': 0, 'total_spent': 0, 'avg_order_value': 0}
        recent_orders = []
    except Exception as e:
        print(f"Error fetching order stats: {e}")
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
        'title': f'Customer - {customer.display_name}',
        'urls': get_customer_urls(request),
    }
    return render(request, 'customers/customer_detail.html', context)

@login_required
@employee_required()
def customer_edit_view(request, pk):
    """Edit customer information - FIXED UUID handling"""
    pk = _convert_uuid(pk)
    customer = get_object_or_404(Customer, pk=pk)
    
    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            try:
                customer = form.save(commit=False)
                customer.updated_by = request.user  # Use user object directly
                customer.save()
                
                success_message = f'Customer {customer.display_name} updated successfully!'
                messages.success(request, success_message)
                
                # Convert UUID to string for redirect
                return redirect(get_business_url(request, 'customers:detail', pk=customer.pk))
            except Exception as e:
                error_message = f'Error updating customer: {str(e)}'
                messages.error(request, error_message)
    else:
        form = CustomerForm(instance=customer)
    
    context = {
        'form': form,
        'customer': customer,
        'title': f'Edit Customer - {customer.display_name}',
        'urls': get_customer_urls(request),
    }
    return render(request, 'customers/customer_edit.html', context)

@login_required
@employee_required()
def vehicle_create_view(request, customer_pk):
    """Add vehicle to customer - FIXED UUID handling"""
    customer_pk = _convert_uuid(customer_pk)
    customer = get_object_or_404(Customer, pk=customer_pk)
    
    if request.method == 'POST':
        form = VehicleForm(request.POST)
        if form.is_valid():
            try:
                vehicle = form.save(commit=False)
                vehicle.customer = customer
                vehicle.created_by = request.user  # Use user object directly
                vehicle.save()
                
                success_message = f'Vehicle {vehicle.registration_number} added successfully!'
                messages.success(request, success_message)
                
                # Convert UUID to string for redirect
                return redirect(get_business_url(request, 'customers:detail', pk=customer.pk))
            except Exception as e:
                error_message = f'Error adding vehicle: {str(e)}'
                messages.error(request, error_message)
    else:
        form = VehicleForm()
    
    context = {
        'form': form,
        'customer': customer,
        'title': f'Add Vehicle - {customer.display_name}',
        'urls': get_customer_urls(request),
    }
    return render(request, 'customers/vehicle_form.html', context)

# Vehicle detail view with UUID handling, not for customer and also intergration with service orders
@login_required
@employee_required()
def vehicle_detail_view(request, pk):
    """View vehicle details - FIXED UUID handling"""
    pk = _convert_uuid(pk)
    vehicle = get_object_or_404(Vehicle, pk=pk)
    
    # Fetch related service orders
    try:
        from apps.services.models import ServiceOrder
        service_orders = ServiceOrder.objects.filter(vehicle=vehicle).order_by('-created_at')[:5]
    except ImportError:
        service_orders = []
    
    context = {
        'vehicle': vehicle,
        'service_orders': service_orders,
        'title': f'Vehicle - {vehicle.registration_number}',
        'urls': get_customer_urls(request),
    }
    return render(request, 'customers/vehicle_detail.html', context)



@login_required
@employee_required()
def vehicle_edit_view(request, pk):
    """Edit vehicle information - FIXED UUID handling"""
    pk = _convert_uuid(pk)
    vehicle = get_object_or_404(Vehicle, pk=pk)
    
    if request.method == 'POST':
        form = VehicleForm(request.POST, instance=vehicle)
        if form.is_valid():
            try:
                vehicle = form.save(commit=False)
                vehicle.updated_by_id = request.user.id  # Use integer ID
                vehicle.save()
                
                success_message = f'Vehicle {vehicle.registration_number} updated successfully!'
                messages.success(request, success_message)
                
                # Convert UUID to string for redirect
                return redirect(get_business_url(request, 'customers:detail', pk=str(vehicle.customer.pk)))
            except Exception as e:
                error_message = f'Error updating vehicle: {str(e)}'
                messages.error(request, error_message)
    else:
        form = VehicleForm(instance=vehicle)
    
    context = {
        'form': form,
        'vehicle': vehicle,
        'title': f'Edit Vehicle - {vehicle.registration_number}',
        'urls': get_customer_urls(request),
    }
    return render(request, 'customers/vehicle_form.html', context)

@login_required
@employee_required()
def customer_note_create_view(request, customer_pk):
    """Add note to customer - FIXED UUID handling"""
    customer_pk = _convert_uuid(customer_pk)
    customer = get_object_or_404(Customer, pk=customer_pk)
    
    if request.method == 'POST':
        form = CustomerNoteForm(request.POST)
        if form.is_valid():
            try:
                note = form.save(commit=False)
                note.customer = customer
                note.created_by = request.user  # Use user object directly
                note.save()
                
                messages.success(request, 'Note added successfully!')
                return redirect(get_business_url(request, 'customers:detail', pk=customer.pk))
            except Exception as e:
                error_message = f'Error adding note: {str(e)}'
                messages.error(request, error_message)
    else:
        form = CustomerNoteForm()
    
    context = {
        'form': form,
        'customer': customer,
        'title': f'Add Note - {customer.display_name}',
        'urls': get_customer_urls(request),
    }
    return render(request, 'customers/note_form.html', context)

@login_required
@employee_required()
@ajax_required
def customer_search_ajax(request):
    """AJAX customer search for quick lookups - FIXED UUID serialization"""
    query = request.GET.get('q', '').strip()
    customers = []
    
    if len(query) >= 2:
        try:
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
                    'id': str(customer.id),  # Convert UUID to string
                    'customer_id': customer.customer_id,
                    'name': customer.display_name,
                    'phone': str(customer.phone) if customer.phone else '',
                    'email': customer.email,
                    'is_vip': customer.is_vip,
                    'vehicles': [
                        {
                            'id': str(vehicle.id),  # Convert UUID to string
                            'registration': vehicle.registration_number,
                            'make_model': f"{vehicle.make} {vehicle.model}",
                            'year': vehicle.year
                        }
                        for vehicle in customer.vehicles.filter(is_active=True)
                    ]
                }
                for customer in customer_qs
            ]
        except Exception as e:
            print(f"Customer search error: {e}")
            return JsonResponse({'error': 'Search failed', 'customers': []})
    
    return JsonResponse({'customers': customers})

@login_required
@employee_required()
@ajax_required
def vehicle_search_ajax(request):
    """AJAX vehicle search by registration number - FIXED UUID serialization"""
    query = request.GET.get('q', '').strip()
    vehicles = []
    
    if len(query) >= 2:
        try:
            vehicle_qs = Vehicle.objects.select_related('customer').filter(
                registration_number__icontains=query,
                is_active=True
            )[:10]
            
            vehicles = [
                {
                    'id': str(vehicle.id),  # Convert UUID to string
                    'registration_number': vehicle.registration_number,
                    'make_model': f"{vehicle.make} {vehicle.model} ({vehicle.year})",
                    'color': vehicle.color,
                    'customer': {
                        'id': str(vehicle.customer.id),  # Convert UUID to string
                        'name': vehicle.customer.display_name,
                        'customer_id': vehicle.customer.customer_id,
                        'phone': str(vehicle.customer.phone) if vehicle.customer.phone else '',
                    }
                }
                for vehicle in vehicle_qs
            ]
        except Exception as e:
            print(f"Vehicle search error: {e}")
            return JsonResponse({'error': 'Search failed', 'vehicles': []})
    
    return JsonResponse({'vehicles': vehicles})

@login_required
@employee_required()
@require_POST
def toggle_customer_vip(request, pk):
    """Toggle customer VIP status - FIXED UUID handling"""
    pk = _convert_uuid(pk)
    
    try:
        customer = get_object_or_404(Customer, pk=pk)
        customer.is_vip = not customer.is_vip
        customer.updated_by_id = request.user.id  # Use integer ID
        customer.save(update_fields=['is_vip', 'updated_at', 'updated_by_id'])
        
        status = 'VIP' if customer.is_vip else 'regular'
        success_message = f'{customer.display_name} is now a {status} customer.'
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True, 
                'message': success_message,
                'is_vip': customer.is_vip
            })
        else:
            messages.success(request, success_message)
            return redirect(get_business_url(request, 'customers:detail', pk=customer.pk))
    except Exception as e:
        error_message = f'Error updating VIP status: {str(e)}'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': error_message})
        else:
            messages.error(request, error_message)
            return redirect(get_business_url(request, 'customers:list'))

@login_required
@employee_required()
@require_POST
def deactivate_customer(request, pk):
    """Deactivate customer account - FIXED UUID handling"""
    pk = _convert_uuid(pk)
    
    try:
        customer = get_object_or_404(Customer, pk=pk)
        customer.is_active = False
        customer.updated_by = request.user  # Use user object directly
        customer.save(update_fields=['is_active', 'updated_at'])  # Don't save updated_by_id
        
        success_message = f'{customer.display_name} account has been deactivated.'
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': success_message})
        else:
            messages.success(request, success_message)
            return redirect(get_business_url(request, 'customers:detail', pk=customer.pk))
    except Exception as e:
        error_message = f'Error deactivating customer: {str(e)}'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': error_message})
        else:
            messages.error(request, error_message)
            return redirect(get_business_url(request, 'customers:list'))

@login_required
@employee_required()
def customer_export_view(request):
    """Export customer data to CSV/Excel - FIXED UUID handling"""
    import csv
    from django.http import HttpResponse
    
    try:
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
                float(customer.total_spent) if customer.total_spent else 0,  # Convert Decimal to float
                customer.loyalty_points,
                'Yes' if customer.is_vip else 'No',
                'Yes' if customer.is_active else 'No',
                customer.created_at.strftime('%Y-%m-%d')
            ])
        
        return response
    except Exception as e:
        messages.error(request, f'Error exporting customers: {str(e)}')
        return redirect(get_business_url(request, 'customers:list'))

@login_required
@employee_required()    
def customer_import_view(request):
    """Import customer data from CSV/Excel - FIXED UUID handling"""
    from django.core.files.storage import FileSystemStorage
    from django.core.exceptions import ValidationError
    
    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']
        fs = FileSystemStorage()
        filename = fs.save(file.name, file)
        file_path = fs.path(filename)
        
        try:
            with open(file_path, 'r') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header row
                
                for row in reader:
                    if len(row) < 12:  # Ensure all required fields are present
                        continue
                    
                    customer_data = {
                        'customer_id': row[0],
                        'first_name': row[1],
                        'last_name': row[2],
                        'email': row[3],
                        'phone': row[4] if row[4] else None,
                        'city': row[5],
                        'customer_type': row[6],
                        'is_vip': row[7].lower() == 'yes',
                        'is_active': row[8].lower() == 'yes',
                        'created_at': row[9]
                    }
                    
                    # Create or update customer
                    customer, created = Customer.objects.update_or_create(
                        customer_id=customer_data['customer_id'],
                        defaults=customer_data
                    )
                    
                    if created:
                        messages.success(request, f'Customer {customer.display_name} imported successfully!')
                    else:
                        messages.info(request, f'Customer {customer.display_name} updated successfully!')
            
            fs.delete(filename)  # Clean up uploaded file
            
            return redirect(get_business_url(request, 'customers:list'))
        except ValidationError as ve:
            messages.error(request, f'Validation error: {str(ve)}')
        except Exception as e:
            messages.error(request, f'Error importing customers: {str(e)}')
    return render(request, 'customers/customer_import.html', {'title': 'Import Customers', 'urls': get_customer_urls(request)})

@login_required
@employee_required()
def customer_feedback_view(request, customer_pk):
    """View customer feedback - FIXED UUID handling"""
    customer_pk = _convert_uuid(customer_pk)
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
        'title': f'Feedback - {customer.display_name}',
        'urls': get_customer_urls(request),
    }
    return render(request, 'customers/customer_feedback.html', context)

@login_required
@employee_required()
def customer_documents_view(request, customer_pk):
    """View customer documents - FIXED UUID handling"""
    customer_pk = _convert_uuid(customer_pk)
    customer = get_object_or_404(Customer, pk=customer_pk)
    
    if request.method == 'POST':
        form = CustomerDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                document = form.save(commit=False)
                document.customer = customer
                document.created_by = request.user  # Use user object directly
                document.save()
                
                messages.success(request, 'Document uploaded successfully!')
                return redirect(get_business_url(request, 'customers:documents', customer_pk=customer.pk))
            except Exception as e:
                error_message = f'Error uploading document: {str(e)}'
                messages.error(request, error_message)
    else:
        form = CustomerDocumentForm()
    
    documents = customer.documents.all().order_by('-created_at')
    
    context = {
        'customer': customer,
        'documents': documents,
        'form': form,
        'title': f'Documents - {customer.display_name}',
        'urls': get_customer_urls(request),
    }
    return render(request, 'customers/customer_documents.html', context)

@login_required
@employee_required()
def loyalty_dashboard_view(request):
    """Loyalty program dashboard - FIXED UUID handling"""
    loyalty_program = LoyaltyProgram.objects.filter(is_active=True).first()
    
    if not loyalty_program:
        messages.info(request, 'No active loyalty program found.')
        return redirect(get_business_url(request, 'customers:list'))
    
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
    
    # Recent activity (placeholder for now)
    recent_activity = []
    
    context = {
        'loyalty_program': loyalty_program,
        'tier_stats': tier_stats,
        'top_customers': top_customers,
        'recent_activity': recent_activity,
        'total_customers': customers.count(),
        'title': 'Loyalty Program Dashboard',
        'urls': get_customer_urls(request),
    }
    return render(request, 'customers/loyalty_dashboard.html', context)


@login_required
@employee_required()
@ajax_required
def vehicle_customer_ajax(request):
    """Get customer details for a vehicle"""
    vehicle_id = request.GET.get('vehicle_id')
    
    if not vehicle_id:
        return JsonResponse({'success': False, 'error': 'Vehicle ID required'})
    
    try:
        vehicle = Vehicle.objects.select_related('customer').get(id=vehicle_id, is_active=True)
        
        customer_data = {
            'id': str(vehicle.customer.id),
            'name': vehicle.customer.full_name,
            'full_name': vehicle.customer.full_name,
            'phone': str(vehicle.customer.phone) if vehicle.customer.phone else '',
            'customer_id': vehicle.customer.customer_id,
            'email': vehicle.customer.email or '',
            'is_walk_in': getattr(vehicle.customer, 'is_walk_in', False)
        }
        
        return JsonResponse({
            'success': True,
            'customer': customer_data
        })
        
    except Vehicle.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Vehicle not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@employee_required()
def save_walk_in_customer_view(request, payment_id):
    """Convert walk-in customer to regular customer with details from payment"""
    from apps.payments.models import Payment
    
    try:
        payment = get_object_or_404(Payment, id=payment_id)
        
        if not (payment.customer and hasattr(payment.customer, 'is_walk_in') and payment.customer.is_walk_in):
            messages.error(request, 'This is not a walk-in customer.')
            return redirect('customers:list')
        
        if request.method == 'POST':
            form = CustomerForm(request.POST, instance=payment.customer)
            if form.is_valid():
                with transaction.atomic():
                    customer = form.save(commit=False)
                    customer.is_walk_in = False  # Convert to regular customer
                    
                    # Update phone from payment if not provided
                    if not customer.phone and payment.customer_phone:
                        customer.phone = payment.customer_phone
                    
                    # Generate proper customer ID if it's still a walk-in ID
                    if customer.customer_id.startswith('WALK'):
                        from apps.core.utils import generate_unique_code
                        customer.customer_id = generate_unique_code('CUST', 6)
                    
                    customer.updated_by_user_id = request.user.id
                    customer.save()
                    
                    # Mark notification as read if it exists
                    from apps.notification.models import Notification
                    Notification.objects.filter(
                        related_object_type='payment',
                        related_object_id=payment_id,
                        metadata__suggestion_type='customer_save'
                    ).update(is_read=True)
                    
                    messages.success(request, f'Customer {customer.full_name} saved successfully!')
                    return redirect('customers:detail', pk=customer.id)
        else:
            # Pre-fill form with existing data and transaction phone
            initial_data = {}
            if payment.customer_phone:
                initial_data['phone'] = payment.customer_phone
            
            form = CustomerForm(instance=payment.customer, initial=initial_data)
        
        context = {
            'form': form,
            'payment': payment,
            'customer': payment.customer,
            'title': 'Save Walk-in Customer',
        }
        
        return render(request, 'customers/save_walk_in.html', context)
        
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        return redirect('customers:list')


@login_required
@employee_required()
@ajax_required
def check_walk_in_transactions_ajax(request):
    """Check if walk-in customer has transaction details available for saving"""
    customer_id = request.GET.get('customer_id')
    
    if not customer_id:
        return JsonResponse({'success': False, 'error': 'Customer ID required'})
    
    try:
        customer = get_object_or_404(Customer, id=customer_id)
        
        # Check if customer is walk-in
        if not (hasattr(customer, 'is_walk_in') and customer.is_walk_in):
            return JsonResponse({'success': True, 'has_transactions': False})
        
        # Check for recent payments with transaction details
        from apps.payments.models import Payment
        recent_payments = Payment.objects.filter(
            customer=customer,
            status='completed',
            method='mpesa',
            customer_phone__isnull=False
        ).order_by('-created_at')[:5]
        
        has_transactions = recent_payments.exists()
        recent_payment_data = None
        
        if has_transactions:
            latest_payment = recent_payments.first()
            recent_payment_data = {
                'id': str(latest_payment.id),
                'amount': float(latest_payment.amount),
                'customer_phone': latest_payment.customer_phone,
                'created_at': latest_payment.created_at.isoformat()
            }
        
        return JsonResponse({
            'success': True,
            'has_transactions': has_transactions,
            'recent_payment': recent_payment_data,
            'transaction_count': recent_payments.count()
        })
        
    except Customer.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Customer not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})