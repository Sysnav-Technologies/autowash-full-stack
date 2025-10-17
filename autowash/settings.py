import os
os.environ.update({
    'OPENBLAS_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
    'NUMEXPR_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1',
    'VECLIB_MAXIMUM_THREADS': '1', 'BLAS_NUM_THREADS': '1'
})

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
LOCAL = not RENDER and not CPANEL

ALLOWED_HOSTS = {
    'LOCAL': ['localhost', '127.0.0.1', '*.localhost', 'testserver'],
    'RENDER': ['.onrender.com', 'autowash-3jpr.onrender.com', 'autowash.co.ke', 'www.autowash.co.ke', '*.autowash.co.ke'],
    'CPANEL': ['app.autowash.co.ke', 'autowash.co.ke', 'www.autowash.co.ke', '*.autowash.co.ke', 'www.app.autowash.co.ke']
}

if LOCAL:
    ALLOWED_HOSTS = ALLOWED_HOSTS['LOCAL']
elif RENDER:
    ALLOWED_HOSTS = ALLOWED_HOSTS['RENDER']
    external_host = config('RENDER_EXTERNAL_HOSTNAME', default='')
    if external_host:
        ALLOWED_HOSTS.append(external_host)
else:
    ALLOWED_HOSTS = ALLOWED_HOSTS['CPANEL']
    cpanel_domain = config('CPANEL_DOMAIN', default='')
    if cpanel_domain:
        ALLOWED_HOSTS.append(cpanel_domain)

# Shared apps configuration
SHARED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
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
    'allauth.socialaccount.providers.google',
    'django_celery_beat',
    'django_celery_results',
    'channels',
    'django.contrib.humanize',
    'apps.core',
    'apps.accounts',
    'apps.subscriptions',
    'messaging',  # SMS/WhatsApp messaging system
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
    'allauth.socialaccount.providers.google',
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

SILENCED_SYSTEM_CHECKS = ['admin.E410']

MIDDLEWARE = [
    # 1. Security and CORS first (before any processing)
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
] + (
    # 2. Static files (if needed)
    ['whitenoise.middleware.WhiteNoiseMiddleware'] if RENDER or CPANEL else []
) + [
    # 3. Database protection (before any DB operations)
    'apps.core.db_protection_middleware.DatabaseConnectionProtectionMiddleware',
    
    # 4. Performance monitoring (early for accurate timing)
    'apps.core.performance_middleware.PerformanceMonitoringMiddleware',
    
    # 5. Cache middleware (before sessions/tenant resolution)
    'django.middleware.cache.UpdateCacheMiddleware',
    
    # 6. Sessions (needed for tenant resolution)
    'django.contrib.sessions.middleware.SessionMiddleware',
    
    # 7. Tenant resolution (critical for multi-tenant system)
    'apps.core.mysql_middleware.MySQLTenantMiddleware',
    'apps.core.mysql_middleware.TenantBusinessContextMiddleware',
    
    # 8. Common middleware (URL processing, ETags)
    'django.middleware.common.CommonMiddleware',
    
    # 9. CSRF protection (after common middleware)
    'django.middleware.csrf.CsrfViewMiddleware',
    
    # 10. Authentication protection (before auth middleware)
    'apps.core.auth_protection_middleware.AuthProtectionMiddleware',
    
    # 11. Authentication middleware
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    
    # 12. Messages (after authentication)
    'django.contrib.messages.middleware.MessageMiddleware',
    
    # 13. Business logic middleware (after auth)
    'apps.subscriptions.middleware.SubscriptionMiddleware',
    
    # 14. Rate limiting (if not cPanel)
] + (
    ['django_ratelimit.middleware.RatelimitMiddleware'] if not CPANEL else []
) + [
    # 15. Third-party account middleware
    'allauth.account.middleware.AccountMiddleware',
    
    # 16. Logging (near the end for complete request context)
    'apps.core.logging_utils.LoggingMiddleware',
    
    # 17. Security headers (near the end)
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
    # 18. Cache fetch middleware (last for caching)
    'django.middleware.cache.FetchFromCacheMiddleware',
]

if DEBUG:
    MIDDLEWARE.append('debug_toolbar.middleware.DebugToolbarMiddleware')

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

