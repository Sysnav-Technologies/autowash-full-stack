from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import AnonymousUser

def business_context(request):
    """Add business context to templates with MySQL multi-tenant routing"""
    context = {
        'tenant': getattr(request, 'tenant', None),
        'business': getattr(request, 'tenant', None),  # For backward compatibility
        'business_slug': getattr(request, 'tenant_slug', None),
        'current_year': timezone.now().year,
        'app_name': 'Autowash',
        'company_name': 'Autowash Technologies',
        'is_tenant_context': hasattr(request, 'tenant') and request.tenant is not None,
    }
    
    # Add tenant-specific context if we're in a tenant context
    if hasattr(request, 'tenant') and request.tenant:
        tenant = request.tenant
        
        # Check if business is verified
        is_verified = getattr(tenant, 'is_verified', False)
        
        context.update({
            'business_name': tenant.name,
            'business_logo': tenant.logo.url if tenant.logo else None,
            'business_phone': tenant.phone,
            'business_email': tenant.email,
            'business_timezone': getattr(tenant, 'timezone', 'Africa/Nairobi'),
            'business_verified': is_verified,
            'business_slug': tenant.slug,
            'business_url_prefix': f'/business/{tenant.slug}',
            'tenant_subdomain': tenant.subdomain,
            'tenant_primary_domain': tenant.primary_domain,
        })
        
        # Add verification status if not verified
        if not is_verified:
            try:
                verification = tenant.verification
                context.update({
                    'verification_status': verification.status,
                    'verification_submitted': verification.submitted_at,
                })
            except:
                context.update({
                    'verification_status': 'pending',
                    'verification_submitted': None,
                })
    else:
        # Public context
        context.update({
            'business_url_prefix': '',
            'is_public_context': True,
        })
    
    return context

def user_role_context(request):
    """Add user role context for permission checks - COMPLETELY FIXED"""
    context = {
        'user_role': None,
        'is_owner': False,
        'is_manager': False,
        'is_supervisor': False,
        'is_attendant': False,
        'is_cashier': False,
        'is_employee': False,
        'can_manage_business': False,
        'can_manage_employees': False,
        'can_view_reports': False,
        'can_manage_expenses': False,
        'can_approve_expenses': False,
        'employee': None,
        'user_clocked_in': False,
        'user_on_break': False,
        'pending_orders_count': 0,
        'active_queue_count': 0,
        'pending_expense_approvals': 0,
        'overdue_expenses_count': 0,
    }
    
    # Only for authenticated users in tenant schemas
    if (hasattr(request, 'user') and 
        request.user.is_authenticated and 
        not isinstance(request.user, AnonymousUser) and
        hasattr(request, 'business') and 
        request.business):
        
        try:
            from apps.employees.models import Employee, Attendance
            from datetime import date
            
            # FIXED: Use user_id for cross-schema compatibility
            employee = Employee.objects.filter(user_id=request.user.id, is_active=True).first()
            
            if employee:
                # Check attendance status
                today = date.today()
                today_attendance = Attendance.objects.filter(
                    employee=employee, 
                    date=today
                ).first()
                
                user_clocked_in = bool(
                    today_attendance and 
                    today_attendance.check_in_time and 
                    not today_attendance.check_out_time
                )
                
                user_on_break = bool(
                    today_attendance and 
                    hasattr(today_attendance, 'is_on_break') and
                    today_attendance.is_on_break
                )
                
                # Get queue counts based on role
                pending_orders = 0
                active_queue = 0
                pending_expense_approvals = 0
                overdue_expenses = 0
                
                if employee.role in ['owner', 'manager', 'supervisor', 'attendant']:
                    try:
                        from apps.services.models import ServiceOrder
                        pending_orders = ServiceOrder.objects.filter(
                            status__in=['pending', 'confirmed']
                        ).count()
                        
                        active_queue = ServiceOrder.objects.filter(
                            status='in_progress'
                        ).count()
                    except Exception:
                        pass
                
                # Get expense-related counts for managers and owners
                if employee.role in ['owner', 'manager']:
                    try:
                        from apps.expenses.models import Expense
                        from django.utils import timezone
                        from datetime import timedelta
                        
                        pending_expense_approvals = Expense.objects.filter(
                            status='pending_approval'
                        ).count()
                        
                        # Overdue expenses (due more than 7 days ago)
                        seven_days_ago = timezone.now() - timedelta(days=7)
                        overdue_expenses = Expense.objects.filter(
                            status='pending',
                            due_date__lt=seven_days_ago
                        ).count()
                    except Exception:
                        pass
                
                # Set role-based permissions
                role = employee.role
                context.update({
                    'user_role': role,
                    'is_owner': role == 'owner',
                    'is_manager': role == 'manager',
                    'is_supervisor': role == 'supervisor',
                    'is_attendant': role == 'attendant',
                    'is_cashier': role == 'cashier',
                    'is_employee': True,
                    'can_manage_business': role in ['owner', 'manager'],
                    'can_manage_employees': role in ['owner', 'manager'],
                    'can_view_reports': role in ['owner', 'manager', 'supervisor'],
                    'can_manage_expenses': role in ['owner', 'manager'],
                    'can_approve_expenses': role in ['owner', 'manager'],
                    'employee': employee,
                    'user_clocked_in': user_clocked_in,
                    'user_on_break': user_on_break,
                    'pending_orders_count': pending_orders,
                    'active_queue_count': active_queue,
                    'pending_expense_approvals': pending_expense_approvals,
                    'overdue_expenses_count': overdue_expenses,
                })
                
            else:
                # FALLBACK: Check if this is the business owner without employee record
                if hasattr(request.business, 'owner') and request.business.owner.id == request.user.id:
                    context.update({
                        'user_role': 'owner',
                        'is_owner': True,
                        'is_manager': True,
                        'can_manage_business': True,
                        'can_manage_employees': True,
                        'can_view_reports': True,
                        'can_manage_expenses': True,
                        'can_approve_expenses': True,
                        'is_employee': False,
                        'employee': None,
                    })
                    
        except Exception as e:
            if settings.DEBUG:
                print(f"ERROR in user_role_context: {e}")
    
    return context

