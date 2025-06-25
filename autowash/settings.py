import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['NUMEXPR_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['VECLIB_MAXIMUM_THREADS'] = '1'
os.environ['BLAS_NUM_THREADS'] = '1'

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

# Environment Detection
RENDER = config('RENDER', default=False, cast=bool)
CPANEL = config('CPANEL', default=False, cast=bool)
# CPANEL = True

# SMART ALLOWED_HOSTS based on environment
if not RENDER and not CPANEL:
    # Local development
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', '*.localhost', 'testserver']
    print("[LOCAL] Running in LOCAL DEVELOPMENT mode")
elif RENDER:
    # Production on Render
    ALLOWED_HOSTS = [
        '.onrender.com',                 
        'autowash-3jpr.onrender.com',      
        'autowash.co.ke',                   
        'www.autowash.co.ke',               
        '*.autowash.co.ke',                
    ]
    
    # Render automatically sets this environment variable
    render_external_hostname = config('RENDER_EXTERNAL_HOSTNAME', default='')
    if render_external_hostname and render_external_hostname not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(render_external_hostname)
        print(f"[RENDER] Added Render hostname: {render_external_hostname}")
    
    if DEBUG:
        print("[RENDER] RENDER with DEBUG ENABLED")
    else:
        print("[RENDER] RENDER PRODUCTION mode")
elif CPANEL:
    # Production on cPanel
    ALLOWED_HOSTS = [
        'app.autowash.co.ke',
        'autowash.co.ke',                   
        'www.autowash.co.ke',               
        '*.autowash.co.ke',
    ]
    
    # Add cPanel domain if specified
    cpanel_domain = config('CPANEL_DOMAIN', default='')
    if cpanel_domain and cpanel_domain not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(cpanel_domain)
        print(f"[CPANEL] Added cPanel domain: {cpanel_domain}")
    
    if DEBUG:
        print("[CPANEL] CPANEL with DEBUG ENABLED")
    else:
        print("[CPANEL] CPANEL PRODUCTION mode")

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
    'django.contrib.humanize',
    
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

# Add debug toolbar when debugging is enabled - NOT in production environments
if DEBUG and not RENDER and not CPANEL:
    # Only in local development
    SHARED_APPS.append('debug_toolbar')
elif DEBUG and (RENDER or CPANEL):
    # Production with debug - be selective
    SHARED_APPS.append('debug_toolbar')

INSTALLED_APPS = list(SHARED_APPS) + [app for app in TENANT_APPS if app not in SHARED_APPS]

# Tenant Configuration - PATH-BASED ROUTING
TENANT_MODEL = "accounts.Business"
TENANT_DOMAIN_MODEL = "accounts.Domain"
PUBLIC_SCHEMA_URLCONF = 'autowash.urls_public'
ROOT_URLCONF = 'autowash.urls'
PUBLIC_SCHEMA_NAME = 'public'
SHOW_PUBLIC_IF_NO_TENANT_FOUND = True

# PATH-BASED TENANT ROUTING CONFIGURATION
if not RENDER and not CPANEL:
    # Local development
    public_domain = 'localhost:8000'
elif RENDER:
    # Render environment
    public_domain = 'autowash-3jpr.onrender.com'
elif CPANEL:
    # cPanel environment
    public_domain = 'app.autowash.co.ke'

TENANT_ROUTING = {
    'ROUTING_METHOD': 'path',  # Use path-based instead of subdomain
    'TENANT_URL_PREFIX': 'business',  # URL prefix for tenant routes
    'PUBLIC_TENANT_DOMAIN': public_domain,
}

# Enhanced Session Configuration for Multi-tenant setup
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_NAME = 'autowash_sessionid'
SESSION_COOKIE_AGE = 86400
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_SAVE_EVERY_REQUEST = False
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# Session sharing across schemas
SESSION_COOKIE_DOMAIN = None
SESSION_COOKIE_PATH = '/'

SESSION_SERIALIZER = 'django.contrib.sessions.serializers.JSONSerializer'
SESSION_CACHE_ALIAS = 'default'

# Database session table configuration
DATABASE_ROUTERS = (
    'autowash.routers.SessionRouter',
    'django_tenants.routers.TenantSyncRouter',
)

# Updated MIDDLEWARE configuration
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
]

