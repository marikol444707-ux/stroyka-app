import { useEffect } from 'react';
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
    globalSearch,
    isMobile,
    masterProjectId,
    user,
  } = state;
  const {
    loadPricelistItems,
    setActivePage,
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

  const navigateTo = (page) => {
    if (!canAccess(page)) return;
    setActivePage(page);
    setShowForm(false);
    setExpandedProject(null);
    setExpandedClient(null);
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
    setSelectedWarehouseProject(null);
    setInlineEditPl(null);
    setShowRoomForm(false);
  };

  const searchTerm = String(globalSearch || '').trim().toLowerCase();
  const searchResults = (!isMobile && searchTerm.length >= 2) ? [
    ...(projects || [])
      .filter(project => String(project.name || '').toLowerCase().includes(searchTerm))
      .map(project => ({ icon: '📋', title: project.name, subtitle: project.client, page: 'projects' })),
    ...(clients || [])
      .filter(client => String(client.name || '').toLowerCase().includes(searchTerm))
      .map(client => ({ icon: '👥', title: client.name, subtitle: client.phone, page: 'clients' })),
    ...(materials || [])
      .filter(material => String(material.name || '').toLowerCase().includes(searchTerm))
      .map(material => ({ icon: '📦', title: material.name, subtitle: `${material.quantity} ${material.unit}`, page: 'warehouse' })),
    ...(tools || [])
      .filter(tool => String(tool.name || '').toLowerCase().includes(searchTerm))
      .map(tool => ({ icon: '🔧', title: tool.name, subtitle: tool.status, page: 'warehouse' })),
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
