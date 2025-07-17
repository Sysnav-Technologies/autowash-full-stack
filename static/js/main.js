$(document).ready(function() {
    // Initialize all components
    initializeApp();
});

function initializeApp() {
    // Initialize AOS if available
    if (typeof AOS !== 'undefined') {
        AOS.init({
            duration: 800,
            easing: 'ease-in-out',
            once: true,
            offset: 100
        });
    }
    
    // Initialize core components
    initializeLoadingOverlay();
    initializeWelcomeMessage();
    initializePublicNavbar();
    initializeSidebar();
    initializeMessages();
    initializeSearch();
    initializeNotifications();
    initializeTooltips();
    initializeForms();
    initializeTheme();
    initializeKeyboardShortcuts();
    initializeDebugPanel();
    
    // Set up CSRF for AJAX requests
    setupCSRF();
}

// ===============================
// WELCOME MESSAGE
// ===============================
function initializeWelcomeMessage() {
    const welcomeMessage = document.getElementById('welcomeMessage');
    if (welcomeMessage && $('.public-main').length) {
        const username = window.current_user?.username || new URLSearchParams(window.location.search).get('username') || '';
        welcomeMessage.textContent = username ? `Welcome Back, ${username}` : 'Welcome to Autowash System';
    }
}

// ===============================
// LOADING OVERLAY
// ===============================
function initializeLoadingOverlay() {
    const overlay = $('#loading-overlay');
    if (overlay.length) {
        // Fade out loading overlay after 2 seconds or on page load completion
        setTimeout(() => {
            overlay.addClass('hide');
            setTimeout(() => overlay.remove(), 500); // Remove after fade-out animation
        }, 2000);
    }
    
    // Ensure loading overlay can be shown/hidden via global functions
    window.showLoadingOverlay = showLoadingOverlay;
    window.hideLoadingOverlay = hideLoadingOverlay;
}

// ===============================
// PUBLIC NAVBAR FUNCTIONALITY
// ===============================
function initializePublicNavbar() {
    // Only initialize if public navbar exists
    if (!$('.public-navbar').length) return;
    
    const navbarToggler = $('.navbar-toggler');
    const navbarCollapse = $('.navbar-collapse');
    
    // Remove existing event handlers to prevent duplicates
    navbarToggler.off('click.navbar');
    
    // Toggle navbar on mobile
    navbarToggler.on('click.navbar', function(e) {
        e.preventDefault();
        console.log('Public navbar toggler clicked'); // Debug
        navbarCollapse.toggleClass('show');
        $(this).find('.navbar-toggler-icon').toggleClass('active');
    });
    
    // Close navbar when clicking outside on mobile
    $(document).on('click.navbarOutside', function(e) {
        if (window.innerWidth <= 991 && navbarCollapse.hasClass('show')) {
            if (!navbarCollapse.is(e.target) && 
                navbarCollapse.has(e.target).length === 0 &&
                !navbarToggler.is(e.target) && 
                navbarToggler.has(e.target).length === 0) {
                console.log('Closing public navbar on outside click'); // Debug
                navbarCollapse.removeClass('show');
                navbarToggler.find('.navbar-toggler-icon').removeClass('active');
            }
        }
    });
    
    // Handle window resize for navbar
    $(window).on('resize.navbar', function() {
        if (window.innerWidth > 991) {
            navbarCollapse.removeClass('show');
            navbarToggler.find('.navbar-toggler-icon').removeClass('active');
        }
    });
}

