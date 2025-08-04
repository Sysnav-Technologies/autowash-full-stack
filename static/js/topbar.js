// Topbar Components JavaScript
$(document).ready(function() {
    initializeTopbarComponents();
});

function initializeTopbarComponents() {
    initializeQuickActions();
    initializeNotifications();
    initializeUserMenu();
}

// ===============================
// QUICK ACTIONS FUNCTIONALITY
// ===============================
function initializeQuickActions() {
    // Quick search functionality
    let searchTimeout;
    
    $('#quickSearchInput').on('input', function() {
        clearTimeout(searchTimeout);
        const query = $(this).val().trim();
        
        if (query.length < 2) {
            $('#quickSearchResults').removeClass('show').empty();
            return;
        }
        
        searchTimeout = setTimeout(() => {
            performQuickSearch(query);
        }, 300);
    });
    
    // Hide search results when clicking outside
    $(document).on('click', function(e) {
        if (!$(e.target).closest('.quick-search-container').length) {
            $('#quickSearchResults').removeClass('show');
        }
    });
    
    // Keyboard shortcuts
    $(document).on('keydown', function(e) {
        // Ctrl/Cmd + K for new customer
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            const tenantSlug = window.tenant_slug || getTenantSlugFromURL();
            if (tenantSlug) {
                window.location.href = `/business/${tenantSlug}/customers/create/`;
            }
        }
        
        // Ctrl/Cmd + Shift + O for quick order
        if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'O') {
            e.preventDefault();
            const tenantSlug = window.tenant_slug || getTenantSlugFromURL();
            if (tenantSlug) {
                window.location.href = `/business/${tenantSlug}/services/orders/quick/`;
            }
        }
    });
}

function performQuickSearch(query) {
    const tenantSlug = window.tenant_slug || getTenantSlugFromURL();
    if (!tenantSlug) return;
    
    $.ajax({
        url: `/business/${tenantSlug}/customers/ajax/search/`,
        method: 'GET',
        data: { q: query, limit: 5 },
        beforeSend: function() {
            $('#quickSearchResults').html('<div class="p-2 text-center"><i class="fas fa-spinner fa-spin"></i></div>').addClass('show');
        },
        success: function(data) {
            displayQuickSearchResults(data.results || []);
        },
        error: function() {
            $('#quickSearchResults').html('<div class="p-2 text-muted">Search error</div>');
        }
    });
}

function displayQuickSearchResults(results) {
    const container = $('#quickSearchResults');
    
    if (!results || results.length === 0) {
        container.html('<div class="p-2 text-muted">No customers found</div>');
        return;
    }
    
    let html = '';
    results.forEach(result => {
        html += `
            <div class="search-result-item" onclick="selectCustomer('${result.id}', '${result.name}')">
                <div class="search-result-title">${result.name}</div>
                <div class="search-result-subtitle">${result.phone || result.email || ''}</div>
            </div>
        `;
    });
    
    container.html(html);
}

function selectCustomer(customerId, customerName) {
    // Close search results
    $('#quickSearchResults').removeClass('show');
    $('#quickSearchInput').val(customerName);
    
    const tenantSlug = window.tenant_slug || getTenantSlugFromURL();
    if (tenantSlug) {
        window.location.href = `/business/${tenantSlug}/customers/${customerId}/`;
    }
}

// Attendance confirmation functions
function confirmClockIn() {
    return confirm('Are you ready to start your work day?');
}

function confirmClockOut() {
    return confirm('Are you sure you want to end your work day?');
}

function confirmTakeBreak() {
    return confirm('Do you want to start your break?');
}

function confirmEndBreak() {
    return confirm('Ready to resume work?');
}

// Show success/error messages for attendance actions
function showAttendanceMessage(message, type = 'success') {
    const alertClass = type === 'success' ? 'alert-success' : 'alert-danger';
    const icon = type === 'success' ? 'check-circle' : 'exclamation-triangle';
    
    const alert = $(`
        <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
            <i class="fas fa-${icon} me-2"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `);
    
    $('.content-wrapper').prepend(alert);
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        alert.alert('close');
    }, 5000);
}

// ===============================
// NOTIFICATIONS FUNCTIONALITY
// ===============================
function initializeNotifications() {
    // Only initialize notifications if we have a tenant slug (i.e., we're in a business context)
    const tenantSlug = window.tenant_slug || getTenantSlugFromURL();
    if (!tenantSlug) {
        return; // Exit early if not in a business context
    }
    
    // Mark notification as read when clicked
    $(document).on('click', '.notification-item', function() {
        const $item = $(this);
        if ($item.hasClass('unread')) {
            markNotificationAsRead($item);
        }
    });
    
    // Mark all notifications as read
    $(document).on('click', '[data-action="mark-all-read"]', function(e) {
        e.preventDefault();
        markAllNotificationsAsRead();
    });
    
    // Periodic check for new notifications
    setInterval(checkForNewNotifications, 30000); // Check every 30 seconds
}

