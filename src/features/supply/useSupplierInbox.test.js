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
it('order data loads as a complete authorized snapshot and clears stale records on failure',async()=>{
 let fail=false;
 global.fetch=jest.fn(async url=>({ok:!(fail&&url.endsWith('/supplier-invoices')),status:503,json:async()=>url.endsWith('/supply-requests')?[{id:1}]:url.endsWith('/supplier-offers')?[{id:2,requestId:1}]:url.endsWith('/supply-deliveries')?[{id:3,offerId:2}]:fail?{detail:'Unavailable'}:[]}));
 const {result}=renderHook(()=>useSupplierInbox('/api',{id:1,role:'поставщик'},true));
 await waitFor(()=>expect(result.current.status).toBe('ready'));
 expect(result.current.deliveries).toHaveLength(1);
 expect(global.fetch).toHaveBeenCalledTimes(4);
 fail=true;await act(async()=>{await result.current.reload();});
 expect(result.current.status).toBe('error');expect(result.current.deliveries).toEqual([]);expect(result.current.offers).toEqual([]);
});
