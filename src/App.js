import React, { useRef } from 'react';
import './App.css';
import { API, installAuthFetch } from './api';
import { CRM_STAGES, DOOR_PURPOSES, DOOR_TYPES, ESTIMATE_CHANGE_TYPES, ESTIMATE_CHANGE_VISIBLE_STATUSES, ESTIMATE_PACKAGES, EXPENSE_CATEGORIES, MATERIAL_CATEGORIES, PAYMENT_TYPES, REVEAL_MATERIALS, STAGE_STATUSES, SUPPLIER_CATEGORIES, SURFACES, TOOL_STATUSES, UNITS, VAT_OPTIONS, WEATHER_CONDITIONS, WINDOW_TYPES } from './constants/catalogs';
import {
  PROJECT_MEASUREMENT_DOC_TYPES,
  PROJECT_MEASUREMENT_SOURCE_TYPES,
  PROJECT_MEASUREMENT_STATUSES,
} from './constants/estimateConstants';
import {
  AUDIT_LOG_PAGE_LIMIT,
  DIRECTOR_MAP_FEATURE_ENABLED,
  MATERIAL_NORMS_PAGE_LIMIT,
  MATERIALS_PAGE_LIMIT,
  WORK_JOURNAL_PAGE_LIMIT,
} from './constants/appConfig';
import {
  CHECKLIST_TEMPLATES,
  PD_CONSENT_TEXT,
  PRICELISTS_DATA,
  TB_INSTRUCTIONS,
  TB_TYPES_GOST,
} from './constants/documentTemplates';
import {
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
  btnState,
  card,
  inp,
  tbl,
  tblC,
  tblH,
} from './constants/uiTheme';
import { ROLES, ROLE_GROUPS, ROLE_LABELS } from './constants/roles';
import ProjectCardHeader from './components/ProjectCardHeader';
import ProjectTabsNav from './components/ProjectTabsNav';
import ProjectMaterialsControlPanel from './components/ProjectMaterialsControlPanel';
import ProjectMaterialsStockPanel from './components/ProjectMaterialsStockPanel';
import ProjectMaterialsTransferPanel from './components/ProjectMaterialsTransferPanel';
import ProjectFinancePanel from './components/ProjectFinancePanel';
import ProjectEconomyPanel from './components/ProjectEconomyPanel';
import ProjectObjectLinksPanel from './components/ProjectObjectLinksPanel';
import ProjectDocumentsRegistryPanel from './components/ProjectDocumentsRegistryPanel';
import ProjectLettersPanel from './components/ProjectLettersPanel';
import ProjectBrigadeCalculationTab from './components/ProjectBrigadeCalculationTab';
import ProjectHiddenWorksActsPanel from './components/ProjectHiddenWorksActsPanel';
import ProjectPrescriptionsPanel from './components/ProjectPrescriptionsPanel';
import ProjectSafetyJournalPanel from './components/ProjectSafetyJournalPanel';
import ProjectWorkJournalPanel from './components/ProjectWorkJournalPanel';
import ProjectScheduleSummaryPanel from './components/ProjectScheduleSummaryPanel';
import { ProjectDirectorMapPanel } from './features/director-map';
import { ProjectLaunchPanel } from './features/project-launch';
import { createProjectCrudActions } from './features/projects/projectCrudActions';
import { createWarehouseCrudActions } from './features/warehouse/warehouseCrudActions';
import EstimatesTabsNav from './components/EstimatesTabsNav';
import EstimatesListToolbar from './components/EstimatesListToolbar';
import EstimateSearchResults from './components/EstimateSearchResults';
import EstimateImportValidationBanner from './components/EstimateImportValidationBanner';
import MaterialNormNotice from './components/MaterialNormNotice';
import MaterialNormsHeader from './components/MaterialNormsHeader';
import MaterialNormOverridesPanel from './components/MaterialNormOverridesPanel';
import EstimateImportView from './components/EstimateImportView';
import MaterialNormCoverageSection from './components/MaterialNormCoverageSection';
import EstimateCreateFormFields from './components/EstimateCreateFormFields';
import EstimatesListView from './components/EstimatesListView';
import EstimateCreateActions from './components/EstimateCreateActions';
import EstimateSelectedToolbar from './components/EstimateSelectedToolbar';
import EstimateAddSectionForm from './components/EstimateAddSectionForm';
import EstimateTotalCard from './components/EstimateTotalCard';
import MaterialNormSuggestionsPanel from './components/MaterialNormSuggestionsPanel';
import EstimateDuplicateWorkSummaryPanel from './components/EstimateDuplicateWorkSummaryPanel';
import EstimateSectionsEditor from './components/EstimateSectionsEditor';
import MaterialNormFormPanel from './components/MaterialNormFormPanel';
import MaterialNormsListPanel from './components/MaterialNormsListPanel';
import EstimateExecutionPricingPanel from './components/EstimateExecutionPricingPanel';
import PhotoAttachmentField from './components/PhotoAttachmentField';
import AppAuthenticatedShell from './components/AppAuthenticatedShell';
import { WorkAssignmentStatusPanel } from './features/work-assignment';
import { useAiAssistantState } from './features/ai-assistant/useAiAssistantState';
import { createUserAccessActions } from './features/admin/userAccessActions';
import { createDocumentActions } from './features/documents/documentActions';
import { usePaymentUiState } from './features/payments/usePaymentUiState';
import { createPersonnelActions } from './features/personnel/personnelActions';
import { createPricelistActions } from './features/pricelists/pricelistActions';
import { useMaterialNormsState } from './features/material-norms/useMaterialNormsState';
import { createWorkJournalActions } from './features/work-journal/workJournalActions';
import AppPageFallback from './components/AppPageFallback';
import { buildAppMenuItems } from './components/AppMenuItems';
import { _normalizeUnit, denormalizeMeasure, fmtMeasure, normalizeMeasure, toNum } from './utils/measureUtils';
import {
  WORK_MATERIAL_NORM_RULES,
  convertUnits,
  materialNormCoverageComment,
  materialNormCoverageDisplayRows,
  materialNormCoverageExportRows,
  materialNormRuleForCalc,
  materialNormCanCreateSupply,
  materialTitleForNormRule,
} from './utils/materialNormUtils';
import {
  calcDoorArea,
  calcDoorReveals,
  calcWindowArea,
  calcWindowReveals,
} from './utils/roomMeasurementUtils';
import {
  buildEstimateWorkSummary,
  enrichEstimateMeasurementBasis,
  activeEstimateFromList,
  applyEstimateActivationState,
  estimateDisplayVersion,
  estimateExecutionFillPercentOf,
  estimateGroupKey,
  estimateImportedPlanMeasure,
  estimateItemDoneTotal,
  estimateItemMaterialSum,
  estimateItemTotal,
  estimateItemTypeMeta,
  estimateItemWorkSum,
  estimateIssueDomId,
  estimateKind,
  estimateMaterialPlanIssue,
  estimateMeasurementBasisMeta,
  estimateMeasurementBasisOf,
  estimatePackage,
  estimateSectionsOf as _sectionsOfEst,
  estimateTotal,
  estimateTypeIcon,
  estimateUpdatedTs,
  estimateVersionChain,
  nextEstimateVersionFor as nextEstimateVersionForFromList,
  estimateWorkKey,
  isArchivedEstimate,
  isGlobalEstimateTemplate,
  isEstimatePricelist,
  isEstimateMaterialItem,
  isEstimateWorkItem,
  normalizeEstimateImportSections,
  normalizeEstimateItemType,
  sameEstimateGroup,
} from './utils/estimateUtils';
import { estimateQualityRows } from './utils/estimateReviewUtils';
import { createEstimatePageActions } from './features/estimates/estimatePageActions';
import { persistEstimateAction } from './features/estimates/estimatePersistenceActions';
import { createSupplyActions } from './features/supply/supplyActions';
import { createSupplyPlanningUi } from './features/supply/supplyPlanningUi';
import { useSupplyWorkflowState } from './features/supply/useSupplyWorkflowState';
import { useSupplierRequisitesSync } from './features/supply/useSupplierRequisitesSync';
import { createProjectOperationActions } from './features/project-operations/projectOperationActions';
import { createProjectMeasurementActions } from './features/project-measurements/projectMeasurementActions';
import { createAppUtilityRuntime } from './features/app-shell/appShellSelectors';
import {
  useAuthEntryState,
  useDarkModeState,
  useResponsiveLayout,
  useShellOverlayState,
} from './features/app-shell/useAppShellState';
import { useAppCoreRuntime } from './features/app-shell/useAppCoreRuntime';
import { useAppMainState } from './features/app-shell/useAppMainState';
import { useAppBusinessRuntime } from './features/app-shell/useAppBusinessRuntime';
import { renderAppEarlyRoleRoute } from './features/app-shell/renderAppEarlyRoleRoute';
import { useEstimateExecutionFillPercentSync } from './features/estimates/useEstimateExecutionPricingState';
import { useEstimateWorkflowState } from './features/estimates/useEstimateWorkflowState';
import { parseAiTaskPayload } from './utils/aiControlDescriptionUtils';
import { calcVat, daysInMonth, doPrint, generateQR, readApiResult } from './utils/appRuntimeUtils';
import { normalizeDocDate, workDocDate } from './utils/documentFormatUtils';
import { exportToExcelFile } from './utils/exportUtils';
import { cableTypeOf, isCableName } from './utils/cableUtils';
import { contractRequisitesWarning, normalizePersonKey } from './utils/performerUtils';
import { generateTempPassword } from './utils/accessUtils';
import { EMPTY_ESTIMATE_CHANGE, isApprovedEstimateChangeStatus, signedEstimateChangeTotal } from './utils/estimateChangeUtils';
import { isSameSupplyMaterial, parseOfferItems, parseSupplyItems, supplyRequestOrigin, supplyUnitKey } from './utils/supplyUtils';
import { aiSeverityMeta, estimateStatusView, materialControlStatus, materialNormCoverageMeta, materialNormStatus } from './utils/statusMetaUtils';
import { FolderKanban, Package, ScrollText, Search, Plus, Edit2, Trash2, Eye, Check, X, ChevronDown, ChevronUp, Upload, MapPin, FileText, Archive, QrCode, Calculator, Bot, GitBranch } from 'lucide-react';

installAuthFetch();

const GENERAL_WORK_ROOM_NAME = 'Без помещения';

