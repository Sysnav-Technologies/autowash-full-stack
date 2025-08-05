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

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-in-production')
DEBUG = config('DEBUG', default=True, cast=bool)

RENDER = config('RENDER', default=False, cast=bool)
CPANEL = config('CPANEL', default=False, cast=bool)

if not RENDER and not CPANEL:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', '*.localhost', 'testserver']
elif RENDER:
    ALLOWED_HOSTS = [
        '.onrender.com',                 
        'autowash-3jpr.onrender.com',      
        'autowash.co.ke',                   
        'www.autowash.co.ke',               
        '*.autowash.co.ke',                
    ]
    render_external_hostname = config('RENDER_EXTERNAL_HOSTNAME', default='')
    if render_external_hostname:
        ALLOWED_HOSTS.append(render_external_hostname)
elif CPANEL:
    ALLOWED_HOSTS = [
        'app.autowash.co.ke',
        'autowash.co.ke',                   
        'www.autowash.co.ke',               
        '*.autowash.co.ke',
    ]
    cpanel_domain = config('CPANEL_DOMAIN', default='')
    if cpanel_domain:
        ALLOWED_HOSTS.append(cpanel_domain)

SHARED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'crispy_forms',
    'crispy_bootstrap5',
    'phonenumber_field',
    'django_extensions',
    'django_filters',
    'widget_tweaks',
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
    'django.contrib.sites',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'rest_framework.authtoken',
    'django_celery_beat',
    'django_celery_results',
    'apps.core',  # For TenantSettings model
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
    'apps.accounts',
    'apps.system_admin',  # System administration
]

if DEBUG:
    SHARED_APPS.append('debug_toolbar')

INSTALLED_APPS = list(SHARED_APPS) + [app for app in TENANT_APPS if app not in SHARED_APPS]

# MySQL Multi-Tenant Configuration
MAIN_DOMAIN = 'autowash.co.ke'
TENANT_MODEL = "core.Tenant"
TENANT_URLCONF = 'autowash.urls'
ROOT_URLCONF = 'autowash.urls'

# Public domain configuration
public_domain = 'localhost:8000' if not RENDER and not CPANEL else \
               'autowash-3jpr.onrender.com' if RENDER else \
               'app.autowash.co.ke'

# Multi-tenant routing configuration
TENANT_ROUTING = {
    'ROUTING_METHOD': 'path',  # or 'subdomain' or 'domain'
    'TENANT_URL_PREFIX': 'business',
    'PUBLIC_TENANT_DOMAIN': public_domain,
}

# Disable admin session check since we handle sessions ourselves
SILENCED_SYSTEM_CHECKS = ['admin.E410']

# MySQL Multi-Tenant Middleware Configuration
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
]

if RENDER:
    MIDDLEWARE.append('whitenoise.middleware.WhiteNoiseMiddleware')
elif CPANEL:
    # Add whitenoise for cPanel static file serving
    MIDDLEWARE.append('whitenoise.middleware.WhiteNoiseMiddleware')

MIDDLEWARE.extend([
    # Session middleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    
    # MySQL Multi-tenant middleware
    'apps.core.mysql_middleware.MySQLTenantMiddleware',
    'apps.core.mysql_middleware.TenantBusinessContextMiddleware',
    'apps.core.mysql_middleware.TenantURLMiddleware',
    
    # Standard Django middleware
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    
    # Auth middleware after tenant middleware
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    
    # Suspension and access control middleware (after auth)
    'apps.core.suspension_middleware.SuspensionCheckMiddleware',
    'apps.core.suspension_middleware.BusinessAccessControlMiddleware',
    
    # Message and other middleware
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_ratelimit.middleware.RatelimitMiddleware',
    
    # Custom middleware
    'apps.core.middleware.TimezoneMiddleware',
    'apps.core.middleware.UserActivityMiddleware',
    
    # AllAuth middleware at the end
    'allauth.account.middleware.AccountMiddleware',
])

if DEBUG:
    MIDDLEWARE.append('debug_toolbar.middleware.DebugToolbarMiddleware')

# Session Configuration - Enhanced for multi-tenant
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_NAME = 'autowash_sessionid'
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_COOKIE_DOMAIN = None
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_PATH = '/'
SESSION_SAVE_EVERY_REQUEST = False  # CRITICAL: Let our middleware handle saves
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SERIALIZER = 'django.contrib.sessions.serializers.JSONSerializer'

