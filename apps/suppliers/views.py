from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.db.models import Q, Sum, Count, Avg, F
from django.utils import timezone
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
from django.contrib.auth.mixins import LoginRequiredMixin
from datetime import datetime, timedelta
import json
import csv

from apps.core.decorators import business_required, employee_required, manager_required
from .models import (
    Supplier, SupplierCategory, PurchaseOrder, PurchaseOrderItem,
    GoodsReceipt, GoodsReceiptItem, SupplierEvaluation, SupplierPayment,
    SupplierDocument, SupplierContact
)
from .forms import (
    SupplierForm, SupplierCategoryForm, PurchaseOrderForm, PurchaseOrderItemFormSet,
    GoodsReceiptForm, GoodsReceiptItemFormSet, SupplierEvaluationForm,
    SupplierPaymentForm, SupplierDocumentForm, SupplierContactForm, 
    SupplierFilterForm, PurchaseOrderFilterForm
)

@login_required
@business_required
@employee_required(['owner', 'manager', 'supervisor'])
def supplier_dashboard(request):
    """Supplier management dashboard"""
    # Key metrics
    total_suppliers = Supplier.objects.filter(is_active=True).count()
    active_suppliers = Supplier.objects.filter(status='active').count()
    pending_orders = PurchaseOrder.objects.filter(
        status__in=['pending', 'approved', 'sent']
    ).count()
    overdue_orders = PurchaseOrder.objects.filter(
        expected_delivery_date__lt=timezone.now().date(),
        status__in=['approved', 'sent', 'acknowledged', 'partially_received']
    ).count()
    
    # Recent activities
    recent_orders = PurchaseOrder.objects.select_related('supplier').order_by('-created_at')[:5]
    recent_receipts = GoodsReceipt.objects.select_related('supplier').order_by('-receipt_date')[:5]
    
    # Top suppliers by value
    top_suppliers = Supplier.objects.filter(
        is_active=True
    ).order_by('-total_value')[:5]
    
    # Supplier performance
    supplier_ratings = Supplier.objects.filter(
        is_active=True,
        rating__gt=0
    ).order_by('-rating')[:5]
    
    # Monthly purchase trends (last 6 months)
    six_months_ago = timezone.now().date() - timedelta(days=180)
    monthly_purchases = PurchaseOrder.objects.filter(
        order_date__gte=six_months_ago
    ).extra(
        select={'month': 'DATE_FORMAT(order_date, "%%Y-%%m")'}
    ).values('month').annotate(
        total_amount=Sum('total_amount'),
        order_count=Count('id')
    ).order_by('month')
    
    context = {
        'metrics': {
            'total_suppliers': total_suppliers,
            'active_suppliers': active_suppliers,
            'pending_orders': pending_orders,
            'overdue_orders': overdue_orders,
        },
        'recent_orders': recent_orders,
        'recent_receipts': recent_receipts,
        'top_suppliers': top_suppliers,
        'supplier_ratings': supplier_ratings,
        'monthly_purchases': list(monthly_purchases),
    }
    
    return render(request, 'suppliers/dashboard.html', context)

@method_decorator([login_required, business_required, employee_required(['owner', 'manager', 'supervisor'])], name='dispatch')
class SupplierListView(ListView):
    """List all suppliers"""
    model = Supplier
    template_name = 'suppliers/supplier_list.html'
    context_object_name = 'suppliers'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Supplier.objects.filter(is_active=True).select_related('category')
        
        # Apply filters
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category_id=category)
        
        supplier_type = self.request.GET.get('supplier_type')
        if supplier_type:
            queryset = queryset.filter(supplier_type=supplier_type)
        
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(supplier_code__icontains=search) |
                Q(business_name__icontains=search) |
                Q(email__icontains=search)
            )
        
        # Sorting
        sort_by = self.request.GET.get('sort', 'name')
        if sort_by in ['name', '-name', 'rating', '-rating', 'total_orders', '-total_orders']:
            queryset = queryset.order_by(sort_by)
        else:
            queryset = queryset.order_by('name')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = SupplierCategory.objects.filter(is_active=True)
        context['supplier_types'] = Supplier.SUPPLIER_TYPES
        context['status_choices'] = Supplier.STATUS_CHOICES
        context['filter_form'] = SupplierFilterForm(self.request.GET)
        
        # Statistics
        context['total_suppliers'] = Supplier.objects.filter(is_active=True).count()
        context['active_suppliers'] = Supplier.objects.filter(status='active').count()
        context['preferred_suppliers'] = Supplier.objects.filter(is_preferred=True).count()
        
        return context

