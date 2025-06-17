"""
Environment utilities for multi-environment Django application
Located in apps.core for easy importing across the project
Supports Local, Render, and cPanel environments
"""
from django.conf import settings


def get_current_environment():
    """
    Detect the current environment based on settings
    Returns: 'local', 'render', or 'cpanel'
    """
    if getattr(settings, 'RENDER', False):
        return 'render'
    elif getattr(settings, 'CPANEL', False):
        return 'cpanel'
    else:
        return 'local'


def get_base_url(environment=None):
    """
    Get the base URL for the current environment
    """
    if environment is None:
        environment = get_current_environment()
    
    if environment == 'local':
        return 'http://localhost:8000'
    elif environment == 'render':
        return 'https://autowash-3jpr.onrender.com'
    elif environment == 'cpanel':
        return 'https://app.autowash.co.ke'
    else:
        return 'http://localhost:8000'  # fallback


def get_domain_for_environment(business_slug, environment=None):
    """
    Get domain name based on environment for path-based routing
    This is used for Domain model records
    """
    if environment is None:
        environment = get_current_environment()
        
    if environment == 'local':
        # Local development
        return f'{business_slug}.path-based.localhost'
    elif environment == 'render':
        # Render production
        return f'{business_slug}.path-based.autowash'
    elif environment == 'cpanel':
        # cPanel production
        return f'{business_slug}.path-based.cpanel'
    else:
        # Fallback
        return f'{business_slug}.path-based.default'


def get_business_url(business_slug, environment=None):
    """
    Get the full business URL for path-based routing
    This is the actual URL users will access
    """
    if environment is None:
        environment = get_current_environment()
    
    base_url = get_base_url(environment)
    return f'{base_url}/business/{business_slug}/'


def get_admin_url(environment=None):
    """
    Get the admin URL for the current environment
    """
    if environment is None:
        environment = get_current_environment()
    
    base_url = get_base_url(environment)
    return f'{base_url}/admin/'


def get_success_message(business, environment=None):
    """
    Get environment-specific success message for business registration
    """
    if environment is None:
        environment = get_current_environment()
        
    base_message = f'Business "{business.name}" registered successfully!'
    business_url = get_business_url(business.slug, environment)
    
    return (
        f'{base_message} '
        f'Once approved, access your business at: {business_url} '
        f'Please upload verification documents for admin review.'
    )


def get_error_message(error_str, environment=None):
    """
    Get environment-specific error message
    """
    if environment is None:
        environment = get_current_environment()
        
    base_message = f'Registration failed: {error_str}'
    
    if environment == 'cpanel':
        if 'permission' in error_str.lower():
            return (
                f'{base_message} '
                f'This may be a cPanel file permission issue. Please contact support if the problem persists.'
            )
        elif 'database' in error_str.lower():
            return (
                f'{base_message} '
                f'Database connection issue. Please check your cPanel database configuration.'
            )
    elif environment == 'render':
        if 'timeout' in error_str.lower():
            return (
                f'{base_message} '
                f'This may be a temporary Render service issue. Please try again in a few moments.'
            )
        elif 'memory' in error_str.lower():
            return (
                f'{base_message} '
                f'Render memory limit reached. Please try again or contact support.'
            )
    elif environment == 'local':
        if 'database' in error_str.lower():
            return (
                f'{base_message} '
                f'Please ensure your local database is running and properly configured.'
            )
        elif 'redis' in error_str.lower():
            return (
                f'{base_message} '
                f'Redis connection issue. Please check if Redis is running locally.'
            )
    
    return base_message


def get_environment_context():
    """
    Get environment context for templates
    """
    environment = get_current_environment()
    
    return {
        'environment': environment,
        'environment_display': environment.upper(),
        'base_url': get_base_url(environment),
        'admin_url': get_admin_url(environment),
        'is_local': environment == 'local',
        'is_render': environment == 'render',
        'is_cpanel': environment == 'cpanel',
        'is_production': environment in ['render', 'cpanel'],
        'debug_mode': getattr(settings, 'DEBUG', False),
    }


