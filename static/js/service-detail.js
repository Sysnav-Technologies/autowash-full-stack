// Service Detail JavaScript Functions

/**
 * Add service to order
 * @param {string} serviceId - The ID of the service to add
 */
function addToOrder(serviceId) {
    // Navigate to quick order with service pre-selected
    const tenantSlug = document.querySelector('[data-tenant-slug]')?.dataset.tenantSlug || '';
    window.location.href = `/business/${tenantSlug}/services/orders/quick/?service=${serviceId}`;
}

/**
 * Quick order functionality (alias for addToOrder)
 * @param {string} serviceId - The ID of the service
 */
function quickOrder(serviceId) {
    addToOrder(serviceId);
}

/**
 * Add service to package
 * @param {string} serviceId - The ID of the service to add to package
 */
function addToPackage(serviceId) {
    // Show modal for adding to service package
    // TODO: Implement package creation/editing modal
    if (confirm('Would you like to add this service to a package?')) {
        const tenantSlug = document.querySelector('[data-tenant-slug]')?.dataset.tenantSlug || '';
        window.location.href = `/business/${tenantSlug}/services/packages/create/?service=${serviceId}`;
    }
}

/**
 * View analytics for service
 * @param {string} serviceId - The ID of the service
 */
function viewAnalytics(serviceId) {
    const tenantSlug = document.querySelector('[data-tenant-slug]')?.dataset.tenantSlug || '';
    window.location.href = `/business/${tenantSlug}/reports/analytics/?module=services&service=${serviceId}`;
}

/**
 * Edit service
 * @param {string} serviceId - The ID of the service to edit
 */
function editService(serviceId) {
    const tenantSlug = document.querySelector('[data-tenant-slug]')?.dataset.tenantSlug || '';
    window.location.href = `/business/${tenantSlug}/services/${serviceId}/edit/`;
}

/**
 * Toggle service active status
 * @param {string} serviceId - The ID of the service
 * @param {boolean} currentStatus - Current active status
 */
function toggleServiceStatus(serviceId, currentStatus) {
    const action = currentStatus ? 'deactivate' : 'activate';
    const confirmMessage = `Are you sure you want to ${action} this service?`;
    
    if (confirm(confirmMessage)) {
        // TODO: Implement AJAX status toggle
        const tenantSlug = document.querySelector('[data-tenant-slug]')?.dataset.tenantSlug || '';
        
        fetch(`/business/${tenantSlug}/services/${serviceId}/toggle-status/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || '',
            },
            body: JSON.stringify({
                active: !currentStatus
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Error updating service status: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error updating service status');
        });
    }
}

/**
 * Initialize service detail page functionality
 */
document.addEventListener('DOMContentLoaded', function() {
    // Add tenant slug to document for easy access
    const tenantSlug = window.location.pathname.split('/')[2];
    if (tenantSlug) {
        document.body.setAttribute('data-tenant-slug', tenantSlug);
    }
    
    // Initialize dynamic category colors
    initializeCategoryColors();
    
    // Initialize additional functionality
    initializeImagePreview();
    initializeTooltips();
});

/**
 * Initialize dynamic category colors
 */
function initializeCategoryColors() {
    const categoryBadges = document.querySelectorAll('.category-badge[data-category-color]');
    
    categoryBadges.forEach(badge => {
        const color = badge.getAttribute('data-category-color');
        if (color) {
            // Convert hex to rgba for background
            const rgba = hexToRgba(color, 0.1);
            const borderRgba = hexToRgba(color, 0.2);
            
            badge.style.backgroundColor = rgba;
            badge.style.color = color;
            badge.style.borderColor = borderRgba;
        }
    });
}

/**
 * Convert hex color to rgba
 * @param {string} hex - Hex color code
 * @param {number} alpha - Alpha value (0-1)
 * @returns {string} RGBA color string
 */
function hexToRgba(hex, alpha) {
    // Remove # if present
    hex = hex.replace('#', '');
    
    // Parse hex values
    const r = parseInt(hex.substr(0, 2), 16);
    const g = parseInt(hex.substr(2, 2), 16);
    const b = parseInt(hex.substr(4, 2), 16);
    
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/**
 * Initialize image preview functionality
 */
function initializeImagePreview() {
    const serviceImage = document.querySelector('.service-main-image');
    if (serviceImage) {
        serviceImage.addEventListener('click', function() {
            // Create modal for image preview
            const modal = document.createElement('div');
            modal.className = 'image-preview-modal';
            modal.innerHTML = `
                <div class="image-preview-overlay">
                    <div class="image-preview-container">
                        <button class="image-preview-close">&times;</button>
                        <img src="${this.src}" alt="${this.alt}" class="image-preview-full">
                    </div>
                </div>
            `;
            
            document.body.appendChild(modal);
            
            // Close modal functionality
            modal.querySelector('.image-preview-close').addEventListener('click', function() {
                document.body.removeChild(modal);
            });
            
            modal.querySelector('.image-preview-overlay').addEventListener('click', function(e) {
                if (e.target === this) {
                    document.body.removeChild(modal);
                }
            });
        });
    }
}

/**
 * Initialize Bootstrap tooltips if available
 */
function initializeTooltips() {
    if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
}
