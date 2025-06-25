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
    InventoryAlert, ItemLocation
)
from .forms import (
    InventoryItemForm, InventoryCategoryForm, UnitForm, 
    StockAdjustmentForm, StockTakeForm, ItemSearchForm, UnitSearchForm
)
from datetime import datetime, timedelta
import json


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
        'title': 'Inventory Dashboard'
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
        'title': 'Inventory Items'
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
            return redirect('inventory:item_detail', pk=item.pk)
    else:
        form = InventoryItemForm()
    
    context = {
        'form': form,
        'title': 'Create Inventory Item'
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
        return redirect('inventory:stock_take_detail', pk=pk)
    
    stock_take.start_stock_take()
    messages.success(request, f'Stock take "{stock_take.name}" has been started.')
    return redirect('inventory:stock_take_detail', pk=pk)

@login_required
@employee_required(['owner', 'manager'])
@require_POST
def complete_stock_take(request, pk):
    """Complete a stock take"""
    stock_take = get_object_or_404(StockTake, pk=pk)
    
    if stock_take.status != 'in_progress':
        messages.error(request, 'Stock take is not in progress.')
        return redirect('inventory:stock_take_detail', pk=pk)
    
    # Check if all items have been counted
    uncounted_items = stock_take.count_records.filter(counted_quantity=0).count()
    if uncounted_items > 0:
        messages.warning(request, f'{uncounted_items} items have not been counted yet.')
        return redirect('inventory:stock_take_detail', pk=pk)
    
    stock_take.complete_stock_take()
    messages.success(request, f'Stock take "{stock_take.name}" has been completed.')
    return redirect('inventory:stock_take_detail', pk=pk)

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
        'title': 'Inventory Alerts'
    }
    return render(request, 'inventory/alerts.html', context)

@login_required
@employee_required()
@require_POST
def resolve_alert(request, alert_id):
    """Resolve an inventory alert"""
    alert = get_object_or_404(InventoryAlert, id=alert_id)
    alert.resolve(request.user)
    
    messages.success(request, f'Alert for {alert.item.name} has been resolved.')
    return redirect('inventory:alerts')

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
        'title': 'Stock Movements'
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
        'title': 'Inventory Categories'
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
            return redirect('inventory:category_list')
    else:
        form = InventoryCategoryForm()
    
    context = {
        'form': form,
        'title': 'Create Category'
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
            data = json.loads(request.body)
            item_id = data.get('item_id')
            service_order_id = data.get('service_order_id')
            service_id = data.get('service_id')
            quantity = float(data.get('quantity', 0))
            
            item = InventoryItem.objects.get(id=item_id)
            
            # Check if enough stock is available
            if item.current_stock < quantity:
                return JsonResponse({
                    'error': f'Insufficient stock. Available: {item.current_stock}'
                }, status=400)
            
            # Create consumption record
            consumption = ItemConsumption.objects.create(
                item=item,
                service_order_id=service_order_id,
                service_id=service_id,
                quantity=quantity,
                unit_cost=item.unit_cost,
                used_by=request.employee
            )
            
            # Update stock
            item.current_stock -= quantity
            item.save()
            
            # Create stock movement
            StockMovement.objects.create(
                item=item,
                movement_type='out',
                quantity=-quantity,
                unit_cost=item.unit_cost,
                old_stock=item.current_stock + quantity,
                new_stock=item.current_stock,
                reference_type='sale',
                service_order_id=service_order_id,
                reason=f'Used for service order',
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
        'title': 'Inventory Valuation Report'
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
        'title': f'Item - {item.name}'
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
                    adjustment.new_stock = adjustment.old_stock + adjustment.quantity
                    adjustment.created_by = request.user
                    adjustment.save()
                    
                    # Update item stock
                    adjustment.item.current_stock = adjustment.new_stock
                    adjustment.item.save()
                    
                    # Create stock movement
                    StockMovement.objects.create(
                        item=adjustment.item,
                        movement_type='adjustment',
                        quantity=adjustment.quantity,
                        unit_cost=adjustment.unit_cost,
                        old_stock=adjustment.old_stock,
                        new_stock=adjustment.new_stock,
                        reference_type='adjustment',
                        reason=adjustment.reason,
                        created_by=request.user
                    )
                    
                    # Auto-approve if user has permission
                    if request.employee.role in ['owner', 'manager']:
                        adjustment.approve(request.user)
                    
                    messages.success(request, 'Stock adjustment created successfully!')
                    return redirect('inventory:item_detail', pk=adjustment.item.pk)
                    
            except Exception as e:
                messages.error(request, f'Error creating adjustment: {str(e)}')
    else:
        form = StockAdjustmentForm(initial_item=item)
    
    context = {
        'form': form,
        'item': item,
        'title': f'Stock Adjustment - {item.name}' if item else 'Stock Adjustment'
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
        'title': 'Low Stock Report'
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
        'title': 'Stock Takes'
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
            stock_take.supervisor = request.employee
            stock_take.created_by = request.user
            stock_take.save()
            
            # Save many-to-many relationships
            form.save_m2m()
            
            messages.success(request, f'Stock take "{stock_take.name}" created successfully!')
            return redirect('inventory:stock_take_detail', pk=stock_take.pk)
    else:
        form = StockTakeForm()
    
    context = {
        'form': form,
        'title': 'Create Stock Take'
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
        'title': f'Stock Take - {stock_take.name}'
    }
    return render(request, 'inventory/stock_take_detail.html', context)

@login_required
@employee_required()
@require_POST
def update_stock_count(request, stock_take_id, item_id):
    """Update stock count for an item"""
    stock_take = get_object_or_404(StockTake, pk=stock_take_id)
    item = get_object_or_404(InventoryItem, pk=item_id)
    
    if stock_take.status != 'in_progress':
        return JsonResponse({'error': 'Stock take is not in progress'}, status=400)
    
    counted_quantity = request.POST.get('counted_quantity')
    notes = request.POST.get('notes', '')
    
    try:
        counted_quantity = float(counted_quantity)
        
        count_record, created = StockTakeCount.objects.get_or_create(
            stock_take=stock_take,
            item=item,
            defaults={
                'system_quantity': item.current_stock,
                'counted_quantity': counted_quantity,
                'counted_by': request.employee,
                'notes': notes
            }
        )
        
        if not created:
            count_record.counted_quantity = counted_quantity
            count_record.counted_by = request.employee
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
# views.py - Add these views to your inventory views

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
        'title': 'Units of Measurement'
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
            return redirect('inventory:unit_list')
    else:
        form = UnitForm()
    
    context = {
        'form': form,
        'title': 'Create Unit of Measurement'
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
            return redirect('inventory:unit_list')
    else:
        form = UnitForm(instance=unit)
    
    context = {
        'form': form,
        'unit': unit,
        'title': f'Edit Unit - {unit.name}'
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
        'items_using_unit': items_using_unit[:20],  # Show first 20
        'recent_items': recent_items,
        'stats': stats,
        'title': f'Unit Details - {unit.name}'
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
    
    return redirect('inventory:unit_list')

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
    
    return redirect('inventory:unit_list')

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
    
    return redirect('inventory:unit_list')