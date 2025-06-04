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
from apps.core.decorators import ajax_required
from .models import UserProfile, Business, BusinessSettings, BusinessVerification
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
    """Smart dashboard redirect based on user context"""
    
    # Check if we're in a business tenant (multi-tenant setup)
    if hasattr(request, 'business') and request.business:
        # User is in a business tenant - check if they're an employee
        try:
            from apps.employees.models import Employee
            employee = Employee.objects.get(user=request.user, is_active=True)
            
            # Check business verification and subscription
            if not request.business.is_verified:
                if employee.role == 'owner':
                    messages.warning(request, 'Please complete business verification.')
                    return redirect('accounts:business_verification')
                else:
                    messages.info(request, 'Business verification is pending.')
            
            if not request.business.subscription or not request.business.subscription.is_active:
                if employee.role == 'owner':
                    messages.warning(request, 'Please activate your subscription.')
                    return redirect('subscriptions:plans')
                else:
                    messages.info(request, 'Business subscription is inactive.')
            
            # Redirect based on role
            if employee.role == 'owner':
                return redirect('businesses:dashboard')
            else:
                return redirect('employees:dashboard')
                
        except Employee.DoesNotExist:
            # User is in tenant but not an employee - shouldn't happen
            messages.error(request, 'Access denied. You are not authorized for this business.')
            return redirect('accounts:logout')
    
    # Public schema - check if user owns a business
    business = request.user.owned_businesses.first()
    if business:
        # Redirect to business tenant
        domain = business.domains.filter(is_primary=True).first()
        if domain:
            return redirect(f'http://{domain.domain}/dashboard/')
        else:
            messages.error(request, 'Business domain not configured.')
            return redirect('subscriptions:plans')
    
    # No business found - redirect to business registration
    messages.info(request, 'Welcome! Please register your business to get started.')
    return redirect('accounts:business_register')