@method_decorator([login_required, business_required, employee_required(['owner', 'manager', 'supervisor'])], name='dispatch')
class SupplierDetailView(DetailView):
    """Supplier detail view"""
    model = Supplier
    template_name = 'suppliers/supplier_detail.html'
    context_object_name = 'supplier'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        supplier = self.object
        
        # Recent orders
        context['recent_orders'] = supplier.purchase_orders.order_by('-created_at')[:5]
        
        # Performance metrics
        context['performance_metrics'] = {
            'total_orders': supplier.total_orders,
            'total_value': supplier.total_value,
            'average_rating': supplier.average_rating,
            'on_time_delivery': self.calculate_on_time_delivery(supplier),
            'items_supplied': supplier.items_supplied_count,
        }
        
        # Recent evaluations
        context['recent_evaluations'] = supplier.evaluations.order_by('-created_at')[:3]
        
        # Outstanding orders
        context['outstanding_orders'] = supplier.purchase_orders.filter(
            status__in=['approved', 'sent', 'acknowledged', 'partially_received']
        ).count()
        
        # Documents
        context['documents'] = supplier.documents.filter(is_active=True)[:5]
        
        # Payment history
        context['recent_payments'] = supplier.payments.order_by('-payment_date')[:5]
        
        # Contacts
        context['contacts'] = supplier.contacts.filter(is_active=True)
        
        return context
    
    def calculate_on_time_delivery(self, supplier):
        """Calculate on-time delivery percentage"""
        completed_orders = supplier.purchase_orders.filter(
            status='completed',
            delivery_date__isnull=False
        )
        
        if completed_orders.exists():
            on_time_orders = completed_orders.filter(
                delivery_date__lte=F('expected_delivery_date')
            ).count()
            return (on_time_orders / completed_orders.count()) * 100
        return 0

@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class SupplierCreateView(CreateView):
    """Create new supplier"""
    model = Supplier
    form_class = SupplierForm
    template_name = 'suppliers/supplier_form.html'
    success_url = reverse_lazy('suppliers:list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Supplier created successfully!')
        return super().form_valid(form)

@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class SupplierUpdateView(UpdateView):
    """Update supplier"""
    model = Supplier
    form_class = SupplierForm
    template_name = 'suppliers/supplier_form.html'
    success_url = reverse_lazy('suppliers:list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Supplier updated successfully!')
        return super().form_valid(form)

@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class SupplierDeleteView(DeleteView):
    """Delete supplier (soft delete)"""
    model = Supplier
    template_name = 'suppliers/supplier_confirm_delete.html'
    success_url = reverse_lazy('suppliers:list')
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        # Soft delete
        self.object.is_active = False
        self.object.save()
        messages.success(request, 'Supplier deleted successfully!')
        return redirect(self.success_url)

