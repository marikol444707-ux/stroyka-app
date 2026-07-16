import { act, renderHook, waitFor } from '@testing-library/react';
import {
  useAuthEntryState,
  useAuthenticatedAppBootstrapEffect,
  useDarkModeState,
} from './useAppShellState';
import { requestPushPermission } from '../../utils/appRuntimeUtils';

jest.mock('../../utils/appRuntimeUtils', () => ({
  ...jest.requireActual('../../utils/appRuntimeUtils'),
  requestPushPermission: jest.fn(() => Promise.resolve(false)),
}));

describe('app shell state contracts', () => {
  const originalFetch = window.fetch;

  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    document.documentElement.removeAttribute('data-theme');
    window.history.replaceState({}, '', '/');
    requestPushPermission.mockResolvedValue(false);
  });

  afterEach(() => {
    window.fetch = originalFetch;
    localStorage.clear();
    sessionStorage.clear();
    document.documentElement.removeAttribute('data-theme');
    window.history.replaceState({}, '', '/');
    jest.restoreAllMocks();
  });

  it('restores an authenticated ERP user from storage on the /app route', () => {
    const storedUser = {
      id: 7,
      name: 'Директор',
      email: 'director@example.test',
      role: 'директор',
    };
    localStorage.setItem('authToken', 'session-token');
    localStorage.setItem('user', JSON.stringify(storedUser));
    window.history.replaceState({}, '', '/app');

    const { result } = renderHook(() => useAuthEntryState());

    expect(result.current.user).toEqual(storedUser);
    expect(result.current.page).toBe('login');
  });

  it('applies and persists the selected color theme', async () => {
    localStorage.setItem('darkMode', '1');

    const { result } = renderHook(() => useDarkModeState());

    expect(result.current[0]).toBe(true);
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe('dark'));

    act(() => result.current[1](false));

    await waitFor(() => expect(document.documentElement.dataset.theme).toBe('light'));
    expect(localStorage.getItem('darkMode')).toBe('0');
  });

  it('releases the dashboard loading state when initial data loading fails', async () => {
    const loadError = new Error('network unavailable');
    const setInitialDataLoaded = jest.fn();
    const refreshData = jest.fn().mockRejectedValue(loadError);
    const consoleError = jest.spyOn(console, 'error').mockImplementation(() => {});
    window.fetch = jest.fn().mockResolvedValue(new Response('{}', { status: 200 }));

    const args = {
      API: '/api',
      isMobile: false,
      loadMasterProfile: jest.fn(),
      loadMobileInitial: null,
      mobileApiRequestsRef: { current: new Map() },
      mobileLoadedScopesRef: { current: new Set(['stale']) },
      refreshData,
      setActivePage: jest.fn(),
      setCompanyName: jest.fn(),
      setInitialDataLoaded,
      setPushEnabled: jest.fn(),
      storageSetters: {},
      user: { id: 7, name: 'Директор', role: 'директор' },
    };

    const { unmount } = renderHook(() => useAuthenticatedAppBootstrapEffect(args));

    await waitFor(() => expect(setInitialDataLoaded).toHaveBeenCalledWith(true));
    expect(refreshData).toHaveBeenCalledTimes(1);
    expect(consoleError).toHaveBeenCalledWith('initial app data load failed', loadError);

    unmount();
  });
});
