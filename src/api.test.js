import { installAuthFetch, sendClientError } from './api';

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
    expect(new Headers(firstInit.headers || {}).has('X-Company-Mode')).toBe(false);
    expect(new Headers(firstInit.headers || {}).has('X-Company-Id')).toBe(false);
  });

  it('adds the selected company context to protected requests', async () => {
    localStorage.setItem('user', JSON.stringify({ id: 42, email: 'director@example.test' }));
    localStorage.setItem('stroyka.companyContext.v1.42', JSON.stringify({ mode: 'company', companyId: 7 }));
    const nativeFetch = jest.fn().mockResolvedValue(new Response('{}', { status: 200 }));
    window.fetch = nativeFetch;

    installAuthFetch();
    await window.fetch('/supply-requests');

    const headers = new Headers(nativeFetch.mock.calls[0][1].headers || {});
    expect(headers.get('X-Company-Mode')).toBe('company');
    expect(headers.get('X-Company-Id')).toBe('7');
  });

  it('sends all-companies mode without inventing a company id', async () => {
    localStorage.setItem('user', JSON.stringify({ id: 42, email: 'director@example.test' }));
    localStorage.setItem('stroyka.companyContext.v1.42', JSON.stringify({ mode: 'all_companies', companyId: null }));
    const nativeFetch = jest.fn().mockResolvedValue(new Response('{}', { status: 200 }));
    window.fetch = nativeFetch;

    installAuthFetch();
    await window.fetch('/supply-requests');

    const headers = new Headers(nativeFetch.mock.calls[0][1].headers || {});
    expect(headers.get('X-Company-Mode')).toBe('all_companies');
    expect(headers.has('X-Company-Id')).toBe(false);
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

  it.each([
    {
      label: 'accounting exception checks',
      path: '/accounting-exception-checks',
      init: {},
      mutating: false,
    },
    {
      label: 'assignment daily draft preview',
      path: '/assignment-daily-draft-previews',
      init: {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          projectId: 10,
          date: '2026-08-21',
          estimateId: 80,
          estimateVersionId: 4,
          workPackage: 'Слаботочка',
        }),
      },
      mutating: true,
    },
    {
      label: 'warehouse anomaly preview',
      path: '/warehouse-anomaly-previews',
      init: {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          projectId: 17,
          jobId: 27,
          selected: {
            subjectKind: 'warehouseInvoice',
            subjectId: 91,
            anomalyCode: 'warehouse_invoice_project_mismatch',
          },
        }),
      },
      mutating: true,
    },
    {
      label: 'human action proposal',
      path: '/human-approved-actions/proposals',
      init: {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          projectId: 17,
          jobId: 27,
          selected: {
            subjectKind: 'warehouseInvoice',
            subjectId: 91,
            anomalyCode: 'warehouse_invoice_project_mismatch',
          },
        }),
      },
      mutating: true,
    },
    {
      label: 'human action decision',
      path: '/human-approved-actions/decisions',
      init: {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          proposalId: 301,
          proposalSha256: 'a'.repeat(64),
          decision: 'approve',
        }),
      },
      mutating: true,
    },
    {
      label: 'human action history',
      path: '/human-approved-actions/history',
      init: {},
      mutating: false,
    },
    {
      label: 'material capability proof',
      path: '/supply-requests/21/items/0/material-capability-proof',
      init: {},
      mutating: false,
    },
    {
      label: 'material capability confirmation',
      path: '/supply-requests/21/items/0/material-capability-confirmations',
      init: {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          companySupplierLinkId: 31,
          supplierId: 41,
          confirmationSubjectSha256: 'b'.repeat(64),
        }),
      },
      mutating: true,
    },
    {
      label: 'material capability revocation',
      path: '/supplier-material-capability-confirmations/501/revocations',
      init: {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      },
      mutating: true,
    },
  ])('keeps $label cookie-only after a 401', async ({ path, init, mutating }) => {
    localStorage.setItem('authToken', 'legacy-token');
    localStorage.setItem('user', JSON.stringify({ id: 42, email: 'director@example.test' }));
    localStorage.setItem('stroyka.companyContext.v1.42', JSON.stringify({ mode: 'company', companyId: 7 }));
    const nativeFetch = jest.fn();
    if (mutating) {
      nativeFetch.mockResolvedValueOnce(new Response('{"csrfToken":"csrf-token"}', { status: 200 }));
    }
    nativeFetch
      .mockResolvedValueOnce(new Response('{}', { status: 401 }))
      .mockResolvedValue(new Response('{}', { status: 401 }));
    window.fetch = nativeFetch;
    const originalLocation = window.location;
    delete window.location;
    window.location = { ...originalLocation, origin: 'http://localhost', reload: jest.fn() };

    try {
      installAuthFetch();
      await window.fetch(path, init);

      const callsForPath = (expectedPath) => nativeFetch.mock.calls.filter(([input]) => {
        const url = typeof input === 'string' ? input : input.url;
        return new URL(url, window.location.origin).pathname === expectedPath;
      });
      const targetCalls = callsForPath(path);
      expect(targetCalls).toHaveLength(1);
      expect(nativeFetch).toHaveBeenCalledTimes(mutating ? 2 : 1);

      const targetHeaders = new Headers(targetCalls[0][1].headers || {});
      expect(targetHeaders.get('X-Company-Mode')).toBe('company');
      expect(targetHeaders.get('X-Company-Id')).toBe('7');
      expect(targetHeaders.has('Authorization')).toBe(false);

      const csrfCalls = callsForPath('/csrf-token');
      expect(csrfCalls).toHaveLength(mutating ? 1 : 0);
      if (mutating) {
        expect(targetHeaders.get('X-CSRF-Token')).toBe('csrf-token');
        expect(csrfCalls[0][1].credentials).toBe('include');
        expect(new Headers(csrfCalls[0][1].headers || {}).has('Authorization')).toBe(false);
      }
      nativeFetch.mock.calls.forEach(([, requestInit]) => {
        expect(new Headers(requestInit?.headers || {}).has('Authorization')).toBe(false);
      });
    } finally {
      window.location = originalLocation;
    }
  });

  it('expires the frontend session once when cookie and Bearer auth are both rejected', async () => {
    localStorage.setItem('authToken', 'legacy-token');
    localStorage.setItem('user', JSON.stringify({ id: 42, email: 'director@example.test' }));
    const nativeFetch = jest.fn().mockResolvedValue(new Response('{}', { status: 401 }));
    window.fetch = nativeFetch;
    const originalLocation = window.location;
    delete window.location;
    window.location = { ...originalLocation, origin: 'http://localhost', reload: jest.fn() };

    try {
      installAuthFetch();
      const response = await window.fetch('/users');

      expect(response.status).toBe(401);
      expect(nativeFetch).toHaveBeenCalledTimes(2);
      expect(localStorage.getItem('authToken')).toBeNull();
      expect(localStorage.getItem('user')).toBeNull();
      expect(sessionStorage.getItem('authExpiredNotice')).toBe('1');
      expect(window.location.reload).toHaveBeenCalledTimes(1);

      await window.fetch('/users');
      expect(window.location.reload).toHaveBeenCalledTimes(1);
    } finally {
      window.location = originalLocation;
    }
  });

  it.each(['/login', '/password-reset-request'])(
    'does not add protected-request headers to public auth path %s',
    async (path) => {
      localStorage.setItem('user', JSON.stringify({ id: 42, email: 'director@example.test' }));
      localStorage.setItem('stroyka.companyContext.v1.42', JSON.stringify({ mode: 'company', companyId: 7 }));
      const nativeFetch = jest.fn().mockResolvedValue(new Response('{"ok":true}', { status: 200 }));
      window.fetch = nativeFetch;

      installAuthFetch();
      const response = await window.fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: 'test@example.test', password: 'secret' }),
      });

      expect(response.status).toBe(200);
      expect(nativeFetch).toHaveBeenCalledTimes(1);
      expect(nativeFetch.mock.calls[0][0]).toBe(path);
      expect(nativeFetch.mock.calls[0][1].credentials).toBe('include');
      const headers = new Headers(nativeFetch.mock.calls[0][1].headers || {});
      expect(headers.has('X-CSRF-Token')).toBe(false);
      expect(headers.has('X-Company-Mode')).toBe(false);
      expect(headers.has('X-Company-Id')).toBe(false);
    },
  );
});