@method_decorator([login_required, business_required, employee_required(['owner', 'manager', 'supervisor'])], name='dispatch')
class PurchaseOrderListView(ListView):
    """List purchase orders"""
    model = PurchaseOrder
    template_name = 'suppliers/purchase_order_list.html'
    context_object_name = 'orders'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = PurchaseOrder.objects.select_related('supplier').prefetch_related('items')
        
        # Apply filters
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        supplier = self.request.GET.get('supplier')
        if supplier:
            queryset = queryset.filter(supplier_id=supplier)
        
        priority = self.request.GET.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)
        
        # Date range filter
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            queryset = queryset.filter(order_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(order_date__lte=date_to)
        
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(po_number__icontains=search) |
                Q(supplier__name__icontains=search) |
                Q(supplier_reference__icontains=search)
            )
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['suppliers'] = Supplier.objects.filter(is_active=True, status='active')
        context['status_choices'] = PurchaseOrder.STATUS_CHOICES
        context['priority_choices'] = PurchaseOrder.PRIORITY_LEVELS
        context['filter_form'] = PurchaseOrderFilterForm(self.request.GET)
        
        # Statistics
        orders = PurchaseOrder.objects.all()
        context['total_orders'] = orders.count()
        context['pending_orders'] = orders.filter(status__in=['draft', 'pending', 'approved']).count()
        context['overdue_orders'] = orders.filter(
            expected_delivery_date__lt=timezone.now().date(),
            status__in=['approved', 'sent', 'acknowledged', 'partially_received']
        ).count()
        
        return context

@method_decorator([login_required, business_required, employee_required(['owner', 'manager', 'supervisor'])], name='dispatch')
class PurchaseOrderDetailView(DetailView):
    """Purchase order detail view"""
    model = PurchaseOrder
    template_name = 'suppliers/purchase_order_detail.html'
    context_object_name = 'order'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = self.object
        
        # Order items
        context['items'] = order.items.select_related('item').all()
        
        # Receipts
        context['receipts'] = order.receipts.order_by('-receipt_date')
        
        # Progress tracking
        context['progress'] = {
            'completion_percentage': order.completion_percentage,
            'is_overdue': order.is_overdue,
            'days_overdue': order.days_overdue if order.is_overdue else 0,
        }
        
        return context

@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class PurchaseOrderCreateView(CreateView):
    """Create purchase order"""
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = 'suppliers/purchase_order_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['items_formset'] = PurchaseOrderItemFormSet(self.request.POST)
        else:
            context['items_formset'] = PurchaseOrderItemFormSet()
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        items_formset = context['items_formset']
        
        if items_formset.is_valid():
            # Generate PO number
            form.instance.po_number = self.generate_po_number()
            if hasattr(self.request, 'employee'):
                form.instance.requested_by = self.request.employee
            
            self.object = form.save()
            items_formset.instance = self.object
            items_formset.save()
            
            # Calculate totals
            self.object.calculate_totals()
            
            messages.success(self.request, f'Purchase Order {self.object.po_number} created successfully!')
            return redirect('suppliers:purchase_order_detail', pk=self.object.pk)
        else:
            return self.form_invalid(form)
    
    def generate_po_number(self):
        """Generate unique PO number"""
        today = timezone.now()
        prefix = f"PO{today.strftime('%Y%m')}"
        
        last_po = PurchaseOrder.objects.filter(
            po_number__startswith=prefix
        ).order_by('-po_number').first()
        
        if last_po:
            try:
                last_num = int(last_po.po_number[-4:])
                new_num = last_num + 1
            except (ValueError, IndexError):
                new_num = 1
        else:
            new_num = 1
        
        return f"{prefix}{new_num:04d}"

@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class PurchaseOrderUpdateView(UpdateView):
    """Update purchase order"""
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = 'suppliers/purchase_order_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['items_formset'] = PurchaseOrderItemFormSet(
                self.request.POST, 
                instance=self.object
            )
        else:
            context['items_formset'] = PurchaseOrderItemFormSet(instance=self.object)
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        items_formset = context['items_formset']
        
        if items_formset.is_valid():
            self.object = form.save()
            items_formset.save()
            
            # Recalculate totals
            self.object.calculate_totals()
            
            messages.success(self.request, 'Purchase Order updated successfully!')
            return redirect('suppliers:purchase_order_detail', pk=self.object.pk)
        else:
            return self.form_invalid(form)

