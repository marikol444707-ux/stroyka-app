import { useEffect } from 'react';
import { createAiAssistantActions } from '../ai-assistant/aiAssistantActions';
import { createAuthActions } from '../auth/authActions';
import { createChatActions } from '../chat/chatActions';
import { useCompanyChatContextSync } from '../chat/useCompanyChatContextSync';
import { createCrmActions } from '../crm/crmActions';
import { createDataLoadActions } from '../data-loaders/dataLoadActions';
import { useAppDataLoaders } from '../data-loaders/useAppDataLoaders';
import { createGeoActions } from '../geolocation/geoActions';
import { createMaterialTransferActions } from '../material-transfer/materialTransferActions';
import { createNotificationActions } from '../notifications/notificationActions';
import { createPaymentActions } from '../payments/paymentActions';
import { createSystemActions } from '../system/systemActions';
import { createUploadActions } from '../uploads/uploadActions';
import { useAppNavigationRuntime } from '../navigation/appNavigationRuntime';
import { canAccessRole, roleFlagsForUser } from '../../utils/accessUtils';
import {
  buildPagedPath,
  createMaterialNormsPageState,
  createMaterialsPageState,
  createWorkJournalPageState,
  mergeRowsByIdValue,
  mobileScopeForPage,
  sendPushNotification,
} from '../../utils/appRuntimeUtils';
import { normalizeEstimateList } from '../../utils/estimateUtils';
import { fmtMeasure, toNum } from '../../utils/measureUtils';
import { unreadCompanyMessagesCount } from './appShellSelectors';
import {
  useAuthenticatedAppBootstrapEffect,
  useInviteCodeCheckEffect,
  useNotificationDismissEffect,
} from './useAppShellState';

