# Autowash Multi-Tenant Django Application Setup

## Prerequisites

- Python 3.8+
- PostgreSQL 12+
- Redis 6+
- Git

## 1. Clone and Setup Project

```bash
# Clone the repository
git clone <your-repo-url>
cd autowash

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/Mac:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## 2. Database Setup

```bash
# Create PostgreSQL database
sudo -u postgres createdb autowash_db

# Create database user (optional)
sudo -u postgres createuser --interactive autowash_user
```

## 3. Redis Setup

```bash
# Install Redis (Ubuntu/Debian)
sudo apt update
sudo apt install redis-server

# Start Redis
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Test Redis connection
redis-cli ping
```

## 4. Environment Configuration

Create a `.env` file in your project root with the provided environment variables. Update the following:

- `SECRET_KEY`: Generate a new secret key
- `DB_PASSWORD`: Your PostgreSQL password
- `EMAIL_HOST_USER` & `EMAIL_HOST_PASSWORD`: Your email credentials
- `SMS_API_KEY`: Your SMS service API key
- `MPESA_*`: Your M-Pesa credentials (for production)

## 5. Database Migration

```bash
# Create and run migrations for public schema
python manage.py makemigrations
python manage.py migrate_schemas --shared

# Create superuser
python manage.py createsuperuser
```

## 6. Create First Business (Tenant)

```bash
# Run the development server
python manage.py runserver

# Access the application at http://localhost:8000
# Register a new business through the web interface
```

## 7. Setup Celery (Background Tasks)

Open a new terminal and run:

```bash
# Activate virtual environment
source venv/bin/activate

# Start Celery worker
celery -A autowash worker --loglevel=info

# In another terminal, start Celery Beat (for scheduled tasks)
celery -A autowash beat --loglevel=info
```

## 8. Directory Structure Setup

Create necessary directories:

```bash
mkdir -p logs
mkdir -p media/business_logos
mkdir -p media/employee_photos
mkdir -p media/customer_photos
mkdir -p media/verification/licenses
mkdir -p media/verification/tax
mkdir -p media/verification/ids
mkdir -p staticfiles
```

## 9. Collect Static Files

```bash
python manage.py collectstatic --noinput
```

## 10. Testing Tenant Access

After creating a business:

1. **Public Schema**: Access at `http://localhost:8000`
2. **Tenant Schema**: Access at `http://yourbusiness.localhost:8000`

## Common Commands

### Development Server
```bash
python manage.py runserver
```

### Create Migrations
```bash
python manage.py makemigrations
python manage.py makemigrations --empty appname  # Empty migration
```

### Apply Migrations
```bash
# Shared apps only
python manage.py migrate_schemas --shared

# Tenant apps only  
python manage.py migrate_schemas --tenant

# All schemas
python manage.py migrate_schemas
```

### Create Tenant
```bash
python manage.py create_tenant
```

### List Tenants
```bash
python manage.py list_tenants
```

### Django Shell
```bash
python manage.py shell
```

### Tenant-specific Shell
```bash
python manage.py tenant_command shell --schema=yourbusiness
```

## Production Deployment Notes

1. **Environment Variables**: Set `DEBUG=False` and update `ALLOWED_HOSTS`
2. **Static Files**: Use a web server (Nginx) to serve static files
3. **Database**: Use a managed PostgreSQL service
4. **Redis**: Use a managed Redis service
5. **Celery**: Use a process manager like Supervisor
6. **SSL**: Enable HTTPS and update security settings
7. **Domain**: Configure proper domain and subdomain routing

## Troubleshooting

### Common Issues

1. **Redis Connection Error**: Ensure Redis is running
2. **Database Connection Error**: Check PostgreSQL credentials
3. **Tenant Not Found**: Ensure domain is properly configured
4. **Static Files Not Loading**: Run `collectstatic` command
5. **Migration Errors**: Check for circular dependencies in models

### Logs Location
- Application logs: `logs/django.log`
- Error logs: Check console output

### Reset Database
```bash
# Drop and recreate database (WARNING: This will delete all data)
sudo -u postgres dropdb autowash_db
sudo -u postgres createdb autowash_db
python manage.py migrate_schemas --shared
```

## Additional Configuration

### Email Testing (Development)
For testing emails locally, you can use Django's console backend:
```python
# In settings.py (development only)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
```

### SMS Testing
Use the sandbox credentials provided by your SMS service provider.

### M-Pesa Testing
Use Safaricom's sandbox environment for testing payments.