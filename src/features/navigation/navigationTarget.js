import { useEffect, useState } from 'react';

export const NAVIGATION_EVENT = 'stroyka:navigation';
const pages = { material: 'warehouse', tool: 'warehouse', estimate: 'estimates', document: 'projects' };
export const ownerId = row => String(row?.companyId ?? row?.company_id ?? '');
export const selectedCompanyId = (context, user) => context
  ? (context.mode === 'company' ? String(context.selectedCompanyId || '') : '')
  : ownerId(user);
export function readNavigationTarget(search = window.location.search) {
  const query = new URLSearchParams(search);
  const type = query.get('entityType');
  const id = query.get('entityId');
  const companyId = query.get('appCompanyId');
  if (!pages[type] || !/^[1-9]\d*$/.test(id || '') || !/^[1-9]\d*$/.test(companyId || '') || query.get('view') !== pages[type]) return null;
  const projectId = query.get('appProjectId');
  if (projectId && !/^[1-9]\d*$/.test(projectId)) return null;
  if (type === 'document' && !projectId) return null;
  return { type, id, companyId, projectId };
}
export function navigationHref({ type, id, companyId, projectId, projectTab }, base = window.location.href) {
  const url = new URL(base);
  ['entityType', 'entityId', 'appCompanyId', 'appProjectId', 'projectTab'].forEach(key => url.searchParams.delete(key));
  url.searchParams.set('view', pages[type] || 'projects');
  url.searchParams.set('entityType', type);
  url.searchParams.set('entityId', String(id));
  url.searchParams.set('appCompanyId', String(companyId));
  if (projectId) url.searchParams.set('appProjectId', String(projectId));
  if (type === 'document' || projectTab) url.searchParams.set('projectTab', type === 'document' ? '📁 Реестр' : projectTab);
  if (!readNavigationTarget(url.search)) return null;
  return url.pathname + url.search + url.hash;
}
export function useNavigationTarget() {
  const [search, setSearch] = useState(() => window.location.search);
  useEffect(() => {
    const changed = () => setSearch(window.location.search);
    window.addEventListener('popstate', changed);
    window.addEventListener(NAVIGATION_EVENT, changed);
    return () => { window.removeEventListener('popstate', changed); window.removeEventListener(NAVIGATION_EVENT, changed); };
  }, []);
  return readNavigationTarget(search);
}
export function clearNavigationTarget() {
  const url = new URL(window.location.href);
  url.searchParams.delete('entityId'); url.searchParams.delete('entityType');
  window.history.replaceState(window.history.state, '', url.pathname + url.search + url.hash);
  window.dispatchEvent(new Event(NAVIGATION_EVENT));
}
export function targetMatchesRow(target, row) {
  return !!target && String(row?.id) === target.id && ownerId(row) === target.companyId;
}

// Legacy documents can name an object only when that name resolves uniquely
// inside their authoritative company. A URL is never an ownership source.
export function targetMatchesProject(target, row, projects = []) {
  if (!target?.projectId) return true;
  const project = projects.find(p => String(p.id) === target.projectId && ownerId(p) === target.companyId);
  if (!project) return false;
  const exactId = row.projectId ?? row.project_id;
  if (exactId != null) return String(exactId) === target.projectId;
  const name = row.projectName || row.project;
  return name === project.name && projects.filter(p => ownerId(p) === target.companyId && p.name === name).length === 1;
}
