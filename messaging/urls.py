from django.urls import path
from . import views

app_name = 'messaging'

urlpatterns = [
    # SMS Management URLs
    path('', views.SMSListView.as_view(), name='sms_list'),
    path('send/', views.SendSMSView.as_view(), name='send_sms'),
    path('bulk/', views.BulkSMSView.as_view(), name='bulk_sms'),
    path('templates/', views.SMSTemplateListView.as_view(), name='template_list'),
    path('templates/create/', views.CreateTemplateView.as_view(), name='create_template'),
    path('templates/<int:pk>/edit/', views.EditTemplateView.as_view(), name='edit_template'),
    path('templates/<int:pk>/delete/', views.DeleteTemplateView.as_view(), name='delete_template'),
    
    # SMS Settings URLs
    path('settings/', views.SMSSettingsView.as_view(), name='sms_settings'),
    path('settings/test/', views.TestSMSView.as_view(), name='test_sms'),
    
    # API URLs for AJAX calls
    path('api/message/<int:pk>/status/', views.MessageStatusAPIView.as_view(), name='message_status_api'),
    path('api/statistics/', views.SMSStatisticsAPIView.as_view(), name='sms_statistics_api'),
    
    # Webhook URLs for SMS delivery status updates
    path('webhook/host-pinnacle/', views.HostPinnacleWebhookView.as_view(), name='host_pinnacle_webhook'),
    path('webhook/africas-talking/', views.AfricasTalkingWebhookView.as_view(), name='africas_talking_webhook'),
    path('webhook/twilio/', views.TwilioWebhookView.as_view(), name='twilio_webhook'),
    path('webhook/general/<str:provider_type>/', views.GeneralSMSWebhookView.as_view(), name='general_sms_webhook'),
]