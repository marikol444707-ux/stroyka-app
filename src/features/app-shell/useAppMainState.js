import { useState } from 'react';
import { EMPTY_ESTIMATE_CHANGE } from '../../utils/estimateChangeUtils';
import { readStoredJson } from '../../utils/appRuntimeUtils';
import { emptyStaffForm } from '../../utils/staffUtils';
import {
  createClientForm,
  createProjectForm,
} from '../projects/projectInitialForms';
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
} from '../warehouse/warehouseInitialForms';
import { createLeadForm } from '../crm/crmInitialForms';
import {
  createProjectDocumentForm,
  createProjectLetterForm,
  createSupervisorActForm,
} from '../documents/projectDocumentInitialForms';
import {
  createActPaymentForm,
  createBrigadePaymentForm,
} from '../payments/paymentInitialForms';
import {
  createBrigadeContractForm,
  createBrigadeItemForm,
  createContractForm,
  createInterimActForm,
  createPieceworkForm,
  createStaffDocumentForm,
  createUserForm,
} from '../personnel/personnelInitialForms';
import {
  createPricelistForm,
  createPricelistItemForm,
} from '../pricelists/pricelistInitialForms';
import {
  createRequestForm,
  createSupplierForm,
  createSupplierOfferForm,
} from '../supply/supplyInitialForms';
import {
  createChecklistForm,
  createDoorForm,
  createPrescriptionForm,
  createProjectStageForm,
  createRoomForm,
  createTbEntryForm,
  createWeatherForm,
  createWindowForm,
} from '../project-operations/projectOperationInitialForms';
import {
  createCompanyDocumentForm,
  createCompanyRequisitesForm,
  createProfileForm,
} from '../settings/settingsInitialForms';
import { createMeasurementDocForm } from '../project-measurements/projectMeasurementInitialForms';

const readCustomRoomTypes = () => {
  try {
    return JSON.parse(localStorage.getItem('customRoomTypes') || '[]');
  } catch {
    return [];
  }
};

