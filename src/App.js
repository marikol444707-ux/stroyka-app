import React, { useState, useEffect, useRef } from 'react';
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
import MaterialWriteoffStatus from './components/MaterialWriteoffStatus';
import { ProjectDirectorMapPanel } from './features/director-map';
import { ProjectLaunchPanel } from './features/project-launch';
import { createProjectCrudActions } from './features/projects/projectCrudActions';
import {
  createClientForm,
  createProjectForm,
} from './features/projects/projectInitialForms';
import { createWarehouseCrudActions } from './features/warehouse/warehouseCrudActions';
import {
  createCatalogItemForm,
  createInventoryForm,
  createIssueToolForm,
  createMaterialTransferForm,
  createSupplierRequisitesForm,
  createToolForm,
  createWarehouseForm,
  createWarehouseInvoiceForm,
  createWarehouseMovementForm,
} from './features/warehouse/warehouseInitialForms';
import { createMaterialControlActions } from './features/material-control/materialControlActions';
import { createMaterialRuntime } from './features/material-control/materialRuntime';
import { createDataLoadActions } from './features/data-loaders/dataLoadActions';
import { useAppDataLoaders } from './features/data-loaders/useAppDataLoaders';
import { createProjectDashboardRuntime } from './features/dashboard/projectDashboardRuntime';
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
import AppMasterCabinetRoute from './components/AppMasterCabinetRoute';
import AppSupplierCabinetRoute from './components/AppSupplierCabinetRoute';
import { createAuthActions } from './features/auth/authActions';
import { createAiAssistantActions } from './features/ai-assistant/aiAssistantActions';
import { createChatActions } from './features/chat/chatActions';
import { createCrmActions } from './features/crm/crmActions';
import { createLeadForm } from './features/crm/crmInitialForms';
import { createGeoActions } from './features/geolocation/geoActions';
import { createNotificationActions } from './features/notifications/notificationActions';
import { createSystemActions } from './features/system/systemActions';
import { createUploadActions } from './features/uploads/uploadActions';
import { WorkAssignmentStatusPanel } from './features/work-assignment';
import { useAiAssistantState } from './features/ai-assistant/useAiAssistantState';
import { createAiTaskActions } from './features/ai-control/aiTaskActions';
import { createAiReviewQueueActions } from './features/ai-control/aiReviewQueueActions';
import { createUserAccessActions } from './features/admin/userAccessActions';
import { createDocumentActions } from './features/documents/documentActions';
import {
  createProjectDocumentForm,
  createProjectLetterForm,
  createSupervisorActForm,
} from './features/documents/projectDocumentInitialForms';
import { createPaymentActions } from './features/payments/paymentActions';
import {
  createActPaymentForm,
  createBrigadePaymentForm,
} from './features/payments/paymentInitialForms';
import { usePaymentUiState } from './features/payments/usePaymentUiState';
import { createPersonnelActions } from './features/personnel/personnelActions';
import {
  createBrigadeContractForm,
  createBrigadeItemForm,
  createContractForm,
  createInterimActForm,
  createPieceworkForm,
  createStaffDocumentForm,
  createUserForm,
} from './features/personnel/personnelInitialForms';
import { createPricelistActions } from './features/pricelists/pricelistActions';
import {
  createPricelistForm,
  createPricelistItemForm,
} from './features/pricelists/pricelistInitialForms';
import { createMaterialNormActions } from './features/material-norms/materialNormActions';
import { createMaterialNormCoverageActions } from './features/material-norms/materialNormCoverageActions';
import { useMaterialNormsState } from './features/material-norms/useMaterialNormsState';
import { createMaterialTransferActions } from './features/material-transfer/materialTransferActions';
import { createMaterialWriteoffActions } from './features/material-writeoff/materialWriteoffActions';
import { createWorkJournalActions } from './features/work-journal/workJournalActions';
import { createProjectEstimateRuntime } from './features/estimates/projectEstimateRuntime';
import AppEntryRoutes from './components/AppEntryRoutes';
import AppPageFallback from './components/AppPageFallback';
import { buildAppMenuItems } from './components/AppMenuItems';
import AppRoleCabinetRoutes from './components/AppRoleCabinetRoutes';
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
  buildEstimateDiff,
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
  normalizeEstimateList,
  sameEstimateGroup,
} from './utils/estimateUtils';
import {
  estimateChangeAutoDecision,
  estimateChangeReconcileMarker,
  estimateChangeReconcileDescription,
  estimateDiffReviewMarker,
  estimateDiffReviewDescription,
  estimateNormReviewMarker,
  estimateNormReviewDescription,
  estimateNormReviewIssueStatuses,
  estimateQualityReviewMarker,
  estimateQualityDescription,
  estimateQualityRows,
} from './utils/estimateReviewUtils';
import { createEstimateWorkflowActions } from './features/estimates/estimateWorkflowActions';
import { createEstimatePageActions } from './features/estimates/estimatePageActions';
import { persistEstimateAction } from './features/estimates/estimatePersistenceActions';
import { createSupplyActions } from './features/supply/supplyActions';
import {
  createRequestForm,
  createSupplierForm,
  createSupplierOfferForm,
} from './features/supply/supplyInitialForms';
import { createSupplyPlanningUi } from './features/supply/supplyPlanningUi';
import { useSupplyWorkflowState } from './features/supply/useSupplyWorkflowState';
import { useSupplierRequisitesSync } from './features/supply/useSupplierRequisitesSync';
import { createProjectOperationActions } from './features/project-operations/projectOperationActions';
import {
  createChecklistForm,
  createDoorForm,
  createPrescriptionForm,
  createProjectStageForm,
  createRoomForm,
  createTbEntryForm,
  createWeatherForm,
  createWindowForm,
} from './features/project-operations/projectOperationInitialForms';
import {
  createCompanyDocumentForm,
  createCompanyRequisitesForm,
  createProfileForm,
} from './features/settings/settingsInitialForms';
import { createProjectMeasurementActions } from './features/project-measurements/projectMeasurementActions';
import { createMeasurementDocForm } from './features/project-measurements/projectMeasurementInitialForms';
import { createRoomMeasurementRuntime } from './features/project-measurements/roomMeasurementRuntime';
import { createDirectorDashboardActions } from './features/dashboard/directorDashboardActions';
import { useAppNavigationRuntime } from './features/navigation/appNavigationRuntime';
import { createAppRoleRuntime, createAppUtilityRuntime, unreadCompanyMessagesCount } from './features/app-shell/appShellSelectors';
import {
  useAuthenticatedAppBootstrapEffect,
  useAuthEntryState,
  useDarkModeState,
  useInviteCodeCheckEffect,
  useNotificationDismissEffect,
  useResponsiveLayout,
  useShellOverlayState,
} from './features/app-shell/useAppShellState';
import { useEstimateExecutionFillPercentSync } from './features/estimates/useEstimateExecutionPricingState';
import { useEstimateWorkflowState } from './features/estimates/useEstimateWorkflowState';
import {
  invoiceControlMaterialName,
  invoiceControlNeedsReview,
  invoiceControlProjectName,
  invoiceControlReviewReason,
  parseAiTaskPayload,
} from './utils/aiControlDescriptionUtils';
import {
  buildPagedPath,
  calcVat,
  createMaterialsPageState,
  createMaterialNormsPageState,
  createWorkJournalPageState,
  daysInMonth,
  doPrint,
  generateQR,
  mergeRowsByIdValue,
  mobileScopeForPage,
  readStoredJson,
  readApiResult,
  sendPushNotification,
} from './utils/appRuntimeUtils';
import {
  normalizeDocDate,
  workDocDate,
} from './utils/documentFormatUtils';
import { exportToExcelFile } from './utils/exportUtils';
import { cableTypeOf, isCableName } from './utils/cableUtils';
import {
  contractRequisitesWarning,
  normalizePersonKey,
} from './utils/performerUtils';
import {
  canAccessRole,
  canCreateSupplyRequestFromNormForUser,
  canEditMaterialNormsForUser,
  generateTempPassword,
  roleFlagsForUser,
} from './utils/accessUtils';
import {
  buildEstimateDiffDocContent,
  buildEstimateReconciliationDocContent,
  fmtDocMoney,
} from './utils/printDocumentBuilders';
import {
  EMPTY_ESTIMATE_CHANGE,
  isApprovedEstimateChangeStatus,
  signedEstimateChangeTotal,
} from './utils/estimateChangeUtils';
import { emptyStaffForm } from './utils/staffUtils';
import {
  isActiveSupplyRequestStatus,
  isSameSupplyMaterial,
  parseOfferItems,
  parseSupplyItems,
  supplyRequestOrigin,
  supplyUnitKey,
} from './utils/supplyUtils';
import { aiSeverityMeta, estimateStatusView, isOpenAiStatus, materialControlStatus, materialNormCoverageMeta, materialNormStatus, workJournalEstimateStatusMeta } from './utils/statusMetaUtils';
import { FolderKanban, Package, ScrollText, Search, Plus, Edit2, Trash2, Eye, Check, X, ChevronDown, ChevronUp, Upload, MapPin, FileText, Archive, QrCode, Calculator, Bot, GitBranch } from 'lucide-react';

