from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.serializers.json import DjangoJSONEncoder
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
import json
import uuid

from apps.core.decorators import business_required, employee_required, manager_required
from .models import (
    ReportTemplate, GeneratedReport, Dashboard, ReportWidget, 
    BusinessMetrics, ReportSchedule, ReportExport, AnalyticsEvent, KPI
)
from .forms import (
    ReportTemplateForm, DashboardForm, ReportWidgetForm, 
    ReportScheduleForm, KPIForm, ReportFilterForm
)
from .utils import ReportGenerator, DashboardDataProvider

def get_reports_urls(request):
    """Generate all reports URLs for templates with tenant slug."""
    tenant_slug = request.tenant.slug
    base_url = f"/business/{tenant_slug}/reports"
    
    return {
        # Main URLs
        'dashboard': f"{base_url}/",
        'list': f"{base_url}/list/",
        'create': f"{base_url}/create/",
        'detail': f"{base_url}/{{}}/" ,  # Use string formatting in template
        'edit': f"{base_url}/{{}}/edit/",
        'delete': f"{base_url}/{{}}/delete/",
        'generate': f"{base_url}/{{}}/generate/",
        'download': f"{base_url}/{{}}/download/",
        
        # Template URLs
        'template_list': f"{base_url}/templates/",
        'template_create': f"{base_url}/templates/create/",
        'template_edit': f"{base_url}/templates/{{}}/edit/",
        'template_delete': f"{base_url}/templates/{{}}/delete/",
        
        # Dashboard URLs
        'dashboard_create': f"{base_url}/dashboards/create/",
        'dashboard_edit': f"{base_url}/dashboards/{{}}/edit/",
        'dashboard_view': f"{base_url}/dashboards/{{}}/",
        
        # Widget URLs
        'widget_create': f"{base_url}/widgets/create/",
        'widget_edit': f"{base_url}/widgets/{{}}/edit/",
        'widget_delete': f"{base_url}/widgets/{{}}/delete/",
        
        # Analytics URLs
        'analytics': f"{base_url}/analytics/",
        'analytics_events': f"{base_url}/analytics/events/",
        'kpi_list': f"{base_url}/kpi/",
        'kpi_create': f"{base_url}/kpi/create/",
        
        # Export URLs
        'export_csv': f"{base_url}/export/csv/",
        'export_pdf': f"{base_url}/export/pdf/",
        'export_excel': f"{base_url}/export/excel/",
        
        # Schedule URLs
        'schedule_list': f"{base_url}/schedules/",
        'schedule_create': f"{base_url}/schedules/create/",
        'schedule_edit': f"{base_url}/schedules/{{}}/edit/",
        
        # Ajax URLs
        'report_data': f"{base_url}/ajax/{{}}/data/",
        'widget_data': f"{base_url}/ajax/widgets/{{}}/data/",
        'preview_report': f"{base_url}/ajax/preview/",
        
        # Navigation
        'businesses_dashboard': f"/business/{tenant_slug}/dashboard/",
    }

@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class ReportsDashboardView(ListView):
    """Main reports dashboard"""
    model = ReportTemplate
    template_name = 'reports/dashboard.html'
    context_object_name = 'templates'
    
    def get_queryset(self):
        return ReportTemplate.objects.filter(is_active=True).order_by('report_type', 'name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get recent generated reports
        context['recent_reports'] = GeneratedReport.objects.filter(
            status='completed'
        ).order_by('-created_at')[:5]
        
        # Get dashboard metrics
        today = timezone.now().date()
        context['metrics'] = {
            'total_templates': ReportTemplate.objects.filter(is_active=True).count(),
            'generated_today': GeneratedReport.objects.filter(
                created_at__date=today
            ).count(),
            'scheduled_reports': ReportSchedule.objects.filter(is_active=True).count(),
            'total_kpis': KPI.objects.filter(is_active=True).count(),
        }
        
        # Get KPI summary
        context['kpis'] = KPI.objects.filter(is_active=True)[:4]
        
        # Get chart data for dashboard
        context['chart_data'] = self.get_dashboard_chart_data()
        
        return context
    
    def get_dashboard_chart_data(self):
        """Get chart data for dashboard widgets"""
        # Revenue chart data (last 7 days)
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=6)
        
        revenue_data = []
        for i in range(7):
            date_obj = start_date + timedelta(days=i)
            try:
                metrics = BusinessMetrics.objects.get(date=date_obj)
                revenue = float(metrics.total_revenue)
            except BusinessMetrics.DoesNotExist:
                revenue = 0
            
            revenue_data.append({
                'date': date_obj.strftime('%Y-%m-%d'),
                'revenue': revenue
            })
        
        return {
            'revenue_chart': revenue_data,
        }

