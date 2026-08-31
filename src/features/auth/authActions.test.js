import {createAuthActions} from './authActions';

describe('authActions cookie-only browser session', () => {
  const originalFetch = window.fetch;

  afterEach(() => {
    window.fetch = originalFetch;
    localStorage.clear();
  });

  test('accepts a successful cookie login without authToken and clears a legacy token', async () => {
    localStorage.setItem('authToken', 'legacy-token');
    const setUser = jest.fn();
    const setLoginError = jest.fn();
    window.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue({
        id: 7,
        role: 'директор',
        email: 'director@example.test',
        authToken: 'server-compatibility-token',
      }),
    });
    const actions = createAuthActions({
      API: '',
      email: 'director@example.test',
      password: 'secret',
      setInitialDataLoaded: jest.fn(),
      setLoginError,
      setUser,
    });

    const result = await actions.handleLogin();

    expect(result).toEqual(expect.objectContaining({id: 7, role: 'директор'}));
    expect(result).not.toHaveProperty('authToken');
    expect(setLoginError).not.toHaveBeenCalledWith('Сервер не вернул токен входа');
    expect(setUser).toHaveBeenCalledWith(expect.objectContaining({id: 7, role: 'директор'}));
    expect(localStorage.getItem('authToken')).toBeNull();
    expect(JSON.parse(localStorage.getItem('user'))).toEqual(expect.objectContaining({id: 7, role: 'директор'}));
    expect(JSON.parse(localStorage.getItem('user'))).not.toHaveProperty('authToken');
  });
});
