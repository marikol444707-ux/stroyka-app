import { act, renderHook, waitFor } from '@testing-library/react';
import useSupplierQuoteResponse from './useSupplierQuoteResponse';
const originalFetch = global.fetch;
beforeEach(() => {
  Object.defineProperty(window, 'crypto', { configurable: true, value: { randomUUID: () => '12345678-1234-4234-8234-123456789012' } });
});
afterEach(() => { global.fetch = originalFetch; jest.useRealTimers(); });
it('ignores an old completion after switching actor or leaving the form', async () => {
  let finish;
  global.fetch = jest.fn(() => new Promise(resolve => { finish = resolve; }));
  const onSaved = jest.fn();
  const { result, rerender, unmount } = renderHook(({ actorId }) => useSupplierQuoteResponse({ API: '/api', actorId, offerId: 42, onSaved }), { initialProps: { actorId: 1 } });
  let request;
  act(() => { request = result.current.submit({ action: 'respond' }); });
  const oldSubmit = result.current.submit;
  rerender({ actorId: 2 });
  expect(result.current.busy).toBe(false);
  await act(async () => { finish({ ok: true, json: async () => ({ id: 42, status: 'Получено' }) }); await request; });
  expect(onSaved).not.toHaveBeenCalled();
  await act(async () => { await oldSubmit({ action: 'respond' }); });
  expect(global.fetch).toHaveBeenCalledTimes(1);
  const submit = result.current.submit;
  unmount();
  await submit({ action: 'respond' });
  expect(global.fetch).toHaveBeenCalledTimes(1);
});
it('releases a timed out request with a persistent uncertainty message', async () => {
  jest.useFakeTimers();
  global.fetch = jest.fn((url, { signal }) => new Promise((resolve, reject) => {
    signal.addEventListener('abort', () => reject(new Error('Timeout')));
  }));
  const onSaved = jest.fn();
  const { result } = renderHook(() => useSupplierQuoteResponse({ API: '/api', actorId: 1, offerId: 42, onSaved }));
  let request;
  act(() => { request = result.current.submit({ action: 'respond' }); });
  await act(async () => { jest.advanceTimersByTime(20000); await request; });
  expect(result.current.busy).toBe(false);
  expect(result.current.error).toContain('результат неизвестен');
  expect(onSaved).not.toHaveBeenCalled();
});

it('reopening the same offer after a successful send starts with an unlocked form', async () => {
  global.fetch = jest.fn(async () => ({ ok: true, json: async () => ({ id: 42, status: 'Получено' }) }));
  let refreshDone;
  const onSaved = jest.fn(() => new Promise(resolve => { refreshDone = resolve; }));
  const { result, rerender } = renderHook(({ offerId }) => useSupplierQuoteResponse({ API: '/api', actorId: 1, offerId, onSaved }), { initialProps: { offerId: 42 } });
  let request;
  act(() => { request = result.current.submit({ action: 'respond' }); });
  await waitFor(() => expect(onSaved).toHaveBeenCalledTimes(1));
  rerender({ offerId: null });
  await act(async () => { refreshDone(); await request; });
  rerender({ offerId: 42 });
  expect(result.current.busy).toBe(false);
  expect(result.current.error).toBe('');
});
