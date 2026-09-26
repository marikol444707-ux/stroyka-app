import { act, renderHook, waitFor } from '@testing-library/react';
import useSupplierPaymentDialog from './useSupplierPaymentDialog';
import { readPending } from './paymentClient';

const scope = { API: '/fixture', userId: 7, companyId: 2, documentKind: 'invoice', documentId: 9 };
const key = 'supplier-payment:v1:7:2';
const command = { version: 1, userId: 7, companyId: 2, body: {
  requestId: '12345678-1234-4234-8234-123456789abc', kind: 'reversal', documentKind: 'warehouse', documentId: 8,
  reversesId: 51, paidAt: '2026-09-18', reason: 'Ошибка' } };
const snapshot = { schemaVersion: 1, companyId: 2, documentKind: 'invoice', documentId: 9,
  canonicalTarget: { documentKind: 'invoice', documentId: 9 }, amount: '20.00', paidAmount: '10.01', remainingAmount: '9.99' };
const response = data => ({ ok: true, json: async () => data });
const oldFetch = window.fetch;
const oldLocks = Object.getOwnPropertyDescriptor(window.navigator, 'locks');
let cancellation, posts;
beforeEach(() => {
  posts = []; window.localStorage.setItem(key, JSON.stringify(command));
  Object.defineProperty(window.navigator, 'locks', { configurable: true, value: { request: (_name, _options, work) => work({}) } });
  cancellation = { status: 'cancelled', companyId: 2, ...command.body, cancelledAt: '2026-09-18T12:00:00Z' };
  window.fetch = jest.fn(async (url, init) => {
    if (init.method === 'POST') {
      expect(url).toBe('/fixture/companies/2/supplier-payments/cancel-request');
      expect(readPending(scope).cancelRequested).toBe(true);
      posts.push(JSON.parse(init.body)); return response(cancellation);
    }
    return response(url.includes('payment-documents') ? snapshot : { schemaVersion: 1, companyId: 2, items: [], hasMore: false });
  });
});
afterEach(() => {
  window.fetch = oldFetch;
  if (oldLocks) Object.defineProperty(window.navigator, 'locks', oldLocks); else delete window.navigator.locks;
  window.localStorage.removeItem(key);
});
async function prepared() {
  const view = renderHook(() => useSupplierPaymentDialog(scope));
  await waitFor(() => expect(view.result.current.loading).toBe(false));
  act(() => view.result.current.confirmCancellation(true)); return view;
}
test('real client cancellation clears only verified attempt and refreshes unchanged money', async () => {
  const { result } = await prepared();
  await act(async () => { const cancel = result.current.cancelPending; await cancel(); await cancel(); });
  expect(posts).toEqual([command.body]); expect(readPending(scope)).toBeNull();
  expect(result.current.success.status).toBe('cancelled');
  expect(result.current.snapshot.remainingAmount).toBe('9.99');
  expect(result.current.pending).toBeNull();
  act(() => result.current.startNext()); expect(result.current.success).toBeNull();
});
test('commit won: nested result retains original identity and reversal kind, never cancelled', async () => {
  cancellation = { companyId: 2, ...command.body, status: 'confirmed',
    result: { operationId: 61, projectPaymentId: 71, kind: 'reversal', amount: '10.01' } };
  const { result } = await prepared(); await act(async () => result.current.cancelPending());
  expect(result.current.success).toEqual({ companyId: 2, requestId: command.body.requestId, documentKind: 'warehouse', documentId: 8,
    kind: 'reversal', operationId: 61, projectPaymentId: 71, amount: '10.01' });
  expect(readPending(scope)).toBeNull();
});
test('lost cancellation response persists direction across remount and cannot retry original operation', async () => {
  const { result, unmount } = await prepared();
  window.fetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));
  await act(async () => result.current.cancelPending());
  expect(readPending(scope).cancelRequested).toBe(true); unmount();
  const view = renderHook(() => useSupplierPaymentDialog(scope));
  await waitFor(() => expect(view.result.current.loading).toBe(false));
  const before = window.fetch.mock.calls.length;
  await act(async () => view.result.current.retry()); expect(window.fetch).toHaveBeenCalledTimes(before);
  await act(async () => view.result.current.cancelPending());
  expect(posts).toEqual([command.body]); expect(readPending(scope)).toBeNull();
});
test('mismatching cancellation identity remains pending, never success', async () => {
  cancellation.companyId = 3;
  const { result } = await prepared(); await act(async () => result.current.cancelPending());
  expect(result.current.success).toBeNull(); expect(result.current.pending.cancelRequested).toBe(true);
  expect(readPending(scope).body).toEqual(command.body);
});

test('confirmation of an old command cannot cancel a replacement stored by another tab', async () => {
  const { result } = await prepared();
  window.localStorage.setItem(key, JSON.stringify({ ...command, body: { ...command.body,
    requestId: '22345678-1234-4234-8234-123456789abc' } }));
  await act(async () => result.current.cancelPending());
  expect(posts).toHaveLength(0); expect(result.current.cancellationConfirmed).toBe(false);
  expect(readPending(scope).cancelRequested).toBeUndefined();
});

test.each([
  ['cancelPending', { requestId: '22345678-1234-4234-8234-123456789abc' }],
  ['retry', { requestId: '22345678-1234-4234-8234-123456789abc' }],
  ['cancelPending', { reason: 'Другой текст с тем же UUID' }],
  ['retry', { reason: 'Другой текст с тем же UUID' }],
])('%s pins displayed body across replacement at lock acquisition: %j', async (action, change) => {
  const { result } = await prepared();
  const replacement = { ...command, body: { ...command.body, ...change } };
  Object.defineProperty(window.navigator, 'locks', { configurable: true, value: { request: (_name, _options, work) => {
    window.localStorage.setItem(key, JSON.stringify(replacement)); return work({});
  } } });
  const before = window.fetch.mock.calls.length;
  await act(async () => result.current[action]());
  expect(window.fetch).toHaveBeenCalledTimes(before);
  expect(readPending(scope)).toEqual(replacement);
  expect(result.current.success).toBeNull();
});
