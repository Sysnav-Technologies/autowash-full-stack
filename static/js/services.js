/* ========================================
   SERVICES MODULE JAVASCRIPT - AUTOWASH DESIGN SYSTEM
======================================== */

class ServicesManager {
    constructor() {
        this.initializeComponents();
        this.setupEventListeners();
    }

    initializeComponents() {
        // Initialize sortable table if exists
        const table = document.querySelector('.nexus-table[data-sortable="true"]');
        if (table) {
            this.initializeSortableTable(table);
        }

        // Initialize filter form
        this.initializeFilters();
        
        // Initialize stats cards animations
        this.initializeStatsCards();
    }

    initializeSortableTable(table) {
        const headers = table.querySelectorAll('.sortable-header');
        headers.forEach(header => {
            header.style.cursor = 'pointer';
            header.addEventListener('click', () => this.handleSort(header));
        });
    }

    handleSort(header) {
        const column = header.dataset.column;
        const currentDirection = header.dataset.direction || 'asc';
        const newDirection = currentDirection === 'asc' ? 'desc' : 'asc';
        
        // Update header
        header.dataset.direction = newDirection;
        
        // Clear other headers
        header.parentNode.querySelectorAll('.sortable-header').forEach(h => {
            if (h !== header) {
                delete h.dataset.direction;
                h.classList.remove('sorted-asc', 'sorted-desc');
            }
        });
        
        // Add sort class
        header.classList.remove('sorted-asc', 'sorted-desc');
        header.classList.add(`sorted-${newDirection}`);
        
        console.log(`Sorting by ${column} in ${newDirection} order`);
    }

