# apps/accounts/views.py - Updated with fixed employee creation

import re
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.urls import reverse
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView, CreateView, UpdateView
from django.utils.decorators import method_decorator
from django.db import transaction, connection
from django.views.decorators.csrf import csrf_protect


from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.utils import timezone
import uuid
from django.conf import settings
from apps.core.decorators import ajax_required
from apps.core.management.environment import get_current_environment, get_domain_for_environment, get_environment_context, get_error_message, get_success_message
from .models import UserProfile, Business, BusinessSettings, BusinessVerification, Domain
from .forms import (
    UserRegistrationForm, UserProfileForm, BusinessRegistrationForm,
    BusinessSettingsForm, BusinessVerificationForm
)

class LandingView(TemplateView):
    """Public landing page"""
    template_name = 'public/landing.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': 'Welcome to Autowash',
            'features': [
                {
                    'icon': 'fas fa-users',
                    'title': 'Employee Management',
                    'description': 'Manage your staff, roles, and permissions easily'
                },
                {
                    'icon': 'fas fa-car',
                    'title': 'Service Management',
                    'description': 'Track services, packages, and customer orders'
                },
                {
                    'icon': 'fas fa-chart-line',
                    'title': 'Analytics & Reports',
                    'description': 'Get insights into your business performance'
                },
                {
                    'icon': 'fas fa-mobile-alt',
                    'title': 'Mobile Ready',
                    'description': 'Access your business from anywhere, anytime'
                },
            ]
        })
        return context

def register_view(request):
    """User registration view"""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard_redirect')
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save()
                    
                    # Create user profile
                    UserProfile.objects.create(
                        user=user,
                        phone=form.cleaned_data.get('phone'),
                    )
                    
                    # Authenticate and login
                    username = form.cleaned_data.get('username')
                    password = form.cleaned_data.get('password1')
                    user = authenticate(username=username, password=password)
                    
                    if user:
                        login(request, user)
                        messages.success(request, 'Account created successfully!')
                        return redirect('accounts:business_register')
                        
            except Exception as e:
                messages.error(request, f'Registration failed: {str(e)}')
    else:
        form = UserRegistrationForm()
    
    return render(request, 'auth/register.html', {'form': form})

def login_view(request):
    """User login view"""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard_redirect')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')
            
            # Redirect to next URL or dashboard
            next_url = request.GET.get('next', 'accounts:dashboard_redirect')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid credentials. Please try again.')
    
    return render(request, 'auth/login.html')

