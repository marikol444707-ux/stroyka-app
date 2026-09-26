import { act, renderHook, waitFor } from '@testing-library/react';
import useSupplierPaymentDialog from './useSupplierPaymentDialog';
import { readPending } from './paymentClient';

// Real client/normalizer/storage; only the browser transport and lock are fakes.
const scope = { API: '/fixture', userId: 7, companyId: 2, documentKind: 'invoice', documentId: 9 };
const original = { operationId: 51, companyId: 2, documentKind: 'warehouse', documentId: 8,
  kind: 'payment', amount: '10.01', paidAt: '2026-09-17', reversedById: null };
const response = data => ({ ok: true, json: async () => data });
const oldFetch = window.fetch;
const oldLocks = Object.getOwnPropertyDescriptor(window.navigator, 'locks');
const oldCrypto = Object.getOwnPropertyDescriptor(window, 'crypto');
let posts, loseResponse, committed;
beforeEach(() => {
  window.localStorage.removeItem('supplier-payment:v1:7:2'); posts = []; loseResponse = false; committed = false;
  Object.defineProperty(window.navigator, 'locks', { configurable: true, value: { request: (_name, _options, work) => work({}) } });
  Object.defineProperty(window, 'crypto', { configurable: true, value: { randomUUID: () => '12345678-1234-4234-8234-123456789abc' } });
  window.fetch = jest.fn(async (url, init) => {
    if (init.method === 'POST') {
      const body = JSON.parse(init.body); posts.push(body);
      expect(readPending(scope).body).toEqual(body); committed = true;
      if (loseResponse) { loseResponse = false; throw new TypeError('Failed to fetch'); }
      return response({ ...body, companyId: 2, operationId: 61, projectPaymentId: 71, amount: '10.01' });
    }
    if (url.includes('payment-documents')) return response({ schemaVersion: 1, companyId: 2, documentKind: 'invoice', documentId: 9,
      canonicalTarget: { documentKind: 'invoice', documentId: 9 }, amount: '20.00', paidAmount: committed ? '0.00' : '10.01',
      remainingAmount: committed ? '20.00' : '9.99' });
    return response({ schemaVersion: 1, companyId: 2, hasMore: false, items: [{ ...original, reversedById: committed ? 61 : null }] });
  });
});
afterEach(() => {
  window.fetch = oldFetch;
  if (oldLocks) Object.defineProperty(window.navigator, 'locks', oldLocks); else delete window.navigator.locks;
  if (oldCrypto) Object.defineProperty(window, 'crypto', oldCrypto); else delete window.crypto;
  window.localStorage.removeItem('supplier-payment:v1:7:2');
});
async function prepared() {
  const view = renderHook(() => useSupplierPaymentDialog(scope));
  await waitFor(() => expect(view.result.current.loading).toBe(false));
  act(() => view.result.current.beginReversal(51));
  act(() => view.result.current.updateReversal({ paidAt: '2026-09-18', reason: '  Ошибка оплаты  ', confirmed: true }));
  return view;
}
test('real normalization sends no amount, retains paired origin and refreshes confirmed history/debt', async () => {
  const { result } = await prepared();
  await act(async () => result.current.submitReversal());
  expect(posts).toHaveLength(1);
  expect(posts[0]).toEqual({ requestId: '12345678-1234-4234-8234-123456789abc', kind: 'reversal',
    documentKind: 'warehouse', documentId: 8, reversesId: 51, paidAt: '2026-09-18', reason: 'Ошибка оплаты' });
  expect(result.current.success.kind).toBe('reversal');
  expect(result.current.snapshot.remainingAmount).toBe('20.00');
  expect(result.current.history.items[0].reversedById).toBe(61);
  expect(readPending(scope)).toBeNull();
});
test('lost reversal response preserves exact command; local draft cancellation cannot discard pending', async () => {
  const { result } = await prepared(); loseResponse = true;
  await act(async () => result.current.submitReversal());
  const saved = readPending(scope);
  act(() => result.current.cancelReversal()); expect(readPending(scope)).toEqual(saved);
  await act(async () => result.current.retry());
  expect(posts).toHaveLength(2); expect(posts[1]).toEqual(posts[0]);
  expect(result.current.success.kind).toBe('reversal'); expect(readPending(scope)).toBeNull();
});
test.each([{ reason: ' ' }, { paidAt: '2026-02-31' }])('invalid reversal details rejected before POST: %j', async change => {
  const { result } = await prepared(); act(() => result.current.updateReversal(change));
  await act(async () => result.current.submitReversal());
  expect(posts).toHaveLength(0); expect(readPending(scope)).toBeNull(); expect(result.current.error).toBeTruthy();
});

test('server race rejection keeps original history and saved reversal; no optimistic debt update', async () => {
  const { result } = await prepared();
  window.fetch.mockResolvedValueOnce({ ok: false, status: 409, json: async () => ({ detail: 'Платёж уже сторнирован.' }) });
  await act(async () => result.current.submitReversal());
  expect(result.current.error).toBe('Платёж уже сторнирован.');
  expect(result.current.success).toBeNull();
  expect(result.current.snapshot.remainingAmount).toBe('9.99');
  expect(result.current.history.items[0].reversedById).toBeNull();
  expect(result.current.reversal.reason).toBe('  Ошибка оплаты  ');
  expect(readPending(scope).body).toMatchObject({ kind: 'reversal', reversesId: 51 });
});