// ===============================
// SIDEBAR FUNCTIONALITY
// ===============================
function initializeSidebar() {
    // Skip sidebar initialization for public pages
    if ($('.public-main').length) return;
    
    const sidebar = $('#sidebar');
    const mainContent = $('#main-content');
    
    // Create overlay if it doesn't exist
    let overlay = $('.mobile-sidebar-overlay');
    if (overlay.length === 0) {
        overlay = $('<div class="mobile-sidebar-overlay" id="mobileSidebarOverlay"></div>');
        $('body').append(overlay);
    }
    
    // Remove any existing event handlers to prevent duplicates
    $('.sidebar-toggle').off('click.sidebar');
    
    // Toggle sidebar - use delegation to catch all sidebar toggles
    $(document).on('click.sidebar', '.sidebar-toggle', function(e) {
        e.preventDefault();
        e.stopPropagation();
        console.log('Sidebar toggle clicked, window width:', window.innerWidth); // Debug
        toggleSidebar();
    });
    
    // Close mobile sidebar when clicking overlay
    overlay.off('click.overlay').on('click.overlay', function(e) {
        e.preventDefault();
        console.log('Overlay clicked'); // Debug
        closeMobileSidebar();
    });
    
    // Handle window resize
    $(window).on('resize.sidebar', function() {
        handleSidebarResize();
    });
    
    // Auto-open active dropdown on page load
    $('.nav-link.active').closest('.nav-dropdown').addClass('open');
    
    // Restore sidebar state from localStorage if available
    try {
        const isCollapsed = localStorage.getItem('sidebar-collapsed') === 'true';
        if (isCollapsed && window.innerWidth > 768) {
            sidebar.addClass('collapsed');
            mainContent.addClass('expanded');
        }
    } catch (e) {
        console.warn('localStorage not available for sidebar state:', e); // Debug
    }
    
    // Initialize dropdown functionality
    initializeSidebarDropdowns();
    
    // Close sidebar when clicking outside on mobile
    $(document).on('click.outside', function(e) {
        if (window.innerWidth <= 768) {
            const sidebar = $('#sidebar');
            const sidebarToggle = $('.sidebar-toggle');
            const overlay = $('.mobile-sidebar-overlay');
            
            if (sidebar.hasClass('mobile-open') && 
                !sidebar.is(e.target) && 
                sidebar.has(e.target).length === 0 &&
                !sidebarToggle.is(e.target) && 
                sidebarToggle.has(e.target).length === 0 &&
                !overlay.is(e.target)) {
                console.log('Closing sidebar on outside click'); // Debug
                closeMobileSidebar();
            }
        }
    });
}

function initializeSidebarDropdowns() {
    // Auto-expand active dropdown
    const activeNavItem = document.querySelector('.nav-link.active');
    if (activeNavItem) {
        const parentDropdown = activeNavItem.closest('.nav-dropdown');
        if (parentDropdown) {
            parentDropdown.classList.add('open');
        }
    }
}

function toggleSidebar() {
    const sidebar = $('#sidebar');
    const mainContent = $('#main-content');
    
    console.log('toggleSidebar called, window width:', window.innerWidth); // Debug
    
    if (window.innerWidth <= 768) {
        // Mobile behavior
        console.log('Mobile mode detected'); // Debug
        if (sidebar.hasClass('mobile-open')) {
            console.log('Closing mobile sidebar'); // Debug
            closeMobileSidebar();
        } else {
            console.log('Opening mobile sidebar'); // Debug
            openMobileSidebar();
        }
    } else {
        // Desktop behavior
        console.log('Desktop mode detected'); // Debug
        sidebar.toggleClass('collapsed');
        mainContent.toggleClass('expanded');
        
        // Store preference in localStorage
        try {
            localStorage.setItem('sidebar-collapsed', sidebar.hasClass('collapsed'));
        } catch (e) {
            console.warn('localStorage not available for sidebar state:', e); // Debug
        }
    }
}

function openMobileSidebar() {
    const sidebar = $('#sidebar');
    const overlay = $('#mobileSidebarOverlay, .mobile-sidebar-overlay');
    const body = $('body');
    
    console.log('openMobileSidebar: Adding classes'); // Debug
    
    // Add classes
    sidebar.addClass('mobile-open');
    overlay.addClass('active');
    body.addClass('sidebar-open');
    
    // Force reflow
    sidebar[0].offsetHeight;
    
    console.log('openMobileSidebar: Classes added', {
        sidebarHasMobileOpen: sidebar.hasClass('mobile-open'),
        overlayHasActive: overlay.hasClass('active'),
        bodyHasSidebarOpen: body.hasClass('sidebar-open')
    }); // Debug
}

