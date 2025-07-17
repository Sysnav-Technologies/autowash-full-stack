// Public JavaScript - Public page functionality

$(document).ready(function() {
    // Navbar scroll effect
    $(window).scroll(function() {
        if ($(this).scrollTop() > 50) {
            $('.public-navbar').addClass('scrolled');
        } else {
            $('.public-navbar').removeClass('scrolled');
        }
    });
    
    // Hero section animations
    initializeHeroAnimations();
    
    // Feature cards hover effects
    initializeFeatureCards();
    
    // Pricing cards interactions
    initializePricingCards();
    
    // Contact form handling
    initializeContactForm();
    
    // Newsletter subscription
    initializeNewsletterForm();
    
    // Parallax effects
    initializeParallaxEffects();
    
    // Counter animations
    initializeCounterAnimations();
});

// Initialize hero section animations
function initializeHeroAnimations() {
    // Typing effect for hero title
    const heroTitle = $('.hero-title');
    if (heroTitle.length && heroTitle.data('typing')) {
        const text = heroTitle.text();
        heroTitle.text('');
        
        let i = 0;
        const typeWriter = () => {
            if (i < text.length) {
                heroTitle.text(heroTitle.text() + text.charAt(i));
                i++;
                setTimeout(typeWriter, 50);
            }
        };
        
        setTimeout(typeWriter, 1000);
    }
    
    // Floating animation for hero elements
    $('.hero-float').each(function(index) {
        $(this).css({
            'animation-delay': (index * 0.2) + 's',
            'animation-duration': (3 + Math.random() * 2) + 's'
        });
    });
}

// Initialize feature cards
function initializeFeatureCards() {
    $('.feature-card').hover(
        function() {
            $(this).find('.feature-icon').addClass('animate__animated animate__pulse');
        },
        function() {
            $(this).find('.feature-icon').removeClass('animate__animated animate__pulse');
        }
    );
    
    // Intersection Observer for feature cards
    if ('IntersectionObserver' in window) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry, index) => {
                if (entry.isIntersecting) {
                    setTimeout(() => {
                        entry.target.classList.add('fade-in');
                    }, index * 200);
                }
            });
        }, { threshold: 0.1 });
        
        $('.feature-card').each(function() {
            observer.observe(this);
        });
    }
}

// Initialize pricing cards
function initializePricingCards() {
    $('.pricing-card').hover(
        function() {
            if (!$(this).hasClass('featured')) {
                $(this).addClass('shadow-lg').css('transform', 'translateY(-5px)');
            }
        },
        function() {
            if (!$(this).hasClass('featured')) {
                $(this).removeClass('shadow-lg').css('transform', 'translateY(0)');
            }
        }
    );
    
    // Pricing toggle (monthly/yearly)
    $('.pricing-toggle input').on('change', function() {
        const isYearly = $(this).is(':checked');
        
        $('.pricing-price').each(function() {
            const monthlyPrice = $(this).data('monthly');
            const yearlyPrice = $(this).data('yearly');
            
            if (monthlyPrice && yearlyPrice) {
                const price = isYearly ? yearlyPrice : monthlyPrice;
                const period = isYearly ? '/year' : '/month';
                
                $(this).find('.amount').text(price);
                $(this).find('.period').text(period);
            }
        });
        
        // Show/hide discount badges
        $('.discount-badge').toggle(isYearly);
    });
}

// Initialize contact form
function initializeContactForm() {
    $('#contact-form').on('submit', function(e) {
        e.preventDefault();
        
        const form = $(this);
        const submitBtn = form.find('button[type="submit"]');
        const originalText = submitBtn.text();
        
        // Show loading state
        submitBtn.prop('disabled', true)
                 .html('<span class="spinner-border spinner-border-sm me-2"></span>Sending...');
        
        // Simulate form submission (replace with actual AJAX call)
        $.ajax({
            url: form.attr('action') || '/contact/',
            method: 'POST',
            data: form.serialize(),
            success: function(response) {
                showNotification('success', 'Message sent successfully! We\'ll get back to you soon.');
                form[0].reset();
            },
            error: function() {
                showNotification('error', 'Error sending message. Please try again.');
            },
            complete: function() {
                submitBtn.prop('disabled', false).text(originalText);
            }
        });
    });
}

// Initialize newsletter form
function initializeNewsletterForm() {
    $('.newsletter-form').on('submit', function(e) {
        e.preventDefault();
        
        const email = $(this).find('input[type="email"]').val();
        const form = $(this);
        
        $.ajax({
            url: '/newsletter/subscribe/',
            method: 'POST',
            data: { email: email },
            success: function(response) {
                showNotification('success', 'Successfully subscribed to newsletter!');
                form[0].reset();
            },
            error: function() {
                showNotification('error', 'Error subscribing. Please try again.');
            }
        });
    });
}

