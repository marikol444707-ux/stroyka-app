import {renderHook, waitFor} from '@testing-library/react';
import {useAuthEntryState} from './useAppShellState';

describe('useAuthEntryState cookie restore', () => {
  const originalFetch = window.fetch;

  afterEach(() => {
    window.fetch = originalFetch;
    localStorage.clear();
    sessionStorage.clear();
  });

  test('empty localStorage with a valid cookie leaves the login screen', async () => {
    window.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        id: 7,
        role: 'прораб',
        name: 'Иван',
        email: 'foreman@example.test',
        companyId: 4,
        authToken: 'must-not-be-stored',
      }),
    });

    const {result} = renderHook(() => useAuthEntryState());
    expect(result.current.user).toBeNull();
    expect(result.current.sessionChecked).toBe(false);

    await waitFor(() => expect(result.current.sessionChecked).toBe(true));
    expect(result.current.user).toEqual(expect.objectContaining({id: 7, role: 'прораб', companyId: 4}));
    expect(result.current.user).not.toHaveProperty('authToken');
    expect(result.current.loginError).toBe('');
    expect(JSON.parse(localStorage.getItem('user'))).not.toHaveProperty('authToken');
  });

  test('a rejected cookie shows login instead of an application failure', async () => {
    window.fetch = jest.fn().mockResolvedValue({ok: false, status: 401, json: async () => ({})});
    const {result} = renderHook(() => useAuthEntryState());

    await waitFor(() => expect(result.current.sessionChecked).toBe(true));
    expect(result.current.user).toBeNull();
    expect(result.current.loginError).toBe('');
  });

  test('a network failure is not the same as a missing session', async () => {
    window.fetch = jest.fn().mockRejectedValue(new Error('offline'));
    const {result} = renderHook(() => useAuthEntryState());

    await waitFor(() => expect(result.current.sessionChecked).toBe(true));
    expect(result.current.user).toBeNull();
    expect(result.current.loginError).toBe('Не удалось проверить вход. Обновите страницу.');
  });

  test('an already stored user is not asked to log in again', () => {
    localStorage.setItem('user', JSON.stringify({id: 3, role: 'директор', email: 'director@example.test'}));
    window.fetch = jest.fn();
    const {result} = renderHook(() => useAuthEntryState());

    expect(result.current.sessionChecked).toBe(true);
    expect(result.current.user).toEqual(expect.objectContaining({id: 3, role: 'директор'}));
    expect(window.fetch).not.toHaveBeenCalled();
  });
});