# CSRF Configuration
CSRF_COOKIE_NAME = 'autowash_csrftoken'
CSRF_COOKIE_AGE = 31449600
CSRF_COOKIE_DOMAIN = None
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_PATH = '/'
CSRF_USE_SESSIONS = False
CSRF_FAILURE_VIEW = 'apps.core.views.csrf_failure'

if not RENDER and not CPANEL:
    CSRF_TRUSTED_ORIGINS = [
        'http://localhost:8000',
        'http://127.0.0.1:8000',
        'http://testserver'
    ]
elif RENDER:
    CSRF_TRUSTED_ORIGINS = [
        'https://autowash-3jpr.onrender.com',
        'https://autowash.co.ke',
        'https://www.autowash.co.ke',
        'https://*.autowash.co.ke'
    ]
    render_external_hostname = config('RENDER_EXTERNAL_HOSTNAME', default='')
    if render_external_hostname:
        CSRF_TRUSTED_ORIGINS.append(f'https://{render_external_hostname}')
elif CPANEL:
    CSRF_TRUSTED_ORIGINS = [
        'https://app.autowash.co.ke',
        'https://autowash.co.ke',
        'https://www.autowash.co.ke',
        'https://*.autowash.co.ke'
    ]
    cpanel_domain = config('CPANEL_DOMAIN', default='')
    if cpanel_domain:
        CSRF_TRUSTED_ORIGINS.append(f'https://{cpanel_domain}')

CSRF_HEADER_NAME = 'HTTP_X_CSRFTOKEN'

# CRITICAL: Database configuration for MySQL multi-tenant routing
DATABASE_ROUTERS = [
    'apps.core.database_router.TenantDatabaseRouter',
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
                'apps.core.context_processors.user_role_context',
                'apps.core.context_processors.navigation_context',
                'apps.core.context_processors.notifications_context',
                'apps.core.context_processors.performance_context',
                'apps.core.context_processors.verification_context',
                'apps.core.context_processors.subscription_flow_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'autowash.wsgi.application'
ASGI_APPLICATION = 'autowash.asgi.application'

# MySQL Database Configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('DB_NAME', default='autowash_main'),
        'USER': config('DB_USER', default='root'),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            'autocommit': True,
        },
    }
}

# Database router for multi-tenant architecture
DATABASE_ROUTERS = [
    'apps.core.database_router.TenantDatabaseRouter',
]

# Redis and Channel Layers Configuration
redis_url = config('REDIS_URL', default='')
if redis_url and 'redis://' in redis_url:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                "hosts": [redis_url],
            },
        },
    }
else:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        },
    }

# Cache Configuration
if redis_url and redis_url != '' and 'redis://' in redis_url:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': redis_url.replace('/1', '/2'),
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
            'LOCATION': 'django_cache_table',
        }
    }

# Password Validation
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

# Static Files Configuration
STATIC_URL = '/static/'

if RENDER:
    STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
elif CPANEL:
    # For cPanel, static files should be in public_html/static
    STATIC_ROOT = os.path.join(BASE_DIR, 'public_html', 'static')
    # Use whitenoise for cPanel too to handle static files properly
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'
else:
    STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

# Media Files Configuration
MEDIA_URL = '/media/'

if CPANEL:
    MEDIA_ROOT = os.path.join(BASE_DIR, 'public_html', 'media')
else:
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Tenant-specific media root
TENANT_MEDIA_ROOT = os.path.join(BASE_DIR, 'tenants', 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Crispy Forms Configuration
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Celery Configuration
if redis_url and 'redis://' in redis_url:
    CELERY_BROKER_URL = redis_url.replace('/1', '/0')
    CELERY_RESULT_BACKEND = redis_url.replace('/1', '/0')
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_TIMEZONE = TIME_ZONE
    CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

if not RENDER and not CPANEL:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
    EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
    EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
    EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
    EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
    DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@localhost')
else:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = config('EMAIL_HOST', default='mail.autowash.co.ke')
    EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
    EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
    EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='noreply@autowash.co.ke')
    EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
    DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='Autowash <noreply@autowash.co.ke>')

SMS_API_KEY = config('SMS_API_KEY', default='')
SMS_USERNAME = config('SMS_USERNAME', default='sandbox')