function closeMobileSidebar() {
    const sidebar = $('#sidebar');
    const overlay = $('#mobileSidebarOverlay, .mobile-sidebar-overlay');
    const body = $('body');
    
    console.log('closeMobileSidebar: Removing classes'); // Debug
    
    sidebar.removeClass('mobile-open');
    overlay.removeClass('active');
    body.removeClass('sidebar-open');
    
    console.log('closeMobileSidebar: Classes removed'); // Debug
}

function handleSidebarResize() {
    const sidebar = $('#sidebar');
    const mainContent = $('#main-content');
    
    if (window.innerWidth > 768) {
        // Desktop: remove mobile classes
        sidebar.removeClass('mobile-open');
        $('.mobile-sidebar-overlay').removeClass('active');
        $('body').removeClass('sidebar-open');
    } else {
        // Mobile: remove desktop classes
        sidebar.removeClass('collapsed');
        mainContent.removeClass('expanded');
    }
}

// Dropdown toggle function
function toggleDropdown(dropdownId) {
    const dropdown = $('#' + dropdownId);
    const allDropdowns = $('.nav-dropdown');
    
    // Close other dropdowns
    allDropdowns.not(dropdown).removeClass('open');
    
    // Toggle current dropdown
    dropdown.toggleClass('open');
}

// ===============================
// DEBUG PANEL FUNCTIONALITY
// ===============================
function initializeDebugPanel() {
    const debugToggle = $('.debug-toggle');
    const debugPanel = $('.debug-panel');
    
    if (debugToggle.length && debugPanel.length) {
        debugToggle.on('click.debug', function() {
            debugPanel.toggle();
            console.log('Debug panel toggled:', debugPanel.is(':visible')); // Debug
        });
        
        // Log initial page state
        console.log('Page initialized:', {
            isPublicPage: $('.public-main').length > 0,
            hasSidebar: $('#sidebar').length > 0,
            hasPublicNavbar: $('.public-navbar').length > 0,
            windowWidth: window.innerWidth
        });
    }
}

// ===============================
// MESSAGES AND NOTIFICATIONS
// ===============================
function initializeMessages() {
    // Auto-hide messages after 5 seconds
    setTimeout(function() {
        $('.message-alert, .alert').each(function() {
            $(this).addClass('fade-out');
            setTimeout(() => {
                $(this).remove();
            }, 500);
        });
    }, 5000);
}

function initializeNotifications() {
    // Real-time notifications - check every 30 seconds
    setInterval(checkForNewNotifications, 30000);
}

function checkForNewNotifications() {
    if (!window.location.pathname.includes('/business/')) return;
    
    $.ajax({
        url: '/api/notifications/check/',
        method: 'GET',
        success: function(data) {
            if (data.new_count > 0) {
                updateNotificationBadge(data.new_count);
                if (data.latest_notification) {
                    showNotificationToast(data.latest_notification);
                }
            }
        },
        error: function() {
            console.warn('Notification check failed'); // Debug
        }
    });
}

function updateNotificationBadge(count) {
    const badge = $('.notification-badge');
    if (badge.length) {
        badge.text(count);
        badge.toggle(count > 0);
    }
}

function showNotificationToast(notification) {
    showToast(notification.message, notification.type || 'info', notification.icon || 'bell');
}

// ===============================
// TOAST NOTIFICATIONS
// ===============================
function showToast(message, type = 'info', icon = 'info-circle') {
    const toast = $(`
        <div class="toast-notification toast-${type}">
            <div class="toast-content">
                <i class="fas fa-${icon}"></i>
                <div class="toast-message">${message}</div>
            </div>
            <button class="toast-close">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `);
    
    $('body').append(toast);
    
    // Handle close button
    toast.find('.toast-close').on('click', function() {
        toast.remove();
    });
    
    // Auto-remove after 4 seconds
    setTimeout(() => {
        if (toast.parent().length) {
            toast.remove();
        }
    }, 4000);
}

function showSuccessToast(message) {
    showToast(message, 'success', 'check-circle');
}

function showErrorToast(message) {
    showToast(message, 'danger', 'exclamation-triangle');
}

