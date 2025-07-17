// Dashboard JavaScript - Tenant-specific functionality

$(document).ready(function() {
    // Sidebar toggle functionality
    $('#sidebarToggle').on('click', function() {
        const sidebar = $('#sidebar');
        const mainContent = $('#main-content');
        
        if (window.innerWidth <= 768) {
            // Mobile behavior
            sidebar.toggleClass('mobile-open');
        } else {
            // Desktop behavior
            sidebar.toggleClass('collapsed');
            mainContent.toggleClass('expanded');
            
            // Store preference in localStorage if available
            try {
                localStorage.setItem('sidebar-collapsed', sidebar.hasClass('collapsed'));
            } catch (e) {
                // localStorage not available
            }
        }
    });
    
    // Close mobile sidebar when clicking outside
    $(document).on('click', function(event) {
        if (window.innerWidth <= 768) {
            const sidebar = $('#sidebar');
            const sidebarToggle = $('#sidebarToggle');
            
            if (!sidebar.is(event.target) && sidebar.has(event.target).length === 0 &&
                !sidebarToggle.is(event.target) && sidebarToggle.has(event.target).length === 0) {
                sidebar.removeClass('mobile-open');
            }
        }
    });
    
    // Restore sidebar state from localStorage if available
    try {
        const isCollapsed = localStorage.getItem('sidebar-collapsed') === 'true';
        if (isCollapsed && window.innerWidth > 768) {
            $('#sidebar').addClass('collapsed');
            $('#main-content').addClass('expanded');
        }
    } catch (e) {
        // localStorage not available
    }
    
    // Dashboard charts and widgets
    initializeDashboardWidgets();
    
    // Real-time notifications
    initializeNotifications();
    
    // Auto-refresh dashboard data
    setInterval(refreshDashboardData, 300000); // 5 minutes
    
    // Quick actions
    initializeQuickActions();
});

// Initialize dashboard widgets
function initializeDashboardWidgets() {
    // Stats cards animation
    $('.stats-card').each(function(index) {
        $(this).css('animation-delay', (index * 0.1) + 's');
        $(this).addClass('fade-in');
    });
    
    // Initialize charts if Chart.js is available
    if (typeof Chart !== 'undefined') {
        initializeCharts();
    }
    
    // Initialize data tables
    if ($.fn.DataTable) {
        $('.data-table').DataTable({
            responsive: true,
            pageLength: 25,
            order: [[0, 'desc']],
            language: {
                search: "Search:",
                lengthMenu: "Show _MENU_ entries",
                info: "Showing _START_ to _END_ of _TOTAL_ entries",
                infoEmpty: "No entries found",
                infoFiltered: "(filtered from _MAX_ total entries)",
                zeroRecords: "No matching records found",
                emptyTable: "No data available in table"
            }
        });
    }
}

