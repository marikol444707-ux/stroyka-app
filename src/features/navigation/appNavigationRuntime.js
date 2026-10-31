import { useEffect, useRef } from 'react';
import { NAVIGATION_EVENT, navigationHref, ownerId, selectedCompanyId } from './navigationTarget';
import {
  canAccessRole,
  isFinanceUser,
  selectableActiveProjectsForUser,
  visibleEstimatesForUser,
  visibleProjectsForUser,
} from '../../utils/accessUtils';

export function useAppNavigationRuntime({
  ROLES,
  actions = {},
  data = {},
  state = {},
}) {
  const {
    clients,
    materials,
    projects,
    tools,
  } = data;
  const {
    activePage, expandedProject, activeProjectTab,
    companyContext,
    globalSearch,
    isMobile,
    masterProjectId,
    user,
  } = state;
  const {
    loadPricelistItems,
    setActivePage, setActiveProjectTab,
    setEditingItem,
    setEditingPlItem,
    setExpandedClient,
    setExpandedProject,
    setGlobalSearch,
    setInlineEditPl,
    setMasterProjectId,
    setPricelistItems,
    setSelectedInventory,
    setSelectedPricelist,
    setSelectedWarehouseProject,
    setSelectedWorks,
    setShowArchive,
    setShowForm,
    setShowInvites,
    setShowOffers,
    setShowPiecework,
    setShowRoomForm,
    setShowSearch,
    setSidebarVisible,
  } = actions;

  const canAccess = (page) => canAccessRole(user, page, ROLES);
  const isFinanceRole = () => isFinanceUser(user);
  const visibleProjects = (list) => visibleProjectsForUser(list, user);
  const visibleEstimatesForCurrentUser = (list) => visibleEstimatesForUser(list, user);
  const selectableActiveProjects = (list = projects) => selectableActiveProjectsForUser(list || [], user);
  const visibleActiveProjects = (list = projects) => selectableActiveProjects(list || []);

  useEffect(() => {
    if (!user || !['мастер', 'субподрядчик', 'бригадир'].includes(user.role)) return;
    const options = selectableActiveProjects(projects);
    const currentOk = masterProjectId && options.some(project => String(project.id) === String(masterProjectId));
    if (currentOk) return;
    if (masterProjectId && !currentOk) {
      setMasterProjectId('');
      setSelectedWorks({});
      setPricelistItems([]);
    }
    if (options.length === 1) {
      const project = options[0];
      setMasterProjectId(String(project.id));
      setSelectedWorks({});
      if (project.pricelistId) loadPricelistItems(project.pricelistId);
      else setPricelistItems([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.role, user?.assignedProjects, user?.assigned_projects, projects, masterProjectId]);

  const companyId = selectedCompanyId(companyContext, user);
  const navigationActorKey = JSON.stringify([companyId, user?.id, user?.role, user?.companyId, user?.company_id, user?.assignedProjects, user?.assigned_projects]);
  const routeLoaded = useRef(false);
  const skipRouteSync = useRef(false);
  const writeRoute = (page, projectId, tab, push = false, target = {}) => {
    const url = new URL(window.location.href);
    if (push) { url.searchParams.delete('entityId'); url.searchParams.delete('entityType'); }
    if (companyId) url.searchParams.set('appCompanyId', companyId); else url.searchParams.delete('appCompanyId');
    if (page) url.searchParams.set('view', page); else url.searchParams.delete('view');
    if (projectId) url.searchParams.set('appProjectId', String(projectId)); else url.searchParams.delete('appProjectId');
    if (tab) url.searchParams.set('projectTab', tab); else url.searchParams.delete('projectTab');
    const next = target.entityType ? navigationHref({type:target.entityType, id:target.entityId, companyId, projectId, projectTab:tab}, url.href) : url.pathname + url.search + url.hash;
    if (!next) return;
    if (next !== window.location.pathname + window.location.search + window.location.hash) {
      window.history[push ? 'pushState' : 'replaceState'](window.history.state, '', next);
      window.dispatchEvent(new Event(NAVIGATION_EVENT));
    }
  };
  useEffect(() => {
    const restore = () => {
      if (!user) return;
      const url = new URL(window.location.href);
      const linkCompany = url.searchParams.get('appCompanyId');
      if (linkCompany && linkCompany !== companyId) {
        routeLoaded.current = false;
        setExpandedProject(null);
        const linkedPage = url.searchParams.get('view');
        if (linkedPage && canAccess(linkedPage)) setActivePage(linkedPage);
        return;
      }
      const page = url.searchParams.get('view');
      const projectId = url.searchParams.get('appProjectId');
      if (projectId && !(projects || []).length) return;
      skipRouteSync.current = true;
      routeLoaded.current = true;
      if (page && canAccess(page)) setActivePage(page);
      if (projectId) {
        const project = visibleProjects(projects || []).find(item => String(item.id) === projectId && (!ownerId(item) || ownerId(item) === companyId));
        setExpandedProject(project?.id ?? null);
      } else if (page) setExpandedProject(null);
      const tab = url.searchParams.get('projectTab');
      if (tab && typeof setActiveProjectTab === 'function') setActiveProjectTab(tab);
    };
    restore();
    window.addEventListener('popstate', restore);
    return () => window.removeEventListener('popstate', restore);
    // The current authorized project list validates restored IDs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navigationActorKey, projects]);
  useEffect(() => {
    if (!routeLoaded.current) return;
    if (skipRouteSync.current) { skipRouteSync.current = false; return; }
    writeRoute(activePage, expandedProject, activeProjectTab);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activePage, expandedProject, activeProjectTab]);

  const navigateTo = (page, target = {}) => {
    if (!canAccess(page) || (target.companyId && String(target.companyId) !== companyId)) return;
    const nextTab = target.entityType === 'document' ? '📁 Реестр' : target.projectTab || activeProjectTab;
    writeRoute(page, Object.prototype.hasOwnProperty.call(target, 'projectId') ? target.projectId : expandedProject, nextTab, true, target);
    setActivePage(page);
    if (target.projectTab || target.entityType === 'document') setActiveProjectTab(nextTab);
    setShowForm(false);
    if (Object.prototype.hasOwnProperty.call(target, 'projectId')) setExpandedProject(target.projectId);
    if (target.clientId != null) setExpandedClient(target.clientId);
    setEditingItem(null);
    setEditingPlItem(null);
    setShowPiecework(false);
    setSelectedPricelist(null);
    setPricelistItems([]);
    setShowInvites(false);
    setShowOffers(null);
    setShowSearch(false);
    setGlobalSearch('');
    setShowArchive(false);
    setSelectedInventory(null);
    setSidebarVisible(false);
    if (target.warehouseProject != null) setSelectedWarehouseProject(target.warehouseProject);
    setInlineEditPl(null);
    setShowRoomForm(false);
  };

  const searchTerm = String(globalSearch || '').trim().toLowerCase();
  const searchResults = (!isMobile && searchTerm.length >= 2) ? [
    ...(projects || [])
      .filter(project => String(project.name || '').toLowerCase().includes(searchTerm))
      .map(project => ({ icon: '📋', title: project.name, subtitle: project.client, page: 'projects', projectId: project.id, companyId: ownerId(project) || companyId })),
    ...(clients || [])
      .filter(client => String(client.name || '').toLowerCase().includes(searchTerm))
      .map(client => ({ icon: '👥', title: client.name, subtitle: client.phone, page: 'clients', clientId: client.id, companyId: ownerId(client) || companyId })),
    ...(materials || []).filter(row => companyId && ownerId(row) === companyId)
      .filter(material => String(material.name || '').toLowerCase().includes(searchTerm))
      .map(material => ({ icon: '📦', title: material.name, subtitle: `${material.quantity} ${material.unit}`, page: 'warehouse', entityId: material.id, entityType: 'material', companyId: ownerId(material), projectId: (() => { const matches = visibleProjects(projects || []).filter(p => ownerId(p) === ownerId(material) && p.name === material.project); return matches.length === 1 ? matches[0].id : null; })() })),
    ...(tools || []).filter(row => companyId && ownerId(row) === companyId)
      .filter(tool => String(tool.name || '').toLowerCase().includes(searchTerm))
      .map(tool => ({ icon: '🔧', title: tool.name, subtitle: tool.status, page: 'warehouse', entityId: tool.id, entityType: 'tool', companyId: ownerId(tool), projectId: tool.projectId ?? tool.project_id ?? null })),
  ].slice(0, 8) : [];

  return {
    canAccess,
    isFinanceRole,
    navigateTo,
    searchResults,
    selectableActiveProjects,
    visibleActiveProjects,
    visibleEstimatesForCurrentUser,
    visibleProjects,
  };
}