function showInfoToast(message) {
    showToast(message, 'info', 'info-circle');
}

function showWarningToast(message) {
    showToast(message, 'warning', 'exclamation-triangle');
}

// ===============================
// SEARCH FUNCTIONALITY
// ===============================
function initializeSearch() {
    const searchInput = $('#globalSearch');
    const searchResults = $('#searchResults');
    
    if (!searchInput.length || !searchResults.length) return;
    
    let searchTimeout;
    
    searchInput.on('input', function() {
        clearTimeout(searchTimeout);
        const query = this.value.trim();
        
        if (query.length < 2) {
            searchResults.hide();
            return;
        }
        
        searchTimeout = setTimeout(() => {
            performSearch(query);
        }, 300);
    });
    
    // Hide search results when clicking outside
    $(document).on('click.searchOutside', function(event) {
        if (!searchInput.is(event.target) && !searchResults.is(event.target) && 
            !searchInput.has(event.target).length && !searchResults.has(event.target).length) {
            searchResults.hide();
        }
    });
}

function performSearch(query) {
    const searchResults = $('#searchResults');
    
    // Show loading state
    searchResults.html('<div class="p-3 text-center"><i class="fas fa-spinner fa-spin"></i> Searching...</div>');
    searchResults.show();
    
    // Get tenant slug from global variable or URL
    const tenantSlug = window.tenant_slug || getTenantSlugFromURL();
    
    if (!tenantSlug) {
        searchResults.html('<div class="p-3 text-muted">Search not available</div>');
        return;
    }
    
    $.ajax({
        url: `/business/${tenantSlug}/api/search/`,
        method: 'GET',
        data: { q: query },
        success: function(data) {
            displaySearchResults(data.results || []);
        },
        error: function() {
            searchResults.html('<div class="p-3 text-muted">Search error occurred</div>');
        }
    });
}

function displaySearchResults(results) {
    const searchResults = $('#searchResults');
    
    if (!results || results.length === 0) {
        searchResults.html('<div class="p-3 text-muted">No results found</div>');
        return;
    }
    
    let html = '';
    results.forEach(result => {
        html += `
            <a href="${result.url}" class="search-result-item">
                <i class="fas fa-${result.icon || 'file'} text-${result.type || 'primary'}"></i>
                <div>
                    <div class="search-result-title">${result.title}</div>
                    <div class="search-result-description">${result.description || ''}</div>
                </div>
            </a>
        `;
    });
    
    searchResults.html(html);
}

// ===============================
// FORM ENHANCEMENTS
// ===============================
function initializeForms() {
    // Loading states for forms
    $(document).on('submit', 'form', function() {
        const form = $(this);
        const submitBtn = form.find('button[type="submit"]');
        
        if (submitBtn.length && !submitBtn.hasClass('no-loading')) {
            const originalText = submitBtn.html();
            
            submitBtn.prop('disabled', true);
            submitBtn.html('<span class="spinner-border spinner-border-sm me-2"></span>Processing...');
            
            // Store original text for restoration
            submitBtn.data('original-text', originalText);
            
            // Re-enable after 10 seconds as fallback
            setTimeout(() => {
                if (submitBtn.prop('disabled')) {
                    submitBtn.prop('disabled', false);
                    submitBtn.html(originalText);
                }
            }, 10000);
        }
    });
    
    // Restore button state on page show (for back button navigation)
    $(window).on('pageshow', function() {
        $('button[type="submit"]').each(function() {
            const btn = $(this);
            const originalText = btn.data('original-text');
            if (originalText) {
                btn.prop('disabled', false);
                btn.html(originalText);
            }
        });
    });
}

// ===============================
// TOOLTIPS AND POPOVERS
// ===============================
function initializeTooltips() {
    // Initialize Bootstrap tooltips
    if (typeof bootstrap !== 'undefined') {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function(tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
        
        // Initialize Bootstrap popovers
        const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
        popoverTriggerList.map(function(popoverTriggerEl) {
            return new bootstrap.Popover(popoverTriggerEl);
        });
    }
}

// ===============================
// THEME FUNCTIONALITY
// ===============================
function initializeTheme() {
    // Load theme from localStorage
    try {
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme === 'dark') {
            document.body.classList.add('dark-theme');
            updateThemeToggle(true);
        } else {
            updateThemeToggle(false);
        }
    } catch (e) {
        console.warn('localStorage not available for theme:', e); // Debug
        updateThemeToggle(false);
    }
}

