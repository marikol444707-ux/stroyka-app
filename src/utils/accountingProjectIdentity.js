const positiveId = value => {
  if (typeof value !== 'number' && !(typeof value === 'string' && /^\d+$/.test(value))) return null;
  const id = Number(value);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
};

// Display grouping only. This never assigns ownership or writes an allocation.
export function createAccountingProjectResolver(projects = [], companies = []) {
  const byId = new Map();
  const byCompanyName = new Map();
  const companyNames = new Map();
  for (const company of companies || []) {
    const id = positiveId(company.companyId ?? company.id);
    if (id) companyNames.set(id, company.companyName || company.name || `Компания #${id}`);
  }
  for (const project of projects || []) {
    const id = positiveId(project.id);
    const companyId = positiveId(project.companyId ?? project.company_id);
    if (!id || !companyId) continue;
    const name = String(project.name || '').trim();
    const row = { id, companyId, name };
    byId.set(id, [...(byId.get(id) || []), row]);
    const nameKey = JSON.stringify([companyId, name]);
    byCompanyName.set(nameKey, [...(byCompanyName.get(nameKey) || []), row]);
  }
  return (row, name) => {
    const companyId = positiveId(row.companyId ?? row.company_id);
    const rawProjectId = row.projectId ?? row.project_id;
    const projectId = positiveId(rawProjectId);
    const projectName = String(name || '').trim() || 'Без объекта';
    const base = { companyId, projectId: null, projectName, needsReview: true,
      companyLabel: companyId ? companyNames.get(companyId) || `Компания #${companyId}` : 'Компания не определена' };
    if (!companyId) return { ...base, key: JSON.stringify(['unassigned', projectId, projectName]) };
    const hasProjectId = rawProjectId != null && rawProjectId !== '';
    const matches = hasProjectId ? byId.get(projectId) || []
      : byCompanyName.get(JSON.stringify([companyId, String(name || '').trim()])) || [];
    const match = matches.length === 1 && matches[0].companyId === companyId
      && byId.get(matches[0].id)?.length === 1 ? matches[0] : null;
    if (match) return { ...base, key: JSON.stringify([companyId, 'project', match.id]),
      projectId: match.id, projectName: match.name || projectName, needsReview: !hasProjectId };
    return { ...base, key: JSON.stringify([companyId, 'unresolved', hasProjectId ? String(rawProjectId) : null, projectName]) };
  };
}
