import {renderHook, waitFor} from '@testing-library/react';

import {useLatestDirectorDailyBrief} from './useLatestDirectorDailyBrief';


const companyContext = (companyId) => ({
  loading: false,
  mode: 'company',
  selectedCompanyId: companyId,
});

describe('useLatestDirectorDailyBrief', () => {
  const originalFetch = window.fetch;

  afterEach(() => {
    window.fetch = originalFetch;
    jest.restoreAllMocks();
  });

  test('does not request a brief without one selected company', async () => {
    window.fetch = jest.fn();

    const {result} = renderHook(() => useLatestDirectorDailyBrief({
      API: '',
      enabled: true,
      companyContext: {loading: false, mode: 'all_companies', selectedCompanyId: null},
    }));

    await waitFor(() => expect(result.current.status).toBe('select-company'));
    expect(window.fetch).not.toHaveBeenCalled();
  });

  test('loads the latest available brief for the selected company', async () => {
    const payload = {
      available: true,
      jobId: 17,
      completedAt: '2026-08-05T11:30:00',
      brief: {
        schemaVersion: 1,
        briefDate: '2026-08-05',
        mode: 'deterministic_read_only',
        summary: {total: 2, critical: 1, warning: 1, info: 0},
        sections: [{key: 'overdue', title: 'Просрочки', status: 'attention', count: 2, truncated: false, items: []}],
        sourceCounts: {projects: 4},
      },
    };
    window.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => payload,
    });

    const {result} = renderHook(() => useLatestDirectorDailyBrief({
      API: '/api',
      enabled: true,
      companyContext: companyContext(4),
    }));

    await waitFor(() => expect(result.current.status).toBe('ready'));
    expect(window.fetch).toHaveBeenCalledWith(
      '/api/agent-jobs/director-daily-brief/latest',
      expect.objectContaining({signal: expect.anything()}),
    );
    expect(result.current.data).toEqual(payload);
  });

  test('uses the resolved default company while selection state is settling', async () => {
    window.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({available: false}),
    });

    const {result} = renderHook(() => useLatestDirectorDailyBrief({
      API: '',
      enabled: true,
      companyContext: {
        loading: false,
        mode: 'company',
        selectedCompanyId: null,
        defaultCompanyId: 4,
      },
    }));

    await waitFor(() => expect(result.current.status).toBe('empty'));
    expect(window.fetch).toHaveBeenCalledTimes(1);
  });

  test('uses the account company when the context directory is still unavailable', async () => {
    window.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({available: false}),
    });

    const {result} = renderHook(() => useLatestDirectorDailyBrief({
      API: '',
      enabled: true,
      companyContext: {loading: false, mode: 'company', selectedCompanyId: null},
      fallbackCompanyId: 4,
    }));

    await waitFor(() => expect(result.current.status).toBe('empty'));
    expect(window.fetch).toHaveBeenCalledTimes(1);
  });

  test('reports an explicit empty state when no brief has been completed', async () => {
    window.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({available: false}),
    });

    const {result} = renderHook(() => useLatestDirectorDailyBrief({
      API: '',
      enabled: true,
      companyContext: companyContext(4),
    }));

    await waitFor(() => expect(result.current.status).toBe('empty'));
    expect(result.current.data).toBeNull();
  });

  test('clears the previous company result before loading another company', async () => {
    let resolveSecond;
    window.fetch = jest.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          available: true,
          jobId: 17,
          completedAt: '2026-08-05T11:30:00',
          brief: {
            schemaVersion: 1,
            briefDate: '2026-08-05',
            mode: 'deterministic_read_only',
            summary: {total: 0, critical: 0, warning: 0, info: 0},
            sections: [],
            sourceCounts: {},
          },
        }),
      })
      .mockImplementationOnce(() => new Promise((resolve) => { resolveSecond = resolve; }));

    const {result, rerender} = renderHook(
      ({context}) => useLatestDirectorDailyBrief({API: '', enabled: true, companyContext: context}),
      {initialProps: {context: companyContext(4)}},
    );
    await waitFor(() => expect(result.current.status).toBe('ready'));

    rerender({context: companyContext(5)});

    await waitFor(() => expect(result.current.status).toBe('loading'));
    expect(result.current.data).toBeNull();
    resolveSecond({ok: true, json: async () => ({available: false})});
    await waitFor(() => expect(result.current.status).toBe('empty'));
  });

  test('does not expose a malformed response as a ready brief', async () => {
    window.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({available: true, brief: null}),
    });

    const {result} = renderHook(() => useLatestDirectorDailyBrief({
      API: '',
      enabled: true,
      companyContext: companyContext(4),
    }));

    await waitFor(() => expect(result.current.status).toBe('error'));
    expect(result.current.data).toBeNull();
  });
});