def get_deployment_info():
    """
    Get deployment information for the current environment
    """
    environment = get_current_environment()
    context = get_environment_context()
    
    info = {
        'environment': environment,
        'base_url': context['base_url'],
        'admin_url': context['admin_url'],
        'debug_mode': context['debug_mode'],
    }
    
    if environment == 'local':
        info.update({
            'title': 'LOCAL DEVELOPMENT',
            'icon': '🏠',
            'description': 'Running in local development mode',
            'features': [
                'Debug mode enabled',
                'Local database',
                'Gmail SMTP for emails',
                'Sandbox M-Pesa',
                'Relaxed security settings'
            ]
        })
    elif environment == 'render':
        info.update({
            'title': 'RENDER PRODUCTION',
            'icon': '🚀',
            'description': 'Running on Render cloud platform',
            'features': [
                'Production database (PostgreSQL)',
                'Domain email configuration',
                'Production M-Pesa',
                'WhiteNoise static files',
                'Redis caching (if configured)'
            ]
        })
    elif environment == 'cpanel':
        info.update({
            'title': 'CPANEL HOSTING',
            'icon': '🏢',
            'description': 'Running on cPanel shared hosting',
            'features': [
                'cPanel managed database',
                'Domain email configuration',
                'Production M-Pesa',
                'Apache/Nginx static files',
                'External Redis (if configured)'
            ]
        })
    
    return info


def format_business_access_info(business, environment=None):
    """
    Format business access information for display
    """
    if environment is None:
        environment = get_current_environment()
    
    business_url = get_business_url(business.slug, environment)
    base_url = get_base_url(environment)
    admin_url = get_admin_url(environment)
    
    return {
        'business_name': business.name,
        'business_slug': business.slug,
        'business_url': business_url,
        'environment': environment.upper(),
        'main_site': base_url,
        'admin_url': admin_url,
        'is_verified': business.is_verified,
        'status': 'Active' if business.is_verified else 'Pending Verification'
    }


def get_verification_instructions(environment=None):
    """
    Get environment-specific verification instructions
    """
    if environment is None:
        environment = get_current_environment()
    
    base_instructions = [
        "Upload your business registration documents",
        "Provide valid business license or permit", 
        "Include business owner ID verification",
        "Wait for admin review and approval"
    ]
    
    if environment == 'cpanel':
        base_instructions.extend([
            "cPanel hosting: Check email for approval notifications",
            "Contact support if approval takes longer than 48 hours"
        ])
    elif environment == 'render':
        base_instructions.extend([
            "Render hosting: Notifications sent to registered email",
            "Check application logs for any deployment issues"
        ])
    elif environment == 'local':
        base_instructions.extend([
            "Local development: Use admin panel for quick approval",
            "Access admin at: http://localhost:8000/admin/"
        ])
    
    return base_instructions


def get_post_approval_steps(business, environment=None):
    """
    Get steps to follow after business approval
    """
    if environment is None:
        environment = get_current_environment()
    
    business_url = get_business_url(business.slug, environment)
    
    steps = [
        f"Access your business dashboard at: {business_url}",
        "Complete your business profile setup",
        "Add employees and assign roles",
        "Configure your services and pricing",
        "Set up customer management",
        "Start accepting bookings and payments"
    ]
    
    if environment == 'cpanel':
        steps.append("Monitor cPanel resource usage for optimal performance")
    elif environment == 'render':
        steps.append("Monitor Render deployment logs for any issues")
    
    return steps


# Environment-specific configurations
ENVIRONMENT_CONFIGS = {
    'local': {
        'name': 'Local Development',
        'icon': '🏠',
        'domains': {
            'main': 'localhost:8000',
            'admin': 'localhost:8000/admin/',
            'pattern': '{slug}.path-based.localhost'
        },
        'features': {
            'debug': True,
            'ssl': False,
            'redis': 'optional',
            'email': 'gmail_smtp',
            'mpesa': 'sandbox',
            'database': 'local_postgresql'
        }
    },
    'render': {
        'name': 'Render Production',
        'icon': '🚀',
        'domains': {
            'main': 'autowash-3jpr.onrender.com',
            'admin': 'autowash-3jpr.onrender.com/admin/',
            'pattern': '{slug}.path-based.autowash'
        },
        'features': {
            'debug': False,
            'ssl': True,
            'redis': 'render_redis',
            'email': 'domain_smtp',
            'mpesa': 'production',
            'database': 'render_postgresql'
        }
    },
    'cpanel': {
        'name': 'cPanel Hosting',
        'icon': '🏢',
        'domains': {
            'main': 'app.autowash.co.ke',
            'admin': 'app.autowash.co.ke/admin/',
            'pattern': '{slug}.path-based.cpanel'
        },
        'features': {
            'debug': False,
            'ssl': True,
            'redis': 'external_redis',
            'email': 'domain_smtp',
            'mpesa': 'production',
            'database': 'cpanel_database'
        }
    }
}

def get_environment_config(environment=None):
    """
    Get configuration for specific environment
    """
    if environment is None:
        environment = get_current_environment()
    
    return ENVIRONMENT_CONFIGS.get(environment, ENVIRONMENT_CONFIGS['local'])