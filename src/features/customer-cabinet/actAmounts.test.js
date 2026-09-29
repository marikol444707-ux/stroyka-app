import { customerActRows } from './actAmounts';

const project = { id: 3, companyId: 2, name: 'Site' };
const estimates = [{ id: 7, companyId: 2, projectId: 3, sectionsLoaded: true, sections: [
  { name: 'Work', items: [{ name: 'Same name', quantity: 0.5, priceWork: 200 },
    { name: 'Same name', quantity: 5, priceWork: 900 }] },
] }];
const entry = { id: 1, companyId: 2, projectId: 3, status: 'Подтверждено', estimateItemKey: '7:0:0', quantity: 0.25 };

test('prices fractional quantities from their exact estimate line', () => {
  const rows = customerActRows(project, estimates, [entry], []);
  expect(rows.sourceItems[0]).toMatchObject({ quantity: 0.25, pricePerUnit: 200, total: 50 });
});
test('never guesses a line by its repeated name or stored done quantity', () => {
  expect(() => customerActRows(project, estimates, [{ ...entry, estimateItemKey: '', description: 'Same name' }], [])).toThrow();
  expect(customerActRows(project, estimates, [], []).sourceItems).toEqual([]);
});
test('approved extra work is billed only for its confirmed actual quantity', () => {
  const offer = { id: 9, companyId: 2, projectId: 3, status: 'Утверждено отдельной допработой',
    description: 'Extra', quantity: 4, price: 150, total: 600, changeType: 'Работа вне сметы' };
  expect(customerActRows(project, estimates, [], [offer]).outsideEstimateItems).toEqual([]);
  const result = customerActRows(project, estimates, [{ ...entry, unexpectedWorkId: 9, quantity: 2 }], [offer]);
  expect(result.outsideEstimateItems[0]).toMatchObject({ quantity: 2, pricePerUnit: 150, total: 300 });
});
test('unavailable terms and over-completed lines fail instead of understating the act', () => {
  expect(() => customerActRows(project, [{ ...estimates[0], sectionsLoaded: false }], [entry], [])).toThrow();
  expect(() => customerActRows(project, estimates, [{ ...entry, quantity: 1 }], [])).toThrow();
  expect(() => customerActRows(project, estimates, [{ ...entry, unexpectedWorkId: 99 }], [])).toThrow();
});
test('foreign and unconfirmed entries cannot contribute money', () => {
  expect(customerActRows(project, estimates, [{ ...entry, companyId: 4 }, { ...entry, status: 'На проверке' }], []).sourceItems).toEqual([]);
});