# AllAuth Settings
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = 'optional'
ACCOUNT_LOGIN_ATTEMPTS_LIMIT = 5
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_UNIQUE_EMAIL = True

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
                'apps.core.context_processors.static_version_context',  # For browser cache invalidation
                'apps.core.context_processors.business_context',
                'apps.core.context_processors.user_role_context',
                'apps.core.context_processors.navigation_context',
                'apps.core.context_processors.notifications_context',
                'apps.core.context_processors.performance_context',
                'apps.core.context_processors.verification_context',
                'apps.core.context_processors.subscription_flow_context',
                'apps.core.context_processors.sidebar_context',
                # Multi-tenant cache context processors
                'apps.core.cache_context_processors.tenant_cache_context',
                'apps.core.cache_context_processors.cache_performance_context',
                'apps.core.cache_context_processors.cache_health_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'autowash.wsgi.application'
ASGI_APPLICATION = 'autowash.asgi.application'

# MySQL Database Configuration with Enhanced Connection Pooling
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('DB_NAME', default='autowash_main'),
        'USER': config('DB_USER', default='root'),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='3306'),
        'CONN_MAX_AGE': 60,  # 1 minute connection age for controlled pooling
        'CONN_HEALTH_CHECKS': True,  # Enable connection health checks
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': (
                "SET sql_mode='STRICT_TRANS_TABLES',"
                "autocommit=1,"
                "wait_timeout=28800,"
                "interactive_timeout=28800,"
                "net_read_timeout=600,"
                "net_write_timeout=600,"
                "innodb_lock_wait_timeout=120"
            ),
            'autocommit': True,
            'connect_timeout': 10,  # Reduced from 60 to fail faster
            'read_timeout': 30,    # Reduced from 60 for faster failure detection
            'write_timeout': 30,   # Reduced from 60 for faster failure detection
            'sql_mode': 'STRICT_TRANS_TABLES',
            'isolation_level': None,  # Use MySQL default
        },
        'TEST': {
            'CHARSET': 'utf8mb4',
            'COLLATION': 'utf8mb4_unicode_ci',
        },
        'ATOMIC_REQUESTS': False,  # Disable for better multi-tenant performance
        'TIME_ZONE': None,  # Use global TIME_ZONE setting
        'AUTOCOMMIT': True,  # Enable autocommit for MySQL
    }
}

DATABASE_ROUTERS = ['apps.core.database_router.TenantDatabaseRouter']

# Redis and Channel Layers Configuration
redis_url = config('REDIS_URL', default='')
# Force in-memory channel layer for cPanel and LOCAL environments, Redis for RENDER
if CPANEL or LOCAL:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        },
    }
elif RENDER and redis_url and 'redis://' in redis_url:
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

# Cache Configuration - Production-Ready Database Cache

