from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    # Dashboard and Overview
    path('', views.notification_dashboard, name='dashboard'),
    path('list/', views.NotificationListView.as_view(), name='list'),
    
    # Individual Notifications
    path('<int:pk>/', views.NotificationDetailView.as_view(), name='detail'),
    path('<int:pk>/redirect/', views.notification_redirect, name='redirect'),
    path('<int:pk>/read/', views.mark_notification_read, name='mark_read'),
    path('<int:pk>/unread/', views.mark_notification_unread, name='mark_unread'),
    path('<int:pk>/archive/', views.archive_notification, name='archive'),
    
    # Bulk Actions
    path('bulk-action/', views.bulk_notification_action, name='bulk_action'),
    path('mark-all-read/', views.mark_all_read, name='mark_all_read'),
    
    # User Preferences
    path('preferences/', views.NotificationPreferenceView.as_view(), name='preferences'),
    path('settings/', views.notification_settings, name='settings'),
    
    # API Endpoints
    path('api/get/', views.get_notifications_api, name='api_get'),
    path('api/check/', views.check_notifications_api, name='api_check'),
    path('api/test/', views.test_notification, name='api_test'),
    
    # Management (Admin/Manager only)
    path('templates/', views.NotificationTemplateListView.as_view(), name='template_list'),
    path('templates/create/', views.NotificationTemplateCreateView.as_view(), name='template_create'),
    path('templates/<int:pk>/edit/', views.NotificationTemplateUpdateView.as_view(), name='template_edit'),
    
    # Analytics and Reporting
    path('analytics/', views.notification_analytics, name='analytics'),
    
    # Bulk Notifications
    path('send-bulk/', views.send_bulk_notification, name='send_bulk'),
]