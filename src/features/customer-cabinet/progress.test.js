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