def get_cache_config():
    """
    Production-ready cache configuration optimized for immediate template updates
    Designed to prevent template staleness and system unresponsiveness
    """
    
    if CPANEL:
        # cPanel Production: Use locmem cache for speed, file-based for persistence
        # This configuration prevents template staleness while maintaining performance
        cache_dir = BASE_DIR / 'cache'
        cache_dir.mkdir(exist_ok=True)
        
        return {
            'default': {
                # Fast in-memory cache with optimized timeout for better performance
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                'TIMEOUT': 60,  # Increased from 30s to 60s for better performance
                'OPTIONS': {
                    'MAX_ENTRIES': 10000,  # Increased for higher concurrency
                    'CULL_FREQUENCY': 4,   # Less aggressive culling for better performance
                },
                'KEY_PREFIX': 'aw_fast_',
                'VERSION': 4,  # Bump version to clear old cache
            },
            'persistent': {
                # File-based cache for data that needs persistence
                'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
                'LOCATION': str(cache_dir / 'persistent'),
                'TIMEOUT': 600,  # Increased from 5 to 10 minutes for persistent data
                'OPTIONS': {
                    'MAX_ENTRIES': 2000,  # Increased from 500 for more capacity
                    'CULL_FREQUENCY': 4,  # Less aggressive culling
                }
            },
            'sessions': {
                # Separate cache for sessions with high-concurrency optimizations
                'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
                'LOCATION': str(cache_dir / 'sessions'),
                'TIMEOUT': 3600 * 24,  # 24 hours for better session persistence
                'OPTIONS': {
                    'MAX_ENTRIES': 10000,   # Support more concurrent sessions
                    'CULL_FREQUENCY': 3,    # Light culling for better performance
                }
            },
            'tenant_cache': {
                # Dedicated cache for tenant data to improve multi-tenant performance
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                'TIMEOUT': 300,  # 5 minutes for tenant data
                'OPTIONS': {
                    'MAX_ENTRIES': 2000,  # Support more tenants
                    'CULL_FREQUENCY': 4,
                },
                'KEY_PREFIX': 'aw_tenant_',
            }
        }
    
    elif RENDER:
        # Render: Use Redis if available, otherwise locmem for speed
        redis_url = config('REDIS_URL', default='')
        if redis_url and 'redis://' in redis_url:
            try:
                return {
                    'default': {
                        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
                        'LOCATION': redis_url,
                        'TIMEOUT': 60,  # Short timeout for immediate updates
                        'OPTIONS': {
                            'CONNECTION_POOL_KWARGS': {
                                'max_connections': 20,
                                'socket_connect_timeout': 5,
                                'socket_timeout': 5,
                            }
                        },
                        'KEY_PREFIX': 'aw_prod_',
                        'VERSION': 3,
                    }
                }
            except:
                pass
        
        # Fallback to fast locmem cache
        return {
            'default': {
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                'TIMEOUT': 60,  # Short timeout for immediate updates
                'OPTIONS': {
                    'MAX_ENTRIES': 2000,
                    'CULL_FREQUENCY': 2,
                }
            },
            'sessions': {
                # Add sessions cache for Render fallback
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                'TIMEOUT': 3600,  # 1 hour for sessions
                'OPTIONS': {
                    'MAX_ENTRIES': 1000,
                    'CULL_FREQUENCY': 3,
                }
            }
        }
    
    else:
        # Development: Use dummy cache to ensure immediate template updates
        # This completely eliminates caching issues during development
        return {
            'default': {
                'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
            },
            'sessions': {
                # Add sessions cache for local development
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                'TIMEOUT': 3600,  # 1 hour for sessions
                'OPTIONS': {
                    'MAX_ENTRIES': 1000,
                    'CULL_FREQUENCY': 3,
                }
            },
            'redis': {
                'BACKEND': 'django.core.cache.backends.redis.RedisCache',
                'LOCATION': 'redis://127.0.0.1:6379/1',
                'TIMEOUT': 60,
            } if LOCAL else {
                'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
            }
        }


CACHES = get_cache_config()

# Cache Configuration - Optimized for high concurrency performance
CACHE_VERSION = '5'  # Increment to invalidate all caches - HIGH CONCURRENCY OPTIMIZATIONS
CACHE_MIDDLEWARE_KEY_PREFIX = 'aw_hc'  # high-concurrency prefix
CACHE_MIDDLEWARE_SECONDS = 60 if CPANEL else 0  # Enable page caching for cPanel production only
CACHE_MIDDLEWARE_ALIAS = 'default'

# Template caching - COMPLETELY DISABLED to ensure immediate updates
USE_TEMPLATE_CACHE = False  # Never cache templates to prevent staleness
TEMPLATE_CACHE_TIMEOUT = 0  # Disable any template caching

# Session configuration - optimized for reliability and multi-tenant stability
# Use database sessions for maximum reliability in multi-tenant environment
SESSION_ENGINE = 'django.contrib.sessions.backends.db'

SESSION_COOKIE_AGE = 3600 * 24  # 24 hours for better session persistence
SESSION_COOKIE_NAME = 'autowash_sessionid'
SESSION_COOKIE_SECURE = not DEBUG and (CPANEL or RENDER)  # Secure in production
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_SAVE_EVERY_REQUEST = False  # Don't save on every request - performance boost
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SERIALIZER = 'django.contrib.sessions.serializers.JSONSerializer'  # Use JSON serializer for better compatibility

