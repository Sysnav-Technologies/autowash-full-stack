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
from apps.core.decorators import employee_required, manager_required, ajax_required
from apps.core.utils import generate_unique_code
from .models import (
    InventoryItem, InventoryCategory, Unit, StockMovement, 
    StockAdjustment, ItemConsumption, StockTake, StockTakeCount,
    InventoryAlert, ItemLocation, DailyOperations, BayConsumption,
    InventoryReconciliation, ReconciliationItem
)
from .forms import (
    InventoryItemForm, InventoryCategoryForm, UnitForm, 
    StockAdjustmentForm, StockTakeForm, ItemSearchForm, UnitSearchForm
)
from datetime import datetime, timedelta
import json

# --- Tenant-aware URL helpers ---

def get_inventory_urls(request):
    tenant_slug = request.tenant.slug
    base_url = f"/business/{tenant_slug}/inventory"
    return {
        'dashboard': f"{base_url}/",
        'list': f"{base_url}/items/",
        'item_create': f"{base_url}/items/create/",
        'item_detail': f"{base_url}/items/{{pk}}/",
        'stock_adjustment': f"{base_url}/stock/adjustments/",
        'stock_adjustment_item': f"{base_url}/stock/adjustments/{{item_id}}/",
        'stock_movements': f"{base_url}/stock/movements/",
        'stock_take_list': f"{base_url}/stock-takes/",
        'stock_take_create': f"{base_url}/stock-takes/create/",
        'stock_take_detail': f"{base_url}/stock-takes/{{pk}}/",
        'start_stock_take': f"{base_url}/stock-takes/{{pk}}/start/",
        'complete_stock_take': f"{base_url}/stock-takes/{{pk}}/complete/",
        'update_stock_count': f"{base_url}/stock-takes/{{stock_take_id}}/count/{{item_id}}/",
        'low_stock_report': f"{base_url}/reports/low-stock/",
        'valuation_report': f"{base_url}/reports/valuation/",
        'export_csv': f"{base_url}/reports/export/csv/",
        'category_list': f"{base_url}/categories/",
        'category_create': f"{base_url}/categories/create/",
        'alerts': f"{base_url}/alerts/",
        'resolve_alert': f"{base_url}/alerts/{{alert_id}}/resolve/",
        'unit_list': f"{base_url}/units/",
        'unit_create': f"{base_url}/units/create/",
        'unit_detail': f"{base_url}/units/{{pk}}/",
        'unit_edit': f"{base_url}/units/{{pk}}/edit/",
        'unit_toggle_status': f"{base_url}/units/{{pk}}/toggle/",
        'unit_delete': f"{base_url}/units/{{pk}}/delete/",
        'populate_car_wash_units': f"{base_url}/units/populate/",
        'unit_search': f"{base_url}/ajax/units/search/",
        'item_search': f"{base_url}/ajax/items/search/",
        'item_consumption': f"{base_url}/ajax/consumption/",
    }

def get_business_url(request, url_name, **kwargs):
    tenant_slug = request.tenant.slug
    base_url = f"/business/{tenant_slug}/inventory"
    url_mapping = {
        'inventory:dashboard': f"{base_url}/",
        'inventory:list': f"{base_url}/items/",
        'inventory:item_create': f"{base_url}/items/create/",
        'inventory:item_detail': f"{base_url}/items/{{pk}}/",
        'inventory:stock_adjustment': f"{base_url}/stock/adjustments/",
        'inventory:stock_adjustment_item': f"{base_url}/stock/adjustments/{{item_id}}/",
        'inventory:stock_movements': f"{base_url}/stock/movements/",
        'inventory:stock_take_list': f"{base_url}/stock-takes/",
        'inventory:stock_take_create': f"{base_url}/stock-takes/create/",
        'inventory:stock_take_detail': f"{base_url}/stock-takes/{{pk}}/",
        'inventory:start_stock_take': f"{base_url}/stock-takes/{{pk}}/start/",
        'inventory:complete_stock_take': f"{base_url}/stock-takes/{{pk}}/complete/",
        'inventory:update_stock_count': f"{base_url}/stock-takes/{{stock_take_id}}/count/{{item_id}}/",
        'inventory:low_stock_report': f"{base_url}/reports/low-stock/",
        'inventory:valuation_report': f"{base_url}/reports/valuation/",
        'inventory:export_csv': f"{base_url}/reports/export/csv/",
        'inventory:category_list': f"{base_url}/categories/",
        'inventory:category_create': f"{base_url}/categories/create/",
        'inventory:alerts': f"{base_url}/alerts/",
        'inventory:resolve_alert': f"{base_url}/alerts/{{alert_id}}/resolve/",
        'inventory:unit_list': f"{base_url}/units/",
        'inventory:unit_create': f"{base_url}/units/create/",
        'inventory:unit_detail': f"{base_url}/units/{{pk}}/",
        'inventory:unit_edit': f"{base_url}/units/{{pk}}/edit/",
        'inventory:unit_toggle_status': f"{base_url}/units/{{pk}}/toggle/",
        'inventory:unit_delete': f"{base_url}/units/{{pk}}/delete/",
        'inventory:populate_car_wash_units': f"{base_url}/units/populate/",
        'inventory:unit_search': f"{base_url}/ajax/units/search/",
        'inventory:item_search': f"{base_url}/ajax/items/search/",
        'inventory:item_consumption': f"{base_url}/ajax/consumption/",
    }
    url = url_mapping.get(url_name, f"{base_url}/")
    for key, value in kwargs.items():
        url = url.replace(f"{{{key}}}", str(value))
    return url

@login_required
@employee_required()
def inventory_dashboard_view(request):
    """Inventory dashboard with key metrics"""
    
    # Key statistics
    total_items = InventoryItem.objects.filter(is_active=True).count()
    low_stock_items = InventoryItem.objects.filter(
        current_stock__lte=F('minimum_stock_level'),
        is_active=True
    ).count()
    out_of_stock_items = InventoryItem.objects.filter(
        current_stock__lte=0,
        is_active=True
    ).count()
    
    # Calculate total inventory value
    total_value = InventoryItem.objects.filter(
        is_active=True
    ).aggregate(
        total=Sum(F('current_stock') * F('unit_cost'))
    )['total'] or 0
    
    # Recent stock movements
    recent_movements = StockMovement.objects.select_related(
        'item', 'item__category'
    ).order_by('-created_at')[:10]
    
    # Active alerts
    active_alerts = InventoryAlert.objects.filter(
        is_active=True,
        is_resolved=False
    ).select_related('item').order_by('-created_at')[:5]
    
    # Items needing reorder
    reorder_items = InventoryItem.objects.filter(
        current_stock__lte=F('reorder_point'),
        is_active=True
    ).order_by('current_stock')[:10]
    
    # Top consumed items (this month)
    current_month = timezone.now().replace(day=1)
    top_consumed = ItemConsumption.objects.filter(
        created_at__gte=current_month
    ).values('item__name').annotate(
        total_consumed=Sum('quantity'),
        total_cost=Sum(F('quantity') * F('unit_cost'))
    ).order_by('-total_consumed')[:5]
    
    # Category breakdown - FIXED VERSION
    category_stats = []
    categories = InventoryCategory.objects.filter(is_active=True)
    
    for category in categories:
        # Calculate statistics for each category
        category_items = InventoryItem.objects.filter(
            category=category,
            is_active=True
        )
        
        item_count = category_items.count()
        if item_count > 0:  # Only include categories with items
            total_value = category_items.aggregate(
                total=Sum(F('current_stock') * F('unit_cost'))
            )['total'] or 0
            
            # Create a dictionary with category data
            category_data = {
                'id': category.id,
                'name': category.name,
                'description': category.description,
                'item_count': item_count,
                'total_value': total_value,
                'parent': category.parent
            }
            category_stats.append(category_data)
    
    # Sort by item count descending and limit to top 10
    category_stats = sorted(category_stats, key=lambda x: x['item_count'], reverse=True)[:10]
    
    context = {
        'total_items': total_items,
        'low_stock_items': low_stock_items,
        'out_of_stock_items': out_of_stock_items,
        'total_value': total_value,
        'recent_movements': recent_movements,
        'active_alerts': active_alerts,
        'reorder_items': reorder_items,
        'top_consumed': top_consumed,
        'category_stats': category_stats,
        'title': 'Inventory Dashboard',
        'urls': get_inventory_urls(request),
    }
    
    return render(request, 'inventory/dashboard.html', context)

