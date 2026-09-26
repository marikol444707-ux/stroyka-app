import { cancelPendingPayment, paymentPath, readPending, submitPayment, withSupplierPaymentContext } from './paymentClient';

const scope = { userId: 7, companyId: 2 };
const requestId = '12345678-1234-4234-8234-123456789abc';
const input = { kind: 'payment', documentKind: 'invoice', documentId: 12,
  amount: '10,20', paidAt: '2026-09-18', reason: 'Частичная оплата' };
const result = { ...scope, requestId, documentKind: 'invoice', documentId: 12,
  operationId: 1, projectPaymentId: 2, kind: 'payment', amount: '10.20' };
const locks = { request: (name, options, work) => work({ name }) };
let storage, fetcher, options;
beforeEach(() => {
  const values = new Map();
  storage = { getItem: jest.fn(key => values.get(key) ?? null),
    setItem: jest.fn((key, value) => values.set(key, value)), removeItem: jest.fn(key => values.delete(key)) };
  fetcher = jest.fn(async () => ({ ok: true, json: async () => result }));
  options = { ...scope, API: '', input, storage, fetcher, locks, uuid: () => requestId,
    expectedBody: { ...input, requestId, amount: '10.20' } };
});

test('persists exact command before the only POST, clears only verified success', async () => {
  fetcher.mockImplementation(async (path, init) => {
    expect(readPending(scope, storage).body).toEqual(JSON.parse(init.body));
    expect(JSON.parse(init.body).amount).toBe('10.20');
    expect(init.credentials).toBe('include');
    return { ok: true, json: async () => result };
  });
  expect(await submitPayment(options)).toEqual(result);
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(fetcher.mock.calls[0][0]).toBe(paymentPath(2));
  expect(readPending(scope, storage)).toBeNull();
});

test('lost response survives reload and retry sends the identical UUID/body', async () => {
  fetcher.mockRejectedValueOnce(new Error('Lost response'));
  await expect(submitPayment(options)).rejects.toThrow('Lost response');
  const saved = readPending(scope, storage);
  await expect(submitPayment({ ...options, input: { ...input, amount: '90' } })).rejects.toThrow();
  expect(fetcher).toHaveBeenCalledTimes(1);
  await submitPayment({ ...options, retry: true, input: undefined, uuid: () => { throw Error('New UUID forbidden'); } });
  expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual(saved.body);
  expect(readPending(scope, storage)).toBeNull();
});

test.each([403, 409, 422, 500])('HTTP %s never discards an uncertain pending command', async status => {
  fetcher.mockResolvedValue({ ok: false, status, json: async () => ({ detail: 'Rejected' }) });
  await expect(submitPayment(options)).rejects.toMatchObject({ status });
  expect(readPending(scope, storage).body.requestId).toBe(requestId);
});

test.each([{ companyId: 3 }, { requestId: 'wrong' }, { documentId: 13 }, { amount: '10.21' },
  { kind: 'reversal' }, { operationId: null }])('mismatched success remains pending: %j', changes => {
  fetcher.mockResolvedValue({ ok: true, json: async () => ({ ...result, ...changes }) });
  return expect(submitPayment(options)).rejects.toThrow().then(() => {
    expect(readPending(scope, storage)).not.toBeNull();
  });
});

test('blocked or unavailable durable storage prevents dispatch', async () => {
  storage.setItem.mockImplementation(() => { throw Error('Quota'); });
  await expect(submitPayment(options)).rejects.toThrow();
  expect(fetcher).not.toHaveBeenCalled();
});

test('missing cross-tab lock or busy tab prevents dispatch', async () => {
  await expect(submitPayment({ ...options, locks: null })).rejects.toThrow();
  await expect(submitPayment({ ...options, locks: { request: (name, opts, work) => work(null) } })).rejects.toThrow();
  expect(fetcher).not.toHaveBeenCalled();
});

test('pending commands are isolated by actor and company', async () => {
  fetcher.mockRejectedValue(new Error('Offline'));
  await expect(submitPayment(options)).rejects.toThrow();
  expect(readPending({ ...scope, userId: 8 }, storage)).toBeNull();
  expect(readPending({ ...scope, companyId: 3 }, storage)).toBeNull();
});