export function useAppCoreRuntime({
  API,
  ROLES,
  appMainState,
  authEntryState,
  companyContext,
  shellOverlayState,
  aiAssistantState,
  materialNormsState,
  refs,
  limits,
  layout,
}) {
  const {
    AUDIT_LOG_PAGE_LIMIT,
    MATERIAL_NORMS_PAGE_LIMIT,
    MATERIALS_PAGE_LIMIT,
    WORK_JOURNAL_PAGE_LIMIT,
  } = limits;
  const { chatEndRef, mobileApiRequestsRef, mobileLoadedScopesRef } = refs;
  const { isMobile } = layout;
  const {
    email,
    password,
    regCode,
    regEmail,
    regInviteInfo,
    regName,
    regPassword,
    regSupplierData,
    setEmail,
    setLoginError,
    setPage,
    setRegInviteInfo,
    setRegSupplierData,
    setUser,
    user,
  } = authEntryState;
  const {
    setShowChatPanelRaw,
    setShowSystemStatus,
    setSystemStatus,
    setSystemStatusLoading,
    showChatPanel,
  } = shellOverlayState;
  const {
    aiChat,
    aiMessage,
    directorAgentLoading,
    directorAgentQuestion,
    setAiChat,
    setAiLoading,
    setAiMessage,
    setDirectorAgentAnswer,
    setDirectorAgentError,
    setDirectorAgentLoading,
    setDirectorAgentQuestion,
    setDirectorAgentSteps,
  } = aiAssistantState;
  const {
    materialNormSearch,
    setMaterialNormsPage,
    setMaterialNormSuggestions,
  } = materialNormsState;
  const {
    activePage, activeProjectTab, actPayments, companyMessages, consentChecked, estimatesTab,
    expandedProject, geoCheckins, globalSearch, initialDataLoaded, interimActs, materials,
    masterProjectId, newBrigadePayment, newPayment, notifications, profileData, projects,
    pushEnabled, selectedBrigadeContract, setAccountablePayments, setActivePage,
    setActivityLog, setActPayments, setAiFindings, setAiTasks, setAllBrigadeItems,
    setAllBrigadePayments, setAuditLog, setBrigadeContractItems, setBrigadeContracts,
    setBrigadePayments, setCableJournal, setChecklists, setChecklistItems, setClients,
    setCompanyDocuments, setCompanyMessages, setCompanyName, setCompanyRequisites,
    setContracts, setEditingItem, setEditingPlItem, setEstimateReconciliations,
    setEstimatesList, setEstimatesPage, setExpenseReports, setExpandedClient,
    setExpandedProject, setGeoCheckins, setGlobalSearch, setHiddenActs, setHistory,
    setInitialDataLoaded, setInlineEditPl, setInspectionOrders, setInterimActs, setInventory, setInviteCodes,
    setInvoices, setLeads, setManualExpenses, setMasterProfile, setMasterProfiles,
    setMasterProjectId, setMaterialAliases, setMaterialInspections, setMaterialNormOverrides,
    setMaterialNorms, setMaterials, setMaterialsPage, setMaterialTransfers,
    setMeasurementRoomDrafts, setNotifications, setOwnExpenses, setPdConsents, setPiecework,
    setPrescriptionsList, setPricelistItems, setPricelists, setProjectChatMessage,
    setProjectChatMessages, setProjectDocuments, setProjectLetters, setProjectMeasurements,
    setProjectPayments, setProjects, setProjectStages, setPushEnabled, setRoomDoors, setRooms,
    setRoomWindows, setRoomWorks, setSalaryPayments, setSelectedBrigadeContract,
    setSelectedInventory, setSelectedPricelist, setSelectedWarehouseProject, setSelectedWorks,
    setShowArchive, setShowBrigadePayModal, setShowForm, setShowInvites, setShowOffers,
    setShowPayActModal, setShowPiecework, setShowProfileForm, setShowRoomForm, setShowSearch,
    setSidebarVisible, setSignedDocs, setStaff, setSupervisorActs, setSupplierCatalog,
    setSupplierInvoices, setSupplierOffers, setSuppliers, setSupplyClaims, setSupplyDeliveries,
    setSupplyHistory, setSupplyRequests, setSupplyTemplates, setTbJournal, setTimesheet,
    setToolHistory, setTools, setUnexpectedWorksList, setWarehouseMain, setWarehouseMovements,
    setWarehouses, setWarrantyDefects, setWeatherLog, setWorkJournal, setWorkJournalPage,
    tools,
  } = appMainState;

  const currentUser = user || null;

  const { askDirectorAgent, sendAiMessage } = createAiAssistantActions({
    API,
    aiChat,
    aiMessage,
    chatEndRef,
    directorAgentLoading,
    directorAgentQuestion,
    setAiChat,
    setAiLoading,
    setAiMessage,
    setDirectorAgentAnswer,
    setDirectorAgentError,
    setDirectorAgentLoading,
    setDirectorAgentQuestion,
    setDirectorAgentSteps,
  });

  const { loadAuditLog, openSystemStatus } = createSystemActions({
    API,
    setAuditLog,
    setShowSystemStatus,
    setSystemStatus,
    setSystemStatusLoading,
  });

  const {
    addActivity,
    closeNotifications,
    getNotifPage,
    markMyNotificationsRead,
    myNotifications,
    notify,
    toggleNotifications,
  } = createNotificationActions({
    API,
    activePage,
    loadAuditLog,
    notifications,
    pushEnabled,
    sendPushNotification,
    setActivityLog,
    setNotifications,
    setShowNotifications: appMainState.setShowNotifications,
    user: currentUser,
  });

  useNotificationDismissEffect(appMainState.setShowNotifications);

  const {
    canUseCompanyChat,
    companyChatContextKey,
    isCompanyChatContextCurrent,
    reloadCompanyMessages,
  } = useCompanyChatContextSync({
    API,
    companyContext,
    notify,
    setCompanyMessages,
    user: currentUser,
  });

  useEffect(() => {
    if (!currentUser || activePage !== 'activitylog') return;
    loadAuditLog();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentUser, activePage]);

  const {
    apiAuthHeaders,
    loadAll,
    loadMaterialNormsPage,
    loadMaterialsPage,
    loadMobileInitial,
    loadWorkJournalPage,
    refreshData,
  } = useAppDataLoaders({
    activePage,
    API,
    AUDIT_LOG_PAGE_LIMIT,
    buildPagedPath,
    canAccessRole,
    createMaterialNormsPageState,
    createMaterialsPageState,
    createWorkJournalPageState,
    estimatesTab,
    initialDataLoaded,
    isMobile,
    MATERIAL_NORMS_PAGE_LIMIT,
    materialNormSearch,
    MATERIALS_PAGE_LIMIT,
    mergeRowsByIdValue,
    mobileApiRequestsRef,
    mobileLoadedScopesRef,
    mobileScopeForPage,
    normalizeEstimateList,
    roleFlagsForUser,
    ROLES,
    setAccountablePayments,
    setAiFindings,
    setAiTasks,
    setAllBrigadeItems,
    setAllBrigadePayments,
    setAuditLog,
    setBrigadeContracts,
    setCableJournal,
    setChecklists,
    setClients,
    setCompanyDocuments,
    setCompanyRequisites,
    setContracts,
    setEstimateReconciliations,
    setEstimatesList,
    setEstimatesPage,
    setExpenseReports,
    setHiddenActs,
    setHistory,
    setInitialDataLoaded,
    setInspectionOrders,
    setInterimActs,
    setInventory,
    setInviteCodes,
    setInvoices,
    setLeads,
    setManualExpenses,
    setMasterProfiles,
    setMaterialAliases,
    setMaterialInspections,
    setMaterialNormOverrides,
    setMaterialNorms,
    setMaterialNormsPage,
    setMaterialNormSuggestions,
    setMaterials,
    setMaterialsPage,
    setMaterialTransfers,
    setMeasurementRoomDrafts,
    setOwnExpenses,
    setPdConsents,
    setPiecework,
    setPrescriptionsList,
    setPricelists,
    setProjectDocuments,
    setProjectLetters,
    setProjectMeasurements,
    setProjectPayments,
    setProjects,
    setProjectStages,
    setRoomDoors,
    setRooms,
    setRoomWindows,
    setRoomWorks,
    setSalaryPayments,
    setStaff,
    setSupervisorActs,
    setSupplierCatalog,
    setSupplierInvoices,
    setSupplierOffers,
    setSuppliers,
    setSupplyClaims,
    setSupplyDeliveries,
    setSupplyHistory,
    setSupplyRequests,
    setSupplyTemplates,
    setTbJournal,
    setTimesheet,
    setToolHistory,
    setTools,
    setUnexpectedWorksList,
    setUser,
    setUsers: appMainState.setUsers,
    setWarehouseMain,
    setWarehouseMovements,
    setWarehouses,
    setWarrantyDefects,
    setWorkJournal,
    setWorkJournalPage,
    user: currentUser,
    WORK_JOURNAL_PAGE_LIMIT,
  });

  const unreadMessagesCount = unreadCompanyMessagesCount(companyMessages, currentUser);

  const {
    loadChecklistItems,
    loadMasterProfile,
    loadPricelistItems,
    loadProjectChat,
  } = createDataLoadActions({
    API,
    setChecklistItems,
    setMasterProfile,
    setPricelistItems,
    setProjectChatMessages,
    setShowProfileForm,
    user: currentUser,
  });

  useAuthenticatedAppBootstrapEffect({
    API,
    isMobile,
    loadMasterProfile,
    loadMobileInitial,
    mobileApiRequestsRef,
    mobileLoadedScopesRef,
    refreshData,
    setActivePage,
    setCompanyName,
    setInitialDataLoaded,
    setPushEnabled,
    storageSetters: {
      masterRatings: appMainState.setMasterRatings,
      activityLog: setActivityLog,
      notifications: setNotifications,
      tbJournal: setTbJournal,
      geoCheckins: setGeoCheckins,
      signedDocs: setSignedDocs,
      actPayments: setActPayments,
      weatherLog: setWeatherLog,
    },
    user: currentUser,
  });

  const { appendPhotos, uploadPhoto } = createUploadActions({
    API,
    activePage,
    activeProjectTab,
    expandedProject,
    masterProjectId,
    projects,
  });

  const { checkinGeo } = createGeoActions({
    geoCheckins,
    setGeoCheckins,
    user: currentUser,
  });

  const {
    deleteBrigadePayment,
    openBrigadeContract,
    saveActPayment,
    saveBrigadePayment,
  } = createPaymentActions({
    API,
    actPayments,
    interimActs,
    loadPricelistItems,
    newBrigadePayment,
    newPayment,
    refreshData,
    selectedBrigadeContract,
    setActPayments,
    setBrigadeContractItems,
    setBrigadePayments,
    setNewBrigadePayment: appMainState.setNewBrigadePayment,
    setNewPayment: appMainState.setNewPayment,
    setSelectedBrigadeContract,
    setShowBrigadePayModal,
    setShowPayActModal,
    toNum,
    user: currentUser,
  });

  const {
    sendCompanyChatMessage,
    sendProjectChatMessage,
    setShowChatPanel,
  } = createChatActions({
    API,
    canUseCompanyChat,
    companyChatContextKey,
    isCompanyChatContextCurrent,
    loadProjectChat,
    notify,
    reloadCompanyMessages,
    setCompanyChatMessage: appMainState.setCompanyChatMessage,
    setShowChatPanelRaw,
    setProjectChatMessage,
    showChatPanel,
    unreadMessagesCount,
    user: currentUser,
  });

  const {
    saveLead,
    deleteLead,
    createProjectFromLead,
  } = createCrmActions({
    API,
    notify,
    setLeads,
    setProjects,
    user: currentUser,
  });

  const {
    confirmMaterialReceipt,
    returnMaterialToProject,
  } = createMaterialTransferActions({
    API,
    fmtMeasure,
    notify,
    refreshData,
    setMaterialTransfers,
    toNum,
  });

  const {
    handleLogout,
    handleLogin,
    handleTwoFactorLogin,
    handleRegister,
    checkInviteCode,
    saveProfile,
  } = createAuthActions({
    API,
    consentChecked,
    email,
    password,
    profileData,
    refreshData,
    regCode,
    regEmail,
    regInviteInfo,
    regName,
    regPassword,
    regSupplierData,
    setEmail,
    setInitialDataLoaded,
    setLoginError,
    setMasterProfile,
    setPage,
    setRegInviteInfo,
    setRegSupplierData,
    setShowProfileForm,
    setUser,
    user: currentUser,
  });

  useInviteCodeCheckEffect({ checkInviteCode, regCode, setRegInviteInfo });

  const {
    canAccess,
    isFinanceRole,
    navigateTo,
    searchResults,
    selectableActiveProjects,
    visibleActiveProjects,
    visibleEstimatesForCurrentUser,
    visibleProjects,
  } = useAppNavigationRuntime({
    ROLES,
    data: { clients: appMainState.clients, materials, projects, tools },
    state: { globalSearch, isMobile, masterProjectId, user: currentUser },
    actions: {
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
    },
  });

  return {
    addActivity,
    apiAuthHeaders,
    appendPhotos,
    askDirectorAgent,
    canAccess,
    checkinGeo,
    closeNotifications,
    confirmMaterialReceipt,
    createProjectFromLead,
    deleteBrigadePayment,
    deleteLead,
    getNotifPage,
    handleLogin,
    handleLogout,
    handleRegister,
    handleTwoFactorLogin,
    isFinanceRole,
    loadAll,
    loadAuditLog,
    loadChecklistItems,
    loadMaterialNormsPage,
    loadMaterialsPage,
    loadMobileInitial,
    loadPricelistItems,
    loadProjectChat,
    loadWorkJournalPage,
    markMyNotificationsRead,
    myNotifications,
    navigateTo,
    notify,
    openBrigadeContract,
    openSystemStatus,
    refreshData,
    returnMaterialToProject,
    saveActPayment,
    saveBrigadePayment,
    saveLead,
    saveProfile,
    searchResults,
    selectableActiveProjects,
    sendAiMessage,
    sendCompanyChatMessage,
    sendProjectChatMessage,
    setShowChatPanel,
    toggleNotifications,
    unreadMessagesCount,
    uploadPhoto,
    visibleActiveProjects,
    visibleEstimatesForCurrentUser,
    visibleProjects,
  };
}
