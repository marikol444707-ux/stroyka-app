import { act, renderHook, waitFor } from '@testing-library/react';
import { useState } from 'react';
import useCustomerRecordsLoader from './useCustomerRecordsLoader';

function useHarness(companyId = 2, mode = 'company') {
  const [state, setCustomerRecordsLoadState] = useState({});
  const [docs, setProjectDocuments] = useState([]);
  const [letters, setProjectLetters] = useState([]);
  const [warranty, setWarrantyDefects] = useState([]);
  const reload = useCustomerRecordsLoader({ API: '/api', user: { id: 7, role: 'заказчик', companyId, projectId: 3 },
    companyContext: { mode, selectedCompanyId: companyId }, customerProjects: [{ id: 3, companyId }],
    setCustomerRecordsLoadState, setProjectDocuments, setProjectLetters, setWarrantyDefects });
  return { state, docs, letters, warranty, reload };
}
afterEach(() => jest.restoreAllMocks());
test('each resource has its own status and a failed refresh cannot masquerade as success', async () => {
  global.fetch = jest.fn(async url => ({ ok: !url.includes('warranty'), json: async () => [] }));
  const { result } = renderHook(() => useHarness());
  await waitFor(() => expect(result.current.state.warranty?.status).toBe('error'));
  expect(result.current.state.documents.status).toBe('ready');
  expect(result.current.state.letters.status).toBe('ready');
  await act(async () => { await expect(result.current.reload()).rejects.toThrow(); });
  expect(fetch.mock.calls[0][1].headers['X-Company-Id']).toBe('2');
});
test('foreign ownership in an HTTP 200 result is rejected', async () => {
  global.fetch = jest.fn(async () => ({ ok: true, json: async () => [{ companyId: 8, projectId: 3, side: 'customer' }] }));
  const { result } = renderHook(() => useHarness());
  await waitFor(() => expect(result.current.state.documents?.status).toBe('error'));
  expect(result.current.docs).toEqual([]);
});
test('another project in the same company is rejected for every resource', async () => {
  global.fetch = jest.fn(async () => ({ ok: true, json: async () => [{ companyId: 2, projectId: 4, side: 'customer', createdByUserId: 7 }] }));
  const { result } = renderHook(() => useHarness());
  await waitFor(() => expect(result.current.state.warranty?.status).toBe('error'));
  for (const kind of ['documents', 'letters', 'warranty']) expect(result.current.state[kind].status).toBe('error');
  expect(result.current.docs).toEqual([]);
  expect(result.current.letters).toEqual([]);
  expect(result.current.warranty).toEqual([]);
});
test.each(['all_companies', 'unset'])('no implicit single-company fallback in %s mode', mode => {
  global.fetch = jest.fn();
  renderHook(() => useHarness(2, mode));
  expect(fetch).not.toHaveBeenCalled();
});
test('late response from previous company cannot overwrite the new scope', async () => {
  const pending = [];
  global.fetch = jest.fn(() => new Promise(resolve => pending.push(resolve)));
  const { result, rerender } = renderHook(({ company }) => useHarness(company), { initialProps: { company: 2 } });
  rerender({ company: 3 });
  await act(async () => { for (const resolve of pending.slice(3)) resolve({ ok: true, json: async () => [] }); });
  await act(async () => { for (const resolve of pending.slice(0, 3)) resolve({ ok: true, json: async () => [{ companyId: 2, projectId: 3, side: 'customer' }] }); });
  expect(result.current.docs).toEqual([]);
  expect(result.current.state.documents.scope).toContain('7:3:');
  expect(result.current.state.documents.status).toBe('ready');
});
