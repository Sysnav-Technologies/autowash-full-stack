/**
 * Authentication JavaScript
 * Handles login and registration functionality
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize authentication functionality
    initializeAuth();
});

function initializeAuth() {
    // Check if we're on login or register page
    const loginForm = document.getElementById('loginForm');
    const registrationForm = document.getElementById('registrationForm');
    
    if (loginForm) {
        initializeLogin();
    }
    
    if (registrationForm) {
        initializeRegistration();
    }
    
    // Common functionality
    initializeCommonFeatures();
}

function initializeLogin() {
    // Personalize welcome message
    personalizeWelcomeMessage();
    
    // Password toggle functionality
    setupPasswordToggle('togglePassword', 'password');
    
    // Form validation and submission
    setupLoginFormSubmission();
    
    // Real-time validation
    setupRealTimeValidation();
}

function initializeRegistration() {
    // Password toggle functionality
    setupPasswordToggle('togglePassword1', 'password1');
    setupPasswordToggle('togglePassword2', 'password2');
    
    // Form validation and submission
    setupRegistrationFormSubmission();
    
    // Real-time validation
    setupRealTimeValidation();
    
    // Password strength indicator
    setupPasswordStrength();
}

function initializeCommonFeatures() {
    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth'
                });
            }
        });
    });
    
    // Add fade-in animation to cards
    const cards = document.querySelectorAll('.auth-card');
    cards.forEach(card => {
        card.classList.add('fade-in');
        setTimeout(() => {
            card.classList.add('visible');
        }, 100);
    });
}

function personalizeWelcomeMessage() {
    const welcomeMessage = document.getElementById('welcomeMessage');
    if (!welcomeMessage) return;
    
    const urlParams = new URLSearchParams(window.location.search);
    const username = urlParams.get('username') || '';
    
    if (username) {
        welcomeMessage.textContent = `Welcome Back, ${username}`;
    }
}

function setupPasswordToggle(toggleId, passwordId) {
    const toggleButton = document.getElementById(toggleId);
    const passwordInput = document.getElementById(passwordId);
    
    if (!toggleButton || !passwordInput) return;
    
    const toggleIcon = toggleButton.querySelector('i');
    
    toggleButton.addEventListener('click', function(e) {
        e.preventDefault();
        
        const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
        passwordInput.setAttribute('type', type);
        
        // Toggle icon
        toggleIcon.classList.toggle('fa-eye', type === 'password');
        toggleIcon.classList.toggle('fa-eye-slash', type !== 'password');
        
        // Add visual feedback
        toggleButton.style.color = type === 'text' ? '#007bff' : '#6c757d';
    });
}

function setupLoginFormSubmission() {
    const loginForm = document.getElementById('loginForm');
    if (!loginForm) return;
    
    loginForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const submitBtn = this.querySelector('button[type="submit"]');
        const originalText = submitBtn.innerHTML;
        
        // Validate form
        if (!validateLoginForm()) {
            return;
        }
        
        // Show loading state
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Signing In...';
        
        // Simulate API call
        setTimeout(() => {
            // Reset button state
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalText;
            
            // Show success message (in real app, redirect to dashboard)
            showNotification('Login successful! Redirecting...', 'success');
            
            // Simulate redirect
            setTimeout(() => {
                window.location.href = 'dashboard.html';
            }, 1500);
        }, 2000);
    });
}

function setupRegistrationFormSubmission() {
    const registrationForm = document.getElementById('registrationForm');
    if (!registrationForm) return;
    
    registrationForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const submitBtn = this.querySelector('button[type="submit"]');
        const originalText = submitBtn.innerHTML;
        
        // Validate form
        if (!validateRegistrationForm()) {
            return;
        }
        
        // Show loading state
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Creating Account...';
        
        // Simulate API call
        setTimeout(() => {
            // Reset button state
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalText;
            
            // Show success message
            showNotification('Account created successfully! Please check your email for verification.', 'success');
            
            // Simulate redirect to login
            setTimeout(() => {
                window.location.href = 'login.html';
            }, 2000);
        }, 3000);
    });
}

function setupRealTimeValidation() {
    const inputs = document.querySelectorAll('.form-control');
    
    inputs.forEach(input => {
        input.addEventListener('blur', function() {
            validateField(this);
        });
        
        input.addEventListener('input', function() {
            if (this.classList.contains('is-invalid')) {
                validateField(this);
            }
        });
    });
}

function validateField(field) {
    const value = field.value.trim();
    let isValid = true;
    let errorMessage = '';
    
    // Required field validation
    if (field.hasAttribute('required') && value === '') {
        isValid = false;
        errorMessage = 'This field is required.';
    }
    
    // Email validation
    if (field.type === 'email' && value !== '') {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(value)) {
            isValid = false;
            errorMessage = 'Please enter a valid email address.';
        }
    }
    
    // Username validation
    if (field.name === 'username' && value !== '') {
        const usernameRegex = /^[a-zA-Z0-9_-]{3,20}$/;
        if (!usernameRegex.test(value)) {
            isValid = false;
            errorMessage = 'Username must be 3-20 characters long and contain only letters, numbers, hyphens, and underscores.';
        }
    }
    
    // Phone validation
    if (field.name === 'phone' && value !== '') {
        const phoneRegex = /^\+?[1-9]\d{1,14}$/;
        if (!phoneRegex.test(value.replace(/\s/g, ''))) {
            isValid = false;
            errorMessage = 'Please enter a valid phone number.';
        }
    }
    
    // Password confirmation validation
    if (field.id === 'password2') {
        const password1 = document.getElementById('password1');
        if (password1 && value !== password1.value) {
            isValid = false;
            errorMessage = 'Passwords do not match.';
        }
    }
    
    // Update field state
    updateFieldState(field, isValid, errorMessage);
    
    return isValid;
}

function updateFieldState(field, isValid, errorMessage) {
    const feedback = field.parentNode.querySelector('.invalid-feedback') || 
                    field.parentNode.parentNode.querySelector('.invalid-feedback');
    
    if (isValid) {
        field.classList.remove('is-invalid');
        field.classList.add('is-valid');
        if (feedback) {
            feedback.textContent = '';
        }
    } else {
        field.classList.remove('is-valid');
        field.classList.add('is-invalid');
        if (feedback) {
            feedback.textContent = errorMessage;
        }
    }
}

function validateLoginForm() {
    const username = document.getElementById('username');
    const password = document.getElementById('password');
    
    let isValid = true;
    
    if (!validateField(username)) isValid = false;
    if (!validateField(password)) isValid = false;
    
    return isValid;
}

function validateRegistrationForm() {
    const requiredFields = ['first_name', 'last_name', 'username', 'email', 'password1', 'password2'];
    const termsCheckbox = document.getElementById('terms');
    
    let isValid = true;
    
    // Validate required fields
    requiredFields.forEach(fieldName => {
        const field = document.getElementById(fieldName);
        if (field && !validateField(field)) {
            isValid = false;
        }
    });
    
    // Validate optional phone field if filled
    const phoneField = document.getElementById('phone');
    if (phoneField && phoneField.value.trim() !== '') {
        if (!validateField(phoneField)) {
            isValid = false;
        }
    }
    
    // Check terms acceptance
    if (!termsCheckbox.checked) {
        isValid = false;
        showNotification('Please accept the Terms of Service and Privacy Policy.', 'error');
    }
    
    return isValid;
}

function setupPasswordStrength() {
    const password1 = document.getElementById('password1');
    if (!password1) return;
    
    password1.addEventListener('input', function() {
        checkPasswordStrength(this.value);
    });
}

function checkPasswordStrength(password) {
    const strengthMeter = document.getElementById('passwordStrength');
    if (!strengthMeter) return;
    
    let strength = 0;
    let feedback = [];
    
    // Length check
    if (password.length >= 8) {
        strength++;
    } else if (password.length > 0) {
        feedback.push('at least 8 characters');
    }
    
    // Lowercase check
    if (/[a-z]/.test(password)) {
        strength++;
    } else if (password.length > 0) {
        feedback.push('lowercase letters');
    }
    
    // Uppercase check
    if (/[A-Z]/.test(password)) {
        strength++;
    } else if (password.length > 0) {
        feedback.push('uppercase letters');
    }
    
    // Number check
    if (/[0-9]/.test(password)) {
        strength++;
    } else if (password.length > 0) {
        feedback.push('numbers');
    }
    
    // Special character check
    if (/[^A-Za-z0-9]/.test(password)) {
        strength++;
    } else if (password.length > 0) {
        feedback.push('special characters');
    }
    
    // Update strength display
    const strengthLabels = ['Very Weak', 'Weak', 'Fair', 'Good', 'Strong'];
    const strengthColors = ['danger', 'warning', 'warning', 'info', 'success'];
    
    if (password.length === 0) {
        strengthMeter.textContent = '';
        strengthMeter.className = 'form-text small mt-1';
    } else {
        const label = strengthLabels[Math.min(strength, 4)];
        const color = strengthColors[Math.min(strength, 4)];
        
        strengthMeter.textContent = `Password strength: ${label}`;
        strengthMeter.className = `form-text small mt-1 text-${color}`;
        
        if (feedback.length > 0) {
            strengthMeter.textContent += ` (needs: ${feedback.join(', ')})`;
        }
    }
}

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    notification.style.cssText = `
        top: 20px;
        right: 20px;
        z-index: 9999;
        max-width: 400px;
        box-shadow: 0 0.5rem 1rem rgba(0, 0, 0, 0.15);
    `;
    
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    // Add to DOM
    document.body.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.classList.remove('show');
            setTimeout(() => {
                notification.remove();
            }, 150);
        }
    }, 5000);
}

// Social login handlers
document.addEventListener('DOMContentLoaded', function() {
    // Google login button
    const googleBtns = document.querySelectorAll('.btn-outline-secondary');
    googleBtns.forEach(btn => {
        if (btn.textContent.includes('Google')) {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                handleSocialLogin('google');
            });
        }
    });
});

function handleSocialLogin(provider) {
    showNotification(`${provider.charAt(0).toUpperCase() + provider.slice(1)} login is not implemented yet.`, 'info');
    
    // In a real application, you would redirect to the OAuth provider
    // window.location.href = `/auth/${provider}/`;
}

// Form enhancement utilities
function addFormEnhancements() {
    // Add loading states to all buttons
    const buttons = document.querySelectorAll('.btn');
    buttons.forEach(btn => {
        btn.addEventListener('click', function() {
            if (this.type === 'submit') {
                // This will be handled by form submission handlers
                return;
            }
            
            // Add subtle hover effect
            this.style.transform = 'translateY(-1px)';
            setTimeout(() => {
                this.style.transform = '';
            }, 200);
        });
    });
    
    // Add focus enhancement to form controls
    const formControls = document.querySelectorAll('.form-control');
    formControls.forEach(control => {
        control.addEventListener('focus', function() {
            this.parentNode.classList.add('focused');
        });
        
        control.addEventListener('blur', function() {
            this.parentNode.classList.remove('focused');
        });
    });
}

// Initialize enhancements when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    addFormEnhancements();
    
    // Add smooth transitions
    document.body.style.transition = 'all 0.3s ease';
    
    // Handle form auto-fill styling
    const inputs = document.querySelectorAll('input');
    inputs.forEach(input => {
        input.addEventListener('animationstart', function(e) {
            if (e.animationName === 'onAutoFillStart') {
                this.classList.add('auto-filled');
            }
        });
        
        input.addEventListener('animationend', function(e) {
            if (e.animationName === 'onAutoFillCancel') {
                this.classList.remove('auto-filled');
            }
        });
    });
});

// Keyboard navigation enhancement
document.addEventListener('keydown', function(e) {
    // Enter key on form inputs
    if (e.key === 'Enter') {
        const activeElement = document.activeElement;
        if (activeElement.tagName === 'INPUT' && activeElement.type !== 'submit') {
            const form = activeElement.closest('form');
            if (form) {
                const submitBtn = form.querySelector('button[type="submit"]');
                if (submitBtn && !submitBtn.disabled) {
                    submitBtn.click();
                }
            }
        }
    }
    
    // Escape key to clear focus
    if (e.key === 'Escape') {
        document.activeElement.blur();
    }
});

// Accessibility improvements
function enhanceAccessibility() {
    // Add ARIA labels to password toggle buttons
    const toggleButtons = document.querySelectorAll('.toggle-password');
    toggleButtons.forEach(btn => {
        btn.setAttribute('aria-label', 'Toggle password visibility');
        btn.setAttribute('title', 'Show/hide password');
    });
    
    // Add live region for form validation messages
    const liveRegion = document.createElement('div');
    liveRegion.id = 'live-region';
    liveRegion.setAttribute('aria-live', 'polite');
    liveRegion.setAttribute('aria-atomic', 'true');
    liveRegion.style.cssText = 'position: absolute; left: -10000px; width: 1px; height: 1px; overflow: hidden;';
    document.body.appendChild(liveRegion);
}

// Initialize accessibility enhancements
document.addEventListener('DOMContentLoaded', enhanceAccessibility);