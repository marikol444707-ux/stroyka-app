import { getQualityJournalRevision, qualityJournalMutationIssue } from './qualityJournalEvents';

// Ownership is authoritative. Null/missing owners are the only legacy case;
// partial, invalid or conflicting ownership must never fall back to a name.
const normalizeId = value => {
  if (typeof value !== 'number' && (typeof value !== 'string' || !/^\d+$/.test(value))) return null;
  const id = Number(value);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
};

const ownerId = (row, camel, snake) => {
  const values = [row?.[camel], row?.[snake]].filter(value => value != null);
  const id = normalizeId(values[0]);
  return id !== null && values.every(value => normalizeId(value) === id) ? id : null;
};

export const resolveQualityJournalProject = (projectOrName, projects = []) => {
  if (projectOrName && typeof projectOrName === 'object') return projectOrName;
  const name = typeof projectOrName === 'string' ? projectOrName : '';
  const matches = (projects || []).filter(project => project.name === name);
  if (matches.length > 1) {
    throw new Error('Неоднозначное имя объекта для печати журнала. Выберите объект по companyId и projectId.');
  }
  // Do not infer ownership from rows or arbitrarily choose a same-name project.
  return matches[0] || { name };
};

export const selectQualityJournalRows = (rows, project) => {
  if (!project) return [];
  const companyId = ownerId(project, 'companyId', 'company_id');
  const projectId = normalizeId(project.id);
  return (rows || []).filter(row => {
    if (!row || row.status === 'Аннулирована') return false;
    const hasOwner = [row.companyId, row.company_id, row.projectId, row.project_id].some(value => value != null);
    if (!hasOwner) return row.projectName === project.name;
    return companyId !== null && projectId !== null
      && ownerId(row, 'companyId', 'company_id') === companyId
      && ownerId(row, 'projectId', 'project_id') === projectId;
  });
};

export const qualityJournalScopeKey = (context = {}, user) => {
  const companyId = normalizeId(context.selectedCompanyId);
  const member = context.companies?.find(item => Number(item.companyId) === companyId);
  if (!user?.id || context.mode !== 'company' || !companyId || context.loading || context.error
      || !member || member.active === false || member.companyActive === false) return null;
  return JSON.stringify([user.id, companyId, member.role, Boolean(context.readOnly || member.readOnly)]);
};

export const requireQualityJournalOwnership = (rows, selectedCompanyId) => {
  const companyId = normalizeId(selectedCompanyId);
  if (!companyId || rows.some(row => normalizeId(row?.companyId) !== companyId
      || normalizeId(row?.projectId) === null
      || ownerId(row, 'companyId', 'company_id') !== companyId
      || ownerId(row, 'projectId', 'project_id') !== normalizeId(row.projectId))) {
    throw new Error('Требуется миграция журналов: companyId/projectId отсутствуют или не соответствуют выбранной компании. Печать заблокирована.');
  }
};

export const qualityJournalLoadIssue = (state, project, context, user, kinds = ['inspections', 'cables']) => {
  const mutationIssue = qualityJournalMutationIssue();
  if (mutationIssue) return mutationIssue;
  const scopeKey = qualityJournalScopeKey(context, user);
  if (!scopeKey || ownerId(project, 'companyId', 'company_id') !== Number(context.selectedCompanyId)) {
    return 'Выберите одну компанию и объект: область журналов не подтверждена.';
  }
  for (const kind of kinds) {
    const load = state?.[kind];
    if (!load || load.scopeKey !== scopeKey) return 'Журналы для выбранной области ещё не загружены.';
    if (load.revision !== getQualityJournalRevision()) return 'Журнал изменён. Дождитесь обновления данных перед печатью.';
    if (load.status !== 'ready' || load.complete !== true) return load.error || 'Журналы загружаются или загружены не полностью. Печать и диагностика недоступны.';
  }
  return '';
};
