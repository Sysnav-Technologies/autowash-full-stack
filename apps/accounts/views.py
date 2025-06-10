# apps/accounts/views.py - Updated with fixed employee creation

import re
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.urls import reverse
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView, CreateView, UpdateView
from django.utils.decorators import method_decorator
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils.text import slugify
import uuid
from django.conf import settings
from apps.core.decorators import ajax_required
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
    business = request.user.owned_businesses.first()
    print(f"User owned business: {business}")
    
    if business:
        print(f"Business found: {business.name}")
        print(f"Business slug: {business.slug}")
        print(f"Business verified: {business.is_verified}")
        
        # Check verification status
        if not business.is_verified:
            # Business is not verified yet
            messages.info(request, 'Your business is pending verification. Please check your verification status.')
            return redirect('/auth/verification-pending/')
        
        # Business is verified - redirect to business dashboard using path-based URL
        business_url = f'/business/{business.slug}/'
        print(f"Redirecting to business dashboard: {business_url}")
        return redirect(business_url)
    
    # User doesn't own a business - check if they're an employee
    print("No owned business found, checking for employee records...")
    
    # Search across all verified businesses for this user's employee record
    try:
        from django_tenants.utils import get_tenant_model, schema_context
        
        tenant_model = get_tenant_model()
        verified_businesses = tenant_model.objects.filter(is_verified=True, is_active=True)
        
        employee_business = None
        
        for biz in verified_businesses:
            try:
                # Switch to the business schema to check for employee record
                with schema_context(biz.schema_name):
                    from apps.employees.models import Employee
                    
                    # Check if user has an employee record in this business
                    employee = Employee.objects.filter(
                        user_id=request.user.id, 
                        is_active=True
                    ).first()
                    
                    if employee:
                        employee_business = biz
                        print(f"Found employee record in business: {biz.name}")
                        print(f"Employee ID: {employee.employee_id}")
                        print(f"Employee role: {employee.role}")
                        break
                        
            except Exception as e:
                # Skip businesses where we can't check (maybe schema doesn't exist yet)
                print(f"Could not check business {biz.name}: {e}")
                continue
        
        if employee_business:
            # User is an employee - redirect to their business dashboard
            business_url = f'/business/{employee_business.slug}/'
            print(f"Redirecting employee to business dashboard: {business_url}")
            messages.success(request, f'Welcome back! Redirecting to {employee_business.name} dashboard.')
            return redirect(business_url)
        
    except Exception as e:
        print(f"Error checking employee records: {e}")
    
    # User is neither a business owner nor an employee
    print("User is neither business owner nor employee")
    
    # Check if user has multiple business access options
    try:
        from django_tenants.utils import get_tenant_model
        tenant_model = get_tenant_model()
        
        # Get all businesses where user might have access
        all_businesses = []
        
        # Add owned businesses (even unverified ones)
        owned_businesses = request.user.owned_businesses.all()
        for biz in owned_businesses:
            all_businesses.append({
                'business': biz,
                'access_type': 'owner',
                'verified': biz.is_verified
            })
        
        # Add employee businesses
        verified_businesses = tenant_model.objects.filter(is_verified=True, is_active=True)
        for biz in verified_businesses:
            try:
                with schema_context(biz.schema_name):
                    from apps.employees.models import Employee
                    employee = Employee.objects.filter(
                        user_id=request.user.id, 
                        is_active=True
                    ).first()
                    
                    if employee:
                        all_businesses.append({
                            'business': biz,
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
    """Business registration - NO schema/employee creation during registration"""
    print(f"\n" + "="*50)
    print(f"BUSINESS REGISTER VIEW CALLED - PATH-BASED ROUTING")
    print(f"Request method: {request.method}")
    print(f"User: {request.user}")
    print(f"Environment: {'LOCAL' if not settings.RENDER else 'RENDER'}")
    print(f"Debug mode: {'ON' if settings.DEBUG else 'OFF'}")
    print(f"="*50)
    
    # Check if user already owns a business
    existing_businesses = request.user.owned_businesses.all()
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
                    business.owner = request.user
                    business.slug = slugify(business.name)
                    
                    # Create schema name for tenant
                    schema_name = re.sub(r'[^a-z0-9]', '', business.name.lower())
                    if not schema_name or not schema_name[0].isalpha():
                        schema_name = 'biz' + schema_name
                    business.schema_name = schema_name[:20]
                    
                    print(f"About to save business: {business.name}")
                    print(f"Schema name: {business.schema_name}")
                    print(f"Business slug: {business.slug}")
                    
                    # Check for conflicts
                    original_slug = business.slug
                    original_schema = business.schema_name
                    counter = 1
                    while (Business.objects.filter(slug=business.slug).exists() or 
                           Business.objects.filter(schema_name=business.schema_name).exists()):
                        business.slug = f"{original_slug}{counter}"
                        business.schema_name = f"{original_schema}{counter}"
                        counter += 1
                        print(f"Conflict found, trying: {business.slug}")
                    
                    # IMPORTANT: Don't create schema yet - wait for admin verification
                    business.auto_create_schema = False
                    business.is_verified = False  # Explicitly set to False
                    business.save()
                    print(f"Business saved successfully! ID: {business.id}")
                    
                    # Create domain record for path-based routing
                    print("Creating domain record for path-based routing...")
                    
                    # For path-based routing, we use a standardized domain format
                    if not settings.RENDER:
                        # Local development
                        domain_name = f'{business.slug}.path-based.localhost'
                    else:
                        # Production on Render
                        domain_name = f'{business.slug}.path-based.autowash'

                    # Create domain but note that schema doesn't exist yet
                    domain = Domain.objects.create(
                        domain=domain_name,
                        tenant=business,
                        is_primary=True
                    )
                    print(f"Domain record created: {domain.domain}")
                    
                    # Create business settings and verification records
                    print("Creating business settings and verification...")
                    BusinessSettings.objects.create(business=business)
                    BusinessVerification.objects.create(business=business, status='pending')
                    
                    # IMPORTANT: NO schema or employee creation here!
                    # That will be done by admin during approval process
                    print("Business registration complete - waiting for admin approval")
                    
                    success_message = (
                        f'Business "{business.name}" registered successfully! '
                        f'Please upload verification documents. Admin will review and activate your account.'
                    )
                    messages.success(request, success_message)
                    
                    # Redirect to verification upload
                    return redirect('/auth/business/verification/')
                
            except Exception as e:
                print(f"=== SAVE ERROR ===")
                print(f"Error: {str(e)}")
                import traceback
                traceback.print_exc()
                messages.error(request, f'Registration failed: {str(e)}')
        else:
            print("=== FORM VALIDATION ERRORS ===")
            for field, errors in form.errors.items():
                print(f"  {field}: {errors}")
    else:
        form = BusinessRegistrationForm()
    
    return render(request, 'auth/business_register.html', {'form': form})

@login_required
def verification_pending(request):
    """Show verification pending status"""
    business = request.user.owned_businesses.first()
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
        business = request.user.owned_businesses.first()
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

def logout_view(request):
    """User logout view"""
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
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
        business = request.user.owned_businesses.first()
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
    if not request.user.owned_businesses.exists():
        return JsonResponse({'error': 'No business found'}, status=404)
    
    business = request.user.owned_businesses.first()
    
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
    owned_businesses = request.user.owned_businesses.filter(is_verified=True)
    
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
def create_business_schema(request):
    """Admin function to create schema for verified business"""
    if not request.user.is_superuser:
        messages.error(request, 'Access denied.')
        return redirect('/public/')
    
    business_id = request.GET.get('business_id')
    if not business_id:
        messages.error(request, 'Business ID required.')
        return redirect('/admin/')
    
    try:
        business = Business.objects.get(id=business_id)
        
        if business.schema_name == 'public':
            messages.error(request, 'Cannot create schema for public tenant.')
            return redirect('/admin/')
        
        # Force create the schema
        from django_tenants.utils import schema_context
        from django.core.management import call_command
        from django.db import connection
        
        # Create the schema
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{business.schema_name}"')
        
        # Run migrations for this tenant
        call_command('migrate_schemas', '--tenant', business.schema_name, verbosity=1)
        
        messages.success(request, f'Schema created successfully for business: {business.name}')
        
    except Business.DoesNotExist:
        messages.error(request, 'Business not found.')
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