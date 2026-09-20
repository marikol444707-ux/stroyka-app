import { customerProject, customerRemark } from './projectSelection';
test('an exact assigned ID wins over an earlier matching name', () => {
  const projects = [{ id: 1, name: 'Лицей', companyId: 2 }, { id: 7, name: 'Лицей', companyId: 3 }];
  expect(customerProject(projects, { projectId: 7, projectName: 'Лицей', companyId: 3 })).toBe(projects[1]);
});
test('an unavailable assigned ID never falls back to its name', () => {
  expect(customerProject([{ id: 1, name: 'Лицей' }], { projectId: 7, projectName: 'Лицей' })).toBeNull();
});
test('legacy name requires an unambiguous scoped match', () => {
  const projects = [{ id: 1, name: 'Лицей', companyId: 2 }, { id: 7, name: 'Лицей', companyId: 3 }];
  expect(customerProject(projects, { projectName: 'Лицей' })).toBeNull();
  expect(customerProject(projects, { projectName: 'Лицей', companyId: 3 })).toBe(projects[1]);
});
test('company mismatch and missing assignment fail closed', () => {
  expect(customerProject([{ id: 7, companyId: 2 }], { projectId: 7, companyId: 3 })).toBeNull();
  expect(customerProject([{ id: 7, name: '' }], {})).toBeNull();
});

test('malformed assigned IDs do not select another project', () => {
  for (const projectId of [true, [], [1], {}, -1, 1.5]) {
    expect(customerProject([{ id: 1, name: 'Лицей' }], { projectId, projectName: 'Лицей' })).toBeNull();
  }
});

test('remarks use immutable ownership even when names coincide or change', () => {
  const project = { id: 1, companyId: 2, name: 'Новое название' };
  const user = { id: 9, name: 'Новое имя' };
  const row = { projectId: 1, companyId: 2, createdByUserId: 9, projectName: 'Старое название', issuedBy: 'Старое имя' };
  expect(customerRemark(row, project, user)).toBe(true);
  for (const changed of [{ companyId: 3 }, { projectId: 3 }, { createdByUserId: 10 }, { createdByUserId: null }]) {
    expect(customerRemark({ ...row, ...changed }, project, user)).toBe(false);
  }
});
