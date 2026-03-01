/**
 * FlightAlertPro Service Worker
 *
 * Strategy:
 *  - App shell (HTML/JS/CSS/assets): Cache-first, with network fallback.
 *  - /api/metadata/* endpoints: Stale-while-revalidate (serve cache, refresh in background).
 *  - All other requests: Network-first.
 */

const CACHE_NAME = 'flightalertpro-v1';
const METADATA_CACHE = 'flightalertpro-metadata-v1';

// App-shell assets to pre-cache on install.
// Vite generates hashed filenames; we cache the root document and let runtime
// caching handle JS/CSS bundles as they are requested.
const APP_SHELL = ['/'];

// ── Install ────────────────────────────────────────────────────────────────────
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

// ── Activate ───────────────────────────────────────────────────────────────────
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k !== CACHE_NAME && k !== METADATA_CACHE)
          .map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// ── Fetch ──────────────────────────────────────────────────────────────────────
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Only handle GET requests
  if (request.method !== 'GET') return;

  // Metadata API: stale-while-revalidate
  if (url.pathname.startsWith('/api/metadata/')) {
    event.respondWith(staleWhileRevalidate(request, METADATA_CACHE));
    return;
  }

  // App shell / static assets: cache-first with network fallback
  if (
    url.pathname === '/' ||
    url.pathname.endsWith('.js') ||
    url.pathname.endsWith('.css') ||
    url.pathname.endsWith('.png') ||
    url.pathname.endsWith('.svg') ||
    url.pathname.endsWith('.ico') ||
    url.pathname.endsWith('.webmanifest') ||
    url.pathname === '/manifest.json'
  ) {
    event.respondWith(cacheFirstWithFallback(request));
    return;
  }

  // Everything else: network-first
  event.respondWith(networkFirst(request));
});

// ── Push notifications ─────────────────────────────────────────────────────────
self.addEventListener('push', (event) => {
  let data = { title: 'FlightAlertPro', body: 'Price alert triggered!' };
  try {
    data = event.data ? event.data.json() : data;
  } catch (_) {
    data.body = event.data ? event.data.text() : data.body;
  }

  const options = {
    body: data.body || data.message || '',
    icon: '/icons/icon-192.png',
    badge: '/icons/icon-192.png',
    tag: data.tag || 'flight-alert',
    data: { url: data.url || '/' },
    requireInteraction: false,
  };

  event.waitUntil(self.registration.showNotification(data.title, options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = event.notification.data?.url || '/';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((cs) => {
      const existing = cs.find((c) => c.url.includes(target));
      if (existing) return existing.focus();
      return clients.openWindow(target);
    })
  );
});

// ── Cache helpers ──────────────────────────────────────────────────────────────

async function cacheFirstWithFallback(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch (_) {
    // Return cached index.html as offline fallback for navigation requests
    if (request.mode === 'navigate') {
      const fallback = await caches.match('/');
      if (fallback) return fallback;
    }
    return new Response('Offline', { status: 503, statusText: 'Service Unavailable' });
  }
}

async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);

  const networkFetch = fetch(request).then((response) => {
    if (response.ok) cache.put(request, response.clone());
    return response;
  }).catch(() => null);

  if (cached) return cached;
  // No cache hit – wait for the network (may be null on failure)
  const fresh = await networkFetch;
  return fresh || new Response('Offline', { status: 503, statusText: 'Service Unavailable' });
}

async function networkFirst(request) {
  try {
    const response = await fetch(request);
    return response;
  } catch (_) {
    const cached = await caches.match(request);
    return cached || new Response('Offline', { status: 503, statusText: 'Service Unavailable' });
  }
}
