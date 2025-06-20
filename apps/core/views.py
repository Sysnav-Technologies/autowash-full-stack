from django.http import HttpResponse
from django.conf import settings
from django.db import connection
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.apps import apps
import sys
import os
import datetime
import traceback

User = get_user_model()

def health_check(request):
    """Comprehensive health check view to test all system components"""
    
    checks = {}
    overall_status = "✅ HEALTHY"
    
    # 1. Django Basic Status
    try:
        import django
        django_version = f"Django {django.get_version()}"
    except:
        django_version = "Django (version unknown)"
        
    checks['django'] = {
        'status': '✅ Running',
        'version': django_version,
        'python': f"Python {sys.version.split()[0]}",
        'debug': 'Enabled' if settings.DEBUG else 'Disabled'
    }
    
    # 2. Environment Detection
    env_type = 'LOCAL'
    if getattr(settings, 'RENDER', False):
        env_type = 'RENDER'
    elif getattr(settings, 'CPANEL', False):
        env_type = 'CPANEL'
    
    checks['environment'] = {
        'type': env_type,
        'allowed_hosts': settings.ALLOWED_HOSTS,
        'timezone': settings.TIME_ZONE
    }
    
    # 3. Database Connection Test
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            db_status = "✅ Connected"
            
            # Test tenant schema awareness
            cursor.execute("SELECT current_schema()")
            current_schema = cursor.fetchone()[0]
            
            # Get database info
            cursor.execute("SELECT version()")
            db_version = cursor.fetchone()[0]
            
        checks['database'] = {
            'status': db_status,
            'engine': settings.DATABASES['default']['ENGINE'],
            'schema': current_schema,
            'version': db_version[:50] + '...' if len(db_version) > 50 else db_version
        }
    except Exception as e:
        checks['database'] = {
            'status': f"❌ Error: {str(e)}",
            'engine': settings.DATABASES['default']['ENGINE'],
            'schema': 'Unknown',
            'version': 'Unknown'
        }
        overall_status = "⚠️ DEGRADED"
    
    # 4. Cache Test
    try:
        cache_key = f"health_check_{datetime.datetime.now().timestamp()}"
        cache.set(cache_key, "test_value", 30)
        cache_value = cache.get(cache_key)
        if cache_value == "test_value":
            cache_status = "✅ Working"
            cache.delete(cache_key)
        else:
            cache_status = "❌ Not working"
            overall_status = "⚠️ DEGRADED"
            
        cache_backend = settings.CACHES['default']['BACKEND']
        checks['cache'] = {
            'status': cache_status,
            'backend': cache_backend.split('.')[-1],
            'location': settings.CACHES['default'].get('LOCATION', 'Not specified')
        }
    except Exception as e:
        checks['cache'] = {
            'status': f"❌ Error: {str(e)}",
            'backend': 'Unknown',
            'location': 'Unknown'
        }
        overall_status = "⚠️ DEGRADED"
    
    # 5. Threading Configuration Check
    threading_env = {
        'OPENBLAS_NUM_THREADS': os.environ.get('OPENBLAS_NUM_THREADS', 'Not set'),
        'MKL_NUM_THREADS': os.environ.get('MKL_NUM_THREADS', 'Not set'),
        'OMP_NUM_THREADS': os.environ.get('OMP_NUM_THREADS', 'Not set'),
        'NUMEXPR_NUM_THREADS': os.environ.get('NUMEXPR_NUM_THREADS', 'Not set')
    }
    
    threading_status = "✅ Configured" if threading_env['OPENBLAS_NUM_THREADS'] == '1' else "⚠️ Not optimized"
    
    checks['threading'] = {
        'status': threading_status,
        'config': threading_env
    }
    
    # 6. Authentication System Test
    try:
        user_count = User.objects.count()
        auth_status = "✅ Working"
        checks['auth'] = {
            'status': auth_status,
            'user_model': User.__name__,
            'total_users': user_count,
            'current_user': str(request.user) if request.user.is_authenticated else 'Anonymous'
        }
    except Exception as e:
        checks['auth'] = {
            'status': f"❌ Error: {str(e)}",
            'user_model': 'Unknown',
            'total_users': 'Unknown',
            'current_user': 'Unknown'
        }
        overall_status = "⚠️ DEGRADED"
    
    # 7. Multi-tenant System Check
    try:
        schema_name = getattr(connection, 'schema_name', 'Unknown')
        tenant_info = getattr(request, 'tenant', None)
        business_info = getattr(request, 'business', None)
        
        tenant_status = "✅ Working"
        checks['tenancy'] = {
            'status': tenant_status,
            'current_schema': schema_name,
            'tenant_model': settings.TENANT_MODEL if hasattr(settings, 'TENANT_MODEL') else 'Not configured',
            'routing_method': settings.TENANT_ROUTING.get('ROUTING_METHOD', 'Unknown') if hasattr(settings, 'TENANT_ROUTING') else 'Unknown',
            'tenant_info': str(tenant_info) if tenant_info else 'None',
            'business_context': str(business_info) if business_info else 'None'
        }
    except Exception as e:
        checks['tenancy'] = {
            'status': f"❌ Error: {str(e)}",
            'current_schema': 'Unknown',
            'tenant_model': 'Unknown',
            'routing_method': 'Unknown'
        }
        overall_status = "⚠️ DEGRADED"
    
    # 8. Static/Media Files Check
    try:
        static_status = "✅ Configured"
        if hasattr(settings, 'STATICFILES_STORAGE'):
            storage_backend = settings.STATICFILES_STORAGE
        else:
            storage_backend = "Default"
            
        checks['static_files'] = {
            'status': static_status,
            'static_url': settings.STATIC_URL,
            'static_root': str(settings.STATIC_ROOT),
            'media_url': settings.MEDIA_URL,
            'media_root': str(settings.MEDIA_ROOT),
            'storage_backend': storage_backend
        }
    except Exception as e:
        checks['static_files'] = {
            'status': f"❌ Error: {str(e)}",
            'static_url': 'Unknown',
            'static_root': 'Unknown'
        }
    
    # 9. Email Configuration Check
    try:
        email_backend = settings.EMAIL_BACKEND
        email_status = "✅ Configured"
        
        checks['email'] = {
            'status': email_status,
            'backend': email_backend.split('.')[-1],
            'host': getattr(settings, 'EMAIL_HOST', 'Not set'),
            'port': getattr(settings, 'EMAIL_PORT', 'Not set'),
            'use_tls': getattr(settings, 'EMAIL_USE_TLS', 'Not set'),
            'default_from': getattr(settings, 'DEFAULT_FROM_EMAIL', 'Not set')
        }
    except Exception as e:
        checks['email'] = {
            'status': f"❌ Error: {str(e)}",
            'backend': 'Unknown'
        }
    
    # 10. Celery/Redis Check (if configured)
    if hasattr(settings, 'CELERY_BROKER_URL'):
        try:
            # Simple check if Redis is configured
            redis_url = getattr(settings, 'REDIS_URL', 'Not configured')
            celery_status = "✅ Configured" if redis_url != 'Not configured' else "⚠️ Not configured"
            
            checks['celery'] = {
                'status': celery_status,
                'broker_url': settings.CELERY_BROKER_URL if hasattr(settings, 'CELERY_BROKER_URL') else 'Not set',
                'result_backend': settings.CELERY_RESULT_BACKEND if hasattr(settings, 'CELERY_RESULT_BACKEND') else 'Not set'
            }
        except Exception as e:
            checks['celery'] = {
                'status': f"❌ Error: {str(e)}",
                'broker_url': 'Unknown'
            }
    else:
        checks['celery'] = {
            'status': "⚠️ Not configured",
            'broker_url': 'Not configured'
        }
    
    # Generate HTML response
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>AutoWash System Health Check</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                margin: 0; 
                padding: 20px; 
                background-color: #f5f5f5; 
            }}
            .container {{ 
                max-width: 1200px; 
                margin: 0 auto; 
                background: white; 
                border-radius: 8px; 
                box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
                padding: 30px; 
            }}
            .header {{ 
                text-align: center; 
                margin-bottom: 30px; 
                border-bottom: 2px solid #eee; 
                padding-bottom: 20px; 
            }}
            .status-grid {{ 
                display: grid; 
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); 
                gap: 20px; 
                margin-bottom: 30px; 
            }}
            .check-card {{ 
                border: 1px solid #ddd; 
                border-radius: 6px; 
                padding: 15px; 
                background: #fafafa; 
            }}
            .check-title {{ 
                font-weight: bold; 
                font-size: 16px; 
                margin-bottom: 10px; 
                color: #333; 
            }}
            .check-detail {{ 
                margin: 5px 0; 
                font-size: 14px; 
            }}
            .status-ok {{ color: #28a745; }}
            .status-warning {{ color: #ffc107; }}
            .status-error {{ color: #dc3545; }}
            .links {{ 
                background: #e9ecef; 
                padding: 20px; 
                border-radius: 6px; 
                margin-top: 20px; 
            }}
            .links a {{ 
                display: inline-block; 
                margin: 5px 10px 5px 0; 
                padding: 8px 15px; 
                background: #007bff; 
                color: white; 
                text-decoration: none; 
                border-radius: 4px; 
                font-size: 14px; 
            }}
            .links a:hover {{ background: #0056b3; }}
            .refresh-btn {{ 
                background: #28a745; 
                color: white; 
                border: none; 
                padding: 10px 20px; 
                border-radius: 4px; 
                cursor: pointer; 
                font-size: 14px; 
            }}
            .refresh-btn:hover {{ background: #218838; }}
            pre {{ 
                background: #f8f9fa; 
                padding: 10px; 
                border-radius: 4px; 
                font-size: 12px; 
                overflow-x: auto; 
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚗 AutoWash System Health Check</h1>
                <h2 class="{'status-ok' if overall_status.startswith('✅') else 'status-warning' if overall_status.startswith('⚠️') else 'status-error'}">{overall_status}</h2>
                <p>Last checked: {current_time}</p>
                <button class="refresh-btn" onclick="location.reload()">🔄 Refresh</button>
            </div>
            
            <div class="status-grid">
    """
    
    # Add each check as a card
    for check_name, check_data in checks.items():
        html_content += f"""
                <div class="check-card">
                    <div class="check-title">🔧 {check_name.replace('_', ' ').title()}</div>
        """
        
        for key, value in check_data.items():
            if key == 'status':
                status_class = 'status-ok' if value.startswith('✅') else 'status-warning' if value.startswith('⚠️') else 'status-error'
                html_content += f'<div class="check-detail"><strong>{key.title()}:</strong> <span class="{status_class}">{value}</span></div>'
            elif isinstance(value, dict):
                html_content += f'<div class="check-detail"><strong>{key.title()}:</strong></div>'
                for sub_key, sub_value in value.items():
                    html_content += f'<div class="check-detail" style="margin-left: 15px;">• {sub_key}: {sub_value}</div>'
            else:
                html_content += f'<div class="check-detail"><strong>{key.title()}:</strong> {value}</div>'
        
        html_content += "</div>"
    
    html_content += f"""
            </div>
            
            <div class="links">
                <h3>🔗 Quick Navigation</h3>
                <a href="/health/">🔄 Refresh Health Check</a>
                <a href="/admin/">🛠️ Django Admin</a>
                <a href="/system-admin/">⚙️ System Admin</a>
                <a href="/public/">🌐 Public Site</a>
                <a href="/auth/login/">🔐 Login</a>
                <a href="/auth/dashboard/">📊 Dashboard</a>
                
                <h4 style="margin-top: 20px;">📋 System Information</h4>
                <pre>Request Path: {request.path}
Request Method: {request.method}
User Agent: {request.META.get('HTTP_USER_AGENT', 'Unknown')[:100]}
Remote Address: {request.META.get('REMOTE_ADDR', 'Unknown')}
Server Name: {request.META.get('SERVER_NAME', 'Unknown')}
Request Time: {current_time}</pre>
            </div>
        </div>
    </body>
    </html>
    """
    
    return HttpResponse(html_content)