# Add WhiteNoise only for Render (cPanel serves static files differently)
if RENDER:
    MIDDLEWARE.append('whitenoise.middleware.WhiteNoiseMiddleware')

MIDDLEWARE.extend([
    'django.contrib.sessions.middleware.SessionMiddleware',
    'apps.core.middleware.SimpleSessionFixMiddleware',
    'apps.core.middleware.PathBasedTenantMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.core.middleware.SharedAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_ratelimit.middleware.RatelimitMiddleware',
    'apps.core.middleware.BusinessContextMiddleware',
    'apps.core.middleware.TimezoneMiddleware',
    'apps.core.middleware.UserActivityMiddleware',
    'allauth.account.middleware.AccountMiddleware',
])

# Add debug toolbar middleware only in development
if DEBUG and not RENDER and not CPANEL:
    MIDDLEWARE.append('debug_toolbar.middleware.DebugToolbarMiddleware')
elif DEBUG and (RENDER or CPANEL):
    MIDDLEWARE.append('debug_toolbar.middleware.DebugToolbarMiddleware')

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
                'apps.core.context_processors.user_role_context',
                'apps.core.context_processors.navigation_context',
                'apps.core.context_processors.notifications_context',
                'apps.core.context_processors.performance_context',
                'apps.core.context_processors.verification_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'autowash.wsgi.application'
ASGI_APPLICATION = 'autowash.asgi.application'

# DATABASE CONFIGURATION - FIXED for django-tenants
database_url = config('DATABASE_URL')

DATABASES = {
    'default': dj_database_url.parse(
        database_url,
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# CRITICAL FIX: Always use django-tenants PostgreSQL backend
DATABASES['default']['ENGINE'] = 'django_tenants.postgresql_backend'

# Configure SSL and connection options based on environment
if not RENDER and not CPANEL:
    # Local development - disable SSL for local PostgreSQL
    DATABASES['default']['OPTIONS'] = {
        'sslmode': 'disable',
        'options': '-c search_path=public'
    }
    print("[DATABASE] Using LOCAL PostgreSQL database (SSL disabled)")
elif RENDER:
    # Production/Render - require SSL for external PostgreSQL + timeout settings
    DATABASES['default']['OPTIONS'] = {
        'sslmode': 'require',
        'options': '-c search_path=public -c statement_timeout=300000 -c lock_timeout=300000'
    }
    DATABASES['default']['CONN_MAX_AGE'] = 0 if DEBUG else 600
    print("[DATABASE] Using RENDER PostgreSQL database (SSL required)")
elif CPANEL:
    # cPanel - typically localhost database
    DATABASES['default']['OPTIONS'] = {
        'sslmode': 'prefer',
        'options': '-c search_path=public'
    }
    print("[DATABASE] Using CPANEL PostgreSQL database")

# Redis & Channels
redis_url = config('REDIS_URL', default='redis://localhost:6379/1')
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [redis_url],
        },
    },
}

# CACHE CONFIGURATION
if redis_url and redis_url != '' and 'redis://' in redis_url:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': redis_url.replace('/1', '/2'),
        }
    }
    print("[CACHE] Using Redis cache")
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
            'LOCATION': 'cache_table',
        }
    }
    print("[CACHE] Using database cache")

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

# Static files (CSS, JavaScript, Images) - Environment-specific
STATIC_URL = '/static/'

if RENDER:
    # Render configuration
    STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
elif CPANEL:
    # cPanel configuration - FIXED for web accessibility
    STATIC_ROOT = os.path.join(BASE_DIR, 'public_html', 'static')
else:
    # Local development
    STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

# Media files - Environment-specific
MEDIA_URL = '/media/'

if CPANEL:
    # cPanel configuration
    MEDIA_ROOT = os.path.join(BASE_DIR, 'public_html', 'media')
