# Enhanced settings.py with path-based django-tenants routing
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
RENDER = config('RENDER', default=False, cast=bool)

# SMART ALLOWED_HOSTS based on RENDER environment
if not RENDER:
    # Local development
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', '*.localhost', 'testserver']
    print("🏠 Running in LOCAL DEVELOPMENT mode")
else:
    # Production on Render
    ALLOWED_HOSTS = [
        '.onrender.com',                    # Covers ALL Render subdomains
        'autowash-3jpr.onrender.com',       # Your specific Render service
        'autowash.co.ke',                   # Custom domain
        'www.autowash.co.ke',               # WWW version
        '*.autowash.co.ke',                 # Subdomains
    ]
    
    # Render automatically sets this environment variable
    render_external_hostname = config('RENDER_EXTERNAL_HOSTNAME', default='')
    if render_external_hostname and render_external_hostname not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(render_external_hostname)
        print(f"🚀 Added Render hostname: {render_external_hostname}")
    
    if DEBUG:
        print("🚀 RENDER with DEBUG ENABLED")
    else:
        print("🚀 RENDER PRODUCTION mode")

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

# Add debug toolbar when debugging is enabled - BUT NOT ON RENDER ADMIN
if DEBUG and not RENDER:
    # Only in local development
    SHARED_APPS.append('debug_toolbar')
elif DEBUG and RENDER:
    # On Render with debug - be selective
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
TENANT_ROUTING = {
    'ROUTING_METHOD': 'path',  # Use path-based instead of subdomain
    'TENANT_URL_PREFIX': 'business',  # URL prefix for tenant routes
    'PUBLIC_TENANT_DOMAIN': 'localhost:8000' if not RENDER else 'autowash-3jpr.onrender.com',
}

# Enhanced Session Configuration for Multi-tenant setup
SESSION_ENGINE = 'django.contrib.sessions.backends.db'  # Use database sessions
SESSION_COOKIE_NAME = 'autowash_sessionid'  # Custom session name
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'  # Important for cross-schema navigation
SESSION_SAVE_EVERY_REQUEST = False  # CHANGED: Don't save on every request
SESSION_EXPIRE_AT_BROWSER_CLOSE = False  # Keep session across browser tabs

# CRITICAL: Session sharing across schemas
SESSION_COOKIE_DOMAIN = None  # Use default domain
SESSION_COOKIE_PATH = '/'  # Apply to all paths

# Add these new settings for better session handling
SESSION_SERIALIZER = 'django.contrib.sessions.serializers.JSONSerializer'
SESSION_CACHE_ALIAS = 'default'  # Use default cache for session caching

# Database session table configuration
# Make sure sessions are always stored in public schema
DATABASE_ROUTERS = (
    'autowash.routers.SessionRouter',  # Add this custom router
    'django_tenants.routers.TenantSyncRouter',
)

# Updated MIDDLEWARE configuration with session fix
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'apps.core.middleware.SimpleSessionFixMiddleware',  # NEW - Session persistence
    'apps.core.middleware.PathBasedTenantMiddleware',  # BEFORE auth
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.core.middleware.SharedAuthenticationMiddleware',  # NEW - AFTER auth
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_ratelimit.middleware.RatelimitMiddleware',
    'apps.core.middleware.BusinessContextMiddleware',
    'apps.core.middleware.TimezoneMiddleware',
    'apps.core.middleware.UserActivityMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

# Add debug toolbar middleware when enabled
if DEBUG and not RENDER:
    # Local development only
    MIDDLEWARE.append('debug_toolbar.middleware.DebugToolbarMiddleware')
elif DEBUG and RENDER:
    # Render with debug - add but with restrictions
    MIDDLEWARE.append('debug_toolbar.middleware.DebugToolbarMiddleware')

