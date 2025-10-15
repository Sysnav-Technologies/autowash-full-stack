/**
 * Main JavaScript Application - Clean Version
 * Handles sidebar functionality and core interactions with smooth loading
 */

// Global navigation state
window.AutoWashNavigation = {
    isNavigating: false,
    loadingTimeout: null
};

$(document).ready(function() {
    initializeApp();
});

function initializeApp() {
    // Check if this is a public page and handle accordingly
    if ($('.public-main').length > 0) {
        initializePublicPage();
        return;
    }
    
    initializeSidebar();
    initializeDebugPanel();
    initializeSmoothNavigation();
    initializeMessages(); // Add message handling
}

// ===============================
// SMOOTH NAVIGATION SYSTEM
// ===============================
function initializeSmoothNavigation() {
    // Create loading overlay
    // createLoadingOverlay();
    
    // Intercept navigation clicks
    $(document).on('click', 'a[href]:not([href^="#"]):not([href^="javascript:"]):not([target="_blank"]):not(.no-smooth)', function(e) {
        const href = $(this).attr('href');
        const isDropdownToggle = $(this).hasClass('nav-dropdown-toggle') || $(this).attr('onclick');
        
        // Skip if it's a dropdown toggle or external link
        if (isDropdownToggle || !href || href === '#' || href.startsWith('mailto:') || href.startsWith('tel:')) {
            return true;
        }
        
        // Check if it's the same page
        const currentPath = window.location.pathname;
        const linkPath = new URL(href, window.location.origin).pathname;
        
        if (currentPath === linkPath) {
            return true; // Don't show loader for same page
        }
        
        // Show smooth loading overlay
        window.AutoWashNavigation.isNavigating = true;
        showSmoothLoader();
        
        // Set a maximum loading time
        if (window.AutoWashNavigation.loadingTimeout) {
            clearTimeout(window.AutoWashNavigation.loadingTimeout);
        }
        
        window.AutoWashNavigation.loadingTimeout = setTimeout(() => {
            if (window.AutoWashNavigation.isNavigating) {
                hideSmoothLoader();
                window.AutoWashNavigation.isNavigating = false;
            }
        }, 5000);
        
        // Allow the navigation to proceed normally
        return true;
    });
    
    // Handle form submissions
    $(document).on('submit', 'form:not(.no-smooth)', function(e) {
        window.AutoWashNavigation.isNavigating = true;
        showSmoothLoader();
    });
    
    // Hide loader on page load completion
    $(window).on('load', function() {
        setTimeout(() => {
            hideSmoothLoader();
            window.AutoWashNavigation.isNavigating = false;
        }, 150);
    });
    
    // Also hide on DOM ready for faster perceived loading
    $(document).ready(function() {
        // Small delay to ensure all scripts are loaded
        setTimeout(() => {
            // Only hide if it's not a PWA startup and loader is showing
            if ($('#smooth-loader').hasClass('active') && !document.getElementById('pwa-startup-loader')) {
                hideSmoothLoader();
                window.AutoWashNavigation.isNavigating = false;
            }
        }, 150);
    });
    
    // Handle browser back/forward navigation
    $(window).on('pageshow', function(event) {
        if (event.originalEvent.persisted) {
            // Page was loaded from cache, hide loader immediately
            hideSmoothLoader();
            window.AutoWashNavigation.isNavigating = false;
        }
    });
    
    // Handle visibility change (when user switches tabs)
    $(document).on('visibilitychange', function() {
        if (!document.hidden && $('#smooth-loader').hasClass('active')) {
            // User came back to tab, hide loader if it's still showing
            setTimeout(() => {
                hideSmoothLoader();
                window.AutoWashNavigation.isNavigating = false;
            }, 200);
        }
    });
}

function createLoadingOverlay() {
    if ($('#smooth-loader').length === 0) {
        const loaderHTML = `
            <div id="smooth-loader" class="smooth-loading-overlay">
                <div class="smooth-loader-content">
                    <div class="smooth-spinner-container">
                        <div class="smooth-spinner">
                            <img src="/static/img/logo.png" alt="AutoWash" class="smooth-logo-img">
                        </div>
                    </div>
                    <div class="smooth-loader-text" id="smooth-loader-text">Loading...</div>
                </div>
            </div>
        `;
        $('body').append(loaderHTML);
    }
}

// Array of loading messages for variety
const loadingMessages = [
    'Loading...',
    'Preparing your dashboard...',
    'Getting things ready...',
    'Almost there...',
    'Loading your data...'
];

let currentMessageIndex = 0;
let loadingMessageInterval = null;

