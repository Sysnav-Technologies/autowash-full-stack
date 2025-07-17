// Sidebar initialization
document.addEventListener('DOMContentLoaded', function() {
    // Sidebar toggle
    const sidebarToggle = document.querySelector('.sidebar-toggle');
    const sidebar = document.getElementById('sidebar');
    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', function(e) {
            e.preventDefault();
            sidebar.classList.toggle('mobile-open');
            if (sidebar.classList.contains('mobile-open')) {
                sidebar.classList.remove('collapsed');
            } else if (window.innerWidth <= 768) {
                sidebar.classList.add('collapsed');
            }
        });
    }

    // Auto-expand active dropdown
    const activeNavItem = document.querySelector('.nav-link.active');
    if (activeNavItem) {
        const parentDropdown = activeNavItem.closest('.nav-dropdown');
        if (parentDropdown) {
            parentDropdown.classList.add('open');
        }
    }
});

// Dropdown toggle function
function toggleDropdown(dropdownId) {
    const dropdown = document.getElementById(dropdownId);
    const allDropdowns = document.querySelectorAll('.nav-dropdown');
    
    allDropdowns.forEach(dd => {
        if (dd.id !== dropdownId) {
            dd.classList.remove('open');
        }
    });
    
    dropdown.classList.toggle('open');
}

// Utility function to get CSRF token
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