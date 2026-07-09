import { withStoredCompanyContextHeaders } from './features/company-context/companyContextStorage';

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

export const sendClientError = (payload) => {
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
  const authPublicPaths = [
    '/login',
    '/login/2fa/setup-confirm',
    '/login/2fa/verify',
    '/register',
    '/password-reset-request',
    '/password-reset',
    '/password-reset/request',
    '/password-reset/confirm',
  ];
  const csrfMethods = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);
  const csrfHeaderName = 'X-CSRF-Token';
  let csrfToken = '';
  let csrfTokenPromise = null;
  const getRequestPath = (input) => {
    try {
      const url = typeof input === 'string' ? input : input?.url;
      if (!url) return '';
      return new URL(url, window.location.origin).pathname;
    } catch (_e) {
      return '';
    }
  };
  const isAuthPublicPath = (path) => authPublicPaths.some(publicPath => path === publicPath || path.startsWith(publicPath + '/'));
  const getRequestMethod = (input, init = {}) => {
    const method = init.method || (typeof Request !== 'undefined' && input instanceof Request ? input.method : '') || 'GET';
    return String(method).toUpperCase();
  };
  const getStoredAuthToken = () => {
    try {
      return localStorage.getItem('authToken') || '';
    } catch (_e) {
      return '';
    }
  };
  const hasAuthorizationHeader = (input, init) => {
    const headers = new Headers(init.headers || {});
    if (headers.has('Authorization')) return true;
    try {
      if (typeof Request !== 'undefined' && input instanceof Request) {
        return input.headers.has('Authorization');
      }
    } catch (_e) {}
    return false;
  };
  const hasCsrfHeader = (input, init) => {
    const headers = new Headers(init.headers || {});
    if (headers.has(csrfHeaderName)) return true;
    try {
      if (typeof Request !== 'undefined' && input instanceof Request) {
        return input.headers.has(csrfHeaderName);
      }
    } catch (_e) {}
    return false;
  };
  const fetchCsrfToken = async () => {
    if (csrfToken) return csrfToken;
    if (!csrfTokenPromise) {
      csrfTokenPromise = nativeFetch(API + '/csrf-token', { credentials: 'include' })
        .then(async (response) => {
          if (!response.ok) return '';
          const data = await response.json().catch(() => ({}));
          csrfToken = typeof data.csrfToken === 'string' ? data.csrfToken : '';
          return csrfToken;
        })
        .catch(() => '')
        .finally(() => {
          csrfTokenPromise = null;
        });
    }
    return csrfTokenPromise;
  };
  const withCsrfToken = (init, token) => {
    if (!token) return init;
    const headers = new Headers(init.headers || {});
    if (!headers.has(csrfHeaderName)) headers.set(csrfHeaderName, token);
    return {...init, headers};
  };
  const withBearerFallback = (init, token) => {
    const headers = new Headers(init.headers || {});
    if (!headers.has('Authorization')) headers.set('Authorization', 'Bearer ' + token);
    return {...init, headers};
  };
  const expireFrontendSession = (response) => {
    // Токен/сессия истекли или стали недействительны — сервер отвечает 401.
    // Чистим сессию и возвращаем на экран входа, чтобы приложение не показывало
    // пустые данные (нули, «Проектов нет»), как будто всё удалено.
    if (!window.__stroykaSessionExpiring) {
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
  window.fetch = async (input, init = {}) => {
    const path = getRequestPath(input);
    const isPublicAuthRequest = isAuthPublicPath(path);
    if (isPublicAuthRequest) return nativeFetch(input, {...init, credentials: init.credentials || 'include'});
    const method = getRequestMethod(input, init);
    let nextInit = withStoredCompanyContextHeaders({...init, credentials: init.credentials || 'include'});
    if (csrfMethods.has(method) && !hasCsrfHeader(input, init)) {
      nextInit = withCsrfToken(nextInit, await fetchCsrfToken());
    }
    const response = await nativeFetch(input, nextInit);
    if (response.status !== 401) return response;

    const token = getStoredAuthToken();
    if (token && !hasAuthorizationHeader(input, init)) {
      const fallbackResponse = await nativeFetch(input, withBearerFallback(nextInit, token));
      if (fallbackResponse.status !== 401) return fallbackResponse;
      return expireFrontendSession(fallbackResponse);
    }

    return expireFrontendSession(response);
  };
  window.__stroykaAuthFetchInstalled = true;
};
