/**
 * Modern Components JavaScript - Nexus Style Design
 * Handles sidebar, topbar, and responsive interactions
 */

document.addEventListener('DOMContentLoaded', function() {
    initializeSidebar();
    initializeDropdowns();
    initializeResponsive();
    initializeSearch();
    restoreDropdownStates();
});

/**
 * Initialize sidebar functionality
 */
function initializeSidebar() {
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const mainContent = document.querySelector('.app-main-content');
    
    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('collapsed');
            
            // Store sidebar state
            localStorage.setItem('sidebarCollapsed', sidebar.classList.contains('collapsed'));
        });
        
        // Restore sidebar state
        const isCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
        if (isCollapsed) {
            sidebar.classList.add('collapsed');
        }
    }
}

/**
 * Initialize dropdown functionality
 */
function initializeDropdowns() {
    console.log('Dropdown initialization skipped - handled by nexus-components.js'); // Debug log
    
    // The dropdown functionality is already handled by nexus-components.js
    // We'll just handle the mobile-specific behaviors here
    
    // Handle submenu item clicks on mobile
    const submenuLinks = document.querySelectorAll('.nav-submenu .nav-link');
    submenuLinks.forEach(link => {
        link.addEventListener('click', function() {
            const isMobile = window.innerWidth <= 768;
            if (isMobile) {
                const sidebar = document.getElementById('sidebar');
                const overlay = document.querySelector('.sidebar-overlay');
                
                // Close mobile sidebar when navigating
                if (sidebar && sidebar.classList.contains('mobile-open')) {
                    sidebar.classList.remove('mobile-open');
                    document.body.classList.remove('sidebar-open');
                    if (overlay) {
                        overlay.classList.remove('show');
                        setTimeout(() => overlay.style.display = 'none', 300);
                    }
                    // Close all dropdowns
                    document.querySelectorAll('.nav-dropdown.open, .nav-dropdown.expanded').forEach(dropdown => {
                        dropdown.classList.remove('open', 'expanded');
                    });
                }
            }
        });
    });
}

/**
 * Toggle dropdown function (global) - Fallback only
 */
function toggleDropdown(dropdownId) {
    // This is a fallback - the main function is in nexus-components.js
    console.log('Fallback toggleDropdown called for:', dropdownId);
    if (window.toggleDropdown && window.toggleDropdown !== toggleDropdown) {
        window.toggleDropdown(dropdownId);
    }
}

/**
 * Restore dropdown states from localStorage
 */
function restoreDropdownStates() {
    try {
        const openDropdowns = JSON.parse(localStorage.getItem('openDropdowns') || '[]');
        openDropdowns.forEach(dropdownId => {
            const dropdown = document.getElementById(dropdownId);
            if (dropdown) {
                dropdown.classList.add('expanded'); // Use expanded class to match nexus-components.js
            }
        });
    } catch (e) {
        console.warn('Could not restore dropdown states:', e);
    }
}

// Make toggleDropdown available globally
window.toggleDropdown = toggleDropdown;

/**
 * Initialize responsive behavior
 */
function initializeResponsive() {
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.querySelector('.app-main-content');
    
    function handleResize() {
        const isMobile = window.innerWidth <= 768;
        
        if (sidebar && mainContent) {
            if (isMobile) {
                sidebar.classList.add('mobile');
                
                // Close all dropdowns when switching to mobile
                document.querySelectorAll('.nav-dropdown.open, .nav-dropdown.expanded').forEach(dropdown => {
                    dropdown.classList.remove('open', 'expanded');
                });
                
                // Add overlay for mobile sidebar
                if (!document.querySelector('.sidebar-overlay')) {
                    const overlay = document.createElement('div');
                    overlay.className = 'sidebar-overlay';
                    overlay.addEventListener('click', function() {
                        sidebar.classList.remove('mobile-open');
                        document.body.classList.remove('sidebar-open');
                        this.classList.remove('show');
                        setTimeout(() => this.style.display = 'none', 300);
                        // Close all dropdowns when overlay is clicked
                        document.querySelectorAll('.nav-dropdown.open, .nav-dropdown.expanded').forEach(dropdown => {
                            dropdown.classList.remove('open', 'expanded');
                        });
                    });
                    document.body.appendChild(overlay);
                }
            } else {
                sidebar.classList.remove('mobile', 'mobile-open');
                const overlay = document.querySelector('.sidebar-overlay');
                if (overlay) {
                    overlay.style.display = 'none';
                }
                // Restore dropdown states from localStorage when switching back to desktop
                restoreDropdownStates();
            }
        }
    }
    
    // Handle mobile sidebar toggle
    const sidebarToggle = document.getElementById('sidebarToggle');
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function() {
            const isMobile = window.innerWidth <= 768;
            if (isMobile && sidebar) {
                const isOpening = !sidebar.classList.contains('mobile-open');
                sidebar.classList.toggle('mobile-open');
                const overlay = document.querySelector('.sidebar-overlay');
                
                if (isOpening) {
                    // Opening sidebar
                    document.body.classList.add('sidebar-open');
                    if (overlay) {
                        overlay.style.display = 'block';
                        setTimeout(() => overlay.classList.add('show'), 10);
                    }
                } else {
                    // Closing sidebar
                    document.body.classList.remove('sidebar-open');
                    if (overlay) {
                        overlay.classList.remove('show');
                        setTimeout(() => overlay.style.display = 'none', 300);
                    }
                    // Close all dropdowns when closing mobile sidebar
                    document.querySelectorAll('.nav-dropdown.open, .nav-dropdown.expanded').forEach(dropdown => {
                        dropdown.classList.remove('open', 'expanded');
                    });
                }
            }
        });
    }
    
    // Initial check
    handleResize();
    
    // Listen for resize events
    window.addEventListener('resize', handleResize);
}

/**
 * Initialize search functionality
 */
function initializeSearch() {
    const searchInput = document.querySelector('.search-input');
    
    if (searchInput) {
        searchInput.addEventListener('focus', function() {
            this.parentElement.classList.add('focused');
        });
        
        searchInput.addEventListener('blur', function() {
            this.parentElement.classList.remove('focused');
        });
        
        // Handle search keyboard shortcut (Cmd/Ctrl + K)
        document.addEventListener('keydown', function(e) {
            if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
                e.preventDefault();
                searchInput.focus();
            }
        });
    }
}

/**
 * Utility functions
 */
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
