import {
  CRM_STAGES,
  EXPENSE_CATEGORIES,
  MATERIAL_CATEGORIES,
  PAYMENT_TYPES,
  SUPPLIER_CATEGORIES,
  TOOL_STATUSES,
  UNITS,
  VAT_OPTIONS,
  WEATHER_CONDITIONS,
} from '../../constants/catalogs';
import { PD_CONSENT_TEXT, PRICELISTS_DATA } from '../../constants/documentTemplates';
import { ROLE_GROUPS, ROLE_LABELS, ROLES } from '../../constants/roles';

export function buildAppShellProps({
  API,
  activePage,
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
  estimatesPageContext,
  layout = {},
  materialNormsState = {},
  pageFallback,
  paymentUiState = {},
  personnelActions = {},
  pricelistActions = {},
  projectCrudActions = {},
  projectOperationActions = {},
  projectsPageContext,
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
  const noop = () => {};
  const safeFn = (fn, fallback = noop) => (typeof fn === 'function' ? fn : fallback);
  const {
    C,
    aiNotice,
    aiNoticeIcon,
    aiNoticeText,
    badge,
    btnB,
    btnG,
    btnGr,
    btnO,
    btnR,
    card,
    darkMode,
    inp,
    isCompactHeader,
    isMobile,
    tbl,
    tblC,
    tblH
  } = ui;
  const {

    companyMessages,
    confirmAcceptedQty,
    confirmComment,
    confirmingEntry,

    editingAct,
    editingCable,
    editingInspection,
    editingJournal,
    globalSearch,
    hiddenActs,
    journalFilter,
    newBrigadePayment,
    newPayment,
    notifications,
    previewContent,
    previewTitle,

    projects,
    rejectComment,
    rejectingEntry,
    setActivePage,
    setDailyReportDate,
    setDarkMode,
    setGlobalSearch,
    setNotifications,
    setPreviewContent,
    setShowAiAssistant,

    setShowChatPanel,
    setShowForm,
    setShowJournalTableModal,
    setShowNotifications,
    setShowPhotoModal,
    setShowQuickActions,
    setSidebarVisible,
    setUser: appMainSetUser,
    showAiAssistant,

    showJournalTableModal,
    showNotifications,

    showPhotoModal,

    sidebarVisible,
    supplyRequests,
    users,
    user: appMainUser,
    weatherLog,
    workJournal
  } = appMainState;
  const user = authUser || authEntryState.user || appMainUser || null;
  const setUser = safeFn(authEntryState.setUser, safeFn(appMainSetUser));
  const {
    aiChat,
    aiLoading,
    aiMessage,
    directorAgentAnswer,
    directorAgentError,
    directorAgentLoading,
    directorAgentQuestion,
    directorAgentSteps,
    setAiMessage,
    setDirectorAgentQuestion
  } = aiAssistantState;
  const {
    companyChatInput,
    setCompanyChatInput,

    setShowMobileMenu,

    setShowSystemStatus,

    showChatPanel,
    showMobileMenu,

    showSystemStatus,
    systemStatus,
    systemStatusLoading
  } = shellOverlayState;
  const { setShowReimburseModal } = paymentUiState;
  const {
    closeNotifications,
    canAccess,
    getNotifPage,
    handleLogout,
    markMyNotificationsRead,
    myNotifications,
    navigateTo,
    openSystemStatus,
    searchResults,

    sendCompanyChatMessage,
    toggleNotifications,
    unreadMessagesCount
  } = coreRuntime;
  const safeCanAccess = typeof canAccess === 'function' ? canAccess : () => true;
  const readMyNotifications = typeof myNotifications === 'function' ? myNotifications : () => [];
  const safeAllMenuItems = Array.isArray(allMenuItems) ? allMenuItems : [];
  const safeNavigateTo = safeFn(navigateTo, safeFn(setActivePage));
  const safeSetActivePage = safeFn(setActivePage);
  const safeSetPreviewContent = safeFn(setPreviewContent);
  const safeSetShowPhotoModal = safeFn(setShowPhotoModal);
  const safeSetShowMobileMenu = safeFn(setShowMobileMenu);
  const safeSetShowQuickActions = safeFn(setShowQuickActions);
  const safeSetShowChatPanel = safeFn(setShowChatPanel);
  const safeSetSidebarVisible = safeFn(setSidebarVisible);
  const safeSetDarkMode = safeFn(setDarkMode);
  const safeSetGlobalSearch = safeFn(setGlobalSearch);
  const safeSetShowNotifications = safeFn(setShowNotifications);
  const safeSetNotifications = safeFn(setNotifications);
  const safeSetShowAiAssistant = safeFn(setShowAiAssistant);
  const safeSetCompanyChatInput = safeFn(setCompanyChatInput);
  const safeSetShowSystemStatus = safeFn(setShowSystemStatus);
  const safeOpenSystemStatus = safeFn(openSystemStatus);
  const safeSendCompanyChatMessage = safeFn(sendCompanyChatMessage);
  const safeUploadPhoto = typeof coreRuntime.uploadPhoto === 'function' ? coreRuntime.uploadPhoto : async () => '';
  const safeSetShowWorkAssignment = safeFn(estimateWorkflowState.setShowWorkAssignment);
  const {
    buildDirectorBriefReportContent,
    buildSupplyControlReportContent,
    canUseDirectorAgent,
    estimateControlIssues,
    isLeadership,
    isMasterRole,
    lowMainStock,
    lowStock,
    openEstimateControlReport,
    projectBudgetSpent,
    projectPaymentSignedAmount,
    projectRealProgress,
    roleColor
  } = businessRuntime;
  const {
    buildCableJournalContent,
    buildDailyObjectReportContent,
    buildHiddenActContent,
    buildMaterialInspectionContent,
    buildWorkJournalContent
  } = documentActions;
  const { projectSiteDraft: getProjectSiteDraft, saveProjectSitePublication, updateProjectSiteDraft } = projectCrudActions;
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
  const notificationItems = readMyNotifications(notifications);
  const unreadNotifications = (Array.isArray(notificationItems) ? notificationItems : []).filter((n) => !n.read).length;
  const uiBase = { API, C, badge, btnB, btnG, btnGr, btnO, btnR, card, inp, isMobile, tbl, tblC, tblH };
  const showPreview = safeFn(dashboardActions.showPreview);

  return {
    activePage,
    appActionModalsProps: {
      ui: { C, btnG, btnGr, btnO, btnR, card, inp },
      constants: { PAYMENT_TYPES, ROLE_LABELS },
      state: sharedState,
      actions: {
        ...sharedActions,
        aiChat,
        aiLoading,
        aiMessage,
        confirmAcceptedQty,
        confirmComment,
        confirmingEntry,
        generateQR: selectors.generateQR,
        newBrigadePayment,
        newPayment,
        rejectComment,
        rejectingEntry,
        returnTool: warehouseActions.returnTool,
        saveActPayment: coreRuntime.saveActPayment,
        saveBrigadePayment: coreRuntime.saveBrigadePayment,
        sendAiMessage: coreRuntime.sendAiMessage,
        setAiMessage
      }
    },
    appBackofficePagesProps: {
      activePage,
      ui: uiBase,
      constants: { PD_CONSENT_TEXT, ROLE_GROUPS, ROLE_LABELS, UNITS },
      state: sharedState,
      actions: sharedActions
    },
    appDirectoryPagesProps: {
      activePage,
      ui: uiBase,
      constants: { PRICELISTS_DATA, ROLE_GROUPS, ROLE_LABELS, ROLES, SUPPLIER_CATEGORIES, UNITS },
      state: sharedState,
      actions: sharedActions
    },
    appOperationsPagesProps: {
      activePage,
      ui: uiBase,
      constants: { MATERIAL_CATEGORIES, SUPPLIER_CATEGORIES, TOOL_STATUSES, UNITS, VAT_OPTIONS },
      state: sharedState,
      actions: sharedActions
    },
    appProjectEditModalsProps: {
      ui: { C, aiNotice, aiNoticeIcon, aiNoticeText, btnB, btnG, btnO, btnR, card, inp, tbl, tblC, tblH },
      state: sharedState,
      actions: {
        ...sharedActions,
        buildCableJournalContent,
        buildHiddenActContent,
        buildMaterialInspectionContent,
        buildWorkJournalContent,
        editingAct,
        editingCable,
        editingInspection,
        editingJournal,
        hiddenActs,
        journalFilter,
        setShowJournalTableModal,
        showJournalTableModal,
        users,
        weatherLog,
        workJournal
      }
    },
    appSecondaryPagesProps: {
      activePage,
      ui: { API, C, badge, btnB, btnG, btnO, btnR, card, inp, isMobile, tbl, tblC, tblH },
      constants: { CRM_STAGES, EXPENSE_CATEGORIES, ROLE_LABELS, WEATHER_CONDITIONS },
      state: sharedState,
      actions: sharedActions
    },
    appWorkflowModalsProps: {
      ui: { API, C, badge, btnB, btnG, btnO, btnR, card, darkMode, inp, isMobile },
      constants: { estimatePackages: selectors.ESTIMATE_PACKAGES, expenseCategories: EXPENSE_CATEGORIES, roleLabels: ROLE_LABELS, supplierCategories: SUPPLIER_CATEGORIES, units: UNITS },
      state: sharedState,
      actions: sharedActions
    },
    C,
    canOpenProjects: safeCanAccess('projects'),
    dashboardProps: {
      ui: { API, C, btnG, btnO, darkMode, isMobile, showAiAssistant, showNotifications, unreadMessagesCount, unreadNotifications },
      data: {
        ...sharedState,
        canUseDirectorAgent,
        directorAgentAnswer,
        directorAgentError,
        directorAgentLoading,
        directorAgentQuestion,
        directorAgentSteps,
        estimateControlIssues,
        lowMainStock,
        lowStock
      },
      actions: {
        ...sharedActions,
        buildDailyObjectReportContent,
        buildDirectorBriefReportContent,
        buildSupplyControlReportContent,
        closeNotifications,
        getNotifPage,
        markMyNotificationsRead,
        navigateTo: safeNavigateTo,
        openEstimateControlReport,
        projectBudgetSpent,
        projectPaymentSignedAmount,
        projectRealProgress,
        setDailyReportDate,
        setDarkMode: safeSetDarkMode,
        setDirectorAgentQuestion,
        setNotifications: safeSetNotifications,
        setShowAiAssistant: safeSetShowAiAssistant,
        setShowChatPanel: safeSetShowChatPanel,
        setShowForm,
        setShowNotifications: safeSetShowNotifications,
        setShowQuickActions: safeSetShowQuickActions,
        setShowReimburseModal,
        setSidebarVisible: safeSetSidebarVisible,
        setUser,
        showPreview,
        toggleNotifications,
        visibleActiveProjects: coreRuntime.visibleActiveProjects || sharedActions.visibleActiveProjects
      }
    },
    estimatesPageContext,
    headerProps: {
      ...sharedState,
      ...sharedActions,
      C,
      API,
      activePage,
      allMenuItems: safeAllMenuItems,
      btnG,
      btnO,
      darkMode,
      globalSearch,
      inp,
      isCompactHeader,
      isMobile,
      menuItems,
      navigateTo: safeNavigateTo,
      notifications,
      openSystemStatus: safeOpenSystemStatus,
      searchResults,
      setDarkMode: safeSetDarkMode,
      setGlobalSearch: safeSetGlobalSearch,
      setNotifications: safeSetNotifications,
      setShowChatPanel: safeSetShowChatPanel,
      setShowNotifications: safeSetShowNotifications,
      setShowQuickActions: safeSetShowQuickActions,
      setSidebarVisible: safeSetSidebarVisible,
      setUser,
      showNotifications,
      toggleNotifications,
      unreadMessagesCount,
      unreadNotifications,
      user
    },
    isMobile,
    mobileBottomNavProps: {
      activePage,
      isMobile,
      menuItems,
      navigateTo: safeNavigateTo,
      setActivePage: safeSetActivePage,
      setShowChatPanel: safeSetShowChatPanel,
      setShowMobileMenu: safeSetShowMobileMenu,
      setShowQuickActions: safeSetShowQuickActions,
      unreadMessagesCount
    },
    overlayProps: {
      C,
      activePage,
      badge,
      btnG,
      companyChatInput,
      companyMessages,
      menuItems,
      navigateTo: safeNavigateTo,
      openSystemStatus: safeOpenSystemStatus,
      sendCompanyChatMessage: safeSendCompanyChatMessage,
      setActivePage: safeSetActivePage,
      setCompanyChatInput: safeSetCompanyChatInput,
      setShowChatPanel: safeSetShowChatPanel,
      setShowMobileMenu: safeSetShowMobileMenu,
      setShowSystemStatus: safeSetShowSystemStatus,
      showChatPanel,
      showMobileMenu,
      showSystemStatus,
      systemStatus,
      systemStatusLoading,
      uploadPhoto: safeUploadPhoto,
      user
    },
    pageFallback,
    photoPreviewProps: { src: showPhotoModal, onClose: () => safeSetShowPhotoModal(null) },
    previewProps: {
      content: previewContent,
      title: previewTitle,
      onClose: () => safeSetPreviewContent(null),
      onPrint: safeFn(selectors.doPrint)
    },
    projectSiteProps: {
      C,
      badge,
      btnG,
      btnO,
      card,
      inp,
      isMobile,
      projects,
      projectSiteDraft: getProjectSiteDraft,
      saveProjectSitePublication,
      updateProjectSiteDraft
    },
    projectsPageContext,
    sidebarProps: {
      C,
      activePage,
      handleLogout: safeFn(handleLogout),
      isLeadership,
      isMasterRole,
      isMobile,
      menuItems,
      navigateTo: safeNavigateTo,
      roleColor,
      roleLabels: ROLE_LABELS,
      setSidebarVisible: safeSetSidebarVisible,
      sidebarRef: refs.sidebarRef,
      sidebarVisible,
      supplyRequests,
      user
    },
    workAssignmentProps: {
      show: estimateWorkflowState.showWorkAssignment,
      onClose: () => safeSetShowWorkAssignment(false),
      selectedEstimate: estimateWorkflowState.selectedEstimate,
      staff: appMainState.staff,
      users,
      API,
      loadAll: coreRuntime.loadAll,
      C,
      card,
      inp,
      btnO,
      btnG,
      btnB,
      isMobile
    }
  };
}
