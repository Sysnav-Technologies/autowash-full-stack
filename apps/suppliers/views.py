from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.db.models import Q, Sum, Count, Avg, F
from django.db.models.functions import TruncMonth
from django.db import models, transaction
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
    Invoice, Supplier, SupplierCategory, PurchaseOrder, PurchaseOrderItem,
    GoodsReceipt, GoodsReceiptItem, SupplierEvaluation, SupplierPayment,
    SupplierDocument, SupplierContact
)
from .forms import (
    InvoiceForm, InvoiceItemFormSet, SupplierForm, SupplierCategoryForm, PurchaseOrderForm, PurchaseOrderItemFormSet,
    GoodsReceiptForm, GoodsReceiptItemFormSet, SupplierEvaluationForm,
    SupplierPaymentForm, SupplierDocumentForm, SupplierContactForm, 
    SupplierFilterForm, PurchaseOrderFilterForm
)

def get_supplier_urls(request):
    """Generate all supplier URLs for templates"""
    tenant_slug = request.tenant.slug
    base_url = f"/business/{tenant_slug}/suppliers"
    
    return {
        'dashboard': f"{base_url}/",
        'businesses_dashboard': f"/business/{tenant_slug}/dashboard/",
        'list': f"{base_url}/list/",
        'create': f"{base_url}/create/",
        'categories': f"{base_url}/categories/",
        'purchase_order_list': f"{base_url}/orders/",
        'purchase_order_create': f"{base_url}/orders/create/",
        'goods_receipt_list': f"{base_url}/receipts/",
        'goods_receipt_create': f"{base_url}/receipts/create/",
        'invoice_list': f"{base_url}/invoices/",
        'invoice_create': f"{base_url}/invoices/create/",
        'evaluation_list': f"{base_url}/evaluations/",
        'evaluation_create': f"{base_url}/evaluations/create/",
        'payment_list': f"{base_url}/payments/",
        'payment_create': f"{base_url}/payments/create/",
        'document_list': f"{base_url}/documents/",
        'document_upload': f"{base_url}/documents/upload/",
        'performance_report': f"{base_url}/performance/",
        'export': f"{base_url}/export/",
        'ajax_purchase_order_items': f"{base_url}/ajax/purchase-order-items/",
        'ajax_search_purchase_orders': f"{base_url}/ajax/search-purchase-orders/",
        'ajax_purchase_order_details': f"{base_url}/ajax/purchase-order-details/",
        'ajax_supplier_details': f"{base_url}/ajax/supplier-details/",
    }

def get_business_url(request, url_name, **kwargs):
    """Helper function to generate URLs with business slug"""
    tenant_slug = request.tenant.slug
    base_url = f"/business/{tenant_slug}/suppliers"
    
    url_mapping = {
        'suppliers:dashboard': f"{base_url}/",
        'businesses:dashboard': f"/business/{tenant_slug}/dashboard/",
        'suppliers:list': f"{base_url}/list/",
        'suppliers:create': f"{base_url}/create/",
        'suppliers:detail': f"{base_url}/{{pk}}/",
        'suppliers:edit': f"{base_url}/{{pk}}/edit/",
        'suppliers:delete': f"{base_url}/{{pk}}/delete/",
        'suppliers:categories': f"{base_url}/categories/",
        'suppliers:contact_add': f"{base_url}/{{supplier_id}}/contacts/add/",
        'suppliers:purchase_order_list': f"{base_url}/orders/",
        'suppliers:purchase_order_create': f"{base_url}/orders/create/",
        'suppliers:purchase_order_detail': f"{base_url}/orders/{{pk}}/",
        'suppliers:purchase_order_edit': f"{base_url}/orders/{{pk}}/edit/",
        'suppliers:purchase_order_approve': f"{base_url}/orders/{{pk}}/approve/",
        'suppliers:purchase_order_send': f"{base_url}/orders/{{pk}}/send/",
        'suppliers:purchase_order_print': f"{base_url}/orders/{{pk}}/print/",
        'suppliers:purchase_order_pdf': f"{base_url}/orders/{{pk}}/pdf/",
        'suppliers:goods_receipt_list': f"{base_url}/receipts/",
        'suppliers:goods_receipt_create': f"{base_url}/receipts/create/",
        'suppliers:goods_receipt_detail': f"{base_url}/receipts/{{pk}}/",
        'suppliers:goods_receipt_complete': f"{base_url}/receipts/{{pk}}/complete/",
        'suppliers:invoice_list': f"{base_url}/invoices/",
        'suppliers:invoice_create': f"{base_url}/invoices/create/",
        'suppliers:invoice_detail': f"{base_url}/invoices/{{pk}}/",
        'suppliers:invoice_print': f"{base_url}/invoices/{{pk}}/print/",
        'suppliers:invoice_pdf': f"{base_url}/invoices/{{pk}}/pdf/",
        'suppliers:evaluation_list': f"{base_url}/evaluations/",
        'suppliers:evaluation_create': f"{base_url}/evaluations/create/",
        'suppliers:payment_list': f"{base_url}/payments/",
        'suppliers:payment_create': f"{base_url}/payments/create/",
        'suppliers:payment_detail': f"{base_url}/payments/{{pk}}/",
        'suppliers:payment_process': f"{base_url}/payments/{{pk}}/process/",
        'suppliers:document_list': f"{base_url}/documents/",
        'suppliers:document_upload': f"{base_url}/documents/upload/",
        'suppliers:performance_report': f"{base_url}/performance/",
        'suppliers:export': f"{base_url}/export/",
        'suppliers:ajax_purchase_order_items': f"{base_url}/ajax/purchase-order-items/",
        'suppliers:create_invoice_from_po': f"{base_url}/orders/{{po_pk}}/create-invoice/",
    }
    
    url = url_mapping.get(url_name, f"{base_url}/")
    
    for key, value in kwargs.items():
        url = url.replace(f"{{{key}}}", str(value))
    
    return url

@login_required
@business_required
@employee_required(['owner', 'manager', 'supervisor'])
def supplier_dashboard(request):
    """Supplier management dashboard"""
    total_suppliers = Supplier.objects.filter(is_deleted=False).count()
    active_suppliers = Supplier.objects.filter(status='active', is_deleted=False).count()
    pending_orders = PurchaseOrder.objects.filter(
        status__in=['pending', 'approved', 'sent']
    ).count()
    overdue_orders = PurchaseOrder.objects.filter(
        expected_delivery_date__lt=timezone.now().date(),
        status__in=['approved', 'sent', 'acknowledged', 'partially_received']
    ).count()
    
    recent_orders = PurchaseOrder.objects.select_related('supplier').order_by('-created_at')[:5]
    recent_receipts = GoodsReceipt.objects.select_related('supplier').order_by('-receipt_date')[:5]
    
    top_suppliers = Supplier.objects.filter(
        is_deleted=False
    ).order_by('-total_value')[:5]
    
    supplier_ratings = Supplier.objects.filter(
        is_deleted=False,
        rating__gt=0
    ).order_by('-rating')[:5]
    
    six_months_ago = timezone.now().date() - timedelta(days=180)
    monthly_purchases = PurchaseOrder.objects.filter(
        order_date__gte=six_months_ago
    ).annotate(
        month=TruncMonth('order_date')
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
        'urls': get_supplier_urls(request),
    }
    
    return render(request, 'suppliers/dashboard.html', context)

@method_decorator([login_required, business_required, employee_required(['owner', 'manager', 'supervisor'])], name='dispatch')
class SupplierListView(ListView):
    model = Supplier
    template_name = 'suppliers/supplier_list.html'
    context_object_name = 'suppliers'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Supplier.objects.filter(is_deleted=False).select_related('category')
        
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
        
        context['total_suppliers'] = Supplier.objects.filter(is_deleted=False).count()
        context['active_suppliers'] = Supplier.objects.filter(status='active', is_deleted=False).count()
        context['preferred_suppliers'] = Supplier.objects.filter(is_preferred=True, is_deleted=False).count()
        
        context['urls'] = get_supplier_urls(self.request)
        
        return context