# Debug Toolbar Configuration
if DEBUG:
    INTERNAL_IPS = [
        '127.0.0.1',
        'localhost',
    ]
    
    # Configure debug toolbar for Render environment when debugging
    if RENDER:
        import socket
        try:
            # Get container IP for Render
            hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
            INTERNAL_IPS += [ip[: ip.rfind(".")] + ".1" for ip in ips]
            INTERNAL_IPS += ips
            
        except Exception as e:
            print(f"⚠️ Could not determine Render IPs for debug toolbar: {e}")
        
        # RENDER-SPECIFIC: Disable debug toolbar on admin operations to prevent timeout
        DEBUG_TOOLBAR_CONFIG = {
            'SHOW_TOOLBAR_CALLBACK': lambda request: (
                DEBUG and 
                not request.path.startswith('/system-admin/') and 
                not request.path.startswith('/admin/')
            ),
            'DISABLE_PANELS': [
                'debug_toolbar.panels.sql.SQLPanel',  # Disable SQL panel for performance
                'debug_toolbar.panels.staticfiles.StaticFilesPanel',  # Disable static files panel
            ],
            'SHOW_TEMPLATE_CONTEXT': False,  # Reduce memory usage
            'ENABLE_STACKTRACES': False,  # Reduce processing time
            'SHOW_COLLAPSED': True,
            'JQUERY_URL': '//ajax.googleapis.com/ajax/libs/jquery/3.6.0/jquery.min.js',
        }
        print("🐛 Debug toolbar configured for Render (ADMIN DISABLED)")
    else:
        # Local development - full debug toolbar
        DEBUG_TOOLBAR_CONFIG = {
            'SHOW_TOOLBAR_CALLBACK': lambda request: DEBUG,
            'SHOW_TEMPLATE_CONTEXT': True,
            'ENABLE_STACKTRACES': True,
        }
        print("🐛 Debug toolbar configured for local development")
# TEMPLATES section for settings.py - Updated context processors

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
                # Custom context processors - ORDER IS IMPORTANT!
                'apps.core.context_processors.business_context',         # First - sets up business context
                'apps.core.context_processors.user_role_context',        # Second - determines user role
                'apps.core.context_processors.navigation_context',       # Third - builds navigation based on role
                'apps.core.context_processors.notifications_context',    # Fourth - notifications (existing)
                'apps.core.context_processors.performance_context',      # Fifth - performance metrics
                'apps.core.context_processors.verification_context',     # Last - verification status
            ],
        },
    },
]
WSGI_APPLICATION = 'autowash.wsgi.application'
ASGI_APPLICATION = 'autowash.asgi.application'

# DATABASE CONFIGURATION
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

# Configure SSL based on RENDER environment variable
if not RENDER:
    # Local development - disable SSL for local PostgreSQL
    DATABASES['default']['OPTIONS'] = {
        'sslmode': 'disable',
        'options': '-c search_path=public'
    }
    print(f"📊 Using LOCAL PostgreSQL database (SSL disabled)")
else:
    # Production/Render - require SSL for external PostgreSQL + timeout settings
    DATABASES['default']['OPTIONS'] = {
        'sslmode': 'require',
        'options': '-c search_path=public -c statement_timeout=300000 -c lock_timeout=300000'
    }
    # Optimize for Render performance during schema creation
    DATABASES['default']['CONN_MAX_AGE'] = 0 if DEBUG else 600  # Disable persistent connections when debugging
    print(f"📊 Using RENDER PostgreSQL database (SSL required, timeouts configured)")

# Redis & Channels
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [config('REDIS_URL', default='redis://localhost:6379/1')],
        },
    },
}

# CACHE CONFIGURATION
redis_url = config('REDIS_URL', default=None)
if redis_url and redis_url != '':
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': redis_url.replace('/1', '/2'),
        }
    }
    print("💾 Using Redis cache")
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
            'LOCATION': 'cache_table',
        }
    }
    print("💾 Using database cache")

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

# STATIC FILES CONFIGURATION - Render optimized
STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

if RENDER:
    # Production on Render - use WhiteNoise
    STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
    
    # Render-specific static file optimizations
    WHITENOISE_USE_FINDERS = True
    WHITENOISE_AUTOREFRESH = DEBUG  # Only refresh when debugging
    WHITENOISE_SKIP_COMPRESS_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'zip', 'gz', 'tgz', 'bz2', 'tbz', 'xz', 'br']
else:
    # Local development
    STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Create required directories
def ensure_directories():
    directories = [
        BASE_DIR / 'static', BASE_DIR / 'static' / 'css', BASE_DIR / 'static' / 'js',
        BASE_DIR / 'static' / 'img', BASE_DIR / 'staticfiles', BASE_DIR / 'media', BASE_DIR / 'logs',
    ]
    for directory in directories:
        directory.mkdir(exist_ok=True)

ensure_directories()

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

# EMAIL CONFIGURATION based on RENDER environment
if not RENDER:
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
    # Production/Render - Domain email
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

