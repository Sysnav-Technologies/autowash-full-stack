/**
 * Modern Components JavaScript - Clean Version
 * Handles dropdowns, responsive interactions, and search functionality
 */

document.addEventListener('DOMContentLoaded', function() {
    initializeDropdowns();
    initializeResponsive();
    initializeSearch();
    restoreDropdownStates();
});

/**
 * Initialize dropdown functionality
 */
function initializeDropdowns() {
    // Handle mobile-specific dropdown behaviors
    const dropdowns = document.querySelectorAll('.dropdown');
    
    dropdowns.forEach(dropdown => {
        const toggle = dropdown.querySelector('.dropdown-toggle');
        const menu = dropdown.querySelector('.dropdown-menu');
        
        if (toggle && menu) {
            toggle.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                
                // Close other dropdowns
                dropdowns.forEach(other => {
                    if (other !== dropdown) {
                        other.classList.remove('show');
                    }
                });
                
                // Toggle current dropdown
                dropdown.classList.toggle('show');
            });
        }
    });
    
    // Close dropdowns when clicking outside
    document.addEventListener('click', function(e) {
        if (!e.target.closest('.dropdown')) {
            dropdowns.forEach(dropdown => {
                dropdown.classList.remove('show');
            });
        }
    });
}

/**
 * Initialize responsive functionality
 */
function initializeResponsive() {
    // Handle responsive navigation
    const navTogglers = document.querySelectorAll('.navbar-toggler');
    
    navTogglers.forEach(toggler => {
        toggler.addEventListener('click', function() {
            const target = document.querySelector(this.getAttribute('data-bs-target') || this.getAttribute('data-target'));
            if (target) {
                target.classList.toggle('show');
            }
        });
    });
    
    // Handle responsive tables
    const tables = document.querySelectorAll('.table-responsive');
    tables.forEach(tableContainer => {
        const table = tableContainer.querySelector('table');
        if (table) {
            // Add scroll indicators if needed
            updateScrollIndicators(tableContainer);
            
            tableContainer.addEventListener('scroll', function() {
                updateScrollIndicators(tableContainer);
            });
        }
    });
}

/**
 * Update scroll indicators for responsive tables
 */
function updateScrollIndicators(container) {
    const scrollLeft = container.scrollLeft;
    const scrollWidth = container.scrollWidth;
    const clientWidth = container.clientWidth;
    
    container.classList.toggle('scroll-left', scrollLeft > 0);
    container.classList.toggle('scroll-right', scrollLeft < scrollWidth - clientWidth);
}

/**
 * Initialize search functionality
 */
function initializeSearch() {
    const searchInputs = document.querySelectorAll('.search-input, [data-search]');
    
    searchInputs.forEach(input => {
        const targetSelector = input.getAttribute('data-search-target');
        if (targetSelector) {
            const debounceDelay = parseInt(input.getAttribute('data-search-delay')) || 300;
            
            let searchTimeout;
            input.addEventListener('input', function() {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    performSearch(this.value, targetSelector);
                }, debounceDelay);
            });
        }
    });
}

/**
 * Perform search on target elements
 */
function performSearch(query, targetSelector) {
    const targets = document.querySelectorAll(targetSelector);
    const searchTerm = query.toLowerCase().trim();
    
    targets.forEach(target => {
        const searchableText = target.textContent.toLowerCase();
        const matches = searchTerm === '' || searchableText.includes(searchTerm);
        
        target.style.display = matches ? '' : 'none';
        
        // Add search highlighting
        if (matches && searchTerm) {
            highlightSearchTerm(target, searchTerm);
        } else {
            removeSearchHighlight(target);
        }
    });
    
    // Update search results count
    updateSearchResultsCount(targets, query);
}

/**
 * Highlight search terms in target element
 */
function highlightSearchTerm(element, term) {
    removeSearchHighlight(element);
    
    const walker = document.createTreeWalker(
        element,
        NodeFilter.SHOW_TEXT,
        null,
        false
    );
    
    const textNodes = [];
    let node;
    
    while (node = walker.nextNode()) {
        textNodes.push(node);
    }
    
    textNodes.forEach(textNode => {
        const text = textNode.textContent;
        const regex = new RegExp(`(${term})`, 'gi');
        
        if (regex.test(text)) {
            const highlightedHTML = text.replace(regex, '<mark class="search-highlight">$1</mark>');
            const wrapper = document.createElement('span');
            wrapper.innerHTML = highlightedHTML;
            textNode.parentNode.replaceChild(wrapper, textNode);
        }
    });
}

/**
 * Remove search highlighting from element
 */
function removeSearchHighlight(element) {
    const highlights = element.querySelectorAll('.search-highlight');
    highlights.forEach(highlight => {
        const parent = highlight.parentNode;
        parent.replaceChild(document.createTextNode(highlight.textContent), highlight);
        parent.normalize();
    });
}

/**
 * Update search results count display
 */
function updateSearchResultsCount(targets, query) {
    const visibleCount = Array.from(targets).filter(target => target.style.display !== 'none').length;
    const totalCount = targets.length;
    
    const countElements = document.querySelectorAll('.search-results-count');
    countElements.forEach(element => {
        if (query.trim()) {
            element.textContent = `Showing ${visibleCount} of ${totalCount} results`;
            element.style.display = '';
        } else {
            element.style.display = 'none';
        }
    });
}

/**
 * Restore dropdown states from localStorage
 */
function restoreDropdownStates() {
    try {
        const savedStates = JSON.parse(localStorage.getItem('dropdown-states') || '{}');
        
        Object.keys(savedStates).forEach(dropdownId => {
            const dropdown = document.getElementById(dropdownId);
            if (dropdown && savedStates[dropdownId]) {
                dropdown.classList.add('show');
            }
        });
    } catch (e) {
        // Ignore localStorage errors
    }
}

/**
 * Save dropdown states to localStorage
 */
function saveDropdownStates() {
    try {
        const states = {};
        const dropdowns = document.querySelectorAll('.dropdown[id]');
        
        dropdowns.forEach(dropdown => {
            states[dropdown.id] = dropdown.classList.contains('show');
        });
        
        localStorage.setItem('dropdown-states', JSON.stringify(states));
    } catch (e) {
        // Ignore localStorage errors
    }
}

/**
 * Initialize tooltips (if Bootstrap is available)
 */
function initializeTooltips() {
    if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
}

/**
 * Initialize popovers (if Bootstrap is available)
 */
function initializePopovers() {
    if (typeof bootstrap !== 'undefined' && bootstrap.Popover) {
        const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
        popoverTriggerList.map(function (popoverTriggerEl) {
            return new bootstrap.Popover(popoverTriggerEl);
        });
    }
}

// Initialize tooltips and popovers when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    initializeTooltips();
    initializePopovers();
});

// Save dropdown states before page unload
window.addEventListener('beforeunload', saveDropdownStates);