@method_decorator([login_required, business_required, employee_required(['owner', 'manager', 'supervisor'])], name='dispatch')
class SupplierDetailView(DetailView):
    model = Supplier
    template_name = 'suppliers/supplier_detail.html'
    context_object_name = 'supplier'
    
    def get_queryset(self):
        return Supplier.objects.filter(is_deleted=False)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        supplier = self.object
        
        context['recent_orders'] = supplier.purchase_orders.order_by('-created_at')[:5]
        
        context['performance_metrics'] = {
            'total_orders': supplier.total_orders,
            'total_value': supplier.total_value,
            'average_rating': supplier.average_rating,
            'on_time_delivery': self.calculate_on_time_delivery(supplier),
            'items_supplied': supplier.items_supplied_count,
        }
        
        context['recent_evaluations'] = supplier.evaluations.order_by('-created_at')[:3]
        
        context['outstanding_orders'] = supplier.purchase_orders.filter(
            status__in=['approved', 'sent', 'acknowledged', 'partially_received']
        ).count()
        
        context['documents'] = supplier.documents.filter(is_active=True)[:5]
        context['recent_payments'] = supplier.payments.order_by('-payment_date')[:5]
        context['contacts'] = supplier.contacts.filter(is_active=True)
        context['urls'] = get_supplier_urls(self.request)
        
        return context
    
    def calculate_on_time_delivery(self, supplier):
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
    model = Supplier
    form_class = SupplierForm
    template_name = 'suppliers/supplier_form.html'
    
    def get_success_url(self):
        return get_business_url(self.request, 'suppliers:list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['urls'] = get_supplier_urls(self.request)
        return context
    
    def form_valid(self, form):
        messages.success(self.request, 'Supplier created successfully!')
        return super().form_valid(form)

@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class SupplierUpdateView(UpdateView):
    model = Supplier
    form_class = SupplierForm
    template_name = 'suppliers/supplier_form.html'
    
    def get_queryset(self):
        return Supplier.objects.filter(is_deleted=False)
    
    def get_success_url(self):
        return get_business_url(self.request, 'suppliers:detail', pk=self.object.pk)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['urls'] = get_supplier_urls(self.request)
        return context
    
    def form_valid(self, form):
        messages.success(self.request, 'Supplier updated successfully!')
        return super().form_valid(form)

@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class SupplierDeleteView(DeleteView):
    model = Supplier
    template_name = 'suppliers/supplier_confirm_delete.html'
    
    def get_queryset(self):
        return Supplier.objects.filter(is_deleted=False)
    
    def get_success_url(self):
        return get_business_url(self.request, 'suppliers:list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['urls'] = get_supplier_urls(self.request)
        return context
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.is_deleted = True
        self.object.deleted_at = timezone.now()
        self.object.save()
        messages.success(request, 'Supplier deleted successfully!')
        return redirect(self.get_success_url())

@method_decorator([login_required, business_required, employee_required(['owner', 'manager', 'supervisor'])], name='dispatch')
class PurchaseOrderListView(ListView):
    model = PurchaseOrder
    template_name = 'suppliers/purchase_order_list.html'
    context_object_name = 'orders'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = PurchaseOrder.objects.select_related('supplier').prefetch_related('items')
        
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        supplier = self.request.GET.get('supplier')
        if supplier:
            queryset = queryset.filter(supplier_id=supplier)
        
        priority = self.request.GET.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)
        
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
        context['suppliers'] = Supplier.objects.filter(is_deleted=False, status='active')
        context['status_choices'] = PurchaseOrder.STATUS_CHOICES
        context['priority_choices'] = PurchaseOrder.PRIORITY_LEVELS
        context['filter_form'] = PurchaseOrderFilterForm(self.request.GET)
        
        orders = PurchaseOrder.objects.all()
        context['total_orders'] = orders.count()
        context['pending_orders'] = orders.filter(status__in=['draft', 'pending', 'approved']).count()
        context['overdue_orders'] = orders.filter(
            expected_delivery_date__lt=timezone.now().date(),
            status__in=['approved', 'sent', 'acknowledged', 'partially_received']
        ).count()
        
        context['urls'] = get_supplier_urls(self.request)
        
        return context

@method_decorator([login_required, business_required, employee_required(['owner', 'manager', 'supervisor'])], name='dispatch')
class PurchaseOrderDetailView(DetailView):
    model = PurchaseOrder
    template_name = 'suppliers/purchase_order_detail.html'
    context_object_name = 'order'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = self.object
        
        user_role = None
        if hasattr(self.request.user, 'employee_profile') and self.request.user.employee_profile:
            user_role = self.request.user.employee_profile.role
        
        context['items'] = order.items.select_related('item').all()
        context['receipts'] = order.receipts.order_by('-receipt_date')
        
        context['progress'] = {
            'completion_percentage': order.completion_percentage,
            'is_overdue': order.is_overdue,
            'days_overdue': order.days_overdue if order.is_overdue else 0,
        }
        
        context['user_role'] = user_role
        
        context['can_edit'] = order.status in ['draft', 'pending']
        context['can_approve'] = (
            order.status in ['draft', 'pending'] and 
            user_role in ['owner', 'manager']
        )
        context['can_send'] = order.status == 'approved'
        context['can_acknowledge'] = order.status == 'sent'
        context['can_receive'] = order.status in ['sent', 'acknowledged', 'partially_received']
        context['can_cancel'] = order.status in ['draft', 'pending', 'approved']
        context['can_create_invoice'] = order.status == 'completed'
        
        context['print_url'] = f"/business/{self.request.tenant.slug}/suppliers/orders/{order.pk}/print/"
        context['pdf_url'] = f"/business/{self.request.tenant.slug}/suppliers/orders/{order.pk}/pdf/"
        
        context['urls'] = get_supplier_urls(self.request)
        
        return context

@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class PurchaseOrderCreateView(CreateView):
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = 'suppliers/purchase_order_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['items_formset'] = PurchaseOrderItemFormSet(self.request.POST)
        else:
            context['items_formset'] = PurchaseOrderItemFormSet()
        
        context['urls'] = get_supplier_urls(self.request)
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        items_formset = context['items_formset']
        
        if items_formset.is_valid():
            form.instance.po_number = self.generate_po_number()
            if hasattr(self.request.user, 'employee_profile'):
                form.instance.requested_by = self.request.user.employee_profile
            
            self.object = form.save()
            items_formset.instance = self.object
            items_formset.save()
            
            self.object.calculate_totals()
            
            messages.success(self.request, f'Purchase Order {self.object.po_number} created successfully!')
            return redirect(get_business_url(self.request, 'suppliers:purchase_order_detail', pk=self.object.pk))
        else:
            return self.form_invalid(form)
    
    def generate_po_number(self):
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
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = 'suppliers/purchase_order_form.html'
    
    def get_queryset(self):
        return PurchaseOrder.objects.filter(status__in=['draft', 'pending'])
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['items_formset'] = PurchaseOrderItemFormSet(
                self.request.POST, 
                instance=self.object
            )
        else:
            context['items_formset'] = PurchaseOrderItemFormSet(instance=self.object)
        
        user_role = None
        if hasattr(self.request.user, 'employee_profile') and self.request.user.employee_profile:
            user_role = self.request.user.employee_profile.role
        context['user_role'] = user_role
        
        context['urls'] = get_supplier_urls(self.request)
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        items_formset = context['items_formset']
        
        if items_formset.is_valid():
            self.object = form.save()
            items_formset.save()
            
            self.object.calculate_totals()
            
            messages.success(self.request, 'Purchase Order updated successfully!')
            return redirect(get_business_url(self.request, 'suppliers:purchase_order_detail', pk=self.object.pk))
        else:
            return self.form_invalid(form)
    
    def get_success_url(self):
        return get_business_url(self.request, 'suppliers:purchase_order_detail', pk=self.object.pk)

@login_required
@business_required
@employee_required(['owner', 'manager', 'supervisor'])
def purchase_order_print(request, pk):
    order = get_object_or_404(PurchaseOrder, pk=pk)
    
    context = {
        'order': order,
        'items': order.items.select_related('item').all(),
    }
    
    return render(request, 'suppliers/purchase_order_print.html', context)

@login_required
@business_required
@employee_required(['owner', 'manager', 'supervisor'])
def purchase_order_pdf(request, pk):
    try:
        from weasyprint import HTML, CSS
        from django.template.loader import render_to_string
        
        order = get_object_or_404(PurchaseOrder, pk=pk)
        
        html_string = render_to_string('suppliers/purchase_order_print.html', {
            'order': order,
            'items': order.items.select_related('item').all(),
            'request': request,
        })
        
        html = HTML(string=html_string, base_url=request.build_absolute_uri())
        pdf = html.write_pdf()
        
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="PO-{order.po_number}.pdf"'
        return response
        
    except ImportError:
        messages.error(request, 'PDF generation is not available. Please install weasyprint.')
        return redirect('suppliers:purchase_order_detail', pk=pk)

@login_required
@business_required
@employee_required(['owner', 'manager', 'supervisor'])
@require_http_methods(["POST"])
def approve_purchase_order(request, pk):
    order = get_object_or_404(PurchaseOrder, pk=pk)
    
    if order.status not in ['draft', 'pending']:
        messages.error(request, 'Only draft or pending orders can be approved.')
        return redirect(get_business_url(request, 'suppliers:purchase_order_detail', pk=pk))
    
    if not order.items.exists():
        messages.error(request, 'Cannot approve an order without items.')
        return redirect(get_business_url(request, 'suppliers:purchase_order_detail', pk=pk))
    
    order.approve(request.user)
    
    # Trigger notification
    from apps.core.notifications import send_purchase_order_notification
    send_purchase_order_notification(order, 'approved')
    
    auto_send = request.POST.get('auto_send', 'false').lower() == 'true'
    if auto_send:
        order.send_to_supplier()
        send_purchase_order_notification(order, 'sent')
        messages.success(request, f'Purchase Order {order.po_number} approved and sent to supplier!')
    else:
        messages.success(request, f'Purchase Order {order.po_number} approved successfully!')
    
    return redirect(get_business_url(request, 'suppliers:purchase_order_detail', pk=pk))

@login_required
@business_required
@employee_required(['owner', 'manager', 'supervisor'])
@require_http_methods(["POST"])
def send_purchase_order(request, pk):
    order = get_object_or_404(PurchaseOrder, pk=pk)
    
    if order.status != 'approved':
        messages.error(request, 'Only approved orders can be sent.')
        return redirect(get_business_url(request, 'suppliers:purchase_order_detail', pk=pk))
    
    order.send_to_supplier()
    
    # Trigger notification
    from apps.core.notifications import send_purchase_order_notification
    send_purchase_order_notification(order, 'sent')
    
    messages.success(request, f'Purchase Order {order.po_number} sent to supplier!')
    
    return redirect(get_business_url(request, 'suppliers:purchase_order_detail', pk=pk))

@login_required
@business_required
@employee_required(['owner', 'manager', 'supervisor'])
@require_http_methods(["POST"])
def submit_purchase_order(request, pk):
    order = get_object_or_404(PurchaseOrder, pk=pk)
    
    if order.status != 'draft':
        messages.error(request, 'Only draft orders can be submitted for approval.')
        return redirect(get_business_url(request, 'suppliers:purchase_order_detail', pk=pk))
    
    if not order.items.exists():
        messages.error(request, 'Cannot submit an order without items.')
        return redirect(get_business_url(request, 'suppliers:purchase_order_detail', pk=pk))
    
    order.status = 'pending'
    order.save()
    
    messages.success(request, f'Purchase Order {order.po_number} submitted for approval!')
    return redirect(get_business_url(request, 'suppliers:purchase_order_detail', pk=pk))

@login_required
@business_required
@employee_required(['owner', 'manager'])
@require_http_methods(["POST"])
def cancel_purchase_order(request, pk):
    order = get_object_or_404(PurchaseOrder, pk=pk)
    
    if order.status not in ['draft', 'pending', 'approved']:
        messages.error(request, 'Cannot cancel an order that has been sent to supplier.')
        return redirect(get_business_url(request, 'suppliers:purchase_order_detail', pk=pk))
    
    order.status = 'cancelled'
    order.save()
    
    # Trigger notification
    from apps.core.notifications import send_purchase_order_notification
    send_purchase_order_notification(order, 'cancelled')
    
    messages.success(request, f'Purchase Order {order.po_number} has been cancelled.')
    return redirect(get_business_url(request, 'suppliers:purchase_order_detail', pk=pk))

@login_required
@business_required
@employee_required(['owner', 'manager', 'supervisor'])
@require_http_methods(["POST"])
def acknowledge_purchase_order(request, pk):
    order = get_object_or_404(PurchaseOrder, pk=pk)
    
    if order.status != 'sent':
        messages.error(request, 'Only sent orders can be acknowledged.')
        return redirect(get_business_url(request, 'suppliers:purchase_order_detail', pk=pk))
    
    order.acknowledge_receipt()
    messages.success(request, f'Purchase Order {order.po_number} marked as acknowledged by supplier!')
    
    return redirect(get_business_url(request, 'suppliers:purchase_order_detail', pk=pk))

@login_required
@business_required
@employee_required(['owner', 'manager', 'supervisor'])
def purchase_order_status_update(request, pk):
    order = get_object_or_404(PurchaseOrder, pk=pk)
    new_status = request.POST.get('status')
    
    if not new_status:
        messages.error(request, 'No status provided.')
        return redirect(get_business_url(request, 'suppliers:purchase_order_detail', pk=pk))
    
    valid_transitions = {
        'draft': ['pending', 'cancelled'],
        'pending': ['approved', 'cancelled', 'draft'],
        'approved': ['sent', 'cancelled'],
        'sent': ['acknowledged', 'cancelled'],
        'acknowledged': ['partially_received', 'completed', 'cancelled'],
        'partially_received': ['completed', 'cancelled'],
        'completed': [],
        'cancelled': [],
        'on_hold': ['pending', 'cancelled'],
    }
    
    if new_status not in valid_transitions.get(order.status, []):
        messages.error(request, f'Invalid status transition from {order.get_status_display()} to {new_status}.')
        return redirect(get_business_url(request, 'suppliers:purchase_order_detail', pk=pk))
    
    old_status = order.status
    order.status = new_status
    
    if new_status == 'approved' and hasattr(request.user, 'employee_profile'):
        order.approved_by = request.user.employee_profile
        order.approved_at = timezone.now()
    
    order.save()
    
    status_messages = {
        'pending': f'Purchase Order {order.po_number} submitted for approval.',
        'approved': f'Purchase Order {order.po_number} has been approved.',
        'sent': f'Purchase Order {order.po_number} has been sent to supplier.',
        'acknowledged': f'Purchase Order {order.po_number} acknowledged by supplier.',
        'completed': f'Purchase Order {order.po_number} has been completed.',
        'cancelled': f'Purchase Order {order.po_number} has been cancelled.',
        'on_hold': f'Purchase Order {order.po_number} has been put on hold.',
    }
    
    message = status_messages.get(new_status, f'Purchase Order {order.po_number} status updated to {order.get_status_display()}.')
    messages.success(request, message)
    
    return redirect(get_business_url(request, 'suppliers:purchase_order_detail', pk=pk))

@method_decorator([login_required, business_required, employee_required(['owner', 'manager', 'supervisor'])], name='dispatch')
class GoodsReceiptListView(ListView):
    model = GoodsReceipt
    template_name = 'suppliers/goods_receipt_list.html'
    context_object_name = 'receipts'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = GoodsReceipt.objects.select_related('supplier', 'purchase_order')
        
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
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['urls'] = get_supplier_urls(self.request)
        return context

@method_decorator([login_required, business_required, employee_required(['owner', 'manager', 'supervisor'])], name='dispatch')
class GoodsReceiptCreateView(CreateView):
    model = GoodsReceipt
    form_class = GoodsReceiptForm
    template_name = 'suppliers/goods_receipt_form.html'
    
    def get_initial(self):
        initial = super().get_initial()
        po_id = self.request.GET.get('po')
        if po_id:
            try:
                po = PurchaseOrder.objects.get(pk=po_id)
                if self.can_receive_goods(po):
                    initial['purchase_order'] = po
                    initial['supplier'] = po.supplier
                else:
                    messages.warning(self.request, f'Purchase Order {po.po_number} cannot receive goods or has already been fully received.')
            except PurchaseOrder.DoesNotExist:
                messages.error(self.request, 'Purchase Order not found.')
        return initial
    
    def can_receive_goods(self, po):
        if po.status not in ['approved', 'sent', 'acknowledged', 'partially_received']:
            return False
        
        pending_items = po.items.filter(received_quantity__lt=F('quantity'))
        if not pending_items.exists():
            return False
        
        return True
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.request.POST:
            context['items_formset'] = GoodsReceiptItemFormSet(self.request.POST)
        else:
            context['items_formset'] = GoodsReceiptItemFormSet()
        
        po_id = self.request.GET.get('po')
        if po_id:
            try:
                po = PurchaseOrder.objects.get(pk=po_id)
                if self.can_receive_goods(po):
                    context['purchase_order'] = po
                    context['pending_items'] = po.items.filter(
                        received_quantity__lt=F('quantity')
                    ).select_related('item')
                    
                    context['existing_receipts'] = po.receipts.order_by('-receipt_date')
                    
                    context['po_completion'] = {
                        'percentage': po.completion_percentage,
                        'is_fully_received': po.is_fully_received,
                        'total_items': po.items.count(),
                        'pending_items': context['pending_items'].count()
                    }
                    
                    context['duplicate_warning'] = self.check_duplicate_receipts(po)
            except PurchaseOrder.DoesNotExist:
                pass
        
        context['available_pos'] = PurchaseOrder.objects.filter(
            status__in=['approved', 'sent', 'acknowledged', 'partially_received']
        ).annotate(
            pending_items_count=Count('items', filter=Q(items__received_quantity__lt=F('items__quantity')))
        ).filter(
            pending_items_count__gt=0
        ).select_related('supplier').order_by('-created_at')[:10]
        
        context['urls'] = get_supplier_urls(self.request)
        return context
    
    def check_duplicate_receipts(self, po):
        recent_receipts = po.receipts.filter(
            created_at__gte=timezone.now() - timedelta(hours=24)
        ).order_by('-created_at')
        
        if recent_receipts.exists():
            return {
                'has_recent': True,
                'recent_receipts': recent_receipts,
                'warning_message': f'Warning: {recent_receipts.count()} receipt(s) created for this PO in the last 24 hours.'
            }
        return {'has_recent': False}
    
    def form_valid(self, form):
        context = self.get_context_data()
        items_formset = context['items_formset']
        
        if not items_formset.is_valid():
            return self.form_invalid(form)
        
        po = form.cleaned_data.get('purchase_order')
        if not po:
            messages.error(self.request, 'Please select a purchase order.')
            return self.form_invalid(form)
        
        if not self.can_receive_goods(po):
            messages.error(self.request, f'Purchase Order {po.po_number} cannot receive goods.')
            return self.form_invalid(form)
        
        with transaction.atomic():
            form.instance.receipt_number = self.generate_receipt_number()
            if hasattr(self.request.user, 'employee_profile'):
                form.instance.received_by = self.request.user.employee_profile
            
            self.object = form.save()
            
            items_formset.instance = self.object
            receipt_items = items_formset.save(commit=False)
            
            for receipt_item in receipt_items:
                po_item = receipt_item.purchase_order_item
                
                if receipt_item.received_quantity > po_item.pending_quantity:
                    messages.error(self.request, f'Cannot receive {receipt_item.received_quantity} of {po_item.item.name}. Only {po_item.pending_quantity} pending.')
                    return self.form_invalid(form)
                
                receipt_item.expected_quantity = po_item.pending_quantity
                receipt_item.save()
            
            items_formset.save_m2m()
            
            messages.success(self.request, f'Goods Receipt {self.object.receipt_number} created successfully!')
            
            if self.request.POST.get('save_and_complete'):
                return redirect(get_business_url(self.request, 'suppliers:goods_receipt_complete', pk=self.object.pk))
            else:
                return redirect(get_business_url(self.request, 'suppliers:goods_receipt_detail', pk=self.object.pk))
    
    def generate_receipt_number(self):
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
    model = GoodsReceipt
    template_name = 'suppliers/goods_receipt_detail.html'
    context_object_name = 'receipt'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        receipt = self.object
        
        context['items'] = receipt.items.select_related('purchase_order_item__item').all()
        context['urls'] = get_supplier_urls(self.request)
        
        return context

@login_required
@business_required
@employee_required(['owner', 'manager', 'supervisor'])
@require_http_methods(["POST"])
def complete_goods_receipt(request, pk):
    receipt = get_object_or_404(GoodsReceipt, pk=pk)
    
    if receipt.status == 'completed':
        messages.error(request, 'Receipt is already completed.')
        return redirect(get_business_url(request, 'suppliers:goods_receipt_detail', pk=pk))
    
    try:
        with transaction.atomic():
            receipt.complete_receipt()
            messages.success(request, f'Goods Receipt {receipt.receipt_number} completed and inventory updated!')
    except Exception as e:
        messages.error(request, f'Error completing receipt: {str(e)}')
    
    return redirect(get_business_url(request, 'suppliers:goods_receipt_detail', pk=pk))

@login_required
@business_required
@employee_required(['owner', 'manager', 'supervisor'])
def ajax_search_purchase_orders(request):
    query = request.GET.get('q', '').strip()
    show_all = request.GET.get('show_all', 'false').lower() == 'true'
    invoice_mode = request.GET.get('invoice_mode', 'false').lower() == 'true'
    
    if invoice_mode:
        queryset = PurchaseOrder.objects.filter(
            status='completed'
        ).exclude(
            invoices__isnull=False
        ).select_related('supplier')
    else:
        queryset = PurchaseOrder.objects.filter(
            status__in=['approved', 'sent', 'acknowledged', 'partially_received']
        ).annotate(
            pending_items_count=Count('items', filter=Q(items__received_quantity__lt=F('items__quantity')))
        ).filter(
            pending_items_count__gt=0
        ).select_related('supplier')
    
    if query and not show_all:
        queryset = queryset.filter(
            Q(po_number__icontains=query) |
            Q(supplier__name__icontains=query) |
            Q(supplier__supplier_code__icontains=query) |
            Q(supplier_reference__icontains=query)
        )
    
    queryset = queryset[:20]
    
    results = []
    for po in queryset:
        pending_items_count = 0
        if not invoice_mode:
            pending_items_count = po.items.filter(
                received_quantity__lt=F('quantity')
            ).count()
        
        results.append({
            'id': str(po.pk),
            'po_number': po.po_number,
            'supplier_name': po.supplier.name,
            'supplier_id': str(po.supplier.pk),
            'order_date': po.order_date.strftime('%Y-%m-%d'),
            'expected_delivery': po.expected_delivery_date.strftime('%Y-%m-%d'),
            'total_amount': float(po.total_amount),
            'status': po.status,
            'status_display': po.get_status_display(),
            'pending_items': pending_items_count,
            'completion_percentage': float(po.completion_percentage) if hasattr(po, 'completion_percentage') else 0,
            'items_count': po.items.count(),
        })
    
    return JsonResponse({
        'results': results,
        'total': len(results)
    })

@login_required
@business_required
@employee_required(['owner', 'manager', 'supervisor'])
def ajax_purchase_order_details(request):
    po_id = request.GET.get('po_id')
    
    if not po_id:
        return JsonResponse({'error': 'Purchase Order ID required'}, status=400)
    
    try:
        po = PurchaseOrder.objects.get(pk=po_id)
        
        invoice_mode = request.GET.get('invoice_mode', 'false').lower() == 'true'
        
        if invoice_mode:
            items = po.items.filter(received_quantity__gt=0).select_related('item')
            items_data = []
            for item in items:
                items_data.append({
                    'id': item.id,
                    'item_name': item.item.name,
                    'item_sku': item.item.sku,
                    'description': item.item_description or item.item.name,
                    'quantity': float(item.received_quantity),
                    'unit_price': float(item.unit_price),
                    'total_amount': float(item.unit_price * item.received_quantity),
                })
        else:
            items = po.items.filter(received_quantity__lt=F('quantity')).select_related('item')
            items_data = []
            for item in items:
                pending_qty = item.quantity - item.received_quantity
                items_data.append({
                    'id': item.id,
                    'item_name': item.item.name,
                    'item_sku': item.item.sku,
                    'item_unit': getattr(item.item, 'unit', 'units'),
                    'ordered_quantity': float(item.quantity),
                    'received_quantity': float(item.received_quantity),
                    'pending_quantity': float(pending_qty),
                    'unit_price': float(item.unit_price),
                })
        
        return JsonResponse({
            'po_number': po.po_number,
            'supplier': {
                'id': str(po.supplier.pk),
                'name': po.supplier.name,
                'code': po.supplier.supplier_code,
                'email': po.supplier.email,
                'phone': str(po.supplier.phone) if po.supplier.phone else '',
            },
            'order_date': po.order_date.strftime('%Y-%m-%d'),
            'expected_delivery': po.expected_delivery_date.strftime('%Y-%m-%d'),
            'total_amount': float(po.total_amount),
            'subtotal': float(po.subtotal),
            'tax_amount': float(po.tax_amount),
            'shipping_cost': float(po.shipping_cost),
            'discount_amount': float(po.discount_amount),
            'status': po.status,
            'status_display': po.get_status_display(),
            'items': items_data,
            'delivery_address': po.delivery_address,
            'contact_person': po.contact_person,
            'contact_phone': po.contact_phone,
            'special_instructions': po.special_instructions,
        })
        
    except PurchaseOrder.DoesNotExist:
        return JsonResponse({'error': 'Purchase Order not found'}, status=404)

@login_required
@business_required
@employee_required(['owner', 'manager', 'supervisor'])
def ajax_supplier_details(request):
    supplier_id = request.GET.get('supplier_id')
    
    if not supplier_id:
        return JsonResponse({'error': 'Supplier ID required'}, status=400)
    
    try:
        supplier = Supplier.objects.get(pk=supplier_id, is_deleted=False)
        
        return JsonResponse({
            'id': str(supplier.pk),
            'name': supplier.name,
            'supplier_code': supplier.supplier_code,
            'business_name': supplier.business_name,
            'email': supplier.email,
            'phone': str(supplier.phone) if supplier.phone else '',
            'payment_terms': supplier.payment_terms,
            'currency': supplier.currency,
            'address': supplier.address if hasattr(supplier, 'address') else '',
            'city': supplier.city,
            'state': supplier.state,
            'postal_code': supplier.postal_code,
            'country': supplier.country,
        })
        
    except Supplier.DoesNotExist:
        return JsonResponse({'error': 'Supplier not found'}, status=404)

@login_required
@business_required
@employee_required(['owner', 'manager', 'supervisor'])
def ajax_purchase_order_items(request):
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

@login_required
@business_required
@employee_required(['owner', 'manager'])
def supplier_categories(request):
    categories = SupplierCategory.objects.filter(is_active=True).annotate(
        supplier_count=Count('suppliers', filter=Q(suppliers__is_deleted=False))
    )
    
    if request.method == 'POST':
        form = SupplierCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category created successfully!')
            return redirect(get_business_url(request, 'suppliers:categories'))
    else:
        form = SupplierCategoryForm()
    
    context = {
        'categories': categories,
        'form': form,
        'urls': get_supplier_urls(request),
    }
    
    return render(request, 'suppliers/categories.html', context)

@login_required
@business_required
@employee_required(['owner', 'manager'])
def export_suppliers(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="suppliers.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Supplier Code', 'Name', 'Business Name', 'Category', 'Type', 'Status',
        'Email', 'Phone', 'Total Orders', 'Total Value', 'Rating', 'Last Order Date'
    ])
    
    suppliers = Supplier.objects.filter(is_deleted=False).select_related('category')
    
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
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=90)
    
    if request.GET.get('start_date'):
        start_date = datetime.strptime(request.GET.get('start_date'), '%Y-%m-%d').date()
    if request.GET.get('end_date'):
        end_date = datetime.strptime(request.GET.get('end_date'), '%Y-%m-%d').date()
    
    suppliers_data = []
    
    for supplier in Supplier.objects.filter(is_deleted=False):
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
    
    suppliers_data.sort(key=lambda x: x['total_value'], reverse=True)
    
    context = {
        'suppliers_data': suppliers_data,
        'start_date': start_date,
        'end_date': end_date,
        'total_suppliers': len(suppliers_data),
        'total_orders': sum(s['total_orders'] for s in suppliers_data),
        'total_value': sum(s['total_value'] for s in suppliers_data),
        'urls': get_supplier_urls(request),
    }
    
    return render(request, 'suppliers/performance_report.html', context)

