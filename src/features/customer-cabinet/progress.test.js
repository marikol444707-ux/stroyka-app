import { customerProgress } from './progress';

const project = { id: 3, companyId: 2, progress: 40, budget: 100000 };
const estimates = [{ id: 7, sectionsLoaded: true, sections: [{ name: 'Works', items: [{ name: 'Wall', quantity: 10, priceWork: 100 }] }] }];
const entry = { projectId: 3, companyId: 2, status: 'Подтверждено', estimateItemKey: '7:0:0', quantity: 3 };
test('progress uses confirmed quantities, not estimate done or internal spending', () => {
  const result = customerProgress(project, estimates, [entry, { ...entry, status: 'На проверке', quantity: 7 }, { ...entry, companyId: 9 }]);
  expect(result).toMatchObject({ percent: 30, plan: 1000, done: 300, source: 'confirmed' });
});
test('completion cannot exceed the planned quantity', () => {
  expect(customerProgress(project, estimates, [{ ...entry, quantity: 30 }]).percent).toBe(100);
});
test('unlinked confirmed works make the calculated progress unknown', () => {
  expect(customerProgress(project, estimates, [{ ...entry, estimateItemKey: '' }]).percent).toBeNull();
  expect(customerProgress(project, estimates, [entry, { ...entry, unexpectedWorkId: 9 }]).percent).toBeNull();
});
test('summary or partial estimates never produce a manual or partial percentage', () => {
  expect(customerProgress(project, [{ id: 8, sectionsLoaded: false }], []).percent).toBeNull();
  expect(customerProgress(project, [...estimates, { id: 8, sectionsLoaded: false, workPackage: 'Other' }], [entry]).percent).toBeNull();
});
test('multiple active estimates for one package cannot produce a percentage', () => {
  expect(customerProgress(project, [...estimates, { ...estimates[0], id: 8 }], [entry]).percent).toBeNull();
});
test('without a priced plan the stored assessment is explicitly manual', () => {
  expect(customerProgress(project, [], [])).toMatchObject({ percent: 40, source: 'manual' });
  expect(customerProgress({ ...project, progress: null }, [], []).percent).toBeNull();
});

const stableEstimates = (field, key) => [{ ...estimates[0], sections: [{ name: 'Works', items: [
  { ...estimates[0].sections[0].items[0], [field]: key },
] }] }];

test.each(['id', 'workKey'])('confirmed master work resolves item.%s within its estimate', field => {
  const scoped = { ...entry, estimateId: 7, estimateItemKey: 'master-work-1' };
  expect(customerProgress(project, stableEstimates(field, 'master-work-1'), [scoped]))
    .toMatchObject({ percent: 30, plan: 1000, done: 300, source: 'confirmed' });
});

test.each(['id', 'workKey'])('stable item.%s requires the exact estimateId', field => {
  for (const estimateId of [undefined, null, '', 0, 8]) {
    const result = customerProgress(project, stableEstimates(field, 'master-work-1'), [
      { ...entry, estimateId, estimateItemKey: 'master-work-1' },
    ]);
    expect(result).toMatchObject({ percent: null, done: null, source: 'unlinked' });
  }
});

test.each(['id', 'workKey'])('repeated item.%s in one estimate is ambiguous', field => {
  const ambiguous = stableEstimates(field, 'master-work-1');
  ambiguous[0].sections[0].items.push({ ...ambiguous[0].sections[0].items[0], priceWork: 900 });
  expect(customerProgress(project, ambiguous, [{ ...entry, estimateId: 7, estimateItemKey: 'master-work-1' }]))
    .toMatchObject({ percent: null, done: null, source: 'unlinked' });
});

test('an id matching another line workKey cannot silently choose a progress line', () => {
  const ambiguous = stableEstimates('id', 'master-work-1');
  ambiguous[0].sections[0].items.push({ name: 'Other', quantity: 10, priceWork: 900, workKey: 'master-work-1' });
  expect(customerProgress(project, ambiguous, [{ ...entry, estimateId: 7, estimateItemKey: 'master-work-1' }]).percent).toBeNull();
});

test('same stable key in different estimates uses the journal estimate scope', () => {
  const scoped = stableEstimates('id', 'master-work-1');
  scoped.push({ ...scoped[0], id: 8, workPackage: 'Other', sections: [{ name: 'Works', items: [
    { id: 'master-work-1', name: 'Other', quantity: 10, priceWork: 300 },
  ] }] });
  expect(customerProgress(project, scoped, [{ ...entry, estimateId: 8, estimateItemKey: 'master-work-1' }]))
    .toMatchObject({ plan: 4000, done: 900, percent: 23, source: 'confirmed' });
});

test('legacy position and stable aliases contribute once to the same planned line', () => {
  const scoped = stableEstimates('id', 'master-work-1');
  scoped[0].sections[0].items[0].workKey = 'normalized-work-1';
  expect(customerProgress(project, scoped, [
    { ...entry, quantity: 1 },
    { ...entry, estimateId: 7, estimateItemKey: 'master-work-1', quantity: 1 },
    { ...entry, estimateId: 7, estimateItemKey: 'normalized-work-1', quantity: 1 },
  ])).toMatchObject({ plan: 1000, done: 300, percent: 30, source: 'confirmed' });
});