# Additional session settings for multi-tenant stability
SESSION_COOKIE_DOMAIN = None  # Allow sessions to work across subdomains
SESSION_FILE_PATH = None  # Not using file sessions

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
# Disable Redis for Celery in cPanel and LOCAL environments
if RENDER and redis_url and 'redis://' in redis_url:
    CELERY_BROKER_URL = redis_url.replace('/1', '/0')
    CELERY_RESULT_BACKEND = redis_url.replace('/1', '/0')
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_TIMEZONE = TIME_ZONE
    CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
elif CPANEL or LOCAL:
    # Use database backend for Celery in cPanel and local development
    CELERY_BROKER_URL = 'django://'
    CELERY_RESULT_BACKEND = 'django-cache'
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
    DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='Autowash <noreply@localhost>')
    SERVER_EMAIL = DEFAULT_FROM_EMAIL
    EMAIL_SUBJECT_PREFIX = '[Autowash] '
else:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = config('EMAIL_HOST', default='mail.autowash.co.ke')
    EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
    EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
    EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='noreply@autowash.co.ke')
    EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
    DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='Autowash <noreply@autowash.co.ke>')
    SERVER_EMAIL = DEFAULT_FROM_EMAIL
    EMAIL_SUBJECT_PREFIX = '[Autowash] '

# Email verification settings
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 7
ACCOUNT_EMAIL_CONFIRMATION_HMAC = True

SMS_API_KEY = config('SMS_API_KEY', default='')
SMS_USERNAME = config('SMS_USERNAME', default='sandbox')

if not RENDER and not CPANEL:
    MPESA_ENVIRONMENT = 'sandbox'
    MPESA_CONSUMER_KEY = config('MPESA_CONSUMER_KEY', default='')
    MPESA_CONSUMER_SECRET = config('MPESA_CONSUMER_SECRET', default='')
    MPESA_SHORTCODE = config('MPESA_SHORTCODE', default='174379')
    MPESA_PASSKEY = config('MPESA_PASSKEY', default='')
    MPESA_BASE_URL = config('MPESA_BASE_URL', default='https://sandbox.safaricom.co.ke')
    # For development, use httpbin.org as M-Pesa requires public URLs
    # To test real callbacks, use ngrok and update .env file
    MPESA_TIMEOUT_URL = config('MPESA_TIMEOUT_URL', default='https://httpbin.org/post')
    MPESA_CALLBACK_URL = config('MPESA_CALLBACK_URL', default='https://httpbin.org/post')
else:
    MPESA_ENVIRONMENT = config('MPESA_ENVIRONMENT', default='production')
    MPESA_CONSUMER_KEY = config('MPESA_CONSUMER_KEY', default='')
    MPESA_CONSUMER_SECRET = config('MPESA_CONSUMER_SECRET', default='')
    MPESA_SHORTCODE = config('MPESA_SHORTCODE', default='174379')
    MPESA_PASSKEY = config('MPESA_PASSKEY', default='') 
    MPESA_BASE_URL = config('MPESA_BASE_URL', default='https://sandbox.safaricom.co.ke')
    MPESA_CALLBACK_URL = config('MPESA_CALLBACK_URL', default='https://app.autowash.co.ke/subscriptions/mpesa-callback/')
    MPESA_TIMEOUT_URL = config('MPESA_TIMEOUT_URL', default='https://app.autowash.co.ke/subscriptions/mpesa-timeout/')
   

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
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_LOGOUT_REDIRECT_URL = '/public/'
ACCOUNT_LOGOUT_ON_GET = True

# Social Account Settings
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        'OAUTH_PKCE_ENABLED': True,
        'VERIFIED_EMAIL': True,
    }
}

# Social Account Configuration
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_VERIFICATION = 'none'  # Since Google emails are pre-verified
SOCIALACCOUNT_QUERY_EMAIL = True

# Google OAuth Credentials (to be set in environment variables)
GOOGLE_OAUTH2_CLIENT_ID = config('GOOGLE_OAUTH2_CLIENT_ID', default='')
GOOGLE_OAUTH2_CLIENT_SECRET = config('GOOGLE_OAUTH2_CLIENT_SECRET', default='')