function App() {
  const { isMobile, isCompactHeader } = useResponsiveLayout();
  const mobileLoadedScopesRef = useRef(new Set());
  const mobileApiRequestsRef = useRef(new Map());
  const [darkMode, setDarkMode] = useDarkModeState();
  const authEntryState = useAuthEntryState();
  const { setUser, user } = authEntryState;
  const appMainState = useAppMainState();
  const {
    accountablePayments, accountingDocProject, accountingTab, activePage, activeProjectTab,
    activeTabGroup, activityLog, actPayments, aiFindings, allBrigadeItems, allBrigadePayments,
    auditLog, brigadeCoef, brigadeContractItems, brigadeContracts, brigadePayments, cableJournal,
    checklists, checklistItems, clients, companyChatMessage, companyDocuments, companyMessages,
    companyName, companyReqForm, companyRequisites, confirmAcceptedQty, confirmComment,
    confirmingEntry, contracts, customRoomTypes, dailyReportDate, draftRoomDoors, draftRoomWindows,
    editingAct, editingCable, editingDoor, editingInspection, editingItem, editingJournal,
    editingPlItem, editingWindow, estimateWorkMaterials, estimateWorkParams, estimatesList,
    estimatesPage, estimatesTab, expandedActDate, expandedClient, expandedGroup, expandedMaster,
    expandedMasterProject, expandedPieceworkProject, expandedProject, expandedRoom,
    expandedStaffId, expenseReports, globalSearch, hiddenActs, history, initialDataLoaded,
    inlineEditPl, inlineEditPlData, inlineEditPrice, inspectionOrders, interimActs, inventory,
    inviteCodes, invoices, issueToolData, journalFilter, leads, listSearch, manualExpenses,
    masterProfiles, masterProjectId, masterRatings, materialInspections, materialNormOverrides,
    materialNorms, materialTransfers, materials, materialsPage, measurementDraftLoadingId,
    measurementRoomDrafts, mobileExpandedRenderLists, newAct, newBrigadeContract, newBrigadeItem,
    newBrigadePayment, newChecklist, newChecklistItem, newClient, newCompanyDoc, newContract,
    newDoor, newExpenseReport, newInspOrder, newInventory, newInvoice, newInviteRole, newLead,
    newLetter, newMeasurementDoc, newMovement, newOffer, newParticipant, newPayment, newPiecework,
    newPlItem, newPrescription, newPricelist, newProject, newProjectDoc, newRequest, newRoom,
    newStaff, newStaffDoc, newStage, newSupplier, newSupplierInvoice, newTbEntry, newTask, newTool,
    newTransfer, newUnexpected, newUser, newWarehouse, newWarrantyDefect, newWeather, newWindow,
    notifications, ownExpenses, payrollExtras, pdConsents, personnelTab, piecework,
    prescriptionsList, previewContent, previewTitle, priceHints, pricelistItems, pricelists,
    projectAiSummaries, projectChatMessage, projectChatMessages, projectDocuments, projectLetters,
    projectMeasurements, projectPayments, projectStages, projects, rejectingEntry, rejectComment,
    returnToolCondition, roomDoors, roomWindows, rooms, salaryEdits, salaryMonth, salaryPayments,
    searchUser, selectedBrigadeContract, selectedChecklist, selectedEstimate, selectedInventory,
    selectedPricelist, selectedWarehouseProject, selectedWorks, showAiAssistant, showArchive,
    showBrigadeForm, showBrigadePayModal, showDocForm, showForm, showInvites, showIssueToolModal,
    showJournalTableModal, showLetterForm, showMeasurementForm, showNotifications, showOffers,
    showPayActModal, showPhotoModal, showPiecework, showQRModal, showReimburseModal,
    showReturnToolModal, showRoomForm, showSearch, showStaffDocForm, showTransferForm,
    sidebarVisible, sitePublicationDrafts, staff, staffExpandedSections, staffProfile,
    staffProfileLoading, settingsTab, supervisorActs, supplierCatalog, supplierInvoices,
    supplierOffers, suppliers, suppliersTab, supplyClaims, supplyDeliveries, supplyHistory,
    supplyRequests, supplyTemplates, sverkaModal, tbJournal, timesheet, toolHistory, tools,
    toolsTab, unexpectedWorksList, uploadingDoc, uploadingLetter, uploadingMeasurementDoc, users,
    warehouseMain, warehouseMovements, warehouses, warehouseTab, warrantyDefects, warrantyEditForm,
    weatherLog, weatherTab, workJournal, workJournalPage, setAccountingDocProject,
    setAccountingTab, setActivePage, setActiveProjectTab, setActiveTabGroup, setAuditLog,
    setBrigadeCoef, setBrigadeContractItems, setBrigadeContracts, setBrigadePayments,
    setCableJournal, setCompanyChatMessage, setCompanyReqForm, setCompanyRequisites,
    setConfirmAcceptedQty, setConfirmComment, setConfirmingEntry, setCustomRoomTypes,
    setDailyReportDate, setDraftRoomDoors, setDraftRoomWindows, setEditingAct, setEditingCable,
    setEditingDoor, setEditingInspection, setEditingItem, setEditingJournal, setEditingPlItem,
    setEditingWindow, setEstimateDoneDrafts, setEstimateWorkMaterials, setEstimateWorkParams,
    setEstimatesList, setEstimatesTab, setExpandedActDate, setExpandedClient, setExpandedGroup,
    setExpandedMaster, setExpandedMasterProject, setExpandedPieceworkProject, setExpandedProject,
    setExpandedRoom, setExpandedStaffId, setGlobalSearch, setHiddenActs, setInlineEditPl,
    setInlineEditPlData, setInlineEditPrice, setIssueToolData, setJournalFilter, setLeads,
    setListSearch, setMasterProjectId, setMasterRatings, setMaterialInspections,
    setMaterialTransfers, setMaterials, setMeasurementDraftLoadingId, setMobileExpandedRenderLists,
    setNewAct, setNewBrigadeContract, setNewBrigadeItem, setNewBrigadePayment, setNewChecklist,
    setNewChecklistItem, setNewClient, setNewCompanyDoc, setNewContract, setNewDoor,
    setNewExpenseReport, setNewInspOrder, setNewInventory, setNewInvoice, setNewInviteRole,
    setNewLead, setNewLetter, setNewMeasurementDoc, setNewMovement, setNewOffer, setNewParticipant,
    setNewPayment, setNewPiecework, setNewPlItem, setNewPrescription, setNewPricelist,
    setNewProject, setNewProjectDoc, setNewRequest, setNewRoom, setNewStaff, setNewStaffDoc,
    setNewStage, setNewSupplier, setNewSupplierInvoice, setNewTbEntry, setNewTask, setNewTool,
    setNewTransfer, setNewUnexpected, setNewUser, setNewWarehouse, setNewWarrantyDefect,
    setNewWeather, setNewWindow, setNotifications, setPayrollExtras, setPersonnelTab,
    setPreviewContent, setPreviewTitle, setPriceHints, setPricelistItems, setProjectAiSummaries,
    setProjectChatMessage, setRejectingEntry, setRejectComment, setReturnToolCondition,
    setRoomDoors, setRoomWindows, setSalaryEdits, setSalaryMonth, setSalaryPayments, setSearchUser,
    setSelectedBrigadeContract, setSelectedChecklist, setSelectedEstimate, setSelectedInventory,
    setSelectedPricelist, setSelectedWarehouseProject, setSelectedWorks, setShowAiAssistant,
    setShowArchive, setShowBrigadeForm, setShowBrigadePayModal, setShowDocForm, setShowForm,
    setShowInvites, setShowIssueToolModal, setShowJournalTableModal, setShowLetterForm,
    setShowMeasurementForm, setShowNotifications, setShowOffers, setShowPayActModal,
    setShowPhotoModal, setShowPiecework, setShowQRModal, setShowReimburseModal,
    setShowReturnToolModal, setShowRoomForm, setShowSearch, setShowStaffDocForm,
    setShowTransferForm, setSidebarVisible, setSitePublicationDrafts, setStaffExpandedSections,
    setStaffProfile, setStaffProfileLoading, setSettingsTab, setSupplierRequisites,
    setSuppliersTab, setSverkaModal, setTbJournal, setTimesheet, setToolsTab, setUploadingDoc,
    setUploadingLetter, setUploadingMeasurementDoc, setWarehouseMain, setWarehouseTab,
    setWarrantyEditForm, setWeatherLog, setWeatherTab, setWorkJournal,
  } = appMainState;
  useSupplierRequisitesSync({ setSupplierRequisites, suppliers, user });
  const shellOverlayState = useShellOverlayState();
  const {
    companyChatInput, scanningInvoice, setCompanyChatInput, setScanningInvoice, setShowAiChat,
    setShowMobileMenu, setShowQuickActions, setShowReceiveDialog,
    setShowScanInvoice, setShowScannedInvoiceForm, setShowSystemStatus,
    showAiChat, showChatPanel, showMobileMenu, showQuickActions,
    showReceiveDialog, showScanInvoice, showScannedInvoiceForm, showSystemStatus,
    systemStatus, systemStatusLoading,
  } = shellOverlayState;
  const paymentUiState = usePaymentUiState();
  const {
    addExpenseProject, expenseSubmitting, newAccountable, newExpense, newManualExpense,
    newOwnExpense, reportingPayment, setAddExpenseProject, setExpenseSubmitting,
    setNewAccountable, setNewExpense, setNewManualExpense, setNewOwnExpense,
    setReportingPayment, setShowAccountableForm, setShowBalanceDetails,
    setShowOwnExpenseForm, showAccountableForm, showBalanceDetails, showOwnExpenseForm,
  } = paymentUiState;
  const aiAssistantState = useAiAssistantState();
  const {
    aiChat, aiInput, aiLoading, aiMessage, aiMessages, directorAgentAnswer,
    directorAgentError, directorAgentLoading, directorAgentQuestion, directorAgentSteps,
    setAiInput, setAiLoading, setAiMessage, setAiMessages,
    setDirectorAgentQuestion,
  } = aiAssistantState;
  const estimateNormReviewQueuedRef = useRef(new Set());
  const estimateQualityReviewQueuedRef = useRef(new Set());
  const estimateDiffReviewQueuedRef = useRef(new Set());
  const estimateChangeReconcileQueuedRef = useRef(new Set());
  const materialControlTaskQueuedRef = useRef(new Set());
  const roomControlTaskQueuedRef = useRef(new Set());
  const supplyWorkflowState = useSupplyWorkflowState();
  const {
    compareLoadingReqId, compareResultByReq, deliveryAiLoadingId, deliveryAiResultById,
    generatedInviteLink, newOfferInvoice, newSupplyReq,
    receiveForm, receivingDeliveryId, requestKpLoading, selectedSupplierIds,
    setCompareLoadingReqId, setCompareResultByReq, setDeliveryAiLoadingId, setDeliveryAiResultById,
    setGeneratedInviteLink, setInvoicingOfferId, setNewOfferInvoice, setNewSupplyReq,
    setReceiveForm, setReceivingDeliveryId, setRequestKpLoading, setSelectedSupplierIds,
    setShipmentForm, setShippingOfferId, setShowRequestKpModal, setShowSupplierInviteModal, setShowSupplyForm,
    setSuggestedSuppliers, setSupplierInviteForm, setSupplyAiLoading, setSupplyAiText, setSupplyCollapsedProjects,
    setSupplyExpandedId, setSupplyRejectId, setSupplyRejectReason, setSupplyStockCheck, setSupplyTab,
    shipmentForm, showRequestKpModal, showSupplierInviteModal, showSupplyForm,
    suggestedSuppliers, supplierInviteForm, supplyAiLoading, supplyAiText, supplyCollapsedProjects,
    supplyExpandedId, supplyRejectId, supplyRejectReason, supplyStockCheck, supplyTab,
  } = supplyWorkflowState;
  const materialNormsState = useMaterialNormsState();
  const {
    editingMaterialNormId, estimateProjectFilter, estimateSearch, materialNormCoverageProject,
    materialNormNotice, materialNormPreviewSuggestions, materialNormSearch,
    materialNormSuggestionLoading, materialNormsPage, newMaterialNorm,
    setEstimateProjectFilter, setEstimateSearch,
    setMaterialNormCoverageProject, setMaterialNormNotice, setMaterialNormPreviewSuggestions,
    setMaterialNormSearch, setNewMaterialNorm, setShowArchivedEstimates, showArchivedEstimates,
  } = materialNormsState;
  const {
    fileSrc,
    lowStockFor,
    matchSearch,
    nextEstimateVersionFor,
    projectFactSpent,
  } = createAppUtilityRuntime({
    API,
    allBrigadeItems,
    estimatesList,
    materials,
    nextEstimateVersionForFromList,
    workJournal,
  });
  const {
    creatingFromEstimate, distributeAssignments, distributeBrigades, distributing,
    estimateChatInput, estimateChatLoading, estimateChatMessages, estimateIssueFocusKey,
    estimateVersions, executionPriceFillPercent, fromEstimateForm, generateForm,
    generatePricelistForm, generating, generatingPricelist, importValidating,
    importValidationWarnings, newDistributeBrigade, newEstimate, newEstimateItem,
    newEstimateSection, selectedVersionsToCompare, setCreatingFromEstimate,
    setDistributeAssignments, setDistributeBrigades, setDistributing, setEstimateChatInput,
    setEstimateChatLoading, setEstimateChatMessages, setEstimateIssueFocusKey,
    setEstimateVersions, setExecutionPriceFillPercent, setFromEstimateForm, setGenerateForm,
    setGeneratePricelistForm, setGenerating, setGeneratingPricelist, setImportValidating,
    setImportValidationWarnings, setNewDistributeBrigade, setNewEstimate, setNewEstimateItem,
    setNewEstimateSection, setSelectedVersionsToCompare, setShowDistribute, setShowEstimateChat,
    setShowEstimateIssuesOnly, setShowEstimateWorkSummary, setShowFromEstimate,
    setShowGenerateEstimate, setShowGeneratePricelist, setShowVersionHistory,
    setShowWorkAssignment, showDistribute, showEstimateChat, showEstimateIssuesOnly,
    showEstimateWorkSummary, showFromEstimate, showGenerateEstimate, showGeneratePricelist,
    showVersionHistory, showWorkAssignment,
  } = useEstimateWorkflowState();
  const selectedEstimateExecutionFillPercent = estimateExecutionFillPercentOf(selectedEstimate);
  useEstimateExecutionFillPercentSync({
    selectedEstimate,
    selectedEstimateExecutionFillPercent,
    setExecutionPriceFillPercent,
  });

  const persistEstimate = async (est) => persistEstimateAction({
    API,
    est,
    estimateListWithUpdatedEstimate,
    estimatesList,
    queueEstimateNormReviewTask,
    queueEstimateQualityReviewTask,
  });

  const sidebarRef = useRef(null);
  const chatEndRef = useRef(null);

  const showPreview = (content, title) => { setPreviewContent(content); setPreviewTitle(title); };

  const {
    addActivity, apiAuthHeaders, appendPhotos, askDirectorAgent, canAccess,
    checkinGeo, closeNotifications, confirmMaterialReceipt, createProjectFromLead,
    deleteBrigadePayment, deleteLead, getNotifPage, handleLogin, handleLogout,
    handleRegister, handleTwoFactorLogin, isFinanceRole, loadAll, loadAuditLog,
    loadChecklistItems, loadMaterialNormsPage, loadMaterialsPage,
    loadPricelistItems, loadProjectChat, loadWorkJournalPage, markMyNotificationsRead,
    myNotifications, navigateTo, notify, openBrigadeContract, openSystemStatus,
    refreshData, returnMaterialToProject, saveActPayment, saveBrigadePayment,
    saveLead, saveProfile, searchResults, selectableActiveProjects, sendAiMessage,
    sendCompanyChatMessage, sendProjectChatMessage, setShowChatPanel, toggleNotifications,
    unreadMessagesCount, uploadPhoto, visibleActiveProjects, visibleEstimatesForCurrentUser,
    visibleProjects,
  } = useAppCoreRuntime({
    API,
    ROLES,
    aiAssistantState,
    appMainState,
    authEntryState,
    layout: { isMobile },
    limits: { AUDIT_LOG_PAGE_LIMIT, MATERIAL_NORMS_PAGE_LIMIT, MATERIALS_PAGE_LIMIT, WORK_JOURNAL_PAGE_LIMIT },
    materialNormsState,
    refs: { chatEndRef, mobileApiRequestsRef, mobileLoadedScopesRef },
    shellOverlayState,
  });
  const {
    acceptMaterialAliasTask,
    acceptMaterialNormSuggestion,
    acceptMaterialNormSuggestionAsOverride,
    activeEstimatesForProject,
    activeMaterialNormSuggestions,
    addEstimateMaterialFromCoverage,
    aiFindingsForProject,
    aiTasksForProject,
    applyMaterialOverNormReason,
    autoFillNormMaterialsForWork,
    autoReconcileEstimateChanges,
    buildDirectorBriefReportContent,
    buildEstimateDiffContent,
    buildMaterialNormCoverageContent,
    buildSupplyControlReportContent,
    calcSalary,
    canonicalMaterialMeta,
    canCreateSupplyRequestFromNorm,
    canEditMaterialNorms,
    canUseDirectorAgent,
    computeNotifications,
    createBatchSupplyRequestFromMaterialControl,
    createBatchSupplyRequestFromNormCoverage,
    createEstimateFromNormSuggestions,
    createEstimateReconciliation,
    createInvoiceControlReviewTasksForInvoice,
    createMaterialNormCoverageTask,
    createSupplyRequestFromNormCoverage,
    createTaskFromMaterialNormSuggestion,
    deleteEstimateRemote,
    directorMapActionTarget,
    directorMapContractForProject,
    disableMaterialNorm,
    documentActionRefs,
    editMaterialNorm,
    estimateChangeRowsForDocs,
    estimateChangesForNewEstimate,
    estimateControlIssues,
    estimateDiffBaseFor,
    estimateItemOptionsForProject,
    estimateListWithUpdatedEstimate,
    estimateNormCoverageRows,
    estimateReconciliationsForProject,
    estimateWorkNormRequirementRows,
    expByCategory,
    financeUsers,
    formatSignedRub,
    generateAiFindingsForProject,
    generateMaterialNormSuggestions,
    getActStatusForJournal,
    getProjectEstimateWorkOptions,
    getProjectWorkPackageOptions,
    getRoomNetWall,
    includableEstimateChanges,
    includeChangesInNewEstimate,
    isDirector,
    isLeadership,
    isMasterRole,
    isPersonalMaterialRole,
    isProrab,
    isSupplyDeliveryInvoice,
    jumpToEstimateIssue,
    ks2ItemsFromEstimate,
    lowMainStock,
    lowStock,
    markEstimateWorkNoMaterialFromCoverage,
    materialAvailabilityMapForWork,
    materialControlSummaryForProject,
    materialHintForProject,
    materialNameKey,
    materialNormControlSummaryForProject,
    materialNormForWork,
    materialNormOverrunReason,
    materialNormSupplyRequestExists,
    materialReconciliationRows,
    materialRowsAvailableForWork,
    materialSuggestionsForWork,
    materialWriteoffBlockMessage,
    openAiTaskAction,
    openEstimateControlReport,
    openEstimateDetail,
    personalMaterialRowsForProject,
    projectBudgetSpent,
    projectEconomy,
    projectObjectLinks,
    projectPaymentInAmount,
    projectPaymentSignedAmount,
    projectPlanDone,
    projectRealProgress,
    queueEstimateDiffReviewTask,
    queueEstimateNormReviewTask,
    queueEstimateQualityReviewTask,
    rejectMaterialNormSuggestion,
    removeEstimateWorkMaterial,
    removeSelectedWorkMaterial,
    renderEstimateChangeReconcileTask,
    renderEstimateMeasurementComparisonPanel,
    renderEstimateReconciliationsPanel,
    renderInvoiceControlActions,
    renderMaterialAliasControls,
    renderMaterialReconciliationPanel,
    renderMaterialSupplyAction,
    renderMaterialWriteoffStatus,
    renderWorkJournalEstimateReconciliationPanel,
    resetMaterialNormForm,
    roleColor,
    roomCompleteness,
    roomMeasurementCheck,
    roomMeasurementMessage,
    saveMaterialNorm,
    saveMaterialNormOverrideFromCoverage,
    setEstimateStatusRemote,
    updateAiFinding,
    updateAiTask,
    updateEstimateWorkMaterialQty,
    updateSelectedWorkMaterialQty,
    upsertEstimateWorkMaterial,
    upsertSelectedWorkMaterial,
    warehouseInvoiceEstimateControl,
    warehouseInvoiceItems,
    workExecutionTotal,
    workedDays,
    workNeedsThicknessParam,
  } = useAppBusinessRuntime({
    API,
    constants: { ESTIMATE_PACKAGES, EXPENSE_CATEGORIES },
    appMainState,
    coreRuntime: {
      apiAuthHeaders,
      isFinanceRole,
      navigateTo,
      notify,
      refreshData,
      visibleActiveProjects,
    },
    estimateWorkflowState: { setEstimateIssueFocusKey },
    materialNormsState,
    refs: {
      estimateChangeReconcileQueuedRef,
      estimateDiffReviewQueuedRef,
      estimateNormReviewQueuedRef,
      estimateQualityReviewQueuedRef,
      materialControlTaskQueuedRef,
      roomControlTaskQueuedRef,
    },
    layout: { isMobile },
    ui: { C, badge, btnB, btnG, btnO, card, tbl, tblC, tblH },
    utilities: { lowStockFor, projectFactSpent },
    selectors: {
      isApprovedEstimateChangeStatus,
      parseSupplyItems,
      sectionsOfEstimate: _sectionsOfEst,
      visibleEstimatesForCurrentUser,
    },
    showPreview,
    persistEstimate,
  });

  const {
    addPiecework,
    addStaffDoc,
    createContract,
    createInterimAct,
    createStaffAccessFromPrompt,
    deleteContract,
    deleteInterimAct,
    deletePiecework,
    deleteStaff,
    findUserForStaff,
    openStaffProfile,
    paySalary,
    ratemaster,
    resetStaffAccessPassword,
    resolveContractPerformer,
    saveStaff,
    setPayrollExtra,
    setSalaryEdit,
    toggleDay,
  } = createPersonnelActions({
    API,
    ROLE_LABELS,
    contracts,
    editingItem,
    expandedStaffId,
    masterProfiles,
    masterRatings,
    newAct,
    newContract,
    newPiecework,
    newStaff,
    newStaffDoc,
    notify,
    readApiResult,
    refreshData,
    setEditingItem,
    setExpandedStaffId,
    setNewAct,
    setNewContract,
    setNewPiecework,
    setNewStaff,
    setNewStaffDoc,
    setMasterRatings,
    setPayrollExtras,
    setSalaryPayments,
    setSalaryEdits,
    setShowForm,
    setShowStaffDocForm,
    setStaffProfile,
    setStaffProfileLoading,
    setTimesheet,
    projects,
    staff,
    user,
    users,
    workJournal,
  });

  const {
    buildActContent,
    buildBrigadeActContent,
    buildCableJournalContent,
    buildContractContent,
    buildDailyObjectReportContent,
    buildHiddenActContent,
    buildInventoryDoc,
    buildInvoiceContent,
    buildJPRContent,
    buildM15Content,
    buildAOSKContent,
    buildKS11Content,
    buildKS14Content,
    buildIGDContent,
    buildSpecJournalContent,
    buildM2Content,
    buildM8Content,
    buildMaterialRequirementContent,
    buildVATBookContent,
    buildSupplementaryAgreementContent,
    buildExecPackageContent,
    buildM29Content,
    buildSupervisorMonthlyReport,
    buildKS3Content,
    buildMaterialInspectionContent,
    buildMovementDoc,
    buildPassportContent,
    buildPositionInstructionContent,
    buildPrescriptionContent,
    buildPricelistContent,
    buildTBContent,
    buildWorkJournalContent,
    showKS2,
  } = createDocumentActions({
    accountablePayments,
    activeEstimatesForProject,
    actPayments,
    allBrigadeItems,
    calcDoorArea,
    calcDoorReveals,
    calcVat,
    calcWindowArea,
    calcWindowReveals,
    cableJournal,
    cableTypeOf,
    companyName,
    companyRequisites,
    contractRequisitesWarning,
    estimateChangeRowsForDocs,
    estimateWorkNormRequirementRows,
    expByCategory,
    generateQR,
    getRoomNetWall,
    hiddenActs,
    interimActs,
    isFinanceRole,
    isSupplyDeliveryInvoice,
    ks2ItemsFromEstimate,
    materialInspections,
    materialNormControlSummaryForProject,
    materialReconciliationRows,
    materialTransfers,
    masterProfiles,
    ownExpenses,
    prescriptionsList,
    projects,
    resolveContractPerformer,
    roomDoors,
    rooms,
    roomWindows,
    showPreview,
    supervisorActs,
    supplierInvoices,
    tbJournal,
    tools,
    user,
    users,
    warehouseInvoiceEstimateControl,
    warehouseInvoiceItems,
    weatherLog,
    workJournal,
  });
  documentActionRefs.buildMaterialRequirementContent = buildMaterialRequirementContent;

  const unreadNotifications = myNotifications(notifications).filter(n=>!n.read).length;

  const exportToExcel = exportToExcelFile;

  const {
    saveProject,
    updateProjectProgress,
    editProject,
    projectSiteDraft,
    updateProjectSiteDraft,
    saveProjectSitePublication,
    addTask,
    removeTask,
    saveClient,
    deleteClient,
  } = createProjectCrudActions({
    API,
    brigadeContracts,
    editingItem,
    newClient,
    newProject,
    newTask,
    notify,
    projects,
    readApiResult,
    refreshData,
    setEditingItem,
    setNewClient,
    setNewProject,
    setNewTask,
    setShowForm,
    setSitePublicationDrafts,
    sitePublicationDrafts,
    addActivity,
  });

  const {
    applyWarehouseMovement,
    deleteMaterial,
    deleteMainMaterial,
    openReceiveInvoice,
    saveInvoiceNew,
    saveTool,
    deleteTool,
    issueTool,
    returnTool,
  } = createWarehouseCrudActions({
    API,
    addActivity,
    calcVat,
    createInvoiceControlReviewTasksForInvoice,
    editingItem,
    getProjectWorkPackageOptions,
    issueToolData,
    newInvoice,
    newMovement,
    newTool,
    notify,
    projects,
    refreshData,
    returnToolCondition,
    setEditingItem,
    setIssueToolData,
    setNewInvoice,
    setNewMovement,
    setNewTool,
    setReturnToolCondition,
    setShowReceiveDialog,
    setShowForm,
    setShowIssueToolModal,
    setShowReturnToolModal,
    setShowScanInvoice,
    suppliers,
    user,
  });

  const {
    addMasterWorks,
    confirmJ,
    openConfirmModal,
    rejectJ,
    submitEstimateWorkDone,
  } = createWorkJournalActions({
    API,
    GENERAL_WORK_ROOM_NAME,
    addActivity,
    applyMaterialOverNormReason,
    autoFillNormMaterialsForWork,
    denormalizeMeasure,
    estimatePackage,
    estimateWorkKey,
    estimateWorkMaterials,
    estimateWorkParams,
    estimatesList,
    fmtMeasure,
    isFinanceRole,
    isPersonalMaterialRole,
    materialNameKey,
    materialNormOverrunReason,
    materialWriteoffBlockMessage,
    masterProjectId,
    notify,
    pricelistItems,
    pricelists,
    projects,
    refreshData,
    roomMeasurementCheck,
    roomMeasurementMessage,
    rooms,
    selectedWorks,
    setConfirmAcceptedQty,
    setConfirmComment,
    setConfirmingEntry,
    setEstimateDoneDrafts,
    setEstimateWorkMaterials,
    setEstimateWorkParams,
    setEstimatesList,
    setMasterProjectId,
    setPricelistItems,
    setRejectComment,
    setRejectingEntry,
    setSelectedWorks,
    toNum,
    updateProjectProgress,
    user,
  });

  const {
    saveUser,
    toggleUserActive,
    deleteUser,
    resetUserTwoFactor,
    createInvite,
    createSupplierInvite,
    deleteInvite,
  } = createUserAccessActions({
    API,
    editingItem,
    newInviteRole,
    newUser,
    refreshData,
    setEditingItem,
    setGeneratedInviteLink,
    setNewUser,
    setShowForm,
    supplierInviteForm,
    suppliers,
    user,
  });

  const {
    savePricelist,
    deletePricelist,
    copyPricelist,
    savePlItem,
    startInlinePlEdit,
    cancelInlinePlEdit,
    saveInlinePlItem,
    deletePlItem,
  } = createPricelistActions({
    API,
    editingItem,
    editingPlItem,
    inlineEditPlData,
    inlineEditPrice,
    loadPricelistItems,
    newPlItem,
    newPricelist,
    refreshData,
    selectedPricelist,
    setEditingItem,
    setEditingPlItem,
    setInlineEditPl,
    setInlineEditPlData,
    setInlineEditPrice,
    setNewPlItem,
    setNewPricelist,
    setPricelistItems,
    setSelectedPricelist,
    setShowForm,
  });

  const {
    approveOffer,
    approveSupplyAsDirector,
    askSupplyAi,
    cancelRequest,
    cancelSupply,
    confirmSupplyAsProrab,
    createInvoiceFromOffer,
    createShipmentFromOffer,
    createSupplyReq,
    deleteSupplier,
    deleteSupplyTemplate,
    fetchPriceHint,
    loadSupplyStockCheck,
    openRequestKpModal,
    receiveSupplyDelivery,
    rejectSupplierOffer,
    rejectSupply,
    runCompareKp,
    runDeliveryAiCheck,
    saveOffer,
    saveRequest,
    saveSupplier,
    saveSupplyTemplate,
    selectSupplierOffer,
    sendKpRequest,
    applySupplyTemplate,
  } = createSupplyActions({
    API,
    editingItem,
    getProjectWorkPackageOptions,
    newOffer,
    newOfferInvoice,
    newRequest,
    newSupplier,
    newSupplyReq,
    notify,
    priceHints,
    receiveForm,
    refreshData,
    selectedSupplierIds,
    setCompareLoadingReqId,
    setCompareResultByReq,
    setDeliveryAiLoadingId,
    setDeliveryAiResultById,
    setEditingItem,
    setInvoicingOfferId,
    setNewOffer,
    setNewOfferInvoice,
    setNewRequest,
    setNewSupplier,
    setNewSupplyReq,
    setPriceHints,
    setReceiveForm,
    setReceivingDeliveryId,
    setRequestKpLoading,
    setSelectedSupplierIds,
    setShipmentForm,
    setShippingOfferId,
    setShowForm,
    setShowRequestKpModal,
    setShowSupplyForm,
    setSuggestedSuppliers,
    setSupplyAiLoading,
    setSupplyAiText,
    setSupplyRejectId,
    setSupplyRejectReason,
    setSupplyStockCheck,
    shipmentForm,
    showRequestKpModal,
    suggestedSuppliers,
    supplyRejectReason,
    supplyRequests,
    supplyTemplates,
    user,
  });

  const {
    approveUnexpectedWork,
    deleteDoor,
    deleteRoom,
    deleteStage,
    deleteWarehouse,
    deleteWindow,
    saveChecklist,
    saveCompanyRequisites,
    saveDoor,
    savePrescription,
    saveProjectStage,
    saveRoom,
    saveTbEntry,
    saveUnexpectedWork,
    saveWarehouse,
    saveWeather,
    saveWindow,
    toggleChecklistItem,
    updateDoor,
    updateStage,
    updateWindow,
  } = createProjectOperationActions({
    API,
    CHECKLIST_TEMPLATES,
    EMPTY_ESTIMATE_CHANGE,
    companyReqForm,
    customRoomTypes,
    draftRoomDoors,
    draftRoomWindows,
    editingItem,
    loadChecklistItems,
    newChecklist,
    newDoor,
    newPrescription,
    newRoom,
    newStage,
    newUnexpected,
    newWarehouse,
    newWeather,
    newWindow,
    notify,
    refreshData,
    roomDoors,
    roomWindows,
    setCustomRoomTypes,
    setDraftRoomDoors,
    setDraftRoomWindows,
    setEditingDoor,
    setEditingItem,
    setEditingWindow,
    setExpandedRoom,
    setNewChecklist,
    setNewDoor,
    setNewPrescription,
    setNewRoom,
    setNewStage,
    setNewUnexpected,
    setNewWarehouse,
    setNewWeather,
    setNewWindow,
    setRoomDoors,
    setRoomWindows,
    setShowForm,
    setShowRoomForm,
    setTbJournal,
    setWeatherLog,
    tbJournal,
    toNum,
    user,
    weatherLog,
  });

  const {
    renderSupplyPlanningHint,
    renderSupplyRequestOrigin,
  } = createSupplyPlanningUi({
    C,
    btnB,
    btnG,
    projects,
    user,
    navigateTo,
    setExpandedProject,
    setActiveProjectTab,
    setActiveTabGroup,
    setWarehouseTab,
    supplyRequestOrigin,
    newSupplyReq,
    setNewSupplyReq,
    materialReconciliationRows,
    canonicalMaterialMeta,
    isSameSupplyMaterial,
    supplyUnitKey,
    toNum,
    fmtMeasure,
  });

  const pageFallback = <AppPageFallback C={C} card={card} isMobile={isMobile} />;

  const earlyRoleRoute = renderAppEarlyRoleRoute({
    constants: { EXPENSE_CATEGORIES, PD_CONSENT_TEXT, ROLE_LABELS, SURFACES, UNITS },
    data: {
      actions: {
        addMasterWorks, appendPhotos, applySupplyTemplate, autoFillNormMaterialsForWork,
        checkinGeo, closeNotifications, confirmMaterialReceipt, createInvoiceFromOffer,
        createShipmentFromOffer, createSupplyReq, deleteSupplyTemplate, fetchPriceHint,
        getNotifPage, handleLogin, handleLogout, handleRegister, handleTwoFactorLogin,
        loadAll, loadPricelistItems, markMyNotificationsRead, myNotifications, navigateTo,
        notify, refreshData, removeEstimateWorkMaterial, removeSelectedWorkMaterial,
        renderMaterialWriteoffStatus, renderSupplyPlanningHint, renderSupplyRequestOrigin,
        returnMaterialToProject, roleColor, saveProfile, saveSupplyTemplate,
        selectableActiveProjects, sendCompanyChatMessage, showPreview, submitEstimateWorkDone,
        toggleNotifications, updateEstimateWorkMaterialQty, updateProjectProgress,
        updateSelectedWorkMaterialQty, uploadPhoto, upsertEstimateWorkMaterial,
        upsertSelectedWorkMaterial, visibleEstimatesForCurrentUser,
      },
      appMainState,
      authEntryState,
      builders: {
        buildActContent, buildCableJournalContent, buildContractContent, buildHiddenActContent,
        buildKS3Content, buildPrescriptionContent, buildSupervisorMonthlyReport,
        buildSupplementaryAgreementContent, showKS2,
      },
      materialRuntime: {
        isPersonalMaterialRole, materialAvailabilityMapForWork, materialHintForProject,
        materialNameKey, materialNormForWork, materialRowsAvailableForWork,
        materialSuggestionsForWork, personalMaterialRowsForProject, workNeedsThicknessParam,
      },
      paymentUiState,
      projectRuntime: {
        activeEstimatesForProject, computeNotifications, projectPlanDone, roomMeasurementCheck,
        roomMeasurementMessage,
      },
      supplyWorkflowState,
      user,
    },
    pageFallback,
    selectors: {
      cableTypeOf, doPrint, estimateItemDoneTotal, estimateItemMaterialSum, estimateItemTotal,
      estimatePackage, estimateWorkKey, fileSrc, fmtMeasure, isApprovedEstimateChangeStatus,
      isMasterRole, matchSearch, materialControlStatus, materialNormStatus, normalizeMeasure,
      parseSupplyItems, projectRealProgress, sectionsOfEstimate: _sectionsOfEst,
      supplyRequestOrigin, toNum, unreadNotifications,
    },
    ui: { API, C, badge, btnB, btnG, btnGr, btnO, btnR, card, inp, isMobile, tbl, tblC, tblH },
  });
  if (earlyRoleRoute) return earlyRoleRoute;

  const allMenuItems = buildAppMenuItems();

  const {
    fillSelectedEstimateExecutionPrices,
    handleDetectEstimateHiddenWorks,
    handleEstimateAiAnalysis,
    handleEstimateImportFile,
    handleExportSelectedEstimate,
    handleNormalizeSelectedEstimateImport,
    handleOpenEstimateDistribute,
    handleOpenSelectedEstimateChat,
    handleOpenSelectedEstimateHistory,
    handleOpenWorkAssignment,
    handlePreviewSelectedEstimate,
    handleShowSelectedEstimateDiff,
    handleToggleSelectedEstimateTemplate,
    selectedEstimateExecutionPriceStats,
    sendAiAssistantMessage,
    sendEstimateChatMessage,
  } = createEstimatePageActions({
    API,
    ROLE_LABELS,
    applyEstimateActivationState,
    aiMessages,
    autoReconcileEstimateChanges,
    brigadeContracts,
    buildEstimateDiffContent,
    contracts,
    createEstimateReconciliation,
    enrichEstimateMeasurementBasis,
    estimateDiffBaseFor,
    estimateItemMaterialSum,
    estimateItemTotal,
    estimateItemTypeMeta,
    estimateItemWorkSum,
    estimateChatInput,
    estimateChatLoading,
    estimateChatMessages,
    estimateListWithUpdatedEstimate,
    estimateMeasurementBasisMeta,
    estimateMeasurementBasisOf,
    estimateQualityRows,
    executionPriceFillPercent,
    exportToExcel,
    estimatesList,
    isGlobalEstimateTemplate,
    isLeadership,
    isEstimateWorkItem,
    materials,
    newEstimate,
    nextEstimateVersionFor,
    normalizeEstimateImportSections,
    normalizeEstimateItemType,
    projects,
    queueEstimateDiffReviewTask,
    queueEstimateNormReviewTask,
    queueEstimateQualityReviewTask,
    readApiResult,
    sameEstimateGroup,
    selectedEstimate,
    setAiInput,
    setAiLoading,
    setAiMessages,
    setDistributeAssignments,
    setDistributeBrigades,
    setEstimateChatInput,
    setEstimateChatLoading,
    setEstimateChatMessages,
    setEstimateVersions,
    setEstimatesList,
    setEstimatesTab,
    setExecutionPriceFillPercent,
    setImportValidating,
    setImportValidationWarnings,
    setSelectedEstimate,
    setSelectedVersionsToCompare,
    setShowAiChat,
    setShowDistribute,
    setShowEstimateChat,
    setShowVersionHistory,
    setShowWorkAssignment,
    showPreview,
    staff,
    toNum,
    user,
  });

  const menuItems = allMenuItems.filter(item=>canAccess(item.id));

  const estimatesPageContext = {
    acceptMaterialNormSuggestion, acceptMaterialNormSuggestionAsOverride, activeEstimateFromList, activeMaterialNormSuggestions, addEstimateMaterialFromCoverage, allBrigadeItems, API, applyEstimateActivationState,
    autoReconcileEstimateChanges, badge, brigadeContracts, btnB, btnG, btnGr, btnO, btnR,
    btnState, buildEstimateDiffContent, buildEstimateWorkSummary, buildMaterialNormCoverageContent, C, canCreateSupplyRequestFromNorm, canEditMaterialNorms, card,
    createBatchSupplyRequestFromNormCoverage, createEstimateFromNormSuggestions, createEstimateReconciliation, createMaterialNormCoverageTask, createSupplyRequestFromNormCoverage, createTaskFromMaterialNormSuggestion, deleteEstimateRemote, disableMaterialNorm,
    editingMaterialNormId, editMaterialNorm, enrichEstimateMeasurementBasis, ESTIMATE_PACKAGES, EstimateAddSectionForm, EstimateCreateActions, EstimateCreateFormFields, estimateDiffBaseFor,
    estimateDisplayVersion, EstimateDuplicateWorkSummaryPanel, EstimateExecutionPricingPanel, estimateGroupKey, EstimateImportValidationBanner, EstimateImportView, estimateIssueDomId, estimateIssueFocusKey,
    estimateItemTotal, estimateKind, estimateNormCoverageRows, estimatePackage, estimateProjectFilter, estimateQualityRows, estimateSearch, EstimateSearchResults,
    EstimateSectionsEditor, EstimateSelectedToolbar, estimatesList, EstimatesListToolbar, EstimatesListView, estimatesPage, estimatesTab, EstimatesTabsNav,
    estimateStatusView, estimateTotal, EstimateTotalCard, estimateTypeIcon, estimateUpdatedTs, estimateVersionChain, executionPriceFillPercent, exportToExcel,
    fillSelectedEstimateExecutionPrices, fmtMeasure, generateMaterialNormSuggestions, handleDetectEstimateHiddenWorks, handleEstimateAiAnalysis, handleEstimateImportFile, handleExportSelectedEstimate, handleNormalizeSelectedEstimateImport,
    handleOpenEstimateDistribute, handleOpenSelectedEstimateChat, handleOpenSelectedEstimateHistory, handleOpenWorkAssignment, handlePreviewSelectedEstimate, handleShowSelectedEstimateDiff, handleToggleSelectedEstimateTemplate, importValidating,
    importValidationWarnings, inp, isArchivedEstimate, isDirector, isGlobalEstimateTemplate, isLeadership, isMobile, jumpToEstimateIssue,
    loadAll, loadMaterialNormsPage, markEstimateWorkNoMaterialFromCoverage, materialNormCanCreateSupply, materialNormCoverageComment, materialNormCoverageDisplayRows, materialNormCoverageExportRows, materialNormCoverageMeta,
    materialNormCoverageProject, MaterialNormCoverageSection, MaterialNormFormPanel, materialNormNotice, MaterialNormNotice, materialNormOverrides, MaterialNormOverridesPanel, materialNormPreviewSuggestions,
    materialNormRuleForCalc, materialNorms, materialNormSearch, MaterialNormsHeader, MaterialNormsListPanel, materialNormsPage, materialNormSuggestionLoading, MaterialNormSuggestionsPanel,
    materialNormSupplyRequestExists, materialTitleForNormRule, mobileExpandedRenderLists, newEstimate, newEstimateItem, newEstimateSection, newMaterialNorm, nextEstimateVersionFor,
    openEstimateDetail, persistEstimate, projects, queueEstimateDiffReviewTask, queueEstimateNormReviewTask, queueEstimateQualityReviewTask, readApiResult, refreshData,
    rejectMaterialNormSuggestion, resetMaterialNormForm, sameEstimateGroup, saveMaterialNorm, saveMaterialNormOverrideFromCoverage, selectedEstimate, selectedEstimateExecutionPriceStats, setActivePage,
    setEstimateProjectFilter, setEstimateSearch, setEstimatesList, setEstimatesTab, setEstimateStatusRemote, setExecutionPriceFillPercent, setGenerateForm, setImportValidationWarnings,
    setMaterialNormCoverageProject, setMaterialNormNotice, setMaterialNormPreviewSuggestions, setMaterialNormSearch, setMobileExpandedRenderLists, setNewEstimate, setNewEstimateItem, setNewEstimateSection,
    setNewMaterialNorm, setSelectedEstimate, setShowArchivedEstimates, setShowEstimateIssuesOnly, setShowEstimateWorkSummary, setShowForm, setShowGenerateEstimate, showArchivedEstimates,
    showEstimateIssuesOnly, showEstimateWorkSummary, showForm, showPreview, user, visibleActiveProjects, visibleEstimatesForCurrentUser, WORK_MATERIAL_NORM_RULES,
    WorkAssignmentStatusPanel,
  };

  const projectsPageContext = {
    API, Archive, Bot, C, CHECKLIST_TEMPLATES, Calculator, Check, ChevronDown,
    ChevronUp, DIRECTOR_MAP_FEATURE_ENABLED, DOOR_PURPOSES, DOOR_TYPES, EMPTY_ESTIMATE_CHANGE, ESTIMATE_CHANGE_TYPES, ESTIMATE_CHANGE_VISIBLE_STATUSES, ESTIMATE_PACKAGES,
    EXPENSE_CATEGORIES, Edit2, Eye, FileText, FolderKanban, GitBranch, MapPin, PROJECT_MEASUREMENT_DOC_TYPES,
    PROJECT_MEASUREMENT_SOURCE_TYPES, PROJECT_MEASUREMENT_STATUSES, Package, PhotoAttachmentField, Plus, ProjectBrigadeCalculationTab, ProjectCardHeader, ProjectDirectorMapPanel,
    ProjectDocumentsRegistryPanel, ProjectEconomyPanel, ProjectFinancePanel, ProjectHiddenWorksActsPanel, ProjectLaunchPanel, ProjectLettersPanel, ProjectMaterialsControlPanel, ProjectMaterialsStockPanel,
    ProjectMaterialsTransferPanel, ProjectObjectLinksPanel, ProjectPrescriptionsPanel, ProjectSafetyJournalPanel, ProjectScheduleSummaryPanel, ProjectTabsNav, ProjectWorkJournalPanel, QrCode,
    REVEAL_MATERIALS, STAGE_STATUSES, ScrollText, Search, TB_INSTRUCTIONS, TB_TYPES_GOST, Trash2, UNITS,
    Upload, WINDOW_TYPES, X, _normalizeUnit, _sectionsOfEst, acceptMaterialAliasTask, accountablePayments, activeEstimatesForProject,
    activeProjectTab, activeTabGroup, addTask, aiFindingsForProject, aiSeverityMeta, aiTasksForProject, appendPhotos, approveUnexpectedWork,
    badge, brigadeCoef, brigadeContractItems, brigadeContracts, brigadePayments, btnB, btnG, btnGr,
    btnO, btnR, buildCableJournalContent, buildHiddenActContent, buildJPRContent, buildKS3Content, buildM15Content, buildMaterialInspectionContent,
    buildMaterialRequirementContent, buildPassportContent, buildSupplementaryAgreementContent, buildTBContent, cableJournal, cableTypeOf, isCableName, calcDoorArea, calcDoorReveals,
    calcWindowArea, calcWindowReveals, card, checklistItems, checklists, companyName, companyRequisites, convertUnits,
    createBatchSupplyRequestFromMaterialControl, createProjectMeasurementActions, customRoomTypes, deleteBrigadePayment, deleteDoor, deleteRoom, deleteStage, deleteWindow,
    denormalizeMeasure, directorMapActionTarget, directorMapContractForProject, draftRoomDoors, draftRoomWindows, editProject, editingDoor, editingItem,
    editingWindow, estimateChangesForNewEstimate, estimateImportedPlanMeasure, estimateItemOptionsForProject, estimateItemTotal, estimateKind, estimateMaterialPlanIssue, estimatePackage,
    estimateReconciliationsForProject, estimateSearch, estimateWorkNormRequirementRows, estimatesList, expByCategory, expandedProject, expandedRoom, fileSrc,
    fmtMeasure, formatSignedRub, generateAiFindingsForProject, getActStatusForJournal, getRoomNetWall, hiddenActs, history, includableEstimateChanges,
    includeChangesInNewEstimate, inp, inspectionOrders, isApprovedEstimateChangeStatus, isEstimateMaterialItem, isEstimatePricelist, isEstimateWorkItem, isFinanceRole,
    isLeadership, isMobile, isProrab, listSearch, loadAll, loadChecklistItems, loadProjectChat, loadWorkJournalPage,
    manualExpenses, masterProfiles, matchSearch, materialControlStatus, materialControlSummaryForProject, materialInspections, materialNameKey, materialNormControlSummaryForProject,
    materialReconciliationRows, materialTransfers, materials, measurementDraftLoadingId, measurementRoomDrafts, mobileExpandedRenderLists, navigateTo, newAccountable,
    newBrigadeContract, newBrigadeItem, newChecklist, newChecklistItem, newDoor, newInspOrder, newLetter, newMeasurementDoc,
    newParticipant, newPrescription, newProject, newProjectDoc, newRoom, newStage, newTask, newTbEntry,
    newTransfer, newUnexpected, newWarrantyDefect, newWindow, normalizeMeasure, openAiTaskAction, openBrigadeContract, openConfirmModal,
    openEstimateDetail, ownExpenses, parseAiTaskPayload, prescriptionsList, pricelists, projectAiSummaries, projectBudgetSpent, projectChatMessage,
    projectChatMessages, projectDocuments, projectEconomy, projectLetters, projectMeasurements, projectObjectLinks, projectPaymentInAmount, projectPaymentSignedAmount,
    projectPayments, projectPlanDone, projectRealProgress, projectStages, projects, refreshData, removeTask, renderEstimateChangeReconcileTask,
    renderEstimateMeasurementComparisonPanel, renderEstimateReconciliationsPanel, renderMaterialAliasControls, renderMaterialSupplyAction, renderWorkJournalEstimateReconciliationPanel, roleColor, roomCompleteness, roomDoors,
    roomWindows, rooms, saveChecklist, saveDoor, savePrescription, saveProject, saveProjectStage, saveRoom,
    saveTbEntry, saveUnexpectedWork, saveWindow, selectedBrigadeContract, selectedChecklist, sendProjectChatMessage, setActiveProjectTab, setActiveTabGroup,
    setAddExpenseProject, setBrigadeCoef, setBrigadeContractItems, setBrigadeContracts, setBrigadePayments, setDraftRoomDoors, setDraftRoomWindows, setEditingAct,
    setEditingCable, setEditingDoor, setEditingInspection, setEditingItem, setEditingJournal, setEditingWindow, setEstimateSearch, setExpandedProject,
    setExpandedRoom, setHiddenActs, setListSearch, setMaterialTransfers, setMaterials, setMeasurementDraftLoadingId, setMobileExpandedRenderLists, setNewAccountable,
    setNewBrigadeContract, setNewBrigadeItem, setNewBrigadePayment, setNewChecklist, setNewChecklistItem, setNewDoor, setNewInspOrder, setNewLetter,
    setNewManualExpense, setNewMeasurementDoc, setNewParticipant, setNewPrescription, setNewProject, setNewProjectDoc, setNewRoom, setNewStage,
    setNewTask, setNewTbEntry, setNewTransfer, setNewUnexpected, setNewWarrantyDefect, setNewWindow, setProjectAiSummaries, setProjectChatMessage,
    setRejectingEntry, setRoomDoors, setRoomWindows, setSelectedBrigadeContract, setSelectedChecklist, setShowAccountableForm, setShowArchive, setShowBalanceDetails,
    setShowBrigadeForm, setShowBrigadePayModal, setShowDocForm, setShowForm, setShowJournalTableModal, setShowLetterForm, setShowMeasurementForm, setShowPhotoModal,
    setShowQRModal, setShowRoomForm, setShowTransferForm, setUploadingDoc, setUploadingLetter, setUploadingMeasurementDoc, setWarehouseMain, setWarrantyEditForm,
    showArchive, showBalanceDetails, showBrigadeForm, showDocForm, showForm, showKS2, showLetterForm, showMeasurementForm,
    showPreview, showRoomForm, showTransferForm, signedEstimateChangeTotal, staff, supervisorActs, supplierInvoices, supplyRequests,
    tbJournal, tbl, tblC, tblH, toNum, toggleChecklistItem, unexpectedWorksList, updateAiFinding,
    updateAiTask, updateDoor, updateStage, updateWindow, uploadPhoto, uploadingDoc, uploadingLetter, uploadingMeasurementDoc,
    user, users, visibleActiveProjects, visibleEstimatesForCurrentUser, visibleProjects, warehouseMain, warrantyDefects, warrantyEditForm,
    weatherLog, workExecutionTotal, workJournal, workJournalPage,
  };

  const appProjectEditModalsProps = {
    ui: { C, aiNotice, aiNoticeIcon, aiNoticeText, btnB, btnG, btnO, btnR, card, inp, tbl, tblC, tblH },
    state: { editingAct, editingCable, editingInspection, editingJournal, hiddenActs, journalFilter, showJournalTableModal, users, weatherLog, workJournal },
    actions: { appendPhotos, buildCableJournalContent, buildHiddenActContent, buildMaterialInspectionContent, buildWorkJournalContent, cableTypeOf, fileSrc, fmtMeasure, getActStatusForJournal, setCableJournal, setEditingAct, setEditingCable, setEditingInspection, setEditingJournal, setHiddenActs, setJournalFilter, setMaterialInspections, setShowJournalTableModal, setShowPhotoModal, setWorkJournal, showPreview, uploadPhoto },
  };

  const appActionModalsProps = {
    ui: { C, btnG, btnGr, btnO, btnR, card, inp },
    constants: { PAYMENT_TYPES, ROLE_LABELS },
    state: { actPayments, aiChat, aiLoading, aiMessage, chatEndRef, confirmAcceptedQty, confirmComment, confirmingEntry, financeUsers, issueToolData, masterProfiles, newBrigadePayment, newPayment, projects, rejectComment, rejectingEntry, returnToolCondition, selectedBrigadeContract, showAiAssistant, showBrigadePayModal, showIssueToolModal, showPayActModal, showQRModal, showReturnToolModal },
    actions: { confirmJ, generateQR, issueTool, normalizeMeasure, rejectJ, returnTool, saveActPayment, saveBrigadePayment, sendAiMessage, setAiMessage, setConfirmAcceptedQty, setConfirmComment, setConfirmingEntry, setIssueToolData, setNewBrigadePayment, setNewPayment, setRejectComment, setRejectingEntry, setReturnToolCondition, setShowAiAssistant, setShowBrigadePayModal, setShowIssueToolModal, setShowPayActModal, setShowQRModal, setShowReturnToolModal, toNum },
  };

  const sidebarProps = { isMobile, sidebarRef, sidebarVisible, setSidebarVisible, C, user, roleLabels: ROLE_LABELS, roleColor, menuItems, supplyRequests, isLeadership, isMasterRole, activePage, navigateTo, handleLogout };

  const headerProps = { C, activePage, isCompactHeader, isMobile, setSidebarVisible, allMenuItems, globalSearch, setGlobalSearch, setShowSearch, showSearch, searchResults, navigateTo, inp, darkMode, setDarkMode, setShowQuickActions, user, openSystemStatus, setShowChatPanel, unreadMessagesCount, showNotifications, toggleNotifications, unreadNotifications, btnG, btnO, myNotifications, notifications, markMyNotificationsRead, closeNotifications, getNotifPage, setShowNotifications, setNotifications, setUser, API };

  const dashboardProps = {
    ui: { API, C, btnG, btnO, darkMode, isMobile, showAiAssistant, showNotifications, unreadMessagesCount, unreadNotifications },
    data: { accountablePayments, activityLog, aiFindings, canUseDirectorAgent, dailyReportDate, directorAgentAnswer, directorAgentError, directorAgentLoading, directorAgentQuestion, directorAgentSteps, estimateControlIssues, hiddenActs, initialDataLoaded, inspectionOrders, lowMainStock, lowStock, manualExpenses, mobileExpandedRenderLists, myNotifications, notifications, ownExpenses, projectPayments, projects, supplierInvoices, supplierOffers, supplyRequests, unexpectedWorksList, user, workJournal },
    actions: { askDirectorAgent, buildDailyObjectReportContent, buildDirectorBriefReportContent, buildSupplyControlReportContent, closeNotifications, getNotifPage, isApprovedEstimateChangeStatus, isLeadership, markMyNotificationsRead, navigateTo, normalizeDocDate, openEstimateControlReport, projectBudgetSpent, projectPaymentSignedAmount, projectRealProgress, setAccountingTab, setActivePage, setDailyReportDate, setDirectorAgentQuestion, setDarkMode, setExpandedProject, setMobileExpandedRenderLists, setNotifications, setShowAiAssistant, setShowChatPanel, setShowForm, setShowNotifications, setShowQuickActions, setShowReimburseModal, setShowSupplyForm, setSidebarVisible, setSupplyTab, setUser, setWarehouseTab, showPreview, toggleNotifications, visibleActiveProjects, workDocDate },
  };

  const projectSiteProps = {
    C,
    badge,
    btnG,
    btnO,
    card,
    inp,
    isMobile,
    projects,
    projectSiteDraft,
    updateProjectSiteDraft,
    saveProjectSitePublication,
  };

  const appDirectoryPagesProps = {
    activePage,
    ui: { API, C, badge, btnB, btnG, btnGr, btnO, btnR, card, inp, isMobile, tbl, tblC, tblH },
    constants: { PRICELISTS_DATA, ROLE_GROUPS, ROLE_LABELS, ROLES, SUPPLIER_CATEGORIES, UNITS },
    state: { clients, compareLoadingReqId, compareResultByReq, editingItem, editingPlItem, estimatesList, expandedClient, expandedGroup, fileSrc, inlineEditPl, inlineEditPlData, inviteCodes, listSearch, newClient, newInviteRole, newOffer, newPlItem, newPricelist, newRequest, newSupplier, newUser, pricelistItems, pricelists, projects, searchUser, selectedPricelist, showForm, showInvites, showOffers, suppliers, suppliersTab, supplierOffers, supplyDeliveries, supplyHistory, supplyRequestOrigin, supplyRequests, user, users },
    actions: { approveOffer, buildPricelistContent, cancelInlinePlEdit, cancelRequest, copyPricelist, createInvite, deleteClient, deleteInvite, deletePlItem, deletePricelist, deleteSupplier, deleteUser, exportToExcel, generateTempPassword, getProjectWorkPackageOptions, isLeadership, loadAll, loadPricelistItems, matchSearch, parseOfferItems, parseSupplyItems, renderSupplyRequestOrigin, resetUserTwoFactor, roleColor, runCompareKp, saveClient, saveInlinePlItem, saveOffer, savePlItem, savePricelist, saveRequest, saveSupplier, saveUser, selectSupplierOffer, setEditingItem, setEditingPlItem, setExpandedClient, setExpandedGroup, setFromEstimateForm, setGeneratedInviteLink, setGeneratePricelistForm, setInlineEditPlData, setInlineEditPrice, setListSearch, setNewClient, setNewInviteRole, setNewOffer, setNewPlItem, setNewPricelist, setNewRequest, setNewSupplier, setNewUser, setPricelistItems, setSearchUser, setSelectedPricelist, setShowForm, setShowFromEstimate, setShowGeneratePricelist, setShowInvites, setShowOffers, setShowSupplierInviteModal, setSupplierInviteForm, setSuppliersTab, showPreview, startInlinePlEdit, rejectSupplierOffer, toggleUserActive },
  };

  const appOperationsPagesProps = {
    activePage,
    ui: { C, badge, btnB, btnG, btnGr, btnO, btnR, card, inp, isMobile, tbl, tblC, tblH },
    constants: { MATERIAL_CATEGORIES, SUPPLIER_CATEGORIES, TOOL_STATUSES, UNITS, VAT_OPTIONS },
    state: { compareLoadingReqId, compareResultByReq, deliveryAiLoadingId, deliveryAiResultById, editingItem, estimatesList, expandedProject, fileSrc, history, inventory, invoices, listSearch, materialReconciliationRows, materials, materialsPage, materialTransfers, newInventory, newInvoice, newMovement, newSupplier, newSupplierInvoice, newSupplyReq, newTool, newTransfer, newWarehouse, priceHints, projects, receiveForm, receivingDeliveryId, selectedInventory, selectedWarehouseProject, showForm, showSupplyForm, showTransferForm, staff, suppliers, supplierCatalog, supplierInvoices, supplierOffers, supplyAiLoading, supplyAiText, supplyClaims, supplyCollapsedProjects, supplyDeliveries, supplyExpandedId, supplyRejectId, supplyRejectReason, supplyRequests, supplyRequestOrigin, supplyStockCheck, supplyTab, supplyTemplates, toolHistory, tools, toolsTab, user, warehouseInvoiceItems, warehouseMain, warehouseMovements, warehouses, warehouseTab },
    actions: { _normalizeUnit, applySupplyTemplate, applyWarehouseMovement, approveSupplyAsDirector, askSupplyAi, buildInventoryDoc, buildInvoiceContent, buildMaterialRequirementContent, buildMovementDoc, cancelSupply, confirmSupplyAsProrab, convertUnits, createSupplyReq, deleteMainMaterial, deleteMaterial, deleteSupplier, deleteSupplyTemplate, deleteTool, deleteWarehouse, exportToExcel, fetchPriceHint, getProjectEstimateWorkOptions, getProjectWorkPackageOptions, isFinanceRole, isLeadership, isProrab, isSupplyDeliveryInvoice, loadAll, loadMaterialsPage, loadSupplyStockCheck, matchSearch, materialControlSummaryForProject, notify, openReceiveInvoice, openRequestKpModal, parseOfferItems, parseSupplyItems, receiveSupplyDelivery, refreshData, rejectSupplierOffer, rejectSupply, renderInvoiceControlActions, renderMaterialReconciliationPanel, renderSupplyPlanningHint, renderSupplyRequestOrigin, runCompareKp, runDeliveryAiCheck, saveInvoiceNew, saveSupplier, saveSupplyTemplate, saveTool, saveWarehouse, selectSupplierOffer, setDeliveryAiLoadingId, setDeliveryAiResultById, setEditingItem, setExpandedProject, setGeneratedInviteLink, setListSearch, setMaterialTransfers, setMaterials, setNewInventory, setNewInvoice, setNewMovement, setNewSupplier, setNewSupplierInvoice, setNewSupplyReq, setNewTool, setNewTransfer, setNewWarehouse, setReceiveForm, setReceivingDeliveryId, setSelectedInventory, setSelectedWarehouseProject, setShowForm, setShowIssueToolModal, setShowPhotoModal, setShowQRModal, setShowReturnToolModal, setShowSupplierInviteModal, setShowSupplyForm, setShowTransferForm, setSupplierInviteForm, setSupplyCollapsedProjects, setSupplyExpandedId, setSupplyRejectId, setSupplyRejectReason, setSupplyTab, setToolsTab, setWarehouseMain, setWarehouseTab, showPreview, toNum, uploadPhoto, visibleActiveProjects, warehouseInvoiceEstimateControl },
  };

  const appBackofficePagesProps = {
    activePage,
    ui: { API, C, badge, btnB, btnG, btnGr, btnO, btnR, card, inp, isMobile, tbl, tblC, tblH },
    constants: { PD_CONSENT_TEXT, ROLE_GROUPS, ROLE_LABELS, UNITS },
    state: { accountablePayments, accountingDocProject, accountingTab, allBrigadeItems, allBrigadePayments, auditLog, brigadeContracts, contracts, editingItem, estimatesList, expandedActDate, expandedMaster, expandedMasterProject, expandedPieceworkProject, expandedProject, expandedStaffId, expenseReports, fileSrc, interimActs, invoices, listSearch, manualExpenses, masterProfiles, masterRatings, newAct, newContract, newExpenseReport, newPiecework, newStaff, newStaffDoc, ownExpenses, payrollExtras, pdConsents, personnelTab, piecework, projectDocuments, projectPaymentInAmount, projectPayments, projectPlanDone, projects, salaryEdits, salaryMonth, salaryPayments, showForm, showPiecework, showStaffDocForm, staff, staffExpandedSections, staffProfile, staffProfileLoading, supplierInvoices, suppliers, timesheet, tools, unexpectedWorksList, user, users, workJournal },
    actions: { addPiecework, addStaffDoc, buildAOSKContent, buildActContent, buildBrigadeActContent, buildContractContent, buildExecPackageContent, buildIGDContent, buildInvoiceContent, buildJPRContent, buildKS11Content, buildKS14Content, buildKS3Content, buildM29Content, buildM2Content, buildM8Content, buildMaterialRequirementContent, buildPassportContent, buildPositionInstructionContent, buildSpecJournalContent, buildVATBookContent, calcSalary, contractRequisitesWarning, createContract, createInterimAct, createStaffAccessFromPrompt, daysInMonth, deleteContract, deleteInterimAct, deletePiecework, deleteStaff, findUserForStaff, fmtMeasure, isApprovedEstimateChangeStatus, isFinanceRole, isLeadership, loadAuditLog, matchSearch, materialControlSummaryForProject, normalizePersonKey, openStaffProfile, paySalary, ratemaster, refreshData, resetStaffAccessPassword, resolveContractPerformer, roleColor, saveStaff, setAccountingDocProject, setAccountingTab, setAuditLog, setEditingItem, setExpandedActDate, setExpandedMaster, setExpandedMasterProject, setExpandedPieceworkProject, setExpandedProject, setListSearch, setNewAct, setNewContract, setNewExpenseReport, setNewPiecework, setNewStaff, setNewStaffDoc, setPayrollExtra, setPersonnelTab, setSalaryEdit, setSalaryMonth, setSalaryPayments, setShowForm, setShowPayActModal, setShowPhotoModal, setShowPiecework, setShowReimburseModal, setShowStaffDocForm, setStaffExpandedSections, setStaffProfile, showKS2, showPreview, toggleDay, toNum, uploadPhoto, warehouseInvoiceEstimateControl, workedDays },
  };

  const appSecondaryPagesProps = {
    activePage,
    ui: { API, C, badge, btnB, btnG, btnO, btnR, card, inp, isMobile, tbl, tblC, tblH },
    constants: { CRM_STAGES, EXPENSE_CATEGORIES, ROLE_LABELS, WEATHER_CONDITIONS },
    state: {
      accountablePayments, activityLog, auditLog, companyChatMessage, companyDocuments,
      companyMessages, companyReqForm, companyRequisites, contracts, editingItem,
      expByCategory, fileSrc, leads, newCompanyDoc, newLead, newWeather, ownExpenses,
      projects, settingsTab, showForm, staff, suppliers, user, users, weatherLog,
      weatherTab, workJournal,
    },
    actions: {
      appendPhotos, buildJPRContent, createProjectFromLead, deleteLead, isFinanceRole,
      loadAll, roleColor, saveCompanyRequisites, saveLead, saveWeather,
      sendCompanyChatMessage, setCompanyChatMessage, setCompanyReqForm,
      setCompanyRequisites, setEditingItem, setLeads, setNewCompanyDoc, setNewLead,
      setNewWeather, setReportingPayment, setSettingsTab, setShowForm,
      setShowOwnExpenseForm, setShowPhotoModal, setWeatherTab, showPreview,
      uploadPhoto,
    },
  };

  const workAssignmentProps = {
    show: showWorkAssignment,
    onClose: () => setShowWorkAssignment(false),
    selectedEstimate,
    staff,
    users,
    API,
    loadAll,
    C,
    card,
    inp,
    btnO,
    btnG,
    btnB,
    isMobile,
  };

  const appWorkflowModalsProps = {
    ui: { API, C, badge, btnB, btnG, btnO, btnR, card, darkMode, inp, isMobile },
    constants: { estimatePackages: ESTIMATE_PACKAGES, expenseCategories: EXPENSE_CATEGORIES, roleLabels: ROLE_LABELS, supplierCategories: SUPPLIER_CATEGORIES, units: UNITS },
    state: {
      activeEstimateFromList, addExpenseProject, aiInput, aiLoading, aiMessages, creatingFromEstimate,
      distributeAssignments, distributeBrigades, distributing, estimateChatInput, estimateChatLoading,
      estimateChatMessages, estimateVersions, estimatesList, expenseSubmitting, fileSrc, fromEstimateForm,
      generateForm, generatePricelistForm, generatedInviteLink, generating, generatingPricelist,
      isFinanceRole, isGlobalEstimateTemplate, newAccountable, newDistributeBrigade, newExpense,
      newInvoice, newManualExpense, newOwnExpense, ownExpenses, pricelists, projects, reportingPayment,
      requestKpLoading, scanningInvoice, selectedEstimate, selectedSupplierIds, selectedVersionsToCompare,
      showAccountableForm, showAiChat, showDistribute, showEstimateChat, showFromEstimate,
      showGenerateEstimate, showGeneratePricelist, showOwnExpenseForm, showPreview, showQuickActions,
      showReceiveDialog, showReimburseModal, showRequestKpModal, showScanInvoice, showScannedInvoiceForm,
      showSupplierInviteModal, showVersionHistory, suggestedSuppliers, suppliers, supplierInviteForm,
      supplyRequests, sverkaModal, user, users, staff, visibleActiveProjects,
    },
    actions: {
      appendPhotos, applyEstimateActivationState, autoReconcileEstimateChanges, buildEstimateDiffContent,
      createSupplierInvite, enrichEstimateMeasurementBasis, estimateItemTotal, getProjectEstimateWorkOptions,
      getProjectWorkPackageOptions, loadAll, loadPricelistItems, navigateTo, nextEstimateVersionFor,
      openReceiveInvoice, parseSupplyItems, queueEstimateDiffReviewTask, queueEstimateNormReviewTask,
      queueEstimateQualityReviewTask, renderSupplyRequestOrigin, sameEstimateGroup, saveInvoiceNew,
      sendAiAssistantMessage, sendEstimateChatMessage, sendKpRequest, setActivePage, setAddExpenseProject,
      setAiInput, setAiLoading, setAiMessages, setCreatingFromEstimate, setDistributeAssignments,
      setDistributeBrigades, setDistributing, setEstimateChatInput, setEstimateChatMessages, setEstimatesList,
      setExpenseSubmitting, setFromEstimateForm, setGenerateForm, setGeneratePricelistForm,
      setGeneratedInviteLink, setGenerating, setGeneratingPricelist, setMaterialTransfers, setNewAccountable,
      setNewDistributeBrigade, setNewExpense, setNewInvoice, setNewManualExpense, setNewOwnExpense,
      setReportingPayment, setScanningInvoice, setSelectedEstimate, setSelectedPricelist, setSelectedSupplierIds,
      setSelectedVersionsToCompare, setSelectedWarehouseProject, setShowAccountableForm, setShowAiAssistant,
      setShowAiChat, setShowChatPanel, setShowDistribute, setShowEstimateChat, setShowFromEstimate,
      setShowGenerateEstimate, setShowGeneratePricelist, setShowOwnExpenseForm, setShowPhotoModal,
      setShowQuickActions, setShowReceiveDialog, setShowReimburseModal, setShowRequestKpModal,
      setShowScanInvoice, setShowScannedInvoiceForm, setShowSupplierInviteModal, setShowTransferForm,
      setShowVersionHistory, setSverkaModal, setSupplierInviteForm, setWarehouseTab,
    },
  };

  const overlayProps = {
    showSystemStatus,
    systemStatus,
    systemStatusLoading,
    openSystemStatus,
    setShowSystemStatus,
    C,
    badge,
    btnG,
    showMobileMenu,
    setShowMobileMenu,
    menuItems,
    activePage,
    navigateTo,
    setActivePage,
    showChatPanel,
    setShowChatPanel,
    companyMessages,
    user,
    companyChatInput,
    setCompanyChatInput,
    sendCompanyChatMessage,
    uploadPhoto,
  };

  const mobileBottomNavProps = {
    activePage,
    isMobile,
    unreadMessagesCount,
    menuItems,
    navigateTo,
    setActivePage,
    setShowMobileMenu,
    setShowQuickActions,
    setShowChatPanel,
  };

  return (
    <AppAuthenticatedShell
      activePage={activePage}
      appActionModalsProps={appActionModalsProps}
      appBackofficePagesProps={appBackofficePagesProps}
      appDirectoryPagesProps={appDirectoryPagesProps}
      appOperationsPagesProps={appOperationsPagesProps}
      appProjectEditModalsProps={appProjectEditModalsProps}
      appSecondaryPagesProps={appSecondaryPagesProps}
      appWorkflowModalsProps={appWorkflowModalsProps}
      C={C}
      canOpenProjects={canAccess('projects')}
      dashboardProps={dashboardProps}
      estimatesPageContext={estimatesPageContext}
      headerProps={headerProps}
      isMobile={isMobile}
      mobileBottomNavProps={mobileBottomNavProps}
      overlayProps={overlayProps}
      pageFallback={pageFallback}
      photoPreviewProps={{ src: showPhotoModal, onClose: () => setShowPhotoModal(null) }}
      previewProps={{
        content: previewContent,
        title: previewTitle,
        onClose: () => setPreviewContent(null),
        onPrint: doPrint,
      }}
      projectSiteProps={projectSiteProps}
      projectsPageContext={projectsPageContext}
      sidebarProps={sidebarProps}
      workAssignmentProps={workAssignmentProps}
    />
  );
}

export default App;
