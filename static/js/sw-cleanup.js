/**
 * Service Worker Cleanup Script
 * Aggressively unregisters any existing service workers to prevent cache conflicts
 */

(function() {
    'use strict';
    
    console.log('Starting service worker cleanup...');
    
    // Unregister all service workers immediately
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.getRegistrations().then(function(registrations) {
            if (registrations.length > 0) {
                console.log(`Found ${registrations.length} service worker(s) to unregister`);
                registrations.forEach(function(registration) {
                    console.log('Unregistering service worker:', registration.scope);
                    registration.unregister().then(function(success) {
                        if (success) {
                            console.log('✓ Service worker unregistered successfully');
                        } else {
                            console.log('✗ Service worker unregistration failed');
                        }
                    });
                });
            } else {
                console.log('✓ No service workers found');
            }
        }).catch(function(error) {
            console.log('Error getting service worker registrations:', error);
        });

        // Force reload any active service worker
        if (navigator.serviceWorker.controller) {
            console.log('Found active service worker, posting skip waiting message');
            navigator.serviceWorker.controller.postMessage({action: 'skipWaiting'});
        }

        // Listen for service worker changes
        navigator.serviceWorker.addEventListener('controllerchange', function() {
            console.log('Service worker controller changed, reloading page...');
            // Small delay to let cleanup complete
            setTimeout(() => window.location.reload(), 1000);
        });

        // Clear all AutoWash caches aggressively
        if ('caches' in window) {
            caches.keys().then(function(cacheNames) {
                const cachesToDelete = cacheNames.filter(name => 
                    name.includes('autowash') || 
                    name.includes('static') || 
                    name.includes('dynamic') ||
                    name.includes('v1.0')
                );
                
                if (cachesToDelete.length > 0) {
                    console.log(`Deleting ${cachesToDelete.length} cache(s):`, cachesToDelete);
                    return Promise.all(
                        cachesToDelete.map(cacheName => {
                            console.log('Deleting cache:', cacheName);
                            return caches.delete(cacheName);
                        })
                    );
                } else {
                    console.log('✓ No AutoWash caches found');
                }
            }).then(function() {
                console.log('✓ Cache cleanup completed');
            }).catch(function(error) {
                console.log('Error clearing caches:', error);
            });
        }
    }

    // Clear localStorage items related to service worker and PWA
    try {
        const itemsToRemove = [];
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key && (
                key.includes('sw-') || 
                key.includes('service-worker') || 
                key.includes('autowash-cache') ||
                key.includes('pwa-') ||
                key.includes('cache-')
            )) {
                itemsToRemove.push(key);
            }
        }
        if (itemsToRemove.length > 0) {
            itemsToRemove.forEach(key => {
                localStorage.removeItem(key);
                console.log('Removed localStorage item:', key);
            });
            console.log(`✓ Cleaned ${itemsToRemove.length} localStorage items`);
        } else {
            console.log('✓ No SW-related localStorage items found');
        }
    } catch (error) {
        console.log('Error cleaning localStorage:', error);
    }

    // Clear sessionStorage too
    try {
        const sessionItemsToRemove = [];
        for (let i = 0; i < sessionStorage.length; i++) {
            const key = sessionStorage.key(i);
            if (key && (
                key.includes('sw-') || 
                key.includes('service-worker') || 
                key.includes('autowash-cache')
            )) {
                sessionItemsToRemove.push(key);
            }
        }
        if (sessionItemsToRemove.length > 0) {
            sessionItemsToRemove.forEach(key => {
                sessionStorage.removeItem(key);
                console.log('Removed sessionStorage item:', key);
            });
            console.log(`✓ Cleaned ${sessionItemsToRemove.length} sessionStorage items`);
        }
    } catch (error) {
        console.log('Error cleaning sessionStorage:', error);
    }

    console.log('Service worker cleanup completed');
})();