function toggleTheme() {
    const body = document.body;
    const isDark = body.classList.contains('dark-theme');
    
    console.log('Toggle theme called, current isDark:', isDark); // Debug
    
    if (isDark) {
        body.classList.remove('dark-theme');
        updateThemeToggle(false);
        try {
            localStorage.setItem('theme', 'light');
        } catch (e) {
            console.warn('localStorage not available for theme:', e); // Debug
        }
        showSuccessToast('Switched to Light Mode');
    } else {
        body.classList.add('dark-theme');
        updateThemeToggle(true);
        try {
            localStorage.setItem('theme', 'dark');
        } catch (e) {
            console.warn('localStorage not available for theme:', e); // Debug
        }
        showSuccessToast('Switched to Dark Mode');
    }
}

function updateThemeToggle(isDark) {
    // Update all theme icons across the app
    const themeIcons = [
        document.getElementById('theme-icon'),
        document.getElementById('user-menu-theme-icon'),
        document.getElementById('sidebar-theme-icon')
    ];
    
    const themeTexts = [
        document.getElementById('theme-text'),
        document.getElementById('user-menu-theme-text'),
        document.getElementById('sidebar-theme-text')
    ];
    
    themeIcons.forEach(icon => {
        if (icon) {
            icon.className = isDark ? 'fas fa-sun me-2' : 'fas fa-moon me-2';
        }
    });
    
    themeTexts.forEach(text => {
        if (text) {
            text.textContent = isDark ? 'Light Mode' : 'Dark Mode';
        }
    });
    
    // Update document attribute for CSS targeting
    document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
    
    console.log('Theme updated to:', isDark ? 'dark' : 'light'); // Debug
}

// ===============================
// KEYBOARD SHORTCUTS
// ===============================
function initializeKeyboardShortcuts() {
    $(document).on('keydown', function(event) {
        // Ctrl/Cmd + K for search
        if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
            event.preventDefault();
            const searchInput = $('#globalSearch');
            if (searchInput.length) {
                searchInput.focus();
            }
        }
        
        // ESC to close modals and dropdowns
        if (event.key === 'Escape') {
            // Close search results
            $('#searchResults').hide();
            
            // Close dropdowns
            $('.nav-dropdown.open').removeClass('open');
            
            // Close mobile sidebar
            if ($('#sidebar').hasClass('mobile-open')) {
                closeMobileSidebar();
            }
            
            // Close public navbar
            if ($('.navbar-collapse').hasClass('show')) {
                $('.navbar-collapse').removeClass('show');
                $('.navbar-toggler .navbar-toggler-icon').removeClass('active');
            }
            
            // Close search modals
            $('.search-modal').remove();
        }
    });
}

// ===============================
// AJAX AND CSRF SETUP
// ===============================
function setupCSRF() {
    // AJAX setup for Django CSRF
    $.ajaxSetup({
        beforeSend: function(xhr, settings) {
            if (!this.crossDomain && !csrfSafeMethod(settings.type)) {
                const csrfToken = getCookie('csrftoken') || $('[name=csrfmiddlewaretoken]').val();
                if (csrfToken) {
                    xhr.setRequestHeader("X-CSRFToken", csrfToken);
                }
            }
        }
    });
}

