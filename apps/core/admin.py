"""
Django Core Admin - Only Global Platform Functionalities
For business management, use /system-admin/
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

class SuperUserAdmin(BaseUserAdmin):
    """User admin for platform super admin"""
    
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_superuser', 'date_joined')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'date_joined')
    search_fields = ('username', 'first_name', 'last_name', 'email')

admin.site.unregister(User)
admin.site.register(User, SuperUserAdmin)

admin.site.site_header = 'Autowash Global Administration'
admin.site.site_title = 'Global Admin'
admin.site.index_title = 'Global Platform Management'
