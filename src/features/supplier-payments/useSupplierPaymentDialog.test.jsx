import { act, renderHook, waitFor } from '@testing-library/react';
import useSupplierPaymentDialog from './useSupplierPaymentDialog';
import { cancelPendingPayment, paymentRequest, readPending, submitPayment } from './paymentClient';

jest.mock('./paymentClient', () => ({ cancelPendingPayment: jest.fn(), paymentRequest: jest.fn(), readPending: jest.fn(), submitPayment: jest.fn(),
  paymentPath: id => `/companies/${id}/supplier-payments` }));
const scope = { API: '/api', userId: 4, companyId: 2, documentKind: 'warehouse', documentId: 7 };
const snapshot = { schemaVersion: 1, companyId: 2, documentKind: 'warehouse', documentId: 7,
  canonicalTarget: { documentKind: 'invoice', documentId: 9 }, amount: '200.00', paidAmount: '0.00',
  remainingAmount: '200.00', scope: { payerCompanyId: 2, supplierId: 3, projectName: 'Объект', workPackage: 'Основная' } };
const history = { schemaVersion: 1, companyId: 2, items: [], hasMore: false, nextCursor: null };
const pending = { version: 1, userId: 4, companyId: 2, body: { requestId: 'saved-uuid', kind: 'payment',
  documentKind: 'invoice', documentId: 9, amount: '10.01', paidAt: '2026-09-18', reason: 'Поставка' } };
