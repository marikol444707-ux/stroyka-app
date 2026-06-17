export function registerServiceWorker() {
  if (process.env.NODE_ENV !== 'production') return;
  if (typeof window === 'undefined' || !('serviceWorker' in navigator)) return;

  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(error => {
      // PWA не должна ломать вход в систему, если браузер запретил service worker.
      console.warn('Service worker registration failed:', error);
    });
  });
}