def navigation_context(request):
    """Add navigation context for path-based routing - ROLE-BASED"""
    context = {
        'nav_items': [],
        'current_section': None,
    }
    
    # Determine current section based on path
    path = request.path_info
    
    if hasattr(request, 'business') and request.business:
        business_prefix = f'/business/{request.business.slug}'
        
        # Remove business prefix for section detection
        if path.startswith(business_prefix):
            section_path = path[len(business_prefix):]
        else:
            section_path = path
            
        # Determine current section
        if section_path.startswith('/employees/'):
            context['current_section'] = 'employees'
        elif section_path.startswith('/customers/'):
            context['current_section'] = 'customers'
        elif section_path.startswith('/services/'):
            context['current_section'] = 'services'
        elif section_path.startswith('/inventory/'):
            context['current_section'] = 'inventory'
        elif section_path.startswith('/expenses/'):
            context['current_section'] = 'expenses'
        elif section_path.startswith('/suppliers/'):
            context['current_section'] = 'suppliers'
        elif section_path.startswith('/payments/'):
            context['current_section'] = 'payments'
        elif section_path.startswith('/reports/'):
            context['current_section'] = 'reports'
        elif section_path.startswith('/notifications/'):
            context['current_section'] = 'notifications'
        elif section_path.startswith('/settings/'):
            context['current_section'] = 'settings'
        elif section_path.startswith('/profile/'):
            context['current_section'] = 'profile'
        elif section_path in ['/', '/dashboard/']:
            context['current_section'] = 'dashboard'
            
        # Build navigation items based on user role
        if request.user.is_authenticated:
            try:
                from apps.employees.models import Employee
                
                # Get employee record or check if business owner
                employee = Employee.objects.filter(user_id=request.user.id, is_active=True).first()
                user_role = None
                
                if employee:
                    user_role = employee.role
                elif hasattr(request.business, 'owner') and request.business.owner.id == request.user.id:
                    user_role = 'owner'
                
                # Build navigation based on role
                nav_items = []
                
                if user_role:
                    # Dashboard - available to all
                    nav_items.append({
                        'name': 'Dashboard', 
                        'url': f'{business_prefix}/', 
                        'icon': 'fas fa-tachometer-alt', 
                        'section': 'dashboard'
                    })
                    
                    # Core Operations - ALL roles except cleaners and security
                    if user_role in ['owner', 'manager', 'supervisor', 'attendant', 'cashier']:
                        nav_items.extend([
                            {
                                'name': 'Services', 
                                'url': f'{business_prefix}/services/', 
                                'icon': 'fas fa-car-wash', 
                                'section': 'services'
                            },
                            {
                                'name': 'Customers', 
                                'url': f'{business_prefix}/customers/', 
                                'icon': 'fas fa-user-friends', 
                                'section': 'customers'
                            },
                        ])
                    
                    # Payments - Owners, Managers, Cashiers, Attendants
                    if user_role in ['owner', 'manager', 'cashier', 'attendant']:
                        nav_items.append({
                            'name': 'Payments', 
                            'url': f'{business_prefix}/payments/', 
                            'icon': 'fas fa-credit-card', 
                            'section': 'payments'
                        })
                    
                    # Management - Owners and Managers only
                    if user_role in ['owner', 'manager']:
                        nav_items.extend([
                            {
                                'name': 'Team', 
                                'url': f'{business_prefix}/employees/', 
                                'icon': 'fas fa-users', 
                                'section': 'employees'
                            },
                            {
                                'name': 'Inventory', 
                                'url': f'{business_prefix}/inventory/', 
                                'icon': 'fas fa-boxes', 
                                'section': 'inventory'
                            },
                            {
                                'name': 'Suppliers', 
                                'url': f'{business_prefix}/suppliers/', 
                                'icon': 'fas fa-truck', 
                                'section': 'suppliers'
                            },
                        ])
                    
                    # Reports - Owners, Managers, Supervisors
                    if user_role in ['owner', 'manager', 'supervisor']:
                        nav_items.append({
                            'name': 'Reports', 
                            'url': f'{business_prefix}/reports/', 
                            'icon': 'fas fa-chart-bar', 
                            'section': 'reports'
                        })
                    
                    # Settings - Owner only
                    if user_role == 'owner':
                        nav_items.append({
                            'name': 'Settings', 
                            'url': f'{business_prefix}/settings/', 
                            'icon': 'fas fa-cog', 
                            'section': 'settings'
                        })
                    
                    # Personal items - available to all
                    nav_items.extend([
                        {
                            'name': 'Profile', 
                            'url': f'{business_prefix}/profile/', 
                            'icon': 'fas fa-user', 
                            'section': 'profile'
                        },
                        {
                            'name': 'Notifications', 
                            'url': f'{business_prefix}/notifications/', 
                            'icon': 'fas fa-bell', 
                            'section': 'notifications'
                        },
                    ])
                
                context['nav_items'] = nav_items
                
            except Exception as e:
                if settings.DEBUG:
                    print(f"Navigation error: {e}")
                
                # Fallback navigation
                context['nav_items'] = [
                    {'name': 'Dashboard', 'url': f'{business_prefix}/', 'icon': 'fas fa-tachometer-alt', 'section': 'dashboard'},
                ]
    
    return context