@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class ReportTemplateListView(ListView):
    """List all report templates"""
    model = ReportTemplate
    template_name = 'reports/template_list.html'
    context_object_name = 'templates'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = ReportTemplate.objects.all()
        
        # Filter by type
        report_type = self.request.GET.get('type')
        if report_type:
            queryset = queryset.filter(report_type=report_type)
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(description__icontains=search)
            )
        
        return queryset.order_by('report_type', 'name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['report_types'] = ReportTemplate.REPORT_TYPES
        context['current_type'] = self.request.GET.get('type', '')
        context['current_search'] = self.request.GET.get('search', '')
        return context

@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class ReportTemplateCreateView(CreateView):
    """Create new report template"""
    model = ReportTemplate
    form_class = ReportTemplateForm
    template_name = 'reports/template_form.html'
    success_url = reverse_lazy('reports:template_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Report template created successfully!')
        return super().form_valid(form)

@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class ReportTemplateUpdateView(UpdateView):
    """Update report template"""
    model = ReportTemplate
    form_class = ReportTemplateForm
    template_name = 'reports/template_form.html'
    success_url = reverse_lazy('reports:template_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Report template updated successfully!')
        return super().form_valid(form)

@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class ReportTemplateDeleteView(DeleteView):
    """Delete report template"""
    model = ReportTemplate
    template_name = 'reports/template_confirm_delete.html'
    success_url = reverse_lazy('reports:template_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Report template deleted successfully!')
        return super().delete(request, *args, **kwargs)

@login_required
@business_required
@employee_required(['owner', 'manager', 'supervisor'])
def generate_report(request, template_id):
    """Generate a report from template"""
    template = get_object_or_404(ReportTemplate, id=template_id)
    
    if request.method == 'POST':
        form = ReportFilterForm(request.POST, template=template)
        if form.is_valid():
            # Create generated report instance
            report = GeneratedReport.objects.create(
                template=template,
                date_from=form.cleaned_data['date_from'],
                date_to=form.cleaned_data['date_to'],
                generated_by=request.employee,
                status='generating'
            )
            
            try:
                # Generate report data
                generator = ReportGenerator(template, report)
                generator.generate()
                
                messages.success(request, 'Report generated successfully!')
                return redirect('reports:report_detail', report.report_id)
                
            except Exception as e:
                report.mark_failed(str(e))
                messages.error(request, f'Failed to generate report: {str(e)}')
                return redirect('reports:template_list')
    else:
        form = ReportFilterForm(template=template)
    
    return render(request, 'reports/generate_report.html', {
        'template': template,
        'form': form
    })

@login_required
@business_required
@employee_required(['owner', 'manager', 'supervisor'])
def report_detail(request, report_id):
    """View generated report details"""
    report = get_object_or_404(GeneratedReport, report_id=report_id)
    
    # Check if user can access this report
    if not report.template.can_access(request.user):
        raise Http404("Report not found")
    
    context = {
        'report': report,
        'charts_data': json.dumps(report.charts_data, cls=DjangoJSONEncoder) if report.charts_data else '{}',
    }
    
    return render(request, 'reports/report_detail.html', context)

@login_required
@business_required
@employee_required(['owner', 'manager', 'supervisor'])
def export_report(request, report_id, format_type):
    """Export report in specified format"""
    report = get_object_or_404(GeneratedReport, report_id=report_id)
    
    if not report.template.can_access(request.user):
        raise Http404("Report not found")
    
    # Check if export already exists
    export_obj, created = ReportExport.objects.get_or_create(
        report=report,
        format=format_type,
        defaults={'exported_by': request.employee}
    )
    
    if created:
        # Generate export file
        from .utils import ReportExporter
        exporter = ReportExporter(report)
        file_path = exporter.export(format_type)
        export_obj.file_path = file_path
        export_obj.save()
    
    # Record download
    export_obj.record_download()
    
    # Serve file
    response = HttpResponse(content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{report.template.name}_{report.date_from}_{report.date_to}.{format_type}"'
    
    with open(export_obj.file_path, 'rb') as f:
        response.write(f.read())
    
    return response

@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class GeneratedReportListView(ListView):
    """List all generated reports"""
    model = GeneratedReport
    template_name = 'reports/generated_list.html'
    context_object_name = 'reports'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = GeneratedReport.objects.all()
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by template
        template_id = self.request.GET.get('template')
        if template_id:
            queryset = queryset.filter(template_id=template_id)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['templates'] = ReportTemplate.objects.filter(is_active=True)
        context['statuses'] = GeneratedReport.STATUS_CHOICES
        return context

@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class DashboardListView(ListView):
    """List all dashboards"""
    model = Dashboard
    template_name = 'reports/dashboard_list.html'
    context_object_name = 'dashboards'
    
    def get_queryset(self):
        return Dashboard.objects.filter(is_active=True).order_by('role', 'name')

@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class DashboardCreateView(CreateView):
    """Create new dashboard"""
    model = Dashboard
    form_class = DashboardForm
    template_name = 'reports/dashboard_form.html'
    success_url = reverse_lazy('reports:dashboard_list')

@login_required
@business_required
@employee_required(['owner', 'manager', 'supervisor', 'attendant'])
def view_dashboard(request, dashboard_id):
    """View specific dashboard with widgets"""
    dashboard = get_object_or_404(Dashboard, id=dashboard_id, is_active=True)
    
    # Get widgets for this dashboard
    widgets = ReportWidget.objects.filter(
        id__in=dashboard.widgets,
        is_active=True
    )
    
    # Get widget data
    provider = DashboardDataProvider()
    widget_data = {}
    
    for widget in widgets:
        cached_data = widget.get_cached_data()
        if cached_data:
            widget_data[widget.id] = cached_data
        else:
            # Generate fresh data
            data = provider.get_widget_data(widget)
            widget.update_cache(data)
            widget_data[widget.id] = data
    
    context = {
        'dashboard': dashboard,
        'widgets': widgets,
        'widget_data': json.dumps(widget_data, cls=DjangoJSONEncoder),
    }
    
    return render(request, 'reports/dashboard_view.html', context)

@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class ReportWidgetListView(ListView):
    """List all report widgets"""
    model = ReportWidget
    template_name = 'reports/widget_list.html'
    context_object_name = 'widgets'
    
    def get_queryset(self):
        return ReportWidget.objects.filter(is_active=True).order_by('widget_type', 'name')

@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class ReportWidgetCreateView(CreateView):
    """Create new report widget"""
    model = ReportWidget
    form_class = ReportWidgetForm
    template_name = 'reports/widget_form.html'
    success_url = reverse_lazy('reports:widget_list')

@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class KPIListView(ListView):
    """List all KPIs"""
    model = KPI
    template_name = 'reports/kpi_list.html'
    context_object_name = 'kpis'
    
    def get_queryset(self):
        return KPI.objects.filter(is_active=True).order_by('kpi_type', 'name')

@method_decorator([login_required, business_required, employee_required(['owner', 'manager'])], name='dispatch')
class KPICreateView(CreateView):
    """Create new KPI"""
    model = KPI
    form_class = KPIForm
    template_name = 'reports/kpi_form.html'
    success_url = reverse_lazy('reports:kpi_list')

@login_required
@business_required
@employee_required(['owner', 'manager'])
def analytics_dashboard(request):
    """Analytics dashboard with various metrics"""
    # Get date range
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    # Get analytics events
    events = AnalyticsEvent.objects.filter(
        created_at__date__gte=start_date
    ).values('event_type').annotate(count=Count('id'))
    
    # Get business metrics
    metrics = BusinessMetrics.objects.filter(
        date__gte=start_date
    ).order_by('date')
    
    context = {
        'events': events,
        'metrics': metrics,
        'date_range': f"{start_date} to {end_date}",
    }
    
    return render(request, 'reports/analytics_dashboard.html', context)

@login_required
@business_required
@employee_required(['owner', 'manager'])
@require_http_methods(["POST"])
def update_kpi(request, kpi_id):
    """Update KPI current value"""
    kpi = get_object_or_404(KPI, id=kpi_id)
    
    try:
        new_value = float(request.POST.get('value', 0))
        kpi.current_value = new_value
        kpi.last_calculated = timezone.now()
        kpi.save()
        
        return JsonResponse({
            'success': True,
            'achievement': kpi.achievement_percentage,
            'status': kpi.status,
            'formatted_value': kpi.formatted_value
        })
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'Invalid value'})