# Password Reset view
def password_reset_view(request):
    """Password reset view"""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard_redirect')
    
    if request.method == 'POST':
        email = request.POST.get('email')
        if email:
            try:
                user = User.objects.get(email=email)
                # Trigger password reset email (using Django's built-in functionality)
                from django.contrib.auth.tokens import default_token_generator
                from django.core.mail import send_mail
                from django.urls import reverse
                
                token = default_token_generator.make_token(user)
                reset_url = request.build_absolute_uri(
                    reverse('accounts:password_reset_confirm', kwargs={'uidb64': user.pk, 'token': token})
                )
                
                send_mail(
                    'Password Reset Request',
                    f'Click the link to reset your password: {reset_url}',
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
                
                messages.success(request, 'Password reset email sent! Please check your inbox.')
            except User.DoesNotExist:
                messages.error(request, 'No user found with that email address.')
        else:
            messages.error(request, 'Email is required.')
    
    return render(request, 'auth/password_reset.html')


@login_required
def dashboard_redirect(request):
    """Smart dashboard redirect based on user context and verification status"""
    print(f"\n" + "="*50)
    print(f"DASHBOARD REDIRECT CALLED")
    print(f"User: {request.user.username}")
    print(f"Current path: {request.path}")
    print(f"Request META HOST: {request.META.get('HTTP_HOST')}")
    print(f"="*50)
    
    # First check if user owns a business
    business = request.user.owned_tenants.first()
    print(f"User owned business: {business}")
    
    if business:
        print(f"Business found: {business.name}")
        print(f"Business slug: {business.slug}")
        print(f"Business verified: {business.is_verified}")
        
        # Check subscription status first
        if not hasattr(business, 'subscription') or not business.subscription or not business.subscription.is_active:
            # Business doesn't have an active subscription - redirect to subscription selection
            messages.info(request, 'Please select a subscription plan to continue.')
            return redirect(f'/business/{business.slug}/subscriptions/select/')
        
        # Check verification status
        if not business.is_verified:
            # Business is not verified yet
            messages.info(request, 'Your business is pending verification. Please check your verification status.')
            return redirect(f'/business/{business.slug}/verification-pending/')
        
        # Business is verified - redirect to business dashboard using path-based URL
        business_url = f'/business/{business.slug}/'
        print(f"Redirecting to business dashboard: {business_url}")
        return redirect(business_url)
    
    # User doesn't own a business - check if they're an employee
    print("No owned business found, checking for employee records...")
    
    # Search across all verified tenants for this user's employee record
    try:
        from apps.core.tenant_models import Tenant
        
        verified_tenants = Tenant.objects.filter(is_verified=True, is_active=True)
        
        employee_business = None
        
        for tenant in verified_tenants:
            try:
                # Use the tenant database to check for employee record
                from apps.employees.models import Employee
                
                # Check if user has an employee record in this tenant
                employee = Employee.objects.using(tenant.get_database_name()).filter(
                    user_id=request.user.id, 
                    is_active=True
                ).first()
                
                if employee:
                    employee_business = tenant
                    print(f"Found employee record in business: {tenant.name}")
                    print(f"Employee ID: {employee.employee_id}")
                    print(f"Employee role: {employee.role}")
                    break
                        
            except Exception as e:
                # Skip tenants where we can't check (maybe database doesn't exist yet)
                print(f"Could not check tenant {tenant.name}: {e}")
                continue
        
        if employee_business:
            # User is an employee - redirect to their business dashboard
            business_url = f'/business/{employee_business.slug}/services/dashboard/'
            print(f"Redirecting employee to business dashboard: {business_url}")
            messages.success(request, f'Welcome back! Redirecting to your {employee_business.name} dashboard.')
            return redirect(business_url)
        
    except Exception as e:
        print(f"Error checking employee records: {e}")
    
    # User is neither a business owner nor an employee
    print("User is neither business owner nor employee")
    
    # Check if user has multiple business access options
    try:
        from apps.core.tenant_models import Tenant
        
        # Get all businesses where user might have access
        all_businesses = []
        
        # Add owned businesses (even unverified ones)
        owned_businesses = request.user.owned_tenants.all()
        for biz in owned_businesses:
            all_businesses.append({
                'business': biz,
                'access_type': 'owner',
                'verified': biz.is_verified
            })
        
        # Add employee businesses
        verified_tenants = Tenant.objects.filter(is_verified=True, is_active=True)
        for tenant in verified_tenants:
            try:
                from apps.employees.models import Employee
                employee = Employee.objects.using(tenant.get_database_name()).filter(
                    user_id=request.user.id, 
                    is_active=True
                ).first()
                
                if employee:
                    all_businesses.append({
                        'business': tenant,
                        'access_type': 'employee',
                        'verified': True,
                        'employee': employee
                    })
            except:
                continue
        
        if len(all_businesses) > 1:
            # User has multiple business access - show selection page
            print(f"User has access to {len(all_businesses)} businesses")
            return redirect('/auth/switch-business/')
        
        elif len(all_businesses) == 1:
            # User has access to one business
            business_access = all_businesses[0]
            biz = business_access['business']
            
            if not business_access['verified']:
                # Unverified business (must be owned)
                messages.info(request, 'Your business is pending verification.')
                return redirect('/auth/verification-pending/')
            else:
                # Verified business access
                business_url = f'/business/{biz.slug}/'
                return redirect(business_url)
    
    except Exception as e:
        print(f"Error checking business access: {e}")
    
    # No business access found - redirect to business registration
    print("No business access found, redirecting to business registration")
    messages.info(request, 'Welcome! Please register your business to get started, or contact your employer for access.')
    return redirect('/auth/business/register/')


@login_required
def business_register_view(request):
    """
    Business registration view with multi-environment support
    Supports Local, Render, and cPanel environments
    NO schema/employee creation during registration - only after admin approval
    """
    
    # Detect current environment
    environment = get_current_environment()
    
    print(f"\n" + "="*50)
    print(f"BUSINESS REGISTER VIEW CALLED - PATH-BASED ROUTING")
    print(f"Request method: {request.method}")
    print(f"User: {request.user}")
    print(f"Environment: {environment.upper()}")
    print(f"Debug mode: {'ON' if settings.DEBUG else 'OFF'}")
    print(f"="*50)
    
    # Check if user already owns a business
    existing_businesses = request.user.owned_tenants.all()
    print(f"Existing businesses count: {existing_businesses.count()}")
    
    if existing_businesses.exists():
        business = existing_businesses.first()
        if business.is_verified:
            messages.info(request, 'You already have a verified business.')
            return redirect(f'/business/{business.slug}/')
        else:
            messages.info(request, 'Your business registration is pending verification.')
            return redirect('/auth/verification-pending/')
    
    if request.method == 'POST':
        print("\n" + "="*30 + " POST REQUEST " + "="*30)
        
        form = BusinessRegistrationForm(request.POST, request.FILES)
        print(f"Form is valid: {form.is_valid()}")
        
        if form.is_valid():
            print("=== FORM IS VALID - ATTEMPTING SAVE ===")
            try:
                with transaction.atomic():
                    business = form.save(commit=False)
                    
                    # Set the owner
                    business.owner = request.user
                    
                    # The subdomain is already set by the form's clean() method
                    
                    # Create database name for tenant based on subdomain
                    database_name = re.sub(r'[^a-z0-9]', '', business.subdomain.lower())
                    if not database_name or not database_name[0].isalpha():
                        database_name = 'biz' + database_name
                    business.database_name = database_name[:20]
                    
                    # Set database credentials (you can customize these)
                    business.database_user = f"user_{business.database_name}"
                    business.database_password = str(uuid.uuid4())[:12]  # Generate random password
                    
                    print(f"About to save business: {business.name}")
                    print(f"Subdomain: {business.subdomain}")
                    print(f"Database name: {business.database_name}")
                    print(f"Business slug: {business.slug}")
                    print(f"Environment: {environment}")
                    
                    # Check for conflicts
                    original_subdomain = business.subdomain
                    original_database_name = business.database_name
                    counter = 1
                    while (Business.objects.filter(subdomain=business.subdomain).exists() or 
                           Business.objects.filter(database_name=business.database_name).exists()):
                        business.subdomain = f"{original_subdomain}{counter}"
                        business.database_name = f"{original_database_name}{counter}"
                        counter += 1
                        print(f"Conflict found, trying: {business.subdomain}")
                    
                    # Set approval status
                    business.is_active = False  # Needs admin approval
                    business.is_verified = False
                    business.is_approved = False
                    business.save()
                    print(f"Business saved successfully! ID: {business.id}")
                    
                    # Create domain record for path-based routing (environment-specific)
                    print("Creating domain record for path-based routing...")
                    domain_name = get_domain_for_environment(business.subdomain, environment)
                    print(f"Domain name for {environment}: {domain_name}")

                    # Create domain but note that database doesn't exist yet
                    domain = Domain.objects.create(
                        domain=domain_name,
                        tenant=business,
                        is_primary=True
                    )
                    print(f"Domain record created: {domain.domain}")
                    
                    # Create business verification record with approved terms
                    print("Creating business verification...")
                    BusinessVerification.objects.create(
                        business=business, 
                        status='pending',
                        notes='Business registered with terms agreement - no documents uploaded',
                        submitted_at=timezone.now()
                    )
                    
                    # IMPORTANT: NO database creation here!
                    # That will be done by admin during approval process
                    print("Business registration complete - waiting for admin approval")
                    
                    # Environment-specific success message
                    success_message = f"Business '{business.name}' registered successfully! Please select a subscription plan to continue."
                    messages.success(request, success_message)
                    
                    # Redirect to subscription selection instead of verification pending
                    return redirect('/subscriptions/select/')
                
            except Exception as e:
                print(f"=== SAVE ERROR ===")
                print(f"Error: {str(e)}")
                import traceback
                traceback.print_exc()
                
                # Environment-specific error handling
                error_message = get_error_message(str(e), environment)
                messages.error(request, error_message)
        else:
            print("=== FORM VALIDATION ERRORS ===")
            for field, errors in form.errors.items():
                print(f"  {field}: {errors}")
    else:
        form = BusinessRegistrationForm()
    
    # Add environment context to template
    context = {
        'form': form,
        **get_environment_context()  # This adds all environment info to template
    }
    
    return render(request, 'auth/business_register.html', context)

@login_required
def verification_pending(request):
    """Show verification pending status"""
    business = request.user.owned_tenants.first()
    if not business:
        messages.error(request, 'No business found.')
        return redirect('/auth/business/register/')
    
    # If business is already verified, redirect to dashboard
    if business.is_verified:
        messages.success(request, 'Your business has been verified!')
        return redirect(f'/business/{business.slug}/')
    
    try:
        verification = business.verification
    except BusinessVerification.DoesNotExist:
        verification = BusinessVerification.objects.create(business=business)
    
    context = {
        'business': business,
        'verification': verification,
        'title': 'Verification Status',
        'business_url': f'/business/{business.slug}/' if business.is_verified else None,
    }
    
    return render(request, 'auth/verification_pending.html', context)

@login_required
def business_verification_view(request):
    """Business verification document upload"""
    try:
        business = request.user.owned_tenants.first()
        if not business:
            messages.error(request, 'You do not own any business.')
            return redirect('/auth/business/register/')
        
        verification, created = BusinessVerification.objects.get_or_create(business=business)
        
        if request.method == 'POST':
            form = BusinessVerificationForm(request.POST, request.FILES, instance=verification)
            if form.is_valid():
                verification = form.save(commit=False)
                verification.status = 'in_review'
                verification.save()
                
                messages.success(request, 'Verification documents submitted successfully! Admin will review them within 24-48 hours.')
                return redirect('/auth/verification-pending/')
        else:
            form = BusinessVerificationForm(instance=verification)
        
        context = {
            'form': form,
            'business': business,
            'verification': verification,
            'title': 'Business Verification'
        }
        return render(request, 'auth/business_verification.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading verification: {str(e)}')
        return redirect('/auth/dashboard/')

@csrf_protect
@require_http_methods(["GET", "POST"])
def logout_view(request):
    """
    Enhanced logout view that properly handles cross-tenant logout
    and ensures session is completely cleared
    """
    if settings.DEBUG:
        print(f"\n" + "="*50)
        print(f"[LOGOUT] LOGOUT VIEW CALLED")
        print(f"[LOGOUT] User: {request.user.username if request.user.is_authenticated else 'Anonymous'}")
        print(f"[LOGOUT] Current path: {request.path}")
        print(f"[LOGOUT] Current schema: {getattr(connection, 'schema_name', 'unknown')}")
        print(f"[LOGOUT] Session key before logout: {request.session.session_key if hasattr(request, 'session') else 'None'}")
        print(f"="*50)
    
    # Store user info before logout for message
    was_authenticated = request.user.is_authenticated
    username = request.user.username if was_authenticated else None
    
    # Clear session data manually first
    if hasattr(request, 'session'):
        try:
            # Clear all session data
            request.session.flush()  # This deletes the session data and regenerates the session key
            if settings.DEBUG:
                print(f"[LOGOUT] Session flushed manually")
        except Exception as e:
            if settings.DEBUG:
                print(f"[LOGOUT] Error flushing session: {e}")
    
    # Perform Django logout
    auth_logout(request)
    
    # Add success message only if user was authenticated
    if was_authenticated:
        messages.success(request, f'You have been logged out successfully. See you next time!')
    
    # Clear any preserved session data attributes
    if hasattr(request, '_preserved_session_data'):
        delattr(request, '_preserved_session_data')
    
    # Clear business context
    if hasattr(request, 'business'):
        request.business = None
    if hasattr(request, 'business_slug'):
        request.business_slug = None
    
    if settings.DEBUG:
        print(f"[LOGOUT] User logged out: {username}")
        print(f"[LOGOUT] Session key after logout: {request.session.session_key if hasattr(request, 'session') else 'None'}")
        print(f"[LOGOUT] Redirecting to: /public/")
    
    # Always redirect to public schema
    return redirect('/public/')

def logout_and_redirect_to_public(request):
    """
    Utility function to logout user and redirect to public schema
    Useful for business context redirects
    """
    # Clear business context
    if hasattr(request, 'business'):
        request.business = None
    if hasattr(request, 'business_slug'):
        request.business_slug = None
    
    # Perform logout
    if request.user.is_authenticated:
        auth_logout(request)
        messages.info(request, 'You have been logged out.')
    
    return redirect('/public/')


@login_required
def profile_view(request):
    """User profile view"""
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('/auth/profile/')
    else:
        form = UserProfileForm(instance=profile)
    
    context = {
        'form': form,
        'profile': profile,
        'title': 'My Profile'
    }
    return render(request, 'auth/profile.html', context)

@login_required
def business_settings_view(request):
    """Business settings view - only for verified businesses"""
    try:
        business = request.user.owned_tenants.first()
        if not business:
            messages.error(request, 'You do not own any business.')
            return redirect('/auth/business/register/')
        
        if not business.is_verified:
            messages.warning(request, 'Please complete business verification first.')
            return redirect('/auth/verification-pending/')
        
        settings_obj, created = BusinessSettings.objects.get_or_create(business=business)
        
        if request.method == 'POST':
            form = BusinessSettingsForm(request.POST, instance=settings_obj)
            if form.is_valid():
                form.save()
                messages.success(request, 'Business settings updated successfully!')
                return redirect('/auth/business/settings/')
        else:
            form = BusinessSettingsForm(instance=settings_obj)
        
        context = {
            'form': form,
            'business': business,
            'settings': settings_obj,
            'title': 'Business Settings'
        }
        return render(request, 'business/settings.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading settings: {str(e)}')
        return redirect('/auth/dashboard/')

@login_required
def check_verification_status(request):
    """AJAX endpoint to check verification status"""
    if not request.user.owned_tenants.exists():
        return JsonResponse({'error': 'No business found'}, status=404)
    
    business = request.user.owned_tenants.first()
    
    try:
        verification = business.verification
        return JsonResponse({
            'status': verification.status,
            'status_display': verification.get_status_display(),
            'is_verified': business.is_verified,
            'submitted_at': verification.submitted_at.isoformat() if verification.submitted_at else None,
            'verified_at': verification.verified_at.isoformat() if verification.verified_at else None,
            'has_documents': bool(verification.business_license and verification.tax_certificate and verification.id_document),
            'business_url': f'/business/{business.slug}/' if business.is_verified else None,
        })
    except BusinessVerification.DoesNotExist:
        return JsonResponse({
            'status': 'pending',
            'status_display': 'Pending',
            'is_verified': False,
            'submitted_at': None,
            'verified_at': None,
            'has_documents': False,
            'business_url': None,
        })
    
@login_required
@ajax_required
def check_business_name(request):
    """Check if business name is available"""
    name = request.GET.get('name', '').strip()
    if not name:
        return JsonResponse({'available': False, 'message': 'Name is required'})
    
    slug = slugify(name)
    exists = Business.objects.filter(name__iexact=name).exists() or \
             Business.objects.filter(slug=slug).exists()
    
    return JsonResponse({
        'available': not exists,
        'message': 'Name is available' if not exists else 'Name is already taken',
        'suggested_url': f'/business/{slug}/' if not exists else None,
    })

@require_http_methods(["GET"])
def check_notifications_api(request):
    """Check for notifications - placeholder API endpoint"""
    return JsonResponse({
        'status': 'success',
        'notifications': [],
        'count': 0,
        'message': 'No new notifications'
    })

# Additional views for path-based routing management

@login_required
def business_dashboard_redirect(request, slug):
    """Redirect to business dashboard for verified businesses"""
    print(f"\n" + "="*50)
    print(f"BUSINESS DASHBOARD REDIRECT CALLED")
    print(f"User: {request.user.username}")
    print(f"Business slug: {slug}")
    print(f"Current path: {request.path}")
    print(f"="*50)
    
    try:
        business = Business.objects.get(slug=slug, is_active=True)
        print(f"Business found: {business.name}")
        
        # Check if user has access to this business
        if request.user != business.owner:
            try:
                from apps.employees.models import Employee
                # Use user_id to check employee access
                employee = Employee.objects.get(user_id=request.user.id, is_active=True)
                print(f"User is employee of business: {employee.employee_id}")
            except Employee.DoesNotExist:
                print(f"User has no access to business")
                messages.error(request, 'You do not have access to this business.')
                return redirect('/public/')
        else:
            print(f"User is owner of business")
        
        # Check if business is verified
        if not business.is_verified:
            print(f"Business not verified")
            messages.warning(request, 'This business is pending verification.')
            if request.user == business.owner:
                return redirect('/auth/verification-pending/')
            else:
                return redirect('/public/')
        
        print(f"Redirecting to business dashboard: /business/{slug}/")
        # Redirect to business dashboard
        return redirect(f'/business/{slug}/')
        
    except Business.DoesNotExist:
        print(f"Business not found")
        messages.error(request, 'Business not found.')
        return redirect('/public/')

def switch_business(request):
    """Allow users to switch between businesses they have access to"""
    if not request.user.is_authenticated:
        return redirect('/auth/login/')
    
    # Get all businesses the user has access to
    owned_businesses = request.user.owned_tenants.filter(is_verified=True)
    
    try:
        from apps.employees.models import Employee
        # Use user_id to find employee businesses
        employee_records = Employee.objects.filter(user_id=request.user.id, is_active=True)
        employee_business_ids = [emp.id for emp in employee_records]  # This needs to be fixed based on your Employee model
        employee_businesses = Business.objects.filter(
            id__in=employee_business_ids,
            is_verified=True
        ).distinct()
    except:
        employee_businesses = Business.objects.none()
    
    all_businesses = (owned_businesses | employee_businesses).distinct()
    
    if request.method == 'POST':
        business_slug = request.POST.get('business_slug')
        if business_slug and all_businesses.filter(slug=business_slug).exists():
            return redirect(f'/business/{business_slug}/')
        else:
            messages.error(request, 'Invalid business selection.')
    
    context = {
        'businesses': all_businesses,
        'title': 'Switch Business'
    }
    return render(request, 'auth/switch_business.html', context)

@login_required 
def create_tenant_database(request):
    """Admin function to create database for verified tenant"""
    if not request.user.is_superuser:
        messages.error(request, 'Access denied.')
        return redirect('/public/')
    
    tenant_id = request.GET.get('tenant_id')
    if not tenant_id:
        messages.error(request, 'Tenant ID required.')
        return redirect('/admin/')
    
    try:
        from apps.core.tenant_models import Tenant
        from apps.core.database_router import TenantDatabaseManager
        from django.core.management import call_command
        
        tenant = Tenant.objects.get(id=tenant_id)
        db_manager = TenantDatabaseManager()
        
        # Create the database
        db_name = tenant.get_database_name()
        if not db_manager.database_exists(db_name):
            db_manager.create_database(db_name)
            
            # Run migrations for this tenant database
            call_command('migrate', database=db_name, verbosity=1)
            
            messages.success(request, f'Database created successfully for tenant: {tenant.name}')
        else:
            messages.warning(request, f'Database already exists for tenant: {tenant.name}')
        
    except Tenant.DoesNotExist:
        messages.error(request, 'Tenant not found.')
    except Exception as e:
        messages.error(request, f'Error creating schema: {str(e)}')
    
    return redirect('/admin/accounts/business/')

def business_info_api(request, slug):
    """API endpoint to get business information"""
    try:
        business = Business.objects.get(slug=slug, is_active=True, is_verified=True)
        
        return JsonResponse({
            'success': True,
            'business': {
                'name': business.name,
                'slug': business.slug,
                'description': business.description,
                'business_type': business.get_business_type_display(),
                'phone': str(business.phone) if business.phone else None,
                'email': business.email,
                'website': business.website,
                'address': business.address,
                'city': business.city,
                'logo_url': business.logo.url if business.logo else None,
                'is_verified': business.is_verified,
                'url': f'/business/{business.slug}/',
            }
        })
        
    except Business.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Business not found'
        }, status=404)