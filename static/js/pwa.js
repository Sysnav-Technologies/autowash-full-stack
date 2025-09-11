// AutoWash PWA Manager - Efficient and Lightweight
class PWAManager {
    constructor() {
        this.deferredPrompt = null;
        this.swRegistration = null;
        this.init();
    }

    init() {
        this.registerServiceWorker();
        this.setupInstallPrompt();
        this.setupOfflineHandling();
        this.showSplashScreen();
    }

    // Show branded splash screen
    showSplashScreen() {
        if (window.matchMedia('(display-mode: standalone)').matches) {
            const splash = document.createElement('div');
            splash.className = 'pwa-splash';
            splash.innerHTML = `
                <img src="/static/img/logo.png" alt="AutoWash" class="logo">
                <h3>AutoWash</h3>
                <p>Loading your dashboard...</p>
            `;
            document.body.appendChild(splash);
            
            setTimeout(() => {
                splash.classList.add('fade-out');
                setTimeout(() => splash.remove(), 300);
            }, 1500);
        }
    }

    // Service Worker Registration
    async registerServiceWorker() {
        if ('serviceWorker' in navigator) {
            try {
                this.swRegistration = await navigator.serviceWorker.register('/static/js/sw.js', {
                    scope: '/'
                });
                
                console.log('Service Worker registered successfully:', this.swRegistration);
                
                // Handle service worker updates
                this.swRegistration.addEventListener('updatefound', () => {
                    const newWorker = this.swRegistration.installing;
                    newWorker.addEventListener('statechange', () => {
                        if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                            this.showUpdateNotification();
                        }
                    });
                });

            } catch (error) {
                console.log('Service Worker registration failed:', error);
            }
        }
    }

    // Install Prompt Setup
    setupInstallPrompt() {
        window.addEventListener('beforeinstallprompt', (e) => {
            console.log('PWA install prompt triggered');
            e.preventDefault();
            this.deferredPrompt = e;
            this.showInstallButton();
        });

        // Handle successful installation
        window.addEventListener('appinstalled', (e) => {
            console.log('PWA installed successfully');
            this.isInstalled = true;
            this.hideInstallButton();
            this.showInstallSuccessMessage();
        });
    }

    // Show install button
    showInstallButton() {
        const installButton = document.getElementById('pwa-install-btn');
        if (installButton) {
            installButton.style.display = 'block';
            installButton.addEventListener('click', () => this.installPWA());
        } else {
            // Create install button if it doesn't exist
            this.createInstallButton();
        }
        
        // Also show a branded install banner
        this.showInstallBanner();
    }
    
    // Show branded install banner
    showInstallBanner() {
        // Don't show banner if already shown recently
        if (sessionStorage.getItem('pwa-banner-shown')) return;
        
        const banner = document.createElement('div');
        banner.id = 'pwa-install-banner';
        banner.className = 'alert alert-info alert-dismissible fade show position-fixed';
        banner.style.cssText = `
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 1055;
            max-width: 480px;
            box-shadow: var(--shadow-lg);
            border: none;
            background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
            border-radius: 12px;
        `;
        
        banner.innerHTML = `
            <div class="d-flex align-items-start">
                <img src="/static/img/logo.png" alt="AutoWash" style="width: 48px; height: 48px; margin-right: 12px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                <div class="flex-grow-1">
                    <div class="d-flex align-items-center justify-content-between mb-2">
                        <strong style="color: var(--autowash-primary); font-weight: 600;">📱 Install AutoWash App</strong>
                        <button type="button" class="btn-close" onclick="this.parentElement.parentElement.parentElement.remove(); sessionStorage.setItem('pwa-banner-shown', 'true')" style="font-size: 12px;"></button>
                    </div>
                    <small class="text-muted d-block mb-3">Get quick access, work offline, and receive notifications</small>
                    
                    <!-- Screenshot Preview -->
                    <div class="d-flex gap-2 mb-3" style="overflow-x: auto; padding: 2px;">
                        <img src="/static/img/screenshots/desktop-1.png" alt="Dashboard" 
                             style="width: 50px; height: 30px; border-radius: 4px; object-fit: cover; border: 1px solid #e2e8f0; opacity: 0.8; transition: all 0.2s;" 
                             onmouseover="this.style.opacity='1'; this.style.transform='scale(1.05)'" 
                             onmouseout="this.style.opacity='0.8'; this.style.transform='scale(1)'">
                        <img src="/static/img/screenshots/desktop-2.png" alt="Customers" 
                             style="width: 50px; height: 30px; border-radius: 4px; object-fit: cover; border: 1px solid #e2e8f0; opacity: 0.8; transition: all 0.2s;" 
                             onmouseover="this.style.opacity='1'; this.style.transform='scale(1.05)'" 
                             onmouseout="this.style.opacity='0.8'; this.style.transform='scale(1)'">
                        <img src="/static/img/screenshots/desktop-3.png" alt="Services" 
                             style="width: 50px; height: 30px; border-radius: 4px; object-fit: cover; border: 1px solid #e2e8f0; opacity: 0.8; transition: all 0.2s;" 
                             onmouseover="this.style.opacity='1'; this.style.transform='scale(1.05)'" 
                             onmouseout="this.style.opacity='0.8'; this.style.transform='scale(1)'">
                        <span style="font-size: 11px; color: #94a3b8; align-self: center; margin-left: 6px;">+more</span>
                    </div>
                    
                    <div class="d-flex gap-2">
                        <button type="button" class="btn btn-sm btn-primary" onclick="window.pwaManager.installPWA()" 
                                style="background: var(--autowash-primary); border: none; font-size: 13px; padding: 6px 14px; border-radius: 6px; font-weight: 500;">
                            <i class="fas fa-download me-1"></i>Install
                        </button>
                        <button type="button" class="btn btn-sm btn-outline-secondary" onclick="this.parentElement.parentElement.parentElement.remove(); sessionStorage.setItem('pwa-banner-shown', 'true')" 
                                style="font-size: 13px; padding: 6px 12px; border-radius: 6px;">
                            Later
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(banner);
        
        // Auto-remove after 20 seconds
        setTimeout(() => {
            if (banner.parentElement) {
                banner.remove();
                sessionStorage.setItem('pwa-banner-shown', 'true');
            }
        }, 20000);
    }

    // Create minimal install button
    createInstallButton() {
        const button = document.createElement('button');
        button.id = 'pwa-install-btn';
        button.className = 'btn btn-primary position-fixed';
        button.style.cssText = `
            bottom: 80px;
            right: 20px;
            z-index: 1000;
            border-radius: 50px;
            padding: 10px 16px;
            font-size: 14px;
            display: none;
        `;
        button.innerHTML = '<i class="fas fa-download me-1"></i>Install';
        
        document.body.appendChild(button);
        button.addEventListener('click', () => this.installPWA());
        
        // Auto-hide after 10 seconds if not clicked
        setTimeout(() => {
            if (button.parentElement) {
                button.style.display = 'none';
            }
        }, 10000);
    }

    // Install PWA
    async installPWA() {
        if (!this.deferredPrompt) return;

        this.deferredPrompt.prompt();
        const { outcome } = await this.deferredPrompt.userChoice;
        
        console.log(`User ${outcome} the install prompt`);
        this.deferredPrompt = null;
        
        if (outcome === 'accepted') {
            this.hideInstallButton();
        }
    }

    // Hide install button
    hideInstallButton() {
        const installButton = document.getElementById('pwa-install-btn');
        if (installButton) {
            installButton.style.display = 'none';
        }
    }

    // Show install success message
    showInstallSuccessMessage() {
        const toast = this.createToast(
            'AutoWash App Installed!',
            'AutoWash has been installed successfully. You can now access it from your home screen for faster, offline-capable management.',
            'success'
        );
        this.showToast(toast);
        
        // Hide install banner if it exists
        const banner = document.getElementById('pwa-install-banner');
        if (banner) banner.remove();
    }

    // Update Check and Notification
    setupUpdateCheck() {
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.addEventListener('controllerchange', () => {
                window.location.reload();
            });
        }
    }

    showUpdateNotification() {
        const toast = this.createToast(
            'Update Available!',
            'A new version of AutoWash is available. Refresh to update.',
            'info',
            [
                {
                    text: 'Update Now',
                    action: () => {
                        if (this.swRegistration && this.swRegistration.waiting) {
                            this.swRegistration.waiting.postMessage({ type: 'SKIP_WAITING' });
                        }
                    }
                },
                {
                    text: 'Later',
                    action: () => {}
                }
            ]
        );
        this.showToast(toast);
    }

    // Push Notifications Setup
    async setupNotifications() {
        if ('Notification' in window && 'serviceWorker' in navigator) {
            const permission = await Notification.requestPermission();
            
            if (permission === 'granted' && this.swRegistration) {
                try {
                    const subscription = await this.swRegistration.pushManager.subscribe({
                        userVisibleOnly: true,
                        applicationServerKey: this.urlBase64ToUint8Array(window.vapidPublicKey || '')
                    });
                    
                    // Send subscription to server
                    await this.sendSubscriptionToServer(subscription);
                } catch (error) {
                    console.log('Push subscription failed:', error);
                }
            }
        }
    }

    // Send push subscription to Django backend
    async sendSubscriptionToServer(subscription) {
        try {
            const response = await fetch('/api/push-subscription/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify(subscription)
            });
            
            if (response.ok) {
                console.log('Push subscription sent to server');
            }
        } catch (error) {
            console.log('Failed to send subscription to server:', error);
        }
    }

    // Offline Handling
    setupOfflineHandling() {
        window.addEventListener('online', () => {
            this.hideOfflineNotification();
            this.syncOfflineData();
        });

        window.addEventListener('offline', () => {
            this.showOfflineNotification();
        });

        // Check initial connection status
        if (!navigator.onLine) {
            this.showOfflineNotification();
        }
    }

    showOfflineNotification() {
        const notification = document.getElementById('offline-notification');
        if (notification) {
            notification.style.display = 'block';
        } else {
            this.createOfflineNotification();
        }
    }

    hideOfflineNotification() {
        const notification = document.getElementById('offline-notification');
        if (notification) {
            notification.style.display = 'none';
        }
    }

    createOfflineNotification() {
        const notification = document.createElement('div');
        notification.id = 'offline-notification';
        notification.className = 'alert alert-warning position-fixed';
        notification.style.cssText = `
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 9999;
            min-width: 300px;
            text-align: center;
        `;
        notification.innerHTML = `
            <i class="fas fa-wifi-slash me-2"></i>
            You're offline. Some features may be limited.
        `;
        
        document.body.appendChild(notification);
    }

    // Sync offline data when back online
    async syncOfflineData() {
        if ('serviceWorker' in navigator && this.swRegistration) {
            try {
                await this.swRegistration.sync.register('background-sync');
                console.log('Background sync registered');
            } catch (error) {
                console.log('Background sync registration failed:', error);
            }
        }
    }

    // Utility Functions
    urlBase64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding)
            .replace(/-/g, '+')
            .replace(/_/g, '/');

        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);

        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
    }

    getCSRFToken() {
        const token = document.querySelector('[name=csrfmiddlewaretoken]');
        return token ? token.value : '';
    }

    createToast(title, message, type = 'info', actions = []) {
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${type === 'success' ? 'success' : type === 'error' ? 'danger' : 'info'} border-0`;
        toast.setAttribute('role', 'alert');
        toast.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 9999;';
        
        let actionsHTML = '';
        if (actions.length > 0) {
            actionsHTML = actions.map(action => 
                `<button type="button" class="btn btn-sm btn-outline-light me-2" onclick="(${action.action.toString()})()">${action.text}</button>`
            ).join('');
        }
        
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    <strong>${title}</strong><br>
                    ${message}
                    ${actionsHTML ? `<div class="mt-2">${actionsHTML}</div>` : ''}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" onclick="this.parentElement.parentElement.remove()"></button>
            </div>
        `;
        
        return toast;
    }

    showToast(toast) {
        document.body.appendChild(toast);
        
        // Auto remove after 5 seconds if no actions
        if (!toast.querySelector('button[onclick*="action"]')) {
            setTimeout(() => {
                if (toast.parentElement) {
                    toast.remove();
                }
            }, 5000);
        }
    }
}

// Initialize PWA Manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.pwaManager = new PWAManager();
});

// Export for use in other scripts
window.PWAManager = PWAManager;
