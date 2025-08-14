from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    # Main dashboard
    path('', views.ReportsDashboardView.as_view(), name='dashboard'),
    
    # Analytics dashboard
    path('analytics/', views.analytics_dashboard, name='analytics_dashboard'),
    
    # Report generation
    path('generate/', views.generate_business_report, name='generate_report'),
    path('list/', views.reports_list, name='reports_list'),
    path('detail/<uuid:report_id>/', views.report_detail, name='report_detail'),
    path('export/<uuid:report_id>/<str:format_type>/', views.export_report, name='export_report'),
]