import os
from pathlib import Path
from decouple import config
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
import dj_database_url

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Security
SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-in-production')
DEBUG = config('DEBUG', default=True, cast=bool)
RENDER = config('RENDER', default=True, cast=bool)

# PRODUCTION DEBUGGING - Simple flag to enable verbose logging and relaxed security
PRODUCTION_DEBUG = config('PRODUCTION_DEBUG', default=False, cast=bool)

# SMART ALLOWED_HOSTS based on environment
if DEBUG:
    # Local development
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', '*.localhost', 'testserver']
    print("🏠 Running in LOCAL DEVELOPMENT mode")
else:
    # Production (CPanel)
    ALLOWED_HOSTS = [
        'autowash.co.ke',
        'www.autowash.co.ke', 
        '*.autowash.co.ke',
        '.autowash.co.ke',
        'autowash-3jpr.onrender.com',
        'www.autowash-3jpr.onrender.com'
    ]
    if PRODUCTION_DEBUG:
        print("🚀 Running in PRODUCTION mode with DEBUG ENABLED")
    else:
        print("🚀 Running in PRODUCTION mode")

# Multi-tenant Apps Configuration
SHARED_APPS = [
    'django_tenants',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    
    # Third party apps
    'crispy_forms',
    'crispy_bootstrap5',
    'phonenumber_field',
    'django_extensions',
    'django_filters',
    'import_export',
    'corsheaders',
    'rest_framework',
    'rest_framework.authtoken',
    'dj_rest_auth',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'django_celery_beat',
    'django_celery_results',
    'channels',
    
    # Shared apps (public schema)
    'apps.core',
    'apps.accounts',
    'apps.subscriptions',
]

TENANT_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.admin',
    
    # Tenant specific apps
    'apps.businesses',
    'apps.employees',
    'apps.customers',
    'apps.services',
    'apps.inventory',
    'apps.suppliers',
    'apps.payments',
    'apps.reports',
    'apps.expenses',
    'apps.notification',
]

INSTALLED_APPS = list(SHARED_APPS) + [app for app in TENANT_APPS if app not in SHARED_APPS]

# Tenant Configuration
TENANT_MODEL = "accounts.Business"
TENANT_DOMAIN_MODEL = "accounts.Domain"
PUBLIC_SCHEMA_URLCONF = 'autowash.urls_public'
ROOT_URLCONF = 'autowash.urls'
PUBLIC_SCHEMA_NAME = 'public'
SHOW_PUBLIC_IF_NO_TENANT_FOUND = True

# Database routing
DATABASE_ROUTERS = (
    'django_tenants.routers.TenantSyncRouter',
)

MIDDLEWARE = [
    'django_tenants.middleware.main.TenantMainMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_ratelimit.middleware.RatelimitMiddleware',
    'apps.core.middleware.BusinessContextMiddleware',
    'apps.core.middleware.TimezoneMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.business_context',
                'apps.core.context_processors.notifications_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'autowash.wsgi.application'
ASGI_APPLICATION = 'autowash.asgi.application'

# DATABASE CONFIGURATION - Always use DATABASE_URL
database_url = config('DATABASE_URL')

DATABASES = {
    'default': dj_database_url.parse(
        database_url,
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# Override engine for django-tenants
DATABASES['default']['ENGINE'] = 'django_tenants.postgresql_backend'

# Configure SSL based on environment
if 'localhost' in database_url or '127.0.0.1' in database_url:
    # Local database - disable SSL
    DATABASES['default']['OPTIONS'] = {
        'sslmode': 'disable',
        'options': '-c search_path=public'
    }
    print(f"📊 Using LOCAL PostgreSQL database via DATABASE_URL (SSL disabled)")
else:
    # External database - require SSL
    DATABASES['default']['OPTIONS'] = {
        'sslmode': 'require',
        'options': '-c search_path=public'
    }
    print(f"📊 Using EXTERNAL PostgreSQL database via DATABASE_URL (SSL required)")

# Redis & Channels
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [config('REDIS_URL', default='redis://localhost:6379/1')],
        },
    },
}

# SMART CACHE CONFIGURATION
redis_url = config('REDIS_URL', default=None)
if redis_url and redis_url != '':
    # Redis available
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': redis_url.replace('/1', '/2'),  # Use different Redis DB for cache
        }
    }
    print("💾 Using Redis cache")
else:
    # Fallback to database cache (common in CPanel)
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
            'LOCATION': 'cache_table',
        }
    }
    print("💾 Using database cache (Redis not available)")

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True

# SMART STATIC FILES CONFIGURATION WITH WHITENOISE
if DEBUG:
    # Local development
    STATIC_URL = '/static/'
    STATIC_ROOT = BASE_DIR / 'staticfiles'
    STATICFILES_DIRS = [BASE_DIR / 'static']
    
    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'
    print("📁 Using LOCAL static/media file paths")
