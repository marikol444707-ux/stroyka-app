import { acknowledgedPayment, pruneDefectDraft } from './ledgerDrafts';

const path = '/work-journal/11';
const photos = ['/uploads/synthetic-defect.jpg'];
const reason = 'Повреждение материала';
const copy = value => JSON.parse(JSON.stringify(value));
const freeze = value => {
  if (value && typeof value === 'object') {
    Object.values(value).forEach(freeze);
    Object.freeze(value);
  }
  return value;
};
const defect = (payload = {}, commandPath = path + '/material-defects') => ({
  path: commandPath, method: 'POST',
  payload: { reason, photos: [...photos], items: [{ entryId: 22, quantity: '0.5' }], ...payload },
});
const draft = changes => ({ reason, photos: [...photos], quantities: { 22: '0.5' }, ...changes });
const payment = changes => ({ path: '/brigade-payments', method: 'POST', payload: {
  contractId: 4, actId: 55, amount: '6.00', paidDate: '2026-09-18', ...changes,
} });

test('a completed defect clears matching fields and quantities without mutating either input', () => {
  const batch = freeze({ next: 1, commands: [defect()] });
  const current = freeze(draft({ quantities: { 22: '0.5', 99: '2' } }));
  const batchBefore = copy(batch);
  const draftBefore = copy(current);
  expect(pruneDefectDraft(batch, path, current)).toEqual({ reason: '', photos: [], quantities: { 99: '2' } });
  expect(batch).toEqual(batchBefore);
  expect(current).toEqual(draftBefore);
});

test('only the completed prefix clears entries while the rejected tail remains a draft', () => {
  const tail = defect({ reason: 'Новая причина', items: [{ entryId: 33, quantity: '2' }] });
  const current = draft({ reason: 'Новая причина', quantities: { 22: '0.5', 33: '2' } });
  const result = pruneDefectDraft({ next: 1, rejected: true, commands: [defect(), tail] }, path, current);
  expect(result).toEqual({ reason: 'Новая причина', photos: [], quantities: { 33: '2' } });
});

test('edits to reason, photos and quantities made after an unknown reply survive its recovery', () => {
  const current = draft({ reason: 'Уточнённая причина', photos: [...photos, '/uploads/added-later.jpg'],
    quantities: { 22: '0.75', 99: '2' } });
  expect(pruneDefectDraft({ next: 1, commands: [defect()] }, path, current)).toEqual(current);
});

test('matching fields are cleared independently of edited fields in the same defect form', () => {
  const current = draft({ photos: ['/uploads/replacement.jpg'], quantities: { 22: '0.75', 23: '1', 99: '2' } });
  const batch = { next: 1, commands: [defect({ items: [{ entryId: 22, quantity: '0.5' }, { entryId: 23, quantity: 1 }] })] };
  expect(pruneDefectDraft(batch, path, current)).toEqual({
    reason: '', photos: ['/uploads/replacement.jpg'], quantities: { 22: '0.75', 99: '2' },
  });
});

test('an attempted defect with an unknown result does not clear anything until acknowledged', () => {
  const current = draft();
  const commands = [{ ...defect(), attempted: true }];
  expect(pruneDefectDraft({ next: 0, commands }, path, current)).toEqual(current);
  expect(pruneDefectDraft({ next: 1, commands }, path, current)).toEqual({ reason: '', photos: [], quantities: {} });
});

test('completed operations for another work or another command cannot clear this defect form', () => {
  const current = draft();
  const commands = [defect({}, '/work-journal/12/material-defects'), defect({}, path + '/material-corrections')];
  expect(pruneDefectDraft({ next: 2, commands }, path, current)).toEqual(current);
});

test('quantity comparison follows the recorded string value and preserves a changed representation', () => {
  const current = draft({ quantities: { 22: '0.5', 23: '0.50' } });
  const commands = [defect({ items: [{ entryId: 22, quantity: 0.5 }, { entryId: 23, quantity: 0.5 }] })];
  expect(pruneDefectDraft({ next: 1, commands }, path, current)).toEqual({ reason: '', photos: [], quantities: { 23: '0.50' } });
});

test('a payment is acknowledged only when its own command is in the completed prefix', () => {
  const batch = freeze({ next: 1, commands: [payment({ actId: 56 }), payment()] });
  expect(acknowledgedPayment(batch, 4, 55, '6.00', '2026-09-18')).toBe(false);
  expect(acknowledgedPayment({ ...batch, next: 2 }, 4, 55, '6.00', '2026-09-18')).toBe(true);
  expect(acknowledgedPayment({ next: 0, commands: [payment()] }, 4, 55, '6.00', '2026-09-18')).toBe(false);
});

test.each([
  ['another contract', { contractId: 5 }],
  ['another act', { actId: 56 }],
  ['edited amount', { amount: '7.00' }],
  ['edited date', { paidDate: '2026-09-19' }],
])('completed payment for %s cannot acknowledge the current payment draft', (_label, changes) => {
  expect(acknowledgedPayment({ next: 1, commands: [payment(changes)] }, 4, 55, '6.00', '2026-09-18')).toBe(false);
});

test('an identical payload sent to a different endpoint cannot acknowledge payment', () => {
  const command = { ...payment(), path: '/brigade-contracts/4/acts' };
  expect(acknowledgedPayment({ next: 1, commands: [command] }, 4, 55, '6.00', '2026-09-18')).toBe(false);
});