else:
    # Render and local development
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Tenant-specific media storage
TENANT_MEDIA_ROOT = os.path.join(BASE_DIR, 'tenants', 'media')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Celery Configuration - Only if Redis is available
if redis_url and 'redis://' in redis_url:
    CELERY_BROKER_URL = redis_url.replace('/1', '/0')
    CELERY_RESULT_BACKEND = redis_url.replace('/1', '/0')
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_TIMEZONE = TIME_ZONE
    CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
    print("[CELERY] Celery configured with Redis")
else:
    print("[CELERY] Celery disabled - No Redis available")

# EMAIL CONFIGURATION based on environment
if not RENDER and not CPANEL:
    # Local development - Gmail SMTP
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
    EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
    EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
    EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
    EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
    DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@localhost')
    print("[EMAIL] Using LOCAL email configuration (Gmail SMTP)")
else:
    # Production - Domain email (both Render and cPanel)
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = config('EMAIL_HOST', default='mail.autowash.co.ke')
    EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
    EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
    EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='noreply@autowash.co.ke')
    EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
    DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='Autowash <noreply@autowash.co.ke>')
    if RENDER:
        print("[EMAIL] Using RENDER email configuration")
    elif CPANEL:
        print("[EMAIL] Using CPANEL email configuration")

# SMS Configuration
SMS_API_KEY = config('SMS_API_KEY', default='')
SMS_USERNAME = config('SMS_USERNAME', default='sandbox')

# M-PESA CONFIGURATION based on environment
if not RENDER and not CPANEL:
    # Local development - Sandbox
    MPESA_ENVIRONMENT = 'sandbox'
    MPESA_CONSUMER_KEY = config('MPESA_CONSUMER_KEY', default='')
    MPESA_CONSUMER_SECRET = config('MPESA_CONSUMER_SECRET', default='')
    MPESA_SHORTCODE = config('MPESA_SHORTCODE', default='174379')
    MPESA_PASSKEY = config('MPESA_PASSKEY', default='')
    MPESA_CALLBACK_URL = config('MPESA_CALLBACK_URL', default='http://localhost:8000/api/mpesa/callback/')
    print("[MPESA] Using SANDBOX M-Pesa configuration")
else:
    # Production - both Render and cPanel
    MPESA_ENVIRONMENT = config('MPESA_ENVIRONMENT', default='production')
    MPESA_CONSUMER_KEY = config('MPESA_CONSUMER_KEY', default='')
    MPESA_CONSUMER_SECRET = config('MPESA_CONSUMER_SECRET', default='')
    MPESA_SHORTCODE = config('MPESA_SHORTCODE', default='174379')
    MPESA_PASSKEY = config('MPESA_PASSKEY', default='')
    
    if RENDER:
        MPESA_CALLBACK_URL = config('MPESA_CALLBACK_URL', default='https://autowash-3jpr.onrender.com/api/mpesa/callback/')
    elif CPANEL:
        MPESA_CALLBACK_URL = config('MPESA_CALLBACK_URL', default='https://app.autowash.co.ke/api/mpesa/callback/')
    
    print("[MPESA] Using PRODUCTION M-Pesa configuration")

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

# AllAuth Configuration
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True

# SMART SECURITY SETTINGS
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

if not RENDER and not CPANEL:
    # Local development - relaxed security
    SECURE_HSTS_SECONDS = 0
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    print("[SECURITY] Using LOCAL security settings (relaxed)")
else:
    if DEBUG:
        # Production with debugging - relaxed security for easier debugging
        SECURE_HSTS_SECONDS = 0
        SECURE_SSL_REDIRECT = False
        SESSION_COOKIE_SECURE = False
        CSRF_COOKIE_SECURE = False
        if RENDER:
            print("[SECURITY] Using RENDER security settings (RELAXED for debugging)")
        elif CPANEL:
            print("[SECURITY] Using CPANEL security settings (RELAXED for debugging)")
    else:
        # Strict production security
        SECURE_HSTS_SECONDS = 31536000
        SECURE_HSTS_INCLUDE_SUBDOMAINS = True
        SECURE_HSTS_PRELOAD = True
        SECURE_SSL_REDIRECT = True
        SESSION_COOKIE_SECURE = True
        CSRF_COOKIE_SECURE = True
        
        if RENDER:
            SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
        elif CPANEL:
            SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
        
        if RENDER:
            print("[SECURITY] Using RENDER security settings (strict)")
        elif CPANEL:
            print("[SECURITY] Using CPANEL security settings (strict)")