else:
    # Production (CPanel) with WhiteNoise
    STATIC_URL = '/static/'
    STATIC_ROOT = BASE_DIR / 'public_html' / 'static'
    STATICFILES_DIRS = [BASE_DIR / 'static']
    
    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'public_html' / 'media'
    
    # WhiteNoise configuration for production
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
    
    # WhiteNoise settings
    WHITENOISE_USE_FINDERS = True
    WHITENOISE_AUTOREFRESH = True
    WHITENOISE_MTIME = None
    WHITENOISE_MAX_AGE = 31536000  # 1 year cache for static files
    
    # Serve media files through WhiteNoise (only if needed)
    # Note: For large media files, consider using a CDN instead
    WHITENOISE_MANIFEST_STRICT = False
    
    # Custom MIME types for WhiteNoise
    WHITENOISE_MIMETYPES = {
        '.js': 'application/javascript',
        '.css': 'text/css',
    }
    
    # Skip compression for these file types
    WHITENOISE_SKIP_COMPRESS_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'zip', 'gz', 'tgz', 'bz2', 'tbz', 'xz', 'br']
    
    print("📁 Using PRODUCTION (CPanel) static/media file paths with WhiteNoise")

# Create static directory if it doesn't exist (fixes the warning)
static_dir = BASE_DIR / 'static'
if not static_dir.exists():
    static_dir.mkdir(exist_ok=True)
    print(f"📁 Created static directory: {static_dir}")

# Ensure public_html directories exist in production
if not DEBUG:
    public_static = BASE_DIR / 'public_html' / 'static'
    public_media = BASE_DIR / 'public_html' / 'media'
    public_static.mkdir(parents=True, exist_ok=True)
    public_media.mkdir(parents=True, exist_ok=True)
    print(f"📁 Ensured public_html directories exist")

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Celery Configuration
CELERY_BROKER_URL = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# SMART EMAIL CONFIGURATION
if DEBUG:
    # Local development - Gmail SMTP
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
    EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
    EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
    EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
    EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
    DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@localhost')
    print("📧 Using LOCAL email configuration (Gmail SMTP)")
else:
    # Production - Domain email
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = config('EMAIL_HOST', default='mail.autowash.co.ke')
    EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
    EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
    EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='noreply@autowash.co.ke')
    EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
    DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='Autowash <noreply@autowash.co.ke>')
    print("📧 Using PRODUCTION email configuration (Domain email)")

# SMS Configuration
SMS_API_KEY = config('SMS_API_KEY', default='')
SMS_USERNAME = config('SMS_USERNAME', default='sandbox')

# SMART M-PESA CONFIGURATION
if DEBUG:
    # Sandbox for development
    MPESA_ENVIRONMENT = 'sandbox'
    MPESA_CONSUMER_KEY = config('MPESA_CONSUMER_KEY', default='')
    MPESA_CONSUMER_SECRET = config('MPESA_CONSUMER_SECRET', default='')
    MPESA_SHORTCODE = config('MPESA_SHORTCODE', default='174379')
    MPESA_PASSKEY = config('MPESA_PASSKEY', default='')
    MPESA_CALLBACK_URL = config('MPESA_CALLBACK_URL', default='http://localhost:8000/api/mpesa/callback/')
    print("💰 Using SANDBOX M-Pesa configuration")
else:
    # Production
    MPESA_ENVIRONMENT = config('MPESA_ENVIRONMENT', default='production')
    MPESA_CONSUMER_KEY = config('MPESA_CONSUMER_KEY', default='')
    MPESA_CONSUMER_SECRET = config('MPESA_CONSUMER_SECRET', default='')
    MPESA_SHORTCODE = config('MPESA_SHORTCODE', default='174379')
    MPESA_PASSKEY = config('MPESA_PASSKEY', default='')
    MPESA_CALLBACK_URL = config('MPESA_CALLBACK_URL', default='https://www.autowash.co.ke/api/mpesa/callback/')
    print("💰 Using PRODUCTION M-Pesa configuration")

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
}

# Sites Framework
SITE_ID = 1

# Authentication
LOGIN_URL = '/auth/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

# AllAuth Configuration (Updated to new format)
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True

# SMART SECURITY SETTINGS
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

if DEBUG:
    # Local development - relaxed security
    SECURE_HSTS_SECONDS = 0
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    print("🔒 Using LOCAL security settings (relaxed)")
else:
    # Production security - but relaxed if debugging
    if PRODUCTION_DEBUG:
        # Relaxed security for production debugging
        SECURE_HSTS_SECONDS = 0
        SECURE_SSL_REDIRECT = False
        SESSION_COOKIE_SECURE = False
        CSRF_COOKIE_SECURE = False
        print("🔒 Using PRODUCTION security settings (RELAXED for debugging)")
    else:
        # Strict production security
        SECURE_HSTS_SECONDS = 31536000
        SECURE_HSTS_INCLUDE_SUBDOMAINS = True
        SECURE_HSTS_PRELOAD = True
        SECURE_SSL_REDIRECT = True
        SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
        SESSION_COOKIE_SECURE = True
        CSRF_COOKIE_SECURE = True
        print("🔒 Using PRODUCTION security settings (strict)")

