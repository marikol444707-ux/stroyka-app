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

const unregisterStroykaServiceWorkers = async () => {
  try {
    if (!('serviceWorker' in navigator)) return;
    const registrations = await navigator.serviceWorker.getRegistrations();
    await Promise.all(registrations.map((registration) => registration.unregister().catch(() => false)));
  } catch (_e) {}
};

const reloadWithFreshAssets = async () => {
  try {
    const lastReload = Number(sessionStorage.getItem(ASSET_RELOAD_STORAGE_KEY) || 0);
    if (lastReload && Date.now() - lastReload < ASSET_RELOAD_THROTTLE_MS) return;
    sessionStorage.setItem(ASSET_RELOAD_STORAGE_KEY, String(Date.now()));
  } catch (_e) {}

  await clearStroykaCaches();
  await unregisterStroykaServiceWorkers();
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
    // Рабочая ERP важнее офлайн-кэша: старый service worker уже приводил к
    // смешиванию index.html и JS-чанков разных сборок после деплоя.
    unregisterStroykaServiceWorkers().then(clearStroykaCaches).catch(() => {});
  });
}
