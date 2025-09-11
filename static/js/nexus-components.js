// Nexus Components JavaScript
document.addEventListener('DOMContentLoaded', function() {
// Make functions globally available
window.toggleTheme = toggleTheme;
window.initializeTheme = initializeTheme;
window.applyTheme = applyTheme;
window.updateThemeToggleButton = updateThemeToggleButton;    // Sidebar elements
    const mobileToggle = document.getElementById('mobileSidebarToggle');
    const desktopToggle = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');
    const sidebarOverlay = document.querySelector('.sidebar-overlay');
    const topbar = document.querySelector('.topbar');
    const mainContent = document.querySelector('.main-content');
    const body = document.body;

    // Create sidebar overlay if it doesn't exist
    if (!sidebarOverlay) {
        const overlay = document.createElement('div');
        overlay.className = 'sidebar-overlay';
        overlay.id = 'sidebarOverlay';
        document.body.appendChild(overlay);
    }

    // Get the actual overlay element (created or existing)
    const actualOverlay = document.querySelector('.sidebar-overlay') || document.getElementById('sidebarOverlay');

    // Mobile toggle functionality
    if (mobileToggle) {
        mobileToggle.addEventListener('click', function() {
            console.log('Mobile toggle clicked'); // Debug log
            sidebar.classList.toggle('mobile-open');
            
            // When opening mobile sidebar, ensure it's not collapsed
            if (sidebar.classList.contains('mobile-open')) {
                sidebar.classList.remove('collapsed');
                if (topbar) topbar.classList.remove('sidebar-collapsed');
                if (mainContent) mainContent.classList.remove('sidebar-collapsed');
                
                // Force visibility of text elements on mobile
                setTimeout(() => {
                    const navTexts = document.querySelectorAll('.nav-text');
                    const brandText = document.querySelector('.brand-text');
                    const userInfo = document.querySelector('.user-info');
                    
                    navTexts.forEach(text => {
                        text.style.opacity = '1';
                        text.style.width = 'auto';
                        text.style.whiteSpace = 'normal'; // Allow text wrapping
                        text.style.overflow = 'visible';
                        text.style.textOverflow = 'initial';
                    });
                    
                    if (brandText) {
                        brandText.style.opacity = '1';
                        brandText.style.width = 'auto';
                    }
                    
                    if (userInfo) {
                        userInfo.style.opacity = '1';
                        userInfo.style.width = 'auto';
                    }
                    
                    console.log('Mobile sidebar opened - forced text visibility and wrapping');
                }, 50);
            }
            
            if (actualOverlay) {
                actualOverlay.classList.toggle('show');
            }
            body.classList.toggle('sidebar-open');
        });
    }

    // Desktop toggle functionality
    if (desktopToggle) {
        desktopToggle.addEventListener('click', function() {
            sidebar.classList.toggle('collapsed');
            if (topbar) topbar.classList.toggle('sidebar-collapsed');
            if (mainContent) mainContent.classList.toggle('sidebar-collapsed');
            
            // Save state to localStorage
            const isCollapsed = sidebar.classList.contains('collapsed');
            localStorage.setItem('sidebarCollapsed', isCollapsed);
        });
    }

    // Sidebar overlay click
    if (actualOverlay) {
        actualOverlay.addEventListener('click', function() {
            console.log('Overlay clicked'); // Debug log
            sidebar.classList.remove('mobile-open');
            actualOverlay.classList.remove('show');
            body.classList.remove('sidebar-open');
        });
    }

    // Clear sidebar collapsed state for debugging (remove after testing)
    localStorage.removeItem('sidebarCollapsed');
    
    // Restore sidebar state on page load (desktop only)
    if (window.innerWidth > 992) {
        const savedState = localStorage.getItem('sidebarCollapsed');
        if (savedState === 'true') {
            sidebar.classList.add('collapsed');
            if (topbar) topbar.classList.add('sidebar-collapsed');
            if (mainContent) mainContent.classList.add('sidebar-collapsed');
        }
    }

    // Force brand text visibility check
    function ensureBrandTextVisibility() {
        const brandText = document.querySelector('.brand-text');
        const brandName = document.querySelector('.brand-name');
        const brandType = document.querySelector('.brand-type');
        
        if (brandText && brandName && brandType) {
            const isCollapsed = sidebar.classList.contains('collapsed');
            console.log('Sidebar collapsed state:', isCollapsed);
            console.log('Brand text computed style:', window.getComputedStyle(brandText));
            
            if (!isCollapsed) {
                // Force visibility when not collapsed
                brandText.style.opacity = '1';
                brandText.style.width = 'auto';
                brandName.style.display = 'block';
                brandType.style.display = 'block';
                console.log('Forced brand text visibility');
            }
        } else {
            console.log('Brand elements not found:', { brandText, brandName, brandType });
        }
    }

    // Run visibility check after DOM is ready
    setTimeout(ensureBrandTextVisibility, 100);

    // Ensure sidebar scrolling works properly
    function ensureSidebarScrolling() {
        const sidebarNav = document.querySelector('.sidebar-nav');
        if (sidebarNav) {
            const navHeight = sidebarNav.scrollHeight;
            const containerHeight = sidebarNav.clientHeight;
            const isScrollable = navHeight > containerHeight;
            
            console.log('Sidebar navigation stats:', {
                scrollHeight: navHeight,
                clientHeight: containerHeight,
                isScrollable: isScrollable,
                overflow: window.getComputedStyle(sidebarNav).overflowY
            });
            
            // Force scroll properties if needed
            if (isScrollable) {
                sidebarNav.style.overflowY = 'auto';
                sidebarNav.style.overflowX = 'hidden';
                console.log('Sidebar scrolling enabled');
            }
        }
    }

    // Run scrolling check after DOM is ready
    setTimeout(ensureSidebarScrolling, 200);

    // Add scroll event listener for debugging
    const sidebarNav = document.querySelector('.sidebar-nav');
    if (sidebarNav) {
        sidebarNav.addEventListener('scroll', function() {
            console.log('Sidebar scrolled:', {
                scrollTop: this.scrollTop,
                scrollHeight: this.scrollHeight,
                clientHeight: this.clientHeight
            });
        });
    }

    // Enhanced submenu management
    function enhanceSubmenuScrolling() {
        const dropdowns = document.querySelectorAll('.nav-dropdown');
        dropdowns.forEach(dropdown => {
            const toggle = dropdown.querySelector('.nav-dropdown-toggle, .dropdown-toggle');
            const submenu = dropdown.querySelector('.nav-submenu');
            
            if (toggle && submenu) {
                toggle.addEventListener('click', function() {
                    setTimeout(() => {
                        if (dropdown.classList.contains('open')) {
                            const submenuHeight = submenu.scrollHeight;
                            const availableHeight = window.innerHeight - 300;
                            
                            console.log('Submenu opened:', {
                                submenuHeight: submenuHeight,
                                availableHeight: availableHeight,
                                needsScrolling: submenuHeight > availableHeight
                            });
                            
                            // Ensure submenu scrolling is enabled if needed
                            if (submenuHeight > availableHeight) {
                                submenu.style.overflowY = 'auto';
                                submenu.style.maxHeight = availableHeight + 'px';
                                console.log('Enabled submenu scrolling');
                            }
                        }
                    }, 300); // Wait for animation to complete
                });
            }
        });
    }

    // Initialize submenu enhancements
    setTimeout(enhanceSubmenuScrolling, 300);

    // Handle window resize
    window.addEventListener('resize', function() {
        if (window.innerWidth > 768) {
            // Close mobile sidebar on desktop
            sidebar.classList.remove('mobile-open');
            if (actualOverlay) {
                actualOverlay.classList.remove('show');
            }
            body.classList.remove('sidebar-open');
        } else {
            // Remove collapsed state on mobile and force text visibility
            sidebar.classList.remove('collapsed');
            if (topbar) topbar.classList.remove('sidebar-collapsed');
            if (mainContent) mainContent.classList.remove('sidebar-collapsed');
            
            // Force visibility of all text elements on mobile
            setTimeout(() => {
                const navTexts = document.querySelectorAll('.nav-text');
                const brandText = document.querySelector('.brand-text');
                const userInfo = document.querySelector('.user-info');
                const sectionTitles = document.querySelectorAll('.nav-section-title');
                
                navTexts.forEach(text => {
                    text.style.opacity = '1';
                    text.style.width = 'auto';
                    text.style.whiteSpace = 'normal'; // Allow text wrapping
                    text.style.overflow = 'visible';
                    text.style.textOverflow = 'initial';
                });
                
                sectionTitles.forEach(title => {
                    title.style.opacity = '1';
                    title.style.height = 'auto';
                });
                
                if (brandText) {
                    brandText.style.opacity = '1';
                    brandText.style.width = 'auto';
                }
                
                if (userInfo) {
                    userInfo.style.opacity = '1';
                    userInfo.style.width = 'auto';
                }
                
                console.log('Mobile view - forced all text visibility and wrapping');
            }, 100);
        }
    });

    // Enhanced dropdown behavior
    const dropdowns = document.querySelectorAll('.dropdown');
    dropdowns.forEach(dropdown => {
        const toggle = dropdown.querySelector('.dropdown-toggle');
        const menu = dropdown.querySelector('.dropdown-menu');

        if (toggle && menu) {
            // Prevent dropdown from closing when clicking inside
            menu.addEventListener('click', function(e) {
                if (!e.target.closest('a')) {
                    e.stopPropagation();
                }
            });
        }
    });

    // Navigation active states
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.nav-link');
    
    navLinks.forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
            
            // Expand parent group if exists
            const parentGroup = link.closest('.nav-group');
            if (parentGroup) {
                parentGroup.classList.add('expanded');
            }
        }
    });

    // Submenu toggle functionality
    const groupToggles = document.querySelectorAll('.nav-group-toggle');
    groupToggles.forEach(toggle => {
        toggle.addEventListener('click', function(e) {
            e.preventDefault();
            const group = this.closest('.nav-group');
            group.classList.toggle('expanded');
        });
    });

    // Initialize sidebar dropdowns
    initializeSidebarDropdowns();

    // Auto-hide alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            setTimeout(() => {
                alert.remove();
            }, 300);
        }, 5000);
    });

    // Initialize Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