# Rate Limiting
RATELIMIT_ENABLE = True

# File Upload Settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB

# LOGGING CONFIGURATION
log_dir = BASE_DIR / 'logs'
log_dir.mkdir(exist_ok=True)

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
    },
    'handlers': {
        'file': {
            'level': 'DEBUG' if DEBUG else 'INFO',
            'class': 'logging.FileHandler',
            'filename': log_dir / 'django.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG' if DEBUG else 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'DEBUG' if DEBUG else 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django_tenants': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}

# CORS CONFIGURATION based on environment
if not RENDER and not CPANEL:
    # Local development - allow all origins
    CORS_ALLOW_ALL_ORIGINS = True
    CORS_ALLOW_CREDENTIALS = True
    print("[CORS] Using LOCAL CORS settings (allow all)")
elif RENDER:
    # Production/Render - Render-optimized CORS
    CORS_ALLOWED_ORIGINS = [
        "https://autowash.co.ke",
        "https://www.autowash.co.ke",
        'https://autowash-3jpr.onrender.com',
        'https://www.autowash-3jpr.onrender.com'
    ]
    
    render_external_hostname = config('RENDER_EXTERNAL_HOSTNAME', default='')
    if render_external_hostname:
        CORS_ALLOWED_ORIGINS.append(f"https://{render_external_hostname}")
    
    CORS_ALLOWED_ORIGIN_REGEXES = [
        r"^https://.*\.autowash\.co\.ke$",
        r"^https://.*\.autowash-3jpr\.onrender\.com$",
        r"^https://.*\.onrender\.com$",
    ]
    CORS_ALLOW_CREDENTIALS = True
    CORS_ALLOW_ALL_ORIGINS = False
    CORS_PREFLIGHT_MAX_AGE = 86400
    
    print("[CORS] Using RENDER CORS settings (optimized for Render)")
elif CPANEL:
    # Production/cPanel - cPanel-optimized CORS
    CORS_ALLOWED_ORIGINS = [
        "https://app.autowash.co.ke",
        "https://autowash.co.ke",
        "https://www.autowash.co.ke",
    ]
    
    cpanel_domain = config('CPANEL_DOMAIN', default='')
    if cpanel_domain:
        CORS_ALLOWED_ORIGINS.append(f"https://{cpanel_domain}")
    
    CORS_ALLOWED_ORIGIN_REGEXES = [
        r"^https://.*\.autowash\.co\.ke$",
    ]
    CORS_ALLOW_CREDENTIALS = True
    CORS_ALLOW_ALL_ORIGINS = False
    CORS_PREFLIGHT_MAX_AGE = 86400
    
    print("[CORS] Using CPANEL CORS settings (optimized for cPanel)")

# Sentry Configuration - Only when not debugging
# sentry_dsn = config('SENTRY_DSN', default='')
# if (RENDER or CPANEL) and not DEBUG and sentry_dsn:
#     sentry_sdk.init(
#         dsn=sentry_dsn,
#         integrations=[DjangoIntegration()],
#         traces_sample_rate=1.0,
#         send_default_pii=True
#     )
#     print("[SENTRY] Sentry error tracking enabled")
# elif DEBUG:
#     print("[SENTRY] Sentry disabled (debug mode active)")
# else:
#     print("[SENTRY] Sentry disabled (local development or no DSN)")

# Custom Settings
BUSINESS_LOGO_UPLOAD_PATH = 'business_logos/'
EMPLOYEE_PHOTO_UPLOAD_PATH = 'employee_photos/'
CUSTOMER_PHOTO_UPLOAD_PATH = 'customer_photos/'

# Subscription Plans
SUBSCRIPTION_PLANS = {
    'basic': {
        'name': 'Basic Plan',
        'price': 2000,
        'max_employees': 5,
        'max_customers': 100,
        'features': ['Basic reporting', 'SMS notifications', 'Customer management']
    },
    'professional': {
        'name': 'Professional Plan',
        'price': 5000,
        'max_employees': 15,
        'max_customers': 500,
        'features': ['Advanced reporting', 'SMS & Email notifications', 'Inventory management', 'Employee management']
    },
    'enterprise': {
        'name': 'Enterprise Plan',
        'price': 10000,
        'max_employees': -1,
        'max_customers': -1,
        'features': ['All features', 'API access', 'Custom integrations', 'Priority support']
    }
}

# STARTUP MESSAGES based on environment
if not RENDER and not CPANEL:
    print("\n" + "="*70)
    print("[LOCAL] AUTOWASH - LOCAL DEVELOPMENT ENVIRONMENT (PATH-BASED)")
    print("="*70)
    print("[LOCAL] Main site: http://localhost:8000")
    print("[LOCAL] Business URLs: http://localhost:8000/business/{slug}/")
    print("[LOCAL] Email: Gmail SMTP")
    print("[LOCAL] M-Pesa: Sandbox")
    print("[LOCAL] Security: Relaxed")
    print(f"[LOCAL] Debug mode: {'Enabled' if DEBUG else 'Disabled'}")
    print("="*70 + "\n")
elif RENDER:
    print("\n" + "="*70) 
    print("[RENDER] AUTOWASH - PRODUCTION ENVIRONMENT (RENDER - PATH-BASED)")
    print("="*70)
    print("[RENDER] Main site: https://autowash-3jpr.onrender.com")
    print("[RENDER] Business URLs: https://autowash-3jpr.onrender.com/business/{slug}/")
    print("[RENDER] Email: Domain server")
    print("[RENDER] M-Pesa: Production")
    
    if DEBUG:
        print("[RENDER] DEBUG MODE: Enabled")
        print("[RENDER] Debug toolbar: Available")
        print("[RENDER] Enhanced logging: Enabled")
        print("[RENDER] Security: Relaxed for debugging")
        print("[RENDER] Sentry: Disabled")
    else:
        print("[RENDER] Security: Strict production mode")
        if config('SENTRY_DSN', default=''):
            print("[RENDER] Sentry: Enabled")
        else:
            print("[RENDER] Sentry: No DSN configured")
    
    print("[RENDER] Static files: WhiteNoise")
    print("="*70 + "\n")
elif CPANEL:
    print("\n" + "="*70) 
    print("[CPANEL] AUTOWASH - PRODUCTION ENVIRONMENT (CPANEL - PATH-BASED)")
    print("="*70)
    print("[CPANEL] Main site: https://app.autowash.co.ke")
    print("[CPANEL] Business URLs: https://app.autowash.co.ke/business/{slug}/")
    print("[CPANEL] Email: Domain server")
    print("[CPANEL] M-Pesa: Production")
    
    if DEBUG:
        print("[CPANEL] DEBUG MODE: Enabled")
        print("[CPANEL] Debug toolbar: Available")
        print("[CPANEL] Enhanced logging: Enabled")
        print("[CPANEL] Security: Relaxed for debugging")
        print("[CPANEL] Sentry: Disabled")
    else:
        print("[CPANEL] Security: Strict production mode")
        if config('SENTRY_DSN', default=''):
            print("[CPANEL] Sentry: Enabled")
        else:
            print("[CPANEL] Sentry: No DSN configured")
    
    print("[CPANEL] Static files: Apache/Nginx")
    if redis_url and 'redis://' in redis_url:
        print("[CPANEL] Celery: Enabled with Redis")
    else:
        print("[CPANEL] Celery: Disabled (No Redis)")
    print("="*70 + "\n")