// Nexus Sidebar & Component JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Sidebar Toggle Functionality
    const sidebarToggle = document.getElementById('sidebarToggle');
    const mobileSidebarToggle = document.getElementById('mobileSidebarToggle');
    const sidebar = document.querySelector('.sidebar');
    const topbar = document.querySelector('.topbar');
    const mainContent = document.querySelector('.main-content');
    const sidebarOverlay = document.querySelector('.sidebar-overlay');
    
    // Desktop sidebar toggle
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('collapsed');
            topbar.classList.toggle('sidebar-collapsed');
            if (mainContent) {
                mainContent.classList.toggle('sidebar-collapsed');
            }
            
            // Store sidebar state in localStorage
            localStorage.setItem('sidebarCollapsed', sidebar.classList.contains('collapsed'));
        });
    }
    
    // Mobile sidebar toggle
    if (mobileSidebarToggle) {
        mobileSidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('mobile-open');
            sidebarOverlay.classList.toggle('show');
            document.body.classList.toggle('sidebar-open');
        });
    }
    
    // Close mobile sidebar when clicking overlay
    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', function() {
            sidebar.classList.remove('mobile-open');
            sidebarOverlay.classList.remove('show');
            document.body.classList.remove('sidebar-open');
        });
    }
    
    // Mobile Quick Menu Functionality
    const mobileMenuToggle = document.getElementById('mobileMenuToggle');
    const mobileQuickMenu = document.getElementById('mobileQuickMenu');
    const mobileMenuOverlay = document.getElementById('mobileMenuOverlay');
    const closeMobileMenu = document.getElementById('closeMobileMenu');
    
    if (mobileMenuToggle && mobileQuickMenu) {
        mobileMenuToggle.addEventListener('click', function() {
            mobileQuickMenu.classList.toggle('show');
            mobileMenuOverlay.classList.toggle('show');
            document.body.classList.toggle('mobile-menu-open');
        });
    }
    
    if (closeMobileMenu) {
        closeMobileMenu.addEventListener('click', function() {
            mobileQuickMenu.classList.remove('show');
            mobileMenuOverlay.classList.remove('show');
            document.body.classList.remove('mobile-menu-open');
        });
    }
    
    if (mobileMenuOverlay) {
        mobileMenuOverlay.addEventListener('click', function() {
            mobileQuickMenu.classList.remove('show');
            mobileMenuOverlay.classList.remove('show');
            document.body.classList.remove('mobile-menu-open');
        });
    }
    
    // Restore sidebar state from localStorage (desktop only)
    if (window.innerWidth > 768) {
        const sidebarCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
        if (sidebarCollapsed) {
            sidebar.classList.add('collapsed');
            topbar.classList.add('sidebar-collapsed');
            if (mainContent) {
                mainContent.classList.add('sidebar-collapsed');
            }
        }
    }
    
    // Navigation Active States
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
    
    // Handle window resize
    window.addEventListener('resize', function() {
        if (window.innerWidth > 768) {
            // Close mobile menus on desktop
            sidebar.classList.remove('mobile-open');
            sidebarOverlay.classList.remove('show');
            mobileQuickMenu.classList.remove('show');
            mobileMenuOverlay.classList.remove('show');
            document.body.classList.remove('sidebar-open', 'mobile-menu-open');
        }
    });
    
    // Submenu Toggle
    const navGroupToggles = document.querySelectorAll('.nav-group-toggle');
    navGroupToggles.forEach(toggle => {
        toggle.addEventListener('click', function(e) {
            e.preventDefault();
            const navGroup = this.closest('.nav-group');
            navGroup.classList.toggle('expanded');
        });
    });
    
    // Dropdown Toggle Function
    window.toggleDropdown = function(dropdownId) {
        const dropdown = document.getElementById(dropdownId);
        if (dropdown) {
            dropdown.classList.toggle('expanded');
            
            // Close other dropdowns
            const allDropdowns = document.querySelectorAll('.nav-dropdown');
            allDropdowns.forEach(dd => {
                if (dd.id !== dropdownId) {
                    dd.classList.remove('expanded');
                }
            });
        }
    };
    
    // Close dropdowns when clicking outside
    document.addEventListener('click', function(e) {
        if (!e.target.closest('.nav-dropdown')) {
            const allDropdowns = document.querySelectorAll('.nav-dropdown');
            allDropdowns.forEach(dd => {
                dd.classList.remove('expanded');
            });
        }
    });
    
    // Notification Mark as Read
    window.markAllAsRead = function() {
        fetch('/api/notifications/mark-all-read/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                'Content-Type': 'application/json',
            },
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update notification badge
                const badge = document.querySelector('.notification-badge');
                if (badge) {
                    badge.remove();
                }
                
                // Mark all notifications as read in UI
                const notificationItems = document.querySelectorAll('.notification-item.unread');
                notificationItems.forEach(item => {
                    item.classList.remove('unread');
                });
            }
        })
        .catch(error => console.error('Error:', error));
    };
    
    // Mobile Responsiveness
    function handleMobileNav() {
        if (window.innerWidth <= 768) {
            sidebar.classList.add('mobile-hidden');
        } else {
            sidebar.classList.remove('mobile-hidden');
        }
    }
    
    // Mobile sidebar overlay (check if it exists, if not create it)
    let mobileSidebarOverlay = document.querySelector('.sidebar-overlay');
    if (!mobileSidebarOverlay) {
        mobileSidebarOverlay = document.createElement('div');
        mobileSidebarOverlay.className = 'sidebar-overlay';
        document.body.appendChild(mobileSidebarOverlay);
    }
    
    // Mobile sidebar toggle
    if (window.innerWidth <= 768) {
        sidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('mobile-open');
            mobileSidebarOverlay.classList.toggle('show');
            document.body.classList.toggle('sidebar-open');
        });
        
        mobileSidebarOverlay.addEventListener('click', function() {
            sidebar.classList.remove('mobile-open');
            mobileSidebarOverlay.classList.remove('show');
            document.body.classList.remove('sidebar-open');
        });
    }
    
    // Handle window resize
    window.addEventListener('resize', handleMobileNav);
    handleMobileNav();
    
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
    
    // Tooltip initialization for Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});