if not RENDER and not CPANEL:
    MPESA_ENVIRONMENT = 'sandbox'
    MPESA_CONSUMER_KEY = config('MPESA_CONSUMER_KEY', default='')
    MPESA_CONSUMER_SECRET = config('MPESA_CONSUMER_SECRET', default='')
    MPESA_SHORTCODE = config('MPESA_SHORTCODE', default='174379')
    MPESA_PASSKEY = config('MPESA_PASSKEY', default='')
    MPESA_CALLBACK_URL = config('MPESA_CALLBACK_URL', default='http://localhost:8000/api/mpesa/callback/')
else:
    MPESA_ENVIRONMENT = config('MPESA_ENVIRONMENT', default='production')
    MPESA_CONSUMER_KEY = config('MPESA_CONSUMER_KEY', default='')
    MPESA_CONSUMER_SECRET = config('MPESA_CONSUMER_SECRET', default='')
    MPESA_SHORTCODE = config('MPESA_SHORTCODE', default='174379')
    MPESA_PASSKEY = config('MPESA_PASSKEY', default='')
    
    if RENDER:
        MPESA_CALLBACK_URL = config('MPESA_CALLBACK_URL', default='https://autowash-3jpr.onrender.com/api/mpesa/callback/')
    elif CPANEL:
        MPESA_CALLBACK_URL = config('MPESA_CALLBACK_URL', default='https://app.autowash.co.ke/api/mpesa/callback/')

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

SITE_ID = 1

LOGIN_URL = '/auth/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/public/'

ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_LOGOUT_REDIRECT_URL = '/public/'
ACCOUNT_LOGOUT_ON_GET = True

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

if not RENDER and not CPANEL:
    SECURE_HSTS_SECONDS = 0
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
else:
    if DEBUG:
        SECURE_HSTS_SECONDS = 0
        SECURE_SSL_REDIRECT = False
        SESSION_COOKIE_SECURE = False
        CSRF_COOKIE_SECURE = False
    else:
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

RATELIMIT_ENABLE = True

FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB

log_dir = BASE_DIR / 'logs'
log_dir.mkdir(exist_ok=True)

# Session logging configuration - Minimal to prevent noise
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
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': log_dir / 'django.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django.contrib.sessions': {
            'handlers': ['console', 'file'],
            'level': 'ERROR',  # Only log errors, not debug info
            'propagate': False,
        },
        'apps.core.middleware': {
            'handlers': ['console', 'file'],
            'level': 'ERROR',  # Only log errors
            'propagate': False,
        },
        'django_tenants': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

if not RENDER and not CPANEL:
    CORS_ALLOW_ALL_ORIGINS = True
    CORS_ALLOW_CREDENTIALS = True
elif RENDER:
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
elif CPANEL:
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

BUSINESS_LOGO_UPLOAD_PATH = 'business_logos/'
EMPLOYEE_PHOTO_UPLOAD_PATH = 'employee_photos/'
CUSTOMER_PHOTO_UPLOAD_PATH = 'customer_photos/'

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

if DEBUG:
    def show_toolbar(request):
        return DEBUG and (
            request.META.get('REMOTE_ADDR') in ['127.0.0.1', '::1'] or
            'localhost' in request.get_host()
        )
    
    DEBUG_TOOLBAR_CONFIG = {
        'SHOW_TOOLBAR_CALLBACK': show_toolbar,
        'SHOW_COLLAPSED': True,
        'INTERCEPT_REDIRECTS': False,
    }
    
    INTERNAL_IPS = [
        '127.0.0.1',
        'localhost',
    ]

# Whitenoise configuration for static files
if CPANEL or RENDER:
    # Whitenoise settings for production
    WHITENOISE_USE_FINDERS = True
    WHITENOISE_AUTOREFRESH = DEBUG
    WHITENOISE_MAX_AGE = 31536000  # 1 year
    
    # Add MIME types for whitenoise
    WHITENOISE_MIMETYPES = {
        '.css': 'text/css',
        '.js': 'application/javascript',
        '.json': 'application/json',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.svg': 'image/svg+xml',
        '.ico': 'image/x-icon',
        '.woff': 'font/woff',
        '.woff2': 'font/woff2',
        '.ttf': 'font/ttf',
        '.eot': 'application/vnd.ms-fontobject',
    }