describe('sendClientError', () => {
  const originalFetch = window.fetch;
  const originalSendBeacon = navigator.sendBeacon;
  const originalClientErrorLogging = process.env.REACT_APP_CLIENT_ERROR_LOGGING;

  beforeEach(() => {
    localStorage.clear();
    delete window.__stroykaAuthFetchInstalled;
    process.env.REACT_APP_CLIENT_ERROR_LOGGING = 'true';
  });

  afterEach(() => {
    window.fetch = originalFetch;
    Object.defineProperty(navigator, 'sendBeacon', {
      configurable: true,
      value: originalSendBeacon,
    });
    localStorage.clear();
    delete window.__stroykaAuthFetchInstalled;
    if (originalClientErrorLogging === undefined) {
      delete process.env.REACT_APP_CLIENT_ERROR_LOGGING;
    } else {
      process.env.REACT_APP_CLIENT_ERROR_LOGGING = originalClientErrorLogging;
    }
  });

  it('uses authenticated tenant fetch before beacon fallback', async () => {
    localStorage.setItem('authToken', 'director-token');
    localStorage.setItem('user', JSON.stringify({ id: 42, email: 'director@example.test' }));
    localStorage.setItem('stroyka.companyContext.v1.42', JSON.stringify({ mode: 'company', companyId: 7 }));
    const nativeFetch = jest.fn().mockResolvedValue(new Response('{"ok":true}', { status: 200 }));
    window.fetch = nativeFetch;
    Object.defineProperty(navigator, 'sendBeacon', {
      configurable: true,
      value: jest.fn().mockReturnValue(true),
    });

    installAuthFetch();
    await sendClientError({ type: 'WindowError', message: 'failure', stack: 'stack' });

    expect(nativeFetch).toHaveBeenCalledTimes(2);
    expect(navigator.sendBeacon).not.toHaveBeenCalled();
    expect(String(nativeFetch.mock.calls[0][0])).toContain('/csrf-token');
    const headers = new Headers(nativeFetch.mock.calls[1][1].headers || {});
    expect(headers.get('Authorization')).toBe('Bearer director-token');
    expect(headers.get('X-Company-Mode')).toBe('company');
    expect(headers.get('X-Company-Id')).toBe('7');
    expect(nativeFetch.mock.calls[1][1].keepalive).toBe(true);
  });
});
