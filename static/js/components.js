/**
 * Modern Components JavaScript - Nexus Style Design
 * Handles sidebar, topbar, and responsive interactions
 */

document.addEventListener('DOMContentLoaded', function() {
    initializeSidebar();
    initializeDropdowns();
    initializeResponsive();
    initializeSearch();
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
    // Handle navigation dropdowns
    const dropdownToggles = document.querySelectorAll('.nav-dropdown-toggle');
    
    dropdownToggles.forEach(toggle => {
        toggle.addEventListener('click', function(e) {
            e.preventDefault();
            const dropdown = this.closest('.nav-dropdown');
            const isOpen = dropdown.classList.contains('open');
            
            // Close all other dropdowns
            document.querySelectorAll('.nav-dropdown.open').forEach(openDropdown => {
                if (openDropdown !== dropdown) {
                    openDropdown.classList.remove('open');
                }
            });
            
            // Toggle current dropdown
            dropdown.classList.toggle('open', !isOpen);
        });
    });
    
    // Close dropdowns when clicking outside
    document.addEventListener('click', function(e) {
        if (!e.target.closest('.nav-dropdown')) {
            document.querySelectorAll('.nav-dropdown.open').forEach(dropdown => {
                dropdown.classList.remove('open');
            });
        }
    });
}

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
                
                // Add overlay for mobile sidebar
                if (!document.querySelector('.sidebar-overlay')) {
                    const overlay = document.createElement('div');
                    overlay.className = 'sidebar-overlay';
                    overlay.addEventListener('click', function() {
                        sidebar.classList.remove('mobile-open');
                        this.style.display = 'none';
                    });
                    document.body.appendChild(overlay);
                }
            } else {
                sidebar.classList.remove('mobile', 'mobile-open');
                const overlay = document.querySelector('.sidebar-overlay');
                if (overlay) {
                    overlay.style.display = 'none';
                }
            }
        }
    }
    
    // Handle mobile sidebar toggle
    const sidebarToggle = document.getElementById('sidebarToggle');
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function() {
            const isMobile = window.innerWidth <= 768;
            if (isMobile && sidebar) {
                sidebar.classList.toggle('mobile-open');
                const overlay = document.querySelector('.sidebar-overlay');
                if (overlay) {
                    overlay.style.display = sidebar.classList.contains('mobile-open') ? 'block' : 'none';
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
