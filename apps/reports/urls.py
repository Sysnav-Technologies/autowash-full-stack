from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    # Reports interface with export functionality
    path('', views.ReportsView.as_view(), name='reports'),
]