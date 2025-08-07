// Tablet Base JavaScript
class TabletBase {
    constructor() {
        this.isOnline = navigator.onLine;
        this.currentTime = null;
        this.timeInterval = null;
    }
    
    static init() {
        const instance = new TabletBase();
        instance.initializeTime();
        instance.initializeConnectionStatus();
        instance.initializeToasts();
        instance.initializeLoadingOverlay();
        return instance;
    }
    
    // Initialize current time display
    initializeTime() {
        this.currentTime = document.getElementById('currentTime');
        if (this.currentTime) {
            this.updateTime();
            this.timeInterval = setInterval(() => this.updateTime(), 1000);
        }
    }
    
    updateTime() {
        const now = new Date();
        const timeString = now.toLocaleTimeString('en-US', {
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        if (this.currentTime) {
            this.currentTime.textContent = timeString;
        }
    }
    
    // Initialize connection status
    initializeConnectionStatus() {
        const statusElement = document.getElementById('connectionStatus');
        
        if (statusElement) {
            this.updateConnectionStatus(statusElement);
            
            // Listen for online/offline events
            window.addEventListener('online', () => {
                this.isOnline = true;
                this.updateConnectionStatus(statusElement);
                this.showToast('Connection restored', 'success');
            });
            
            window.addEventListener('offline', () => {
                this.isOnline = false;
                this.updateConnectionStatus(statusElement);
                this.showToast('Connection lost', 'warning');
            });
        }
    }
    
    updateConnectionStatus(element) {
        if (this.isOnline) {
            element.innerHTML = '<i class="fas fa-wifi text-success"></i> Online';
            element.className = 'connection-status online';
        } else {
            element.innerHTML = '<i class="fas fa-wifi text-danger"></i> Offline';
            element.className = 'connection-status offline';
        }
    }
    
    // Initialize toast notifications
    initializeToasts() {
        this.toastElement = document.getElementById('toastNotification');
        this.toastMessage = document.getElementById('toastMessage');
        
        if (this.toastElement) {
            this.toast = new bootstrap.Toast(this.toastElement, {
                autohide: true,
                delay: 4000
            });
        }
    }
    
    // Show toast notification
    showToast(message, type = 'info') {
        if (!this.toast) return;
        
        // Update toast content
        this.toastMessage.textContent = message;
        
        // Update toast type
        this.toastElement.className = `toast toast-${type}`;
        
        // Update icon based on type
        const iconElement = this.toastElement.querySelector('.toast-icon');
        if (iconElement) {
            iconElement.className = `toast-icon fas ${this.getToastIcon(type)} me-2`;
        }
        
        // Show toast
        this.toast.show();
    }
    
    getToastIcon(type) {
        const icons = {
            success: 'fa-check-circle',
            warning: 'fa-exclamation-triangle',
            error: 'fa-exclamation-circle',
            danger: 'fa-exclamation-circle',
            info: 'fa-info-circle'
        };
        return icons[type] || icons.info;
    }
    
    // Initialize loading overlay
    initializeLoadingOverlay() {
        this.loadingOverlay = document.getElementById('loadingOverlay');
    }
    
    showLoading(message = 'Loading...') {
        if (this.loadingOverlay) {
            const messageElement = this.loadingOverlay.querySelector('p');
            if (messageElement) {
                messageElement.textContent = message;
            }
            this.loadingOverlay.classList.remove('hidden');
        }
    }
    
    hideLoading() {
        if (this.loadingOverlay) {
            this.loadingOverlay.classList.add('hidden');
        }
    }
    
    // Utility methods
    static showToast(message, type = 'info') {
        if (window.tabletBase) {
            window.tabletBase.showToast(message, type);
        }
    }
    
    static showLoading(message) {
        if (window.tabletBase) {
            window.tabletBase.showLoading(message);
        }
    }
    
    static hideLoading() {
        if (window.tabletBase) {
            window.tabletBase.hideLoading();
        }
    }
    
    // CSRF token utility
    static getCsrfToken() {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
        return csrfToken ? csrfToken.value : null;
    }
    
    // API request helper
    static async apiRequest(url, options = {}) {
        const defaultOptions = {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': TabletBase.getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest',
            },
        };
        
        const finalOptions = { ...defaultOptions, ...options };
        
        try {
            const response = await fetch(url, finalOptions);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('API Request Error:', error);
            throw error;
        }
    }
    
    // Cleanup
    destroy() {
        if (this.timeInterval) {
            clearInterval(this.timeInterval);
        }
    }
}

// Global access
window.TabletBase = TabletBase;

// Automatically hide loading on page load
window.addEventListener('load', () => {
    setTimeout(() => {
        TabletBase.hideLoading();
    }, 500);
});

// Prevent zoom on double tap for better tablet experience
let lastTouchEnd = 0;
document.addEventListener('touchend', function (event) {
    const now = (new Date()).getTime();
    if (now - lastTouchEnd <= 300) {
        event.preventDefault();
    }
    lastTouchEnd = now;
}, false);

// Enhanced error handling for tablet
window.addEventListener('error', function(e) {
    console.error('Application Error:', e.error);
    TabletBase.showToast('An unexpected error occurred', 'error');
});

window.addEventListener('unhandledrejection', function(e) {
    console.error('Unhandled Promise Rejection:', e.reason);
    TabletBase.showToast('An unexpected error occurred', 'error');
});

// Service Worker registration for offline support (optional)
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/js/sw.js')
            .then((registration) => {
                console.log('SW registered: ', registration);
            })
            .catch((registrationError) => {
                console.log('SW registration failed: ', registrationError);
            });
    });
}
