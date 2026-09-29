import { buildProjectObjectLinks } from './projectObjectLinksUtils';
import { qualityJournalScopeKey } from './qualityJournalScope';
import { getQualityJournalRevision } from './qualityJournalEvents';

const project = { id: 11, companyId: 2, name: 'Школа' };
const user = { id: 7, role: 'директор' };
const companyContext = { mode: 'company', selectedCompanyId: 2, companies: [{ companyId: 2, role: 'директор' }] };
const ready = { scopeKey: qualityJournalScopeKey(companyContext, user), status: 'ready', complete: true, revision: getQualityJournalRevision() };
const owned = { id: 1, companyId: 2, projectId: 11, projectName: 'Старое имя' };
const journalLink = changes => buildProjectObjectLinks({ project, user, companyContext, C: { warning: 'warning' },
  qualityJournalLoadState: { inspections: ready, cables: ready }, ...changes }).find(item => item.key === 'journals');

test('journal links use exact company and project IDs, not names, and exclude cancelled rows', () => {
  const rows = [owned, { ...owned, id: 2, companyId: 3, projectName: project.name },
    { ...owned, id: 3, projectId: 12, projectName: project.name }, { ...owned, id: 4, status: 'Аннулирована' }];
  expect(journalLink({ materialInspections: rows, cableJournal: rows })).toMatchObject({
    count: 2, hint: 'АОСР 0, входной 1, кабель 1', status: 'ожидают проверки/монтажа: 2',
  });
});

test.each([undefined, {}, { inspections: ready }, { inspections: { ...ready, complete: false }, cables: ready },
  { inspections: { ...ready, status: 'error', error: 'HTTP 409' }, cables: ready },
  { inspections: ready, cables: { ...ready, scopeKey: 'old-company' } },
  { inspections: ready, cables: { ...ready, revision: ready.revision - 1 } }])('unconfirmed load state never becomes a zero count: %j', qualityJournalLoadState => {
  const result = journalLink({ qualityJournalLoadState });
  expect(result.count).toBe('—');
  expect(result.color).toBe('warning');
  expect(result.status).toMatch(/не подтвержден/i);
  expect(result.hint).not.toMatch(/входной 0|кабель 0/);
});

test.each([{ projectName: 'Школа' }, { companyId: 2, projectName: 'Школа' },
  { ...owned, company_id: 3 }, { ...owned, projectId: true }, { ...owned, projectId: 11.5 }])(
  'unproven row ownership is explicitly unconfirmed: %j', row => {
    expect(journalLink({ materialInspections: [row] }).count).toBe('—');
  });

test('confirmed empty snapshot remains a genuine zero', () => {
  expect(journalLink({})).toMatchObject({ count: 0, hint: 'АОСР 0, входной 0, кабель 0' });
});

test('missing project identity or different selected company remains unconfirmed', () => {
  expect(journalLink({ project: { name: 'Школа', companyId: 2 } }).count).toBe('—');
  expect(journalLink({ project: { ...project, companyId: 3 } }).count).toBe('—');
  expect(journalLink({ project: { ...project, project_id: 12 } }).count).toBe('—');
});

test('snake-case ownership is accepted only when both exact IDs are proven', () => {
  expect(journalLink({ materialInspections: [{ id: 1, company_id: 2, project_id: 11 }] }).count).toBe(1);
});