@login_required
@employee_required()
def item_list_view(request):
    """List inventory items with filtering and search"""
    items = InventoryItem.objects.select_related('category', 'unit', 'primary_supplier')
    
    # Search and filters
    search_form = ItemSearchForm(request.GET)
    if search_form.is_valid():
        search_query = search_form.cleaned_data.get('search')
        category = search_form.cleaned_data.get('category')
        stock_status = search_form.cleaned_data.get('stock_status')
        item_type = search_form.cleaned_data.get('item_type')
        
        if search_query:
            items = items.filter(
                Q(name__icontains=search_query) |
                Q(sku__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(barcode__icontains=search_query)
            )
        
        if category:
            items = items.filter(category=category)
        
        if stock_status:
            if stock_status == 'low_stock':
                items = items.filter(current_stock__lte=F('minimum_stock_level'))
            elif stock_status == 'out_of_stock':
                items = items.filter(current_stock__lte=0)
            elif stock_status == 'normal':
                items = items.filter(
                    current_stock__gt=F('minimum_stock_level'),
                    current_stock__lt=F('maximum_stock_level')
                )
            elif stock_status == 'overstock':
                items = items.filter(current_stock__gte=F('maximum_stock_level'))
        
        if item_type:
            items = items.filter(item_type=item_type)
    
    # Sorting
    sort_by = request.GET.get('sort', 'name')
    if sort_by in ['name', 'sku', 'current_stock', 'unit_cost', 'created_at']:
        if request.GET.get('order') == 'desc':
            sort_by = f'-{sort_by}'
        items = items.order_by(sort_by)
    
    # Pagination
    paginator = Paginator(items, 20)
    page = request.GET.get('page')
    items_page = paginator.get_page(page)
    
    # Quick stats for the filtered results
    filtered_stats = items.aggregate(
        total_items=Count('id'),
        total_value=Sum(F('current_stock') * F('unit_cost')),
        avg_stock=Avg('current_stock')
    )
    
    context = {
        'items': items_page,
        'search_form': search_form,
        'filtered_stats': filtered_stats,
        'title': 'Inventory Items',
        'urls': get_inventory_urls(request),
    }
    return render(request, 'inventory/item_list.html', context)

@login_required
@employee_required(['owner', 'manager'])
def item_create_view(request):
    """Create new inventory item"""
    if request.method == 'POST':
        form = InventoryItemForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save(commit=False)
            if not item.sku:
                item.sku = generate_unique_code('ITM', 8)
            item.created_by = request.user
            item.save()
            
            # Create initial stock movement if there's opening stock
            if item.current_stock > 0:
                StockMovement.objects.create(
                    item=item,
                    movement_type='in',
                    quantity=item.current_stock,
                    unit_cost=item.unit_cost,
                    old_stock=0,
                    new_stock=item.current_stock,
                    reference_type='adjustment',
                    reason='Opening stock',
                    created_by=request.user
                )
            
            messages.success(request, f'Inventory item "{item.name}" created successfully!')
            return redirect(get_business_url(request, 'inventory:item_detail', pk=item.pk))
    else:
        form = InventoryItemForm()
    
    context = {
        'form': form,
        'title': 'Create Inventory Item',
        'urls': get_inventory_urls(request),
    }
    return render(request, 'inventory/item_form.html', context)

@login_required
@employee_required(['owner', 'manager'])
@require_POST
def start_stock_take(request, pk):
    """Start a stock take"""
    stock_take = get_object_or_404(StockTake, pk=pk)
    
    if stock_take.status != 'planned':
        messages.error(request, 'Stock take cannot be started.')
        return redirect(get_business_url(request, 'inventory:stock_take_detail', pk=pk))
    
    stock_take.start_stock_take()
    messages.success(request, f'Stock take "{stock_take.name}" has been started.')
    return redirect(get_business_url(request, 'inventory:stock_take_detail', pk=pk))

@login_required
@employee_required(['owner', 'manager'])
@require_POST
def complete_stock_take(request, pk):
    """Complete a stock take"""
    stock_take = get_object_or_404(StockTake, pk=pk)
    
    if stock_take.status != 'in_progress':
        messages.error(request, 'Stock take is not in progress.')
        return redirect(get_business_url(request, 'inventory:stock_take_detail', pk=pk))
    
    # Check if all items have been counted
    uncounted_items = stock_take.count_records.filter(counted_quantity=0).count()
    if uncounted_items > 0:
        messages.warning(request, f'{uncounted_items} items have not been counted yet.')
        return redirect(get_business_url(request, 'inventory:stock_take_detail', pk=pk))
    
    stock_take.complete_stock_take()
    messages.success(request, f'Stock take "{stock_take.name}" has been completed.')
    return redirect(get_business_url(request, 'inventory:stock_take_detail', pk=pk))

@login_required
@employee_required()
def alerts_view(request):
    """Inventory alerts dashboard"""
    alerts = InventoryAlert.objects.filter(
        is_active=True
    ).select_related('item').order_by('-created_at')
    
    # Filter by alert type
    alert_type = request.GET.get('type')
    if alert_type:
        alerts = alerts.filter(alert_type=alert_type)
    
    # Filter by priority
    priority = request.GET.get('priority')
    if priority:
        alerts = alerts.filter(priority=priority)
    
    # Separate resolved and unresolved
    unresolved_alerts = alerts.filter(is_resolved=False)
    resolved_alerts = alerts.filter(is_resolved=True)[:20]
    
    # Group alerts by type
    alert_counts = {}
    for alert in unresolved_alerts:
        alert_type = alert.alert_type
        if alert_type not in alert_counts:
            alert_counts[alert_type] = 0
        alert_counts[alert_type] += 1
    
    context = {
        'unresolved_alerts': unresolved_alerts,
        'resolved_alerts': resolved_alerts,
        'alert_counts': alert_counts,
        'alert_types': InventoryAlert.ALERT_TYPES,
        'priority_levels': InventoryAlert.PRIORITY_LEVELS,
        'current_filters': {
            'type': alert_type,
            'priority': priority
        },
        'title': 'Inventory Alerts',
        'urls': get_inventory_urls(request),
    }
    return render(request, 'inventory/alerts.html', context)

@login_required
@employee_required()
@require_POST
def resolve_alert(request, alert_id):
    """Resolve an inventory alert"""
    alert = get_object_or_404(InventoryAlert, id=alert_id)
    
    # Try to get employee from request, fallback to None
    employee = getattr(request, 'employee', None)
    alert.resolve(employee)
    
    messages.success(request, f'Alert for {alert.item.name} has been resolved.')
    return redirect(get_business_url(request, 'inventory:alerts'))

@login_required
@employee_required()
def stock_movements_view(request):
    """Stock movements report"""
    movements = StockMovement.objects.select_related(
        'item', 'item__category'
    ).order_by('-created_at')
    
    # Filters
    item_id = request.GET.get('item')
    movement_type = request.GET.get('movement_type')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if item_id:
        movements = movements.filter(item_id=item_id)
    if movement_type:
        movements = movements.filter(movement_type=movement_type)
    if date_from:
        movements = movements.filter(created_at__date__gte=date_from)
    if date_to:
        movements = movements.filter(created_at__date__lte=date_to)
    
    # Pagination
    paginator = Paginator(movements, 50)
    page = request.GET.get('page')
    movements_page = paginator.get_page(page)
    
    # Calculate totals for filtered results
    totals = movements.aggregate(
        total_in=Sum('quantity', filter=Q(movement_type='in')),
        total_out=Sum('quantity', filter=Q(movement_type='out')),
        total_value=Sum(F('quantity') * F('unit_cost'))
    )
    
    context = {
        'movements': movements_page,
        'totals': totals,
        'movement_types': StockMovement.MOVEMENT_TYPES,
        'current_filters': {
            'item': item_id,
            'movement_type': movement_type,
            'date_from': date_from,
            'date_to': date_to
        },
        'title': 'Stock Movements',
        'urls': get_inventory_urls(request),
    }
    return render(request, 'inventory/stock_movements.html', context)

@login_required
@employee_required()
def category_list_view(request):
    """List inventory categories"""
    categories = InventoryCategory.objects.filter(
        is_active=True,
        parent__isnull=True  # Only top-level categories
    ).prefetch_related('subcategories', 'items')
    
    # Calculate statistics for each category
    for category in categories:
        category.total_items = category.item_count
        category.total_value = category.items.aggregate(
            total=Sum(F('current_stock') * F('unit_cost'))
        )['total'] or 0
        
        # Include subcategory statistics
        for subcategory in category.subcategories.filter(is_active=True):
            subcategory.total_items = subcategory.item_count
            subcategory.total_value = subcategory.items.aggregate(
                total=Sum(F('current_stock') * F('unit_cost'))
            )['total'] or 0
    
    context = {
        'categories': categories,
        'title': 'Inventory Categories',
        'urls': get_inventory_urls(request),
    }
    return render(request, 'inventory/category_list.html', context)

@login_required
@employee_required(['owner', 'manager'])
def category_create_view(request):
    """Create inventory category"""
    if request.method == 'POST':
        form = InventoryCategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.created_by = request.user
            category.save()
            
            messages.success(request, f'Category "{category.name}" created successfully!')
            return redirect(get_business_url(request, 'inventory:category_list'))
    else:
        form = InventoryCategoryForm()
    
    context = {
        'form': form,
        'title': 'Create Category',
        'urls': get_inventory_urls(request),
    }
    return render(request, 'inventory/category_form.html', context)

@login_required
@employee_required()
@ajax_required
def item_search_ajax(request):
    """AJAX search for inventory items"""
    query = request.GET.get('q', '').strip()
    items = []
    
    if len(query) >= 2:
        items_qs = InventoryItem.objects.filter(
            Q(name__icontains=query) |
            Q(sku__icontains=query) |
            Q(barcode__icontains=query),
            is_active=True
        ).select_related('category', 'unit')[:10]
        
        items = [
            {
                'id': item.id,
                'name': item.name,
                'sku': item.sku,
                'current_stock': float(item.current_stock),
                'unit': item.unit.name,
                'unit_cost': float(item.unit_cost),
                'category': item.category.name,
                'stock_status': item.stock_status,
                'is_low_stock': item.is_low_stock,
                'is_out_of_stock': item.is_out_of_stock
            }
            for item in items_qs
        ]
    
    return JsonResponse({'items': items})

@login_required
@employee_required()
@ajax_required
def item_consumption_ajax(request):
    """Record item consumption for service orders"""
    if request.method == 'POST':
        try:
            # Handle both JSON and form data
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST
            
            item_id = data.get('item_id')
            service_order_id = data.get('service_order_id')
            service_id = data.get('service_id')
            quantity = float(data.get('quantity', 0))
            notes = data.get('notes', '')
            
            item = InventoryItem.objects.get(id=item_id)
            
            # Check if enough stock is available
            if item.current_stock < quantity:
                return JsonResponse({
                    'error': f'Insufficient stock. Available: {item.current_stock}'
                }, status=400)
            
            # Get employee from request
            employee = getattr(request, 'employee', None)
            
            # Create consumption record
            consumption = ItemConsumption.objects.create(
                item=item,
                service_order_id=service_order_id if service_order_id else None,
                service_id=service_id if service_id else None,
                quantity=quantity,
                unit_cost=item.unit_cost,
                used_by=employee,
                notes=notes
            )
            
            # Update stock
            old_stock = item.current_stock
            item.current_stock -= quantity
            item.save()
            
            # Create stock movement
            StockMovement.objects.create(
                item=item,
                movement_type='out',
                quantity=-quantity,
                unit_cost=item.unit_cost,
                old_stock=old_stock,
                new_stock=item.current_stock,
                reference_type='sale',
                service_order_id=service_order_id if service_order_id else None,
                reason=f'Used for service order' if service_order_id else 'Item consumption',
                created_by=request.user
            )
            
            # Check for low stock alerts
            if item.is_low_stock:
                InventoryAlert.objects.get_or_create(
                    item=item,
                    alert_type='low_stock',
                    defaults={
                        'priority': 'medium',
                        'message': f'{item.name} is running low on stock',
                        'current_stock': item.current_stock,
                        'threshold_value': item.minimum_stock_level
                    }
                )
            
            return JsonResponse({
                'success': True,
                'new_stock': float(item.current_stock),
                'consumption_id': consumption.id
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@login_required
@employee_required()
def inventory_valuation_report(request):
    """Inventory valuation report"""
    items = InventoryItem.objects.filter(
        is_active=True,
        current_stock__gt=0
    ).select_related('category', 'unit').order_by('category__name', 'name')
    
    # Group by category
    categories = {}
    total_value = 0
    
    for item in items:
        category_name = item.category.name
        if category_name not in categories:
            categories[category_name] = {
                'items': [],
                'total_value': 0,
                'total_quantity': 0
            }
        
        item_value = item.current_stock * item.unit_cost
        categories[category_name]['items'].append({
            'item': item,
            'value': item_value
        })
        categories[category_name]['total_value'] += item_value
        categories[category_name]['total_quantity'] += item.current_stock
        total_value += item_value
    
    context = {
        'categories': categories,
        'total_value': total_value,
        'total_items': items.count(),
        'report_date': timezone.now(),
        'title': 'Inventory Valuation Report',
        'urls': get_inventory_urls(request),
    }
    return render(request, 'inventory/valuation_report.html', context)

@login_required
@employee_required()
def export_inventory_csv(request):
    """Export inventory to CSV"""
    import csv

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="inventory_report.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'SKU', 'Name', 'Category', 'Current Stock', 'Unit', 'Unit Cost',
        'Stock Value', 'Min Stock', 'Max Stock', 'Reorder Point', 'Status'
    ])

    items = InventoryItem.objects.filter(is_active=True).select_related('category', 'unit')
    for item in items:
        writer.writerow([
            item.sku,
            item.name,
            item.category.name if item.category else '',
            item.current_stock,
            item.unit.abbreviation if item.unit else '',
            item.unit_cost,
            item.stock_value,
            item.minimum_stock_level,
            item.maximum_stock_level,
            item.reorder_point,
            item.stock_status
        ])

    return response

@login_required
@employee_required()
def item_detail_view(request, pk):
    """Inventory item detail view"""
    item = get_object_or_404(InventoryItem, pk=pk)
    
    # Recent stock movements
    recent_movements = item.stock_movements.order_by('-created_at')[:15]
    
    # Consumption history (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_consumption = item.consumption_records.filter(
        created_at__gte=thirty_days_ago
    ).select_related('service_order', 'service', 'used_by')
    
    # Stock level statistics
    movements_in = item.stock_movements.filter(
        movement_type='in'
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    movements_out = item.stock_movements.filter(
        movement_type='out'
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    total_consumed = item.consumption_records.aggregate(
        total=Sum('quantity')
    )['total'] or 0
    
    # Locations
    locations = item.locations.all()
    
    # Active alerts
    active_alerts = item.alerts.filter(is_active=True, is_resolved=False)
    
    # Calculate reorder suggestion
    avg_daily_consumption = 0
    if recent_consumption.exists():
        total_days = (timezone.now() - thirty_days_ago).days
        avg_daily_consumption = total_consumed / total_days if total_days > 0 else 0
    
    days_until_stockout = 0
    if avg_daily_consumption > 0:
        days_until_stockout = item.current_stock / avg_daily_consumption
    
    # Calculate stock percentage for progress bar
    stock_percentage = 0
    if item.maximum_stock_level > 0:
        stock_percentage = min((item.current_stock / item.maximum_stock_level) * 100, 100)
    
    context = {
        'item': item,
        'recent_movements': recent_movements,
        'recent_consumption': recent_consumption,
        'locations': locations,
        'active_alerts': active_alerts,
        'stats': {
            'movements_in': movements_in,
            'movements_out': movements_out,
            'total_consumed': total_consumed,
            'avg_daily_consumption': avg_daily_consumption,
            'days_until_stockout': days_until_stockout,
        },
        'title': f'Item - {item.name}',
        'urls': get_inventory_urls(request),
    }
    return render(request, 'inventory/item_detail.html', context)

@login_required
@employee_required(['owner', 'manager'])
def stock_adjustment_view(request, item_id=None):
    """Stock adjustment form"""
    item = get_object_or_404(InventoryItem, pk=item_id) if item_id else None
    
    if request.method == 'POST':
        form = StockAdjustmentForm(request.POST, initial_item=item)
        if form.is_valid():
            try:
                with transaction.atomic():
                    adjustment = form.save(commit=False)
                    adjustment.old_stock = adjustment.item.current_stock
                    
                    # Handle quantity based on adjustment type
                    if adjustment.adjustment_type == 'decrease':
                        actual_quantity = -abs(adjustment.quantity)  # Make sure it's negative
                    else:
                        actual_quantity = abs(adjustment.quantity)   # Make sure it's positive
                    
                    adjustment.quantity = actual_quantity
                    adjustment.new_stock = adjustment.old_stock + actual_quantity
                    adjustment.set_created_by(request.user)
                    adjustment.save()
                    
                    # Update item stock
                    adjustment.item.current_stock = adjustment.new_stock
                    adjustment.item.save()
                    
                    # Auto-approve if user has permission
                    employee = getattr(request, 'employee', None)
                    if employee and employee.role in ['owner', 'manager']:
                        adjustment.approve(request.user)
                    else:
                        # Create stock movement only if not auto-approved
                        # (approve method will create it if auto-approved)
                        stock_movement = StockMovement.objects.create(
                            item=adjustment.item,
                            movement_type='adjustment',
                            quantity=actual_quantity,
                            unit_cost=adjustment.unit_cost,
                            old_stock=adjustment.old_stock,
                            new_stock=adjustment.new_stock,
                            reference_type='adjustment',
                            reason=adjustment.reason,
                        )
                        # Set created_by user ID
                        stock_movement.set_created_by(request.user)
                        stock_movement.save()
                    
                    messages.success(request, 'Stock adjustment created successfully!')
                    try:
                        return redirect(get_business_url(request, 'inventory:item_detail', pk=adjustment.item.pk))
                    except:
                        # Fallback if item detail redirect fails
                        return redirect(get_business_url(request, 'inventory:list'))
                    
            except Exception as e:
                messages.error(request, f'Error creating adjustment: {str(e)}')
    else:
        form = StockAdjustmentForm(initial_item=item)
    
    context = {
        'form': form,
        'item': item,
        'title': f'Stock Adjustment - {item.name}' if item else 'Stock Adjustment',
        'urls': get_inventory_urls(request),
    }
    return render(request, 'inventory/stock_adjustment.html', context)

@login_required
@employee_required()
def low_stock_report_view(request):
    """Low stock items report"""
    low_stock_items = InventoryItem.objects.filter(
        current_stock__lte=F('minimum_stock_level'),
        is_active=True
    ).select_related('category', 'unit', 'primary_supplier').order_by('current_stock')
    
    # Group by category
    categories = {}
    for item in low_stock_items:
        category_name = item.category.name
        if category_name not in categories:
            categories[category_name] = []
        categories[category_name].append(item)
    
    # Calculate reorder suggestions
    for item in low_stock_items:
        if item.reorder_quantity > 0:
            item.suggested_order_qty = item.reorder_quantity
        else:
            # Suggest quantity to reach maximum stock level
            item.suggested_order_qty = max(0, item.maximum_stock_level - item.current_stock)
        
        item.suggested_order_value = item.suggested_order_qty * item.unit_cost
    
    total_reorder_value = sum(
        item.suggested_order_value for item in low_stock_items
    )
    
    context = {
        'low_stock_items': low_stock_items,
        'categories': categories,
        'total_items': low_stock_items.count(),
        'total_reorder_value': total_reorder_value,
        'title': 'Low Stock Report',
        'urls': get_inventory_urls(request),
    }
    return render(request, 'inventory/low_stock_report.html', context)

@login_required
@employee_required(['owner', 'manager'])
def stock_take_list_view(request):
    """List stock takes"""
    stock_takes = StockTake.objects.all().order_by('-created_at')
    
    # Pagination
    paginator = Paginator(stock_takes, 10)
    page = request.GET.get('page')
    stock_takes_page = paginator.get_page(page)
    
    context = {
        'stock_takes': stock_takes_page,
        'title': 'Stock Takes',
        'urls': get_inventory_urls(request),
    }
    return render(request, 'inventory/stock_take_list.html', context)

@login_required
@employee_required(['owner', 'manager'])
def stock_take_create_view(request):
    """Create new stock take"""
    if request.method == 'POST':
        form = StockTakeForm(request.POST)
        if form.is_valid():
            stock_take = form.save(commit=False)
            stock_take.supervisor = getattr(request, 'employee', None)
            stock_take.created_by = request.user
            stock_take.save()
            
            # Save many-to-many relationships
            form.save_m2m()
            
            messages.success(request, f'Stock take "{stock_take.name}" created successfully!')
            return redirect(get_business_url(request, 'inventory:stock_take_detail', pk=stock_take.pk))
    else:
        form = StockTakeForm()
    
    context = {
        'form': form,
        'title': 'Create Stock Take',
        'urls': get_inventory_urls(request),
    }
    return render(request, 'inventory/stock_take_form.html', context)

@login_required
@employee_required(['owner', 'manager'])
def stock_take_detail_view(request, pk):
    """Stock take detail and counting interface"""
    stock_take = get_object_or_404(StockTake, pk=pk)
    
    # Get count records
    count_records = stock_take.count_records.select_related('item', 'counted_by').order_by('item__name')
    
    # Calculate progress
    total_items = count_records.count()
    counted_items = count_records.filter(counted_quantity__gt=0).count()
    progress_percentage = (counted_items / total_items * 100) if total_items > 0 else 0
    
    # Discrepancies
    discrepancies = count_records.filter(
        counted_quantity__gt=0
    ).exclude(
        counted_quantity=F('system_quantity')
    )
    
    context = {
        'stock_take': stock_take,
        'count_records': count_records,
        'total_items': total_items,
        'counted_items': counted_items,
        'progress_percentage': progress_percentage,
        'discrepancies': discrepancies,
        'title': f'Stock Take - {stock_take.name}',
        'urls': get_inventory_urls(request),
    }
    return render(request, 'inventory/stock_take_detail.html', context)

@login_required
@employee_required(['owner', 'manager', 'supervisor'])
def stock_take_edit_view(request, pk):
    """Edit stock take"""
    stock_take = get_object_or_404(StockTake, pk=pk)
    
    # Only allow editing of planned stock takes
    if stock_take.status not in ['planned']:
        messages.error(request, 'This stock take cannot be edited.')
        return redirect(get_business_url(request, 'inventory:stock_take_detail', pk=pk))
    
    if request.method == 'POST':
        form = StockTakeForm(request.POST, instance=stock_take)
        if form.is_valid():
            stock_take = form.save()
            messages.success(request, f'Stock take "{stock_take.name}" updated successfully!')
            return redirect(get_business_url(request, 'inventory:stock_take_detail', pk=stock_take.pk))
    else:
        form = StockTakeForm(instance=stock_take)
    
    context = {
        'form': form,
        'stock_take': stock_take,
        'title': f'Edit Stock Take - {stock_take.name}',
        'urls': get_inventory_urls(request),
    }
    return render(request, 'inventory/stock_take_form.html', context)

@login_required
@employee_required()
@ajax_required
@require_POST
def update_stock_count(request, stock_take_id, item_id):
    """Update stock count for an item"""
    import json
    
    stock_take = get_object_or_404(StockTake, pk=stock_take_id)
    item = get_object_or_404(InventoryItem, pk=item_id)
    
    if stock_take.status != 'in_progress':
        return JsonResponse({'error': 'Stock take is not in progress'}, status=400)
    
    # Handle both JSON and form data
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
            counted_quantity = data.get('counted_quantity')
            notes = data.get('notes', '')
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    else:
        counted_quantity = request.POST.get('counted_quantity')
        notes = request.POST.get('notes', '')
    
    try:
        counted_quantity = float(counted_quantity)
        
        # Get employee from request
        employee = getattr(request, 'employee', None)
        
        count_record, created = StockTakeCount.objects.get_or_create(
            stock_take=stock_take,
            item=item,
            defaults={
                'system_quantity': item.current_stock,
                'counted_quantity': counted_quantity,
                'counted_by': employee,
                'notes': notes
            }
        )
        
        if not created:
            count_record.counted_quantity = counted_quantity
            count_record.counted_by = employee
            count_record.notes = notes
            count_record.save()
        
        return JsonResponse({
            'success': True,
            'variance_quantity': count_record.variance_quantity,
            'variance_value': float(count_record.variance_value),
            'has_discrepancy': count_record.has_discrepancy
        })
    except ValueError:
        return JsonResponse({'error': 'Invalid quantity'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# UNIT VIEWS
@login_required
@employee_required()
def unit_list_view(request):
    """List units of measurement with filtering"""
    units = Unit.objects.all()
    
    # Search and filters
    search_form = UnitSearchForm(request.GET)
    if search_form.is_valid():
        search_query = search_form.cleaned_data.get('search')
        status = search_form.cleaned_data.get('status')
        category = search_form.cleaned_data.get('category')
        
        if search_query:
            units = units.filter(
                Q(name__icontains=search_query) |
                Q(abbreviation__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        
        if status == 'active':
            units = units.filter(is_active=True)
        elif status == 'inactive':
            units = units.filter(is_active=False)
        
        if category:
            # Filter by category based on common unit patterns
            category_filters = {
                'liquid': ['ml', 'L', 'gal', 'qt', 'pt', 'fl oz', 'bbl', 'drm'],
                'solid': ['g', 'kg', 'lb', 'oz', 'bag', 'pail', 'bx'],
                'count': ['pcs', 'ea', 'pr', 'set', 'dz', 'gr'],
                'equipment': ['fltr', 'nzl', 'pump', 'gun', 'hose'],
                'measurement': ['psi', 'bar', 'gpm', 'A', 'V', 'W', '°F', '°C'],
                'time': ['sec', 'min', 'hr', 'cyc', 'wash', 'use'],
                'specialty': ['pH', 'ppm', '%', 'ratio', 'coat', 'app']
            }
            
            if category in category_filters:
                units = units.filter(abbreviation__in=category_filters[category])
    
    # Sorting
    sort_by = request.GET.get('sort', 'name')
    if sort_by in ['name', 'abbreviation', 'created_at']:
        if request.GET.get('order') == 'desc':
            sort_by = f'-{sort_by}'
        units = units.order_by(sort_by)
    
    # Pagination
    paginator = Paginator(units, 25)
    page = request.GET.get('page')
    units_page = paginator.get_page(page)
    
    # Statistics
    stats = {
        'total_units': Unit.objects.count(),
        'active_units': Unit.objects.filter(is_active=True).count(),
        'inactive_units': Unit.objects.filter(is_active=False).count(),
        'filtered_count': units.count(),
    }
    
    context = {
        'units': units_page,
        'search_form': search_form,
        'stats': stats,
        'title': 'Units of Measurement',
        'urls': get_inventory_urls(request),
    }
    return render(request, 'inventory/unit_list.html', context)

@login_required
@employee_required(['owner', 'manager'])
def unit_create_view(request):
    """Create new unit of measurement"""
    if request.method == 'POST':
        form = UnitForm(request.POST)
        if form.is_valid():
            unit = form.save()
            messages.success(request, f'Unit "{unit.name} ({unit.abbreviation})" created successfully!')
            return redirect(get_business_url(request, 'inventory:unit_list'))
    else:
        form = UnitForm()
    
    context = {
        'form': form,
        'title': 'Create Unit of Measurement',
        'urls': get_inventory_urls(request),
    }
    return render(request, 'inventory/unit_form.html', context)

@login_required
@employee_required(['owner', 'manager'])
def unit_edit_view(request, pk):
    """Edit unit of measurement"""
    unit = get_object_or_404(Unit, pk=pk)
    
    if request.method == 'POST':
        form = UnitForm(request.POST, instance=unit)
        if form.is_valid():
            unit = form.save()
            messages.success(request, f'Unit "{unit.name} ({unit.abbreviation})" updated successfully!')
            return redirect(get_business_url(request, 'inventory:unit_list'))
    else:
        form = UnitForm(instance=unit)
    
    context = {
        'form': form,
        'unit': unit,
        'title': f'Edit Unit - {unit.name}',
        'urls': get_inventory_urls(request),
    }
    return render(request, 'inventory/unit_form.html', context)

@login_required
@employee_required(['owner', 'manager'])
def unit_detail_view(request, pk):
    """Unit detail view with usage statistics"""
    unit = get_object_or_404(Unit, pk=pk)
    
    # Get items using this unit
    items_using_unit = InventoryItem.objects.filter(unit=unit, is_active=True)
    
    # Statistics
    stats = {
        'items_count': items_using_unit.count(),
        'total_stock_value': items_using_unit.aggregate(
            total=Sum(F('current_stock') * F('unit_cost'))
        )['total'] or 0,
        'total_stock_quantity': items_using_unit.aggregate(
            total=Sum('current_stock')
        )['total'] or 0,
        'avg_unit_cost': items_using_unit.aggregate(
            avg=Avg('unit_cost')
        )['avg'] or 0,
    }
    
    # Recent items added with this unit
    recent_items = items_using_unit.order_by('-created_at')[:10]
    
    context = {
        'unit': unit,
        'items_using_unit': items_using_unit[:20],
        'recent_items': recent_items,
        'stats': stats,
        'title': f'Unit Details - {unit.name}',
        'urls': get_inventory_urls(request),
    }
    return render(request, 'inventory/unit_detail.html', context)

@login_required
@employee_required(['owner', 'manager'])
@require_POST
def unit_toggle_status(request, pk):
    """Toggle unit active status"""
    unit = get_object_or_404(Unit, pk=pk)
    
    # Check if unit is being used by any active items
    if not unit.is_active:
        # Activating unit - safe to do
        unit.is_active = True
        unit.save()
        messages.success(request, f'Unit "{unit.name}" has been activated.')
    else:
        # Deactivating unit - check for usage
        items_using_unit = InventoryItem.objects.filter(unit=unit, is_active=True)
        if items_using_unit.exists():
            messages.error(
                request, 
                f'Cannot deactivate unit "{unit.name}". It is currently used by {items_using_unit.count()} active items.'
            )
        else:
            unit.is_active = False
            unit.save()
            messages.success(request, f'Unit "{unit.name}" has been deactivated.')
    
    return redirect(get_business_url(request, 'inventory:unit_list'))

@login_required
@employee_required(['owner', 'manager'])
@require_POST
def unit_delete_view(request, pk):
    """Delete unit of measurement"""
    unit = get_object_or_404(Unit, pk=pk)
    
    # Check if unit is being used
    items_using_unit = InventoryItem.objects.filter(unit=unit)
    if items_using_unit.exists():
        messages.error(
            request,
            f'Cannot delete unit "{unit.name}". It is used by {items_using_unit.count()} items. '
            'Please reassign those items to different units first.'
        )
    else:
        unit_name = str(unit)
        unit.delete()
        messages.success(request, f'Unit "{unit_name}" has been deleted.')
    
    return redirect(get_business_url(request, 'inventory:unit_list'))

@login_required
@employee_required()
@ajax_required
def unit_search_ajax(request):
    """AJAX search for units"""
    query = request.GET.get('q', '').strip()
    units = []
    
    if len(query) >= 1:
        units_qs = Unit.objects.filter(
            Q(name__icontains=query) | Q(abbreviation__icontains=query),
            is_active=True
        )[:10]
        
        units = [
            {
                'id': unit.id,
                'name': unit.name,
                'abbreviation': unit.abbreviation,
                'display': f"{unit.name} ({unit.abbreviation})",
                'description': unit.description
            }
            for unit in units_qs
        ]
    
    return JsonResponse({'units': units})

@login_required
@employee_required(['owner', 'manager'])
def populate_car_wash_units_view(request):
    """Populate database with car wash units"""
    if request.method == 'POST':
        from django.core.management import call_command
        from io import StringIO
        try:
            # Capture command output
            out = StringIO()
            call_command('populate_car_wash_units', stdout=out)
            output = out.getvalue()
            
            messages.success(request, 'Car wash units populated successfully!')
            
            # Return JSON response for AJAX calls
            if request.headers.get('Content-Type') == 'application/json':
                return JsonResponse({
                    'success': True,
                    'message': 'Units populated successfully',
                    'output': output
                })
                
        except Exception as e:
            messages.error(request, f'Error populating units: {str(e)}')
            
            if request.headers.get('Content-Type') == 'application/json':
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                })
    
    return redirect(get_business_url(request, 'inventory:unit_list'))

# Additional helper views for AJAX operations
@login_required
@employee_required()
@ajax_required
def ajax_location_create(request):
    """AJAX endpoint to create item locations"""
    if request.method == 'POST':
        try:
            item_id = request.POST.get('item')
            warehouse = request.POST.get('warehouse', 'Main Warehouse')
            zone = request.POST.get('zone', '')
            aisle = request.POST.get('aisle', '')
            shelf = request.POST.get('shelf', '')
            bin_location = request.POST.get('bin', '')
            quantity = float(request.POST.get('quantity', 0))
            is_primary = request.POST.get('is_primary') == 'on'
            is_picking_location = request.POST.get('is_picking_location') == 'on'
            
            item = InventoryItem.objects.get(id=item_id)
            
            # If this is set as primary, remove primary flag from other locations
            if is_primary:
                ItemLocation.objects.filter(item=item, is_primary=True).update(is_primary=False)
            
            location = ItemLocation.objects.create(
                item=item,
                warehouse=warehouse,
                zone=zone,
                aisle=aisle,
                shelf=shelf,
                bin=bin_location,
                quantity=quantity,
                is_primary=is_primary,
                is_picking_location=is_picking_location
            )
            
            return JsonResponse({
                'success': True,
                'location_id': location.id,
                'full_location': location.full_location
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
    
    return JsonResponse({'success': False, 'message': 'Invalid request'}, status=400)


# === DAILY OPERATIONS VIEWS ===

@employee_required()
def daily_operations_dashboard(request):
    """Comprehensive daily operations dashboard integrating all app functionalities"""
    from .models import DailyOperations, BayConsumption, InventoryReconciliation
    from apps.services.models import ServiceBay, ServiceOrder
    from apps.customers.models import Customer
    from apps.employees.models import Employee, Attendance
    from apps.payments.models import Payment
    from django.utils import timezone
    from datetime import timedelta
    
    today = timezone.now().date()
    
    # Get or create today's operations
    operations, created = DailyOperations.objects.get_or_create(
        operation_date=today,
        defaults={
            'shift_supervisor': request.user.employee if hasattr(request.user, 'employee') else None,
            'target_services': 50,  # Default target
        }
    )
    
    # Get all wash bays
    bays = ServiceBay.objects.filter(is_active=True).order_by('bay_number')
    
    # Get bay consumptions for today
    bay_consumptions = BayConsumption.objects.filter(
        daily_operations=operations
    ).select_related('item', 'bay').order_by('bay__bay_number', 'item__name')
    
    # Organize consumptions by bay
    bay_consumption_data = {}
    for bay in bays:
        bay_consumptions_for_bay = bay_consumptions.filter(bay=bay)
        total_allocated = bay_consumptions_for_bay.aggregate(
            total=Sum(F('quantity_allocated') * F('unit_cost'))
        )['total'] or 0
        total_used = bay_consumptions_for_bay.aggregate(
            total=Sum(F('quantity_used') * F('unit_cost'))
        )['total'] or 0
        total_remaining = bay_consumptions_for_bay.aggregate(
            total=Sum(F('quantity_remaining') * F('unit_cost'))
        )['total'] or 0
        
        bay_consumption_data[bay.id] = {
            'bay': bay,
            'consumptions': bay_consumptions_for_bay,
            'total_allocated_value': total_allocated,
            'total_used_value': total_used,
            'total_remaining_value': total_remaining,
        }
    
    # Get inventory items available for allocation
    available_items = InventoryItem.objects.filter(
        current_stock__gt=0,
        is_active=True
    ).order_by('category__name', 'name')
    
    # Get reconciliation status
    try:
        reconciliation = InventoryReconciliation.objects.get(daily_operations=operations)
    except InventoryReconciliation.DoesNotExist:
        reconciliation = None
    
    # Calculate summary statistics
    total_allocated = bay_consumptions.aggregate(
        total=Sum(F('quantity_allocated') * F('unit_cost'))
    )['total'] or 0
    
    total_used = bay_consumptions.aggregate(
        total=Sum(F('quantity_used') * F('unit_cost'))
    )['total'] or 0
    
    total_remaining = bay_consumptions.aggregate(
        total=Sum(F('quantity_remaining') * F('unit_cost'))
    )['total'] or 0
    
    # Get recent activities from various apps
    recent_orders = ServiceOrder.objects.filter(
        created_at__date=today
    ).select_related('customer', 'queue_entry__service_bay').order_by('-created_at')
    
    # Calculate metrics before slicing
    active_customers_today = recent_orders.values('customer').distinct().count()
    
    # Now slice for display
    recent_orders = recent_orders[:10]
    
    recent_stock_movements = StockMovement.objects.filter(
        created_at__date=today
    ).select_related('item').order_by('-created_at')[:10]
    
    # Get recent payments (if Payment model exists)
    recent_payments = []
    try:
        from apps.payments.models import Payment
        recent_payments = Payment.objects.filter(
            created_at__date=today
        ).select_related('customer').order_by('-created_at')[:10]
    except:
        pass
    
    # Get recent customers
    recent_customers_queryset = Customer.objects.filter(
        created_at__date=today
    ).order_by('-created_at')
    
    # Calculate count before slicing
    new_customers_today = recent_customers_queryset.count()
    
    # Now slice for display
    recent_customers = recent_customers_queryset[:10]
    
    # Get employees on duty
    on_duty_employees = []
    try:
        from apps.employees.models import Attendance
        today_attendances = Attendance.objects.filter(
            date=today,
            check_out_time__isnull=True,
            status='present'
        ).select_related('employee')
        on_duty_employees = [att.employee for att in today_attendances]
    except:
        pass
    
    # Calculate additional metrics
    daily_revenue = 0
    try:
        daily_revenue = recent_payments and sum(p.amount for p in recent_payments) or 0
    except:
        pass
    
    low_stock_alerts = InventoryAlert.objects.filter(
        is_resolved=False,
        alert_type__in=['low_stock', 'out_of_stock']
    ).count()
    
    context = {
        'operations': operations,
        'bays': bays,
        'bay_consumption_data': bay_consumption_data,
        'available_items': available_items,
        'reconciliation': reconciliation,
        'summary': {
            'total_allocated': total_allocated,
            'total_used': total_used,
            'total_remaining': total_remaining,
            'total_bays': bays.count(),
            'active_bays': bays.filter(is_active=True).count(),
            'occupied_bays': bays.filter(is_occupied=True).count(),
        },
        'recent_orders': recent_orders,
        'recent_stock_movements': recent_stock_movements,
        'recent_payments': recent_payments,
        'recent_customers': recent_customers,
        'on_duty_employees': on_duty_employees,
        'daily_revenue': daily_revenue,
        'active_customers_today': active_customers_today,
        'new_customers_today': new_customers_today,
        'low_stock_alerts': low_stock_alerts,
        'page_title': f'Daily Operations Command Center - {today}',
        **get_inventory_urls(request)
    }
    
    return render(request, 'inventory/daily_operations.html', context)


@employee_required()
@require_POST
def allocate_to_bay(request):
    """Allocate inventory items to wash bays"""
    from .models import DailyOperations, BayConsumption
    from apps.services.models import ServiceBay
    
    try:
        with transaction.atomic():
            today = timezone.now().date()
            operations = DailyOperations.objects.get(operation_date=today)
            
            bay_id = request.POST.get('bay_id')
            item_id = request.POST.get('item_id')
            quantity = float(request.POST.get('quantity', 0))
            
            bay = ServiceBay.objects.get(id=bay_id)
            item = InventoryItem.objects.get(id=item_id)
            
            # Check stock availability
            if item.current_stock < quantity:
                messages.error(request, f'Insufficient stock for {item.name}. Available: {item.current_stock}')
                return redirect('inventory:daily_operations')
            
            # Check if allocation already exists
            allocation, created = BayConsumption.objects.get_or_create(
                daily_operations=operations,
                bay=bay,
                item=item,
                defaults={
                    'quantity_allocated': quantity,
                    'unit_cost': item.unit_cost,
                    'transferred_by': request.user.employee if hasattr(request.user, 'employee') else None,
                }
            )
            
            if not created:
                # Update existing allocation
                allocation.quantity_allocated += quantity
                allocation.save()
            
            # Create stock movement
            StockMovement.objects.create(
                item=item,
                movement_type='out',
                quantity=quantity,
                unit_cost=item.unit_cost,
                reference_type='bay_allocation',
                reference_id=f"Bay-{bay.bay_number}-{today}",
                notes=f"Allocated to Bay {bay.bay_number} for daily operations",
                created_by=request.user
            )
            
            # Update item stock
            item.current_stock -= quantity
            item.save()
            
            messages.success(request, f'Successfully allocated {quantity} {item.unit.symbol} of {item.name} to Bay {bay.bay_number}')
            
    except Exception as e:
        messages.error(request, f'Error allocating items: {str(e)}')
    
    return redirect('inventory:daily_operations')


@employee_required()
@require_POST
def record_bay_consumption(request):
    """Record actual consumption by a bay"""
    from .models import DailyOperations, BayConsumption
    
    try:
        today = timezone.now().date()
        operations = DailyOperations.objects.get(operation_date=today)
        
        consumption_id = request.POST.get('consumption_id')
        quantity_used = float(request.POST.get('quantity_used', 0))
        notes = request.POST.get('notes', '')
        
        consumption = BayConsumption.objects.get(
            id=consumption_id,
            daily_operations=operations
        )
        
        # Validate quantity
        if quantity_used > consumption.quantity_allocated:
            messages.error(request, 'Quantity used cannot exceed allocated quantity')
            return redirect('inventory:daily_operations')
        
        consumption.quantity_used = quantity_used
        consumption.quantity_remaining = consumption.quantity_allocated - quantity_used
        consumption.notes = notes
        consumption.status = 'completed' if quantity_used == consumption.quantity_allocated else 'in_use'
        consumption.updated_by = request.user.employee if hasattr(request.user, 'employee') else None
        consumption.save()
        
        messages.success(request, f'Consumption recorded for Bay {consumption.bay.bay_number}')
        
    except Exception as e:
        messages.error(request, f'Error recording consumption: {str(e)}')
    
    return redirect('inventory:daily_operations')


@employee_required()
@require_POST
def transfer_between_bays(request):
    """Transfer inventory between wash bays"""
    from .models import DailyOperations, BayConsumption
    
    try:
        with transaction.atomic():
            today = timezone.now().date()
            operations = DailyOperations.objects.get(operation_date=today)
            
            from_bay_id = request.POST.get('from_bay_id')
            to_bay_id = request.POST.get('to_bay_id')
            item_id = request.POST.get('item_id')
            quantity = float(request.POST.get('quantity', 0))
            
            # Get source consumption
            from_consumption = BayConsumption.objects.get(
                daily_operations=operations,
                bay_id=from_bay_id,
                item_id=item_id
            )
            
            # Check available quantity
            if from_consumption.quantity_remaining < quantity:
                messages.error(request, 'Insufficient quantity available for transfer')
                return redirect('inventory:daily_operations')
            
            # Update source bay
            from_consumption.quantity_remaining -= quantity
            from_consumption.save()
            
            # Get or create target bay allocation
            to_consumption, created = BayConsumption.objects.get_or_create(
                daily_operations=operations,
                bay_id=to_bay_id,
                item_id=item_id,
                defaults={
                    'quantity_allocated': quantity,
                    'unit_cost': from_consumption.unit_cost,
                    'transferred_by': request.user.employee if hasattr(request.user, 'employee') else None,
                }
            )
            
            if not created:
                to_consumption.quantity_allocated += quantity
                to_consumption.quantity_remaining += quantity
                to_consumption.save()
            
            messages.success(request, f'Successfully transferred {quantity} units between bays')
            
    except Exception as e:
        messages.error(request, f'Error transferring items: {str(e)}')
    
    return redirect('inventory:daily_operations')


@employee_required()
@require_POST
def return_to_stock(request):
    """Return unused items from bay back to stock"""
    from .models import DailyOperations, BayConsumption
    
    try:
        with transaction.atomic():
            today = timezone.now().date()
            operations = DailyOperations.objects.get(operation_date=today)
            
            consumption_id = request.POST.get('consumption_id')
            quantity_returned = float(request.POST.get('quantity_returned', 0))
            
            consumption = BayConsumption.objects.get(
                id=consumption_id,
                daily_operations=operations
            )
            
            # Validate quantity
            if quantity_returned > consumption.quantity_remaining:
                messages.error(request, 'Return quantity cannot exceed remaining quantity')
                return redirect('inventory:daily_operations')
            
            # Update consumption
            consumption.quantity_remaining -= quantity_returned
            consumption.status = 'returned' if consumption.quantity_remaining == 0 else consumption.status
            consumption.save()
            
            # Return to stock
            item = consumption.item
            item.current_stock += quantity_returned
            item.save()
            
            # Create stock movement
            StockMovement.objects.create(
                item=item,
                movement_type='in',
                quantity=quantity_returned,
                unit_cost=consumption.unit_cost,
                reference_type='bay_return',
                reference_id=f"Bay-{consumption.bay.bay_number}-Return-{today}",
                notes=f"Returned from Bay {consumption.bay.bay_number}",
                created_by=request.user
            )
            
            messages.success(request, f'Successfully returned {quantity_returned} units to stock')
            
    except Exception as e:
        messages.error(request, f'Error returning items: {str(e)}')
    
    return redirect('inventory:daily_operations')


@employee_required()
def start_reconciliation(request):
    """Start daily inventory reconciliation"""
    from .models import DailyOperations, InventoryReconciliation, ReconciliationItem
    
    try:
        with transaction.atomic():
            today = timezone.now().date()
            operations = DailyOperations.objects.get(operation_date=today)
            
            # Create reconciliation record
            reconciliation, created = InventoryReconciliation.objects.get_or_create(
                daily_operations=operations,
                defaults={
                    'completed_by': request.user.employee if hasattr(request.user, 'employee') else None,
                }
            )
            
            if created:
                # Create reconciliation items for all active inventory
                active_items = InventoryItem.objects.filter(is_active=True)
                
                for item in active_items:
                    ReconciliationItem.objects.create(
                        reconciliation=reconciliation,
                        item=item,
                        system_stock=item.current_stock,
                        physical_stock=item.current_stock,  # To be updated during count
                    )
                
                reconciliation.total_items_checked = active_items.count()
                reconciliation.save()
                
                messages.success(request, f'Reconciliation started with {active_items.count()} items')
            else:
                messages.info(request, 'Reconciliation already in progress')
            
    except Exception as e:
        messages.error(request, f'Error starting reconciliation: {str(e)}')
    
    return redirect('inventory:daily_operations')


@employee_required()
@ajax_required
def ajax_update_reconciliation_item(request):
    """AJAX endpoint to update reconciliation item physical count"""
    from .models import ReconciliationItem
    
    if request.method == 'POST':
        try:
            item_id = request.POST.get('item_id')
            physical_stock = float(request.POST.get('physical_stock', 0))
            reason = request.POST.get('reason', '')
            
            recon_item = ReconciliationItem.objects.get(id=item_id)
            recon_item.physical_stock = physical_stock
            recon_item.reason = reason
            recon_item.verified_by = request.user.employee if hasattr(request.user, 'employee') else None
            recon_item.save()
            
            # Update reconciliation summary
            reconciliation = recon_item.reconciliation
            reconciliation.total_discrepancies = reconciliation.item_records.filter(has_discrepancy=True).count()
            reconciliation.total_variance_value = reconciliation.item_records.aggregate(
                total=Sum('variance_value')
            )['total'] or 0
            reconciliation.save()
            
            return JsonResponse({
                'success': True,
                'variance': float(recon_item.variance),
                'variance_value': float(recon_item.variance_value),
                'has_discrepancy': recon_item.has_discrepancy
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
    
    return JsonResponse({'success': False, 'message': 'Invalid request'}, status=400)


@employee_required()
@require_POST
def complete_reconciliation(request):
    """Complete daily reconciliation and update stock levels"""
    from .models import DailyOperations, InventoryReconciliation
    
    try:
        with transaction.atomic():
            today = timezone.now().date()
            operations = DailyOperations.objects.get(operation_date=today)
            reconciliation = InventoryReconciliation.objects.get(daily_operations=operations)
            
            # Update stock levels based on physical counts
            for item_record in reconciliation.item_records.all():
                if item_record.has_discrepancy:
                    # Update item stock to match physical count
                    item = item_record.item
                    old_stock = item.current_stock
                    item.current_stock = item_record.physical_stock
                    item.save()
                    
                    # Create stock movement for adjustment
                    movement_type = 'in' if item_record.variance > 0 else 'out'
                    StockMovement.objects.create(
                        item=item,
                        movement_type=movement_type,
                        quantity=abs(item_record.variance),
                        unit_cost=item.unit_cost,
                        reference_type='reconciliation',
                        reference_id=f"Recon-{today}",
                        notes=f"Reconciliation adjustment. Reason: {item_record.reason}",
                        created_by=request.user
                    )
            
            # Mark reconciliation as completed
            reconciliation.is_completed = True
            reconciliation.completed_at = timezone.now()
            reconciliation.save()
            
            # Update operations status
            operations.status = 'reconciled'
            operations.reconciled_at = timezone.now()
            operations.reconciled_by = request.user.employee if hasattr(request.user, 'employee') else None
            operations.save()
            
            messages.success(request, 'Reconciliation completed successfully')
            
    except Exception as e:
        messages.error(request, f'Error completing reconciliation: {str(e)}')
    
    return redirect('inventory:daily_operations')


@employee_required()
def get_bay_status(request):
    """Get current status of all wash bays for AJAX updates"""
    from apps.services.models import ServiceBay, ServiceOrder
    
    try:
        bays = ServiceBay.objects.filter(is_active=True).order_by('bay_number')
        bay_data = []
        
        for bay in bays:
            # Get current order if any
            current_order = None
            try:
                current_order = ServiceOrder.objects.filter(
                    bay=bay,
                    status__in=['in_progress', 'started']
                ).first()
            except:
                pass
            
            bay_info = {
                'id': bay.id,
                'bay_number': bay.bay_number,
                'name': bay.name,
                'is_occupied': getattr(bay, 'is_occupied', False),
                'is_active': bay.is_active,
                'current_order': None
            }
            
            if current_order:
                bay_info['current_order'] = {
                    'id': current_order.id,
                    'customer_name': str(current_order.customer),
                    'service_name': current_order.service.name if hasattr(current_order, 'service') else 'Service',
                    'started_at': current_order.created_at.strftime('%H:%M')
                }
            
            bay_data.append(bay_info)
        
        return JsonResponse({
            'success': True,
            'bays': bay_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@employee_required()
def get_activity_feed(request):
    """Get recent activities across all modules for the activity feed"""
    try:
        activities = []
        today = timezone.now().date()
        
        # Recent stock movements
        recent_movements = StockMovement.objects.filter(
            created_at__date=today
        ).select_related('item').order_by('-created_at')[:5]
        
        for movement in recent_movements:
            activities.append({
                'type': 'stock_movement',
                'icon': 'fas fa-boxes',
                'color': 'info',
                'title': f'Stock {movement.movement_type.title()}',
                'description': f'{movement.quantity} {movement.item.name}',
                'time': movement.created_at.strftime('%H:%M'),
                'user': str(movement.created_by) if movement.created_by else 'System'
            })
        
        # Recent service orders
        try:
            from apps.services.models import ServiceOrder
            recent_orders = ServiceOrder.objects.filter(
                created_at__date=today
            ).select_related('customer', 'queue_entry__service_bay').order_by('-created_at')[:5]
            
            for order in recent_orders:
                bay_info = "TBD"
                if hasattr(order, 'queue_entry') and order.queue_entry and order.queue_entry.service_bay:
                    bay_info = f"Bay {order.queue_entry.service_bay.bay_number}"
                
                activities.append({
                    'type': 'service_order',
                    'icon': 'fas fa-car',
                    'color': 'primary',
                    'title': 'New Service Order',
                    'description': f'{order.customer} - {bay_info}',
                    'time': order.created_at.strftime('%H:%M'),
                    'user': str(order.created_by) if hasattr(order, 'created_by') else 'System'
                })
        except:
            pass
        
        # Recent payments
        try:
            from apps.payments.models import Payment
            recent_payments = Payment.objects.filter(
                created_at__date=today
            ).select_related('customer').order_by('-created_at')[:3]
            
            for payment in recent_payments:
                activities.append({
                    'type': 'payment',
                    'icon': 'fas fa-money-bill-wave',
                    'color': 'success',
                    'title': 'Payment Received',
                    'description': f'${payment.amount} from {payment.customer}',
                    'time': payment.created_at.strftime('%H:%M'),
                    'user': str(payment.created_by) if hasattr(payment, 'created_by') else 'System'
                })
        except:
            pass
        
        # Sort all activities by time (newest first)
        activities.sort(key=lambda x: x['time'], reverse=True)
        
        return JsonResponse({
            'success': True,
            'activities': activities[:15]  # Limit to 15 most recent
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@employee_required()
@require_POST
def update_operations_target(request):
    """Update daily operations target"""
    try:
        target = int(request.POST.get('target', 0))
        today = timezone.now().date()
        
        operations, _ = DailyOperations.objects.get_or_create(
            operation_date=today,
            defaults={'shift_supervisor': request.user.employee if hasattr(request.user, 'employee') else None}
        )
        
        operations.target_services = target
        operations.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Target updated to {target} services'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@employee_required()
def create_purchase_orders_ajax(request):
    """Create purchase orders for low stock items via AJAX"""
    if request.method == 'POST':
        try:
            import json
            from apps.suppliers.models import PurchaseOrder, PurchaseOrderItem, Supplier
            from django.db import transaction
            
            data = json.loads(request.body)
            item_ids = data.get('item_ids', [])
            
            if not item_ids:
                return JsonResponse({
                    'success': False,
                    'error': 'No items selected'
                })
            
            created_orders = []
            
            with transaction.atomic():
                # Group items by supplier
                items_by_supplier = {}
                
                for item_id in item_ids:
                    try:
                        item = InventoryItem.objects.get(id=item_id)
                        supplier = item.primary_supplier
                        
                        if not supplier:
                            continue
                            
                        if supplier.id not in items_by_supplier:
                            items_by_supplier[supplier.id] = {
                                'supplier': supplier,
                                'items': []
                            }
                        
                        # Calculate reorder quantity
                        reorder_qty = item.reorder_quantity or (item.maximum_stock_level - item.current_stock)
                        if reorder_qty <= 0:
                            reorder_qty = item.minimum_stock_level * 2  # Default to 2x minimum
                        
                        items_by_supplier[supplier.id]['items'].append({
                            'item': item,
                            'quantity': reorder_qty
                        })
                        
                    except InventoryItem.DoesNotExist:
                        continue
                
                # Create purchase orders for each supplier
                for supplier_data in items_by_supplier.values():
                    supplier = supplier_data['supplier']
                    items = supplier_data['items']
                    
                    if not items:
                        continue
                    
                    # Generate PO number
                    import datetime
                    po_number = f"PO-{datetime.datetime.now().strftime('%Y%m%d')}-{supplier.supplier_code}"
                    
                    # Create purchase order
                    po = PurchaseOrder.objects.create(
                        po_number=po_number,
                        supplier=supplier,
                        status='draft',
                        priority='normal',
                        order_date=timezone.now().date(),
                        expected_delivery_date=timezone.now().date() + timezone.timedelta(days=supplier.lead_time_days or 7),
                        payment_terms=supplier.payment_terms,
                        delivery_terms=supplier.delivery_terms,
                        requested_by=request.user.employee if hasattr(request.user, 'employee') else None,
                        notes=f"Auto-generated for low stock items on {timezone.now().date()}"
                    )
                    
                    # Add items to purchase order
                    total_amount = 0
                    for item_data in items:
                        item = item_data['item']
                        quantity = item_data['quantity']
                        unit_price = item.unit_cost or 0
                        line_total = quantity * unit_price
                        
                        PurchaseOrderItem.objects.create(
                            purchase_order=po,
                            item=item,
                            quantity=quantity,
                            unit_price=unit_price,
                            line_total=line_total,
                            notes=f"Restock for low inventory (Current: {item.current_stock} {item.unit.abbreviation})"
                        )
                        
                        total_amount += line_total
                    
                    # Update purchase order totals
                    po.subtotal = total_amount
                    po.total_amount = total_amount
                    po.save()
                    
                    created_orders.append({
                        'po_number': po.po_number,
                        'supplier': supplier.name,
                        'total_amount': float(total_amount),
                        'item_count': len(items),
                        'url': f"/business/{request.tenant.slug}/suppliers/orders/{po.id}/"
                    })
            
            return JsonResponse({
                'success': True,
                'message': f'Created {len(created_orders)} purchase order(s) successfully',
                'orders': created_orders
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Failed to create purchase orders: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'error': 'Invalid request method'
    })