@login_required
def business_register_view(request):
    """Smart business registration view - works for both local and CPanel production"""
    print(f"\n" + "="*50)
    print(f"BUSINESS REGISTER VIEW CALLED")
    print(f"Request method: {request.method}")
    print(f"User: {request.user}")
    print(f"Environment: {'LOCAL' if settings.DEBUG else 'PRODUCTION'}")
    print(f"="*50)
    
    # Check if user already owns a business
    existing_businesses = request.user.owned_businesses.all()
    print(f"Existing businesses count: {existing_businesses.count()}")
    
    if existing_businesses.exists():
        messages.info(request, 'You already have a registered business.')
        return redirect('accounts:dashboard_redirect')
    
    if request.method == 'POST':
        print("\n" + "="*30 + " POST REQUEST " + "="*30)
        
        # Print all POST data
        print("POST data:")
        for key, value in request.POST.items():
            print(f"  {key}: {value}")
        
        # Print all FILES data
        print("FILES data:")
        for key, value in request.FILES.items():
            print(f"  {key}: {value}")
        
        print("\nCreating form...")
        form = BusinessRegistrationForm(request.POST, request.FILES)
        print(f"Form created: {type(form)}")
        
        print(f"Form is bound: {form.is_bound}")
        print(f"Form data: {form.data}")
        
        is_valid = form.is_valid()
        print(f"Form is valid: {is_valid}")
        
        if not is_valid:
            print("=== FORM VALIDATION ERRORS ===")
            for field, errors in form.errors.items():
                print(f"  {field}: {errors}")
            print(f"Non-field errors: {form.non_field_errors()}")
        else:
            print("=== FORM IS VALID - ATTEMPTING SAVE ===")
            try:
                with transaction.atomic():
                    business = form.save(commit=False)
                    business.owner = request.user
                    business.slug = slugify(business.name)
                    
                    # Create schema name for django-tenants
                    schema_name = re.sub(r'[^a-z0-9]', '', business.name.lower())
                    if not schema_name or not schema_name[0].isalpha():
                        schema_name = 'biz' + schema_name
                    business.schema_name = schema_name[:20]
                    
                    print(f"About to save business: {business.name}")
                    print(f"Schema name: {business.schema_name}")
                    
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
                    
                    business.save()
                    print(f"Business saved successfully! ID: {business.id}")
                    
                    # SMART DOMAIN CREATION - Local vs Production
                    print("Creating domain...")
                    from .models import Domain
                    from django.conf import settings
                    
                    if settings.DEBUG:
                        # LOCAL DEVELOPMENT
                        domain_name = f"{business.slug}.localhost:8000"
                        print(f"Creating LOCAL domain: {domain_name}")
                    else:
                        # PRODUCTION (CPanel)
                        domain_name = f"{business.slug}.autowash.co.ke"
                        print(f"Creating PRODUCTION domain: {domain_name}")
                    
                    domain = Domain.objects.create(
                        domain=domain_name,
                        tenant=business,
                        is_primary=True
                    )
                    print(f"Domain created: {domain.domain}")
                    
                    # Create business settings
                    print("Creating business settings...")
                    business_settings = BusinessSettings.objects.create(business=business)
                    print(f"Business settings created: {business_settings.id}")
                    
                    # Create business verification record
                    print("Creating business verification...")
                    verification = BusinessVerification.objects.create(business=business)
                    print(f"Business verification created: {verification.id}")
                    
                    # Skip employee creation for now - handle separately
                    print("Skipping employee creation - will be handled in employee management section")
                    
                    # Smart success message based on environment
                    if settings.DEBUG:
                        success_message = (
                            f'Business "{business.name}" registered successfully! '
                            f'Your local business URL is: http://{domain_name}'
                        )
                    else:
                        success_message = (
                            f'Business "{business.name}" registered successfully! '
                            f'Your business URL is: https://{domain_name}'
                        )
                    
                    messages.success(request, success_message)
                    
                    # Try to redirect to subscriptions, fallback to dashboard
                    try:
                        return redirect('subscriptions:plans')
                    except:
                        print("Subscriptions app not found, redirecting to dashboard")
                        return redirect('accounts:dashboard_redirect')
                
            except Exception as e:
                print(f"=== SAVE ERROR ===")
                print(f"Error: {str(e)}")
                import traceback
                traceback.print_exc()
                messages.error(request, f'Registration failed: {str(e)}')
    else:
        print("\n" + "="*30 + " GET REQUEST " + "="*30)
        form = BusinessRegistrationForm()
        print(f"Empty form created")
    
    print(f"\nRendering template with form: {form}")
    return render(request, 'auth/business_register.html', {'form': form})

def logout_view(request):
    """User logout view"""
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('landing')

@login_required
def profile_view(request):
    """User profile view"""
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('accounts:profile')
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
    """Business settings view"""
    try:
        business = request.user.owned_businesses.first()
        if not business:
            messages.error(request, 'You do not own any business.')
            return redirect('accounts:business_register')
        
        settings_obj, created = BusinessSettings.objects.get_or_create(business=business)
        
        if request.method == 'POST':
            form = BusinessSettingsForm(request.POST, instance=settings_obj)
            if form.is_valid():
                form.save()
                messages.success(request, 'Business settings updated successfully!')
                return redirect('accounts:business_settings')
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
        return redirect('accounts:dashboard_redirect')

@login_required
def business_verification_view(request):
    """Business verification view"""
    try:
        business = request.user.owned_businesses.first()
        if not business:
            messages.error(request, 'You do not own any business.')
            return redirect('accounts:business_register')
        
        verification, created = BusinessVerification.objects.get_or_create(business=business)
        
        if request.method == 'POST':
            form = BusinessVerificationForm(request.POST, request.FILES, instance=verification)
            if form.is_valid():
                verification = form.save(commit=False)
                verification.status = 'in_review'
                verification.save()
                
                messages.success(request, 'Verification documents submitted successfully!')
                return redirect('accounts:business_verification')
        else:
            form = BusinessVerificationForm(instance=verification)
        
        context = {
            'form': form,
            'business': business,
            'verification': verification,
            'title': 'Business Verification'
        }
        return render(request, 'business/verification.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading verification: {str(e)}')
        return redirect('accounts:dashboard_redirect')

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
        'message': 'Name is available' if not exists else 'Name is already taken'
    })