test('captured company wins over mutable global headers only on payment paths', () => {
  const init = { headers: { 'X-Company-Id': '99', 'X-Company-Mode': 'all', 'X-CSRF-Token': 'synthetic' } };
  const scoped = withSupplierPaymentContext('/companies/2/supplier-payments?limit=50', init);
  expect(scoped.headers.get('X-Company-Id')).toBe('2');
  expect(scoped.headers.get('X-Company-Mode')).toBe('company');
  expect(scoped.headers.get('X-CSRF-Token')).toBe('synthetic');
  expect(withSupplierPaymentContext('/companies/2/other', init)).toBe(init);
});

test('invalid money and impossible dates are rejected without storage or network writes', async () => {
  for (const change of [{ amount: '0' }, { amount: '1.001' }, { paidAt: '2026-02-31' },
    { documentId: -1 }, { kind: 'reversal', reversesId: 1 }]) {
    await expect(submitPayment({ ...options, input: { ...input, ...change } })).rejects.toThrow();
  }
  expect(fetcher).not.toHaveBeenCalled();
  expect(storage.setItem).not.toHaveBeenCalled();
});

test('reversal uses the original operation, never a client supplied amount', async () => {
  const reversal = { kind: 'reversal', documentKind: 'invoice', documentId: 12,
    reversesId: 4, paidAt: input.paidAt, reason: 'Исправление ошибочного платежа' };
  fetcher.mockResolvedValue({ ok: true, json: async () => ({ ...result, kind: 'reversal' }) });
  await submitPayment({ ...options, input: reversal });
  expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({ ...reversal, requestId });
  expect(readPending(scope, storage)).toBeNull();
});

test.each(['{broken', JSON.stringify({ version: 1, ...scope, body: { ...input, requestId, documentId: -1 } })])(
  'corrupted pending storage blocks both a fresh command and retry', async raw => {
    storage.setItem('supplier-payment:v1:7:2', raw);
    await expect(submitPayment(options)).rejects.toThrow();
    await expect(submitPayment({ ...options, retry: true })).rejects.toThrow();
    expect(fetcher).not.toHaveBeenCalled();
    expect(storage.removeItem).not.toHaveBeenCalled();
  });

test('changed pending storage during dispatch is never cleared by an older response', async () => {
  fetcher.mockImplementation(async () => {
    const changed = readPending(scope, storage);
    changed.body.reason = 'Другая сохранённая операция';
    storage.setItem('supplier-payment:v1:7:2', JSON.stringify(changed));
    return { ok: true, json: async () => result };
  });
  await expect(submitPayment(options)).rejects.toThrow('изменилась');
  expect(readPending(scope, storage).body.reason).toBe('Другая сохранённая операция');
  expect(storage.removeItem).not.toHaveBeenCalled();
});

test('overlapping submissions across tabs do not queue a second payment', async () => {
  let active = false, finish;
  const contendedLocks = { request: async (name, opts, work) => {
    expect(opts.ifAvailable).toBe(true);
    if (active) return work(null);
    active = true;
    try { return await work({ name }); } finally { active = false; }
  } };
  fetcher.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  const first = submitPayment({ ...options, locks: contendedLocks });
  await expect(submitPayment({ ...options, locks: contendedLocks })).rejects.toThrow('другой вкладке');
  expect(fetcher).toHaveBeenCalledTimes(1);
  finish({ ok: true, json: async () => result });
  await first;
  expect(readPending(scope, storage)).toBeNull();
});

async function saveUncertain() {
  fetcher.mockRejectedValueOnce(new Error('Lost response'));
  await expect(submitPayment(options)).rejects.toThrow();
}

test('cancellation persists intent before POST and clears only committed cancellation', async () => {
  await saveUncertain();
  const body = readPending(scope, storage).body;
  fetcher.mockImplementation(async (path, init) => {
    expect(path).toBe(paymentPath(2) + '/cancel-request');
    expect(readPending(scope, storage).cancelRequested).toBe(true);
    expect(JSON.parse(init.body)).toEqual(body);
    return { ok: true, json: async () => ({ ...result, status: 'cancelled', cancelledAt: '2026-09-18T08:00:00Z' }) };
  });
  expect((await cancelPendingPayment(options)).status).toBe('cancelled');
  expect(readPending(scope, storage)).toBeNull();
});

