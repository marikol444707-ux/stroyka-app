self.addEventListener('install', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(key => key.startsWith('stroyka-')).map(key => caches.delete(key))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(key => key.startsWith('stroyka-')).map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});
