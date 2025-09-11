const CACHE_NAME = 'autowash-v1.0.0';
const STATIC_CACHE = 'autowash-static-v1.0.0';
const DYNAMIC_CACHE = 'autowash-dynamic-v1.0.0';

// Essential files for AutoWash functionality
const STATIC_FILES = [
  '/',
  '/static/css/main.css',
  '/static/css/sidebar.css',
  '/static/css/auth.css',
  '/static/css/components.css',
  '/static/css/pwa.css',
  '/static/js/main.js',
  '/static/js/sidebar.js',
  '/static/js/pwa.js',
  '/static/img/logo.png',
  '/static/img/autowash.svg',
  '/static/img/icons/icon-192x192.png',
  '/static/img/icons/icon-512x512.png',
  // Only cache essential external resources
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css'
];

// Core AutoWash routes to cache
const DYNAMIC_ROUTES = [
  '/dashboard/',
  '/customers/',
  '/services/',
  '/inventory/',
  '/reports/',
  '/employees/',
  '/expenses/',
  '/payments/'
];

// Install event - cache static files
self.addEventListener('install', event => {
  console.log('Service Worker: Installing...');
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then(cache => {
        console.log('Service Worker: Caching static files');
        return cache.addAll(STATIC_FILES);
      })
      .catch(err => {
        console.log('Service Worker: Cache failed', err);
      })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
  console.log('Service Worker: Activating...');
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cache => {
          if (cache !== STATIC_CACHE && cache !== DYNAMIC_CACHE) {
            console.log('Service Worker: Clearing old cache', cache);
            return caches.delete(cache);
          }
        })
      );
    })
  );
});

// Fetch event - serve cached content when offline
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);
  
  // Skip non-GET requests
  if (request.method !== 'GET') {
    return;
  }
  
  // Skip chrome-extension and other non-http(s) requests
  if (!request.url.startsWith('http')) {
    return;
  }

  event.respondWith(
    caches.match(request)
      .then(response => {
        // Return cached version or fetch from network
        if (response) {
          return response;
        }
        
        return fetch(request)
          .then(fetchResponse => {
            // Check if valid response
            if (!fetchResponse || fetchResponse.status !== 200 || fetchResponse.type !== 'basic') {
              return fetchResponse;
            }
            
            // Clone response for caching
            const responseClone = fetchResponse.clone();
            
            // Cache dynamic content
            if (shouldCache(request.url)) {
              caches.open(DYNAMIC_CACHE)
                .then(cache => {
                  cache.put(request, responseClone);
                });
            }
            
            return fetchResponse;
          })
          .catch(() => {
            // Return offline page for navigation requests
            if (request.destination === 'document') {
              return caches.match('/offline/');
            }
            
            // Return fallback icon for image requests
            if (request.destination === 'image') {
              return caches.match('/static/img/icons/icon-192x192.png');
            }
          });
      })
  );
});

// Background sync for form submissions
self.addEventListener('sync', event => {
  console.log('Service Worker: Background sync', event.tag);
  
  if (event.tag === 'background-sync') {
    event.waitUntil(syncData());
  }
});

// Push notifications
self.addEventListener('push', event => {
  console.log('Service Worker: Push received');
  
  const options = {
    body: event.data ? event.data.text() : 'New notification from AutoWash',
    icon: '/static/img/icons/icon-192x192.png',
    badge: '/static/img/icons/icon-72x72.png',
    vibrate: [200, 100, 200],
    data: {
      dateOfArrival: Date.now(),
      primaryKey: 1
    },
    actions: [
      {
        action: 'explore',
        title: 'View Details',
        icon: '/static/img/icons/icon-96x96.png'
      },
      {
        action: 'close',
        title: 'Close',
        icon: '/static/img/icons/icon-96x96.png'
      }
    ]
  };
  
  event.waitUntil(
    self.registration.showNotification('AutoWash', options)
  );
});

// Notification click handling
self.addEventListener('notificationclick', event => {
  console.log('Service Worker: Notification click received');
  
  event.notification.close();
  
  if (event.action === 'explore') {
    event.waitUntil(
      clients.openWindow('/dashboard/')
    );
  }
});

// Helper functions
function shouldCache(url) {
  // Cache API responses and dynamic routes
  return url.includes('/api/') || 
         DYNAMIC_ROUTES.some(route => url.includes(route)) ||
         url.includes('/static/');
}

async function syncData() {
  // Implement background sync for offline form submissions
  try {
    const cache = await caches.open('offline-forms');
    const requests = await cache.keys();
    
    for (const request of requests) {
      try {
        const response = await fetch(request);
        if (response.ok) {
          await cache.delete(request);
        }
      } catch (error) {
        console.log('Sync failed for:', request.url);
      }
    }
  } catch (error) {
    console.log('Background sync failed:', error);
  }
}

// Message handling for cache updates
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  
  if (event.data && event.data.type === 'UPDATE_CACHE') {
    event.waitUntil(updateCache());
  }
});

async function updateCache() {
  const cache = await caches.open(STATIC_CACHE);
  await cache.addAll(STATIC_FILES);
}
