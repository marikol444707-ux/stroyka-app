import { previewOpening, readOpeningPending, submitOpening } from './openingClient';
import { withSupplierPaymentContext } from './paymentClient';
const scope = { API: '/api', userId: 7, companyId: 2, invoiceId: 12 };
const preview = { companyId: 2, invoiceId: 12, amount: '200.00', openingPaid: '50.00',
  remainingAmount: '150.00', newCashAmount: '0.00', reviewedHash: 'a'.repeat(64) };
const requestId = '12345678-1234-4234-8234-123456789abc';
const result = { companyId: 2, invoiceId: 12, requestId, confirmationId: 1,
  amount: '200.00', openingPaid: '50.00', newCashAmount: '0.00' };
let storage, fetcher, options;
const response = (data, status = 200) => ({ ok: status === 200, status, json: async () => data });
beforeEach(() => {
  const data = new Map();
  storage = { getItem: key => data.get(key) ?? null, setItem: (key, value) => data.set(key, value), removeItem: key => data.delete(key) };
  fetcher = jest.fn(async () => response(result));
  options = { scope, preview, reason: 'Сверено', storage, fetcher, uuid: () => requestId,
    locks: { request: (key, config, work) => work({ name: key }) } };
});
test('checks preview context and exact balance', async () => {
  await expect(previewOpening(scope, { fetcher: async () => response(preview) })).resolves.toEqual(preview);
  for (const change of [{ companyId: 3 }, { remainingAmount: '151.00' }, { openingPaid: 50 }, { newCashAmount: '50.00' }]) {
    await expect(previewOpening(scope, { fetcher: async () => response({ ...preview, ...change }) })).rejects.toThrow();
  }
});
test('saves before POST and never sends a new payment amount', async () => {
  fetcher.mockImplementation(async (url, init) => {
    expect(url).toBe('/api/companies/2/supplier-opening-confirmations');
    expect(JSON.parse(init.body)).toEqual(readOpeningPending(scope, storage).body);
    expect(JSON.parse(init.body)).not.toHaveProperty('amount');
    return response(result);
  });
  await expect(submitOpening(options)).resolves.toEqual(result);
  expect(readOpeningPending(scope, storage)).toBeNull();
});
test('network failure keeps the same command across reopening and retry', async () => {
  fetcher.mockRejectedValueOnce(new TypeError('offline'));
  await expect(submitOpening(options)).rejects.toThrow('offline');
  const saved = readOpeningPending(scope, storage);
  expect(readOpeningPending({ ...scope, companyId: 3 }, storage)).toBeNull();
  expect(readOpeningPending({ ...scope, userId: 8 }, storage)).toBeNull();
  await submitOpening({ ...options, expectedPending: saved, uuid: () => { throw new Error('Must not generate another UUID'); } });
  expect(fetcher.mock.calls[0][1].body).toEqual(fetcher.mock.calls[1][1].body);
});
test.each([503, 403])('uncertain/restricted status %s retains the request', async status => {
  fetcher.mockResolvedValue(response({ detail: 'Недоступно' }, status));
  await expect(submitOpening(options)).rejects.toThrow();
  expect(readOpeningPending(scope, storage)).not.toBeNull();
});
test('definite conflict permits a fresh review; does not retry automatically', async () => {
  fetcher.mockResolvedValue(response({ detail: 'Счёт изменился' }, 409));
  await expect(submitOpening(options)).rejects.toThrow('Счёт изменился');
  expect(readOpeningPending(scope, storage)).toBeNull();
  expect(fetcher).toHaveBeenCalledTimes(1);
});
test('foreign result retains the saved attempt', async () => {
  fetcher.mockResolvedValue(response({ ...result, invoiceId: 99 }));
  await expect(submitOpening(options)).rejects.toThrow('не подтверждён');
  expect(readOpeningPending(scope, storage)).not.toBeNull();
});
test('storage failure and busy tab prevent sending', async () => {
  await expect(submitOpening({ ...options, storage: { ...storage, setItem: () => { throw new Error('full'); } } })).rejects.toThrow();
  await expect(submitOpening({ ...options, locks: { request: (_, __, work) => work(null) } })).rejects.toThrow();
  expect(fetcher).not.toHaveBeenCalled();
});
test('global context wrapper preserves explicit company for opening routes', () => {
  const init = withSupplierPaymentContext('/companies/2/supplier-opening-confirmations', { headers: { 'X-Company-Id': '9' } });
  expect(init.headers.get('X-Company-Id')).toBe('2');
  expect(init.headers.get('X-Company-Mode')).toBe('company');
});
