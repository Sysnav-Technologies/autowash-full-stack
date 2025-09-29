"""
Performance Monitoring Views for System Admin
Advanced AutoWash Control Panel with Comprehensive System Monitoring
"""

from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import connection
from django.core.cache import cache
from django.contrib.sessions.models import Session
from django.contrib.auth.models import User
from django.db.models import Count, Q, Sum, Avg
from django.core.paginator import Paginator
from apps.core.tenant_models import Tenant
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import psutil
import platform
import os
import json
import gc
import logging
import socket
import subprocess


# Set up logging to capture Django logs
logger = logging.getLogger(__name__)


def get_django_logs(hours=24, level='INFO'):
    """
    Retrieve actual Django application logs from the log file
    """
    logs = []
    log_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs', 'django.log')
    
    try:
        if os.path.exists(log_file):
            cutoff_time = timezone.now() - timedelta(hours=hours)
            
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                        
                    # Parse actual log entries
                    if any(level_check in line for level_check in ['INFO', 'ERROR', 'WARNING', 'DEBUG', 'CRITICAL']):
                        # Extract timestamp if present in log format
                        timestamp = timezone.now()  # Default to now if can't parse
                        
                        # Determine log level
                        if 'ERROR' in line:
                            log_level = 'ERROR'
                        elif 'WARNING' in line:
                            log_level = 'WARNING'
                        elif 'CRITICAL' in line:
                            log_level = 'CRITICAL'
                        elif 'DEBUG' in line:
                            log_level = 'DEBUG'
                        else:
                            log_level = 'INFO'
                            
                        log_entry = {
                            'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                            'level': log_level,
                            'message': line[:200] + '...' if len(line) > 200 else line,
                            'source': 'django'
                        }
                        logs.append(log_entry)
                        
            # Return most recent logs first
            logs = logs[-100:] if len(logs) > 100 else logs
            logs.reverse()
            
    except Exception as e:
        logs.append({
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            'level': 'ERROR',
            'message': f'Failed to read Django logs: {str(e)}',
            'source': 'system'
        })
    
    return logs


def get_tenant_query_stats():
    """
    Get actual detailed query statistics per tenant from real database
    """
    tenant_stats = {}
    
    try:
        # Get all actual tenants
        tenants = Tenant.objects.all()
        
        for tenant in tenants:
            # Get actual tenant database information
            tenant_db_name = getattr(tenant, 'schema_name', f'tenant_{tenant.id}')
            
            # Query actual database statistics
            with connection.cursor() as cursor:
                try:
                    # Get actual table information for this tenant
                    cursor.execute("""
                        SELECT 
                            COUNT(*) as table_count,
                            COALESCE(SUM(DATA_LENGTH + INDEX_LENGTH), 0) as size_bytes
                        FROM information_schema.TABLES 
                        WHERE TABLE_SCHEMA = %s
                    """, [tenant_db_name])
                    
                    result = cursor.fetchone()
                    table_count, size_bytes = result if result else (0, 0)
                    
                    # Get actual recent activity for this tenant
                    recent_activity = 0
                    try:
                        # Count recent updates/activities for this tenant
                        if hasattr(tenant, 'updated_at'):
                            recent_activity = 1 if tenant.updated_at and tenant.updated_at >= (timezone.now() - timedelta(hours=24)) else 0
                    except:
                        recent_activity = 0
                    
                    tenant_stats[tenant.name if hasattr(tenant, 'name') else f'tenant_{tenant.id}'] = {
                        'id': str(tenant.id),
                        'table_count': table_count or 0,
                        'size_mb': round(size_bytes / (1024 * 1024), 2) if size_bytes else 0,
                        'recent_activity': recent_activity,
                        'is_active': getattr(tenant, 'is_active', True),
                        'created_date': tenant.created_at.strftime('%Y-%m-%d') if hasattr(tenant, 'created_at') and tenant.created_at else 'Unknown',
                        'last_activity': tenant.updated_at.strftime('%Y-%m-%d %H:%M') if hasattr(tenant, 'updated_at') and tenant.updated_at else 'No recent activity'
                    }
                    
                except Exception as e:
                    # If tenant-specific query fails, add basic info
                    tenant_stats[tenant.name if hasattr(tenant, 'name') else f'tenant_{tenant.id}'] = {
                        'id': str(tenant.id),
                        'table_count': 0,
                        'size_mb': 0,
                        'recent_activity': 0,
                        'is_active': getattr(tenant, 'is_active', True),
                        'created_date': tenant.created_at.strftime('%Y-%m-%d') if hasattr(tenant, 'created_at') and tenant.created_at else 'Unknown',
                        'error': f'Query failed: {str(e)[:50]}'
                    }
                
    except Exception as e:
        logger.error(f"Error getting actual tenant query stats: {e}")
        tenant_stats['error'] = f"Failed to fetch tenant data: {str(e)}"
    
    return tenant_stats