function markNotificationAsRead($item) {
    const notificationId = $item.data('notification-id');
    if (!notificationId) return;
    
    const tenantSlug = window.tenant_slug || getTenantSlugFromURL();
    if (!tenantSlug) return;
    
    $.ajax({
        url: `/business/${tenantSlug}/notifications/${notificationId}/mark-read/`,
        method: 'POST',
        success: function() {
            $item.removeClass('unread');
            $item.find('.notification-indicator').remove();
            updateNotificationBadge();
        },
        error: function() {
            console.error('Failed to mark notification as read');
        }
    });
}

function markAllNotificationsAsRead() {
    const tenantSlug = window.tenant_slug || getTenantSlugFromURL();
    if (!tenantSlug) return;
    
    $.ajax({
        url: `/business/${tenantSlug}/notifications/mark-all-read/`,
        method: 'POST',
        success: function() {
            $('.notification-item.unread').removeClass('unread');
            $('.notification-indicator').remove();
            $('.notification-badge').hide();
            updateNotificationBadge(0);
            showSuccessToast('All notifications marked as read');
        },
        error: function() {
            showErrorToast('Failed to mark notifications as read');
        }
    });
}

function checkForNewNotifications() {
    const tenantSlug = window.tenant_slug || getTenantSlugFromURL();
    if (!tenantSlug) return;
    
    $.ajax({
        url: `/business/${tenantSlug}/notifications/api/check/`,
        method: 'GET',
        success: function(data) {
            if (data.unread_count > 0) {
                updateNotificationBadge(data.unread_count);
                if (data.notifications && data.notifications.length > 0) {
                    showNotificationToast(data.notifications[0]);
                }
            }
        },
        error: function() {
            // Silently fail
        }
    });
}

function updateNotificationBadge(count = null) {
    const badge = $('.notification-badge');
    
    if (count !== null) {
        badge.text(count);
        badge.toggle(count > 0);
    } else {
        // Count unread notifications in DOM
        const unreadCount = $('.notification-item.unread').length;
        badge.text(unreadCount);
        badge.toggle(unreadCount > 0);
    }
}

function showNotificationToast(notification) {
    showToast(notification.message, notification.type || 'info', notification.icon || 'bell');
}

// ===============================
// USER MENU FUNCTIONALITY
// ===============================
function initializeUserMenu() {
    // Handle user menu interactions
    $('.user-menu').on('click', function() {
        // Additional user menu logic can go here
    });
    
    // Handle theme toggle - use event delegation for all theme toggle buttons
    $(document).off('click.theme').on('click.theme', '[onclick="toggleTheme()"], .theme-toggle-btn', function(e) {
        e.preventDefault();
        console.log('Theme toggle clicked'); // Debug
        if (window.toggleTheme) {
            window.toggleTheme();
        } else {
            console.error('toggleTheme function not available');
        }
    });
    
    // Initialize theme on page load
    if (window.initializeTheme) {
        window.initializeTheme();
    }
}

// Make sure theme functions are available globally
window.toggleTheme = window.toggleTheme || function() {
    console.log('Fallback toggleTheme called');
    const body = document.body;
    const isDark = body.classList.contains('dark-theme');
    
    if (isDark) {
        body.classList.remove('dark-theme');
        try {
            localStorage.setItem('theme', 'light');
        } catch (e) {}
    } else {
        body.classList.add('dark-theme');
        try {
            localStorage.setItem('theme', 'dark');
        } catch (e) {}
    }
    
    // Update icons manually if updateThemeToggle isn't available
    const themeIcons = document.querySelectorAll('[id*="theme-icon"]');
    const themeTexts = document.querySelectorAll('[id*="theme-text"]');
    
    themeIcons.forEach(icon => {
        icon.className = isDark ? 'fas fa-sun me-2' : 'fas fa-moon me-2';
    });
    
    themeTexts.forEach(text => {
        text.textContent = isDark ? 'Light Mode' : 'Dark Mode';
    });
};

