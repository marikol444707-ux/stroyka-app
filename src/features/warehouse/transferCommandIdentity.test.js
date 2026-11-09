import { readTransferCommand, saveTransferCommand, clearTransferCommand, transferPath } from './distributionCommands';
const command = () => { const payload = { companyId: 2, allocationId: 8, toProjectId: 13, quantity: '2', reason: 'Перемещение' };
  return { id: 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee', path: transferPath, payload, signature: JSON.stringify({ path: transferPath, ...payload }), draftRevision: 3 }; };
beforeEach(() => sessionStorage.clear());
test('unconfirmed transfer is isolated by user and company', () => {
  const value = command(); saveTransferCommand(2, value, 10);
  expect(readTransferCommand(2, 10)).toEqual(value); expect(readTransferCommand(2, 11)).toBeNull(); expect(readTransferCommand(3, 10)).toBeNull();
  clearTransferCommand(2, value.id, 11); expect(readTransferCommand(2, 10)).toEqual(value);
});
test('old unowned pending transfer fails closed for new signed in user', () => {
  saveTransferCommand(2, command()); expect(() => readTransferCommand(2, 10)).toThrow(/Сначала сверьте/);
  expect(sessionStorage.getItem('warehouse-transfers.pending.v1.2')).not.toBeNull();
});
test.each([0, -1, 1.5, '3', null])('invalid saved draft revision %s is rejected before replay', draftRevision => {
  saveTransferCommand(2, { ...command(), draftRevision }, 10);
  expect(() => readTransferCommand(2, 10)).toThrow(/повреждено/);
});
