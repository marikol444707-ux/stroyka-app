const ASSET_RELOAD_STORAGE_KEY = 'stroykaAssetReloadAt';
const ASSET_RELOAD_THROTTLE_MS = 15000;

const clearStroykaCaches = async () => {
  try {
    if ('caches' in window) {
      const keys = await caches.keys();
      await Promise.all(keys.filter((key) => key.startsWith('stroyka-')).map((key) => caches.delete(key)));
    }
  } catch (_e) {}
};

const reloadWithFreshAssets = async () => {
  try {
    const lastReload = Number(sessionStorage.getItem(ASSET_RELOAD_STORAGE_KEY) || 0);
    if (lastReload && Date.now() - lastReload < ASSET_RELOAD_THROTTLE_MS) return;
    sessionStorage.setItem(ASSET_RELOAD_STORAGE_KEY, String(Date.now()));
  } catch (_e) {}

  await clearStroykaCaches();
  window.location.reload();
};

const isStaticAssetUrl = (value) => {
  const url = String(value || '');
  return /\/static\/(js|css)\//.test(url);
};

const installAssetFailureRecovery = () => {
  if (typeof window === 'undefined' || window.__stroykaAssetFailureRecoveryInstalled) return;

  window.addEventListener('error', (event) => {
    const target = event.target;
    const assetUrl = target && (target.src || target.href);
    if (isStaticAssetUrl(assetUrl)) reloadWithFreshAssets();
  }, true);

  window.addEventListener('unhandledrejection', (event) => {
    const reason = event.reason || {};
    const message = String(reason.message || reason || '');
    if (/ChunkLoadError|Loading chunk|dynamically imported module|module script failed/i.test(message)) {
      reloadWithFreshAssets();
    }
  });

  window.__stroykaAssetFailureRecoveryInstalled = true;
};

export function registerServiceWorker() {
  installAssetFailureRecovery();

  if (process.env.NODE_ENV !== 'production') return;
  if (typeof window === 'undefined' || !('serviceWorker' in navigator)) return;

  window.addEventListener('load', () => {
    let refreshing = false;
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      if (refreshing) return;
      refreshing = true;
      window.location.reload();
    });

    navigator.serviceWorker.register('/sw.js').catch(error => {
      // PWA не должна ломать вход в систему, если браузер запретил service worker.
      console.warn('Service worker registration failed:', error);
    });
  });
}
