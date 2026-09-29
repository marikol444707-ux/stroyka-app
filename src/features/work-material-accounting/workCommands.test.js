import { pendingWorkBatch, sendWorkBatch, resumeWorkBatch, clearWorkBatch, abandonRejectedWorkTail } from './workCommands';

const scope = { companyId: 3, userId: 9 };
const commands = [
  { path: '/work-journal', method: 'POST', payload: { description: 'Монтаж', quantity: 2 } },
  { path: '/estimates/4', method: 'PUT', payload: { sections: [] } },
];
beforeAll(() => { Object.defineProperty(window, 'crypto', { configurable: true, value: require('crypto').webcrypto }); });
beforeEach(() => { sessionStorage.clear(); });

test('lost reply keeps exact command and resume does not resend completed work', async () => {
  const sent = [];
  const fetchFn = jest.fn(async (url, options) => {
    sent.push(JSON.parse(options.body));
    if (sent.length === 2) throw new Error('connection lost');
    return { ok: true, json: async () => url.endsWith('work-journal') ? { id: 11 } : { ok: true } };
  });
  await expect(sendWorkBatch({ API: '/api', scope, commands, fetchFn })).rejects.toThrow('connection lost');
  expect(pendingWorkBatch(scope).next).toBe(1);
  const second = sent[1];
  await resumeWorkBatch({ API: '/api', scope, fetchFn });
  expect(sent).toHaveLength(3);
  expect(sent[2]).toEqual(second);
  expect(sent[2].materialAccountingVersion).toBe(2);
  expect(sent[2].requestId).toMatch(/^[0-9a-f-]{36}$/);
  expect(pendingWorkBatch(scope).next).toBe(2);
  clearWorkBatch(scope);
  expect(pendingWorkBatch(scope)).toBeNull();
});

test('pending batch blocks new work even with changed contents and isolates actor/company', async () => {
  const fetchFn = jest.fn(async () => { throw new Error('offline'); });
  await expect(sendWorkBatch({ API: '/api', scope, commands, fetchFn })).rejects.toThrow('offline');
  await expect(sendWorkBatch({ API: '/api', scope, commands: commands.slice(0, 1), fetchFn })).rejects.toThrow(/повтор/i);
  expect(fetchFn).toHaveBeenCalledTimes(1);
  expect(pendingWorkBatch({ companyId: 4, userId: 9 })).toBeNull();
  expect(pendingWorkBatch({ companyId: 3, userId: 10 })).toBeNull();
});

test('first known rejection clears unsaved batch; ambiguous retry rejection preserves it', async () => {
  const rejected = async () => ({ ok: false, status: 400, json: async () => ({ detail: 'Недостаточно' }) });
  await expect(sendWorkBatch({ API: '/api', scope, commands, fetchFn: rejected })).rejects.toThrow('Недостаточно');
  expect(pendingWorkBatch(scope)).toBeNull();
  await expect(sendWorkBatch({ API: '/api', scope, commands, fetchFn: async () => { throw new Error('offline'); } })).rejects.toThrow();
  await expect(resumeWorkBatch({ API: '/api', scope, fetchFn: rejected })).rejects.toThrow();
  expect(pendingWorkBatch(scope)).not.toBeNull();
});

test('invalid successful response is unknown outcome and cannot be cleared', async () => {
  await expect(sendWorkBatch({ API: '/api', scope, commands, fetchFn: async () => ({ ok: true, json: async () => ({}) }) })).rejects.toThrow(/ответ/i);
  expect(pendingWorkBatch(scope).next).toBe(0);
  expect(() => clearWorkBatch(scope)).toThrow();
});

test('storage failure prevents any request', async () => {
  const spy = jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('storage blocked'); });
  const fetchFn = jest.fn();
  await expect(sendWorkBatch({ API: '/api', scope, commands, fetchFn })).rejects.toThrow();
  expect(fetchFn).not.toHaveBeenCalled();
  spy.mockRestore();
});

test('definitively rejected tail can be abandoned after partial success without resending committed work', async () => {
  const fetchFn = jest.fn(async url => url.endsWith('work-journal')
    ? { ok: true, json: async () => ({ id: 11 }) }
    : { ok: false, status: 409, json: async () => ({ detail: 'Объём уже отправлен' }) });
  await expect(sendWorkBatch({ API: '/api', scope, commands, fetchFn })).rejects.toThrow('Объём уже отправлен');
  expect(pendingWorkBatch(scope).rejected).toBe(true);
  abandonRejectedWorkTail(scope);
  expect(pendingWorkBatch(scope)).toBeNull();
  expect(fetchFn).toHaveBeenCalledTimes(2);
});

test('unknown outcome cannot be abandoned, including after retry gets an authorization error', async () => {
  await expect(sendWorkBatch({ API: '/api', scope, commands, fetchFn: async () => { throw new Error('offline'); } })).rejects.toThrow();
  await expect(resumeWorkBatch({ API: '/api', scope, fetchFn: async () => ({ ok: false, status: 403, json: async () => ({}) }) })).rejects.toThrow();
  expect(() => abandonRejectedWorkTail(scope)).toThrow();
  expect(pendingWorkBatch(scope)).not.toBeNull();
});