@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class SupplierEvaluationListView(ListView):
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
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['urls'] = get_supplier_urls(self.request)
        return context

@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class SupplierEvaluationCreateView(CreateView):
    model = SupplierEvaluation
    form_class = SupplierEvaluationForm
    template_name = 'suppliers/evaluation_form.html'
    
    def get_success_url(self):
        return get_business_url(self.request, 'suppliers:evaluation_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['urls'] = get_supplier_urls(self.request)
        return context
    
    def form_valid(self, form):
        if hasattr(self.request.user, 'employee_profile'):
            form.instance.evaluated_by = self.request.user.employee_profile
        messages.success(self.request, 'Supplier evaluation saved successfully!')
        return super().form_valid(form)

@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class SupplierPaymentListView(ListView):
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
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['urls'] = get_supplier_urls(self.request)
        return context

@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class SupplierPaymentCreateView(CreateView):
    model = SupplierPayment
    form_class = SupplierPaymentForm
    template_name = 'suppliers/payment_form.html'
    
    def get_success_url(self):
        return get_business_url(self.request, 'suppliers:payment_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['urls'] = get_supplier_urls(self.request)
        return context
    
    def form_valid(self, form):
        form.instance.payment_number = self.generate_payment_number()
        if hasattr(self.request.user, 'employee_profile'):
            form.instance.processed_by = self.request.user.employee_profile
        
        messages.success(self.request, 'Payment record created successfully!')
        return super().form_valid(form)
    
    def generate_payment_number(self):
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
    model = SupplierPayment
    template_name = 'suppliers/payment_detail.html'
    context_object_name = 'payment'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['urls'] = get_supplier_urls(self.request)
        outstanding_invoices = context.get('outstanding_invoices')
        if outstanding_invoices:
            context['total_outstanding'] = sum(
                float(inv.total_amount - (inv.paid_amount or 0)) for inv in outstanding_invoices
            )
        else:
            context['total_outstanding'] = 0
        return context

@login_required
@business_required
@employee_required(['owner', 'manager'])
@require_http_methods(["POST"])
def process_payment(request, pk):
    """Process supplier payment"""
    payment = get_object_or_404(SupplierPayment, pk=pk)
    
    if payment.status != 'pending':
        messages.error(request, 'Only pending payments can be processed.')
        return redirect(get_business_url(request, 'suppliers:payment_detail', pk=pk))
    
    try:
        payment.process_payment(request.user)
        messages.success(request, f'Payment {payment.payment_number} processed successfully!')
    except Exception as e:
        messages.error(request, f'Error processing payment: {str(e)}')
    
    return redirect(get_business_url(request, 'suppliers:payment_detail', pk=pk))

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
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['urls'] = get_supplier_urls(self.request)
        return context

@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class SupplierDocumentCreateView(CreateView):
    """Upload supplier document"""
    model = SupplierDocument
    form_class = SupplierDocumentForm
    template_name = 'suppliers/document_form.html'
    
    def get_success_url(self):
        return get_business_url(self.request, 'suppliers:document_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['urls'] = get_supplier_urls(self.request)
        return context
    
    def form_valid(self, form):
        if hasattr(self.request.user, 'employee_profile'):
            form.instance.uploaded_by = self.request.user.employee_profile
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
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['urls'] = get_supplier_urls(self.request)
        return context
    
    def form_valid(self, form):
        messages.success(self.request, 'Contact added successfully!')
        return super().form_valid(form)
    
    def get_success_url(self):
        return get_business_url(self.request, 'suppliers:detail', pk=self.object.supplier.pk)
    

# Invoice views 
@method_decorator([login_required, business_required, employee_required(['owner', 'manager', 'supervisor'])], name='dispatch')
class InvoiceListView(ListView):
    model = Invoice
    template_name = 'suppliers/invoice_list.html'
    context_object_name = 'invoices'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Invoice.objects.select_related('supplier', 'purchase_order')
        
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        payment_status = self.request.GET.get('payment_status')
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)
        
        supplier = self.request.GET.get('supplier')
        if supplier:
            queryset = queryset.filter(supplier_id=supplier)
        
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            queryset = queryset.filter(invoice_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(invoice_date__lte=date_to)
        
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(invoice_number__icontains=search) |
                Q(supplier_invoice_number__icontains=search) |
                Q(supplier__name__icontains=search)
            )
        
        return queryset.order_by('-invoice_date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['suppliers'] = Supplier.objects.filter(is_deleted=False, status='active')
        context['status_choices'] = Invoice.STATUS_CHOICES
        context['payment_status_choices'] = Invoice.PAYMENT_STATUS_CHOICES
        
        invoices = Invoice.objects.all()
        context['total_invoices'] = invoices.count()
        context['pending_approval'] = invoices.filter(status='received').count()
        context['overdue_invoices'] = invoices.filter(
            due_date__lt=timezone.now().date(),
            payment_status__in=['pending', 'partial']
        ).count()
        # Calculate outstanding amount as total_amount - paid_amount
        outstanding_invoices = invoices.filter(payment_status__in=['pending', 'partial'])
        total_outstanding = 0
        for invoice in outstanding_invoices:
            outstanding = invoice.total_amount - (invoice.paid_amount or 0)
            total_outstanding += outstanding
        context['total_outstanding'] = total_outstanding
        
        context['urls'] = get_supplier_urls(self.request)
        return context

@method_decorator([login_required, business_required, employee_required(['owner', 'manager', 'supervisor'])], name='dispatch')
class InvoiceDetailView(DetailView):
    model = Invoice
    template_name = 'suppliers/invoice_detail.html'
    context_object_name = 'invoice'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        invoice = self.object
        
        context['items'] = invoice.items.all()
        
        context['payments'] = invoice.supplier.payments.filter(
            purchase_orders__in=[invoice.purchase_order] if invoice.purchase_order else []
        ).order_by('-payment_date')[:5]
        
        context['print_url'] = get_business_url(self.request, 'suppliers:invoice_print', pk=invoice.pk)
        context['pdf_url'] = get_business_url(self.request, 'suppliers:invoice_pdf', pk=invoice.pk)
        
        context['urls'] = get_supplier_urls(self.request)
        return context

@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class InvoiceCreateView(CreateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = 'suppliers/invoice_form.html'
    
    def get_initial(self):
        initial = super().get_initial()
        po_id = self.request.GET.get('po')
        if po_id:
            try:
                po = PurchaseOrder.objects.get(pk=po_id, status='completed')
                
                # Check if invoice already exists for this PO
                existing_invoice = Invoice.objects.filter(purchase_order=po).first()
                if existing_invoice:
                    messages.warning(self.request, f'Invoice {existing_invoice.invoice_number} already exists for this purchase order.')
                    return initial
                
                initial['purchase_order'] = po
                initial['supplier'] = po.supplier
                initial['total_amount'] = po.total_amount
                initial['subtotal'] = po.subtotal
                initial['tax_amount'] = po.tax_amount
                initial['shipping_cost'] = po.shipping_cost
                initial['discount_amount'] = po.discount_amount
            except PurchaseOrder.DoesNotExist:
                pass
        return initial
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.request.POST:
            context['items_formset'] = InvoiceItemFormSet(self.request.POST)
        else:
            context['items_formset'] = InvoiceItemFormSet()
        
        # Get purchase order if pre-selected
        po_id = self.request.GET.get('po')
        if po_id:
            try:
                po = PurchaseOrder.objects.get(pk=po_id, status='completed')
                existing_invoice = Invoice.objects.filter(purchase_order=po).first()
                if not existing_invoice:
                    context['purchase_order'] = po
                    context['po_items'] = po.items.filter(
                        received_quantity__gt=0
                    ).select_related('item')
            except PurchaseOrder.DoesNotExist:
                pass
        
        # Get available completed purchase orders without invoices
        context['available_pos'] = PurchaseOrder.objects.filter(
            status='completed'
        ).exclude(
            invoices__isnull=False
        ).select_related('supplier').order_by('-created_at')[:10]
        
        context['urls'] = get_supplier_urls(self.request)
        return context
    
    def form_valid(self, form):
        # Check for duplicate invoice
        po = form.cleaned_data.get('purchase_order')
        if po:
            existing_invoice = Invoice.objects.filter(purchase_order=po).first()
            if existing_invoice:
                messages.error(self.request, f'Invoice {existing_invoice.invoice_number} already exists for this purchase order.')
                return self.form_invalid(form)
        
        context = self.get_context_data()
        items_formset = context['items_formset']
        
        if items_formset.is_valid():
            with transaction.atomic():
                # Generate invoice number
                form.instance.invoice_number = self.generate_invoice_number()
                form.instance.received_date = timezone.now().date()
                
                self.object = form.save()
                items_formset.instance = self.object
                items_formset.save()
                
                # Calculate totals
                self.calculate_invoice_totals()
                
                messages.success(self.request, f'Invoice {self.object.invoice_number} created successfully!')
                return redirect(get_business_url(self.request, 'suppliers:invoice_detail', pk=self.object.pk))
        else:
            return self.form_invalid(form)
    
    def generate_invoice_number(self):
        """Generate unique invoice number"""
        today = timezone.now()
        prefix = f"INV{today.strftime('%Y%m')}"
        
        last_invoice = Invoice.objects.filter(
            invoice_number__startswith=prefix
        ).order_by('-invoice_number').first()
        
        if last_invoice:
            try:
                last_num = int(last_invoice.invoice_number[-4:])
                new_num = last_num + 1
            except (ValueError, IndexError):
                new_num = 1
        else:
            new_num = 1
        
        return f"{prefix}{new_num:04d}"
    
    def calculate_invoice_totals(self):
        """Calculate and update invoice totals"""
        items = self.object.items.all()
        self.object.subtotal = sum(item.total_amount for item in items)
        self.object.save()

@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class InvoiceUpdateView(UpdateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = 'suppliers/invoice_form.html'
    
    def get_queryset(self):
        return Invoice.objects.filter(status__in=['draft', 'received'])
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['items_formset'] = InvoiceItemFormSet(
                self.request.POST, 
                instance=self.object
            )
        else:
            context['items_formset'] = InvoiceItemFormSet(instance=self.object)
        
        context['urls'] = get_supplier_urls(self.request)
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        items_formset = context['items_formset']
        
        if items_formset.is_valid():
            with transaction.atomic():
                self.object = form.save()
                items_formset.save()
                
                # Calculate totals
                self.calculate_invoice_totals()
                
                messages.success(self.request, f'Invoice {self.object.invoice_number} updated successfully!')
                return redirect(get_business_url(self.request, 'suppliers:invoice_detail', pk=self.object.pk))
        else:
            return self.form_invalid(form)
    
    def calculate_invoice_totals(self):
        """Calculate and update invoice totals"""
        items = self.object.items.all()
        self.object.subtotal = sum(item.total_amount for item in items)
        self.object.save()
    
    def get_success_url(self):
        return get_business_url(self.request, 'suppliers:invoice_detail', pk=self.object.pk)

@login_required
@business_required
@employee_required(['owner', 'manager'])
def get_purchase_order_items(request, po_id):
    """Get items from a purchase order for invoice creation"""
    try:
        po = get_object_or_404(PurchaseOrder, pk=po_id, status='completed')
        
        # Get items that have been received
        items = po.items.filter(received_quantity__gt=0).select_related('item')
        
        items_data = []
        for item in items:
            items_data.append({
                'id': item.id,
                'item_name': item.item.name if item.item else item.description,
                'description': item.description,
                'quantity': float(item.received_quantity),
                'unit_price': float(item.unit_price),
                'total_amount': float(item.received_quantity * item.unit_price),
                'item_code': item.item.sku if item.item else '',
                'notes': item.notes or ''
            })
        
        return JsonResponse({
            'success': True,
            'items': items_data,
            'supplier_name': po.supplier.name,
            'po_number': po.po_number
        })
        
    except PurchaseOrder.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Purchase order not found'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@business_required
@employee_required(['owner', 'manager'])
def get_inventory_items(request):
    """Get inventory items for invoice creation"""
    try:
        # Import here to avoid circular imports
        from apps.inventory.models import InventoryItem
        
        search = request.GET.get('search', '')
        supplier_id = request.GET.get('supplier_id')
        
        items = InventoryItem.objects.filter(is_active=True)
        
        if search:
            items = items.filter(
                models.Q(name__icontains=search) | 
                models.Q(sku__icontains=search) |
                models.Q(description__icontains=search)
            )
        
        if supplier_id:
            items = items.filter(suppliers__id=supplier_id)
        
        items = items[:20]  # Limit results
        
        items_data = []
        for item in items:
            items_data.append({
                'id': item.id,
                'name': item.name,
                'sku': item.sku,
                'description': item.description or '',
                'cost_price': float(item.cost_price or 0),
                'current_stock': float(item.current_stock or 0),
                'unit': item.unit or 'pcs'
            })
        
        return JsonResponse({
            'success': True,
            'items': items_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@business_required
@employee_required(['owner', 'manager'])
@require_http_methods(["POST"])
def verify_invoice(request, pk):
    """Verify invoice"""
    invoice = get_object_or_404(Invoice, pk=pk)
    
    if invoice.status != 'received':
        messages.error(request, 'Only received invoices can be verified.')
        return redirect(get_business_url(request, 'suppliers:invoice_detail', pk=pk))
    
    invoice.verify_invoice(request.user)
    messages.success(request, f'Invoice {invoice.invoice_number} verified successfully!')
    
    return redirect(get_business_url(request, 'suppliers:invoice_detail', pk=pk))

@login_required
@business_required
@employee_required(['owner', 'manager'])
@require_http_methods(["POST"])
def approve_invoice(request, pk):
    """Approve invoice for payment"""
    invoice = get_object_or_404(Invoice, pk=pk)
    
    if invoice.status != 'verified':
        messages.error(request, 'Only verified invoices can be approved.')
        return redirect(get_business_url(request, 'suppliers:invoice_detail', pk=pk))
    
    invoice.approve_invoice(request.user)
    messages.success(request, f'Invoice {invoice.invoice_number} approved for payment!')
    
    return redirect(get_business_url(request, 'suppliers:invoice_detail', pk=pk))

@login_required
@business_required
@employee_required(['owner', 'manager', 'supervisor'])
def invoice_print(request, pk):
    """Print invoice"""
    invoice = get_object_or_404(Invoice, pk=pk)
    
    context = {
        'invoice': invoice,
        'items': invoice.items.all(),
    }
    
    return render(request, 'suppliers/invoice_print.html', context)

@login_required
@business_required
@employee_required(['owner', 'manager', 'supervisor'])
def invoice_pdf(request, pk):
    """Generate PDF for invoice"""
    try:
        from weasyprint import HTML, CSS
        from django.template.loader import render_to_string
        
        invoice = get_object_or_404(Invoice, pk=pk)
        
        # Render HTML template
        html_string = render_to_string('suppliers/invoice_print.html', {
            'invoice': invoice,
            'items': invoice.items.all(),
            'request': request,
        })
        
        # Create PDF
        html = HTML(string=html_string, base_url=request.build_absolute_uri())
        pdf = html.write_pdf()
        
        # Return PDF response
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Invoice-{invoice.invoice_number}.pdf"'
        return response
        
    except ImportError:
        # Fallback if weasyprint is not installed
        messages.error(request, 'PDF generation is not available. Please install weasyprint.')
        return redirect('suppliers:invoice_detail', pk=pk)

@login_required
@business_required
@employee_required(['owner', 'manager'])
def create_invoice_from_po(request, po_pk):
    """Create invoice from purchase order"""
    po = get_object_or_404(PurchaseOrder, pk=po_pk)
    
    if po.status != 'completed':
        messages.error(request, 'Can only create invoices from completed purchase orders.')
        return redirect(get_business_url(request, 'suppliers:purchase_order_detail', pk=po_pk))
    
    # Check if invoice already exists for this PO
    existing_invoice = Invoice.objects.filter(purchase_order=po).first()
    if existing_invoice:
        messages.info(request, f'Invoice already exists for this PO: {existing_invoice.invoice_number}')
        return redirect(get_business_url(request, 'suppliers:invoice_detail', pk=existing_invoice.pk))
    
    # Redirect to invoice creation with PO pre-selected
    return redirect(f"{get_business_url(request, 'suppliers:invoice_create')}?po={po.pk}")

# AJAX endpoints for invoice creation
@login_required
@business_required
@employee_required(['owner', 'manager', 'supervisor'])
def ajax_completed_purchase_orders(request):
    """AJAX endpoint to get completed purchase orders for invoice creation"""
    query = request.GET.get('q', '').strip()
    
    # Get completed POs without invoices
    queryset = PurchaseOrder.objects.filter(
        status='completed'
    ).exclude(
        invoices__isnull=False
    ).select_related('supplier')
    
    # Apply search filter
    if query:
        queryset = queryset.filter(
            Q(po_number__icontains=query) |
            Q(supplier__name__icontains=query) |
            Q(supplier__supplier_code__icontains=query)
        )
    
    queryset = queryset[:15]
    
    results = []
    for po in queryset:
        results.append({
            'id': str(po.pk),
            'po_number': po.po_number,
            'supplier_name': po.supplier.name,
            'supplier_id': str(po.supplier.pk),
            'order_date': po.order_date.strftime('%Y-%m-%d'),
            'delivery_date': po.delivery_date.strftime('%Y-%m-%d') if po.delivery_date else '',
            'total_amount': float(po.total_amount),
            'subtotal': float(po.subtotal),
            'tax_amount': float(po.tax_amount),
            'shipping_cost': float(po.shipping_cost),
            'discount_amount': float(po.discount_amount),
            'items_count': po.items.count(),
            'received_items_count': po.items.filter(received_quantity__gt=0).count(),
        })
    
    return JsonResponse({
        'results': results,
        'total': len(results)
    })

@login_required
@business_required
@employee_required(['owner', 'manager', 'supervisor'])
def ajax_po_invoice_items(request):
    """AJAX endpoint to get PO items for invoice creation"""
    po_id = request.GET.get('po_id')
    
    if not po_id:
        return JsonResponse({'error': 'Purchase Order ID required'}, status=400)
    
    try:
        po = PurchaseOrder.objects.get(pk=po_id, status='completed')
        
        # Check if invoice already exists
        existing_invoice = Invoice.objects.filter(purchase_order=po).first()
        if existing_invoice:
            return JsonResponse({
                'error': 'Invoice already exists',
                'invoice_number': existing_invoice.invoice_number,
                'invoice_id': str(existing_invoice.pk)
            }, status=400)
        
        # Get received items only
        items = po.items.filter(received_quantity__gt=0).select_related('item')
        items_data = []
        
        for item in items:
            items_data.append({
                'id': item.id,
                'item_name': item.item.name,
                'item_sku': item.item.sku,
                'description': item.item_description or item.item.name,
                'quantity': float(item.received_quantity),  # Use received quantity
                'unit_price': float(item.unit_price),
                'total_amount': float(item.unit_price * item.received_quantity),
                'item_code': item.item_sku,
            })
        
        return JsonResponse({
            'success': True,
            'po_number': po.po_number,
            'supplier': {
                'id': str(po.supplier.pk),
                'name': po.supplier.name,
                'code': po.supplier.supplier_code,
                'email': po.supplier.email,
            },
            'total_amount': float(po.total_amount),
            'subtotal': float(po.subtotal),
            'tax_amount': float(po.tax_amount),
            'shipping_cost': float(po.shipping_cost),
            'discount_amount': float(po.discount_amount),
            'items': items_data,
            'delivery_address': po.delivery_address,
            'special_instructions': po.special_instructions,
        })
        
    except PurchaseOrder.DoesNotExist:
        return JsonResponse({'error': 'Purchase Order not found'}, status=404)
@login_required
@business_required
@employee_required(['owner', 'manager', 'supervisor'])
@require_http_methods(["POST"])
def submit_purchase_order(request, pk):
    """Submit purchase order for approval"""
    order = get_object_or_404(PurchaseOrder, pk=pk)
    
    if order.status != 'draft':
        messages.error(request, 'Only draft orders can be submitted for approval.')
        return redirect(get_business_url(request, 'suppliers:purchase_order_detail', pk=pk))
    
    # Validate that order has items
    if not order.items.exists():
        messages.error(request, 'Cannot submit an order without items.')
        return redirect(get_business_url(request, 'suppliers:purchase_order_detail', pk=pk))
    
    # Update status to pending
    order.status = 'pending'
    order.save()
    
    messages.success(request, f'Purchase Order {order.po_number} submitted for approval!')
    return redirect(get_business_url(request, 'suppliers:purchase_order_detail', pk=pk))

@login_required
@business_required
@employee_required(['owner', 'manager'])
@require_http_methods(["POST"])
def cancel_purchase_order(request, pk):
    """Cancel purchase order"""
    order = get_object_or_404(PurchaseOrder, pk=pk)
    
    if order.status not in ['draft', 'pending', 'approved']:
        messages.error(request, 'Cannot cancel an order that has been sent to supplier.')
        return redirect(get_business_url(request, 'suppliers:purchase_order_detail', pk=pk))
    
    order.status = 'cancelled'
    order.save()
    
    messages.success(request, f'Purchase Order {order.po_number} has been cancelled.')
    return redirect(get_business_url(request, 'suppliers:purchase_order_detail', pk=pk))

@login_required
@business_required
@employee_required(['owner', 'manager', 'supervisor'])
@require_http_methods(["POST"])
def acknowledge_purchase_order(request, pk):
    """Mark purchase order as acknowledged by supplier"""
    order = get_object_or_404(PurchaseOrder, pk=pk)
    
    if order.status != 'sent':
        messages.error(request, 'Only sent orders can be acknowledged.')
        return redirect(get_business_url(request, 'suppliers:purchase_order_detail', pk=pk))
    
    order.acknowledge_receipt()
    messages.success(request, f'Purchase Order {order.po_number} marked as acknowledged by supplier!')
    
    return redirect(get_business_url(request, 'suppliers:purchase_order_detail', pk=pk))

@login_required
@business_required
@employee_required(['owner', 'manager', 'supervisor'])
def purchase_order_status_update(request, pk):
    """Generic status update view with validation"""
    order = get_object_or_404(PurchaseOrder, pk=pk)
    new_status = request.POST.get('status')
    
    if not new_status:
        messages.error(request, 'No status provided.')
        return redirect(get_business_url(request, 'suppliers:purchase_order_detail', pk=pk))
    
    # Define valid status transitions
    valid_transitions = {
        'draft': ['pending', 'cancelled'],
        'pending': ['approved', 'cancelled', 'draft'],
        'approved': ['sent', 'cancelled'],
        'sent': ['acknowledged', 'cancelled'],
        'acknowledged': ['partially_received', 'completed', 'cancelled'],
        'partially_received': ['completed', 'cancelled'],
        'completed': [],
        'cancelled': [],
        'on_hold': ['pending', 'cancelled'],
    }
    
    if new_status not in valid_transitions.get(order.status, []):
        messages.error(request, f'Invalid status transition from {order.get_status_display()} to {new_status}.')
        return redirect(get_business_url(request, 'suppliers:purchase_order_detail', pk=pk))
    
    # Perform status-specific actions
    old_status = order.status
    order.status = new_status
    
    if new_status == 'approved' and hasattr(request.user, 'employee_profile'):
        order.approved_by = request.user.employee_profile
        order.approved_at = timezone.now()
    
    order.save()
    
    # Status change notifications
    status_messages = {
        'pending': f'Purchase Order {order.po_number} submitted for approval.',
        'approved': f'Purchase Order {order.po_number} has been approved.',
        'sent': f'Purchase Order {order.po_number} has been sent to supplier.',
        'acknowledged': f'Purchase Order {order.po_number} acknowledged by supplier.',
        'completed': f'Purchase Order {order.po_number} has been completed.',
        'cancelled': f'Purchase Order {order.po_number} has been cancelled.',
        'on_hold': f'Purchase Order {order.po_number} has been put on hold.',
    }
    
    message = status_messages.get(new_status, f'Purchase Order {order.po_number} status updated to {order.get_status_display()}.')
    messages.success(request, message)
    
    return redirect(get_business_url(request, 'suppliers:purchase_order_detail', pk=pk))

# Enhanced PurchaseOrderDetailView with status-based context
@method_decorator([login_required, business_required, employee_required(['owner', 'manager', 'supervisor'])], name='dispatch')
class PurchaseOrderDetailView(DetailView):
    """Purchase order detail view with status-based actions"""
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
        
        # Status-based actions
        context['can_edit'] = order.status in ['draft', 'pending']
        context['can_approve'] = (
            order.status == 'pending' and 
            self.request.user.has_perm('suppliers.can_approve_purchase_orders')
        )
        context['can_send'] = order.status == 'approved'
        context['can_acknowledge'] = order.status == 'sent'
        context['can_receive'] = order.status in ['sent', 'acknowledged', 'partially_received']
        context['can_cancel'] = order.status in ['draft', 'pending', 'approved']
        context['can_create_invoice'] = order.status == 'completed'
        
        # Available status transitions
        context['available_statuses'] = self.get_available_statuses(order.status)
        
        # Print URLs
        context['print_url'] = get_business_url(self.request, 'suppliers:purchase_order_print', pk=order.pk)
        context['pdf_url'] = get_business_url(self.request, 'suppliers:purchase_order_pdf', pk=order.pk)
        
        # URLs
        context['urls'] = get_supplier_urls(self.request)
        
        return context
    
    def get_available_statuses(self, current_status):
        """Get available status transitions for current status"""
        transitions = {
            'draft': [
                ('pending', 'Submit for Approval', 'warning'),
                ('cancelled', 'Cancel Order', 'danger'),
            ],
            'pending': [
                ('approved', 'Approve Order', 'success'),
                ('draft', 'Return to Draft', 'secondary'),
                ('cancelled', 'Cancel Order', 'danger'),
            ],
            'approved': [
                ('sent', 'Send to Supplier', 'primary'),
                ('cancelled', 'Cancel Order', 'danger'),
            ],
            'sent': [
                ('acknowledged', 'Mark as Acknowledged', 'info'),
                ('cancelled', 'Cancel Order', 'danger'),
            ],
            'acknowledged': [
                ('partially_received', 'Mark Partial Receipt', 'warning'),
                ('completed', 'Mark as Completed', 'success'),
                ('cancelled', 'Cancel Order', 'danger'),
            ],
            'partially_received': [
                ('completed', 'Mark as Completed', 'success'),
                ('cancelled', 'Cancel Order', 'danger'),
            ],
            'on_hold': [
                ('pending', 'Resume Order', 'warning'),
                ('cancelled', 'Cancel Order', 'danger'),
            ],
        }
        
        return transitions.get(current_status, [])

# Add email notification function (optional)
def send_purchase_order_notification(order, action, user):
    """Send email notifications for purchase order actions"""
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.conf import settings
    
    # Define notification settings
    notifications = {
        'submitted': {
            'subject': f'Purchase Order {order.po_number} - Approval Required',
            'template': 'suppliers/emails/po_submitted.html',
            'recipients': ['manager@company.com'],  # Replace with actual manager emails
        },
        'approved': {
            'subject': f'Purchase Order {order.po_number} - Approved',
            'template': 'suppliers/emails/po_approved.html',
            'recipients': [order.requested_by.user.email] if order.requested_by else [],
        },
        'sent': {
            'subject': f'Purchase Order {order.po_number} - New Order',
            'template': 'suppliers/emails/po_sent.html',
            'recipients': [order.supplier.email] if order.supplier.email else [],
        },
    }
    
    if action in notifications:
        notification = notifications[action]
        
        try:
            html_message = render_to_string(notification['template'], {
                'order': order,
                'user': user,
                'company': 'Your Company Name',  # Replace with your company name
            })
            
            send_mail(
                subject=notification['subject'],
                message='',  # Plain text version
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=notification['recipients'],
                fail_silently=True,
            )
        except Exception as e:
            # Log the error but don't fail the request
            print(f"Failed to send notification: {e}")