def get_user_session_analytics():
    """
    Get actual user session and activity analytics from real data
    """
    try:
        # Get actual active sessions
        active_sessions = Session.objects.filter(expire_date__gt=timezone.now()).count()
        
        # Get actual user activity in last 24 hours  
        recent_activity = 0
        total_users = 0
        
        try:
            # Check if using custom user model or default
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            total_users = User.objects.count()
            
            if hasattr(User, 'last_login'):
                recent_activity = User.objects.filter(
                    last_login__gte=timezone.now() - timedelta(hours=24)
                ).count()
        except:
            total_users = 0
            recent_activity = 0
        
        # Get actual tenant activity
        try:
            total_tenants = Tenant.objects.count()
            active_tenants_today = Tenant.objects.filter(
                updated_at__gte=timezone.now() - timedelta(hours=24)
            ).count() if Tenant.objects.filter(updated_at__isnull=False).exists() else 0
            
            # Get tenant status breakdown
            active_tenants = Tenant.objects.filter(is_active=True).count() if hasattr(Tenant, 'is_active') else total_tenants
            inactive_tenants = total_tenants - active_tenants
            
        except Exception as e:
            total_tenants = 0
            active_tenants_today = 0
            active_tenants = 0
            inactive_tenants = 0
        
        return {
            'active_sessions': active_sessions,
            'recent_user_activity': recent_activity,
            'active_tenants_today': active_tenants_today,
            'total_users': total_users,
            'total_tenants': total_tenants,
            'active_tenants': active_tenants,
            'inactive_tenants': inactive_tenants,
            'last_updated': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
    except Exception as e:
        logger.error(f"Error getting actual user session analytics: {e}")
        return {
            'active_sessions': 0,
            'recent_user_activity': 0,
            'active_tenants_today': 0,
            'total_users': 0,
            'total_tenants': 0,
            'active_tenants': 0,
            'inactive_tenants': 0,
            'error': str(e),
            'last_updated': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        }


def get_ip_geolocation_data():
    """
    Get actual IP address data from real request logs and system
    """
    locations = []
    
    try:
        # Get actual server IP information
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        
        # Get network interfaces and their IPs
        try:
            import netifaces
            interfaces = []
            for interface in netifaces.interfaces():
                try:
                    addresses = netifaces.ifaddresses(interface)
                    if netifaces.AF_INET in addresses:
                        for link in addresses[netifaces.AF_INET]:
                            interfaces.append({
                                'interface': interface,
                                'ip': link['addr'],
                                'netmask': link.get('netmask', ''),
                            })
                except:
                    continue
        except ImportError:
            # If netifaces not available, use psutil
            interfaces = []
            for interface, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == socket.AF_INET:
                        interfaces.append({
                            'interface': interface,
                            'ip': addr.address,
                            'netmask': addr.netmask,
                        })
        
        # Add actual system location (East Africa timezone)
        system_location = {
            'ip': local_ip,
            'hostname': hostname,
            'timezone': str(timezone.get_current_timezone()),
            'region': 'East Africa',
            'interfaces': interfaces[:5],  # Limit to first 5
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        locations.append(system_location)
        
        # Try to read actual access logs if they exist
        access_log_paths = [
            '/var/log/nginx/access.log',
            '/var/log/apache2/access.log',
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs', 'access.log')
        ]
        
        for log_path in access_log_paths:
            if os.path.exists(log_path):
                try:
                    with open(log_path, 'r') as f:
                        lines = f.readlines()[-100:]  # Last 100 lines
                        
                    ip_counter = Counter()
                    for line in lines:
                        # Parse IP from log line (basic parsing)
                        parts = line.split()
                        if parts and parts[0]:
                            ip = parts[0]
                            # Skip local/private IPs for geolocation
                            if not any(ip.startswith(prefix) for prefix in ['127.', '10.', '192.168.', '172.']):
                                ip_counter[ip] += 1
                    
                    # Add top IPs from actual logs
                    for ip, count in ip_counter.most_common(10):
                        locations.append({
                            'ip': ip,
                            'requests': count,
                            'source': 'access_log',
                            'log_file': log_path
                        })
                    break
                        
                except Exception as e:
                    logger.error(f"Error reading access log {log_path}: {e}")
        
    except Exception as e:
        logger.error(f"Error getting actual IP geolocation data: {e}")
        locations.append({
            'error': f'Failed to get IP data: {str(e)}',
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    
    return locations


def get_query_performance_metrics():
    """
    Get actual detailed query performance metrics from database
    """
    metrics = {
        'slow_queries': [],
        'query_distribution': {},
        'avg_query_time': 0,
        'queries_per_second': 0,
        'connection_stats': {},
        'performance_schema_data': {}
    }
    
    try:
        with connection.cursor() as cursor:
            # Get actual slow query count
            cursor.execute("SHOW GLOBAL STATUS LIKE 'Slow_queries'")
            slow_queries_result = cursor.fetchone()
            slow_queries_count = int(slow_queries_result[1]) if slow_queries_result else 0
            
            # Get total queries
            cursor.execute("SHOW GLOBAL STATUS LIKE 'Questions'")
            total_queries_result = cursor.fetchone()
            total_queries = int(total_queries_result[1]) if total_queries_result else 0
            
            # Get uptime
            cursor.execute("SHOW GLOBAL STATUS LIKE 'Uptime'")
            uptime_result = cursor.fetchone()
            uptime_seconds = int(uptime_result[1]) if uptime_result else 1
            
            # Calculate actual QPS
            qps = round(total_queries / uptime_seconds, 2) if uptime_seconds > 0 else 0
            
            # Get connection statistics
            cursor.execute("SHOW GLOBAL STATUS LIKE 'Connections'")
            total_connections_result = cursor.fetchone()
            total_connections = int(total_connections_result[1]) if total_connections_result else 0
            
            cursor.execute("SHOW GLOBAL STATUS LIKE 'Max_used_connections'")
            max_connections_result = cursor.fetchone()
            max_connections = int(max_connections_result[1]) if max_connections_result else 0
            
            cursor.execute("SHOW GLOBAL STATUS LIKE 'Threads_connected'")
            current_connections_result = cursor.fetchone()
            current_connections = int(current_connections_result[1]) if current_connections_result else 0
            
            # Get query cache statistics if available
            try:
                cursor.execute("SHOW GLOBAL STATUS LIKE 'Qcache_%'")
                cache_stats = {row[0]: row[1] for row in cursor.fetchall()}
            except:
                cache_stats = {}
            
            # Get actual table statistics
            cursor.execute("""
                SELECT 
                    TABLE_SCHEMA,
                    COUNT(*) as table_count,
                    SUM(TABLE_ROWS) as total_rows,
                    SUM(DATA_LENGTH + INDEX_LENGTH) as total_size
                FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
                GROUP BY TABLE_SCHEMA
                ORDER BY total_size DESC
            """)
            
            schema_stats = []
            for row in cursor.fetchall():
                schema_stats.append({
                    'schema': row[0],
                    'tables': row[1],
                    'rows': row[2] or 0,
                    'size_mb': round((row[3] or 0) / (1024 * 1024), 2)
                })
            
            # Try to get recent slow queries if slow query log is enabled
            slow_query_details = []
            try:
                # Check if slow query log is enabled
                cursor.execute("SHOW VARIABLES LIKE 'slow_query_log'")
                slow_log_enabled = cursor.fetchone()
                
                if slow_log_enabled and slow_log_enabled[1] == 'ON':
                    # Try to read slow query log file location
                    cursor.execute("SHOW VARIABLES LIKE 'slow_query_log_file'")
                    log_file_result = cursor.fetchone()
                    
                    if log_file_result and log_file_result[1]:
                        slow_log_file = log_file_result[1]
                        # Add info about slow query log
                        slow_query_details.append({
                            'log_enabled': True,
                            'log_file': slow_log_file,
                            'total_slow_queries': slow_queries_count
                        })
            except:
                pass
            
            # Populate metrics with actual data
            metrics.update({
                'slow_queries_count': slow_queries_count,
                'total_queries': total_queries,
                'queries_per_second': qps,
                'uptime_seconds': uptime_seconds,
                'uptime_formatted': f"{uptime_seconds // 86400}d {(uptime_seconds % 86400) // 3600}h {(uptime_seconds % 3600) // 60}m",
                'connection_stats': {
                    'total_connections': total_connections,
                    'max_used_connections': max_connections,
                    'current_connections': current_connections,
                    'connection_usage_pct': round((current_connections / max_connections * 100), 2) if max_connections > 0 else 0
                },
                'cache_stats': cache_stats,
                'schema_statistics': schema_stats,
                'slow_query_details': slow_query_details,
                'last_updated': timezone.now().strftime('%Y-%m-%d %H:%M:%S %Z')
            })
            
    except Exception as e:
        logger.error(f"Error getting actual query performance metrics: {e}")
        metrics['error'] = str(e)
        metrics['last_updated'] = timezone.now().strftime('%Y-%m-%d %H:%M:%S %Z')
    
    return metrics


def get_actual_application_errors():
    """
    Get actual application errors from Django logs and database
    """
    errors = []
    
    try:
        # Read actual Django error logs
        log_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs', 'django.log')
        
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            # Parse actual error entries from last 24 hours
            for line in reversed(lines[-500:]):  # Last 500 lines
                if 'ERROR' in line or 'CRITICAL' in line:
                    errors.append({
                        'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'level': 'CRITICAL' if 'CRITICAL' in line else 'ERROR',
                        'message': line.strip()[:300],
                        'source': 'django_log'
                    })
                    
                    if len(errors) >= 50:  # Limit to recent 50 errors
                        break
        
        # Check for database connection errors
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception as db_error:
            errors.insert(0, {
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                'level': 'CRITICAL',
                'message': f'Database connection error: {str(db_error)}',
                'source': 'database'
            })
        
        # Check cache connectivity
        try:
            cache.set('health_check', 'ok', 30)
            if cache.get('health_check') != 'ok':
                errors.append({
                    'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'level': 'ERROR',
                    'message': 'Cache system not responding properly',
                    'source': 'cache'
                })
        except Exception as cache_error:
            errors.append({
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                'level': 'ERROR',
                'message': f'Cache error: {str(cache_error)}',
                'source': 'cache'
            })
        
    except Exception as e:
        errors.append({
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            'level': 'ERROR',
            'message': f'Error collecting application errors: {str(e)}',
            'source': 'monitor'
        })
    
    return errors


def get_real_system_resources():
    """
    Get actual detailed system resource usage
    """
    try:
        # CPU information
        cpu_info = {
            'usage_percent': round(psutil.cpu_percent(interval=1), 2),
            'count_physical': psutil.cpu_count(logical=False),
            'count_logical': psutil.cpu_count(logical=True),
            'frequency_current': round(psutil.cpu_freq().current, 2) if psutil.cpu_freq() else 0,
            'frequency_max': round(psutil.cpu_freq().max, 2) if psutil.cpu_freq() else 0,
            'per_cpu_usage': [round(x, 2) for x in psutil.cpu_percent(percpu=True, interval=1)]
        }
        
        # Memory information
        memory = psutil.virtual_memory()
        memory_info = {
            'total_gb': round(memory.total / (1024**3), 2),
            'available_gb': round(memory.available / (1024**3), 2),
            'used_gb': round(memory.used / (1024**3), 2),
            'usage_percent': round(memory.percent, 2),
            'free_gb': round(memory.free / (1024**3), 2),
            'cached_gb': round(getattr(memory, 'cached', 0) / (1024**3), 2),
            'buffers_gb': round(getattr(memory, 'buffers', 0) / (1024**3), 2)
        }
        
        # Disk information
        disk_info = []
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disk_info.append({
                    'device': partition.device,
                    'mountpoint': partition.mountpoint,
                    'fstype': partition.fstype,
                    'total_gb': round(usage.total / (1024**3), 2),
                    'used_gb': round(usage.used / (1024**3), 2),
                    'free_gb': round(usage.free / (1024**3), 2),
                    'usage_percent': round((usage.used / usage.total) * 100, 2)
                })
            except PermissionError:
                continue
        
        # Network information
        network_io = psutil.net_io_counters()
        network_info = {
            'bytes_sent': network_io.bytes_sent,
            'bytes_recv': network_io.bytes_recv,
            'packets_sent': network_io.packets_sent,
            'packets_recv': network_io.packets_recv,
            'errors_in': network_io.errin,
            'errors_out': network_io.errout,
            'drops_in': network_io.dropin,
            'drops_out': network_io.dropout
        }
        
        # Process information
        process_info = {
            'total_processes': len(psutil.pids()),
            'running_processes': len([p for p in psutil.process_iter(['status']) if p.info['status'] == psutil.STATUS_RUNNING]),
            'sleeping_processes': len([p for p in psutil.process_iter(['status']) if p.info['status'] == psutil.STATUS_SLEEPING])
        }
        
        # System uptime
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        
        return {
            'cpu': cpu_info,
            'memory': memory_info,
            'disk': disk_info,
            'network': network_info,
            'processes': process_info,
            'uptime_seconds': int(uptime.total_seconds()),
            'uptime_formatted': str(uptime).split('.')[0],
            'boot_time': boot_time.strftime('%Y-%m-%d %H:%M:%S'),
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S %Z')
        }
        
    except Exception as e:
        logger.error(f"Error getting actual system resources: {e}")
        return {
            'error': str(e),
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S %Z')
        }


@staff_member_required
def performance_monitoring_view(request):
    """
    AutoWash Control Panel - Comprehensive Real-Time System Monitoring
    Displays actual system metrics, logs, analytics, and comprehensive insights
    """
    try:
        # Get current East Africa time
        current_time = timezone.now()
        
        # === COMPREHENSIVE SYSTEM RESOURCES ===
        system_resources = get_real_system_resources()
        
        # === ACTUAL DATA COLLECTION ===
        django_logs = get_django_logs(hours=24)
        application_errors = get_actual_application_errors()
        tenant_analytics = get_tenant_query_stats()
        user_analytics = get_user_session_analytics()
        ip_location_data = get_ip_geolocation_data()
        query_metrics = get_query_performance_metrics()
        
        # === SYSTEM INFORMATION ===
        system_info = {
            'hostname': platform.node(),
            'platform': f"{platform.system()} {platform.release()}",
            'architecture': platform.machine(),
            'python_version': platform.python_version(),
            'django_version': getattr(__import__('django'), 'VERSION', 'Unknown'),
            'timezone': str(timezone.get_current_timezone()),
            'current_time': current_time,
            'uptime': system_resources.get('uptime_formatted', 'Unknown'),
            'boot_time': system_resources.get('boot_time', 'Unknown')
        }
        
        # === EXTRACT ACTUAL METRICS ===
        cpu_info = system_resources.get('cpu', {})
        memory_info = system_resources.get('memory', {})
        disk_info = system_resources.get('disk', [])
        network_info = system_resources.get('network', {})
        
        # === DATABASE STATISTICS ===
        database_stats = {
            'active_connections': query_metrics.get('connection_stats', {}).get('current_connections', 0),
            'total_connections': query_metrics.get('connection_stats', {}).get('total_connections', 0),
            'max_connections': query_metrics.get('connection_stats', {}).get('max_used_connections', 0),
            'queries_per_second': query_metrics.get('queries_per_second', 0),
            'total_queries': query_metrics.get('total_queries', 0),
            'slow_queries': query_metrics.get('slow_queries_count', 0),
            'uptime_seconds': query_metrics.get('uptime_seconds', 0),
            'schema_stats': query_metrics.get('schema_statistics', []),
            'cache_stats': query_metrics.get('cache_stats', {}),
            'status': 'optimal' if query_metrics.get('slow_queries_count', 0) < 10 else 'warning'
        }
        
        # === TENANT STATISTICS ===
        tenant_stats = {
            'total_tenants': user_analytics.get('total_tenants', 0),
            'active_tenants': user_analytics.get('active_tenants', 0),
            'inactive_tenants': user_analytics.get('inactive_tenants', 0),
            'recent_activity_24h': user_analytics.get('active_tenants_today', 0),
            'tenant_details': tenant_analytics,
            'health_status': 'optimal' if user_analytics.get('active_tenants', 0) > 0 else 'warning'
        }
        
        # === USER SESSION ANALYTICS ===
        session_stats = {
            'active_sessions': user_analytics.get('active_sessions', 0),
            'recent_user_activity': user_analytics.get('recent_user_activity', 0),
            'total_users': user_analytics.get('total_users', 0),
            'last_updated': user_analytics.get('last_updated', current_time.strftime('%Y-%m-%d %H:%M:%S'))
        }
        
        # === NETWORK & LOCATION DATA ===
        network_stats = {
            'interfaces': ip_location_data,
            'total_bytes_sent': network_info.get('bytes_sent', 0),
            'total_bytes_recv': network_info.get('bytes_recv', 0),
            'errors_in': network_info.get('errors_in', 0),
            'errors_out': network_info.get('errors_out', 0),
            'status': 'optimal' if network_info.get('errors_in', 0) + network_info.get('errors_out', 0) == 0 else 'warning'
        }
        
        # === CACHE PERFORMANCE ===
        cache_stats = {}
        try:
            test_key = f'monitor_test_{int(time.time())}'
            cache.set(test_key, 'test', 30)
            cache_working = cache.get(test_key) == 'test'
            cache.delete(test_key)
            
            cache_stats = {
                'status': 'operational' if cache_working else 'error',
                'backend': str(type(cache).__name__),
                'test_successful': cache_working,
                'last_tested': current_time.strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            cache_stats = {
                'status': 'error',
                'error': str(e),
                'last_tested': current_time.strftime('%Y-%m-%d %H:%M:%S')
            }
        
        # === PERFORMANCE LOGS (ACTUAL DATA ONLY) ===
        performance_logs = []
        performance_logs.extend(django_logs[:25])  # Latest 25 Django logs
        performance_logs.extend([{
            'timestamp': error['timestamp'],
            'level': error['level'],
            'message': error['message'],
            'source': error['source']
        } for error in application_errors[:25]])  # Latest 25 errors
        
        # Sort by timestamp (most recent first)
        performance_logs.sort(key=lambda x: x['timestamp'], reverse=True)
        performance_logs = performance_logs[:50]  # Limit to 50 total entries
        
        # === OVERALL SYSTEM STATUS ===
        cpu_status = 'optimal' if cpu_info.get('usage_percent', 0) < 70 else 'warning' if cpu_info.get('usage_percent', 0) < 90 else 'critical'
        memory_status = 'optimal' if memory_info.get('usage_percent', 0) < 70 else 'warning' if memory_info.get('usage_percent', 0) < 90 else 'critical'
        
        overall_status = 'critical' if any(status == 'critical' for status in [cpu_status, memory_status]) else \
                        'warning' if any(status == 'warning' for status in [cpu_status, memory_status, database_stats['status']]) else 'optimal'
        
        # === TEMPLATE CONTEXT ===
        context = {
            'title': 'AutoWash Control Panel - Real-Time Monitoring',
            'current_time': current_time,
            'system_info': system_info,
            'cpu_info': cpu_info,
            'memory_info': memory_info,
            'disk_info': disk_info,
            'network_info': network_stats,
            'database_stats': database_stats,
            'tenant_stats': tenant_stats,
            'session_stats': session_stats,
            'cache_stats': cache_stats,
            'performance_logs': performance_logs,
            'application_errors': application_errors,
            'django_logs': django_logs,
            'query_metrics': query_metrics,
            'ip_location_data': ip_location_data,
            'overall_status': overall_status,
            'performance_data': json.dumps({
                'system_metrics': {
                    'cpu_percent': cpu_info.get('usage_percent', 0),
                    'memory_percent': memory_info.get('usage_percent', 0),
                    'disk_usage': [d.get('usage_percent', 0) for d in disk_info],
                    'network_errors': network_stats.get('errors_in', 0) + network_stats.get('errors_out', 0)
                },
                'application_metrics': {
                    'active_tenants': tenant_stats['active_tenants'],
                    'db_connections': database_stats['active_connections'],
                    'active_sessions': session_stats['active_sessions'],
                    'queries_per_second': database_stats['queries_per_second']
                },
                'health_status': {
                    'cpu': cpu_status,
                    'memory': memory_status,
                    'database': database_stats['status'],
                    'cache': cache_stats['status'],
                    'network': network_stats['status']
                },
                'timestamp': current_time.isoformat(),
                'timezone': str(timezone.get_current_timezone()),
                'system_info': system_info,
                'tenant_analytics': tenant_analytics,
                'user_analytics': user_analytics
            })
        }
        
        return render(request, 'system_admin/performance_monitoring.html', context)
        
    except Exception as e:
        logger.error(f"Error in performance monitoring view: {e}")
        
        # Return minimal error context
        error_context = {
            'title': 'AutoWash Control Panel - System Error',
            'error': str(e),
            'current_time': timezone.now(),
            'overall_status': 'critical',
            'system_info': {
                'hostname': platform.node(),
                'error_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S %Z'),
                'error_message': str(e)
            },
            'performance_data': json.dumps({
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            })
        }
        
        return render(request, 'system_admin/performance_monitoring.html', error_context)
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                usage_percent = round((usage.used / usage.total) * 100, 1)
                disk_info.append({
                    'device': partition.device,
                    'mountpoint': partition.mountpoint,
                    'filesystem': partition.fstype,
                    'total_gb': round(usage.total / (1024**3), 2),
                    'used_gb': round(usage.used / (1024**3), 2),
                    'free_gb': round(usage.free / (1024**3), 2),
                    'usage_percent': usage_percent,
                    'status': 'optimal' if usage_percent < 70 else 'warning' if usage_percent < 90 else 'critical'
                })
            except (PermissionError, FileNotFoundError, OSError):
                continue
        
        # === NETWORK METRICS ===
        network = psutil.net_io_counters()
        network_interfaces = []
        try:
            for interface, stats in psutil.net_io_counters(pernic=True).items():
                if stats.bytes_sent > 0 or stats.bytes_recv > 0:  # Only active interfaces
                    network_interfaces.append({
                        'name': interface,
                        'bytes_sent': stats.bytes_sent,
                        'bytes_recv': stats.bytes_recv,
                        'packets_sent': stats.packets_sent,
                        'packets_recv': stats.packets_recv,
                        'errors_in': stats.errin,
                        'errors_out': stats.errout
                    })
        except Exception:
            network_interfaces = []
        
        network_info = {
            'total_bytes_sent': network.bytes_sent,
            'total_bytes_recv': network.bytes_recv,
            'total_packets_sent': network.packets_sent,
            'total_packets_recv': network.packets_recv,
            'errors_in': network.errin,
            'errors_out': network.errout,
            'drops_in': network.dropin,
            'drops_out': network.dropout,
            'interfaces': network_interfaces[:5],  # Limit to 5 interfaces
            'status': 'optimal' if (network.errin + network.errout) == 0 else 'warning'
        }
        
        # === DATABASE PERFORMANCE ===
        database_stats = {}
        try:
            with connection.cursor() as cursor:
                # MySQL specific queries
                queries = [
                    ("SELECT COUNT(*) FROM information_schema.processlist", "active_connections"),
                    ("SHOW GLOBAL STATUS LIKE 'Connections'", "total_connections"),
                    ("SHOW GLOBAL STATUS LIKE 'Queries'", "total_queries"),
                    ("SHOW GLOBAL STATUS LIKE 'Uptime'", "uptime_seconds"),
                    ("SHOW GLOBAL STATUS LIKE 'Slow_queries'", "slow_queries"),
                    ("SHOW GLOBAL STATUS LIKE 'Threads_running'", "threads_running")
                ]
                
                stats = {}
                for query, key in queries:
                    try:
                        cursor.execute(query)
                        result = cursor.fetchone()
                        if key == "active_connections":
                            stats[key] = int(result[0]) if result else 0
                        else:
                            stats[key] = int(result[1]) if result else 0
                    except Exception:
                        stats[key] = 0
                
                # Calculate derived metrics
                uptime = max(stats.get('uptime_seconds', 1), 1)
                queries_per_second = round(stats.get('total_queries', 0) / uptime, 2)
                
                database_stats = {
                    **stats,
                    'queries_per_second': queries_per_second,
                    'status': 'optimal' if stats.get('slow_queries', 0) < 10 else 'warning' if stats.get('slow_queries', 0) < 50 else 'critical'
                }
                
        except Exception as db_error:
            database_stats = {
                'error': f"Database metrics unavailable: {str(db_error)}",
                'active_connections': 0,
                'total_connections': 0,
                'total_queries': 0,
                'uptime_seconds': 0,
                'slow_queries': 0,
                'queries_per_second': 0,
                'threads_running': 0,
                'status': 'error'
            }
        
        # === DJANGO CACHE PERFORMANCE ===
        cache_stats = {}
        try:
            # Test cache functionality
            test_key = 'perf_monitor_test'
            test_value = f'test_{timezone.now().timestamp()}'
            
            # Write test
            cache.set(test_key, test_value, 30)
            
            # Read test
            retrieved_value = cache.get(test_key)
            cache_working = retrieved_value == test_value
            
            # Cleanup
            cache.delete(test_key)
            
            cache_stats = {
                'status': 'operational' if cache_working else 'error',
                'backend': str(type(cache).__name__),
                'backend_type': cache.__class__.__module__.split('.')[-1],
                'test_successful': cache_working,
                'response_time_ms': 'N/A'  # Could be measured if needed
            }
            
            # Try to get additional stats if available
            if hasattr(cache, 'get_stats'):
                additional_stats = cache.get_stats()
                cache_stats.update(additional_stats)
                
        except Exception as cache_error:
            cache_stats = {
                'status': 'error',
                'error': str(cache_error),
                'backend': 'unknown',
                'test_successful': False
            }
        
        # === TENANT STATISTICS ===
        tenant_stats = {
            'total_tenants': Tenant.objects.count(),
            'active_tenants': Tenant.objects.filter(is_active=True).count(),
            'suspended_tenants': Tenant.objects.filter(is_active=False).count(),
            'recent_signups_24h': Tenant.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=24)
            ).count(),
            'recent_signups_7d': Tenant.objects.filter(
                created_at__gte=timezone.now() - timedelta(days=7)
            ).count(),
            'recent_signups_30d': Tenant.objects.filter(
                created_at__gte=timezone.now() - timedelta(days=30)
            ).count()
        }
        
        # Calculate health status
        total = tenant_stats['total_tenants']
        active = tenant_stats['active_tenants']
        tenant_stats['health_status'] = 'optimal' if total > 0 and (active / total) > 0.9 else 'warning'
        
        # === PERFORMANCE METRICS FROM MIDDLEWARE ===
        performance_logs = []
        try:
            # Generate sample performance data - replace with real data from logs
            current_time = timezone.now()
            for i in range(24):  # Last 24 hours
                timestamp = current_time - timedelta(hours=i)
                # These would come from your performance monitoring middleware
                performance_logs.append({
                    'timestamp': timestamp,
                    'response_time_ms': 150 + (i * 5) + (i % 3 * 20),  # Sample data
                    'query_count': 12 + (i % 5),
                    'active_users': max(1, 50 - i + (i % 7 * 10)),
                    'memory_usage_mb': 256 + (i * 2) + (i % 4 * 15)
                })
        except Exception:
            performance_logs = []
        
        # === PROCESS INFORMATION ===
        current_process = psutil.Process()
        try:
            process_info = {
                'pid': current_process.pid,
                'memory_percent': round(current_process.memory_percent(), 2),
                'memory_rss_mb': round(current_process.memory_info().rss / (1024**2), 2),
                'memory_vms_mb': round(current_process.memory_info().vms / (1024**2), 2),
                'cpu_percent': round(current_process.cpu_percent(), 2),
                'num_threads': current_process.num_threads(),
                'create_time': datetime.fromtimestamp(current_process.create_time()),
                'status': current_process.status(),
                'num_fds': current_process.num_fds() if hasattr(current_process, 'num_fds') else 'N/A'
            }
        except Exception:
            process_info = {
                'pid': 'N/A',
                'memory_percent': 0,
                'memory_rss_mb': 0,
                'memory_vms_mb': 0,
                'cpu_percent': 0,
                'num_threads': 0,
                'create_time': timezone.now(),
                'status': 'unknown',
                'num_fds': 'N/A'
            }
        
        # === SECURITY METRICS ===
        security_info = {
            'failed_login_attempts_24h': 0,  # Would come from security logs
            'suspicious_requests_24h': 0,    # Would come from security middleware
            'blocked_ips_count': 0,          # Would come from firewall logs
            'last_security_scan': timezone.now() - timedelta(days=1),  # Sample data
            'ssl_cert_expires': timezone.now() + timedelta(days=90),   # Sample data
            'status': 'secure'
        }
        
        # === OVERALL SYSTEM HEALTH ===
        health_indicators = {
            'cpu': cpu_info['status'],
            'memory': memory_info['status'],
            'disk': 'optimal' if not disk_info or all(d['status'] == 'optimal' for d in disk_info) else 'warning',
            'database': database_stats['status'],
            'cache': cache_stats['status'],
            'network': network_info['status'],
            'tenants': tenant_stats['health_status']
        }
        
        # Overall system status
        critical_count = sum(1 for status in health_indicators.values() if status == 'critical')
        warning_count = sum(1 for status in health_indicators.values() if status == 'warning')
        
        if critical_count > 0:
            overall_status = 'critical'
        elif warning_count > 0:
            overall_status = 'warning'
        else:
            overall_status = 'optimal'
        
        context = {
            'system_info': system_info,
            'cpu_info': cpu_info,
            'memory_info': memory_info,
            'disk_info': disk_info,
            'network_info': network_info,
            'database_stats': database_stats,
            'cache_stats': cache_stats,
            'tenant_stats': tenant_stats,
            'performance_logs': performance_logs,
            'process_info': process_info,
            'security_info': security_info,
            'health_indicators': health_indicators,
            'overall_status': overall_status,
            'current_time': timezone.now(),
            'page_title': 'Mission Control - Performance Monitoring'
        }
        
        return render(request, 'system_admin/performance_monitoring.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading performance monitoring: {str(e)}")
        return render(request, 'system_admin/performance_monitoring.html', {
            'error': str(e),
            'current_time': timezone.now(),
            'page_title': 'Mission Control - Error',
            'overall_status': 'critical'
        })


@staff_member_required
@require_http_methods(["POST"])
def server_action_view(request):
    """
    Handle server management actions from the performance monitoring dashboard
    """
    action = request.POST.get('action')
    confirm = request.POST.get('confirm') == 'true'
    
    try:
        if action == 'clear_cache':
            if not confirm:
                return JsonResponse({
                    'success': False, 
                    'requires_confirmation': True,
                    'message': 'This will clear all cached data. Are you sure?'
                })
            
            cache.clear()
            return JsonResponse({
                'success': True, 
                'message': 'Cache cleared successfully',
                'action_performed': 'Cache Clear',
                'timestamp': timezone.now().isoformat()
            })
            
        elif action == 'restart_server':
            return JsonResponse({
                'success': False, 
                'message': 'Server restart requires external process management. Use your hosting control panel.',
                'action_performed': 'Server Restart',
                'requires_external': True
            })
            
        elif action == 'optimize_database':
            if not confirm:
                return JsonResponse({
                    'success': False,
                    'requires_confirmation': True, 
                    'message': 'This will optimize database tables. This may take several minutes. Continue?'
                })
            
            optimized_tables = []
            try:
                with connection.cursor() as cursor:
                    # Get list of tables to optimize
                    cursor.execute("SHOW TABLES")
                    tables = [row[0] for row in cursor.fetchall()]
                    
                    # Optimize each table
                    for table in tables[:5]:  # Limit to first 5 tables for safety
                        try:
                            cursor.execute(f"OPTIMIZE TABLE {table}")
                            optimized_tables.append(table)
                        except Exception as table_error:
                            continue
                
                return JsonResponse({
                    'success': True, 
                    'message': f'Database optimization completed. Optimized {len(optimized_tables)} tables.',
                    'action_performed': 'Database Optimization',
                    'details': {'optimized_tables': optimized_tables},
                    'timestamp': timezone.now().isoformat()
                })
            except Exception as db_error:
                return JsonResponse({
                    'success': False,
                    'message': f'Database optimization failed: {str(db_error)}'
                })
            
        elif action == 'collect_garbage':
            collected = gc.collect()
            return JsonResponse({
                'success': True, 
                'message': f'Garbage collection completed. Collected {collected} objects.',
                'action_performed': 'Garbage Collection',
                'details': {'objects_collected': collected},
                'timestamp': timezone.now().isoformat()
            })
            
        elif action == 'flush_sessions':
            if not confirm:
                return JsonResponse({
                    'success': False,
                    'requires_confirmation': True,
                    'message': 'This will log out all users by clearing session data. Continue?'
                })
            
            try:
                # Clear Django sessions
                from django.contrib.sessions.models import Session
                deleted_count = Session.objects.all().delete()[0]
                return JsonResponse({
                    'success': True,
                    'message': f'Flushed {deleted_count} active sessions.',
                    'action_performed': 'Session Flush',
                    'details': {'sessions_cleared': deleted_count},
                    'timestamp': timezone.now().isoformat()
                })
            except Exception as session_error:
                return JsonResponse({
                    'success': False,
                    'message': f'Session flush failed: {str(session_error)}'
                })
            
        else:
            return JsonResponse({
                'success': False, 
                'message': f'Unknown action: {action}',
                'available_actions': ['clear_cache', 'optimize_database', 'collect_garbage', 'flush_sessions']
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'message': f'Server action error: {str(e)}',
            'action_attempted': action,
            'timestamp': timezone.now().isoformat()
        })


@staff_member_required
def performance_api_view(request):
    """
    API endpoint for real-time performance data updates
    Returns JSON data for AJAX requests to update dashboard in real-time
    """
    try:
        # Get current metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        
        # Get disk usage for primary partition
        disk_percent = 0
        try:
            disk_percent = psutil.disk_usage('/').percent
        except:
            try:
                disk_percent = psutil.disk_usage('C:').percent  # Windows fallback
            except:
                disk_percent = 0
        
        # Get network stats
        network = psutil.net_io_counters()
        
        # Get database connection count
        db_connections = 0
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM information_schema.processlist")
                result = cursor.fetchone()
                db_connections = result[0] if result else 0
        except:
            db_connections = 0
        
        data = {
            'timestamp': timezone.now().isoformat(),
            'system_metrics': {
                'cpu_percent': round(cpu_percent, 1),
                'memory_percent': round(memory.percent, 1),
                'memory_used_gb': round(memory.used / (1024**3), 2),
                'disk_percent': round(disk_percent, 1),
                'network_bytes_sent': network.bytes_sent,
                'network_bytes_recv': network.bytes_recv
            },
            'application_metrics': {
                'active_tenants': Tenant.objects.filter(is_active=True).count(),
                'total_tenants': Tenant.objects.count(),
                'db_connections': db_connections
            },
            'health_status': {
                'cpu': 'optimal' if cpu_percent < 70 else 'warning' if cpu_percent < 90 else 'critical',
                'memory': 'optimal' if memory.percent < 70 else 'warning' if memory.percent < 90 else 'critical',
                'disk': 'optimal' if disk_percent < 70 else 'warning' if disk_percent < 90 else 'critical'
            }
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=500)


@staff_member_required
def system_logs_view(request):
    """
    View system logs and recent activities
    """
    try:
        # This would integrate with your logging system
        # For now, return sample data
        logs = [
            {
                'timestamp': timezone.now() - timedelta(minutes=i),
                'level': 'INFO' if i % 3 == 0 else 'WARNING' if i % 5 == 0 else 'ERROR',
                'message': f'Sample log message {i}',
                'source': 'system' if i % 2 == 0 else 'application'
            }
            for i in range(50)
        ]
        
        context = {
            'logs': logs,
            'log_levels': ['INFO', 'WARNING', 'ERROR'],
            'log_sources': ['system', 'application'],
            'current_time': timezone.now()
        }
        
        return render(request, 'system_admin/system_logs.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading system logs: {str(e)}")
        return render(request, 'system_admin/system_logs.html', {
            'error': str(e),
            'current_time': timezone.now()
        })