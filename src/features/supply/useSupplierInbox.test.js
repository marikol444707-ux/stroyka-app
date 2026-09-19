import { act, renderHook, waitFor } from '@testing-library/react';
import useSupplierInbox from './useSupplierInbox';
const originalFetch = global.fetch;
afterEach(() => { global.fetch = originalFetch; });
it('an old action completion cannot restart loading after switching accounts or leaving the cabinet', async () => {
  global.fetch = jest.fn(async () => ({ ok: true, json: async () => [] }));
  const { result, rerender, unmount } = renderHook(({ id }) => useSupplierInbox('/api', { id, role: 'поставщик' }), { initialProps: { id: 1 } });
  await waitFor(() => expect(result.current.status).toBe('ready'));
  const oldReload = result.current.reload;
  rerender({ id: 2 }); await waitFor(() => expect(result.current.status).toBe('ready'));
  const calls = global.fetch.mock.calls.length;
  await act(async () => { await oldReload(); });
  expect(result.current.status).toBe('ready'); expect(global.fetch).toHaveBeenCalledTimes(calls);
  const reloadAfterLeaving = result.current.reload;
  unmount(); await act(async () => { await reloadAfterLeaving(); });
  expect(global.fetch).toHaveBeenCalledTimes(calls);
});