@login_required
@business_required
@employee_required(['owner', 'manager'])
@require_http_methods(["POST"])
def approve_purchase_order(request, pk):
    """Approve purchase order"""
    order = get_object_or_404(PurchaseOrder, pk=pk)
    
    if order.status != 'pending':
        messages.error(request, 'Only pending orders can be approved.')
        return redirect('suppliers:purchase_order_detail', pk=pk)
    
    order.approve(request.user)
    messages.success(request, f'Purchase Order {order.po_number} approved successfully!')
    
    return redirect('suppliers:purchase_order_detail', pk=pk)

@login_required
@business_required
@employee_required(['owner', 'manager', 'supervisor'])
@require_http_methods(["POST"])
def send_purchase_order(request, pk):
    """Send purchase order to supplier"""
    order = get_object_or_404(PurchaseOrder, pk=pk)
    
    if order.status != 'approved':
        messages.error(request, 'Only approved orders can be sent.')
        return redirect('suppliers:purchase_order_detail', pk=pk)
    
    order.send_to_supplier()
    messages.success(request, f'Purchase Order {order.po_number} sent to supplier!')
    
    return redirect('suppliers:purchase_order_detail', pk=pk)

@method_decorator([login_required, business_required, employee_required(['owner', 'manager', 'supervisor'])], name='dispatch')
class GoodsReceiptListView(ListView):
    """List goods receipts"""
    model = GoodsReceipt
    template_name = 'suppliers/goods_receipt_list.html'
    context_object_name = 'receipts'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = GoodsReceipt.objects.select_related('supplier', 'purchase_order')
        
        # Apply filters
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        supplier = self.request.GET.get('supplier')
        if supplier:
            queryset = queryset.filter(supplier_id=supplier)
        
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(receipt_number__icontains=search) |
                Q(purchase_order__po_number__icontains=search) |
                Q(delivery_note_number__icontains=search)
            )
        
        return queryset.order_by('-receipt_date')

@method_decorator([login_required, business_required, employee_required(['owner', 'manager', 'supervisor'])], name='dispatch')
class GoodsReceiptCreateView(CreateView):
    """Create goods receipt"""
    model = GoodsReceipt
    form_class = GoodsReceiptForm
    template_name = 'suppliers/goods_receipt_form.html'
    
    def get_initial(self):
        initial = super().get_initial()
        po_id = self.request.GET.get('po')
        if po_id:
            try:
                po = PurchaseOrder.objects.get(pk=po_id)
                initial['purchase_order'] = po
                initial['supplier'] = po.supplier
            except PurchaseOrder.DoesNotExist:
                pass
        return initial
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.request.POST:
            context['items_formset'] = GoodsReceiptItemFormSet(self.request.POST)
        else:
            context['items_formset'] = GoodsReceiptItemFormSet()
            
        # Pre-populate items if PO is selected
        po_id = self.request.GET.get('po')
        if po_id and not self.request.POST:
            try:
                po = PurchaseOrder.objects.get(pk=po_id)
                context['purchase_order'] = po
                context['pending_items'] = po.items.filter(
                    received_quantity__lt=F('quantity')
                )
            except PurchaseOrder.DoesNotExist:
                pass
        
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        items_formset = context['items_formset']
        
        if items_formset.is_valid():
            # Generate receipt number
            form.instance.receipt_number = self.generate_receipt_number()
            if hasattr(self.request, 'employee'):
                form.instance.received_by = self.request.employee
            
            self.object = form.save()
            items_formset.instance = self.object
            items_formset.save()
            
            messages.success(self.request, f'Goods Receipt {self.object.receipt_number} created successfully!')
            return redirect('suppliers:goods_receipt_detail', pk=self.object.pk)
        else:
            return self.form_invalid(form)
    
    def generate_receipt_number(self):
        """Generate unique receipt number"""
        today = timezone.now()
        prefix = f"GR{today.strftime('%Y%m')}"
        
        last_receipt = GoodsReceipt.objects.filter(
            receipt_number__startswith=prefix
        ).order_by('-receipt_number').first()
        
        if last_receipt:
            try:
                last_num = int(last_receipt.receipt_number[-4:])
                new_num = last_num + 1
            except (ValueError, IndexError):
                new_num = 1
        else:
            new_num = 1
        
        return f"{prefix}{new_num:04d}"