// Initialize Sidebar Dropdowns
function initializeSidebarDropdowns() {
    console.log('Initializing sidebar dropdowns...'); // Debug log
    const dropdownToggles = document.querySelectorAll('.nav-dropdown-toggle');
    console.log('Found dropdown toggles:', dropdownToggles.length); // Debug log
    
    dropdownToggles.forEach((toggle, index) => {
        console.log('Processing toggle', index, toggle); // Debug log
        
        // Remove existing onclick handlers
        toggle.removeAttribute('onclick');
        
        // Add new click event listener
        toggle.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            console.log('Toggle clicked!'); // Debug log
            
            const dropdown = this.closest('.nav-dropdown');
            if (dropdown) {
                console.log('Found dropdown:', dropdown.id); // Debug log
                toggleDropdown(dropdown.id);
            } else {
                console.log('No dropdown found for toggle'); // Debug log
            }
        });
    });
}

// Sidebar Dropdown Toggle Function (Global)
window.toggleDropdown = function(dropdownId) {
    console.log('toggleDropdown called with:', dropdownId); // Debug log
    const dropdown = document.getElementById(dropdownId);
    if (!dropdown) {
        console.log('Dropdown not found:', dropdownId); // Debug log
        return;
    }

    console.log('Dropdown found, current classes:', dropdown.className); // Debug log
    
    const isExpanded = dropdown.classList.contains('expanded');
    
    // Close all other dropdowns first
    const allDropdowns = document.querySelectorAll('.nav-dropdown');
    allDropdowns.forEach(dd => {
        if (dd.id !== dropdownId) {
            dd.classList.remove('expanded');
            const ddArrow = dd.querySelector('.nav-arrow');
            if (ddArrow) {
                ddArrow.classList.remove('fa-chevron-up');
                ddArrow.classList.add('fa-chevron-down');
            }
        }
    });
    
    // Toggle current dropdown
    if (isExpanded) {
        dropdown.classList.remove('expanded');
    } else {
        dropdown.classList.add('expanded');
    }
    
    console.log('After toggle, dropdown classes:', dropdown.className); // Debug log
    
    // Update arrow direction
    const arrow = dropdown.querySelector('.nav-arrow');
    if (arrow) {
        if (dropdown.classList.contains('expanded')) {
            arrow.classList.remove('fa-chevron-down');
            arrow.classList.add('fa-chevron-up');
        } else {
            arrow.classList.remove('fa-chevron-up');
            arrow.classList.add('fa-chevron-down');
        }
    }
};

