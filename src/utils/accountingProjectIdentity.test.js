import { createAccountingProjectResolver } from './accountingProjectIdentity';

const projects = [{ id: 10, companyId: 2, name: 'Жилой комплекс' },
  { id: 20, companyId: 3, name: 'Жилой комплекс' }];

test('identical names in different companies are different groups', () => {
  const resolve = createAccountingProjectResolver(projects);
  const a = resolve({ companyId: 2 }, 'Жилой комплекс');
  const b = resolve({ companyId: 3 }, 'Жилой комплекс');
  expect(a.key).not.toBe(b.key);
  expect(a.projectId).toBe(10);
  expect(b.projectId).toBe(20);
  expect(a.needsReview).toBe(true); // display lookup is not persisted identity
});

test('stored project identity survives a renamed project', () => {
  const resolve = createAccountingProjectResolver(projects);
  const a = resolve({ companyId: 2, projectId: 10 }, 'Старое название');
  const b = resolve({ companyId: 2, projectId: 10 }, 'Жилой комплекс');
  expect(a.key).toBe(b.key);
  expect(a.projectName).toBe('Жилой комплекс');
  expect(a.needsReview).toBe(false);
});

test('duplicate names within a company never pick the first object', () => {
  const resolve = createAccountingProjectResolver([...projects, { id: 11, companyId: 2, name: 'Жилой комплекс' }]);
  const unknown = resolve({ companyId: 2 }, 'Жилой комплекс');
  expect(unknown.projectId).toBeNull();
  expect(unknown.needsReview).toBe(true);
  expect(unknown.key).not.toBe(resolve({ companyId: 2, projectId: 10 }, 'Жилой комплекс').key);
});

test('missing company is not inferred from a name or even a catalog project ID', () => {
  const resolve = createAccountingProjectResolver(projects);
  const row = resolve({ projectId: 10 }, 'Жилой комплекс');
  expect(row.companyId).toBeNull();
  expect(row.companyLabel).toBe('Компания не определена');
  expect(row.needsReview).toBe(true);
});

test('foreign or missing stored project does not fall back to its name', () => {
  const resolve = createAccountingProjectResolver(projects);
  for (const projectId of [20, 999]) {
    const row = resolve({ companyId: 2, projectId }, 'Жилой комплекс');
    expect(row.needsReview).toBe(true);
    expect(row.key).not.toBe(resolve({ companyId: 2, projectId: 10 }, 'Жилой комплекс').key);
  }
});

test('snake-case IDs and company labels are supported without coercing booleans', () => {
  const resolve = createAccountingProjectResolver(projects, [{ companyId: 2, companyName: 'Строй А' }]);
  expect(resolve({ company_id: '2', project_id: '10' }, '').companyLabel).toBe('Строй А');
  expect(resolve({ companyId: true }, '').companyId).toBeNull();
});