# Session Settings
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Rate Limiting
RATELIMIT_ENABLE = True

# File Upload Settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB

# SMART LOGGING CONFIGURATION - Enhanced for production debugging
log_dir = BASE_DIR / 'logs'
log_dir.mkdir(exist_ok=True)

# Enhanced logging level when production debugging is enabled
log_level = 'DEBUG' if (DEBUG or PRODUCTION_DEBUG) else 'INFO'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
        'debug': {
            'format': '[{asctime}] {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': log_level,
            'class': 'logging.FileHandler',
            'filename': log_dir / 'django.log',
            'formatter': 'verbose',
        },
        'debug_file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': log_dir / 'debug.log',
            'formatter': 'debug',
        },
        'console': {
            'level': log_level,
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': log_level,
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django_tenants': {
            'handlers': ['console', 'file', 'debug_file'] if (DEBUG or PRODUCTION_DEBUG) else ['console', 'file'],
            'level': log_level,
            'propagate': False,
        },
        'apps': {
            'handlers': ['console', 'file', 'debug_file'] if (DEBUG or PRODUCTION_DEBUG) else ['console', 'file'],
            'level': log_level,
            'propagate': False,
        },
    },
}

# SMART CORS CONFIGURATION
if DEBUG:
    # Local development - allow all
    CORS_ALLOW_ALL_ORIGINS = True
    CORS_ALLOW_CREDENTIALS = True
    print("🌐 Using LOCAL CORS settings (allow all)")
else:
    # Production - specific domains only
    CORS_ALLOWED_ORIGINS = [
        "https://autowash.co.ke",
        "https://www.autowash.co.ke",
        'https://www.autowash-3jpr.onrender.com',
        'https://autowash-3jpr.onrender.com'  
    ]
    CORS_ALLOWED_ORIGIN_REGEXES = [
        r"^https://.*\.autowash\.co\.ke$",
        r"^https://.*\.autowash-3jpr\.onrender\.com$",
    ]
    CORS_ALLOW_CREDENTIALS = True
    CORS_ALLOW_ALL_ORIGINS = False
    print("🌐 Using PRODUCTION CORS settings (restricted)")

# Sentry Configuration (Production Error Tracking) - Disabled when debugging
if not DEBUG and not PRODUCTION_DEBUG and config('SENTRY_DSN', default=''):
    sentry_sdk.init(
        dsn=config('SENTRY_DSN'),
        integrations=[DjangoIntegration()],
        traces_sample_rate=1.0,
        send_default_pii=True
    )
    print("🐛 Sentry error tracking enabled")

# Custom Settings
BUSINESS_LOGO_UPLOAD_PATH = 'business_logos/'
EMPLOYEE_PHOTO_UPLOAD_PATH = 'employee_photos/'
CUSTOMER_PHOTO_UPLOAD_PATH = 'customer_photos/'

# Subscription Plans
SUBSCRIPTION_PLANS = {
    'basic': {
        'name': 'Basic Plan',
        'price': 2000,  # KES
        'max_employees': 5,
        'max_customers': 100,
        'features': ['Basic reporting', 'SMS notifications', 'Customer management']
    },
    'professional': {
        'name': 'Professional Plan',
        'price': 5000,  # KES
        'max_employees': 15,
        'max_customers': 500,
        'features': ['Advanced reporting', 'SMS & Email notifications', 'Inventory management', 'Employee management']
    },
    'enterprise': {
        'name': 'Enterprise Plan',
        'price': 10000,  # KES
        'max_employees': -1,  # Unlimited
        'max_customers': -1,  # Unlimited
        'features': ['All features', 'API access', 'Custom integrations', 'Priority support']
    }
}

# Environment-specific startup message
if DEBUG:
    print("\n" + "="*60)
    print("🏠 AUTOWASH - LOCAL DEVELOPMENT ENVIRONMENT")
    print("="*60)
    print("🌐 Tenant URLs will be: businessname.localhost:8000")
    print("📧 Using Gmail SMTP for emails")
    print("💰 Using M-Pesa sandbox")
    print("🔒 Security settings are relaxed")
    print("="*60 + "\n")
else:
    print("\n" + "="*60) 
    print("🚀 AUTOWASH - PRODUCTION ENVIRONMENT")
    print("="*60)
    print("🌐 Tenant URLs will be: businessname.autowash.co.ke")
    print("📧 Using domain email server")
    print("💰 Using M-Pesa production")
    if PRODUCTION_DEBUG:
        print("🔧 PRODUCTION DEBUG MODE ENABLED")
        print("🔒 Security settings are relaxed for debugging")
        print("📝 Enhanced logging enabled (check logs/debug.log)")
    else:
        print("🔒 Security settings are strict")
    print("🌐 PUBLIC_SCHEMA_URLCONF: autowash.urls_public")
    print("🌐 ROOT_URLCONF: autowash.urls")
    print("="*60 + "\n")