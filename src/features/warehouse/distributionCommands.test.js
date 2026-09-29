import { clearCommand, pendingCommand, saveCommand, validateCommandResult, validateList, readTransferCommand, saveTransferCommand, clearTransferCommand, validateTransferResult } from './distributionCommands';

const command = id => {
  const path = '/warehouse-distributions';
  const payload = { companyId: 2, reason: 'Проверка', rows: [{ lotId: 1, projectId: 2, quantity: '1' }] };
  return { id, path, payload, signature: JSON.stringify({ path, ...payload }) };
};
beforeEach(() => sessionStorage.clear());

test('transfer pending storage is independent, scoped, validated and compare-cleared', () => {
  const original = command('11111111-1111-4111-8111-111111111111');
  saveCommand(2, original);
  const transfer = { id: original.id, path: '/warehouse-distributions/transfers', payload: { companyId: 2, allocationId: 8, toProjectId: 13, reason: 'Отправка', quantity: '2' } };
  transfer.signature = JSON.stringify({ path: transfer.path, ...transfer.payload });
  saveTransferCommand(2, transfer);
  expect(readTransferCommand(2)).toEqual(transfer);
  expect(readTransferCommand(3)).toBeNull();
  clearTransferCommand(2, 'other'); expect(readTransferCommand(2)).toEqual(transfer);
  clearTransferCommand(2, transfer.id); expect(readTransferCommand(2)).toBeNull();
  expect(pendingCommand(2)).toEqual(original);
  saveTransferCommand(2, { ...transfer, payload: { ...transfer.payload, quantity: '-1' } });
  expect(() => readTransferCommand(2)).toThrow();
});
test('wrong transfer ID does not confirm a receipt', () => {
  expect(() => validateTransferResult({ ok: true, requestId: 'same', item: { id: 9 } }, { id: 'same', path: '/warehouse-distributions/transfers/8/receipts', payload: { companyId: 2 } })).toThrow();
});

const historyRow = id => ({ id, materialName: 'Кабель', unit: 'м', quantity: 2, returnedQuantity: 0, netQuantity: 2 });
test('pagination accepts legacy lists and validates descending cursor pages', () => {
  expect(validateList({ items: [historyRow(8)], truncated: true }).nextCursor).toBeUndefined();
  expect(validateList({ items: [historyRow(8)], truncated: true, nextCursor: 8 }).nextCursor).toBe(8);
  expect(validateList({ items: [], truncated: false, nextCursor: null }).items).toEqual([]);
});
test.each([undefined, null, 0, 1, 'false', {}, []])('cursor response rejects non-boolean truncated %p', truncated => {
  expect(() => validateList({ items: [historyRow(8)], nextCursor: null, truncated })).toThrow();
});
test.each([false, true])('cursor and truncated must agree for source=%p', source => {
  const items = source ? [{ lotId: 8, materialName: 'Кабель', unit: 'м', availableQuantity: 2 }] : [historyRow(8)];
  expect(() => validateList({ items, truncated: true, nextCursor: null }, source)).toThrow();
  expect(() => validateList({ items, truncated: false, nextCursor: 8 }, source)).toThrow();
  expect(() => validateList({ items: [], truncated: true, nextCursor: 8 }, source)).toThrow();
  expect(() => validateList({ items, truncated: true, nextCursor: 8 }, source)).not.toThrow();
  expect(() => validateList({ items, truncated: false, nextCursor: null }, source)).not.toThrow();
});
test('missing cursor remains compatible with legacy metadata', () => {
  for (const data of [{ items: [] }, { items: [], truncated: true }, { items: [], truncated: false }]) {
    expect(validateList(data)).toBe(data);
  }
});
test.each([0, -1, 1.5, '8', true, {}, 9])('malformed cursor %p fails closed', nextCursor => {
  expect(() => validateList({ items: [historyRow(8)], truncated: true, nextCursor })).toThrow();
});
test('pagination rejects empty continuation, unordered pages and non-advancing IDs', () => {
  for (const data of [{ items: [], nextCursor: 8 }, { items: [historyRow(7), historyRow(8)], nextCursor: null }, { items: [historyRow(8), historyRow(8)], nextCursor: 8 }]) {
    expect(() => validateList({ ...data, truncated: data.nextCursor !== null })).toThrow();
  }
  expect(() => validateList({ items: [historyRow(8)], truncated: false, nextCursor: null }, false, 8)).toThrow();
});

test('late completion cannot erase a newer pending operation', () => {
  const first = command('11111111-1111-4111-8111-111111111111');
  const second = command('22222222-2222-4222-8222-222222222222');
  saveCommand(2, second);
  clearCommand(2, first.id);
  expect(pendingCommand(2)).toEqual(second);
  clearCommand(2, second.id);
  expect(pendingCommand(2)).toBeNull();
});

test('stored payload is scoped and malformed rows fail closed', () => {
  const value = command('11111111-1111-4111-8111-111111111111');
  saveCommand(2, value);
  expect(pendingCommand(3)).toBeNull();
  value.payload.rows = {};
  saveCommand(2, value);
  expect(() => pendingCommand(2)).toThrow();
});

test('unknown or mismatched success is not a receipt', () => {
  const value = command('11111111-1111-4111-8111-111111111111');
  for (const data of [null, {}, { ok: false }, { ok: true, requestId: 'different', items: [{ id: 1 }] }, { ok: true, requestId: value.id, items: [] }]) {
    expect(() => validateCommandResult(data, value)).toThrow();
  }
  expect(() => validateCommandResult({ ok: true, requestId: value.id, items: [{ id: 1 }] }, value)).not.toThrow();
  expect(() => validateList({ items: [null] })).toThrow();
});
