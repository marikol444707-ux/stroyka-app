const noop = () => {};

export const safeFn = (fn, fallback = noop) => (typeof fn === 'function' ? fn : fallback);

export function buildAppShellSharedContext({
  API,
  aiAssistantState = {},
  allMenuItems,
  appMainState = {},
  authEntryState = {},
  businessRuntime = {},
  coreRuntime = {},
  dashboardActions = {},
  documentActions = {},
  estimatePageActions = {},
  estimateWorkflowState = {},
  materialNormsState = {},
  paymentUiState = {},
  personnelActions = {},
  pricelistActions = {},
  projectCrudActions = {},
  projectOperationActions = {},
  refs = {},
  selectors = {},
  shellOverlayState = {},
  supplyActions = {},
  supplyPlanningUi = {},
  supplyWorkflowState = {},
  ui = {},
  user: authUser,
  userAccessActions = {},
  warehouseActions = {},
  workJournalActions = {}
}) {
  const user = authUser || authEntryState.user || null;
  const setUser = safeFn(authEntryState.setUser);
  const safeCanAccess = typeof coreRuntime.canAccess === 'function' ? coreRuntime.canAccess : () => true;
  const readMyNotifications = typeof coreRuntime.myNotifications === 'function' ? coreRuntime.myNotifications : () => [];
  const safeAllMenuItems = Array.isArray(allMenuItems) ? allMenuItems : [];
  const safeNavigateTo = safeFn(coreRuntime.navigateTo, safeFn(appMainState.setActivePage));

  const safeSetActivePage = safeFn(appMainState.setActivePage);
  const safeSetPreviewContent = safeFn(appMainState.setPreviewContent);
  const safeSetShowPhotoModal = safeFn(appMainState.setShowPhotoModal);
  const safeSetShowMobileMenu = safeFn(shellOverlayState.setShowMobileMenu);
  const safeSetShowQuickActions = safeFn(appMainState.setShowQuickActions);
  const safeSetShowChatPanel = safeFn(coreRuntime.setShowChatPanel, safeFn(appMainState.setShowChatPanel));
  const safeSetSidebarVisible = safeFn(appMainState.setSidebarVisible);
  const safeSetDarkMode = safeFn(ui.setDarkMode);
  const safeSetGlobalSearch = safeFn(appMainState.setGlobalSearch);
  const safeSetShowNotifications = safeFn(appMainState.setShowNotifications);
  const safeSetNotifications = safeFn(appMainState.setNotifications);
  const safeSetShowAiAssistant = safeFn(appMainState.setShowAiAssistant);
  const safeSetCompanyChatInput = safeFn(shellOverlayState.setCompanyChatInput);
  const safeSetShowSystemStatus = safeFn(shellOverlayState.setShowSystemStatus);
  const safeOpenSystemStatus = safeFn(coreRuntime.openSystemStatus);
  const safeSendCompanyChatMessage = safeFn(coreRuntime.sendCompanyChatMessage);
  const safeUploadPhoto = typeof coreRuntime.uploadPhoto === 'function' ? coreRuntime.uploadPhoto : async () => '';
  const safeSetShowWorkAssignment = safeFn(estimateWorkflowState.setShowWorkAssignment);

  const sharedState = {
    ...appMainState,
    ...aiAssistantState,
    ...shellOverlayState,
    ...paymentUiState,
    ...supplyWorkflowState,
    ...materialNormsState,
    ...estimateWorkflowState,
    ...refs,
    ...selectors,
    ...businessRuntime,
    user
  };

  const sharedActions = {
    ...sharedState,
    ...coreRuntime,
    ...businessRuntime,
    ...documentActions,
    ...personnelActions,
    ...projectCrudActions,
    ...warehouseActions,
    ...workJournalActions,
    ...userAccessActions,
    ...pricelistActions,
    ...supplyActions,
    ...projectOperationActions,
    ...supplyPlanningUi,
    ...estimatePageActions,
    ...dashboardActions,
    ...selectors,
    canAccess: safeCanAccess,
    myNotifications: readMyNotifications,
    setUser
  };

  const menuItems = safeAllMenuItems.filter((item) => item && safeCanAccess(item.id));
  const notificationItems = readMyNotifications(appMainState.notifications);
  const unreadNotifications = (Array.isArray(notificationItems) ? notificationItems : []).filter((n) => !n.read).length;
  const uiBase = {
    API,
    C: ui.C,
    badge: ui.badge,
    btnB: ui.btnB,
    btnG: ui.btnG,
    btnGr: ui.btnGr,
    btnO: ui.btnO,
    btnR: ui.btnR,
    card: ui.card,
    inp: ui.inp,
    isMobile: ui.isMobile,
    tbl: ui.tbl,
    tblC: ui.tblC,
    tblH: ui.tblH
  };

  return {
    menuItems,
    readMyNotifications,
    safeAllMenuItems,
    safeCanAccess,
    safeFn,
    safeNavigateTo,
    safeOpenSystemStatus,
    safeSendCompanyChatMessage,
    safeSetActivePage,
    safeSetCompanyChatInput,
    safeSetDarkMode,
    safeSetGlobalSearch,
    safeSetNotifications,
    safeSetPreviewContent,
    safeSetShowAiAssistant,
    safeSetShowChatPanel,
    safeSetShowMobileMenu,
    safeSetShowNotifications,
    safeSetShowPhotoModal,
    safeSetShowQuickActions,
    safeSetShowSystemStatus,
    safeSetShowWorkAssignment,
    safeSetSidebarVisible,
    safeUploadPhoto,
    setUser,
    sharedActions,
    sharedState,
    showPreview: safeFn(dashboardActions.showPreview),
    uiBase,
    unreadNotifications,
    user
  };
}
