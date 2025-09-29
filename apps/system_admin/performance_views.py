"""
System Admin Performance Views
Comprehensive real-time monitoring for AutoWash platform
"""

import json
import time
import logging
import platform
import os
import socket
import subprocess
from datetime import datetime, timedelta
from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.core.cache import cache
from django.db import connection
from django.conf import settings

# Third party imports
import psutil

# Local imports
from apps.core.tenant_models import Tenant
from apps.accounts.models import User

logger = logging.getLogger(__name__)


# ==============================================================================
# REAL DATA COLLECTION FUNCTIONS
# ==============================================================================

def get_real_system_resources():
    """
    Collect actual system resource metrics using psutil
    Returns comprehensive system information with no sample data
    """
    try:
        # === CPU METRICS ===
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_freq = psutil.cpu_freq()
        cpu_info = {
            'usage_percent': round(cpu_percent, 1),
            'core_count': psutil.cpu_count(logical=False),
            'logical_cores': psutil.cpu_count(logical=True),
            'frequency_mhz': round(cpu_freq.current, 1) if cpu_freq else 0,
            'frequency_max': round(cpu_freq.max, 1) if cpu_freq else 0,
            'per_core_usage': psutil.cpu_percent(interval=0.1, percpu=True)[:8],  # Limit to 8 cores
            'load_average': list(os.getloadavg()) if hasattr(os, 'getloadavg') else [0, 0, 0],
            'status': 'optimal' if cpu_percent < 70 else 'warning' if cpu_percent < 90 else 'critical'
        }
        
        # === MEMORY METRICS ===
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        memory_info = {
            'total_gb': round(memory.total / (1024**3), 2),
            'available_gb': round(memory.available / (1024**3), 2),
            'used_gb': round(memory.used / (1024**3), 2),
            'usage_percent': round(memory.percent, 1),
            'cached_gb': round(memory.cached / (1024**3), 2) if hasattr(memory, 'cached') else 0,
            'buffers_gb': round(memory.buffers / (1024**3), 2) if hasattr(memory, 'buffers') else 0,
            'swap_total_gb': round(swap.total / (1024**3), 2),
            'swap_used_gb': round(swap.used / (1024**3), 2),
            'swap_percent': round(swap.percent, 1),
            'status': 'optimal' if memory.percent < 70 else 'warning' if memory.percent < 90 else 'critical'
        }
        
        # === DISK METRICS ===
        disk_info = []
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                if usage.total == 0:
                    continue
                    
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
        network_info = {
            'bytes_sent': network.bytes_sent,
            'bytes_recv': network.bytes_recv,
            'packets_sent': network.packets_sent,
            'packets_recv': network.packets_recv,
            'errors_in': network.errin,
            'errors_out': network.errout,
            'drops_in': network.dropin,
            'drops_out': network.dropout,
            'status': 'optimal' if (network.errin + network.errout) < 100 else 'warning'
        }
        
        # === SYSTEM UPTIME ===
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime_seconds = (datetime.now() - boot_time).total_seconds()
        uptime_str = str(timedelta(seconds=int(uptime_seconds)))
        
        return {
            'cpu': cpu_info,
            'memory': memory_info,
            'disk': disk_info,
            'network': network_info,
            'uptime_formatted': uptime_str,
            'boot_time': boot_time.strftime('%Y-%m-%d %H:%M:%S'),
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error collecting system resources: {e}")
        return {
            'cpu': {'usage_percent': 0, 'core_count': 0, 'status': 'error'},
            'memory': {'usage_percent': 0, 'total_gb': 0, 'status': 'error'},
            'disk': [],
            'network': {'bytes_sent': 0, 'bytes_recv': 0, 'status': 'error'},
            'uptime_formatted': 'Unknown',
            'boot_time': 'Unknown',
            'error': str(e)
        }


def get_comprehensive_logs(hours=24):
    """
    Read all configured log files from the Django logging system
    Returns logs from system, error, performance, business, security, and tenant logs
    """
    all_logs = []
    cutoff_time = timezone.now() - timedelta(hours=hours)
    
    # Get log files from Django LOGGING configuration
    log_files = {}
    
    # Extract log file paths from Django settings
    if hasattr(settings, 'LOGGING') and 'handlers' in settings.LOGGING:
        handlers = settings.LOGGING['handlers']
        for handler_name, handler_config in handlers.items():
            if 'filename' in handler_config:
                filename = handler_config['filename']
                # Convert Path objects to strings if needed
                if hasattr(filename, '__fspath__'):
                    filename = str(filename)
                log_files[handler_name] = filename
    
    # Fallback to default paths if LOGGING not properly configured
    if not log_files:
        log_files = {
            'django': os.path.join(settings.BASE_DIR, 'logs', 'django.log'),
            'errors': os.path.join(settings.BASE_DIR, 'reports', 'error_tracking', 'application_errors.log'),
            'performance': os.path.join(settings.BASE_DIR, 'reports', 'performance_metrics', 'performance.log'),
            'business': os.path.join(settings.BASE_DIR, 'reports', 'business_analytics', 'business_events.log'),
            'security': os.path.join(settings.BASE_DIR, 'reports', 'security_logs', 'security_events.log'),
            'tenant_activity': os.path.join(settings.BASE_DIR, 'reports', 'tenant_activity', 'tenant_actions.log'),
            'user_logins': os.path.join(settings.BASE_DIR, 'reports', 'user_logins', 'login_attempts.log'),
        }
    
    for log_type, log_path in log_files.items():
        try:
            if os.path.exists(log_path):
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                
                # Process recent lines (last 50 per file for performance)
                for line in lines[-50:]:
                    line = line.strip()
                    if line:
                        # Parse log entry with improved parsing
                        log_entry = parse_log_line(line, log_type)
                        if log_entry:
                            all_logs.append(log_entry)
            else:
                # Log file doesn't exist, add informational entry
                all_logs.append({
                    'timestamp': timezone.now(),
                    'level': 'INFO',
                    'message': f'{log_type.title()} log file not found: {log_path}',
                    'source': log_type,
                    'category': log_type
                })
                
        except Exception as e:
            logger.warning(f"Error reading {log_type} logs: {e}")
            all_logs.append({
                'timestamp': timezone.now(),
                'level': 'WARNING',
                'message': f'Error reading {log_type} log file: {str(e)}',
                'source': log_type,
                'category': 'system_error'
            })
    
    # Sort by timestamp (most recent first) and limit results
    all_logs.sort(key=lambda x: x['timestamp'], reverse=True)
    return all_logs[:100]  # Return last 100 entries across all logs


def parse_log_line(line, log_type):
    """
    Parse a log line based on the log type and format
    Returns a structured log entry dictionary
    """
    import re
    from datetime import datetime
    
    try:
        # Try to extract timestamp from the log line
        timestamp = timezone.now()  # Default to current time
        
        # Common Django log format: "LEVEL YYYY-MM-DD HH:MM:SS,mmm module ..."
        django_pattern = r'(\w+)\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d+)?)'
        match = re.match(django_pattern, line)
        
        if match:
            level = match.group(1)
            timestamp_str = match.group(2).replace(',', '.')  # Handle milliseconds
            try:
                # Parse timestamp
                if '.' in timestamp_str:
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S.%f')
                else:
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                timestamp = timezone.make_aware(timestamp)
            except ValueError:
                pass  # Keep default timestamp if parsing fails
            
            return {
                'timestamp': timestamp,
                'level': level,
                'message': line[match.end():].strip()[:500],  # Message after timestamp
                'source': 'django' if log_type == 'file' else log_type,
                'category': 'django',
                'logger': log_type,
                'name': 'django'
            }
        
        # Detailed format with pipes (|)
        elif '|' in line:
            parts = line.split('|', 4)
            if len(parts) >= 4:
                # Try to parse timestamp from first part
                try:
                    timestamp_str = parts[0].strip()
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    if timezone.is_naive(timestamp):
                        timestamp = timezone.make_aware(timestamp)
                except (ValueError, AttributeError):
                    pass
                
                return {
                    'timestamp': timestamp,
                    'level': parts[1].strip() if len(parts) > 1 else 'INFO',
                    'logger': parts[2].strip() if len(parts) > 2 else log_type,
                    'function': parts[3].strip() if len(parts) > 3 else 'unknown',
                    'message': parts[4].strip()[:500] if len(parts) > 4 else line[:500],
                    'source': log_type,
                    'category': log_type,
                    'name': log_type
                }
        
        # Fallback: Extract level and use whole line as message
        else:
            level = 'INFO'
            for lvl in ['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG']:
                if lvl in line.upper():
                    level = lvl
                    break
            
            return {
                'timestamp': timestamp,
                'level': level,
                'message': line[:500],  # Limit message length
                'source': 'django' if log_type == 'file' else log_type,
                'category': 'django' if log_type == 'file' else log_type,
                'logger': log_type,
                'name': log_type
            }
            
    except Exception as e:
        return {
            'timestamp': timezone.now(),
            'level': 'ERROR',
            'message': f'Error parsing log line: {str(e)}',
            'source': log_type,
            'category': 'parse_error',
            'logger': 'parser',
            'name': 'parser'
        }


def get_django_logs(hours=24):
    """
    Legacy function for backward compatibility
    Now uses the comprehensive logs function
    """
    all_logs = get_comprehensive_logs(hours)
    # Filter for django logs only
    django_logs = [log for log in all_logs if log.get('source') == 'django']
    return django_logs[:50]


def get_tenant_query_stats():
    """
    Get actual tenant database statistics and query analytics
    Returns real tenant data with no sample information
    """
    try:
        # === BASIC TENANT COUNTS ===
        total_tenants = Tenant.objects.count()
        active_tenants = Tenant.objects.filter(is_active=True).count()
        suspended_tenants = Tenant.objects.filter(is_active=False).count()
        
        # === TIME-BASED ANALYTICS ===
        now = timezone.now()
        recent_signups_24h = Tenant.objects.filter(created_at__gte=now - timedelta(hours=24)).count()
        recent_signups_7d = Tenant.objects.filter(created_at__gte=now - timedelta(days=7)).count()
        recent_signups_30d = Tenant.objects.filter(created_at__gte=now - timedelta(days=30)).count()
        
        # === TENANT ACTIVITY ===
        active_today = Tenant.objects.filter(
            is_active=True,
            updated_at__gte=now - timedelta(hours=24)
        ).count()
        
        return {
            'total_tenants': total_tenants,
            'active_tenants': active_tenants,
            'suspended_tenants': suspended_tenants,
            'recent_signups_24h': recent_signups_24h,
            'recent_signups_7d': recent_signups_7d,
            'recent_signups_30d': recent_signups_30d,
            'active_today': active_today,
            'activity_rate': round((active_today / max(active_tenants, 1)) * 100, 1),
            'last_updated': now.strftime('%Y-%m-%d %H:%M:%S')
        }
        
    except Exception as e:
        logger.error(f"Error getting tenant stats: {e}")
        return {
            'total_tenants': 0,
            'active_tenants': 0,
            'suspended_tenants': 0,
            'recent_signups_24h': 0,
            'recent_signups_7d': 0,
            'recent_signups_30d': 0,
            'active_today': 0,
            'activity_rate': 0,
            'error': str(e)
        }


def get_user_session_analytics():
    """
    Get actual user session data and authentication analytics
    Returns real user activity metrics
    """
    try:
        from django.contrib.sessions.models import Session
        
        now = timezone.now()
        
        # === SESSION ANALYTICS ===
        total_sessions = Session.objects.count()
        active_sessions = Session.objects.filter(expire_date__gt=now).count()
        expired_sessions = total_sessions - active_sessions
        
        # === USER ANALYTICS ===
        total_users = User.objects.count()
        active_users_24h = User.objects.filter(last_login__gte=now - timedelta(hours=24)).count()
        active_users_7d = User.objects.filter(last_login__gte=now - timedelta(days=7)).count()
        new_users_24h = User.objects.filter(date_joined__gte=now - timedelta(hours=24)).count()
        
        # === TENANT ANALYTICS ===
        total_tenants = Tenant.objects.count()
        active_tenants = Tenant.objects.filter(is_active=True).count()
        inactive_tenants = total_tenants - active_tenants
        active_tenants_today = Tenant.objects.filter(
            is_active=True,
            updated_at__gte=now - timedelta(hours=24)
        ).count()
        
        return {
            'total_sessions': total_sessions,
            'active_sessions': active_sessions,
            'expired_sessions': expired_sessions,
            'total_users': total_users,
            'recent_user_activity': active_users_24h,
            'weekly_active_users': active_users_7d,
            'new_users_24h': new_users_24h,
            'total_tenants': total_tenants,
            'active_tenants': active_tenants,
            'inactive_tenants': inactive_tenants,
            'active_tenants_today': active_tenants_today,
            'user_session_ratio': round((active_sessions / max(total_users, 1)), 2),
            'last_updated': now.strftime('%Y-%m-%d %H:%M:%S')
        }
        
    except Exception as e:
        logger.error(f"Error getting user session analytics: {e}")
        return {
            'total_sessions': 0,
            'active_sessions': 0,
            'total_users': 0,
            'recent_user_activity': 0,
            'total_tenants': 0,
            'active_tenants': 0,
            'inactive_tenants': 0,
            'active_tenants_today': 0,
            'error': str(e)
        }


def get_ip_geolocation_data():
    """
    Get actual IP address and geolocation information from system interfaces
    Returns real network interface and location data
    """
    ip_data = []
    try:
        # === NETWORK INTERFACES ===
        for interface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET:  # IPv4
                    ip_info = {
                        'interface': interface,
                        'ip': addr.address,
                        'netmask': addr.netmask,
                        'broadcast': addr.broadcast,
                        'family': 'IPv4',
                        'city': 'Local Network',
                        'country': 'Local',
                        'is_private': addr.address.startswith(('192.168.', '10.', '172.')) or addr.address == '127.0.0.1'
                    }
                    
                    # Add basic location info for public IPs
                    if not ip_info['is_private']:
                        ip_info['city'] = 'Unknown'
                        ip_info['country'] = 'Unknown'
                        # In production, you could integrate with a geolocation API here
                    
                    ip_data.append(ip_info)
        
        # === SYSTEM HOSTNAME AND EXTERNAL INFO ===
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            
            ip_data.append({
                'interface': 'system',
                'ip': local_ip,
                'hostname': hostname,
                'family': 'System',
                'city': 'System Network',
                'country': 'Local',
                'is_private': True
            })
            
        except Exception:
            pass
            
    except Exception as e:
        logger.error(f"Error getting IP geolocation data: {e}")
        ip_data.append({
            'interface': 'error',
            'ip': '127.0.0.1',
            'error': str(e),
            'family': 'Error',
            'city': 'Unknown',
            'country': 'Unknown'
        })
    
    return ip_data[:10]  # Limit to 10 entries


def get_query_performance_metrics():
    """
    Get actual database performance metrics and query statistics
    Returns real database performance data
    """
    try:
        with connection.cursor() as cursor:
            metrics = {}
            
            # === CONNECTION STATISTICS ===
            try:
                cursor.execute("SHOW STATUS LIKE 'Threads_connected'")
                result = cursor.fetchone()
                current_connections = int(result[1]) if result else 0
                
                cursor.execute("SHOW STATUS LIKE 'Threads_running'")
                result = cursor.fetchone()
                running_connections = int(result[1]) if result else 0
                
                cursor.execute("SHOW STATUS LIKE 'Max_used_connections'")
                result = cursor.fetchone()
                max_used_connections = int(result[1]) if result else 0
                
                cursor.execute("SHOW VARIABLES LIKE 'max_connections'")
                result = cursor.fetchone()
                max_connections = int(result[1]) if result else 0
                
                metrics['connection_stats'] = {
                    'current_connections': current_connections,
                    'running_connections': running_connections,
                    'max_used_connections': max_used_connections,
                    'max_connections': max_connections,
                    'connection_usage_percent': round((current_connections / max(max_connections, 1)) * 100, 2)
                }
            except Exception as e:
                logger.warning(f"Could not get connection stats: {e}")
                metrics['connection_stats'] = {'current_connections': 0, 'error': str(e)}
            
            # === QUERY STATISTICS ===
            try:
                cursor.execute("SHOW STATUS LIKE 'Questions'")
                result = cursor.fetchone()
                total_queries = int(result[1]) if result else 0
                
                cursor.execute("SHOW STATUS LIKE 'Slow_queries'")
                result = cursor.fetchone()
                slow_queries_count = int(result[1]) if result else 0
                
                cursor.execute("SHOW STATUS LIKE 'Uptime'")
                result = cursor.fetchone()
                uptime_seconds = int(result[1]) if result else 1
                
                queries_per_second = round(total_queries / max(uptime_seconds, 1), 2)
                
                metrics.update({
                    'total_queries': total_queries,
                    'slow_queries_count': slow_queries_count,
                    'queries_per_second': queries_per_second,
                    'uptime_seconds': uptime_seconds,
                    'slow_query_ratio': round((slow_queries_count / max(total_queries, 1)) * 100, 4)
                })
            except Exception as e:
                logger.warning(f"Could not get query stats: {e}")
                metrics.update({'total_queries': 0, 'queries_per_second': 0, 'error': str(e)})
            
            # === SCHEMA STATISTICS ===
            try:
                cursor.execute("""
                    SELECT table_schema, COUNT(*) as table_count, 
                           ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS 'size_mb'
                    FROM information_schema.tables 
                    WHERE table_schema NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
                    GROUP BY table_schema
                    ORDER BY size_mb DESC
                    LIMIT 5
                """)
                
                schema_stats = []
                for row in cursor.fetchall():
                    schema_stats.append({
                        'schema_name': row[0],
                        'table_count': row[1],
                        'size_mb': row[2]
                    })
                
                metrics['schema_statistics'] = schema_stats
            except Exception as e:
                logger.warning(f"Could not get schema stats: {e}")
                metrics['schema_statistics'] = []
            
            return metrics
            
    except Exception as e:
        logger.error(f"Error getting query performance metrics: {e}")
        return {
            'connection_stats': {'current_connections': 0},
            'total_queries': 0,
            'queries_per_second': 0,
            'slow_queries_count': 0,
            'schema_statistics': [],
            'error': str(e)
        }


def get_main_database_auth_metrics():
    """
    Get authentication and main default database specific metrics
    Returns detailed stats about user access, authentication patterns, and main DB performance
    """
    try:
        auth_metrics = {}
        
        # === AUTHENTICATION STATISTICS ===
        from django.contrib.auth.models import User
        from django.contrib.sessions.models import Session
        from apps.accounts.models import User as CustomUser
        
        # Get active sessions (authenticated users currently accessing)
        active_sessions = Session.objects.filter(expire_date__gte=timezone.now()).count()
        
        # Get user statistics
        total_users = CustomUser.objects.count()
        active_users_today = CustomUser.objects.filter(
            last_login__gte=timezone.now() - timedelta(days=1)
        ).count()
        
        recent_signups = CustomUser.objects.filter(
            date_joined__gte=timezone.now() - timedelta(days=7)
        ).count()
        
        # Get staff and superuser counts
        staff_users = CustomUser.objects.filter(is_staff=True).count()
        superusers = CustomUser.objects.filter(is_superuser=True).count()
        
        auth_metrics['authentication_stats'] = {
            'active_sessions': active_sessions,
            'total_users': total_users,
            'active_users_24h': active_users_today,
            'recent_signups_7d': recent_signups,
            'staff_users': staff_users,
            'superusers': superusers,
            'session_to_user_ratio': round(active_sessions / max(total_users, 1) * 100, 2)
        }
        
        # === MAIN DATABASE CONNECTION STATS ===
        with connection.cursor() as cursor:
            try:
                # Get main database size and table stats
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_tables,
                        ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) as total_size_mb,
                        SUM(table_rows) as total_rows
                    FROM information_schema.tables 
                    WHERE table_schema = DATABASE()
                """)
                
                result = cursor.fetchone()
                if result:
                    auth_metrics['main_db_stats'] = {
                        'total_tables': result[0],
                        'total_size_mb': result[1],
                        'total_rows': result[2],
                        'database_name': settings.DATABASES['default']['NAME']
                    }
                
                # Get authentication-related table stats
                cursor.execute("""
                    SELECT table_name, table_rows, 
                           ROUND((data_length + index_length) / 1024 / 1024, 2) as size_mb
                    FROM information_schema.tables 
                    WHERE table_schema = DATABASE() 
                    AND (table_name LIKE '%user%' OR table_name LIKE '%session%' OR 
                         table_name LIKE '%auth%' OR table_name LIKE '%account%')
                    ORDER BY table_rows DESC
                    LIMIT 10
                """)
                
                auth_tables = []
                for row in cursor.fetchall():
                    auth_tables.append({
                        'table_name': row[0],
                        'row_count': row[1],
                        'size_mb': row[2]
                    })
                
                auth_metrics['auth_tables'] = auth_tables
                
            except Exception as e:
                logger.warning(f"Could not get main DB stats: {e}")
                auth_metrics['main_db_stats'] = {'error': str(e)}
                auth_metrics['auth_tables'] = []
        
        # === RECENT LOGIN PATTERNS ===
        try:
            # Get login patterns for last 24 hours
            recent_logins = CustomUser.objects.filter(
                last_login__gte=timezone.now() - timedelta(hours=24)
            ).values('last_login').order_by('-last_login')[:50]
            
            # Group by hour for pattern analysis
            login_by_hour = {}
            for login in recent_logins:
                if login['last_login']:
                    hour = login['last_login'].hour
                    login_by_hour[hour] = login_by_hour.get(hour, 0) + 1
            
            auth_metrics['login_patterns'] = {
                'recent_logins_24h': len(recent_logins),
                'login_by_hour': login_by_hour,
                'peak_hour': max(login_by_hour, key=login_by_hour.get) if login_by_hour else 0
            }
            
        except Exception as e:
            logger.warning(f"Could not get login patterns: {e}")
            auth_metrics['login_patterns'] = {'error': str(e)}
        
        return auth_metrics
        
    except Exception as e:
        logger.error(f"Error getting main database auth metrics: {e}")
        return {
            'authentication_stats': {'active_sessions': 0, 'total_users': 0, 'error': str(e)},
            'main_db_stats': {'error': str(e)},
            'auth_tables': [],
            'login_patterns': {'error': str(e)}
        }


def get_actual_application_errors():
    """
    Get actual application errors from logs and system monitoring
    Returns real error tracking data
    """
    errors = []
    try:
        # === DJANGO ERROR LOG ===
        error_log_path = os.path.join(settings.BASE_DIR, 'logs', 'django.log')
        if os.path.exists(error_log_path):
            try:
                with open(error_log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                
                # Look for ERROR and WARNING entries in recent logs
                for line in lines[-100:]:  # Check last 100 lines
                    line = line.strip()
                    if 'ERROR' in line or 'WARNING' in line:
                        level = 'ERROR' if 'ERROR' in line else 'WARNING'
                        errors.append({
                            'timestamp': timezone.now(),
                            'level': level,
                            'message': line[:300],  # Limit message length
                            'source': 'django_log'
                        })
            except Exception as e:
                errors.append({
                    'timestamp': timezone.now(),
                    'level': 'ERROR',
                    'message': f'Error reading error log: {str(e)}',
                    'source': 'log_reader'
                })
        
        # === SYSTEM ERROR INDICATORS ===
        system_resources = get_real_system_resources()
        
        # Check for system resource warnings
        if system_resources['cpu']['usage_percent'] > 90:
            errors.append({
                'timestamp': timezone.now(),
                'level': 'WARNING',
                'message': f'High CPU usage detected: {system_resources["cpu"]["usage_percent"]}%',
                'source': 'system_monitor'
            })
        
        if system_resources['memory']['usage_percent'] > 90:
            errors.append({
                'timestamp': timezone.now(),
                'level': 'WARNING',
                'message': f'High memory usage detected: {system_resources["memory"]["usage_percent"]}%',
                'source': 'system_monitor'
            })
        
        # === DATABASE ERROR CHECK ===
        try:
            query_metrics = get_query_performance_metrics()
            if query_metrics.get('slow_queries_count', 0) > 50:
                errors.append({
                    'timestamp': timezone.now(),
                    'level': 'WARNING',
                    'message': f'High number of slow queries: {query_metrics["slow_queries_count"]}',
                    'source': 'database_monitor'
                })
        except Exception:
            pass
        
        # If no errors found, add status message
        if not errors:
            errors.append({
                'timestamp': timezone.now(),
                'level': 'INFO',
                'message': 'No critical application errors detected in recent monitoring',
                'source': 'system_monitor'
            })
            
    except Exception as e:
        errors.append({
            'timestamp': timezone.now(),
            'level': 'ERROR',
            'message': f'Error collecting application errors: {str(e)}',
            'source': 'error_collector'
        })
    
    return errors[-25:]  # Return last 25 errors


# ==============================================================================
# MAIN PERFORMANCE MONITORING VIEW
# ==============================================================================

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
        comprehensive_logs = get_comprehensive_logs(hours=24)
        django_logs = [log for log in comprehensive_logs if log.get('source') == 'django']
        application_errors = get_actual_application_errors()
        tenant_analytics = get_tenant_query_stats()
        user_analytics = get_user_session_analytics()
        ip_location_data = get_ip_geolocation_data()
        query_metrics = get_query_performance_metrics()
        main_db_auth_metrics = get_main_database_auth_metrics()
        
        # === SYSTEM INFORMATION ===
        system_info = {
            'hostname': platform.node(),
            'platform': f"{platform.system()} {platform.release()}",
            'architecture': platform.machine(),
            'python_version': platform.python_version(),
            'django_version': getattr(__import__('django'), 'VERSION', 'Unknown'),
            'timezone': str(timezone.get_current_timezone()),
            'current_time_str': current_time.strftime('%Y-%m-%d %H:%M:%S %Z'),
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
        
        # === PERFORMANCE LOGS (COMPREHENSIVE DATA) ===
        performance_logs = []
        # Use comprehensive logs - all system logs
        performance_logs.extend(comprehensive_logs[:50])  # Latest 50 comprehensive logs
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
            'comprehensive_logs': comprehensive_logs,
            'application_errors': application_errors,
            'django_logs': django_logs,
            'query_metrics': query_metrics,
            'main_db_auth_metrics': main_db_auth_metrics,
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
                'timezone': str(timezone.get_current_timezone())
            })
        }
        
        return render(request, 'system_admin/performance_monitoring.html', context)
        
    except Exception as e:
        logger.error(f"Error in performance monitoring view: {e}")
        
        # Return comprehensive error context with all required variables
        error_context = {
            'title': 'AutoWash Control Panel - System Error',
            'error': str(e),
            'current_time': timezone.now(),
            'overall_status': 'critical',
            'system_info': {
                'hostname': platform.node(),
                'platform': platform.system(),
                'uptime': 'Error retrieving uptime',
                'error_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S %Z'),
                'error_message': str(e)
            },
            'cpu_info': {'usage_percent': 0, 'core_count': 0, 'logical_cores': 0, 'frequency_mhz': 0},
            'memory_info': {'usage_percent': 0, 'used_gb': 0, 'available_gb': 0, 'total_gb': 0},
            'disk_info': [],
            'network_info': {'total_bytes_sent': 0, 'total_bytes_recv': 0, 'errors_in': 0, 'errors_out': 0, 'status': 'unknown'},
            'database_stats': {'active_connections': 0, 'total_queries': 0, 'slow_queries': 0, 'queries_per_second': 0, 'uptime_seconds': 0, 'status': 'error'},
            'tenant_stats': {'total_tenants': 0, 'active_tenants': 0, 'inactive_tenants': 0, 'recent_activity_24h': 0},
            'session_stats': {'active_sessions': 0, 'total_users': 0, 'recent_user_activity': 0, 'last_updated': 'Unknown'},
            'cache_stats': {'status': 'error', 'hit_rate': 0, 'miss_rate': 0},
            'health_indicators': {'cpu': 'critical', 'memory': 'critical', 'database': 'critical', 'cache': 'critical', 'network': 'critical'},
            'performance_logs': [],
            'application_errors': [],
            'django_logs': [],
            'query_metrics': {},
            'ip_location_data': [],
            'performance_data': json.dumps({
                'error': str(e),
                'timestamp': timezone.now().isoformat(),
                'system_metrics': {'cpu_percent': 0, 'memory_percent': 0, 'disk_usage': [], 'network_errors': 0},
                'application_metrics': {'active_tenants': 0, 'db_connections': 0, 'active_sessions': 0, 'queries_per_second': 0},
                'health_status': {'cpu': 'critical', 'memory': 'critical', 'database': 'critical', 'cache': 'critical', 'network': 'critical'}
            })
        }
        
        return render(request, 'system_admin/performance_monitoring.html', error_context)


# ==============================================================================
# AJAX API ENDPOINT FOR REAL-TIME UPDATES
# ==============================================================================

@staff_member_required
def performance_api_view(request):
    """
    API endpoint for real-time performance data updates
    Returns actual system metrics in JSON format
    """
    try:
        current_time = timezone.now()
        system_resources = get_real_system_resources()
        query_metrics = get_query_performance_metrics()
        user_analytics = get_user_session_analytics()
        django_logs = get_django_logs(hours=24)  # Get fresh Django logs
        main_db_auth_metrics = get_main_database_auth_metrics()  # Get auth metrics
        
        data = {
            'timestamp': current_time.isoformat(),
            'system_metrics': {
                'cpu_percent': system_resources.get('cpu', {}).get('usage_percent', 0),
                'memory_percent': system_resources.get('memory', {}).get('usage_percent', 0),
                'memory_used_gb': system_resources.get('memory', {}).get('used_gb', 0),
                'disk_usage': [d.get('usage_percent', 0) for d in system_resources.get('disk', [])],
                'network_bytes_sent': system_resources.get('network', {}).get('bytes_sent', 0),
                'network_bytes_recv': system_resources.get('network', {}).get('bytes_recv', 0)
            },
            'application_metrics': {
                'active_tenants': user_analytics.get('active_tenants', 0),
                'total_tenants': user_analytics.get('total_tenants', 0),
                'db_connections': query_metrics.get('connection_stats', {}).get('current_connections', 0),
                'active_sessions': user_analytics.get('active_sessions', 0),
                'queries_per_second': query_metrics.get('queries_per_second', 0)
            },
            'health_status': {
                'cpu': 'optimal' if system_resources.get('cpu', {}).get('usage_percent', 0) < 70 else 'warning' if system_resources.get('cpu', {}).get('usage_percent', 0) < 90 else 'critical',
                'memory': 'optimal' if system_resources.get('memory', {}).get('usage_percent', 0) < 70 else 'warning' if system_resources.get('memory', {}).get('usage_percent', 0) < 90 else 'critical',
                'database': 'optimal' if query_metrics.get('slow_queries_count', 0) < 10 else 'warning'
            },
            'django_logs': django_logs,  # Include fresh Django logs
            'main_db_auth_metrics': main_db_auth_metrics  # Include auth metrics
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=500)


@staff_member_required
def server_action_view(request):
    """Handle server actions like restart, clear cache, etc."""
    if request.method == 'POST':
        action = request.POST.get('action')
        
        try:
            if action == 'clear_cache':
                cache.clear()
                messages.success(request, 'Cache cleared successfully')
            elif action == 'restart_server':
                # Note: This would require proper deployment setup
                messages.info(request, 'Server restart requested - contact system administrator')
            elif action == 'refresh_data':
                # Force refresh of cached data
                cache.delete_many([
                    'system_resources',
                    'django_logs',
                    'tenant_stats',
                    'user_sessions',
                    'application_errors'
                ])
                messages.success(request, 'Data refreshed successfully')
            else:
                messages.error(request, 'Unknown action requested')
                
        except Exception as e:
            logger.error(f"Error in server action {action}: {str(e)}")
            messages.error(request, f'Error performing action: {str(e)}')
    
    return redirect('system_admin:performance_monitoring')