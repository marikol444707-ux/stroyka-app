const ESTIMATE_LEADERSHIP_ROLES = new Set(['директор', 'зам_директора']);

export function estimateRoleForContext(user, companyContext) {
  if (companyContext?.mode === 'company') {
    return companyContext?.selectedCompany?.role || user?.role || '';
  }
  return user?.role || '';
}

export function canManageEstimateForContext(user, companyContext) {
  if (companyContext?.mode === 'all_companies') return false;
  return ESTIMATE_LEADERSHIP_ROLES.has(estimateRoleForContext(user, companyContext));
}
