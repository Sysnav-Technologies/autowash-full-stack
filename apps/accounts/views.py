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
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.sites.models import Site

from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.utils import timezone
from datetime import timedelta
import uuid
from django.conf import settings
from apps.core.decorators import ajax_required
from apps.core.management.environment import get_current_environment, get_domain_for_environment, get_environment_context, get_error_message, get_success_message
from .models import UserProfile, Business, BusinessSettings, BusinessVerification, Domain, EmailOTP
from .forms import (
    UserRegistrationForm, UserProfileForm, BusinessRegistrationForm,
    BusinessSettingsForm, BusinessVerificationForm
)

class LandingView(TemplateView):
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
    if request.user.is_authenticated:
        return redirect('accounts:dashboard_redirect')
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save(commit=False)
                    user.is_active = False
                    
                    if form.cleaned_data.get('first_name'):
                        user.first_name = form.cleaned_data['first_name']
                    if form.cleaned_data.get('last_name'):
                        user.last_name = form.cleaned_data['last_name']
                    
                    user.save()
                    
                    UserProfile.objects.create(
                        user=user,
                        phone=form.cleaned_data.get('phone'),
                    )
                    
                    success = send_otp_email(request, user)
                    
                    if success:
                        messages.success(
                            request, 
                            'Account created! Please check your email for the verification code.'
                        )
                        # Include email parameter in redirect
                        return redirect(f"{reverse('accounts:verify_otp')}?email={user.email}")
                    else:
                        messages.error(request, 'Account created but failed to send verification email. Please contact support.')
                        # Include email parameter even if sending failed
                        return redirect(f"{reverse('accounts:verify_otp')}?email={user.email}")
                        
            except Exception as e:
                messages.error(request, f'Registration failed: {str(e)}')
        else:
            # More user-friendly error handling
            for field, errors in form.errors.items():
                for error in errors:
                    if field == '__all__':
                        messages.error(request, error)
                    else:
                        field_label = form.fields[field].label or field.replace('_', ' ').title()
                        messages.error(request, f"{field_label}: {error}")
    else:
        form = UserRegistrationForm()
    
    return render(request, 'auth/register.html', {'form': form})