# Site ID for allauth
SITE_ID = 1

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Browser compatibility: Use SAMEORIGIN for local dev, DENY for production
if not RENDER and not CPANEL:
    X_FRAME_OPTIONS = 'SAMEORIGIN'  # Less restrictive for local development
    SECURE_HSTS_SECONDS = 0
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
else:
    X_FRAME_OPTIONS = 'DENY'  # Strict security for production
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

# Reports directory for comprehensive logging
reports_dir = BASE_DIR / 'reports'
reports_dir.mkdir(exist_ok=True)
(reports_dir / 'tenant_activity').mkdir(exist_ok=True)
(reports_dir / 'user_logins').mkdir(exist_ok=True)
(reports_dir / 'performance_metrics').mkdir(exist_ok=True)
(reports_dir / 'business_analytics').mkdir(exist_ok=True)
(reports_dir / 'system_health').mkdir(exist_ok=True)
(reports_dir / 'security_logs').mkdir(exist_ok=True)
(reports_dir / 'error_tracking').mkdir(exist_ok=True)

# Enhanced logging configuration with comprehensive reporting
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
        'detailed': {
            'format': '{asctime} | {levelname} | {name} | {funcName} | {message}',
            'style': '{',
        },
        'json_format': {
            'format': '{asctime} | {levelname} | {name} | {funcName} | {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': log_dir / 'django.log',
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'tenant_activity': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': reports_dir / 'tenant_activity' / 'tenant_actions.log',
            'formatter': 'detailed',
            'encoding': 'utf-8',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
        },
        'user_logins': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': reports_dir / 'user_logins' / 'login_attempts.log',
            'formatter': 'json_format',
            'encoding': 'utf-8',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 10,
        },
        'performance_metrics': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': reports_dir / 'performance_metrics' / 'performance.log',
            'formatter': 'detailed',
            'encoding': 'utf-8',
            'maxBytes': 20971520,  # 20MB
            'backupCount': 7,
        },
        'security_logs': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': reports_dir / 'security_logs' / 'security_events.log',
            'formatter': 'json_format',
            'encoding': 'utf-8',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 20,  # Keep more security logs
        },
        'error_tracking': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': reports_dir / 'error_tracking' / 'application_errors.log',
            'formatter': 'verbose',
            'encoding': 'utf-8',
            'maxBytes': 20971520,  # 20MB
            'backupCount': 10,
        },
        'business_analytics': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': reports_dir / 'business_analytics' / 'business_events.log',
            'formatter': 'json_format',
            'encoding': 'utf-8',
            'maxBytes': 15728640,  # 15MB
            'backupCount': 12,
        },
    },
    'root': {
        'handlers': ['console', 'file', 'error_tracking'],
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
            'handlers': ['console', 'file', 'tenant_activity'],
            'level': 'INFO',
            'propagate': False,
        },
        'autowash.tenant_activity': {
            'handlers': ['tenant_activity'],
            'level': 'INFO',
            'propagate': False,
        },
        'autowash.user_logins': {
            'handlers': ['user_logins'],
            'level': 'INFO',
            'propagate': False,
        },
        'autowash.performance': {
            'handlers': ['performance_metrics'],
            'level': 'INFO',
            'propagate': False,
        },
        'autowash.security': {
            'handlers': ['security_logs'],
            'level': 'WARNING',
            'propagate': False,
        },
        'autowash.business': {
            'handlers': ['business_analytics'],
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

if not DEBUG:
    CONN_HEALTH_CHECKS = True
    DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
    FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
    
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    
    if CPANEL:
        USE_TZ = True
        TIME_ZONE = 'Africa/Nairobi'  # Keep Kenya timezone for cPanel
        ATOMIC_REQUESTS = False
        PREPEND_WWW = False
        
        # Additional cPanel optimizations for high concurrency
        DATA_UPLOAD_MAX_MEMORY_SIZE = 2621440  # 2.5MB
        FILE_UPLOAD_MAX_MEMORY_SIZE = 2621440  # 2.5MB
        
        # Connection and performance optimizations
        CONN_HEALTH_CHECKS = True
        
        # Enable optimizations
        USE_L10N = False  # Disable localization for better performance
        USE_I18N = False  # Disable internationalization for better performance