    initializeFilters() {
        const filterForm = document.querySelector('.filter-form');
        if (!filterForm) return;

        // Auto-submit on select changes
        const selects = filterForm.querySelectorAll('select');
        selects.forEach(select => {
            select.addEventListener('change', () => {
                setTimeout(() => filterForm.submit(), 100);
            });
        });

        // Search input with debounce
        const searchInput = filterForm.querySelector('input[name="search"]');
        if (searchInput) {
            let searchTimeout;
            searchInput.addEventListener('input', () => {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    if (searchInput.value.length >= 3 || searchInput.value.length === 0) {
                        filterForm.submit();
                    }
                }, 500);
            });
        }
    }

    initializeStatsCards() {
        const statsCards = document.querySelectorAll('.services-stat-card');
        
        // Animate cards on load
        statsCards.forEach((card, index) => {
            card.style.opacity = '0';
            card.style.transform = 'translateY(20px)';
            
            setTimeout(() => {
                card.style.transition = 'all 0.4s ease';
                card.style.opacity = '1';
                card.style.transform = 'translateY(0)';
            }, index * 100);
        });
    }

    setupEventListeners() {
        // Service deletion
        window.deleteService = this.deleteService.bind(this);
    }

    deleteService(serviceId) {
        const confirmed = confirm('Are you sure you want to delete this service? This action cannot be undone.');
        
        if (!confirmed) return;

        const deleteBtn = document.querySelector(`[onclick="deleteService('${serviceId}')"]`);
        if (deleteBtn) {
            deleteBtn.disabled = true;
            deleteBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        }

        fetch(`/business/${window.location.pathname.split('/')[2]}/services/${serviceId}/delete/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': this.getCSRFToken(),
                'Content-Type': 'application/json',
            },
            credentials: 'same-origin'
        })
        .then(response => {
            if (response.ok) {
                const row = document.querySelector(`tr[data-id="${serviceId}"]`);
                if (row) {
                    row.style.transition = 'all 0.3s ease';
                    row.style.opacity = '0';
                    row.style.transform = 'translateX(-100%)';
                    
                    setTimeout(() => {
                        location.reload();
                    }, 300);
                } else {
                    location.reload();
                }
            } else {
                throw new Error('Delete failed');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error deleting service. Please try again.');
            
            if (deleteBtn) {
                deleteBtn.disabled = false;
                deleteBtn.innerHTML = '<i class="fas fa-trash"></i>';
            }
        });
    }

    getCSRFToken() {
        const token = document.querySelector('[name=csrfmiddlewaretoken]');
        return token ? token.value : '';
    }
}

document.addEventListener('DOMContentLoaded', function() {
    // Initialize Services Manager
    new ServicesManager();
    
    // Legacy compatibility
    initializeTables();
    initializeFormValidation();
    initializeSearchAndFilters();
    initializeServiceQueue();
});

// Legacy functions for compatibility
function initializeTables() {
    // Table row selection
    const tables = document.querySelectorAll('.nexus-table');
    tables.forEach(table => {
        const checkboxes = table.querySelectorAll('input[type="checkbox"]');
        const selectAllCheckbox = table.querySelector('thead input[type="checkbox"]');
        
        // Select all functionality
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', function() {
                checkboxes.forEach(checkbox => {
                    if (checkbox !== selectAllCheckbox) {
                        checkbox.checked = selectAllCheckbox.checked;
                        updateRowSelection(checkbox);
                    }
                });
                updateBulkActions();
            });
        }
        
        // Individual row selection
        checkboxes.forEach(checkbox => {
            if (checkbox !== selectAllCheckbox) {
                checkbox.addEventListener('change', function() {
                    updateRowSelection(checkbox);
                    updateSelectAllCheckbox(table);
                    updateBulkActions();
                });
            }
        });
    });
    
    // Table sorting
    const sortableHeaders = document.querySelectorAll('[data-sort]');
    sortableHeaders.forEach(header => {
        header.addEventListener('click', function() {
            const sortKey = this.getAttribute('data-sort');
            const sortDirection = this.getAttribute('data-direction') || 'asc';
            const newDirection = sortDirection === 'asc' ? 'desc' : 'asc';
            
            // Update sort indicators
            sortableHeaders.forEach(h => h.removeAttribute('data-direction'));
            this.setAttribute('data-direction', newDirection);
            
            // Perform sort (implement based on your data structure)
            sortTable(sortKey, newDirection);
        });
    });
}

function updateRowSelection(checkbox) {
    const row = checkbox.closest('tr');
    if (checkbox.checked) {
        row.classList.add('selected');
    } else {
        row.classList.remove('selected');
    }
}

function updateSelectAllCheckbox(table) {
    const selectAllCheckbox = table.querySelector('thead input[type="checkbox"]');
    const rowCheckboxes = table.querySelectorAll('tbody input[type="checkbox"]');
    const checkedBoxes = table.querySelectorAll('tbody input[type="checkbox"]:checked');
    
    if (selectAllCheckbox) {
        if (checkedBoxes.length === 0) {
            selectAllCheckbox.checked = false;
            selectAllCheckbox.indeterminate = false;
        } else if (checkedBoxes.length === rowCheckboxes.length) {
            selectAllCheckbox.checked = true;
            selectAllCheckbox.indeterminate = false;
        } else {
            selectAllCheckbox.checked = false;
            selectAllCheckbox.indeterminate = true;
        }
    }
}

function updateBulkActions() {
    const checkedBoxes = document.querySelectorAll('tbody input[type="checkbox"]:checked');
    const bulkActions = document.querySelector('.bulk-actions');
    
    if (bulkActions) {
        if (checkedBoxes.length > 0) {
            bulkActions.style.display = 'block';
            const countElement = bulkActions.querySelector('.selected-count');
            if (countElement) {
                countElement.textContent = checkedBoxes.length;
            }
        } else {
            bulkActions.style.display = 'none';
        }
    }
}

// Search and Filters
function initializeSearchAndFilters() {
    const searchInput = document.querySelector('.table-search input');
    const filterSelects = document.querySelectorAll('.table-filter-select');
    
    // Search functionality with debouncing
    if (searchInput) {
        let searchTimeout;
        searchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                performSearch(this.value);
            }, 300);
        });
    }
    
    // Filter functionality
    filterSelects.forEach(select => {
        select.addEventListener('change', function() {
            applyFilters();
        });
    });
}

function performSearch(query) {
    const rows = document.querySelectorAll('.nexus-table tbody tr');
    const lowerQuery = query.toLowerCase();
    
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        if (text.includes(lowerQuery)) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
    
    updateTableInfo();
}

function applyFilters() {
    const filters = {};
    const filterSelects = document.querySelectorAll('.table-filter-select');
    
    filterSelects.forEach(select => {
        const filterKey = select.getAttribute('data-filter');
        const filterValue = select.value;
        if (filterValue && filterValue !== 'all') {
            filters[filterKey] = filterValue;
        }
    });
    
    const rows = document.querySelectorAll('.nexus-table tbody tr');
    rows.forEach(row => {
        let showRow = true;
        
        Object.keys(filters).forEach(filterKey => {
            const cell = row.querySelector(`[data-${filterKey}]`);
            if (cell) {
                const cellValue = cell.getAttribute(`data-${filterKey}`);
                if (cellValue !== filters[filterKey]) {
                    showRow = false;
                }
            }
        });
        
        row.style.display = showRow ? '' : 'none';
    });
    
    updateTableInfo();
}

function updateTableInfo() {
    const visibleRows = document.querySelectorAll('.nexus-table tbody tr:not([style*="display: none"])');
    const totalRows = document.querySelectorAll('.nexus-table tbody tr');
    const tableInfo = document.querySelector('.table-info');
    
    if (tableInfo) {
        tableInfo.textContent = `Showing ${visibleRows.length} of ${totalRows.length} entries`;
    }
}

// Form Validation
function initializeFormValidation() {
    const forms = document.querySelectorAll('.service-form form');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!validateForm(this)) {
                e.preventDefault();
            }
        });
        
        // Real-time validation
        const inputs = form.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            input.addEventListener('blur', function() {
                validateField(this);
            });
        });
    });
}

function validateForm(form) {
    const inputs = form.querySelectorAll('input[required], select[required], textarea[required]');
    let isValid = true;
    
    inputs.forEach(input => {
        if (!validateField(input)) {
            isValid = false;
        }
    });
    
    return isValid;
}

function validateField(field) {
    const fieldGroup = field.closest('.service-form-group');
    const errorElement = fieldGroup.querySelector('.field-error');
    
    // Remove existing error
    if (errorElement) {
        errorElement.remove();
    }
    field.classList.remove('error');
    
    let isValid = true;
    let errorMessage = '';
    
    // Required field validation
    if (field.required && !field.value.trim()) {
        isValid = false;
        errorMessage = 'This field is required';
    }
    
    // Email validation
    if (field.type === 'email' && field.value) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(field.value)) {
            isValid = false;
            errorMessage = 'Please enter a valid email address';
        }
    }
    
    // Phone validation
    if (field.type === 'tel' && field.value) {
        const phoneRegex = /^[\+]?[\d\s\-\(\)]{10,}$/;
        if (!phoneRegex.test(field.value)) {
            isValid = false;
            errorMessage = 'Please enter a valid phone number';
        }
    }
    
    // Number validation
    if (field.type === 'number' && field.value) {
        if (isNaN(field.value) || field.value < 0) {
            isValid = false;
            errorMessage = 'Please enter a valid positive number';
        }
    }
    
    if (!isValid) {
        field.classList.add('error');
        const errorDiv = document.createElement('div');
        errorDiv.className = 'field-error';
        errorDiv.style.color = '#dc2626';
        errorDiv.style.fontSize = '0.75rem';
        errorDiv.style.marginTop = '0.25rem';
        errorDiv.textContent = errorMessage;
        fieldGroup.appendChild(errorDiv);
    }
    
    return isValid;
}

// Service Queue Functionality
function initializeServiceQueue() {
    // Queue item status updates
    const statusButtons = document.querySelectorAll('[data-update-status]');
    statusButtons.forEach(button => {
        button.addEventListener('click', function() {
            const serviceId = this.getAttribute('data-service-id');
            const newStatus = this.getAttribute('data-update-status');
            updateServiceStatus(serviceId, newStatus);
        });
    });
    
    // Auto-refresh queue every 30 seconds
    setInterval(refreshServiceQueue, 30000);
}

function updateServiceStatus(serviceId, newStatus) {
    if (!window.tenant_slug) {
        console.error('Tenant slug not available');
        return;
    }
    
    const button = document.querySelector(`[data-service-id="${serviceId}"][data-update-status="${newStatus}"]`);
    if (button) {
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Updating...';
    }
    
    fetch(`/business/${window.tenant_slug}/services/update-status/${serviceId}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            status: newStatus
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Update the UI
            const queueItem = document.querySelector(`[data-service-id="${serviceId}"]`).closest('.service-queue-item');
            if (queueItem) {
                const statusBadge = queueItem.querySelector('.service-queue-status');
                if (statusBadge) {
                    statusBadge.className = `service-queue-status ${newStatus}`;
                    statusBadge.textContent = newStatus.replace('-', ' ');
                }
            }
            
            // Show success message
            showNotification('Service status updated successfully', 'success');
        } else {
            showNotification('Failed to update service status', 'error');
        }
    })
    .catch(error => {
        console.error('Error updating service status:', error);
        showNotification('An error occurred while updating status', 'error');
    })
    .finally(() => {
        if (button) {
            button.disabled = false;
            button.innerHTML = button.getAttribute('data-original-text') || 'Update';
        }
    });
}

function refreshServiceQueue() {
    if (!window.tenant_slug) return;
    
    fetch(`/business/${window.tenant_slug}/services/queue/refresh/`)
    .then(response => response.json())
    .then(data => {
        if (data.html) {
            const queueContainer = document.querySelector('.service-queue');
            if (queueContainer) {
                queueContainer.innerHTML = data.html;
                // Reinitialize queue functionality
                initializeServiceQueue();
            }
        }
    })
    .catch(error => {
        console.error('Error refreshing service queue:', error);
    });
}

// Utility Functions
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} alert-dismissible`;
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    // Add to page
    const container = document.querySelector('.app-content-area') || document.body;
    container.insertBefore(notification, container.firstChild);
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        notification.remove();
    }, 5000);
}

function sortTable(sortKey, direction) {
    // Implement table sorting based on your data structure
    // This is a placeholder - you'll need to implement based on your backend
    console.log(`Sorting by ${sortKey} in ${direction} order`);
}

// Export functions for use in other scripts
window.ServicesJS = {
    updateServiceStatus,
    refreshServiceQueue,
    showNotification,
    validateForm,
    performSearch,
    applyFilters
};
