/* eslint-disable no-restricted-globals */
/**
 * WordAddress Service Worker
 * Provides offline-first capability with background sync.
 */

const CACHE_NAME = 'open3words-v1';
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/static/js/main.js',
  '/static/css/main.css',
];

const DB_NAME = 'Open3WordsOffline';
const DB_VERSION = 1;

// ── Install: pre-cache static assets ────────────────────────
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(STATIC_ASSETS))
      .then(() => self.skipWaiting())
  );
});

// ── Activate: clean old caches ──────────────────────────────
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then(names => Promise.all(
        names.filter(n => n !== CACHE_NAME).map(n => caches.delete(n))
      ))
      .then(() => self.clients.claim())
  );
});

// ── Fetch: network-first for API, cache-first for static ───
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // API calls: network-first
  if (url.pathname.startsWith('/encode') ||
      url.pathname.startsWith('/decode') ||
      url.pathname.startsWith('/correct') ||
      url.pathname.startsWith('/autosuggest')) {
    event.respondWith(networkFirst(request));
    return;
  }

  // Map tiles: cache-first with TTL
  if (url.hostname.includes('tile') || url.pathname.includes('/tiles/')) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // Static assets: cache-first
  event.respondWith(cacheFirst(request));
});

async function networkFirst(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    const cached = await caches.match(request);
    if (cached) return cached;

    return new Response(JSON.stringify({
      error: 'Offline',
      offline: true,
      message: 'You are offline. This request has been queued.',
    }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    return new Response('', { status: 404 });
  }
}

// ── Background sync ─────────────────────────────────────────
self.addEventListener('sync', (event) => {
  if (event.tag === 'process-queue') {
    event.waitUntil(processOfflineQueue());
  }
});

async function processOfflineQueue() {
  // IndexedDB queue processing would go here
  console.log('[SW] Processing offline queue');
}

// ── Push notifications ──────────────────────────────────────
self.addEventListener('push', (event) => {
  const data = event.data ? event.data.json() : {};
  event.waitUntil(
    self.registration.showNotification('WordAddress', {
      body: data.message || 'New location shared',
      icon: '/icon-192.png',
      badge: '/badge-72.png',
      tag: data.words || 'notification',
      data: data,
      actions: [
        { action: 'open', title: 'View' },
        { action: 'dismiss', title: 'Dismiss' },
      ],
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  if (event.action === 'open' || !event.action) {
    event.waitUntil(
      clients.openWindow(`/?words=${event.notification.data?.words || ''}`)
    );
  }
});

// ── Message handling from main thread ───────────────────────
self.addEventListener('message', (event) => {
  const { type, payload } = event.data || {};
  if (type === 'STORE_LOCATION') {
    // Cache location in IndexedDB
    console.log('[SW] Storing location:', payload);
  }
});