@method_decorator([login_required, business_required, employee_required(['owner', 'manager', 'supervisor'])], name='dispatch')
class GoodsReceiptDetailView(DetailView):
    """Goods receipt detail view"""
    model = GoodsReceipt
    template_name = 'suppliers/goods_receipt_detail.html'
    context_object_name = 'receipt'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        receipt = self.object
        
        # Receipt items
        context['items'] = receipt.items.select_related('purchase_order_item__item').all()
        
        return context

@login_required
@business_required
@employee_required(['owner', 'manager', 'supervisor'])
@require_http_methods(["POST"])
def complete_goods_receipt(request, pk):
    """Complete goods receipt and update inventory"""
    receipt = get_object_or_404(GoodsReceipt, pk=pk)
    
    if receipt.status == 'completed':
        messages.error(request, 'Receipt is already completed.')
        return redirect('suppliers:goods_receipt_detail', pk=pk)
    
    try:
        receipt.complete_receipt()
        messages.success(request, f'Goods Receipt {receipt.receipt_number} completed and inventory updated!')
    except Exception as e:
        messages.error(request, f'Error completing receipt: {str(e)}')
    
    return redirect('suppliers:goods_receipt_detail', pk=pk)

@login_required
@business_required
@employee_required(['owner', 'manager'])
def supplier_categories(request):
    """Manage supplier categories"""
    categories = SupplierCategory.objects.filter(is_active=True).annotate(
        supplier_count=Count('suppliers', filter=Q(suppliers__is_active=True))
    )
    
    if request.method == 'POST':
        form = SupplierCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category created successfully!')
            return redirect('suppliers:categories')
    else:
        form = SupplierCategoryForm()
    
    context = {
        'categories': categories,
        'form': form
    }
    
    return render(request, 'suppliers/categories.html', context)

