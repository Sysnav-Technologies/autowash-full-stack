/**
 * AutoWash Unified Loading & Network Manager
 * GitHub/Spotify-style robust connection handling with unified loading states
 */

class AutoWashManager {
    constructor() {
        this.isOnline = navigator.onLine;
        this.isLoading = false;
        this.activeRequests = new Map();
        this.requestQueue = new Map();
        this.duplicateGuard = new Map();
        this.loadingElements = new Set();
        this.debugMode = localStorage.getItem('autowash-debug') === 'true';
        
        // Configuration
        this.config = {
            duplicateWindow: 2000,     // 2 seconds
            connectionTimeout: 10000,  // 10 seconds
            slowThreshold: 3000,       // 3 seconds
            retryAttempts: 3,
            retryDelay: 1000,
            healthCheckInterval: 30000 // 30 seconds
        };
        
        this.init();
    }
    
    init() {
        this.setupNetworkListeners();
        this.setupRequestInterception();
        this.setupFormHandling();
        this.setupGlobalLoading();
        this.startHealthCheck();
        this.cleanupLegacySystems();
    }
    
    cleanupLegacySystems() {
        // Remove duplicate loading indicators and scripts
        const duplicateLoaders = document.querySelectorAll('.loading-indicator:not(.aw-loader)');
        duplicateLoaders.forEach(loader => {
            if (!loader.classList.contains('aw-loader')) {
                loader.remove();
            }
        });
        
        // Disable other network managers if they exist
        if (window.AutoWashNetwork) {
            window.AutoWashNetwork = null;
        }
        if (window.connectionStateManager) {
            window.connectionStateManager = null;
        }
    }
    
