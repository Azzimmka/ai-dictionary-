const CACHE_NAME = 'ai-dict-cache-v3';
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
self.addEventListener('fetch', event => {
    // 1. POST/PUT etc -> Network only
    if (event.request.method !== 'GET') return;

    // 2. API/Admin -> Network only
    const url = new URL(event.request.url);
    if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/admin/')) {
        return;
    }

    // 3. Navigation (HTML) -> Network First (Fresh content), fallback to Cache
    if (event.request.mode === 'navigate') {
        event.respondWith(
            fetch(event.request)
                .then(response => {
                    // Update cache for next time
                    const resClone = response.clone();
                    caches.open(CACHE_NAME).then(cache => {
                        cache.put(event.request, resClone);
                    });
                    return response;
                })
                .catch(() => {
                    // Offline? Return cached version
                    return caches.match(event.request) || caches.match('/');
                })
        );
        return;
    }

    // 4. Static Assets -> Cache First (Speed), fallback to Network
    event.respondWith(
        caches.match(event.request).then(response => {
            return response || fetch(event.request);
        })
    );
});
