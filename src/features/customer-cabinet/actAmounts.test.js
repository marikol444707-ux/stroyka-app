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

const stableEstimates = (field, key) => [{ ...estimates[0], sections: [{ name: 'Work', items: [
  { ...estimates[0].sections[0].items[0], [field]: key },
  { ...estimates[0].sections[0].items[1] },
] }] }];

test.each(['id', 'workKey'])('confirmed master work prices exact item.%s within its estimate', field => {
  const result = customerActRows(project, stableEstimates(field, 'master-work-1'), [
    { ...entry, estimateId: 7, estimateItemKey: 'master-work-1' },
  ], []);
  expect(result.sourceItems).toHaveLength(1);
  expect(result.sourceItems[0]).toMatchObject({ quantity: 0.25, pricePerUnit: 200, total: 50 });
});

test.each(['id', 'workKey'])('stable item.%s cannot be priced without the exact estimateId', field => {
  for (const estimateId of [undefined, null, '', 0, 8]) {
    expect(() => customerActRows(project, stableEstimates(field, 'master-work-1'), [
      { ...entry, estimateId, estimateItemKey: 'master-work-1' },
    ], [])).toThrow();
  }
});

test.each(['id', 'workKey'])('repeated item.%s in one estimate cannot produce an act', field => {
  const ambiguous = stableEstimates(field, 'master-work-1');
  ambiguous[0].sections[0].items[1][field] = 'master-work-1';
  expect(() => customerActRows(project, ambiguous, [
    { ...entry, estimateId: 7, estimateItemKey: 'master-work-1' },
  ], [])).toThrow();
});

test('an id matching another line workKey cannot silently choose an act price', () => {
  const ambiguous = stableEstimates('id', 'master-work-1');
  ambiguous[0].sections[0].items[1].workKey = 'master-work-1';
  expect(() => customerActRows(project, ambiguous, [
    { ...entry, estimateId: 7, estimateItemKey: 'master-work-1' },
  ], [])).toThrow();
});

test('same stable key in different estimates keeps quantities and prices separate', () => {
  const scoped = stableEstimates('id', 'master-work-1');
  scoped.push({ ...scoped[0], id: 8, workPackage: 'Other', sections: [{ name: 'Other', items: [
    { id: 'master-work-1', name: 'Other work', quantity: 5, priceWork: 900 },
  ] }] });
  const result = customerActRows(project, scoped, [
    { ...entry, estimateId: 7, estimateItemKey: 'master-work-1' },
    { ...entry, id: 2, estimateId: 8, estimateItemKey: 'master-work-1', quantity: 2 },
  ], []);
  expect(result.sourceItems).toHaveLength(2);
  expect(result.sourceItems).toEqual(expect.arrayContaining([
    expect.objectContaining({ quantity: 0.25, pricePerUnit: 200, total: 50 }),
    expect.objectContaining({ quantity: 2, pricePerUnit: 900, total: 1800 }),
  ]));
});

test('legacy position and stable aliases share one quantity and over-completion limit', () => {
  const scoped = stableEstimates('id', 'master-work-1');
  scoped[0].sections[0].items[0].workKey = 'normalized-work-1';
  const journal = [
    { ...entry, quantity: 0.1 },
    { ...entry, id: 2, estimateId: 7, estimateItemKey: 'master-work-1', quantity: 0.1 },
    { ...entry, id: 3, estimateId: 7, estimateItemKey: 'normalized-work-1', quantity: 0.05 },
  ];
  const result = customerActRows(project, scoped, journal, []);
  expect(result.sourceItems).toHaveLength(1);
  expect(result.sourceItems[0]).toMatchObject({ quantity: 0.25, pricePerUnit: 200, total: 50 });
  expect(() => customerActRows(project, scoped, [...journal, { ...entry, id: 4, quantity: 0.3 }], [])).toThrow();
});
