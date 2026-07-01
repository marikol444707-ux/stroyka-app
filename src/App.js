import React, { useState, useEffect, useRef, useCallback } from 'react';
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
import DocumentRecognitionPanel from './components/DocumentRecognitionPanel';
import ProjectLettersPanel from './components/ProjectLettersPanel';
import ProjectBrigadeCalculationTab from './components/ProjectBrigadeCalculationTab';
import ProjectHiddenWorksActsPanel from './components/ProjectHiddenWorksActsPanel';
import ProjectPrescriptionsPanel from './components/ProjectPrescriptionsPanel';
import ProjectSafetyJournalPanel from './components/ProjectSafetyJournalPanel';
import ProjectWorkJournalPanel from './components/ProjectWorkJournalPanel';
import ProjectScheduleSummaryPanel from './components/ProjectScheduleSummaryPanel';
import MaterialReconciliationPanel from './components/MaterialReconciliationPanel';
import MaterialWriteoffStatus from './components/MaterialWriteoffStatus';
import { ProjectDirectorMapPanel, buildDirectorMapContract, getDirectorMapActionTarget } from './features/director-map';
import { ProjectLaunchPanel } from './features/project-launch';
import { createProjectCrudActions } from './features/projects/projectCrudActions';
import { createWarehouseCrudActions } from './features/warehouse/warehouseCrudActions';
import { createMaterialControlActions } from './features/material-control/materialControlActions';
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
import {
  DashboardActivityPanel,
  DashboardDirectorAiPanel,
  DashboardProductionSummaryPanel,
  DashboardSupplyPanel,
  MasterCabinetPage,
} from './app/lazyComponents';
import { buildLeadPayload } from './features/crm/leadUtils';
import WorkAssignmentModal, { WorkAssignmentStatusPanel } from './features/work-assignment';
import { createAiTaskActions } from './features/ai-control/aiTaskActions';
import { createDocumentActions } from './features/documents/documentActions';
import { createPersonnelActions } from './features/personnel/personnelActions';
import { createMaterialNormActions } from './features/material-norms/materialNormActions';
import { createMaterialNormCoverageActions } from './features/material-norms/materialNormCoverageActions';
import { createMaterialWriteoffActions } from './features/material-writeoff/materialWriteoffActions';
import AppSidebar from './components/AppSidebar';
import AppHeaderBar from './components/AppHeaderBar';
import DashboardTopBar from './components/DashboardTopBar';
import DashboardStatsGrid from './components/DashboardStatsGrid';
import DashboardRisksPanel from './components/DashboardRisksPanel';
import AppWorkflowModals from './components/AppWorkflowModals';
import AppSecondaryPages from './components/AppSecondaryPages';
import AppDirectoryPages from './components/AppDirectoryPages';
import AppOperationsPages from './components/AppOperationsPages';
import AppBackofficePages from './components/AppBackofficePages';
import AppActionModals from './components/AppActionModals';
import AppEntryRoutes from './components/AppEntryRoutes';
import AppProjectEditModals from './components/AppProjectEditModals';
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
import { buildEstimateChatContext } from './utils/estimateChatUtils';
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
import {
  buildDirectorBriefReportContentForDate,
  buildDirectorEstimateControlIssues,
  buildDirectorEstimateControlReportContent,
  buildDirectorSupplyControlIssues,
  buildDirectorSupplyControlReportContent,
} from './utils/directorReportWorkflowUtils';
import {
  invoiceControlMaterialName,
  invoiceControlNeedsReview,
  invoiceControlProjectName,
  invoiceControlReviewReason,
  parseAiTaskPayload,
} from './utils/aiControlDescriptionUtils';
import {
  buildMaterialControlSignatureForProject,
  buildMaterialControlTaskDescriptorsForProject,
  buildRoomControlSignatureForProject,
  buildRoomControlTaskDescriptorsForProject,
} from './utils/aiControlTaskUtils';
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
  writeStoredJson,
} from './utils/appRuntimeUtils';
import {
  normalizeDocDate,
  workDocDate,
} from './utils/documentFormatUtils';
import { exportToExcelFile } from './utils/exportUtils';
import { cableTypeOf } from './utils/cableUtils';
import {
  contractRequisitesWarning,
  findUserForStaff as findUserForStaffRow,
  normalizePersonKey,
  resolveContractPerformer as resolveContractPerformerRow,
} from './utils/performerUtils';
import {
  activeProjectsOnly,
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
  buildProjectEconomy,
  projectBudgetSpentSummary,
  projectExpenseCategories,
  projectFactSpentValue,
  projectRealProgressValue,
  workExecutionTotalValue,
} from './utils/projectEconomyUtils';
import { buildProjectObjectLinks } from './utils/projectObjectLinksUtils';
import {
  buildComputedNotifications,
  notificationPageForType,
  notificationsForUser,
} from './utils/notificationUtils';
import {
  buildWarehouseInvoiceItems,
  packageMatches,
  parseJournalMaterialsValue,
} from './utils/materialDocumentUtils';
import { actStatusForJournalWork } from './utils/hiddenActUtils';
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
import { buildScanDraftInvoiceNumber } from './utils/accountingInvoices';
import {
  isActiveSupplyRequestStatus,
  isSameSupplyMaterial,
  parseOfferItems,
  parseSupplyItems,
  supplyRequestOrigin,
  supplyUnitKey,
} from './utils/supplyUtils';
import { aiSeverityMeta, estimateStatusView, isOpenAiStatus, materialControlStatus, materialNormCoverageMeta, materialNormStatus, workJournalEstimateStatusMeta } from './utils/statusMetaUtils';
import { FolderKanban, Package, ScrollText, Search, Plus, Edit2, Trash2, Eye, Check, X, ChevronDown, ChevronUp, Download, Upload, MapPin, FileText, Archive, QrCode, Calculator, Bot, GitBranch } from 'lucide-react';

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

  const openReceiveInvoice = (preselectedLocation, options = {}) => {
    const assignedProjectNames = [
      ...(Array.isArray(user?.assignedProjects) ? user.assignedProjects : []),
      ...(Array.isArray(user?.assigned_projects) ? user.assigned_projects : []),
      user?.projectName,
      user?.project_name,
      user?.project,
    ].map((project) => {
      if (!project) return '';
      if (typeof project === 'string') return project;
      return project.name || project.projectName || project.project_name || '';
    }).map((project) => String(project).trim()).filter(Boolean);
    const assignedProjectSet = new Set(assignedProjectNames);
    let location = preselectedLocation || '';
    if (!location && user?.role === 'прораб') {
      const projectFromList = assignedProjectNames.length
        ? (projects || []).find((project) => project?.name && !project.archived && project.status !== 'Завершён' && assignedProjectSet.has(project.name))
        : null;
      location = projectFromList?.name || assignedProjectNames[0] || '';
    }
    const warehouseTarget = location && location !== 'Основной склад' ? 'object' : 'main';
    setNewInvoice({
      number:'',
      date:new Date().toISOString().split('T')[0],
      supplierId:'',
      isNewSupplier:false,
      newSupplierName:'',
      acceptedBy:user?.name||'',
      location,
      project:warehouseTarget === 'object' ? location : '',
      warehouseTarget,
      selectedAction:'receive_to_warehouse',
      sourceType:warehouseTarget === 'object' ? 'manual_project_invoice' : 'manual_main_invoice',
      sourceId:null,
      vat:'Без НДС',
      photos:[],
      photoUrls:[],
      pagesCount:1,
      items:[{name:'',quantity:'',unit:'шт',price:'',category:'',workPackage:''}],
      supplier:'',
      totalWithVat:0
    });
    if (options.scanFirst) {
      setShowScanInvoice(true);
      return;
    }
    setShowReceiveDialog(true);
  };
  const openSystemStatus = async () => {
    setShowSystemStatus(true);
    setSystemStatusLoading(true);
    try {
      const res = await fetch(API+'/system-status');
      const data = await res.json().catch(()=>({ok:false,error:'bad_json'}));
      setSystemStatus(res.ok ? data : {...data,ok:false,httpStatus:res.status});
    } catch (e) {
      setSystemStatus({ok:false,error:e.message});
    } finally {
      setSystemStatusLoading(false);
    }
  };
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
  const setSalaryEdit = (month, staffId, field, value) => {
    setSalaryEdits(prev => {
      const next = {...prev};
      if(!next[month]) next[month] = {};
      if(!next[month][staffId]) next[month][staffId] = {};
      next[month][staffId][field] = value;
      return writeStoredJson('salaryEdits', next);
    });
  };
  const setPayrollExtra = (month, list) => {
    setPayrollExtras(prev => {
      const next = {...prev, [month]: list};
      return writeStoredJson('payrollExtras', next);
    });
  };
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

  const sendEstimateChatMessage = async () => {
    if (!selectedEstimate || !estimateChatInput.trim() || estimateChatLoading) return;
    const msg = estimateChatInput.trim();
    setEstimateChatInput('');
    const localHistory = [...estimateChatMessages, {role:'user', content:msg, id:Date.now()}];
    setEstimateChatMessages(localHistory);
    setEstimateChatLoading(true);
    try {
      const context = buildEstimateChatContext(selectedEstimate);
      const res = await fetch(API+'/estimate-chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({estimateId:selectedEstimate.id,message:msg,context,history:estimateChatMessages.map(m=>({role:m.role,content:m.content}))})});
      const data = await res.json();
      setEstimateChatMessages([...localHistory,{role:'assistant',content:data.response||'Ошибка ответа',id:data.assistantMessageId||Date.now()+1}]);
    } catch(err) {
      setEstimateChatMessages([...localHistory,{role:'assistant',content:'Ошибка соединения',id:Date.now()+1}]);
    }
    setEstimateChatLoading(false);
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

  const callAI = async (prompt, conversational) => {
    setAiLoading(true);
    try {
      let messages;
      if (conversational) {
        messages = [...aiChat.map(m=>({role:m.role,content:m.content})), {role:'user',content:prompt}];
      } else {
        messages = [{role:'user',content:prompt}];
      }
      const res = await fetch(API+'/ai-chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages})});
      const data = await res.json();
      const text = data.response || data.text || 'Нет ответа';
      setAiLoading(false);
      return text;
    } catch(e) { setAiLoading(false); return ''; }
  };

  const sendAiMessage = async () => {
    if (!aiMessage.trim()) return;
    const userMsg = {role:'user',content:aiMessage,time:new Date().toLocaleTimeString('ru-RU')};
    setAiChat(prev=>[...prev,userMsg]);
    setAiMessage('');
    const response = await callAI(aiMessage, true);
    const assistantMsg = {role:'assistant',content:response,time:new Date().toLocaleTimeString('ru-RU')};
    setAiChat(prev=>[...prev,assistantMsg]);
    setTimeout(()=>chatEndRef.current?.scrollIntoView({behavior:'smooth'}),100);
  };

  const askDirectorAgent = async (questionOverride = '') => {
    const question = String(questionOverride || directorAgentQuestion || '').trim();
    if (!question || directorAgentLoading) return;
    setDirectorAgentQuestion(question);
    setDirectorAgentLoading(true);
    setDirectorAgentError('');
    setDirectorAgentAnswer('');
    setDirectorAgentSteps([]);
    try {
      const res = await fetch(API+'/director-agent/ask', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({question})
      });
      const data = await res.json().catch(()=>({}));
      if (!res.ok) throw new Error(data.detail || data.error || 'Ошибка запроса');
      setDirectorAgentAnswer(data.answer || 'Ответ пустой');
      setDirectorAgentSteps(Array.isArray(data.steps) ? data.steps : []);
    } catch(e) {
      setDirectorAgentError(e.message || 'Не удалось получить ответ');
    } finally {
      setDirectorAgentLoading(false);
    }
  };

  const getNotifPage = (type) => notificationPageForType(type);

  const myNotifications = (notifs) => notificationsForUser(notifs, user);
  const toggleNotifications = (e) => { e?.stopPropagation?.(); setShowNotifications(v=>!v); };
  const closeNotifications = () => setShowNotifications(false);
  const markMyNotificationsRead = () => {
    const visibleIds = new Set(myNotifications(notifications).map(n=>n.id));
    const updated = notifications.map(n=>visibleIds.has(n.id)?{...n,read:true}:n);
    setNotifications(updated);
    localStorage.setItem('notifications',JSON.stringify(updated));
  };

  const notify = (text, type) => {
    const n = {id:Date.now(),text,type,time:new Date().toLocaleString('ru-RU'),read:false};
    setNotifications(prev=>{const updated=[n,...prev].slice(0,50);localStorage.setItem('notifications',JSON.stringify(updated));return updated;});
    if (pushEnabled) sendPushNotification('СтройКа', text);
  };

  const addActivity = (action) => {
    const entry = {id:Date.now(),action,user:user?user.name:'',role:user?user.role:'',time:new Date().toLocaleString('ru-RU')};
    setActivityLog(prev=>{const updated=[entry,...prev].slice(0,100);localStorage.setItem('activityLog',JSON.stringify(updated));return updated;});
    try {
      const token = localStorage.getItem('authToken');
      if (token && user) {
        fetch(API + '/audit-log', {
          method: 'POST',
          headers: {'Content-Type': 'application/json', Authorization: 'Bearer ' + token},
          body: JSON.stringify({action, entityType: 'ui', description: action})
        }).then((res) => {
          if (res.ok && activePage === 'activitylog') loadAuditLog();
        }).catch(() => {});
      }
    } catch {}
  };

  const loadAuditLog = async () => {
    try {
      const token = localStorage.getItem('authToken');
      const data = await fetch(API + pagedPath('/audit-log', {limit: AUDIT_LOG_PAGE_LIMIT}), token ? {headers: {Authorization: 'Bearer ' + token}} : undefined).then(r => r.ok ? r.json() : []);
      setAuditLog(Array.isArray(data) ? data : []);
    } catch (e) {
      setAuditLog([]);
    }
  };

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

  const roleFlags = () => roleFlagsForUser(user);
  const canLoadEstimatesForUser = (targetUser = user) => {
    const flags = roleFlagsForUser(targetUser);
    return flags.canSeeProjectDocs || canAccessRole(targetUser, 'estimates', ROLES);
  };
  const applyLoadedEstimates = (payload) => {
    if (Array.isArray(payload)) setEstimatesList(normalizeEstimateList(payload));
  };
  const handleApiUnauthorized = () => {
    try {
      localStorage.removeItem('authToken');
      localStorage.removeItem('user');
    } catch (e) {}
    mobileLoadedScopesRef.current.clear();
    mobileApiRequestsRef.current.clear();
    setInitialDataLoaded(false);
    setUser(null);
  };

  const getApi = (path, fallback = []) => {
    if (mobileApiRequestsRef.current.has(path)) return mobileApiRequestsRef.current.get(path);
    const token = localStorage.getItem('authToken');
    const request = fetch(API + path, token ? {headers: {Authorization: 'Bearer ' + token}} : undefined)
      .then(r => {
        if (r.ok) return r.json();
        if (r.status === 401) handleApiUnauthorized();
        return fallback;
      })
      .catch(() => fallback)
      .finally(() => mobileApiRequestsRef.current.delete(path));
    mobileApiRequestsRef.current.set(path, request);
    return request;
  };
  const apiAuthHeaders = (headers={}) => {
    const token = localStorage.getItem('authToken');
    return token ? {...headers, Authorization: 'Bearer ' + token} : headers;
  };

  const pagedPath = (path, params = {}) => buildPagedPath(path, params);

  const mergeRowsById = (current = [], incoming = []) => mergeRowsByIdValue(current, incoming);

  const loadMaterialsPage = useCallback(async ({projectName = '', search = '', offset = 0} = {}) => {
    setMaterialsPage(prev => ({...prev, projectName, search, loading:true, error:''}));
    try {
      const data = await getApi(pagedPath('/materials', {
        project_name: projectName,
        search,
        limit: MATERIALS_PAGE_LIMIT,
        offset,
      }), []);
      const rows = Array.isArray(data) ? data : [];
      setMaterials(prev => mergeRowsById(prev, rows));
      setMaterialsPage({
        projectName,
        search,
        hasMore: rows.length === MATERIALS_PAGE_LIMIT,
        loading:false,
        error:'',
      });
      return rows;
    } catch (e) {
      setMaterialsPage(prev => ({...prev, loading:false, error:'Не удалось загрузить материалы'}));
      return [];
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadMaterialNormsPage = useCallback(async ({search = '', offset = 0} = {}) => {
    setMaterialNormsPage(prev => ({...prev, search, loading:true, error:''}));
    try {
      const data = await getApi(pagedPath('/material-norms', {
        search,
        limit: MATERIAL_NORMS_PAGE_LIMIT,
        offset,
      }), []);
      const rows = Array.isArray(data) ? data : [];
      setMaterialNorms(prev => mergeRowsById(prev, rows));
      setMaterialNormsPage({
        search,
        hasMore: rows.length === MATERIAL_NORMS_PAGE_LIMIT,
        loading:false,
        error:'',
      });
      return rows;
    } catch (e) {
      setMaterialNormsPage(prev => ({...prev, loading:false, error:'Не удалось загрузить нормы'}));
      return [];
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const workJournalPageState = (params = {}) => createWorkJournalPageState(params, WORK_JOURNAL_PAGE_LIMIT);

  const loadWorkJournalPage = useCallback(async ({projectName = '', search = '', dateFrom = '', dateTo = '', offset = 0} = {}) => {
    setWorkJournalPage(prev => ({...prev, projectName, search, dateFrom, dateTo, loading:true, error:''}));
    try {
      const data = await getApi(pagedPath('/work-journal', {
        project_name: projectName,
        search,
        date_from: dateFrom,
        date_to: dateTo,
        limit: WORK_JOURNAL_PAGE_LIMIT,
        offset,
      }), []);
      const rows = Array.isArray(data) ? data : [];
      setWorkJournal(prev => mergeRowsById(prev, rows));
      setWorkJournalPage(workJournalPageState({
        projectName,
        search,
        dateFrom,
        dateTo,
        rows,
        loading:false,
        error:'',
      }));
      return rows;
    } catch (e) {
      setWorkJournalPage(prev => ({...prev, loading:false, error:'Не удалось загрузить ЖПР'}));
      return [];
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const resetWorkJournalPage = (rows = []) => {
    setWorkJournalPage(workJournalPageState({
      rows,
      loading:false,
      error:'',
    }));
  };

  const resetMaterialNormsPage = (rows = []) => {
    setMaterialNormsPage(createMaterialNormsPageState({rows, loading:false, error:''}, MATERIAL_NORMS_PAGE_LIMIT));
  };

  const resetMaterialsPage = (rows = []) => {
    setMaterialsPage(createMaterialsPageState({rows, loading:false, error:''}, MATERIALS_PAGE_LIMIT));
  };

  useEffect(() => {
    if (!user || activePage !== 'estimates' || estimatesTab !== 'norms') return undefined;
    const search = materialNormSearch.trim();
    const timer = setTimeout(() => {
      loadMaterialNormsPage({search, offset: 0});
    }, search ? 300 : 0);
    return () => clearTimeout(timer);
  }, [user, activePage, estimatesTab, materialNormSearch, loadMaterialNormsPage]);

  const loadMobileScopeOnce = async (scope, loader) => {
    if (mobileLoadedScopesRef.current.has('full') || mobileLoadedScopesRef.current.has(scope)) return;
    mobileLoadedScopesRef.current.add(scope);
    try { await loader(); }
    catch(e) { mobileLoadedScopesRef.current.delete(scope); }
  };

  const loadMobileInitial = async () => loadMobileScopeOnce('mobile:init', async () => {
    const {role,isLeadershipRole,isFinanceRole,isSupplyRole,isInternalRole,canSeeProjectDocs} = roleFlags();
    const isWorkerRole = ['мастер','субподрядчик','бригадир'].includes(role);
    const shouldLoadUsersAtBoot = isLeadershipRole || isFinanceRole;
    const [
      p,u,sr,ait,oe,pp,wm,wj
    ] = await Promise.all([
      role === 'поставщик' ? Promise.resolve([]) : getApi('/projects'),
      shouldLoadUsersAtBoot ? getApi('/users') : Promise.resolve([]),
      isSupplyRole ? getApi('/supply-requests') : Promise.resolve([]),
      canSeeProjectDocs ? getApi('/ai-tasks') : Promise.resolve([]),
      isInternalRole ? getApi('/own-expenses') : Promise.resolve([]),
      isFinanceRole ? getApi('/project-payments') : Promise.resolve([]),
      role === 'кладовщик' ? getApi('/warehouse-main') : Promise.resolve([]),
      isWorkerRole ? getApi(pagedPath('/work-journal', {limit: WORK_JOURNAL_PAGE_LIMIT})) : Promise.resolve([]),
    ]);
    setProjects(Array.isArray(p)?p:[]);
    setUsers(Array.isArray(u)?u:[]);
    setSupplyRequests(Array.isArray(sr)?sr:[]);
    setAiTasks(Array.isArray(ait)?ait:[]);
    setOwnExpenses(Array.isArray(oe)?oe:[]);
    setProjectPayments(Array.isArray(pp)?pp:[]);
    setWarehouseMain(Array.isArray(wm)?wm:[]);
    setWorkJournal(Array.isArray(wj)?wj:[]);
    resetWorkJournalPage(wj);
    setInitialDataLoaded(true);
  });

  const loadMobilePageData = async (page = activePage) => {
    if (!user || !isMobile) return;
    const {role,isLeadershipRole,isFinanceRole,isWarehouseRole,isSupplyRole,canSeeSupplierInvoices,isInternalRole,canSeeProjectDocs} = roleFlags();
    const isWorkerRole = ['мастер','субподрядчик','бригадир'].includes(role);
    const canLoadEstimates = canLoadEstimatesForUser();
    const estimatesLoadPath = isWorkerRole ? '/estimates' : '/estimates-summary';
    if (page === 'dashboard') return loadMobileScopeOnce('mobile:dashboard', async () => {
      const [aif,ait,sh,sd,scat] = await Promise.all([
        canSeeProjectDocs ? getApi('/ai-findings') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/ai-tasks') : Promise.resolve([]),
        (isSupplyRole || isWarehouseRole || isFinanceRole) ? getApi('/supply-history') : Promise.resolve([]),
        isSupplyRole ? getApi('/supply-deliveries') : Promise.resolve([]),
        (isSupplyRole || isWarehouseRole || isFinanceRole || role === 'поставщик') ? getApi('/supplier-catalog') : Promise.resolve([]),
      ]);
      setAiFindings(Array.isArray(aif)?aif:[]);
      setAiTasks(Array.isArray(ait)?ait:[]);
      setSupplyHistory(Array.isArray(sh)?sh:[]);
      setSupplyDeliveries(Array.isArray(sd)?sd:[]);
      setSupplierCatalog(Array.isArray(scat)?scat:[]);
    });
    if (['projects','site','works','documents','cable'].includes(page)) return loadMobileScopeOnce('mobile:projects-docs', async () => {
      const [p,wj,mt,ro,rw,rwin,rdoor,ps,pcl,pres,uw,est,er,bc,abi,hwa,mij,cbj,sva,inspO,warD,pdocs,plet,pmeas,mdrafts] = await Promise.all([
        role === 'поставщик' ? Promise.resolve([]) : getApi('/projects'),
        role === 'поставщик' ? Promise.resolve([]) : getApi(pagedPath('/work-journal', {limit: WORK_JOURNAL_PAGE_LIMIT})),
        (isWarehouseRole || ['мастер','субподрядчик','бригадир'].includes(role)) ? getApi('/material-transfers') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/rooms') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/room-works') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/room-windows') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/room-doors') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/project-stages') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/project-checklists') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/prescriptions') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/unexpected-works') : Promise.resolve([]),
        canSeeProjectDocs ? getApi(estimatesLoadPath, null) : Promise.resolve(null),
        canSeeProjectDocs ? getApi('/estimate-reconciliations') : Promise.resolve([]),
        (isInternalRole || isFinanceRole) ? getApi('/brigade-contracts') : Promise.resolve([]),
        (isInternalRole || isFinanceRole || ['мастер','субподрядчик','бригадир'].includes(role)) ? getApi('/brigade-contract-items-all') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/hidden-works-acts') : Promise.resolve([]),
        (canSeeProjectDocs || isWarehouseRole) ? getApi('/material-inspection') : Promise.resolve([]),
        (canSeeProjectDocs || isWarehouseRole) ? getApi('/cable-journal') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/supervisor-acts') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/inspection-orders') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/warranty-defects') : Promise.resolve([]),
        (isInternalRole || isFinanceRole || role==='заказчик') ? getApi('/project-documents') : Promise.resolve([]),
        (isInternalRole || isFinanceRole || role==='заказчик') ? getApi('/project-letters') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/project-measurements') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/measurement-room-drafts') : Promise.resolve([]),
      ]);
      setProjects(Array.isArray(p)?p:[]);
      setWorkJournal(Array.isArray(wj)?wj:[]);
      resetWorkJournalPage(wj);
      setMaterialTransfers(Array.isArray(mt)?mt:[]);
      setRooms(Array.isArray(ro)?ro:[]); setRoomWorks(Array.isArray(rw)?rw:[]);
      setRoomWindows(Array.isArray(rwin)?rwin:[]); setRoomDoors(Array.isArray(rdoor)?rdoor:[]);
      setProjectStages(Array.isArray(ps)?ps:[]); setChecklists(Array.isArray(pcl)?pcl:[]);
      setPrescriptionsList(Array.isArray(pres)?pres:[]); setUnexpectedWorksList(Array.isArray(uw)?uw:[]);
      applyLoadedEstimates(est); setEstimateReconciliations(Array.isArray(er)?er:[]); setBrigadeContracts(Array.isArray(bc)?bc:[]); setAllBrigadeItems(Array.isArray(abi)?abi:[]);
      setHiddenActs(Array.isArray(hwa)?hwa:[]); setMaterialInspections(Array.isArray(mij)?mij:[]);
      setCableJournal(Array.isArray(cbj)?cbj:[]); setSupervisorActs(Array.isArray(sva)?sva:[]);
      setInspectionOrders(Array.isArray(inspO)?inspO:[]); setWarrantyDefects(Array.isArray(warD)?warD:[]);
      setProjectDocuments(Array.isArray(pdocs)?pdocs:[]); setProjectLetters(Array.isArray(plet)?plet:[]);
      setProjectMeasurements(Array.isArray(pmeas)?pmeas:[]); setMeasurementRoomDrafts(Array.isArray(mdrafts)?mdrafts:[]);
    });
    if (page === 'estimates') return loadMobileScopeOnce('mobile:estimates', async () => {
      const [est,er,pl,mn,ma,mno,mns,bc,abi,abp] = await Promise.all([
        canLoadEstimates ? getApi(estimatesLoadPath, null) : Promise.resolve(null),
        canLoadEstimates ? getApi('/estimate-reconciliations') : Promise.resolve([]),
        ((isInternalRole && !['мастер','субподрядчик','бригадир'].includes(role)) || role === 'технадзор') ? getApi('/pricelists') : Promise.resolve([]),
        canSeeProjectDocs ? getApi(pagedPath('/material-norms', {limit: MATERIAL_NORMS_PAGE_LIMIT})) : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/material-aliases') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/material-norms/overrides') : Promise.resolve([]),
        canSeeProjectDocs ? getApi('/material-norm-suggestions') : Promise.resolve([]),
        (isInternalRole || isFinanceRole) ? getApi('/brigade-contracts') : Promise.resolve([]),
        (isInternalRole || isFinanceRole) ? getApi('/brigade-contract-items-all') : Promise.resolve([]),
        (isInternalRole || isFinanceRole) ? getApi('/brigade-payments') : Promise.resolve([]),
      ]);
      applyLoadedEstimates(est); setEstimateReconciliations(Array.isArray(er)?er:[]); setPricelists(Array.isArray(pl)?pl:[]);
      setMaterialNorms(Array.isArray(mn)?mn:[]); resetMaterialNormsPage(mn); setMaterialAliases(Array.isArray(ma)?ma:[]);
      setMaterialNormOverrides(Array.isArray(mno)?mno:[]); setMaterialNormSuggestions(Array.isArray(mns)?mns:[]);
      setBrigadeContracts(Array.isArray(bc)?bc:[]); setAllBrigadeItems(Array.isArray(abi)?abi:[]);
      setAllBrigadePayments(Array.isArray(abp)?abp:[]);
    });
    if (['warehouse','materials'].includes(page)) return loadMobileScopeOnce('mobile:warehouse', async () => {
      const [m,winv,wm,wmov,h,wh,mt,mij,cbj] = await Promise.all([
        role === 'поставщик' ? Promise.resolve([]) : getApi(pagedPath('/materials', {limit: MATERIALS_PAGE_LIMIT})),
        (isWarehouseRole || isFinanceRole) ? getApi('/warehouse-invoices') : Promise.resolve([]),
        (isWarehouseRole || isFinanceRole) ? getApi('/warehouse-main') : Promise.resolve([]),
        (isWarehouseRole || isFinanceRole) ? getApi('/warehouse-movements') : Promise.resolve([]),
	        (isWarehouseRole || isFinanceRole || ['мастер','субподрядчик','бригадир'].includes(role)) ? getApi('/warehouse-history') : Promise.resolve([]),
        (isWarehouseRole || isSupplyRole || isFinanceRole) ? getApi('/warehouses') : Promise.resolve([]),
	        (isWarehouseRole || ['мастер','субподрядчик','бригадир'].includes(role)) ? getApi('/material-transfers') : Promise.resolve([]),
        (canSeeProjectDocs || isWarehouseRole) ? getApi('/material-inspection') : Promise.resolve([]),
        (canSeeProjectDocs || isWarehouseRole) ? getApi('/cable-journal') : Promise.resolve([]),
      ]);
      setMaterials(Array.isArray(m)?m:[]); resetMaterialsPage(m); setInvoices(Array.isArray(winv)?winv:[]);
      setWarehouseMain(Array.isArray(wm)?wm:[]); setWarehouseMovements(Array.isArray(wmov)?wmov:[]);
      setHistory(Array.isArray(h)?h:[]); setWarehouses(Array.isArray(wh)?wh:[]);
      setMaterialTransfers(Array.isArray(mt)?mt:[]); setMaterialInspections(Array.isArray(mij)?mij:[]);
      setCableJournal(Array.isArray(cbj)?cbj:[]);
    });
    if (['supply','suppliers'].includes(page)) return loadMobileScopeOnce('mobile:supply', async () => {
      const [sup,sr,so,sh,sd,sc,supI,scat,stpl] = await Promise.all([
        (isSupplyRole || isWarehouseRole || isFinanceRole) ? getApi('/suppliers') : Promise.resolve([]),
        isSupplyRole ? getApi('/supply-requests') : Promise.resolve([]),
        isSupplyRole ? getApi('/supplier-offers') : Promise.resolve([]),
        (isSupplyRole || isWarehouseRole || isFinanceRole) ? getApi('/supply-history') : Promise.resolve([]),
        isSupplyRole ? getApi('/supply-deliveries') : Promise.resolve([]),
        isSupplyRole ? getApi('/supply-claims') : Promise.resolve([]),
        canSeeSupplierInvoices ? getApi('/supplier-invoices') : Promise.resolve([]),
        (isSupplyRole || isWarehouseRole || isFinanceRole || role === 'поставщик') ? getApi('/supplier-catalog') : Promise.resolve([]),
        isSupplyRole ? getApi('/supply-request-templates') : Promise.resolve([]),
      ]);
      setSuppliers(Array.isArray(sup)?sup:[]); setSupplyRequests(Array.isArray(sr)?sr:[]);
      setSupplierOffers(Array.isArray(so)?so:[]); setSupplyHistory(Array.isArray(sh)?sh:[]);
      setSupplyDeliveries(Array.isArray(sd)?sd:[]); setSupplyClaims(Array.isArray(sc)?sc:[]);
      setSupplierInvoices(Array.isArray(supI)?supI:[]); setSupplierCatalog(Array.isArray(scat)?scat:[]);
      setSupplyTemplates(Array.isArray(stpl)?stpl:[]);
    });
    if (['personnel','users'].includes(page)) return loadMobileScopeOnce('mobile:people', async () => {
      const [s,pw,u,mp,ts,pdc,ic] = await Promise.all([
        (isInternalRole || isFinanceRole) ? getApi('/staff') : Promise.resolve([]),
        (isInternalRole || isFinanceRole) ? getApi('/piecework') : Promise.resolve([]),
        role === 'system_owner' ? Promise.resolve([]) : getApi('/users'),
        (isInternalRole || isFinanceRole) ? getApi('/master-profiles') : Promise.resolve([]),
        (isInternalRole || isFinanceRole) ? getApi('/timesheet') : Promise.resolve([]),
        (isLeadershipRole || isFinanceRole) ? getApi('/pd-consents') : Promise.resolve([]),
        isLeadershipRole ? getApi('/invite-codes') : Promise.resolve([]),
      ]);
      setStaff(Array.isArray(s)?s:[]); setPiecework(Array.isArray(pw)?pw:[]);
      setUsers(Array.isArray(u)?u:[]); setMasterProfiles(Array.isArray(mp)?mp:[]);
      if (Array.isArray(ts)) setTimesheet(Object.fromEntries(ts.map(t=>[t.staffId+'-'+t.day, true])));
      setPdConsents(Array.isArray(pdc)?pdc:[]);
      setInviteCodes(Array.isArray(ic)?ic:[]);
    });
    if (page === 'accounting') return loadMobileScopeOnce('mobile:accounting', async () => {
      const [pp,acp,oe,me,ct,ia,expR,supI,cd,sp,s,pw,u,bc] = await Promise.all([
        isFinanceRole ? getApi('/project-payments') : Promise.resolve([]),
        isFinanceRole ? getApi('/accountable-payments') : Promise.resolve([]),
        isInternalRole ? getApi('/own-expenses') : Promise.resolve([]),
        isFinanceRole ? getApi('/expenses') : Promise.resolve([]),
        (isInternalRole || isFinanceRole) ? getApi('/contracts') : Promise.resolve([]),
        (isInternalRole || isFinanceRole) ? getApi('/interim-acts') : Promise.resolve([]),
        isFinanceRole ? getApi('/expense-reports') : Promise.resolve([]),
        canSeeSupplierInvoices ? getApi('/supplier-invoices') : Promise.resolve([]),
        isFinanceRole ? getApi('/company-documents') : Promise.resolve([]),
        isFinanceRole ? getApi('/salary-payments') : Promise.resolve([]),
        (isInternalRole || isFinanceRole) ? getApi('/staff') : Promise.resolve([]),
        (isInternalRole || isFinanceRole) ? getApi('/piecework') : Promise.resolve([]),
        role === 'system_owner' ? Promise.resolve([]) : getApi('/users'),
        (isInternalRole || isFinanceRole) ? getApi('/brigade-contracts') : Promise.resolve([]),
      ]);
      setProjectPayments(Array.isArray(pp)?pp:[]); setAccountablePayments(Array.isArray(acp)?acp:[]);
      setOwnExpenses(Array.isArray(oe)?oe:[]); setManualExpenses(Array.isArray(me)?me:[]);
      setContracts(Array.isArray(ct)?ct:[]); setInterimActs(Array.isArray(ia)?ia:[]);
      setExpenseReports(Array.isArray(expR)?expR:[]); setSupplierInvoices(Array.isArray(supI)?supI:[]);
      setCompanyDocuments(Array.isArray(cd)?cd:[]); setSalaryPayments(Array.isArray(sp)?sp:[]);
      setStaff(Array.isArray(s)?s:[]); setPiecework(Array.isArray(pw)?pw:[]); setUsers(Array.isArray(u)?u:[]);
      setBrigadeContracts(Array.isArray(bc)?bc:[]);
    });
    if (page === 'history') return loadMobileScopeOnce('mobile:history', async () => {
      const [wj,h,mt] = await Promise.all([
        role === 'поставщик' ? Promise.resolve([]) : getApi(pagedPath('/work-journal', {limit: WORK_JOURNAL_PAGE_LIMIT})),
	        (isWarehouseRole || isFinanceRole || ['мастер','субподрядчик','бригадир'].includes(role)) ? getApi('/warehouse-history') : Promise.resolve([]),
	        (isWarehouseRole || ['мастер','субподрядчик','бригадир'].includes(role)) ? getApi('/material-transfers') : Promise.resolve([]),
      ]);
      setWorkJournal(Array.isArray(wj)?wj:[]);
      resetWorkJournalPage(wj);
      setHistory(Array.isArray(h)?h:[]);
      setMaterialTransfers(Array.isArray(mt)?mt:[]);
    });
    if (page === 'myexpenses') return loadMobileScopeOnce('mobile:myexpenses', async () => {
      const oe = isInternalRole ? await getApi('/own-expenses') : [];
      setOwnExpenses(Array.isArray(oe)?oe:[]);
    });
    if (page === 'clients') return loadMobileScopeOnce('mobile:clients', async () => {
      const c = (isLeadershipRole || role === 'менеджер_crm') ? await getApi('/clients') : [];
      setClients(Array.isArray(c)?c:[]);
    });
    if (page === 'pricelists') return loadMobileScopeOnce('mobile:pricelists', async () => {
      const pl = ((isInternalRole && !['мастер','субподрядчик','бригадир'].includes(role)) || role === 'технадзор') ? await getApi('/pricelists') : [];
      setPricelists(Array.isArray(pl)?pl:[]);
    });
    if (page === 'crm') return loadMobileScopeOnce('mobile:crm', async () => {
      const ls = (isLeadershipRole || role === 'менеджер_crm') ? await getApi('/crm/lead-summaries') : [];
      setLeads(Array.isArray(ls)?ls:[]);
    });
    if (page === 'analytics') return loadMobileScopeOnce('mobile:analytics', async () => {
      const [pp,me,wj,est] = await Promise.all([
        isFinanceRole ? getApi('/project-payments') : Promise.resolve([]),
        isFinanceRole ? getApi('/expenses') : Promise.resolve([]),
        role === 'поставщик' ? Promise.resolve([]) : getApi(pagedPath('/work-journal', {limit: WORK_JOURNAL_PAGE_LIMIT})),
        canLoadEstimates ? getApi(estimatesLoadPath, null) : Promise.resolve(null),
      ]);
      setProjectPayments(Array.isArray(pp)?pp:[]);
      setManualExpenses(Array.isArray(me)?me:[]);
      setWorkJournal(Array.isArray(wj)?wj:[]);
      resetWorkJournalPage(wj);
      applyLoadedEstimates(est);
    });
    if (page === 'settings') return loadMobileScopeOnce('mobile:settings', async () => {
      const [cr,cd] = await Promise.all([
        role === 'поставщик' ? Promise.resolve({}) : getApi('/company-requisites', {}),
        isFinanceRole ? getApi('/company-documents') : Promise.resolve([]),
      ]);
      setCompanyRequisites(cr || {});
      setCompanyDocuments(Array.isArray(cd)?cd:[]);
    });
    if (page === 'activitylog') return loadMobileScopeOnce('mobile:activitylog', async () => {
      const aud = (isLeadershipRole || isFinanceRole) ? await getApi(pagedPath('/audit-log', {limit: AUDIT_LOG_PAGE_LIMIT})) : [];
      setAuditLog(Array.isArray(aud) ? aud : []);
    });
    if (page === 'companychat') return loadMobileScopeOnce('mobile:chat', async () => {
      const msgs = await getApi('/messages');
      setCompanyMessages(Array.isArray(msgs)?msgs:[]);
    });
  };

  useEffect(() => {
    if (!user || !isMobile) return undefined;
    if (!initialDataLoaded) return undefined;
    const run = () => loadMobilePageData(activePage);
    if (typeof window !== 'undefined' && typeof window.requestIdleCallback === 'function') {
      const id = window.requestIdleCallback(run, {timeout: 1200});
      return () => window.cancelIdleCallback?.(id);
    }
    const id = setTimeout(run, 250);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, isMobile, activePage, initialDataLoaded]);

  const loadAll = async () => {
    try {
      const {
        role,
        isLeadershipRole,
        isFinanceRole,
        isWarehouseRole,
        isSupplyRole,
        canSeeSupplierInvoices,
        isInternalRole,
        canSeeProjectDocs,
      } = roleFlagsForUser(user);
      const isWorkerRole = ['мастер','субподрядчик','бригадир'].includes(role);
      const canLoadEstimates = canLoadEstimatesForUser(user);
      const estimatesLoadPath = isWorkerRole ? '/estimates' : '/estimates-summary';
      const token = localStorage.getItem('authToken');
      const get = (path, fallback = []) => fetch(API + path, token ? {headers: {Authorization: 'Bearer ' + token}} : undefined)
        .then(r => {
          if (r.ok) return r.json();
          if (r.status === 401) handleApiUnauthorized();
          return fallback;
        })
        .catch(() => fallback);
      const skip = (fallback = []) => Promise.resolve(fallback);

      const [p,c,m,winv,pp,acp,oe,me,wm,wmov,h,s,pw,u,pl,ic,sup,sr,so,sh,sd,sc,wj,mp,ct,ia,ro,rw,tl,th,inv,pdc,wh,cr,cd,ps,pcl,pres,uw,est,er,bc,hwa,mij,cbj,sva,inspO,expR,supI,warD,scat,stpl,aif,ait,mn,ma,mno,mns,aud] = await Promise.all([
        role === 'поставщик' ? skip([]) : get('/projects'),
        (isLeadershipRole || role === 'менеджер_crm') ? get('/clients') : skip([]),
        role === 'поставщик' ? skip([]) : get(pagedPath('/materials', {limit: MATERIALS_PAGE_LIMIT})),
        (isWarehouseRole || isFinanceRole) ? get('/warehouse-invoices') : skip([]),
        isFinanceRole ? get('/project-payments') : skip([]),
        isFinanceRole ? get('/accountable-payments') : skip([]),
        isInternalRole ? get('/own-expenses') : skip([]),
        isFinanceRole ? get('/expenses') : skip([]),
        (isWarehouseRole || isFinanceRole) ? get('/warehouse-main') : skip([]),
        (isWarehouseRole || isFinanceRole) ? get('/warehouse-movements') : skip([]),
	        (isWarehouseRole || isFinanceRole || ['мастер','субподрядчик','бригадир'].includes(role)) ? get('/warehouse-history') : skip([]),
        (isInternalRole || isFinanceRole) ? get('/staff') : skip([]),
        (isInternalRole || isFinanceRole) ? get('/piecework') : skip([]),
        role === 'system_owner' ? skip([]) : get('/users'),
        ((isInternalRole && !['мастер','субподрядчик','бригадир'].includes(role)) || role === 'технадзор') ? get('/pricelists') : skip([]),
        isLeadershipRole ? get('/invite-codes') : skip([]),
        (isSupplyRole || isWarehouseRole || isFinanceRole) ? get('/suppliers') : skip([]),
        isSupplyRole ? get('/supply-requests') : skip([]),
        isSupplyRole ? get('/supplier-offers') : skip([]),
        (isSupplyRole || isWarehouseRole || isFinanceRole) ? get('/supply-history') : skip([]),
        isSupplyRole ? get('/supply-deliveries') : skip([]),
        isSupplyRole ? get('/supply-claims') : skip([]),
        role === 'поставщик' ? skip([]) : get(pagedPath('/work-journal', {limit: WORK_JOURNAL_PAGE_LIMIT})),
        (isInternalRole || isFinanceRole) ? get('/master-profiles') : skip([]),
        (isInternalRole || isFinanceRole) ? get('/contracts') : skip([]),
        (isInternalRole || isFinanceRole) ? get('/interim-acts') : skip([]),
        canSeeProjectDocs ? get('/rooms') : skip([]),
        canSeeProjectDocs ? get('/room-works') : skip([]),
        isInternalRole ? get('/tools') : skip([]),
        isInternalRole ? get('/tool-history') : skip([]),
        isInternalRole ? get('/inventory') : skip([]),
        (isLeadershipRole || isFinanceRole) ? get('/pd-consents') : skip([]),
        (isWarehouseRole || isSupplyRole || isFinanceRole) ? get('/warehouses') : skip([]),
        role === 'поставщик' ? skip({}) : get('/company-requisites', {}),
        isFinanceRole ? get('/company-documents') : skip([]),
        canSeeProjectDocs ? get('/project-stages') : skip([]),
        canSeeProjectDocs ? get('/project-checklists') : skip([]),
        canSeeProjectDocs ? get('/prescriptions') : skip([]),
        canSeeProjectDocs ? get('/unexpected-works') : skip([]),
        canLoadEstimates ? get(estimatesLoadPath, null) : skip(null),
        canLoadEstimates ? get('/estimate-reconciliations') : skip([]),
        (isInternalRole || isFinanceRole) ? get('/brigade-contracts') : skip([]),
        canSeeProjectDocs ? get('/hidden-works-acts') : skip([]),
        (canSeeProjectDocs || isWarehouseRole) ? get('/material-inspection') : skip([]),
        (canSeeProjectDocs || isWarehouseRole) ? get('/cable-journal') : skip([]),
        canSeeProjectDocs ? get('/supervisor-acts') : skip([]),
        canSeeProjectDocs ? get('/inspection-orders') : skip([]),
        isFinanceRole ? get('/expense-reports') : skip([]),
        canSeeSupplierInvoices ? get('/supplier-invoices') : skip([]),
        canSeeProjectDocs ? get('/warranty-defects') : skip([]),
        (isSupplyRole || isWarehouseRole || isFinanceRole || role === 'поставщик') ? get('/supplier-catalog') : skip([]),
        isSupplyRole ? get('/supply-request-templates') : skip([]),
        canSeeProjectDocs ? get('/ai-findings') : skip([]),
        canSeeProjectDocs ? get('/ai-tasks') : skip([]),
        canSeeProjectDocs ? get(pagedPath('/material-norms', {limit: MATERIAL_NORMS_PAGE_LIMIT})) : skip([]),
        canSeeProjectDocs ? get('/material-aliases') : skip([]),
        canSeeProjectDocs ? get('/material-norms/overrides') : skip([]),
        canSeeProjectDocs ? get('/material-norm-suggestions') : skip([]),
        (isLeadershipRole || isFinanceRole) ? get(pagedPath('/audit-log', {limit: AUDIT_LOG_PAGE_LIMIT})) : skip([]),
      ]);
      setProjects(p);setClients(c);setMaterials(m);resetMaterialsPage(m);setInvoices(Array.isArray(winv)?winv:[]);setProjectPayments(Array.isArray(pp)?pp:[]);setAccountablePayments(Array.isArray(acp)?acp:[]);setOwnExpenses(Array.isArray(oe)?oe:[]);setManualExpenses(Array.isArray(me)?me:[]);setWarehouseMain(wm);setWarehouseMovements(wmov);
      setHistory(h);setStaff(s);setPiecework(pw);setUsers(u);setPricelists(pl);
      setInviteCodes(ic);setSuppliers(sup);setSupplyRequests(sr);setSupplierOffers(so);
      setSupplyHistory(sh);setSupplyDeliveries(Array.isArray(sd)?sd:[]);setSupplyClaims(Array.isArray(sc)?sc:[]);setWorkJournal(wj);resetWorkJournalPage(wj);setMasterProfiles(mp);setContracts(ct);
      setInterimActs(ia);setRooms(ro);setRoomWorks(rw);setTools(tl);setToolHistory(th);
      setInventory(inv);setPdConsents(pdc);setWarehouses(Array.isArray(wh)?wh:[]);
      setCompanyRequisites(cr||{});setCompanyDocuments(Array.isArray(cd)?cd:[]);
      setProjectStages(Array.isArray(ps)?ps:[]);setChecklists(Array.isArray(pcl)?pcl:[]);
      setPrescriptionsList(Array.isArray(pres)?pres:[]);setUnexpectedWorksList(Array.isArray(uw)?uw:[]);applyLoadedEstimates(est);setEstimateReconciliations(Array.isArray(er)?er:[]);setBrigadeContracts(Array.isArray(bc)?bc:[]);setHiddenActs(Array.isArray(hwa)?hwa:[]);setMaterialInspections(Array.isArray(mij)?mij:[]);setCableJournal(Array.isArray(cbj)?cbj:[]);setSupervisorActs(Array.isArray(sva)?sva:[]);setInspectionOrders(Array.isArray(inspO)?inspO:[]);setExpenseReports(Array.isArray(expR)?expR:[]);setSupplierInvoices(Array.isArray(supI)?supI:[]);setWarrantyDefects(Array.isArray(warD)?warD:[]);setSupplierCatalog(Array.isArray(scat)?scat:[]);setSupplyTemplates(Array.isArray(stpl)?stpl:[]);setAiFindings(Array.isArray(aif)?aif:[]);setAiTasks(Array.isArray(ait)?ait:[]);setMaterialNorms(Array.isArray(mn)?mn:[]);resetMaterialNormsPage(mn);setMaterialAliases(Array.isArray(ma)?ma:[]);setMaterialNormOverrides(Array.isArray(mno)?mno:[]);setMaterialNormSuggestions(Array.isArray(mns)?mns:[]);setAuditLog(Array.isArray(aud)?aud:[]);
      if (canSeeProjectDocs) try {
        const [rwin,rdoor] = await Promise.all([
          get('/room-windows'),
          get('/room-doors'),
        ]);
        setRoomWindows(Array.isArray(rwin)?rwin:[]); setRoomDoors(Array.isArray(rdoor)?rdoor:[]);
      } catch(e) {}
      if (isInternalRole || isFinanceRole) try {
        const ts = await get('/timesheet');
        if (Array.isArray(ts)) setTimesheet(Object.fromEntries(ts.map(t=>[t.staffId+'-'+t.day, true])));
      } catch(e) {}
      if (isFinanceRole) try {
        const sp = await get('/salary-payments');
        setSalaryPayments(Array.isArray(sp)?sp:[]);
      } catch(e) {}
      try {
        let ls = await get('/crm/lead-summaries');
        if (!Array.isArray(ls)) ls = [];
        // Одноразовая миграция старых лидов из localStorage в БД
        const oldRaw = localStorage.getItem('leads');
        if (ls.length===0 && oldRaw) {
          try {
            const old = JSON.parse(oldRaw);
            if (Array.isArray(old) && old.length>0) {
              for (const l of old) {
                await fetch(API+'/crm/leads',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:l.name||'',phone:l.phone||'',email:l.email||'',source:l.source||'',budget:Number(l.budget)||0,notes:l.notes||'',stage:l.stage||'Новый',createdBy:l.createdBy||user.name,createdAt:l.createdAt||''})});
              }
              localStorage.removeItem('leads');
              ls = await get('/crm/lead-summaries');
            }
          } catch(_){}
        }
        setLeads(Array.isArray(ls)?ls:[]);
      } catch(e) {}
      try {
        const msgs = await get('/messages');
        setCompanyMessages(Array.isArray(msgs)?msgs:[]);
      } catch(e) {}
      if (isWarehouseRole || ['мастер','субподрядчик','бригадир'].includes(role)) try {
        const mt = await get('/material-transfers');
        setMaterialTransfers(Array.isArray(mt)?mt:[]);
      } catch(e) {}
      if (isInternalRole) try {
        const tb = await get('/tb-journal');
        const tbNorm = (Array.isArray(tb)?tb:[]).map(t=>({...t, project: t.projectName, type: t.instructionType}));
        setTbJournal(tbNorm);
        try { localStorage.setItem('tbJournal', JSON.stringify(tbNorm)); } catch(e){}
      } catch(e) {}
      if (isInternalRole || isFinanceRole || ['мастер','субподрядчик','бригадир'].includes(role)) try {
        const abi = await get('/brigade-contract-items-all');
        setAllBrigadeItems(Array.isArray(abi)?abi:[]);
      } catch(e) {}
      if (isInternalRole || isFinanceRole) try {
        const abp = await get('/brigade-payments');
        setAllBrigadePayments(Array.isArray(abp)?abp:[]);
      } catch(e) {}
      if (isInternalRole || isFinanceRole || role==='заказчик') try {
        const pdocs = await get('/project-documents');
        setProjectDocuments(Array.isArray(pdocs)?pdocs:[]);
        const plet = await get('/project-letters');
        setProjectLetters(Array.isArray(plet)?plet:[]);
      } catch(e) {}
      if (canSeeProjectDocs) try {
        const pmeas = await get('/project-measurements');
        setProjectMeasurements(Array.isArray(pmeas)?pmeas:[]);
        const mdrafts = await get('/measurement-room-drafts');
        setMeasurementRoomDrafts(Array.isArray(mdrafts)?mdrafts:[]);
      } catch(e) {}
      mobileLoadedScopesRef.current.add('full');
    } catch(e) {
      console.error('loadAll failed', e);
    } finally {
      setInitialDataLoaded(true);
    }
  };

  const refreshData = async (page = activePage) => {
    if (!isMobile) {
      await loadAll();
      return;
    }
    mobileApiRequestsRef.current.clear();
    mobileLoadedScopesRef.current.delete('full');
    const scope = mobileScopeForPage(page);
    if (scope) mobileLoadedScopesRef.current.delete(scope);
    if (page === 'dashboard') {
      mobileLoadedScopesRef.current.delete('mobile:init');
      await loadMobileInitial();
    }
    await loadMobilePageData(page);
  };

  // Счётчик непрочитанных сообщений чата для текущего пользователя
  const unreadMessagesCount = (companyMessages||[]).filter(m=>{
    const rb = m.readBy||[];
    return user && !rb.includes(user.id) && (m.author_id!==user.id);
  }).length;

  // Открыть чат-панель и сразу пометить сообщения прочитанными
  const setShowChatPanel = (val) => {
    const next = typeof val === 'function' ? val(showChatPanel) : val;
    setShowChatPanelRaw(next);
    if(next && user && unreadMessagesCount>0){
      fetch(API+'/messages/mark-read',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({userId:user.id,chatType:'company'})})
        .then(()=>setCompanyMessages(prev=>prev.map(m=>({...m,readBy:[...(m.readBy||[]),user.id]}))))
        .catch(()=>{});
    }
  };

  const loadMasterProfile = async () => {
    try {
      const profile = await fetch(API+'/master-profile/'+user.id).then(r=>r.json());
      setMasterProfile(profile);
      if (!profile.profileCompleted) setShowProfileForm(true);
    } catch(e) {}
  };

  const loadPricelistItems = async (plId) => {
    const items = await fetch(API+'/pricelists/'+plId+'/items').then(r=>r.json());
    setPricelistItems(items);
  };

  const loadProjectChat = async (projectName) => {
    try {
      const msgs = await fetch(API+'/project-chat/'+encodeURIComponent(projectName)).then(r=>r.json()).catch(()=>[]);
      setProjectChatMessages(prev=>({...prev,[projectName]:Array.isArray(msgs)?msgs:[]}));
    } catch(e) {}
  };

  const loadChecklistItems = async (checklistId) => {
    try {
      const items = await fetch(API+'/checklist-items/'+checklistId).then(r=>r.json()).catch(()=>[]);
      setChecklistItems(prev=>({...prev,[checklistId]:Array.isArray(items)?items:[]}));
    } catch(e) {}
  };

  const uploadPhoto = async (file, meta={}) => {
    const projectFromExpanded = (projects||[]).find(pr=>String(pr.id)===String(expandedProject))?.name || '';
    const projectFromMaster = (projects||[]).find(pr=>String(pr.id)===String(masterProjectId))?.name || '';
    const projectName = meta.projectName || meta.project || projectFromExpanded || projectFromMaster || '';
    const context = meta.context || activeProjectTab || activePage || 'general';
    const fd = new FormData();
    fd.append('file',file);
    if (projectName) fd.append('projectName',projectName);
    if (context) fd.append('context',context);
    try { const res = await fetch(API+'/upload-photo',{method:'POST',body:fd}); const data = await res.json(); return data.url; } catch { return ''; }
  };

  // Загрузка нескольких фото за раз. Возвращает строку с URL через запятую.
  const uploadMultiplePhotos = async (files, meta={}) => {
    const urls = [];
    for (const f of Array.from(files||[])) {
      const u = await uploadPhoto(f, meta);
      if (u) urls.push(u);
    }
    return urls.join(',');
  };

  // Добавить новые фото к существующему набору (CSV) — для multi-input
  const appendPhotos = async (existing, files, meta={}) => {
    const added = await uploadMultiplePhotos(files, meta);
    if (!added) return existing || '';
    return existing ? existing + ',' + added : added;
  };

  const fileSrc = createFileSrc(API);

  const checkinGeo = () => {
    if (!navigator.geolocation) { alert('Геолокация не поддерживается'); return; }
    navigator.geolocation.getCurrentPosition((pos) => {
      const checkin = {id:Date.now(),userId:user.id,userName:user.name,lat:pos.coords.latitude,lng:pos.coords.longitude,time:new Date().toLocaleString('ru-RU'),date:new Date().toISOString().split('T')[0]};
      const updated = [...geoCheckins,checkin];
      setGeoCheckins(updated); localStorage.setItem('geoCheckins',JSON.stringify(updated));
      alert('Отметка зафиксирована: '+new Date().toLocaleTimeString('ru-RU'));
    }, () => alert('Не удалось получить геолокацию'));
  };

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
  const saveActPayment = async (actId) => {
    if (!newPayment.amount||!newPayment.date) { alert('Заполните сумму и дату'); return; }
    const act = interimActs.find(a=>a.id===actId);
    if (!act) return;
    const amount = Number(newPayment.amount);
    if (!Number.isFinite(amount) || amount <= 0) { alert('Введите сумму оплаты больше нуля'); return; }
    const paymentNote = 'Оплата акта #' + actId + ' · ' + (act.masterName || act.brigadeName || act.performerName || 'исполнитель') + (newPayment.notes ? ' · ' + newPayment.notes : '');
    const payRes = await fetch(API + '/interim-acts/' + actId + '/pay', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        amount,
        note: paymentNote,
        paidDate: newPayment.date,
        paidBy: newPayment.paidBy || user?.name || '',
      }),
    });
    if (!payRes.ok) {
      const err = await payRes.json().catch(()=>({detail:'Не удалось провести оплату акта'}));
      alert(err.detail || 'Не удалось провести оплату акта');
      return;
    }
    const payment = {...newPayment,id:Date.now(),actId,amount};
    const updated = [...actPayments,payment];
    setActPayments(updated); localStorage.setItem('actPayments',JSON.stringify(updated));
    await refreshData();
    setNewPayment({amount:'',paymentType:'Наличный расчёт',paidBy:'',date:'',notes:''});
    setShowPayActModal(null);
  };

  // Ф9.1: оплаты бригаде по договору (частичные, с историей)
  const openBrigadeContract = async (bc) => {
    setSelectedBrigadeContract(bc);
    try {
      const [items, pays] = await Promise.all([
        fetch(API+'/brigade-contract-items/'+bc.id).then(r=>r.json()),
        fetch(API+'/brigade-payments?contract_id='+bc.id).then(r=>r.json()),
      ]);
      setBrigadeContractItems(Array.isArray(items)?items:[]);
      setBrigadePayments(Array.isArray(pays)?pays:[]);
    } catch(_) {}
    if (bc.pricelistId) await loadPricelistItems(bc.pricelistId);
  };
  const saveBrigadePayment = async () => {
    if (!selectedBrigadeContract) return;
    const sum = toNum(newBrigadePayment.amount);
    if (sum<=0) { alert('Введите сумму оплаты'); return; }
    const payRes = await fetch(API+'/brigade-payments',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({contractId:selectedBrigadeContract.id,amount:sum,paidBy:newBrigadePayment.paidBy||user.name,paidDate:newBrigadePayment.paidDate||new Date().toISOString().split('T')[0],note:newBrigadePayment.note||''})});
    if(!payRes.ok){const err=await payRes.json().catch(()=>({detail:'Не удалось записать оплату'}));alert(err.detail||'Не удалось записать оплату');return;}
    const pays = await fetch(API+'/brigade-payments?contract_id='+selectedBrigadeContract.id).then(r=>r.json());
    setBrigadePayments(Array.isArray(pays)?pays:[]);
    setNewBrigadePayment({amount:'',paidBy:'',paidDate:'',note:''});
    setShowBrigadePayModal(false);
    await refreshData();
  };
  const deleteBrigadePayment = async (id) => {
    if (!window.confirm('Удалить эту оплату?')) return;
    await fetch(API+'/brigade-payments/'+id,{method:'DELETE'});
    if (selectedBrigadeContract) {
      const pays = await fetch(API+'/brigade-payments?contract_id='+selectedBrigadeContract.id).then(r=>r.json());
      setBrigadePayments(Array.isArray(pays)?pays:[]);
    }
    await refreshData();
  };

  const saveInvoiceNew = async () => {
    const isScannedInvoice = String(newInvoice.sourceType || '').startsWith('scan_') || Boolean(newInvoice.scanDocumentType || newInvoice.scanWarnings);
    const invoiceNumber = String(newInvoice.number || '').trim() || (isScannedInvoice ? buildScanDraftInvoiceNumber() : '');
    if (!invoiceNumber || newInvoice.items.filter(i=>i.name&&i.quantity).length===0) { alert('Заполните номер накладной и материалы'); return false; }
    if (!newInvoice.location) { alert('Выберите куда оприходовать (основной склад или объект)'); return false; }
    let supplierId = newInvoice.supplierId;
    let resolvedSupplierName = suppliers.find(s=>s.id===Number(supplierId))?.name || '';
    if (newInvoice.isNewSupplier && newInvoice.newSupplierName) {
      const normalizeSupplierName = value => String(value||'')
        .toLowerCase()
        .replace(/ё/g,'е')
        .replace(/(?:,|\s)\s*(инн|кпп|огрн|огрнип|тел\.?|телефон|р\/с|расч[её]тн|адрес)\b.*$/g,' ')
        .replace(/\b(инн|кпп|огрн|огрнип)\s*[:№#-]?\s*\d+\b/g,' ')
        .replace(/\b(ооо|оао|ао|пао|зао|ип|индивидуальный предприниматель)\b/g,' ')
        .replace(/[.,;:()«»"'`/\\]+/g,' ')
        .replace(/\s+/g,' ')
        .trim();
      const existingSupplier = suppliers.find(s=>normalizeSupplierName(s.name)===normalizeSupplierName(newInvoice.newSupplierName));
      if (existingSupplier) {
        supplierId = existingSupplier.id;
        resolvedSupplierName = existingSupplier.name;
      } else {
        const res = await fetch(API+'/suppliers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:newInvoice.newSupplierName,phone:'',email:'',specialization:'',category:'Прочее',rating:5.0,status:'Активный'})});
        if (!res.ok) {
          const err = await res.json().catch(()=>({}));
          alert(err.detail || 'Не удалось сохранить поставщика');
          return false;
        }
        const newSup = await res.json();
        supplierId = newSup.id;
        resolvedSupplierName = newSup.name || newInvoice.newSupplierName;
      }
    }
    const invoiceProject = newInvoice.location !== 'Основной склад' ? newInvoice.location : '';
    const invoicePackages = invoiceProject ? getProjectWorkPackageOptions(invoiceProject) : [];
    const defaultWorkPackage = newInvoice.workPackage || (invoicePackages.length === 1 ? invoicePackages[0] : '');
    const validItems = newInvoice.items
      .filter(i=>i.name&&i.quantity)
      .map(i=>({...i, workPackage:i.workPackage || i.work_package || defaultWorkPackage}));
    const rowsTotal = validItems.reduce((s,i)=>s+(Number(i.lineTotal||0)||Number(i.quantity)*Number(i.price||0)),0);
    const declaredTotal = Number(newInvoice.totalWithVat||0);
    const declaredBase = Number(newInvoice.totalBase||0);
    const declaredVat = Number(newInvoice.totalVat||0);
    const totalBefore = declaredTotal > 0 ? declaredTotal : (declaredBase > 0 && declaredVat > 0 ? declaredBase + declaredVat : rowsTotal);
    const calculatedVat = calcVat(totalBefore, newInvoice.vat);
    const inferredVat = declaredVat > 0 ? declaredVat : (declaredTotal > 0 && declaredBase > 0 ? Math.max(0, declaredTotal - declaredBase) : 0);
    const vatCalc = {
      base: declaredBase > 0 ? declaredBase : calculatedVat.base,
      vat: inferredVat > 0 ? inferredVat : calculatedVat.vat,
      total: totalBefore,
    };
    const photoUrls = Array.isArray(newInvoice.photoUrls) && newInvoice.photoUrls.length ? newInvoice.photoUrls : (Array.isArray(newInvoice.photos) ? newInvoice.photos : []);
    const photoUrl = photoUrls.length > 0 ? photoUrls[0] : (newInvoice.photoUrl || '');
    const warehouseTarget = newInvoice.warehouseTarget || (invoiceProject ? 'object' : 'main');
    const selectedAction = newInvoice.selectedAction || 'receive_to_warehouse';
    const sourceType = newInvoice.sourceType || (invoiceProject ? 'manual_project_invoice' : 'manual_main_invoice');
    const materialMatch = validItems.map((item, index) => ({
      row:index+1,
      name:item.name || '',
      quantity:Number(item.quantity || 0) || 0,
      unit:item.unit || '',
      workPackage:item.workPackage || item.work_package || '',
      estimateMatched:Boolean(item.estimateMaterialId || item.estimateItemId || item.workPackage || item.work_package),
      needsReview:invoiceProject ? !(item.workPackage || item.work_package) : false,
    }));
    const inv = {
      id:Date.now(),
      number:invoiceNumber,
      date:newInvoice.date,
      supplierId:Number(supplierId)||0,
      supplierName:resolvedSupplierName||suppliers.find(s=>s.id===Number(supplierId))?.name||newInvoice.newSupplierName||'',
      acceptedBy:newInvoice.acceptedBy||user.name,
      location:newInvoice.location,
      project:invoiceProject,
      vat:newInvoice.vat,
      photoUrl,
      photos:photoUrls,
      photoUrls,
      pagesCount:newInvoice.pagesCount||photoUrls.length||1,
      items:validItems,
      totalBase:vatCalc.base,
      totalVat:vatCalc.vat,
      totalWithVat:vatCalc.total,
      status:'Принята',
      addedBy:user.name,
      warehouseTarget,
      selectedAction,
      sourceType,
      sourceId:newInvoice.sourceId||null,
      materialMatch
    };
    const savedInv = inv;
    const invoiceRes = await fetch(API+'/warehouse-invoices',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(savedInv)});
    if (!invoiceRes.ok) {
      const err = await invoiceRes.json().catch(()=>({}));
      alert(err.detail || 'Не удалось сохранить накладную');
      return false;
    }
    let reviewTasksCreated = 0;
    try {
      reviewTasksCreated = await createInvoiceControlReviewTasksForInvoice(savedInv);
    } catch (err) {
      console.warn('invoice material review tasks failed', err);
    }
    notify('Накладная №'+invoiceNumber+' принята'+(reviewTasksCreated ? ' · задач ИИ-контроля: '+reviewTasksCreated : ''),'invoice');
    addActivity('Принята накладная №'+invoiceNumber);
    await refreshData();
    setNewInvoice({number:'',date:'',supplierId:'',isNewSupplier:false,newSupplierName:'',acceptedBy:'',location:'Основной склад',project:'',warehouseTarget:'main',selectedAction:'receive_to_warehouse',sourceType:'manual_main_invoice',sourceId:null,vat:'Без НДС',photos:[],photoUrls:[],pagesCount:1,items:[{name:'',quantity:'',unit:'шт',price:'',category:'',workPackage:''}]});
    setShowForm(false);
    alert('Накладная принята!'+(reviewTasksCreated ? '\nСоздано задач ИИ-контроля: '+reviewTasksCreated : ''));
    return true;
  };

  const applyWarehouseMovement = async () => {
    if (!newMovement.toLocation) { alert('Выберите куда переместить'); return; }
    const selected = newMovement.selectedMaterials||[];
    if (selected.length===0) { alert('Выберите материалы'); return; }
    for (const item of selected) {
      if (!item.quantity||Number(item.quantity)<=0) continue;
      const itemWorkPackage = item.workPackage || item.work_package || newMovement.workPackage || '';
      const res = await fetch(API+'/warehouse-movements',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({materialName:item.name,fromLocation:newMovement.fromLocation,toLocation:newMovement.toLocation,quantity:Number(item.quantity),unit:item.unit,workPackage:itemWorkPackage,date:new Date().toISOString().split('T')[0],createdBy:user.name,notes:newMovement.notes})});
      if (!res.ok) {
        const err = await res.json().catch(()=>({}));
        alert(err.detail || 'Не удалось выполнить перемещение материала');
        return;
      }
    }
    notify('Перемещение выполнено','material');
    await refreshData();
    setNewMovement({materialName:'',fromLocation:'Основной склад',toLocation:'',quantity:'',unit:'шт',notes:'',selectedMaterials:[]});
  };

  const findUserForStaff = (st) => findUserForStaffRow(st, users);
  const staffAccessRoles = Object.keys(ROLE_LABELS).filter(r=>!['заказчик','поставщик','system_owner','platform_admin','platform_support','billing_admin','account_owner','account_admin'].includes(r));
  const staffProjectRequiredRoles = ['прораб','технадзор','стройконтроль','мастер','субподрядчик','бригадир'];
  const staffPackageRequiredRoles = ['мастер','субподрядчик','бригадир'];
  const upsertStaffAccess = async ({staffRow={}, fullName, email, password, role, projectName, assignedProjects=[], assignedPackages=[]}) => {
    const cleanEmail = String(email||'').trim().toLowerCase();
    const cleanPassword = String(password||'').trim();
    if (!cleanEmail || !role) throw new Error('Нужны системная роль и email');
    if (!staffAccessRoles.includes(role)) throw new Error('Недопустимая системная роль: '+role);
    const existing = (users||[]).find(u=>String(u.email||'').trim().toLowerCase()===cleanEmail);
    if (!existing && !cleanPassword) throw new Error('Для нового пользователя нужен пароль');
    if (cleanPassword && cleanPassword.length < 5) throw new Error('Пароль минимум 5 символов');
    const project = projectName || staffRow.project || existing?.projectName || existing?.project_name || '';
    const projectRow = (projects||[]).find(p=>String(p.name||'')===String(project||''));
    const payload = {
      name: fullName || staffRow.name || existing?.name || cleanEmail,
      email: cleanEmail,
      password: cleanPassword,
      role,
      projectId: existing?.projectId || existing?.project_id || projectRow?.id || '',
      projectName: project,
      assignedProjects: Array.isArray(assignedProjects) ? assignedProjects : [],
      assignedPackages: Array.isArray(assignedPackages) ? assignedPackages : [],
      active: true
    };
    if (!cleanPassword) delete payload.password;
    let accessUser = existing || null;
    if (existing?.id) {
      await readApiResult(await fetch(API+'/users/'+existing.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}));
      accessUser = {...existing, ...payload};
    } else {
      accessUser = await readApiResult(await fetch(API+'/users',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}));
    }
    const ap = Array.isArray(assignedProjects) ? assignedProjects : [];
    const apk = Array.isArray(assignedPackages) ? assignedPackages : [];
    if (accessUser?.id && (ap.length>0 || apk.length>0 || ['прораб','технадзор','стройконтроль','мастер','субподрядчик','бригадир'].includes(role))) {
      await readApiResult(await fetch(API+'/users/'+accessUser.id+'/assigned-projects',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({assignedProjects:ap,assignedPackages:apk})}));
    }
    return {accessUser, updatedExisting: !!existing};
  };
  const resolveContractPerformer = (contract={}, preferredProfile=null) => resolveContractPerformerRow({
    contract,
    preferredProfile,
    staffRows: staff,
    users,
    masterProfiles,
  });
  const sendCompanyChatMessage = async (text, photoUrl) => {
    if (!text && !photoUrl) return;
    try {
      await fetch(API+'/messages',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({chatType:'company',projectId:null,authorId:user.id,authorName:user.name,authorRole:user.role,text,photoUrl})});
      const msgs = await fetch(API+'/messages').then(r=>r.json()).catch(()=>[]);
      setCompanyMessages(Array.isArray(msgs)?msgs:[]);
    } catch(e) {
      const msg = {id:Date.now(),text,photo_url:photoUrl,author_name:user.name,author_role:user.role,created_at:new Date().toISOString()};
      setCompanyMessages(prev=>[...prev,msg]);
    }
    setCompanyChatMessage('');
  };

  const sendProjectChatMessage = async (projectName, text, photoUrl) => {
    if (!text && !photoUrl) return;
    try {
      await fetch(API+'/project-chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({projectName,authorId:user.id,authorName:user.name,authorRole:user.role,text,photoUrl})});
      await loadProjectChat(projectName);
    } catch(e) {}
    setProjectChatMessage('');
  };

  const saveLead = async (lead) => {
    const body = buildLeadPayload(lead);
    if (lead.id) {
      await fetch(API+'/crm/leads/'+lead.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    } else {
      await fetch(API+'/crm/leads',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(buildLeadPayload(lead, {
        createdBy: user.name,
        createdAt: new Date().toISOString().split('T')[0],
        includeCreateMeta: true,
      }))});
    }
    const ls = await fetch(API+'/crm/lead-summaries').then(r=>r.json());
    setLeads(Array.isArray(ls)?ls:[]);
  };

  const deleteLead = async (id) => { await fetch(API+'/crm/leads/'+id,{method:'DELETE'}); const ls=await fetch(API+'/crm/lead-summaries').then(r=>r.json()); setLeads(Array.isArray(ls)?ls:[]); };
  const createProjectFromLead = async (lead) => {
    if (!lead?.id) return;
    if (lead.projectId) {
      notify('По этой заявке объект уже создан', 'project');
      return;
    }
    const projectName = window.prompt('Название объекта:', lead.name || ('Заявка #'+lead.id));
    if (projectName === null) return;
    const cleanName = String(projectName || '').trim();
    if (!cleanName) return alert('Укажите название объекта');
    const res = await fetch(API+'/crm/leads/'+lead.id+'/create-project', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({projectName:cleanName,budget:Number(lead.budget)||0})
    });
    const data = await res.json().catch(()=>({}));
    if (!res.ok) return alert(data.detail || 'Не удалось создать объект из заявки');
    const [ls, ps] = await Promise.all([
      fetch(API+'/crm/lead-summaries').then(r=>r.json()).catch(()=>[]),
      fetch(API+'/projects').then(r=>r.json()).catch(()=>[])
    ]);
    setLeads(Array.isArray(ls)?ls:[]);
    setProjects(Array.isArray(ps)?ps:[]);
    notify((data.alreadyExists?'Объект уже был создан: ':'Создан объект: ')+(data.project?.name||cleanName), 'project');
  };
  const ratemaster = (masterId, rating) => { const updated={...masterRatings,[masterId]:rating}; setMasterRatings(updated); localStorage.setItem('masterRatings',JSON.stringify(updated)); };
	  const confirmMaterialReceipt = async (transferId) => {
	    await fetch(API+'/material-transfers/'+transferId+'/sign',{method:'PUT'});
	    setMaterialTransfers(prev=>prev.map(t=>t.id===transferId?{...t,signed:true}:t));
	  };
	  const returnMaterialToProject = async (materialRow) => {
	    const maxQty = toNum(materialRow?.quantity);
	    if (!materialRow || maxQty <= 0) return;
	    const raw = window.prompt('Сколько вернуть на склад объекта? Доступно: '+fmtMeasure(maxQty, materialRow.unit), String(maxQty));
	    if (raw === null) return;
	    const qty = toNum(raw);
	    if (!qty || qty <= 0) return alert('Укажите количество больше 0');
	    if (qty > maxQty) return alert('Нельзя вернуть больше остатка: '+fmtMeasure(maxQty, materialRow.unit));
	    const res = await fetch(API+'/material-transfers/return', {
	      method:'POST',
	      headers:{'Content-Type':'application/json'},
	      body:JSON.stringify({
	        projectName: materialRow.project,
	        materialName: materialRow.name,
	        quantity: qty,
	        unit: materialRow.unit,
	        workPackage: materialRow.workPackage || '',
	        date: new Date().toISOString().split('T')[0],
	      })
	    });
	    const data = await res.json().catch(()=>({}));
	    if (!res.ok || !data.ok) return alert('Ошибка: '+(data.detail||data.error||'не удалось вернуть материал'));
	    notify('Материал возвращён на склад объекта: '+materialRow.name+' · '+fmtMeasure(qty, materialRow.unit), 'material');
	    await refreshData();
	  };

  const handleLogout = () => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('user');
    setInitialDataLoaded(false);
    setUser(null);
  };

  const handleLogin = async () => {
    try {
      const res = await fetch(API+'/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:(email||'').trim().toLowerCase(),password:(password||'').trim()})});
      const data = await res.json().catch(()=>({}));
      if (!res.ok) { setLoginError(data.detail || 'Неверный email или пароль'); return null; }
      if (data.twoFactorRequired || data.twoFactorSetupRequired) {
        setLoginError('');
        return data;
      }
      if (!data.authToken) { setLoginError('Сервер не вернул токен входа'); return null; }
      localStorage.setItem('authToken', data.authToken);
      localStorage.setItem('user', JSON.stringify(data));
      setInitialDataLoaded(false);
      setUser(data);
      return data;
    } catch { setLoginError('Ошибка подключения к серверу'); return null; }
  };

  const handleTwoFactorLogin = async ({mode, token, code}) => {
    try {
      const endpoint = mode === 'setup' ? '/login/2fa/setup-confirm' : '/login/2fa/verify';
      const body = mode === 'setup' ? {setupToken: token, code} : {challengeToken: token, code};
      const res = await fetch(API+endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      const data = await res.json();
      if (!res.ok) return {ok:false, error:data.detail || 'Неверный код 2FA'};
      if (data.authToken) localStorage.setItem('authToken', data.authToken);
      localStorage.setItem('user', JSON.stringify(data));
      setInitialDataLoaded(false);
      setUser(data);
      return {ok:true, data};
    } catch {
      return {ok:false, error:'Ошибка подключения к серверу'};
    }
  };

  const handleRegister = async () => {
    if (!regName||!regEmail||!regPassword||!regCode) { setLoginError('Заполните все поля'); return; }
    try {
      const body = {name:regName, email:regEmail, password:regPassword, code:regCode};
      // Если приглашение для поставщика — добавляем расширенные поля
      if (regInviteInfo?.role === 'поставщик') {
        Object.assign(body, regSupplierData);
      }
      const res = await fetch(API+'/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      if (!res.ok) { const err=await res.json(); setLoginError(err.detail); return; }
      const data = await res.json();
      if (data.authToken) localStorage.setItem('authToken', data.authToken);
      localStorage.setItem('user', JSON.stringify(data));
      setInitialDataLoaded(false);
      setUser(data);
    } catch { setLoginError('Ошибка подключения'); }
  };

  // Проверка кода приглашения — показывает расширенную форму для поставщика
  const checkInviteCode = async (code) => {
    if (!code || code.length < 4) { setRegInviteInfo(null); return; }
    try {
      const r = await fetch(API+'/invite-codes/'+encodeURIComponent(code)+'/info');
      const data = await r.json();
      if (data.valid) {
        setRegInviteInfo(data);
        if (data.role === 'поставщик') {
          setRegSupplierData(prev => ({...prev, companyName: data.presetName||'', category: data.presetCategory||''}));
        }
      } else {
        setRegInviteInfo(null);
      }
    } catch(_) { setRegInviteInfo(null); }
  };

  // Авто-проверка при изменении кода (debounce 400 мс)
  useEffect(() => {
    if (!regCode) { setRegInviteInfo(null); return; }
    const t = setTimeout(()=>{ checkInviteCode(regCode); }, 400);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [regCode]);

  const saveProfile = async () => {
    if (!profileData.fullName||!profileData.inn||!profileData.bankAccount) { alert('Заполните обязательные поля'); return; }
    if (!consentChecked) { alert('Необходимо согласие на обработку ПД'); return; }
    const res = await fetch(API+'/master-profile',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...profileData,userId:user.id})});
    setMasterProfile(await res.json()); setShowProfileForm(false);
    await fetch(API+'/pd-consents',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({userId:user.id,signedAt:new Date().toLocaleString('ru-RU'),scanUrl:'',uploadedBy:user.name})});
    await refreshData();
  };

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
  const estimateChangeTypeForComparisonRow = (row) => row?.status==='Сверх сметы'
    ? 'Дополнительный объём к строке сметы'
    : row?.status==='В смете больше'
      ? 'Исключение объёма'
      : '';
  const estimateChangeForComparisonRow = (projectName, row) => {
    const changeType = estimateChangeTypeForComparisonRow(row);
    if (!changeType) return null;
    return (unexpectedWorksList||[]).find(u=>
      u.projectName===projectName &&
      u.changeType===changeType &&
      Number(u.estimateId||0)===Number(row.estimateId||0) &&
      (u.sectionName||'')===(row.sectionName||'') &&
      (u.estimateItemName||'')===(row.itemName||'') &&
      !['Отклонено','Включено в новую смету'].includes(u.status||'')
    ) || null;
  };
  const createEstimateChangeFromComparisonRow = async (project, row) => {
    const changeType = estimateChangeTypeForComparisonRow(row);
    if (!project || !changeType) return;
    const existing = estimateChangeForComparisonRow(project.name, row);
    if (existing) {
      alert('Изменение по этой строке уже оформлено: '+(existing.status||''));
      setActiveProjectTab('Изменения к смете');
      setActiveTabGroup('work');
      return;
    }
    const unit = row.expectedUnit || row.planUnit || '';
    const deltaQty = row.status==='Сверх сметы' ? toNum(row.overQty) : toNum(row.shortageQty);
    if (deltaQty<=0) return;
    const price = toNum(row.price);
    const total = deltaQty * price;
    const reason = row.status==='Сверх сметы'
      ? 'По обмеру помещений требуется больше, чем указано в активной смете: '+fmtMeasure(row.measuredQty, unit)+' против '+fmtMeasure(row.planQty, row.planUnit)+'.'
      : 'По обмеру помещений требуется меньше, чем указано в активной смете: '+fmtMeasure(row.measuredQty, unit)+' против '+fmtMeasure(row.planQty, row.planUnit)+'.';
    const payload = {
      projectName: project.name,
      description: row.itemName,
      unit,
      quantity: deltaQty,
      price,
      total,
      addedBy: user.name,
      addedByRole: user.role,
      status: 'Ожидает согласования',
      notes: 'Создано из панели «Смета ↔ обмеры помещений». Основание: '+row.basisLabel+'.',
      changeType,
      estimateId: row.estimateId,
      sectionName: row.sectionName,
      estimateItemName: row.itemName,
      baseQuantity: row.planQty,
      newRequiredQuantity: row.measuredQty,
      deltaQuantity: deltaQty,
      reason
    };
    const res = await fetch(API+'/unexpected-works',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    if (!res.ok) {
      const data = await res.json().catch(()=>({}));
      alert(data.detail||'Не удалось оформить изменение');
      return;
    }
    notify('Оформлено изменение к смете: '+row.itemName,'unexpected');
    await refreshData();
    setActiveProjectTab('Изменения к смете');
    setActiveTabGroup('work');
    setShowForm(false);
  };
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
  const setEstimateStatusRemote = async (est, status) => {
    if(!est?.id) return;
    const diffBase = status==='Активная'
      ? activeEstimateFromList((estimatesList||[]).filter(e=>!isGlobalEstimateTemplate(e) && e.id!==est.id && sameEstimateGroup(e,est) && e.status==='Активная'))
      : null;
    const res = await fetch(API+'/estimates/'+est.id+'/status',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status})});
    if(!res.ok){const data=await res.json().catch(()=>({}));alert(data.detail||'Не удалось изменить статус сметы');return;}
    const updated = {...est,status};
    const nextEstimates = applyEstimateActivationState((estimatesList||[]).map(e=>e.id===est.id?updated:e), updated);
    setEstimatesList(nextEstimates);
    setSelectedEstimate(prev=>prev&&prev.id===est.id?updated:prev);
    if (status==='Активная') {
      if (diffBase) {
        await queueEstimateDiffReviewTask(diffBase, updated, 'Смета активирована');
        await autoReconcileEstimateChanges(diffBase, updated, 'Смета активирована');
      }
      await queueEstimateQualityReviewTask(updated, 'Смета активирована');
      await queueEstimateNormReviewTask(updated, 'Смета активирована', nextEstimates);
    }
  };
  const deleteEstimateRemote = async (est) => {
    if (!est?.id) return;
    const title = est.name || 'смету';
    if (!window.confirm('Удалить смету "' + title + '" безвозвратно? Это действие доступно только директору. Если смета уже связана с ЖПР, АОСР, договорными позициями или материалами, сервер не даст удалить ее, чтобы не потерять историю объекта.')) return;
    const res = await fetch(API + '/estimates/' + est.id + '?hard=true', {method: 'DELETE'});
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      alert(data.detail || 'Не удалось удалить смету');
      return;
    }
    setEstimatesList(prev => (prev || []).filter(e => e.id !== est.id));
    setSelectedEstimate(prev => prev && prev.id === est.id ? null : prev);
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
  const includeChangesInNewEstimate = async (project, est, rows) => {
    if (!project || !est || !rows?.length) return;
    const signedTotal = signedEstimateChangeTotal(rows);
    const msg = 'Создать новую активную версию сметы "'+(est.name||'')+'" и включить изменений: '+rows.length+' на '+(signedTotal>0?'+':'')+Math.round(signedTotal).toLocaleString('ru-RU')+' ₽?\n\nСтарая смета уйдёт в архив, изменения получат статус "Включено в новую смету" и не будут идти в КС отдельными строками.';
    if (!window.confirm(msg)) return;
    const res = await fetch(API+'/estimates/'+est.id+'/include-changes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({changeIds:rows.map(u=>u.id),updatedBy:user.name})});
    const data = await res.json().catch(()=>({}));
    if (!res.ok) {
      alert(data.detail || 'Не удалось включить изменения в смету');
      return;
    }
    await refreshData();
    const next = data.estimate || null;
    if (next) {
      setSelectedEstimate(next);
      setActivePage('estimates');
      setEstimatesTab('list');
    }
    notify('Создана новая версия сметы: '+(next?.name||''),'estimate');
  };
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
  const aiTaskByMarker = (marker) => (aiTasks||[]).find(t=>
    isOpenAiStatus(t.status) && String(t.actionPayload||'').includes(marker)
  );
  const jumpToEstimateIssue = (row) => {
    if (!row || row.sectionIdx === undefined || row.itemIdx === undefined) return;
    const key = estimateIssueDomId(row.estimateId || selectedEstimate?.id, row.sectionIdx, row.itemIdx);
    setEstimateIssueFocusKey(key);
    setTimeout(() => {
      const el = document.getElementById(key);
      if (el) el.scrollIntoView({behavior:'smooth', block:'center'});
    }, 30);
    setTimeout(() => setEstimateIssueFocusKey(prev => prev === key ? '' : prev), 4500);
  };
  const queueEstimateQualityReviewTask = async (est, reason='Автопроверка сметы') => {
    if (!est?.id || !est.projectName) return;
    if (estimateKind(est)!=='Заказчик' || isArchivedEstimate(est) || (est.status||'Черновик')!=='Активная') return;
    const marker = estimateQualityReviewMarker(est.id);
    const existingTask = aiTaskByMarker(marker);
    const rows = estimateQualityRows(est);
    const counts = rows.reduce((acc,row)=>{acc[row.status]=(acc[row.status]||0)+1;return acc;},{});
    if (existingTask) {
      if (!rows.length) {
        await patchAiTaskSilent(existingTask.id,{status:'Закрыто'});
        return;
      }
      await patchAiTaskSilent(existingTask.id,{
        title:'Исправить данные сметы: '+est.projectName+' — '+rows.length+' ош.',
        description:estimateQualityDescription(est, rows, reason),
        assignedRole:hasActiveEstimator() ? 'сметчик' : 'директор',
        actionPayload:JSON.stringify({
          type:'estimate_quality_review',
          marker,
          estimateId:est.id,
          estimateName:est.name||'',
          projectName:est.projectName||'',
          workPackage:estimatePackage(est),
          reason,
          counts
        }),
      });
      return;
    }
    if (!rows.length || estimateQualityReviewQueuedRef.current.has(marker)) return;
    estimateQualityReviewQueuedRef.current.add(marker);
    const payload = {
      projectName: est.projectName,
      title:'Исправить данные сметы: '+est.projectName+' — '+rows.length+' ош.',
      description:estimateQualityDescription(est, rows, reason),
      assignedRole:hasActiveEstimator() ? 'сметчик' : 'директор',
      status:'Новое',
      actionLabel:'Открыть смету',
      actionPayload:JSON.stringify({
        type:'estimate_quality_review',
        marker,
        estimateId:est.id,
        estimateName:est.name||'',
        projectName:est.projectName||'',
        workPackage:estimatePackage(est),
        reason,
        counts
      }),
    };
    try {
      const res = await fetch(API+'/ai-tasks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      const data = await res.json().catch(()=>({}));
      if (!res.ok) {
        estimateQualityReviewQueuedRef.current.delete(marker);
        return;
      }
      setAiTasks(prev=>{
        const list = prev||[];
        if (data?.id && list.some(t=>Number(t.id)===Number(data.id))) {
          return list.map(t=>Number(t.id)===Number(data.id)?data:t);
        }
        return [data,...list];
      });
    } catch(e) {
      estimateQualityReviewQueuedRef.current.delete(marker);
    }
  };
  const estimateListWithUpdatedEstimate = (est) => {
    if (!est?.id) return estimatesList||[];
    let found = false;
    const mapped = (estimatesList||[]).map(e=>{
      if (Number(e.id)===Number(est.id)) { found = true; return est; }
      return e;
    });
    return found ? mapped : [...mapped, est];
  };
  const hasActiveEstimator = () => {
    const roleOf = (v) => String(v||'').trim().toLowerCase();
    return (users||[]).some(u=>roleOf(u.role)==='сметчик')
      || (staff||[]).some(s=>roleOf(s.systemRole||s.role)==='сметчик' && roleOf(s.status||'активен')!=='уволен');
  };
  const estimateNormReviewExistingTask = (marker) => aiTaskByMarker(marker);
  const queueEstimateDiffReviewTask = async (baseEst, nextEst, reason='Новая смета') => {
    if (!baseEst?.id || !nextEst?.id || Number(baseEst.id)===Number(nextEst.id)) return;
    if (!sameEstimateGroup(baseEst,nextEst) || isGlobalEstimateTemplate(nextEst) || (nextEst.status||'Черновик')!=='Активная') return;
    const diff = buildEstimateDiff(baseEst,nextEst);
    const changeCount = diff.changed.length + diff.added.length + diff.removed.length;
    const marker = estimateDiffReviewMarker(baseEst.id,nextEst.id);
    const existingTask = aiTaskByMarker(marker);
    if (existingTask) {
      if (!changeCount) {
        await patchAiTaskSilent(existingTask.id,{status:'Закрыто'});
        return;
      }
      await patchAiTaskSilent(existingTask.id,{
        title:'Сверить разницу смет: '+(nextEst.projectName||baseEst.projectName||'')+' — '+changeCount+' изм.',
        description:estimateDiffReviewDescription(baseEst,nextEst,diff,reason),
        assignedRole:hasActiveEstimator() ? 'сметчик' : 'директор',
        actionPayload:JSON.stringify({
          type:'estimate_diff_review',
          marker,
          baseEstimateId:baseEst.id,
          nextEstimateId:nextEst.id,
          projectName:nextEst.projectName||baseEst.projectName||'',
          workPackage:estimatePackage(nextEst),
          reason,
          changed:diff.changed.length,
          added:diff.added.length,
          removed:diff.removed.length,
          impact:diff.impact
        }),
      });
      return;
    }
    if (!changeCount || estimateDiffReviewQueuedRef.current.has(marker)) return;
    estimateDiffReviewQueuedRef.current.add(marker);
    const payload = {
      projectName: nextEst.projectName || baseEst.projectName || '',
      title:'Сверить разницу смет: '+(nextEst.projectName||baseEst.projectName||'')+' — '+changeCount+' изм.',
      description:estimateDiffReviewDescription(baseEst,nextEst,diff,reason),
      assignedRole:hasActiveEstimator() ? 'сметчик' : 'директор',
      status:'Новое',
      actionLabel:'Открыть ведомость смет',
      actionPayload:JSON.stringify({
        type:'estimate_diff_review',
        marker,
        baseEstimateId:baseEst.id,
        nextEstimateId:nextEst.id,
        projectName:nextEst.projectName||baseEst.projectName||'',
        workPackage:estimatePackage(nextEst),
        reason,
        changed:diff.changed.length,
        added:diff.added.length,
        removed:diff.removed.length,
        impact:diff.impact
      }),
    };
    try {
      const res = await fetch(API+'/ai-tasks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      const data = await res.json().catch(()=>({}));
      if (!res.ok) {
        estimateDiffReviewQueuedRef.current.delete(marker);
        return;
      }
      setAiTasks(prev=>{
        const list = prev||[];
        if (data?.id && list.some(t=>Number(t.id)===Number(data.id))) {
          return list.map(t=>Number(t.id)===Number(data.id)?data:t);
        }
        return [data,...list];
      });
    } catch(e) {
      estimateDiffReviewQueuedRef.current.delete(marker);
    }
  };
  const autoReconcileEstimateChanges = async (baseEst, nextEst, reason='Новая смета') => {
    if (!baseEst?.id || !nextEst?.id || Number(baseEst.id)===Number(nextEst.id)) return;
    if (!sameEstimateGroup(baseEst,nextEst) || isGlobalEstimateTemplate(nextEst) || estimateKind(nextEst)!=='Заказчик' || (nextEst.status||'Черновик')!=='Активная') return;
    const marker = estimateChangeReconcileMarker(nextEst.id);
    const candidates = includableEstimateChanges(nextEst.projectName || baseEst.projectName || '');
    const existingTask = aiTaskByMarker(marker);
    if (!candidates.length) {
      if (existingTask) await patchAiTaskSilent(existingTask.id,{status:'Закрыто'});
      return;
    }
    const diff = buildEstimateDiff(baseEst,nextEst);
    const decisions = candidates.map(change=>estimateChangeAutoDecision(change,nextEst,diff));
    const autoIds = decisions.filter(d=>d.autoInclude).map(d=>Number(d.change.id)).filter(Boolean);
    let includedIds = [];
    if (autoIds.length) {
      try {
        const res = await fetch(API+'/estimates/'+nextEst.id+'/reconcile-changes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({changeIds:autoIds,updatedBy:user.name})});
        const data = await res.json().catch(()=>({}));
        if (res.ok) {
          includedIds = (data.includedChangeIds||[]).map(Number);
          if (includedIds.length) {
            const includedSet = new Set(includedIds);
            setUnexpectedWorksList(prev=>(prev||[]).map(u=>includedSet.has(Number(u.id))?{...u,status:'Включено в новую смету',includedInEstimateId:nextEst.id,reason:u.reason||('Автоматически сопоставлено с новой сметой №'+nextEst.id)}:u));
          }
        }
      } catch(e) {}
    }
    const includedSet = new Set(includedIds);
    const unresolved = decisions.filter(d=>!includedSet.has(Number(d.change.id)));
    if (!unresolved.length) {
      if (existingTask) await patchAiTaskSilent(existingTask.id,{status:'Закрыто'});
      return;
    }
    const payloadData = {
      type:'estimate_change_reconcile',
      marker,
      baseEstimateId:baseEst.id,
      nextEstimateId:nextEst.id,
      projectName:nextEst.projectName||baseEst.projectName||'',
      workPackage:estimatePackage(nextEst),
      reason,
      included:includedIds.length,
      unresolved:unresolved.length
    };
    const patch = {
      title:'Проверить включение допработ: '+(nextEst.projectName||baseEst.projectName||'')+' — '+unresolved.length+' спорн.',
      description:estimateChangeReconcileDescription(baseEst,nextEst,unresolved,includedIds.length,reason),
      assignedRole:hasActiveEstimator() ? 'сметчик' : 'директор',
      actionPayload:JSON.stringify(payloadData),
    };
    if (existingTask) {
      await patchAiTaskSilent(existingTask.id,patch);
      return;
    }
    if (estimateChangeReconcileQueuedRef.current.has(marker)) return;
    estimateChangeReconcileQueuedRef.current.add(marker);
    try {
      const res = await fetch(API+'/ai-tasks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
        projectName:nextEst.projectName||baseEst.projectName||'',
        ...patch,
        status:'Новое',
        actionLabel:'Открыть изменения к смете',
      })});
      const data = await res.json().catch(()=>({}));
      if (!res.ok) {
        estimateChangeReconcileQueuedRef.current.delete(marker);
        return;
      }
      setAiTasks(prev=>{
        const list = prev||[];
        if (data?.id && list.some(t=>Number(t.id)===Number(data.id))) {
          return list.map(t=>Number(t.id)===Number(data.id)?data:t);
        }
        return [data,...list];
      });
    } catch(e) {
      estimateChangeReconcileQueuedRef.current.delete(marker);
    }
  };
  const estimateChangeReconcileRowsForTask = (task) => {
    const payload = parseAiTaskPayload(task);
    if (payload.type !== 'estimate_change_reconcile') return [];
    const nextEst = (estimatesList||[]).find(e=>Number(e.id)===Number(payload.nextEstimateId));
    const baseEst = (estimatesList||[]).find(e=>Number(e.id)===Number(payload.baseEstimateId)) || (nextEst ? estimateDiffBaseFor(nextEst) : null);
    if (!baseEst || !nextEst) return [];
    const diff = buildEstimateDiff(baseEst,nextEst);
    const projectName = payload.projectName || task.projectName || nextEst.projectName || baseEst.projectName || '';
    return includableEstimateChanges(projectName).map(change=>estimateChangeAutoDecision(change,nextEst,diff));
  };
  const confirmEstimateChangeIncluded = async (task, decision) => {
    const payload = parseAiTaskPayload(task);
    const changeId = Number(decision?.change?.id);
    const estimateId = Number(payload.nextEstimateId);
    if (!changeId || !estimateId) return;
    const res = await fetch(API+'/estimates/'+estimateId+'/reconcile-changes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({changeIds:[changeId],updatedBy:user.name})});
    const data = await res.json().catch(()=>({}));
    if (!res.ok) {
      alert(data.detail || 'Не удалось включить изменение в новую смету');
      return;
    }
    const included = new Set((data.includedChangeIds||[]).map(Number));
    if (included.size) {
      setUnexpectedWorksList(prev=>(prev||[]).map(u=>included.has(Number(u.id))?{...u,status:'Включено в новую смету',includedInEstimateId:estimateId,reason:u.reason||('Подтверждено при сверке с новой сметой №'+estimateId)}:u));
      const remaining = estimateChangeReconcileRowsForTask(task).filter(r=>Number(r.change?.id)!==changeId);
      if (remaining.length === 0 && task?.id) await patchAiTaskSilent(task.id,{status:'Закрыто'});
    }
  };
  const renderEstimateChangeReconcileTask = (task) => {
    const payload = parseAiTaskPayload(task);
    const nextEst = (estimatesList||[]).find(e=>Number(e.id)===Number(payload.nextEstimateId));
    const baseEst = (estimatesList||[]).find(e=>Number(e.id)===Number(payload.baseEstimateId)) || (nextEst ? estimateDiffBaseFor(nextEst) : null);
    const rows = estimateChangeReconcileRowsForTask(task);
    const scoreLabel = (score) => score ? Math.round(score*100)+'%' : '—';
    return (
      <div style={{marginTop:'10px',padding:'10px',borderRadius:'10px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border}}>
        <div style={{display:'flex',justifyContent:'space-between',gap:'8px',flexWrap:'wrap',marginBottom:'8px'}}>
          <div>
            <b style={{color:C.text,fontSize:'12px'}}>Сверка изменений с новой сметой</b>
            <p style={{color:C.textSec,fontSize:'11px',margin:'2px 0 0'}}>{(baseEst?.name||'База')+' → '+(nextEst?.name||'Новая смета')}</p>
          </div>
          <span style={badge(rows.length?C.warning:C.success,rows.length?C.warningLight:C.successLight,rows.length?C.warningBorder:C.successBorder)}>{rows.length?rows.length+' на проверке':'закрыто'}</span>
        </div>
        {rows.length===0?<p style={{color:C.success,fontSize:'12px',margin:0}}>Спорных изменений не осталось.</p>:(
          <div style={{overflowX:'auto'}}>
            <table style={{...tbl,fontSize:'12px'}}>
              <thead><tr><th style={tblH}>Изменение</th><th style={tblH}>Кандидат в новой смете</th><th style={tblH}>Причина</th><th style={tblH}>Увер.</th><th style={tblH}></th></tr></thead>
              <tbody>{rows.map(d=>{
                const u=d.change||{};
                const c=d.candidate||null;
                return (<tr key={u.id}>
                  <td style={{...tblC,minWidth:'220px'}}>
                    <b style={{display:'block',color:C.text,fontSize:'12px'}}>{u.estimateItemName||u.description||'Изменение'}</b>
                    <span style={{color:C.textSec,fontSize:'11px'}}>{(u.changeType||'')+' · '+fmtMeasure(u.deltaQuantity||u.quantity,u.unit)}</span>
                  </td>
                  <td style={{...tblC,minWidth:'240px'}}>
                    {c?<><b style={{display:'block',color:C.text,fontSize:'12px'}}>{c.name}</b><span style={{color:C.textSec,fontSize:'11px'}}>{(c.section||'')+' · '+fmtMeasure(c.qty,c.unit)+' · '+Math.round(c.sum||0).toLocaleString('ru-RU')+' ₽'}</span></>:<span style={{color:C.textMuted}}>Не найден</span>}
                  </td>
                  <td style={{...tblC,color:d.autoInclude?C.success:C.warning,fontWeight:'600',minWidth:'180px'}}>{d.reason||'Нужно проверить'}</td>
                  <td style={tblC}>{scoreLabel(d.score)}</td>
                  <td style={tblC}>
                    <div style={{display:'flex',gap:'5px',justifyContent:'flex-end',flexWrap:'wrap'}}>
                      {c&&<button onClick={()=>confirmEstimateChangeIncluded(task,d)} style={{...btnGr,padding:'4px 8px',fontSize:'11px'}}><Check size={11}/>Включить</button>}
                      <button onClick={()=>openAiTaskAction(task)} style={{...btnB,padding:'4px 8px',fontSize:'11px'}}><Eye size={11}/>Открыть</button>
                    </div>
                  </td>
                </tr>);
              })}</tbody>
            </table>
          </div>
        )}
      </div>
    );
  };
  const queueEstimateNormReviewTask = async (est, reason='Автопроверка сметы', sourceEstimates=null) => {
    if (!est?.id || !est.projectName) return;
    if (estimateKind(est)!=='Заказчик' || isArchivedEstimate(est) || (est.status||'Черновик')!=='Активная') return;
    const marker = estimateNormReviewMarker(est.id);
    const existingTask = estimateNormReviewExistingTask(marker);
    const rows = estimateNormCoverageRows(est.projectName, sourceEstimates)
      .filter(r=>Number(r.estimateId)===Number(est.id) && estimateNormReviewIssueStatuses.includes(r.status));
    const counts = estimateNormReviewIssueStatuses.reduce((acc,status)=>{
      const count = rows.filter(r=>r.status===status).length;
      if (count) acc[status] = count;
      return acc;
    }, {});
    if (existingTask) {
      if (!rows.length) {
        await patchAiTaskSilent(existingTask.id,{status:'Закрыто'});
        return;
      }
      await patchAiTaskSilent(existingTask.id,{
        title:'Проверить смету: '+est.projectName+' — '+rows.length+' замеч.',
        description:estimateNormReviewDescription(est, rows, reason),
        assignedRole:hasActiveEstimator() ? 'сметчик' : 'директор',
        actionPayload:JSON.stringify({
          type:'estimate_norm_review',
          marker,
          estimateId:est.id,
          estimateName:est.name||'',
          projectName:est.projectName||'',
          workPackage:estimatePackage(est),
          reason,
          counts
        }),
      });
      return;
    }
    if (!rows.length || estimateNormReviewQueuedRef.current.has(marker)) return;
    estimateNormReviewQueuedRef.current.add(marker);
    const payload = {
      projectName: est.projectName,
      title: 'Проверить смету: '+est.projectName+' — '+rows.length+' замеч.',
      description: estimateNormReviewDescription(est, rows, reason),
      assignedRole: hasActiveEstimator() ? 'сметчик' : 'директор',
      status: 'Новое',
      actionLabel: 'Открыть проверку сметы',
      actionPayload: JSON.stringify({
        type:'estimate_norm_review',
        marker,
        estimateId:est.id,
        estimateName:est.name||'',
        projectName:est.projectName||'',
        workPackage:estimatePackage(est),
        reason,
        counts
      }),
    };
    try {
      const res = await fetch(API+'/ai-tasks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      const data = await res.json().catch(()=>({}));
      if (!res.ok) {
        estimateNormReviewQueuedRef.current.delete(marker);
        return;
      }
      setAiTasks(prev=>{
        const list = prev||[];
        if (data?.id && list.some(t=>Number(t.id)===Number(data.id))) {
          return list.map(t=>Number(t.id)===Number(data.id)?data:t);
        }
        return [data,...list];
      });
    } catch(e) {
      estimateNormReviewQueuedRef.current.delete(marker);
    }
  };
  const materialControlTaskDescriptorsForProject = (projectName, reason='Фоновая проверка материалов') => buildMaterialControlTaskDescriptorsForProject({
    projectName,
    reason,
    materialControlSummaryForProject,
    materialNormControlSummaryForProject,
    materialNameKey,
    materialAliasCandidates,
    hasActiveEstimator,
  });
  const materialControlSignatureForProject = (projectName) => buildMaterialControlSignatureForProject({
    projectName,
    materialControlSummaryForProject,
    materialNormControlSummaryForProject,
  });
  const roomControlTaskDescriptorsForProject = (projectName, reason='Фоновая проверка помещений') => buildRoomControlTaskDescriptorsForProject({
    projectName,
    reason,
    rooms,
    roomWorks,
    workJournal,
    roomCompleteness,
    materialNameKey,
  });
  const roomControlSignatureForProject = (projectName) => buildRoomControlSignatureForProject({
    projectName,
    rooms,
    roomWorks,
    workJournal,
    roomCompleteness,
    materialNameKey,
  });
  const queueMaterialControlTask = async (descriptor) => {
    if (!descriptor?.marker || !descriptor.projectName) return;
    const existingTask = aiTaskByMarker(descriptor.marker);
    const patch = {
      title: descriptor.title,
      description: descriptor.description,
      assignedRole: descriptor.assignedRole,
      actionLabel: descriptor.actionLabel,
      actionPayload: JSON.stringify(descriptor.actionPayload),
    };
    if (existingTask) {
      await patchAiTaskSilent(existingTask.id, patch);
      return;
    }
    if (materialControlTaskQueuedRef.current.has(descriptor.marker)) return;
    materialControlTaskQueuedRef.current.add(descriptor.marker);
    try {
      const res = await fetch(API+'/ai-tasks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
        projectName: descriptor.projectName,
        ...patch,
        status:'Новое',
      })});
      const data = await res.json().catch(()=>({}));
      if (!res.ok) {
        materialControlTaskQueuedRef.current.delete(descriptor.marker);
        return;
      }
      setAiTasks(prev=>{
        const list = prev||[];
        if (data?.id && list.some(t=>Number(t.id)===Number(data.id))) {
          return list.map(t=>Number(t.id)===Number(data.id)?data:t);
        }
        return [data,...list];
      });
    } catch(e) {
      materialControlTaskQueuedRef.current.delete(descriptor.marker);
    }
  };
  const queueMaterialControlTasksForProject = async (projectName, reason='Фоновая проверка материалов') => {
    const descriptors = materialControlTaskDescriptorsForProject(projectName, reason);
    const activeMarkers = new Set(descriptors.map(d=>d.marker));
    const openMaterialTasks = (aiTasks||[]).filter(t=>{
      if (!isOpenAiStatus(t.status)) return false;
      const payload = parseAiTaskPayload(t);
      return String(payload.marker||'').startsWith('MATERIAL_CONTROL:')
        && (payload.projectName || t.projectName || '') === projectName;
    });
    openMaterialTasks.forEach(t=>{
      const payload = parseAiTaskPayload(t);
      if (payload.marker && !activeMarkers.has(payload.marker)) patchAiTaskSilent(t.id,{status:'Закрыто'});
    });
    for (const descriptor of descriptors) {
      await queueMaterialControlTask(descriptor);
    }
  };
  const queueRoomControlTask = async (descriptor) => {
    if (!descriptor?.marker || !descriptor.projectName) return;
    const existingTask = aiTaskByMarker(descriptor.marker);
    const patch = {
      title: descriptor.title,
      description: descriptor.description,
      assignedRole: descriptor.assignedRole,
      actionLabel: descriptor.actionLabel,
      actionPayload: JSON.stringify(descriptor.actionPayload),
    };
    if (existingTask) {
      await patchAiTaskSilent(existingTask.id, patch);
      return;
    }
    if (roomControlTaskQueuedRef.current.has(descriptor.marker)) return;
    roomControlTaskQueuedRef.current.add(descriptor.marker);
    try {
      const res = await fetch(API+'/ai-tasks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
        projectName: descriptor.projectName,
        ...patch,
        status:'Новое',
      })});
      const data = await res.json().catch(()=>({}));
      if (!res.ok) {
        roomControlTaskQueuedRef.current.delete(descriptor.marker);
        return;
      }
      setAiTasks(prev=>{
        const list = prev||[];
        if (data?.id && list.some(t=>Number(t.id)===Number(data.id))) {
          return list.map(t=>Number(t.id)===Number(data.id)?data:t);
        }
        return [data,...list];
      });
    } catch(e) {
      roomControlTaskQueuedRef.current.delete(descriptor.marker);
    }
  };
  const queueRoomControlTasksForProject = async (projectName, reason='Фоновая проверка помещений') => {
    const descriptors = roomControlTaskDescriptorsForProject(projectName, reason);
    const activeMarkers = new Set(descriptors.map(d=>d.marker));
    const isLegacyRoomBinding = (item) => {
      const dedupe = String(item?.dedupeKey || item?.dedupe_key || '');
      const payload = String(item?.actionPayload || item?.action_payload || '');
      return (dedupe.startsWith('work_journal:') && dedupe.endsWith(':room_binding')) || payload.includes('room_binding');
    };
    (aiTasks||[])
      .filter(t=>isOpenAiStatus(t.status) && (t.projectName||'')===projectName && isLegacyRoomBinding(t))
      .forEach(t=>patchAiTaskSilent(t.id,{status:'Закрыто'}));
    (aiFindings||[])
      .filter(f=>isOpenAiStatus(f.status) && (f.projectName||'')===projectName && isLegacyRoomBinding(f))
      .forEach(f=>patchAiFindingSilent(f.id,{status:'Закрыто'}));
    const openRoomTasks = (aiTasks||[]).filter(t=>{
      if (!isOpenAiStatus(t.status)) return false;
      const payload = parseAiTaskPayload(t);
      return String(payload.marker||'').startsWith('ROOM_CONTROL:')
        && (payload.projectName || t.projectName || '') === projectName;
    });
    openRoomTasks.forEach(t=>{
      const payload = parseAiTaskPayload(t);
      if (payload.marker && !activeMarkers.has(payload.marker)) patchAiTaskSilent(t.id,{status:'Закрыто'});
    });
    for (const descriptor of descriptors) {
      await queueRoomControlTask(descriptor);
    }
  };
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
  const renderMaterialReconciliationPanel = (projectName, options={}) => (
    <MaterialReconciliationPanel
      projectName={projectName}
      options={options}
      C={C}
      card={card}
      btnB={btnB}
      tbl={tbl}
      tblH={tblH}
      tblC={tblC}
      badge={badge}
      fmtMeasure={fmtMeasure}
      materialControlSummaryForProject={materialControlSummaryForProject}
      materialControlStatus={materialControlStatus}
      renderMaterialAliasControls={renderMaterialAliasControls}
      renderMaterialSupplyAction={renderMaterialSupplyAction}
      showPreview={showPreview}
      buildMaterialRequirementContent={buildMaterialRequirementContent}
      isFinanceRole={isFinanceRole}
      isLeadership={isLeadership}
      user={user}
    />
  );
  // Себестоимость объекта = все категории из expByCategory (работы, материалы, доставка, топливо, и т.д.)
  const projectBudgetSpent = (p) => {
    if(!p) return projectBudgetSpentSummary(null);
    return projectBudgetSpentSummary(p, expByCategory(p.name));
  };
  const workExecutionTotal = (work) => workExecutionTotalValue(work);
	  const projectEconomy = (p) => buildProjectEconomy({
	    project: p,
	    projectPlanDone,
	    activeEstimatesForProject,
	    estimatePackage,
	    materialControlSummaryForProject,
	    projectBudgetSpent,
	    workJournal,
	  });
	  const projectObjectLinks = (p) => buildProjectObjectLinks({
	    project: p,
	    C,
	    estimatesList,
	    rooms,
	    projectMeasurements,
	    measurementRoomDrafts,
	    workJournal,
	    hiddenActs,
	    materialInspections,
	    cableJournal,
	    projectDocuments,
	    projectLetters,
	    projectPayments,
	    ownExpenses,
	    visibleEstimatesForCurrentUser,
	    isArchivedEstimate,
	    activeEstimatesForProject,
	    roomCompleteness,
	    materialControlSummaryForProject,
	    estimateReconciliationsForProject,
	    aiFindingsForProject,
	    aiTasksForProject,
	    isFinanceRole,
	  });
	  const directorMapActionTarget = ({ item, action } = {}) => getDirectorMapActionTarget({ item, action, isFinanceRole });
	  const directorMapContractForProject = (p) => buildDirectorMapContract({
	    project: p,
	    stages: projectStages,
	    estimates: activeEstimatesForProject(p, 'Заказчик').map(est => ({...est, workPackage: estimatePackage(est)})),
	    workJournal,
	    materials,
	    supplyRequests,
	    supplyDeliveries,
	    supplierInvoices,
	    warehouseInvoices: invoices,
	    materialInspections,
	    hiddenActs,
	    projectPayments,
	    materialSummary: materialControlSummaryForProject(p.name),
	    planDone: projectPlanDone(p),
	    projectProgress: projectRealProgress(p),
	  });
	  const projectRealProgress = (p) => projectRealProgressValue({
	    project: p,
	    projectPlanDone,
	    projectFactSpent,
	  });

  // Уведомления для текущего пользователя — собираются из АОСР, изменений к смете, предписаний
  const computeNotifications = () => buildComputedNotifications({
    user,
    expenseReports,
    ownExpenses,
    supplierInvoices,
    unexpectedWorksList,
    hiddenActs,
    prescriptionsList,
    accountablePayments,
  });

  // Хелпер: статус АОСР для записи журнала работ
  const getActStatusForJournal = (w) => actStatusForJournalWork(w, hiddenActs);

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
  // Стоимость материалов на объекте: факт прихода по накладным/поставкам, а не текущий остаток.
  // Остаток уменьшается при выдаче/списании, но себестоимость объекта от этого исчезать не должна.
  // Себестоимость работ: что должны бригадам (по priceBrigade × doneQuantity) + зарплата + сдельщина
  const expByCategory = (pn) => projectExpenseCategories({
    projectName: pn,
    expenseCategories: EXPENSE_CATEGORIES,
    materialControlSummaryForProject,
    allBrigadeItems,
    staff,
    piecework,
    calcSalary,
    manualExpenses,
    unexpectedWorksList,
    accountablePayments,
    isApprovedEstimateChangeStatus,
  });
  const lowStock = materials.filter(m=>m.minQuantity&&m.quantity<m.minQuantity);
  const lowMainStock = warehouseMain.filter(m=>m.minQuantity&&m.quantity<m.minQuantity);
  const activeDirectorProjects = () => activeProjectsOnly(projects);
  const buildDirectorBriefReportContent = (date) => buildDirectorBriefReportContentForDate(date, {
    companyName,
    user,
    projects,
    workJournal,
    inspectionOrders,
    ownExpenses,
    supplierInvoices,
    lowStock,
    lowMainStock,
    projectBudgetSpent,
  });
  const estimateControlIssues = (sourceEstimates = estimatesList) => buildDirectorEstimateControlIssues({
    sourceEstimates,
    projects,
    activeProjects: activeDirectorProjects(),
    activeEstimatesForProject,
  });
  const buildEstimateControlReportContent = (sourceEstimates = estimatesList) => {
    const issues = estimateControlIssues(sourceEstimates);
    return buildDirectorEstimateControlReportContent({
      sourceEstimates,
      issues,
      companyName,
      generatedBy: user?.name || '',
    });
  };
  const loadEstimatesForDirectorReport = async () => {
    if ((estimatesList||[]).length) return estimatesList;
    try {
      const token = localStorage.getItem('authToken');
      const res = await fetch(API+'/estimates-summary', token ? {headers:{Authorization:'Bearer '+token}} : undefined);
      if (!res.ok) return estimatesList||[];
      const data = await res.json();
      const list = Array.isArray(data) ? data : [];
      if (list.length) setEstimatesList(normalizeEstimateList(list));
      return list;
    } catch(e) {
      return estimatesList||[];
    }
  };
  const openEstimateControlReport = async () => {
    const list = await loadEstimatesForDirectorReport();
    showPreview(buildEstimateControlReportContent(list),'Проверка смет директора');
  };
  const supplyControlIssues = () => buildDirectorSupplyControlIssues({
    lowMainStock,
    lowStock,
    supplyRequests,
    supplierInvoices,
    invoices,
    activeProjects: activeDirectorProjects(),
    warehouseInvoiceEstimateControl,
    invoiceControlNeedsReview,
    invoiceControlProjectName,
    invoiceControlMaterialName,
    invoiceControlReviewReason,
    materialReconciliationRows,
    materialNormControlSummaryForProject,
    fmtMeasure,
    fmtMoney: fmtDocMoney,
  });
  const buildSupplyControlReportContent = () => {
    const issues = supplyControlIssues();
    return buildDirectorSupplyControlReportContent({
      issues,
      supplyRequests,
      supplierOffers,
      supplierInvoices,
      companyName,
      generatedBy:user?.name||'',
    });
  };

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
    deleteMaterial,
    deleteMainMaterial,
    saveTool,
    deleteTool,
    issueTool,
    returnTool,
  } = createWarehouseCrudActions({
    API,
    editingItem,
    issueToolData,
    newTool,
    refreshData,
    returnToolCondition,
    setEditingItem,
    setIssueToolData,
    setNewTool,
    setReturnToolCondition,
    setShowForm,
    setShowIssueToolModal,
    setShowReturnToolModal,
    user,
  });

  const submitEstimateWorkDone = async (mi, displayQty) => {
    const project = projects.find(p=>p.id===Number(masterProjectId));
    const est = estimatesList.find(e=>Number(e.id)===Number(mi.estId));
    if (!project || !est) return;
    const qty = toNum(mi.quantity);
    const done = toNum(mi.doneQuantity);
    const raw = denormalizeMeasure(displayQty, mi.unit);
    if (raw <= done) { alert('Введите объём больше уже отправленного: сейчас '+fmtMeasure(done,mi.unit)); return; }
    if (qty>0 && raw>qty) { alert('План '+fmtMeasure(qty,mi.unit)+'. Нельзя поставить больше.'); return; }
    const workKey = estimateWorkKey(mi.estId, mi.sectionIdx, mi.itemIdx);
    const estimateItemKey = mi.estimateItemKey || workKey;
    let params = estimateWorkParams[workKey]||{};
    const deltaQty = Math.max(0, raw-done);
    const projectRoomsForWork = rooms.filter(room => room.project === project.name);
    if (!params.roomId && !String(params.roomName || '').trim()) {
      if (projectRoomsForWork.length > 0 && isPersonalMaterialRole()) {
        alert('Выберите помещение для закрытия объёма.');
        return;
      }
      params = { ...params, roomName: GENERAL_WORK_ROOM_NAME };
    }
    const roomCheck = params.roomId ? roomMeasurementCheck(project.name, params.roomId, params.surface||'Стены', deltaQty, mi.unit, mi.name) : null;
    if (roomCheck?.over>0) { alert(roomMeasurementMessage(roomCheck)); return; }
    const currentWorkMaterials = autoFillNormMaterialsForWork(project.name, mi.name, mi.section, deltaQty, mi.unit, estimateWorkMaterials[workKey] || [], {
      ...params,
      workPackage: estimatePackage(est),
    });
    setEstimateWorkMaterials(prev => ({ ...prev, [workKey]: currentWorkMaterials }));
    let usedMats = currentWorkMaterials
      .filter(m=>m.name)
      .map(m=>({name:m.name, quantity:toNum(m.quantity), unit:m.unit||'шт', workPackage:m.workPackage||estimatePackage(est), normQuantity:toNum(m.normQuantity), normSource:m.normSource||'', normRuleId:m.normRuleId||m.ruleId||'', normThicknessMm:m.normThicknessMm||m.thicknessMm||'', autoNorm:!!m.autoNorm, overNorm:toNum(m.normQuantity)>0 && toNum(m.quantity)>toNum(m.normQuantity)*1.1}));
    for (const m of usedMats) {
      if (toNum(m.quantity)<=0) { alert('Укажите количество материала «'+m.name+'» или снимите галочку.'); return; }
    }
    const blockMessage = materialWriteoffBlockMessage(project.name, usedMats);
    if (blockMessage) { alert(blockMessage); return; }
    const overReason = materialNormOverrunReason(project.name, mi.name, usedMats);
    if (overReason === null) return;
    usedMats = applyMaterialOverNormReason(project.name, usedMats, overReason);
    const newSections = est.sections.map((s,si)=>si===mi.sectionIdx?{...s,items:s.items.map((it,ii)=>ii===mi.itemIdx?{...it,doneQuantity:raw}:it)}:s);
    const customerPricePerUnit = toNum(mi.pricePerUnit || mi.price || 0) || (toNum(mi.priceWork || 0) + toNum(mi.priceMaterial || 0));
    const fixedExecutionPrice = toNum(mi.executionPricePerUnit || mi.internalPricePerUnit || mi.masterPricePerUnit || mi.contractorPricePerUnit || mi.executorPricePerUnit);
    const executionCoeff = toNum(mi.executionCoefficient || mi.internalCoefficient || mi.masterCoefficient || mi.contractorCoefficient || mi.executorCoefficient);
    const executionPricePerUnit = fixedExecutionPrice > 0 ? fixedExecutionPrice : (executionCoeff > 0 ? customerPricePerUnit * executionCoeff : 0);
    const executionPriceMode = fixedExecutionPrice > 0 ? 'fixed' : (executionCoeff > 0 ? 'coefficient' : 'not_set');
    if (isPersonalMaterialRole() && executionPricePerUnit <= 0) {
      alert('По этой работе не назначена цена исполнителю. Директор или замдиректора должен задать цену/коэффициент в смете или договорной позиции.');
      return;
    }
    const updated = {
      ...est,
      sections:newSections,
      _workJournalMaterials:{[workKey]:usedMats},
      _workJournalParams:{[workKey]:{
        ...params,
        roomId: params.roomId ? Number(params.roomId) : null,
        roomName: params.roomName || roomCheck?.room?.name || '',
        surface: params.surface || 'Стены',
        workPackage: estimatePackage(est),
        estimateItemName: mi.name,
        estimateItemKey,
        contractItemId: mi.contractItemId || null,
        customerPricePerUnit,
        customerTotal: deltaQty * customerPricePerUnit,
        executionPricePerUnit,
        executionTotal: deltaQty * executionPricePerUnit,
        executionPriceMode,
        photoUrl: params.photoUrl || '',
      }},
    };
    const res = await fetch(API+'/estimates/'+est.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(updated)});
    if (!res.ok) {
      const er = await res.json().catch(()=>({}));
      alert('Не удалось отправить работу: '+(er.detail||res.status));
      return;
    }
    setEstimatesList(prev=>prev.map(e=>Number(e.id)===Number(est.id)?{...est,sections:newSections}:e));
    setEstimateDoneDrafts(prev=>{const next={...prev};delete next[workKey];return next;});
    setEstimateWorkMaterials(prev=>{const next={...prev};delete next[workKey];return next;});
    setEstimateWorkParams(prev=>{const next={...prev};delete next[workKey];return next;});
    await refreshData();
    notify('Работа отправлена в ЖПР: '+mi.name,'work');
    alert('Работа отправлена на проверку. Материалы списаны по выбранным нормам/количествам.');
  };

  const addMasterWorks = async () => {
    const project = projects.find(p=>p.id===Number(masterProjectId));
    if (!project) return;
    const pl = pricelists.find(p=>p.id===project.pricelistId);
    const coeff = pl?pl.coefficient:1.0;
    const now = new Date();
    let hasWork = false;
    const selectedEntries = Object.entries(selectedWorks).filter(([itemId,workData])=>{
      const item = pricelistItems.find(i=>i.id===Number(itemId));
      return item && workData.quantity && toNum(workData.quantity)>0;
    });
    if (!selectedEntries.length) { alert('Введите количество хотя бы для одной работы'); return; }
    const projectRoomsForWork = rooms.filter(room => room.project === project.name);
    const normalizedSelectedEntries = selectedEntries.map(([itemId, workData]) => {
      if (!workData.roomId && !String(workData.roomName || '').trim() && projectRoomsForWork.length === 0) {
        return [itemId, { ...workData, roomName: GENERAL_WORK_ROOM_NAME }];
      }
      return [itemId, workData];
    });
    const plannedUsage = {};
    for (const [itemId, workData] of normalizedSelectedEntries) {
      const item = pricelistItems.find(i=>i.id===Number(itemId));
      if (!workData.roomId && !String(workData.roomName || '').trim()) {
        if (projectRoomsForWork.length > 0 && isPersonalMaterialRole()) {
          alert('Выберите помещение для работы «'+item.name+'».');
          return;
        }
      }
      const roomCheck = workData.roomId ? roomMeasurementCheck(project.name, workData.roomId, workData.surface||'Стены', workData.quantity, item.unit, item.name) : null;
      if (roomCheck?.over>0) { alert(roomMeasurementMessage(roomCheck)); return; }
      for (const m of (workData.materials||[]).filter(mm=>mm.name)) {
        const qty = toNum(m.quantity);
        if (qty<=0) { alert('Укажите количество материала «'+m.name+'» для работы «'+item.name+'» или снимите галочку.'); return; }
        const key = materialNameKey(m.name);
        if (!plannedUsage[key]) plannedUsage[key] = {name:m.name, unit:m.unit||'шт', quantity:0};
        plannedUsage[key].quantity += qty;
      }
    }
    const blockMessage = materialWriteoffBlockMessage(project.name, Object.values(plannedUsage));
    if (blockMessage) { alert(blockMessage); return; }
    const overrunReasons = {};
    for (const [itemId, workData] of normalizedSelectedEntries) {
      const item = pricelistItems.find(i=>i.id===Number(itemId));
      if (!item) continue;
      const overReason = materialNormOverrunReason(project.name, item.name, workData.materials||[]);
      if (overReason === null) return;
      if (overReason) overrunReasons[itemId] = overReason;
    }
    for (const [itemId,workData] of normalizedSelectedEntries) {
      const item = pricelistItems.find(i=>i.id===Number(itemId));
      if (!item) continue;
      hasWork = true;
      const ppu = item.price*coeff;
      const workQty = toNum(workData.quantity);
      const total = workQty*ppu;
      const reason = overrunReasons[itemId] || '';
      const usedMats=(workData.materials||[]).filter(m=>m.name&&toNum(m.quantity)>0).map(m=>{const over=toNum(m.normQuantity)>0&&toNum(m.quantity)>toNum(m.normQuantity)*1.1;return {name:m.name,quantity:toNum(m.quantity),unit:m.unit||'шт',workPackage:m.workPackage||'Прайс',normQuantity:toNum(m.normQuantity),normSource:m.normSource||'',normRuleId:m.normRuleId||m.ruleId||'',normThicknessMm:m.normThicknessMm||m.thicknessMm||'',autoNorm:!!m.autoNorm,overNorm:over,overNormReason:over?reason:''};});
      const wjRes=await fetch(API+'/work-journal',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({masterId:user.id,masterName:user.name,project:project.name,description:item.name,unit:item.unit,quantity:workQty,pricePerUnit:ppu,total,customerPricePerUnit:ppu,customerTotal:total,executionPricePerUnit:ppu,executionTotal:total,executionPriceMode:'pricelist',date:now.toISOString().split('T')[0],comment:workData.comment||'',photoUrl:workData.photoUrl||'',materialsUsed:usedMats,workPackage:'Прайс',roomId:workData.roomId?Number(workData.roomId):null,roomName:workData.roomName||'',surface:workData.surface||'Стены',estimateItemName:item.name})});
      if(!wjRes.ok){const er=await wjRes.json().catch(()=>({}));alert('Не удалось отправить работу: '+(er.detail||'ошибка'));return;}
    }
    if (!hasWork) { alert('Введите количество хотя бы для одной работы'); return; }
    notify(user.name+' отправил работы','work');
    await refreshData(); setSelectedWorks({}); setMasterProjectId(''); setPricelistItems([]);
    alert('Работы отправлены на проверку!');
  };

  // Открыть модалку для подтверждения с возможным пересчётом количества
  const openConfirmModal = (e) => {
    // Если исполнительская цена пустая, не подставляем заказчиковую сумму.
    const fallbackPpu = (Number(e.executionPricePerUnit||0)===0 && Number(e.quantity||0)>0) ? (Number(e.executionTotal||0)/Number(e.quantity||0)) : Number(e.executionPricePerUnit||0);
    setConfirmingEntry({...e, _ppu: fallbackPpu});
    setConfirmAcceptedQty(String(e.quantity||''));
    setConfirmComment('');
  };

  const confirmJ = async (e, acceptedQty, comment) => {
    const planQty = toNum(e.quantity||0);
    const accepted = (acceptedQty===undefined||acceptedQty===null||acceptedQty==='')?planQty:toNum(acceptedQty);
    const ppu = Number(e._ppu||e.executionPricePerUnit||0) || (Number(e.executionTotal||0)/Math.max(1, planQty));
    const customerPpu = Number(e.customerPricePerUnit||0) || (Number(e.customerTotal||0)/Math.max(1, planQty));
    const newTotal = Math.round(accepted * ppu);
    const newCustomerTotal = Math.round(accepted * customerPpu);
    const body = {
      status:'Подтверждено',
      confirmedBy:user.name,
      confirmedAt:new Date().toISOString().split('T')[0],
      quantity: accepted,
    };
    if (isFinanceRole) {
      body.total = newTotal;
      body.pricePerUnit = ppu;
      body.executionPricePerUnit = ppu;
      body.executionTotal = newTotal;
      body.customerPricePerUnit = customerPpu;
      body.customerTotal = newCustomerTotal;
    }
    if(comment) body.comment = comment;
    await fetch(API+'/work-journal/'+e.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    await refreshData();
    await updateProjectProgress(e.project||"");
    setConfirmingEntry(null); setConfirmAcceptedQty(''); setConfirmComment('');
    const msg = (accepted<planQty)?('Принято '+accepted+' из '+planQty+' '+(e.unit||'')+' · '+e.description):'Работа подтверждена: '+e.description;
    notify(msg,'work'); addActivity(msg);
  };

  const rejectJ = async (e,c) => {
    await fetch(API+'/work-journal/'+e.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Отклонено',confirmedBy:user.name,comment:c||''})});
    await refreshData(); setRejectingEntry(null); setRejectComment('');
  };

  const saveUser = async () => {
    const cleanUser = {
      ...newUser,
      name:(newUser.name||'').trim(),
      email:(newUser.email||'').trim().toLowerCase(),
      password:(newUser.password||'').trim(),
    };
    if (!cleanUser.name||!cleanUser.email) return;
    if (!editingItem && !cleanUser.password) { alert('Укажите пароль'); return; }
    if (editingItem) {
      const res = await fetch(API+'/users/'+editingItem.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(cleanUser)});
      if(!res.ok){ const e=await res.json().catch(()=>({})); alert(e.detail||'Не удалось сохранить пользователя'); return; }
    }
    else {
      const res = await fetch(API+'/users',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(cleanUser)});
      if(!res.ok){ const e=await res.json().catch(()=>({})); alert(e.detail||'Не удалось создать пользователя'); return; }
      if(cleanUser.role==='поставщик'){
        const existing = suppliers.find(s=>s.name===cleanUser.name||s.email===cleanUser.email);
        if(!existing){
          await fetch(API+'/suppliers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:cleanUser.name,email:cleanUser.email,phone:'',specialization:'',category:'Прочее',rating:5.0,status:'Активный'})});
        }
      }
    }
    await refreshData(); setNewUser({name:'',email:'',password:'',role:'прораб',companyName:'',inn:'',projectId:'',projectName:'',assignedProjects:[],assignedPackages:[],active:true}); setEditingItem(null); setShowForm(false);
  };

  const toggleUserActive = async (u, nextActive) => {
    if (!nextActive && u.id===user.id) { alert('Нельзя отключить себя!'); return; }
    const label = nextActive ? 'Включить доступ пользователю?' : 'Отключить доступ пользователю? История останется в системе.';
    if (!window.confirm(label)) return;
    if (nextActive) {
      await fetch(API+'/users/'+u.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({
        name:u.name,
        email:u.email,
        password:'',
        role:u.role,
        projectId:u.projectId||'',
        projectName:u.projectName||u.project_name||'',
        assignedProjects:u.assignedProjects||u.assigned_projects||[],
        assignedPackages:u.assignedPackages||u.assigned_packages||[],
        active:true
      })});
    } else {
      await fetch(API+'/users/'+u.id,{method:'DELETE'});
    }
    await refreshData();
  };

  const deleteUser = async (u) => {
    await toggleUserActive(u, false);
  };

  const resetUserTwoFactor = async (u) => {
    if (!u?.id) return;
    const label = `Сбросить 2FA для ${u.name || u.email}? При следующем входе пользователь настроит код заново.`;
    if (!window.confirm(label)) return;
    const res = await fetch(API + '/users/' + u.id + '/2fa-reset', { method: 'POST' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.ok === false) {
      alert(data.detail || data.error || 'Не удалось сбросить 2FA');
      return;
    }
    await refreshData();
    alert('2FA сброшена');
  };

  const createInvite = async () => { await fetch(API+'/invite-codes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({role:newInviteRole})}); await refreshData(); };

  // Создать пригласительную ссылку для поставщика и показать её для копирования
  const createSupplierInvite = async () => {
    const body = {
      role:'поставщик',
      presetName: supplierInviteForm.presetName || '',
      presetCategory: supplierInviteForm.presetCategory || '',
      supplierId: supplierInviteForm.supplierId,
      expiresInDays: supplierInviteForm.expiresInDays || 14,
      createdBy: user?.name || ''
    };
    const r = await fetch(API+'/invite-codes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const data = await r.json();
    if (data.code) {
      const link = window.location.origin + '/?invite=' + data.code;
      setGeneratedInviteLink({code:data.code, link, presetName:body.presetName, expiresAt:data.expires_at});
      await refreshData();
    } else {
      alert('Не удалось создать ссылку');
    }
  };

  const deleteInvite = async (id) => { await fetch(API+'/invite-codes/'+id,{method:'DELETE'}); await refreshData(); };

  const savePricelist = async () => {
    if (!newPricelist.name) return;
    if (editingItem) await fetch(API+'/pricelists/'+editingItem.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(newPricelist)});
    else await fetch(API+'/pricelists',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(newPricelist)});
    await refreshData(); setNewPricelist({name:'',description:'',forWho:'',coefficient:1.0}); setEditingItem(null); setShowForm(false);
  };

  const deletePricelist = async (id) => {
    if (window.confirm('Удалить прайс-лист?')) {
      await fetch(API+'/pricelists/'+id,{method:'DELETE'});
      await refreshData();
      if (selectedPricelist&&selectedPricelist.id===id) { setSelectedPricelist(null); setPricelistItems([]); }
    }
  };

  const copyPricelist = async (pl) => { const name=prompt('Название копии:','Копия — '+pl.name); if (!name) return; await fetch(API+'/pricelists/'+pl.id+'/copy',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})}); await refreshData(); };

  const savePlItem = async () => {
    if (!newPlItem.name||!newPlItem.price) return;
    const data = {...newPlItem,price:Number(newPlItem.price),pricelistId:selectedPricelist.id};
    if (editingPlItem&&editingPlItem.id) await fetch(API+'/pricelist-items/'+editingPlItem.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
    else await fetch(API+'/pricelist-items',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
    await loadPricelistItems(selectedPricelist.id);
    setNewPlItem({name:'',unit:'м2',price:'',category:''}); setEditingPlItem(null);
  };

  const startInlinePlEdit = (item) => {
    setInlineEditPl(item.id);
    setInlineEditPrice(String(item.price ?? ''));
    setInlineEditPlData({name:item.name||'',unit:item.unit||'м2',price:String(item.price ?? ''),category:item.category||''});
  };

  const cancelInlinePlEdit = () => {
    setInlineEditPl(null);
    setInlineEditPrice('');
    setInlineEditPlData({name:'',unit:'м2',price:'',category:''});
  };

  const saveInlinePlItem = async (item) => {
    const data = inlineEditPlData.name ? inlineEditPlData : {...item,price:inlineEditPrice};
    if (!String(data.name||'').trim() || String(data.price||'').trim()==='') return;
    await fetch(API+'/pricelist-items/'+item.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...item,...data,price:Number(data.price),pricelistId:selectedPricelist.id})});
    await loadPricelistItems(selectedPricelist.id);
    cancelInlinePlEdit();
  };

  const deletePlItem = async (id) => { await fetch(API+'/pricelist-items/'+id,{method:'DELETE'}); await loadPricelistItems(selectedPricelist.id); };

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
    addPiecework,
    addStaffDoc,
    createContract,
    createInterimAct,
    createStaffAccessFromPrompt,
    deleteContract,
    deleteInterimAct,
    deletePiecework,
    deleteStaff,
    openStaffProfile,
    paySalary,
    resetStaffAccessPassword,
    saveStaff,
    toggleDay,
  } = createPersonnelActions({
    API,
    ROLE_LABELS,
    contracts,
    editingItem,
    expandedStaffId,
    findUserForStaff,
    newAct,
    newContract,
    newPiecework,
    newStaff,
    newStaffDoc,
    notify,
    readApiResult,
    refreshData,
    resolveContractPerformer,
    setEditingItem,
    setExpandedStaffId,
    setNewAct,
    setNewContract,
    setNewPiecework,
    setNewStaff,
    setNewStaffDoc,
    setSalaryPayments,
    setShowForm,
    setShowStaffDocForm,
    setStaffProfile,
    setStaffProfileLoading,
    setTimesheet,
    staffAccessRoles,
    staffPackageRequiredRoles,
    staffProjectRequiredRoles,
    upsertStaffAccess,
    user,
    users,
    workJournal,
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

  const pageFallback = (
    <div style={{padding:isMobile?'18px':'24px',color:C.text}}>
      <div style={{...card,padding:'18px',display:'flex',alignItems:'center',gap:'10px'}}>
        <span style={{fontSize:'18px'}}>⏳</span>
        <div>
          <div style={{fontWeight:800}}>Загружаю раздел</div>
          <div style={{color:C.textSec,fontSize:'13px',marginTop:'3px'}}>Подгружаю только нужный экран, чтобы приложение быстрее открывалось на телефоне.</div>
        </div>
      </div>
    </div>
  );

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
    const mySupplier = suppliers.find(s => s.name === user.name || s.email === user.email);
    const myCatalog = supplierCatalog.filter(c => c.supplierId === mySupplier?.id);
    const myOffers = supplierOffers.filter(o => o.supplierId === mySupplier?.id);
    const mySupplierInvoices = supplierInvoices.filter(inv => inv.supplierId===mySupplier?.id || inv.supplierName===mySupplier?.name || inv.supplierName===user.name);
    const myDeliveries = supplyDeliveries.filter(d => d.supplierId===mySupplier?.id || d.supplierName===mySupplier?.name || d.supplierName===user.name);
    const myClaims = supplyClaims.filter(c => c.supplierId===mySupplier?.id);
    const SUPPLIER_TABS = [{id:'requests',label:'📋 Заявки'},{id:'catalog',label:'📦 Мой каталог'},{id:'offers',label:'💰 Предложения'},{id:'deliveries',label:'🚚 Отгрузки'},{id:'documents',label:'📄 Счета'},{id:'claims',label:'⚠️ Претензии'},{id:'profile',label:'⚙️ Профиль'}];
    const appendSupplierReqNote = (current, line) => {
      const base = String(current || '').trim();
      const addition = String(line || '').trim();
      if (!addition || base.includes(addition)) return base;
      return base ? base + '\n' + addition : addition;
    };
    const supplierRequisitesPatchFromRecognition = (result, current = {}) => {
      const extracted = result?.extracted || {};
      const doc = result?.suggestedCrmDocument || {};
      const docType = String(extracted.docType || doc.docType || '').toLowerCase();
      const contractLike = docType.includes('договор') || docType.includes('контракт');
      const patch = {
        companyName: extracted.counterpartyName || '',
        inn: extracted.inn || '',
        kpp: extracted.kpp || '',
        ogrn: extracted.ogrn || '',
        address: extracted.legalAddress || '',
        bank: extracted.bank || '',
        bik: extracted.bik || '',
        account: extracted.bankAccount || '',
        korAccount: extracted.corrAccount || '',
        directorName: extracted.signerName || '',
        directorPosition: extracted.signerBasis || '',
        contractNumber: contractLike ? (extracted.number || '') : '',
        contractDate: contractLike ? (extracted.docDate || '') : '',
        contractUrl: contractLike ? (result?.fileUrl || '') : '',
        specialization: extracted.workType || '',
      };
      if (extracted.contractSubject) {
        patch.notes = appendSupplierReqNote(current.notes, 'Предмет договора: ' + extracted.contractSubject);
      }
      return Object.fromEntries(Object.entries(patch).filter(([, value]) => value));
    };
    const createOwnSupplierDocumentFromRecognition = async (docPatch, result) => {
      const supplierId = mySupplier?.id || 0;
      if (!supplierId) return alert('Сначала сохраните реквизиты поставщика');
      const extracted = result?.extracted || {};
      const res = await fetch(API + '/supplier-documents', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          supplierId,
          docType: docPatch.docType || extracted.docType || 'Другое',
          title: docPatch.title || extracted.documentTitle || 'Распознанный документ',
          fileUrl: docPatch.fileUrl || result?.fileUrl || '',
          status: 'На проверке',
          signedAt: extracted.docDate || '',
          notes: docPatch.notes || (extracted.contractSubject ? 'Предмет договора: ' + extracted.contractSubject : ''),
          uploadedBy: user?.name || '',
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.detail || data.error) {
        alert(data.detail || data.error || 'Не удалось добавить документ');
        return;
      }
      await refreshData();
    };
    return (
      <div style={{minHeight:'100vh',backgroundColor:C.bg,padding:'20px'}}>
        <div style={{maxWidth:'900px',margin:'0 auto'}}>
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'16px'}}>
            <div style={{display:'flex',alignItems:'center',gap:'12px'}}>
              <span style={{fontSize:'28px'}}>🏭</span>
              <div><b style={{color:C.text,fontSize:'18px',display:'block'}}>Кабинет поставщика</b><p style={{color:C.textSec,margin:0,fontSize:'13px'}}>{user.name}</p></div>
            </div>
            <button onClick={()=>handleLogout()} style={{...btnG,fontSize:'12px'}}>Выйти</button>
          </div>
          {/* Селектор клиентов (заготовка под multi-tenancy) */}
          <div style={{...card,padding:'10px 14px',marginBottom:'16px',backgroundColor:C.infoLight,border:'1.5px solid '+C.infoBorder,display:'flex',alignItems:'center',justifyContent:'space-between',gap:'10px',flexWrap:'wrap'}}>
            <div style={{display:'flex',alignItems:'center',gap:'10px'}}>
              <span style={{fontSize:'18px'}}>🏢</span>
              <div>
                <b style={{color:C.text,fontSize:'13px'}}>Компания-клиент: СтройКа</b>
                <p style={{color:C.textSec,margin:'2px 0 0',fontSize:'11px'}}>Сейчас показываем заявки только от одной компании. В будущем сюда подключатся другие клиенты — увидите всех в одном кабинете.</p>
              </div>
            </div>
            <select disabled value='1' style={{...inp,marginBottom:0,width:'auto',cursor:'not-allowed',opacity:0.7}}>
              <option value='1'>СтройКа</option>
              <option value='all' disabled>🚧 Скоро: все клиенты</option>
            </select>
          </div>
          <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:'12px',marginBottom:'16px'}}>
            <div style={{...card,padding:'16px',textAlign:'center'}}>
              <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 4px'}}>Новых заявок</p>
              <b style={{color:C.danger,fontSize:'24px'}}>{supplyRequests.filter(r=>r.status==='Новая').length}</b>
            </div>
            <div style={{...card,padding:'16px',textAlign:'center'}}>
              <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 4px'}}>Моих предложений</p>
              <b style={{color:C.accent,fontSize:'24px'}}>{myOffers.length}</b>
            </div>
            <div style={{...card,padding:'16px',textAlign:'center'}}>
              <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 4px'}}>Утверждено</p>
              <b style={{color:C.success,fontSize:'24px'}}>{myOffers.filter(o=>o.status==='Утверждено').length}</b>
            </div>
          </div>

          <div style={{display:'flex',gap:0,overflowX:'auto',borderBottom:'1.5px solid '+C.border,marginBottom:'16px'}}>
            {SUPPLIER_TABS.map(t=>(<button key={t.id} onClick={()=>setSupplierTab(t.id)} style={{padding:'10px 16px',border:'none',backgroundColor:'transparent',cursor:'pointer',fontSize:'12px',fontWeight:supplierTab===t.id?'700':'400',color:supplierTab===t.id?C.accent:C.textSec,borderBottom:supplierTab===t.id?'2px solid '+C.accent:'2px solid transparent',whiteSpace:'nowrap'}}>{t.label}</button>))}
          </div>

          {supplierTab==='requests'&&(<div>
            <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>📋 Запросы КП</b>
            {(()=>{
              // Берём supplier_offers где я — поставщик, и группируем по статусу
              const myOffersForMe = (supplierOffers||[]).filter(o=>o.supplierId===(mySupplier?.id||0));
              if (myOffersForMe.length===0) return (<p style={{color:C.textMuted,fontSize:'12px',textAlign:'center',padding:'20px'}}>
                Запросов нет. Когда директор запросит у вас КП по своей заявке — он появится здесь.
              </p>);
              const waiting = myOffersForMe.filter(o=>o.status==='Ожидает ответа');
              const responded = myOffersForMe.filter(o=>o.status==='Получено');
              const won = myOffersForMe.filter(o=>o.status==='Утверждено');
              const lost = myOffersForMe.filter(o=>o.status==='Отклонено');
              const groups = [
                {key:'wait', title:'⏳ Ждут ответа', items:waiting, color:C.warning, bg:C.warningLight, bd:C.warningBorder},
                {key:'resp', title:'📤 КП отправлено, ждёт решения', items:responded, color:C.info, bg:C.infoLight, bd:C.infoBorder},
                {key:'won',  title:'✅ Выиграно', items:won, color:C.success, bg:C.successLight, bd:C.successBorder},
                {key:'lost', title:'❌ Отклонено', items:lost, color:C.danger, bg:C.dangerLight, bd:C.dangerBorder},
              ];
              return groups.filter(g=>g.items.length>0).map(g=>(<div key={g.key} style={{marginBottom:'16px'}}>
                <b style={{color:g.color,fontSize:'12px',display:'block',marginBottom:'8px'}}>{g.title} ({g.items.length})</b>
                {g.items.map(o=>{
                  const req = supplyRequests.find(r=>r.id===o.requestId);
                  if (!req) return null;
                  const isResponding = respondingOfferId===o.id;
                  return (<div key={o.id} style={{padding:'12px',backgroundColor:g.bg,borderRadius:'8px',marginBottom:'8px',border:'1.5px solid '+g.bd}}>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'8px',flexWrap:'wrap'}}>
                      <div style={{flex:1,minWidth:'200px'}}>
                        {(()=>{const items=parseSupplyItems(req); if (items.length<=1) {
                          const it = items[0] || {materialName:req.materialName,quantity:req.quantity,unit:req.unit};
                          return (<><b style={{fontSize:'13px',color:C.text}}>{it.materialName}</b><p style={{color:C.textSec,margin:'3px 0',fontSize:'12px'}}>{it.quantity+' '+it.unit+' · 🏗 '+(req.project||'')}</p></>);
                        } return (<>
                          <b style={{fontSize:'13px',color:C.text}}>📋 Запрос на {items.length} позиций <span style={{color:C.textSec,fontWeight:'400'}}>· 🏗 {req.project||''}</span></b>
                          <ol style={{margin:'4px 0 6px',paddingLeft:'18px',color:C.text,fontSize:'12px'}}>
                            {items.map((it,i)=>(<li key={i} style={{marginBottom:'2px'}}>{it.materialName} <span style={{color:C.textSec}}>— {it.quantity} {it.unit}</span></li>))}
                          </ol>
                        </>);})()}
                        {req.notes && <p style={{color:C.textMuted,margin:'0',fontSize:'11px',fontStyle:'italic'}}>«{req.notes}»</p>}
                        {o.aiRecommended && <span style={badge(C.accent,C.accentLight,C.accentBorder||C.border)}>🤖 AI рекомендовал вас</span>}
                        {o.pricePerUnit>0 && (<p style={{color:C.textSec,margin:'4px 0 0',fontSize:'11px'}}>
                          Ваш ответ: <b>{Number(o.pricePerUnit).toLocaleString('ru-RU')+' ₽/'+req.unit}</b>{o.deliveryDays?' · '+o.deliveryDays+' дн.':''}{o.paymentTerms?' · '+o.paymentTerms:''}
                        </p>)}
                      </div>
                      <div>
                        {g.key==='wait' && !isResponding && (
                          <button onClick={()=>{setRespondingOfferId(o.id);setNewKpResponse({pricePerUnit:o.pricePerUnit||'',deliveryDays:o.deliveryDays||'',paymentTerms:o.paymentTerms||'Постоплата',vatIncluded:o.vatIncluded!==false,validUntil:o.validUntil||'',supplierMessage:o.supplierMessage||'',pdfUrl:o.pdfUrl||''});}} style={{...btnO,padding:'5px 12px',fontSize:'12px'}}>💰 Отправить КП</button>
                        )}
                        {g.key==='resp' && (
                          <button onClick={()=>{setRespondingOfferId(o.id);setNewKpResponse({pricePerUnit:o.pricePerUnit||'',deliveryDays:o.deliveryDays||'',paymentTerms:o.paymentTerms||'Постоплата',vatIncluded:o.vatIncluded!==false,validUntil:o.validUntil||'',supplierMessage:o.supplierMessage||'',pdfUrl:o.pdfUrl||''});}} style={{...btnG,padding:'4px 10px',fontSize:'11px'}}><Edit2 size={11}/>Изменить</button>
                        )}
                        {g.key==='won' && (
                          (()=>{
                            const hasInvoice = (supplierInvoices||[]).find(inv=>inv.offerId===o.id||inv.offer_id===o.id);
                            const delivery = (supplyDeliveries||[]).find(d=>d.offerId===o.id);
                            const paid = Number(hasInvoice?.paidAmount||0);
                            const amount = Number(hasInvoice?.amount||hasInvoice?.totalAmount||o.totalPrice||0);
                            const terms = String(o.paymentTerms||'').toLowerCase();
                            const needPay = terms.includes('предоплат') || terms.includes('50/50');
                            const required = terms.includes('50/50') ? amount*0.5 : amount;
                            const blockedByPay = needPay && (!hasInvoice || paid + 0.01 < required);
                            return (<div style={{display:'flex',gap:'6px',flexWrap:'wrap',justifyContent:'flex-end'}}>
                              {hasInvoice
                                ? <span style={badge(hasInvoice.status==='Оплачен'||hasInvoice.status==='Частично оплачен'?C.success:C.info,hasInvoice.status==='Оплачен'||hasInvoice.status==='Частично оплачен'?C.successLight:C.infoLight,hasInvoice.status==='Оплачен'||hasInvoice.status==='Частично оплачен'?C.successBorder:C.infoBorder)}>💳 {hasInvoice.status}</span>
                                : <button onClick={()=>{setInvoicingOfferId(o.id);setNewOfferInvoice({invoiceNumber:'',invoiceDate:new Date().toISOString().split('T')[0],amount:o.totalPrice||'',vatAmount:'',description:'Материал: '+req.materialName,fileUrl:''});}} style={{...btnO,padding:'5px 12px',fontSize:'12px'}}>💳 Выставить счёт</button>}
                              {delivery
                                ? <span style={badge(delivery.status==='Принято'?C.success:delivery.status==='Проблема'?C.danger:C.warning,delivery.status==='Принято'?C.successLight:delivery.status==='Проблема'?C.dangerLight:C.warningLight,delivery.status==='Принято'?C.successBorder:delivery.status==='Проблема'?C.dangerBorder:C.warningBorder)}>🚚 {delivery.status}</span>
                                : <button disabled={blockedByPay} title={blockedByPay?'По условиям оплаты сначала нужна оплата бухгалтерии':''} onClick={()=>{if(blockedByPay){alert('По условиям «'+(o.paymentTerms||'')+'» сначала нужна оплата.');return;}setShippingOfferId(o.id);setShipmentForm({shippedQuantity:String(req.quantity||''),waybillNumber:'',waybillDate:new Date().toISOString().split('T')[0],vehicleNumber:'',driverName:'',documentUrl:'',photoUrl:''});}} style={{...btnGr,padding:'5px 12px',fontSize:'12px',opacity:blockedByPay?0.5:1,cursor:blockedByPay?'not-allowed':'pointer'}}>🚚 Отгрузить</button>}
                            </div>);
                          })()
                        )}
                      </div>
                    </div>
                    {/* Форма ответа КП — постатейная для multi-item */}
                    {isResponding && (()=>{
                      const reqItems = parseSupplyItems(req);
                      const isMulti = reqItems.length > 1;
                      // Сохранённые цены по позициям — берём из state, если уже инициализированы
                      const itemsKp = (newKpResponse.itemsKp && newKpResponse.itemsKp.length === reqItems.length)
                        ? newKpResponse.itemsKp
                        : reqItems.map(it => ({
                            materialName: it.materialName, quantity: Number(it.quantity)||0, unit: it.unit,
                            workPackage: it.workPackage || it.work_package || req.workPackage || req.work_package || '',
                            pricePerUnit: '', deliveryDays: '', notes: ''
                          }));
                      const grandTotal = itemsKp.reduce((s,it)=>s+(Number(it.pricePerUnit||0)*Number(it.quantity||0)), 0);
                      const setItem = (idx, field, value) => {
                        const arr = [...itemsKp];
                        arr[idx] = {...arr[idx], [field]: value};
                        setNewKpResponse({...newKpResponse, itemsKp: arr});
                      };
                      return (<div style={{borderTop:'1.5px solid '+C.border,paddingTop:'12px',marginTop:'10px'}}>
                      <b style={{color:C.text,fontSize:'12px',display:'block',marginBottom:'8px'}}>
                        💰 Ваше КП {isMulti?'(заполните цену по каждой позиции)':'на '+(reqItems[0]?.quantity||req.quantity)+' '+(reqItems[0]?.unit||req.unit)}:
                      </b>
                      {/* Постатейная таблица для multi-item */}
                      {isMulti && (<div style={{marginBottom:'10px',overflowX:'auto'}}>
                        <table style={{width:'100%',borderCollapse:'collapse',fontSize:'12px'}}>
                          <thead>
                            <tr style={{backgroundColor:C.bg}}>
                              <th style={{padding:'6px 8px',textAlign:'left',color:C.textSec,fontWeight:'600',borderBottom:'1px solid '+C.border}}>#</th>
                              <th style={{padding:'6px 8px',textAlign:'left',color:C.textSec,fontWeight:'600',borderBottom:'1px solid '+C.border}}>Материал</th>
                              <th style={{padding:'6px 8px',textAlign:'center',color:C.textSec,fontWeight:'600',borderBottom:'1px solid '+C.border}}>Кол-во</th>
                              <th style={{padding:'6px 8px',textAlign:'right',color:C.textSec,fontWeight:'600',borderBottom:'1px solid '+C.border,minWidth:'110px'}}>Цена за ед. (₽)</th>
                              <th style={{padding:'6px 8px',textAlign:'right',color:C.textSec,fontWeight:'600',borderBottom:'1px solid '+C.border,minWidth:'100px'}}>Сумма</th>
                            </tr>
                          </thead>
                          <tbody>
                            {itemsKp.map((it,i)=>{
                              const subtotal = Number(it.pricePerUnit||0) * Number(it.quantity||0);
                              return (<tr key={i} style={{borderBottom:'1px solid '+C.border}}>
                                <td style={{padding:'6px 8px',color:C.textMuted}}>{i+1}</td>
                                <td style={{padding:'6px 8px',color:C.text}}>{it.materialName}</td>
                                <td style={{padding:'6px 8px',color:C.text,textAlign:'center',whiteSpace:'nowrap'}}>{it.quantity} {it.unit}</td>
                                <td style={{padding:'4px 8px',textAlign:'right'}}>
                                  <input type='number' step='any' inputMode='decimal' value={it.pricePerUnit} onChange={e=>setItem(i,'pricePerUnit',e.target.value)} placeholder='—' style={{...inp,marginBottom:0,textAlign:'right',padding:'4px 6px',fontSize:'12px'}}/>
                                </td>
                                <td style={{padding:'6px 8px',color:C.text,textAlign:'right',fontWeight:'600',whiteSpace:'nowrap'}}>
                                  {subtotal>0 ? Math.round(subtotal).toLocaleString('ru-RU')+' ₽' : '—'}
                                </td>
                              </tr>);
                            })}
                            <tr style={{backgroundColor:C.successLight}}>
                              <td colSpan={4} style={{padding:'8px',textAlign:'right',color:C.text,fontWeight:'700'}}>ИТОГО:</td>
                              <td style={{padding:'8px',textAlign:'right',color:C.success,fontWeight:'800',fontSize:'14px'}}>{grandTotal>0 ? Math.round(grandTotal).toLocaleString('ru-RU')+' ₽' : '—'}</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>)}
                      {/* Single-item: одно поле цены */}
                      {!isMulti && (<div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginBottom:'8px'}}>
                        <div>
                          <label style={{fontSize:'11px',color:C.textSec,display:'block',marginBottom:'3px'}}>Цена за {reqItems[0]?.unit||req.unit} (₽) *</label>
                          <input type='number' step='any' inputMode='decimal' value={newKpResponse.pricePerUnit} onChange={e=>setNewKpResponse({...newKpResponse,pricePerUnit:e.target.value})} style={{...inp,marginBottom:0}}/>
                        </div>
                        <div>
                          <label style={{fontSize:'11px',color:C.textSec,display:'block',marginBottom:'3px'}}>Срок поставки (дни) *</label>
                          <input type='number' step='1' inputMode='numeric' value={newKpResponse.deliveryDays} onChange={e=>setNewKpResponse({...newKpResponse,deliveryDays:e.target.value})} style={{...inp,marginBottom:0}}/>
                        </div>
                      </div>)}
                      {/* Общие поля */}
                      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginBottom:'8px'}}>
                        {isMulti && (<div>
                          <label style={{fontSize:'11px',color:C.textSec,display:'block',marginBottom:'3px'}}>Срок поставки (дни) *</label>
                          <input type='number' step='1' inputMode='numeric' value={newKpResponse.deliveryDays} onChange={e=>setNewKpResponse({...newKpResponse,deliveryDays:e.target.value})} style={{...inp,marginBottom:0}}/>
                        </div>)}
                        <div>
                          <label style={{fontSize:'11px',color:C.textSec,display:'block',marginBottom:'3px'}}>Условия оплаты</label>
                          <select value={newKpResponse.paymentTerms} onChange={e=>setNewKpResponse({...newKpResponse,paymentTerms:e.target.value})} style={{...inp,marginBottom:0}}>
                            <option>Предоплата 100%</option>
                            <option>50/50</option>
                            <option>Постоплата</option>
                            <option>Отсрочка 7 дней</option>
                            <option>Отсрочка 14 дней</option>
                            <option>Отсрочка 30 дней</option>
                          </select>
                        </div>
                        <div>
                          <label style={{fontSize:'11px',color:C.textSec,display:'block',marginBottom:'3px'}}>НДС</label>
                          <select value={newKpResponse.vatIncluded?'incl':'excl'} onChange={e=>setNewKpResponse({...newKpResponse,vatIncluded:e.target.value==='incl'})} style={{...inp,marginBottom:0}}>
                            <option value='incl'>С НДС (включён)</option>
                            <option value='excl'>Без НДС</option>
                          </select>
                        </div>
                        <div>
                          <label style={{fontSize:'11px',color:C.textSec,display:'block',marginBottom:'3px'}}>КП действительно до</label>
                          <input type='date' value={newKpResponse.validUntil} onChange={e=>setNewKpResponse({...newKpResponse,validUntil:e.target.value})} style={{...inp,marginBottom:0}}/>
                        </div>
                        <div style={{gridColumn:isMulti?'span 2':'span 2'}}>
                          <label style={{fontSize:'11px',color:C.textSec,display:'block',marginBottom:'3px'}}>PDF КП (опц.)</label>
                          <label style={{...btnG,padding:'8px 12px',fontSize:'12px',cursor:'pointer',display:'inline-flex',alignItems:'center',gap:'4px',width:'100%',justifyContent:'center'}}>
                            <Upload size={12}/>{newKpResponse.pdfUrl?'PDF загружен':'Прикрепить PDF'}
                            <input type='file' accept='.pdf,image/*' style={{display:'none'}} onChange={async e=>{if(e.target.files[0]){const url=await uploadPhoto(e.target.files[0],{projectName:req.project||req.projectName,context:'supplier-offers'});setNewKpResponse({...newKpResponse,pdfUrl:url});}}}/>
                          </label>
                        </div>
                      </div>
                      <textarea placeholder='Комментарий (опц.) — особенности, условия доставки' value={newKpResponse.supplierMessage} onChange={e=>setNewKpResponse({...newKpResponse,supplierMessage:e.target.value})} style={{...inp,height:'50px',resize:'vertical'}}/>
                      {/* Итог для single-item */}
                      {!isMulti && newKpResponse.pricePerUnit && (<div style={{padding:'8px 10px',backgroundColor:C.successLight,borderRadius:'6px',marginBottom:'8px',fontSize:'12px',color:C.text}}>
                        Итого: <b>{Math.round(Number(newKpResponse.pricePerUnit||0)*Number(reqItems[0]?.quantity||req.quantity||0)).toLocaleString('ru-RU')} ₽</b>
                      </div>)}
                      <div style={{display:'flex',gap:'8px'}}>
                        <button onClick={async()=>{
                          if (isMulti) {
                            // Валидация: все позиции должны иметь цену > 0
                            const missing = itemsKp.filter(it=>!(Number(it.pricePerUnit)>0));
                            if (missing.length>0) { alert('Заполните цену по всем '+itemsKp.length+' позициям'); return; }
                            if (!newKpResponse.deliveryDays) { alert('Заполните срок'); return; }
                          } else {
                            if (!newKpResponse.pricePerUnit||!newKpResponse.deliveryDays) { alert('Заполните цену и срок'); return; }
                          }
                          const body = isMulti
                            ? {
                                action:'respond',
                                itemsKp: itemsKp.map(it=>({materialName:it.materialName, quantity:Number(it.quantity)||0, unit:it.unit, workPackage:it.workPackage||it.work_package||req.workPackage||req.work_package||'', pricePerUnit:Number(it.pricePerUnit)||0})),
                                deliveryDays: Number(newKpResponse.deliveryDays),
                                paymentTerms: newKpResponse.paymentTerms,
                                vatIncluded: newKpResponse.vatIncluded,
                                validUntil: newKpResponse.validUntil||null,
                                supplierMessage: newKpResponse.supplierMessage,
                                pdfUrl: newKpResponse.pdfUrl,
                              }
                            : {
                                action:'respond',
                                pricePerUnit: Number(newKpResponse.pricePerUnit),
                                quantity: Number(reqItems[0]?.quantity||req.quantity||0),
                                totalPrice: Number(newKpResponse.pricePerUnit) * Number(reqItems[0]?.quantity||req.quantity||0),
                                deliveryDays: Number(newKpResponse.deliveryDays),
                                paymentTerms: newKpResponse.paymentTerms,
                                vatIncluded: newKpResponse.vatIncluded,
                                validUntil: newKpResponse.validUntil||null,
                                supplierMessage: newKpResponse.supplierMessage,
                                pdfUrl: newKpResponse.pdfUrl,
                              };
                          await fetch(API+'/supplier-offers/'+o.id,{
                            method:'PUT', headers:{'Content-Type':'application/json'},
                            body: JSON.stringify(body)
                          });
                          setRespondingOfferId(null);
                          await refreshData();
                          notify('КП отправлено директору','supply');
                        }} style={btnO}><Check size={14}/>Отправить КП</button>
                        <button onClick={()=>setRespondingOfferId(null)} style={btnG}><X size={14}/>Отмена</button>
                      </div>
                    </div>);
                    })()}
                    {/* Форма выставления счёта (Сн.3) — для выигранного КП */}
                    {invoicingOfferId===o.id && (<div style={{borderTop:'1.5px solid '+C.border,paddingTop:'12px',marginTop:'10px'}}>
                      <b style={{color:C.text,fontSize:'12px',display:'block',marginBottom:'8px'}}>💳 Выставить счёт по выигранному КП</b>
                      <div style={{padding:'10px',backgroundColor:C.successLight,borderRadius:'6px',marginBottom:'10px',fontSize:'11px',color:C.text}}>
                        Условия оплаты по КП: <b>{o.paymentTerms||'Не указано'}</b>. После выставления счёт уйдёт бухгалтеру компании на оплату.
                      </div>
                      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginBottom:'8px'}}>
                        <div>
                          <label style={{fontSize:'11px',color:C.textSec,display:'block',marginBottom:'3px'}}>Номер счёта *</label>
                          <input value={newOfferInvoice.invoiceNumber} onChange={e=>setNewOfferInvoice({...newOfferInvoice,invoiceNumber:e.target.value})} placeholder='№ 123/05' style={{...inp,marginBottom:0}}/>
                        </div>
                        <div>
                          <label style={{fontSize:'11px',color:C.textSec,display:'block',marginBottom:'3px'}}>Дата счёта</label>
                          <input type='date' value={newOfferInvoice.invoiceDate} onChange={e=>setNewOfferInvoice({...newOfferInvoice,invoiceDate:e.target.value})} style={{...inp,marginBottom:0}}/>
                        </div>
                        <div>
                          <label style={{fontSize:'11px',color:C.textSec,display:'block',marginBottom:'3px'}}>Сумма (₽) *</label>
                          <input type='number' step='any' inputMode='decimal' value={newOfferInvoice.amount} onChange={e=>setNewOfferInvoice({...newOfferInvoice,amount:e.target.value})} style={{...inp,marginBottom:0}}/>
                        </div>
                        <div>
                          <label style={{fontSize:'11px',color:C.textSec,display:'block',marginBottom:'3px'}}>в т.ч. НДС (₽)</label>
                          <input type='number' step='any' inputMode='decimal' value={newOfferInvoice.vatAmount} onChange={e=>setNewOfferInvoice({...newOfferInvoice,vatAmount:e.target.value})} style={{...inp,marginBottom:0}}/>
                        </div>
                      </div>
                      <input value={newOfferInvoice.description} onChange={e=>setNewOfferInvoice({...newOfferInvoice,description:e.target.value})} placeholder='Описание (по умолчанию название материала)' style={inp}/>
                      <label style={{...btnG,padding:'8px 12px',fontSize:'12px',cursor:'pointer',display:'inline-flex',alignItems:'center',gap:'4px',marginBottom:'10px'}}>
                        <Upload size={12}/>{newOfferInvoice.fileUrl?'PDF/Фото загружен':'Прикрепить счёт (PDF/фото)'}
                        <input type='file' accept='.pdf,image/*' style={{display:'none'}} onChange={async e=>{if(e.target.files[0]){const url=await uploadPhoto(e.target.files[0],{projectName:req.project||req.projectName,context:'supplier-invoices'});setNewOfferInvoice({...newOfferInvoice,fileUrl:url});}}}/>
                      </label>
                      <div style={{display:'flex',gap:'8px'}}>
                        <button onClick={()=>createInvoiceFromOffer(o.id)} style={btnO}><Check size={14}/>Отправить счёт</button>
                        <button onClick={()=>setInvoicingOfferId(null)} style={btnG}><X size={14}/>Отмена</button>
                      </div>
                    </div>)}
                    {/* Сн.4: форма отгрузки поставщика */}
                    {shippingOfferId===o.id && (<div style={{borderTop:'1.5px solid '+C.border,paddingTop:'12px',marginTop:'10px'}}>
                      <b style={{color:C.text,fontSize:'12px',display:'block',marginBottom:'8px'}}>🚚 Отгрузка по выигранному КП</b>
                      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginBottom:'8px'}}>
                        <div>
                          <label style={{fontSize:'11px',color:C.textSec,display:'block',marginBottom:'3px'}}>Отгружено, {req.unit}</label>
                          <input type='number' step='any' inputMode='decimal' value={shipmentForm.shippedQuantity} onChange={e=>setShipmentForm({...shipmentForm,shippedQuantity:e.target.value})} style={{...inp,marginBottom:0}}/>
                        </div>
                        <div>
                          <label style={{fontSize:'11px',color:C.textSec,display:'block',marginBottom:'3px'}}>Дата накладной</label>
                          <input type='date' value={shipmentForm.waybillDate} onChange={e=>setShipmentForm({...shipmentForm,waybillDate:e.target.value})} style={{...inp,marginBottom:0}}/>
                        </div>
                        <input placeholder='Номер накладной / УПД' value={shipmentForm.waybillNumber} onChange={e=>setShipmentForm({...shipmentForm,waybillNumber:e.target.value})} style={{...inp,marginBottom:0}}/>
                        <input placeholder='Машина / госномер' value={shipmentForm.vehicleNumber} onChange={e=>setShipmentForm({...shipmentForm,vehicleNumber:e.target.value})} style={{...inp,marginBottom:0}}/>
                        <input placeholder='Водитель / контакт' value={shipmentForm.driverName} onChange={e=>setShipmentForm({...shipmentForm,driverName:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                      </div>
                      <label style={{...btnG,padding:'8px 12px',fontSize:'12px',cursor:'pointer',display:'inline-flex',alignItems:'center',gap:'4px',marginBottom:'10px'}}>
                        <Upload size={12}/>{shipmentForm.documentUrl?'Документ загружен':'Прикрепить накладную / УПД'}
                        <input type='file' accept='.pdf,image/*' style={{display:'none'}} onChange={async e=>{if(e.target.files[0]){const url=await uploadPhoto(e.target.files[0],{projectName:req.project||req.projectName,context:'supply-shipments'});setShipmentForm({...shipmentForm,documentUrl:url});}}}/>
                      </label>
                      <div style={{display:'flex',gap:'8px'}}>
                        <button onClick={()=>createShipmentFromOffer(o)} style={btnO}><Check size={14}/>Отгрузить</button>
                        <button onClick={()=>setShippingOfferId(null)} style={btnG}><X size={14}/>Отмена</button>
                      </div>
                    </div>)}
                  </div>);
                })}
              </div>));
            })()}
          </div>)}

          {supplierTab==='catalog'&&(<div>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'12px'}}>
              <b style={{color:C.text,fontSize:'14px'}}>📦 Мой каталог</b>
              <div style={{display:'flex',gap:'8px'}}>
                <label style={{...btnG,padding:'6px 12px',fontSize:'12px',cursor:'pointer',display:'flex',alignItems:'center',gap:'4px'}}>
                  📥 Excel
                  <input type='file' accept='.xlsx,.xls,.csv' style={{display:'none'}} onChange={e=>{const file=e.target.files[0];if(!file)return;const reader=new FileReader();reader.onload=async ev=>{try{const XLSX=await import('xlsx');const wb=XLSX.read(ev.target.result,{type:'array'});const ws=wb.Sheets[wb.SheetNames[0]];const rows=XLSX.utils.sheet_to_json(ws,{header:1,defval:''});let count=0;for(let i=1;i<rows.length;i++){const r=rows[i];if(!r[0])continue;const item={materialName:String(r[0]),unit:String(r[1]||'шт'),price:Number(r[2]||0),minQuantity:Number(r[3]||1),deliveryDays:Number(r[4]||3),notes:String(r[5]||''),supplierId:mySupplier?.id||0,supplierName:user.name};const res=await fetch(API+'/supplier-catalog',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(item)});const saved=await res.json();setSupplierCatalog(prev=>[...prev,{...item,id:saved.id}]);count++;}alert('Импортировано '+count+' позиций!');}catch(err){alert('Ошибка: '+err.message);}};reader.readAsArrayBuffer(file);e.target.value='';}} />
                </label>
                {supplierRequisites.priceUrl&&(<button onClick={async()=>{
                  try{
                    alert('Загрузка прайса... Это может занять несколько секунд.');
                    const res=await fetch('https://corsproxy.io/?'+encodeURIComponent(supplierRequisites.priceUrl));
                    const blob=await res.arrayBuffer();
                    const XLSX=await import('xlsx');
                    const wb=XLSX.read(blob,{type:'array'});
                    const ws=wb.Sheets[wb.SheetNames[0]];
                    const rows=XLSX.utils.sheet_to_json(ws,{header:1,defval:''});
                    let count=0;
                    for(let i=1;i<rows.length;i++){
                      const r=rows[i];
                      if(!r[0]) continue;
                      const item={materialName:String(r[0]),unit:String(r[1]||'шт'),price:Number(r[2]||0),minQuantity:Number(r[3]||1),deliveryDays:Number(r[4]||3),notes:String(r[5]||''),supplierId:mySupplier?.id||0,supplierName:user.name};
                      const res2=await fetch(API+'/supplier-catalog',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(item)});
                      const saved=await res2.json();
                      setSupplierCatalog(prev=>[...prev,{...item,id:saved.id}]);
                      count++;
                    }
                    alert('Загружено '+count+' позиций!');
                  }catch(err){alert('Ошибка загрузки: '+err.message);}
                }} style={btnG}><Download size={14}/>По ссылке</button>)}
                <button onClick={()=>setShowCatalogForm(!showCatalogForm)} style={btnO}><Plus size={14}/>Добавить</button>
              </div>
            </div>
            {showCatalogForm&&(<div style={{...card,padding:'16px',marginBottom:'12px'}}>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px'}}>
                <input placeholder='Наименование *' value={newCatalogItem.materialName} onChange={e=>setNewCatalogItem({...newCatalogItem,materialName:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                <select value={newCatalogItem.unit} onChange={e=>setNewCatalogItem({...newCatalogItem,unit:e.target.value})} style={{...inp,marginBottom:0}}>{UNITS.map(u=><option key={u}>{u}</option>)}</select>
                <input placeholder='Цена за ед.' type='number' step='any' inputMode='decimal' value={newCatalogItem.price} onChange={e=>setNewCatalogItem({...newCatalogItem,price:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Мин. партия' type='number' step='any' inputMode='decimal' value={newCatalogItem.minQuantity} onChange={e=>setNewCatalogItem({...newCatalogItem,minQuantity:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Срок поставки (дней)' type='number' step='any' inputMode='decimal' value={newCatalogItem.deliveryDays} onChange={e=>setNewCatalogItem({...newCatalogItem,deliveryDays:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Примечание' value={newCatalogItem.notes} onChange={e=>setNewCatalogItem({...newCatalogItem,notes:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
              </div>
              <div style={{display:'flex',gap:'8px',marginTop:'10px'}}>
                <button onClick={async()=>{
                  if(!newCatalogItem.materialName) return;
                  const res=await fetch(API+'/supplier-catalog',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...newCatalogItem,supplierId:mySupplier?.id||0,supplierName:user.name})});
                  const saved=await res.json();
                  setSupplierCatalog(prev=>[...prev,{...newCatalogItem,id:saved.id,supplierId:mySupplier?.id||0}]);
                  setNewCatalogItem({materialName:'',unit:'шт',price:'',minQuantity:'1',deliveryDays:'3',notes:''});
                  setShowCatalogForm(false);
                }} style={btnO}><Check size={14}/>Сохранить</button>
                <button onClick={()=>setShowCatalogForm(false)} style={btnG}><X size={14}/>Отмена</button>
              </div>
            </div>)}
            <table style={tbl}><thead><tr>
              <th style={tblH}>Наименование</th>
              <th style={tblH}>Ед.</th>
              <th style={tblH}>Цена</th>
              <th style={tblH}>Мин. партия</th>
              <th style={tblH}>Поставка</th>
              <th style={tblH}>Наличие</th>
              <th style={tblH}></th>
            </tr></thead><tbody>
              {myCatalog.map(item=>(<tr key={item.id}>
                <td style={tblC}>{item.materialName}</td>
                <td style={tblC}>{item.unit}</td>
                <td style={tblC}>{Number(item.price).toLocaleString()+' ₽'}</td>
                <td style={tblC}>{item.minQuantity}</td>
                <td style={tblC}>{item.deliveryDays+' дн.'}</td>
                <td style={tblC}><span style={{color:item.inStock?C.success:C.danger,fontSize:'12px'}}>{item.inStock?'✅ Есть':'❌ Нет'}</span></td>
                <td style={tblC}><button onClick={async()=>{await fetch(API+'/supplier-catalog/'+item.id,{method:'DELETE'});setSupplierCatalog(prev=>prev.filter(c=>c.id!==item.id));}} style={{...btnR,padding:'3px 7px'}}><Trash2 size={11}/></button></td>
              </tr>))}
            </tbody></table>
            {myCatalog.length===0&&<p style={{color:C.textMuted,fontSize:'12px',textAlign:'center',padding:'20px'}}>Каталог пуст — добавьте материалы</p>}
          </div>)}

          {supplierTab==='offers'&&(<div>
            <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>Мои предложения</b>
            {myOffers.map(o=>(<div key={o.id} style={{...card,padding:'12px',marginBottom:'8px'}}>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',marginBottom:'8px'}}>
                <div>
                  <b style={{fontSize:'13px',color:C.text}}>{(()=>{const r=supplyRequests.find(r=>r.id===o.requestId);if(!r) return 'Материал';const items=parseSupplyItems(r);return items.length>1?('📋 Пакет из '+items.length+' позиций'):(items[0]?.materialName||r.materialName||'Материал');})()}</b>
                  {Number(o.pricePerUnit||0)>0
                    ? <p style={{color:C.textSec,margin:'2px 0',fontSize:'11px'}}>{Number(o.pricePerUnit||0).toLocaleString('ru-RU')+' руб/ед · '+Number(o.totalPrice||0).toLocaleString('ru-RU')+' руб'+(o.deliveryDays?' · '+o.deliveryDays+' дн.':'')}</p>
                    : <p style={{color:C.textMuted,margin:'2px 0',fontSize:'11px',fontStyle:'italic'}}>⏳ Не отправлено ещё</p>}
                </div>
                <span style={{padding:'3px 8px',borderRadius:'6px',fontSize:'11px',backgroundColor:o.status==='Утверждено'?C.successLight:C.warningLight,color:o.status==='Утверждено'?C.success:C.warning}}>{o.status==='Утверждено'?'Утверждено':'Ожидает'}</span>
              </div>
              {o.status==='Утверждено'&&(<p style={{fontSize:'11px',color:C.textSec,margin:'6px 0 0'}}>Отгрузка теперь оформляется из вкладки «📋 Заявки» по выигранному КП, чтобы не обходить счёт и приёмку.</p>)}
            </div>))}
            {myOffers.length===0&&<p style={{color:C.textMuted,fontSize:'12px',textAlign:'center',padding:'20px'}}>Предложений нет</p>}
          </div>)}

          {supplierTab==='deliveries'&&(<div>
            <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>🚚 Мои отгрузки</b>
            {myDeliveries.map(d=>{const claim=myClaims.find(c=>c.deliveryId===d.id);return(<div key={d.id} style={{...card,padding:'12px',marginBottom:'8px',borderLeft:'3px solid '+(d.status==='Принято'?C.success:d.status==='Проблема'?C.danger:C.warning)}}>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
                <div>
                  <b style={{fontSize:'13px',color:C.text}}>{d.materialName}</b>
                  <p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{d.shippedQuantity||d.plannedQuantity} {d.unit} · 🏗 {d.project||'—'} · накл. {d.waybillNumber||'—'}</p>
                  {d.receivedBy&&<p style={{color:C.textMuted,margin:0,fontSize:'11px'}}>Принял: {d.receivedBy} · принято {d.receivedQuantity||0} {d.unit}</p>}
                  {claim&&<p style={{color:C.danger,margin:'4px 0 0',fontSize:'11px'}}>⚠️ Претензия: {claim.claimType} · {claim.status}</p>}
                </div>
                <span style={badge(d.status==='Принято'?C.success:d.status==='Проблема'?C.danger:C.warning,d.status==='Принято'?C.successLight:d.status==='Проблема'?C.dangerLight:C.warningLight,d.status==='Принято'?C.successBorder:d.status==='Проблема'?C.dangerBorder:C.warningBorder)}>{d.status}</span>
              </div>
            </div>);})}
            {myDeliveries.length===0&&<p style={{color:C.textMuted,fontSize:'12px',textAlign:'center',padding:'20px'}}>Отгрузок пока нет</p>}
          </div>)}

          {supplierTab==='documents'&&(<div>
            <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>📄 Мои счета</b>
            {mySupplierInvoices.map(inv=>(
              <div key={inv.id} style={{padding:'10px',backgroundColor:C.bg,borderRadius:'8px',marginBottom:'6px',border:'1.5px solid '+C.border,display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                <div>
                  <b style={{fontSize:'12px',color:C.text}}>Счёт № {inv.invoiceNumber||'—'}</b>
                  <p style={{color:C.textSec,margin:'2px 0',fontSize:'11px'}}>{(inv.invoiceDate||'')+' · '+Number(inv.amount||0).toLocaleString('ru-RU')+' ₽ · '+(inv.projectName||'—')}</p>
                  {inv.paidAmount>0&&<p style={{color:C.success,margin:0,fontSize:'11px'}}>Оплачено: {Number(inv.paidAmount||0).toLocaleString('ru-RU')} ₽</p>}
                </div>
                <span style={badge(inv.status==='Оплачен'?C.success:inv.status==='Частично оплачен'?C.warning:C.info,inv.status==='Оплачен'?C.successLight:inv.status==='Частично оплачен'?C.warningLight:C.infoLight,inv.status==='Оплачен'?C.successBorder:inv.status==='Частично оплачен'?C.warningBorder:C.infoBorder)}>{inv.status}</span>
              </div>
            ))}
            {mySupplierInvoices.length===0&&<p style={{color:C.textMuted,fontSize:'12px',textAlign:'center',padding:'20px'}}>Счетов пока нет</p>}
          </div>)}

          {supplierTab==='claims'&&(<div>
            <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>⚠️ Претензии по поставкам</b>
            {myClaims.map(c=>(<div key={c.id} style={{...card,padding:'12px',marginBottom:'8px',borderLeft:'3px solid '+(c.status==='Открыта'?C.danger:C.success)}}>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
                <div>
                  <b style={{fontSize:'13px',color:C.text}}>{c.materialName}</b>
                  <p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{c.claimType} · 🏗 {c.project||'—'}</p>
                  <p style={{color:C.textSec,margin:'2px 0',fontSize:'11px'}}>{c.description}</p>
                </div>
                <span style={badge(c.status==='Открыта'?C.danger:C.success,c.status==='Открыта'?C.dangerLight:C.successLight,c.status==='Открыта'?C.dangerBorder:C.successBorder)}>{c.status}</span>
              </div>
            </div>))}
            {myClaims.length===0&&<p style={{color:C.textMuted,fontSize:'12px',textAlign:'center',padding:'20px'}}>Претензий нет</p>}
          </div>)}

          {supplierTab==='profile'&&(<div>
            <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>⚙️ Реквизиты компании</b>
            <div style={{...card,padding:'16px',marginBottom:'14px'}}>
              <b style={{color:C.textSec,fontSize:'12px',display:'block',marginBottom:'10px'}}>📋 Основное</b>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px'}}>
                <input placeholder='Название компании' value={supplierRequisites.companyName} onChange={e=>setSupplierRequisites({...supplierRequisites,companyName:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                <input placeholder='ИНН' value={supplierRequisites.inn} onChange={e=>setSupplierRequisites({...supplierRequisites,inn:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='КПП' value={supplierRequisites.kpp} onChange={e=>setSupplierRequisites({...supplierRequisites,kpp:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='ОГРН/ОГРНИП' value={supplierRequisites.ogrn||''} onChange={e=>setSupplierRequisites({...supplierRequisites,ogrn:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                <input placeholder='Юридический адрес' value={supplierRequisites.address} onChange={e=>setSupplierRequisites({...supplierRequisites,address:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                <input placeholder='Фактический адрес' value={supplierRequisites.actualAddress||''} onChange={e=>setSupplierRequisites({...supplierRequisites,actualAddress:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                <input placeholder='Директор (ФИО)' value={supplierRequisites.directorName||''} onChange={e=>setSupplierRequisites({...supplierRequisites,directorName:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Должность директора' value={supplierRequisites.directorPosition||''} onChange={e=>setSupplierRequisites({...supplierRequisites,directorPosition:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Телефон' value={supplierRequisites.phone} onChange={e=>setSupplierRequisites({...supplierRequisites,phone:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Email' value={supplierRequisites.email} onChange={e=>setSupplierRequisites({...supplierRequisites,email:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Сайт (опц.)' value={supplierRequisites.website||''} onChange={e=>setSupplierRequisites({...supplierRequisites,website:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                <input placeholder='Специализация (что поставляете)' value={supplierRequisites.specialization||''} onChange={e=>setSupplierRequisites({...supplierRequisites,specialization:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                <textarea placeholder='Примечания / предмет договора' value={supplierRequisites.notes||''} onChange={e=>setSupplierRequisites({...supplierRequisites,notes:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2',minHeight:'64px',resize:'vertical',fontFamily:'inherit'}}/>
              </div>
              <b style={{color:C.textSec,fontSize:'12px',display:'block',marginBottom:'8px',marginTop:'12px'}}>🏦 Банковские реквизиты</b>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px'}}>
                <input placeholder='Банк' value={supplierRequisites.bank} onChange={e=>setSupplierRequisites({...supplierRequisites,bank:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                <input placeholder='БИК' value={supplierRequisites.bik} onChange={e=>setSupplierRequisites({...supplierRequisites,bik:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Корр. счёт' value={supplierRequisites.korAccount||''} onChange={e=>setSupplierRequisites({...supplierRequisites,korAccount:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Расчётный счёт' value={supplierRequisites.account} onChange={e=>setSupplierRequisites({...supplierRequisites,account:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
              </div>
              <b style={{color:C.textSec,fontSize:'12px',display:'block',marginBottom:'8px',marginTop:'12px'}}>📄 Договор поставки</b>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginBottom:'8px'}}>
                <input placeholder='Номер договора' value={supplierRequisites.contractNumber||''} onChange={e=>setSupplierRequisites({...supplierRequisites,contractNumber:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input type='date' placeholder='Дата договора' value={supplierRequisites.contractDate||''} onChange={e=>setSupplierRequisites({...supplierRequisites,contractDate:e.target.value})} style={{...inp,marginBottom:0}}/>
              </div>
              <label style={{...btnG,padding:'10px 14px',fontSize:'12px',cursor:'pointer',display:'inline-flex',alignItems:'center',gap:'6px',marginRight:'8px'}}>
                <Upload size={14}/>{supplierRequisites.contractUrl?'✅ Договор загружен':'Загрузить договор (PDF)'}
                <input type='file' accept='.pdf,image/*' style={{display:'none'}} onChange={async e=>{if(e.target.files[0]){const url=await uploadPhoto(e.target.files[0],{context:'supplier-documents'});setSupplierRequisites({...supplierRequisites,contractUrl:url});}}}/>
              </label>
              {supplierRequisites.contractUrl && (<a href={fileSrc(supplierRequisites.contractUrl)} target='_blank' rel='noopener noreferrer' style={{fontSize:'12px',color:C.accent,marginRight:'8px'}}>📥 Посмотреть</a>)}
              <DocumentRecognitionPanel
                C={C}
                card={card}
                inp={inp}
                btnG={btnG}
                btnO={btnO}
                btnB={btnB}
                uploadPhoto={uploadPhoto}
                fileSrc={fileSrc}
                projectName={supplierRequisites.companyName || user.name || 'Поставщик'}
                context="supplier-documents"
                entityType="supplier"
                currentFields={supplierRequisites}
                onApplyExtracted={result => setSupplierRequisites(prev => ({...prev, ...supplierRequisitesPatchFromRecognition(result, prev)}))}
                applyExtractedLabel="Заполнить реквизиты"
                onCreateRecognizedDocument={mySupplier?.id ? createOwnSupplierDocumentFromRecognition : null}
                createRecognizedDocumentLabel="Добавить в документы"
              />
              <b style={{color:C.textSec,fontSize:'12px',display:'block',marginBottom:'8px',marginTop:'12px'}}>📦 Прайс-лист (опц.)</b>
              <input placeholder='Ссылка на прайс (Google Sheet / Excel URL)' value={supplierRequisites.priceUrl||''} onChange={e=>setSupplierRequisites({...supplierRequisites,priceUrl:e.target.value})} style={inp}/>
              <label style={{...btnG,padding:'10px 14px',fontSize:'12px',cursor:'pointer',display:'inline-flex',alignItems:'center',gap:'6px',marginRight:'8px'}}>
                <Upload size={14}/>{supplierRequisites.licenseUrl?'✅ Лицензия загружена':'Загрузить лицензию/сертификат'}
                <input type='file' accept='.pdf,image/*' style={{display:'none'}} onChange={async e=>{if(e.target.files[0]){const url=await uploadPhoto(e.target.files[0],{context:'supplier-documents'});setSupplierRequisites({...supplierRequisites,licenseUrl:url});}}}/>
              </label>
              {supplierRequisites.licenseUrl && (<a href={fileSrc(supplierRequisites.licenseUrl)} target='_blank' rel='noopener noreferrer' style={{fontSize:'12px',color:C.accent}}>📥 Посмотреть</a>)}
              <button onClick={async()=>{
                const res = await fetch(API+'/suppliers/'+(mySupplier?.id||0)+'/requisites',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({
                  ...supplierRequisites,
                  legalAddress: supplierRequisites.address // alias
                })});
                if (res.ok) {
                  localStorage.setItem('supplierReq_'+user.id,JSON.stringify(supplierRequisites));
                  alert('Реквизиты сохранены!');
                  await refreshData();
                } else {
                  alert('Ошибка сохранения');
                }
              }} style={{...btnO,marginTop:'14px',width:'100%',justifyContent:'center',padding:'12px'}}><Check size={14}/>Сохранить реквизиты</button>
            </div>
          </div>)}
        </div>
      </div>
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
          {activePage==='dashboard'&&(()=>{
            if(!initialDataLoaded){
              return (
                <div style={{minHeight:'100%',padding:'28px',background:'radial-gradient(circle at 15% 0%,rgba(249,115,22,.15),transparent 32%),linear-gradient(135deg,#0b1120 0%,#111827 100%)',color:'#f8fafc'}}>
                  <DashboardTopBar C={C} setSidebarVisible={setSidebarVisible} darkMode={darkMode} setDarkMode={setDarkMode} setShowChatPanel={setShowChatPanel} unreadMessagesCount={unreadMessagesCount} setShowAiAssistant={setShowAiAssistant} showAiAssistant={showAiAssistant} showNotifications={showNotifications} toggleNotifications={toggleNotifications} unreadNotifications={unreadNotifications} btnG={btnG} btnO={btnO} myNotifications={myNotifications} notifications={notifications} markMyNotificationsRead={markMyNotificationsRead} closeNotifications={closeNotifications} navigateTo={navigateTo} getNotifPage={getNotifPage} setShowNotifications={setShowNotifications} setNotifications={setNotifications} user={user} setUser={setUser} API={API} setShowQuickActions={setShowQuickActions} isMobile={isMobile}/>
                  <div style={{marginTop:'24px',background:'rgba(17,24,39,.88)',border:'1px solid rgba(148,163,184,.18)',borderRadius:'22px',padding:'24px',boxShadow:'0 18px 60px rgba(0,0,0,.25)'}}>
                    <div style={{fontSize:'18px',fontWeight:800,marginBottom:'8px'}}>Загружаю данные объекта</div>
                    <div style={{color:'#94a3b8',fontSize:'14px'}}>Сейчас подтягиваются сметы, задачи, склад и журналы. Нули на дашборде не показываются до окончания загрузки.</div>
                  </div>
                </div>
              );
            }
            const _today=new Date().toISOString().split('T')[0];
            const dashboardProjects = visibleActiveProjects(projects||[]);
            const risks=[];
            // Низкие остатки материалов
            lowStock.slice(0,2).forEach(m=>risks.push({icon:'📦',text:'Мало на объекте: '+m.name,severity:'warn',page:'warehouse'}));
            lowMainStock.slice(0,2).forEach(m=>risks.push({icon:'🏭',text:'Мало на складе: '+m.name,severity:'warn',page:'warehouse',tab:'main'}));
            // Просроченные проекты
            dashboardProjects.filter(p=>p.deadline&&p.deadline<_today).slice(0,2).forEach(p=>risks.push({icon:'⏰',text:'Срок истёк: '+p.name+' (до '+p.deadline+')',severity:'danger',page:'projects'}));
            // АОСР зависшие в черновике > 7 дней
            const _weekAgo=new Date(Date.now()-7*24*3600*1000).toISOString().split('T')[0];
            (hiddenActs||[]).filter(a=>a.status!=='Подписан'&&a.createdAt&&String(a.createdAt).split('T')[0]<_weekAgo).slice(0,2).forEach(a=>risks.push({icon:'🔒',text:'АОСР долго без подписи: '+a.actNumber,severity:'warn',page:'projects'}));
            // Открытые замечания ГСН
            const openInsp=(inspectionOrders||[]).filter(o=>o.status!=='Закрыто').length;
            if(openInsp>0) risks.push({icon:'🏛',text:'Открытых замечаний ГСН: '+openInsp,severity:'danger',page:'projects'});
            // Изменения к смете отдельной допработой >10%
            dashboardProjects.forEach(p=>{const budget=Number(p.budget||0);if(budget<=0) return;const sumUnx=(unexpectedWorksList||[]).filter(u=>u.projectName===p.name&&isApprovedEstimateChangeStatus(u.status)&&u.changeType!=='Исключение объёма'&&!u.includedInEstimateId).reduce((s,u)=>s+Number(u.total||0),0);const pct=sumUnx/budget*100;if(pct>10) risks.push({icon:'💸',text:p.name+': изменения к смете '+pct.toFixed(1)+'% от бюджета',severity:'danger',page:'projects'});});
            // Траты сотрудников на возмещении
            const pendingExp=(ownExpenses||[]).filter(e=>e.status==='Ожидает');
            if(pendingExp.length>0){const sum=pendingExp.reduce((s,e)=>s+Number(e.amount||0),0);risks.push({icon:'💸',text:'К возмещению сотрудникам: '+Math.round(sum).toLocaleString('ru-RU')+' ₽ ('+pendingExp.length+' трат)',severity:'warn',action:'reimburse'});}
            const openAiControl=(aiFindings||[]).filter(f=>isOpenAiStatus(f.status));
            const criticalAiControl=openAiControl.filter(f=>f.severity==='Критично'||f.severity==='Не хватает данных');
            if(openAiControl.length>0) risks.push({icon:'🤖',text:'ИИ-контроль: '+openAiControl.length+' замечаний, из них важных '+criticalAiControl.length,severity:criticalAiControl.length?'danger':'warn',page:'projects'});
            const _projProgress=projectRealProgress;
            const avgProg=dashboardProjects.length?Math.round(dashboardProjects.reduce((s,p)=>s+_projProgress(p),0)/dashboardProjects.length):0;
            // Выполнено = работы (max сметы/журнала) + материалы + утв.доп.соглашения по всем проектам
            const dashboardBudgetSpent = dashboardProjects.map(p=>({projectId:p.id,projectName:p.name,spent:projectBudgetSpent(p)}));
            const dashboardBudgetSpentById = new Map(dashboardBudgetSpent.map(x=>[String(x.projectId),x.spent]));
            const dashboardBudgetSpentByName = new Map(dashboardBudgetSpent.map(x=>[x.projectName,x.spent]));
            const totalDone=dashboardBudgetSpent.reduce((s,x)=>s+Number(x.spent?.total||0),0);
            const dashboardJournalExpenses = (projectPayments||[]).reduce((sum,pay)=>{const signed=projectPaymentSignedAmount(pay);return signed<0?sum+Math.abs(signed):sum;},0);
            const dashboardDirectExpenses = (manualExpenses||[])
              .filter(expense=>!expense.ownExpenseId&&expense.source!=='own_expense')
              .reduce((sum,expense)=>sum+Number(expense.amount||0),0);
            const dashboardAccountableExpenses = (accountablePayments||[]).reduce((sum,payment)=>sum+Number(payment.amount||0),0);
            const dashboardAccountingExpenses = dashboardJournalExpenses + dashboardDirectExpenses + dashboardAccountableExpenses;
            const dashboardProjectPreviewLimit=isMobile?3:5;
            const openSupplyDashboard = (tab) => { setActivePage('supply'); setSupplyTab(tab); setShowSupplyForm(false); setShowForm(false); };
            const dashboardExtraKey = 'dashboard-extra-panels';
            const showDashboardExtra = !isMobile || !!mobileExpandedRenderLists[dashboardExtraKey];
            const showSupplyDashboard = showDashboardExtra && ['директор','зам_директора','бухгалтер','прораб','кладовщик','снабженец'].includes(user.role);
            const supplyPendingRequests = showDashboardExtra ? (supplyRequests||[]).filter(r=>{
              if (user.role==='прораб') return r.status==='Новая';
              if (isLeadership()) return r.status==='Новая'||r.status==='Подтверждена прорабом';
              return r.status==='Утверждена'||r.status==='КП запрошены';
            }) : [];
            const supplyOffersToReview = showDashboardExtra ? (supplierOffers||[]).filter(o=>o.status==='Получено') : [];
            const supplyInvoicesToPay = showDashboardExtra ? (supplierInvoices||[]).filter(i=>i.status==='На утверждении'||i.status==='Утверждён'||i.status==='Частично оплачен'||!i.status) : [];
            const supplyInvoiceDebt = showDashboardExtra ? supplyInvoicesToPay.reduce((s,i)=>s+Math.max(0,Number(i.amount||i.totalAmount||0)-Number(i.paidAmount||0)),0) : 0;
            const directorSkillDate = showDashboardExtra ? (normalizeDocDate(dailyReportDate)||_today) : _today;
            const directorSkillDailyWorks = showDashboardExtra ? (workJournal||[]).filter(w=>workDocDate(w)===directorSkillDate) : [];
            const directorSkillEstimateIssues = showDashboardExtra && isLeadership()?estimateControlIssues().length:0;
            const directorSkillSupplyIssues = showDashboardExtra ? lowStock.length+lowMainStock.length
              +(supplyRequests||[]).filter(r=>r.status==='Новая'||r.status==='Подтверждена прорабом').length
              +(supplierInvoices||[]).filter(i=>i.status==='На утверждении'||!i.status).length : 0;
            const directorSkillCards = showDashboardExtra ? [
              {label:'Сводка директору',sub:'риски, деньги, задачи',icon:<Bot size={18}/>,color:'#fdba74',bg:'rgba(234,88,12,.14)',border:'rgba(234,88,12,.32)',metric:risks.length+' рисков',onClick:()=>showPreview(buildDirectorBriefReportContent(directorSkillDate),'Сводка директора — '+new Date(directorSkillDate+'T00:00:00').toLocaleDateString('ru-RU'))},
              {label:'ИИ-контроль',sub:'обмеры и поручения',icon:<Bot size={18}/>,color:'#fca5a5',bg:'rgba(239,68,68,.12)',border:'rgba(239,68,68,.28)',metric:openAiControl.length+' замеч.',onClick:()=>navigateTo('projects')},
              {label:'Ежедневный отчёт',sub:'работы по объектам',icon:<FileText size={18}/>,color:'#86efac',bg:'rgba(34,197,94,.12)',border:'rgba(34,197,94,.28)',metric:directorSkillDailyWorks.length+' работ',onClick:()=>showPreview(buildDailyObjectReportContent(directorSkillDate),'Ежедневный отчет — '+new Date(directorSkillDate+'T00:00:00').toLocaleDateString('ru-RU'))},
              {label:'Проверка смет',sub:'нули, дубли, бюджет',icon:<Calculator size={18}/>,color:'#93c5fd',bg:'rgba(59,130,246,.12)',border:'rgba(59,130,246,.28)',metric:directorSkillEstimateIssues+' замеч.',onClick:openEstimateControlReport},
              {label:'Склад и снабжение',sub:'остатки, заявки, счета',icon:<Package size={18}/>,color:'#c4b5fd',bg:'rgba(139,92,246,.12)',border:'rgba(139,92,246,.28)',metric:directorSkillSupplyIssues+' задач',onClick:()=>showPreview(buildSupplyControlReportContent(),'Контроль снабжения и склада')},
            ] : [];
            return(
            <div style={{minHeight:'100%',padding:'28px',background:'radial-gradient(circle at 15% 0%,rgba(249,115,22,.15),transparent 32%),linear-gradient(135deg,#0b1120 0%,#111827 100%)',color:'#f8fafc'}}>
              <DashboardTopBar C={C} setSidebarVisible={setSidebarVisible} darkMode={darkMode} setDarkMode={setDarkMode} setShowChatPanel={setShowChatPanel} unreadMessagesCount={unreadMessagesCount} setShowAiAssistant={setShowAiAssistant} showAiAssistant={showAiAssistant} showNotifications={showNotifications} toggleNotifications={toggleNotifications} unreadNotifications={unreadNotifications} btnG={btnG} btnO={btnO} myNotifications={myNotifications} notifications={notifications} markMyNotificationsRead={markMyNotificationsRead} closeNotifications={closeNotifications} navigateTo={navigateTo} getNotifPage={getNotifPage} setShowNotifications={setShowNotifications} setNotifications={setNotifications} user={user} setUser={setUser} API={API} setShowQuickActions={setShowQuickActions} isMobile={isMobile}/>
              <DashboardStatsGrid dashboardProjects={dashboardProjects} avgProg={avgProg} totalDone={totalDone} totalExpenses={dashboardAccountingExpenses} setActivePage={setActivePage} navigateTo={navigateTo} setAccountingTab={setAccountingTab}/>
              {showDashboardExtra&&<DashboardDirectorAiPanel isLeadership={isLeadership} directorSkillCards={directorSkillCards} dailyReportDate={dailyReportDate} setDailyReportDate={setDailyReportDate} canUseDirectorAgent={canUseDirectorAgent} directorAgentLoading={directorAgentLoading} askDirectorAgent={askDirectorAgent} directorAgentQuestion={directorAgentQuestion} setDirectorAgentQuestion={setDirectorAgentQuestion} isMobile={isMobile} directorAgentAnswer={directorAgentAnswer} directorAgentError={directorAgentError} directorAgentSteps={directorAgentSteps}/>}
              {showDashboardExtra&&<DashboardSupplyPanel showSupplyDashboard={showSupplyDashboard} user={user} openSupplyDashboard={openSupplyDashboard} supplyPendingRequests={supplyPendingRequests} supplyOffersToReview={supplyOffersToReview} supplyInvoicesToPay={supplyInvoicesToPay} supplyInvoiceDebt={supplyInvoiceDebt}/>}
              <div style={{display:'grid',gridTemplateColumns:isMobile?'1fr':'1.3fr 0.7fr',gap:'16px'}}>
                <div style={{background:'rgba(17,24,39,.88)',border:'1px solid rgba(148,163,184,.18)',borderRadius:'22px',padding:'20px',backdropFilter:'blur(24px)'}}>
                  <h2 style={{margin:'0 0 16px',fontSize:'18px',color:'#f8fafc'}}>Ключевые объекты</h2>
                  {dashboardProjects.slice(0,dashboardProjectPreviewLimit).map(p=>{const bs=dashboardBudgetSpentById.get(String(p.id))||dashboardBudgetSpentByName.get(p.name)||{works:0,materials:0,unexpected:0,total:0};const factTotal=bs.total;const realProg=_projProgress(p);return(
                    <div key={p.id} onClick={()=>{setExpandedProject(p.id);navigateTo('projects');}} style={{padding:'16px',borderRadius:'18px',background:'rgba(30,41,59,.62)',border:'1px solid rgba(148,163,184,.18)',marginBottom:'10px',cursor:'pointer'}}>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'12px'}}>
                        <div><div style={{fontWeight:'800',fontSize:'15px',color:'#f8fafc'}}>{p.name}</div><div style={{color:'#94a3b8',fontSize:'12px',marginTop:'3px'}}>{p.client||'Без заказчика'} · {p.status}</div></div>
                        <span style={{display:'inline-flex',borderRadius:'999px',padding:'4px 10px',fontSize:'11px',fontWeight:'700',background:'rgba(234,88,12,.14)',color:'#fdba74',border:'1px solid rgba(234,88,12,.32)',whiteSpace:'nowrap'}}>{realProg}%</span>
                      </div>
                      <div style={{height:'6px',background:'rgba(148,163,184,.16)',borderRadius:'999px',overflow:'hidden',margin:'10px 0'}}>
                        <div style={{height:'100%',borderRadius:'999px',background:'linear-gradient(90deg,#f97316,#22c55e)',width:`${realProg}%`}}/>
                      </div>
                      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:'8px'}}>
                        <div style={{background:'rgba(30,41,59,.6)',border:'1px solid rgba(148,163,184,.18)',borderRadius:'12px',padding:'10px'}}><div style={{color:'#94a3b8',fontSize:'11px'}}>Бюджет</div><div style={{fontWeight:'700',color:'#f8fafc',fontSize:'13px',marginTop:'3px'}}>{(Number(p.budget||0)/1000).toFixed(0)+' тыс'}</div></div>
                        <div style={{background:'rgba(30,41,59,.6)',border:'1px solid rgba(148,163,184,.18)',borderRadius:'12px',padding:'10px'}} title={'Работы: '+Math.round(bs.works).toLocaleString('ru-RU')+' ₽\nМатериалы: '+Math.round(bs.materials).toLocaleString('ru-RU')+' ₽'+(bs.unexpected>0?'\nДоп.соглашения: '+Math.round(bs.unexpected).toLocaleString('ru-RU')+' ₽':'')}><div style={{color:'#94a3b8',fontSize:'11px'}}>Выполнено</div><div style={{fontWeight:'700',color:'#86efac',fontSize:'13px',marginTop:'3px'}}>{factTotal>0?(factTotal/1000).toFixed(0)+' тыс':'0'}</div></div>
                        <div style={{background:'rgba(30,41,59,.6)',border:'1px solid rgba(148,163,184,.18)',borderRadius:'12px',padding:'10px'}}><div style={{color:'#94a3b8',fontSize:'11px'}}>Срок</div><div style={{fontWeight:'700',color:'#f8fafc',fontSize:'13px',marginTop:'3px'}}>{p.deadline||'—'}</div></div>
                      </div>
                      <div style={{marginTop:'10px',padding:'8px 12px',borderRadius:'12px',background:'rgba(234,88,12,.12)',border:'1px solid rgba(234,88,12,.24)',color:'#fed7aa',fontSize:'12px',fontWeight:'700'}}>{realProg<40?'⚠️ AI: низкий темп':realProg>80?'✅ AI: близко к сдаче':'🔵 AI: темп в норме'}</div>
                    </div>
                  );})}
                  {isMobile&&dashboardProjects.length>dashboardProjectPreviewLimit&&(
                    <button type="button" onClick={()=>navigateTo('projects')} style={{...btnG,width:'100%',justifyContent:'center',marginTop:'8px',borderColor:'rgba(148,163,184,.28)',background:'rgba(30,41,59,.72)',color:'#e2e8f0'}}>
                      Показать все объекты ({dashboardProjects.length})
                    </button>
                  )}
                </div>
                <div style={{display:'flex',flexDirection:'column',gap:'16px'}}>
                  <DashboardRisksPanel risks={risks} setShowReimburseModal={setShowReimburseModal} setActivePage={setActivePage} setWarehouseTab={setWarehouseTab}/>
                  {!showDashboardExtra&&isMobile&&(
                    <button type="button" onClick={()=>setMobileExpandedRenderLists(prev=>({...prev,[dashboardExtraKey]:true}))} style={{...btnO,width:'100%',justifyContent:'center',padding:'12px 14px'}}>
                      Загрузить рабочие панели
                    </button>
                  )}
                  {showDashboardExtra&&<DashboardProductionSummaryPanel workJournal={workJournal} workDocDate={workDocDate} normalizeDocDate={normalizeDocDate} dailyReportDate={dailyReportDate} setDailyReportDate={setDailyReportDate} user={user} showPreview={showPreview} buildDailyObjectReportContent={buildDailyObjectReportContent} setActivePage={setActivePage} setAccountingTab={setAccountingTab}/>}
                  {showDashboardExtra&&<DashboardActivityPanel activityLog={activityLog}/>}
                </div>
              </div>
              <div style={{height:'100px'}}/>
            </div>
            );
          })()}
          {activePage==='projects'&&canAccess('projects')&&(<div>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'20px',flexWrap:'wrap',gap:'10px'}}>
              <div style={{display:'flex',gap:'8px',flexWrap:'wrap'}}>
                {isLeadership()&&<button onClick={()=>{setShowForm(showForm===true?false:true);setEditingItem(null);setNewProject({name:'',client:'',status:'Планирование',budget:'',deadline:'',progress:0,tasks:[],pricelistId:null});}} style={btnO}><Plus size={14}/>Новый проект</button>}
                {projects.some(pr=>pr.archived)&&<button onClick={()=>setShowArchive(!showArchive)} style={btnG}><Archive size={14}/>{showArchive?'Активные':'Архив'}</button>}
              </div>
            </div>
            {showArchive&&<div style={{...card,padding:'12px 14px',marginBottom:'14px',backgroundColor:C.warningLight,border:'1.5px solid '+C.warningBorder}}><p style={{margin:0,color:C.text,fontSize:'12px'}}>📦 <b>Архив закрытых объектов.</b> Здесь хранятся завершённые объекты со всеми документами, перепиской и актами только для просмотра.</p></div>}
            {showForm===true&&isLeadership()&&(<div style={{...card,padding:'20px',marginBottom:'20px'}}>
              <h3 style={{color:C.text,marginBottom:'15px',fontWeight:'700'}}>{editingItem?'Редактировать проект':'Новый проект'}</h3>
              <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(200px,1fr))',gap:'10px'}}>
                <input placeholder="Название *" value={newProject.name} onChange={e=>setNewProject({...newProject,name:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder="Заказчик (название)" value={newProject.client} onChange={e=>setNewProject({...newProject,client:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder="Email заказчика (для доступа в кабинет)" value={newProject.clientEmail||''} onChange={e=>setNewProject({...newProject,clientEmail:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder="Пароль заказчика" value={newProject.clientPassword||''} onChange={e=>setNewProject({...newProject,clientPassword:e.target.value})} style={{...inp,marginBottom:0}}/>
                <select value={newProject.status} onChange={e=>setNewProject({...newProject,status:e.target.value})} style={{...inp,marginBottom:0}}>{['Планирование','В работе','Заморожен'].map(s=><option key={s}>{s}</option>)}</select>
                <input placeholder="Бюджет" type="number" step="any" inputMode="decimal" value={newProject.budget} onChange={e=>setNewProject({...newProject,budget:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder="Дедлайн" type="date" value={newProject.deadline} onChange={e=>setNewProject({...newProject,deadline:e.target.value})} style={{...inp,marginBottom:0}}/>
                <select value={newProject.pricelistId||''} onChange={e=>setNewProject({...newProject,pricelistId:e.target.value?Number(e.target.value):null})} style={{...inp,marginBottom:0}}><option value="">Прайс-лист</option>{pricelists.filter(pl=>!isEstimatePricelist(pl)||Number(pl.id)===Number(newProject.pricelistId)).map(pl=><option key={pl.id} value={pl.id}>{pl.name}</option>)}</select>
                <input placeholder="Этажей (например: 3)" type="number" step="any" inputMode="decimal" value={newProject.floors||''} onChange={e=>setNewProject({...newProject,floors:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder="Литеры (например: А,Б,В)" value={newProject.liters||''} onChange={e=>setNewProject({...newProject,liters:e.target.value})} style={{...inp,marginBottom:0}}/>
              </div>
              <div style={{display:'flex',gap:'10px',marginTop:'15px'}}><button onClick={saveProject} style={btnO}><Check size={14}/>{editingItem?'Сохранить':'Создать'}</button><button onClick={()=>{setShowForm(false);setEditingItem(null);}} style={btnG}><X size={14}/>Отмена</button></div>
            </div>)}
            {visibleProjects((showArchive?projects.filter(pr=>pr.archived):projects.filter(pr=>!pr.archived))).map(p=>{
              const _bs=projectBudgetSpent(p);const total=_bs.total;
              const isOpen=expandedProject===p.id;
              const shouldRenderProjectOverview=isOpen&&activeProjectTab==='Общее';
              const cat=shouldRenderProjectOverview&&isFinanceRole()?expByCategory(p.name):{};
              const economy=shouldRenderProjectOverview&&isFinanceRole()?projectEconomy(p):null;
              const statusColors={'Планирование':[C.info,C.infoLight,C.infoBorder],'В работе':[C.success,C.successLight,C.successBorder],'Завершён':[C.textSec,C.bgGray,C.border],'Заморожен':[C.warning,C.warningLight,C.warningBorder]};
              return(<div key={p.id} style={{...card,marginBottom:'12px',overflow:'visible'}}>
                <ProjectCardHeader
                  C={C}
                  btnG={btnG}
                  badge={badge}
                  project={p}
                  statusColors={statusColors}
                  isOpen={isOpen}
                  total={total}
                  canSeeFinance={isFinanceRole()}
                  canManage={isLeadership()}
                  onToggle={async()=>{if(isOpen){setExpandedProject(null);}else{setExpandedProject(p.id);setActiveProjectTab('Общее');if(user&&['директор','зам_директора','бухгалтер','прораб'].includes(user.role)&&!projectAiSummaries[p.name]){try{const r=await fetch(API+'/project-ai-summary/'+encodeURIComponent(p.name));const d=await r.json();if(d&&d.exists)setProjectAiSummaries(prev=>({...prev,[p.name]:d}));}catch(e){}}}}}
                  onEdit={()=>editProject(p)}
                />
                {isOpen&&(<div style={{borderTop:'1.5px solid '+C.border}}>
                  <div style={{borderBottom:'1.5px solid '+C.border,backgroundColor:C.bg,padding:'18px 16px 10px'}}>
                    <ProjectTabsNav
                      C={C}
                      role={user.role}
                      activeProjectTab={activeProjectTab}
                      activeTabGroup={activeTabGroup}
                      setActiveProjectTab={setActiveProjectTab}
                      setActiveTabGroup={setActiveTabGroup}
                    />
                  </div>
                  <div style={{padding:isMobile?'12px':'20px',overflowX:'hidden'}}>
	                    {activeProjectTab==='Общее'&&(<div>
		                      {isFinanceRole()&&(<div style={{display:'grid',gridTemplateColumns:isMobile?'repeat(2,minmax(0,1fr))':'1fr 1fr 1fr',gap:isMobile?'8px':'12px',marginBottom:'16px'}}>
		                        {EXPENSE_CATEGORIES.map(c=>(<div key={c.id} style={{padding:'12px',backgroundColor:C.bg,borderRadius:'10px',border:'1.5px solid '+C.border}}><p style={{margin:'0 0 4px',fontSize:'11px',color:C.textSec}}>{c.label}</p><b style={{fontSize:'14px',color:c.color}}>{(cat[c.id]||0).toLocaleString()+' ₽'}</b></div>))}
		                      </div>)}
		                      {isFinanceRole()&&<ProjectEconomyPanel C={C} card={card} btnB={btnB} btnG={btnG} btnO={btnO} project={p} economy={economy} isMobile={isMobile} onOpenFinance={()=>setActiveProjectTab('Финансы')} onOpenJournal={()=>setActiveProjectTab('Производство работ')} onOpenMaterials={()=>setActiveProjectTab('Материалы')} onOpenEstimate={()=>setActiveProjectTab('Смета')} showPreview={showPreview} />}
		                      {(()=>{const linksKey=['project-object-links',p.id||p.name].join(':');const showLinks=!isMobile||mobileExpandedRenderLists[linksKey];if(!showLinks){return(<div style={{...card,padding:'14px',marginBottom:'12px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border}}>
                              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap'}}>
                                <div>
                                  <b style={{color:C.text,fontSize:'14px'}}>🧭 Связи объекта</b>
                                  <p style={{margin:'4px 0 0',color:C.textSec,fontSize:'12px',lineHeight:1.4}}>Сметы, журналы, материалы и документы загружаются по запросу.</p>
                                </div>
                                <button type="button" onClick={()=>setMobileExpandedRenderLists(prev=>({...prev,[linksKey]:true}))} style={{...btnB,padding:'8px 12px',fontSize:'12px'}}>Показать</button>
                              </div>
                            </div>);}return <ProjectObjectLinksPanel C={C} card={card} items={projectObjectLinks(p)} isMobile={isMobile} onOpen={(tab)=>tab&&setActiveProjectTab(tab)} />;})()}
		                      {(()=>{const wj=(workJournal||[]).filter(w=>w.project===p.name);const pending=wj.filter(w=>!w.status||w.status==='На проверке'||w.status==='Автоматически из сметы');const confirmed=wj.filter(w=>w.status==='Подтверждено');const rejected=wj.filter(w=>w.status==='Отклонено');const last7=wj.filter(w=>{if(!w.date) return false;const d=new Date(w.date);return (Date.now()-d.getTime())<7*24*3600*1000;});const sumConfirmed=confirmed.reduce((s,w)=>s+workExecutionTotal(w),0);return(<div style={{...card,padding:'14px',marginBottom:'12px',backgroundColor:pending.length>0?C.warningLight:C.bg,border:'1.5px solid '+(pending.length>0?C.warningBorder:C.border)}}>
                        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'10px',flexWrap:'wrap',gap:'8px'}}>
                          <b style={{color:C.text,fontSize:'13px'}}>👷 Работы от мастеров {pending.length>0&&<span style={{padding:'2px 8px',borderRadius:'8px',backgroundColor:C.warning,color:'white',fontSize:'11px',marginLeft:'4px'}}>{pending.length+' на проверке'}</span>}</b>
                          <button onClick={()=>setActiveProjectTab('Производство работ')} style={{...btnG,padding:'4px 10px',fontSize:'11px'}}>📜 Открыть журнал</button>
                        </div>
                        <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(120px,1fr))',gap:'8px'}}>
                          <div style={{padding:'8px',borderRadius:'8px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border}}><p style={{color:C.textSec,fontSize:'10px',margin:'0 0 2px'}}>За 7 дней</p><b style={{color:C.text,fontSize:'15px'}}>{last7.length}</b></div>
                          <div style={{padding:'8px',borderRadius:'8px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border}}><p style={{color:C.textSec,fontSize:'10px',margin:'0 0 2px'}}>Подтверждено</p><b style={{color:C.success,fontSize:'15px'}}>{confirmed.length}</b></div>
                          <div style={{padding:'8px',borderRadius:'8px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border}}><p style={{color:C.textSec,fontSize:'10px',margin:'0 0 2px'}}>На проверке</p><b style={{color:C.warning,fontSize:'15px'}}>{pending.length}</b></div>
                          {rejected.length>0&&<div style={{padding:'8px',borderRadius:'8px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border}}><p style={{color:C.textSec,fontSize:'10px',margin:'0 0 2px'}}>Отклонено</p><b style={{color:C.danger,fontSize:'15px'}}>{rejected.length}</b></div>}
	                          {isFinanceRole()&&<div style={{padding:'8px',borderRadius:'8px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border,gridColumn:'span 2'}}><p style={{color:C.textSec,fontSize:'10px',margin:'0 0 2px'}}>К оплате исполнителям</p><b style={{color:C.accent,fontSize:'15px'}}>{Math.round(sumConfirmed).toLocaleString('ru-RU')+' ₽'}</b></div>}
                        </div>
                      </div>);})()}
                      <div style={{...card,padding:'16px',marginBottom:'12px',backgroundColor:C.accentLight,border:'1.5px solid '+C.accentBorder}}>
                        <b style={{color:C.text,fontSize:'13px',display:'block',marginBottom:'12px'}}>📊 Бригады и выполнение</b>
                        <div style={{display:'grid',gridTemplateColumns:isMobile?'1fr':'repeat(3,1fr)',gap:'10px',marginBottom:'12px'}}>
                          <div style={{textAlign:'center'}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Бригад</p><b style={{color:C.text,fontSize:'18px'}}>{brigadeContracts.filter(bc=>bc.projectName===p.name).length}</b></div>
                          <div style={{textAlign:'center'}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>По договорам</p><b style={{color:C.accent,fontSize:'16px'}}>{brigadeContracts.filter(bc=>bc.projectName===p.name).reduce((s,bc)=>s+Number(bc.totalAmount||0),0).toLocaleString()+' ₽'}</b></div>
                          <div style={{textAlign:'center'}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Смет</p><b style={{color:C.text,fontSize:'18px'}}>{visibleEstimatesForCurrentUser(estimatesList).filter(e=>e.projectName===p.name||Number(e.projectId)===Number(p.id)).length}</b></div>
                        </div>
                        <div style={{marginBottom:'12px'}}>
                          <div style={{display:'flex',justifyContent:'space-between',marginBottom:'4px'}}>
                            <b style={{fontSize:'12px',color:C.text}}>Выполнение работ бригадами</b>
                            <span style={{fontSize:'12px',color:C.textSec}}>{(()=>{
                              const pBrigades=brigadeContracts.filter(bc=>bc.projectName===p.name);
                              if(!pBrigades.length) return '0%';
                              const totalSmeta=pBrigades.reduce((s,bc)=>s+Number(bc.totalAmount||0),0);
                              const totalDone=pBrigades.reduce((s,bc)=>s+Number(bc.doneAmount||0),0);
                              return totalSmeta>0?Math.min(100,Math.round(totalDone/totalSmeta*100))+'%':'0%';
                            })()}</span>
                          </div>
                          <div style={{backgroundColor:C.bgGray,borderRadius:'6px',height:'10px'}}>
                            <div style={{backgroundColor:C.success,width:(()=>{const pBrigades=brigadeContracts.filter(bc=>bc.projectName===p.name);const totalSmeta=pBrigades.reduce((s,bc)=>s+Number(bc.totalAmount||0),0);const totalDone=pBrigades.reduce((s,bc)=>s+Number(bc.doneAmount||0),0);return Math.min(100,totalSmeta>0?Math.round(totalDone/totalSmeta*100):0)+'%';})(),height:'100%',borderRadius:'6px'}}/>
                          </div>
                        </div>
                        <div style={{display:'grid',gridTemplateColumns:isMobile?'1fr':'repeat(2,1fr)',gap:'10px'}}>
                          <div style={{backgroundColor:C.successLight,padding:'10px',borderRadius:'8px',border:'1px solid '+C.successBorder}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Смета заказчика</p><b style={{color:C.success,fontSize:'14px'}}>{Math.round(projectPlanDone(p).plan).toLocaleString('ru-RU')+' ₽'}</b></div>
                          <div style={{backgroundColor:C.warningLight,padding:'10px',borderRadius:'8px',border:'1px solid '+C.warningBorder}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Подрядчикам</p><b style={{color:C.warning,fontSize:'14px'}}>{brigadeContracts.filter(bc=>bc.projectName===p.name).reduce((s,bc)=>s+Number(bc.totalAmount||0),0).toLocaleString()+' ₽'}</b></div>
                        </div>
                      </div>
                      <div style={{backgroundColor:C.bg,borderRadius:'10px',padding:'14px',border:'1.5px solid '+C.border,marginBottom:'12px'}}>
                        {isFinanceRole()&&(<><div style={{display:'flex',justifyContent:'space-between',marginBottom:'8px'}}><b style={{color:C.text,fontSize:'13px'}}>Прогресс бюджета</b><span style={{fontSize:'13px',color:total>p.budget?C.danger:C.success}}>{Math.round(total).toLocaleString('ru-RU')+' из '+p.budget.toLocaleString()+' ₽'}</span></div>
                        <div style={{backgroundColor:C.bgGray,borderRadius:'6px',height:'10px'}}><div style={{backgroundColor:total>p.budget?C.danger:total>p.budget*0.8?C.warning:C.success,width:Math.min(100,p.budget>0?total/p.budget*100:0)+'%',height:'100%',borderRadius:'6px',transition:'width 0.3s'}}/></div>
                        <div style={{display:'flex',gap:'12px',flexWrap:'wrap',marginTop:'8px',fontSize:'11px',color:C.textSec}}>
                          <span>🔨 Работы/Бригады: <b style={{color:C.text}}>{Math.round(_bs.works).toLocaleString('ru-RU')+' ₽'}</b></span>
                          <span>📦 Материалы: <b style={{color:C.text}}>{Math.round(_bs.materials).toLocaleString('ru-RU')+' ₽'}</b></span>
                          {_bs.unexpected>0&&<span>🆕 Изменения к смете: <b style={{color:C.warning}}>{Math.round(_bs.unexpected).toLocaleString('ru-RU')+' ₽'}</b></span>}
                          {_bs.other>0&&<span>⚙️ Прочие затраты: <b style={{color:C.text}}>{Math.round(_bs.other).toLocaleString('ru-RU')+' ₽'}</b></span>}
                        </div>
                        <p style={{margin:'6px 0 0',fontSize:'10px',color:C.textMuted,fontStyle:'italic'}}>Себестоимость = всё что мы потратили (наши затраты), а не бюджет заказчика</p></>)}
                      </div>
                      <div style={{display:'flex',gap:'8px',flexWrap:'wrap',marginBottom:'16px'}}>
                        <button onClick={()=>showPreview(buildPassportContent(p),'Паспорт объекта — '+p.name)} style={btnB}><FileText size={14}/>Паспорт</button>
                        <button onClick={()=>showKS2(p)} style={btnG}><FileText size={14}/>КС-2</button>
                        <button onClick={()=>showPreview(buildKS3Content(p),'КС-3 — '+p.name)} style={btnG}><FileText size={14}/>КС-3</button>
                        <button onClick={()=>showPreview(buildJPRContent(p.name),'ЖПР — '+p.name)} style={btnG}><ScrollText size={14}/>ЖПР</button>
                        <button onClick={()=>setShowQRModal({title:'QR — '+p.name,data:window.location.origin+'/?project='+encodeURIComponent(p.name)})} style={btnG}><QrCode size={14}/>QR</button>
                      </div>
                      <div>
                        <b style={{color:C.text,fontSize:'13px'}}>Задачи:</b>
                        {isLeadership()&&<div style={{display:'flex',gap:'8px',marginTop:'8px',marginBottom:'10px'}}>
                          <input placeholder="Новая задача..." value={newTask} onChange={e=>setNewTask(e.target.value)} onKeyDown={e=>e.key==='Enter'&&addTask(p)} style={{...inp,marginBottom:0,flex:1,fontSize:'13px'}}/>
                          <button onClick={()=>addTask(p)} style={btnO}><Plus size={14}/></button>
                        </div>}
                        {(p.tasks||[]).map((t,i)=>(<div key={i} style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'8px 10px',backgroundColor:C.bg,borderRadius:'8px',marginBottom:'6px',border:'1.5px solid '+C.border}}><span style={{fontSize:'13px',color:C.text}}>{'• '+t}</span>{isLeadership()&&<button onClick={()=>removeTask(p,i)} style={{...btnR,padding:'3px 7px',fontSize:'10px'}}><X size={10}/></button>}</div>))}
                      </div>

                      {user&&['директор','зам_директора','бухгалтер','прораб'].includes(user.role)&&(()=>{
                        const smetaItems=activeEstimatesForProject(p,'Заказчик').flatMap(est=>(_sectionsOfEst(est)||[]).flatMap(s=>(s.items||[]).map(i=>({...i,section:s.name,workPackage:estimatePackage(est)}))));
                        const norm=(s)=>(s||'').toLowerCase().replace(/[.,;:()«»"'-]/g,' ').replace(/\s+/g,' ').trim();
                        const matchScore=(a,b)=>{const aw=norm(a).split(' ').filter(w=>w.length>=3);const bw=new Set(norm(b).split(' ').filter(w=>w.length>=3));if(!aw.length||!bw.size) return 0;const common=aw.filter(w=>bw.has(w)).length;return common/Math.max(aw.length,1);};
                        const projMaterials=materials.filter(m=>m.project===p.name);
                        const projTransfers=materialTransfers.filter(t=>t.projectName===p.name);
                        const workProgress=smetaItems.filter(it=>isEstimateWorkItem(it,it.section)).map(it=>{
                          const plan=Number(it.quantity||0);
                          const done=Number(it.doneQuantity||0);
                          const left=Math.max(0,plan-done);
                          const pct=plan>0?Math.min(100,Math.round(done/plan*100)):0;
                          return {name:it.name,section:it.section,unit:it.unit,plan,done,left,pct};
                        });
                        const matPlan=smetaItems.filter(i=>isEstimateMaterialItem(i,i.section)&&!estimateMaterialPlanIssue(i,i.section)&&toNum(estimateImportedPlanMeasure(i).qty)>0).map(it=>{
                          const planMeasure=estimateImportedPlanMeasure(it);
                          const plan=toNum(planMeasure.qty);
                          const bought=projMaterials.filter(m=>matchScore(m.name,it.name)>=0.4).reduce((s,m)=>s+Number(m.quantity||0),0);
                          return {name:it.name,unit:planMeasure.unit||it.unit,plan,bought,need:Math.max(0,plan-bought)};
                        });
                        const fmt=(n)=>Number(n||0).toLocaleString('ru-RU');
                        const payload={
                          project:p.name,
                          total:smetaItems.reduce((s,i)=>s+estimateItemTotal(i),0),
                          workProgress:workProgress.filter(w=>w.plan>0),
                          materials:matPlan,
                          stock:projMaterials.map(m=>({name:m.name,qty:Number(m.quantity||0),unit:m.unit})),
                          transfers:projTransfers.slice(0,20).map(t=>({name:t.materialName,qty:Number(t.quantity||0),unit:t.unit,to:t.toPerson,date:t.transferDate}))
                        };
                        const payloadStr=JSON.stringify(payload);
                        let _h=0;for(let i=0;i<payloadStr.length;i++){_h=((_h*31)+payloadStr.charCodeAt(i))|0;}
                        const currentHash=(_h>>>0).toString(16);
                        const cached=projectAiSummaries[p.name];
                        const isFresh=cached&&cached.payloadHash===currentHash;
                        const fmtAgo=(iso)=>{if(!iso) return '';const d=new Date(iso);const m=Math.floor((Date.now()-d.getTime())/60000);if(m<1) return 'только что';if(m<60) return m+' мин назад';const h=Math.floor(m/60);if(h<24) return h+' ч назад';return Math.floor(h/24)+' дн назад';};
                        const runAiSummary=async()=>{
                          const prompt='Объект "'+p.name+'". Проанализируй прогресс и материальный учёт. Данные ниже.\n\n'+JSON.stringify(payload,null,1)+'\n\nОТВЕТЬ СТРОГО JSON (без markdown):\n{\n  "summary":"одна-две фразы общего впечатления",\n  "progress":[{"what":"что","status":"в норме|отставание|опережение","note":"что заметил"}],\n  "materials":[{"what":"материал","problem":"нехватка|избыток|пропажа|норма","action":"что сделать","amount":число_или_0}],\n  "alerts":[{"type":"критично|внимание|совет","text":"что"}]\n}\nИспользуй только данные из payload. Если данных мало — пиши "недостаточно данных".';
                          // Показываем загрузку прямо в карточке (без открытия панели чата)
                          setProjectAiSummaries(prev=>({...prev,[p.name]:{...(prev[p.name]||{}),loading:true}}));
                          try{
                            const res=await fetch(API+'/ai-chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:[{role:'user',content:prompt}],jsonOnly:true})});
                            const data=await res.json();
                            const raw=(data.response||data.error||'').trim();
                            let parsed=null;
                            try{const clean=raw.replace(/^```(?:json)?/i,'').replace(/```$/,'').trim();const s=clean.indexOf('{'),e=clean.lastIndexOf('}');if(s>=0&&e>s) parsed=JSON.parse(clean.slice(s,e+1));}catch(e){}
                            let out;
                            if(parsed){
                              const ln=[];
                              if(parsed.summary) ln.push('📋 '+parsed.summary,'');
                              if(Array.isArray(parsed.alerts)&&parsed.alerts.length){ln.push('🚨 ВНИМАНИЕ');parsed.alerts.forEach((a,n)=>ln.push((n+1)+'. ['+(a.type||'')+'] '+(a.text||'')));ln.push('');}
                              if(Array.isArray(parsed.progress)&&parsed.progress.length){ln.push('🔨 РАБОТЫ');parsed.progress.forEach((q,n)=>ln.push((n+1)+'. '+(q.what||'?')+' — '+(q.status||'?')+(q.note?': '+q.note:'')));ln.push('');}
                              if(Array.isArray(parsed.materials)&&parsed.materials.length){ln.push('📦 МАТЕРИАЛЫ');parsed.materials.forEach((m,n)=>ln.push((n+1)+'. '+(m.what||'?')+' — '+(m.problem||'?')+(m.action?' → '+m.action:'')+(m.amount?' ('+fmt(m.amount)+')':'')));}
                              out=ln.join('\n');
                            }else out=raw||'Ошибка ответа ИИ';
                            try{await fetch(API+'/project-ai-summary',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({projectName:p.name,payloadHash:currentHash,summary:out})});}catch(e){}
                            setProjectAiSummaries(prev=>({...prev,[p.name]:{exists:true,payloadHash:currentHash,summary:out,updatedAt:new Date().toISOString(),loading:false}}));
                          }catch(e){
                            setProjectAiSummaries(prev=>({...prev,[p.name]:{...(prev[p.name]||{}),loading:false,error:'Ошибка соединения с AI'}}));
                          }
                        };
                        return(<div style={{...card,padding:'16px',marginBottom:'12px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.accentBorder}}>
                          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'14px'}}>
                            <b style={{color:C.text,fontSize:'14px'}}>📊 Контроль объекта</b>
                            <button onClick={runAiSummary} disabled={cached&&cached.loading} style={{...btnB,backgroundColor:'#10b981',color:'white',borderColor:'#059669',fontSize:'12px',opacity:(cached&&cached.loading)?0.6:1}}><Bot size={13}/>{cached&&cached.loading?'AI думает...':cached&&cached.summary?'Обновить ИИ':'AI-сводка'}</button>
                          </div>
                          {cached&&cached.loading&&(<div style={{...card,padding:'14px',marginBottom:'14px',backgroundColor:C.infoLight,border:'1.5px solid '+C.infoBorder,textAlign:'center'}}>
                            <p style={{margin:0,fontSize:'13px',color:C.info}}>⏳ AI анализирует объект... (15-40 сек)</p>
                          </div>)}
                          {cached&&cached.error&&(<div style={{...card,padding:'12px',marginBottom:'14px',backgroundColor:C.dangerLight,border:'1.5px solid '+C.dangerBorder}}>
                            <p style={{margin:0,fontSize:'13px',color:C.danger}}>❌ {cached.error}</p>
                          </div>)}
                          {cached&&cached.summary&&!cached.loading&&(<div style={{...card,padding:'12px',marginBottom:'14px',backgroundColor:isFresh?C.successLight:C.warningLight,border:'1.5px solid '+(isFresh?C.successBorder:C.warningBorder)}}>
                            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'8px'}}>
                              <b style={{fontSize:'12px',color:isFresh?C.success:C.warning}}>🤖 {isFresh?'AI-сводка актуальна':'⚠️ Данные изменились — нужно обновить'}</b>
                              <span style={{fontSize:'11px',color:C.textSec}}>{fmtAgo(cached.updatedAt)}</span>
                            </div>
                            <div style={{fontSize:'12px',color:C.text,whiteSpace:'pre-wrap',lineHeight:'1.5'}}>{cached.summary}</div>
                          </div>)}
                          {(!cached||(!cached.summary&&!cached.loading&&!cached.error))&&<p style={{fontSize:'12px',color:C.textMuted,marginBottom:'12px',padding:'8px',backgroundColor:C.bg,borderRadius:'8px'}}>💡 AI-сводка ещё не делалась. Нажмите «AI-сводка» — анализ сохранится в системе.</p>}
                          {smetaItems.length===0&&<p style={{color:C.textMuted,fontSize:'12px',padding:'10px',textAlign:'center'}}>У объекта нет сметы — нечего сравнивать. Добавьте смету в разделе «Сметы».</p>}
                          {smetaItems.length>0&&(<>
                          <div style={{marginBottom:'14px'}}>
                            <b style={{color:C.text,fontSize:'12px',display:'block',marginBottom:'6px'}}>📋 Прогресс по смете (работы)</b>
                            <table style={{...tbl,fontSize:'11px'}}><thead><tr><th style={tblH}>Позиция</th><th style={tblH}>План</th><th style={tblH}>Выполнено</th><th style={tblH}>Осталось</th><th style={tblH}>%</th></tr></thead><tbody>
                              {workProgress.filter(w=>w.plan>0).slice(0,15).map((w,i)=>(<tr key={i}><td style={{...tblC,fontSize:'11px'}}>{w.name}</td><td style={{...tblC,fontSize:'11px'}}>{fmtMeasure(w.plan,w.unit)}</td><td style={{...tblC,fontSize:'11px',color:w.done>0?C.success:C.textMuted}}>{fmtMeasure(w.done,w.unit)}</td><td style={{...tblC,fontSize:'11px',color:w.left>0?C.warning:C.success}}>{fmtMeasure(w.left,w.unit)}</td><td style={{...tblC,fontSize:'11px',fontWeight:'600',color:w.pct>=100?C.success:w.pct>=50?C.info:C.warning}}>{w.pct}%</td></tr>))}
                            </tbody></table>
                            {!workProgress.filter(w=>w.plan>0).length&&<p style={{color:C.textMuted,fontSize:'11px',padding:'8px'}}>В смете нет позиций работ</p>}
                          </div>
                          <div style={{marginBottom:'14px'}}>
                            <b style={{color:C.text,fontSize:'12px',display:'block',marginBottom:'6px'}}>📥 Материалы — план vs закуплено</b>
                            <table style={{...tbl,fontSize:'11px'}}><thead><tr><th style={tblH}>Материал</th><th style={tblH}>По смете</th><th style={tblH}>Закуплено</th><th style={tblH}>Не хватает</th></tr></thead><tbody>
                              {matPlan.slice(0,15).map((m,i)=>(<tr key={i}><td style={{...tblC,fontSize:'11px'}}>{m.name}</td><td style={{...tblC,fontSize:'11px'}}>{m.plan} {m.unit}</td><td style={{...tblC,fontSize:'11px',color:m.bought>=m.plan?C.success:C.info}}>{m.bought} {m.unit}</td><td style={{...tblC,fontSize:'11px',color:m.need>0?C.danger:C.success}}>{m.need>0?m.need+' '+m.unit:'✅'}</td></tr>))}
                            </tbody></table>
                            {!matPlan.length&&<p style={{color:C.textMuted,fontSize:'11px',padding:'8px'}}>В смете нет материалов</p>}
                          </div>
                          </>)}
                          <div style={{marginBottom:'14px'}}>
                            <b style={{color:C.text,fontSize:'12px',display:'block',marginBottom:'6px'}}>📤 Выдачи мастерам ({projTransfers.length})</b>
                            <table style={{...tbl,fontSize:'11px'}}><thead><tr><th style={tblH}>Материал</th><th style={tblH}>Кол-во</th><th style={tblH}>Кому</th><th style={tblH}>Дата</th></tr></thead><tbody>
                              {projTransfers.slice(0,10).map((t,i)=>(<tr key={i}><td style={{...tblC,fontSize:'11px'}}>{t.materialName}</td><td style={{...tblC,fontSize:'11px'}}>{t.quantity} {t.unit}</td><td style={{...tblC,fontSize:'11px'}}>{t.toPerson}</td><td style={{...tblC,fontSize:'11px'}}>{t.transferDate}</td></tr>))}
                            </tbody></table>
                            {!projTransfers.length&&<p style={{color:C.textMuted,fontSize:'11px',padding:'8px'}}>Передач ещё не было</p>}
                          </div>
                          <div>
                            <b style={{color:C.text,fontSize:'12px',display:'block',marginBottom:'6px'}}>🏬 Остатки на складе объекта ({projMaterials.filter(m=>Number(m.quantity||0)>0).length})</b>
                            <table style={{...tbl,fontSize:'11px'}}><thead><tr><th style={tblH}>Материал</th><th style={tblH}>Остаток</th><th style={tblH}>Категория</th></tr></thead><tbody>
                              {projMaterials.filter(m=>Number(m.quantity||0)>0).slice(0,15).map((m,i)=>(<tr key={i}><td style={{...tblC,fontSize:'11px'}}>{m.name}</td><td style={{...tblC,fontSize:'11px',fontWeight:'600',color:C.success}}>{m.quantity} {m.unit}</td><td style={{...tblC,fontSize:'11px',color:C.textSec}}>{m.category||''}</td></tr>))}
                            </tbody></table>
                            {!projMaterials.filter(m=>Number(m.quantity||0)>0).length&&<p style={{color:C.textMuted,fontSize:'11px',padding:'8px'}}>Склад объекта пуст</p>}
                          </div>
                        </div>);
                      })()}

                  </div>)}

                    {activeProjectTab==='ИИ-контроль'&&(()=> {
                      const projectFindings = aiFindingsForProject(p.name);
                      const projectTasks = aiTasksForProject(p.name);
                      const standaloneTasks = projectTasks.filter(t=>!t.findingId);
                      const byCategory = projectFindings.reduce((acc,f)=>{const k=f.category||'Общее';if(!acc[k])acc[k]=[];acc[k].push(f);return acc;},{});
                      const importantCount = projectFindings.filter(f=>f.severity==='Критично'||f.severity==='Не хватает данных').length;
                      const canRunAiControl = user&&['директор','зам_директора','прораб','главный_инженер','сметчик','технадзор','стройконтроль'].includes(user.role);
                      const taskTypeMeta = (task) => {
                        const type = parseAiTaskPayload(task).type;
                        if (['material_purchase_review','material_outside_estimate_review','material_writeoff_review','material_norm_over_review','material_without_norm_review','material_transfer_sign_review'].includes(type)) return {key:'materials',label:'Материалы',icon:<Package size={13}/>,color:C.info,bg:C.infoLight,border:C.infoBorder};
                        if (['room_measurement_review','work_room_link_review'].includes(type)) return {key:'rooms',label:'Помещения',icon:<MapPin size={13}/>,color:C.success,bg:C.successLight,border:C.successBorder};
                        if (['estimate_quality_review','estimate_norm_review','material_norm_coverage'].includes(type)) return {key:'estimate',label:'Смета и нормы',icon:<Calculator size={13}/>,color:C.accent,bg:C.accentLight,border:C.accentBorder};
                        if (['estimate_diff_review','estimate_change_reconcile'].includes(type)) return {key:'changes',label:'Изменения к смете',icon:<GitBranch size={13}/>,color:C.warning,bg:C.warningLight,border:C.warningBorder};
                        return {key:'other',label:'Прочее',icon:<Eye size={13}/>,color:C.textSec,bg:C.bgGray,border:C.border};
                      };
                      const groupedStandaloneTasks = standaloneTasks.reduce((acc,task)=>{
                        const meta = taskTypeMeta(task);
                        if (!acc[meta.key]) acc[meta.key] = {meta,tasks:[]};
                        acc[meta.key].tasks.push(task);
                        return acc;
                      },{});
                      const standaloneTaskGroups = ['materials','rooms','estimate','changes','other'].map(k=>groupedStandaloneTasks[k]).filter(Boolean);
                      return (<div>
                        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap',marginBottom:'14px'}}>
                          <div>
                            <b style={{color:C.text,fontSize:'15px'}}>🤖 ИИ-контроль объекта</b>
                            <p style={{color:C.textSec,fontSize:'12px',margin:'4px 0 0'}}>Фоновый контроль обмеров, ЖПР, смет, норм, материалов и поручений.</p>
                          </div>
                          <button onClick={()=>generateAiFindingsForProject(p.name)} disabled={!canRunAiControl} style={{...btnO,opacity:canRunAiControl?1:.55}}><Bot size={14}/>Обновить контроль</button>
                        </div>
                        <div style={{display:'grid',gridTemplateColumns:isMobile?'1fr 1fr':'repeat(4,1fr)',gap:'10px',marginBottom:'14px'}}>
                          <div style={{padding:'12px',borderRadius:'10px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Открыто</p><b style={{color:C.text,fontSize:'20px'}}>{projectFindings.length}</b></div>
                          <div style={{padding:'12px',borderRadius:'10px',backgroundColor:importantCount?C.warningLight:C.successLight,border:'1.5px solid '+(importantCount?C.warningBorder:C.successBorder)}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Важные</p><b style={{color:importantCount?C.warning:C.success,fontSize:'20px'}}>{importantCount}</b></div>
                          <div style={{padding:'12px',borderRadius:'10px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Поручения</p><b style={{color:C.accent,fontSize:'20px'}}>{projectTasks.length}</b></div>
                          <div style={{padding:'12px',borderRadius:'10px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Категорий</p><b style={{color:C.text,fontSize:'20px'}}>{Object.keys(byCategory).length}</b></div>
                        </div>
                        {projectFindings.length===0&&standaloneTasks.length===0&&(<div style={{...card,padding:'18px',textAlign:'center',backgroundColor:C.successLight,border:'1.5px solid '+C.successBorder}}>
                          <b style={{color:C.success,fontSize:'14px'}}>Замечаний пока нет</b>
                          <p style={{color:C.textSec,fontSize:'12px',margin:'6px 0 12px'}}>Система обновляет контроль после ключевых событий, а эту кнопку можно использовать для ручного пересчёта.</p>
                          <button onClick={()=>generateAiFindingsForProject(p.name)} disabled={!canRunAiControl} style={{...btnGr,opacity:canRunAiControl?1:.55}}><Bot size={14}/>Обновить контроль</button>
                        </div>)}
                        {standaloneTasks.length>0&&(<div style={{...card,padding:'14px',marginBottom:'12px'}}>
                          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'8px',marginBottom:'10px'}}>
                            <b style={{color:C.text,fontSize:'13px'}}>Поручения</b>
                            <span style={badge(C.accent,C.accentLight,C.accentBorder)}>{standaloneTasks.length}</span>
                          </div>
                          {standaloneTaskGroups.map(group=>(
                            <div key={group.meta.key} style={{marginBottom:'12px'}}>
                              <div style={{display:'flex',alignItems:'center',gap:'8px',margin:'0 0 8px',padding:'7px 9px',borderRadius:'10px',backgroundColor:group.meta.bg,border:'1.5px solid '+group.meta.border}}>
                                <span style={{color:group.meta.color,display:'inline-flex'}}>{group.meta.icon}</span>
                                <b style={{color:group.meta.color,fontSize:'12px'}}>{group.meta.label}</b>
                                <span style={badge(group.meta.color,group.meta.bg,group.meta.border)}>{group.tasks.length}</span>
                              </div>
                              {group.tasks.map(task=>{
                                const payload=parseAiTaskPayload(task);
                                const isEstimateTask=['estimate_quality_review','estimate_norm_review','material_norm_coverage','estimate_diff_review','estimate_change_reconcile'].includes(payload.type);
                                const isMaterialTask=['material_purchase_review','material_outside_estimate_review','material_writeoff_review','material_norm_over_review','material_without_norm_review','material_transfer_sign_review'].includes(payload.type);
                                const isRoomTask=['room_measurement_review','work_room_link_review'].includes(payload.type);
                                const aliasCandidate=payload.aliasCandidate||null;
                                const purchaseRow=payload.type==='material_purchase_review'
                                  ? materialReconciliationRows(payload.projectName||task.projectName||'').find(r=>materialNameKey(r.name)===materialNameKey(payload.materialName)&&(!payload.unit||_normalizeUnit(r.unit||'')===_normalizeUnit(payload.unit||'')))
                                  : null;
                                return (<div key={task.id} style={{padding:'12px',borderRadius:'10px',backgroundColor:C.bg,border:'1.5px solid '+C.border,marginBottom:'8px'}}>
                                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
                                    <div style={{flex:1,minWidth:'220px'}}>
                                      <div style={{display:'flex',alignItems:'center',gap:'6px',flexWrap:'wrap',marginBottom:'5px'}}>
                                        <span style={badge(C.info,C.infoLight,C.infoBorder)}>{task.status||'Новое'}</span>
                                        <span style={{fontSize:'11px',color:C.textSec}}>{task.assignedRole?'кому: '+task.assignedRole:'без роли'}</span>
                                      </div>
                                      <b style={{display:'block',color:C.text,fontSize:'13px',lineHeight:1.35}}>{task.title}</b>
                                      {payload.type==='estimate_change_reconcile'
                                        ? renderEstimateChangeReconcileTask(task)
                                        : task.description&&<p style={{color:C.textSec,fontSize:'12px',margin:'6px 0 0',lineHeight:1.45,whiteSpace:'pre-wrap'}}>{task.description}</p>}
                                    </div>
                                    <div style={{display:'flex',gap:'6px',flexWrap:'wrap',justifyContent:'flex-end'}}>
                                      {aliasCandidate?.aliasName&&aliasCandidate?.canonicalName&&<button onClick={()=>acceptMaterialAliasTask(task)} style={{...btnGr,padding:'5px 9px',fontSize:'11px'}}><Check size={11}/>Привязать</button>}
                                      {purchaseRow&&toNum(purchaseRow.toBuy)>0&&renderMaterialSupplyAction(payload.projectName||task.projectName||'', purchaseRow)}
                                      {task.actionLabel&&<button onClick={()=>openAiTaskAction(task)} style={{...btnB,padding:'5px 9px',fontSize:'11px'}}>{payload.type==='estimate_diff_review'?<FileText size={11}/>:isEstimateTask?<Calculator size={11}/>:isMaterialTask?<Package size={11}/>:isRoomTask?<MapPin size={11}/>:<Eye size={11}/>} {task.actionLabel}</button>}
                                      {task.status==='Новое'&&<button onClick={()=>updateAiTask(task.id,{status:'Принято к исполнению'})} style={{...btnG,padding:'5px 9px',fontSize:'11px'}}>Принять</button>}
                                      {['Новое','Принято к исполнению'].includes(task.status||'')&&<button onClick={()=>updateAiTask(task.id,{status:'В работе'})} style={{...btnO,padding:'5px 9px',fontSize:'11px'}}>В работу</button>}
                                      <button onClick={()=>updateAiTask(task.id,{status:'Закрыто'})} style={{...btnGr,padding:'5px 9px',fontSize:'11px'}}>Закрыть</button>
                                      <button onClick={()=>updateAiTask(task.id,{status:'Отклонено'})} style={{...btnR,padding:'5px 9px',fontSize:'11px'}}>Отклонить</button>
                                    </div>
                                  </div>
                                </div>);
                              })}
                            </div>
                          ))}
                        </div>)}
                        {Object.entries(byCategory).map(([category,list])=>(
                          <div key={category} style={{...card,padding:'14px',marginBottom:'12px'}}>
                            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'8px',marginBottom:'10px'}}>
                              <b style={{color:C.text,fontSize:'13px'}}>{category}</b>
                              <span style={badge(C.accent,C.accentLight,C.accentBorder)}>{list.length}</span>
                            </div>
                            {list.map(f=>{
                              const meta=aiSeverityMeta(f.severity);
                              const task=projectTasks.find(t=>Number(t.findingId)===Number(f.id));
                              return (<div key={f.id} style={{padding:'12px',borderRadius:'10px',backgroundColor:meta.bg,border:'1.5px solid '+meta.border,marginBottom:'8px'}}>
                                <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
                                  <div style={{flex:1,minWidth:'220px'}}>
                                    <div style={{display:'flex',alignItems:'center',gap:'6px',flexWrap:'wrap',marginBottom:'5px'}}>
                                      <span style={badge(meta.color,meta.bg,meta.border)}>{f.severity||'Проверить'}</span>
                                      <span style={{fontSize:'11px',color:C.textSec}}>{f.assignedRole?'кому: '+f.assignedRole:'без роли'}{task&&task.status?' · '+task.status:''}</span>
                                    </div>
                                    <b style={{display:'block',color:C.text,fontSize:'13px',lineHeight:1.35}}>{f.title}</b>
                                    {f.description&&<p style={{color:C.textSec,fontSize:'12px',margin:'6px 0 0',lineHeight:1.45}}>{f.description}</p>}
                                    {f.suggestedAction&&<p style={{color:C.text,fontSize:'12px',margin:'6px 0 0'}}><b>Что сделать:</b> {f.suggestedAction}</p>}
                                  </div>
                                  <div style={{display:'flex',gap:'6px',flexWrap:'wrap',justifyContent:'flex-end'}}>
                                    {task&&task.status==='Новое'&&<button onClick={()=>updateAiTask(task.id,{status:'Принято к исполнению'})} style={{...btnG,padding:'5px 9px',fontSize:'11px'}}>Принять</button>}
                                    {task&&['Новое','Принято к исполнению'].includes(task.status||'')&&<button onClick={()=>updateAiTask(task.id,{status:'В работе'})} style={{...btnO,padding:'5px 9px',fontSize:'11px'}}>В работу</button>}
                                    <button onClick={()=>updateAiFinding(f.id,{status:'Исправлено'})} style={{...btnGr,padding:'5px 9px',fontSize:'11px'}}>Исправлено</button>
                                    <button onClick={()=>updateAiFinding(f.id,{status:'Закрыто'})} style={{...btnG,padding:'5px 9px',fontSize:'11px'}}>Закрыть</button>
                                    <button onClick={()=>updateAiFinding(f.id,{status:'Отклонено'})} style={{...btnR,padding:'5px 9px',fontSize:'11px'}}>Отклонить</button>
                                  </div>
                                </div>
                              </div>);
                            })}
                          </div>
                        ))}
                      </div>);
                    })()}

                    {activeProjectTab==='Проект / Обмеры'&&(()=> {
                      const docs = (projectMeasurements||[]).filter(d=>d.projectName===p.name);
                      const drafts = (measurementRoomDrafts||[]).filter(d=>d.projectName===p.name);
                      const projectRooms = rooms.filter(r=>r.project===p.name);
                      const roomChecks = projectRooms.map(roomCompleteness);
                      const fullRooms = roomChecks.filter(x=>x.status==='Обмер полный').length;
                      const missingRooms = roomChecks.filter(x=>x.status==='Не хватает данных').length;
                      const acceptedDocs = docs.filter(d=>d.status==='Принято').length;
                      const reviewDocs = docs.filter(d=>d.status==='На проверке').length;
                      const pendingDrafts = drafts.filter(d=>d.status==='Черновик ИИ').length;
                      const acceptedDrafts = drafts.filter(d=>d.acceptedRoomId||d.status==='Принято').length;
                      const canEditMeasurements = user&&['директор','зам_директора','прораб','главный_инженер','сметчик'].includes(user.role);
                      const statusMeta = (st) => st==='Принято'
                        ? [C.success,C.successLight,C.successBorder]
                        : st==='На проверке'
                          ? [C.warning,C.warningLight,C.warningBorder]
                          : st==='Отклонено'
                            ? [C.danger,C.dangerLight,C.dangerBorder]
                            : [C.textSec,C.bgGray,C.border];
                      const saveMeasurement = async () => {
                        if (!newMeasurementDoc.title.trim() && !newMeasurementDoc.fileUrl && !newMeasurementDoc.photoUrl) { alert('Укажите название или загрузите файл/фото'); return; }
                        await fetch(API+'/project-measurements',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...newMeasurementDoc,projectName:p.name,roomsCreated:Number(newMeasurementDoc.roomsCreated||0),uploadedBy:user.name})});
                        setNewMeasurementDoc({sourceType:'Фактический ручной',docType:'Обмер',title:'',fileUrl:'',photoUrl:'',status:'Черновик',roomsCreated:'0',notes:''});
                        setShowMeasurementForm(false);
                        await refreshData();
                      };
                      const updateMeasurement = async (doc, patch) => {
                        await fetch(API+'/project-measurements/'+doc.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(patch)});
                        await refreshData();
                      };
                      const deleteMeasurement = async (doc) => {
                        if (!window.confirm('Удалить исходник «'+(doc.title||doc.docType||'обмер')+'»?')) return;
                        await fetch(API+'/project-measurements/'+doc.id,{method:'DELETE'});
                        await refreshData();
                      };
                      const generateRoomDrafts = async (doc) => {
                        setMeasurementDraftLoadingId(doc.id);
                        try {
                          const r = await fetch(API+'/project-measurements/'+doc.id+'/ai-draft-rooms',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({replaceExisting:true})});
                          const data = await r.json().catch(()=>({}));
                          if (!r.ok || data.detail) alert('Не удалось разобрать источник: '+(data.detail||'ошибка'));
                          else if (!data.created) alert('ИИ не нашёл помещений. Добавьте текст в комментарий или загрузите более читаемый скан.');
                        } finally {
                          setMeasurementDraftLoadingId(null);
                          await refreshData();
                        }
                      };
                      const acceptRoomDraft = async (draft) => {
                        await fetch(API+'/measurement-room-drafts/'+draft.id+'/accept',{method:'POST'});
                        await refreshData();
                      };
                      const rejectRoomDraft = async (draft) => {
                        await fetch(API+'/measurement-room-drafts/'+draft.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Отклонено'})});
                        await refreshData();
                      };
                      return (<div>
                        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap',marginBottom:'14px'}}>
                          <div>
                            <b style={{color:C.text,fontSize:'15px'}}>📐 Проект / Обмеры</b>
                            <p style={{color:C.textSec,fontSize:'12px',margin:'4px 0 0'}}>Исходники объёмов: проект, экспликации, ведомости окон/дверей, ручные и фактические обмеры.</p>
                          </div>
                          {canEditMeasurements&&<button onClick={()=>setShowMeasurementForm(!showMeasurementForm)} style={btnO}><Plus size={14}/>Добавить источник</button>}
                        </div>

                        <div style={{display:'grid',gridTemplateColumns:isMobile?'1fr 1fr':'repeat(auto-fit,minmax(130px,1fr))',gap:'10px',marginBottom:'14px'}}>
                          <div style={{padding:'12px',borderRadius:'10px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Исходников</p><b style={{color:C.text,fontSize:'20px'}}>{docs.length}</b></div>
                          <div style={{padding:'12px',borderRadius:'10px',backgroundColor:acceptedDocs?C.successLight:C.bgWhite,border:'1.5px solid '+(acceptedDocs?C.successBorder:C.border)}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Принято</p><b style={{color:acceptedDocs?C.success:C.text,fontSize:'20px'}}>{acceptedDocs}</b></div>
                          <div style={{padding:'12px',borderRadius:'10px',backgroundColor:reviewDocs?C.warningLight:C.bgWhite,border:'1.5px solid '+(reviewDocs?C.warningBorder:C.border)}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>На проверке</p><b style={{color:reviewDocs?C.warning:C.text,fontSize:'20px'}}>{reviewDocs}</b></div>
                          <div style={{padding:'12px',borderRadius:'10px',backgroundColor:pendingDrafts?C.infoLight:C.bgWhite,border:'1.5px solid '+(pendingDrafts?C.infoBorder:C.border)}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Черновики ИИ</p><b style={{color:pendingDrafts?C.info:C.text,fontSize:'20px'}}>{pendingDrafts}</b><span style={{color:C.textMuted,fontSize:'11px',marginLeft:'6px'}}>принято {acceptedDrafts}</span></div>
                          <div style={{padding:'12px',borderRadius:'10px',backgroundColor:missingRooms?C.warningLight:C.successLight,border:'1.5px solid '+(missingRooms?C.warningBorder:C.successBorder)}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Помещения</p><b style={{color:missingRooms?C.warning:C.success,fontSize:'20px'}}>{fullRooms+'/'+projectRooms.length}</b></div>
                        </div>

                        {showMeasurementForm&&canEditMeasurements&&(<div style={{...card,padding:'16px',marginBottom:'14px',backgroundColor:C.bg}}>
                          <div style={{display:'grid',gridTemplateColumns:isMobile?'1fr':'1fr 1fr 1fr',gap:'8px'}}>
                            <select value={newMeasurementDoc.sourceType} onChange={e=>setNewMeasurementDoc({...newMeasurementDoc,sourceType:e.target.value})} style={{...inp,marginBottom:0}}>{PROJECT_MEASUREMENT_SOURCE_TYPES.map(t=><option key={t}>{t}</option>)}</select>
                            <select value={newMeasurementDoc.docType} onChange={e=>setNewMeasurementDoc({...newMeasurementDoc,docType:e.target.value})} style={{...inp,marginBottom:0}}>{PROJECT_MEASUREMENT_DOC_TYPES.map(t=><option key={t}>{t}</option>)}</select>
                            <select value={newMeasurementDoc.status} onChange={e=>setNewMeasurementDoc({...newMeasurementDoc,status:e.target.value})} style={{...inp,marginBottom:0}}>{PROJECT_MEASUREMENT_STATUSES.map(t=><option key={t}>{t}</option>)}</select>
                            <input placeholder="Название / лист / файл" value={newMeasurementDoc.title} onChange={e=>setNewMeasurementDoc({...newMeasurementDoc,title:e.target.value})} style={{...inp,marginBottom:0}}/>
                            <input placeholder="Создано помещений" type="number" min="0" inputMode="numeric" value={newMeasurementDoc.roomsCreated} onChange={e=>setNewMeasurementDoc({...newMeasurementDoc,roomsCreated:e.target.value})} style={{...inp,marginBottom:0}}/>
                            <label style={{...btnG,cursor:'pointer',justifyContent:'center',margin:0}}>
                              <Upload size={14}/>{uploadingMeasurementDoc?'Загрузка...':(newMeasurementDoc.fileUrl?'Файл загружен':'Загрузить файл')}
                              <input type='file' accept='.pdf,.doc,.docx,.xls,.xlsx,image/*' style={{display:'none'}} onChange={async e=>{const f=e.target.files[0];if(!f)return;setUploadingMeasurementDoc(true);const url=await uploadPhoto(f,{projectName:p.name,context:'project-measurements'});setUploadingMeasurementDoc(false);if(url)setNewMeasurementDoc(prev=>({...prev,fileUrl:url,title:prev.title||f.name}));}}/>
                            </label>
                          </div>
                          <div style={{marginTop:'8px'}}>
                            <PhotoAttachmentField
                              C={C}
                              btnG={btnG}
                              value={newMeasurementDoc.photoUrl || ''}
                              onChange={photoUrl => {
                                const firstPhoto = String(photoUrl || '').split(',').map(url => url.trim()).filter(Boolean)[0] || '';
                                setNewMeasurementDoc(prev => ({...prev, photoUrl, fileUrl: prev.fileUrl || firstPhoto, title: prev.title || (firstPhoto ? 'Фото обмера' : '')}));
                              }}
                              appendPhotos={appendPhotos}
                              fileSrc={fileSrc}
                              setShowPhotoModal={setShowPhotoModal}
                              projectName={p.name}
                              context="project-measurements"
                              title="Фото/сканы листов замеров"
                            />
                          </div>
                          <textarea placeholder="Комментарий: откуда взяты объёмы, что нужно проверить, какие помещения создать" value={newMeasurementDoc.notes} onChange={e=>setNewMeasurementDoc({...newMeasurementDoc,notes:e.target.value})} style={{...inp,minHeight:'70px',resize:'vertical',marginTop:'8px'}}/>
                          <div style={{display:'flex',gap:'8px',flexWrap:'wrap'}}>
                            <button onClick={saveMeasurement} style={btnO}><Check size={14}/>Сохранить</button>
                            <button onClick={()=>setShowMeasurementForm(false)} style={btnG}><X size={14}/>Отмена</button>
                          </div>
                        </div>)}

                        <div style={{...card,padding:'14px',marginBottom:'14px',backgroundColor:missingRooms?C.warningLight:C.successLight,border:'1.5px solid '+(missingRooms?C.warningBorder:C.successBorder)}}>
                          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'8px',flexWrap:'wrap'}}>
                            <div>
                              <b style={{color:C.text,fontSize:'13px'}}>Помещения и обмеры</b>
                              <p style={{color:C.textSec,fontSize:'12px',margin:'4px 0 0'}}>{projectRooms.length?('Полный обмер: '+fullRooms+' из '+projectRooms.length+(missingRooms?' · дозаполнить: '+missingRooms:'')):'Помещения ещё не заведены'}</p>
                            </div>
                            <button onClick={()=>setActiveProjectTab('Помещения')} style={btnG}>Открыть помещения</button>
                          </div>
                        </div>

                        {renderEstimateMeasurementComparisonPanel(p)}

                        {docs.length===0&&(<div style={{...card,padding:'28px',textAlign:'center',color:C.textMuted}}>
                          <FileText size={42} style={{opacity:.35,marginBottom:'10px'}}/>
                          <p style={{margin:0}}>Исходники проекта и обмеров пока не добавлены</p>
                        </div>)}
                        {docs.map(doc=>{
                          const sm=statusMeta(doc.status);
                          const docDrafts = drafts.filter(d=>Number(d.measurementId)===Number(doc.id));
                          const docPhotos = String(doc.photoUrl || '').split(',').map(url=>url.trim()).filter(Boolean);
                          return (<div key={doc.id} style={{...card,padding:'14px',marginBottom:'10px',borderLeft:'4px solid '+sm[0]}}>
                            <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
                              <div style={{flex:1,minWidth:'220px'}}>
                                <div style={{display:'flex',gap:'6px',flexWrap:'wrap',alignItems:'center',marginBottom:'6px'}}>
                                  <span style={badge(sm[0],sm[1],sm[2])}>{doc.status}</span>
                                  <span style={{fontSize:'11px',color:C.textSec}}>{doc.sourceType+' · '+doc.docType}</span>
                                </div>
                                <b style={{color:C.text,fontSize:'13px',display:'block'}}>{doc.title||doc.docType}</b>
                                <p style={{color:C.textSec,fontSize:'12px',margin:'4px 0'}}>{(doc.uploadedBy?'Загрузил: '+doc.uploadedBy:'')+(doc.createdAt?' · '+String(doc.createdAt).slice(0,10):'')+(doc.roomsCreated?(' · помещений: '+doc.roomsCreated):'')}</p>
                                {doc.notes&&<p style={{color:C.textSec,fontSize:'12px',margin:'4px 0 0',lineHeight:1.45}}>{doc.notes}</p>}
                                {docPhotos.length>0&&<div style={{display:'flex',gap:'5px',flexWrap:'wrap',marginTop:'8px'}}>{docPhotos.slice(0,6).map((url,index)=><img key={url+index} src={fileSrc(url)} alt='' onClick={()=>setShowPhotoModal(fileSrc(url))} style={{width:'54px',height:'54px',objectFit:'cover',borderRadius:'7px',cursor:'pointer',border:'1px solid '+C.border}}/>)}{docPhotos.length>6&&<span style={{fontSize:'11px',color:C.textSec,alignSelf:'center'}}>+{docPhotos.length-6}</span>}</div>}
                                {doc.reviewedBy&&<p style={{color:C.success,fontSize:'11px',margin:'4px 0 0'}}>{'Принял: '+doc.reviewedBy}</p>}
                              </div>
                              <div style={{display:'flex',gap:'6px',flexWrap:'wrap',justifyContent:'flex-end'}}>
                                {doc.fileUrl&&<a href={fileSrc(doc.fileUrl)} target='_blank' rel='noreferrer' style={{...btnB,padding:'5px 9px',fontSize:'11px',textDecoration:'none'}}><Eye size={11}/>Файл</a>}
                                {canEditMeasurements&&<button disabled={measurementDraftLoadingId===doc.id} onClick={()=>generateRoomDrafts(doc)} style={{...btnB,padding:'5px 9px',fontSize:'11px',opacity:measurementDraftLoadingId===doc.id?0.7:1}}><Bot size={11}/>{measurementDraftLoadingId===doc.id?'Разбираю...':'ИИ разобрать'}</button>}
                                {canEditMeasurements&&doc.status!=='На проверке'&&<button onClick={()=>updateMeasurement(doc,{status:'На проверке'})} style={{...btnG,padding:'5px 9px',fontSize:'11px'}}>На проверку</button>}
                                {canEditMeasurements&&doc.status!=='Принято'&&<button onClick={()=>updateMeasurement(doc,{status:'Принято'})} style={{...btnGr,padding:'5px 9px',fontSize:'11px'}}>Принять</button>}
                                {canEditMeasurements&&doc.status!=='Отклонено'&&<button onClick={()=>updateMeasurement(doc,{status:'Отклонено'})} style={{...btnR,padding:'5px 9px',fontSize:'11px'}}>Отклонить</button>}
                                {canEditMeasurements&&<button onClick={()=>deleteMeasurement(doc)} style={{...btnR,padding:'5px 9px',fontSize:'11px'}}><Trash2 size={11}/></button>}
                              </div>
                            </div>
                            {docDrafts.length>0&&(<div style={{marginTop:'12px',paddingTop:'12px',borderTop:'1px solid '+C.border}}>
                              <b style={{color:C.text,fontSize:'12px',display:'block',marginBottom:'8px'}}>Черновики помещений из этого источника ({docDrafts.length})</b>
                              <div style={{display:'grid',gap:'8px'}}>
                                {docDrafts.map(draft=>{
                                  const accepted = draft.acceptedRoomId || draft.status==='Принято';
                                  const rejected = draft.status==='Отклонено';
                                  const dColor = accepted ? C.success : rejected ? C.danger : C.info;
                                  const dBg = accepted ? C.successLight : rejected ? C.dangerLight : C.infoLight;
                                  const dBorder = accepted ? C.successBorder : rejected ? C.dangerBorder : C.infoBorder;
                                  return (<div key={draft.id} style={{padding:'10px',borderRadius:'8px',backgroundColor:dBg,border:'1.5px solid '+dBorder}}>
                                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'8px',flexWrap:'wrap'}}>
                                      <div style={{flex:1,minWidth:'210px'}}>
                                        <span style={badge(dColor,dBg,dBorder)}>{draft.status||'Черновик ИИ'}</span>
                                        <b style={{display:'block',color:C.text,fontSize:'13px',marginTop:'5px'}}>{draft.name}</b>
                                        <p style={{color:C.textSec,fontSize:'12px',margin:'4px 0 0'}}>
                                          {'Этаж '+(draft.floor||1)+(draft.roomType?' · '+draft.roomType:'')+
                                          ' · пол '+fmtMeasure(draft.floorArea||0,'м2')+
                                          (draft.wallArea?(' · стены '+fmtMeasure(draft.wallArea,'м2')):'')+
                                          (draft.ceilingArea?(' · потолок '+fmtMeasure(draft.ceilingArea,'м2')):'')+
                                          (draft.height?(' · высота '+fmtMeasure(draft.height,'м')):'')+
                                          ((draft.windows||draft.doors)?(' · окна '+(draft.windows||0)+' / двери '+(draft.doors||0)):'')}
                                        </p>
                                        {draft.notes&&<p style={{color:C.textMuted,fontSize:'11px',margin:'4px 0 0',lineHeight:1.4}}>{draft.notes}</p>}
                                      </div>
                                      {canEditMeasurements&&<div style={{display:'flex',gap:'6px',flexWrap:'wrap',justifyContent:'flex-end'}}>
                                        {!accepted&&!rejected&&<button onClick={()=>acceptRoomDraft(draft)} style={{...btnGr,padding:'5px 9px',fontSize:'11px'}}><Check size={11}/>В помещения</button>}
                                        {!accepted&&!rejected&&<button onClick={()=>rejectRoomDraft(draft)} style={{...btnR,padding:'5px 9px',fontSize:'11px'}}><X size={11}/>Отклонить</button>}
                                        {accepted&&<button onClick={()=>setActiveProjectTab('Помещения')} style={{...btnG,padding:'5px 9px',fontSize:'11px'}}>Открыть</button>}
                                      </div>}
                                    </div>
                                  </div>);
                                })}
                              </div>
                            </div>)}
                          </div>);
                        })}
                      </div>);
                    })()}

                    {activeProjectTab==='Этапы'&&(<div>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                        <b style={{color:C.text}}>Этапы проекта</b>
                        {isProrab()&&<button onClick={()=>setShowForm(showForm==='stages'?false:'stages')} style={btnO}><Plus size={14}/>Добавить этап</button>}
                      </div>
                      {showForm==='stages'&&(<div style={{...card,padding:'16px',marginBottom:'16px',backgroundColor:C.bg}}>
                        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px'}}>
                          <input placeholder="Название этапа *" value={newStage.name} onChange={e=>setNewStage({...newStage,name:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <select value={newStage.status} onChange={e=>setNewStage({...newStage,status:e.target.value})} style={{...inp,marginBottom:0}}>{STAGE_STATUSES.map(s=><option key={s}>{s}</option>)}</select>
                          <input type="date" placeholder="Начало" value={newStage.startDate} onChange={e=>setNewStage({...newStage,startDate:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <input type="date" placeholder="Конец" value={newStage.endDate} onChange={e=>setNewStage({...newStage,endDate:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <input placeholder="Ответственный" value={newStage.responsible} onChange={e=>setNewStage({...newStage,responsible:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <div style={{display:'flex',alignItems:'center',gap:'8px'}}><label style={{fontSize:'12px',color:C.textSec,whiteSpace:'nowrap'}}>Прогресс: {newStage.progress}%</label><input type="range" min="0" max="100" value={newStage.progress} onChange={e=>setNewStage({...newStage,progress:Number(e.target.value)})} style={{flex:1,accentColor:C.accent}}/></div>
                        </div>
                        <div style={{display:'flex',gap:'8px',marginTop:'10px'}}>
                          <button onClick={()=>saveProjectStage(p.id,p.name)} style={btnO}><Check size={14}/>Сохранить</button>
                          <button onClick={()=>setShowForm(false)} style={btnG}><X size={14}/>Отмена</button>
                        </div>
                  </div>)}
                      {projectStages.filter(s=>s.projectName===p.name).map(stage=>{
                        const stColors={'Не начат':[C.textSec,C.bgGray,C.border],'В работе':[C.info,C.infoLight,C.infoBorder],'Завершён':[C.success,C.successLight,C.successBorder],'Заморожен':[C.warning,C.warningLight,C.warningBorder],'Просрочен':[C.danger,C.dangerLight,C.dangerBorder]};
                        const sc=stColors[stage.status]||stColors['Не начат'];
                        return(<div key={stage.id} style={{...card,padding:'14px',marginBottom:'10px',borderLeft:'3px solid '+sc[0]}}>
                          <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start'}}>
                            <div style={{flex:1}}>
                              <div style={{display:'flex',alignItems:'center',gap:'10px',marginBottom:'6px'}}>
                                <b style={{color:C.text,fontSize:'13px'}}>{stage.name}</b>
                                <span style={badge(sc[0],sc[1],sc[2])}>{stage.status}</span>
                              </div>
                              {(stage.startDate||stage.endDate)&&<p style={{color:C.textSec,margin:'0 0 4px',fontSize:'12px'}}>{(stage.startDate||'')+(stage.endDate?' — '+stage.endDate:'')}</p>}
                              {stage.responsible&&<p style={{color:C.textSec,margin:'0 0 6px',fontSize:'12px'}}>{'👤 '+stage.responsible}</p>}
                              <div style={{backgroundColor:C.bgGray,borderRadius:'4px',height:'6px',marginTop:'6px'}}>
                                <div style={{backgroundColor:sc[0],width:(stage.progress||0)+'%',height:'100%',borderRadius:'4px'}}/>
                              </div>
                              <p style={{color:C.textMuted,margin:'4px 0 0',fontSize:'11px'}}>{(stage.progress||0)+'% выполнено'}</p>
                            </div>
                            {isProrab()&&(<div style={{display:'flex',gap:'4px',marginLeft:'10px'}}>
                              <select value={stage.status} onChange={async e=>{await updateStage({...stage,status:e.target.value});}} style={{fontSize:'11px',padding:'3px 6px',border:'1.5px solid '+C.border,borderRadius:'6px',cursor:'pointer'}}>
                                {STAGE_STATUSES.map(s=><option key={s}>{s}</option>)}
                              </select>
                              <button onClick={()=>deleteStage(stage.id)} style={{...btnR,padding:'4px 8px'}}><Trash2 size={11}/></button>
                  </div>)}
                          </div>
                        </div>);
                      })}
                      {projectStages.filter(s=>s.projectName===p.name).length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'20px'}}>Этапов нет — добавьте первый!</p>}
                  </div>)}

	                    {activeProjectTab==='График'&&(<div>
	                      <ProjectScheduleSummaryPanel
	                        C={C}
	                        card={card}
	                        project={p}
	                        stages={projectStages}
	                        workJournal={workJournal}
	                        planDone={projectPlanDone(p)}
	                        progress={projectRealProgress(p)}
	                        materialSummary={materialControlSummaryForProject(p.name)}
	                        supplierInvoices={supplierInvoices}
	                        isMobile={isMobile}
	                        onOpenStages={()=>setActiveProjectTab('Этапы')}
	                        onOpenJournal={()=>setActiveProjectTab('Производство работ')}
	                        onOpenMaterials={()=>setActiveProjectTab('Материалы')}
	                      />
	                      <b style={{color:C.text,display:'block',marginBottom:'15px'}}>График Ганта</b>
	                      {(()=>{
                        const stages=projectStages.filter(s=>s.projectName===p.name&&s.startDate&&s.endDate);
                        if(stages.length===0) return <p style={{color:C.textMuted,textAlign:'center',padding:'30px'}}>Добавьте этапы с датами во вкладке Этапы</p>;
                        const allDates=stages.flatMap(s=>[s.startDate,s.endDate]).filter(Boolean).sort();
                        const minDate=new Date(allDates[0]);
                        const maxDate=new Date(allDates[allDates.length-1]);
                        const totalDays=Math.max(1,Math.round((maxDate-minDate)/86400000))+1;
                        const stColors={'Не начат':C.textSec,'В работе':C.info,'Завершён':C.success,'Заморожен':C.warning,'Просрочен':C.danger};
                        return(<div style={{overflowX:'auto'}}>
                          <div style={{minWidth:'600px'}}>
                            <div style={{display:'flex',borderBottom:'1.5px solid '+C.border,paddingBottom:'6px',marginBottom:'8px'}}>
                              <div style={{width:'200px',flexShrink:0,fontSize:'11px',color:C.textSec,fontWeight:'600'}}>Этап</div>
                              <div style={{flex:1,fontSize:'11px',color:C.textSec,fontWeight:'600'}}>Временная шкала</div>
                            </div>
                            {stages.map(stage=>{
                              const sd=new Date(stage.startDate);
                              const ed=new Date(stage.endDate);
                              const left=Math.round((sd-minDate)/86400000)/totalDays*100;
                              const width=Math.max(1,Math.round((ed-sd)/86400000)+1)/totalDays*100;
                              const color=stColors[stage.status]||C.textSec;
                              return(<div key={stage.id} style={{display:'flex',alignItems:'center',marginBottom:'10px'}}>
                                <div style={{width:'200px',flexShrink:0,fontSize:'12px',color:C.text,paddingRight:'10px',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{stage.name}</div>
                                <div style={{flex:1,position:'relative',height:'26px',backgroundColor:C.bg,borderRadius:'4px',border:'1px solid '+C.border}}>
                                  <div style={{position:'absolute',left:left+'%',width:width+'%',minWidth:'2%',height:'100%',backgroundColor:color,borderRadius:'4px',display:'flex',alignItems:'center',paddingLeft:'6px',overflow:'hidden'}}>
                                    <span style={{fontSize:'10px',color:'white',fontWeight:'600',whiteSpace:'nowrap'}}>{stage.progress+'%'}</span>
                                  </div>
                                </div>
                              </div>);
                            })}
                          </div>
                          {projectPayments.filter(pay=>pay.projectName===p.name).length>0&&(<div style={{marginTop:'12px'}}>
                            <b style={{color:C.textSec,fontSize:'12px',display:'block',marginBottom:'8px'}}>История оплат:</b>
                            {projectPayments.filter(pay=>pay.projectName===p.name).map(pay=>(<div key={pay.id} style={{display:'flex',justifyContent:'space-between',padding:'6px 0',borderBottom:'1px solid '+C.border}}>
                              <div><span style={{fontSize:'12px',color:C.text}}>{pay.note||'Оплата'}</span>{(pay.workPackage||pay.work_package)&&<span style={{fontSize:'11px',color:C.info,marginLeft:'8px'}}>📁 {pay.workPackage||pay.work_package}</span>}<span style={{fontSize:'11px',color:C.textMuted,marginLeft:'8px'}}>{pay.date}</span></div>
                              <b style={{fontSize:'12px',color:C.success}}>+{Number(pay.amount).toLocaleString()+' ₽'}</b>
                            </div>))}
                          </div>)}
                        </div>);
                      })()}
                  </div>)}

                    {DIRECTOR_MAP_FEATURE_ENABLED&&activeProjectTab==='Карта руководителя'&&(
                      <ProjectDirectorMapPanel
                        sandbox={false}
                        contract={directorMapContractForProject(p)}
                        onOpenStages={()=>setActiveProjectTab('Этапы')}
                        onAction={({ item, action }) => {
                          const targetTab = directorMapActionTarget({ item, action });
                          if (targetTab) setActiveProjectTab(targetTab);
                        }}
                      />
                    )}

                    {activeProjectTab==='Запуск объекта'&&(
                      <ProjectLaunchPanel
                        API={API}
                        C={C}
                        card={card}
                        btnB={btnB}
                        btnG={btnG}
                        btnO={btnO}
                        btnR={btnR}
                        project={p}
                        projectDocuments={(projectDocuments||[]).filter(doc=>(doc.projectName||doc.project_name)===p.name||Number(doc.projectId||doc.project_id)===Number(p.id))}
                        estimates={visibleEstimatesForCurrentUser(estimatesList).filter(e=>e.projectName===p.name||Number(e.projectId)===Number(p.id))}
                        isMobile={isMobile}
                        onOpenDocuments={()=>setActiveProjectTab('📁 Реестр')}
                        onOpenEstimate={()=>setActiveProjectTab('Смета')}
                      />
                    )}

	                    {activeProjectTab==='Смета'&&(<div>
	                      <b style={{color:C.text,display:'block',marginBottom:'15px'}}>Смета проекта</b>
                      <div style={{marginBottom:'14px',position:'relative'}}>
                        <Search size={15} style={{position:'absolute',left:'12px',top:'50%',transform:'translateY(-50%)',color:C.textMuted}}/>
                        <input placeholder='🔍 Поиск по позициям сметы (например: «демонтаж»)' value={estimateSearch||''} onChange={e=>setEstimateSearch(e.target.value)} style={{...inp,marginBottom:0,paddingLeft:'34px'}}/>
                      </div>
                      {estimateSearch&&estimateSearch.trim().length>=2&&(()=>{
                        const q=estimateSearch.toLowerCase().trim();
                        const projEstimates=visibleEstimatesForCurrentUser(estimatesList).filter(e=>e.projectName===p.name);
                        const results=[];
                        projEstimates.forEach(est=>{const sects=(est.sections||(typeof est.sectionsJson==='string'?(()=>{try{return JSON.parse(est.sectionsJson||'[]')}catch(_){return []}})():est.sectionsJson)||[]);sects.forEach(sec=>{(sec.items||[]).forEach(it=>{if(String(it.name||'').toLowerCase().includes(q)) results.push({estimate:est,section:sec,item:it});});});});
                        return(<div style={{...card,padding:'12px',marginBottom:'14px',backgroundColor:C.bg}}>
                          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'8px'}}>
                            <b style={{color:C.text,fontSize:'12px'}}>Найдено: {results.length} позиций</b>
                            <button onClick={()=>setEstimateSearch('')} style={{...btnG,padding:'3px 8px',fontSize:'10px'}}>×</button>
                          </div>
                          {results.length===0?<p style={{color:C.textMuted,fontSize:'12px',textAlign:'center',padding:'8px'}}>Ничего не найдено</p>:<div style={{maxHeight:'300px',overflowY:'auto'}}>{results.slice(0,100).map((r,i)=>(<div key={i} style={{padding:'8px 10px',borderRadius:'6px',marginBottom:'4px',backgroundColor:C.bgWhite,border:'1px solid '+C.border}}>
                            <b style={{fontSize:'12px',color:C.text,display:'block'}}>{r.item.name}</b>
                            <p style={{color:C.textMuted,margin:'2px 0 0',fontSize:'10px'}}>{'📂 '+r.section.name+' · '+fmtMeasure(r.item.quantity,r.item.unit)+(r.item.doneQuantity>0?' · сделано '+fmtMeasure(r.item.doneQuantity,r.item.unit):'')}</p>
                          </div>))}</div>}
                        </div>);
                      })()}
                      {(()=>{
                        const projEstimates=visibleEstimatesForCurrentUser(estimatesList).filter(e=>e.projectName===p.name);
                        if(projEstimates.length===0) return(<div style={{textAlign:'center',padding:'30px',color:C.textMuted}}><p>Смета не привязана</p><button onClick={()=>navigateTo('estimates')} style={btnO}>Перейти в Сметы</button></div>);
                        return projEstimates.map(est=>(<div key={est.id} style={{...card,padding:'14px',marginBottom:'10px'}}>
                          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                            <div><b style={{color:C.text,fontSize:'13px'}}>{est.name}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{estimateKind(est)+' · 📁 '+estimatePackage(est)+' · v'+est.version}</p></div>
                            <div style={{display:'flex',gap:'6px'}}>
                              <button onClick={()=>{openEstimateDetail(est);navigateTo('estimates');}} style={btnB}><Eye size={13}/>Открыть</button>
                            </div>
                          </div>
                        </div>));
	                      })()}
	                  </div>)}

	                    {activeProjectTab==='Сверка ЖПР'&&renderWorkJournalEstimateReconciliationPanel(p)}

	                    {activeProjectTab==='Производство работ'&&(
                      <ProjectWorkJournalPanel
                        project={p}
                        workJournal={workJournal}
                        workJournalPage={workJournalPage}
                        loadWorkJournalPage={loadWorkJournalPage}
                        weatherLog={weatherLog}
                        listSearch={listSearch}
                        setListSearch={setListSearch}
                        matchSearch={matchSearch}
                        setShowJournalTableModal={setShowJournalTableModal}
                        showPreview={showPreview}
                        buildJPRContent={buildJPRContent}
                        showKS2={showKS2}
                        setEditingJournal={setEditingJournal}
                        getActStatusForJournal={getActStatusForJournal}
                        setEditingAct={setEditingAct}
                        openConfirmModal={openConfirmModal}
                        setRejectingEntry={setRejectingEntry}
                        canConfirm={isProrab()}
                        showCustomerTotals={['директор','зам_директора','бухгалтер','сметчик','главный_инженер','прораб'].includes(user?.role)}
                        fileSrc={fileSrc}
                        setShowPhotoModal={setShowPhotoModal}
                        C={C}
                        inp={inp}
                        btnB={btnB}
                        btnG={btnG}
                        btnGr={btnGr}
                        btnR={btnR}
                        badge={badge}
                      />
                    )}

	                    {activeProjectTab==='Помещения'&&(<div>
	                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
	                        <b style={{color:C.text}}>Помещения</b>
                        {isProrab()&&<button onClick={()=>{setShowRoomForm(!showRoomForm);setEditingItem(null);setDraftRoomWindows([]);setDraftRoomDoors([]);setNewRoom({project:p.name,name:'',floor:'',liter:'',roomType:'Комната',floorArea:'',wallArea:'',ceilingArea:'',height:'',ceilingType:'Простой',wallMaterial:'Штукатурка',floorMaterial:'Стяжка',photoUrl:'',notes:''});}} style={btnO}><Plus size={14}/>Добавить</button>}
                      </div>
                      {showRoomForm&&(<div style={{...card,padding:'16px',marginBottom:'16px',backgroundColor:C.bg}}>
                        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px'}}>
                          <input placeholder="Название помещения * (например: Кабинет 204)" value={newRoom.name} onChange={e=>setNewRoom({...newRoom,name:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <input placeholder="Этаж (1,2,3...)" type="number" step="any" inputMode="decimal" value={newRoom.floor||''} onChange={e=>setNewRoom({...newRoom,floor:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <input placeholder="Литер (А,Б,В...)" value={newRoom.liter||''} onChange={e=>setNewRoom({...newRoom,liter:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <select value={['Комната','Кабинет','Коридор','Санузел','Кухня','Балкон','Лестница','Холл','Техническое','Другое',...customRoomTypes].includes(newRoom.roomType||'Комната')?(newRoom.roomType||'Комната'):'Другое'} onChange={e=>setNewRoom({...newRoom,roomType:e.target.value})} style={{...inp,marginBottom:0}}>
                            {[...'Комната,Кабинет,Коридор,Санузел,Кухня,Балкон,Лестница,Холл,Техническое'.split(','),...customRoomTypes,'Другое'].map(t=><option key={t}>{t}</option>)}
                          </select>
                          {(newRoom.roomType==='Другое'||(!['Комната','Кабинет','Коридор','Санузел','Кухня','Балкон','Лестница','Холл','Техническое','Другое',''].includes(newRoom.roomType||'Комната')))&&<input placeholder='Свой тип помещения, например: Серверная' value={newRoom.roomType==='Другое'?'':newRoom.roomType||''} onChange={e=>setNewRoom({...newRoom,roomType:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>}
                          <input placeholder="Высота (м)" type="number" step="any" inputMode="decimal" value={newRoom.height} onChange={e=>setNewRoom({...newRoom,height:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <input placeholder="Площадь пола (м2)" type="number" step="any" inputMode="decimal" value={newRoom.floorArea} onChange={e=>setNewRoom({...newRoom,floorArea:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <input placeholder="Площадь стен (м2)" type="number" step="any" inputMode="decimal" value={newRoom.wallArea} onChange={e=>setNewRoom({...newRoom,wallArea:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <input placeholder="Площадь потолка (м2)" type="number" step="any" inputMode="decimal" value={newRoom.ceilingArea} onChange={e=>setNewRoom({...newRoom,ceilingArea:e.target.value})} style={{...inp,marginBottom:0}}/>
                        </div>
                        {(()=>{
                          const existingWins = editingItem ? roomWindows.filter(w=>Number(w.room_id)===Number(editingItem.id)) : [];
                          const existingDoors = editingItem ? roomDoors.filter(d=>Number(d.room_id)===Number(editingItem.id)) : [];
                          const draftOpeningsArea = draftRoomWindows.reduce((s,w)=>s+calcWindowArea(w),0)+draftRoomDoors.reduce((s,d)=>s+calcDoorArea(d),0);
                          const draftWindowReveals = draftRoomWindows.reduce((s,w)=>s+calcWindowReveals(w),0);
                          const draftDoorReveals = draftRoomDoors.reduce((s,d)=>s+calcDoorReveals(d),0);
                          const draftNetWall = Math.max(0, Number(newRoom.wallArea||0)-draftOpeningsArea);
                          return (
                            <div style={{marginTop:'10px',padding:'12px',borderRadius:'10px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border}}>
                              <div style={{display:'flex',justifyContent:'space-between',gap:'10px',alignItems:'flex-start',marginBottom:'10px',flexWrap:'wrap'}}>
                                <div>
                                  <b style={{color:C.text,fontSize:'13px'}}>Окна, двери и откосы</b>
                                  <p style={{color:C.textSec,fontSize:'11px',margin:'3px 0 0'}}>Окна и двери вычитаются из стен. Откосы считаются отдельной площадью.</p>
                                </div>
                                {!editingItem&&<div style={{display:'flex',gap:'6px',flexWrap:'wrap'}}>
                                  <span style={badge(C.info,C.infoLight,C.infoBorder)}>{'Чистые стены: '+draftNetWall.toFixed(2)+' м2'}</span>
                                  <span style={badge(C.accent,C.accentLight,C.accentBorder)}>{'Откосы: '+(draftWindowReveals+draftDoorReveals).toFixed(2)+' м2'}</span>
                                </div>}
                              </div>
                              {editingItem?(
                                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',padding:'10px',borderRadius:'8px',backgroundColor:C.bg,border:'1px solid '+C.border,flexWrap:'wrap'}}>
                                  <span style={{color:C.textSec,fontSize:'12px'}}>{'Сейчас в помещении: окон '+existingWins.length+', дверей '+existingDoors.length+'. Для правки размеров раскройте карточку помещения ниже.'}</span>
                                  <button onClick={()=>{setExpandedRoom(editingItem.id);setShowRoomForm(false);}} style={{...btnG,padding:'6px 10px',fontSize:'12px'}}>Открыть окна/двери</button>
                                </div>
                              ):(
                                <div style={{display:'grid',gridTemplateColumns:isMobile?'1fr':'1fr 1fr',gap:'10px'}}>
                                  <div style={{padding:'10px',borderRadius:'8px',backgroundColor:C.bg,border:'1px solid '+C.border}}>
                                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'8px',gap:'8px'}}>
                                      <b style={{color:C.text,fontSize:'12px'}}>Окна</b>
                                      <button onClick={()=>setDraftRoomWindows(prev=>[...prev,{name:'Окно '+(prev.length+1),width:'',height:'',windowType:'ПВХ',revealDepth:'',revealMaterial:'Штукатурка'}])} style={{...btnO,padding:'4px 8px',fontSize:'11px'}}><Plus size={11}/>Окно</button>
                                    </div>
                                    {draftRoomWindows.length===0&&<p style={{color:C.textMuted,fontSize:'11px',margin:'0'}}>Окон нет</p>}
                                    {draftRoomWindows.map((w,idx)=>(<div key={'draft-window-'+idx} style={{display:'grid',gridTemplateColumns:isMobile?'1fr 1fr':'1.1fr .9fr .8fr .8fr .8fr 34px',gap:'6px',alignItems:'center',marginBottom:'6px'}}>
                                      <input placeholder="Название" value={w.name} onChange={e=>setDraftRoomWindows(prev=>prev.map((x,i)=>i===idx?{...x,name:e.target.value}:x))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'8px'}}/>
                                      <select value={w.windowType||'ПВХ'} onChange={e=>setDraftRoomWindows(prev=>prev.map((x,i)=>i===idx?{...x,windowType:e.target.value}:x))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'8px'}}>{WINDOW_TYPES.map(t=><option key={t}>{t}</option>)}</select>
                                      <input placeholder="Шир., м" type="number" step="any" inputMode="decimal" value={w.width} onChange={e=>setDraftRoomWindows(prev=>prev.map((x,i)=>i===idx?{...x,width:e.target.value}:x))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'8px'}}/>
                                      <input placeholder="Выс., м" type="number" step="any" inputMode="decimal" value={w.height} onChange={e=>setDraftRoomWindows(prev=>prev.map((x,i)=>i===idx?{...x,height:e.target.value}:x))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'8px'}}/>
                                      <input placeholder="Откос, см" type="number" step="any" inputMode="decimal" value={w.revealDepth} onChange={e=>setDraftRoomWindows(prev=>prev.map((x,i)=>i===idx?{...x,revealDepth:e.target.value}:x))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'8px'}}/>
                                      <button onClick={()=>setDraftRoomWindows(prev=>prev.filter((_,i)=>i!==idx))} style={{...btnR,padding:'7px'}}><Trash2 size={11}/></button>
                                    </div>))}
                                  </div>
                                  <div style={{padding:'10px',borderRadius:'8px',backgroundColor:C.bg,border:'1px solid '+C.border}}>
                                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'8px',gap:'8px'}}>
                                      <b style={{color:C.text,fontSize:'12px'}}>Двери</b>
                                      <button onClick={()=>setDraftRoomDoors(prev=>[...prev,{name:'Дверь '+(prev.length+1),width:'',height:'',doorType:'Деревянная',doorPurpose:'Межкомнатная',revealDepth:'',revealMaterial:'Штукатурка'}])} style={{...btnO,padding:'4px 8px',fontSize:'11px'}}><Plus size={11}/>Дверь</button>
                                    </div>
                                    {draftRoomDoors.length===0&&<p style={{color:C.textMuted,fontSize:'11px',margin:'0'}}>Дверей нет</p>}
                                    {draftRoomDoors.map((d,idx)=>(<div key={'draft-door-'+idx} style={{display:'grid',gridTemplateColumns:isMobile?'1fr 1fr':'1.1fr .9fr .8fr .8fr .8fr 34px',gap:'6px',alignItems:'center',marginBottom:'6px'}}>
                                      <input placeholder="Название" value={d.name} onChange={e=>setDraftRoomDoors(prev=>prev.map((x,i)=>i===idx?{...x,name:e.target.value}:x))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'8px'}}/>
                                      <select value={d.doorPurpose||'Межкомнатная'} onChange={e=>setDraftRoomDoors(prev=>prev.map((x,i)=>i===idx?{...x,doorPurpose:e.target.value}:x))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'8px'}}>{DOOR_PURPOSES.map(t=><option key={t}>{t}</option>)}</select>
                                      <input placeholder="Шир., м" type="number" step="any" inputMode="decimal" value={d.width} onChange={e=>setDraftRoomDoors(prev=>prev.map((x,i)=>i===idx?{...x,width:e.target.value}:x))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'8px'}}/>
                                      <input placeholder="Выс., м" type="number" step="any" inputMode="decimal" value={d.height} onChange={e=>setDraftRoomDoors(prev=>prev.map((x,i)=>i===idx?{...x,height:e.target.value}:x))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'8px'}}/>
                                      <input placeholder="Откос, см" type="number" step="any" inputMode="decimal" value={d.revealDepth} onChange={e=>setDraftRoomDoors(prev=>prev.map((x,i)=>i===idx?{...x,revealDepth:e.target.value}:x))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'8px'}}/>
                                      <button onClick={()=>setDraftRoomDoors(prev=>prev.filter((_,i)=>i!==idx))} style={{...btnR,padding:'7px'}}><Trash2 size={11}/></button>
                                    </div>))}
                                  </div>
                                </div>
                              )}
                            </div>
                          );
                        })()}
                        <div style={{marginTop:'8px'}}>
                          <PhotoAttachmentField
                            C={C}
                            btnG={btnG}
                            value={newRoom.photoUrl || ''}
                            onChange={photoUrl => setNewRoom({...newRoom, photoUrl})}
                            appendPhotos={appendPhotos}
                            fileSrc={fileSrc}
                            setShowPhotoModal={setShowPhotoModal}
                            projectName={p.name}
                            context="room-measurements"
                            title="Фото помещения / лист замера"
                          />
                        </div>
                        <div style={{display:'flex',gap:'8px',marginTop:'10px'}}><button onClick={saveRoom} style={btnO}><Check size={14}/>{editingItem?'Сохранить':'Добавить'}</button><button onClick={()=>{setShowRoomForm(false);setEditingItem(null);setDraftRoomWindows([]);setDraftRoomDoors([]);}} style={btnG}><X size={14}/>Отмена</button></div>
                  </div>)}
                      {(()=>{const projectRooms=rooms.filter(r=>r.project===p.name);if(projectRooms.length===0)return null;const checked=projectRooms.map(roomCompleteness);const full=checked.filter(x=>x.status==='Обмер полный').length;const missing=checked.filter(x=>x.status==='Не хватает данных').length;const openings=checked.filter(x=>x.status==='Проверить проёмы').length;return(<div style={{...card,padding:'12px',marginBottom:'12px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border}}>
                        <div style={{display:'grid',gridTemplateColumns:isMobile?'1fr 1fr':'repeat(4,1fr)',gap:'8px'}}>
                          <div style={{padding:'10px',borderRadius:'8px',backgroundColor:C.bg,border:'1px solid '+C.border}}><p style={{color:C.textSec,fontSize:'10px',margin:'0 0 3px'}}>Помещений</p><b style={{color:C.text,fontSize:'16px'}}>{projectRooms.length}</b></div>
                          <div style={{padding:'10px',borderRadius:'8px',backgroundColor:C.successLight,border:'1px solid '+C.successBorder}}><p style={{color:C.success,fontSize:'10px',margin:'0 0 3px'}}>Обмер полный</p><b style={{color:C.success,fontSize:'16px'}}>{full}</b></div>
                          <div style={{padding:'10px',borderRadius:'8px',backgroundColor:missing?C.warningLight:C.bg,border:'1px solid '+(missing?C.warningBorder:C.border)}}><p style={{color:missing?C.warning:C.textSec,fontSize:'10px',margin:'0 0 3px'}}>Дозаполнить</p><b style={{color:missing?C.warning:C.text,fontSize:'16px'}}>{missing}</b></div>
                          <div style={{padding:'10px',borderRadius:'8px',backgroundColor:openings?C.infoLight:C.bg,border:'1px solid '+(openings?C.infoBorder:C.border)}}><p style={{color:openings?C.info:C.textSec,fontSize:'10px',margin:'0 0 3px'}}>Проёмы/откосы</p><b style={{color:openings?C.info:C.text,fontSize:'16px'}}>{openings}</b></div>
                        </div>
                      </div>);})()}
                      {rooms.filter(r=>r.project===p.name).map(room=>{
                        const wins=roomWindows.filter(w=>Number(w.room_id)===Number(room.id));
                        const doors=roomDoors.filter(d=>Number(d.room_id)===Number(room.id));
                        const netWall=getRoomNetWall(room);
                        const winRevTotal=wins.reduce((s,w)=>s+calcWindowReveals(w),0);
                        const doorRevTotal=doors.reduce((s,d)=>s+calcDoorReveals(d),0);
                        const isRoomOpen=expandedRoom===room.id;
                        const completeness=roomCompleteness(room);
                        const roomPhotos=String(room.photoUrl||room.photo_url||'').split(',').map(url=>url.trim()).filter(Boolean);
                        return(<div key={room.id} style={{...card,marginBottom:'10px'}}>
                          <div style={{padding:'14px',cursor:'pointer',display:'flex',justifyContent:'space-between',alignItems:'center'}} onClick={()=>setExpandedRoom(isRoomOpen?null:room.id)}>
                            <div style={{minWidth:0,flex:1}}><b style={{color:C.text,fontSize:'13px'}}>{room.name}</b>{room.floor&&<span style={{fontSize:'11px',color:C.accent,marginLeft:'6px',padding:'1px 6px',backgroundColor:C.accentLight,borderRadius:'4px'}}>{'Эт.'+room.floor+(room.liter?' Лит.'+room.liter:'')}</span>}{room.roomType&&<span style={{fontSize:'11px',color:C.textSec,marginLeft:'4px'}}>{'· '+room.roomType}</span>}<span style={{...badge(completeness.color,completeness.bg,completeness.border),marginLeft:'6px'}}>{completeness.status}</span><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{'Пол: '+room.floorArea+'м² · Стены: '+room.wallArea+'м² (чистые: '+netWall+'м²) · Потолок: '+room.ceilingArea+'м² · Высота: '+(room.height||'—')+'м'}</p><p style={{color:C.textSec,margin:'0',fontSize:'11px'}}>{'Окна: '+wins.length+'шт · Двери: '+doors.length+'шт'+(winRevTotal>0?' · Откосы окон: '+winRevTotal+'м²':'')+(doorRevTotal>0?' · Откосы дверей: '+doorRevTotal+'м²':'')}</p>{roomPhotos.length>0&&<div style={{display:'flex',gap:'4px',flexWrap:'wrap',marginTop:'6px'}}>{roomPhotos.slice(0,4).map((url,index)=><img key={url+index} src={fileSrc(url)} alt='' onClick={e=>{e.stopPropagation();setShowPhotoModal(fileSrc(url));}} style={{width:'44px',height:'44px',objectFit:'cover',borderRadius:'6px',cursor:'pointer',border:'1px solid '+C.border}}/>)}{roomPhotos.length>4&&<span style={{fontSize:'11px',color:C.textSec,alignSelf:'center'}}>+{roomPhotos.length-4}</span>}</div>}{completeness.issues.length>0&&<p style={{color:completeness.color,margin:'3px 0 0',fontSize:'11px',fontWeight:'600'}}>{'Нужно: '+completeness.issues.slice(0,4).join(', ')+(completeness.issues.length>4?' …':'')}</p>}</div>
                            <div style={{display:'flex',gap:'6px',alignItems:'center'}}>
                              {isProrab()&&(<><button onClick={e=>{e.stopPropagation();setEditingItem(room);setDraftRoomWindows([]);setDraftRoomDoors([]);setNewRoom({project:room.project,name:room.name,floor:room.floor||'',liter:room.liter||'',roomType:room.roomType||'Комната',floorArea:room.floorArea,wallArea:room.wallArea,ceilingArea:room.ceilingArea,height:room.height||'',ceilingType:room.ceiling_type||room.ceilingType||'Простой',wallMaterial:room.wall_material||room.wallMaterial||'Штукатурка',floorMaterial:room.floor_material||room.floorMaterial||'Стяжка',photoUrl:room.photoUrl||room.photo_url||'',notes:room.notes||''});setShowRoomForm(true);}} style={{...btnG,padding:'4px 8px'}}><Edit2 size={11}/></button><button onClick={e=>{e.stopPropagation();deleteRoom(room.id);}} style={{...btnR,padding:'4px 8px'}}><Trash2 size={11}/></button></>)}
                              {isRoomOpen?<ChevronUp size={16} color={C.textMuted}/>:<ChevronDown size={16} color={C.textMuted}/>}
                            </div>
                          </div>
                          {isRoomOpen&&(<div style={{borderTop:'1.5px solid '+C.border,padding:'14px'}}>
                            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'16px'}}>
                              <div>
                                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'10px'}}>
                                  <b style={{color:C.text,fontSize:'13px'}}>🪟 Окна</b>
                                  <button onClick={()=>setNewWindow({roomId:room.id,name:'Окно '+(wins.length+1),width:'',height:'',windowType:'ПВХ',revealDepth:'',revealMaterial:'Штукатурка'})} style={{...btnO,padding:'4px 10px',fontSize:'11px'}}><Plus size={11}/>Добавить</button>
                                </div>
                                {wins.map(w=>(<div key={w.id} style={{padding:'8px',backgroundColor:C.bg,borderRadius:'8px',marginBottom:'6px',border:'1.5px solid '+C.border}}>
                                  {editingWindow===w.id?(<div>
                                    <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'6px',marginBottom:'8px'}}>
                                      <input placeholder="Название" value={w.name} onChange={e=>{const updated=roomWindows.map(x=>x.id===w.id?{...x,name:e.target.value}:x);setRoomWindows(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <select value={w.window_type||w.windowType||'ПВХ'} onChange={e=>{const updated=roomWindows.map(x=>x.id===w.id?{...x,window_type:e.target.value}:x);setRoomWindows(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}>{WINDOW_TYPES.map(t=><option key={t}>{t}</option>)}</select>
                                      <input placeholder="Ширина (м)" type="number" step="any" inputMode="decimal" value={w.width} onChange={e=>{const updated=roomWindows.map(x=>x.id===w.id?{...x,width:e.target.value}:x);setRoomWindows(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <input placeholder="Высота (м)" type="number" step="any" inputMode="decimal" value={w.height} onChange={e=>{const updated=roomWindows.map(x=>x.id===w.id?{...x,height:e.target.value}:x);setRoomWindows(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <input placeholder="Откос (см)" type="number" step="any" inputMode="decimal" value={w.reveal_depth||w.revealDepth||''} onChange={e=>{const updated=roomWindows.map(x=>x.id===w.id?{...x,reveal_depth:e.target.value}:x);setRoomWindows(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <select value={w.reveal_material||w.revealMaterial||'Штукатурка'} onChange={e=>{const updated=roomWindows.map(x=>x.id===w.id?{...x,reveal_material:e.target.value}:x);setRoomWindows(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}>{REVEAL_MATERIALS.map(t=><option key={t}>{t}</option>)}</select>
                                    </div>
                                    <div style={{display:'flex',gap:'6px'}}><button onClick={()=>updateWindow(w)} style={{...btnGr,padding:'4px 10px',fontSize:'11px'}}><Check size={11}/>Сохранить</button><button onClick={()=>setEditingWindow(null)} style={{...btnG,padding:'4px 10px',fontSize:'11px'}}><X size={11}/>Отмена</button></div>
                                  </div>):(<div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                                    <div><b style={{fontSize:'12px',color:C.text}}>{w.name}</b><p style={{color:C.textSec,margin:'1px 0',fontSize:'11px'}}>{(w.window_type||w.windowType||'ПВХ')+' '+w.width+'×'+w.height+'м = '+calcWindowArea(w).toFixed(2)+'м²'}</p>{calcWindowReveals(w)>0&&<p style={{color:C.info,margin:'0',fontSize:'10px'}}>{'Откосы: '+calcWindowReveals(w).toFixed(2)+'м² ('+((w.reveal_depth||w.revealDepth)||0)+'см)'}</p>}</div>
                                    <div style={{display:'flex',gap:'4px'}}><button onClick={()=>setEditingWindow(w.id)} style={{...btnG,padding:'3px 7px'}}><Edit2 size={10}/></button><button onClick={()=>deleteWindow(w.id)} style={{...btnR,padding:'3px 7px'}}><Trash2 size={10}/></button></div>
                  </div>)}
                                </div>))}
                                {newWindow.roomId===room.id&&(<div style={{padding:'10px',backgroundColor:C.accentLight,borderRadius:'8px',border:'1.5px solid '+C.accentBorder}}>
                                  <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'6px',marginBottom:'8px'}}>
                                    <input placeholder="Название" value={newWindow.name} onChange={e=>setNewWindow({...newWindow,name:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    <select value={newWindow.windowType} onChange={e=>setNewWindow({...newWindow,windowType:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}>{WINDOW_TYPES.map(t=><option key={t}>{t}</option>)}</select>
                                    <input placeholder="Ширина (м)" type="number" step="any" inputMode="decimal" value={newWindow.width} onChange={e=>setNewWindow({...newWindow,width:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    <input placeholder="Высота (м)" type="number" step="any" inputMode="decimal" value={newWindow.height} onChange={e=>setNewWindow({...newWindow,height:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    <input placeholder="Откос (см)" type="number" step="any" inputMode="decimal" value={newWindow.revealDepth} onChange={e=>setNewWindow({...newWindow,revealDepth:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    <select value={newWindow.revealMaterial} onChange={e=>setNewWindow({...newWindow,revealMaterial:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}>{REVEAL_MATERIALS.map(t=><option key={t}>{t}</option>)}</select>
                                  </div>
                                  <div style={{display:'flex',gap:'6px'}}><button onClick={()=>saveWindow(room.id)} style={{...btnO,padding:'5px 12px',fontSize:'11px'}}><Check size={11}/>Добавить</button><button onClick={()=>setNewWindow({roomId:'',name:'Окно 1',width:'',height:'',windowType:'ПВХ',revealDepth:'',revealMaterial:'Штукатурка'})} style={{...btnG,padding:'5px 12px',fontSize:'11px'}}><X size={11}/>Отмена</button></div>
                  </div>)}
                              </div>
                              <div>
                                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'10px'}}>
                                  <b style={{color:C.text,fontSize:'13px'}}>🚪 Двери</b>
                                  <button onClick={()=>setNewDoor({roomId:room.id,name:'Дверь '+(doors.length+1),width:'',height:'',doorType:'Деревянная',doorPurpose:'Межкомнатная',revealDepth:'',revealMaterial:'Штукатурка'})} style={{...btnO,padding:'4px 10px',fontSize:'11px'}}><Plus size={11}/>Добавить</button>
                                </div>
                                {doors.map(d=>(<div key={d.id} style={{padding:'8px',backgroundColor:C.bg,borderRadius:'8px',marginBottom:'6px',border:'1.5px solid '+C.border}}>
                                  {editingDoor===d.id?(<div>
                                    <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'6px',marginBottom:'8px'}}>
                                      <input placeholder="Название" value={d.name} onChange={e=>{const updated=roomDoors.map(x=>x.id===d.id?{...x,name:e.target.value}:x);setRoomDoors(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <select value={d.door_type||d.doorType||'Деревянная'} onChange={e=>{const updated=roomDoors.map(x=>x.id===d.id?{...x,door_type:e.target.value}:x);setRoomDoors(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}>{DOOR_TYPES.map(t=><option key={t}>{t}</option>)}</select>
                                      <select value={d.door_purpose||d.doorPurpose||'Межкомнатная'} onChange={e=>{const updated=roomDoors.map(x=>x.id===d.id?{...x,door_purpose:e.target.value}:x);setRoomDoors(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}>{DOOR_PURPOSES.map(t=><option key={t}>{t}</option>)}</select>
                                      <input placeholder="Ширина (м)" type="number" step="any" inputMode="decimal" value={d.width} onChange={e=>{const updated=roomDoors.map(x=>x.id===d.id?{...x,width:e.target.value}:x);setRoomDoors(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <input placeholder="Высота (м)" type="number" step="any" inputMode="decimal" value={d.height} onChange={e=>{const updated=roomDoors.map(x=>x.id===d.id?{...x,height:e.target.value}:x);setRoomDoors(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <input placeholder="Откос (см)" type="number" step="any" inputMode="decimal" value={d.reveal_depth||d.revealDepth||''} onChange={e=>{const updated=roomDoors.map(x=>x.id===d.id?{...x,reveal_depth:e.target.value}:x);setRoomDoors(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <select value={d.reveal_material||d.revealMaterial||'Штукатурка'} onChange={e=>{const updated=roomDoors.map(x=>x.id===d.id?{...x,reveal_material:e.target.value}:x);setRoomDoors(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}>{REVEAL_MATERIALS.map(t=><option key={t}>{t}</option>)}</select>
                                    </div>
                                    <div style={{display:'flex',gap:'6px'}}><button onClick={()=>updateDoor(d)} style={{...btnGr,padding:'4px 10px',fontSize:'11px'}}><Check size={11}/>Сохранить</button><button onClick={()=>setEditingDoor(null)} style={{...btnG,padding:'4px 10px',fontSize:'11px'}}><X size={11}/>Отмена</button></div>
                                  </div>):(<div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                                    <div><b style={{fontSize:'12px',color:C.text}}>{d.name}</b><p style={{color:C.textSec,margin:'1px 0',fontSize:'11px'}}>{(d.door_type||d.doorType||'')+(d.door_purpose||d.doorPurpose?'/'+(d.door_purpose||d.doorPurpose):'')+ ' '+d.width+'×'+d.height+'м = '+calcDoorArea(d).toFixed(2)+'м²'}</p>{calcDoorReveals(d)>0&&<p style={{color:C.info,margin:'0',fontSize:'10px'}}>{'Откосы: '+calcDoorReveals(d).toFixed(2)+'м² ('+((d.reveal_depth||d.revealDepth)||0)+'см)'}</p>}</div>
                                    <div style={{display:'flex',gap:'4px'}}><button onClick={()=>setEditingDoor(d.id)} style={{...btnG,padding:'3px 7px'}}><Edit2 size={10}/></button><button onClick={()=>deleteDoor(d.id)} style={{...btnR,padding:'3px 7px'}}><Trash2 size={10}/></button></div>
                  </div>)}
                                </div>))}
                                {newDoor.roomId===room.id&&(<div style={{padding:'10px',backgroundColor:C.accentLight,borderRadius:'8px',border:'1.5px solid '+C.accentBorder}}>
                                  <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'6px',marginBottom:'8px'}}>
                                    <input placeholder="Название" value={newDoor.name} onChange={e=>setNewDoor({...newDoor,name:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    <select value={newDoor.doorType} onChange={e=>setNewDoor({...newDoor,doorType:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}>{DOOR_TYPES.map(t=><option key={t}>{t}</option>)}</select>
                                    <select value={newDoor.doorPurpose} onChange={e=>setNewDoor({...newDoor,doorPurpose:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}>{DOOR_PURPOSES.map(t=><option key={t}>{t}</option>)}</select>
                                    <input placeholder="Ширина (м)" type="number" step="any" inputMode="decimal" value={newDoor.width} onChange={e=>setNewDoor({...newDoor,width:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    <input placeholder="Высота (м)" type="number" step="any" inputMode="decimal" value={newDoor.height} onChange={e=>setNewDoor({...newDoor,height:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    <input placeholder="Откос (см)" type="number" step="any" inputMode="decimal" value={newDoor.revealDepth} onChange={e=>setNewDoor({...newDoor,revealDepth:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    <select value={newDoor.revealMaterial} onChange={e=>setNewDoor({...newDoor,revealMaterial:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}>{REVEAL_MATERIALS.map(t=><option key={t}>{t}</option>)}</select>
                                  </div>
                                  <div style={{display:'flex',gap:'6px'}}><button onClick={()=>saveDoor(room.id)} style={{...btnO,padding:'5px 12px',fontSize:'11px'}}><Check size={11}/>Добавить</button><button onClick={()=>setNewDoor({roomId:'',name:'Дверь 1',width:'',height:'',doorType:'Деревянная',doorPurpose:'Межкомнатная',revealDepth:'',revealMaterial:'Штукатурка'})} style={{...btnG,padding:'5px 12px',fontSize:'11px'}}><X size={11}/>Отмена</button></div>
                  </div>)}
                              </div>
                            </div>
                  </div>)}
                        </div>);
                      })}
                      {rooms.filter(r=>r.project===p.name).length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'20px'}}>Помещений нет</p>}
                  </div>)}

                    {activeProjectTab==='Чек-листы'&&(<div>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                        <b style={{color:C.text}}>Чек-листы</b>
                        {isProrab()&&<button onClick={()=>setShowForm(showForm==='checklist'?false:'checklist')} style={btnO}><Plus size={14}/>Создать</button>}
                      </div>
                      {showForm==='checklist'&&(<div style={{...card,padding:'16px',marginBottom:'16px',backgroundColor:C.bg}}>
                        <input placeholder="Название чек-листа *" value={newChecklist.name} onChange={e=>setNewChecklist({...newChecklist,name:e.target.value})} style={inp}/>
                        <select value={newChecklist.template} onChange={e=>setNewChecklist({...newChecklist,template:e.target.value,name:e.target.value||newChecklist.name})} style={inp}><option value="">Свой чек-лист</option>{Object.keys(CHECKLIST_TEMPLATES).map(t=><option key={t} value={t}>{t}</option>)}</select>
                        <div style={{display:'flex',gap:'8px'}}><button onClick={()=>saveChecklist(p.id,p.name)} style={btnO}><Check size={14}/>Создать</button><button onClick={()=>setShowForm(false)} style={btnG}><X size={14}/>Отмена</button></div>
                  </div>)}
                      {checklists.filter(cl=>cl.projectName===p.name).map(cl=>{
                        const items=checklistItems[cl.id]||[];
                        const checked=items.filter(i=>i.checked).length;
                        const isOpen=selectedChecklist===cl.id;
                        return(<div key={cl.id} style={{...card,marginBottom:'10px'}}>
                          <div style={{padding:'14px',cursor:'pointer',display:'flex',justifyContent:'space-between',alignItems:'center'}} onClick={async()=>{if(isOpen){setSelectedChecklist(null);}else{setSelectedChecklist(cl.id);await loadChecklistItems(cl.id);}}}>
                            <div><b style={{color:C.text,fontSize:'13px'}}>{cl.name}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{checked+'/'+items.length+' выполнено'}</p></div>
                            <div style={{display:'flex',alignItems:'center',gap:'10px'}}>
                              <div style={{backgroundColor:C.bgGray,borderRadius:'10px',height:'8px',width:'80px'}}><div style={{backgroundColor:items.length>0&&checked===items.length?C.success:C.accent,width:(items.length>0?checked/items.length*100:0)+'%',height:'100%',borderRadius:'10px'}}/></div>
                              {isOpen?<ChevronUp size={16} color={C.textMuted}/>:<ChevronDown size={16} color={C.textMuted}/>}
                            </div>
                          </div>
                          {isOpen&&(<div style={{borderTop:'1.5px solid '+C.border,padding:'12px 14px'}}>
                            {items.map(item=>(<div key={item.id} style={{display:'flex',alignItems:'center',gap:'10px',padding:'8px 0',borderBottom:'1px solid '+C.border}}>
                              <input type="checkbox" checked={item.checked} onChange={()=>toggleChecklistItem(item)} style={{width:'18px',height:'18px',accentColor:C.accent,cursor:'pointer'}}/>
                              <span style={{fontSize:'13px',color:item.checked?C.textMuted:C.text,textDecoration:item.checked?'line-through':'none',flex:1}}>{item.name}</span>
                              {item.checked&&item.checkedBy&&<span style={{fontSize:'11px',color:C.textMuted}}>{item.checkedBy}</span>}
                            </div>))}
                            <div style={{display:'flex',gap:'8px',marginTop:'10px'}}>
                              <input placeholder="Добавить пункт..." value={newChecklistItem} onChange={e=>setNewChecklistItem(e.target.value)} style={{...inp,marginBottom:0,flex:1,fontSize:'12px'}}/>
                              <button onClick={async()=>{if(!newChecklistItem) return;await fetch(API+'/checklist-items',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({checklistId:cl.id,name:newChecklistItem,checked:false,orderNum:items.length})});await loadChecklistItems(cl.id);setNewChecklistItem('');}} style={{...btnO,padding:'6px 12px'}}><Plus size={13}/></button>
                            </div>
                  </div>)}
                        </div>);
                      })}
                      {checklists.filter(cl=>cl.projectName===p.name).length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'20px'}}>Чек-листов нет</p>}
                  </div>)}

                    {activeProjectTab==='Изменения к смете'&&(<div>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                        <b style={{color:C.text}}>Изменения к смете</b>
                        <button onClick={()=>setShowForm(showForm==='unexpected'?false:'unexpected')} style={btnO}><Plus size={14}/>Создать изменение</button>
                      </div>
                      {(()=>{const budget=Number(p.budget||0);if(budget<=0) return null;const approved=(unexpectedWorksList||[]).filter(u=>u.projectName===p.name&&isApprovedEstimateChangeStatus(u.status)&&u.changeType!=='Исключение объёма'&&!u.includedInEstimateId).reduce((s,u)=>s+Number(u.total||0),0);const pending=(unexpectedWorksList||[]).filter(u=>u.projectName===p.name&&u.status==='Ожидает согласования'&&u.changeType!=='Исключение объёма').reduce((s,u)=>s+Number(u.total||0),0);const pct=Math.round(approved/budget*100*10)/10;const LIMIT=10;const overLimit=pct>LIMIT;if(approved===0&&pending===0) return null;return(<div style={{...card,padding:'12px',marginBottom:'14px',backgroundColor:overLimit?C.dangerLight:pct>LIMIT*0.7?C.warningLight:C.bg,border:'1.5px solid '+(overLimit?C.dangerBorder:pct>LIMIT*0.7?C.warningBorder:C.border)}}>
                        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap'}}>
                          <div>
                            <b style={{color:C.text,fontSize:'13px'}}>📊 Изменения отдельной допработой: {pct}% от бюджета (контрольный порог {LIMIT}%)</b>
                            <p style={{color:C.textSec,margin:'2px 0 0',fontSize:'11px'}}>Утверждено: {Math.round(approved).toLocaleString('ru-RU')+' ₽'} {pending>0?'· Ждут: '+Math.round(pending).toLocaleString('ru-RU')+' ₽':''}</p>
                          </div>
                          {overLimit&&<span style={{padding:'4px 10px',backgroundColor:C.danger,color:'white',borderRadius:'10px',fontSize:'11px',fontWeight:'700'}}>⚠️ ПРЕВЫШЕН ЛИМИТ</span>}
                        </div>
                        {overLimit&&<p style={{color:C.danger,margin:'8px 0 0',fontSize:'11px',lineHeight:1.4}}>Сумма изменений превысила 10% бюджета. Это не блокировка, но стоит выпустить доп.соглашение или новую редакцию сметы, чтобы КС не задвоились.</p>}
                      </div>);})()}
                      {(()=>{const all=includableEstimateChanges(p.name);if(all.length===0) return null;const activeEsts=activeEstimatesForProject(p,'Заказчик');const unlinked=all.filter(u=>!u.estimateId);if(activeEsts.length===0) return(<div style={{...card,padding:'12px 14px',marginBottom:'14px',backgroundColor:C.warningLight,border:'1.5px solid '+C.warningBorder}}><b style={{color:C.warning,fontSize:'13px'}}>📐 Есть утверждённые изменения, но нет активной сметы заказчика</b><p style={{color:C.textSec,margin:'3px 0 0',fontSize:'11px'}}>Создайте или активируйте смету заказчика, чтобы включить изменения в новую версию без задвоения КС.</p></div>);return(<div style={{...card,padding:'12px 14px',marginBottom:'14px',backgroundColor:C.infoLight,border:'1.5px solid '+C.infoBorder}}>
                        <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap',marginBottom:'8px'}}>
                          <div>
                            <b style={{color:C.info,fontSize:'13px'}}>📐 Включение изменений в новую смету</b>
                            <p style={{color:C.textSec,margin:'2px 0 0',fontSize:'11px'}}>Утверждённые изменения можно перенести в новую активную версию сметы. После этого они не пойдут в КС отдельными строками.</p>
                          </div>
                          <span style={badge(C.info,C.bgWhite,C.infoBorder)}>{all.length+' изм.'}</span>
                        </div>
                        {activeEsts.map(est=>{const rows=estimateChangesForNewEstimate(p,est);if(rows.length===0) return null;const signed=signedEstimateChangeTotal(rows);return(<div key={est.id} style={{padding:'10px',backgroundColor:C.bgWhite,borderRadius:'8px',border:'1px solid '+C.border,marginTop:'8px',display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap'}}>
                          <div style={{minWidth:'220px',flex:1}}>
                            <b style={{color:C.text,fontSize:'12px'}}>{est.name+' · v'+(est.version||'1.0')}</b>
                            <p style={{color:C.textSec,margin:'2px 0 0',fontSize:'11px'}}>{estimatePackage(est)+' · '+rows.length+' изм. · влияние '+(signed>0?'+':'')+Math.round(signed).toLocaleString('ru-RU')+' ₽'}</p>
                          </div>
                          <button onClick={()=>includeChangesInNewEstimate(p,est,rows)} style={{...btnB,padding:'6px 12px',fontSize:'12px'}}><GitBranch size={13}/>В новую смету</button>
                        </div>);})}
                        {activeEsts.length>1&&unlinked.length>0&&<p style={{color:C.warning,margin:'8px 0 0',fontSize:'11px'}}>Есть изменения без привязки к строке сметы: {unlinked.length}. При нескольких активных пакетах их нужно привязать вручную, чтобы не включить не туда.</p>}
                      </div>);})()}
                      {(()=>{const recs=estimateReconciliationsForProject(p.name);if(recs.length===0)return null;const openChecks=recs.reduce((s,r)=>s+Number(r.reviewCount||0),0);return(<div style={{...card,padding:'12px 14px',marginBottom:'14px',backgroundColor:C.bg,border:'1.5px solid '+C.border,display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap'}}>
                        <div>
                          <b style={{color:C.text,fontSize:'13px'}}>Связанные сверки смет: {recs.length}</b>
                          <p style={{color:C.textSec,margin:'2px 0 0',fontSize:'11px'}}>Спорных строк к проверке: {openChecks}. Сверка фиксирует, что вошло в новую смету, а что остаётся отдельной допработой.</p>
                        </div>
                        <button onClick={()=>{setActiveProjectTab('Сверки смет');setActiveTabGroup('work');}} style={{...btnB,padding:'6px 12px',fontSize:'12px'}}><FileText size={13}/>Открыть сверки</button>
                      </div>);})()}
                      {showForm==='unexpected'&&(<div style={{...card,padding:'16px',marginBottom:'16px',backgroundColor:C.bg}}>
                        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginBottom:'8px'}}>
                          <select value={newUnexpected.changeType} onChange={e=>setNewUnexpected({...EMPTY_ESTIMATE_CHANGE,changeType:e.target.value,price:newUnexpected.price})} style={{...inp,marginBottom:0}}>
                            {ESTIMATE_CHANGE_TYPES.map(t=><option key={t}>{t}</option>)}
                          </select>
                          {(()=>{const opts=estimateItemOptionsForProject(p);return(<select value={[newUnexpected.estimateId||'',newUnexpected.sectionName||'',newUnexpected.estimateItemName||''].join('|')} disabled={newUnexpected.changeType!=='Дополнительный объём к строке сметы'||opts.length===0} onChange={e=>{const o=opts.find(x=>[x.estimateId,x.sectionName,x.name].join('|')===e.target.value);if(!o)return;setNewUnexpected({...newUnexpected,estimateId:o.estimateId,sectionName:o.sectionName,estimateItemName:o.name,description:o.name,unit:o.unit,baseQuantity:o.quantity,quantity:'',newRequiredQuantity:'',deltaQuantity:'',price:Math.round(o.pricePerUnit||0)});}} style={{...inp,marginBottom:0}}>
                            <option value=''>{opts.length?'Привязать строку сметы':'Активная смета не найдена'}</option>
                            {opts.map(o=><option key={o.key} value={[o.estimateId,o.sectionName,o.name].join('|')}>{(o.sectionName?o.sectionName+' / ':'')+o.name+' · '+fmtMeasure(o.quantity,o.unit)}</option>)}
                          </select>);})()}
                        </div>
                        {newUnexpected.changeType==='Дополнительный объём к строке сметы'&&(<div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:'8px',marginBottom:'8px',padding:'10px',borderRadius:'8px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border}}>
                          <div><p style={{margin:'0 0 4px',fontSize:'11px',color:C.textSec}}>По активной смете</p><b style={{fontSize:'12px',color:C.text}}>{fmtMeasure(toNum(newUnexpected.baseQuantity),newUnexpected.unit)}</b></div>
                          <input placeholder="Фактически нужно всего" type="number" step="any" inputMode="decimal" value={newUnexpected.newRequiredQuantity?normalizeMeasure(toNum(newUnexpected.newRequiredQuantity),newUnexpected.unit).qty:''} onChange={e=>{const raw=denormalizeMeasure(e.target.value,newUnexpected.unit);const delta=Math.max(0,raw-toNum(newUnexpected.baseQuantity));setNewUnexpected({...newUnexpected,newRequiredQuantity:raw,deltaQuantity:delta,quantity:delta});}} style={{...inp,marginBottom:0}}/>
                          <div><p style={{margin:'0 0 4px',fontSize:'11px',color:C.textSec}}>Доп.объём</p><b style={{fontSize:'12px',color:toNum(newUnexpected.deltaQuantity)>0?C.warning:C.textMuted}}>{fmtMeasure(toNum(newUnexpected.deltaQuantity),newUnexpected.unit)}</b></div>
                        </div>)}
                        <textarea placeholder="Описание изменения *" value={newUnexpected.description} onChange={e=>setNewUnexpected({...newUnexpected,description:e.target.value})} style={{...inp,height:'80px',resize:'vertical'}}/>
                        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:'8px'}}>
                          <input placeholder="Кол-во" type="number" step="any" inputMode="decimal" disabled={newUnexpected.changeType==='Дополнительный объём к строке сметы'} value={newUnexpected.quantity} onChange={e=>setNewUnexpected({...newUnexpected,quantity:e.target.value,deltaQuantity:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <select value={newUnexpected.unit} onChange={e=>setNewUnexpected({...newUnexpected,unit:e.target.value})} style={{...inp,marginBottom:0}}>{UNITS.map(u=><option key={u}>{u}</option>)}</select>
                          <input placeholder="Цена (₽)" type="number" step="any" inputMode="decimal" value={newUnexpected.price} onChange={e=>setNewUnexpected({...newUnexpected,price:e.target.value})} style={{...inp,marginBottom:0}}/>
                        </div>
                        <textarea placeholder="Причина изменения (ошибка объёма, решение заказчика, фактические условия)" value={newUnexpected.reason} onChange={e=>setNewUnexpected({...newUnexpected,reason:e.target.value})} style={{...inp,height:'56px',resize:'vertical',marginTop:'8px'}}/>
                        <div style={{display:'flex',gap:'8px',marginTop:'6px',flexWrap:'wrap'}}>
                          <button disabled={!newUnexpected.description||!!newUnexpected.__aiLoading} onClick={async()=>{
                            setNewUnexpected(prev=>({...prev,__aiLoading:true}));
                            try {
                              // Создаём временную запись чтобы AI имел id
                              const tmpRes = await fetch(API+'/unexpected-works',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({projectName:p.name,description:newUnexpected.description,unit:newUnexpected.unit||'шт',quantity:Number(newUnexpected.quantity||0),changeType:newUnexpected.changeType,price:0,total:0,addedBy:user.name,addedByRole:user.role,status:'_ai_temp_'})});
                              const tmp = await tmpRes.json();
                              const aiRes = await fetch(API+'/unexpected-works/'+tmp.id+'/ai-estimate',{method:'POST'});
                              if(!aiRes.ok){const e=await aiRes.json().catch(()=>({}));throw new Error(e.detail||'Ошибка');}
                              const d = await aiRes.json();
                              // Удаляем временную
                              await fetch(API+'/unexpected-works/'+tmp.id,{method:'DELETE'}).catch(()=>{});
                              setNewUnexpected(prev=>({...prev,price:Math.round(d.pricePerUnit),__aiLoading:false,__aiNote:d.justification}));
                            } catch(e){alert('AI: '+e.message);setNewUnexpected(prev=>({...prev,__aiLoading:false}));}
                          }} style={{...btnB,backgroundColor:'#10b981',color:'white',borderColor:'#059669',fontSize:'12px',padding:'7px 12px',opacity:newUnexpected.__aiLoading?0.6:1}}><Bot size={13}/>{newUnexpected.__aiLoading?'…':'🤖 Оценить через ИИ'}</button>
                          {newUnexpected.__aiNote&&<span style={{fontSize:'11px',color:C.textSec,flex:1,fontStyle:'italic'}}>{newUnexpected.__aiNote}</span>}
                        </div>
                        <div style={{marginTop:'8px'}}>
                          <div style={{display:'flex',gap:'8px',alignItems:'center',marginBottom:'6px'}}>
                            <label style={{...btnB,padding:'8px 12px',fontSize:'12px',cursor:'pointer'}}><Upload size={12}/>📷 Прикрепить фото (можно несколько)<input type='file' accept='image/*' multiple style={{display:'none'}} onChange={async e=>{if(e.target.files&&e.target.files.length>0){const csv=await appendPhotos(newUnexpected.photoUrl,e.target.files,{projectName:p.name,context:'estimate-changes'});setNewUnexpected({...newUnexpected,photoUrl:csv});e.target.value='';}}}/></label>
                            {(newUnexpected.photoUrl||'').split(',').filter(Boolean).length>0&&<span style={{fontSize:'11px',color:C.success,fontWeight:'600'}}>📷 {(newUnexpected.photoUrl||'').split(',').filter(Boolean).length} фото</span>}
                          </div>
                          {(()=>{const urls=(newUnexpected.photoUrl||'').split(',').filter(Boolean);if(urls.length===0) return null;return (<div style={{display:'flex',gap:'4px',flexWrap:'wrap'}}>{urls.map((u,i)=>(<div key={i} style={{position:'relative'}}><img src={fileSrc(u)} alt='' onClick={()=>setShowPhotoModal(fileSrc(u))} style={{width:'60px',height:'60px',objectFit:'cover',borderRadius:'6px',cursor:'pointer',border:'1px solid '+C.border}}/><button type='button' onClick={(ev)=>{ev.preventDefault();ev.stopPropagation();setNewUnexpected({...newUnexpected,photoUrl:urls.filter((_,j)=>j!==i).join(',')});}} style={{position:'absolute',top:'-4px',right:'-4px',background:'rgba(220,38,38,0.9)',color:'white',border:'none',borderRadius:'50%',width:'18px',height:'18px',cursor:'pointer',fontSize:'10px',lineHeight:'1',padding:0}}>×</button></div>))}</div>);})()}
                        </div>
                        <div style={{display:'flex',gap:'8px',marginTop:'10px'}}><button onClick={()=>saveUnexpectedWork(p.name)} style={btnO}><Check size={14}/>Отправить</button><button onClick={()=>setShowForm(false)} style={btnG}><X size={14}/>Отмена</button></div>
                  </div>)}
                      {(()=>{const approvedAll=(unexpectedWorksList||[]).filter(u=>u.projectName===p.name&&isApprovedEstimateChangeStatus(u.status));const ver=approvedAll.length+1;const sumDS=approvedAll.reduce((s,u)=>s+Number(u.total||0),0);if(approvedAll.length===0) return null;return(<div style={{...card,padding:'12px 14px',marginBottom:'14px',backgroundColor:C.infoLight,border:'1.5px solid '+C.infoBorder,display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap'}}>
                        <div>
                          <b style={{color:C.info,fontSize:'13px'}}>📜 Договор подряда — версия v{ver}</b>
                          <p style={{color:C.textSec,margin:'2px 0 0',fontSize:'11px'}}>Утверждённых изменений: {approvedAll.length} на сумму {Math.round(sumDS).toLocaleString('ru-RU')+' ₽'}. Если их не включили в новую смету, они идут в КС отдельными разделами.</p>
                        </div>
                      </div>);})()}
                      {ESTIMATE_CHANGE_VISIBLE_STATUSES.map(status=>{ const items=unexpectedWorksList.filter(u=>u.projectName===p.name&&u.status===status); if(items.length===0) return null; return(<div key={status} style={{marginBottom:'16px'}}><b style={{color:isApprovedEstimateChangeStatus(status)?C.success:status==='Отклонено'?C.danger:status==='Включено в новую смету'?C.info:C.warning,fontSize:'12px',display:'block',marginBottom:'8px'}}>{status==='Ожидает согласования'?'⏳':isApprovedEstimateChangeStatus(status)?'✅':status==='Включено в новую смету'?'📐':'❌'} {status} ({items.length})</b>{items.map((u,idx)=>{const dsNum=isApprovedEstimateChangeStatus(status)?(()=>{const arr=(unexpectedWorksList||[]).filter(x=>x.projectName===p.name&&isApprovedEstimateChangeStatus(x.status));return arr.length-arr.findIndex(x=>x.id===u.id);})():null;return(<div key={u.id} style={{padding:'12px',backgroundColor:C.bg,borderRadius:'8px',marginBottom:'6px',border:'1.5px solid '+C.border}}><div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'8px',flexWrap:'wrap'}}><div style={{flex:1,minWidth:'200px'}}>{dsNum&&<b style={{fontSize:'11px',color:C.info,display:'block'}}>ДС № {dsNum} к договору подряда</b>}<span style={{display:'inline-block',padding:'2px 7px',borderRadius:'9px',backgroundColor:C.bgWhite,border:'1px solid '+C.border,color:C.textSec,fontSize:'10px',marginBottom:'4px'}}>{u.changeType||'Работа вне сметы'}</span><b style={{fontSize:'13px',color:C.text,display:'block'}}>{u.description}</b>{u.estimateItemName&&<p style={{color:C.info,margin:'2px 0',fontSize:'11px'}}>{'Строка сметы: '+(u.sectionName?u.sectionName+' / ':'')+u.estimateItemName}</p>}<p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{fmtMeasure(u.deltaQuantity||u.quantity,u.unit)+(u.price>0?' · '+u.price.toLocaleString()+' ₽/'+u.unit:'')+(u.total>0?' · Итого: '+u.total.toLocaleString()+' ₽':'')}</p><p style={{color:C.textMuted,margin:'0',fontSize:'11px'}}>{'Добавил: '+u.addedBy+(u.approvedAt?' · Утв.: '+u.approvedAt:'')+(u.reason?' · Причина: '+u.reason:'')}</p></div><div style={{display:'flex',gap:'6px',alignItems:'center',flexWrap:'wrap'}}>{isApprovedEstimateChangeStatus(u.status)&&<button onClick={()=>showPreview(buildSupplementaryAgreementContent(u,p),'Доп.соглашение № '+dsNum+' к договору подряда — '+p.name)} style={{...btnB,padding:'4px 8px',fontSize:'11px'}} title='Печать доп.соглашения'><Eye size={11}/>🖨️ ДС</button>}{isLeadership()&&u.status==='Ожидает согласования'&&(<><input placeholder="Цена ₽" type="number" step="any" inputMode="decimal" defaultValue={u.price||''} style={{width:'90px',padding:'4px 8px',border:'1.5px solid '+C.border,borderRadius:'6px',fontSize:'12px'}} onChange={e=>e.target.dataset.price=e.target.value}/><button onClick={e=>{approveUnexpectedWork(u,e.target.previousSibling.dataset.price||u.price||0);}} style={{...btnGr,padding:'4px 8px',fontSize:'11px'}}><Check size={11}/>Утвердить</button><button onClick={async()=>{await fetch(API+'/unexpected-works/'+u.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Отклонено',approvedBy:user.name,approvedAt:new Date().toISOString().split('T')[0]})});await refreshData();}} style={{...btnR,padding:'4px 8px',fontSize:'11px'}}><X size={11}/>Откл.</button></>)}</div></div></div>);})}</div>);})}
                      {unexpectedWorksList.filter(u=>u.projectName===p.name).length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'20px'}}>Изменений к смете нет</p>}
                  </div>)}

                    {activeProjectTab==='Сверки смет'&&renderEstimateReconciliationsPanel(p)}

                    {activeProjectTab==='Расчёт с бригадой'&&(
                      <ProjectBrigadeCalculationTab
                        project={p}
                        brigadeContracts={brigadeContracts}
                        smetaTotal={projectPlanDone(p).plan}
                        showBrigadeForm={showBrigadeForm}
                        setShowBrigadeForm={setShowBrigadeForm}
                        newBrigadeContract={newBrigadeContract}
                        setNewBrigadeContract={setNewBrigadeContract}
                        staff={staff}
                        masterProfiles={masterProfiles}
                        users={users}
                        pricelists={pricelists}
                        setBrigadeContracts={setBrigadeContracts}
                        setSelectedBrigadeContract={setSelectedBrigadeContract}
                        setBrigadeContractItems={setBrigadeContractItems}
                        setBrigadePayments={setBrigadePayments}
                        selectedBrigadeContract={selectedBrigadeContract}
                        brigadeContractItems={brigadeContractItems}
                        brigadePayments={brigadePayments}
                        estimatesList={estimatesList}
                        newBrigadeItem={newBrigadeItem}
                        setNewBrigadeItem={setNewBrigadeItem}
                        UNITS={UNITS}
                        showLeadership={isLeadership()}
                        brigadeCoef={brigadeCoef}
                        setBrigadeCoef={setBrigadeCoef}
                        showFinance={isFinanceRole()}
                        companyRequisites={companyRequisites}
                        companyName={companyName}
                        normalizeMeasure={normalizeMeasure}
                        toNum={toNum}
                        fmtMeasure={fmtMeasure}
                        userName={user.name}
                        setNewBrigadePayment={setNewBrigadePayment}
                        setShowBrigadePayModal={setShowBrigadePayModal}
                        deleteBrigadePayment={deleteBrigadePayment}
                        showPreview={showPreview}
                        uploadPhoto={uploadPhoto}
                        fileSrc={fileSrc}
                        openBrigadeContract={openBrigadeContract}
                        C={C}
                        card={card}
                        inp={inp}
                        btnO={btnO}
                        btnG={btnG}
                        btnB={btnB}
                        btnR={btnR}
                        tbl={tbl}
                        tblH={tblH}
                        tblC={tblC}
                      />
                    )}
                    {activeProjectTab==='Материалы'&&(<div>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                        <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>Материалы объекта</b>
	                        <div style={{display:'flex',gap:'8px'}}>
	                          {(isLeadership()||user.role==='прораб'||user.role==='кладовщик')&&(
                          <button onClick={async()=>{
                            const res=await fetch(API+'/material-transfers?project_name='+encodeURIComponent(p.name));
                            const data=await res.json();
                            setMaterialTransfers(Array.isArray(data)?data:[]);
                            setNewTransfer({
                              materialName: '',
                              quantity: '',
                              unit: 'шт',
                              workPackage: '',
                              toPerson: '',
                              toPersonRole: '',
                              fromLocation: p.name,
                              notes: '',
                              transferDate: new Date().toISOString().split('T')[0],
                            });
                            setShowTransferForm(!showTransferForm);
                          }} style={btnO}><Plus size={14}/>Передать материал</button>)}
                        </div>
                      </div>
                      <ProjectMaterialsControlPanel
                        projectName={p.name}
                        rows={materialReconciliationRows(p.name)}
                        normRows={estimateWorkNormRequirementRows(p.name)}
                        normCtrl={materialNormControlSummaryForProject(p.name)}
                        buildRowsForPackage={(workPackage)=>materialReconciliationRows(p.name, workPackage)}
                        buildNormRowsForPackage={(workPackage)=>estimateWorkNormRequirementRows(p.name, workPackage)}
                        buildNormCtrlForPackage={(workPackage)=>materialNormControlSummaryForProject(p.name, workPackage)}
                        isMobile={isMobile}
                        C={C}
                        card={card}
                        tbl={tbl}
                        tblH={tblH}
                        tblC={tblC}
                        btnB={btnB}
                        badge={badge}
                        fmtMeasure={fmtMeasure}
                        materialControlStatus={materialControlStatus}
                        renderMaterialSupplyAction={renderMaterialSupplyAction}
                        renderMaterialAliasControls={renderMaterialAliasControls}
	                        onCreateSupplyForRows={(rows)=>createBatchSupplyRequestFromMaterialControl(p.name, rows)}
	                        showPreview={showPreview}
	                        buildMaterialRequirementContent={buildMaterialRequirementContent}
	                        onIssueMaterial={(row)=>{
	                          setNewTransfer({
	                            materialName: row.name || '',
	                            quantity: '',
	                            unit: row.unit || 'шт',
	                            workPackage: row.packageName || row.workPackage || '',
	                            toPerson: '',
	                            toPersonRole: '',
	                            fromLocation: p.name,
	                            notes: 'Выдача мастеру из контроля материалов',
	                            transferDate: new Date().toISOString().split('T')[0],
	                          });
	                          setShowTransferForm(true);
	                        }}
	                      />
                      <ProjectMaterialsStockPanel
                        projectName={p.name}
                        materials={materials}
                        warehouseMain={warehouseMain}
                        isMobile={isMobile}
                        C={C}
                        card={card}
                      />

                      <ProjectMaterialsTransferPanel
                        projectName={p.name}
                        showTransferForm={showTransferForm}
                        setShowTransferForm={setShowTransferForm}
                        newTransfer={newTransfer}
                        setNewTransfer={setNewTransfer}
                        materialTransfers={materialTransfers}
                        setMaterialTransfers={setMaterialTransfers}
                        warehouseMain={warehouseMain}
                        setWarehouseMain={setWarehouseMain}
                        materials={materials}
                        setMaterials={setMaterials}
                        visibleProjects={visibleActiveProjects(projects)}
                        supplyRequests={supplyRequests}
                        staff={staff}
                        brigadeContracts={brigadeContracts}
                        workJournal={workJournal}
                        history={history}
                        workPackageOptions={[...new Set([...(activeEstimatesForProject(p,'Заказчик')||[]).map(estimatePackage), ...ESTIMATE_PACKAGES].filter(Boolean))]}
                        user={user}
                        C={C}
                        card={card}
                        inp={inp}
                        tbl={tbl}
                        tblH={tblH}
                        tblC={tblC}
                        btnO={btnO}
                        btnG={btnG}
                        btnGr={btnGr}
                        btnB={btnB}
                        btnR={btnR}
                        normalizeUnit={_normalizeUnit}
                        convertUnits={convertUnits}
                        fmtMeasure={fmtMeasure}
                        showPreview={showPreview}
                        buildM15Content={buildM15Content}
                      />
                  </div>)}
                    {activeProjectTab==='Чат'&&(<div>
                      <b style={{color:C.text,display:'block',marginBottom:'15px'}}>Чат проекта</b>
                      <div style={{backgroundColor:C.bg,borderRadius:'12px',padding:'15px',minHeight:'250px',maxHeight:'350px',overflowY:'auto',marginBottom:'15px',display:'flex',flexDirection:'column',gap:'10px',border:'1.5px solid '+C.border}}>
                        {(()=>{const msgs=projectChatMessages[p.name]||[];if(msgs.length===0) return <p style={{color:C.textMuted,textAlign:'center',margin:'auto',fontSize:'13px'}}>Нет сообщений</p>;return msgs.map(msg=>{const isMe=msg.authorName===user.name;const msgPhoto=fileSrc(msg.photoUrl||msg.photo_url);return(<div key={msg.id} style={{display:'flex',justifyContent:isMe?'flex-end':'flex-start'}}><div style={{maxWidth:'80%',backgroundColor:isMe?C.accent:C.bgWhite,color:isMe?'white':C.text,padding:'10px 14px',borderRadius:isMe?'16px 16px 4px 16px':'16px 16px 16px 4px',border:'1.5px solid '+(isMe?C.accent:C.border)}}>{!isMe&&<div style={{fontSize:'11px',fontWeight:'700',color:roleColor(msg.authorRole),marginBottom:'4px'}}>{msg.authorName}</div>}{msg.text&&<p style={{margin:0,fontSize:'13px'}}>{msg.text}</p>}{msgPhoto&&<img src={msgPhoto} alt='' style={{width:'180px',borderRadius:'8px',display:'block',marginTop:'6px',cursor:'pointer'}} onClick={()=>setShowPhotoModal(msgPhoto)}/>}<div style={{fontSize:'10px',color:isMe?'rgba(255,255,255,0.7)':C.textMuted,marginTop:'4px',textAlign:'right'}}>{msg.createdAt?new Date(msg.createdAt).toLocaleTimeString('ru-RU'):''}</div></div></div>);});})()}
                      </div>
                      <div style={{display:'flex',gap:'8px'}}>
                        <input placeholder="Написать..." value={projectChatMessage} onChange={e=>setProjectChatMessage(e.target.value)} onKeyDown={e=>e.key==='Enter'&&sendProjectChatMessage(p.name,projectChatMessage,'')} style={{...inp,marginBottom:0,flex:1}}/>
                        <button onClick={()=>{if(!projectChatMessages[p.name]) loadProjectChat(p.name);sendProjectChatMessage(p.name,projectChatMessage,'');}} style={btnO}>➤</button>
                      </div>
                      {!projectChatMessages[p.name]&&<button onClick={()=>loadProjectChat(p.name)} style={{...btnG,marginTop:'8px',fontSize:'12px'}}>Загрузить чат</button>}
                  </div>)}

                    {activeProjectTab==='Финансы'&&(<div>
                      {isFinanceRole()&&(
                        <ProjectFinancePanel
                          projectName={p.name}
                          projectPayments={projectPayments}
                          accountablePayments={accountablePayments}
                          ownExpenses={ownExpenses}
                          manualExpenses={manualExpenses}
                          expenseCategories={EXPENSE_CATEGORIES}
                          expByCategory={expByCategory}
                          projectPaymentInAmount={projectPaymentInAmount}
                          projectPaymentSignedAmount={projectPaymentSignedAmount}
                          formatSignedRub={formatSignedRub}
                          user={user}
                          C={C}
                          card={card}
                          btnO={btnO}
                          btnB={btnB}
                          btnG={btnG}
                          btnR={btnR}
                          showBalanceDetails={showBalanceDetails}
                          setShowBalanceDetails={setShowBalanceDetails}
                          setAddExpenseProject={setAddExpenseProject}
                          setNewManualExpense={setNewManualExpense}
                          setShowAccountableForm={setShowAccountableForm}
                          newAccountable={newAccountable}
                          setNewAccountable={setNewAccountable}
                          setShowPhotoModal={setShowPhotoModal}
                          fileSrc={fileSrc}
                          loadAll={loadAll}
                          showProfit={isLeadership()}
                          canAddExpense={isFinanceRole()||user.role==='прораб'}
                        />
                      )}
                  </div>)}
                    {activeProjectTab==='Предписания'&&(
                      <ProjectPrescriptionsPanel
                        projectName={p.name}
                        prescriptionsList={prescriptionsList}
                        showForm={showForm}
                        setShowForm={setShowForm}
                        newPrescription={newPrescription}
                        setNewPrescription={setNewPrescription}
                        savePrescription={savePrescription}
                        loadAll={loadAll}
                        canClose={isProrab()}
                        C={C}
                        card={card}
                        inp={inp}
                        btnO={btnO}
                        btnG={btnG}
                        btnGr={btnGr}
                        badge={badge}
                      />
                    )}

                    {activeProjectTab==='Журнал ТБ'&&(
                      <ProjectSafetyJournalPanel
                        projectName={p.name}
                        tbJournal={tbJournal}
                        showForm={showForm}
                        setShowForm={setShowForm}
                        newTbEntry={newTbEntry}
                        setNewTbEntry={setNewTbEntry}
                        newParticipant={newParticipant}
                        setNewParticipant={setNewParticipant}
                        listSearch={listSearch}
                        setListSearch={setListSearch}
                        tbTypes={TB_TYPES_GOST}
                        tbInstructions={TB_INSTRUCTIONS}
                        saveTbEntry={saveTbEntry}
                        matchSearch={matchSearch}
                        showPreview={showPreview}
                        buildTBContent={buildTBContent}
                        C={C}
                        card={card}
                        inp={inp}
                        btnO={btnO}
                        btnG={btnG}
                        btnB={btnB}
                        btnR={btnR}
                      />
                    )}
                    {activeProjectTab==='АОСР'&&(
                      <ProjectHiddenWorksActsPanel
                        projectName={p.name}
                        hiddenActs={hiddenActs}
                        setEditingAct={setEditingAct}
                        setHiddenActs={setHiddenActs}
                        showPreview={showPreview}
                        buildHiddenActContent={buildHiddenActContent}
                        showDelete={isLeadership()}
                        C={C}
                        card={card}
                        tbl={tbl}
                        tblH={tblH}
                        tblC={tblC}
                        btnB={btnB}
                        btnG={btnG}
                        btnR={btnR}
                      />
                    )}
                  {activeProjectTab==='Главный'&&(<div>
                    <div style={{marginBottom:'15px'}}>
                      <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>📚 Журналы объекта</b>
                      <p style={{color:C.textMuted,fontSize:'12px',margin:'4px 0 0'}}>Клик по карточке откроет соответствующий журнал.</p>
                    </div>
                    {(()=>{
                      const cards=[
                        {tab:'Производство работ',icon:'📖',label:'Производство работ',hint:'Журнал по форме КС-6а',count:workJournal.filter(jw=>jw.project===p.name).length},
                        {tab:'АОСР',icon:'🔒',label:'АОСР',hint:'Печатные формы из сметы и журнала работ',count:hiddenActs.filter(a=>a.projectName===p.name).length},
                        {tab:'Входной контроль',icon:'📦',label:'Входной контроль материалов',hint:'СП 48.13330.2019',count:materialInspections.filter(mi=>mi.projectName===p.name).length},
                        {tab:'Кабельная продукция',icon:'⚡',label:'Кабельная продукция',hint:'СП 76.13330 · ПУЭ',count:cableJournal.filter(c=>c.projectName===p.name).length},
                        {tab:'Журнал ТБ',icon:'🛡️',label:'Техника безопасности',hint:'ГОСТ 12.0.004-2015',count:(tbJournal||[]).filter(e=>e.project===p.name).length},
                        {tab:'Погода',icon:'🌤',label:'Погода',hint:'Метеоусловия по дням',count:(weatherLog||[]).filter(w=>w.projectName===p.name).length},
                        {tab:'Предписания',icon:'⚠️',label:'Предписания',hint:'От технадзора и стройконтроля',count:(prescriptionsList||[]).filter(pr=>pr.projectName===p.name).length},
                        {tab:'Чат',icon:'💬',label:'Чат проекта',hint:'Переписка по объекту',count:0},
                      ];
                      return(<div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(220px,1fr))',gap:'12px'}}>
                        {cards.map(c=>(<div key={c.tab} onClick={()=>setActiveProjectTab(c.tab)} style={{...card,padding:'16px',cursor:'pointer',border:'1.5px solid '+C.border}}><div style={{display:'flex',alignItems:'center',gap:'10px',marginBottom:'6px'}}><span style={{fontSize:'24px'}}>{c.icon}</span><b style={{color:C.text,fontSize:'13px'}}>{c.label}</b></div><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 6px'}}>{c.hint}</p><b style={{color:C.accent,fontSize:'13px'}}>{c.count+' '+(c.count===1?'запись':c.count>=2&&c.count<=4?'записи':'записей')}</b></div>))}
                      </div>);
                    })()}
                  </div>)}
                  {activeProjectTab==='Погода'&&(<div>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                      <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>🌤 Журнал погоды</b>
                      <span style={{fontSize:'11px',color:C.textMuted}}>Метеоусловия по дням строительства</span>
                    </div>
                    {(()=>{
                      const here=(weatherLog||[]).filter(w=>w.projectName===p.name).slice().sort((a,b)=>(b.date||'').localeCompare(a.date||''));
                      if(here.length===0) return(<div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}>Записей о погоде нет. Логируйте погоду из глобального раздела «Погода» — она автоматически появится здесь по этому объекту.</div>);
                      return(<div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(220px,1fr))',gap:'10px'}}>
                        {here.map((w,i)=>(<div key={i} style={{...card,padding:'12px'}}><b style={{color:C.text,fontSize:'13px'}}>{w.date}</b><p style={{color:C.textSec,margin:'4px 0 0',fontSize:'12px'}}>{(w.condition||'—')+' · '+(w.temperature!=null?w.temperature+'°C':'—')+(w.windSpeed?' · ветер '+w.windSpeed+' м/с':'')}</p>{w.notes&&<p style={{color:C.textMuted,fontSize:'11px',margin:'4px 0 0',fontStyle:'italic'}}>{w.notes}</p>}</div>))}
                      </div>);
                    })()}
                  </div>)}
                  {activeProjectTab==='📁 Реестр'&&(
                    <ProjectDocumentsRegistryPanel
                      projectName={p.name}
                      projectDocuments={projectDocuments}
                      newProjectDoc={newProjectDoc}
                      setNewProjectDoc={setNewProjectDoc}
                      showDocForm={showDocForm}
                      setShowDocForm={setShowDocForm}
                      uploadingDoc={uploadingDoc}
                      setUploadingDoc={setUploadingDoc}
                      uploadPhoto={uploadPhoto}
                      fileSrc={fileSrc}
                      loadAll={loadAll}
                      user={user}
                      C={C}
                      card={card}
                      inp={inp}
                      btnO={btnO}
                      btnG={btnG}
                      btnB={btnB}
                      btnR={btnR}
                    />
                  )}
                  {activeProjectTab==='✉️ Переписка'&&(
                    <ProjectLettersPanel
                      projectName={p.name}
                      projectLetters={projectLetters}
                      newLetter={newLetter}
                      setNewLetter={setNewLetter}
                      showLetterForm={showLetterForm}
                      setShowLetterForm={setShowLetterForm}
                      uploadingLetter={uploadingLetter}
                      setUploadingLetter={setUploadingLetter}
                      uploadPhoto={uploadPhoto}
                      fileSrc={fileSrc}
                      loadAll={loadAll}
                      user={user}
                      C={C}
                      card={card}
                      inp={inp}
                      btnO={btnO}
                      btnG={btnG}
                      btnB={btnB}
                      btnR={btnR}
                    />
                  )}
                  {activeProjectTab==='КС-2'&&(<div>
                    <div style={{...card,padding:'24px',textAlign:'center'}}>
                      <div style={{fontSize:'40px',marginBottom:'10px'}}>📄</div>
                      <b style={{color:C.text,fontSize:'15px',display:'block',marginBottom:'6px'}}>Акт о приёмке выполненных работ (КС-2)</b>
                      <p style={{color:C.textMuted,fontSize:'12px',margin:'0 0 16px'}}>Унифицированная форма по ОКУД 0322005. Формируется из выполненных позиций активной сметы. Утверждённые изменения к смете выводятся отдельными разделами без задвоения.</p>
                      <button onClick={()=>showKS2(p)} style={btnO}><Eye size={14}/>🖨 Открыть КС-2</button>
                    </div>
                  </div>)}
                  {activeProjectTab==='КС-3'&&(<div>
                    <div style={{...card,padding:'24px',textAlign:'center'}}>
                      <div style={{fontSize:'40px',marginBottom:'10px'}}>📋</div>
                      <b style={{color:C.text,fontSize:'15px',display:'block',marginBottom:'6px'}}>Справка о стоимости выполненных работ (КС-3)</b>
                      <p style={{color:C.textMuted,fontSize:'12px',margin:'0 0 16px'}}>Унифицированная форма по ОКУД 0322001. Подаётся вместе с КС-2 за отчётный период.</p>
                      <button onClick={()=>showPreview(buildKS3Content(p),'КС-3 — '+p.name)} style={btnO}><Eye size={14}/>🖨 Открыть КС-3</button>
                    </div>
                  </div>)}
                  {activeProjectTab==='Паспорт'&&(<div>
                    <div style={{...card,padding:'24px',textAlign:'center'}}>
                      <div style={{fontSize:'40px',marginBottom:'10px'}}>📘</div>
                      <b style={{color:C.text,fontSize:'15px',display:'block',marginBottom:'6px'}}>Паспорт объекта</b>
                      <p style={{color:C.textMuted,fontSize:'12px',margin:'0 0 16px'}}>Сводная карточка объекта с основными характеристиками и реквизитами.</p>
                      <button onClick={()=>showPreview(buildPassportContent(p),'Паспорт — '+p.name)} style={btnO}><Eye size={14}/>🖨 Открыть Паспорт</button>
                    </div>
                  </div>)}
                  {activeProjectTab==='Акты технадзора'&&(<div>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                      <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>📝 Акты осмотра / обследования от технадзора</b>
                      <span style={{fontSize:'11px',color:C.textMuted}}>Создаются технадзором в его кабинете</span>
                    </div>
                    {(()=>{const here=(supervisorActs||[]).filter(a=>a.projectName===p.name);if(here.length===0) return(<div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}>Технадзор пока не загружал актов осмотра по этому объекту.</div>);return(<div>{here.map(a=>(<div key={a.id} style={{...card,padding:'14px',marginBottom:'8px',borderLeft:'3px solid '+C.accent}}>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px'}}>
                        <div style={{flex:1}}>
                          <b style={{color:C.text,fontSize:'13px'}}>{a.actNumber+' · '+a.actType}</b>
                          <p style={{color:C.textSec,margin:'4px 0',fontSize:'12px'}}>{a.description||'—'}</p>
                          {a.findings&&<p style={{color:C.text,margin:'4px 0',fontSize:'11px'}}><b>Обнаружено:</b> {a.findings}</p>}
                          {a.recommendations&&<p style={{color:C.text,margin:'4px 0',fontSize:'11px'}}><b>Рекомендации:</b> {a.recommendations}</p>}
                          <p style={{color:C.textMuted,margin:'4px 0 0',fontSize:'11px'}}>{a.date+' · '+(a.issuedBy||'—')}</p>
                        </div>
                        {a.photoUrl&&<img src={fileSrc(a.photoUrl)} alt='' onClick={()=>setShowPhotoModal(fileSrc(a.photoUrl))} style={{width:'56px',height:'56px',borderRadius:'6px',objectFit:'cover',cursor:'pointer',flexShrink:0}}/>}
                      </div>
                    </div>))}</div>);})()}
                  </div>)}
                  {activeProjectTab==='Замечания ГСН'&&(<div>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px',flexWrap:'wrap',gap:'8px'}}>
                      <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>🏛 Замечания контролирующих органов</b>
                      <button onClick={()=>setShowForm(showForm==='gsn'?false:'gsn')} style={btnO}><Plus size={14}/>Добавить</button>
                    </div>
                    {showForm==='gsn'&&(<div style={{...card,padding:'16px',marginBottom:'14px',backgroundColor:C.bg}}>
                      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginBottom:'8px'}}>
                        <select value={newInspOrder?.body||'ГСН'} onChange={e=>setNewInspOrder({...(newInspOrder||{}),body:e.target.value})} style={{...inp,marginBottom:0}}>{['ГСН','ГПН','Роспотребнадзор','Ростехнадзор','Прокуратура','Иное'].map(b=><option key={b}>{b}</option>)}</select>
                        <input placeholder='ФИО инспектора' value={newInspOrder?.inspector||''} onChange={e=>setNewInspOrder({...(newInspOrder||{}),inspector:e.target.value})} style={{...inp,marginBottom:0}}/>
                      </div>
                      <textarea placeholder='Описание замечания/нарушения *' value={newInspOrder?.description||''} onChange={e=>setNewInspOrder({...(newInspOrder||{}),description:e.target.value})} style={{...inp,minHeight:'60px',marginBottom:'8px'}}/>
                      <textarea placeholder='Требования / рекомендации' value={newInspOrder?.recommendations||''} onChange={e=>setNewInspOrder({...(newInspOrder||{}),recommendations:e.target.value})} style={{...inp,minHeight:'50px',marginBottom:'8px'}}/>
                      <div style={{display:'flex',gap:'8px',marginBottom:'8px'}}>
                        <input type='date' value={newInspOrder?.date||''} onChange={e=>setNewInspOrder({...(newInspOrder||{}),date:e.target.value})} title='Дата проверки' style={{...inp,marginBottom:0,flex:1}}/>
                        <input type='date' value={newInspOrder?.deadline||''} onChange={e=>setNewInspOrder({...(newInspOrder||{}),deadline:e.target.value})} title='Срок устранения' style={{...inp,marginBottom:0,flex:1}}/>
                      </div>
                      <div style={{display:'flex',gap:'8px'}}>
                        <button onClick={async()=>{
                          if(!(newInspOrder&&newInspOrder.description)){alert('Опишите замечание');return;}
                          await fetch(API+'/inspection-orders',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({projectName:p.name,body:newInspOrder.body||'ГСН',inspector:newInspOrder.inspector||'',description:newInspOrder.description,recommendations:newInspOrder.recommendations||'',deadline:newInspOrder.deadline||null,date:newInspOrder.date||new Date().toISOString().split('T')[0],status:'Открыто'})});
                          await refreshData();
                          setNewInspOrder(null); setShowForm(false);
                        }} style={btnO}><Check size={14}/>Сохранить</button>
                        <button onClick={()=>{setShowForm(false);setNewInspOrder(null);}} style={btnG}>Отмена</button>
                      </div>
                    </div>)}
                    {(()=>{const here=(inspectionOrders||[]).filter(o=>o.projectName===p.name);if(here.length===0) return(<div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}>Замечаний контролирующих органов нет. Если приходила проверка с замечаниями — зафиксируй её здесь, чтобы пакет ИД был полным.</div>);const open=here.filter(o=>o.status!=='Закрыто').length;const closed=here.filter(o=>o.status==='Закрыто').length;return(<div>
                      <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:'10px',marginBottom:'12px'}}>
                        <div style={{...card,padding:'10px',backgroundColor:C.dangerLight}}><p style={{color:C.danger,fontSize:'11px',margin:'0 0 4px'}}>Открытых</p><b style={{color:C.danger,fontSize:'16px'}}>{open}</b></div>
                        <div style={{...card,padding:'10px',backgroundColor:C.successLight}}><p style={{color:C.success,fontSize:'11px',margin:'0 0 4px'}}>Закрытых</p><b style={{color:C.success,fontSize:'16px'}}>{closed}</b></div>
                        <div style={{...card,padding:'10px',backgroundColor:C.bg}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Всего</p><b style={{color:C.text,fontSize:'16px'}}>{here.length}</b></div>
                      </div>
                      {here.map(o=>(<div key={o.id} style={{...card,padding:'14px',marginBottom:'8px',borderLeft:'3px solid '+(o.status==='Закрыто'?C.success:C.danger)}}>
                        <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
                          <div style={{flex:1,minWidth:'200px'}}>
                            <b style={{color:C.text,fontSize:'13px'}}>{o.orderNumber+' · '+(o.body||'ГСН')+(o.inspector?' · '+o.inspector:'')}</b>
                            <p style={{color:C.danger,margin:'4px 0',fontSize:'12px'}}>{o.description||'—'}</p>
                            {o.recommendations&&<p style={{color:C.text,margin:'4px 0',fontSize:'11px'}}><b>Требования:</b> {o.recommendations}</p>}
                            <p style={{color:C.textMuted,margin:'4px 0 0',fontSize:'11px'}}>{(o.date||'')+(o.deadline?' · срок: '+o.deadline:'')}</p>
                            {o.response&&<div style={{marginTop:'8px',padding:'8px 10px',backgroundColor:C.successLight,borderRadius:'6px',fontSize:'11px',color:C.success}}><b>Ответ ({o.responseDate||'—'}):</b> {o.response}</div>}
                          </div>
                          <div style={{display:'flex',gap:'4px',alignItems:'flex-start'}}>
                            <span style={badge(o.status==='Закрыто'?C.success:C.danger,o.status==='Закрыто'?C.successLight:C.dangerLight,o.status==='Закрыто'?C.successBorder:C.dangerBorder)}>{o.status||'Открыто'}</span>
                            {o.status!=='Закрыто'&&<button onClick={async()=>{const resp=prompt('Опишите как устранили / ответ органу:');if(!resp) return;await fetch(API+'/inspection-orders/'+o.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Закрыто',response:resp,responseDate:new Date().toISOString().split('T')[0]})});await refreshData();}} style={{...btnGr,padding:'4px 8px',fontSize:'11px'}}>Закрыть</button>}
                            <button onClick={async()=>{if(!window.confirm('Удалить замечание?')) return;await fetch(API+'/inspection-orders/'+o.id,{method:'DELETE'});await refreshData();}} style={{...btnR,padding:'4px 8px'}}><Trash2 size={11}/></button>
                          </div>
                        </div>
                      </div>))}
                    </div>);})()}
                  </div>)}
                  {activeProjectTab==='Гарантия'&&(<div>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px',flexWrap:'wrap',gap:'8px'}}>
                      <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>🛠 Гарантийный период и дефекты</b>
                      <button onClick={()=>setNewWarrantyDefect({description:'',foundAt:new Date().toISOString().split('T')[0],reportedBy:'',reporterPhone:'',severity:'Средний'})} style={btnO}><Plus size={14}/>Зафиксировать дефект</button>
                    </div>
                    <div style={{...card,padding:'14px',marginBottom:'12px',backgroundColor:C.bg,border:'1.5px solid '+C.border}}>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'8px',flexWrap:'wrap',gap:'6px'}}>
                        <b style={{color:C.text,fontSize:'13px'}}>📋 Условия гарантии</b>
                        {warrantyEditForm?.__projectId!==p.id&&(['директор','зам_директора','бухгалтер','прораб'].includes(user.role))&&(
                          <button onClick={()=>setWarrantyEditForm({__projectId:p.id,warrantyStartDate:p.warrantyStartDate||p.warranty_start_date||'',warrantyEndDate:p.warrantyEndDate||p.warranty_end_date||'',warrantyContact:p.warrantyContact||p.warranty_contact||''})} style={{...btnG,padding:'4px 10px',fontSize:'11px'}}>✏️ Редактировать</button>
                        )}
                      </div>
                      {warrantyEditForm?.__projectId===p.id?(<div>
                        <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:'8px',marginBottom:'8px'}}>
                          <div><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Начало гарантии</p><input type='date' value={warrantyEditForm.warrantyStartDate||''} onChange={e=>setWarrantyEditForm({...warrantyEditForm,warrantyStartDate:e.target.value})} style={{...inp,marginBottom:0}}/></div>
                          <div><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Окончание</p><input type='date' value={warrantyEditForm.warrantyEndDate||''} onChange={e=>setWarrantyEditForm({...warrantyEditForm,warrantyEndDate:e.target.value})} style={{...inp,marginBottom:0}}/></div>
                          <div><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Контакт</p><input type='text' placeholder='ФИО + телефон' value={warrantyEditForm.warrantyContact||''} onChange={e=>setWarrantyEditForm({...warrantyEditForm,warrantyContact:e.target.value})} style={{...inp,marginBottom:0}}/></div>
                        </div>
                        <div style={{display:'flex',gap:'8px'}}>
                          <button onClick={async()=>{
                            await fetch(API+'/projects/'+p.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({warrantyStartDate:warrantyEditForm.warrantyStartDate||null,warrantyEndDate:warrantyEditForm.warrantyEndDate||null,warrantyContact:warrantyEditForm.warrantyContact||''})});
                            await refreshData(); setWarrantyEditForm(null);
                          }} style={btnO}><Check size={14}/>Сохранить</button>
                          <button onClick={()=>setWarrantyEditForm(null)} style={btnG}>Отмена</button>
                        </div>
                      </div>):(<div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:'8px',fontSize:'12px'}}>
                        <div><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Начало гарантии</p><b style={{color:C.text}}>{p.warrantyStartDate||p.warranty_start_date||'не задано'}</b></div>
                        <div><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Окончание</p><b style={{color:C.text}}>{p.warrantyEndDate||p.warranty_end_date||'обычно +1 год'}</b></div>
                        <div><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Контакт по гарантии</p><b style={{color:C.text}}>{p.warrantyContact||p.warranty_contact||(p.foreman||'—')}</b></div>
                      </div>)}
                      <p style={{color:C.textMuted,fontSize:'11px',margin:'8px 0 0',lineHeight:1.4}}>Срок гарантии устанавливается договором подряда (обычно 1-5 лет). В период гарантии устранение дефектов — за счёт подрядчика, если они вызваны его работой.</p>
                    </div>
                    {newWarrantyDefect&&(<div style={{...card,padding:'16px',marginBottom:'14px',backgroundColor:C.bg,border:'1.5px solid '+C.warningBorder}}>
                      <b style={{color:C.text,fontSize:'13px',display:'block',marginBottom:'8px'}}>📝 Новый дефект</b>
                      <textarea placeholder='Описание дефекта *' value={newWarrantyDefect.description} onChange={e=>setNewWarrantyDefect({...newWarrantyDefect,description:e.target.value})} style={{...inp,minHeight:'60px',marginBottom:'8px'}}/>
                      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginBottom:'8px'}}>
                        <input type='date' value={newWarrantyDefect.foundAt} onChange={e=>setNewWarrantyDefect({...newWarrantyDefect,foundAt:e.target.value})} title='Когда обнаружено' style={{...inp,marginBottom:0}}/>
                        <select value={newWarrantyDefect.severity} onChange={e=>setNewWarrantyDefect({...newWarrantyDefect,severity:e.target.value})} style={{...inp,marginBottom:0}}>{['Низкий','Средний','Высокий','Критический'].map(s=><option key={s}>{s}</option>)}</select>
                        <input placeholder='ФИО кто обнаружил' value={newWarrantyDefect.reportedBy} onChange={e=>setNewWarrantyDefect({...newWarrantyDefect,reportedBy:e.target.value})} style={{...inp,marginBottom:0}}/>
                        <input placeholder='Телефон для связи' value={newWarrantyDefect.reporterPhone} onChange={e=>setNewWarrantyDefect({...newWarrantyDefect,reporterPhone:e.target.value})} style={{...inp,marginBottom:0}}/>
                      </div>
                      <div style={{display:'flex',gap:'8px'}}>
                        <button onClick={async()=>{
                          if(!newWarrantyDefect.description){alert('Опишите дефект');return;}
                          await fetch(API+'/warranty-defects',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...newWarrantyDefect,projectName:p.name,status:'Открыт'})});
                          await refreshData(); setNewWarrantyDefect(null);
                        }} style={btnO}><Check size={14}/>Сохранить</button>
                        <button onClick={()=>setNewWarrantyDefect(null)} style={btnG}>Отмена</button>
                      </div>
                    </div>)}
                    {(()=>{const here=warrantyDefects.filter(d=>d.projectName===p.name);if(here.length===0) return(<div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}>Дефектов нет — гарантийных обращений по объекту не было.</div>);const open=here.filter(d=>d.status!=='Закрыт').length;const fixed=here.filter(d=>d.status==='Закрыт').length;return(<div>
                      <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:'10px',marginBottom:'12px'}}>
                        <div style={{...card,padding:'10px',backgroundColor:C.dangerLight}}><p style={{color:C.danger,fontSize:'11px',margin:'0 0 4px'}}>Открытых</p><b style={{color:C.danger,fontSize:'16px'}}>{open}</b></div>
                        <div style={{...card,padding:'10px',backgroundColor:C.successLight}}><p style={{color:C.success,fontSize:'11px',margin:'0 0 4px'}}>Устранено</p><b style={{color:C.success,fontSize:'16px'}}>{fixed}</b></div>
                        <div style={{...card,padding:'10px',backgroundColor:C.bg}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Всего</p><b style={{color:C.text,fontSize:'16px'}}>{here.length}</b></div>
                      </div>
                      {here.map(d=>(<div key={d.id} style={{...card,padding:'14px',marginBottom:'8px',borderLeft:'3px solid '+(d.status==='Закрыт'?C.success:d.severity==='Критический'?C.danger:d.severity==='Высокий'?C.warning:C.textSec)}}>
                        <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
                          <div style={{flex:1,minWidth:'200px'}}>
                            <b style={{color:C.text,fontSize:'13px'}}>{d.description}</b>
                            <p style={{color:C.textSec,margin:'4px 0',fontSize:'11px'}}>Обнаружено: {d.foundAt}{d.reportedBy?' · '+d.reportedBy:''}{d.reporterPhone?' · '+d.reporterPhone:''}</p>
                            <p style={{color:C.textMuted,margin:0,fontSize:'11px'}}>Уровень: <b>{d.severity||'—'}</b></p>
                            {d.fixNotes&&<div style={{marginTop:'6px',padding:'8px 10px',backgroundColor:C.successLight,borderRadius:'6px',fontSize:'11px',color:C.success}}><b>Устранено ({d.fixedAt||'—'}):</b> {d.fixNotes}</div>}
                          </div>
                          <div style={{display:'flex',gap:'4px',alignItems:'flex-start'}}>
                            <span style={badge(d.status==='Закрыт'?C.success:d.severity==='Критический'?C.danger:C.warning,d.status==='Закрыт'?C.successLight:d.severity==='Критический'?C.dangerLight:C.warningLight,d.status==='Закрыт'?C.successBorder:d.severity==='Критический'?C.dangerBorder:C.warningBorder)}>{d.status||'Открыт'}</span>
                            {d.status!=='Закрыт'&&<button onClick={async()=>{const notes=prompt('Опишите как устранили:');if(!notes) return;await fetch(API+'/warranty-defects/'+d.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Закрыт',fixNotes:notes,fixedAt:new Date().toISOString().split('T')[0]})});await refreshData();}} style={{...btnGr,padding:'4px 8px',fontSize:'11px'}}>Устранено</button>}
                            <button onClick={async()=>{if(!window.confirm('Удалить дефект?')) return;await fetch(API+'/warranty-defects/'+d.id,{method:'DELETE'});await refreshData();}} style={{...btnR,padding:'4px 8px'}}><Trash2 size={11}/></button>
                          </div>
                        </div>
                      </div>))}
                    </div>);})()}
                  </div>)}
                  {activeProjectTab==='Входной контроль'&&(<div>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px',flexWrap:'wrap',gap:'10px'}}>
                      <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>📦 Журнал входного контроля материалов</b>
                      <span style={{fontSize:'11px',color:C.textMuted}}>СП 48.13330.2019 · автозаполняется из накладных</span>
                    </div>
                    {(()=>{
                      const here=materialInspections.filter(mi=>mi.projectName===p.name);
	                      if(here.length===0) return(<div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}><div style={{fontSize:'40px',marginBottom:'10px'}}>📦</div><p style={{margin:'0 0 8px',fontWeight:'600'}}>Записей пока нет</p><p style={{fontSize:'12px',margin:0,lineHeight:1.6}}>Записи создаются автоматически при приёмке поставки или оформлении приходной накладной на склад.<br/>Затем здесь прораб/кладовщик дополняет паспорт, сертификат и отметку об осмотре.</p></div>);
                      const cntInsp=here.filter(r=>r.inspected).length;
                      const cntPending=here.length-cntInsp;
                      const cntOk=here.filter(r=>r.visualInspectionResult==='Соответствует').length;
                      return(<div>
                        <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(120px,1fr))',gap:'10px',marginBottom:'14px'}}>
                          <div style={{...card,padding:'12px',backgroundColor:C.bg}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Записей</p><b style={{color:C.text,fontSize:'16px'}}>{here.length}</b></div>
                          <div style={{...card,padding:'12px',backgroundColor:C.warningLight,border:'1.5px solid '+C.warningBorder}}><p style={{color:C.warning,fontSize:'11px',margin:'0 0 4px'}}>Ждут проверки</p><b style={{color:C.warning,fontSize:'16px'}}>{cntPending}</b></div>
                          <div style={{...card,padding:'12px',backgroundColor:C.successLight,border:'1.5px solid '+C.successBorder}}><p style={{color:C.success,fontSize:'11px',margin:'0 0 4px'}}>Проверено</p><b style={{color:C.success,fontSize:'16px'}}>{cntInsp}</b></div>
                          <div style={{...card,padding:'12px',backgroundColor:C.accentLight,border:'1.5px solid '+C.accentBorder}}><p style={{color:C.accent,fontSize:'11px',margin:'0 0 4px'}}>Соответствует</p><b style={{color:C.accent,fontSize:'16px'}}>{cntOk}</b></div>
                        </div>
                        <div style={{display:'flex',justifyContent:'flex-end',marginBottom:'10px'}}>
                          <button onClick={()=>showPreview(buildMaterialInspectionContent(here,p.name,'',''),'Журнал входного контроля — '+p.name)} style={{...btnB,fontSize:'12px',padding:'7px 12px'}}><Eye size={13}/>🖨 Печать журнала</button>
                        </div>
                        <div style={{...card,padding:0,overflow:'auto'}}>
                          <table style={tbl}><thead><tr>
                            <th style={tblH}>Дата приёмки</th>
                            <th style={tblH}>Материал</th>
                            <th style={tblH}>Кол-во</th>
                            <th style={tblH}>Поставщик</th>
                            <th style={tblH}>Партия</th>
                            <th style={tblH}>Сертификат</th>
                            <th style={tblH}>Результат осмотра</th>
                            <th style={tblH}>Статус</th>
                          </tr></thead><tbody>
                            {here.map(mi=>(<tr key={mi.id} style={{cursor:'pointer'}} onClick={()=>setEditingInspection(mi)}>
                              <td style={tblC}>{mi.receivedAt||'—'}</td>
                              <td style={{...tblC,maxWidth:'260px',whiteSpace:'normal'}}>{mi.materialName}{mi.aiFilled?<span title="Заполнено AI" style={{marginLeft:'4px'}}>🤖</span>:null}</td>
                              <td style={tblC}>{(mi.quantity||0)+' '+(mi.unit||'')}</td>
                              <td style={tblC}>{mi.supplier||'—'}</td>
                              <td style={tblC}>{mi.batchNumber||'—'}</td>
                              <td style={tblC}>{mi.certificateNumber||(mi.passportNumber?'паспорт '+mi.passportNumber:'—')}</td>
                              <td style={tblC}>{mi.visualInspectionResult||'—'}</td>
                              <td style={tblC}><span style={{padding:'2px 8px',borderRadius:'10px',fontSize:'11px',fontWeight:'600',backgroundColor:mi.inspected?(mi.visualInspectionResult==='Не соответствует'?C.dangerLight:C.successLight):C.warningLight,color:mi.inspected?(mi.visualInspectionResult==='Не соответствует'?C.danger:C.success):C.warning}}>{mi.inspected?'Проверено':'Ждёт проверки'}</span></td>
                            </tr>))}
                          </tbody></table>
                        </div>
                      </div>);
                    })()}
                  </div>)}
                  {activeProjectTab==='Кабельная продукция'&&(<div>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px',flexWrap:'wrap',gap:'10px'}}>
                      <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>⚡ Журнал кабельной продукции</b>
                      <span style={{fontSize:'11px',color:C.textMuted}}>Электрика · СКС · пожарка · слаботочка</span>
                    </div>
                    {(()=>{
                      const here=cableJournal.filter(cb=>cb.projectName===p.name);
                      if(here.length===0) return(<div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}><div style={{fontSize:'40px',marginBottom:'10px'}}>⚡</div><p style={{margin:'0 0 8px',fontWeight:'600'}}>Записей пока нет</p><p style={{fontSize:'12px',margin:0,lineHeight:1.6}}>Записи создаются автоматически при приходе кабеля (по поставке или накладной).<br/>Система распознаёт силовые ВВГ/NYM/СИП, СКС UTP/FTP/SFTP, слаботочку КСВВ/КСПВ и пожарные КПС/КПСЭ/FRLS.</p></div>);
                      const cntInstalled=here.filter(cb=>cb.installedAt).length;
                      const cntPending=here.length-cntInstalled;
                      const totalLength=here.reduce((s,cb)=>s+Number(cb.lengthReceived||0),0);
                      const typeCounts=here.reduce((acc,cb)=>{const t=cableTypeOf(cb);acc[t]=(acc[t]||0)+1;return acc;},{});
                      return(<div>
                        <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(120px,1fr))',gap:'10px',marginBottom:'14px'}}>
                          <div style={{...card,padding:'12px',backgroundColor:C.bg}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Записей</p><b style={{color:C.text,fontSize:'16px'}}>{here.length}</b></div>
                          <div style={{...card,padding:'12px',backgroundColor:C.warningLight,border:'1.5px solid '+C.warningBorder}}><p style={{color:C.warning,fontSize:'11px',margin:'0 0 4px'}}>Ждут монтажа</p><b style={{color:C.warning,fontSize:'16px'}}>{cntPending}</b></div>
                          <div style={{...card,padding:'12px',backgroundColor:C.successLight,border:'1.5px solid '+C.successBorder}}><p style={{color:C.success,fontSize:'11px',margin:'0 0 4px'}}>Проложено</p><b style={{color:C.success,fontSize:'16px'}}>{cntInstalled}</b></div>
                          <div style={{...card,padding:'12px',backgroundColor:C.accentLight,border:'1.5px solid '+C.accentBorder}}><p style={{color:C.accent,fontSize:'11px',margin:'0 0 4px'}}>Общая длина</p><b style={{color:C.accent,fontSize:'16px'}}>{totalLength.toLocaleString('ru-RU')+' м'}</b></div>
                        </div>
                        <div style={{display:'flex',gap:'6px',flexWrap:'wrap',marginBottom:'10px'}}>
                          {Object.entries(typeCounts).map(([t,n])=><span key={t} style={badge(C.accent,C.accentLight,C.accentBorder)}>{t+': '+n}</span>)}
                        </div>
                        <div style={{display:'flex',justifyContent:'flex-end',marginBottom:'10px'}}>
                          <button onClick={()=>showPreview(buildCableJournalContent(here,p.name,'',''),'Журнал кабельной продукции — '+p.name)} style={{...btnB,fontSize:'12px',padding:'7px 12px'}}><Eye size={13}/>🖨 Печать журнала</button>
                        </div>
                        <div style={{...card,padding:0,overflow:'auto'}}>
                          <table style={tbl}><thead><tr>
                            <th style={tblH}>Дата</th>
                            <th style={tblH}>Тип системы</th>
                            <th style={tblH}>Марка</th>
                            <th style={tblH}>Сечение</th>
                            <th style={tblH}>Жил</th>
                            <th style={tblH}>Длина</th>
                            <th style={tblH}>Барабан №</th>
                            <th style={tblH}>R изол. ДО</th>
                            <th style={tblH}>R изол. ПОСЛЕ</th>
                            <th style={tblH}>Место прокладки</th>
                            <th style={tblH}>Статус</th>
                          </tr></thead><tbody>
                            {here.map(cb=>(<tr key={cb.id} style={{cursor:'pointer'}} onClick={()=>setEditingCable(cb)}>
                              <td style={tblC}>{cb.receivedAt||'—'}</td>
                              <td style={tblC}>{cableTypeOf(cb)}</td>
                              <td style={{...tblC,maxWidth:'220px',whiteSpace:'normal'}}>{cb.cableBrand}{cb.aiFilled?<span title="Заполнено AI" style={{marginLeft:'4px'}}>🤖</span>:null}</td>
                              <td style={tblC}>{cb.crossSection?cb.crossSection+' мм²':'—'}</td>
                              <td style={tblC}>{cb.coresCount||'—'}</td>
                              <td style={tblC}>{(cb.lengthReceived||0)+' м'}</td>
                              <td style={tblC}>{cb.drumNumber||'—'}</td>
                              <td style={tblC}>{cb.insulationBefore?cb.insulationBefore+' МΩ':'—'}</td>
                              <td style={tblC}>{cb.insulationAfter?cb.insulationAfter+' МΩ':'—'}</td>
                              <td style={{...tblC,maxWidth:'220px',whiteSpace:'normal'}}>{cb.installationLocation||'—'}</td>
                              <td style={tblC}><span style={{padding:'2px 8px',borderRadius:'10px',fontSize:'11px',fontWeight:'600',backgroundColor:cb.installedAt?C.successLight:C.warningLight,color:cb.installedAt?C.success:C.warning}}>{cb.installedAt?'Проложен':'На складе'}</span></td>
                            </tr>))}
                          </tbody></table>
                        </div>
                      </div>);
                    })()}
                  </div>)}
                  </div>
                </div>)}
              </div>);
            })}
            {projects.length===0&&<div style={{...card,padding:'40px',textAlign:'center',color:C.textMuted}}><FolderKanban size={48} style={{marginBottom:'15px',opacity:0.3}}/><p>Проектов нет — создайте первый!</p></div>}
          </div>)}
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

          {activePage==='estimates'&&(<div>
            <EstimatesTabsNav
              estimatesTab={estimatesTab}
              setEstimatesTab={setEstimatesTab}
              setActivePage={setActivePage}
              btnO={btnO}
              btnG={btnG}
            />

            {estimatesTab==='list'&&(<div>
              {(()=>{const visibleEstimateList=visibleEstimatesForCurrentUser(estimatesList);const estimateProjectOptions=Array.from(new Set((visibleEstimateList||[]).filter(e=>!isGlobalEstimateTemplate(e)).map(e=>e.projectName||e.project||'Без объекта').filter(Boolean))).sort((a,b)=>a.localeCompare(b,'ru'));const filteredEstimateList=estimateProjectFilter?visibleEstimateList.filter(e=>(e.projectName||e.project||'Без объекта')===estimateProjectFilter):visibleEstimateList;return(<>
              <EstimatesListToolbar
                C={C}
                btnB={btnB}
                btnO={btnO}
                inp={inp}
                showForm={showForm}
                setShowForm={setShowForm}
                setGenerateForm={setGenerateForm}
                setShowGenerateEstimate={setShowGenerateEstimate}
                estimateSearch={estimateSearch}
                setEstimateSearch={setEstimateSearch}
                projectOptions={estimateProjectOptions}
                projectFilter={estimateProjectFilter}
                setProjectFilter={setEstimateProjectFilter}
                showLeadership={isLeadership()}
              />
              <EstimateSearchResults
                C={C}
                card={card}
                btnG={btnG}
                estimateSearch={estimateSearch}
                estimatesList={filteredEstimateList}
                setEstimateSearch={setEstimateSearch}
                setSelectedEstimate={openEstimateDetail}
                fmtMeasure={fmtMeasure}
                estimateItemTotal={estimateItemTotal}
              />
              {showForm&&(<div style={{...card,padding:'20px',marginBottom:'16px'}}>
                <EstimateCreateFormFields
                  inp={inp}
                  projects={projects}
                  newEstimate={newEstimate}
                  setNewEstimate={setNewEstimate}
                  nextEstimateVersionFor={nextEstimateVersionFor}
                  estimatePackages={ESTIMATE_PACKAGES}
                  templates={estimatesList.filter(isGlobalEstimateTemplate)}
                />
                <EstimateCreateActions btnO={btnO} btnG={btnG} onCreate={async()=>{
                  if(!newEstimate.name) return;
                  let sections=[];
                  if(newEstimate.templateId){
                    const tmpl=estimatesList.find(e=>String(e.id)===String(newEstimate.templateId));
                    if(tmpl) sections=enrichEstimateMeasurementBasis((tmpl.sections||[]).map(s=>({...s,id:Date.now()+Math.random(),items:(s.items||[]).map(i=>({...i,id:Date.now()+Math.random()}))})));
                  }
                  const estimateStatus=isLeadership()?(newEstimate.status||'Активная'):'Черновик';
                  const estimatePayload={...newEstimate,status:estimateStatus,sections};
                  const est=await readApiResult(await fetch(API+'/estimates',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(estimatePayload)}));
                  const newEst={...newEstimate,id:est.id,sections,smetaType:newEstimate.smetaType||'Заказчик',workPackage:newEstimate.workPackage||'Основная',status:estimateStatus};
                  const diffBase=activeEstimateFromList((estimatesList||[]).filter(e=>newEst.status==='Активная'&&!isGlobalEstimateTemplate(e)&&sameEstimateGroup(e,newEst)&&e.status==='Активная'));
	                  const nextEstimates=applyEstimateActivationState([...(estimatesList||[]),newEst], newEst);
                  setEstimatesList(nextEstimates);
                  setSelectedEstimate(newEst);
                  setShowForm(false);
                  setNewEstimate({projectId:'',projectName:'',name:'',version:'1.0',smetaType:'Заказчик',workPackage:'Основная',status:'Активная',templateId:''});
                  if(diffBase) {
                    await queueEstimateDiffReviewTask(diffBase,newEst,'Смета создана');
                    await autoReconcileEstimateChanges(diffBase,newEst,'Смета создана');
                    await createEstimateReconciliation(diffBase,newEst,{silent:true});
                  }
                  await queueEstimateQualityReviewTask(newEst, 'Смета создана');
                  await queueEstimateNormReviewTask(newEst, 'Смета создана', nextEstimates);
                }} onCancel={()=>setShowForm(false)} />
              </div>)}
              {selectedEstimate?(<div>
                <EstimateImportValidationBanner
                  C={C}
                  card={card}
                  importValidating={importValidating}
                  importValidationWarnings={importValidationWarnings}
                  setImportValidationWarnings={setImportValidationWarnings}
                  estimateIssues={estimateQualityRows(selectedEstimate)}
                  onJumpToIssue={jumpToEstimateIssue}
                />
                <EstimateSelectedToolbar
                  C={C}
                  badge={badge}
                  btnB={btnB}
                  btnG={btnG}
                  btnGr={btnGr}
                  btnO={btnO}
                  estimateKind={estimateKind}
                  estimatePackage={estimatePackage}
                  estimateStatusView={estimateStatusView}
                  estimateTypeIcon={estimateTypeIcon}
                  estimatesList={estimatesList}
                  hasDiff={Boolean(estimateDiffBaseFor(selectedEstimate))}
                  issueCount={estimateQualityRows(selectedEstimate).length}
                  onAiAnalysis={handleEstimateAiAnalysis}
                  onBack={()=>setSelectedEstimate(null)}
                  onDetectHiddenWorks={handleDetectEstimateHiddenWorks}
                  onExport={handleExportSelectedEstimate}
                  onHistory={handleOpenSelectedEstimateHistory}
                  onNormalize={handleNormalizeSelectedEstimateImport}
                  onOpenChat={handleOpenSelectedEstimateChat}
                  onOpenDistribute={handleOpenEstimateDistribute}
                  onOpenWorkAssignment={handleOpenWorkAssignment}
                  onCreateReconciliation={()=>{const base=estimateDiffBaseFor(selectedEstimate);if(base)createEstimateReconciliation(base,selectedEstimate);}}
                  onPreview={handlePreviewSelectedEstimate}
                  onShowDiff={handleShowSelectedEstimateDiff}
                  onToggleIssuesOnly={()=>estimateQualityRows(selectedEstimate).length&&setShowEstimateIssuesOnly(v=>!v)}
                  onToggleTemplate={handleToggleSelectedEstimateTemplate}
                  sameEstimateGroup={sameEstimateGroup}
                  selectedEstimate={selectedEstimate}
                  setEstimateStatusRemote={setEstimateStatusRemote}
                  showLeadership={['директор','зам_директора'].includes(user?.role)}
	                  showEstimateIssuesOnly={showEstimateIssuesOnly}
	                />
		                {['директор','зам_директора'].includes(user?.role) && (
		                  <EstimateExecutionPricingPanel
		                    priceStats={selectedEstimateExecutionPriceStats()}
		                    executionPriceFillPercent={executionPriceFillPercent}
		                    setExecutionPriceFillPercent={setExecutionPriceFillPercent}
		                    fillSelectedEstimateExecutionPrices={fillSelectedEstimateExecutionPrices}
		                    isMobile={isMobile}
		                  />
		                )}
                <WorkAssignmentStatusPanel
                  selectedEstimate={selectedEstimate}
                  brigadeContracts={brigadeContracts}
                  brigadeContractItems={allBrigadeItems}
                  API={API}
                  loadAll={loadAll}
                  C={C}
                  card={card}
                  btnG={btnG}
                  btnO={btnO}
                  btnR={btnR}
                  isMobile={isMobile}
                  showLeadership={['директор','зам_директора'].includes(user?.role)}
                  onOpenWorkAssignment={handleOpenWorkAssignment}
                />
                <EstimateDuplicateWorkSummaryPanel
                  selectedEstimate={selectedEstimate}
                  userRole={user?.role}
                  isMobile={isMobile}
                  showEstimateWorkSummary={showEstimateWorkSummary}
                  setShowEstimateWorkSummary={setShowEstimateWorkSummary}
                  setShowEstimateIssuesOnly={setShowEstimateIssuesOnly}
                  setMobileExpandedRenderLists={setMobileExpandedRenderLists}
                  buildEstimateWorkSummary={buildEstimateWorkSummary}
                  estimateIssueDomId={estimateIssueDomId}
                />
	                <EstimateAddSectionForm
	                  card={card}
	                  inp={inp}
                  btnO={btnO}
                  newEstimateSection={newEstimateSection}
                  setNewEstimateSection={setNewEstimateSection}
                  onAdd={()=>{if(!newEstimateSection.name) return;const section={id:Date.now(),name:newEstimateSection.name,items:[]};const updated={...selectedEstimate,sections:[...(selectedEstimate.sections||[]),section]};setSelectedEstimate(updated);setEstimatesList(prev=>prev.map(e=>e.id===updated.id?updated:e));setNewEstimateSection({name:''});}}
                />
                <EstimateSectionsEditor
                  selectedEstimate={selectedEstimate}
                  showEstimateIssuesOnly={showEstimateIssuesOnly}
                  mobileExpandedRenderLists={mobileExpandedRenderLists}
                  setMobileExpandedRenderLists={setMobileExpandedRenderLists}
                  isMobile={isMobile}
                  estimateQualityRows={estimateQualityRows}
                  brigadeContracts={brigadeContracts}
                  userRole={user?.role}
                  setSelectedEstimate={setSelectedEstimate}
                  setEstimatesList={setEstimatesList}
                  persistEstimate={persistEstimate}
                  newEstimateItem={newEstimateItem}
                  setNewEstimateItem={setNewEstimateItem}
                  estimateIssueFocusKey={estimateIssueFocusKey}
                />
                <EstimateTotalCard C={C} card={card} total={(selectedEstimate.sections||[]).flatMap(s=>s.items||[]).reduce((sum,i)=>sum+estimateItemTotal(i),0)} />
              </div>):(<div>
                <EstimatesListView
                  C={C}
                  card={card}
                  badge={badge}
                  btnB={btnB}
                  btnG={btnG}
                  btnGr={btnGr}
                  btnO={btnO}
                  btnR={btnR}
                  estimatesList={filteredEstimateList}
                  projectFilter={estimateProjectFilter}
                  showArchivedEstimates={showArchivedEstimates}
                  setShowArchivedEstimates={setShowArchivedEstimates}
                  setSelectedEstimate={openEstimateDetail}
                  isGlobalEstimateTemplate={isGlobalEstimateTemplate}
                  isArchivedEstimate={isArchivedEstimate}
                  estimateGroupKey={estimateGroupKey}
                  activeEstimateFromList={activeEstimateFromList}
                  estimateUpdatedTs={estimateUpdatedTs}
                  estimateTypeIcon={estimateTypeIcon}
                  estimateKind={estimateKind}
                  estimatePackage={estimatePackage}
                  estimateTotal={estimateTotal}
                  estimateStatusView={estimateStatusView}
                  estimateDisplayVersion={estimateDisplayVersion}
                  estimateVersionChain={estimateVersionChain}
                  setEstimateStatusRemote={setEstimateStatusRemote}
                  deleteEstimateRemote={deleteEstimateRemote}
                  showPreview={showPreview}
                  buildEstimateDiffContent={buildEstimateDiffContent}
                  onCreateReconciliation={createEstimateReconciliation}
                  isLeadership={isLeadership}
                  canHardDeleteEstimate={isDirector}
                />
              </div>)}
              </>);})()}
            </div>)}

            {estimatesTab==='import'&&(
              <EstimateImportView
                C={C}
                card={card}
                inp={inp}
                projects={projects}
                newEstimate={newEstimate}
                setNewEstimate={setNewEstimate}
                nextEstimateVersionFor={nextEstimateVersionFor}
                estimatePackages={ESTIMATE_PACKAGES}
                onFileChange={handleEstimateImportFile}
              />
            )}

            {estimatesTab==='norms'&&(<div>
              <MaterialNormsHeader
                C={C}
                badge={badge}
                btnG={btnG}
                btnO={btnO}
                btnState={btnState}
                materialNorms={materialNorms}
                materialNormOverrides={materialNormOverrides}
                materialNormPreviewSuggestions={materialNormPreviewSuggestions}
                setMaterialNormPreviewSuggestions={setMaterialNormPreviewSuggestions}
                materialNormSuggestionLoading={materialNormSuggestionLoading}
                canEditMaterialNorms={canEditMaterialNorms}
                generateMaterialNormSuggestions={generateMaterialNormSuggestions}
                activeSuggestionCount={activeMaterialNormSuggestions().length}
                fallbackNormsCount={WORK_MATERIAL_NORM_RULES.length}
              />
              <MaterialNormNotice
                C={C}
                card={card}
                btnG={btnG}
                materialNormNotice={materialNormNotice}
                setMaterialNormNotice={setMaterialNormNotice}
              />
              <MaterialNormCoverageSection
	                C={C}
	                badge={badge}
	                btnB={btnB}
                btnG={btnG}
                btnGr={btnGr}
                btnO={btnO}
                btnState={btnState}
	                card={card}
	                inp={inp}
	                isMobile={isMobile}
                  projects={projects}
                  materialNormCoverageProject={materialNormCoverageProject}
	                setMaterialNormCoverageProject={setMaterialNormCoverageProject}
                  visibleActiveProjects={visibleActiveProjects}
                  estimateNormCoverageRows={estimateNormCoverageRows}
                  materialNormCoverageDisplayRows={materialNormCoverageDisplayRows}
                  mobileExpandedRenderLists={mobileExpandedRenderLists}
	                setMobileExpandedRenderLists={setMobileExpandedRenderLists}
	                canEditMaterialNorms={canEditMaterialNorms}
                canCreateSupplyRequestFromNorm={canCreateSupplyRequestFromNorm}
                materialNormCanCreateSupply={materialNormCanCreateSupply}
                materialNormSupplyRequestExists={materialNormSupplyRequestExists}
                materialNormCoverageMeta={materialNormCoverageMeta}
                materialNormCoverageComment={materialNormCoverageComment}
                fmtMeasure={fmtMeasure}
                buildMaterialNormCoverageContent={buildMaterialNormCoverageContent}
                showPreview={showPreview}
                exportToExcel={exportToExcel}
                materialNormCoverageExportRows={materialNormCoverageExportRows}
                createBatchSupplyRequestFromNormCoverage={createBatchSupplyRequestFromNormCoverage}
                createSupplyRequestFromNormCoverage={createSupplyRequestFromNormCoverage}
	                addEstimateMaterialFromCoverage={addEstimateMaterialFromCoverage}
	                markEstimateWorkNoMaterialFromCoverage={markEstimateWorkNoMaterialFromCoverage}
	                createMaterialNormCoverageTask={createMaterialNormCoverageTask}
	                saveMaterialNormOverrideFromCoverage={saveMaterialNormOverrideFromCoverage}
	              />
              <MaterialNormSuggestionsPanel
                C={C}
                badge={badge}
                btnB={btnB}
                btnG={btnG}
                btnGr={btnGr}
                btnO={btnO}
                btnR={btnR}
                btnState={btnState}
                card={card}
                inp={inp}
                isMobile={isMobile}
                suggestions={activeMaterialNormSuggestions()}
                materialNormSuggestionLoading={materialNormSuggestionLoading}
                generateMaterialNormSuggestions={generateMaterialNormSuggestions}
                canEditMaterialNorms={canEditMaterialNorms}
                createEstimateFromNormSuggestions={createEstimateFromNormSuggestions}
                acceptMaterialNormSuggestion={acceptMaterialNormSuggestion}
                acceptMaterialNormSuggestionAsOverride={acceptMaterialNormSuggestionAsOverride}
                createTaskFromMaterialNormSuggestion={createTaskFromMaterialNormSuggestion}
                rejectMaterialNormSuggestion={rejectMaterialNormSuggestion}
              />
              <MaterialNormOverridesPanel
                selectedProject={materialNormCoverageProject||visibleActiveProjects(projects||[])[0]?.name||''}
                materialNormOverrides={materialNormOverrides}
                isMobile={isMobile}
              />
              {canEditMaterialNorms()&&(
                <MaterialNormFormPanel
                  editingMaterialNormId={editingMaterialNormId}
                  newMaterialNorm={newMaterialNorm}
                  setNewMaterialNorm={setNewMaterialNorm}
                  saveMaterialNorm={saveMaterialNorm}
                  resetMaterialNormForm={resetMaterialNormForm}
                  isMobile={isMobile}
                />
              )}
              <MaterialNormsListPanel
                materialNormSearch={materialNormSearch}
                setMaterialNormSearch={setMaterialNormSearch}
                materialNorms={materialNorms}
                materialNormsPage={materialNormsPage}
                loadMaterialNormsPage={loadMaterialNormsPage}
                materialNormRuleForCalc={materialNormRuleForCalc}
                materialTitleForNormRule={materialTitleForNormRule}
                canEditMaterialNorms={canEditMaterialNorms}
                editMaterialNorm={editMaterialNorm}
                disableMaterialNorm={disableMaterialNorm}
                isMobile={isMobile}
              />
            </div>)}
          </div>)}

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
