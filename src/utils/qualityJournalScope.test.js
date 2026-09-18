import { resolveQualityJournalProject, selectQualityJournalRows } from './qualityJournalScope';
import { qualityJournalScopeKey, qualityJournalLoadIssue } from './qualityJournalScope';
import { beginQualityJournalMutation, finishQualityJournalMutation, notifyQualityJournalMutation, getQualityJournalRevision } from './qualityJournalEvents';
import { createDocumentActions } from '../features/documents/documentActions';

const project = { id: 11, companyId: 2, name: 'Школа' };
const owned = { id: 1, companyId: 2, projectId: 11, projectName: 'Старое имя' };

test('even a current-revision ready snapshot cannot export during a pending write', () => {
  const user = { id: 1 };
  const context = { mode: 'company', selectedCompanyId: 2, companies: [{ companyId: 2, role: 'директор' }] };
  const token = beginQualityJournalMutation();
  try {
    const ready = { scopeKey: qualityJournalScopeKey(context, user), revision: getQualityJournalRevision(), status: 'ready', complete: true };
    expect(qualityJournalLoadIssue({ inspections: ready, cables: ready }, project, context, user)).toMatch(/выполняется/);
  } finally {
    finishQualityJournalMutation(token, { confirmed: false, uncertain: false });
  }
});

test('a committed mutation immediately blocks an old export snapshot before React rerenders', () => {
  const user = { id: 41 };
  const context = { mode: 'company', selectedCompanyId: 2, companies: [{ companyId: 2, role: 'директор' }] };
  const snapshot = { scopeKey: qualityJournalScopeKey(context, user), status: 'ready', complete: true,
    revision: getQualityJournalRevision() };
  const state = { inspections: snapshot, cables: snapshot };
  expect(qualityJournalLoadIssue(state, project, context, user)).toBe('');
  notifyQualityJournalMutation();
  expect(qualityJournalLoadIssue(state, project, context, user)).toMatch(/изменён|обнов/i);
});

test('missing, failed, partial and old-scope journal states block every quality export action', () => {
  const companyContext = { mode: 'company', selectedCompanyId: 2, companies: [{ companyId: 2, role: 'директор' }] };
  const user = { id: 1 };
  const scopeKey = qualityJournalScopeKey(companyContext, user);
  const ready = { scopeKey, status: 'ready', complete: true, revision: getQualityJournalRevision() };
  for (const incomplete of [undefined, { ...ready, status: 'error', error: '5000 записей' }, { ...ready, complete: false }, { ...ready, scopeKey: 'old' }]) {
    const qualityJournalLoadState = { inspections: incomplete, cables: incomplete };
    expect(qualityJournalLoadIssue(qualityJournalLoadState, project, companyContext, user)).toBeTruthy();
    const actions = createDocumentActions({ projects: [project], user, companyContext, qualityJournalLoadState });
    expect(() => actions.buildMaterialInspectionContent([], project, '', '')).toThrow();
    expect(() => actions.buildCableJournalContent([], project, '', '')).toThrow();
    expect(() => actions.buildJPRContent(project)).toThrow();
    expect(() => actions.buildExecPackageContent(project)).toThrow();
  }
  const qualityJournalLoadState = { inspections: ready, cables: ready };
  expect(qualityJournalLoadIssue(qualityJournalLoadState, project, companyContext, user)).toBe('');
  expect(qualityJournalLoadIssue(qualityJournalLoadState, { ...project, companyId: 3 }, companyContext, user)).toBeTruthy();
  const actions = createDocumentActions({ projects: [project], user, companyContext, qualityJournalLoadState });
  expect(actions.buildCableJournalContent([], project, '', '')).toContain('ЖУРНАЛ');
});

test('owned journals match both IDs even after project rename', () => {
  expect(selectQualityJournalRows([owned], project)).toEqual([owned]);
  expect(selectQualityJournalRows([{ ...owned, companyId: '2', projectId: '11' }], project)).toHaveLength(1);
});

test('annulled receipts are not active journal rows even with matching ownership or legacy name', () => {
  expect(selectQualityJournalRows([
    owned, { ...owned, id: 2, status: 'Аннулирована' },
    { id: 3, projectName: 'Школа', status: 'Аннулирована' },
  ], project)).toEqual([owned]);
});

test.each([
  { companyId: 3, projectId: 11 }, { companyId: 2, projectId: 12 },
  { companyId: 2 }, { projectId: 11 }, { companyId: 2, projectId: null },
  { companyId: '', projectId: '' }, { companyId: false, projectId: 11 },
  { companyId: 2, projectId: 0 }, { companyId: 2, projectId: '11x' },
])('same name never rescues foreign, partial or invalid ownership: %j', ownership => {
  expect(selectQualityJournalRows([{ projectName: 'Школа', ...ownership }], project)).toEqual([]);
});

test('legacy name matching applies only with both ownership fields absent/null', () => {
  const legacy = { id: 2, projectName: 'Школа' };
  const unowned = { ...legacy, companyId: null, projectId: null };
  expect(selectQualityJournalRows([legacy, unowned, { projectName: 'Больница' }], project)).toEqual([legacy, unowned]);
});

test('missing project ownership cannot select owned rows', () => {
  expect(selectQualityJournalRows([{ ...owned, projectName: 'Школа' }], { name: 'Школа' })).toEqual([]);
});

test('snake-case ownership is supported and conflicting aliases fail closed', () => {
  const row = { company_id: 2, project_id: 11, projectName: 'Школа' };
  expect(selectQualityJournalRows([row], { id: '11', company_id: '2', name: 'Школа' })).toEqual([row]);
  expect(selectQualityJournalRows([{ ...row, companyId: 3 }], project)).toEqual([]);
  expect(selectQualityJournalRows([owned], { ...project, company_id: 3 })).toEqual([]);
});

test('explicit project identity is preserved; a name resolves only uniquely', () => {
  const other = { id: 12, companyId: 3, name: 'Школа' };
  expect(resolveQualityJournalProject(project, [project, other])).toBe(project);
  expect(resolveQualityJournalProject('Школа', [project])).toBe(project);
  expect(() => resolveQualityJournalProject('Школа', [project, other])).toThrow(/неоднознач/i);
  expect(() => resolveQualityJournalProject('Школа', [project, { ...other, companyId: 2 }])).toThrow(/неоднознач/i);
});

test('unknown legacy name does not infer ownership from journal rows', () => {
  const selected = resolveQualityJournalProject('Школа', []);
  const legacy = { projectName: 'Школа' };
  expect(selectQualityJournalRows([{ ...owned, projectName: 'Школа' }, legacy], selected)).toEqual([legacy]);
  expect(selectQualityJournalRows(null, selected)).toEqual([]);
});
