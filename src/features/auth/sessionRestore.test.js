import {restoreCookieSession} from './sessionRestore';

describe('restoreCookieSession', () => {
  const originalFetch = window.fetch;

  afterEach(() => {
    window.fetch = originalFetch;
    localStorage.clear();
  });

  test('a cookie-only session restores the server user and does not store a token', async () => {
    localStorage.setItem('authToken', 'legacy-token');
    window.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        id: 7,
        role: 'прораб',
        name: 'Иван',
        email: 'foreman@example.test',
        companyId: 4,
        company_id: 4,
        authToken: 'must-not-be-stored',
      }),
    });

    const result = await restoreCookieSession('');

    expect(result.status).toBe('authenticated');
    expect(result.user).toEqual(expect.objectContaining({id: 7, role: 'прораб', companyId: 4}));
    expect(result.user).not.toHaveProperty('authToken');
    expect(JSON.parse(localStorage.getItem('user'))).toEqual(expect.objectContaining({
      id: 7,
      role: 'прораб',
      companyId: 4,
    }));
    expect(JSON.parse(localStorage.getItem('user'))).not.toHaveProperty('authToken');
    expect(localStorage.getItem('authToken')).toBeNull();
    expect(window.fetch).toHaveBeenCalledWith('/auth/session', expect.objectContaining({
      method: 'GET',
      credentials: 'include',
    }));
    expect(document.cookie).not.toContain('stroyka_session');
  });

  test('an invalid cookie stays logged out and does not invent a user', async () => {
    window.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({detail: 'Сессия недействительна'}),
    });

    const result = await restoreCookieSession('');

    expect(result).toEqual({status: 'anonymous'});
    expect(localStorage.getItem('user')).toBeNull();
    expect(localStorage.getItem('authToken')).toBeNull();
  });

  test('a response without a role is rejected', async () => {
    window.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({id: 7, name: 'Иван', companyId: 4}),
    });

    await expect(restoreCookieSession('')).resolves.toEqual({status: 'anonymous'});
    expect(localStorage.getItem('user')).toBeNull();
  });

  test('a server failure is reported separately from a missing session', async () => {
    window.fetch = jest.fn().mockRejectedValue(new Error('network'));

    await expect(restoreCookieSession('')).resolves.toEqual({status: 'unavailable'});
    expect(localStorage.getItem('user')).toBeNull();
  });
});
