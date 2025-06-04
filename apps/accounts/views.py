# apps/accounts/views.py - Updated version

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
    
    # Check if we're in a business tenant (multi-tenant setup)
    if hasattr(request, 'business') and request.business:
        # User is in a business tenant - check if they're an employee
        try:
            from apps.employees.models import Employee
            employee = Employee.objects.get(user=request.user, is_active=True)
            
            # Check business verification
            if not request.business.is_verified:
                if employee.role == 'owner':
                    messages.warning(request, 'Your business is pending verification. Please upload required documents.')
                    return redirect('accounts:business_verification')
                else:
                    messages.info(request, 'Business verification is pending.')
                    return redirect('accounts:verification_pending')
            
            # Check subscription only for verified businesses
            if not request.business.subscription or not request.business.subscription.is_active:
                if employee.role == 'owner':
                    messages.warning(request, 'Please activate your subscription to access all features.')
                    return redirect('subscriptions:plans')
                else:
                    messages.info(request, 'Business subscription is inactive.')
            
            # Redirect based on role for verified businesses
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
        # Check verification status
        if not business.is_verified:
            # Business is not verified yet
            messages.info(request, 'Your business is pending verification. Please check your verification status.')
            return redirect('accounts:verification_pending')
        
        # Business is verified - check if schema exists and redirect to tenant
        domain = business.domains.filter(is_primary=True).first()
        if domain:
            protocol = 'http' if settings.DEBUG else 'https'
            return redirect(f'{protocol}://{domain.domain}/dashboard/')
        else:
            messages.error(request, 'Business domain not configured. Please contact support.')
            return redirect('accounts:verification_pending')
    
    # No business found - redirect to business registration
    messages.info(request, 'Welcome! Please register your business to get started.')
    return redirect('accounts:business_register')

@login_required
def business_register_view(request):
    """Business registration without immediate schema creation"""
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
        business = existing_businesses.first()
        if business.is_verified:
            messages.info(request, 'You already have a verified business.')
            return redirect('accounts:dashboard_redirect')
        else:
            messages.info(request, 'Your business registration is pending verification.')
            return redirect('accounts:verification_pending')
    
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
                    
                    # Create schema name for future use
                    schema_name = re.sub(r'[^a-z0-9]', '', business.name.lower())
                    if not schema_name or not schema_name[0].isalpha():
                        schema_name = 'biz' + schema_name
                    business.schema_name = schema_name[:20]
                    
                    print(f"About to save business: {business.name}")
                    print(f"Schema name (for future): {business.schema_name}")
                    
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
                    
                    # IMPORTANT: Don't create schema yet - wait for verification
                    business.auto_create_schema = False
                    business.is_verified = False  # Explicitly set to False
                    business.save()
                    print(f"Business saved successfully! ID: {business.id}")
                    
                    # Create domain record but don't activate schema yet
                    print("Creating domain record...")
                    if settings.DEBUG:
                        domain_name = f"{business.slug}.localhost:8000"
                    else:
                        domain_name = f"{business.slug}.autowash-3jpr.onrender.com"

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
                    
                    success_message = (
                        f'Business "{business.name}" registered successfully! '
                        f'Please upload verification documents to activate your account.'
                    )
                    messages.success(request, success_message)
                    
                    # Redirect to verification upload
                    return redirect('accounts:business_verification')
                
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
        return redirect('accounts:business_register')
    
    # If business is already verified, redirect to dashboard
    if business.is_verified:
        messages.success(request, 'Your business has been verified!')
        return redirect('accounts:dashboard_redirect')
    
    try:
        verification = business.verification
    except BusinessVerification.DoesNotExist:
        verification = BusinessVerification.objects.create(business=business)
    
    context = {
        'business': business,
        'verification': verification,
        'title': 'Verification Status'
    }
    
    return render(request, 'auth/verification_pending.html', context)

@login_required
def business_verification_view(request):
    """Business verification document upload"""
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
                
                messages.success(request, 'Verification documents submitted successfully! We will review them within 24-48 hours.')
                return redirect('accounts:verification_pending')
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
        return redirect('accounts:dashboard_redirect')

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
    """Business settings view - only for verified businesses"""
    try:
        business = request.user.owned_businesses.first()
        if not business:
            messages.error(request, 'You do not own any business.')
            return redirect('accounts:business_register')
        
        if not business.is_verified:
            messages.warning(request, 'Please complete business verification first.')
            return redirect('accounts:verification_pending')
        
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
        })
    except BusinessVerification.DoesNotExist:
        return JsonResponse({
            'status': 'pending',
            'status_display': 'Pending',
            'is_verified': False,
            'submitted_at': None,
            'verified_at': None,
            'has_documents': False,
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
        'message': 'Name is available' if not exists else 'Name is already taken'
    })