# M-PESA CONFIGURATION based on RENDER environment
if not RENDER:
    # Local development - Sandbox
    MPESA_ENVIRONMENT = 'sandbox'
    MPESA_CONSUMER_KEY = config('MPESA_CONSUMER_KEY', default='')
    MPESA_CONSUMER_SECRET = config('MPESA_CONSUMER_SECRET', default='')
    MPESA_SHORTCODE = config('MPESA_SHORTCODE', default='174379')
    MPESA_PASSKEY = config('MPESA_PASSKEY', default='')
    MPESA_CALLBACK_URL = config('MPESA_CALLBACK_URL', default='http://localhost:8000/api/mpesa/callback/')
    print("💰 Using SANDBOX M-Pesa configuration")
else:
    # Production/Render - Production M-Pesa
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

# AllAuth Configuration
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True

# SMART SECURITY SETTINGS
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

if not RENDER:
    # Local development - relaxed security
    SECURE_HSTS_SECONDS = 0
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    print("🔒 Using LOCAL security settings (relaxed)")
else:
    if DEBUG:
        # Production with debugging - relaxed security for easier debugging
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

# CORS CONFIGURATION based on RENDER environment
if not RENDER:
    # Local development - allow all origins
    CORS_ALLOW_ALL_ORIGINS = True
    CORS_ALLOW_CREDENTIALS = True
    print("🌐 Using LOCAL CORS settings (allow all)")
else:
    # Production/Render - Render-optimized CORS
    CORS_ALLOWED_ORIGINS = [
        # Primary custom domains
        "https://autowash.co.ke",
        "https://www.autowash.co.ke",
        # Render domains
        'https://autowash-3jpr.onrender.com',
        'https://www.autowash-3jpr.onrender.com'
    ]
    
    # Add Render external hostname if available
    render_external_hostname = config('RENDER_EXTERNAL_HOSTNAME', default='')
    if render_external_hostname:
        CORS_ALLOWED_ORIGINS.append(f"https://{render_external_hostname}")
    
    CORS_ALLOWED_ORIGIN_REGEXES = [
        r"^https://.*\.autowash\.co\.ke$",
        r"^https://.*\.autowash-3jpr\.onrender\.com$",
        r"^https://.*\.onrender\.com$",  # Allow all Render subdomains
    ]
    CORS_ALLOW_CREDENTIALS = True
    CORS_ALLOW_ALL_ORIGINS = False
    
    # Render-specific CORS optimizations
    CORS_PREFLIGHT_MAX_AGE = 86400  # Cache preflight for 24 hours
    
    print("🌐 Using RENDER CORS settings (optimized for Render)")

# Sentry Configuration - Only when not debugging
if RENDER and not DEBUG and config('SENTRY_DSN', default=''):
    sentry_sdk.init(
        dsn=config('SENTRY_DSN'),
        integrations=[DjangoIntegration()],
        traces_sample_rate=1.0,
        send_default_pii=True
    )
    print("🐛 Sentry error tracking enabled")
elif DEBUG:
    print("🐛 Sentry disabled (debug mode active)")
else:
    print("🐛 Sentry disabled (local development or no DSN)")

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

# STARTUP MESSAGES based on RENDER environment
if not RENDER:
    print("\n" + "="*70)
    print("🏠 AUTOWASH - LOCAL DEVELOPMENT ENVIRONMENT (PATH-BASED)")
    print("="*70)
    print("🌐 Main site: http://localhost:8000")
    print("🏢 Business URLs: http://localhost:8000/business/{slug}/")
    print("📧 Email: Gmail SMTP")
    print("💰 M-Pesa: Sandbox")
    print("🔒 Security: Relaxed")
    print(f"🐛 Debug mode: {'Enabled' if DEBUG else 'Disabled'}")
    print("="*70 + "\n")
else:
    print("\n" + "="*70) 
    print("🚀 AUTOWASH - PRODUCTION ENVIRONMENT (RENDER - PATH-BASED)")
    print("="*70)
    print("🌐 Main site: https://autowash-3jpr.onrender.com")
    print("🏢 Business URLs: https://autowash-3jpr.onrender.com/business/{slug}/")
    print("📧 Email: Domain server")
    print("💰 M-Pesa: Production")
    
    if DEBUG:
        print("🔧 DEBUG MODE: Enabled")
        print("🐛 Debug toolbar: Available")
        print("📝 Enhanced logging: Enabled")
        print("🔒 Security: Relaxed for debugging")
        print("🐛 Sentry: Disabled")
    else:
        print("🔒 Security: Strict production mode")
        if config('SENTRY_DSN', default=''):
            print("🐛 Sentry: Enabled")
        else:
            print("🐛 Sentry: No DSN configured")
    
    print("📁 Static files: WhiteNoise")
    print("="*70 + "\n")