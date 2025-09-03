from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    # Reports interface
    path('', views.ReportsView.as_view(), name='reports'),
    
    # Download functionality
    path('download/<str:report_type>/', views.ReportDownloadView.as_view(), name='download'),
]