function showSmoothLoader() {
    // Don't show if PWA startup loader is already showing
    if (document.getElementById('pwa-startup-loader')) {
        return;
    }
    
    const loader = $('#smooth-loader');
    if (loader.length) {
        // Clear any existing fade-out state
        loader.removeClass('fade-out');
        
        loader.addClass('active');
        $('body').addClass('loading');
        
        // Start cycling through loading messages
        const loaderText = $('#smooth-loader-text');
        currentMessageIndex = 0;
        loaderText.text(loadingMessages[currentMessageIndex]);
        
        // Clear any existing interval
        if (loadingMessageInterval) {
            clearInterval(loadingMessageInterval);
        }
        
        loadingMessageInterval = setInterval(() => {
            currentMessageIndex = (currentMessageIndex + 1) % loadingMessages.length;
            loaderText.fadeOut(200, function() {
                $(this).text(loadingMessages[currentMessageIndex]).fadeIn(200);
            });
        }, 1500); // Slightly slower message changes
        
        // Add a subtle vibration for mobile
        if ('vibrate' in navigator && window.innerWidth <= 768) {
            navigator.vibrate(50);
        }
        
        // Close any open dropdowns
        $('.nav-dropdown').removeClass('open');
        $('.sidebar-dropdown').removeClass('open');
    }
}

function hideSmoothLoader() {
    const loader = $('#smooth-loader');
    if (loader.length && loader.hasClass('active')) {
        // Add fade-out class for smooth animation
        loader.addClass('fade-out');
        
        // Remove active class after animation starts
        setTimeout(() => {
            loader.removeClass('active');
            $('body').removeClass('loading');
            
            // Remove fade-out class after animation completes
            setTimeout(() => {
                loader.removeClass('fade-out');
            }, 300);
        }, 100);
        
        // Clear loading message interval
        if (loadingMessageInterval) {
            clearInterval(loadingMessageInterval);
            loadingMessageInterval = null;
        }
    }
}

// ===============================
// PUBLIC PAGE FUNCTIONALITY
// ===============================
function initializePublicPage() {
    // Handle public navbar toggle
    $('.navbar-toggler').on('click', function() {
        const navbar = $('.navbar-collapse');
        navbar.toggleClass('show');
    });
    
    // Close navbar when clicking outside
    $(document).on('click', function(e) {
        if (!$(e.target).closest('.navbar').length) {
            $('.navbar-collapse').removeClass('show');
        }
    });
}

// ===============================
// SIDEBAR FUNCTIONALITY
// ===============================
function initializeSidebar() {
    const sidebar = $('#sidebar');
    
    if (!sidebar.length) {
        return;
    }
    
    // Clear any existing event handlers
    $('.sidebar-toggle').off('click');
    $(document).off('click.sidebar');
    
    // Sidebar toggle functionality
    $('.sidebar-toggle').on('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        if (window.innerWidth <= 768) {
            // Mobile behavior
            sidebar.toggleClass('mobile-open');
            $('body').toggleClass('sidebar-open');
            
            // Save state
            const isOpen = sidebar.hasClass('mobile-open');
            localStorage.setItem('sidebar-mobile-open', isOpen);
        } else {
            // Desktop behavior
            sidebar.toggleClass('collapsed');
            
            // Save state
            const isCollapsed = sidebar.hasClass('collapsed');
            localStorage.setItem('sidebar-collapsed', isCollapsed);
        }
    });
    
    // Click outside to close (mobile only)
    $(document).on('click.sidebar', function(e) {
        if (window.innerWidth <= 768 && sidebar.hasClass('mobile-open')) {
            const clickedElement = $(e.target);
            const isClickInSidebar = clickedElement.closest('#sidebar').length > 0;
            const isClickOnToggle = clickedElement.closest('.sidebar-toggle').length > 0;
            
            if (!isClickInSidebar && !isClickOnToggle) {
                sidebar.removeClass('mobile-open');
                $('body').removeClass('sidebar-open');
                localStorage.setItem('sidebar-mobile-open', 'false');
            }
        }
    });
    
    // Auto-close mobile sidebar when clicking navigation links
    $(document).on('click', '.sidebar .nav-link[href]', function(e) {
        if (window.innerWidth <= 768 && sidebar.hasClass('mobile-open')) {
            const href = $(this).attr('href');
            const isDropdownToggle = $(this).hasClass('nav-dropdown-toggle') || $(this).attr('onclick');
            
            // Only close for actual navigation links (not dropdown toggles)
            if (href && href !== '#' && !isDropdownToggle) {
                // Close sidebar immediately for smooth navigation
                sidebar.removeClass('mobile-open');
                $('body').removeClass('sidebar-open');
                localStorage.setItem('sidebar-mobile-open', 'false');
                
                // Show loading overlay
                showSmoothLoader();
            }
        }
    });
    
    // Restore sidebar state
    restoreSidebarState();
    
    // Initialize dropdown functionality
    initializeSidebarDropdowns();
}