// Initialize charts
function initializeCharts() {
    // Revenue chart
    const revenueCtx = document.getElementById('revenueChart');
    if (revenueCtx) {
        new Chart(revenueCtx, {
            type: 'line',
            data: {
                labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
                datasets: [{
                    label: 'Revenue',
                    data: [12000, 19000, 15000, 25000, 22000, 30000],
                    borderColor: '#2563eb',
                    backgroundColor: 'rgba(37, 99, 235, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return 'KES ' + value.toLocaleString();
                            }
                        }
                    }
                }
            }
        });
    }
    
    // Services chart
    const servicesCtx = document.getElementById('servicesChart');
    if (servicesCtx) {
        new Chart(servicesCtx, {
            type: 'doughnut',
            data: {
                labels: ['Car Wash', 'Detailing', 'Waxing', 'Interior Cleaning'],
                datasets: [{
                    data: [40, 25, 20, 15],
                    backgroundColor: [
                        '#2563eb',
                        '#06b6d4',
                        '#10b981',
                        '#f59e0b'
                    ],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }
}

// Initialize notifications
function initializeNotifications() {
    // Mark notifications as read when dropdown is opened
    $('.notification-btn').on('click', function() {
        setTimeout(() => {
            markNotificationsAsRead();
        }, 1000);
    });
    
    // Check for new notifications periodically
    setInterval(checkNewNotifications, 60000); // 1 minute
}

// Mark notifications as read
function markNotificationsAsRead() {
    $.ajax({
        url: '/notifications/mark-read/',
        method: 'POST',
        success: function(response) {
            if (response.success) {
                $('.notification-badge').fadeOut();
            }
        },
        error: function() {
            // Handle error silently
        }
    });
}

// Check for new notifications
function checkNewNotifications() {
    $.ajax({
        url: '/notifications/check-new/',
        method: 'GET',
        success: function(response) {
            if (response.count > 0) {
                $('.notification-badge').text(response.count).show();
                
                // Show browser notification if permission granted
                if (Notification.permission === 'granted') {
                    new Notification('New Notification', {
                        body: `You have ${response.count} new notification(s)`,
                        icon: '/static/img/favicon.ico'
                    });
                }
            }
        },
        error: function() {
            // Handle error silently
        }
    });
}

// Refresh dashboard data
function refreshDashboardData() {
    $.ajax({
        url: '/api/dashboard-data/',
        method: 'GET',
        success: function(response) {
            updateDashboardStats(response);
        },
        error: function() {
            // Handle error silently
        }
    });
}

// Update dashboard statistics
function updateDashboardStats(data) {
    // Update stats cards
    if (data.revenue) {
        $('#total-revenue').text(new Intl.NumberFormat('en-KE', {
            style: 'currency',
            currency: 'KES'
        }).format(data.revenue));
    }
    
    if (data.customers) {
        $('#total-customers').text(data.customers.toLocaleString());
    }
    
    if (data.services_today) {
        $('#services-today').text(data.services_today.toLocaleString());
    }
    
    if (data.pending_orders) {
        $('#pending-orders').text(data.pending_orders.toLocaleString());
    }
}

// Initialize quick actions
function initializeQuickActions() {
    // Quick customer add
    $(document).on('submit', '#quick-customer-form', function(e) {
        e.preventDefault();
        
        const formData = $(this).serialize();
        
        $.ajax({
            url: $(this).attr('action'),
            method: 'POST',
            data: formData,
            success: function(response) {
                if (response.success) {
                    $('#quick-customer-modal').modal('hide');
                    showAlert('success', 'Customer added successfully!');
                    $(this)[0].reset();
                } else {
                    showAlert('error', response.message || 'Error adding customer');
                }
            },
            error: function() {
                showAlert('error', 'Error adding customer');
            }
        });
    });
    
    // Quick service order
    $(document).on('submit', '#quick-service-form', function(e) {
        e.preventDefault();
        
        const formData = $(this).serialize();
        
        $.ajax({
            url: $(this).attr('action'),
            method: 'POST',
            data: formData,
            success: function(response) {
                if (response.success) {
                    $('#quick-service-modal').modal('hide');
                    showAlert('success', 'Service order created successfully!');
                    $(this)[0].reset();
                    refreshDashboardData();
                } else {
                    showAlert('error', response.message || 'Error creating service order');
                }
            },
            error: function() {
                showAlert('error', 'Error creating service order');
            }
        });
    });
}

// Show alert function
function showAlert(type, message) {
    const alertHtml = `
        <div class="alert alert-${type} alert-dismissible fade show" role="alert">
            <div class="d-flex align-items-center">
                <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-triangle'} me-2"></i>
                <div class="flex-grow-1">${message}</div>
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        </div>
    `;
    
    $('.content-wrapper').prepend(alertHtml);
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        $('.alert').fadeOut('slow');
    }, 5000);
}

// Handle window resize
$(window).on('resize', function() {
    const sidebar = $('#sidebar');
    const mainContent = $('#main-content');
    
    if (window.innerWidth > 768) {
        // Desktop: remove mobile classes
        sidebar.removeClass('mobile-open');
        
        // Restore collapsed state if it was set
        try {
            const isCollapsed = localStorage.getItem('sidebar-collapsed') === 'true';
            if (isCollapsed) {
                sidebar.addClass('collapsed');
                mainContent.addClass('expanded');
            }
        } catch (e) {
            // localStorage not available
        }
    } else {
        // Mobile: remove desktop classes
        sidebar.removeClass('collapsed');
        mainContent.removeClass('expanded');
    }
});

// Request notification permission on page load
if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission();
}

// Export functions for global use
window.dashboardUtils = {
    showAlert: showAlert,
    refreshDashboardData: refreshDashboardData,
    updateDashboardStats: updateDashboardStats
};