$(document).ready(function() {
    // Initialize AOS
    if (typeof AOS !== 'undefined') {
        AOS.init({
            duration: 800,
            easing: 'ease-in-out',
            once: true,
            offset: 100
        });
    }
    
    // Auto-hide alerts
    setTimeout(function() {
        $('.alert').each(function() {
            $(this).fadeOut('slow');
        });
    }, 5000);
    
    // AJAX setup for Django CSRF
    $.ajaxSetup({
        beforeSend: function(xhr, settings) {
            if (!this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", $('[name=csrfmiddlewaretoken]').val());
            }
        }
    });
    
    // Loading states for forms
    $(document).on('submit', 'form', function() {
        const submitBtn = $(this).find('button[type="submit"]');
        const originalText = submitBtn.html();
        
        submitBtn.prop('disabled', true);
        submitBtn.html('<span class="spinner-border spinner-border-sm me-2"></span>Processing...');
        
        // Re-enable after 10 seconds as fallback
        setTimeout(() => {
            submitBtn.prop('disabled', false);
            submitBtn.html(originalText);
        }, 10000);
    });
    
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
    
    // Add animation classes on scroll
    const animateOnScroll = () => {
        const elements = document.querySelectorAll('.animate-on-scroll');
        elements.forEach(element => {
            const elementTop = element.getBoundingClientRect().top;
            const elementVisible = 150;
            
            if (elementTop < window.innerHeight - elementVisible) {
                element.classList.add('fade-in');
            }
        });
    };
    
    window.addEventListener('scroll', animateOnScroll);
    
    // Real-time form validation feedback
    const addInputValidation = () => {
        const inputs = document.querySelectorAll('.form-control, .form-select');
        inputs.forEach(input => {
            input.addEventListener('blur', function() {
                if (this.checkValidity()) {
                    this.classList.remove('is-invalid');
                    this.classList.add('is-valid');
                } else {
                    this.classList.remove('is-valid');
                    this.classList.add('is-invalid');
                }
            });
            
            input.addEventListener('input', function() {
                if (this.classList.contains('is-invalid') && this.checkValidity()) {
                    this.classList.remove('is-invalid');
                    this.classList.add('is-valid');
                }
            });
        });
    };
    
    // Initialize validation
    addInputValidation();
    animateOnScroll();
    
    // Show/hide password functionality
    $(document).on('click', '.toggle-password', function() {
        const target = $($(this).data('target'));
        const icon = $(this).find('i');
        
        if (target.attr('type') === 'password') {
            target.attr('type', 'text');
            icon.removeClass('fa-eye').addClass('fa-eye-slash');
        } else {
            target.attr('type', 'password');
            icon.removeClass('fa-eye-slash').addClass('fa-eye');
        }
    });
    
    // Confirm deletion modals
    $(document).on('click', '[data-confirm-delete]', function(e) {
        e.preventDefault();
        const message = $(this).data('confirm-delete') || 'Are you sure you want to delete this item?';
        const url = $(this).attr('href') || $(this).data('url');
        
        if (confirm(message)) {
            if ($(this).data('method') === 'POST') {
                // Create and submit a form for POST requests
                $('<form>', {
                    method: 'POST',
                    action: url
                }).append($('<input>', {
                    type: 'hidden',
                    name: 'csrfmiddlewaretoken',
                    value: $('[name=csrfmiddlewaretoken]').val()
                })).appendTo('body').submit();
            } else {
                window.location.href = url;
            }
        }
    });
    
    // Auto-resize textareas
    $(document).on('input', 'textarea[data-auto-resize]', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
    });
    
    // Copy to clipboard functionality
    $(document).on('click', '[data-clipboard]', function() {
        const text = $(this).data('clipboard');
        navigator.clipboard.writeText(text).then(() => {
            const originalText = $(this).text();
            $(this).text('Copied!').addClass('btn-success');
            
            setTimeout(() => {
                $(this).text(originalText).removeClass('btn-success');
            }, 2000);
        });
    });
    
    // Number formatting
    $('.format-currency').each(function() {
        const value = parseFloat($(this).text());
        if (!isNaN(value)) {
            $(this).text(new Intl.NumberFormat('en-KE', {
                style: 'currency',
                currency: 'KES'
            }).format(value));
        }
    });
    
    $('.format-number').each(function() {
        const value = parseFloat($(this).text());
        if (!isNaN(value)) {
            $(this).text(new Intl.NumberFormat('en-KE').format(value));
        }
    });
    
    // Search functionality with debounce
    let searchTimeout;
    $(document).on('input', '[data-search]', function() {
        const searchTerm = $(this).val().toLowerCase();
        const target = $(this).data('search');
        
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            $(target).each(function() {
                const text = $(this).text().toLowerCase();
                $(this).toggle(text.includes(searchTerm));
            });
        }, 300);
    });
    
    // File upload preview
    $(document).on('change', 'input[type="file"][data-preview]', function() {
        const file = this.files[0];
        const previewTarget = $(this).data('preview');
        
        if (file && file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = function(e) {
                $(previewTarget).attr('src', e.target.result).show();
            };
            reader.readAsDataURL(file);
        }
    });
});