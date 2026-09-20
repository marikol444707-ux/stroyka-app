const positiveId = value => (typeof value === 'number' || typeof value === 'string')
  && Number.isSafeInteger(Number(value)) && Number(value) > 0 ? Number(value) : null;

// Display selection only. The API must independently enforce the same ownership.
export function customerProject(projects, user = {}) {
  const assigned = user.project_id ?? user.projectId;
  const companyId = positiveId(user.company_id ?? user.companyId);
  const scoped = (Array.isArray(projects) ? projects : []).filter(project =>
    !companyId || positiveId(project.companyId ?? project.company_id) === companyId);
  if (assigned !== undefined && assigned !== null && assigned !== '') {
    const id = positiveId(assigned);
    if (!id) return null;
    const matches = scoped.filter(project => positiveId(project.id) === id);
    return matches.length === 1 ? matches[0] : null;
  }
  const name = String(user.project_name ?? user.projectName ?? '').trim();
  if (!name) return null;
  const matches = scoped.filter(project => String(project.name || '').trim() === name);
  return matches.length === 1 ? matches[0] : null;
}
