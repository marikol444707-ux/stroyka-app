const isLocalHost = typeof window !== 'undefined'
  && ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname);

const configuredApiUrl = (process.env.REACT_APP_API_URL || '').replace(/\/$/, '');

export const API = configuredApiUrl || (isLocalHost ? 'http://localhost:8001' : '');

const clientErrorLoggingEnabled = process.env.REACT_APP_CLIENT_ERROR_LOGGING === 'true'
  || (!isLocalHost && process.env.REACT_APP_CLIENT_ERROR_LOGGING !== 'false');

const clipClientErrorText = (value, limit = 1000) => {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  return text.length > limit ? text.slice(0, limit - 1) + '…' : text;
};

const sendClientError = (payload) => {
  if (!clientErrorLoggingEnabled || typeof window === 'undefined') return;
  const body = JSON.stringify({
    type: clipClientErrorText(payload.type || payload.name || 'ClientError', 120),
    message: clipClientErrorText(payload.message, 500),
    stack: clipClientErrorText(payload.stack, 1200),
    path: clipClientErrorText(window.location.pathname + window.location.search, 255),
  });
  const url = API + '/client-errors';
  try {
    if (navigator.sendBeacon) {
      const ok = navigator.sendBeacon(url, new Blob([body], { type: 'application/json' }));
      if (ok) return;
    }
  } catch (_e) {}
  try {
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
      keepalive: true,
    }).catch(() => {});
  } catch (_e) {}
};

export const installClientErrorLogging = () => {
  if (typeof window === 'undefined' || window.__stroykaClientErrorLoggingInstalled) return;
  window.addEventListener('error', (event) => {
    const err = event.error || {};
    sendClientError({
      type: err.name || 'WindowError',
      message: err.message || event.message,
      stack: err.stack || '',
    });
  });
  window.addEventListener('unhandledrejection', (event) => {
    const reason = event.reason || {};
    sendClientError({
      type: reason.name || 'UnhandledRejection',
      message: reason.message || String(reason),
      stack: reason.stack || '',
    });
  });
  window.__stroykaClientErrorLoggingInstalled = true;
};

export const installAuthFetch = () => {
  if (typeof window === 'undefined' || window.__stroykaAuthFetchInstalled) return;
  const nativeFetch = window.fetch.bind(window);
  window.fetch = async (input, init = {}) => {
    const token = localStorage.getItem('authToken');
    if (!token) return nativeFetch(input, init);
    const headers = new Headers(init.headers || {});
    if (!headers.has('Authorization')) headers.set('Authorization', 'Bearer ' + token);
    const response = await nativeFetch(input, {...init, headers});
    // Токен истёк или стал недействителен — сервер отвечает 401.
    // Чистим сессию и возвращаем на экран входа, чтобы приложение не показывало
    // пустые данные (нули, «Проектов нет»), как будто всё удалено.
    if (response.status === 401 && !window.__stroykaSessionExpiring) {
      window.__stroykaSessionExpiring = true;
      try {
        localStorage.removeItem('authToken');
        localStorage.removeItem('user');
        sessionStorage.setItem('authExpiredNotice', '1');
      } catch (e) {}
      window.location.reload();
    }
    return response;
  };
  window.__stroykaAuthFetchInstalled = true;
};
