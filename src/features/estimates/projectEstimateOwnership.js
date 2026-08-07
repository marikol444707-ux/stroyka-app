export const positiveStoredId = (value) => {
  if (typeof value === 'number') {
    return Number.isSafeInteger(value) && value > 0 ? value : null;
  }
  if (typeof value !== 'string') return null;
  const normalized = value.trim();
  if (!/^[1-9][0-9]*$/.test(normalized)) return null;
  const parsed = Number(normalized);
  return Number.isSafeInteger(parsed) ? parsed : null;
};

export const sameStoredProjectOwner = (project, estimate) => {
  const companyId = positiveStoredId(project?.companyId);
  const projectId = positiveStoredId(project?.id);
  if (companyId === null || projectId === null) return false;
  if (
    estimate?.projectName !== undefined
    && (
      typeof estimate.projectName !== 'string'
      || typeof project?.name !== 'string'
      || estimate.projectName !== project.name
    )
  ) return false;
  return positiveStoredId(estimate?.companyId) === companyId
    && positiveStoredId(estimate?.projectId) === projectId;
};