// Close dropdowns when clicking outside
document.addEventListener('click', function(e) {
    if (!e.target.closest('.nav-dropdown')) {
        const allDropdowns = document.querySelectorAll('.nav-dropdown');
        allDropdowns.forEach(dd => {
            dd.classList.remove('expanded');
            const arrow = dd.querySelector('.nav-arrow');
            if (arrow) {
                arrow.classList.remove('fa-chevron-up');
                arrow.classList.add('fa-chevron-down');
            }
        });
    }
});

// Theme Toggle Function - Re-enabled to work with main.js
function toggleTheme() {
    // Use the main.js implementation if available
    if (window.toggleTheme && typeof window.toggleTheme === 'function') {
        window.toggleTheme();
        return;
    }
    
    // Fallback implementation
    const currentTheme = localStorage.getItem('theme') || 'light';
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    
    // Update localStorage
    localStorage.setItem('theme', newTheme);
    
    // Apply theme
    applyTheme(newTheme);
    
    // Update theme toggle button
    updateThemeToggleButton(newTheme);
    
    console.log('Theme toggled to:', newTheme);
}

// Initialize Theme
function initializeTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    applyTheme(savedTheme);
    updateThemeToggleButton(savedTheme);
}

// Apply Theme
function applyTheme(theme) {
    const body = document.body;
    
    if (theme === 'dark') {
        body.classList.add('dark-theme');
        body.classList.remove('light-theme');
        document.documentElement.setAttribute('data-bs-theme', 'dark');
    } else {
        body.classList.add('light-theme');
        body.classList.remove('dark-theme');
        document.documentElement.setAttribute('data-bs-theme', 'light');
    }
}

