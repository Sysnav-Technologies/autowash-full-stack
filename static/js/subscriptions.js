/**
 * Subscription Selection JavaScript
 * Handles plan selection, billing toggles, and interactive elements
 */

document.addEventListener('DOMContentLoaded', function() {
    initializeBillingToggle();
    initializePlanCardEffects();
    initializeMobileOptimizations();
});

/**
 * Initialize billing toggle functionality
 */
function initializeBillingToggle() {
    const monthlyTab = document.getElementById('monthly-tab');
    const annualTab = document.getElementById('annual-tab');
    
    if (!monthlyTab || !annualTab) return;
    
    // Simple billing toggle (for future enhancement)
    monthlyTab.addEventListener('click', function() {
        setActiveTab(monthlyTab, annualTab);
        // Future: Update pricing display
    });
    
    annualTab.addEventListener('click', function() {
        setActiveTab(annualTab, monthlyTab);
        // Future: Update pricing display
    });
}

/**
 * Set active tab and remove active class from other tab
 */
function setActiveTab(activeTab, inactiveTab) {
    activeTab.classList.add('active');
    inactiveTab.classList.remove('active');
}

/**
 * Initialize plan card hover effects
 */
function initializePlanCardEffects() {
    const planCards = document.querySelectorAll('.plan-card');
    
    planCards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            if (window.innerWidth > 768) { // Only on desktop
                this.style.transform = 'translateY(-4px) scale(1.02)';
            }
        });
        
        card.addEventListener('mouseleave', function() {
            if (window.innerWidth > 768) { // Only on desktop
                if (!this.classList.contains('featured')) {
                    this.style.transform = 'translateY(0) scale(1)';
                } else {
                    this.style.transform = 'translateY(0) scale(1.02)';
                }
            }
        });
    });
}

/**
 * Initialize mobile-specific optimizations
 */
function initializeMobileOptimizations() {
    // Add click handler for mobile plan selection
    const selectButtons = document.querySelectorAll('.select-button');
    
    selectButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            // Add loading state for better UX
            const originalText = this.textContent;
            this.textContent = 'Loading...';
            this.style.pointerEvents = 'none';
            
            // Reset after a delay if navigation doesn't happen
            setTimeout(() => {
                this.textContent = originalText;
                this.style.pointerEvents = 'auto';
            }, 3000);
        });
    });
    
    // Handle responsive step indicator
    handleResponsiveSteps();
}

/**
 * Handle responsive step indicator behavior
 */
function handleResponsiveSteps() {
    const stepIndicator = document.querySelector('.step-indicator');
    if (!stepIndicator) return;
    
    function updateStepLayout() {
        const isMobile = window.innerWidth <= 480;
        
        if (isMobile) {
            stepIndicator.style.flexDirection = 'column';
            const dividers = stepIndicator.querySelectorAll('.step-divider');
            dividers.forEach(divider => {
                divider.style.display = 'none';
            });
        } else {
            stepIndicator.style.flexDirection = 'row';
            const dividers = stepIndicator.querySelectorAll('.step-divider');
            dividers.forEach(divider => {
                divider.style.display = 'block';
            });
        }
    }
    
    // Initial setup
    updateStepLayout();
    
    // Update on resize
    window.addEventListener('resize', debounce(updateStepLayout, 250));
}

/**
 * Debounce function to limit function calls during window resize
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Analytics tracking for plan selection (optional)
 */
function trackPlanSelection(planName, planPrice) {
    // Add analytics tracking here if needed
    console.log(`Plan selected: ${planName} - ${planPrice}`);
}

/**
 * Form validation for subscription terms (if applicable)
 */
function validateSubscriptionForm(formElement) {
    const termsCheckbox = formElement.querySelector('[name="agree_terms"]');
    
    if (termsCheckbox && !termsCheckbox.checked) {
        alert('Please accept the Terms of Service and Privacy Policy to continue.');
        return false;
    }
    
    return true;
}

// Export functions for potential external use
window.SubscriptionSelection = {
    trackPlanSelection,
    validateSubscriptionForm
};