def send_otp_email(request, user):
    try:
        otp = EmailOTP.generate_otp(user, user.email, purpose='registration')
        
        verification_url = request.build_absolute_uri(
            reverse('accounts:verify_otp') + f'?email={user.email}'
        )
        
        current_site = Site.objects.get_current()
        
        email_context = {
            'user': user,
            'otp_code': otp.otp_code,
            'verification_url': verification_url,
            'current_site': current_site,
            'protocol': 'https' if request.is_secure() else 'http',
            'expires_in_minutes': 10,
        }
        
        subject = render_to_string('account/email/otp_verification_subject.txt', email_context).strip()
        html_message = render_to_string('account/email/otp_verification_message.html', email_context)
        text_message = render_to_string('account/email/otp_verification_message.txt', email_context)
        
        send_mail(
            subject=subject,
            message=text_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        
        return True
        
    except Exception as e:
        print(f"Error sending OTP email: {e}")
        return False


def send_login_otp_email(request, user, otp_code):
    try:
        verification_url = request.build_absolute_uri(
            reverse('accounts:verify_login_otp') + f'?email={user.email}'
        )
        
        current_site = Site.objects.get_current()
        
        email_context = {
            'user': user,
            'otp_code': otp_code,
            'verification_url': verification_url,
            'current_site': current_site,
            'protocol': 'https' if request.is_secure() else 'http',
            'expires_in_minutes': 10,
        }
        
        subject = render_to_string('account/email/login_otp_subject.txt', email_context).strip()
        html_message = render_to_string('account/email/login_otp_message.html', email_context)
        text_message = render_to_string('account/email/login_otp_message.txt', email_context)
        
        send_mail(
            subject=subject,
            message=text_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        
        return True
        
    except Exception as e:
        print(f"Error sending login OTP email: {e}")
        return False


def send_verification_email(request, user):
    """Send email verification using custom templates"""
    try:
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        
        verification_url = request.build_absolute_uri(
            reverse('accounts:verify_email', kwargs={'uidb64': uid, 'token': token})
        )
        
        current_site = Site.objects.get_current()
        
        email_context = {
            'user': user,
            'activate_url': verification_url,
            'current_site': current_site,
            'protocol': 'https' if request.is_secure() else 'http',
        }
        
        subject = render_to_string('account/email/email_confirmation_subject.txt', email_context).strip()
        html_message = render_to_string('account/email/email_confirmation_message.html', email_context)
        text_message = render_to_string('account/email/email_confirmation_message.txt', email_context)
        
        send_mail(
            subject=subject,
            message=text_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        
        return True
        
    except Exception as e:
        print(f"Error sending verification email: {e}")
        return False


def send_business_approval_email(request, business):
    """Send business approval notification email"""
    try:
        from datetime import timedelta
        
        # Calculate trial end date (7 days from approval)
        trial_end_date = business.approved_at + timedelta(days=7)
        
        # Build dashboard URL
        dashboard_url = request.build_absolute_uri(f'/business/{business.slug}/')
        help_center_url = request.build_absolute_uri('/help/')
        login_url = request.build_absolute_uri('/auth/login/')
        
        # Get current site
        current_site = Site.objects.get_current()
        
        # Get subscription info
        subscription_info = {}
        if hasattr(business, 'subscription') and business.subscription:
            subscription_info = {
                'plan_name': business.subscription.plan.name,
                'trial_end': trial_end_date,
                'trial_active': True,
            }
        
        # Prepare email context
        email_context = {
            'business': business,
            'owner': business.owner,
            'trial_end_date': trial_end_date,
            'dashboard_url': dashboard_url,
            'help_center_url': help_center_url,
            'login_url': login_url,
            'current_site': current_site,
            'protocol': 'https' if request.is_secure() else 'http',
            'subscription': subscription_info,
            'approved_by': business.approved_by.get_full_name() if business.approved_by else 'Autowash Team',
        }
        
        # Render email templates
        subject = render_to_string('account/email/business_approval_subject.txt', email_context).strip()
        html_message = render_to_string('account/email/business_approval_message.html', email_context)
        text_message = render_to_string('account/email/business_approval_message.txt', email_context)
        
        # Send email to business owner
        send_mail(
            subject=subject,
            message=text_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[business.owner.email],
            fail_silently=False,
        )
        
        # Also send to business email if different
        if business.email and business.email != business.owner.email:
            send_mail(
                subject=subject,
                message=text_message,
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[business.email],
                fail_silently=False,
            )
        
        return True
        
    except Exception as e:
        print(f"Error sending business approval email: {e}")
        return False


def send_business_registration_email(request, business):
    """Send business registration confirmation email"""
    try:
        from datetime import timedelta
        
        # Calculate trial end date (7 days from approval, not registration)
        # Note: Trial starts after admin approval
        trial_end_date = business.created_at + timedelta(days=7)
        
        # Build dashboard URL
        dashboard_url = request.build_absolute_uri(f'/business/{business.slug}/')
        help_center_url = request.build_absolute_uri('/help/')
        
        # Get current site
        current_site = Site.objects.get_current()
        
        # Prepare email context
        email_context = {
            'business': business,
            'trial_end_date': trial_end_date,
            'dashboard_url': dashboard_url,
            'help_center_url': help_center_url,
            'current_site': current_site,
            'protocol': 'https' if request.is_secure() else 'http',
        }
        
        # Render email templates
        subject = render_to_string('account/email/business_registration_subject.txt', email_context).strip()
        html_message = render_to_string('account/email/business_registration_message.html', email_context)
        text_message = render_to_string('account/email/business_registration_message.txt', email_context)
        
        # Send email to business owner
        send_mail(
            subject=subject,
            message=text_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[business.owner.email],
            fail_silently=False,
        )
        
        # Also send to business email if different
        if business.email and business.email != business.owner.email:
            send_mail(
                subject=subject,
                message=text_message,
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[business.email],
                fail_silently=False,
            )
        
        return True
        
    except Exception as e:
        print(f"Error sending business registration email: {e}")
        return False


def send_login_notification_email(request, user):
    """Send login notification email similar to Google's security alerts"""
    try:
        # Check if user wants to receive login notifications
        try:
            if hasattr(user, 'profile') and not user.profile.receive_login_notifications:
                return True  # User opted out
        except Exception:
            pass  # Continue if profile doesn't exist
        
        # Get client information
        ip_address = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Parse user agent for device and browser info
        device_info, browser_info = parse_user_agent(user_agent)
        
        # Get location from IP (you can integrate with a GeoIP service)
        location = get_location_from_ip(ip_address)
        
        # Build dashboard URL for the user's business
        dashboard_url = request.build_absolute_uri('/auth/dashboard/')
        business = user.owned_tenants.first()
        if business:
            dashboard_url = request.build_absolute_uri(f'/business/{business.slug}/')
        
        # Get current site
        current_site = Site.objects.get_current()
        
        # Prepare email context
        email_context = {
            'user': user,
            'login_time': timezone.now(),
            'ip_address': ip_address,
            'device_info': device_info,
            'browser_info': browser_info,
            'location': location,
            'dashboard_url': dashboard_url,
            'current_site': current_site,
            'current_year': timezone.now().year,
            'protocol': 'https' if request.is_secure() else 'http',
        }
        
        # Render email templates
        subject = render_to_string('account/email/login_notification_subject.txt', email_context).strip()
        html_message = render_to_string('account/email/login_notification_message.html', email_context)
        text_message = render_to_string('account/email/login_notification_message.txt', email_context)
        
        # Send email
        send_mail(
            subject=subject,
            message=text_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        
        return True
        
    except Exception as e:
        print(f"Error sending login notification email: {e}")
        return False


def get_client_ip(request):
    """Get the client's IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def parse_user_agent(user_agent):
    """Parse user agent string to extract device and browser information"""
    device_info = "Unknown Device"
    browser_info = "Unknown Browser"
    
    try:
        # Simple user agent parsing (you can use a library like user-agents for better parsing)
        user_agent_lower = user_agent.lower()
        
        # Device detection
        if 'mobile' in user_agent_lower or 'android' in user_agent_lower or 'iphone' in user_agent_lower:
            if 'android' in user_agent_lower:
                device_info = "Android Device"
            elif 'iphone' in user_agent_lower:
                device_info = "iPhone"
            elif 'ipad' in user_agent_lower:
                device_info = "iPad"
            else:
                device_info = "Mobile Device"
        elif 'macintosh' in user_agent_lower or 'mac os' in user_agent_lower:
            device_info = "Mac"
        elif 'windows' in user_agent_lower:
            device_info = "Windows PC"
        elif 'linux' in user_agent_lower:
            device_info = "Linux PC"
        
        # Browser detection
        if 'chrome' in user_agent_lower and 'edg' not in user_agent_lower:
            browser_info = "Google Chrome"
        elif 'firefox' in user_agent_lower:
            browser_info = "Mozilla Firefox"
        elif 'safari' in user_agent_lower and 'chrome' not in user_agent_lower:
            browser_info = "Safari"
        elif 'edg' in user_agent_lower:
            browser_info = "Microsoft Edge"
        elif 'opera' in user_agent_lower:
            browser_info = "Opera"
        
    except Exception:
        pass
    
    return device_info, browser_info


def get_location_from_ip(ip_address):
    """Get approximate location from IP address"""
    # For now, return a simple placeholder
    # You can integrate with services like:
    # - GeoIP2 (MaxMind)
    # - ipapi.co
    # - ip-api.com
    try:
        if ip_address and ip_address != '127.0.0.1' and not ip_address.startswith('192.168.'):
            # This is a public IP, you could do a real lookup here
            return "Approximate location available"
        else:
            return "Local/Private network"
    except Exception:
        return "Unknown"

def login_view(request):
    """User login view with enhanced error handling"""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard_redirect')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Try to find user by email or username
        try:
            if '@' in username:
                # Login with email
                user_obj = User.objects.get(email=username)
                username = user_obj.username
        except User.DoesNotExist:
            pass  # Username will be used as-is
        
        user = authenticate(request, username=username, password=password)
        if user:
            if user.is_active:
                login(request, user)
                messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')
                
                # Send login notification email (async to not slow down login)
                try:
                    from threading import Thread
                    email_thread = Thread(
                        target=send_login_notification_email,
                        args=(request, user)
                    )
                    email_thread.daemon = True
                    email_thread.start()
                except Exception as e:
                    print(f"Failed to start login notification email thread: {e}")
                
                # Redirect to next URL or dashboard
                next_url = request.GET.get('next', 'accounts:dashboard_redirect')
                return redirect(next_url)
            else:
                # User exists but email is not verified - redirect to OTP verification
                messages.warning(request, 'Your email address is not verified. Please check your email for the verification code.')
                
                # Automatically resend OTP verification email
                try:
                    send_otp_email(request, user)
                    messages.info(request, 'A new verification code has been sent to your email.')
                except Exception as e:
                    print(f"Failed to send OTP email: {e}")
                    messages.error(request, 'Failed to send verification code. Please try again.')
                
                # Redirect to OTP verification with email parameter
                return redirect(f"{reverse('accounts:verify_otp')}?email={user.email}")
        else:
            messages.error(request, 'Invalid credentials. Please try again.')
    
    return render(request, 'auth/login.html')

def verify_email(request, uidb64, token):
    """Email verification view with automatic login and redirect to business registration"""
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.http import urlsafe_base64_decode
    from django.utils.encoding import force_str
    from django.contrib.auth import login
    
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    
    if user is not None and default_token_generator.check_token(user, token):
        if not user.is_active:
            user.is_active = True
            user.save()
            
            # Automatically log the user in
            login(request, user)
            
            messages.success(request, 'Email verified successfully! Now let\'s set up your business.')
            # Redirect directly to business registration
            return redirect('accounts:business_register')
        else:
            # User already verified, check if they have a business
            login(request, user)
            business = user.owned_tenants.first()
            if business:
                messages.info(request, 'Welcome back!')
                return redirect('accounts:dashboard_redirect')
            else:
                messages.info(request, 'Your email is already verified. Let\'s complete your business setup.')
                return redirect('accounts:business_register')
    else:
        messages.error(request, 'The verification link is invalid or has expired.')
        return redirect('accounts:login')

def verify_otp(request):
    """OTP verification view - supports both form submission and URL parameters"""
    if request.user.is_authenticated and request.user.is_active:
        return redirect('accounts:dashboard_redirect')
    
    # Check if email is provided via URL parameter
    email_from_url = request.GET.get('email', '').strip()
    
    # If no email provided and it's a GET request, redirect to registration
    if not email_from_url and request.method == 'GET':
        messages.info(request, 'Please complete the registration process first.')
        return redirect('accounts:register')
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        otp_code = request.POST.get('otp_code', '').strip()
        
        if not email:
            messages.error(request, 'Email address is required. Please ensure you accessed this page from the registration flow.')
            return render(request, 'auth/verify_otp.html', {'email': email_from_url or ''})
        
        if not otp_code:
            messages.error(request, 'Please enter the 6-digit verification code.')
            return render(request, 'auth/verify_otp.html', {'email': email})
        
        if len(otp_code) != 6 or not otp_code.isdigit():
            messages.error(request, 'Please enter a valid 6-digit verification code.')
            return render(request, 'auth/verify_otp.html', {'email': email})
        
        try:
            # Find user by email
            user = User.objects.get(email=email)
            
            # Find valid OTP
            otp = EmailOTP.objects.filter(
                user=user,
                email=email,
                otp_code=otp_code,
                purpose='registration',
                is_used=False
            ).first()
            
            if otp and otp.is_valid():
                # Mark OTP as used
                otp.mark_as_used()
                
                # Activate user
                user.is_active = True
                user.save()
                
                # Automatically log the user in
                from django.contrib.auth import login
                login(request, user)
                
                messages.success(request, 'Email verified successfully! Now let\'s set up your business.')
                return redirect('accounts:business_register')
            else:
                if otp and not otp.is_valid():
                    messages.error(request, 'Verification code has expired. Please request a new one.')
                else:
                    messages.error(request, 'Invalid verification code. Please check your email and try again.')
                
        except User.DoesNotExist:
            messages.error(request, 'No account found with this email address.')
        except Exception as e:
            messages.error(request, 'Verification failed. Please try again.')
    
    # Pass email to template if provided via URL
    context = {
        'email': email_from_url or ''
    }
    
    return render(request, 'auth/verify_otp.html', context)

def resend_otp(request):
    """Resend OTP verification code"""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        
        if not email:
            messages.error(request, 'Please provide your email address.')
            return redirect('accounts:verify_otp')
        
        try:
            user = User.objects.get(email=email, is_active=False)
            
            # Check if we can send a new OTP (rate limiting)
            recent_otp = EmailOTP.objects.filter(
                user=user,
                email=email,
                purpose='registration',
                created_at__gte=timezone.now() - timedelta(minutes=1)
            ).first()
            
            if recent_otp:
                messages.warning(request, 'Please wait at least 1 minute before requesting a new code.')
                return redirect('accounts:verify_otp')
            
            # Send new OTP
            success = send_otp_email(request, user)
            
            if success:
                messages.success(request, 'New verification code sent to your email.')
            else:
                messages.error(request, 'Failed to send verification code. Please try again.')
                
        except User.DoesNotExist:
            messages.error(request, 'No pending account found with this email address.')
        except Exception as e:
            messages.error(request, 'Failed to send verification code. Please try again.')
    
    return redirect('accounts:verify_otp')

def email_login_view(request):
    """Email-based OTP login - step 1: enter email"""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard_redirect')
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        
        if not email:
            messages.error(request, 'Please provide your email address.')
            return render(request, 'auth/email_login.html')
        
        try:
            user = User.objects.get(email=email)
            
            if not user.is_active:
                # User exists but email is not verified - redirect to OTP verification
                messages.warning(request, 'Your email address is not verified. Please check your email for the verification code.')
                
                # Automatically resend OTP verification email
                try:
                    send_otp_email(request, user)
                    messages.info(request, 'A new verification code has been sent to your email.')
                except Exception as e:
                    print(f"Failed to send OTP email: {e}")
                    messages.error(request, 'Failed to send verification code. Please try again.')
                
                # Redirect to OTP verification with email parameter
                return redirect(f"{reverse('accounts:verify_otp')}?email={user.email}")
            
            # Check rate limiting - don't allow more than 1 OTP per minute
            recent_otp = EmailOTP.objects.filter(
                user=user,
                email=email,
                purpose='login',
                created_at__gte=timezone.now() - timedelta(minutes=1)
            ).first()
            
            if recent_otp:
                messages.warning(request, 'Please wait at least 1 minute before requesting a new login code.')
                return render(request, 'auth/email_login.html')
            
            # Generate and send login OTP
            otp = EmailOTP.generate_otp(user, email, purpose='login', expires_in_minutes=10)
            success = send_login_otp_email(request, user, otp.otp_code)
            
            if success:
                messages.success(request, f'Login code sent to {email}. Please check your email.')
                return redirect(reverse('accounts:verify_login_otp') + f'?email={email}')
            else:
                messages.error(request, 'Failed to send login code. Please try again.')
                return render(request, 'auth/email_login.html')
                
        except User.DoesNotExist:
            messages.error(request, 'No account found with this email address.')
            return render(request, 'auth/email_login.html')
        except Exception as e:
            messages.error(request, 'Failed to send login code. Please try again.')
            return render(request, 'auth/email_login.html')
    
    return render(request, 'auth/email_login.html')

def verify_login_otp(request):
    """Email-based OTP login - step 2: verify OTP and login"""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard_redirect')
    
    email = request.GET.get('email', '')
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        otp_code = request.POST.get('otp_code', '').strip()
        
        if not email or not otp_code:
            messages.error(request, 'Please provide both email and verification code.')
            return render(request, 'auth/verify_login_otp.html', {'email': email})
        
        if len(otp_code) != 6 or not otp_code.isdigit():
            messages.error(request, 'Please enter a valid 6-digit verification code.')
            return render(request, 'auth/verify_login_otp.html', {'email': email})
        
        try:
            user = User.objects.get(email=email, is_active=True)
            
            # Find valid OTP
            valid_otp = EmailOTP.objects.filter(
                user=user,
                email=email,
                otp_code=otp_code,
                purpose='login',
                is_used=False,
                expires_at__gt=timezone.now()
            ).first()
            
            if valid_otp:
                # Mark OTP as used
                valid_otp.is_used = True
                valid_otp.save()
                
                # Log the user in
                from django.contrib.auth import login
                login(request, user)
                
                messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')
                
                # Send login notification email (async)
                try:
                    from threading import Thread
                    email_thread = Thread(
                        target=send_login_notification_email,
                        args=(request, user)
                    )
                    email_thread.daemon = True
                    email_thread.start()
                except Exception as e:
                    print(f"Failed to start login notification email thread: {e}")
                
                # Redirect to next URL or dashboard
                next_url = request.GET.get('next', 'accounts:dashboard_redirect')
                return redirect(next_url)
            else:
                # Check if OTP exists but is expired/used
                expired_otp = EmailOTP.objects.filter(
                    user=user,
                    email=email,
                    otp_code=otp_code,
                    purpose='login'
                ).first()
                
                if expired_otp:
                    if expired_otp.is_used:
                        messages.error(request, 'This verification code has already been used.')
                    else:
                        messages.error(request, 'This verification code has expired. Please request a new one.')
                else:
                    messages.error(request, 'Invalid verification code. Please try again.')
                
                return render(request, 'auth/verify_login_otp.html', {'email': email})
                
        except User.DoesNotExist:
            messages.error(request, 'No active account found with this email address.')
            return render(request, 'auth/verify_login_otp.html', {'email': email})
        except Exception as e:
            messages.error(request, 'Login failed. Please try again.')
            return render(request, 'auth/verify_login_otp.html', {'email': email})
    
    return render(request, 'auth/verify_login_otp.html', {'email': email})

def resend_login_otp(request):
    """Resend login OTP code"""
    if request.method == 'POST':
        # Handle both form data and JSON requests
        if request.content_type == 'application/json':
            import json
            try:
                data = json.loads(request.body)
                email = data.get('email', '').strip().lower()
            except json.JSONDecodeError:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid JSON data.'
                }, status=400)
        else:
            email = request.POST.get('email', '').strip().lower()
        
        if not email:
            if request.content_type == 'application/json' or request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': 'Please provide your email address.'
                }, status=400)
            messages.error(request, 'Please provide your email address.')
            return redirect('accounts:email_login')
        
        try:
            user = User.objects.get(email=email, is_active=True)
            
            # Check rate limiting
            recent_otp = EmailOTP.objects.filter(
                user=user,
                email=email,
                purpose='login',
                created_at__gte=timezone.now() - timedelta(minutes=1)
            ).first()
            
            if recent_otp:
                if request.content_type == 'application/json' or request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': 'Please wait at least 1 minute before requesting a new code.'
                    }, status=429)
                messages.warning(request, 'Please wait at least 1 minute before requesting a new code.')
                return redirect(reverse('accounts:verify_login_otp') + f'?email={email}')
            
            # Generate and send new login OTP
            otp = EmailOTP.generate_otp(user, email, purpose='login', expires_in_minutes=10)
            success = send_login_otp_email(request, user, otp.otp_code)
            
            if success:
                if request.content_type == 'application/json' or request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'message': 'New login code sent to your email.'
                    })
                messages.success(request, 'New login code sent to your email.')
            else:
                if request.content_type == 'application/json' or request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': 'Failed to send login code. Please try again.'
                    }, status=500)
                messages.error(request, 'Failed to send login code. Please try again.')
                
        except User.DoesNotExist:
            if request.content_type == 'application/json' or request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': 'No active account found with this email address.'
                }, status=404)
            messages.error(request, 'No active account found with this email address.')
        except Exception as e:
            if request.content_type == 'application/json' or request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': 'Failed to send login code. Please try again.'
                }, status=500)
            messages.error(request, 'Failed to send login code. Please try again.')
    
    # For non-AJAX requests or GET requests
    if request.method == 'GET':
        email = request.GET.get('email', '')
    else:
        email = request.POST.get('email', '') if request.content_type != 'application/json' else ''
    return redirect(reverse('accounts:verify_login_otp') + f'?email={email}')

# Password Reset view with enhanced templates
def password_reset_view(request):
    """Password reset view with HTML email templates"""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard_redirect')
    
    if request.method == 'POST':
        email = request.POST.get('email')
        if email:
            try:
                user = User.objects.get(email=email)
                
                # Generate reset token
                from django.contrib.auth.tokens import default_token_generator
                from django.utils.http import urlsafe_base64_encode
                from django.utils.encoding import force_bytes
                
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                
                # Build reset URL
                reset_url = request.build_absolute_uri(
                    reverse('accounts:password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
                )
                
                # Get current site
                current_site = Site.objects.get_current()
                
                # Prepare email context
                email_context = {
                    'user': user,
                    'password_reset_url': reset_url,
                    'current_site': current_site,
                    'protocol': 'https' if request.is_secure() else 'http',
                }
                
                # Render email templates
                subject = render_to_string('account/email/password_reset_key_subject.txt', email_context).strip()
                text_message = render_to_string('account/email/password_reset_key_message.txt', email_context)
                
                # Send email
                send_mail(
                    subject=subject,
                    message=text_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                )
                
                messages.success(request, 'Password reset email sent! Please check your inbox.')
                return redirect('accounts:password_reset_done')
            except User.DoesNotExist:
                # Don't reveal if email exists for security
                messages.success(request, 'If an account with that email exists, a password reset email has been sent.')
                return redirect('accounts:password_reset_done')
        else:
            messages.error(request, 'Email is required.')
    
    return render(request, 'auth/password_reset.html')

def password_reset_confirm_view(request, uidb64, token):
    """Password reset confirmation view"""
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.http import urlsafe_base64_decode
    from django.utils.encoding import force_str
    
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    
    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            password1 = request.POST.get('new_password1')
            password2 = request.POST.get('new_password2')
            
            if password1 and password2:
                if password1 == password2:
                    user.set_password(password1)
                    user.save()
                    messages.success(request, 'Your password has been reset successfully!')
                    return redirect('accounts:password_reset_complete')
                else:
                    messages.error(request, 'Passwords do not match.')
            else:
                messages.error(request, 'Both password fields are required.')
        
        context = {
            'validlink': True,
            'form_action': reverse('accounts:password_reset_confirm', kwargs={'uidb64': uidb64, 'token': token})
        }
        return render(request, 'auth/password_reset_confirm.html', context)
    else:
        messages.error(request, 'The password reset link is invalid or has expired.')
        return redirect('accounts:password_reset')


def password_reset_done_view(request):
    """Password reset email sent confirmation"""
    return render(request, 'auth/password_reset_done.html')


def password_reset_complete_view(request):
    """Password reset complete confirmation"""
    return render(request, 'auth/password_reset_complete.html')


@login_required
def password_change_view(request):
    """Password change view for authenticated users"""
    if request.method == 'POST':
        old_password = request.POST.get('old_password')
        new_password1 = request.POST.get('new_password1')
        new_password2 = request.POST.get('new_password2')
        
        # Validate old password
        if not request.user.check_password(old_password):
            messages.error(request, 'Your old password was entered incorrectly. Please enter it again.')
            return render(request, 'auth/password_change.html')
        
        # Validate new passwords match
        if new_password1 != new_password2:
            messages.error(request, 'The two password fields didn\'t match.')
            return render(request, 'auth/password_change.html')
        
        # Validate password strength (basic validation)
        if len(new_password1) < 8:
            messages.error(request, 'Your password must contain at least 8 characters.')
            return render(request, 'auth/password_change.html')
        
        # Change password
        request.user.set_password(new_password1)
        request.user.save()
        
        # Update session to prevent logout
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(request, request.user)
        
        messages.success(request, 'Your password has been changed successfully!')
        return redirect('accounts:password_change_done')
    
    return render(request, 'auth/password_change.html')


@login_required
def password_change_done_view(request):
    """Password change success confirmation"""
    return render(request, 'auth/password_change_done.html')


def email_verification_sent(request):
    """Email verification sent confirmation"""
    return render(request, 'account/email_verification_sent.html')


def resend_verification_email(request):
    """Resend email verification using OTP"""
    if request.method == 'POST':
        if request.user.is_authenticated and not request.user.is_active:
            try:
                send_otp_email(request, request.user)
                messages.success(request, 'A new verification code has been sent to your email.')
                return redirect(f"{reverse('accounts:verify_otp')}?email={request.user.email}")
            except Exception as e:
                print(f"Failed to send OTP email: {e}")
                messages.error(request, 'Failed to send verification code. Please try again.')
        else:
            messages.error(request, 'Unable to resend verification email.')
    
    return redirect('accounts:verify_otp')


def email_verification_success_view(request):
    """Email verification success page"""
    return render(request, 'account/email_verification_success.html')


@login_required
def dashboard_redirect(request):
    """Smart dashboard redirect based on user context and complete authentication flow"""
    print(f"\n" + "="*50)
    print(f"DASHBOARD REDIRECT CALLED")
    print(f"User: {request.user.username}")
    print(f"Current path: {request.path}")
    print(f"Request META HOST: {request.META.get('HTTP_HOST')}")
    print(f"="*50)
    
    # First check if user email is verified
    if not request.user.is_active:
        messages.warning(request, 'Please verify your email address first.')
        # Send OTP and redirect to verification
        try:
            send_otp_email(request, request.user)
            messages.info(request, 'A verification code has been sent to your email.')
        except Exception as e:
            print(f"Failed to send OTP email: {e}")
        
        return redirect(f"{reverse('accounts:verify_otp')}?email={request.user.email}")
    
    # Check if user owns a business
    business = request.user.owned_tenants.first()
    print(f"User owned business: {business}")
    
    if business:
        print(f"Business found: {business.name}")
        print(f"Business slug: {business.slug}")
        print(f"Business verified: {business.is_verified}")
        print(f"Business approved: {business.is_approved}")
        
        # Step 1: Check if business registration is complete
        if not business.name or not business.phone or not business.email:
            messages.info(request, 'Please complete your business registration.')
            return redirect('/auth/business/register/')
        
        # Step 2: Check subscription status
        has_active_subscription = False
        has_expired_subscription = False
        try:
            # Check if business has an active subscription using the direct subscription field
            has_active_subscription = (
                business.subscription is not None and 
                business.subscription.status in ['active', 'trial'] and
                business.subscription.is_active
            )
            
            # Check if business has an expired/inactive subscription
            has_expired_subscription = (
                business.subscription is not None and 
                business.subscription.status in ['expired', 'cancelled'] and
                not business.subscription.is_active
            )
            
            print(f"Active subscription check result: {has_active_subscription}")
            print(f"Expired subscription check result: {has_expired_subscription}")
            if business.subscription:
                print(f"Subscription status: {business.subscription.status}")
                print(f"Subscription is_active: {business.subscription.is_active}")
        except Exception as e:
            print(f"Error checking subscription: {e}")
            has_active_subscription = False
            has_expired_subscription = False
            
        print(f"Has active subscription: {has_active_subscription}")
        print(f"Has expired subscription: {has_expired_subscription}")
        
        # Handle different subscription states
        if has_expired_subscription:
            print("Expired subscription found, redirecting to subscription renewal/upgrade")
            messages.warning(request, 'Your subscription has expired. Please renew or upgrade to continue using our services.')
            return redirect(f'/business/{business.slug}/subscriptions/upgrade/')
        elif not has_active_subscription and not has_expired_subscription:
            print("No subscription found, redirecting to subscription selection")
            messages.info(request, 'Please select a subscription plan to continue.')
            return redirect('/subscriptions/select/')
        
        # Step 3: Check if business is approved by admin
        if not business.is_approved:
            # Check verification status
            try:
                verification = business.verification
                if verification.status == 'pending':
                    messages.info(request, 'Your business is awaiting admin approval. You will receive an email once approved.')
                elif verification.status == 'in_review':
                    messages.info(request, 'Your business documents are under review. You will receive an email once approved.')
                elif verification.status == 'rejected':
                    messages.warning(request, f'Your business registration was rejected: {business.rejection_reason or "Please contact support for details."}')
                else:
                    messages.info(request, 'Your business is pending approval. You will receive an email once approved.')
            except:
                messages.info(request, 'Your business is pending approval. You will receive an email once approved.')
            
            return redirect('/auth/verification-pending/')
        
        # Step 4: Check if subscription is active (trial or paid)
        if business.subscription and not business.subscription.is_active:
            # Check if trial period has started (trial starts after approval)
            from datetime import timedelta
            from django.utils import timezone
            
            if business.approved_at:
                trial_end = business.approved_at + timedelta(days=7)
                if timezone.now() <= trial_end:
                    # Still in trial period
                    messages.success(request, f'Your 7-day trial is active until {trial_end.strftime("%B %d, %Y")}.')
                else:
                    # Trial expired
                    messages.warning(request, 'Your trial period has expired. Please upgrade your subscription.')
                    return redirect('/subscriptions/upgrade/')
            else:
                # No approval date set - shouldn't happen but handle gracefully
                messages.warning(request, 'Please contact support to activate your subscription.')
                return redirect('/auth/verification-pending/')
        
        # Step 5: Check if business is verified (final step)
        if not business.is_verified:
            messages.info(request, 'Your business setup is being finalized. Please wait a moment...')
            return redirect('/auth/verification-pending/')
        
        # All checks passed - redirect to business dashboard
        business_url = f'/business/{business.slug}/'
        print(f"Redirecting to business dashboard: {business_url}")
        return redirect(business_url)
    
    # User doesn't own a business - check if they're an employee
    print("No owned business found, checking for employee records...")
    
    # Search across all verified and approved tenants for this user's employee record
    try:
        from apps.core.tenant_models import Tenant
        
        verified_tenants = Tenant.objects.filter(
            is_verified=True, 
            is_active=True, 
            is_approved=True
        )
        
        employee_business = None
        
        for tenant in verified_tenants:
            try:
                # Use the tenant database to check for employee record
                from apps.employees.models import Employee
                
                # Check if user has an employee record in this tenant
                # Use the correct database alias format for tenant routing
                db_alias = f"tenant_{tenant.id}"
                
                # Ensure tenant database is registered in settings
                from apps.core.database_router import TenantDatabaseManager
                TenantDatabaseManager.add_tenant_to_settings(tenant)
                
                employee = Employee.objects.using(db_alias).filter(
                    user_id=request.user.id, 
                    is_active=True
                ).first()
                
                if employee:
                    employee_business = tenant
                    print(f"Found employee record in business: {tenant.name}")
                    print(f"Employee ID: {employee.employee_id}")
                    print(f"Employee role: {employee.role}")
                    break
                        
            except (ImportError, LookupError, ConnectionError) as e:
                # Skip tenants where we can't check due to database/import issues
                print(f"Could not check tenant {tenant.name} due to {type(e).__name__}: {e}")
                continue
            except Exception as e:
                # Log other exceptions but don't let them stop the search
                print(f"Unexpected error checking tenant {tenant.name}: {e}")
                continue
        
        if employee_business:
            # User is an employee - redirect to their business dashboard based on role
            from apps.employees.models import Employee
            
            try:
                # Use the correct database alias format for tenant routing
                db_alias = f"tenant_{employee_business.id}"
                
                # Ensure tenant database is registered in settings
                from apps.core.database_router import TenantDatabaseManager
                TenantDatabaseManager.add_tenant_to_settings(employee_business)
                
                employee = Employee.objects.using(db_alias).filter(
                    user_id=request.user.id, 
                    is_active=True
                ).first()
                
                if employee:
                    # Role-based redirect
                    if employee.role in ['owner', 'manager']:
                        # Management roles get full business dashboard
                        business_url = f'/business/{employee_business.slug}/'
                    elif employee.role == 'supervisor':
                        # Supervisors get service management focus
                        business_url = f'/business/{employee_business.slug}/services/'
                    elif employee.role == 'attendant':
                        # Attendants get their specific dashboard
                        business_url = f'/business/{employee_business.slug}/services/dashboard/'
                    elif employee.role == 'cleaner':
                        # Cleaners get employee dashboard
                        business_url = f'/business/{employee_business.slug}/employees/dashboard/'
                    elif employee.role == 'cashier':
                        # Cashiers get payments focus
                        business_url = f'/business/{employee_business.slug}/payments/'
                    else:
                        # Default to employee dashboard
                        business_url = f'/business/{employee_business.slug}/employees/dashboard/'
                    
                    print(f"Redirecting {employee.role} to: {business_url}")
                    messages.success(request, f'Welcome back! Redirecting to your {employee_business.name} workspace.')
                    return redirect(business_url)
                else:
                    # Fallback if employee object not found
                    business_url = f'/business/{employee_business.slug}/'
                    
            except Exception as e:
                print(f"Error getting employee details: {e}")
                business_url = f'/business/{employee_business.slug}/'
            
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
                'verified': biz.is_verified,
                'approved': biz.is_approved
            })
        
        # Add employee businesses (only verified and approved)
        verified_tenants = Tenant.objects.filter(
            is_verified=True, 
            is_active=True, 
            is_approved=True
        )
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
                        'approved': True,
                        'employee': employee
                    })
            except:
                continue
        
        if len(all_businesses) > 1:
            # User has multiple business access - show selection page
            print(f"User has access to {len(all_businesses)} businesses")
            return redirect('/auth/switch-business/')
        
        elif len(all_businesses) == 1:
            # User has access to one business - check its status
            business_access = all_businesses[0]
            biz = business_access['business']
            
            if business_access['access_type'] == 'owner':
                # For owned businesses, check the full flow
                if not business_access['approved']:
                    messages.info(request, 'Your business is pending approval.')
                    return redirect('/auth/verification-pending/')
                elif not business_access['verified']:
                    messages.info(request, 'Your business is being finalized.')
                    return redirect('/auth/verification-pending/')
                else:
                    # Business is fully approved and verified
                    business_url = f'/business/{biz.slug}/'
                    return redirect(business_url)
            else:
                # Employee access - business should already be verified and approved
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
    """Streamlined business registration view for authenticated users"""
    
    # Detect current environment
    environment = get_current_environment()
    
    print(f"\n" + "="*50)
    print(f"STREAMLINED BUSINESS REGISTER VIEW")
    print(f"Request method: {request.method}")
    print(f"User: {request.user}")
    print(f"Environment: {environment.upper()}")
    print(f"="*50)
    
    # Check if user already owns a business
    existing_businesses = request.user.owned_tenants.all()
    print(f"Existing businesses count: {existing_businesses.count()}")
    
    if existing_businesses.exists():
        business = existing_businesses.first()
        if business.is_verified and business.is_approved:
            messages.info(request, 'You already have a verified business.')
            return redirect(f'/business/{business.slug}/')
        else:
            messages.info(request, 'Your business registration is being processed.')
            return redirect('/subscriptions/select/')
    
    if request.method == 'POST':
        print("\n" + "="*30 + " POST REQUEST " + "="*30)
        
        form = BusinessRegistrationForm(request.POST)
        print(f"Form is valid: {form.is_valid()}")
        
        if form.is_valid():
            print("=== FORM IS VALID - ATTEMPTING SAVE ===")
            try:
                with transaction.atomic():
                    business = form.save(commit=False)
                    
                    # Set the owner
                    business.owner = request.user
                    
                    # Create database name for tenant based on subdomain
                    clean_subdomain = re.sub(r'[^a-z0-9]', '', business.subdomain.lower())
                    if not clean_subdomain or not clean_subdomain[0].isalpha():
                        clean_subdomain = 'biz' + clean_subdomain
                    db_name = f"autowash_{clean_subdomain}"
                    business.database_name = db_name[:63]  # MySQL max db name length
                    
                    # Use main database credentials
                    default_db = settings.DATABASES['default']
                    business.database_user = default_db['USER']
                    business.database_password = default_db['PASSWORD']
                    
                    # Set account password for the user (since it wasn't set during registration)
                    account_password = form.cleaned_data.get('account_password')
                    if account_password:
                        request.user.set_password(account_password)
                        request.user.save()
                        print(f"Account password set for user: {request.user.username}")
                        
                        # Re-authenticate the user with new password
                        from django.contrib.auth import update_session_auth_hash
                        update_session_auth_hash(request, request.user)
                    
                    print(f"About to save business: {business.name}")
                    print(f"Subdomain: {business.subdomain}")
                    print(f"Database name: {business.database_name}")
                    
                    # Check for conflicts and handle
                    original_subdomain = business.subdomain
                    original_database_name = business.database_name
                    counter = 1
                    while (Business.objects.filter(subdomain=business.subdomain).exists() or 
                           Business.objects.filter(database_name=business.database_name).exists()):
                        business.subdomain = f"{original_subdomain}{counter}"
                        business.database_name = f"{original_database_name}{counter}"
                        counter += 1
                    
                    # Set initial status - needs admin approval
                    business.is_active = False
                    business.is_verified = False
                    business.is_approved = False
                    business.save()
                    print(f"Business saved successfully! ID: {business.id}")
                    
                    # Create domain record for path-based routing
                    print("Creating domain record...")
                    domain_name = get_domain_for_environment(business.subdomain, environment)
                    domain = Domain.objects.create(
                        domain=domain_name,
                        tenant=business,
                        is_primary=True
                    )
                    print(f"Domain record created: {domain.domain}")
                    
                    # Create business verification record
                    print("Creating business verification...")
                    BusinessVerification.objects.create(
                        business=business, 
                        status='pending',
                        notes='Business registered - awaiting admin approval',
                        submitted_at=timezone.now()
                    )
                    
                    print("Business registration complete - waiting for admin approval")
                    
                    # Send business registration confirmation email
                    print("Sending business registration email...")
                    email_sent = send_business_registration_email(request, business)
                    if email_sent:
                        print("Business registration email sent successfully")
                    
                    # Success message and redirect to subscription selection
                    success_message = f"Business '{business.name}' registered successfully! Please select a subscription plan to continue."
                    messages.success(request, success_message)
                    
                    # Redirect to subscription selection
                    return redirect('/subscriptions/select/')
                
            except Exception as e:
                print(f"=== SAVE ERROR ===")
                print(f"Error: {str(e)}")
                import traceback
                traceback.print_exc()
                
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
        **get_environment_context()
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
    
    # Get employee context if exists
    employee = None
    if hasattr(request, 'employee') and request.employee:
        employee = request.employee
    
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
        'employee': employee,
        'title': 'My Profile'
    }
    return render(request, 'auth/profile.html', context)

@login_required
def profile_photo_upload(request):
    """Handle profile photo upload"""
    if request.method == 'POST':
        try:
            profile, created = UserProfile.objects.get_or_create(user=request.user)
            
            if 'photo' in request.FILES:
                # Delete old photo if exists
                if profile.photo:
                    try:
                        profile.photo.delete(save=False)
                    except:
                        pass
                
                # Save new photo
                profile.photo = request.FILES['photo']
                profile.save()
                
                messages.success(request, 'Profile photo updated successfully!')
            else:
                messages.error(request, 'No photo file provided.')
                
        except Exception as e:
            messages.error(request, f'Error uploading photo: {str(e)}')
    
    return redirect('/auth/profile/')

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