// Update Theme Toggle Button
function updateThemeToggleButton(theme) {
    const themeIcon = document.querySelector('#user-menu-theme-icon');
    const themeText = document.querySelector('#user-menu-theme-text');
    
    if (themeIcon && themeText) {
        if (theme === 'dark') {
            themeIcon.className = 'fas fa-sun';
            themeText.textContent = 'Light Mode';
        } else {
            themeIcon.className = 'fas fa-moon';
            themeText.textContent = 'Dark Mode';
        }
    }
    
    // Also update any other theme toggle buttons with the class selectors
    const otherThemeIcons = document.querySelectorAll('.theme-toggle-icon');
    const otherThemeTexts = document.querySelectorAll('.theme-toggle-text');
    
    otherThemeIcons.forEach(icon => {
        if (theme === 'dark') {
            icon.className = 'fas fa-sun theme-toggle-icon';
        } else {
            icon.className = 'fas fa-moon theme-toggle-icon';
        }
    });
    
    otherThemeTexts.forEach(text => {
        if (theme === 'dark') {
            text.textContent = 'Light Mode';
        } else {
            text.textContent = 'Dark Mode';
        }
    });
    
    console.log('Theme toggle button updated for theme:', theme);
}
    
    otherThemeTexts.forEach(text => {
        if (theme === 'dark') {
            text.textContent = 'Light Mode';
        } else {
            text.textContent = 'Dark Mode';
        }
    });
    
    console.log('Theme toggle button updated for theme:', theme);
}

// Notification functionality
function markNotificationAsRead(notificationId) {
    if (!window.tenant_slug) {
        console.error('Tenant slug not available');
        return;
    }
    
    fetch(`/business/${window.tenant_slug}/notifications/mark-read/${notificationId}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json',
        },
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Update notification badge
            const badge = document.querySelector('.notification-badge');
            if (badge) {
                const currentCount = parseInt(badge.textContent) || 0;
                const newCount = Math.max(0, currentCount - 1);
                if (newCount === 0) {
                    badge.style.display = 'none';
                } else {
                    badge.textContent = newCount;
                }
            }
            
            // Update notification item
            const notificationItem = document.querySelector(`[data-notification-id="${notificationId}"]`);
            if (notificationItem) {
                notificationItem.classList.remove('unread');
            }
        }
    })
    .catch(error => {
        console.error('Error marking notification as read:', error);
    });
}

// Mark all notifications as read
function markAllNotificationsAsRead() {
    if (!window.tenant_slug) {
        console.error('Tenant slug not available');
        return;
    }
    
    fetch(`/business/${window.tenant_slug}/notifications/mark-all-read/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json',
        },
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Hide notification badge
            const badge = document.querySelector('.notification-badge');
            if (badge) {
                badge.style.display = 'none';
            }
            
            // Mark all notifications as read in UI
            const notificationItems = document.querySelectorAll('.notification-item.unread');
            notificationItems.forEach(item => {
                item.classList.remove('unread');
            });
        }
    })
    .catch(error => {
        console.error('Error marking all notifications as read:', error);
    });
}

// CSRF Token helper
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

// Smooth scrolling for anchor links
document.addEventListener('click', function(e) {
    const anchor = e.target.closest('a[href^="#"]');
    if (anchor) {
        e.preventDefault();
        const target = document.querySelector(anchor.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    }
});

// Initialize theme and expose functions globally
initializeTheme();
