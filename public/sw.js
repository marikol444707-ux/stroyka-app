const CACHE_NAME = 'stroyka-shell-v3';
const STATIC_CACHE_LIMIT = 90;
const SHELL_URLS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/favicon.ico',
  '/logo192.png',
  '/logo512.png',
];

const API_PREFIXES = [
  '/login',
  '/logout',
  '/register',
  '/projects',
  '/users',
  '/staff',
  '/estimates',
  '/materials',
  '/warehouse',
  '/supply',
  '/expenses',
  '/own-expenses',
  '/project-payments',
  '/ai-',
  '/messages',
  '/upload',
  '/health',
  '/system-status',
];

const STATIC_PATHS = ['/static/', '/favicon.ico', '/logo192.png', '/logo512.png', '/manifest.json'];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(SHELL_URLS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

function isApiRequest(url) {
  return API_PREFIXES.some(prefix => url.pathname === prefix || url.pathname.startsWith(prefix + '/') || url.pathname.startsWith(prefix));
}

function isStaticRequest(url) {
  return STATIC_PATHS.some(path => url.pathname === path || url.pathname.startsWith(path));
}

function trimCache(cache) {
  return cache.keys().then(keys => {
    if (keys.length <= STATIC_CACHE_LIMIT) return undefined;
    return Promise.all(keys.slice(0, keys.length - STATIC_CACHE_LIMIT).map(key => cache.delete(key)));
  });
}

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (isApiRequest(url)) return;

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then(response => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put('/index.html', copy));
          return response;
        })
        .catch(() => caches.match('/index.html'))
    );
    return;
  }

  if (isStaticRequest(url)) {
    event.respondWith(
      caches.match(request)
        .then(cached => cached || fetch(request).then(response => {
          if (!response || !response.ok) return response;
          const copy = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(request, copy).then(() => trimCache(cache)));
          return response;
        }))
    );
  }
});