    setupNetworkListeners() {
        window.addEventListener('online', () => {
            this.isOnline = true;
            this.showConnectionStatus('Connection restored', 'success');
            this.processQueuedRequests();
        });
        
        window.addEventListener('offline', () => {
            this.isOnline = false;
            this.showConnectionStatus('Connection lost. Working offline...', 'warning');
        });
        
        // Monitor page loading with better detection
        if (document.readyState === 'loading') {
            this.setGlobalLoading(true, 'Loading page...');
        }
        
        document.addEventListener('readystatechange', () => {
            if (document.readyState === 'complete') {
                // Give extra time for all resources to load
                setTimeout(() => {
                    // Only hide loading if no other requests are active
                    if (this.activeRequests.size === 0) {
                        this.setGlobalLoading(false);
                    }
                }, 500);
            }
        });
        
        // Additional safeguard - ensure loading is cleared after page is fully loaded
        window.addEventListener('load', () => {
            setTimeout(() => {
                if (this.activeRequests.size === 0) {
                    this.setGlobalLoading(false);
                }
            }, 1000);
        });
        
        window.addEventListener('beforeunload', () => {
            this.setGlobalLoading(true, 'Navigating...');
        });
        
        // Handle page visibility changes to fix idle page loading bug
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                // User returned to page - check if loading should be cleared
                this.handlePageVisible();
            } else {
                // Page hidden - set up cleanup timer
                this.scheduleHiddenPageCleanup();
            }
        });
        
        // Handle window focus/blur for additional cleanup
        window.addEventListener('focus', () => {
            this.handlePageVisible();
        });
        
        window.addEventListener('blur', () => {
            // Clear any stuck loading states when page loses focus
            this.clearStuckLoadingStates();
        });
        
        // Additional cleanup for dashboard idle issue
        window.addEventListener('pageshow', () => {
            // Page shown from cache - aggressive cleanup
            setTimeout(() => this.handlePageVisible(), 100);
        });
        
        window.addEventListener('pagehide', () => {
            // Page being hidden - prevent stuck states
            this.scheduleHiddenPageCleanup();
        });
        
        // Handle app switching scenario specifically
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                // When returning from another app, give it a moment then cleanup aggressively
                setTimeout(() => {
                    if (this.debugMode) {
                        console.log('AutoWash Debug: App switching cleanup check');
                    }
                    this.performAppSwitchCleanup();
                }, 1000);
            }
        });
    }
    
    setupRequestInterception() {
        // Intercept fetch requests
        const originalFetch = window.fetch;
        window.fetch = (...args) => {
            const requestId = this.generateId();
            
            // Handle offline requests
            if (!this.isOnline) {
                return this.queueRequest('fetch', args, requestId);
            }
            
            // Start tracking request
            this.startRequest(requestId, 'Fetching data...');
            
            const request = originalFetch(...args)
                .then(response => {
                    this.endRequest(requestId);
                    
                    if (!response.ok && response.status >= 500) {
                        this.handleNetworkError(response.status, response.statusText);
                    }
                    
                    return response;
                })
                .catch(error => {
                    this.endRequest(requestId);
                    this.handleNetworkError(0, error.message);
                    throw error;
                });
            
            // Add timeout handling with proper cleanup
            const timeoutPromise = new Promise((_, reject) => {
                setTimeout(() => {
                    this.endRequest(requestId); // Ensure request is ended on timeout
                    reject(new Error('Request timeout'));
                }, this.config.connectionTimeout);
            });
            
            return Promise.race([request, timeoutPromise])
                .catch(error => {
                    // Ensure request is always ended even if race condition occurs
                    this.endRequest(requestId);
                    throw error;
                });
        };
        
        // Intercept jQuery AJAX if available
        if (typeof $ !== 'undefined' && $.ajaxSetup) {
            let jqueryRequestId = null;
            
            $(document).ajaxStart(() => {
                jqueryRequestId = this.generateId();
                this.startRequest(jqueryRequestId, 'Loading...');
            });
            
            $(document).ajaxComplete(() => {
                if (jqueryRequestId) {
                    this.endRequest(jqueryRequestId);
                    jqueryRequestId = null;
                }
            });
            
            $(document).ajaxError((event, xhr, settings, error) => {
                if (jqueryRequestId) {
                    this.endRequest(jqueryRequestId);
                    jqueryRequestId = null;
                }
                this.handleNetworkError(xhr.status, error);
            });
        }
    }
    
    setupFormHandling() {
        document.addEventListener('submit', (event) => {
            const form = event.target;
            const signature = this.createFormSignature(form);
            
            // Prevent duplicate submissions
            if (this.isDuplicateSubmission(signature)) {
                event.preventDefault();
                this.showMessage('Please wait before submitting again', 'warning');
                return false;
            }
            
            // Mark submission
            this.markSubmission(signature);
            
            // Handle offline submissions
            if (!this.isOnline) {
                event.preventDefault();
                this.queueRequest('form', { form, signature });
                this.showMessage('You are offline. Form will be submitted when connection is restored.', 'info');
                return false;
            }
            
            // Add loading state to form
            this.setFormLoading(form, true);
            
            // Start request tracking
            const requestId = this.generateId();
            this.startRequest(requestId, 'Submitting form...');
            
            // Auto-cleanup after timeout
            setTimeout(() => {
                this.setFormLoading(form, false);
                this.endRequest(requestId);
            }, this.config.connectionTimeout);
        });
    }
    
    setupGlobalLoading() {
        // Create unified loading overlay
        if (!document.getElementById('aw-global-loader')) {
            const loader = document.createElement('div');
            loader.id = 'aw-global-loader';
            loader.className = 'aw-loading-overlay';
            loader.innerHTML = `
                <div class="aw-loader-content">
                    <div class="aw-spinner-container">
                        <div class="aw-spinner">
                            <img src="/static/img/logo.png" alt="AutoWash" class="aw-logo">
                        </div>
                    </div>
                    <div class="aw-loader-text" id="aw-loader-text">Loading...</div>
                </div>
            `;
            document.body.appendChild(loader);
        }
        
        // Add unified CSS
        if (!document.getElementById('aw-loading-styles')) {
            const styles = document.createElement('style');
            styles.id = 'aw-loading-styles';
            styles.textContent = `
                .aw-loading-overlay {
                    position: fixed;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: rgba(255, 255, 255, 0.95);
                    backdrop-filter: blur(4px);
                    z-index: 9999;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    opacity: 0;
                    visibility: hidden;
                    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                }
                
                .aw-loading-overlay.active {
                    opacity: 1;
                    visibility: visible;
                }
                
                .aw-loader-content {
                    text-align: center;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    gap: 1rem;
                }
                
                .aw-spinner-container {
                    position: relative;
                    width: 80px;
                    height: 80px;
                }
                
                .aw-spinner {
                    width: 80px;
                    height: 80px;
                    border: 4px solid rgba(37, 99, 235, 0.1);
                    border-top: 4px solid #2563eb;
                    border-radius: 50%;
                    animation: aw-spin 1s linear infinite;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    background: rgba(255, 255, 255, 0.9);
                    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.15);
                }
                
                .aw-logo {
                    width: 32px;
                    height: 32px;
                    object-fit: contain;
                }
                
                .aw-loader-text {
                    font-size: 0.875rem;
                    font-weight: 500;
                    color: #6b7280;
                    animation: aw-pulse 1.5s ease-in-out infinite;
                }
                
                @keyframes aw-spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
                
                @keyframes aw-pulse {
                    0%, 100% { opacity: 0.7; }
                    50% { opacity: 1; }
                }
                
                /* Form loading states */
                .aw-form-loading {
                    position: relative;
                    opacity: 0.7;
                    pointer-events: none;
                }
                
                .aw-form-loading .btn[type="submit"] {
                    position: relative;
                }
                
                .aw-form-loading .btn[type="submit"]::after {
                    content: '';
                    position: absolute;
                    top: 50%;
                    left: 50%;
                    width: 16px;
                    height: 16px;
                    margin: -8px 0 0 -8px;
                    border: 2px solid transparent;
                    border-top: 2px solid currentColor;
                    border-radius: 50%;
                    animation: aw-spin 1s linear infinite;
                }
                
                /* Connection status */
                .aw-connection-status {
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    z-index: 9998;
                    max-width: 400px;
                    border-radius: 8px;
                    padding: 12px 16px;
                    font-size: 14px;
                    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                    transform: translateX(100px);
                    opacity: 0;
                    transition: all 0.3s ease;
                }
                
                .aw-connection-status.show {
                    transform: translateX(0);
                    opacity: 1;
                }
                
                .aw-connection-status.success {
                    background: #10b981;
                    color: white;
                }
                
                .aw-connection-status.warning {
                    background: #f59e0b;
                    color: white;
                }
                
                .aw-connection-status.error {
                    background: #ef4444;
                    color: white;
                }
                
                /* Mobile optimization */
                @media (max-width: 768px) {
                    .aw-spinner-container, .aw-spinner {
                        width: 60px;
                        height: 60px;
                        /* Slower animation on mobile - less aggressive */
                        animation-duration: 2s;
                    }
                    
                    .aw-logo {
                        width: 24px;
                        height: 24px;
                    }
                    
                    .aw-loading-text {
                        /* Slower pulse animation on mobile */
                        animation-duration: 2.5s;
                    }
                    
                    .aw-connection-status {
                        top: 10px;
                        right: 10px;
                        left: 10px;
                        max-width: none;
                    }
                }
            `;
            document.head.appendChild(styles);
        }
    }
    
    startHealthCheck() {
        const checkHealth = () => {
            if (this.isOnline) {
                const startTime = Date.now();
                
                fetch('/api/health/', { 
                    method: 'GET',
                    cache: 'no-cache'
                })
                .then(response => {
                    const responseTime = Date.now() - startTime;
                    
                    if (responseTime > this.config.slowThreshold) {
                        this.showConnectionStatus('Slow connection detected', 'warning');
                    }
                    
                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status}`);
                    }
                })
                .catch(error => {
                    console.warn('Health check failed:', error);
                    this.showConnectionStatus('Connection issues detected', 'error');
                });
            }
        };
        
        // Initial check
        setTimeout(checkHealth, 5000);
        
        // Periodic checks with cleanup
        setInterval(() => {
            checkHealth();
            this.performPeriodicCleanup();
        }, this.config.healthCheckInterval);
    }
    
    // Public API Methods
    setGlobalLoading(loading, text = 'Loading...') {
        const loader = document.getElementById('aw-global-loader');
        const textEl = document.getElementById('aw-loader-text');
        
        if (loader) {
            if (loading) {
                loader.classList.add('active');
                if (textEl) textEl.textContent = text;
                document.body.style.overflow = 'hidden';
            } else {
                loader.classList.remove('active');
                document.body.style.overflow = '';
            }
        }
        
        this.isLoading = loading;
    }
    
    startRequest(requestId, message = 'Loading...') {
        this.activeRequests.set(requestId, {
            startTime: Date.now(),
            message
        });
        
        if (this.activeRequests.size === 1) {
            this.setGlobalLoading(true, message);
        }
    }
    
    endRequest(requestId) {
        this.activeRequests.delete(requestId);
        
        if (this.activeRequests.size === 0) {
            this.setGlobalLoading(false);
        }
    }
    
    setFormLoading(form, loading) {
        if (loading) {
            form.classList.add('aw-form-loading');
        } else {
            form.classList.remove('aw-form-loading');
        }
        
        const submitButtons = form.querySelectorAll('button[type="submit"], input[type="submit"]');
        submitButtons.forEach(button => {
            button.disabled = loading;
            if (loading && !button.dataset.originalText) {
                button.dataset.originalText = button.textContent;
                button.textContent = 'Processing...';
            } else if (!loading && button.dataset.originalText) {
                button.textContent = button.dataset.originalText;
                delete button.dataset.originalText;
            }
        });
    }
    
    setButtonLoading(button, loading, text = null) {
        if (typeof button === 'string') {
            button = document.querySelector(button);
        }
        
        if (!button) return;
        
        if (loading) {
            button.disabled = true;
            button.classList.add('aw-loading');
            
            if (!button.dataset.originalContent) {
                button.dataset.originalContent = button.innerHTML;
            }
            
            const loadingText = text || 'Loading...';
            button.innerHTML = `<i class="fas fa-spinner fa-spin me-2"></i>${loadingText}`;
        } else {
            button.disabled = false;
            button.classList.remove('aw-loading');
            
            if (button.dataset.originalContent) {
                button.innerHTML = button.dataset.originalContent;
                delete button.dataset.originalContent;
            }
        }
    }
    
    setElementLoading(element, loading, text = null) {
        if (typeof element === 'string') {
            element = document.querySelector(element);
        }
        
        if (!element) return;
        
        if (loading) {
            element.classList.add('aw-loading');
            
            if (!element.dataset.originalContent) {
                element.dataset.originalContent = element.innerHTML;
            }
            
            const loadingText = text || 'Loading...';
            element.innerHTML = `<div class="text-center p-3"><i class="fas fa-spinner fa-spin"></i> ${loadingText}</div>`;
        } else {
            element.classList.remove('aw-loading');
            
            if (element.dataset.originalContent) {
                element.innerHTML = element.dataset.originalContent;
                delete element.dataset.originalContent;
            }
        }
    }
    
    showConnectionStatus(message, type = 'info') {
        // Remove existing status
        const existing = document.querySelector('.aw-connection-status');
        if (existing) existing.remove();
        
        const status = document.createElement('div');
        status.className = `aw-connection-status ${type}`;
        status.textContent = message;
        
        document.body.appendChild(status);
        
        // Animate in
        setTimeout(() => status.classList.add('show'), 100);
        
        // Auto-remove
        setTimeout(() => {
            status.classList.remove('show');
            setTimeout(() => status.remove(), 300);
        }, 5000);
    }
    
    showMessage(message, type = 'info') {
        this.showConnectionStatus(message, type);
    }
    
    // Helper methods
    createFormSignature(form) {
        const formData = new FormData(form);
        const path = form.action || window.location.pathname;
        const method = (form.method || 'POST').toUpperCase();
        
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
        return lastSubmission && (Date.now() - lastSubmission) < this.config.duplicateWindow;
    }
    
    markSubmission(signature) {
        this.duplicateGuard.set(signature, Date.now());
    }
    
    queueRequest(type, data, requestId = null) {
        const id = requestId || this.generateId();
        this.requestQueue.set(id, {
            type,
            data,
            timestamp: Date.now(),
            attempts: 0
        });
        
        return new Promise((resolve, reject) => {
            const request = this.requestQueue.get(id);
            request.resolve = resolve;
            request.reject = reject;
            this.requestQueue.set(id, request);
        });
    }
    
    async processQueuedRequests() {
        for (let [id, request] of this.requestQueue.entries()) {
            try {
                if (request.type === 'fetch') {
                    const response = await fetch(...request.data);
                    request.resolve(response);
                } else if (request.type === 'form') {
                    await this.resubmitForm(request.data);
                }
                
                this.requestQueue.delete(id);
            } catch (error) {
                request.attempts++;
                if (request.attempts >= this.config.retryAttempts) {
                    this.requestQueue.delete(id);
                    request.reject && request.reject(error);
                }
            }
        }
    }
    
    async resubmitForm(data) {
        const { form } = data;
        const formData = new FormData(form);
        
        const response = await fetch(form.action || window.location.pathname, {
            method: form.method || 'POST',
            body: formData
        });
        
        if (response.ok) {
            if (response.redirected) {
                window.location.href = response.url;
            } else {
                window.location.reload();
            }
        }
    }
    
    handleNetworkError(status, message) {
        if (status === 429) {
            this.showConnectionStatus('Too many requests. Please wait...', 'warning');
        } else if (status >= 500) {
            this.showConnectionStatus('Server error. Please try again.', 'error');
        } else if (status === 0) {
            this.showConnectionStatus('Network error. Check your connection.', 'error');
        }
    }
    
    generateId() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2);
    }
    
    // Handle page visibility changes and idle state
    handlePageVisible() {
        if (this.debugMode) {
            console.log('AutoWash Debug: Page became visible, checking for stuck loading states', {
                activeRequests: this.activeRequests.size,
                isLoading: this.isLoading,
                requests: Array.from(this.activeRequests.entries()),
                timestamp: new Date().toISOString()
            });
        }
        
        // User returned to page - aggressive cleanup of stuck states
        setTimeout(() => {
            // Check for stuck fetch requests older than 5 seconds
            const now = Date.now();
            const stuckThreshold = 5000; // 5 seconds
            
            for (let [id, request] of this.activeRequests.entries()) {
                if (now - request.startTime > stuckThreshold) {
                    if (this.debugMode) {
                        console.log('AutoWash Debug: Clearing stuck fetch request:', id, request);
                    }
                    this.endRequest(id);
                }
            }
            
            // If no active requests but loading is still shown, clear it
            if (this.activeRequests.size === 0 && this.isLoading) {
                if (this.debugMode) {
                    console.log('AutoWash Debug: Clearing stuck loading state on page return');
                }
                this.setGlobalLoading(false);
            }
            
            // Clear any stuck button loading states
            this.clearStuckButtonStates();
            
            // Clear any stuck element loading states
            this.clearStuckElementStates();
        }, 100);
    }
    
    clearStuckLoadingStates() {
        // Clear loading states when page loses focus to prevent stuck states
        setTimeout(() => {
            if (this.activeRequests.size === 0) {
                this.setGlobalLoading(false);
            }
        }, 1000);
    }
    
    scheduleHiddenPageCleanup() {
        // When page is hidden, set up cleanup after a delay
        setTimeout(() => {
            if (document.hidden && this.activeRequests.size === 0) {
                if (this.debugMode) {
                    console.log('AutoWash Debug: Cleaning up loading state while page hidden');
                }
                this.setGlobalLoading(false);
            }
        }, 5000); // 5 seconds after page is hidden
    }
    
    performAppSwitchCleanup() {
        // Aggressive cleanup when switching back from another app
        const now = Date.now();
        let clearedCount = 0;
        
        // Clear all requests older than 3 seconds when returning from app switch
        for (let [id, request] of this.activeRequests.entries()) {
            if (now - request.startTime > 3000) { // 3 seconds is very aggressive
                if (this.debugMode) {
                    console.log('AutoWash Debug: App switch cleanup removing request:', id, request);
                }
                this.endRequest(id);
                clearedCount++;
            }
        }
        
        // Force clear loading if no requests remain
        if (this.activeRequests.size === 0 && this.isLoading) {
            if (this.debugMode) {
                console.log('AutoWash Debug: App switch cleanup force clearing loading state');
            }
            this.setGlobalLoading(false);
        }
        
        if (clearedCount > 0 && this.debugMode) {
            console.log(`AutoWash Debug: App switch cleanup cleared ${clearedCount} stuck requests`);
        }
    }
    
    clearStuckButtonStates() {
        // Find all buttons that might be stuck in loading state
        const loadingButtons = document.querySelectorAll('button.aw-loading');
        loadingButtons.forEach(button => {
            // Only clear if no ongoing requests for this button
            if (!button.closest('form')?.classList.contains('aw-form-loading')) {
                this.setButtonLoading(button, false);
            }
        });
    }
    
    clearStuckElementStates() {
        // Find all elements that might be stuck in loading state
        const loadingElements = document.querySelectorAll('.aw-loading:not(button):not(form)');
        loadingElements.forEach(element => {
            // Clear loading state if element has original content to restore
            if (element.dataset.originalContent) {
                this.setElementLoading(element, false);
            }
        });
    }
    
    // Enhanced cleanup method to be called periodically
    performPeriodicCleanup() {
        // Clean up old duplicate guard entries (older than 5 minutes)
        const now = Date.now();
        const fiveMinutes = 5 * 60 * 1000;
        
        for (let [signature, timestamp] of this.duplicateGuard.entries()) {
            if (now - timestamp > fiveMinutes) {
                this.duplicateGuard.delete(signature);
            }
        }
        
        // Clean up stale requests - more aggressive for fetch requests
        const fifteenSeconds = 15 * 1000; // Reduced from 30 to 15 seconds
        for (let [id, request] of this.activeRequests.entries()) {
            const age = now - request.startTime;
            
            // Be more aggressive with "Fetching data" requests
            const isStuck = (request.message === 'Fetching data...' && age > 10000) || // 10 seconds for fetch
                           (age > fifteenSeconds); // 15 seconds for others
            
            if (isStuck) {
                if (this.debugMode) {
                    console.warn('AutoWash: Cleaning up stale request:', id, request, `age: ${age}ms`);
                }
                this.endRequest(id);
            }
        }
        
        // Dashboard idle fix - if loading is shown but no active requests and page is visible
        if (this.isLoading && this.activeRequests.size === 0 && !document.hidden) {
            if (this.debugMode) {
                console.log('AutoWash Debug: Periodic cleanup clearing stuck loading state');
            }
            this.setGlobalLoading(false);
        }
    }
    
    // Public API
    getStatus() {
        return {
            online: this.isOnline,
            loading: this.isLoading,
            activeRequests: this.activeRequests.size,
            queuedRequests: this.requestQueue.size
        };
    }
}

// Initialize immediately if DOM is ready, otherwise wait
function initializeAutoWash() {
    if (window.AutoWash) return; // Already initialized
    
    window.AutoWash = new AutoWashManager();
    
    // Global convenience methods
    window.showLoading = (text) => window.AutoWash.setGlobalLoading(true, text);
    window.hideLoading = () => window.AutoWash.setGlobalLoading(false);
    window.showMessage = (message, type) => window.AutoWash.showMessage(message, type);
    window.setButtonLoading = (button, loading, text) => window.AutoWash.setButtonLoading(button, loading, text);
    window.setElementLoading = (element, loading, text) => window.AutoWash.setElementLoading(element, loading, text);
    
    // Debug and cleanup methods
    window.clearStuckLoading = () => {
        console.log('Manually clearing stuck loading states...');
        console.log('Active requests before cleanup:', window.AutoWash.activeRequests.size);
        window.AutoWash.setGlobalLoading(false);
        window.AutoWash.clearStuckButtonStates();
        window.AutoWash.clearStuckElementStates();
        window.AutoWash.activeRequests.clear();
        console.log('Loading states cleared! Active requests:', window.AutoWash.activeRequests.size);
    };
    
    window.autoWashDebug = (enable = true) => {
        localStorage.setItem('autowash-debug', enable.toString());
        window.AutoWash.debugMode = enable;
        console.log(`AutoWash debug mode ${enable ? 'enabled' : 'disabled'}`);
    };
    
    // Force cleanup of any stuck loading states after initialization
    setTimeout(() => {
        if (window.AutoWash && window.AutoWash.activeRequests.size === 0) {
            window.AutoWash.setGlobalLoading(false);
        }
    }, 2000);
}

// Initialize based on document state
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeAutoWash);
} else {
    // DOM is already ready
    initializeAutoWash();
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AutoWashManager;
}