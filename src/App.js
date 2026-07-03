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
  detectMobileLayout,
  inp,
  tbl,
  tblC,
  tblH,
} from './constants/uiTheme';
import { ROLES, ROLE_GROUPS, ROLE_LABELS } from './constants/roles';
import AppOverlayLayer from './components/AppOverlayLayer';
import ProjectCardHeader from './components/ProjectCardHeader';
import ProjectTabsNav from './components/ProjectTabsNav';
import ProjectMaterialsControlPanel from './components/ProjectMaterialsControlPanel';
import ProjectMaterialsStockPanel from './components/ProjectMaterialsStockPanel';
import ProjectMaterialsTransferPanel from './components/ProjectMaterialsTransferPanel';
import ProjectFinancePanel from './components/ProjectFinancePanel';
import ProjectEconomyPanel from './components/ProjectEconomyPanel';
import ProjectObjectLinksPanel from './components/ProjectObjectLinksPanel';
import ProjectSitePublicationPage from './components/ProjectSitePublicationPage';
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
import ProjectsPage from './features/projects/ProjectsPage';
import { createWarehouseCrudActions } from './features/warehouse/warehouseCrudActions';
import { createMaterialControlActions } from './features/material-control/materialControlActions';
import { createDataLoadActions } from './features/data-loaders/dataLoadActions';
import { useAppDataLoaders } from './features/data-loaders/useAppDataLoaders';
import { createProjectDashboardRuntime } from './features/dashboard/projectDashboardRuntime';
import PreviewModal from './components/PreviewModal';
import ImagePreviewModal from './components/ImagePreviewModal';
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
import EstimateReconciliationsPanel from './components/EstimateReconciliationsPanel';
import EstimateMeasurementComparisonPanel from './components/EstimateMeasurementComparisonPanel';
import WorkJournalEstimateReconciliationPanel from './components/WorkJournalEstimateReconciliationPanel';
import EstimateDuplicateWorkSummaryPanel from './components/EstimateDuplicateWorkSummaryPanel';
import EstimateSectionsEditor from './components/EstimateSectionsEditor';
import MaterialNormFormPanel from './components/MaterialNormFormPanel';
import MaterialNormsListPanel from './components/MaterialNormsListPanel';
import EstimateExecutionPricingPanel from './components/EstimateExecutionPricingPanel';
import PhotoAttachmentField from './components/PhotoAttachmentField';
import MobileBottomNav from './components/MobileBottomNav';
import { MasterCabinetPage } from './app/lazyComponents';
import { createAuthActions } from './features/auth/authActions';
import { createAiAssistantActions } from './features/ai-assistant/aiAssistantActions';
import { createChatActions } from './features/chat/chatActions';
import { createCrmActions } from './features/crm/crmActions';
import { createGeoActions } from './features/geolocation/geoActions';
import { createNotificationActions } from './features/notifications/notificationActions';
import { createSystemActions } from './features/system/systemActions';
import { createUploadActions } from './features/uploads/uploadActions';
import WorkAssignmentModal, { WorkAssignmentStatusPanel } from './features/work-assignment';
import { createAiTaskActions } from './features/ai-control/aiTaskActions';
import { createAiReviewQueueActions } from './features/ai-control/aiReviewQueueActions';
import { createUserAccessActions } from './features/admin/userAccessActions';
import { createDocumentActions } from './features/documents/documentActions';
import { createPaymentActions } from './features/payments/paymentActions';
import { createPersonnelActions } from './features/personnel/personnelActions';
import { createPricelistActions } from './features/pricelists/pricelistActions';
import { createMaterialNormActions } from './features/material-norms/materialNormActions';
import { createMaterialNormCoverageActions } from './features/material-norms/materialNormCoverageActions';
import { createMaterialTransferActions } from './features/material-transfer/materialTransferActions';
import { createMaterialWriteoffActions } from './features/material-writeoff/materialWriteoffActions';
import { createWorkJournalActions } from './features/work-journal/workJournalActions';
import SupplierCabinetPage from './features/supply/SupplierCabinetPage';
import DashboardPage from './features/dashboard/DashboardPage';
import EstimatesPage from './features/estimates/EstimatesPage';
import AppSidebar from './components/AppSidebar';
import AppHeaderBar from './components/AppHeaderBar';
import AppWorkflowModals from './components/AppWorkflowModals';
import AppSecondaryPages from './components/AppSecondaryPages';
import AppDirectoryPages from './components/AppDirectoryPages';
import AppOperationsPages from './components/AppOperationsPages';
import AppBackofficePages from './components/AppBackofficePages';
import AppActionModals from './components/AppActionModals';
import AppEntryRoutes from './components/AppEntryRoutes';
import AppProjectEditModals from './components/AppProjectEditModals';
import AppPageFallback from './components/AppPageFallback';
import { buildAppMenuItems } from './components/AppMenuItems';
import AppRoleCabinetRoutes from './components/AppRoleCabinetRoutes';
import { resolveEstimatePackage } from './utils/estimatePackage';
import { _normalizeUnit, denormalizeMeasure, fmtMeasure, normalizeMeasure, toNum } from './utils/measureUtils';
import {
  EMPTY_MATERIAL_NORM_FORM,
  WORK_MATERIAL_NORM_RULES,
  calculateMaterialNormForWork,
  calculateNormRequirementsForWork,
  convertUnits,
  materialNormCoverageComment,
  materialNormCoverageDisplayRows,
  materialNormCoverageExportRows,
  materialNormRuleForCalc,
  materialNormCanCreateSupply,
  materialTitleForNormRule,
  workNormRulesForCalculation,
} from './utils/materialNormUtils';
import { materialLookupText } from './utils/materialMatchUtils';
import {
  buildEstimateMaterialPlanRows,
  buildMaterialAliasCandidates,
  buildMaterialControlSummary,
  buildMaterialReconciliationRows,
} from './utils/materialReconciliationUtils';
import { buildWarehouseInvoiceEstimateControl } from './utils/warehouseInvoiceControlUtils';
import {
  buildEstimateNormCoverageRows,
  buildEstimateWorkNormRequirementRows,
  buildMaterialAvailabilityMap,
  buildMaterialNormControlSummary,
  buildMaterialNormDeviationRows,
  buildMaterialSuggestionsForWork,
  buildPersonalMaterialRowsForProject,
} from './utils/materialNormSelectors';
import {
  calcDoorArea,
  calcDoorReveals,
  calcWindowArea,
  calcWindowReveals,
  buildRoomMeasurementCheck,
  getRoomNetWall as calcRoomNetWall,
  roomCompleteness as calcRoomCompleteness,
  roomMeasurementMessage,
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
  estimateWorkKeyForItem,
  isArchivedEstimate,
  isGlobalEstimateTemplate,
  isEstimatePricelist,
  isEstimateMaterialItem,
  isEstimateWorkItem,
  normalizeEstimateImportSections,
  normalizeEstimateItemType,
  normalizeEstimateList,
  normalizeImportedEstimateItem,
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
import {
  estimateMeasurementComparisonSummaryFor,
  projectMeasurementBasisTotalsFor,
} from './utils/estimateMeasurementComparisonUtils';
import {
  estimateItemOptionsFromActiveEstimates,
  ks2ItemsFromActiveEstimates,
  projectPlanDoneFor,
} from './utils/projectEstimateItemsUtils';
import { workJournalEstimateSummaryFor } from './utils/workJournalEstimateReconciliationUtils';
import { createEstimateWorkflowActions } from './features/estimates/estimateWorkflowActions';
import { createEstimatePageActions } from './features/estimates/estimatePageActions';
import { createSupplyActions } from './features/supply/supplyActions';
import { createSupplyPlanningUi } from './features/supply/supplyPlanningUi';
import { createProjectOperationActions } from './features/project-operations/projectOperationActions';
import { createProjectMeasurementActions } from './features/project-measurements/projectMeasurementActions';
import { createDirectorDashboardActions } from './features/dashboard/directorDashboardActions';
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
  createFileSrc,
  createWorkJournalPageState,
  daysInMonth,
  doPrint,
  generateQR,
  initialGuestPage,
  loadStoredUser,
  matchSearchFields,
  mergeRowsByIdValue,
  mobileScopeForPage,
  readStoredJson,
  readApiResult,
  requestPushPermission,
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
  isFinanceUser,
  isLeadershipUser,
  isProrabUser,
  roleColorForRole,
  roleFlagsForUser,
  selectableActiveProjectsForUser,
  visibleEstimatesForUser,
  visibleProjectsForUser,
} from './utils/accessUtils';
import {
  calcStaffSalary,
  workedDaysForStaff,
} from './utils/payrollUtils';
import {
  formatSignedRubValue,
  projectPaymentIncomingAmount,
  projectPaymentSignedAmountValue,
} from './utils/projectPaymentUtils';
import {
  projectFactSpentValue,
} from './utils/projectEconomyUtils';
import {
  buildWarehouseInvoiceItems,
  packageMatches,
  parseJournalMaterialsValue,
} from './utils/materialDocumentUtils';
import {
  buildEstimateDiffDocContent,
  buildEstimateMeasurementComparisonDocContent,
  buildEstimateReconciliationDocContent,
  buildMaterialNormCoverageDocContent,
  buildWorkJournalEstimateReconciliationDocContent,
  fmtDocMoney,
} from './utils/printDocumentBuilders';
import {
  EMPTY_ESTIMATE_CHANGE,
  estimateChangeRowsForDocsFromList,
  estimateChangesForNewEstimateFromList,
  includableEstimateChangesForProject,
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
  const [isMobile, setIsMobile] = useState(detectMobileLayout);
  const [isCompactHeader, setIsCompactHeader] = useState(typeof window !== 'undefined' && window.innerWidth < 1180);
  const mobileLoadedScopesRef = useRef(new Set());
  const mobileApiRequestsRef = useRef(new Map());
  const [darkMode, setDarkMode] = useState(typeof window !== 'undefined' && localStorage.getItem('darkMode')==='1');
  useEffect(() => {
    if (typeof document !== 'undefined') document.documentElement.dataset.theme = darkMode ? 'dark' : 'light';
    try { localStorage.setItem('darkMode', darkMode ? '1' : '0'); } catch(e) {}
  }, [darkMode]);
  useEffect(() => {
    const onResize = () => {
      setIsMobile(detectMobileLayout());
      setIsCompactHeader(window.innerWidth < 1180);
    };
    window.addEventListener('resize', onResize);
    window.visualViewport?.addEventListener('resize', onResize);
    onResize();
    return () => {
      window.removeEventListener('resize', onResize);
      window.visualViewport?.removeEventListener('resize', onResize);
    };
  }, []);
  // Регистрация по ссылке: проверяем URL ?invite=CODE и переходим на форму регистрации
  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      const params = new URLSearchParams(window.location.search);
      const code = params.get('invite');
      if (code) {
        setRegCode(code.toUpperCase());
        setPage('register');
        // Очищаем URL чтобы при F5 ссылка не дублировалась
        window.history.replaceState({}, '', window.location.pathname);
      }
    } catch(_) {}
  }, []);
  const [user, setUser] = useState(loadStoredUser);
  const [page, setPage] = useState(initialGuestPage);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [regName, setRegName] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regCode, setRegCode] = useState('');
  const [regInviteInfo, setRegInviteInfo] = useState(null); // {role, presetName, presetCategory, supplierId}
  const [regSupplierData, setRegSupplierData] = useState({companyName:'',inn:'',kpp:'',ogrn:'',phone:'',legalAddress:'',bank:'',bik:'',account:'',directorName:'',category:'',specialization:''});
  const [loginError, setLoginError] = useState(() => {
    try {
      if (typeof window !== 'undefined' && sessionStorage.getItem('authExpiredNotice')) {
        sessionStorage.removeItem('authExpiredNotice');
        return 'Сессия истекла, войдите снова';
      }
    } catch (e) {}
    return '';
  });
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
  const [newSupervisorAct, setNewSupervisorAct] = useState({actType:'Осмотр',description:'',findings:'',recommendations:'',date:''});
  const [supervisorActPhoto, setSupervisorActPhoto] = useState('');
  const [prescriptionPhoto, setPrescriptionPhoto] = useState('');
  const [selectedBrigadeContract, setSelectedBrigadeContract] = useState(null);
  const [brigadeContractItems, setBrigadeContractItems] = useState([]);
  const [brigadePayments, setBrigadePayments] = useState([]);
  const [showBrigadePayModal, setShowBrigadePayModal] = useState(false);
  const [newBrigadePayment, setNewBrigadePayment] = useState({amount:'',paidBy:'',paidDate:'',note:''});
  const [allBrigadeItems, setAllBrigadeItems] = useState([]);
  const [allBrigadePayments, setAllBrigadePayments] = useState([]);
  const [projectDocuments, setProjectDocuments] = useState([]);
  const [newProjectDoc, setNewProjectDoc] = useState({side:'customer',docType:'Договор',number:'',docDate:'',counterparty:'',signStatus:'Не подписан',scanUrl:'',amount:'',notes:''});
  const [sitePublicationDrafts, setSitePublicationDrafts] = useState({});
  const [showDocForm, setShowDocForm] = useState(false);
  const [uploadingDoc, setUploadingDoc] = useState(false);
  const [projectMeasurements, setProjectMeasurements] = useState([]);
  const [measurementRoomDrafts, setMeasurementRoomDrafts] = useState([]);
  const [measurementDraftLoadingId, setMeasurementDraftLoadingId] = useState(null);
  const [newMeasurementDoc, setNewMeasurementDoc] = useState({sourceType:'Фактический ручной',docType:'Обмер',title:'',fileUrl:'',photoUrl:'',status:'Черновик',roomsCreated:'0',notes:''});
  const [showMeasurementForm, setShowMeasurementForm] = useState(false);
  const [uploadingMeasurementDoc, setUploadingMeasurementDoc] = useState(false);
  const [projectLetters, setProjectLetters] = useState([]);
  const [newLetter, setNewLetter] = useState({side:'customer',direction:'outgoing',subject:'',body:'',counterparty:'',letterDate:'',fileUrl:''});
  const [showLetterForm, setShowLetterForm] = useState(false);
  const [uploadingLetter, setUploadingLetter] = useState(false);
  const [showBrigadeForm, setShowBrigadeForm] = useState(false);
  const [newBrigadeContract, setNewBrigadeContract] = useState({projectId:'',projectName:'',brigadeName:'',contractorType:'Своя бригада',contractorId:'',notes:'',pricelistId:''});
  const [newBrigadeItem, setNewBrigadeItem] = useState({name:'',unit:'м',quantity:'',priceSmeta:'',priceBrigade:'',estimateSection:'',workPackage:'Основная',estimateItemKey:''});
  const [brigadeCoef, setBrigadeCoef] = useState('0.6');
  const [supplierCatalog, setSupplierCatalog] = useState([]);
  const [supplyTemplates, setSupplyTemplates] = useState([]);
  const [priceHints, setPriceHints] = useState({});
  const [showCatalogForm, setShowCatalogForm] = useState(false);
  const [newCatalogItem, setNewCatalogItem] = useState({materialName:'',unit:'шт',price:'',minQuantity:'1',deliveryDays:'3',notes:''});
  const [supplierTab, setSupplierTab] = useState('requests');
  const [supplierRequisites, setSupplierRequisites] = useState({companyName:'',inn:'',kpp:'',address:'',bank:'',bik:'',account:'',phone:'',email:'',priceUrl:''});

  // Подтягиваем реквизиты из БД когда поставщик логинится
  useEffect(() => {
    if (user && user.role === 'поставщик' && suppliers && suppliers.length > 0) {
      const my = suppliers.find(s => s.name === user.name || s.email === user.email || s.user_id === user.id);
      if (my) {
        setSupplierRequisites(prev => ({
          ...prev,
          companyName: my.name || prev.companyName || '',
          inn: my.inn || '',
          kpp: my.kpp || '',
          ogrn: my.ogrn || '',
          address: my.legal_address || my.legalAddress || prev.address || '',
          actualAddress: my.actual_address || my.actualAddress || '',
          bank: my.bank || '',
          bik: my.bik || '',
          account: my.account || '',
          korAccount: my.kor_account || my.korAccount || '',
          directorName: my.director_name || my.directorName || '',
          directorPosition: my.director_position || my.directorPosition || '',
          phone: my.phone || prev.phone || '',
          email: my.email || prev.email || '',
          website: my.website || '',
          specialization: my.specialization || '',
          category: my.category || '',
          contractUrl: my.contract_url || my.contractUrl || '',
          contractNumber: my.contract_number || my.contractNumber || '',
          contractDate: String(my.contract_date || my.contractDate || '').slice(0, 10),
          licenseUrl: my.license_url || my.licenseUrl || '',
          priceUrl: my.price_url || my.priceUrl || prev.priceUrl || '',
          notes: my.notes || prev.notes || '',
        }));
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, suppliers]);
  const [materialTransfers, setMaterialTransfers] = useState([]);
  const [showTransferForm, setShowTransferForm] = useState(false);
  const [newTransfer, setNewTransfer] = useState({materialName:'',quantity:'',unit:'шт',workPackage:'',toPerson:'',toPersonRole:'',toUserId:'',fromLocation:'Основной склад',notes:'',transferDate:new Date().toISOString().split('T')[0]});
  const [sverkaModal, setSverkaModal] = useState(null);
  const [showAiChat, setShowAiChat] = useState(false);
  const [showMobileMenu, setShowMobileMenu] = useState(false);
  const [showQuickActions, setShowQuickActions] = useState(false);
  const [systemStatus, setSystemStatus] = useState(null);
  const [systemStatusLoading, setSystemStatusLoading] = useState(false);
  const [showSystemStatus, setShowSystemStatus] = useState(false);
  const [showChatPanel, setShowChatPanelRaw] = useState(false);
  const [companyChatInput, setCompanyChatInput] = useState('');
  const [showScanInvoice, setShowScanInvoice] = useState(false);
  const [showScannedInvoiceForm, setShowScannedInvoiceForm] = useState(false);
  const [showReceiveDialog, setShowReceiveDialog] = useState(false);

  const [scanningInvoice, setScanningInvoice] = useState(false);
  const [projectPayments, setProjectPayments] = useState([]);
  const [accountablePayments, setAccountablePayments] = useState([]);
  const [showAccountableForm, setShowAccountableForm] = useState(false);
  const [newAccountable, setNewAccountable] = useState({givenTo:'',amount:'',paymentMethod:'Наличные',purpose:'',date:''});
  const [reportingPayment, setReportingPayment] = useState(null);
  const [newExpense, setNewExpense] = useState({description:'',amount:'',photoUrl:''});
  const [expenseSubmitting, setExpenseSubmitting] = useState(false);
  const [ownExpenses, setOwnExpenses] = useState([]);
  const [showOwnExpenseForm, setShowOwnExpenseForm] = useState(false);
  const [addExpenseProject, setAddExpenseProject] = useState('');
  const [showBalanceDetails, setShowBalanceDetails] = useState(false);
  const [customRoomTypes, setCustomRoomTypes] = useState(()=>{try{return JSON.parse(localStorage.getItem('customRoomTypes')||'[]');}catch{return [];}});
  const [manualExpenses, setManualExpenses] = useState([]);
  const [newManualExpense, setNewManualExpense] = useState({category:'materials',customCategory:'',projectName:'',amount:'',note:'',date:'',photoUrl:''});
  const [newOwnExpense, setNewOwnExpense] = useState({projectName:'',category:'other',description:'',amount:'',photoUrl:'',date:''});
  const [aiMessages, setAiMessages] = useState([{role:'assistant',content:'Привет! Я ИИ помощник СтройКа. Могу ответить на вопросы по вашим объектам, сметам, складу и финансам. Спрашивайте!'}]);
  const [aiInput, setAiInput] = useState('');
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
  const [aiLoading, setAiLoading] = useState(false);
  const [aiChat, setAiChat] = useState([]);
  const [aiMessage, setAiMessage] = useState('');
  const [directorAgentQuestion, setDirectorAgentQuestion] = useState('');
  const [directorAgentAnswer, setDirectorAgentAnswer] = useState('');
  const [directorAgentSteps, setDirectorAgentSteps] = useState([]);
  const [directorAgentLoading, setDirectorAgentLoading] = useState(false);
  const [directorAgentError, setDirectorAgentError] = useState('');
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
  const [supplyTab, setSupplyTab] = useState('inbox');
  const [showSupplyForm, setShowSupplyForm] = useState(false);
  const [newSupplyReq, setNewSupplyReq] = useState({items:[{materialName:'',quantity:'',unit:'шт',workPackage:''}],project:'',urgency:'обычная',notes:'',category:''});
  const [supplyExpandedId, setSupplyExpandedId] = useState(null);
  const [supplyStockCheck, setSupplyStockCheck] = useState(null);
  const [supplyAiText, setSupplyAiText] = useState('');
  const [supplyAiLoading, setSupplyAiLoading] = useState(false);
  const [supplyRejectId, setSupplyRejectId] = useState(null);
  const [supplyRejectReason, setSupplyRejectReason] = useState('');
  const [supplyCollapsedProjects, setSupplyCollapsedProjects] = useState({});
  // Сн.2: запрос КП у поставщиков
  const [showRequestKpModal, setShowRequestKpModal] = useState(null); // id заявки или null
  const [suggestedSuppliers, setSuggestedSuppliers] = useState(null); // {suppliers:[], aiRecommendedCount}
  const [selectedSupplierIds, setSelectedSupplierIds] = useState([]);
  const [requestKpLoading, setRequestKpLoading] = useState(false);
  // Сн.2: ответ поставщика на RFQ
  const [respondingOfferId, setRespondingOfferId] = useState(null);
  const [newKpResponse, setNewKpResponse] = useState({pricePerUnit:'',deliveryDays:'',paymentTerms:'Постоплата',vatIncluded:true,validUntil:'',supplierMessage:'',pdfUrl:''});
  // Сн.3: AI сравнение КП
  const [compareResultByReq, setCompareResultByReq] = useState({}); // {reqId: {ranking, aiText, bestOfferId, ...}}
  const [compareLoadingReqId, setCompareLoadingReqId] = useState(null);
  // Сн.3: поставщик выставляет счёт
  const [invoicingOfferId, setInvoicingOfferId] = useState(null);
  const [newOfferInvoice, setNewOfferInvoice] = useState({invoiceNumber:'',invoiceDate:new Date().toISOString().split('T')[0],amount:'',vatAmount:'',description:'',fileUrl:''});
  // Сн.4: отгрузка, приемка, качество, претензии
  const [shippingOfferId, setShippingOfferId] = useState(null);
  const [shipmentForm, setShipmentForm] = useState({shippedQuantity:'',waybillNumber:'',waybillDate:new Date().toISOString().split('T')[0],vehicleNumber:'',driverName:'',documentUrl:'',photoUrl:''});
  const [receivingDeliveryId, setReceivingDeliveryId] = useState(null);
  const [receiveForm, setReceiveForm] = useState({receivedQuantity:'',qualityStatus:'Принято',qualityNotes:'',photoUrl:'',claimDescription:''});
  const [deliveryAiResultById, setDeliveryAiResultById] = useState({});
  const [deliveryAiLoadingId, setDeliveryAiLoadingId] = useState(null);
  // Регистрация поставщика по ссылке
  const [showSupplierInviteModal, setShowSupplierInviteModal] = useState(false);
  const [supplierInviteForm, setSupplierInviteForm] = useState({presetName:'',presetCategory:'Сыпучие и бетон',supplierId:null,expiresInDays:14});
  const [generatedInviteLink, setGeneratedInviteLink] = useState(null);
  const [personnelTab, setPersonnelTab] = useState('staff');
  const [warehouseTab, setWarehouseTab] = useState('objects');
  const [selectedWarehouseProject, setSelectedWarehouseProject] = useState(null);
  const [toolsTab, setToolsTab] = useState('list');
  const [estimatesTab, setEstimatesTab] = useState('list');
  const [materialNorms, setMaterialNorms] = useState([]);
  const [materialsPage, setMaterialsPage] = useState({projectName:'', search:'', hasMore:false, loading:false, error:''});
  const [materialNormSearch, setMaterialNormSearch] = useState('');
  const [materialNormsPage, setMaterialNormsPage] = useState({search:'', hasMore:false, loading:false, error:''});
  const [workJournalPage, setWorkJournalPage] = useState({projectName:'', search:'', dateFrom:'', dateTo:'', hasMore:false, loading:false, error:''});
  const [materialAliases, setMaterialAliases] = useState([]);
  const [materialNormOverrides, setMaterialNormOverrides] = useState([]);
  const [materialNormSuggestions, setMaterialNormSuggestions] = useState([]);
  const [materialNormPreviewSuggestions, setMaterialNormPreviewSuggestions] = useState([]);
  const [materialNormNotice, setMaterialNormNotice] = useState(null);
  const [materialNormSuggestionLoading, setMaterialNormSuggestionLoading] = useState(false);
  const [materialNormCoverageProject, setMaterialNormCoverageProject] = useState('');
  const [newMaterialNorm, setNewMaterialNorm] = useState(EMPTY_MATERIAL_NORM_FORM);
  const [editingMaterialNormId, setEditingMaterialNormId] = useState(null);
  const [estimateSearch, setEstimateSearch] = useState('');
  const [estimateProjectFilter, setEstimateProjectFilter] = useState('');
  const [showArchivedEstimates, setShowArchivedEstimates] = useState(false);
  const [listSearch, setListSearch] = useState('');
  const [expandedActDate, setExpandedActDate] = useState(null);
  const [showReimburseModal, setShowReimburseModal] = useState(false);
  const [salaryMonth, setSalaryMonth] = useState(new Date().toISOString().slice(0,7));
  // Inline-правки премий/удержаний по сотруднику в месяце (хранится в localStorage)
  const [salaryEdits, setSalaryEdits] = useState(() => readStoredJson('salaryEdits', {}));
  const [payrollExtras, setPayrollExtras] = useState(() => readStoredJson('payrollExtras', {}));
  // Универсальная проверка вхождения подстроки во все указанные поля
  const matchSearch = (q, ...fields) => matchSearchFields(q, ...fields);
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
  const [issueToolData, setIssueToolData] = useState({masterName:'',project:'',issueType:'Временно'});
  const [returnToolCondition, setReturnToolCondition] = useState('Исправен');
  const [newPayment, setNewPayment] = useState({amount:'',paymentType:'Наличный расчёт',paidBy:'',date:'',notes:''});
  const [newPiecework, setNewPiecework] = useState({staffId:'',description:'',unit:'м2',quantity:'',pricePerUnit:'',project:''});
  const [newProject, setNewProject] = useState({name:'',client:'',status:'Планирование',budget:'',deadline:'',progress:0,tasks:[],pricelistId:null});
  const [newClient, setNewClient] = useState({name:'',phone:'',email:'',status:'Активный',notes:''});
  const [newWarehouse, setNewWarehouse] = useState({name:'',city:'',address:'',notes:''});
  const [newMovement, setNewMovement] = useState({materialName:'',fromLocation:'Основной склад',toLocation:'',quantity:'',unit:'шт',notes:'',selectedMaterials:[]});
  const [newInvoice, setNewInvoice] = useState({number:'',date:'',supplierId:'',isNewSupplier:false,newSupplierName:'',acceptedBy:'',location:'Основной склад',project:'',vat:'Без НДС',photos:[],items:[{name:'',quantity:'',unit:'шт',price:'',category:'',workPackage:''}]});
  const [newStaff, setNewStaff] = useState(emptyStaffForm());
  const [staffExpandedSections, setStaffExpandedSections] = useState({access:false,docs:false,finance:false,extra:false});
  const [expandedStaffId, setExpandedStaffId] = useState(null);
  const [staffProfile, setStaffProfile] = useState(null);
  const [staffProfileLoading, setStaffProfileLoading] = useState(false);
  const [newStaffDoc, setNewStaffDoc] = useState({docType:'другое',title:'',fileUrl:'',signedAt:'',expiresAt:'',notes:''});
  const [showStaffDocForm, setShowStaffDocForm] = useState(false);

  const [newUser, setNewUser] = useState({name:'',email:'',password:'',role:'прораб',projectId:'',projectName:'',assignedProjects:[],assignedPackages:[],active:true});
  const [newPricelist, setNewPricelist] = useState({name:'',description:'',forWho:'',coefficient:1.0});
  const [newPlItem, setNewPlItem] = useState({name:'',unit:'м2',price:'',category:''});
  const [newInviteRole, setNewInviteRole] = useState('мастер');
  const [newSupplier, setNewSupplier] = useState({name:'',phone:'',email:'',specialization:'',category:'Сыпучие и бетон',rating:5.0,status:'Активный'});
  const [newRequest, setNewRequest] = useState({items:[{materialName:'',quantity:'',unit:'шт',workPackage:''}],project:'',notes:'',selectedSuppliers:[],category:''});
  const [newOffer, setNewOffer] = useState({supplierId:'',pricePerUnit:'',deliveryDays:'',notes:''});
  const [newContract, setNewContract] = useState({masterId:'',masterName:'',contractType:'ГПХ',contractNumber:'',project:'',startDate:'',endDate:''});
  const [newAct, setNewAct] = useState({masterId:'',masterName:'',project:'',workPackage:'',periodStart:'',periodEnd:''});
  const [newTool, setNewTool] = useState({name:'',inventoryNumber:'',cost:'',status:'На складе',location:'Основной склад',project:'',masterId:'',masterName:'',issueType:'',notes:''});
  const [newRoom, setNewRoom] = useState({project:'',name:'',floorArea:'',wallArea:'',ceilingArea:'',height:'',ceilingType:'Простой',wallMaterial:'Штукатурка',floorMaterial:'Стяжка',photoUrl:'',notes:''});
  const [draftRoomWindows, setDraftRoomWindows] = useState([]);
  const [draftRoomDoors, setDraftRoomDoors] = useState([]);
  const [newWindow, setNewWindow] = useState({roomId:'',name:'Окно 1',width:'',height:'',windowType:'ПВХ',revealDepth:'',revealMaterial:'Штукатурка'});
  const [newDoor, setNewDoor] = useState({roomId:'',name:'Дверь 1',width:'',height:'',doorType:'Деревянная',doorPurpose:'Межкомнатная',revealDepth:'',revealMaterial:'Штукатурка'});
  const [newInventory, setNewInventory] = useState({project:'',date:'',notes:''});
  const [newWeather, setNewWeather] = useState({projectName:'',date:'',temperature:'',condition:'Ясно',windSpeed:'',notes:''});
  const [newEstimate, setNewEstimate] = useState({projectId:'',projectName:'',name:'',version:'1.0',smetaType:'Заказчик',workPackage:'Основная',status:'Активная',templateId:''});
  const [showVersionHistory, setShowVersionHistory] = useState(false);
  const [estimateVersions, setEstimateVersions] = useState([]);
  const [selectedVersionsToCompare, setSelectedVersionsToCompare] = useState([]);
  const [importValidationWarnings, setImportValidationWarnings] = useState([]);
  const [importValidating, setImportValidating] = useState(false);
  const [estimateIssueFocusKey, setEstimateIssueFocusKey] = useState('');
  const [showEstimateIssuesOnly, setShowEstimateIssuesOnly] = useState(false);
  const [showEstimateWorkSummary, setShowEstimateWorkSummary] = useState(false);
  const [executionPriceFillPercent, setExecutionPriceFillPercent] = useState(50);
  const selectedEstimateExecutionFillPercent = estimateExecutionFillPercentOf(selectedEstimate);
  useEffect(() => {
    if (!selectedEstimate?.id || !selectedEstimateExecutionFillPercent) return;
    setExecutionPriceFillPercent(prev => String(prev) === selectedEstimateExecutionFillPercent ? prev : selectedEstimateExecutionFillPercent);
  }, [selectedEstimate?.id, selectedEstimateExecutionFillPercent]);
  const [showEstimateChat, setShowEstimateChat] = useState(false);
  const [estimateChatMessages, setEstimateChatMessages] = useState([]);
  const [estimateChatInput, setEstimateChatInput] = useState('');
  const [estimateChatLoading, setEstimateChatLoading] = useState(false);
  const [showGenerateEstimate, setShowGenerateEstimate] = useState(false);
  const [generateForm, setGenerateForm] = useState({description:'',projectId:'',projectName:'',pricelistId:'',area:'',name:'',version:'1.0',smetaType:'Заказчик',workPackage:'Основная',status:'Активная'});
  const [generating, setGenerating] = useState(false);
  const [showGeneratePricelist, setShowGeneratePricelist] = useState(false);
  const [generatePricelistForm, setGeneratePricelistForm] = useState({description:'',name:'',forWho:'',coefficient:1.0});
  const [generatingPricelist, setGeneratingPricelist] = useState(false);
  const [showFromEstimate, setShowFromEstimate] = useState(false);
  const [fromEstimateForm, setFromEstimateForm] = useState({estimateId:'',name:'',forWho:'',coefficient:1.0});
  const [creatingFromEstimate, setCreatingFromEstimate] = useState(false);
  const [showDistribute, setShowDistribute] = useState(false);
  const [showWorkAssignment, setShowWorkAssignment] = useState(false);
  const [distributeAssignments, setDistributeAssignments] = useState({});
  const [distributeBrigades, setDistributeBrigades] = useState([]);
  const [newDistributeBrigade, setNewDistributeBrigade] = useState({brigadeName:'',contractorType:'Своя бригада',contractorId:'',pricelistId:''});
  const [distributing, setDistributing] = useState(false);

  const persistEstimate = async (est) => {
    if (!est || !est.id) return;
    try {
      const res = await fetch(API+'/estimates/'+est.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(est)});
      if (res.ok) {
        const nextEstimates = estimateListWithUpdatedEstimate(est);
        await queueEstimateQualityReviewTask(est, 'Смета сохранена');
        await queueEstimateNormReviewTask(est, 'Смета сохранена', nextEstimates);
      }
    } catch(e) {}
  };

  const [newEstimateSection, setNewEstimateSection] = useState({name:''});
  const [newEstimateItem, setNewEstimateItem] = useState({sectionId:'',itemType:'work',name:'',unit:'м2',quantity:'',priceWork:'',priceMaterial:'',measurementBasis:''});
  const [newStage, setNewStage] = useState({name:'',status:'Не начат',startDate:'',endDate:'',progress:0,responsible:'',notes:''});
  const [newChecklist, setNewChecklist] = useState({name:'',template:''});
  const [newChecklistItem, setNewChecklistItem] = useState('');
  const [newPrescription, setNewPrescription] = useState({number:'',violation:'',deadline:'',responsible:'',photoUrl:''});
  const [newUnexpected, setNewUnexpected] = useState(EMPTY_ESTIMATE_CHANGE);
  const [newCompanyDoc, setNewCompanyDoc] = useState({name:'',docType:'Устав',fileUrl:'',expiresAt:''});
  const [companyReqForm, setCompanyReqForm] = useState({fullName:'',shortName:'',inn:'',kpp:'',ogrn:'',legalAddress:'',actualAddress:'',phone:'',email:'',directorName:'',directorPosition:'Генеральный директор',basis:'Устава',bankName:'',bik:'',rs:'',ks:''});
  const [profileData, setProfileData] = useState({fullName:'',passport:'',inn:'',contractType:'ГПХ',bankAccount:'',bankName:'',phone:'',specialization:'',ogrnip:''});
  const [newLead, setNewLead] = useState({name:'',phone:'',email:'',source:'',budget:'',notes:'',stage:'Новый',photoUrl:'',contractSubject:''});
  const [newTbEntry, setNewTbEntry] = useState({project:'',type:'Вводный инструктаж',participants:[],date:'',program:'',instructionText:'',aiLoading:false});
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

  useEffect(() => {
    const handleOutside = (e) => {
      const target = e.target;
      if (target && typeof target.closest === 'function' && target.closest('[data-notification-root="1"]')) return;
      setShowNotifications(false);
    };
    const handleKey = (e) => { if (e.key === 'Escape') setShowNotifications(false); };
    document.addEventListener('pointerdown', handleOutside);
    document.addEventListener('touchstart', handleOutside, {passive:true});
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('pointerdown', handleOutside);
      document.removeEventListener('touchstart', handleOutside);
      document.removeEventListener('keydown', handleKey);
    };
  }, []);

  useEffect(() => {
    if (user) {
      mobileLoadedScopesRef.current.clear();
      mobileApiRequestsRef.current.clear();
      if (isMobile) loadMobileInitial();
      else refreshData();
      if (['мастер','субподрядчик','бригадир'].includes(user.role)) { loadMasterProfile(); setActivePage('works'); }
      const saved = localStorage.getItem('companyName'); if (saved) setCompanyName(saved);
      const keys = ['masterRatings','activityLog','notifications','tbJournal','geoCheckins','signedDocs','actPayments','weatherLog'];
      const setters = [setMasterRatings,setActivityLog,setNotifications,setTbJournal,setGeoCheckins,setSignedDocs,setActPayments,setWeatherLog];
      keys.forEach((k,i) => { const v=localStorage.getItem(k); if(v) setters[i](JSON.parse(v)); });
      requestPushPermission().then(granted => setPushEnabled(granted));
      const pingOnline = async () => {
        try {
          await fetch(API+'/online',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({userId:user.id,userName:user.name,userRole:user.role,lastSeen:new Date().toISOString()})});
        } catch(e){}
      };
      pingOnline();
      const pingInterval = setInterval(pingOnline, 30000);
      return ()=>clearInterval(pingInterval);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

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

  // Счётчик непрочитанных сообщений чата для текущего пользователя
  const unreadMessagesCount = (companyMessages||[]).filter(m=>{
    const rb = m.readBy||[];
    return user && !rb.includes(user.id) && (m.author_id!==user.id);
  }).length;

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

  const { appendPhotos, uploadPhoto } = createUploadActions({
    API,
    activePage,
    activeProjectTab,
    expandedProject,
    masterProjectId,
    projects,
  });

  const fileSrc = createFileSrc(API);

  const { checkinGeo } = createGeoActions({
    geoCheckins,
    setGeoCheckins,
    user,
  });

  const getRoomNetWall = (room) => calcRoomNetWall(room, roomWindows, roomDoors);
  const roomCompleteness = (room) => calcRoomCompleteness(room, roomWindows, roomDoors, C);
  const roomMeasurementCheck = (projectName, roomId, surface, quantity, unit, description='') => {
    return buildRoomMeasurementCheck({
      projectName,
      roomId,
      surface,
      quantity,
      unit,
      description,
      rooms,
      roomWindows,
      roomDoors,
      roomWorks,
      materialNameKey,
    });
  };
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

  // Авто-проверка при изменении кода (debounce 400 мс)
  useEffect(() => {
    if (!regCode) { setRegInviteInfo(null); return; }
    const t = setTimeout(()=>{ checkInviteCode(regCode); }, 400);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [regCode]);

  const canAccess = (p) => canAccessRole(user, p, ROLES);
  const isFinanceRole = () => isFinanceUser(user);
  const visibleProjects = (list) => visibleProjectsForUser(list, user);
  const visibleEstimatesForCurrentUser = (list) => visibleEstimatesForUser(list, user);
  const selectableActiveProjects = (list=projects) => selectableActiveProjectsForUser(list||[], user);
  const visibleActiveProjects = (list=projects) => selectableActiveProjects(list||[]);
  useEffect(() => {
    if(!user||!['мастер','субподрядчик','бригадир'].includes(user.role)) return;
    const options = selectableActiveProjects(projects);
    const currentOk = masterProjectId&&options.some(p=>String(p.id)===String(masterProjectId));
    if(currentOk) return;
    if(masterProjectId&&!currentOk){
      setMasterProjectId('');
      setSelectedWorks({});
      setPricelistItems([]);
    }
    if(options.length===1){
      const project = options[0];
      setMasterProjectId(String(project.id));
      setSelectedWorks({});
      if(project.pricelistId) loadPricelistItems(project.pricelistId);
      else setPricelistItems([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.role, user?.assignedProjects, user?.assigned_projects, projects, masterProjectId]);
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

  // Расчёт прогресса и сумм по факту сметы (используется в дашборде, кабинетах технадзора и заказчика, карточке объекта)
  const nextEstimateVersionFor = (draft, sourceEstimates=estimatesList) => {
    return nextEstimateVersionForFromList(draft, sourceEstimates);
  };
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
  const activeEstimatesForProject = (p, kind='Заказчик', sourceEstimates=null) => {
    const groups = {};
    visibleEstimatesForCurrentUser(sourceEstimates||estimatesList||[]).filter(e=>
      (e.projectName===p.name||Number(e.projectId)===Number(p.id)) &&
      estimateKind(e)===kind &&
      e.status==='Активная' &&
      !isArchivedEstimate(e)
    ).forEach(e=>{
      const k = estimatePackage(e);
      if(!groups[k]) groups[k] = [];
      groups[k].push(e);
    });
    return Object.values(groups)
      .map(items=>activeEstimateFromList(items))
      .filter(Boolean);
  };
  const renderEstimateReconciliationsPanel = (p) => {
    const recs = estimateReconciliationsForProject(p.name);
    const projectEstimates = visibleEstimatesForCurrentUser(estimatesList)
      .filter(e=>e.projectName===p.name && estimateKind(e)==='Заказчик' && !isArchivedEstimate(e) && !isGlobalEstimateTemplate(e));
    return (
      <EstimateReconciliationsPanel
        project={p}
        reconciliations={recs}
        projectEstimates={projectEstimates}
        estimateDiffBaseFor={estimateDiffBaseFor}
        estimatePackage={estimatePackage}
        estimateTotal={estimateTotal}
        estimateUpdatedTs={estimateUpdatedTs}
        canApprove={isLeadership()}
        onApprove={approveEstimateReconciliation}
        onCreate={createEstimateReconciliation}
        onOpenPreview={openEstimateReconciliationPreview}
      />
    );
  };
  const getProjectWorkPackageOptions = (projectName='') => {
    const project = (projects||[]).find(p=>p.name===projectName);
    const activePackages = project
      ? activeEstimatesForProject(project, 'Заказчик').map(estimatePackage).filter(Boolean)
      : [];
    const fallback = ESTIMATE_PACKAGES.filter(Boolean);
    return [...new Set((activePackages.length ? activePackages : fallback).filter(Boolean))];
  };
  const getProjectEstimateWorkOptions = (projectName='', workPackage='') => {
    const project = (projects||[]).find(p=>p.name===projectName);
    if (!project) return [];
    const packageFilter = String(workPackage || '').trim();
    const seen = new Set();
    const out = [];
    activeEstimatesForProject(project, 'Заказчик')
      .filter(est => !packageFilter || estimatePackage(est) === packageFilter)
      .forEach(est => {
        const pkg = estimatePackage(est);
        _sectionsOfEst(est).forEach((section, sectionIdx) => {
          const sectionName = section?.name || '';
          (section?.items || []).forEach((item, itemIdx) => {
            if (normalizeEstimateItemType(item, sectionName) !== 'work') return;
            const key = item.workKey || estimateWorkKeyForItem(item, sectionName, itemIdx);
            const value = [est.id, sectionIdx, itemIdx, key].join(':');
            if (seen.has(value)) return;
            seen.add(value);
            out.push({
              value,
              estimateId: est.id,
              estimateName: est.name,
              estimateItemKey: key,
              parentWorkKey: key,
              parentWorkName: item.workName || item.name || '',
              parentWorkSourceCode: item.workSourceCode || item.sourceCode || item.obosn || '',
              sectionName,
              workPackage: pkg,
              label: (item.workName || item.name || '').slice(0, 140),
            });
          });
        });
      });
    return out;
  };
  const projectMeasurementBasisTotals = (projectName) => projectMeasurementBasisTotalsFor(projectName, {rooms, roomWindows, roomDoors});
  const estimateMeasurementComparisonSummary = (project) => estimateMeasurementComparisonSummaryFor(project, {
    totals: projectMeasurementBasisTotals(project?.name || ''),
    activeEstimates: project ? activeEstimatesForProject(project, 'Заказчик') : [],
  });
  const buildEstimateMeasurementComparisonContent = (project) => buildEstimateMeasurementComparisonDocContent(
    project,
    estimateMeasurementComparisonSummary(project),
    projectMeasurementBasisTotals(project?.name||''),
    {generatedBy:user?.name||''}
  );
  const renderEstimateMeasurementComparisonPanel = (project) => {
    return (
      <EstimateMeasurementComparisonPanel
        project={project}
        summary={estimateMeasurementComparisonSummary(project)}
        totals={projectMeasurementBasisTotals(project?.name||'')}
        estimateChangeForComparisonRow={estimateChangeForComparisonRow}
        onCreateEstimateChange={createEstimateChangeFromComparisonRow}
        onOpenChangesTab={() => {setActiveProjectTab('Изменения к смете');setActiveTabGroup('work');}}
        onPrint={() => showPreview(buildEstimateMeasurementComparisonContent(project),'Смета ↔ обмеры — '+project.name)}
      />
    );
  };
  const workJournalEstimateSummary = (project) => workJournalEstimateSummaryFor(project, {
    activeEstimates: project ? activeEstimatesForProject(project, 'Заказчик') : [],
    workJournal,
    planDone: projectPlanDone(project||{}),
  });
  const buildWorkJournalEstimateReconciliationContent = (project) => buildWorkJournalEstimateReconciliationDocContent(
    project,
    workJournalEstimateSummary(project),
    {generatedBy:user?.name||'', statusMeta:workJournalEstimateStatusMeta}
  );
  const renderWorkJournalEstimateReconciliationPanel = (project) => {
    return (
      <WorkJournalEstimateReconciliationPanel
        project={project}
        summary={workJournalEstimateSummary(project)}
        onPrint={() => showPreview(buildWorkJournalEstimateReconciliationContent(project),'Сверка ЖПР ↔ смета — '+project.name)}
      />
    );
  };
  const projectPlanDone = (p) => projectPlanDoneFor(activeEstimatesForProject(p, 'Заказчик'));
  // Выполненные позиции сметы для КС-2/КС-3.
  // Если по смете уже есть ЖПР, в КС попадают только подтвержденные записи,
  // а цена берется из сметы заказчика. Это не дает вывести в КС объемы "На проверке".
  const ks2ItemsFromEstimate = (p) => ks2ItemsFromActiveEstimates({
    project: p,
    activeEstimates: activeEstimatesForProject(p, 'Заказчик'),
    workJournal,
  });
  const estimateItemOptionsForProject = (p) => estimateItemOptionsFromActiveEstimates(activeEstimatesForProject(p, 'Заказчик'));
  const includableEstimateChanges = (projectName) => includableEstimateChangesForProject(projectName, unexpectedWorksList);
  const estimateChangesForNewEstimate = (project, est) => estimateChangesForNewEstimateFromList({
    project,
    estimate: est,
    unexpectedWorksList,
    activeCustomerEstimates: project ? activeEstimatesForProject(project, 'Заказчик') : [],
  });
  const estimateChangeRowsForDocs = (projectName, kind) => estimateChangeRowsForDocsFromList(projectName, kind, unexpectedWorksList);
  // Фактически освоено по проекту: журнал работ + наряды бригадные (по приёмке) + материалы на объекте
  const projectFactSpent = (p) => projectFactSpentValue({
    project: p,
    workJournal,
    allBrigadeItems,
    materials,
  });
  const warehouseInvoiceItems = (inv) => buildWarehouseInvoiceItems(inv, {
    materials,
    warehouseMain,
    materialInspections,
    history,
  });
  const isSupplyDeliveryInvoice = (inv) => !!(inv?.supplyDeliveryId || inv?.sourceType==='supply_delivery');
  const materialNameLookupKey = materialLookupText;
  const materialAliasFor = (projectName, aliasName) => {
    const key = materialNameLookupKey(aliasName);
    if (!key) return null;
    const active = (materialAliases||[]).filter(a=>a&&a.active!==false&&materialNameLookupKey(a.aliasName)===key);
    return active.find(a=>(a.projectName||'')===projectName) || active.find(a=>!(a.projectName||'')) || null;
  };
  const canonicalMaterialMeta = (projectName, name, unit='') => {
    const alias = materialAliasFor(projectName, name);
    return {
      name: alias?.canonicalName || name || '',
      unit: alias?.canonicalUnit || unit || '',
      alias,
    };
  };
  const estimateMaterialPlanRows = (projectName) => buildEstimateMaterialPlanRows({
    projectName,
    projects,
    activeEstimatesForProject,
    materialNameLookupKey,
  });
  const materialAliasCandidates = (projectName, row) => buildMaterialAliasCandidates({
    projectName,
    row,
    estimateMaterialPlanRows,
    materialNameLookupKey,
  });
  const materialReconciliationRows = (projectName, workPackage='') => buildMaterialReconciliationRows({
    projectName,
    workPackage,
    projects,
    invoices,
    supplyDeliveries,
    supplyHistory,
    warehouseMovements,
    materialTransfers,
    workJournal,
    history,
    materials,
    supplyRequests,
    activeEstimatesForProject,
    canonicalMaterialMeta,
    warehouseInvoiceItems,
    isSupplyDeliveryInvoice,
    estimateWorkNormRequirementRows,
    parseSupplyItems,
    materialNameLookupKey,
  });
  const materialControlSummaryForProject = (projectName) => buildMaterialControlSummary(materialReconciliationRows(projectName));
  const warehouseInvoiceEstimateControl = (inv) => buildWarehouseInvoiceEstimateControl({
    inv,
    warehouseInvoiceItems,
    materialControlSummaryForProject,
    canonicalMaterialMeta,
    materialNameLookupKey,
  });
  const materialNameKey = materialNameLookupKey;
  const isPersonalMaterialRole = () => ['мастер','субподрядчик','бригадир'].includes(user?.role);
  const parseJournalMaterials = (value) => parseJournalMaterialsValue(value);
  const materialNormDeviationRows = (projectName, workPackage='') => buildMaterialNormDeviationRows({
    projectName,
    workPackage,
    workJournal,
    parseJournalMaterials,
    materialNameKey,
  });
  const materialNormControlSummaryForProject = (projectName, workPackage='') =>
    buildMaterialNormControlSummary(materialNormDeviationRows(projectName, workPackage));
  const personalMaterialRowsForProject = (projectName, personName=user?.name, personId=user?.id, workPackage='') =>
    buildPersonalMaterialRowsForProject({
      projectName,
      personName,
      personId,
      workPackage,
      materialTransfers,
      workJournal,
      history,
      canonicalMaterialMeta,
      parseJournalMaterials,
      materialNameKey,
    });
  const materialRowsAvailableForWork = (projectName, workPackage='') => {
    if (isPersonalMaterialRole()) return personalMaterialRowsForProject(projectName, user?.name, user?.id, workPackage).filter(r=>toNum(r.quantity)>0);
    return (materials||[]).filter(m=>m.project===projectName&&toNum(m.quantity)>0&&packageMatches(m.workPackage || m.work_package, workPackage));
  };
  const materialAvailabilityMapForWork = (projectName, workPackage='') => buildMaterialAvailabilityMap({
    rows: materialRowsAvailableForWork(projectName, workPackage),
    projectName,
    canonicalMaterialMeta,
    materialNameKey,
  });
  const materialHintForProject = (projectName, materialName, workPackage='') => {
    const meta = canonicalMaterialMeta(projectName, materialName);
    const key = materialNameKey(meta.name);
    if (!key) return null;
    return materialReconciliationRows(projectName, workPackage).find(r=>materialNameKey(r.name)===key) || null;
  };
  const materialSuggestionsForWork = (projectName, workName, sectionName='', workPackage='') => buildMaterialSuggestionsForWork({
    projectName,
    workName,
    sectionName,
    workPackage,
    materialReconciliationRows,
    materialNameKey,
  });
  const workNormRulesFor = (workName, sectionName='', projectName='', estimateId=null) => {
    return workNormRulesForCalculation({
      workName,
      sectionName,
      projectName,
      estimateId,
      materialNorms,
      materialNormOverrides,
      baseRules: WORK_MATERIAL_NORM_RULES,
    });
  };
  const workNeedsThicknessParam = (workName, sectionName='') =>
    workNormRulesFor(workName, sectionName).some(r=>r.thicknessBaseMm);
  const materialNormForWork = (projectName, workName, sectionName, workQty, workUnit, material, params={}) => {
    return calculateMaterialNormForWork({
      projectName,
      workName,
      sectionName,
      workQty,
      workUnit,
      material,
      params,
      materialNorms,
      materialNormOverrides,
      baseRules: WORK_MATERIAL_NORM_RULES,
    });
  };
  const normRequirementsForWork = (workName, sectionName, workQty, workUnit, params={}) => {
    return calculateNormRequirementsForWork({
      workName,
      sectionName,
      workQty,
      workUnit,
      params,
      materialNorms,
      materialNormOverrides,
      baseRules: WORK_MATERIAL_NORM_RULES,
    });
  };
  const estimateWorkNormRequirementRows = (projectName, workPackage='') => buildEstimateWorkNormRequirementRows({
    projectName,
    workPackage,
    projects,
    activeEstimatesForProject,
    normRequirementsForWork,
    materialNameKey,
  });
  const estimateNormCoverageRows = (projectName, sourceEstimates=null) => buildEstimateNormCoverageRows({
    projectName,
    sourceEstimates,
    projects,
    activeEstimatesForProject,
    workNormRulesFor,
    normRequirementsForWork,
    materialNameKey,
  });
  const buildMaterialNormCoverageContent = (projectName) => buildMaterialNormCoverageDocContent(
    projectName,
    projectName ? estimateNormCoverageRows(projectName) : [],
    {companyRequisites, companyName, materialTitleForNormRule, materialNormCoverageComment}
  );
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
  const isLeadership = () => isLeadershipUser(user);
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
  const isDirector = () => (user ? user.role : '') === 'директор';
  const canUseDirectorAgent = () => ['директор','system_owner'].includes(user?user.role:'');
  const isProrab = () => isProrabUser(user);
  const isMasterRole = () => ['мастер','субподрядчик','бригадир'].includes(user?user.role:'');
  const roleColor = (r) => roleColorForRole(r);
  const workedDays = (id) => workedDaysForStaff(id, timesheet, daysInMonth);
  const calcSalary = (s) => calcStaffSalary(s, timesheet, piecework, daysInMonth);
  const projectPaymentSignedAmount = (pay) => projectPaymentSignedAmountValue(pay);
  const projectPaymentInAmount = (pay) => projectPaymentIncomingAmount(pay);
  const formatSignedRub = (amount) => formatSignedRubValue(amount);
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
  const lowStock = materials.filter(m=>m.minQuantity&&m.quantity<m.minQuantity);
  const lowMainStock = warehouseMain.filter(m=>m.minQuantity&&m.quantity<m.minQuantity);
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

  const navigateTo = (p) => {
    if (canAccess(p)) {
      setActivePage(p); setShowForm(false); setExpandedProject(null);
      setExpandedClient(null); setEditingItem(null); setEditingPlItem(null);
      setShowPiecework(false); setSelectedPricelist(null); setPricelistItems([]);
      setShowInvites(false); setShowOffers(null);
      setShowSearch(false); setGlobalSearch(''); setShowArchive(false);
      setSelectedInventory(null); setSidebarVisible(false);
      setSelectedWarehouseProject(null); setInlineEditPl(null); setShowRoomForm(false);
    }
  };

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

  const searchTerm = globalSearch.trim().toLowerCase();
  const searchResults = (!isMobile && searchTerm.length>=2) ? [
    ...projects.filter(p=>String(p.name||'').toLowerCase().includes(searchTerm)).map(p=>({icon:'📋',title:p.name,subtitle:p.client,page:'projects'})),
    ...clients.filter(c=>String(c.name||'').toLowerCase().includes(searchTerm)).map(c=>({icon:'👥',title:c.name,subtitle:c.phone,page:'clients'})),
    ...materials.filter(m=>String(m.name||'').toLowerCase().includes(searchTerm)).map(m=>({icon:'📦',title:m.name,subtitle:m.quantity+' '+m.unit,page:'warehouse'})),
    ...tools.filter(t=>String(t.name||'').toLowerCase().includes(searchTerm)).map(t=>({icon:'🔧',title:t.name,subtitle:t.status,page:'warehouse'})),
  ].slice(0,8) : [];

  const pageFallback = <AppPageFallback C={C} card={card} isMobile={isMobile} />;

  const financeUsers = users.filter(u=>['директор','зам_директора','бухгалтер'].includes(u.role));
  if (isMasterRole()) {
    return (
      <React.Suspense fallback={pageFallback}>
      <MasterCabinetPage
        API={API}
        C={C}
        EXPENSE_CATEGORIES={EXPENSE_CATEGORIES}
        PD_CONSENT_TEXT={PD_CONSENT_TEXT}
        ROLE_LABELS={ROLE_LABELS}
        SURFACES={SURFACES}
        UNITS={UNITS}
        accountablePayments={accountablePayments}
        activePage={activePage}
        addMasterWorks={addMasterWorks}
        appendPhotos={appendPhotos}
        applySupplyTemplate={applySupplyTemplate}
        autoFillNormMaterialsForWork={autoFillNormMaterialsForWork}
        badge={badge}
        brigadeContracts={brigadeContracts}
        brigadeContractItems={allBrigadeItems}
        buildActContent={buildActContent}
        buildCableJournalContent={buildCableJournalContent}
        buildContractContent={buildContractContent}
        buildHiddenActContent={buildHiddenActContent}
        btnB={btnB}
        btnG={btnG}
        btnGr={btnGr}
        btnO={btnO}
        btnR={btnR}
        cableJournal={cableJournal}
        cableTypeOf={cableTypeOf}
        card={card}
        checkinGeo={checkinGeo}
        closeNotifications={closeNotifications}
        companyChatMessage={companyChatMessage}
        companyMessages={companyMessages}
        consentChecked={consentChecked}
        confirmMaterialReceipt={confirmMaterialReceipt}
        contracts={contracts}
        createSupplyReq={createSupplyReq}
        deleteSupplyTemplate={deleteSupplyTemplate}
        doPrint={doPrint}
        estimateDoneDrafts={estimateDoneDrafts}
        estimateItemDoneTotal={estimateItemDoneTotal}
        estimateWorkKey={estimateWorkKey}
        estimateWorkMaterials={estimateWorkMaterials}
        estimateWorkParams={estimateWorkParams}
        estimatesList={estimatesList}
        expandedProject={expandedProject}
        fetchPriceHint={fetchPriceHint}
        fileSrc={fileSrc}
        fmtMeasure={fmtMeasure}
        getNotifPage={getNotifPage}
        handleLogout={handleLogout}
        hiddenActs={hiddenActs}
        inp={inp}
        interimActs={interimActs}
        isMobile={isMobile}
        isPersonalMaterialRole={isPersonalMaterialRole}
        listSearch={listSearch}
        loadAll={loadAll}
        loadPricelistItems={loadPricelistItems}
        markMyNotificationsRead={markMyNotificationsRead}
        masterProfile={masterProfile}
        masterProfiles={masterProfiles}
        masterProjectId={masterProjectId}
        matchSearch={matchSearch}
        materialAvailabilityMapForWork={materialAvailabilityMapForWork}
        materialControlStatus={materialControlStatus}
        materialHintForProject={materialHintForProject}
        materialNameKey={materialNameKey}
        materialNormForWork={materialNormForWork}
        materialNormStatus={materialNormStatus}
        materialRowsAvailableForWork={materialRowsAvailableForWork}
        materialSuggestionsForWork={materialSuggestionsForWork}
        materialTransfers={materialTransfers}
        myNotifications={myNotifications}
        navigateTo={navigateTo}
        newOwnExpense={newOwnExpense}
        newSupplyReq={newSupplyReq}
        normalizeMeasure={normalizeMeasure}
        notifications={notifications}
        notify={notify}
        ownExpenses={ownExpenses}
        parseSupplyItems={parseSupplyItems}
        pdConsents={pdConsents}
        personalMaterialRowsForProject={personalMaterialRowsForProject}
        piecework={piecework}
        previewContent={previewContent}
        previewTitle={previewTitle}
        priceHints={priceHints}
        pricelistItems={pricelistItems}
        pricelists={pricelists}
        profileData={profileData}
        projects={projects}
        refreshData={refreshData}
        removeEstimateWorkMaterial={removeEstimateWorkMaterial}
        removeSelectedWorkMaterial={removeSelectedWorkMaterial}
        renderMaterialWriteoffStatus={renderMaterialWriteoffStatus}
        renderSupplyPlanningHint={renderSupplyPlanningHint}
        renderSupplyRequestOrigin={renderSupplyRequestOrigin}
        returnMaterialToProject={returnMaterialToProject}
        roleColor={roleColor}
        roomMeasurementCheck={roomMeasurementCheck}
        roomMeasurementMessage={roomMeasurementMessage}
        rooms={rooms}
        saveProfile={saveProfile}
        saveSupplyTemplate={saveSupplyTemplate}
        selectableActiveProjects={selectableActiveProjects}
        selectedBrigadeContract={selectedBrigadeContract}
        selectedWorks={selectedWorks}
        sendCompanyChatMessage={sendCompanyChatMessage}
        setActivePage={setActivePage}
        setCableJournal={setCableJournal}
        setCompanyChatMessage={setCompanyChatMessage}
        setConsentChecked={setConsentChecked}
        setEstimateDoneDrafts={setEstimateDoneDrafts}
        setEstimateWorkMaterials={setEstimateWorkMaterials}
        setEstimateWorkParams={setEstimateWorkParams}
        setEditingAct={setEditingAct}
        setExpandedProject={setExpandedProject}
        setListSearch={setListSearch}
        setMasterProjectId={setMasterProjectId}
        setNewOwnExpense={setNewOwnExpense}
        setNewSupplyReq={setNewSupplyReq}
        setNotifications={setNotifications}
        setPreviewContent={setPreviewContent}
        setProfileData={setProfileData}
        setReportingPayment={setReportingPayment}
        setSelectedWorks={setSelectedWorks}
        setShowNotifications={setShowNotifications}
        setShowOwnExpenseForm={setShowOwnExpenseForm}
        setShowPhotoModal={setShowPhotoModal}
        setShowProfileForm={setShowProfileForm}
        setShowSupplyForm={setShowSupplyForm}
        setSupplyCollapsedProjects={setSupplyCollapsedProjects}
        setUser={setUser}
        setHiddenActs={setHiddenActs}
        showNotifications={showNotifications}
        showOwnExpenseForm={showOwnExpenseForm}
        showPhotoModal={showPhotoModal}
        showPreview={showPreview}
        showProfileForm={showProfileForm}
        showSupplyForm={showSupplyForm}
        submitEstimateWorkDone={submitEstimateWorkDone}
        supplyCollapsedProjects={supplyCollapsedProjects}
        supplyRequestOrigin={supplyRequestOrigin}
        supplyRequests={supplyRequests}
        supplyTemplates={supplyTemplates}
        toNum={toNum}
        toggleNotifications={toggleNotifications}
        tools={tools}
        unreadNotifications={unreadNotifications}
        updateEstimateWorkMaterialQty={updateEstimateWorkMaterialQty}
        updateProjectProgress={updateProjectProgress}
        updateSelectedWorkMaterialQty={updateSelectedWorkMaterialQty}
        uploadPhoto={uploadPhoto}
        upsertEstimateWorkMaterial={upsertEstimateWorkMaterial}
        upsertSelectedWorkMaterial={upsertSelectedWorkMaterial}
        user={user}
        visibleEstimatesForCurrentUser={visibleEstimatesForCurrentUser}
        workJournal={workJournal}
        workNeedsThicknessParam={workNeedsThicknessParam}
      />
      </React.Suspense>
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
      <SupplierCabinetPage
        API={API}
        C={C}
        UNITS={UNITS}
        badge={badge}
        btnB={btnB}
        btnG={btnG}
        btnGr={btnGr}
        btnO={btnO}
        btnR={btnR}
        card={card}
        createInvoiceFromOffer={createInvoiceFromOffer}
        createShipmentFromOffer={createShipmentFromOffer}
        fileSrc={fileSrc}
        handleLogout={handleLogout}
        inp={inp}
        invoicingOfferId={invoicingOfferId}
        newCatalogItem={newCatalogItem}
        newKpResponse={newKpResponse}
        newOfferInvoice={newOfferInvoice}
        notify={notify}
        parseSupplyItems={parseSupplyItems}
        refreshData={refreshData}
        respondingOfferId={respondingOfferId}
        setInvoicingOfferId={setInvoicingOfferId}
        setNewCatalogItem={setNewCatalogItem}
        setNewKpResponse={setNewKpResponse}
        setNewOfferInvoice={setNewOfferInvoice}
        setRespondingOfferId={setRespondingOfferId}
        setShipmentForm={setShipmentForm}
        setShippingOfferId={setShippingOfferId}
        setShowCatalogForm={setShowCatalogForm}
        setSupplierCatalog={setSupplierCatalog}
        setSupplierRequisites={setSupplierRequisites}
        setSupplierTab={setSupplierTab}
        shipmentForm={shipmentForm}
        shippingOfferId={shippingOfferId}
        showCatalogForm={showCatalogForm}
        supplierCatalog={supplierCatalog}
        supplierInvoices={supplierInvoices}
        supplierOffers={supplierOffers}
        supplierRequisites={supplierRequisites}
        supplierTab={supplierTab}
        suppliers={suppliers}
        supplyClaims={supplyClaims}
        supplyDeliveries={supplyDeliveries}
        supplyRequests={supplyRequests}
        tbl={tbl}
        tblC={tblC}
        tblH={tblH}
        uploadPhoto={uploadPhoto}
        user={user}
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

  const handleEstimateImportFile = async (e) => {
    if(!e.target.files[0]) return;
    if(!newEstimate.projectId){alert('Сначала выберите проект — без привязки смета не сохранится');e.target.value='';return;}
    const fd=new FormData();
    fd.append('file',e.target.files[0]);
    try {
      const data=await readApiResult(await fetch(API+'/parse-smeta',{method:'POST',body:fd}));
      if(data.error) throw new Error(data.error);
      if(!Array.isArray(data.items)||!data.items.length) throw new Error('В файле не найдены рабочие строки сметы. Если это ССР/сводный расчёт, загрузите его как документ, а рабочую смету импортируйте из ЛСР или СК.');
      const sections={};
      (data.items||[]).forEach(item=>{
        if(!sections[item.section]) sections[item.section]={id:Date.now()+Math.random(),name:item.section,items:[]};
        const importedItem=normalizeImportedEstimateItem({
          id:Date.now()+Math.random(),
          name:item.name,
          unit:item.unit,
          quantity:item.quantity,
          rawUnit:item.rawUnit||'',
          rawQuantity:item.rawQuantity,
          unitFactor:item.unitFactor||1,
          quantityBase:item.quantityBase,
          quantityCoefficient:item.quantityCoefficient,
          quantityFinal:item.quantityFinal,
          baseUnitPrice:item.baseUnitPrice,
          costCoefficient:item.costCoefficient,
          baseTotal:item.baseTotal,
          costIndex:item.costIndex,
          currentTotal:item.currentTotal,
          lineTotalSource:item.lineTotalSource,
          total:item.total,
          sum:item.sum,
          amount:item.amount,
          lineTotal:item.lineTotal,
          totalSum:item.totalSum,
          totalWork:item.totalWork,
          totalMaterial:item.totalMaterial,
          priceWork:item.priceWork,
          priceMaterial:item.priceMaterial,
          sourceCode:item.sourceCode||item.obosn||'',
          workKey:item.workKey||'',
          workName:item.workName||'',
          workSourceCode:item.workSourceCode||'',
          parentWorkKey:item.parentWorkKey||'',
          parentWorkName:item.parentWorkName||'',
          parentWorkSourceCode:item.parentWorkSourceCode||'',
          resourceRole:item.resourceRole||'',
          isImported:true,
          itemType:item.type||''
        }, item.section);
        sections[item.section].items.push(importedItem);
      });
      const projName=newEstimate.projectName||(projects.find(p=>p.id===Number(newEstimate.projectId))?.name||'');const fileName=e.target.files[0].name.replace('.xlsx','').replace('.xls','');const resolvedWorkPackage=resolveEstimatePackage(newEstimate.workPackage,fileName,newEstimate.name);const estimateStatus=isLeadership()?(newEstimate.status||'Активная'):'Черновик';const estDraft={projectId:newEstimate.projectId,projectName:projName,smetaType:newEstimate.smetaType||'Заказчик',workPackage:resolvedWorkPackage};const est={id:Date.now(),name:fileName||newEstimate.name||'Смета — '+projName,projectId:newEstimate.projectId,projectName:projName,version:newEstimate.version||nextEstimateVersionFor(estDraft),smetaType:newEstimate.smetaType||'Заказчик',workPackage:resolvedWorkPackage,status:estimateStatus,sections:enrichEstimateMeasurementBasis(Object.values(sections))};
      const saved=await readApiResult(await fetch(API+'/estimates',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(est)}));
      if(!saved?.id) throw new Error('Сервер не вернул id сохранённой сметы');
      const estWithId={...est,id:saved.id,smetaType:newEstimate.smetaType||'Заказчик',workPackage:resolvedWorkPackage,status:estimateStatus};
      const diffBase=activeEstimateFromList((estimatesList||[]).filter(e=>estWithId.status==='Активная'&&!isGlobalEstimateTemplate(e)&&sameEstimateGroup(e,estWithId)&&e.status==='Активная'));
      const nextEstimates=applyEstimateActivationState([...(estimatesList||[]),estWithId], estWithId);
      setEstimatesList(nextEstimates);
      setSelectedEstimate(estWithId);
      setEstimatesTab('list');
      if(diffBase) {
        await queueEstimateDiffReviewTask(diffBase,estWithId,'Импорт сметы');
        await autoReconcileEstimateChanges(diffBase,estWithId,'Импорт сметы');
        await createEstimateReconciliation(diffBase,estWithId,{silent:true});
      }
      await queueEstimateQualityReviewTask(estWithId, 'Импорт сметы');
      await queueEstimateNormReviewTask(estWithId, 'Импорт сметы', nextEstimates);
      const qualityWarnings = estimateQualityRows(estWithId).map(row=>({
        type:'качество',
        where:(row.sectionName||'')+' / '+(row.itemName||''),
        message:row.status+': '+row.message,
        severity:row.severity==='critical'?'критично':row.severity==='info'?'совет':'внимание'
      }));
      setImportValidating(true);
      setImportValidationWarnings(qualityWarnings);
      try{
        const items=Object.values(sections).flatMap(s=>(s.items||[]).map(i=>({section:s.name,name:i.name,unit:i.unit,qty:Number(i.quantity||0)})));
        const valPrompt='Проверь смету "'+est.name+'" на типовые проблемы при импорте из Гранд Сметы. Позиции:\n'+JSON.stringify(items,null,1)+'\n\nИЩИ:\n- Забытые сопутствующие работы (например штукатурка без грунтовки)\n- Возможные дубликаты позиций\n- Подозрительно большие или маленькие объёмы\n- Странные единицы измерения\n\nОТВЕТЬ СТРОГО JSON:\n{"warnings":[{"type":"забыто|дубль|объём|единица|другое","where":"раздел или позиция","message":"что не так","severity":"критично|внимание|совет"}]}\nЕсли всё хорошо — пиши {"warnings":[]}. Только JSON.';
        const r=await fetch(API+'/ai-chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:[{role:'user',content:valPrompt}],jsonOnly:true})});
        const d=await r.json();
        const raw=(d.response||'').trim();
        const clean=raw.replace(/^```(?:json)?/i,'').replace(/```$/,'').trim();
        const s=clean.indexOf('{'),en=clean.lastIndexOf('}');
        if(s>=0&&en>s){const p=JSON.parse(clean.slice(s,en+1));if(Array.isArray(p.warnings))setImportValidationWarnings([...qualityWarnings,...p.warnings]);}
      }catch(err){}
      setImportValidating(false);
      const meta=data.meta||{};
      const mismatchText=meta.totalMismatch?('\n\nВнимание: итог файла '+Number(meta.declaredTotal||0).toLocaleString('ru-RU')+' ₽, сумма разобранных строк '+Number(meta.parsedTotal||0).toLocaleString('ru-RU')+' ₽. Строки НЕ умножались общим коэффициентом, чтобы не ломать оплату мастерам. Нужно разобрать итоговый блок/индексы работ и материалов отдельно.'):'';
      alert('Импортировано '+data.count+' позиций! ИИ проверяет смету в фоне — результат появится сверху.'+mismatchText);
    } catch(err){alert('Ошибка импорта: '+(err.message||err));}
    finally { e.target.value=''; }
  };

  const {
    fillSelectedEstimateExecutionPrices,
    handleDetectEstimateHiddenWorks,
    handleEstimateAiAnalysis,
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
    aiMessages,
    brigadeContracts,
    buildEstimateDiffContent,
    contracts,
    estimateDiffBaseFor,
    estimateItemMaterialSum,
    estimateItemTotal,
    estimateItemTypeMeta,
    estimateItemWorkSum,
    estimateChatInput,
    estimateChatLoading,
    estimateChatMessages,
    estimateMeasurementBasisMeta,
    estimateMeasurementBasisOf,
    estimateQualityRows,
    executionPriceFillPercent,
    exportToExcel,
    isEstimateWorkItem,
    materials,
    normalizeEstimateImportSections,
    normalizeEstimateItemType,
    persistEstimate,
    projects,
    queueEstimateQualityReviewTask,
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
    setExecutionPriceFillPercent,
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

  return (
    <div style={{display:'flex',height:'100vh',backgroundColor:C.bg,position:'relative',overflow:'hidden'}}>
      {previewContent&&<PreviewModal content={previewContent} title={previewTitle} onClose={()=>setPreviewContent(null)} onPrint={doPrint}/>}
      <ImagePreviewModal src={showPhotoModal} onClose={()=>setShowPhotoModal(null)}/>
      <React.Suspense fallback={null}>
      <AppProjectEditModals
        ui={{ C, aiNotice, aiNoticeIcon, aiNoticeText, btnB, btnG, btnO, btnR, card, inp, tbl, tblC, tblH }}
        state={{ editingAct, editingCable, editingInspection, editingJournal, hiddenActs, journalFilter, showJournalTableModal, users, weatherLog, workJournal }}
        actions={{ appendPhotos, buildCableJournalContent, buildHiddenActContent, buildMaterialInspectionContent, buildWorkJournalContent, cableTypeOf, fileSrc, fmtMeasure, getActStatusForJournal, setCableJournal, setEditingAct, setEditingCable, setEditingInspection, setEditingJournal, setHiddenActs, setJournalFilter, setMaterialInspections, setShowJournalTableModal, setShowPhotoModal, setWorkJournal, showPreview, uploadPhoto }}
      />
      <AppActionModals
        ui={{ C, btnG, btnGr, btnO, btnR, card, inp }}
        constants={{ PAYMENT_TYPES, ROLE_LABELS }}
        state={{ actPayments, aiChat, aiLoading, aiMessage, chatEndRef, confirmAcceptedQty, confirmComment, confirmingEntry, financeUsers, issueToolData, masterProfiles, newBrigadePayment, newPayment, projects, rejectComment, rejectingEntry, returnToolCondition, selectedBrigadeContract, showAiAssistant, showBrigadePayModal, showIssueToolModal, showPayActModal, showQRModal, showReturnToolModal }}
        actions={{ confirmJ, generateQR, issueTool, normalizeMeasure, rejectJ, returnTool, saveActPayment, saveBrigadePayment, sendAiMessage, setAiMessage, setConfirmAcceptedQty, setConfirmComment, setConfirmingEntry, setIssueToolData, setNewBrigadePayment, setNewPayment, setRejectComment, setRejectingEntry, setReturnToolCondition, setShowAiAssistant, setShowBrigadePayModal, setShowIssueToolModal, setShowPayActModal, setShowQRModal, setShowReturnToolModal, toNum }}
      />
      </React.Suspense>

      <AppSidebar isMobile={isMobile} sidebarRef={sidebarRef} sidebarVisible={sidebarVisible} setSidebarVisible={setSidebarVisible} C={C} user={user} roleLabels={ROLE_LABELS} roleColor={roleColor} menuItems={menuItems} supplyRequests={supplyRequests} isLeadership={isLeadership} isMasterRole={isMasterRole} activePage={activePage} navigateTo={navigateTo} handleLogout={handleLogout}/>

      <div style={{flex:1,display:'flex',flexDirection:'column',overflow:'hidden',width:'100%',minWidth:0,marginLeft:isMobile?0:'240px'}}>
        <AppHeaderBar C={C} activePage={activePage} isCompactHeader={isCompactHeader} isMobile={isMobile} setSidebarVisible={setSidebarVisible} allMenuItems={allMenuItems} globalSearch={globalSearch} setGlobalSearch={setGlobalSearch} setShowSearch={setShowSearch} showSearch={showSearch} searchResults={searchResults} navigateTo={navigateTo} inp={inp} darkMode={darkMode} setDarkMode={setDarkMode} setShowQuickActions={setShowQuickActions} user={user} openSystemStatus={openSystemStatus} setShowChatPanel={setShowChatPanel} unreadMessagesCount={unreadMessagesCount} showNotifications={showNotifications} toggleNotifications={toggleNotifications} unreadNotifications={unreadNotifications} btnG={btnG} btnO={btnO} myNotifications={myNotifications} notifications={notifications} markMyNotificationsRead={markMyNotificationsRead} closeNotifications={closeNotifications} getNotifPage={getNotifPage} setShowNotifications={setShowNotifications} setNotifications={setNotifications} setUser={setUser} API={API}/>
        <div style={{flex:1,overflowY:'auto',backgroundColor:activePage==='dashboard'?'#0b1120':C.bg,padding:activePage==='dashboard'?'0':'24px'}}>
          <React.Suspense fallback={pageFallback}>
          {activePage==='dashboard'&&(
            <DashboardPage
              ui={{ API, C, btnG, btnO, darkMode, isMobile, showAiAssistant, showNotifications, unreadMessagesCount, unreadNotifications }}
              data={{ accountablePayments, activityLog, aiFindings, canUseDirectorAgent, dailyReportDate, directorAgentAnswer, directorAgentError, directorAgentLoading, directorAgentQuestion, directorAgentSteps, estimateControlIssues, hiddenActs, initialDataLoaded, inspectionOrders, lowMainStock, lowStock, manualExpenses, mobileExpandedRenderLists, myNotifications, notifications, ownExpenses, projectPayments, projects, supplierInvoices, supplierOffers, supplyRequests, unexpectedWorksList, user, workJournal }}
              actions={{ askDirectorAgent, buildDailyObjectReportContent, buildDirectorBriefReportContent, buildSupplyControlReportContent, closeNotifications, getNotifPage, isApprovedEstimateChangeStatus, isLeadership, markMyNotificationsRead, navigateTo, normalizeDocDate, openEstimateControlReport, projectBudgetSpent, projectPaymentSignedAmount, projectRealProgress, setAccountingTab, setActivePage, setDailyReportDate, setDirectorAgentQuestion, setDarkMode, setExpandedProject, setMobileExpandedRenderLists, setNotifications, setShowAiAssistant, setShowChatPanel, setShowForm, setShowNotifications, setShowQuickActions, setShowReimburseModal, setShowSupplyForm, setSidebarVisible, setSupplyTab, setUser, setWarehouseTab, showPreview, toggleNotifications, visibleActiveProjects, workDocDate }}
            />
          )}
          {activePage==='projects'&&canAccess('projects')&&(<ProjectsPage ctx={projectsPageContext}/>)}
          {activePage==='site'&&canAccess('site')&&(
            <ProjectSitePublicationPage
              C={C}
              badge={badge}
              btnG={btnG}
              btnO={btnO}
              card={card}
              inp={inp}
              isMobile={isMobile}
              projects={projects}
              projectSiteDraft={projectSiteDraft}
              updateProjectSiteDraft={updateProjectSiteDraft}
              saveProjectSitePublication={saveProjectSitePublication}
            />
          )}
          <AppDirectoryPages
            activePage={activePage}
            ui={{ API, C, badge, btnB, btnG, btnGr, btnO, btnR, card, inp, isMobile, tbl, tblC, tblH }}
            constants={{ PRICELISTS_DATA, ROLE_GROUPS, ROLE_LABELS, ROLES, SUPPLIER_CATEGORIES, UNITS }}
            state={{ clients, compareLoadingReqId, compareResultByReq, editingItem, editingPlItem, estimatesList, expandedClient, expandedGroup, fileSrc, inlineEditPl, inlineEditPlData, inviteCodes, listSearch, newClient, newInviteRole, newOffer, newPlItem, newPricelist, newRequest, newSupplier, newUser, pricelistItems, pricelists, projects, searchUser, selectedPricelist, showForm, showInvites, showOffers, suppliers, suppliersTab, supplierOffers, supplyDeliveries, supplyHistory, supplyRequestOrigin, supplyRequests, user, users }}
            actions={{ approveOffer, buildPricelistContent, cancelInlinePlEdit, cancelRequest, copyPricelist, createInvite, deleteClient, deleteInvite, deletePlItem, deletePricelist, deleteSupplier, deleteUser, exportToExcel, generateTempPassword, getProjectWorkPackageOptions, isLeadership, loadAll, loadPricelistItems, matchSearch, parseOfferItems, parseSupplyItems, renderSupplyRequestOrigin, resetUserTwoFactor, roleColor, runCompareKp, saveClient, saveInlinePlItem, saveOffer, savePlItem, savePricelist, saveRequest, saveSupplier, saveUser, selectSupplierOffer, setEditingItem, setEditingPlItem, setExpandedClient, setExpandedGroup, setFromEstimateForm, setGeneratedInviteLink, setGeneratePricelistForm, setInlineEditPlData, setInlineEditPrice, setListSearch, setNewClient, setNewInviteRole, setNewOffer, setNewPlItem, setNewPricelist, setNewRequest, setNewSupplier, setNewUser, setPricelistItems, setSearchUser, setSelectedPricelist, setShowForm, setShowFromEstimate, setShowGeneratePricelist, setShowInvites, setShowOffers, setShowSupplierInviteModal, setSupplierInviteForm, setSuppliersTab, showPreview, startInlinePlEdit, rejectSupplierOffer, toggleUserActive }}
          />

          <AppOperationsPages
            activePage={activePage}
            ui={{ C, badge, btnB, btnG, btnGr, btnO, btnR, card, inp, isMobile, tbl, tblC, tblH }}
            constants={{ MATERIAL_CATEGORIES, SUPPLIER_CATEGORIES, TOOL_STATUSES, UNITS, VAT_OPTIONS }}
            state={{ compareLoadingReqId, compareResultByReq, deliveryAiLoadingId, deliveryAiResultById, editingItem, estimatesList, expandedProject, fileSrc, history, inventory, invoices, listSearch, materialReconciliationRows, materials, materialsPage, materialTransfers, newInventory, newInvoice, newMovement, newSupplier, newSupplierInvoice, newSupplyReq, newTool, newTransfer, newWarehouse, priceHints, projects, receiveForm, receivingDeliveryId, selectedInventory, selectedWarehouseProject, showForm, showSupplyForm, showTransferForm, staff, suppliers, supplierCatalog, supplierInvoices, supplierOffers, supplyAiLoading, supplyAiText, supplyClaims, supplyCollapsedProjects, supplyDeliveries, supplyExpandedId, supplyRejectId, supplyRejectReason, supplyRequests, supplyRequestOrigin, supplyStockCheck, supplyTab, supplyTemplates, toolHistory, tools, toolsTab, user, warehouseInvoiceItems, warehouseMain, warehouseMovements, warehouses, warehouseTab }}
            actions={{ _normalizeUnit, applySupplyTemplate, applyWarehouseMovement, approveSupplyAsDirector, askSupplyAi, buildInventoryDoc, buildInvoiceContent, buildMaterialRequirementContent, buildMovementDoc, cancelSupply, confirmSupplyAsProrab, convertUnits, createSupplyReq, deleteMainMaterial, deleteMaterial, deleteSupplier, deleteSupplyTemplate, deleteTool, deleteWarehouse, exportToExcel, fetchPriceHint, getProjectEstimateWorkOptions, getProjectWorkPackageOptions, isFinanceRole, isLeadership, isProrab, isSupplyDeliveryInvoice, loadAll, loadMaterialsPage, loadSupplyStockCheck, matchSearch, materialControlSummaryForProject, notify, openReceiveInvoice, openRequestKpModal, parseOfferItems, parseSupplyItems, receiveSupplyDelivery, refreshData, rejectSupplierOffer, rejectSupply, renderInvoiceControlActions, renderMaterialReconciliationPanel, renderSupplyPlanningHint, renderSupplyRequestOrigin, runCompareKp, runDeliveryAiCheck, saveInvoiceNew, saveSupplier, saveSupplyTemplate, saveTool, saveWarehouse, selectSupplierOffer, setDeliveryAiLoadingId, setDeliveryAiResultById, setEditingItem, setExpandedProject, setGeneratedInviteLink, setListSearch, setMaterialTransfers, setMaterials, setNewInventory, setNewInvoice, setNewMovement, setNewSupplier, setNewSupplierInvoice, setNewSupplyReq, setNewTool, setNewTransfer, setNewWarehouse, setReceiveForm, setReceivingDeliveryId, setSelectedInventory, setSelectedWarehouseProject, setShowForm, setShowIssueToolModal, setShowPhotoModal, setShowQRModal, setShowReturnToolModal, setShowSupplierInviteModal, setShowSupplyForm, setShowTransferForm, setSupplierInviteForm, setSupplyCollapsedProjects, setSupplyExpandedId, setSupplyRejectId, setSupplyRejectReason, setSupplyTab, setToolsTab, setWarehouseMain, setWarehouseTab, showPreview, toNum, uploadPhoto, visibleActiveProjects, warehouseInvoiceEstimateControl }}
          />

          <AppBackofficePages
            activePage={activePage}
            ui={{ API, C, badge, btnB, btnG, btnGr, btnO, btnR, card, inp, isMobile, tbl, tblC, tblH }}
            constants={{ PD_CONSENT_TEXT, ROLE_GROUPS, ROLE_LABELS, UNITS }}
            state={{ accountablePayments, accountingDocProject, accountingTab, allBrigadeItems, allBrigadePayments, auditLog, brigadeContracts, contracts, editingItem, estimatesList, expandedActDate, expandedMaster, expandedMasterProject, expandedPieceworkProject, expandedProject, expandedStaffId, expenseReports, fileSrc, interimActs, invoices, listSearch, manualExpenses, masterProfiles, masterRatings, newAct, newContract, newExpenseReport, newPiecework, newStaff, newStaffDoc, ownExpenses, payrollExtras, pdConsents, personnelTab, piecework, projectDocuments, projectPaymentInAmount, projectPayments, projectPlanDone, projects, salaryEdits, salaryMonth, salaryPayments, showForm, showPiecework, showStaffDocForm, staff, staffExpandedSections, staffProfile, staffProfileLoading, supplierInvoices, suppliers, timesheet, tools, unexpectedWorksList, user, users, workJournal }}
            actions={{ addPiecework, addStaffDoc, buildAOSKContent, buildActContent, buildBrigadeActContent, buildContractContent, buildExecPackageContent, buildIGDContent, buildInvoiceContent, buildJPRContent, buildKS11Content, buildKS14Content, buildKS3Content, buildM29Content, buildM2Content, buildM8Content, buildMaterialRequirementContent, buildPassportContent, buildPositionInstructionContent, buildSpecJournalContent, buildVATBookContent, calcSalary, contractRequisitesWarning, createContract, createInterimAct, createStaffAccessFromPrompt, daysInMonth, deleteContract, deleteInterimAct, deletePiecework, deleteStaff, findUserForStaff, fmtMeasure, isApprovedEstimateChangeStatus, isFinanceRole, isLeadership, loadAuditLog, matchSearch, materialControlSummaryForProject, normalizePersonKey, openStaffProfile, paySalary, ratemaster, refreshData, resetStaffAccessPassword, resolveContractPerformer, roleColor, saveStaff, setAccountingDocProject, setAccountingTab, setAuditLog, setEditingItem, setExpandedActDate, setExpandedMaster, setExpandedMasterProject, setExpandedPieceworkProject, setExpandedProject, setListSearch, setNewAct, setNewContract, setNewExpenseReport, setNewPiecework, setNewStaff, setNewStaffDoc, setPayrollExtra, setPersonnelTab, setSalaryEdit, setSalaryMonth, setSalaryPayments, setShowForm, setShowPayActModal, setShowPhotoModal, setShowPiecework, setShowReimburseModal, setShowStaffDocForm, setStaffExpandedSections, setStaffProfile, showKS2, showPreview, toggleDay, toNum, uploadPhoto, warehouseInvoiceEstimateControl, workedDays }}
          />

          {activePage==='estimates'&&(<EstimatesPage ctx={estimatesPageContext}/>)}

          <AppSecondaryPages
            activePage={activePage}
            ui={{ API, C, badge, btnB, btnG, btnO, btnR, card, inp, isMobile, tbl, tblC, tblH }}
            constants={{ CRM_STAGES, EXPENSE_CATEGORIES, ROLE_LABELS, WEATHER_CONDITIONS }}
            state={{
              accountablePayments, activityLog, auditLog, companyChatMessage, companyDocuments,
              companyMessages, companyReqForm, companyRequisites, contracts, editingItem,
              expByCategory, fileSrc, leads, newCompanyDoc, newLead, newWeather, ownExpenses,
              projects, settingsTab, showForm, staff, suppliers, user, users, weatherLog,
              weatherTab, workJournal,
            }}
            actions={{
              appendPhotos, buildJPRContent, createProjectFromLead, deleteLead, isFinanceRole,
              loadAll, roleColor, saveCompanyRequisites, saveLead, saveWeather,
              sendCompanyChatMessage, setCompanyChatMessage, setCompanyReqForm,
              setCompanyRequisites, setEditingItem, setLeads, setNewCompanyDoc, setNewLead,
              setNewWeather, setReportingPayment, setSettingsTab, setShowForm,
              setShowOwnExpenseForm, setShowPhotoModal, setWeatherTab, showPreview,
              uploadPhoto,
            }}
          />
          </React.Suspense>
        </div>
      </div>
      <MobileBottomNav activePage={activePage} isMobile={isMobile} unreadMessagesCount={unreadMessagesCount} menuItems={menuItems} navigateTo={navigateTo} setActivePage={setActivePage} setShowMobileMenu={setShowMobileMenu} setShowQuickActions={setShowQuickActions} setShowChatPanel={setShowChatPanel}/>
      <WorkAssignmentModal
        show={showWorkAssignment}
        onClose={()=>setShowWorkAssignment(false)}
        selectedEstimate={selectedEstimate}
        staff={staff}
        users={users}
        API={API}
        loadAll={loadAll}
        C={C}
        card={card}
        inp={inp}
        btnO={btnO}
        btnG={btnG}
        btnB={btnB}
        isMobile={isMobile}
      />
      <AppWorkflowModals
        ui={{ API, C, badge, btnB, btnG, btnO, btnR, card, darkMode, inp, isMobile }}
        constants={{ estimatePackages: ESTIMATE_PACKAGES, expenseCategories: EXPENSE_CATEGORIES, roleLabels: ROLE_LABELS, supplierCategories: SUPPLIER_CATEGORIES, units: UNITS }}
        state={{
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
        }}
        actions={{
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
        }}
      />
	    <AppOverlayLayer
	      showSystemStatus={showSystemStatus}
	      systemStatus={systemStatus}
	      systemStatusLoading={systemStatusLoading}
	      openSystemStatus={openSystemStatus}
	      setShowSystemStatus={setShowSystemStatus}
	      C={C}
	      badge={badge}
	      btnG={btnG}
	      showMobileMenu={showMobileMenu}
	      setShowMobileMenu={setShowMobileMenu}
	      menuItems={menuItems}
	      activePage={activePage}
	      navigateTo={navigateTo}
	      setActivePage={setActivePage}
	      showChatPanel={showChatPanel}
	      setShowChatPanel={setShowChatPanel}
	      companyMessages={companyMessages}
	      user={user}
	      companyChatInput={companyChatInput}
	      setCompanyChatInput={setCompanyChatInput}
	      sendCompanyChatMessage={sendCompanyChatMessage}
	      uploadPhoto={uploadPhoto}
	    />

    </div>
  );
}

export default App;