installAuthFetch();

const GENERAL_WORK_ROOM_NAME = 'Без помещения';

function App() {
  const { isMobile, isCompactHeader } = useResponsiveLayout();
  const mobileLoadedScopesRef = useRef(new Set());
  const mobileApiRequestsRef = useRef(new Map());
  const [darkMode, setDarkMode] = useDarkModeState();
  const {
    email, loginError, page, password, regCode, regEmail, regInviteInfo, regName, regPassword, regSupplierData,
    setEmail, setLoginError, setPage, setPassword, setRegCode, setRegEmail, setRegInviteInfo,
    setRegName, setRegPassword, setRegSupplierData, setUser, user,
  } = useAuthEntryState();
  const [activePage, setActivePage] = useState('dashboard');
  const [initialDataLoaded, setInitialDataLoaded] = useState(false);
  const [activeProjectTab, setActiveProjectTab] = useState('Общее');
  const [activeTabGroup, setActiveTabGroup] = useState(null);
  const [sidebarVisible, setSidebarVisible] = useState(false);
  const [projects, setProjects] = useState([]);
  const [clients, setClients] = useState([]);
  const [materials, setMaterials] = useState([]);
  const [warehouseMain, setWarehouseMain] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [warehouseMovements, setWarehouseMovements] = useState([]);
  const [history, setHistory] = useState([]);
  const [staff, setStaff] = useState([]);
  const [piecework, setPiecework] = useState([]);
  const [users, setUsers] = useState([]);
  const [pricelists, setPricelists] = useState([]);
  const [pricelistItems, setPricelistItems] = useState([]);
  const [inviteCodes, setInviteCodes] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [supplyRequests, setSupplyRequests] = useState([]);
  const [supplierOffers, setSupplierOffers] = useState([]);
  const [supplyHistory, setSupplyHistory] = useState([]);
  const [supplyDeliveries, setSupplyDeliveries] = useState([]);
  const [supplyClaims, setSupplyClaims] = useState([]);
  const [workJournal, setWorkJournal] = useState([]);
  const [masterProfile, setMasterProfile] = useState(null);
  const [masterProfiles, setMasterProfiles] = useState([]);
  const [contracts, setContracts] = useState([]);
  const [interimActs, setInterimActs] = useState([]);
  const [timesheet, setTimesheet] = useState({});
  const [salaryPayments, setSalaryPayments] = useState([]);
  const [unexpectedWorksList, setUnexpectedWorksList] = useState([]);
  const [estimateReconciliations, setEstimateReconciliations] = useState([]);
  const [brigadeContracts, setBrigadeContracts] = useState([]);
  const [hiddenActs, setHiddenActs] = useState([]);
  const [editingAct, setEditingAct] = useState(null);
  const [editingJournal, setEditingJournal] = useState(null);
  const [journalFilter, setJournalFilter] = useState({from:'',to:'',masterName:'',sectionName:'',status:''});
  const [showJournalTableModal, setShowJournalTableModal] = useState(null);
  const [materialInspections, setMaterialInspections] = useState([]);
  const [editingInspection, setEditingInspection] = useState(null);
  const [cableJournal, setCableJournal] = useState([]);
  const [editingCable, setEditingCable] = useState(null);
  const [supervisorActs, setSupervisorActs] = useState([]);
  const [inspectionOrders, setInspectionOrders] = useState([]);
  const [newInspOrder, setNewInspOrder] = useState(null);
  const [auditLog, setAuditLog] = useState([]);
  const [expenseReports, setExpenseReports] = useState([]);
  const [newExpenseReport, setNewExpenseReport] = useState(null);
  const [supplierInvoices, setSupplierInvoices] = useState([]);
  const [newSupplierInvoice, setNewSupplierInvoice] = useState(null);
  const [warrantyDefects, setWarrantyDefects] = useState([]);
  const [newWarrantyDefect, setNewWarrantyDefect] = useState(null);
  const [warrantyEditForm, setWarrantyEditForm] = useState(null);
  const [newSupervisorAct, setNewSupervisorAct] = useState(createSupervisorActForm);
  const [supervisorActPhoto, setSupervisorActPhoto] = useState('');
  const [prescriptionPhoto, setPrescriptionPhoto] = useState('');
  const [selectedBrigadeContract, setSelectedBrigadeContract] = useState(null);
  const [brigadeContractItems, setBrigadeContractItems] = useState([]);
  const [brigadePayments, setBrigadePayments] = useState([]);
  const [showBrigadePayModal, setShowBrigadePayModal] = useState(false);
  const [newBrigadePayment, setNewBrigadePayment] = useState(createBrigadePaymentForm);
  const [allBrigadeItems, setAllBrigadeItems] = useState([]);
  const [allBrigadePayments, setAllBrigadePayments] = useState([]);
  const [projectDocuments, setProjectDocuments] = useState([]);
  const [newProjectDoc, setNewProjectDoc] = useState(createProjectDocumentForm);
  const [sitePublicationDrafts, setSitePublicationDrafts] = useState({});
  const [showDocForm, setShowDocForm] = useState(false);
  const [uploadingDoc, setUploadingDoc] = useState(false);
  const [projectMeasurements, setProjectMeasurements] = useState([]);
  const [measurementRoomDrafts, setMeasurementRoomDrafts] = useState([]);
  const [measurementDraftLoadingId, setMeasurementDraftLoadingId] = useState(null);
  const [newMeasurementDoc, setNewMeasurementDoc] = useState(createMeasurementDocForm);
  const [showMeasurementForm, setShowMeasurementForm] = useState(false);
  const [uploadingMeasurementDoc, setUploadingMeasurementDoc] = useState(false);
  const [projectLetters, setProjectLetters] = useState([]);
  const [newLetter, setNewLetter] = useState(createProjectLetterForm);
  const [showLetterForm, setShowLetterForm] = useState(false);
  const [uploadingLetter, setUploadingLetter] = useState(false);
  const [showBrigadeForm, setShowBrigadeForm] = useState(false);
  const [newBrigadeContract, setNewBrigadeContract] = useState(createBrigadeContractForm);
  const [newBrigadeItem, setNewBrigadeItem] = useState(createBrigadeItemForm);
  const [brigadeCoef, setBrigadeCoef] = useState('0.6');
  const [supplierCatalog, setSupplierCatalog] = useState([]);
  const [supplyTemplates, setSupplyTemplates] = useState([]);
  const [priceHints, setPriceHints] = useState({});
  const [showCatalogForm, setShowCatalogForm] = useState(false);
  const [newCatalogItem, setNewCatalogItem] = useState(createCatalogItemForm);
  const [supplierTab, setSupplierTab] = useState('requests');
  const [supplierRequisites, setSupplierRequisites] = useState(createSupplierRequisitesForm);
  useSupplierRequisitesSync({ setSupplierRequisites, suppliers, user });
  const [materialTransfers, setMaterialTransfers] = useState([]);
  const [showTransferForm, setShowTransferForm] = useState(false);
  const [newTransfer, setNewTransfer] = useState(createMaterialTransferForm);
  const [sverkaModal, setSverkaModal] = useState(null);
  const {
    companyChatInput, scanningInvoice, setCompanyChatInput, setScanningInvoice, setShowAiChat,
    setShowChatPanelRaw, setShowMobileMenu, setShowQuickActions, setShowReceiveDialog,
    setShowScanInvoice, setShowScannedInvoiceForm, setShowSystemStatus, setSystemStatus,
    setSystemStatusLoading, showAiChat, showChatPanel, showMobileMenu, showQuickActions,
    showReceiveDialog, showScanInvoice, showScannedInvoiceForm, showSystemStatus,
    systemStatus, systemStatusLoading,
  } = useShellOverlayState();
  const [projectPayments, setProjectPayments] = useState([]);
  const [accountablePayments, setAccountablePayments] = useState([]);
  const [ownExpenses, setOwnExpenses] = useState([]);
  const [customRoomTypes, setCustomRoomTypes] = useState(()=>{try{return JSON.parse(localStorage.getItem('customRoomTypes')||'[]');}catch{return [];}});
  const [manualExpenses, setManualExpenses] = useState([]);
  const {
    addExpenseProject, expenseSubmitting, newAccountable, newExpense, newManualExpense,
    newOwnExpense, reportingPayment, setAddExpenseProject, setExpenseSubmitting,
    setNewAccountable, setNewExpense, setNewManualExpense, setNewOwnExpense,
    setReportingPayment, setShowAccountableForm, setShowBalanceDetails,
    setShowOwnExpenseForm, showAccountableForm, showBalanceDetails, showOwnExpenseForm,
  } = usePaymentUiState();
  const {
    aiChat, aiInput, aiLoading, aiMessage, aiMessages, directorAgentAnswer,
    directorAgentError, directorAgentLoading, directorAgentQuestion, directorAgentSteps,
    setAiChat, setAiInput, setAiLoading, setAiMessage, setAiMessages,
    setDirectorAgentAnswer, setDirectorAgentError, setDirectorAgentLoading,
    setDirectorAgentQuestion, setDirectorAgentSteps,
  } = useAiAssistantState();
  const [checklists, setChecklists] = useState([]);
  const [checklistItems, setChecklistItems] = useState({});
  const [projectStages, setProjectStages] = useState([]);
  const [prescriptionsList, setPrescriptionsList] = useState([]);
  const [projectChatMessages, setProjectChatMessages] = useState({});
  const [companyMessages, setCompanyMessages] = useState([]);
  const [leads, setLeads] = useState([]);
  const [masterRatings, setMasterRatings] = useState({});
  const [activityLog, setActivityLog] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [aiFindings, setAiFindings] = useState([]);
  const [aiTasks, setAiTasks] = useState([]);
  const estimateNormReviewQueuedRef = useRef(new Set());
  const estimateNormReviewAutoCheckedRef = useRef(new Set());
  const estimateQualityReviewQueuedRef = useRef(new Set());
  const estimateQualityReviewAutoCheckedRef = useRef(new Set());
  const estimateDiffReviewQueuedRef = useRef(new Set());
  const estimateChangeReconcileQueuedRef = useRef(new Set());
  const materialControlTaskQueuedRef = useRef(new Set());
  const materialControlTaskAutoCheckedRef = useRef(new Map());
  const roomControlTaskQueuedRef = useRef(new Set());
  const roomControlTaskAutoCheckedRef = useRef(new Map());
  const [tbJournal, setTbJournal] = useState([]);
  const [geoCheckins, setGeoCheckins] = useState([]);
  const [, setSignedDocs] = useState({});
  const [rooms, setRooms] = useState([]);
  const [roomWorks, setRoomWorks] = useState([]);
  const [roomWindows, setRoomWindows] = useState([]);
  const [roomDoors, setRoomDoors] = useState([]);
  const [tools, setTools] = useState([]);
  const [toolHistory, setToolHistory] = useState([]);
  const [inventory, setInventory] = useState([]);
  const [pdConsents, setPdConsents] = useState([]);
  const [actPayments, setActPayments] = useState([]);
  const [weatherLog, setWeatherLog] = useState([]);
  const [estimatesList, setEstimatesList] = useState([]);
  const [estimatesPage, setEstimatesPage] = useState({loading:false, error:''});
  const [companyRequisites, setCompanyRequisites] = useState({});
  const [companyDocuments, setCompanyDocuments] = useState([]);
  const [pushEnabled, setPushEnabled] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const [previewContent, setPreviewContent] = useState(null);
  const [previewTitle, setPreviewTitle] = useState('');
  const [dailyReportDate, setDailyReportDate] = useState(new Date().toISOString().split('T')[0]);
  const [globalSearch, setGlobalSearch] = useState('');
  const [showSearch, setShowSearch] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [showRoomForm, setShowRoomForm] = useState(false);
  const [showPiecework, setShowPiecework] = useState(false);
  const [showInvites, setShowInvites] = useState(false);
  const [showOffers, setShowOffers] = useState(null);
  const [showProfileForm, setShowProfileForm] = useState(false);
  const [showPhotoModal, setShowPhotoModal] = useState(null);
  const [showArchive, setShowArchive] = useState(false);
  const [showIssueToolModal, setShowIssueToolModal] = useState(null);
  const [showReturnToolModal, setShowReturnToolModal] = useState(null);
  const [showPayActModal, setShowPayActModal] = useState(null);
  const [showAiAssistant, setShowAiAssistant] = useState(false);
  const [showQRModal, setShowQRModal] = useState(null);
  const [consentChecked, setConsentChecked] = useState(false);
  const [accountingTab, setAccountingTab] = useState('summary');
  const [accountingDocProject, setAccountingDocProject] = useState('');
  const [suppliersTab, setSuppliersTab] = useState('active');
  const {
    compareLoadingReqId, compareResultByReq, deliveryAiLoadingId, deliveryAiResultById,
    generatedInviteLink, invoicingOfferId, newKpResponse, newOfferInvoice, newSupplyReq,
    receiveForm, receivingDeliveryId, requestKpLoading, respondingOfferId, selectedSupplierIds,
    setCompareLoadingReqId, setCompareResultByReq, setDeliveryAiLoadingId, setDeliveryAiResultById,
    setGeneratedInviteLink, setInvoicingOfferId, setNewKpResponse, setNewOfferInvoice, setNewSupplyReq,
    setReceiveForm, setReceivingDeliveryId, setRequestKpLoading, setRespondingOfferId, setSelectedSupplierIds,
    setShipmentForm, setShippingOfferId, setShowRequestKpModal, setShowSupplierInviteModal, setShowSupplyForm,
    setSuggestedSuppliers, setSupplierInviteForm, setSupplyAiLoading, setSupplyAiText, setSupplyCollapsedProjects,
    setSupplyExpandedId, setSupplyRejectId, setSupplyRejectReason, setSupplyStockCheck, setSupplyTab,
    shipmentForm, shippingOfferId, showRequestKpModal, showSupplierInviteModal, showSupplyForm,
    suggestedSuppliers, supplierInviteForm, supplyAiLoading, supplyAiText, supplyCollapsedProjects,
    supplyExpandedId, supplyRejectId, supplyRejectReason, supplyStockCheck, supplyTab,
  } = useSupplyWorkflowState();
  const [personnelTab, setPersonnelTab] = useState('staff');
  const [warehouseTab, setWarehouseTab] = useState('objects');
  const [selectedWarehouseProject, setSelectedWarehouseProject] = useState(null);
  const [toolsTab, setToolsTab] = useState('list');
  const [estimatesTab, setEstimatesTab] = useState('list');
  const [materialNorms, setMaterialNorms] = useState([]);
  const [materialsPage, setMaterialsPage] = useState({projectName:'', search:'', hasMore:false, loading:false, error:''});
  const [workJournalPage, setWorkJournalPage] = useState({projectName:'', search:'', dateFrom:'', dateTo:'', hasMore:false, loading:false, error:''});
  const [materialAliases, setMaterialAliases] = useState([]);
  const [materialNormOverrides, setMaterialNormOverrides] = useState([]);
  const {
    editingMaterialNormId, estimateProjectFilter, estimateSearch, materialNormCoverageProject,
    materialNormNotice, materialNormPreviewSuggestions, materialNormSearch,
    materialNormSuggestionLoading, materialNormSuggestions, materialNormsPage, newMaterialNorm,
    setEditingMaterialNormId, setEstimateProjectFilter, setEstimateSearch,
    setMaterialNormCoverageProject, setMaterialNormNotice, setMaterialNormPreviewSuggestions,
    setMaterialNormSearch, setMaterialNormSuggestionLoading, setMaterialNormSuggestions,
    setMaterialNormsPage, setNewMaterialNorm, setShowArchivedEstimates, showArchivedEstimates,
  } = useMaterialNormsState();
  const [listSearch, setListSearch] = useState('');
  const [expandedActDate, setExpandedActDate] = useState(null);
  const [showReimburseModal, setShowReimburseModal] = useState(false);
  const [salaryMonth, setSalaryMonth] = useState(new Date().toISOString().slice(0,7));
  // Inline-правки премий/удержаний по сотруднику в месяце (хранится в localStorage)
  const [salaryEdits, setSalaryEdits] = useState(() => readStoredJson('salaryEdits', {}));
  const [payrollExtras, setPayrollExtras] = useState(() => readStoredJson('payrollExtras', {}));
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
  const [weatherTab, setWeatherTab] = useState('log');
  const [settingsTab, setSettingsTab] = useState('requisites');
  const [rejectComment, setRejectComment] = useState('');
  const [rejectingEntry, setRejectingEntry] = useState(null);
  const [confirmingEntry, setConfirmingEntry] = useState(null);
  const [confirmAcceptedQty, setConfirmAcceptedQty] = useState('');
  const [confirmComment, setConfirmComment] = useState('');
  const [editingItem, setEditingItem] = useState(null);
  const [editingPlItem, setEditingPlItem] = useState(null);
  const [inlineEditPl, setInlineEditPl] = useState(null);
  const [inlineEditPrice, setInlineEditPrice] = useState('');
  const [inlineEditPlData, setInlineEditPlData] = useState({name:'',unit:'м2',price:'',category:''});
  const [editingWindow, setEditingWindow] = useState(null);
  const [editingDoor, setEditingDoor] = useState(null);
  const [selectedPricelist, setSelectedPricelist] = useState(null);
  const [selectedInventory, setSelectedInventory] = useState(null);
  const [selectedEstimate, setSelectedEstimate] = useState(null);
  const [mobileExpandedRenderLists, setMobileExpandedRenderLists] = useState({});
  const [selectedChecklist, setSelectedChecklist] = useState(null);
  const [expandedProject, setExpandedProject] = useState(null);
  const [projectAiSummaries, setProjectAiSummaries] = useState({});
  const [expandedClient, setExpandedClient] = useState(null);
  const [expandedGroup, setExpandedGroup] = useState(null);
  const [expandedMaster, setExpandedMaster] = useState(null);
  const [expandedMasterProject, setExpandedMasterProject] = useState(null);
  const [expandedPieceworkProject, setExpandedPieceworkProject] = useState(null);
  const [expandedRoom, setExpandedRoom] = useState(null);
  const [searchUser, setSearchUser] = useState('');
  const [newTask, setNewTask] = useState('');
  const [companyChatMessage, setCompanyChatMessage] = useState('');
  const [projectChatMessage, setProjectChatMessage] = useState('');
  const [masterProjectId, setMasterProjectId] = useState('');
  const [selectedWorks, setSelectedWorks] = useState({});
  const [estimateDoneDrafts, setEstimateDoneDrafts] = useState({});
  const [estimateWorkMaterials, setEstimateWorkMaterials] = useState({});
  const [estimateWorkParams, setEstimateWorkParams] = useState({});
  const [companyName, setCompanyName] = useState('');
  const [issueToolData, setIssueToolData] = useState(createIssueToolForm);
  const [returnToolCondition, setReturnToolCondition] = useState('Исправен');
  const [newPayment, setNewPayment] = useState(createActPaymentForm);
  const [newPiecework, setNewPiecework] = useState(createPieceworkForm);
  const [newProject, setNewProject] = useState(createProjectForm);
  const [newClient, setNewClient] = useState(createClientForm);
  const [newWarehouse, setNewWarehouse] = useState(createWarehouseForm);
  const [newMovement, setNewMovement] = useState(createWarehouseMovementForm);
  const [newInvoice, setNewInvoice] = useState(createWarehouseInvoiceForm);
  const [newStaff, setNewStaff] = useState(emptyStaffForm());
  const [staffExpandedSections, setStaffExpandedSections] = useState({access:false,docs:false,finance:false,extra:false});
  const [expandedStaffId, setExpandedStaffId] = useState(null);
  const [staffProfile, setStaffProfile] = useState(null);
  const [staffProfileLoading, setStaffProfileLoading] = useState(false);
  const [newStaffDoc, setNewStaffDoc] = useState(createStaffDocumentForm);
  const [showStaffDocForm, setShowStaffDocForm] = useState(false);

  const [newUser, setNewUser] = useState(createUserForm);
  const [newPricelist, setNewPricelist] = useState(createPricelistForm);
  const [newPlItem, setNewPlItem] = useState(createPricelistItemForm);
  const [newInviteRole, setNewInviteRole] = useState('мастер');
  const [newSupplier, setNewSupplier] = useState(createSupplierForm);
  const [newRequest, setNewRequest] = useState(createRequestForm);
  const [newOffer, setNewOffer] = useState(createSupplierOfferForm);
  const [newContract, setNewContract] = useState(createContractForm);
  const [newAct, setNewAct] = useState(createInterimActForm);
  const [newTool, setNewTool] = useState(createToolForm);
  const [newRoom, setNewRoom] = useState(createRoomForm);
  const [draftRoomWindows, setDraftRoomWindows] = useState([]);
  const [draftRoomDoors, setDraftRoomDoors] = useState([]);
  const [newWindow, setNewWindow] = useState(createWindowForm);
  const [newDoor, setNewDoor] = useState(createDoorForm);
  const [newInventory, setNewInventory] = useState(createInventoryForm);
  const [newWeather, setNewWeather] = useState(createWeatherForm);
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

  const [newStage, setNewStage] = useState(createProjectStageForm);
  const [newChecklist, setNewChecklist] = useState(createChecklistForm);
  const [newChecklistItem, setNewChecklistItem] = useState('');
  const [newPrescription, setNewPrescription] = useState(createPrescriptionForm);
  const [newUnexpected, setNewUnexpected] = useState(EMPTY_ESTIMATE_CHANGE);
  const [newCompanyDoc, setNewCompanyDoc] = useState(createCompanyDocumentForm);
  const [companyReqForm, setCompanyReqForm] = useState(createCompanyRequisitesForm);
  const [profileData, setProfileData] = useState(createProfileForm);
  const [newLead, setNewLead] = useState(createLeadForm);
  const [newTbEntry, setNewTbEntry] = useState(createTbEntryForm);
  const [newParticipant, setNewParticipant] = useState('');
  const sidebarRef = useRef(null);
  const chatEndRef = useRef(null);

  const showPreview = (content, title) => { setPreviewContent(content); setPreviewTitle(title); };

  const {
    askDirectorAgent,
    sendAiMessage,
  } = createAiAssistantActions({
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

  const {
    loadAuditLog,
    openSystemStatus,
  } = createSystemActions({
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
    setShowNotifications,
    user,
  });

  useNotificationDismissEffect(setShowNotifications);

  useEffect(() => {
    if (!user || activePage !== 'activitylog') return;
    loadAuditLog();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, activePage]);

  const {
    apiAuthHeaders, loadAll, loadMaterialNormsPage, loadMaterialsPage, loadMobileInitial, loadWorkJournalPage,
    refreshData,
  } = useAppDataLoaders({
    activePage, API, AUDIT_LOG_PAGE_LIMIT, buildPagedPath, canAccessRole, createMaterialNormsPageState,
    createMaterialsPageState, createWorkJournalPageState, estimatesTab, initialDataLoaded, isMobile, MATERIAL_NORMS_PAGE_LIMIT, materialNormSearch,
    MATERIALS_PAGE_LIMIT, mergeRowsByIdValue, mobileApiRequestsRef, mobileLoadedScopesRef, mobileScopeForPage, normalizeEstimateList, roleFlagsForUser,
    ROLES, setAccountablePayments, setAiFindings, setAiTasks, setAllBrigadeItems, setAllBrigadePayments, setAuditLog,
    setBrigadeContracts, setCableJournal, setChecklists, setClients, setCompanyDocuments, setCompanyMessages, setCompanyRequisites,
    setContracts, setEstimateReconciliations, setEstimatesList, setEstimatesPage, setExpenseReports, setHiddenActs, setHistory,
    setInitialDataLoaded, setInspectionOrders, setInterimActs, setInventory, setInviteCodes, setInvoices, setLeads,
    setManualExpenses, setMasterProfiles, setMaterialAliases, setMaterialInspections, setMaterialNormOverrides, setMaterialNorms, setMaterialNormsPage,
    setMaterialNormSuggestions, setMaterials, setMaterialsPage, setMaterialTransfers, setMeasurementRoomDrafts, setOwnExpenses, setPdConsents,
    setPiecework, setPrescriptionsList, setPricelists, setProjectDocuments, setProjectLetters, setProjectMeasurements, setProjectPayments,
    setProjects, setProjectStages, setRoomDoors, setRooms, setRoomWindows, setRoomWorks, setSalaryPayments,
    setStaff, setSupervisorActs, setSupplierCatalog, setSupplierInvoices, setSupplierOffers, setSuppliers, setSupplyClaims,
    setSupplyDeliveries, setSupplyHistory, setSupplyRequests, setSupplyTemplates, setTbJournal, setTimesheet,
    setToolHistory, setTools, setUnexpectedWorksList, setUser, setUsers, setWarehouseMain, setWarehouseMovements,
    setWarehouses, setWarrantyDefects, setWorkJournal, setWorkJournalPage, user, WORK_JOURNAL_PAGE_LIMIT,
  });

  const unreadMessagesCount = unreadCompanyMessagesCount(companyMessages, user);

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
    user,
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
    setPushEnabled,
    storageSetters: {
      masterRatings: setMasterRatings,
      activityLog: setActivityLog,
      notifications: setNotifications,
      tbJournal: setTbJournal,
      geoCheckins: setGeoCheckins,
      signedDocs: setSignedDocs,
      actPayments: setActPayments,
      weatherLog: setWeatherLog,
    },
    user,
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
    user,
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
    setNewBrigadePayment,
    setNewPayment,
    setSelectedBrigadeContract,
    setShowBrigadePayModal,
    setShowPayActModal,
    toNum,
    user,
  });

  const {
    sendCompanyChatMessage,
    sendProjectChatMessage,
    setShowChatPanel,
  } = createChatActions({
    API,
    loadProjectChat,
    setCompanyChatMessage,
    setCompanyMessages,
    setShowChatPanelRaw,
    setProjectChatMessage,
    showChatPanel,
    unreadMessagesCount,
    user,
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
    user,
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
    setInitialDataLoaded,
    setLoginError,
    setMasterProfile,
    setRegInviteInfo,
    setRegSupplierData,
    setShowProfileForm,
    setUser,
    user,
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
    data: { clients, materials, projects, tools },
    state: { globalSearch, isMobile, masterProjectId, user },
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
  const {
    aiFindingsForProject,
    aiTasksForProject,
    generateAiFindingsForProject,
    openAiTaskAction,
    patchAiFindingSilent,
    patchAiTaskSilent,
    updateAiFinding,
    updateAiTask,
  } = createAiTaskActions({
    API,
    aiFindings,
    aiTasks,
    buildEstimateDiffContent: (...args) => buildEstimateDiffContent(...args),
    estimateDiffBaseFor: (...args) => estimateDiffBaseFor(...args),
    estimatesList,
    navigateTo: (...args) => navigateTo(...args),
    openEstimateDetail: (...args) => openEstimateDetail(...args),
    projects,
    refreshData,
    setActiveProjectTab,
    setActiveTabGroup,
    setAiFindings,
    setAiTasks,
    setEstimatesTab,
    setExpandedProject,
    setMaterialNormCoverageProject,
    setWarehouseTab,
    showPreview,
  });

  const {
    openEstimateDetail,
    estimateDiffBaseFor,
    buildEstimateDiffContent,
    estimateReconciliationsForProject,
    openEstimateReconciliationPreview,
    createEstimateReconciliation,
    approveEstimateReconciliation,
    estimateChangeForComparisonRow,
    createEstimateChangeFromComparisonRow,
    includeChangesInNewEstimate,
    setEstimateStatusRemote,
    deleteEstimateRemote,
  } = createEstimateWorkflowActions({
    API,
    estimatesList,
    setEstimatesList,
    setSelectedEstimate,
    estimateReconciliations,
    setEstimateReconciliations,
    unexpectedWorksList,
    isApprovedEstimateChangeStatus,
    buildEstimateDiffDocContent,
    buildEstimateReconciliationDocContent,
    apiAuthHeaders,
    showPreview,
    refreshData,
    user,
    notify,
    setActiveProjectTab,
    setActiveTabGroup,
    setShowForm,
    setActivePage,
    setEstimatesTab,
    queueEstimateDiffReviewTask: (...args) => queueEstimateDiffReviewTask(...args),
    autoReconcileEstimateChanges: (...args) => autoReconcileEstimateChanges(...args),
    queueEstimateQualityReviewTask: (...args) => queueEstimateQualityReviewTask(...args),
    queueEstimateNormReviewTask: (...args) => queueEstimateNormReviewTask(...args),
  });
  const {
    activeEstimatesForProject,
    estimateChangeRowsForDocs,
    estimateChangesForNewEstimate,
    estimateItemOptionsForProject,
    getProjectEstimateWorkOptions,
    getProjectWorkPackageOptions,
    includableEstimateChanges,
    ks2ItemsFromEstimate,
    projectPlanDone,
    renderEstimateMeasurementComparisonPanel,
    renderEstimateReconciliationsPanel,
    renderWorkJournalEstimateReconciliationPanel,
  } = createProjectEstimateRuntime({
    ESTIMATE_PACKAGES,
    activeTabActions: {
      openEstimateChanges: () => {
        setActiveProjectTab('Изменения к смете');
        setActiveTabGroup('work');
      },
    },
    approveEstimateReconciliation,
    createEstimateChangeFromComparisonRow,
    createEstimateReconciliation,
    estimateChangeForComparisonRow,
    estimateDiffBaseFor,
    estimateReconciliationsForProject,
    estimatesList,
    openEstimateReconciliationPreview,
    projects,
    rooms,
    roomDoors,
    roomWindows,
    showPreview,
    unexpectedWorksList,
    user,
    visibleEstimatesForCurrentUser,
    workJournal,
    workJournalEstimateStatusMeta,
  });
  const {
    buildMaterialNormCoverageContent,
    canonicalMaterialMeta,
    estimateNormCoverageRows,
    estimateWorkNormRequirementRows,
    isPersonalMaterialRole,
    isSupplyDeliveryInvoice,
    materialAliasCandidates,
    materialAvailabilityMapForWork,
    materialControlSummaryForProject,
    materialHintForProject,
    materialNameKey,
    materialNameLookupKey,
    materialNormControlSummaryForProject,
    materialNormForWork,
    materialReconciliationRows,
    materialRowsAvailableForWork,
    materialSuggestionsForWork,
    personalMaterialRowsForProject,
    warehouseInvoiceEstimateControl,
    warehouseInvoiceItems,
    workNeedsThicknessParam,
  } = createMaterialRuntime({
    activeEstimatesForProject,
    canonicalCompanyName: companyName,
    companyRequisites,
    history,
    invoices,
    materialAliases,
    materialInspections,
    materialNormOverrides,
    materialNorms,
    materials,
    materialTransfers,
    parseSupplyItems,
    projects,
    supplyDeliveries,
    supplyHistory,
    supplyRequests,
    user,
    warehouseMain,
    warehouseMovements,
    workJournal,
  });
  const {
    getRoomNetWall,
    roomCompleteness,
    roomMeasurementCheck,
    roomMeasurementMessage,
  } = createRoomMeasurementRuntime({
    C,
    materialNameKey,
    roomDoors,
    roomWindows,
    roomWorks,
    rooms,
  });
  const {
    aiTaskByMarker,
    autoReconcileEstimateChanges,
    estimateListWithUpdatedEstimate,
    hasActiveEstimator,
    jumpToEstimateIssue,
    materialControlSignatureForProject,
    queueEstimateDiffReviewTask,
    queueEstimateNormReviewTask,
    queueEstimateQualityReviewTask,
    queueMaterialControlTasksForProject,
    queueRoomControlTasksForProject,
    renderEstimateChangeReconcileTask,
    roomControlSignatureForProject,
  } = createAiReviewQueueActions({
    API,
    aiFindings,
    aiTasks,
    buildEstimateDiff,
    estimateChangeAutoDecision,
    estimateChangeReconcileDescription,
    estimateChangeReconcileMarker,
    estimateChangeReconcileQueuedRef,
    estimateDiffBaseFor,
    estimateDiffReviewDescription,
    estimateDiffReviewMarker,
    estimateDiffReviewQueuedRef,
    estimateKind,
    estimateNormCoverageRows,
    estimateNormReviewDescription,
    estimateNormReviewIssueStatuses,
    estimateNormReviewMarker,
    estimateNormReviewQueuedRef,
    estimatePackage,
    estimateQualityDescription,
    estimateQualityReviewMarker,
    estimateQualityReviewQueuedRef,
    estimateQualityRows,
    estimatesList,
    fmtMeasure,
    includableEstimateChanges,
    isArchivedEstimate,
    isGlobalEstimateTemplate,
    isOpenAiStatus,
    materialAliasCandidates,
    materialControlSummaryForProject,
    materialControlTaskQueuedRef,
    materialNameKey,
    materialNormControlSummaryForProject,
    openAiTaskAction,
    patchAiFindingSilent,
    patchAiTaskSilent,
    roomCompleteness,
    roomControlTaskQueuedRef,
    roomWorks,
    rooms,
    sameEstimateGroup,
    selectedEstimate,
    setAiTasks,
    setEstimateIssueFocusKey,
    setUnexpectedWorksList,
    staff,
    user,
    users,
    workJournal,
  });
  const frontendAiAutoControlEnabled = false; // backend /ai-control/* теперь единый источник фоновых задач
  useEffect(() => {
    if (!frontendAiAutoControlEnabled) return;
    if (!user || !['директор','зам_директора','сметчик','главный_инженер'].includes(user.role)) return;
    if (!Array.isArray(estimatesList) || estimatesList.length===0) return;
    const activeCustomerEstimates = (estimatesList||[])
      .filter(est=>est?.id && estimateKind(est)==='Заказчик' && !isArchivedEstimate(est) && (est.status||'Черновик')==='Активная')
      .slice(0, 25);
    activeCustomerEstimates.forEach(est=>{
      const qualityMarker = estimateQualityReviewMarker(est.id);
      if (!estimateQualityReviewAutoCheckedRef.current.has(qualityMarker)) {
        estimateQualityReviewAutoCheckedRef.current.add(qualityMarker);
        queueEstimateQualityReviewTask(est, 'Фоновая проверка активной сметы');
      }
      const normMarker = estimateNormReviewMarker(est.id);
      if (estimateNormReviewAutoCheckedRef.current.has(normMarker)) return;
      estimateNormReviewAutoCheckedRef.current.add(normMarker);
      queueEstimateNormReviewTask(est, 'Фоновая проверка активной сметы', estimatesList);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id, user?.role, estimatesList, materialNorms, materialNormOverrides]);
  useEffect(() => {
    if (!frontendAiAutoControlEnabled) return;
    if (!user || !['директор','зам_директора','снабженец','прораб','главный_инженер','сметчик'].includes(user.role)) return;
    if (!Array.isArray(projects) || projects.length===0) return;
    const visible = visibleActiveProjects(projects).slice(0,20);
    visible.forEach(p=>{
      const signature = materialControlSignatureForProject(p.name);
      const prev = materialControlTaskAutoCheckedRef.current.get(p.name);
      if (prev === signature) return;
      materialControlTaskAutoCheckedRef.current.set(p.name, signature);
      queueMaterialControlTasksForProject(p.name, 'Фоновая проверка материалов');
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id, user?.role, projects, estimatesList, materials, supplyRequests, supplyDeliveries, supplyHistory, supplierInvoices, invoices, materialTransfers, workJournal, materialNorms, materialNormOverrides, materialAliases]);
  useEffect(() => {
    if (!frontendAiAutoControlEnabled) return;
    if (!user || !['директор','зам_директора','прораб','главный_инженер','сметчик'].includes(user.role)) return;
    if (!Array.isArray(projects) || projects.length===0) return;
    const visible = visibleActiveProjects(projects).slice(0,20);
    visible.forEach(p=>{
      const signature = roomControlSignatureForProject(p.name);
      const prev = roomControlTaskAutoCheckedRef.current.get(p.name);
      if (prev === signature) return;
      roomControlTaskAutoCheckedRef.current.set(p.name, signature);
      queueRoomControlTasksForProject(p.name, 'Фоновая проверка помещений и ЖПР');
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id, user?.role, projects, rooms, roomWindows, roomDoors, roomWorks, workJournal]);
  const {
    materialNormSupplyRequestExists,
    createSupplyRequestFromNormCoverage,
    createBatchSupplyRequestFromNormCoverage,
    autoFillNormMaterialsForWork,
    canEditMaterialNorms,
    canCreateSupplyRequestFromNorm,
    resetMaterialNormForm,
    editMaterialNorm,
    saveMaterialNorm,
    disableMaterialNorm,
    activeMaterialNormSuggestions,
    generateMaterialNormSuggestions,
    acceptMaterialNormSuggestion,
    acceptMaterialNormSuggestionAsOverride,
    createEstimateFromNormSuggestions,
    rejectMaterialNormSuggestion,
    createTaskFromMaterialNormSuggestion,
  } = createMaterialNormActions({
    API,
    user,
    projects,
    supplyRequests,
    materialNormPreviewSuggestions,
    materialNormSuggestions,
    materialNormCoverageProject,
    newMaterialNorm,
    editingMaterialNormId,
    estimatesTab,
    isActiveSupplyRequestStatus,
    materialRowsAvailableForWork,
    materialNormForWork,
    capMaterialWriteoffQty: (...args) => capMaterialWriteoffQty(...args),
    materialNameKey,
    visibleActiveProjects,
    canEditMaterialNormsForUser,
    canCreateSupplyRequestFromNormForUser,
    setSupplyRequests,
    setMaterialNormNotice,
    setNewMaterialNorm,
    setEditingMaterialNormId,
    setEstimatesTab,
    setMaterialNormSuggestionLoading,
    setMaterialNormPreviewSuggestions,
    setEstimatesList,
    setSelectedEstimate,
    notify,
    refreshData,
    navigateTo: (...args) => navigateTo(...args),
  });
  const {
    addEstimateMaterialFromCoverage,
    createMaterialNormCoverageTask,
    markEstimateWorkNoMaterialFromCoverage,
    saveMaterialNormOverrideFromCoverage,
  } = createMaterialNormCoverageActions({
    API,
    user,
    estimatesList,
    selectedEstimate,
    canEditMaterialNorms,
    sectionsOfEstimate: _sectionsOfEst,
    persistEstimate,
    refreshData,
    setAiTasks,
    setEstimatesList,
    setMaterialNormNotice,
    setSelectedEstimate,
  });
  const {
    applyMaterialOverNormReason,
    capMaterialWriteoffQty,
    materialNormOverrunReason,
    materialWriteoffBlockMessage,
    removeEstimateWorkMaterial,
    removeSelectedWorkMaterial,
    renderMaterialWriteoffStatus,
    updateEstimateWorkMaterialQty,
    updateSelectedWorkMaterialQty,
    upsertEstimateWorkMaterial,
    upsertSelectedWorkMaterial,
  } = createMaterialWriteoffActions({
    C,
    MaterialWriteoffStatus,
    canonicalMaterialMeta,
    fmtMeasure,
    isMobile,
    isPersonalMaterialRole,
    materialAvailabilityMapForWork,
    materialNameKey,
    setEstimateWorkMaterials,
    setSelectedWorks,
  });
  const {
    canUseDirectorAgent,
    calcSalary,
    financeUsers,
    formatSignedRub,
    isDirector,
    isLeadership,
    isMasterRole,
    isProrab,
    projectPaymentInAmount,
    projectPaymentSignedAmount,
    roleColor,
    workedDays,
  } = createAppRoleRuntime({ piecework, timesheet, user, users });
  const {
    acceptMaterialAliasTask,
    createBatchSupplyRequestFromMaterialControl,
    createInvoiceControlReviewTasksForInvoice,
    renderInvoiceControlActions,
    renderMaterialAliasControls,
    renderMaterialSupplyAction,
  } = createMaterialControlActions({
    API,
    C,
    btnB,
    btnG,
    btnO,
    user,
    materialAliases,
    setMaterialAliases,
    supplyRequests,
    aiTaskByMarker,
    setAiTasks,
    materialNameLookupKey,
    materialAliasCandidates,
    canonicalMaterialMeta,
    materialNameKey,
    warehouseInvoiceEstimateControl,
    openAiTaskAction,
    updateAiTask,
    hasActiveEstimator,
    notify,
    refreshData,
    fmtMeasure,
    toNum,
    _normalizeUnit,
    isLeadership,
  });
  const documentActionRefs = {};
  const {
    computeNotifications,
    directorMapActionTarget,
    directorMapContractForProject,
    expByCategory,
    getActStatusForJournal,
    projectBudgetSpent,
    projectEconomy,
    projectObjectLinks,
    projectRealProgress,
    renderMaterialReconciliationPanel,
    workExecutionTotal,
  } = createProjectDashboardRuntime({
    C,
    EXPENSE_CATEGORIES,
    accountablePayments,
    activeEstimatesForProject,
    aiFindingsForProject,
    aiTasksForProject,
    allBrigadeItems,
    badge,
    btnB,
    buildMaterialRequirementContent: (...args) => documentActionRefs.buildMaterialRequirementContent?.(...args) || '',
    cableJournal,
    calcSalary,
    card,
    estimatePackage,
    estimateReconciliationsForProject,
    estimatesList,
    expenseReports,
    fmtMeasure,
    hiddenActs,
    invoices,
    isApprovedEstimateChangeStatus,
    isArchivedEstimate,
    isFinanceRole,
    isLeadership,
    manualExpenses,
    materialControlStatus,
    materialControlSummaryForProject,
    materialInspections,
    materials,
    measurementRoomDrafts,
    ownExpenses,
    piecework,
    prescriptionsList,
    projectDocuments,
    projectFactSpent,
    projectLetters,
    projectMeasurements,
    projectPayments,
    projectPlanDone,
    projectStages,
    renderMaterialAliasControls,
    renderMaterialSupplyAction,
    roomCompleteness,
    rooms,
    showPreview,
    staff,
    supplierInvoices,
    supplyDeliveries,
    supplyRequests,
    tbl,
    tblC,
    tblH,
    unexpectedWorksList,
    user,
    visibleEstimatesForCurrentUser,
    workJournal,
  });
  const lowStock = lowStockFor(materials);
  const lowMainStock = lowStockFor(warehouseMain);
  const {
    buildDirectorBriefReportContent,
    buildSupplyControlReportContent,
    estimateControlIssues,
    openEstimateControlReport,
  } = createDirectorDashboardActions({
    API,
    activeEstimatesForProject,
    companyName,
    estimateList: estimatesList,
    fmtDocMoney,
    fmtMeasure,
    inspectionOrders,
    invoiceControlMaterialName,
    invoiceControlNeedsReview,
    invoiceControlProjectName,
    invoiceControlReviewReason,
    invoices,
    lowMainStock,
    lowStock,
    materialNormControlSummaryForProject,
    materialReconciliationRows,
    normalizeEstimateList,
    ownExpenses,
    projectBudgetSpent,
    projects,
    setEstimatesList,
    showPreview,
    supplierInvoices,
    supplierOffers,
    supplyRequests,
    user,
    warehouseInvoiceEstimateControl,
    workJournal,
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

  if (isMasterRole()) {
    return (
      <AppMasterCabinetRoute
        pageFallback={pageFallback}
        constants={{ EXPENSE_CATEGORIES, PD_CONSENT_TEXT, ROLE_LABELS, SURFACES, UNITS }}
        ui={{ API, C, badge, btnB, btnG, btnGr, btnO, btnR, card, inp, isMobile }}
        data={{
          accountablePayments,
          activePage,
          brigadeContracts,
          brigadeContractItems: allBrigadeItems,
          cableJournal,
          companyChatMessage,
          companyMessages,
          consentChecked,
          contracts,
          estimateDoneDrafts,
          estimateItemDoneTotal,
          estimateWorkKey,
          estimateWorkMaterials,
          estimateWorkParams,
          estimatesList,
          expandedProject,
          fileSrc,
          hiddenActs,
          interimActs,
          isPersonalMaterialRole,
          listSearch,
          masterProfile,
          masterProfiles,
          masterProjectId,
          materialAvailabilityMapForWork,
          materialControlStatus,
          materialHintForProject,
          materialNameKey,
          materialNormForWork,
          materialNormStatus,
          materialRowsAvailableForWork,
          materialSuggestionsForWork,
          materialTransfers,
          myNotifications,
          newOwnExpense,
          newSupplyReq,
          notifications,
          ownExpenses,
          pdConsents,
          personalMaterialRowsForProject,
          piecework,
          previewContent,
          previewTitle,
          priceHints,
          pricelistItems,
          pricelists,
          profileData,
          projects,
          rooms,
          selectableActiveProjects,
          selectedBrigadeContract,
          selectedWorks,
          showNotifications,
          showOwnExpenseForm,
          showPhotoModal,
          showProfileForm,
          showSupplyForm,
          supplyCollapsedProjects,
          supplyRequestOrigin,
          supplyRequests,
          supplyTemplates,
          tools,
          unreadNotifications,
          user,
          visibleEstimatesForCurrentUser,
          workJournal,
          workNeedsThicknessParam,
        }}
        actions={{
          addMasterWorks,
          appendPhotos,
          applySupplyTemplate,
          autoFillNormMaterialsForWork,
          buildActContent,
          buildCableJournalContent,
          buildContractContent,
          buildHiddenActContent,
          cableTypeOf,
          checkinGeo,
          closeNotifications,
          confirmMaterialReceipt,
          createSupplyReq,
          deleteSupplyTemplate,
          doPrint,
          fetchPriceHint,
          fmtMeasure,
          getNotifPage,
          handleLogout,
          loadAll,
          loadPricelistItems,
          markMyNotificationsRead,
          matchSearch,
          navigateTo,
          normalizeMeasure,
          notify,
          parseSupplyItems,
          refreshData,
          removeEstimateWorkMaterial,
          removeSelectedWorkMaterial,
          renderMaterialWriteoffStatus,
          renderSupplyPlanningHint,
          renderSupplyRequestOrigin,
          returnMaterialToProject,
          roleColor,
          roomMeasurementCheck,
          roomMeasurementMessage,
          saveProfile,
          saveSupplyTemplate,
          sendCompanyChatMessage,
          setActivePage,
          setCableJournal,
          setCompanyChatMessage,
          setConsentChecked,
          setEstimateDoneDrafts,
          setEstimateWorkMaterials,
          setEstimateWorkParams,
          setEditingAct,
          setExpandedProject,
          setHiddenActs,
          setListSearch,
          setMasterProjectId,
          setNewOwnExpense,
          setNewSupplyReq,
          setNotifications,
          setPreviewContent,
          setProfileData,
          setReportingPayment,
          setSelectedWorks,
          setShowNotifications,
          setShowOwnExpenseForm,
          setShowPhotoModal,
          setShowProfileForm,
          setShowSupplyForm,
          setSupplyCollapsedProjects,
          setUser,
          showPreview,
          submitEstimateWorkDone,
          toNum,
          toggleNotifications,
          updateEstimateWorkMaterialQty,
          updateProjectProgress,
          updateSelectedWorkMaterialQty,
          uploadPhoto,
          upsertEstimateWorkMaterial,
          upsertSelectedWorkMaterial,
        }}
      />
    );
  }

  const isEntryRoute = !user || ['system_owner', 'platform_admin', 'platform_support', 'billing_admin', 'account_owner', 'account_admin'].includes(user.role);
  if (isEntryRoute) {
    return (
      <AppEntryRoutes
        user={user}
        page={page}
        pageFallback={pageFallback}
        ui={{ API, C, badge, btnG, btnGr, btnO, btnR, card, inp }}
        constants={{ ROLE_LABELS }}
        state={{ email, loginError, password, regCode, regEmail, regInviteInfo, regName, regPassword, regSupplierData }}
        actions={{ handleLogin, handleLogout, handleRegister, handleTwoFactorLogin, setEmail, setLoginError, setPage, setPassword, setRegCode, setRegEmail, setRegName, setRegPassword, setRegSupplierData, setUser }}
      />
    );
  }

  const allMenuItems = buildAppMenuItems();

  // Кабинет поставщика
  if (user && user.role === 'поставщик') {
    return (
      <AppSupplierCabinetRoute
        constants={{ UNITS }}
        ui={{ API, C, badge, btnB, btnG, btnGr, btnO, btnR, card, inp, tbl, tblC, tblH }}
        data={{
          invoicingOfferId,
          newCatalogItem,
          newKpResponse,
          newOfferInvoice,
          respondingOfferId,
          shipmentForm,
          shippingOfferId,
          showCatalogForm,
          supplierCatalog,
          supplierInvoices,
          supplierOffers,
          supplierRequisites,
          supplierTab,
          suppliers,
          supplyClaims,
          supplyDeliveries,
          supplyRequests,
          user,
        }}
        actions={{
          createInvoiceFromOffer,
          createShipmentFromOffer,
          fileSrc,
          handleLogout,
          notify,
          parseSupplyItems,
          refreshData,
          setInvoicingOfferId,
          setNewCatalogItem,
          setNewKpResponse,
          setNewOfferInvoice,
          setRespondingOfferId,
          setShipmentForm,
          setShippingOfferId,
          setShowCatalogForm,
          setSupplierCatalog,
          setSupplierRequisites,
          setSupplierTab,
          uploadPhoto,
        }}
      />
    );
  }



  if (user && ['технадзор', 'заказчик'].includes(user.role)) {
    return (
      <AppRoleCabinetRoutes
        user={user}
        pageFallback={pageFallback}
        ui={{ C, card, btnG, btnB, btnO, btnGr, btnR, inp }}
        state={{ listSearch, showForm, newSupervisorAct, supervisorActPhoto, prescriptionPhoto, editingAct, showPhotoModal, previewContent, previewTitle }}
        data={{ projects, workJournal, checklists, prescriptionsList, supervisorActs, materialInspections, hiddenActs, unexpectedWorksList, projectStages, projectPayments, contracts }}
        actions={{ handleLogout, setListSearch, showPreview, setShowPhotoModal, setPrescriptionPhoto, appendPhotos, refreshData, setShowForm, setNewSupervisorAct, setSupervisorActPhoto, setEditingAct, setHiddenActs, setPreviewContent }}
        selectors={{ matchSearch, projectRealProgress, projectPlanDone, computeNotifications, fmtMeasure, fileSrc, activeEstimatesForProject, estimatePackage, sectionsOfEstimate: _sectionsOfEst, estimateItemMaterialSum, estimateItemTotal, isApprovedEstimateChangeStatus }}
        builders={{ buildSupervisorMonthlyReport, buildPrescriptionContent, buildSupplementaryAgreementContent, showKS2, buildKS3Content, doPrint }}
      />
    );
  }

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