test('lost cancellation response retains exact intent and original retry is blocked', async () => {
  await saveUncertain();
  fetcher.mockRejectedValue(new Error('Cancellation response lost'));
  await expect(cancelPendingPayment(options)).rejects.toThrow();
  const saved = readPending(scope, storage);
  expect(saved.cancelRequested).toBe(true);
  await expect(submitPayment({ ...options, retry: true })).rejects.toThrow('отмен');
  expect(fetcher).toHaveBeenCalledTimes(2);
  await expect(cancelPendingPayment(options)).rejects.toThrow();
  expect(JSON.parse(fetcher.mock.calls[2][1].body)).toEqual(saved.body);
});

test('cancel after committed payment returns verified confirmation, not reversal', async () => {
  await saveUncertain();
  fetcher.mockResolvedValue({ ok: true, json: async () => ({ ...result, status: 'confirmed', result }) });
  expect((await cancelPendingPayment(options)).status).toBe('confirmed');
  expect(readPending(scope, storage)).toBeNull();
});

test.each([{ status: 'not_found' }, { status: 'cancelled', requestId: 'different' },
  { status: 'cancelled', companyId: 3 }, { status: 'confirmed', result: { ...result, amount: '99.00' } }])(
  'unverified cancellation response keeps pending: %j', async change => {
    await saveUncertain();
    fetcher.mockResolvedValue({ ok: true, json: async () => ({ ...result,
      cancelledAt: '2026-09-18T08:00:00Z', ...change }) });
    await expect(cancelPendingPayment(options)).rejects.toThrow();
    expect(readPending(scope, storage)).not.toBeNull();
  });

test('typed server cancellation error exposes code and Russian message', async () => {
  fetcher.mockResolvedValue({ ok: false, status: 409,
    json: async () => ({ detail: { code: 'request_cancelled', message: 'Попытка отменена' } }) });
  await expect(submitPayment(options)).rejects.toMatchObject({ code: 'request_cancelled', message: 'Попытка отменена' });
});

test('cancellation storage failure prevents dispatch and preserves the original intent', async () => {
  await saveUncertain();
  storage.setItem.mockImplementation(() => { throw new Error('Storage denied'); });
  await expect(cancelPendingPayment(options)).rejects.toThrow('Storage denied');
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(readPending(scope, storage).cancelRequested).toBeUndefined();
});

test('cancellation and original retry contend for the same cross-tab lock', async () => {
  await saveUncertain();
  let active = false, finish;
  const contendedLocks = { request: async (name, opts, work) => {
    expect(name).toBe('supplier-payment:v1:7:2');
    expect(opts.ifAvailable).toBe(true);
    if (active) return work(null);
    active = true;
    try { return await work({ name }); } finally { active = false; }
  } };
  fetcher.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  const cancel = cancelPendingPayment({ ...options, locks: contendedLocks });
  await expect(submitPayment({ ...options, retry: true, locks: contendedLocks })).rejects.toThrow('другой вкладке');
  expect(fetcher).toHaveBeenCalledTimes(2);
  finish({ ok: true, json: async () => ({ ...result, status: 'cancelled', cancelledAt: '2026-09-18T08:00:00Z' }) });
  await cancel;
  expect(readPending(scope, storage)).toBeNull();
});

test.each(['cancel', 'retry'])('a changed command between UI confirmation and lock blocks %s', async action => {
  await saveUncertain();
  const saved = readPending(scope, storage);
  for (const change of [{ requestId: '22345678-1234-4234-8234-123456789abc' }, { amount: '11.00' }]) {
    storage.setItem('supplier-payment:v1:7:2', JSON.stringify({ ...saved, body: { ...saved.body, ...change } }));
    const invoke = action === 'cancel' ? cancelPendingPayment(options) : submitPayment({ ...options, retry: true });
    await expect(invoke).rejects.toThrow('изменилась');
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(readPending(scope, storage).cancelRequested).toBeUndefined();
  }
});
