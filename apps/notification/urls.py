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
    path('api/', views.check_notifications_api, name='api_default'),
    path('api/get/', views.get_notifications_api, name='api_get'),
    path('api/check/', views.check_notifications_api, name='api_check'),
    path('api/test/', views.test_notification, name='api_test'),
    path('api/mark-all-read/', views.mark_all_read, name='api_mark_all_read'),
    path('api/archive-old/', views.archive_old_notifications, name='api_archive_old'),
    path('api/send/', views.send_notification_api, name='api_send'),
    path('api/<int:pk>/read/', views.mark_notification_read, name='api_mark_read'),
    path('api/<int:pk>/unread/', views.mark_notification_unread, name='api_mark_unread'),
    path('api/<int:pk>/archive/', views.archive_notification, name='api_archive'),
    path('api/bulk/mark-read/', views.bulk_mark_read, name='api_bulk_mark_read'),
    path('api/bulk/archive/', views.bulk_archive, name='api_bulk_archive'),
    path('api/bulk/delete/', views.bulk_delete, name='api_bulk_delete'),
]