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

describe('supplier invitation registration', () => {
  const originalFetch = window.fetch;
  afterEach(() => { window.fetch = originalFetch; localStorage.clear(); });

  test.each([409, 422])('refusal %s preserves the supplied draft and does not log in or retry', async status => {
    const draft = {companyName:'Мой поставщик',inn:'77 - 12345678',bank:'Ручной ввод банка'};
    const setUser = jest.fn(), setPage = jest.fn(), setRegSupplierData = jest.fn(), setLoginError = jest.fn();
    window.fetch = jest.fn().mockResolvedValue({ok:false,status,json:async()=>({detail:'Проверьте реквизиты приглашённого поставщика'})});
    const actions = createAuthActions({API:'/api',regName:'Контакт',regEmail:'test@local.invalid',
      regPassword:'Synthetic-only!123',regCode:'OLD-INVITATION',regInviteInfo:{role:'поставщик'},
      regSupplierData:draft,setUser,setPage,setRegSupplierData,setLoginError});
    await actions.handleRegister();
    expect(window.fetch).toHaveBeenCalledTimes(1);
    expect(JSON.parse(window.fetch.mock.calls[0][1].body)).toMatchObject(draft);
    expect(setLoginError).toHaveBeenCalledWith('Проверьте реквизиты приглашённого поставщика');
    expect(setUser).not.toHaveBeenCalled();
    expect(setPage).not.toHaveBeenCalled();
    expect(setRegSupplierData).not.toHaveBeenCalled();
    expect(draft).toEqual({companyName:'Мой поставщик',inn:'77 - 12345678',bank:'Ручной ввод банка'});
    expect(localStorage.getItem('user')).toBeNull();
  });
});