function csrfSafeMethod(method) {
    return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// ===============================
// UTILITY FUNCTIONS
// ===============================
function getTenantSlugFromURL() {
    const pathParts = window.location.pathname.split('/');
    const businessIndex = pathParts.indexOf('business');
    if (businessIndex !== -1 && pathParts[businessIndex + 1]) {
        return pathParts[businessIndex + 1];
    }
    return null;
}

// ===============================
// BUSINESS SPECIFIC FUNCTIONS
// ===============================
function startNextService() {
    const tenantSlug = window.tenant_slug || getTenantSlugFromURL();
    if (!tenantSlug) {
        showErrorToast('Unable to start service');
        return;
    }
    
    $.ajax({
        url: `/business/${tenantSlug}/services/ajax/start-next/`,
        method: 'POST',
        success: function(data) {
            if (data.success) {
                showSuccessToast('Service started successfully');
                if (data.redirect_url) {
                    window.location.href = data.redirect_url;
                } else {
                    // Refresh current page or update UI
                    window.location.reload();
                }
            } else {
                showErrorToast(data.message || 'No services in queue');
            }
        },
        error: function() {
            showErrorToast('Error starting service');
        }
    });
}

function completeCurrentService() {
    const tenantSlug = window.tenant_slug || getTenantSlugFromURL();
    if (!tenantSlug) {
        showErrorToast('Unable to complete service');
        return;
    }
    
    $.ajax({
        url: `/business/${tenantSlug}/services/ajax/current-service/`,
        method: 'GET',
        success: function(data) {
            if (data.current_service) {
                window.location.href = `/business/${tenantSlug}/services/orders/${data.current_service.id}/`;
            } else {
                showInfoToast('No active service to complete');
            }
        },
        error: function() {
            showErrorToast('Error checking current service');
        }
    });
}

// Customer search functions
function openCustomerSearch() {
    createSearchModal('Find Customer', 'customer', 'Search by name, phone, or ID...');
}

function openVehicleSearch() {
    createSearchModal('Find Vehicle', 'vehicle', 'Search by registration, make, or model...');
}

function createSearchModal(title, type, placeholder) {
    const modal = $(`
        <div class="search-modal">
            <div class="search-modal-content">
                <div class="search-modal-header">
                    <h3>${title}</h3>
                    <button type="button" class="close-modal">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="search-modal-body">
                    <input type="text" id="${type}-search-input" placeholder="${placeholder}" class="form-control" autocomplete="off">
                    <div id="${type}-search-results" class="mt-3"></div>
                </div>
            </div>
        </div>
    `);
    
    $('body').append(modal);
    
    // Focus on input
    modal.find(`#${type}-search-input`).focus();
    
    // Close modal events
    modal.find('.close-modal').on('click', () => modal.remove());
    modal.on('click', function(e) {
        if (e.target === this) {
            modal.remove();
        }
    });
    
    // Search functionality
    let searchTimeout;
    modal.find(`#${type}-search-input`).on('input', function() {
        clearTimeout(searchTimeout);
        const query = this.value.trim();
        const resultsDiv = modal.find(`#${type}-search-results`);
        
        if (query.length < 2) {
            resultsDiv.empty();
            return;
        }
        
        searchTimeout = setTimeout(() => {
            performModalSearch(type, query, resultsDiv);
        }, 300);
    });
}

function performModalSearch(type, query, resultsDiv) {
    const tenantSlug = window.tenant_slug || getTenantSlugFromURL();
    if (!tenantSlug) {
        resultsDiv.html('<div class="text-center p-3 text-muted">Search not available</div>');
        return;
    }
    
    resultsDiv.html('<div class="text-center p-3"><i class="fas fa-spinner fa-spin"></i> Searching...</div>');
    
    $.ajax({
        url: `/business/${tenantSlug}/services/ajax/${type}/search/`,
        method: 'GET',
        data: { q: query },
        success: function(data) {
            displayModalSearchResults(type, data.results || [], resultsDiv);
        },
        error: function() {
            resultsDiv.html('<div class="text-center p-3 text-muted">Search error occurred</div>');
        }
    });
}

function displayModalSearchResults(type, results, resultsDiv) {
    if (!results || results.length === 0) {
        resultsDiv.html('<div class="text-center p-3 text-muted">No results found</div>');
        return;
    }
    
    let html = '';
    results.forEach(result => {
        if (type === 'customer') {
            html += `
                <div class="search-result-item" onclick="selectCustomer('${result.id}', '${result.name}')">
                    <strong>${result.name}</strong><br>
                    <small class="text-muted">${result.phone || ''} ${result.customer_id ? '- ' + result.customer_id : ''}</small>
                </div>
            `;
        } else if (type === 'vehicle') {
            html += `
                <div class="search-result-item" onclick="selectVehicle('${result.id}', '${result.registration}')">
                    <strong>${result.registration}</strong> - ${result.make || ''} ${result.model || ''}<br>
                    <small class="text-muted">${result.color || ''} ${result.customer_name ? '| Owner: ' + result.customer_name : ''}</small>
                </div>
            `;
        }
    });
    
    resultsDiv.html(html);
}

function selectCustomer(customerId, customerName) {
    const tenantSlug = window.tenant_slug || getTenantSlugFromURL();
    $('.search-modal').remove();
    if (tenantSlug) {
        window.location.href = `/business/${tenantSlug}/customers/${customerId}/`;
    }
}

function selectVehicle(vehicleId, registration) {
    const tenantSlug = window.tenant_slug || getTenantSlugFromURL();
    $('.search-modal').remove();
    if (tenantSlug) {
        window.location.href = `/business/${tenantSlug}/customers/vehicles/${vehicleId}/`;
    }
}

// Payment Functions
function openPaymentQuickProcess() {
    const tenantSlug = window.tenant_slug || getTenantSlugFromURL();
    if (tenantSlug) {
        window.location.href = `/business/${tenantSlug}/payments/create/`;
    }
}

function openReceiptPrint() {
    const tenantSlug = window.tenant_slug || getTenantSlugFromURL();
    if (tenantSlug) {
        window.location.href = `/business/${tenantSlug}/payments/receipts/`;
    }
}

// ===============================
// UTILITY FUNCTIONS FOR UI
// ===============================
function printPage() {
    window.print();
}

function printElement(elementId) {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    const printWindow = window.open('', '_blank');
    printWindow.document.write(`
        <html>
            <head>
                <title>Print</title>
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
                <style>
                    @media print {
                        body { margin: 0; padding: 20px; }
                        .no-print { display: none !important; }
                    }
                </style>
            </head>
            <body>
                ${element.outerHTML}
            </body>
        </html>
    `);
    printWindow.document.close();
    printWindow.print();
    printWindow.close();
}

function exportToCSV(tableId, filename = 'export.csv') {
    const table = document.getElementById(tableId);
    if (!table) return;
    
    let csv = [];
    const rows = table.querySelectorAll('tr');
    
    for (let i = 0; i < rows.length; i++) {
        const row = [];
        const cols = rows[i].querySelectorAll('td, th');
        
        for (let j = 0; j < cols.length; j++) {
            let data = cols[j].innerText.replace(/(\r\n|\n|\r)/gm, '').replace(/(\s\s)/gm, ' ');
            data = data.replace(/"/g, '""');
            row.push('"' + data + '"');
        }
        csv.push(row.join(','));
    }
    
    const csvFile = new Blob([csv.join('\n')], { type: 'text/csv' });
    const downloadLink = document.createElement('a');
    downloadLink.download = filename;
    downloadLink.href = window.URL.createObjectURL(csvFile);
    downloadLink.style.display = 'none';
    document.body.appendChild(downloadLink);
    downloadLink.click();
    document.body.removeChild(downloadLink);
}

function confirmAction(message, callback) {
    if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
        const modal = $(`
            <div class="modal fade" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Confirm Action</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p>${message}</p>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-danger confirm-btn">Confirm</button>
                        </div>
                    </div>
                </div>
            </div>
        `);
        
        $('body').append(modal);
        
        const bsModal = new bootstrap.Modal(modal[0]);
        bsModal.show();
        
        modal.find('.confirm-btn').on('click', function() {
            bsModal.hide();
            callback();
        });
        
        modal.on('hidden.bs.modal', function() {
            modal.remove();
        });
    } else {
        if (confirm(message)) {
            callback();
        }
    }
}

function showLoadingOverlay(text = 'Loading...') {
    const overlay = $(`
        <div id="loading-overlay" class="loading-overlay">
            <div class="ripple-container">
                <div class="ripple-circle">
                    <i class="fas fa-car"></i>
                </div>
                <div class="ripple ripple-1"></div>
                <div class="ripple ripple-2"></div>
                <div class="ripple ripple-3"></div>
                <img src="/static/img/water-splash.svg" class="loading-illustration" alt="Loading illustration">
            </div>
        </div>
    `);
    
    $('body').append(overlay);
}

function hideLoadingOverlay() {
    const overlay = $('#loading-overlay');
    if (overlay.length) {
        overlay.addClass('hide');
        setTimeout(() => overlay.remove(), 500); // Remove after fade-out animation
    }
}

// Data table enhancements
function initializeDataTable(tableId, options = {}) {
    const table = $(`#${tableId}`);
    if (!table.length) return;
    
    // Add responsive wrapper if not present
    if (!table.parent().hasClass('table-responsive')) {
        table.wrap('<div class="table-responsive"></div>');
    }
    
    // Add sorting functionality if requested
    if (options.sortable) {
        table.find('thead th').each(function(index) {
            const th = $(this);
            if (!th.hasClass('no-sort')) {
                th.addClass('sortable').css('cursor', 'pointer');
                th.on('click', function() {
                    sortTable(tableId, index);
                });
            }
        });
    }
    
    // Add search functionality if requested
    if (options.searchable) {
        const searchInput = $(`
            <div class="mb-3">
                <input type="text" class="form-control" placeholder="Search table..." id="${tableId}-search">
            </div>
        `);
        
        table.parent().before(searchInput);
        
        searchInput.find('input').on('input', function() {
            filterTable(tableId, this.value);
        });
    }
}

function sortTable(tableId, columnIndex) {
    const table = document.getElementById(tableId);
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    const isAscending = table.getAttribute('data-sort-dir') !== 'asc';
    table.setAttribute('data-sort-dir', isAscending ? 'asc' : 'desc');
    
    rows.sort((a, b) => {
        const aValue = a.cells[columnIndex].textContent.trim();
        const bValue = b.cells[columnIndex].textContent.trim();
        
        const aNum = parseFloat(aValue);
        const bNum = parseFloat(bValue);
        
        if (!isNaN(aNum) && !isNaN(bNum)) {
            return isAscending ? aNum - bNum : bNum - aNum;
        } else {
            return isAscending ? 
                aValue.localeCompare(bValue) : 
                bValue.localeCompare(aValue);
        }
    });
    
    rows.forEach(row => tbody.appendChild(row));
    
    // Update sort indicators
    table.querySelectorAll('th.sortable').forEach((th, index) => {
        th.classList.remove('sort-asc', 'sort-desc');
        if (index === columnIndex) {
            th.classList.add(isAscending ? 'sort-asc' : 'sort-desc');
        }
    });
}

function filterTable(tableId, searchTerm) {
    const table = document.getElementById(tableId);
    const tbody = table.querySelector('tbody');
    const rows = tbody.querySelectorAll('tr');
    
    const term = searchTerm.toLowerCase();
    
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(term) ? '' : 'none';
    });
}

// ===============================
// GLOBAL VARIABLES AND EXPORTS
// ===============================
if (typeof window.tenant_slug === 'undefined') {
    window.tenant_slug = getTenantSlugFromURL();
}

window.toggleDropdown = toggleDropdown;
window.toggleTheme = toggleTheme;
window.startNextService = startNextService;
window.completeCurrentService = completeCurrentService;
window.openCustomerSearch = openCustomerSearch;
window.openVehicleSearch = openVehicleSearch;
window.selectCustomer = selectCustomer;
window.selectVehicle = selectVehicle;
window.openPaymentQuickProcess = openPaymentQuickProcess;
window.openReceiptPrint = openReceiptPrint;
window.printPage = printPage;
window.printElement = printElement;
window.exportToCSV = exportToCSV;
window.confirmAction = confirmAction;
window.showLoadingOverlay = showLoadingOverlay;
window.hideLoadingOverlay = hideLoadingOverlay;
window.showSuccessToast = showSuccessToast;
window.showErrorToast = showErrorToast;
window.showInfoToast = showInfoToast;
window.showWarningToast = showWarningToast;
window.initializeDataTable = initializeDataTable;