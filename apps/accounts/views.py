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
from apps.core.decorators import ajax_required
from .models import UserProfile, Business, BusinessSettings, BusinessVerification
from .forms import (
    UserRegistrationForm, UserProfileForm, BusinessRegistrationForm,
    BusinessSettingsForm, BusinessVerificationForm
)
import uuid

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
        return redirect('dashboard')
    
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
                        
                        # Redirect to business registration
                        return redirect('accounts:business_register')
                        
            except Exception as e:
                messages.error(request, f'Registration failed: {str(e)}')
    else:
        form = UserRegistrationForm()
    
    return render(request, 'auth/register.html', {'form': form})

def login_view(request):
    """User login view"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')
            
            # Redirect to next URL or dashboard
            next_url = request.GET.get('next', 'dashboard')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid credentials. Please try again.')
    
    return render(request, 'auth/login.html')

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
def business_register_view(request):
    """Business registration view"""
    # Check if user already owns a business
    if request.user.owned_businesses.exists():
        messages.info(request, 'You already have a registered business.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = BusinessRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():
                    business = form.save(commit=False)
                    business.owner = request.user
                    business.slug = slugify(business.name)
                    
                    # Ensure unique slug
                    original_slug = business.slug
                    counter = 1
                    while Business.objects.filter(slug=business.slug).exists():
                        business.slug = f"{original_slug}-{counter}"
                        counter += 1
                    
                    business.save()
                    
                    # Create business settings
                    BusinessSettings.objects.create(business=business)
                    
                    # Create business verification record
                    BusinessVerification.objects.create(business=business)
                    
                    # Create domain for the business
                    from .models import Domain
                    domain = Domain.objects.create(
                        domain=f"{business.slug}.localhost",  # Change in production
                        tenant=business,
                        is_primary=True
                    )
                    
                    messages.success(request, 'Business registered successfully! Please wait for verification.')
                    return redirect('subscriptions:plans')
                    
            except Exception as e:
                messages.error(request, f'Business registration failed: {str(e)}')
    else:
        form = BusinessRegistrationForm()
    
    return render(request, 'auth/business_register.html', {'form': form})

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
        return redirect('dashboard')

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
        return redirect('dashboard')

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

@login_required
def dashboard_redirect(request):
    """Redirect to appropriate dashboard based on user role"""
    # Check if user has a business
    business = request.user.owned_businesses.first()
    if business:
        # Check if business is verified
        if not business.is_verified:
            messages.warning(request, 'Your business is pending verification.')
            return redirect('accounts:business_verification')
        
        # Check subscription
        if not business.subscription or not business.subscription.is_active:
            messages.warning(request, 'Please choose a subscription plan to continue.')
            return redirect('subscriptions:plans')
        
        # Redirect to business dashboard
        return redirect('businesses:dashboard')
    
    # Check if user is an employee
    try:
        from apps.employees.models import Employee
        employee = Employee.objects.get(user=request.user)
        if employee.is_active:
            return redirect('employees:dashboard')
    except Employee.DoesNotExist:
        pass
    
    # No business or employee role found
    messages.info(request, 'Please register your business or contact your employer.')
    return redirect('accounts:business_register')