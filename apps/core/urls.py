from .views import health_check
from django.urls import path

name = 'core'
urlpatterns = [
    path('health/', health_check, name='health_check'),

]