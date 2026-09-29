import { clearWorkBatch, pendingWorkBatch, resumeWorkBatch, sendWorkBatch } from './workCommands';

const scope = { companyId: 4, userId: 7 };
const ledgerCommands = [
  { path: '/work-journal/11/material-corrections', method: 'POST',
    payload: { entryId: 22, quantity: '0.5', expectedQuantity: '1', reason: 'Исправление расхода' } },
  { path: '/work-journal/11/material-defects', method: 'POST',
    payload: { reason: 'Брак', photos: ['/uploads/synthetic.jpg'], items: [{ entryId: 22, quantity: '0.5' }] } },
  { path: '/work-journal/11/material-defects/33/decisions', method: 'POST',
    payload: { decision: 'confirmed', reason: 'Подтверждено', contractEvidence: 'Договор № 4',
      valuations: [{ entryId: 22, unitPrice: '10.00', priceEvidence: 'Накладная № 8' }] } },
  { path: '/brigade-contracts/4/acts', method: 'POST',
    payload: { workJournalIds: [11], expectedGrossAmount: '10.00', expectedFineAmount: '4.00',
      fineAllocations: [{ defectId: 33, decisionId: 44, amount: '4.00' }],
      periodFrom: '2026-09-18', periodTo: '2026-09-18' } },
  { path: '/brigade-contracts/4/acts/55/signature', method: 'POST',
    payload: { scanUrl: '/uploads/synthetic-signed.jpg' } },
  { path: '/brigade-payments', method: 'POST',
    payload: { contractId: 4, actId: 55, amount: '6.00', paidDate: '2026-09-18' } },
];
const success = result => ({ ok: true, status: 200, json: async () => result });
beforeAll(() => {
  Object.defineProperty(window, 'crypto', { configurable: true, value: require('crypto').webcrypto });
});
beforeEach(() => sessionStorage.clear());

test.each(ledgerCommands)('accepts and completes the scoped ledger command $path', async command => {
  const original = JSON.parse(JSON.stringify(command));
  const fetchFn = jest.fn(async () => success({ ok: true, id: 123 }));
  const batch = await sendWorkBatch({ API: '/api', scope, commands: [command], fetchFn });
  expect(batch.next).toBe(1);
  expect(fetchFn).toHaveBeenCalledTimes(1);
  const [url, options] = fetchFn.mock.calls[0];
  expect(url).toBe('/api' + command.path);
  expect(options.method).toBe('POST');
  expect(options.credentials).toBe('include');
  expect(options.headers).toEqual(expect.objectContaining({ 'X-Company-Mode': 'company', 'X-Company-Id': '4' }));
  expect(JSON.parse(options.body)).toEqual({ ...command.payload,
    expectedCompanyId: 4, expectedActorId: 7, materialAccountingVersion: 2,
    requestId: expect.stringMatching(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/),
  });
  expect(command).toEqual(original);
  clearWorkBatch(scope);
  expect(pendingWorkBatch(scope)).toBeNull();
});

test.each([
  ['PUT', '/work-journal/11/material-corrections'],
  ['GET', '/work-journal/11/material-defects'],
  ['DELETE', '/work-journal/11/material-defects/33/decisions'],
  ['PUT', '/brigade-contracts/4/acts'],
  ['GET', '/brigade-contracts/4/acts/55/signature'],
  ['DELETE', '/brigade-payments'],
  ['POST', '/work-journal/0/material-corrections'],
  ['POST', '/work-journal/11/material-defects/0/decisions'],
  ['POST', '/work-journal/11/material-defects/33/decisions/extra'],
  ['POST', '/brigade-contracts/4/acts/55'],
  ['POST', '/brigade-contracts/4/acts/55/signature?companyId=8'],
  ['POST', 'https://other.invalid/brigade-payments'],
])('rejects unsupported method/path %s %s before any HTTP request', async (method, path) => {
  const fetchFn = jest.fn();
  await expect(sendWorkBatch({ API: '/api', scope, commands: [{ method, path, payload: {} }], fetchFn })).rejects.toThrow();
  expect(fetchFn).not.toHaveBeenCalled();
});

test.each(ledgerCommands)('an unknown successful reply for $path retries the same command and requestId', async command => {
  const fetchFn = jest.fn()
    .mockResolvedValueOnce(success({}))
    .mockResolvedValueOnce(success({ ok: true, id: 123 }));
  await expect(sendWorkBatch({ API: '/api', scope, commands: [command], fetchFn })).rejects.toThrow(/ответ/i);
  expect(pendingWorkBatch(scope).next).toBe(0);
  expect(() => clearWorkBatch(scope)).toThrow();
  const savedBody = fetchFn.mock.calls[0][1].body;
  await resumeWorkBatch({ API: '/api', scope, fetchFn });
  expect(fetchFn).toHaveBeenCalledTimes(2);
  expect(fetchFn.mock.calls[1][1].body).toBe(savedBody);
  expect(pendingWorkBatch(scope).next).toBe(1);
});

test('a lost payment reply resumes with the original id and the server fake records exactly one payment', async () => {
  const payments = new Map();
  const debitAmounts = [];
  let loseFirstReply = true;
  const fetchFn = jest.fn(async (url, options) => {
    expect(url).toBe('/api/brigade-payments');
    const payload = JSON.parse(options.body);
    let receipt = payments.get(payload.requestId);
    if (!receipt) {
      receipt = { ok: true, id: 88, projectPaymentId: 99, actId: payload.actId };
      payments.set(payload.requestId, receipt);
      debitAmounts.push(payload.amount);
    }
    if (loseFirstReply) {
      loseFirstReply = false;
      throw new Error('reply lost after commit');
    }
    return success(receipt);
  });
  await expect(sendWorkBatch({ API: '/api', scope, commands: [ledgerCommands[5]], fetchFn })).rejects.toThrow('reply lost after commit');
  const savedId = pendingWorkBatch(scope).commands[0].payload.requestId;
  expect(payments.has(savedId)).toBe(true);
  await resumeWorkBatch({ API: '/api', scope, fetchFn });
  await resumeWorkBatch({ API: '/api', scope, fetchFn });
  expect(fetchFn).toHaveBeenCalledTimes(2);
  expect(fetchFn.mock.calls[1][1].body).toBe(fetchFn.mock.calls[0][1].body);
  expect(payments.size).toBe(1);
  expect(debitAmounts).toEqual(['6.00']);
  expect(pendingWorkBatch(scope).next).toBe(1);
  clearWorkBatch(scope);
  expect(pendingWorkBatch(scope)).toBeNull();
});
