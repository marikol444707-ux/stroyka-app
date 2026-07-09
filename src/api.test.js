import { installAuthFetch } from './api';

describe('installAuthFetch', () => {
  const originalFetch = window.fetch;

  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    delete window.__stroykaAuthFetchInstalled;
    delete window.__stroykaSessionExpiring;
  });

  afterEach(() => {
    window.fetch = originalFetch;
    localStorage.clear();
    sessionStorage.clear();
    delete window.__stroykaAuthFetchInstalled;
    delete window.__stroykaSessionExpiring;
  });

  it('uses cookie session before adding the legacy Bearer fallback', async () => {
    localStorage.setItem('authToken', 'legacy-token');
    const nativeFetch = jest.fn().mockResolvedValue(new Response('{}', { status: 200 }));
    window.fetch = nativeFetch;

    installAuthFetch();
    const response = await window.fetch('/users');

    expect(response.status).toBe(200);
    expect(nativeFetch).toHaveBeenCalledTimes(1);
    const firstInit = nativeFetch.mock.calls[0][1];
    expect(firstInit.credentials).toBe('include');
    expect(new Headers(firstInit.headers || {}).has('Authorization')).toBe(false);
  });

  it('retries with the legacy Bearer token only after cookie auth is rejected', async () => {
    localStorage.setItem('authToken', 'legacy-token');
    const nativeFetch = jest.fn()
      .mockResolvedValueOnce(new Response('{}', { status: 401 }))
      .mockResolvedValueOnce(new Response('{"ok":true}', { status: 200 }));
    window.fetch = nativeFetch;

    installAuthFetch();
    const response = await window.fetch('/users');

    expect(response.status).toBe(200);
    expect(nativeFetch).toHaveBeenCalledTimes(2);
    expect(new Headers(nativeFetch.mock.calls[0][1].headers || {}).has('Authorization')).toBe(false);
    expect(new Headers(nativeFetch.mock.calls[1][1].headers || {}).get('Authorization')).toBe('Bearer legacy-token');
    expect(nativeFetch.mock.calls[1][1].credentials).toBe('include');
    expect(localStorage.getItem('authToken')).toBe('legacy-token');
    expect(sessionStorage.getItem('authExpiredNotice')).toBeNull();
  });

  it('adds a CSRF token to protected mutating requests before using Bearer fallback', async () => {
    localStorage.setItem('authToken', 'legacy-token');
    const nativeFetch = jest.fn()
      .mockResolvedValueOnce(new Response('{"csrfToken":"csrf-token"}', { status: 200 }))
      .mockResolvedValueOnce(new Response('{"ok":true}', { status: 200 }));
    window.fetch = nativeFetch;

    installAuthFetch();
    const response = await window.fetch('/project-payments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ amount: 1000 }),
    });

    expect(response.status).toBe(200);
    expect(nativeFetch).toHaveBeenCalledTimes(2);
    expect(String(nativeFetch.mock.calls[0][0])).toContain('/csrf-token');
    expect(nativeFetch.mock.calls[0][1].credentials).toBe('include');
    const requestHeaders = new Headers(nativeFetch.mock.calls[1][1].headers || {});
    expect(requestHeaders.get('X-CSRF-Token')).toBe('csrf-token');
    expect(requestHeaders.has('Authorization')).toBe(false);
  });

  it('does not fetch a CSRF token for public auth requests', async () => {
    const nativeFetch = jest.fn().mockResolvedValue(new Response('{"ok":true}', { status: 200 }));
    window.fetch = nativeFetch;

    installAuthFetch();
    const response = await window.fetch('/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'test@example.test', password: 'secret' }),
    });

    expect(response.status).toBe(200);
    expect(nativeFetch).toHaveBeenCalledTimes(1);
    expect(nativeFetch.mock.calls[0][0]).toBe('/login');
    expect(nativeFetch.mock.calls[0][1].credentials).toBe('include');
    expect(new Headers(nativeFetch.mock.calls[0][1].headers || {}).has('X-CSRF-Token')).toBe(false);
  });
});
