import {act, renderHook, waitFor} from '@testing-library/react';

import {useCompanyChatContextSync} from './useCompanyChatContextSync';

const response = (body, {ok = true, status = 200} = {}) => ({
  ok,
  status,
  json: jest.fn().mockResolvedValue(body),
});

const companyContext = (companyId) => ({
  loading: false,
  mode: 'company',
  selectedCompanyId: companyId,
});

describe('useCompanyChatContextSync', () => {
  beforeEach(() => {
    global.fetch = jest.fn();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test('loads messages for a concrete selected company', async () => {
    global.fetch.mockResolvedValue(response([{id: 1, text: 'Компания 4'}]));
    const setCompanyMessages = jest.fn();

    const {result} = renderHook(() => useCompanyChatContextSync({
      API: '',
      companyContext: companyContext(4),
      notify: jest.fn(),
      setCompanyMessages,
      user: {id: 7},
    }));

    await waitFor(() => expect(setCompanyMessages).toHaveBeenCalledWith([{id: 1, text: 'Компания 4'}]));
    expect(result.current.canUseCompanyChat).toBe(true);
  });

  test('does not let a delayed old-company response overwrite the new company', async () => {
    let resolveCompany4;
    global.fetch
      .mockImplementationOnce(() => new Promise((resolve) => { resolveCompany4 = resolve; }))
      .mockResolvedValueOnce(response([{id: 2, text: 'Компания 5'}]));
    const setCompanyMessages = jest.fn();
    const props = {
      API: '',
      notify: jest.fn(),
      setCompanyMessages,
      user: {id: 7},
    };

    const {rerender} = renderHook(
      ({context}) => useCompanyChatContextSync({...props, companyContext: context}),
      {initialProps: {context: companyContext(4)}},
    );
    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));

    rerender({context: companyContext(5)});
    await waitFor(() => expect(setCompanyMessages).toHaveBeenCalledWith([{id: 2, text: 'Компания 5'}]));

    await act(async () => {
      resolveCompany4(response([{id: 1, text: 'Компания 4'}]));
      await Promise.resolve();
    });

    expect(setCompanyMessages).not.toHaveBeenCalledWith([{id: 1, text: 'Компания 4'}]);
    const company5Call = setCompanyMessages.mock.calls.findIndex(([rows]) => rows?.[0]?.id === 2);
    expect(company5Call).toBeGreaterThan(-1);
    expect(setCompanyMessages.mock.calls.slice(0, company5Call).some(([rows]) => Array.isArray(rows) && rows.length === 0)).toBe(true);
  });

  test('clears messages and skips the endpoint in all-companies mode', async () => {
    const setCompanyMessages = jest.fn();

    const {result} = renderHook(() => useCompanyChatContextSync({
      API: '',
      companyContext: {loading: false, mode: 'all_companies', selectedCompanyId: null},
      notify: jest.fn(),
      setCompanyMessages,
      user: {id: 7},
    }));

    await waitFor(() => expect(setCompanyMessages).toHaveBeenCalledWith([]));
    expect(global.fetch).not.toHaveBeenCalled();
    expect(result.current.canUseCompanyChat).toBe(false);
  });
});