// ===============================
// BREADCRUMB FUNCTIONALITY
// ===============================
function updateBreadcrumbs(breadcrumbs) {
    const breadcrumbContainer = $('.breadcrumb');
    if (!breadcrumbContainer.length) return;
    
    breadcrumbContainer.empty();
    
    breadcrumbs.forEach((crumb, index) => {
        const isLast = index === breadcrumbs.length - 1;
        const listItem = $(`
            <li class="breadcrumb-item ${isLast ? 'active' : ''}">
                ${isLast ? crumb.title : `<a href="${crumb.url}">${crumb.title}</a>`}
            </li>
        `);
        breadcrumbContainer.append(listItem);
    });
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
// GLOBAL EXPORTS
// ===============================
// Make functions available globally
window.confirmClockIn = confirmClockIn;
window.confirmClockOut = confirmClockOut;
window.confirmTakeBreak = confirmTakeBreak;
window.confirmEndBreak = confirmEndBreak;
window.showAttendanceMessage = showAttendanceMessage;
window.selectCustomer = selectCustomer;
window.markAllNotificationsAsRead = markAllNotificationsAsRead;
window.updateBreadcrumbs = updateBreadcrumbs;

// ===============================
// AUTO-INITIALIZATION
// ===============================
// Initialize on DOM ready
$(document).ready(function() {
    // Auto-update notification badge on page load
    updateNotificationBadge();
    
    // Handle form submissions from quick actions
    $(document).on('submit', '.quick-action-form', function(e) {
        e.preventDefault();
        const form = $(this);
        const submitBtn = form.find('button[type="submit"]');
        const originalText = submitBtn.html();
        
        submitBtn.prop('disabled', true);
        submitBtn.html('<span class="spinner-border spinner-border-sm me-2"></span>Processing...');
        
        $.ajax({
            url: form.attr('action'),
            method: form.attr('method') || 'POST',
            data: form.serialize(),
            success: function(data) {
                if (data.success) {
                    showSuccessToast(data.message || 'Action completed successfully');
                    if (data.redirect_url) {
                        window.location.href = data.redirect_url;
                    } else {
                        // Close dropdown
                        $('.dropdown-menu').removeClass('show');
                    }
                } else {
                    showErrorToast(data.message || 'Action failed');
                }
            },
            error: function() {
                showErrorToast('An error occurred');
            },
            complete: function() {
                submitBtn.prop('disabled', false);
                submitBtn.html(originalText);
            }
        });
    });
    
    // Handle attendance actions
    $(document).on('click', '[data-action="clock-in"]', function(e) {
        e.preventDefault();
        if (confirmClockIn()) {
            performAttendanceAction('clock-in', 'Clocked in successfully');
        }
    });
    
    $(document).on('click', '[data-action="clock-out"]', function(e) {
        e.preventDefault();
        if (confirmClockOut()) {
            performAttendanceAction('clock-out', 'Clocked out successfully');
        }
    });
    
    $(document).on('click', '[data-action="take-break"]', function(e) {
        e.preventDefault();
        if (confirmTakeBreak()) {
            performAttendanceAction('take-break', 'Break started');
        }
    });
    
    $(document).on('click', '[data-action="end-break"]', function(e) {
        e.preventDefault();
        if (confirmEndBreak()) {
            performAttendanceAction('end-break', 'Break ended');
        }
    });
});

function performAttendanceAction(action, successMessage) {
    const tenantSlug = window.tenant_slug || getTenantSlugFromURL();
    if (!tenantSlug) return;
    
    $.ajax({
        url: `/business/${tenantSlug}/employees/attendance/${action}/`,
        method: 'POST',
        success: function(data) {
            if (data.success) {
                showAttendanceMessage(successMessage, 'success');
                // Refresh the page or update UI as needed
                setTimeout(() => {
                    window.location.reload();
                }, 1500);
            } else {
                showAttendanceMessage(data.message || 'Action failed', 'error');
            }
        },
        error: function() {
            showAttendanceMessage('An error occurred', 'error');
        }
    });
}

// ===============================
// RESPONSIVE BEHAVIOR
// ===============================
$(window).on('resize', function() {
    // Handle responsive behavior for dropdowns
    if (window.innerWidth <= 768) {
        // Mobile adjustments
        $('.quick-actions-menu, .notification-dropdown, .user-dropdown').each(function() {
            const $dropdown = $(this);
            if ($dropdown.hasClass('show')) {
                // Adjust positioning for mobile
                $dropdown.css('transform', 'none');
            }
        });
    }
});

// Handle dropdown positioning on mobile
$(document).on('shown.bs.dropdown', function(e) {
    if (window.innerWidth <= 768) {
        const dropdown = $(e.target).find('.dropdown-menu');
        const rect = dropdown[0].getBoundingClientRect();
        
        // Check if dropdown goes off screen
        if (rect.right > window.innerWidth) {
            dropdown.css('left', 'auto');
            dropdown.css('right', '0');
        }
        
        if (rect.bottom > window.innerHeight) {
            dropdown.css('top', 'auto');
            dropdown.css('bottom', '100%');
        }
    }
});