function restoreSidebarState() {
    const sidebar = $('#sidebar');
    
    try {
        if (window.innerWidth <= 768) {
            // Mobile: Don't restore open state (always start closed)
            sidebar.removeClass('mobile-open');
            $('body').removeClass('sidebar-open');
        } else {
            // Desktop: Restore collapsed state
            const isCollapsed = localStorage.getItem('sidebar-collapsed') === 'true';
            sidebar.toggleClass('collapsed', isCollapsed);
        }
    } catch (e) {
        // Fallback for localStorage errors
        if (window.innerWidth > 768) {
            sidebar.removeClass('collapsed');
        }
    }
}

function initializeSidebarDropdowns() {
    // Dropdown functionality is handled by the HTML onclick attributes
    // This just ensures proper accordion behavior
    $('.nav-dropdown-toggle').on('click', function(e) {
        e.stopPropagation(); // Prevent sidebar close
    });
    
    // Initialize AdminLTE-style treeview functionality
    initializeTreeview();
}

// Initialize treeview functionality for sidebar menus
function initializeTreeview() {
    // Handle clicks on treeview items
    $('.has-treeview > .nav-link').on('click', function(e) {
        e.preventDefault();
        
        const parentLi = $(this).parent('.has-treeview');
        const treeviewMenu = parentLi.find('> .nav-treeview');
        const isOpen = parentLi.hasClass('menu-open');
        
        // Close all other treeview menus
        $('.has-treeview').not(parentLi).removeClass('menu-open');
        $('.nav-treeview').not(treeviewMenu).slideUp(300);
        
        // Toggle current menu
        if (isOpen) {
            parentLi.removeClass('menu-open');
            treeviewMenu.slideUp(300);
        } else {
            parentLi.addClass('menu-open');
            treeviewMenu.slideDown(300);
        }
        
        return false;
    });
    
    // Keep menu open if a child item is active
    $('.nav-treeview .nav-link.active').each(function() {
        $(this).closest('.has-treeview').addClass('menu-open');
        $(this).closest('.nav-treeview').show();
    });
}

// Dropdown toggle function (called from HTML)
function toggleDropdown(dropdownId) {
    // Skip if loading is active
    if ($('body').hasClass('loading')) {
        return false;
    }
    
    const dropdown = $('#' + dropdownId);
    const allDropdowns = $('.nav-dropdown');
    
    // Close other dropdowns
    allDropdowns.not(dropdown).removeClass('open');
    
    // Toggle current dropdown
    dropdown.toggleClass('open');
    
    // Prevent event bubbling
    if (typeof event !== 'undefined') {
        event.stopPropagation();
    }
    return false;
}

// ===============================
// DEBUG PANEL FUNCTIONALITY
// ===============================
function initializeDebugPanel() {
    const debugToggle = $('.debug-toggle');
    const debugPanel = $('.debug-panel');
    
    if (debugToggle.length && debugPanel.length) {
        debugToggle.on('click', function() {
            debugPanel.toggle();
        });
    }
}

// ===============================
// WELCOME MESSAGE
// ===============================
function initializeWelcomeMessage() {
    const welcomeMessage = document.getElementById('welcomeMessage');
    if (welcomeMessage && $('.public-main').length) {
        const username = window.current_user?.username || 
                        new URLSearchParams(window.location.search).get('username') || '';
        welcomeMessage.textContent = username ? 
            `Welcome Back, ${username}` : 'Welcome to Autowash System';
    }
}

// ===============================
// THEME FUNCTIONALITY
// ===============================
function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('preferred-theme', newTheme);
    
    updateThemeToggleButton(newTheme);
}

function initializeTheme() {
    const savedTheme = localStorage.getItem('preferred-theme') || 'light';
    applyTheme(savedTheme);
}

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    updateThemeToggleButton(theme);
}

function updateThemeToggleButton(theme) {
    const button = document.querySelector('.theme-toggle');
    if (button) {
        const icon = button.querySelector('i');
        if (icon) {
            icon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
        }
    }
}

// ===============================
// UTILITY FUNCTIONS
// ===============================