@login_required
@business_required
@employee_required(['owner', 'manager'])
def export_suppliers(request):
    """Export suppliers to CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="suppliers.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Supplier Code', 'Name', 'Business Name', 'Category', 'Type', 'Status',
        'Email', 'Phone', 'Total Orders', 'Total Value', 'Rating', 'Last Order Date'
    ])
    
    suppliers = Supplier.objects.filter(is_active=True).select_related('category')
    
    for supplier in suppliers:
        writer.writerow([
            supplier.supplier_code,
            supplier.name,
            supplier.business_name,
            supplier.category.name if supplier.category else '',
            supplier.get_supplier_type_display(),
            supplier.get_status_display(),
            supplier.email,
            str(supplier.phone) if supplier.phone else '',
            supplier.total_orders,
            supplier.total_value,
            supplier.rating,
            supplier.last_order_date.strftime('%Y-%m-%d') if supplier.last_order_date else '',
        ])
    
    return response

@login_required
@business_required
@employee_required(['owner', 'manager', 'supervisor'])
def supplier_performance_report(request):
    """Generate supplier performance report"""
    # Get date range
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=90)  # Last 3 months
    
    if request.GET.get('start_date'):
        start_date = datetime.strptime(request.GET.get('start_date'), '%Y-%m-%d').date()
    if request.GET.get('end_date'):
        end_date = datetime.strptime(request.GET.get('end_date'), '%Y-%m-%d').date()
    
    # Get suppliers with orders in the period
    suppliers_data = []
    
    for supplier in Supplier.objects.filter(is_active=True):
        orders = supplier.purchase_orders.filter(
            order_date__gte=start_date,
            order_date__lte=end_date
        )
        
        if orders.exists():
            completed_orders = orders.filter(status='completed')
            on_time_orders = completed_orders.filter(
                delivery_date__lte=F('expected_delivery_date')
            )
            
            suppliers_data.append({
                'supplier': supplier,
                'total_orders': orders.count(),
                'total_value': orders.aggregate(Sum('total_amount'))['total_amount'] or 0,
                'completed_orders': completed_orders.count(),
                'on_time_orders': on_time_orders.count(),
                'on_time_rate': (on_time_orders.count() / completed_orders.count() * 100) if completed_orders.count() > 0 else 0,
                'average_order_value': orders.aggregate(Avg('total_amount'))['total_amount'] or 0,
                'rating': supplier.average_rating,
            })
    
    # Sort by total value
    suppliers_data.sort(key=lambda x: x['total_value'], reverse=True)
    
    context = {
        'suppliers_data': suppliers_data,
        'start_date': start_date,
        'end_date': end_date,
        'total_suppliers': len(suppliers_data),
        'total_orders': sum(s['total_orders'] for s in suppliers_data),
        'total_value': sum(s['total_value'] for s in suppliers_data),
    }
    
    return render(request, 'suppliers/performance_report.html', context)

@login_required
@business_required
@employee_required(['owner', 'manager', 'supervisor'])
def ajax_purchase_order_items(request):
    """AJAX endpoint to get purchase order items for goods receipt"""
    po_id = request.GET.get('po_id')
    
    if not po_id:
        return JsonResponse({'error': 'Purchase Order ID required'}, status=400)
    
    try:
        po = PurchaseOrder.objects.get(pk=po_id)
        items = []
        
        for item in po.items.filter(received_quantity__lt=F('quantity')):
            items.append({
                'id': item.id,
                'item_name': item.item.name,
                'item_sku': item.item.sku,
                'ordered_quantity': float(item.quantity),
                'received_quantity': float(item.received_quantity),
                'pending_quantity': float(item.pending_quantity),
                'unit_price': float(item.unit_price),
            })
        
        return JsonResponse({
            'po_number': po.po_number,
            'supplier': po.supplier.name,
            'items': items
        })
        
    except PurchaseOrder.DoesNotExist:
        return JsonResponse({'error': 'Purchase Order not found'}, status=404)

# Supplier Evaluation Views
@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class SupplierEvaluationListView(ListView):
    """List supplier evaluations"""
    model = SupplierEvaluation
    template_name = 'suppliers/evaluation_list.html'
    context_object_name = 'evaluations'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = SupplierEvaluation.objects.select_related('supplier', 'evaluated_by')
        
        supplier = self.request.GET.get('supplier')
        if supplier:
            queryset = queryset.filter(supplier_id=supplier)
        
        period = self.request.GET.get('period')
        if period:
            queryset = queryset.filter(evaluation_period=period)
        
        return queryset.order_by('-period_end')

@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class SupplierEvaluationCreateView(CreateView):
    """Create supplier evaluation"""
    model = SupplierEvaluation
    form_class = SupplierEvaluationForm
    template_name = 'suppliers/evaluation_form.html'
    success_url = reverse_lazy('suppliers:evaluation_list')
    
    def form_valid(self, form):
        if hasattr(self.request, 'employee'):
            form.instance.evaluated_by = self.request.employee
        messages.success(self.request, 'Supplier evaluation saved successfully!')
        return super().form_valid(form)

# Supplier Payment Views
@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class SupplierPaymentListView(ListView):
    """List supplier payments"""
    model = SupplierPayment
    template_name = 'suppliers/payment_list.html'
    context_object_name = 'payments'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = SupplierPayment.objects.select_related('supplier')
        
        supplier = self.request.GET.get('supplier')
        if supplier:
            queryset = queryset.filter(supplier_id=supplier)
        
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        method = self.request.GET.get('method')
        if method:
            queryset = queryset.filter(payment_method=method)
        
        return queryset.order_by('-payment_date')

@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class SupplierPaymentCreateView(CreateView):
    """Create supplier payment"""
    model = SupplierPayment
    form_class = SupplierPaymentForm
    template_name = 'suppliers/payment_form.html'
    success_url = reverse_lazy('suppliers:payment_list')
    
    def form_valid(self, form):
        # Generate payment number
        form.instance.payment_number = self.generate_payment_number()
        if hasattr(self.request, 'employee'):
            form.instance.processed_by = self.request.employee
        
        messages.success(self.request, 'Payment record created successfully!')
        return super().form_valid(form)
    
    def generate_payment_number(self):
        """Generate unique payment number"""
        today = timezone.now()
        prefix = f"SP{today.strftime('%Y%m')}"
        
        last_payment = SupplierPayment.objects.filter(
            payment_number__startswith=prefix
        ).order_by('-payment_number').first()
        
        if last_payment:
            try:
                last_num = int(last_payment.payment_number[-4:])
                new_num = last_num + 1
            except (ValueError, IndexError):
                new_num = 1
        else:
            new_num = 1
        
        return f"{prefix}{new_num:04d}"

@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class SupplierPaymentDetailView(DetailView):
    """Supplier payment detail view"""
    model = SupplierPayment
    template_name = 'suppliers/payment_detail.html'
    context_object_name = 'payment'

@login_required
@business_required
@employee_required(['owner', 'manager'])
@require_http_methods(["POST"])
def process_payment(request, pk):
    """Process supplier payment"""
    payment = get_object_or_404(SupplierPayment, pk=pk)
    
    if payment.status != 'pending':
        messages.error(request, 'Only pending payments can be processed.')
        return redirect('suppliers:payment_detail', pk=pk)
    
    try:
        payment.process_payment(request.user)
        messages.success(request, f'Payment {payment.payment_number} processed successfully!')
    except Exception as e:
        messages.error(request, f'Error processing payment: {str(e)}')
    
    return redirect('suppliers:payment_detail', pk=pk)

# Supplier Document Views
@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class SupplierDocumentListView(ListView):
    """List supplier documents"""
    model = SupplierDocument
    template_name = 'suppliers/document_list.html'
    context_object_name = 'documents'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = SupplierDocument.objects.select_related('supplier')
        
        supplier = self.request.GET.get('supplier')
        if supplier:
            queryset = queryset.filter(supplier_id=supplier)
        
        doc_type = self.request.GET.get('document_type')
        if doc_type:
            queryset = queryset.filter(document_type=doc_type)
        
        return queryset.order_by('-created_at')

@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class SupplierDocumentCreateView(CreateView):
    """Upload supplier document"""
    model = SupplierDocument
    form_class = SupplierDocumentForm
    template_name = 'suppliers/document_form.html'
    success_url = reverse_lazy('suppliers:document_list')
    
    def form_valid(self, form):
        if hasattr(self.request, 'employee'):
            form.instance.uploaded_by = self.request.employee
        messages.success(self.request, 'Document uploaded successfully!')
        return super().form_valid(form)

# Supplier Contact Views
@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class SupplierContactCreateView(CreateView):
    """Add supplier contact"""
    model = SupplierContact
    form_class = SupplierContactForm
    template_name = 'suppliers/contact_form.html'
    
    def get_initial(self):
        initial = super().get_initial()
        supplier_id = self.kwargs.get('supplier_id')
        if supplier_id:
            initial['supplier'] = get_object_or_404(Supplier, pk=supplier_id)
        return initial
    
    def form_valid(self, form):
        messages.success(self.request, 'Contact added successfully!')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('suppliers:detail', kwargs={'pk': self.object.supplier.pk})