def notifications_context(request):
    """Add notifications context to templates"""
    context = {
        'unread_notifications_count': 0,
        'recent_notifications': [],
    }
    
    # Only for authenticated users in verified businesses
    if (hasattr(request, 'user') and request.user.is_authenticated and 
        hasattr(request, 'business') and request.business and 
        getattr(request.business, 'is_verified', False)):
        try:
            # Check if notifications app exists
            from apps.notification.models import Notification
            notifications = Notification.objects.filter(
                user=request.user,
                is_read=False
            )[:5]
            
            context.update({
                'unread_notifications_count': notifications.count(),
                'recent_notifications': notifications,
            })
        except ImportError:
            # Notification app doesn't exist yet
            pass
        except Exception:
            pass
    
    return context

def performance_context(request):
    """Add performance metrics context for dashboard"""
    context = {}
    
    # Only add metrics for business owners and managers in verified businesses
    if (hasattr(request, 'user') and request.user.is_authenticated and 
        hasattr(request, 'business') and request.business and
        getattr(request.business, 'is_verified', False)):
        
        try:
            from apps.employees.models import Employee
            # Use user_id instead of user for lookup
            employee = Employee.objects.filter(user_id=request.user.id, is_active=True).first()
            
            if employee and employee.role in ['owner', 'manager']:
                # Get today's metrics - you'll need to implement this
                try:
                    # Placeholder for performance metrics
                    context.update({
                        'today_revenue': 0,
                        'today_orders': 0,
                        'today_customers': 0,
                        'employee_role': employee.role,
                    })
                except Exception:
                    pass
        except Exception:
            pass
    
    return context

def verification_context(request):
    """Add verification-specific context"""
    context = {
        'requires_verification': False,
        'verification_complete': False,
    }
    
    # Check if user owns a business that needs verification
    if hasattr(request, 'user') and request.user.is_authenticated:
        try:
            # Use public schema to check businesses
            with schema_context(get_public_schema_name()):
                business = request.user.owned_businesses.first()
                if business:
                    context.update({
                        'user_business': business,
                        'requires_verification': not business.is_verified,
                        'verification_complete': business.is_verified,
                        'business_management_url': f'/business/{business.slug}' if business.is_verified else '/auth/verification-pending/',
                    })
                    
                    # Add verification details if business exists
                    try:
                        verification = business.verification
                        context.update({
                            'verification_status': verification.status,
                            'verification_submitted_at': verification.submitted_at,
                            'verification_documents_uploaded': bool(
                                verification.business_license and 
                                verification.tax_certificate and 
                                verification.id_document
                            ),
                        })
                    except:
                        context.update({
                            'verification_status': 'pending',
                            'verification_submitted_at': None,
                            'verification_documents_uploaded': False,
                        })
        except Exception:
            pass
    
    return context