/**
 * GitHub-Style Network Handler
 * Lightweight client-side network management without server middleware overhead
 */

class AutoWashNetworkManager {
    constructor() {
        this.isOnline = navigator.onLine;
        this.requestQueue = new Map();
        this.retryAttempts = new Map();
        this.duplicateGuard = new Map();
        
        // Configuration
        this.config = {
            duplicateWindow: 2000, // 2 seconds
            retryDelay: 1000,      // 1 second  
            maxRetries: 3,
            timeout: 30000         // 30 seconds
        };
        
        this.init();
    }
    
    init() {
        // Listen for online/offline events
        window.addEventListener('online', () => {
            this.isOnline = true;
            this.processQueuedRequests();
        });
        
        window.addEventListener('offline', () => {
            this.isOnline = false;
        });
        
        // Intercept form submissions for duplicate prevention
        document.addEventListener('submit', (e) => this.handleFormSubmit(e));
        
        // Intercept AJAX requests
        this.interceptFetch();
        
        // Cleanup old entries periodically
        setInterval(() => this.cleanup(), 60000); // Every minute
    }
    
    handleFormSubmit(event) {
        const form = event.target;
        const formData = new FormData(form);
        
        // Create unique signature for this form submission
        const signature = this.createFormSignature(form, formData);
        
        // Check for duplicate submission
        if (this.isDuplicateSubmission(signature)) {
            event.preventDefault();
            this.showMessage('Please wait before submitting again', 'warning');
            return false;
        }
        
        // Mark this submission
        this.markSubmission(signature);
        
        // Add loading state
        this.setFormLoading(form, true);
        
        // If offline, queue the request
        if (!this.isOnline) {
            event.preventDefault();
            this.queueRequest('form', {
                form: form,
                formData: formData,
                signature: signature
            });
            this.showMessage('You are offline. Request will be sent when connection is restored.', 'info');
            return false;
        }
    }
    
    createFormSignature(form, formData) {
        const path = form.action || window.location.pathname;
        const method = (form.method || 'POST').toUpperCase();
        
        // Create a hash of non-CSRF form data
        const dataEntries = [];
        for (let [key, value] of formData.entries()) {
            if (key !== 'csrfmiddlewaretoken') {
                dataEntries.push(`${key}:${value}`);
            }
        }
        
        return `${method}:${path}:${dataEntries.sort().join('|')}`;
    }
    
    isDuplicateSubmission(signature) {
        const lastSubmission = this.duplicateGuard.get(signature);
        if (lastSubmission) {
            const timeDiff = Date.now() - lastSubmission;
            return timeDiff < this.config.duplicateWindow;
        }
        return false;
    }
    
    markSubmission(signature) {
        this.duplicateGuard.set(signature, Date.now());
    }
    
    interceptFetch() {
        const originalFetch = window.fetch;
        
        window.fetch = async (...args) => {
            // If offline, queue the request
            if (!this.isOnline) {
                return this.queueRequest('fetch', args);
            }
            
            try {
                const response = await originalFetch(...args);
                
                // Handle common network errors gracefully
                if (!response.ok) {
                    this.handleNetworkError(response.status, response.statusText);
                }
                
                return response;
            } catch (error) {
                // Network error occurred
                if (error.name === 'TypeError' && error.message.includes('fetch')) {
                    this.handleNetworkError(0, 'Network Error');
                    throw error;
                }
                throw error;
            }
        };
    }
    
    queueRequest(type, data) {
        const requestId = this.generateRequestId();
        this.requestQueue.set(requestId, {
            type: type,
            data: data,
            timestamp: Date.now(),
            attempts: 0
        });
        
        return new Promise((resolve, reject) => {
            // Store resolve/reject for later execution
            const request = this.requestQueue.get(requestId);
            request.resolve = resolve;
            request.reject = reject;
            this.requestQueue.set(requestId, request);
        });
    }
    
    async processQueuedRequests() {
        if (this.requestQueue.size === 0) return;
        
        this.showMessage('Connection restored. Processing queued requests...', 'success');
        
        for (let [requestId, request] of this.requestQueue.entries()) {
            try {
                if (request.type === 'form') {
                    await this.resubmitForm(request.data);
                } else if (request.type === 'fetch') {
                    const response = await fetch(...request.data);
                    request.resolve(response);
                }
                
                this.requestQueue.delete(requestId);
            } catch (error) {
                request.attempts = (request.attempts || 0) + 1;
                if (request.attempts >= this.config.maxRetries) {
                    this.requestQueue.delete(requestId);
                    request.reject && request.reject(error);
                }
            }
        }
    }
    
    async resubmitForm(data) {
        const { form, formData } = data;
        
        try {
            const response = await fetch(form.action || window.location.pathname, {
                method: form.method || 'POST',
                body: formData
            });
            
            if (response.ok) {
                // Handle successful submission
                if (response.redirected) {
                    window.location.href = response.url;
                } else {
                    // Reload page or handle response
                    window.location.reload();
                }
            }
        } catch (error) {
            throw error;
        } finally {
            this.setFormLoading(form, false);
        }
    }
    
    setFormLoading(form, loading) {
        const submitButtons = form.querySelectorAll('button[type="submit"], input[type="submit"]');
        
        submitButtons.forEach(button => {
            if (loading) {
                button.disabled = true;
                button.dataset.originalText = button.textContent;
                button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
            } else {
                button.disabled = false;
                button.textContent = button.dataset.originalText || 'Submit';
            }
        });
    }
    
    handleNetworkError(status, statusText) {
        if (status === 429) {
            this.showMessage('Too many requests. Please wait a moment.', 'warning');
        } else if (status >= 500) {
            this.showMessage('Server error. Please try again later.', 'error');
        } else if (status === 0) {
            this.showMessage('Network connection lost. Please check your internet connection.', 'error');
        }
    }
    
    showMessage(message, type = 'info') {
        // Create a toast notification
        const toast = document.createElement('div');
        toast.className = `alert alert-${this.mapMessageType(type)} alert-dismissible fade show network-toast`;
        toast.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        // Add to page
        const container = document.getElementById('network-messages') || document.body;
        container.appendChild(toast);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (toast.parentNode) {
                toast.remove();
            }
        }, 5000);
    }
    
    mapMessageType(type) {
        const typeMap = {
            'info': 'info',
            'success': 'success', 
            'warning': 'warning',
            'error': 'danger'
        };
        return typeMap[type] || 'info';
    }
    
    cleanup() {
        const now = Date.now();
        const cutoff = now - (this.config.duplicateWindow * 5); // Keep 5x the window
        
        // Clean duplicate guard
        for (let [key, timestamp] of this.duplicateGuard.entries()) {
            if (timestamp < cutoff) {
                this.duplicateGuard.delete(key);
            }
        }
        
        // Clean old queued requests
        for (let [key, request] of this.requestQueue.entries()) {
            if (request.timestamp < cutoff) {
                this.requestQueue.delete(key);
            }
        }
    }
    
    generateRequestId() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2);
    }
    
    // Public API methods
    getNetworkStatus() {
        return {
            online: this.isOnline,
            queuedRequests: this.requestQueue.size,
            duplicateGuardSize: this.duplicateGuard.size
        };
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.AutoWashNetwork = new AutoWashNetworkManager();
});

// Add CSS for toast notifications
const style = document.createElement('style');
style.textContent = `
.network-toast {
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 9999;
    min-width: 300px;
    max-width: 400px;
}
`;
document.head.appendChild(style);