export function useAppMainState() {
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
  const [materialTransfers, setMaterialTransfers] = useState([]);
  const [showTransferForm, setShowTransferForm] = useState(false);
  const [newTransfer, setNewTransfer] = useState(createMaterialTransferForm);
  const [sverkaModal, setSverkaModal] = useState(null);
  const [projectPayments, setProjectPayments] = useState([]);
  const [accountablePayments, setAccountablePayments] = useState([]);
  const [ownExpenses, setOwnExpenses] = useState([]);
  const [customRoomTypes, setCustomRoomTypes] = useState(readCustomRoomTypes);
  const [manualExpenses, setManualExpenses] = useState([]);
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
  const [listSearch, setListSearch] = useState('');
  const [expandedActDate, setExpandedActDate] = useState(null);
  const [showReimburseModal, setShowReimburseModal] = useState(false);
  const [salaryMonth, setSalaryMonth] = useState(new Date().toISOString().slice(0,7));
  const [salaryEdits, setSalaryEdits] = useState(() => readStoredJson('salaryEdits', {}));
  const [payrollExtras, setPayrollExtras] = useState(() => readStoredJson('payrollExtras', {}));
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

  return {
    accountablePayments, accountingDocProject, accountingTab, activePage, activeProjectTab, activeTabGroup,
    activityLog, actPayments, aiFindings, aiTasks, allBrigadeItems, allBrigadePayments, auditLog, brigadeCoef,
    brigadeContractItems, brigadeContracts, brigadePayments, cableJournal, checklists, checklistItems,
    clients, companyChatMessage, companyDocuments, companyMessages, companyName, companyReqForm,
    companyRequisites, confirmAcceptedQty, confirmComment, confirmingEntry, consentChecked, contracts,
    customRoomTypes, dailyReportDate, draftRoomDoors, draftRoomWindows, editingAct, editingCable,
    editingDoor, editingInspection, editingItem, editingJournal, editingPlItem, editingWindow, estimateDoneDrafts,
    estimateReconciliations, estimateWorkMaterials, estimateWorkParams, estimatesList, estimatesPage,
    estimatesTab, expandedActDate, expandedClient, expandedGroup, expandedMaster, expandedMasterProject,
    expandedPieceworkProject, expandedProject, expandedRoom, expandedStaffId, expenseReports, geoCheckins,
    globalSearch, hiddenActs, history, initialDataLoaded, inlineEditPl, inlineEditPlData, inlineEditPrice,
    inspectionOrders, interimActs, inventory, inviteCodes, invoices, issueToolData, journalFilter, leads,
    listSearch, manualExpenses, masterProfile, masterProfiles, masterProjectId, masterRatings, materialAliases,
    materialInspections, materialNormOverrides, materialNorms, materialTransfers, materials, materialsPage,
    measurementDraftLoadingId, measurementRoomDrafts, mobileExpandedRenderLists, newAct, newBrigadeContract,
    newBrigadeItem, newBrigadePayment, newCatalogItem, newChecklist, newChecklistItem, newClient,
    newCompanyDoc, newContract, newDoor, newExpenseReport, newInspOrder, newInventory, newInvoice,
    newInviteRole, newLead, newLetter, newMeasurementDoc, newMovement, newOffer, newParticipant, newPayment, newPiecework, newPlItem,
    newPrescription, newPricelist, newProject, newProjectDoc, newRequest, newRoom, newStaff, newStaffDoc,
    newStage, newSupplier, newSupplierInvoice, newSupervisorAct, newTbEntry, newTask, newTool, newTransfer,
    newUnexpected, newUser, newWarehouse, newWarrantyDefect, newWeather, newWindow, notifications,
    ownExpenses, payrollExtras, pdConsents, personnelTab, piecework, prescriptionsList, prescriptionPhoto,
    previewContent, previewTitle, priceHints, pricelistItems, pricelists, profileData, projectAiSummaries, projectChatMessage,
    projectChatMessages, projectDocuments, projectLetters, projectMeasurements, projectPayments, projectStages,
    projects, pushEnabled, rejectingEntry, rejectComment, returnToolCondition, roomDoors, roomWindows,
    roomWorks, rooms, salaryEdits, salaryMonth, salaryPayments, searchUser, selectedBrigadeContract,
    selectedChecklist, selectedEstimate, selectedInventory, selectedPricelist, selectedWarehouseProject,
    selectedWorks, showAiAssistant, showArchive, showBrigadeForm, showBrigadePayModal, showCatalogForm,
    showDocForm, showForm, showInvites, showIssueToolModal, showJournalTableModal, showLetterForm,
    showMeasurementForm, showNotifications, showOffers, showPayActModal, showPhotoModal, showPiecework,
    showProfileForm, showQRModal, showReimburseModal, showReturnToolModal, showRoomForm, showSearch,
    showStaffDocForm, showTransferForm, sidebarVisible, sitePublicationDrafts, staff, staffExpandedSections,
    staffProfile, staffProfileLoading, settingsTab, supervisorActPhoto, supervisorActs, supplierCatalog,
    supplierInvoices, supplierOffers, supplierRequisites, suppliers, suppliersTab, supplierTab, supplyClaims,
    supplyDeliveries, supplyHistory, supplyRequests, supplyTemplates, sverkaModal, tbJournal, timesheet,
    toolHistory, tools, toolsTab, unexpectedWorksList, uploadingDoc, uploadingLetter, uploadingMeasurementDoc,
    users, warehouseMain, warehouseMovements, warehouses, warehouseTab, warrantyDefects, warrantyEditForm,
    weatherLog, weatherTab, workJournal, workJournalPage,
    setAccountablePayments, setAccountingDocProject, setAccountingTab, setActivePage, setActiveProjectTab,
    setActiveTabGroup, setActivityLog, setActPayments, setAiFindings, setAiTasks, setAllBrigadeItems, setAllBrigadePayments,
    setAuditLog, setBrigadeCoef, setBrigadeContractItems, setBrigadeContracts, setBrigadePayments,
    setCableJournal, setChecklists, setChecklistItems, setClients, setCompanyChatMessage, setCompanyDocuments,
    setCompanyMessages, setCompanyName, setCompanyReqForm, setCompanyRequisites, setConfirmAcceptedQty,
    setConfirmComment, setConfirmingEntry, setConsentChecked, setContracts, setCustomRoomTypes,
    setDailyReportDate, setDraftRoomDoors, setDraftRoomWindows, setEditingAct, setEditingCable,
    setEditingDoor, setEditingInspection, setEditingItem, setEditingJournal, setEditingPlItem,
    setEditingWindow, setEstimateDoneDrafts, setEstimateReconciliations, setEstimateWorkMaterials,
    setEstimateWorkParams, setEstimatesList, setEstimatesPage, setEstimatesTab, setExpandedActDate,
    setExpandedClient, setExpandedGroup, setExpandedMaster, setExpandedMasterProject,
    setExpandedPieceworkProject, setExpandedProject, setExpandedRoom, setExpandedStaffId,
    setExpenseReports, setGeoCheckins, setGlobalSearch, setHiddenActs, setHistory, setInitialDataLoaded,
    setInlineEditPl, setInlineEditPlData, setInlineEditPrice, setInspectionOrders, setInterimActs,
    setInventory, setInviteCodes, setInvoices, setIssueToolData, setJournalFilter, setLeads, setListSearch,
    setManualExpenses, setMasterProfile, setMasterProfiles, setMasterProjectId, setMasterRatings,
    setMaterialAliases, setMaterialInspections, setMaterialNormOverrides, setMaterialNorms, setMaterialTransfers,
    setMaterials, setMaterialsPage, setMeasurementDraftLoadingId, setMeasurementRoomDrafts,
    setMobileExpandedRenderLists, setNewAct, setNewBrigadeContract, setNewBrigadeItem, setNewBrigadePayment,
    setNewCatalogItem, setNewChecklist, setNewChecklistItem, setNewClient, setNewCompanyDoc,
    setNewContract, setNewDoor, setNewExpenseReport, setNewInspOrder, setNewInventory, setNewInvoice,
    setNewInviteRole, setNewLead, setNewLetter, setNewMeasurementDoc, setNewMovement, setNewOffer, setNewParticipant, setNewPayment,
    setNewPiecework, setNewPlItem, setNewPrescription, setNewPricelist, setNewProject, setNewProjectDoc,
    setNewRequest, setNewRoom, setNewStaff, setNewStaffDoc, setNewStage, setNewSupplier,
    setNewSupplierInvoice, setNewSupervisorAct, setNewTbEntry, setNewTask, setNewTool, setNewTransfer,
    setNewUnexpected, setNewUser, setNewWarehouse, setNewWarrantyDefect, setNewWeather, setNewWindow,
    setNotifications, setOwnExpenses, setPayrollExtras, setPdConsents, setPersonnelTab, setPiecework,
    setPrescriptionsList, setPrescriptionPhoto, setPreviewContent, setPreviewTitle, setPriceHints,
    setPricelistItems, setPricelists, setProfileData, setProjectAiSummaries, setProjectChatMessage, setProjectChatMessages,
    setProjectDocuments, setProjectLetters, setProjectMeasurements, setProjectPayments, setProjectStages,
    setProjects, setPushEnabled, setRejectingEntry, setRejectComment, setReturnToolCondition, setRoomDoors,
    setRoomWindows, setRoomWorks, setRooms, setSalaryEdits, setSalaryMonth, setSalaryPayments,
    setSearchUser, setSelectedBrigadeContract, setSelectedChecklist, setSelectedEstimate, setSelectedInventory,
    setSelectedPricelist, setSelectedWarehouseProject, setSelectedWorks, setShowAiAssistant, setShowArchive,
    setShowBrigadeForm, setShowBrigadePayModal, setShowCatalogForm, setShowDocForm, setShowForm,
    setShowInvites, setShowIssueToolModal, setShowJournalTableModal, setShowLetterForm, setShowMeasurementForm,
    setShowNotifications, setShowOffers, setShowPayActModal, setShowPhotoModal, setShowPiecework,
    setShowProfileForm, setShowQRModal, setShowReimburseModal, setShowReturnToolModal, setShowRoomForm,
    setShowSearch, setShowStaffDocForm, setShowTransferForm, setSidebarVisible, setSignedDocs,
    setSitePublicationDrafts, setStaff, setStaffExpandedSections, setStaffProfile, setStaffProfileLoading,
    setSettingsTab, setSupervisorActPhoto, setSupervisorActs, setSupplierCatalog, setSupplierInvoices,
    setSupplierOffers, setSupplierRequisites, setSuppliers, setSuppliersTab, setSupplierTab, setSupplyClaims,
    setSupplyDeliveries, setSupplyHistory, setSupplyRequests, setSupplyTemplates, setSverkaModal,
    setTbJournal, setTimesheet, setToolHistory, setTools, setToolsTab, setUnexpectedWorksList, setUploadingDoc,
    setUploadingLetter, setUploadingMeasurementDoc, setUsers, setWarehouseMain, setWarehouseMovements,
    setWarehouses, setWarehouseTab, setWarrantyDefects, setWarrantyEditForm, setWeatherLog, setWeatherTab,
    setWorkJournal, setWorkJournalPage,
  };
}
