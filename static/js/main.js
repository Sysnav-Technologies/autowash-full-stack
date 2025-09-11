/**
 * Main JavaScript Application - Clean Version
 * Handles sidebar functionality and core interactions
 */

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
                sidebar.removeClass('mobile-open');
                $('body').removeClass('sidebar-open');
                localStorage.setItem('sidebar-mobile-open', 'false');
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
}

// Dropdown toggle function (called from HTML)
function toggleDropdown(dropdownId) {
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