// Format currency
function formatCurrency(amount, currency = 'KES') {
    return new Intl.NumberFormat('en-KE', {
        style: 'currency',
        currency: currency
    }).format(amount);
}

// Format date
function formatDate(date, options = {}) {
    const defaultOptions = {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    };
    
    return new Intl.DateTimeFormat('en-KE', {...defaultOptions, ...options}).format(new Date(date));
}

// Debounce function
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

// Global error handler
window.addEventListener('error', function(e) {
    console.error('Global error:', e.error);
});

// Make functions globally available
window.toggleTheme = toggleTheme;
window.initializeTheme = initializeTheme;
window.toggleDropdown = toggleDropdown;

// ===============================
// MESSAGE HANDLING SYSTEM
// ===============================
function initializeMessages() {
    // Auto-dismiss success messages after 4 seconds
    $('.message-alert.alert-success').each(function() {
        const $alert = $(this);
        setTimeout(() => {
            $alert.fadeOut(300, function() {
                $(this).remove();
            });
        }, 4000);
    });

    // Auto-dismiss info messages after 5 seconds
    $('.message-alert.alert-info').each(function() {
        const $alert = $(this);
        setTimeout(() => {
            $alert.fadeOut(300, function() {
                $(this).remove();
            });
        }, 5000);
    });

    // Auto-dismiss warning messages after 6 seconds
    $('.message-alert.alert-warning').each(function() {
        const $alert = $(this);
        setTimeout(() => {
            $alert.fadeOut(300, function() {
                $(this).remove();
            });
        }, 6000);
    });

    // Error messages stay until manually closed (no auto-dismiss)
    // but add enhanced close functionality
    $('.message-alert .btn-close').on('click', function() {
        const $alert = $(this).closest('.message-alert');
        $alert.fadeOut(300, function() {
            $(this).remove();
        });
    });

    // Add click to dismiss functionality (except for errors)
    $('.message-alert:not(.alert-danger):not(.alert-error)').on('click', function() {
        const $alert = $(this);
        $alert.fadeOut(300, function() {
            $(this).remove();
        });
    });

    // Progressive enhancement: Add hover pause for auto-dismiss
    let autodismissTimeouts = new Map();
    
    $('.message-alert:not(.alert-danger):not(.alert-error)').hover(
        function() {
            // Mouse enter - pause auto dismiss
            const $alert = $(this);
            const timeout = autodismissTimeouts.get(this);
            if (timeout) {
                clearTimeout(timeout);
                $alert.addClass('paused');
            }
        },
        function() {
            // Mouse leave - resume auto dismiss
            const $alert = $(this);
            if ($alert.hasClass('paused')) {
                $alert.removeClass('paused');
                const delay = $alert.hasClass('alert-success') ? 2000 : 
                             $alert.hasClass('alert-info') ? 3000 : 4000;
                
                const newTimeout = setTimeout(() => {
                    $alert.fadeOut(300, function() {
                        $(this).remove();
                    });
                }, delay);
                
                autodismissTimeouts.set(this, newTimeout);
            }
        }
    );
}

// Function to show dynamic messages (for AJAX responses)
function showMessage(message, type = 'info', autoDismiss = true) {
    const iconMap = {
        success: 'fas fa-check-circle',
        error: 'fas fa-exclamation-triangle',
        danger: 'fas fa-exclamation-triangle',
        warning: 'fas fa-exclamation-circle',
        info: 'fas fa-info-circle'
    };

    const messageHtml = `
        <div class="alert alert-${type} alert-dismissible fade show message-alert" role="alert">
            <div class="d-flex align-items-start">
                <div class="message-icon">
                    <i class="${iconMap[type] || 'fas fa-bell'}"></i>
                </div>
                <div class="message-content">
                    ${message}
                </div>
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        </div>
    `;

    // Find or create messages container
    let $container = $('.messages-container');
    if ($container.length === 0) {
        $container = $('<div class="messages-container"></div>');
        $('main .container-fluid, main .container, .main-content').first().prepend($container);
    }

    const $newMessage = $(messageHtml);
    $container.append($newMessage);

    // Apply same auto-dismiss logic
    if (autoDismiss && type !== 'error' && type !== 'danger') {
        const delay = type === 'success' ? 4000 : 
                     type === 'info' ? 5000 : 6000;
        
        setTimeout(() => {
            $newMessage.fadeOut(300, function() {
                $(this).remove();
                if ($container.children().length === 0) {
                    $container.remove();
                }
            });
        }, delay);
    }

    return $newMessage;
}

// Make message functions globally available
window.showMessage = showMessage;
window.initializeMessages = initializeMessages;
