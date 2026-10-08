import {brigadeBalance} from './brigadeBalance';

test('uses act net after fines instead of inventing debt from completed gross', () => {
  expect(brigadeBalance({settlementVersion: 2, doneAmount: 10000, paidAmount: 8000,
    settlementSummary: {grossAmount: 10000, fineAmount: 2000, netAmount: 8000, paidAmount: 8000, remainingAmount: 0}}))
    .toEqual({due: 8000, paid: 8000, remaining: 0, fine: 2000, known: true});
});

test('uses the server balance across multiple acts', () => {
  expect(brigadeBalance({settlementVersion: 2,
    settlementSummary: {netAmount: 10000, paidAmount: 3000, remainingAmount: 7000, fineAmount: 0}}).remaining).toBe(7000);
});

test('does not call work without an act a payable debt', () => {
  expect(brigadeBalance({settlementVersion: 2, doneAmount: 5000,
    settlementSummary: {netAmount: 0, paidAmount: 0, remainingAmount: 0, fineAmount: 0}}).due).toBe(0);
});

test('does not guess debt when authorized act summary is unavailable', () => {
  expect(brigadeBalance({settlementVersion: 2, doneAmount: 10000, paidAmount: 8000}).known).toBe(false);
});

test('preserves legacy contract calculation', () => {
  expect(brigadeBalance({settlementVersion: 1, doneAmount: 10000, paidAmount: 8000}))
    .toEqual({due: 10000, paid: 8000, remaining: 2000, fine: 0, known: true});
});

 test('does not silently mix unlinked historical money with canonical act payments', () => {
  expect(brigadeBalance({settlementVersion: 2, settlementSummary: {
    netAmount: 100, paidAmount: 0, remainingAmount: 100, fineAmount: 0, needsReconciliation: true}}).known).toBe(false);
});
