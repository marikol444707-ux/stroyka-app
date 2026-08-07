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

export const immutableStoredProjectOwner = (project) => {
  if (!project || typeof project !== 'object' || Array.isArray(project)) return null;
  const companyId = positiveStoredId(project.companyId);
  const id = positiveStoredId(project.id);
  const projectId = positiveStoredId(project.projectId);
  if (companyId === null || (id === null && projectId === null)) return null;
  if (id !== null && projectId !== null && id !== projectId) return null;

  const name = project.name;
  const projectName = project.projectName;
  if (name !== undefined && (typeof name !== 'string' || !name.trim())) return null;
  if (projectName !== undefined && (typeof projectName !== 'string' || !projectName.trim())) return null;
  if (name !== undefined && projectName !== undefined && name !== projectName) return null;
  const canonicalName = projectName ?? name;
  if (typeof canonicalName !== 'string' || !canonicalName.trim()) return null;

  return Object.freeze({
    companyId,
    projectId: projectId ?? id,
    projectName: canonicalName,
  });
};

export const uniqueStoredProjectForName = (projects, projectName) => {
  if (!Array.isArray(projects) || typeof projectName !== 'string' || !projectName) return null;
  const matches = projects.filter(project => project?.name === projectName);
  if (matches.length !== 1 || !immutableStoredProjectOwner(matches[0])) return null;
  return matches[0];
};

export const sameStoredProjectOwner = (project, estimate) => {
  const owner = immutableStoredProjectOwner(project);
  if (!owner) return false;
  if (
    estimate?.projectName !== undefined
    && (
      typeof estimate.projectName !== 'string'
      || estimate.projectName !== owner.projectName
    )
  ) return false;
  return positiveStoredId(estimate?.companyId) === owner.companyId
    && positiveStoredId(estimate?.projectId) === owner.projectId;
};