const deferred = () => { let resolve; let reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
beforeEach(() => {
  jest.clearAllMocks(); readPending.mockReturnValue(null);
  paymentRequest.mockImplementation(async (_api, _company, path) => path.includes('payment-documents') ? snapshot : history);
});
async function ready(result) { await waitFor(() => expect(result.current.loading).toBe(false)); }
function fill(result) { act(() => result.current.updateDraft({ amount: '10,01', paidAt: '2026-09-18', reason: 'Поставка' })); }

test('canonical target, exact money, and synchronous retirement prevent sequential double submit', async () => {
  submitPayment.mockResolvedValue({ operationId: 1 });
  const { result } = renderHook(() => useSupplierPaymentDialog(scope));
  await ready(result); fill(result);
  await act(async () => { const send = result.current.submit; await send(); await send(); });
  expect(submitPayment).toHaveBeenCalledTimes(1);
  expect(submitPayment.mock.calls[0][0]).toMatchObject({ userId: 4, companyId: 2, input: {
    documentKind: 'invoice', documentId: 9, amount: '10.01', paidAt: '2026-09-18', reason: 'Поставка', kind: 'payment' } });
  expect(result.current.success).toBeTruthy();
});

test('rapid clicks while awaiting response send once', async () => {
  const response = deferred(); submitPayment.mockReturnValue(response.promise);
  const { result } = renderHook(() => useSupplierPaymentDialog(scope)); await ready(result); fill(result);
  let first; act(() => { first = result.current.submit(); result.current.submit(); });
  expect(submitPayment).toHaveBeenCalledTimes(1);
  await act(async () => { response.resolve({ operationId: 1 }); await first; });
});

test('lost response preserves draft and exact saved command; retry never makes a new input', async () => {
  submitPayment.mockImplementationOnce(async () => { readPending.mockReturnValue(pending); throw new Error('Сеть'); });
  const { result } = renderHook(() => useSupplierPaymentDialog(scope)); await ready(result); fill(result);
  await act(async () => result.current.submit());
  expect(result.current.pending).toEqual(pending);
  expect(result.current.draft.amount).toBe('10,01');
  expect(result.current.error).toContain('Сеть');
  submitPayment.mockImplementationOnce(async () => { readPending.mockReturnValue(null); return { operationId: 1 }; });
  await act(async () => result.current.retry());
  expect(submitPayment.mock.calls[1][0]).toMatchObject({ retry: true, expectedBody: pending.body });
  expect(submitPayment.mock.calls[1][0].input).toBeUndefined();
});

test('pending stays visible and retryable despite failed snapshot/history reads', async () => {
  readPending.mockReturnValue(pending); paymentRequest.mockRejectedValue(new Error('not_found'));
  const { result } = renderHook(() => useSupplierPaymentDialog(scope)); await ready(result);
  expect(result.current.pending).toEqual(pending);
  expect(result.current.snapshot).toBeNull();
  submitPayment.mockRejectedValue(new Error('Сеть'));
  await act(async () => result.current.retry());
  expect(submitPayment.mock.calls[0][0]).toMatchObject({ retry: true });
  expect(result.current.pending).toEqual(pending);
});

test('stale load and mutation success cannot apply to changed user/company/document scope', async () => {
  const response = deferred(); submitPayment.mockReturnValue(response.promise);
  const onSuccess = jest.fn();
  const { result, rerender } = renderHook(props => useSupplierPaymentDialog({ ...props, onSuccess }), { initialProps: scope });
  await ready(result); fill(result);
  let send; act(() => { send = result.current.submit(); });
  const stale = deferred(); paymentRequest.mockReturnValue(stale.promise);
  rerender({ ...scope, companyId: 3 });
  expect(result.current.snapshot).toBeNull();
  await act(async () => { response.resolve({ operationId: 1 }); await send; stale.resolve(snapshot); });
  expect(onSuccess).not.toHaveBeenCalled();
  expect(result.current.success).toBeNull();
  expect(result.current.snapshot).toBeNull();
});

test('unmount ignores completion and aborts scoped requests', async () => {
  const response = deferred(); submitPayment.mockReturnValue(response.promise); const onSuccess = jest.fn();
  const { result, unmount } = renderHook(() => useSupplierPaymentDialog({ ...scope, onSuccess }));
  await ready(result); fill(result); let send; act(() => { send = result.current.submit(); });
  const signal = submitPayment.mock.calls[0][0].signal; unmount(); expect(signal.aborted).toBe(true);
  await act(async () => { response.resolve({ operationId: 1 }); await send; }); expect(onSuccess).not.toHaveBeenCalled();
});

test('bad snapshot identity and unreadable pending storage fail closed', async () => {
  paymentRequest.mockResolvedValue({ ...snapshot, companyId: 3 }); readPending.mockImplementation(() => { throw new Error('Хранилище'); });
  const { result } = renderHook(() => useSupplierPaymentDialog(scope)); await ready(result); fill(result);
  await act(async () => result.current.submit()); expect(submitPayment).not.toHaveBeenCalled();
  expect(result.current.storageError).toContain('Хранилище');
});

test('fractional kopecks rejected, but early partial installments are not schedule capped', async () => {
  const { result } = renderHook(() => useSupplierPaymentDialog(scope)); await ready(result); fill(result);
  act(() => result.current.updateDraft({ amount: '10.001' }));
  await act(async () => result.current.submit()); expect(submitPayment).not.toHaveBeenCalled();
  act(() => result.current.updateDraft({ amount: '150.00' })); submitPayment.mockResolvedValue({ operationId: 1 });
  await act(async () => result.current.submit()); expect(submitPayment).toHaveBeenCalledTimes(1);
});

test('canonical history may include operations originally submitted through a paired warehouse', async () => {
  paymentRequest.mockImplementation(async (_api, _company, path) => path.includes('payment-documents') ? snapshot : {
    ...history, items: [{ companyId: 2, documentKind: 'warehouse', documentId: 7, operationId: 1 }] });
  const { result } = renderHook(() => useSupplierPaymentDialog(scope)); await ready(result);
  expect(result.current.error).toBe('');
  expect(result.current.history.items).toHaveLength(1);
});

test.each([
  ['user', { userId: 5 }],
  ['document ID', { documentId: 8 }],
  ['document kind', { documentKind: 'invoice' }],
])('%s change aborts old mutation, resets draft and rejects captured handlers/completion', async (_name, change) => {
  const response = deferred(); submitPayment.mockReturnValue(response.promise);
  const onSuccess = jest.fn();
  const { result, rerender } = renderHook(props => useSupplierPaymentDialog({ ...props, onSuccess }), { initialProps: scope });
  await ready(result); fill(result);
  const oldSubmit = result.current.submit;
  let send; act(() => { send = oldSubmit(); });
  const oldSignal = submitPayment.mock.calls[0][0].signal;
  const nextScope = { ...scope, ...change };
  const nextSnapshot = { ...snapshot, documentKind: nextScope.documentKind, documentId: nextScope.documentId,
    canonicalTarget: { documentKind: 'invoice', documentId: 19 } };
  paymentRequest.mockImplementation(async (_api, _company, path) => path.includes('payment-documents') ? nextSnapshot : history);
  rerender(nextScope); await ready(result);
  expect(oldSignal.aborted).toBe(true);
  expect(result.current.draft).toEqual({ amount: '', paidAt: '', reason: '' });
  expect(readPending).toHaveBeenLastCalledWith({ userId: nextScope.userId, companyId: 2 });
  await act(async () => { response.resolve({ operationId: 1 }); await send; await oldSubmit(); });
  expect(submitPayment).toHaveBeenCalledTimes(1);
  expect(onSuccess).not.toHaveBeenCalled();
  expect(result.current.success).toBeNull();
  expect(result.current.snapshot).toEqual(nextSnapshot);
  fill(result); submitPayment.mockResolvedValue({ operationId: 2 });
  await act(async () => result.current.submit());
  expect(submitPayment.mock.calls[1][0]).toMatchObject({ userId: nextScope.userId, companyId: 2,
    input: { documentKind: 'invoice', documentId: 19 } });
  expect(onSuccess).toHaveBeenCalledTimes(1);
});

test('StrictMode effect replay aborts first load, ignores its late result and submits only once', async () => {
  const firstLoad = deferred();
  paymentRequest.mockImplementationOnce(() => firstLoad.promise);
  const onSuccess = jest.fn();
  const { result } = renderHook(() => useSupplierPaymentDialog({ ...scope, onSuccess }), { reactStrictMode: true });
  await ready(result);
  const firstSignal = paymentRequest.mock.calls[0][3].signal;
  expect(firstSignal.aborted).toBe(true);
  expect(paymentRequest.mock.calls[1][3].signal.aborted).toBe(false);
  expect(result.current.snapshot).toEqual(snapshot);
  await act(async () => firstLoad.resolve({ ...snapshot, remainingAmount: '1.00' }));
  expect(result.current.snapshot.remainingAmount).toBe('200.00');
  expect(submitPayment).not.toHaveBeenCalled();
  fill(result); submitPayment.mockResolvedValue({ operationId: 1 });
  await act(async () => { const send = result.current.submit; await send(); await send(); });
  expect(submitPayment).toHaveBeenCalledTimes(1);
  expect(submitPayment.mock.calls[0][0].signal.aborted).toBe(false);
  expect(onSuccess).toHaveBeenCalledTimes(1);
});

test('network write failure explains uncertain result and preserves exact retry command', async () => {
  submitPayment.mockImplementationOnce(async () => { readPending.mockReturnValue(pending); throw new TypeError('Failed to fetch'); });
  const { result } = renderHook(() => useSupplierPaymentDialog(scope)); await ready(result); fill(result);
  await act(async () => result.current.submit());
  expect(result.current.error).toBe('Связь прервалась. Результат операции не подтверждён; повторите сохранённый запрос.');
  expect(result.current.pending).toEqual(pending);
  expect(result.current.draft.amount).toBe('10,01');
});

test('network read failure asks to refresh rather than retry a nonexistent payment', async () => {
  paymentRequest.mockRejectedValue(new TypeError('Failed to fetch'));
  const { result } = renderHook(() => useSupplierPaymentDialog(scope)); await ready(result);
  expect(result.current.error).toBe('Не удалось загрузить документ и историю. Проверьте связь и обновите данные.');
  expect(result.current.pending).toBeNull();
});

test('structured domain rejection keeps the server message', async () => {
  submitPayment.mockRejectedValue(Object.assign(new Error('Сумма превышает остаток долга.'), { status: 409 }));
  const { result } = renderHook(() => useSupplierPaymentDialog(scope)); await ready(result); fill(result);
  await act(async () => result.current.submit());
  expect(result.current.error).toBe('Сумма превышает остаток долга.');
});

const originalPayment = { operationId: 51, companyId: 2, documentKind: 'warehouse', documentId: 7,
  kind: 'payment', amount: '10.01', paidAt: '2026-09-17', reason: 'Поставка', reversedById: null };
async function reversalReady() {
  paymentRequest.mockImplementation(async (_api, _company, path) => path.includes('payment-documents') ? snapshot
    : { ...history, items: [originalPayment, { ...originalPayment, operationId: 52, reversedById: 53 },
      { ...originalPayment, operationId: 53, kind: 'reversal' }] });
  const view = renderHook(() => useSupplierPaymentDialog(scope)); await ready(view.result); return view;
}
test('reversal requires eligible history row and confirmation; uses origin identity without amount', async () => {
  const { result } = await reversalReady();
  for (const id of [999, 52, 53]) {
    act(() => result.current.beginReversal(id)); expect(result.current.reversal).toBeNull();
  }
  act(() => result.current.beginReversal(51));
  act(() => result.current.updateReversal({ paidAt: '2026-09-18', reason: 'Ошибка' }));
  await act(async () => result.current.submitReversal()); expect(submitPayment).not.toHaveBeenCalled();
  act(() => result.current.updateReversal({ confirmed: true }));
  submitPayment.mockResolvedValue({ operationId: 54, kind: 'reversal' });
  await act(async () => { const send = result.current.submitReversal; await send(); await send(); });
  expect(submitPayment).toHaveBeenCalledTimes(1);
  expect(submitPayment.mock.calls[0][0].input).toEqual({ kind: 'reversal', documentKind: 'warehouse', documentId: 7,
    reversesId: 51, paidAt: '2026-09-18', reason: 'Ошибка' });
  expect(result.current.success.kind).toBe('reversal');
  expect(originalPayment.reversedById).toBeNull();
});
test('cancelling a reversal draft dispatches nothing and invalidates its captured submit handler', async () => {
  const { result } = await reversalReady();
  act(() => result.current.beginReversal(51));
  act(() => result.current.updateReversal({ paidAt: '2026-09-18', reason: 'Ошибка', confirmed: true }));
  const staleSend = result.current.submitReversal;
  act(() => result.current.cancelReversal());
  expect(result.current.reversal).toBeNull();
  await act(async () => staleSend()); expect(submitPayment).not.toHaveBeenCalled();
});

test('attempt cancellation requires confirmation, retires on success and preserves response identity', async () => {
  readPending.mockReturnValue(pending);
  const { result } = renderHook(() => useSupplierPaymentDialog(scope)); await ready(result);
  await act(async () => result.current.cancelPending()); expect(cancelPendingPayment).not.toHaveBeenCalled();
  act(() => result.current.confirmCancellation(true));
  cancelPendingPayment.mockImplementation(async () => { readPending.mockReturnValue(null); return {
    status: 'confirmed', companyId: 2, requestId: pending.body.requestId, documentKind: 'invoice', documentId: 9, kind: 'payment',
    result: { operationId: 81, projectPaymentId: 91, kind: 'payment', amount: '10.01' } }; });
  await act(async () => { const cancel = result.current.cancelPending; await cancel(); await cancel(); });
  expect(cancelPendingPayment).toHaveBeenCalledTimes(1);
  expect(cancelPendingPayment.mock.calls[0][0].expectedBody).toEqual(pending.body);
  expect(cancelPendingPayment.mock.calls[0][0]).not.toHaveProperty('input');
  expect(result.current.success).toMatchObject({ companyId: 2, documentKind: 'invoice', documentId: 9,
    requestId: pending.body.requestId, kind: 'payment', operationId: 81 });
});

test('marked cancellation blocks original retry and permits cancellation retry without a new confirmation', async () => {
  readPending.mockReturnValue({ ...pending, cancelRequested: true });
  const { result } = renderHook(() => useSupplierPaymentDialog(scope)); await ready(result);
  await act(async () => result.current.retry()); expect(submitPayment).not.toHaveBeenCalled();
  cancelPendingPayment.mockRejectedValue(new TypeError('Failed to fetch'));
  await act(async () => result.current.cancelPending());
  expect(cancelPendingPayment).toHaveBeenCalledTimes(1);
  expect(result.current.error).toBe('Связь прервалась. Отмена попытки не подтверждена; повторите отмену попытки.');
  expect(result.current.pending.cancelRequested).toBe(true);
});
