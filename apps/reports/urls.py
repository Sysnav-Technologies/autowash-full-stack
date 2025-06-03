from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    # Dashboard
    path('', views.ReportsDashboardView.as_view(), name='dashboard'),
    path('analytics/', views.analytics_dashboard, name='analytics_dashboard'),
    path('metrics/', views.business_metrics_view, name='business_metrics'),
    
    # Report Templates
    path('templates/', views.ReportTemplateListView.as_view(), name='template_list'),
    path('templates/create/', views.ReportTemplateCreateView.as_view(), name='template_create'),
    path('templates/<int:pk>/edit/', views.ReportTemplateUpdateView.as_view(), name='template_edit'),
    path('templates/<int:pk>/delete/', views.ReportTemplateDeleteView.as_view(), name='template_delete'),
    
    # Report Generation
    path('templates/<int:template_id>/generate/', views.generate_report, name='generate_report'),
    path('generated/', views.GeneratedReportListView.as_view(), name='generated_list'),
    path('generated/<uuid:report_id>/', views.report_detail, name='report_detail'),
    path('generated/<uuid:report_id>/export/<str:format_type>/', views.export_report, name='export_report'),
    
    # Dashboards
    path('dashboards/', views.DashboardListView.as_view(), name='dashboard_list'),
    path('dashboards/create/', views.DashboardCreateView.as_view(), name='dashboard_create'),
    path('dashboards/<int:dashboard_id>/view/', views.view_dashboard, name='dashboard_view'),
    
    # Widgets
    path('widgets/', views.ReportWidgetListView.as_view(), name='widget_list'),
    path('widgets/create/', views.ReportWidgetCreateView.as_view(), name='widget_create'),
    path('widgets/<int:widget_id>/data/', views.widget_data_api, name='widget_data_api'),
    
    # KPIs
    path('kpis/', views.KPIListView.as_view(), name='kpi_list'),
    path('kpis/create/', views.KPICreateView.as_view(), name='kpi_create'),
    path('kpis/<int:kpi_id>/update/', views.update_kpi, name='kpi_update'),
    
    # Report Schedules
    path('schedules/', views.report_schedule_list, name='schedule_list'),
    path('schedules/create/', views.create_report_schedule, name='schedule_create'),
]