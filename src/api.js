export const API = typeof window !== 'undefined' && window.location.hostname === 'localhost'
  ? 'http://localhost:8001'
  : '';

export const installAuthFetch = () => {
  if (typeof window === 'undefined' || window.__stroykaAuthFetchInstalled) return;
  const nativeFetch = window.fetch.bind(window);
  window.fetch = (input, init = {}) => {
    const token = localStorage.getItem('authToken');
    if (!token) return nativeFetch(input, init);
    const headers = new Headers(init.headers || {});
    if (!headers.has('Authorization')) headers.set('Authorization', 'Bearer ' + token);
    return nativeFetch(input, {...init, headers});
  };
  window.__stroykaAuthFetchInstalled = true;
};