@login_required
@business_required
@employee_required(['owner', 'manager'])
def report_schedule_list(request):
    """List all report schedules"""
    schedules = ReportSchedule.objects.all().order_by('-created_at')
    
    return render(request, 'reports/schedule_list.html', {
        'schedules': schedules
    })

@login_required
@business_required
@employee_required(['owner', 'manager'])
def create_report_schedule(request):
    """Create new report schedule"""
    if request.method == 'POST':
        form = ReportScheduleForm(request.POST)
        if form.is_valid():
            schedule = form.save()
            schedule.calculate_next_generation()
            messages.success(request, 'Report schedule created successfully!')
            return redirect('reports:schedule_list')
    else:
        form = ReportScheduleForm()
    
    return render(request, 'reports/schedule_form.html', {
        'form': form,
        'title': 'Create Report Schedule'
    })

@login_required
@business_required
@require_http_methods(["GET"])
def widget_data_api(request, widget_id):
    """API endpoint to get widget data"""
    widget = get_object_or_404(ReportWidget, id=widget_id, is_active=True)
    
    # Check cache first
    cached_data = widget.get_cached_data()
    if cached_data:
        return JsonResponse(cached_data)
    
    # Generate fresh data
    provider = DashboardDataProvider()
    data = provider.get_widget_data(widget)
    widget.update_cache(data)
    
    return JsonResponse(data)

@login_required
@business_required
@employee_required(['owner', 'manager'])
def business_metrics_view(request):
    """View business metrics"""
    # Get current month's metrics
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    
    metrics = BusinessMetrics.objects.filter(
        date__gte=start_of_month
    ).order_by('date')
    
    # Calculate totals
    totals = metrics.aggregate(
        total_revenue=Sum('total_revenue'),
        total_customers=Sum('total_customers_served'),
        total_services=Sum('total_services'),
        avg_satisfaction=Avg('customer_satisfaction')
    )
    
    context = {
        'metrics': metrics,
        'totals': totals,
        'current_month': start_of_month.strftime('%B %Y'),
    }
    
    return render(request, 'reports/business_metrics.html', context)