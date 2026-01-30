const CACHE_NAME = 'ai-dict-cache-v2';
const ASSETS_TO_CACHE = [
    '/',
    '/static/dictionary/logo.svg',
    '/static/dictionary/favicon.svg',
    '/static/dictionary/moon.svg',
    '/static/dictionary/icons8-sun.svg'
];

// Install Event
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            return cache.addAll(ASSETS_TO_CACHE);
        })
    );
    self.skipWaiting();
});

// Activate Event (Cleanup old caches)
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cache => {
                    if (cache !== CACHE_NAME) {
                        return caches.delete(cache);
                    }
                })
            );
        })
    );
    self.clients.claim();
});

// Fetch Event (Offline Support)
// Fetch Event (Offline Support)
self.addEventListener('fetch', event => {
    // Network-first / Network-only for non-GET requests (POST, PUT, DELETE)
    // This fixes Logout (POST) and AI API (POST) issues
    if (event.request.method !== 'GET') {
        return;
    }

    // Optional: Bypass cache for API and Admin to ensure fresh data
    const url = new URL(event.request.url);
    if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/admin/')) {
        return;
    }

    event.respondWith(
        caches.match(event.request).then(response => {
            return response || fetch(event.request);
        })
    );
});
