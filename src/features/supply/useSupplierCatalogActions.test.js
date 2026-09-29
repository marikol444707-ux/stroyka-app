import { act, renderHook } from '@testing-library/react';
import useSupplierCatalogActions from './useSupplierCatalogActions';
const draft = { materialName: 'Цемент', unit: 'шт', price: 10, minQuantity: 1, deliveryDays: 0 };
const reply = data => ({ ok: true, json: async () => data });
const originalFetch = global.fetch;
afterEach(() => { global.fetch = originalFetch; });
test('rapid duplicate clicks share one pending command', async () => {
  let resolve;
  global.fetch = jest.fn().mockImplementationOnce(() => new Promise(done => { resolve = done; })).mockResolvedValue(reply({ id: 5 }));
  const options = { API: '/api', actorId: 7, supplierId: 1, setCatalog: jest.fn(), onCreated: jest.fn() };
  const { result } = renderHook(() => useSupplierCatalogActions(options));
  let first;
  act(() => { first = result.current.create(draft); result.current.create(draft); });
  expect(global.fetch).toHaveBeenCalledTimes(1);
  await act(async () => { resolve(reply([])); await first; });
  expect(global.fetch).toHaveBeenCalledTimes(2); expect(options.onCreated).toHaveBeenCalledTimes(1);
});
test.each(['scope', 'unmount'])('late success cannot mutate another context after %s', async change => {
  let resolve;
  global.fetch = jest.fn().mockResolvedValueOnce(reply([])).mockImplementationOnce(() => new Promise(done => { resolve = done; }));
  const options = { API: '/api', actorId: 7, supplierId: 1, setCatalog: jest.fn(), onCreated: jest.fn() };
  const { result, rerender, unmount } = renderHook(props => useSupplierCatalogActions(props), { initialProps: options });
  let first;
  await act(async () => { first = result.current.create(draft); });
  if (change === 'scope') rerender({ ...options, actorId: 8, supplierId: 2 }); else unmount();
  await act(async () => { resolve(reply({ id: 5 })); await first; });
  expect(options.setCatalog).not.toHaveBeenCalled(); expect(options.onCreated).not.toHaveBeenCalled();
});
test('does not write while file import owns the shared catalogue lock', async () => {
  global.fetch = jest.fn();
  const mutationLock = { current: true };
  const { result } = renderHook(() => useSupplierCatalogActions({ API: '/api', actorId: 7, supplierId: 1, mutationLock }));
  await act(async () => { await result.current.create(draft); });
  expect(global.fetch).not.toHaveBeenCalled();
  expect(result.current.error).toContain('Дождитесь');
  expect(mutationLock.current).toBe(true);
});
