# MySQL Multi-Tenant Migration Guide

## Overview

This guide covers the migration from django-tenants (PostgreSQL) to a custom MySQL multi-tenant architecture using database-per-tenant approach.

## Architecture Changes

### Before (django-tenants + PostgreSQL)
- Single PostgreSQL database with schemas
- Schema-based tenant isolation
- Built-in tenant routing

### After (Custom MySQL Multi-Tenant)
- Separate MySQL database per tenant
- Database-level tenant isolation
- Custom routing middleware

## Installation Steps

### 1. Install Dependencies

```bash
pip install mysqlclient django-mysql
pip uninstall psycopg2-binary django-tenants django-tenant-schemas
```

### 2. Update Environment Variables

Create/update your `.env` file:

```env
# MySQL Main Database
DB_NAME=autowash_main
DB_USER=your_mysql_user
DB_PASSWORD=your_mysql_password
DB_HOST=localhost
DB_PORT=3306

# Or use DATABASE_URL (will be converted to MySQL)
DATABASE_URL=mysql://user:password@host:port/autowash_main

# Domain Configuration
MAIN_DOMAIN=autowash.co.ke
```

### 3. Run Migration Commands

```bash
# Create and run migrations for main database
python manage.py makemigrations
python manage.py migrate

# Migrate from old django-tenants data (if applicable)
python manage.py migrate_from_django_tenants --backup-file=tenant_backup.json

# Create a new tenant
python manage.py create_tenant my-business \
    --name "My Car Wash Business" \
    --owner-id 1 \
    --subdomain my-business

# Migrate tenant databases
python manage.py migrate_tenants
```

### 4. Update URL Configuration

Update `autowash/urls.py` to handle both public and tenant URLs:

```python
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Public URLs (no tenant required)
urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('apps.accounts.urls')),
    path('api/public/', include('apps.api.public_urls')),
    path('', include('apps.core.public_urls')),
]

# Tenant URLs (require tenant context)
tenant_patterns = [
    path('', include('apps.businesses.urls')),
    path('employees/', include('apps.employees.urls')),
    path('customers/', include('apps.customers.urls')),
    path('services/', include('apps.services.urls')),
    path('inventory/', include('apps.inventory.urls')),
    path('reports/', include('apps.reports.urls')),
    path('payments/', include('apps.payments.urls')),
    path('expenses/', include('apps.expenses.urls')),
]

# Add tenant patterns to main patterns
urlpatterns.extend(tenant_patterns)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

## New Tenant Model Features

### Database-per-Tenant
Each tenant gets its own MySQL database with full isolation:

```python
from apps.core.tenant_models import Tenant

# Create tenant programmatically
tenant = Tenant.objects.create(
    name="My Business",
    slug="my-business",
    subdomain="my-business",
    owner=user,
    database_user="my_business_user",
    database_password="secure_password"
)
```

### Multi-Access Methods

1. **Path-based**: `/business/my-business/dashboard/`
2. **Subdomain**: `my-business.autowash.co.ke`
3. **Custom domain**: `mybusiness.com`

### Tenant Context Management

```python
from apps.core.database_router import tenant_context
from apps.core.tenant_models import Tenant

# Use tenant context
tenant = Tenant.objects.get(slug='my-business')
with tenant_context(tenant):
    # All database operations will use tenant's database
    customers = Customer.objects.all()
```

## Management Commands

### Create Tenant
```bash
python manage.py create_tenant business-slug \
    --name "Business Name" \
    --owner-id 1 \
    --subdomain business-slug \
    --db-host localhost \
    --db-port 3306
```

### Migrate Tenants
```bash
# Migrate all tenants
python manage.py migrate_tenants

# Migrate specific tenant
python manage.py migrate_tenants --tenant business-slug

# Migrate specific app for all tenants
python manage.py migrate_tenants --app employees
```

### Backup and Migration
```bash
# Backup old tenant data
python manage.py migrate_from_django_tenants --dry-run

# Perform migration
python manage.py migrate_from_django_tenants
```

## Production Deployment

### cPanel MySQL Setup

1. **Create Main Database**
   - Database: `username_autowash_main`
   - User: `username_main`

2. **Create Tenant Databases** (as needed)
   - Database: `username_autowash_tenant1`
   - User: `username_tenant1`

3. **Update Environment Variables**
```env
DB_NAME=username_autowash_main
DB_USER=username_main
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=3306
```

### Database Permissions

Grant appropriate permissions for tenant database creation:

```sql
-- Grant user ability to create databases
GRANT CREATE ON *.* TO 'username_main'@'localhost';

-- Grant user ability to create users (if needed)
GRANT CREATE USER ON *.* TO 'username_main'@'localhost';
GRANT GRANT OPTION ON *.* TO 'username_main'@'localhost';
```

## Migration Checklist

- [ ] Install MySQL dependencies
- [ ] Update settings.py
- [ ] Create main database
- [ ] Run initial migrations
- [ ] Backup old tenant data
- [ ] Create new tenant objects
- [ ] Test tenant creation
- [ ] Update URL configurations
- [ ] Test tenant routing
- [ ] Migrate all existing tenants
- [ ] Update deployment scripts
- [ ] Test production deployment

## Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Clear Python cache
   find . -name "*.pyc" -delete
   find . -name "__pycache__" -delete
   ```

2. **Database Connection Issues**
   ```python
   # Test MySQL connection
   python manage.py shell
   >>> from django.db import connection
   >>> cursor = connection.cursor()
   >>> cursor.execute("SELECT 1")
   >>> cursor.fetchone()
   ```

3. **Tenant Database Issues**
   ```bash
   # Check tenant databases
   python manage.py shell
   >>> from apps.core.tenant_models import Tenant
   >>> tenant = Tenant.objects.first()
   >>> print(tenant.database_config)
   ```

### Performance Optimization

1. **Enable MySQL Query Cache**
2. **Use Connection Pooling**
3. **Implement Database Sharding** (for very large deployments)
4. **Cache Tenant Lookups**

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review Django and MySQL logs
3. Test with a simple tenant first
4. Verify database permissions

## Next Steps

1. Test the migration thoroughly
2. Update any custom code that relied on django-tenants
3. Implement monitoring for tenant databases
4. Set up automated backups for all tenant databases
5. Plan database maintenance procedures
