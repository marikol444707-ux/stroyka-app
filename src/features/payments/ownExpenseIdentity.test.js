import { isOwnExpense } from './ownExpenseIdentity';

test('uses the server user link despite different staff id and changed display name', () => {
  expect(isOwnExpense({ employeeUserId: 42, employeeId: 23, employeeName: 'Старое имя' },
    { id: 42, name: 'Новое имя' })).toBe(true);
});
test('never treats an unrelated staff id as the current user id', () => {
  expect(isOwnExpense({ employeeId: 42, employeeName: 'Другой' }, { id: 42, name: 'Мастер' })).toBe(false);
});
test('does not override a different explicit user link with the same display name', () => {
  expect(isOwnExpense({ employeeUserId: 43, employeeName: 'Мастер' }, { id: 42, name: 'Мастер' })).toBe(false);
});
test('uses explicit staff linkage for older API responses', () => {
  expect(isOwnExpense({ employeeId: '23', employeeName: 'Старое имя' }, { id: 42, staffId: 23 })).toBe(true);
});
test('legacy name comparison handles surrounding whitespace and case', () => {
  expect(isOwnExpense({ employeeName: ' МАСТЕР ' }, { id: 42, name: 'Мастер' })).toBe(true);
});