// Initialize parallax effects
function initializeParallaxEffects() {
    if (window.innerWidth > 768) {
        $(window).scroll(function() {
            const scrollTop = $(this).scrollTop();
            
            // Parallax for hero background
            $('.hero-section').css('transform', `translateY(${scrollTop * 0.5}px)`);
            
            // Parallax for floating elements
            $('.parallax-element').each(function() {
                const speed = $(this).data('speed') || 0.3;
                const yPos = -(scrollTop * speed);
                $(this).css('transform', `translateY(${yPos}px)`);
            });
        });
    }
}

// Initialize counter animations
function initializeCounterAnimations() {
    const counters = $('.counter');
    
    if ('IntersectionObserver' in window) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    animateCounter(entry.target);
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.5 });
        
        counters.each(function() {
            observer.observe(this);
        });
    } else {
        // Fallback for browsers without IntersectionObserver
        $(window).scroll(function() {
            counters.each(function() {
                if ($(this).offset().top < $(window).scrollTop() + $(window).height()) {
                    animateCounter(this);
                }
            });
        });
    }
}

// Animate counter
function animateCounter(element) {
    const $element = $(element);
    const target = parseInt($element.data('target'));
    const duration = $element.data('duration') || 2000;
    const increment = target / (duration / 16); // 60fps
    
    let current = 0;
    const timer = setInterval(() => {
        current += increment;
        if (current >= target) {
            current = target;
            clearInterval(timer);
        }
        $element.text(Math.floor(current).toLocaleString());
    }, 16);
}

// Show notification
function showNotification(type, message) {
    const notification = $(`
        <div class="alert alert-${type} alert-dismissible fade show position-fixed" 
             style="top: 20px; right: 20px; z-index: 9999; min-width: 300px;">
            <div class="d-flex align-items-center">
                <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-triangle'} me-2"></i>
                <div class="flex-grow-1">${message}</div>
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        </div>
    `);
    
    $('body').append(notification);
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        notification.fadeOut('slow', function() {
            $(this).remove();
        });
    }, 5000);
}

// FAQ accordion
$('.faq-item .question').on('click', function() {
    const item = $(this).closest('.faq-item');
    const answer = item.find('.answer');
    const icon = $(this).find('i');
    
    // Close other items
    $('.faq-item').not(item).removeClass('active').find('.answer').slideUp();
    $('.faq-item').not(item).find('.question i').removeClass('fa-minus').addClass('fa-plus');
    
    // Toggle current item
    item.toggleClass('active');
    answer.slideToggle();
    icon.toggleClass('fa-plus fa-minus');
});

// Testimonials carousel (if using)
if ($('.testimonials-carousel').length) {
    $('.testimonials-carousel').slick({
        dots: true,
        infinite: true,
        speed: 300,
        slidesToShow: 1,
        adaptiveHeight: true,
        autoplay: true,
        autoplaySpeed: 5000,
        arrows: false
    });
}

// Back to top button
$(window).scroll(function() {
    if ($(this).scrollTop() > 300) {
        $('#back-to-top').fadeIn();
    } else {
        $('#back-to-top').fadeOut();
    }
});

$('#back-to-top').on('click', function() {
    $('html, body').animate({ scrollTop: 0 }, 600);
    return false;
});

// Cookie consent
if (!localStorage.getItem('cookieConsent')) {
    setTimeout(() => {
        showCookieConsent();
    }, 2000);
}

function showCookieConsent() {
    const consent = $(`
        <div id="cookie-consent" class="position-fixed bottom-0 start-0 end-0 bg-dark text-white p-3" style="z-index: 9999;">
            <div class="container">
                <div class="row align-items-center">
                    <div class="col-md-8">
                        <p class="mb-0">We use cookies to enhance your experience. By continuing to visit this site you agree to our use of cookies.</p>
                    </div>
                    <div class="col-md-4 text-md-end">
                        <button class="btn btn-primary btn-sm me-2" onclick="acceptCookies()">Accept</button>
                        <button class="btn btn-outline-light btn-sm" onclick="declineCookies()">Decline</button>
                    </div>
                </div>
            </div>
        </div>
    `);
    
    $('body').append(consent);
}

function acceptCookies() {
    localStorage.setItem('cookieConsent', 'accepted');
    $('#cookie-consent').fadeOut();
}

function declineCookies() {
    localStorage.setItem('cookieConsent', 'declined');
    $('#cookie-consent').fadeOut();
}

// Export functions for global use
window.publicUtils = {
    showNotification: showNotification,
    animateCounter: animateCounter
};