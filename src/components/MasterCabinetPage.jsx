import React from 'react';
import {
  BarChart3,
  Briefcase,
  ClipboardList,
  Eye,
  FileText,
  LogOut,
  MapPin,
  MessageSquare,
  Package,
  Plus,
  Printer,
  ScrollText,
  ShoppingCart,
} from 'lucide-react';
import CompanyChatPage from './CompanyChatPage';
import AssignmentsPage from './AssignmentsPage';
import ImagePreviewModal from './ImagePreviewModal';
import MasterCablePage from './MasterCablePage';
import MasterDocumentsPage from './MasterDocumentsPage';
import MasterHistoryPage from './MasterHistoryPage';
import MasterMaterialsPage from './MasterMaterialsPage';
import MasterSupplyPage from './MasterSupplyPage';
import MasterWorkJournalPhotoField from './MasterWorkJournalPhotoField';
import MyExpensesPage from './MyExpensesPage';
import NotificationsDropdown from './NotificationsDropdown';
import OwnExpenseFormModal from './OwnExpenseFormModal';
import PhotoAttachmentField from './PhotoAttachmentField';
import PreviewModal from './PreviewModal';
import DocumentRecognitionPanel from './DocumentRecognitionPanel';

const GENERAL_WORK_ROOM_NAME = 'Без помещения';
const MASTER_WORKS_INITIAL_VISIBLE = 35;
const MASTER_WORKS_VISIBLE_STEP = 35;

const estimatePackageName = (estimate) => estimate?.workPackage || estimate?.work_package || 'Основная';
const estimateItemKeyForRow = (estimate, sectionIndex, itemIndex, item) => (
  item?.estimateItemKey ||
  item?.estimate_item_key ||
  item?.workKey ||
  item?.work_key ||
  item?.key ||
  item?.id ||
  (String(estimate?.id || '') + ':' + sectionIndex + ':' + itemIndex)
);
const estimateIsActive = (estimate) => String(estimate?.status || 'Активная').toLowerCase() === 'активная';
const estimateItemIsMaterial = (item) => {
  const itemType = String(item?.type || item?.itemType || item?._type || '').toLowerCase();
  if (itemType.includes('материал') || itemType === 'material' || itemType === 'materials' || itemType === 'resource') return true;
  return Number(item?.priceMaterial || item?.materialPrice || item?.materialTotal || 0) > 0 &&
    Number(item?.priceWork || item?.workPrice || item?.workTotal || 0) <= 0;
};

export default function MasterCabinetPage(props) {
  const [showProjectPicker, setShowProjectPicker] = React.useState(false);
  const [showEstimateChangeForm, setShowEstimateChangeForm] = React.useState(false);
  const [dailyWorkReview, setDailyWorkReview] = React.useState(null);
  const [dailyWorkError, setDailyWorkError] = React.useState('');
  const [dailyWorkSubmitting, setDailyWorkSubmitting] = React.useState(false);
  const [estimateWorkVisibleLimit, setEstimateWorkVisibleLimit] = React.useState(MASTER_WORKS_INITIAL_VISIBLE);
  const [dailyWorkActDraft, setDailyWorkActDraft] = React.useState({
    date: new Date().toISOString().split('T')[0],
    comment: '',
    photoUrl: '',
  });
  const [activeEstimateMaterialKey, setActiveEstimateMaterialKey] = React.useState('');
  const [estimateChangeDraft, setEstimateChangeDraft] = React.useState({
    changeType: 'Работа вне сметы',
    description: '',
    quantity: '',
    unit: 'шт',
    workPackage: '',
    reason: '',
    notes: '',
    photoUrl: '',
  });
  const estimateDraftValueRef = React.useRef({});
  const {
    API,
    C,
    EXPENSE_CATEGORIES,
    PD_CONSENT_TEXT,
    ROLE_LABELS,
    SURFACES,
    UNITS,
    accountablePayments,
    activePage,
    aiTasks = [],
    acceptAiTask,
    addMasterWorks,
    appendPhotos,
    applyMaterialOverNormReason,
    applySupplyTemplate,
    badge,
    brigadeContracts = [],
    brigadeContractItems,
    buildActContent,
    buildCableJournalContent,
    buildContractContent,
    buildHiddenActContent,
    btnB,
    btnG,
    btnGr,
    btnO,
    btnR,
    cableJournal,
    cableTypeOf,
    capMaterialWriteoffQty,
    card,
    checkinGeo,
    closeNotifications,
    companyChatMessage,
    companyMessages,
    consentChecked,
    confirmMaterialReceipt,
    contracts,
    closeAiTask,
    createAiTask,
    createSupplyReq,
    denormalizeMeasure,
    doPrint,
    estimateDoneDrafts,
    estimateWorkKey,
    estimateWorkMaterials,
    estimateWorkParams,
    estimatesList,
    visibleEstimatesForCurrentUser,
    expandedProject,
    fileSrc,
    fmtMeasure,
    getNotifPage,
    handleLogout,
    hiddenActs,
    inp,
    interimActs,
    isMobile,
    isPersonalMaterialRole,
    listSearch,
    loadAll,
    loadPricelistItems,
    markMyNotificationsRead,
    masterProfile,
    masterProfiles,
    masterProjectId,
    matchSearch,
    materialAvailabilityMapForWork,
    materialControlStatus,
    materialHintForProject,
    materialNameKey,
    materialNormForWork,
    materialNormOverrunReason,
    materialNormStatus,
    materialRowsAvailableForWork,
    materialSuggestionsForWork,
    materialWriteoffBlockMessage,
    materialTransfers,
    myNotifications,
    navigateTo,
    newOwnExpense,
    newSupplyReq,
    normalizeMeasure,
    notifications,
    notify,
    openAiTaskAction,
    ownExpenses,
    pdConsents,
    personalMaterialRowsForProject,
    piecework,
    priceHints,
    pricelistItems,
    projects,
    renderMaterialWriteoffStatus,
    renderSupplyPlanningHint,
    renderSupplyRequestOrigin,
    refreshData,
    returnMaterialToProject,
    roleColor,
    roomMeasurementCheck,
    roomMeasurementMessage,
    rooms,
    saveProfile,
    saveSupplyTemplate,
    selectableActiveProjects,
    selectedBrigadeContract,
    selectedWorks,
    setActivePage,
    setCompanyChatMessage,
    setConsentChecked,
    setEstimateDoneDrafts,
    setEstimateWorkMaterials,
    setEstimateWorkParams,
    setExpandedProject,
    setListSearch,
    setMasterProjectId,
    setNewOwnExpense,
    setNewSupplyReq,
    setNotifications,
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
    sendCompanyChatMessage,
    showNotifications,
    showOwnExpenseForm,
    showPhotoModal,
    showPreview,
    showProfileForm,
    showSupplyForm,
    submitAiTaskReport,
    submitEstimateWorkDone,
    supplyCollapsedProjects,
    supplyRequestOrigin,
    supplyRequests,
    supplyTemplates,
    toNum,
    toggleNotifications,
    tools,
    unreadNotifications,
    unexpectedWorksList = [],
    updateEstimateWorkMaterialQty,
    updateSelectedWorkMaterialQty,
    uploadPhoto,
    upsertEstimateWorkMaterial,
    upsertSelectedWorkMaterial,
    user,
    users,
    workJournal,
    profileData,
    previewContent,
    previewTitle,
    setPreviewContent,
    parseSupplyItems,
    fetchPriceHint,
    removeEstimateWorkMaterial,
    removeSelectedWorkMaterial,
    setEditingAct,
    setHiddenActs,
  } = props;

  React.useEffect(() => {
    setEstimateWorkVisibleLimit(MASTER_WORKS_INITIAL_VISIBLE);
    setDailyWorkError('');
  }, [masterProjectId]);

  const safeToNum = typeof toNum === 'function' ? toNum : (value) => {
    if (value === null || value === undefined || value === '') return 0;
    const parsed = Number(String(value).replace(',', '.').replace(/\s+/g, ''));
    return Number.isFinite(parsed) ? parsed : 0;
  };
  const safeNormalizeMeasure = typeof normalizeMeasure === 'function'
    ? normalizeMeasure
    : (qty, unit) => ({ qty: safeToNum(qty), unit: unit || '', factor: 1 });
  const safeDenormalizeMeasure = typeof denormalizeMeasure === 'function'
    ? denormalizeMeasure
    : (qty) => safeToNum(qty);
  const safeFmtMeasure = typeof fmtMeasure === 'function'
    ? fmtMeasure
    : (qty, unit) => String(safeToNum(qty)) + ' ' + (unit || '');
  const needsThicknessParam = typeof props.workNeedsThicknessParam === 'function'
    ? props.workNeedsThicknessParam
    : () => false;
  const fillNormMaterialsForWork = typeof props.autoFillNormMaterialsForWork === 'function'
    ? props.autoFillNormMaterialsForWork
    : (_projectName, _workName, _sectionName, _workQty, _workUnit, currentMaterials = []) => currentMaterials;
  const syncEstimateNormMaterials = (workKey, project, item, displayQty, doneQty, paramsOverride = null) => {
    if (!project) return;
    const nextDelta = Math.max(0, safeDenormalizeMeasure(displayQty, item.unit) - safeToNum(doneQty));
    const currentParams = paramsOverride || estimateWorkParams[workKey] || {};
    setEstimateWorkMaterials(prev => ({
      ...prev,
      [workKey]: fillNormMaterialsForWork(project.name, item.name, item.section, nextDelta, item.unit, prev[workKey] || [], currentParams),
    }));
  };
  const workMaterialRowsCache = new Map();
  const workMaterialAvailabilityCache = new Map();
  const workMaterialSuggestionsCache = new Map();
  const workMaterialCacheKey = (...parts) => parts.map(part => String(part || '').trim().toLowerCase()).join('\n');
  const getWorkMaterialRows = (projectName, workPackage) => {
    const key = workMaterialCacheKey(projectName, workPackage);
    if (!workMaterialRowsCache.has(key)) {
      workMaterialRowsCache.set(
        key,
        typeof materialRowsAvailableForWork === 'function'
          ? materialRowsAvailableForWork(projectName, workPackage)
          : [],
      );
    }
    return workMaterialRowsCache.get(key);
  };
  const getWorkMaterialAvailability = (projectName, workPackage) => {
    const key = workMaterialCacheKey(projectName, workPackage);
    if (!workMaterialAvailabilityCache.has(key)) {
      workMaterialAvailabilityCache.set(
        key,
        typeof materialAvailabilityMapForWork === 'function'
          ? materialAvailabilityMapForWork(projectName, workPackage)
          : {},
      );
    }
    return workMaterialAvailabilityCache.get(key);
  };
  const getWorkMaterialSuggestions = (projectName, workName, sectionName, workPackage) => {
    const key = workMaterialCacheKey(projectName, workName, sectionName, workPackage);
    if (!workMaterialSuggestionsCache.has(key)) {
      workMaterialSuggestionsCache.set(
        key,
        typeof materialSuggestionsForWork === 'function'
          ? materialSuggestionsForWork(projectName, workName, sectionName, workPackage)
          : [],
      );
    }
    return workMaterialSuggestionsCache.get(key);
  };
  const commitEstimateDoneDraft = (workKey, value) => {
    estimateDraftValueRef.current[workKey] = value;
    setEstimateDoneDrafts(prev => {
      if (prev[workKey] === value) return prev;
      return { ...prev, [workKey]: value };
    });
  };
  const userAssignedPackages = React.useMemo(() => (
    Array.isArray(user?.assignedPackages)
      ? user.assignedPackages.filter(Boolean)
      : (Array.isArray(user?.assigned_packages) ? user.assigned_packages.filter(Boolean) : [])
  ), [user?.assignedPackages, user?.assigned_packages]);
  const visibleEstimatesList = React.useMemo(() => (
    typeof visibleEstimatesForCurrentUser === 'function'
      ? visibleEstimatesForCurrentUser(estimatesList || [])
      : (estimatesList || [])
  ), [visibleEstimatesForCurrentUser, estimatesList]);
  const masterEstimateWorkState = React.useMemo(() => {
    if (!masterProjectId) {
      return { projectName: '', myItems: [], hasActiveEstimate: false };
    }
    const projectName = projects.find(project => project.id === Number(masterProjectId))?.name || '';
    const projectEstimates = visibleEstimatesList.filter(estimate => (estimate.projectName || estimate.project_name) === projectName);
    const assignedContractItems = Array.isArray(brigadeContractItems) ? brigadeContractItems : [];
    const contractItemsByPackageAndKey = new Map();
    const contractItemsByPackageAndName = new Map();
    const addContractIndex = (map, key, contractItem) => {
      if (!key) return;
      const list = map.get(key) || [];
      list.push(contractItem);
      map.set(key, list);
    };
    assignedContractItems.forEach(contractItem => {
      const contractPackage = String(contractItem.workPackage || contractItem.work_package || '').trim();
      if (!contractPackage) return;
      const contractKey = String(contractItem.estimateItemKey || contractItem.estimate_item_key || '').trim();
      const contractName = String(contractItem.name || contractItem.description || '').trim().toLowerCase();
      addContractIndex(contractItemsByPackageAndKey, contractPackage + '\n' + contractKey, contractItem);
      addContractIndex(contractItemsByPackageAndName, contractPackage + '\n' + contractName, contractItem);
    });
    const myItems = [];
    projectEstimates.forEach(estimate => (estimate.sections || []).forEach((section, sectionIndex) => (section.items || []).forEach((item, itemIndex) => {
      if (!estimateIsActive(estimate) || estimateItemIsMaterial(item)) return;
      const itemPackage = estimatePackageName(estimate);
      const packageAllowed = userAssignedPackages.length > 0 && userAssignedPackages.includes(itemPackage);
      const namedToMe = item.brigadeName && (item.brigadeName === user?.name || (user?.brigade && item.brigadeName === user.brigade));
      const itemKey = String(estimateItemKeyForRow(estimate, sectionIndex, itemIndex, item) || '').trim();
      const itemName = String(item.name || '').trim().toLowerCase();
      const sectionName = String(section.name || '').trim().toLowerCase();
      const itemUnit = String(item.unit || '').trim().toLowerCase();
      const contractCandidates = [
        ...(itemKey ? (contractItemsByPackageAndKey.get(itemPackage + '\n' + itemKey) || []) : []),
        ...(itemName ? (contractItemsByPackageAndName.get(itemPackage + '\n' + itemName) || []) : []),
      ];
      const seenContractCandidates = new Set();
      const assignedContractItem = contractCandidates.find(contractItem => {
        if (seenContractCandidates.has(contractItem)) return false;
        seenContractCandidates.add(contractItem);
        const contractKey = String(contractItem.estimateItemKey || contractItem.estimate_item_key || '').trim();
        const contractName = String(contractItem.name || contractItem.description || '').trim().toLowerCase();
        const contractUnit = String(contractItem.unit || '').trim().toLowerCase();
        const contractSection = String(contractItem.estimateSection || contractItem.estimate_section || '').trim().toLowerCase();
        const contractProject = String(contractItem.projectName || contractItem.project_name || '').trim();
        const sameProject = !contractProject || contractProject === projectName;
        const sameKey = itemKey && contractKey && contractKey === itemKey;
        const sameName = contractName && contractName === itemName && (!contractSection || !sectionName || contractSection === sectionName) && (!itemUnit || !contractUnit || contractUnit === itemUnit);
        return sameProject && (sameKey || sameName);
      });
      if ((assignedContractItems.length > 0 && assignedContractItem) || (assignedContractItems.length === 0 && (packageAllowed || namedToMe))) {
        myItems.push({
          ...item,
          estId: estimate.id,
          estName: estimate.name,
          workPackage: itemPackage,
          sectionIdx: sectionIndex,
          itemIdx: itemIndex,
          section: section.name,
          quantity: assignedContractItem?.quantity ?? item.quantity,
          doneQuantity: assignedContractItem?.doneQuantity ?? assignedContractItem?.done_quantity ?? item.doneQuantity,
          estimateItemKey: itemKey,
          contractItemId: assignedContractItem?.id || null,
          executionPricePerUnit: assignedContractItem?.priceBrigade || item.executionPricePerUnit,
        });
      }
    })));
    return {
      projectName,
      myItems,
      hasActiveEstimate: projectEstimates.some(estimate => estimateIsActive(estimate)),
    };
  }, [
    brigadeContractItems,
    masterProjectId,
    projects,
    user?.brigade,
    user?.name,
    userAssignedPackages,
    visibleEstimatesList,
  ]);

  const profilePatchFromRecognition = (result) => {
    const extracted = result?.extracted || {};
    const legalText = String(extracted.legalForm || extracted.docType || '').toLowerCase();
    const patch = {
      fullName: extracted.counterpartyName || '',
      passport: extracted.passportData || '',
      inn: extracted.inn || '',
      bankAccount: extracted.bankAccount || '',
      bankName: extracted.bank || '',
      bankBik: extracted.bik || '',
      bankCorr: extracted.corrAccount || '',
      ogrnip: extracted.ogrn || '',
      specialization: extracted.workType || '',
    };
    if (legalText.includes('ип')) patch.contractType = 'ИП';
    if (legalText.includes('самозан')) patch.contractType = 'Самозанятый';
    if (legalText.includes('физ')) patch.contractType = 'ГПХ';
    return Object.fromEntries(Object.entries(patch).filter(([, value]) => value));
  };

  if (showProfileForm) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', backgroundColor: C.bg, padding: '20px' }}>
        <div style={{ ...card, padding: '40px', width: '500px', maxHeight: '90vh', overflowY: 'auto' }}>
          <h2 style={{ textAlign: 'center', color: C.text, marginBottom: '25px', fontSize: '22px', fontWeight: '800' }}>
            {user.role === 'субподрядчик' ? '🔩 Заполните профиль субподрядчика' : '👷 Заполните профиль'}
          </h2>
          <input placeholder="ФИО *" value={profileData.fullName} onChange={e => setProfileData({ ...profileData, fullName: e.target.value })} style={inp} />
          <input placeholder="Паспорт серия и номер" value={profileData.passport} onChange={e => setProfileData({ ...profileData, passport: e.target.value })} style={inp} />
          <input placeholder="ИНН *" value={profileData.inn} onChange={e => setProfileData({ ...profileData, inn: e.target.value })} style={inp} />
          <select value={profileData.contractType} onChange={e => setProfileData({ ...profileData, contractType: e.target.value })} style={inp}>
            <option>ГПХ</option>
            <option>ИП</option>
            <option>Самозанятый</option>
          </select>
          {profileData.contractType === 'ИП' && (
            <input placeholder="ОГРНИП" value={profileData.ogrnip} onChange={e => setProfileData({ ...profileData, ogrnip: e.target.value })} style={inp} />
          )}
          <input placeholder="Номер счёта *" value={profileData.bankAccount} onChange={e => setProfileData({ ...profileData, bankAccount: e.target.value })} style={inp} />
          <input placeholder="Банк" value={profileData.bankName} onChange={e => setProfileData({ ...profileData, bankName: e.target.value })} style={inp} />
          <input placeholder="Телефон" value={profileData.phone} onChange={e => setProfileData({ ...profileData, phone: e.target.value })} style={inp} />
          <select value={profileData.specialization} onChange={e => setProfileData({ ...profileData, specialization: e.target.value })} style={inp}>
            <option value="">Специализация</option>
            {['Каменщик', 'Электрик', 'Сантехник', 'Отделочник', 'Кровельщик', 'Бетонщик', 'Монтажник', 'Плотник', 'Сварщик', 'Разнорабочий', 'Общестроительные работы', 'Электромонтаж', 'Сантехника', 'Кровельные работы'].map(s => (
              <option key={s}>{s}</option>
            ))}
          </select>
          <DocumentRecognitionPanel
            C={C}
            card={card}
            inp={inp}
            btnG={btnG}
            btnO={btnO}
            btnB={btnB}
            uploadPhoto={uploadPhoto}
            fileSrc={fileSrc}
            projectName={profileData.fullName || user.name || 'Профиль исполнителя'}
            context="worker-profile-documents"
            entityType={user.role}
            currentFields={profileData}
            onApplyExtracted={result => setProfileData(prev => ({ ...prev, ...profilePatchFromRecognition(result) }))}
            applyExtractedLabel="Заполнить профиль"
          />
          <div style={{ backgroundColor: C.infoLight, border: '1.5px solid ' + C.infoBorder, padding: '14px', borderRadius: '10px', marginBottom: '15px' }}>
            <b style={{ color: C.info, fontSize: '13px' }}>📄 Согласие на обработку ПД</b>
            <div style={{ display: 'flex', gap: '8px', margin: '10px 0' }}>
              <button onClick={() => showPreview(PD_CONSENT_TEXT({ fullName: profileData.fullName, passport: profileData.passport, inn: profileData.inn }), 'Согласие на ПД')} style={btnB}>
                <Eye size={14} />
                Просмотр
              </button>
              <button onClick={() => doPrint(PD_CONSENT_TEXT({ fullName: profileData.fullName, passport: profileData.passport, inn: profileData.inn }))} style={btnO}>
                <Printer size={14} />
                Распечатать
              </button>
            </div>
            <label style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={consentChecked}
                onChange={e => setConsentChecked(e.target.checked)}
                style={{ marginTop: '3px', width: '18px', height: '18px', accentColor: C.accent }}
              />
              <span style={{ fontSize: '13px', color: C.textSec }}>
                Согласен на обработку персональных данных согласно ФЗ №152-ФЗ <span style={{ color: C.danger }}>*</span>
              </span>
            </label>
          </div>
          <button onClick={saveProfile} style={{ ...btnO, width: '100%', padding: '13px', justifyContent: 'center', fontSize: '15px' }}>
            ✅ Сохранить профиль
          </button>
          <button onClick={() => setShowProfileForm(false)} style={{ width: '100%', padding: '10px', marginTop: '10px', backgroundColor: 'transparent', border: '1.5px solid ' + C.border, borderRadius: '8px', cursor: 'pointer', color: C.textSec }}>
            Позже
          </button>
        </div>
      </div>
    );
  }

  const myWorks = piecework.filter(p => Number(p.staffId) === user.id);
  const myTotal = myWorks.reduce((sum, item) => sum + item.total, 0);
  const myJournal = (workJournal || []).filter(work => Number(work.masterId || work.master_id) === user.id || work.masterName === user.name);
  const myConfirmed = myJournal.filter(work => work.status === 'Подтверждено');
  const myPending = myJournal.filter(work => !work.status || work.status === 'На проверке');
  const myRejected = myJournal.filter(work => work.status === 'Отклонено');
  const workExecutionTotal = (work) => Number(work.executionTotal ?? work.execution_total ?? 0);
  const sumConfirmed = myConfirmed.reduce((sum, work) => sum + workExecutionTotal(work), 0);
  const sumPending = myPending.reduce((sum, work) => sum + workExecutionTotal(work), 0);
  const sumRejected = myRejected.reduce((sum, work) => sum + workExecutionTotal(work), 0);
  const today = new Date().toISOString().split('T')[0];
  const monthAgo = new Date(Date.now() - 30 * 24 * 3600 * 1000).toISOString().split('T')[0];
  const myToday = myConfirmed.filter(work => (work.confirmedAt || work.date || '').split('T')[0] === today);
  const myMonth = myConfirmed.filter(work => (work.confirmedAt || work.date || '') >= monthAgo);
  const sumToday = myToday.reduce((sum, work) => sum + workExecutionTotal(work), 0);
  const sumMonth = myMonth.reduce((sum, work) => sum + workExecutionTotal(work), 0);
  const myMaterialProjectNames = [...new Set(materialTransfers.filter(transfer => transfer.toPerson === user.name).map(transfer => transfer.projectName).filter(Boolean))];
  const myMaterialBalances = myMaterialProjectNames.flatMap(projectName => personalMaterialRowsForProject(projectName, user.name, user.id));
  const myPendingMaterialTransfers = materialTransfers.filter(transfer => transfer.toPerson === user.name && !transfer.signed);
  const myOpenAssignmentsCount = (aiTasks || []).filter(task => {
    if (['Закрыто', 'Отклонено', 'Отменено'].includes(task.status || '')) return false;
    const assignedRole = String(task.assignedRole || '').trim().toLowerCase();
    const assignedTo = String(task.assignedTo || '').trim().toLowerCase();
    const identityMatch = [user.name, user.email, user.id].some(value => String(value || '').trim().toLowerCase() === assignedTo);
    if (assignedTo) return identityMatch;
    return assignedRole && assignedRole === String(user.role || '').trim().toLowerCase();
  }).length;
  const categories = [...new Set(pricelistItems.map(item => item.category))];
  const userNameKey = String(user?.name || '').trim().toLowerCase();
  const myContract = [...(contracts || []), ...(brigadeContracts || [])].find(contract =>
    Number(contract.masterId || contract.master_id || contract.contractorId || contract.contractor_id) === Number(user.id) ||
    String(contract.brigadeName || contract.masterName || '').trim().toLowerCase() === userNameKey
  );
  const myActs = interimActs.filter(act => Number(act.masterId || act.master_id) === Number(user.id) || String(act.masterName || act.master_name || '').trim().toLowerCase() === userNameKey);
  const userAssignedProjectNames = [
    ...(Array.isArray(user?.assignedProjects) ? user.assignedProjects : []),
    ...(Array.isArray(user?.assigned_projects) ? user.assigned_projects : []),
    user?.projectName,
    user?.project_name,
  ].map(name => String(name || '').trim()).filter(Boolean);
  const activeProjectRows = (projects || []).filter(project => !project.archived && project.status !== 'Завершён');
  const parentProjectOptions = typeof selectableActiveProjects === 'function' ? selectableActiveProjects(projects) : activeProjectRows;
  const directAssignedProjectOptions = userAssignedProjectNames.length
    ? activeProjectRows.filter(project => userAssignedProjectNames.includes(project.name))
    : [];
  const masterProjectOptions = directAssignedProjectOptions.length ? directAssignedProjectOptions : parentProjectOptions;
  const selectedMasterProject = masterProjectOptions.find(project => project.id === Number(masterProjectId)) || projects.find(project => project.id === Number(masterProjectId));
  const projectRooms = masterProjectId ? rooms.filter(room => room.project === (selectedMasterProject?.name || '')) : [];
  const selectedProjectHasActiveCustomerEstimate = !!selectedMasterProject && visibleEstimatesList.some(estimate =>
    (estimate.projectName || estimate.project_name) === selectedMasterProject.name &&
    String(estimate.status || 'Активная').toLowerCase() === 'активная' &&
    String(estimate.smetaType || estimate.smeta_type || 'Заказчик') === 'Заказчик'
  );
  const selectMasterProject = async (projectId) => {
    setShowProjectPicker(false);
    setMasterProjectId(projectId);
    setSelectedWorks({});
    const project = masterProjectOptions.find(item => item.id === Number(projectId)) || projects.find(item => item.id === Number(projectId));
    if (project?.pricelistId && typeof loadPricelistItems === 'function') await loadPricelistItems(project.pricelistId);
    else if (typeof loadPricelistItems === 'function') loadPricelistItems(null);
  };
  const estimateChangePackage = estimateChangeDraft.workPackage || (userAssignedPackages.length === 1 ? userAssignedPackages[0] : 'Основная');
  const authJsonHeaders = () => {
    let token = '';
    try {
      token = localStorage.getItem('authToken') || '';
    } catch (_e) {
      token = '';
    }
    return token
      ? { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token }
      : { 'Content-Type': 'application/json' };
  };
  const submitEstimateChangeDraft = async () => {
    if (!selectedMasterProject?.name) {
      alert('Сначала выберите объект');
      return;
    }
    const description = String(estimateChangeDraft.description || '').trim();
    if (!description) {
      alert('Опишите работу или изменение к смете');
      return;
    }
    const quantity = safeToNum(estimateChangeDraft.quantity);
    if (quantity <= 0) {
      alert('Укажите количество больше нуля');
      return;
    }
    const payload = {
      projectName: selectedMasterProject.name,
      description,
      unit: estimateChangeDraft.unit || 'шт',
      quantity,
      changeType: estimateChangeDraft.changeType || 'Работа вне сметы',
      price: 0,
      total: 0,
      addedBy: user.name || '',
      addedByRole: user.role || '',
      status: 'Ожидает согласования',
      workPackage: estimateChangePackage,
      sectionName: estimateChangePackage,
      reason: estimateChangeDraft.reason || '',
      notes: estimateChangeDraft.notes || estimateChangeDraft.reason || '',
      photoUrl: estimateChangeDraft.photoUrl || '',
    };
    const res = await fetch(API + '/unexpected-works', {
      method: 'POST',
      headers: authJsonHeaders(),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const error = await res.json().catch(() => ({}));
      alert('Не удалось отправить изменение: ' + (error.detail || res.status));
      return;
    }
    setEstimateChangeDraft({
      changeType: 'Работа вне сметы',
      description: '',
      quantity: '',
      unit: 'шт',
      workPackage: '',
      reason: '',
      notes: '',
      photoUrl: '',
    });
    setShowEstimateChangeForm(false);
    if (typeof refreshData === 'function') await refreshData();
    notify('Изменение к смете отправлено на согласование: ' + description, 'unexpected');
  };
  const buildDailyEstimateWorkRows = (items = []) => {
    const project = selectedMasterProject || projects.find(projectRow => projectRow.id === Number(masterProjectId));
    const rows = [];
    const errors = [];
    if (!project) {
      return { project: null, rows, total: 0, errors: ['Сначала выберите объект'] };
    }
    for (const item of items) {
      const quantity = safeToNum(item.quantity);
      const done = safeToNum(item.doneQuantity);
      const workKey = estimateWorkKey(item.estId, item.sectionIdx, item.itemIdx);
      const draftDisplay = estimateDraftValueRef.current[workKey] !== undefined
        ? estimateDraftValueRef.current[workKey]
        : (estimateDoneDrafts[workKey] !== undefined ? estimateDoneDrafts[workKey] : '');
      if (draftDisplay === '' || draftDisplay === null || draftDisplay === undefined) continue;
      const delta = safeDenormalizeMeasure(draftDisplay, item.unit);
      const target = done + delta;
      if (delta <= 0) continue;
      if (quantity > 0 && target > quantity) {
        errors.push('По работе "' + item.name + '" план ' + safeFmtMeasure(quantity, item.unit) + '. Нельзя закрыть больше.');
        continue;
      }
      const params = { ...(estimateWorkParams[workKey] || {}) };
      if (!params.roomId && !String(params.roomName || '').trim()) {
        if (projectRooms.length > 0 && typeof isPersonalMaterialRole === 'function' && isPersonalMaterialRole()) {
          errors.push('Выберите помещение для работы "' + item.name + '".');
          continue;
        }
        params.roomName = GENERAL_WORK_ROOM_NAME;
      }
      const roomCheck = params.roomId ? roomMeasurementCheck(project.name, params.roomId, params.surface || 'Стены', delta, item.unit, item.name) : null;
      if (roomCheck?.over > 0) {
        errors.push(roomMeasurementMessage(roomCheck));
        continue;
      }
      const customerPricePerUnit = safeToNum(item.pricePerUnit || item.price || 0) || (safeToNum(item.priceWork || 0) + safeToNum(item.priceMaterial || 0));
      const executionPricePerUnit = safeToNum(item.executionPricePerUnit || item.internalPricePerUnit || item.masterPricePerUnit || item.contractorPricePerUnit || item.executorPricePerUnit);
      if (executionPricePerUnit <= 0) {
        errors.push('По работе "' + item.name + '" не назначена цена исполнителя.');
        continue;
      }
      const currentMaterials = fillNormMaterialsForWork(
        project.name,
        item.name,
        item.section,
        delta,
        item.unit,
        estimateWorkMaterials[workKey] || [],
        { ...params, workPackage: item.workPackage },
      );
      let usedMaterials = currentMaterials
        .filter(material => material.name)
        .map(material => {
          const normQuantity = safeToNum(material.normQuantity);
          const materialQuantity = safeToNum(material.quantity);
          return {
            name: material.name,
            quantity: materialQuantity,
            unit: material.unit || 'шт',
            workPackage: material.workPackage || item.workPackage || '',
            normQuantity,
            normSource: material.normSource || '',
            normRuleId: material.normRuleId || material.ruleId || '',
            normThicknessMm: material.normThicknessMm || material.thicknessMm || '',
            autoNorm: !!material.autoNorm,
            overNorm: normQuantity > 0 && materialQuantity > normQuantity * 1.1,
          };
        });
      for (const material of usedMaterials) {
        if (safeToNum(material.quantity) <= 0) {
          errors.push('Укажите количество материала "' + material.name + '" для работы "' + item.name + '" или снимите материал.');
        }
      }
      const blockMessage = typeof materialWriteoffBlockMessage === 'function'
        ? materialWriteoffBlockMessage(project.name, usedMaterials)
        : '';
      if (blockMessage) {
        errors.push(blockMessage);
        continue;
      }
      if (usedMaterials.some(material => material.overNorm) && typeof materialNormOverrunReason === 'function') {
        const overReason = materialNormOverrunReason(project.name, item.name, usedMaterials);
        if (overReason === null) return { project, rows, total: 0, errors: ['Укажите причину перерасхода материала или снимите перерасход.'] };
        if (overReason && typeof applyMaterialOverNormReason === 'function') {
          usedMaterials = applyMaterialOverNormReason(project.name, usedMaterials, overReason);
        }
      }
      rows.push({
        workKey,
        estId: item.estId,
        sectionIdx: item.sectionIdx,
        itemIdx: item.itemIdx,
        name: item.name,
        section: item.section,
        unit: item.unit,
        done,
        target,
        delta,
        plan: quantity,
        workPackage: item.workPackage,
        estimateItemKey: item.estimateItemKey || workKey,
        contractItemId: item.contractItemId || null,
        customerPricePerUnit,
        customerTotal: delta * customerPricePerUnit,
        executionPricePerUnit,
        executionTotal: delta * executionPricePerUnit,
        executionPriceMode: 'fixed',
        params: {
          ...params,
          roomId: params.roomId ? Number(params.roomId) : null,
          roomName: params.roomName || '',
          surface: params.surface || 'Стены',
          workPackage: item.workPackage || '',
          estimateItemName: item.name,
          estimateItemKey: item.estimateItemKey || workKey,
          contractItemId: item.contractItemId || null,
          customerPricePerUnit,
          customerTotal: delta * customerPricePerUnit,
          executionPricePerUnit,
          executionTotal: delta * executionPricePerUnit,
          executionPriceMode: 'fixed',
          photoUrl: params.photoUrl || '',
        },
        materialsUsed: usedMaterials,
      });
    }
    const total = rows.reduce((sum, row) => sum + safeToNum(row.executionTotal), 0);
    return { project, rows, total, errors };
  };
  const openDailyEstimateWorkReview = (items = []) => {
    const itemsWithDraft = items.filter(item => {
      const workKey = estimateWorkKey(item.estId, item.sectionIdx, item.itemIdx);
      const draftDisplay = estimateDraftValueRef.current[workKey] !== undefined
        ? estimateDraftValueRef.current[workKey]
        : (estimateDoneDrafts[workKey] !== undefined ? estimateDoneDrafts[workKey] : '');
      return draftDisplay !== '' && draftDisplay !== null && draftDisplay !== undefined && safeDenormalizeMeasure(draftDisplay, item.unit) > 0;
    });
    const result = buildDailyEstimateWorkRows(itemsWithDraft);
    if (result.errors.length) {
      setDailyWorkError(result.errors[0]);
      return;
    }
    if (!result.rows.length) {
      setDailyWorkError('Введите выполненный объём хотя бы по одной позиции сметы.');
      return;
    }
    setDailyWorkError('');
    setDailyWorkActDraft(prev => ({
      ...prev,
      date: prev.date || new Date().toISOString().split('T')[0],
      comment: prev.comment || '',
      photoUrl: prev.photoUrl || '',
    }));
    setDailyWorkReview({
      projectName: result.project.name,
      rows: result.rows,
      total: result.total,
      count: result.rows.length,
    });
  };
  const submitDailyEstimateWorkReview = async () => {
    if (!dailyWorkReview?.rows?.length) return;
    const workDate = dailyWorkActDraft.date || new Date().toISOString().split('T')[0];
    const groupComment = String(dailyWorkActDraft.comment || '').trim();
    const groupPhotoUrl = dailyWorkActDraft.photoUrl || '';
    setDailyWorkSubmitting(true);
    try {
      const rowsByEstimate = dailyWorkReview.rows.reduce((map, row) => {
        const key = String(row.estId);
        map[key] = map[key] || [];
        map[key].push(row);
        return map;
      }, {});
      for (const [estimateId, rows] of Object.entries(rowsByEstimate)) {
        const listEstimate = estimatesList.find(estimate => Number(estimate.id) === Number(estimateId));
        if (!listEstimate) throw new Error('Смета не найдена: ' + estimateId);
        const freshRes = await fetch(API + '/estimates/' + encodeURIComponent(estimateId), {
          headers: authJsonHeaders(),
        });
        if (!freshRes.ok) {
          const error = await freshRes.json().catch(() => ({}));
          throw new Error(error.detail || ('Не удалось обновить смету перед отправкой: HTTP ' + freshRes.status));
        }
        const freshEstimate = await freshRes.json();
        const est = { ...listEstimate, ...freshEstimate };
        const rowByKey = new Map();
        const rowByName = new Map();
        rows.forEach(row => {
          const rowKey = String(row.estimateItemKey || '').trim();
          if (rowKey) rowByKey.set(rowKey, row);
          rowByName.set(
            [String(row.section || '').trim().toLowerCase(), String(row.name || '').trim().toLowerCase()].join('|'),
            row,
          );
        });
        const matchedRows = new Set();
        const workJournalMaterials = {};
        const workJournalParams = {};
        const newSections = (est.sections || []).map((section, sectionIdx) => ({
          ...section,
          items: (section.items || []).map((item, itemIdx) => {
            const itemKey = String(estimateItemKeyForRow(est, sectionIdx, itemIdx, item) || '').trim();
            const nameKey = [
              String(section.name || '').trim().toLowerCase(),
              String(item.name || '').trim().toLowerCase(),
            ].join('|');
            const row = (itemKey && rowByKey.get(itemKey)) || rowByName.get(nameKey) || null;
            if (!row) return item;
            matchedRows.add(row.workKey);
            const freshDone = safeToNum(item.doneQuantity);
            const freshPlan = safeToNum(item.quantity);
            const nextDone = freshDone + safeToNum(row.delta);
            if (freshPlan > 0 && nextDone > freshPlan + 0.000001) {
              throw new Error(
                'По работе "' + row.name + '" уже закрыто ' + safeFmtMeasure(freshDone, row.unit) +
                ', осталось ' + safeFmtMeasure(Math.max(0, freshPlan - freshDone), row.unit) + '.',
              );
            }
            const freshWorkKey = estimateWorkKey(est.id, sectionIdx, itemIdx);
            const nameParamKey = [String(section.name || ''), String(item.name || '')].join('|');
            const comment = groupComment
              ? 'Дневной акт за ' + workDate + '. ' + groupComment
              : 'Дневной акт за ' + workDate;
            const journalPayload = {
              ...row.params,
              estimateItemKey: itemKey || row.estimateItemKey || freshWorkKey,
              date: workDate,
              comment,
              photoUrl: row.params.photoUrl || groupPhotoUrl || '',
            };
            const materialPayload = row.materialsUsed;
            [freshWorkKey, itemKey, nameParamKey].filter(Boolean).forEach(key => {
              workJournalMaterials[key] = materialPayload;
              workJournalParams[key] = journalPayload;
            });
            return { ...item, doneQuantity: nextDone };
          }),
        }));
        const missingRows = rows.filter(row => !matchedRows.has(row.workKey));
        if (missingRows.length) {
          throw new Error('Не удалось найти в свежей смете строку: ' + missingRows[0].name);
        }
        const res = await fetch(API + '/estimates/' + est.id, {
          method: 'PUT',
          headers: authJsonHeaders(),
          body: JSON.stringify({
            ...est,
            sections: newSections,
            _workJournalMaterials: workJournalMaterials,
            _workJournalParams: workJournalParams,
          }),
        });
        if (!res.ok) {
          const error = await res.json().catch(() => ({}));
          throw new Error(error.detail || ('HTTP ' + res.status));
        }
      }
      const submittedKeys = dailyWorkReview.rows.map(row => row.workKey);
      setEstimateDoneDrafts(prev => {
        const next = { ...prev };
        submittedKeys.forEach(key => { delete next[key]; delete estimateDraftValueRef.current[key]; });
        return next;
      });
      setEstimateWorkMaterials(prev => {
        const next = { ...prev };
        submittedKeys.forEach(key => { delete next[key]; });
        return next;
      });
      setEstimateWorkParams(prev => {
        const next = { ...prev };
        submittedKeys.forEach(key => { delete next[key]; });
        return next;
      });
      setActiveEstimateMaterialKey(prev => submittedKeys.includes(prev) ? '' : prev);
      setDailyWorkReview(null);
      setDailyWorkActDraft({ date: new Date().toISOString().split('T')[0], comment: '', photoUrl: '' });
      if (typeof refreshData === 'function') await refreshData();
      notify('Дневной пакет работ отправлен на проверку: ' + dailyWorkReview.count + ' поз.', 'work');
    } catch (error) {
      setDailyWorkError('Не удалось отправить дневной пакет: ' + (error?.message || error));
    } finally {
      setDailyWorkSubmitting(false);
    }
  };
  const myTools = tools.filter(tool => tool.masterName === (masterProfile?.fullName || user.name) && tool.status.includes('У мастера'));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', backgroundColor: C.bg }}>
      <ImagePreviewModal src={showPhotoModal} onClose={() => setShowPhotoModal(null)} />
      {previewContent && <PreviewModal content={previewContent} title={previewTitle} onClose={() => setPreviewContent(null)} onPrint={doPrint} />}
      <OwnExpenseFormModal
        showOwnExpenseForm={showOwnExpenseForm}
        setShowOwnExpenseForm={setShowOwnExpenseForm}
        C={C}
        card={card}
        inp={inp}
        btnO={btnO}
        btnG={btnG}
        projectOptions={masterProjectOptions}
        expenseCategories={EXPENSE_CATEGORIES}
        newOwnExpense={newOwnExpense}
        setNewOwnExpense={setNewOwnExpense}
        appendPhotos={appendPhotos}
        fileSrc={fileSrc}
        API={API}
        user={user}
        loadAll={loadAll}
        notify={notify}
        showInfo
        validationAlert
      />
      {dailyWorkReview && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 1200, backgroundColor: 'rgba(15,23,42,.62)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '14px' }}>
          <div style={{ ...card, width: '720px', maxWidth: '100%', maxHeight: '92vh', overflowY: 'auto', padding: '18px', backgroundColor: C.bgWhite }}>
	            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', marginBottom: '14px' }}>
	              <div>
	                <h3 style={{ margin: 0, color: C.text, fontSize: '18px', fontWeight: 800 }}>Работы за день</h3>
	                <p style={{ margin: '4px 0 0', color: C.textSec, fontSize: '12px' }}>{dailyWorkReview.projectName + ' · ' + dailyWorkReview.count + ' поз.'}</p>
	              </div>
	              <button onClick={() => setDailyWorkReview(null)} disabled={dailyWorkSubmitting} style={{ ...btnG, padding: '6px 10px' }}>Закрыть</button>
	            </div>
	            {dailyWorkError && (
	              <div style={{ padding: '10px 12px', borderRadius: '10px', backgroundColor: C.dangerLight, border: '1.5px solid ' + C.dangerBorder, color: C.danger, fontSize: '12px', fontWeight: 700, marginBottom: '12px' }}>
	                {dailyWorkError}
	              </div>
	            )}
	            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(140px,.35fr)', gap: '10px', alignItems: 'start', marginBottom: '12px' }}>
              <div style={{ padding: '12px', borderRadius: '10px', backgroundColor: C.accentLight, border: '1.5px solid ' + C.accentBorder }}>
                <b style={{ display: 'block', color: C.accent, fontSize: '12px', marginBottom: '4px' }}>Сумма к проверке</b>
                <span style={{ color: C.text, fontSize: '24px', fontWeight: 800 }}>{Math.round(dailyWorkReview.total).toLocaleString('ru-RU') + ' ₽'}</span>
              </div>
              <input
                type="date"
                value={dailyWorkActDraft.date}
                onChange={e => setDailyWorkActDraft(prev => ({ ...prev, date: e.target.value }))}
                style={{ ...inp, marginBottom: 0 }}
              />
            </div>
            <div style={{ display: 'grid', gap: '8px', marginBottom: '12px' }}>
              {dailyWorkReview.rows.map(row => (
                <div key={row.workKey} style={{ padding: '10px', borderRadius: '10px', backgroundColor: C.bg, border: '1px solid ' + C.border }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'flex-start' }}>
                    <div style={{ minWidth: 0 }}>
                      <b style={{ color: C.text, fontSize: '13px' }}>{row.name}</b>
                      <p style={{ margin: '3px 0 0', color: C.textSec, fontSize: '11px' }}>{row.section + ' · ' + row.workPackage}</p>
                    </div>
                    <b style={{ color: C.success, fontSize: '13px', whiteSpace: 'nowrap' }}>{Math.round(row.executionTotal).toLocaleString('ru-RU') + ' ₽'}</b>
                  </div>
                  <p style={{ margin: '6px 0 0', color: C.textSec, fontSize: '12px' }}>
                    {'Было ' + safeFmtMeasure(row.done, row.unit) + ' · стало ' + safeFmtMeasure(row.target, row.unit) + ' · за день +' + safeFmtMeasure(row.delta, row.unit)}
                  </p>
                  {(row.params.roomName || row.params.roomId || row.params.photoUrl || row.materialsUsed.length > 0) && (
                    <p style={{ margin: '4px 0 0', color: C.textMuted, fontSize: '11px' }}>
                      {(row.params.roomName ? 'Помещение: ' + row.params.roomName + '. ' : '') +
                        (row.materialsUsed.length > 0 ? 'Материалы: ' + row.materialsUsed.length + ' поз. ' : '') +
                        (row.params.photoUrl ? 'Есть фото по строке.' : '')}
                    </p>
                  )}
                </div>
              ))}
            </div>
            <PhotoAttachmentField
              C={C}
              btnG={btnG}
              value={dailyWorkActDraft.photoUrl}
              onChange={photoUrl => setDailyWorkActDraft(prev => ({ ...prev, photoUrl }))}
              appendPhotos={appendPhotos}
              fileSrc={fileSrc}
              setShowPhotoModal={setShowPhotoModal}
              projectName={dailyWorkReview.projectName || ''}
              context="daily-work-act"
              title="Общий фотоотчет"
            />
            <textarea
              placeholder="Комментарий прорабу или директору"
              value={dailyWorkActDraft.comment}
              onChange={e => setDailyWorkActDraft(prev => ({ ...prev, comment: e.target.value }))}
              style={{ ...inp, minHeight: '82px', marginTop: '10px' }}
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', flexWrap: 'wrap' }}>
              <button onClick={() => setDailyWorkReview(null)} disabled={dailyWorkSubmitting} style={btnG}>Отмена</button>
              <button onClick={submitDailyEstimateWorkReview} disabled={dailyWorkSubmitting} style={{ ...btnO, opacity: dailyWorkSubmitting ? 0.7 : 1 }}>
                {dailyWorkSubmitting ? 'Отправляем...' : 'Отправить на проверку'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div style={{ flex: 1, padding: '15px', paddingBottom: isMobile ? '90px' : '15px', overflowY: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', gap: '8px' }}>
          <div>
            <h2 style={{ margin: 0, color: C.text, fontSize: '20px', fontWeight: '800' }}>СтройКа</h2>
            <p style={{ margin: 0, color: C.textSec, fontSize: '12px' }}>{user.name + ' — ' + (ROLE_LABELS[user.role] || user.role)}</p>
          </div>
          <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
            <NotificationsDropdown
              showNotifications={showNotifications}
              toggleNotifications={toggleNotifications}
              unreadNotifications={unreadNotifications}
              C={C}
              btnG={btnG}
              btnO={btnO}
              myNotifications={myNotifications}
              notifications={notifications}
              markMyNotificationsRead={markMyNotificationsRead}
              closeNotifications={closeNotifications}
              navigateTo={navigateTo}
              getNotifPage={getNotifPage}
              setShowNotifications={setShowNotifications}
              setNotifications={setNotifications}
              user={user}
              setUser={setUser}
              API={API}
              dropdownWidth="300px"
              bellSize={16}
              markAllText="Все прочитано"
              emptyStyle={{ fontSize: '12px' }}
            />
            <button onClick={checkinGeo} style={{ ...btnGr, padding: '8px 14px', fontSize: '12px' }}>
              <MapPin size={14} />
              Отметиться
            </button>
          </div>
        </div>

        {activePage === 'works' && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', gap: '10px', flexWrap: 'wrap' }}>
              <h3 style={{ color: C.text, margin: 0, fontSize: '18px', fontWeight: '700' }}>Мои работы</h3>
              {myTotal > 0 ? (
                <div style={{ background: 'linear-gradient(135deg,#f97316,#ea580c)', padding: '8px 18px', borderRadius: '10px', fontWeight: '700', fontSize: '14px', color: 'white' }} title="Сумма по принятым сдельным работам за всё время">
                  💰 Заработано: {myTotal.toLocaleString() + ' ₽'}
                </div>
              ) : (
                <div style={{ padding: '8px 14px', borderRadius: '10px', fontSize: '12px', color: C.textSec, backgroundColor: C.bg, border: '1.5px dashed ' + C.border }} title="Здесь будет сумма ваших принятых работ когда прораб их подтвердит">
                  📊 Работ пока не принято
                </div>
              )}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))', gap: '10px', marginBottom: '14px' }}>
              <div style={{ ...card, padding: '12px', backgroundColor: C.successLight, border: '1.5px solid ' + C.successBorder }}>
                <p style={{ color: C.success, fontSize: '11px', margin: '0 0 4px', fontWeight: '600' }}>✅ Принято</p>
                <b style={{ color: C.success, fontSize: '17px', display: 'block' }}>{Math.round(sumConfirmed).toLocaleString('ru-RU') + ' ₽'}</b>
                <span style={{ color: C.textSec, fontSize: '10px' }}>{myConfirmed.length + ' работ'}</span>
              </div>
              <div style={{ ...card, padding: '12px', backgroundColor: C.warningLight, border: '1.5px solid ' + C.warningBorder }}>
                <p style={{ color: C.warning, fontSize: '11px', margin: '0 0 4px', fontWeight: '600' }}>⏳ На проверке</p>
                <b style={{ color: C.warning, fontSize: '17px', display: 'block' }}>{Math.round(sumPending).toLocaleString('ru-RU') + ' ₽'}</b>
                <span style={{ color: C.textSec, fontSize: '10px' }}>{myPending.length + ' работ'}</span>
              </div>
              {myRejected.length > 0 && (
                <div style={{ ...card, padding: '12px', backgroundColor: C.dangerLight, border: '1.5px solid ' + C.dangerBorder }}>
                  <p style={{ color: C.danger, fontSize: '11px', margin: '0 0 4px', fontWeight: '600' }}>❌ Отклонено</p>
                  <b style={{ color: C.danger, fontSize: '17px', display: 'block' }}>{Math.round(sumRejected).toLocaleString('ru-RU') + ' ₽'}</b>
                  <span style={{ color: C.textSec, fontSize: '10px' }}>{myRejected.length + ' работ'}</span>
                </div>
              )}
              <div style={{ ...card, padding: '12px', backgroundColor: C.infoLight, border: '1.5px solid ' + C.infoBorder }}>
                <p style={{ color: C.info, fontSize: '11px', margin: '0 0 4px', fontWeight: '600' }}>📅 Сегодня</p>
                <b style={{ color: C.info, fontSize: '17px', display: 'block' }}>{Math.round(sumToday).toLocaleString('ru-RU') + ' ₽'}</b>
                <span style={{ color: C.textSec, fontSize: '10px' }}>{myToday.length + ' работ'}</span>
              </div>
              <div style={{ ...card, padding: '12px', backgroundColor: C.bg, border: '1.5px solid ' + C.border }}>
                <p style={{ color: C.textSec, fontSize: '11px', margin: '0 0 4px', fontWeight: '600' }}>📊 За 30 дней</p>
                <b style={{ color: C.text, fontSize: '17px', display: 'block' }}>{Math.round(sumMonth).toLocaleString('ru-RU') + ' ₽'}</b>
                <span style={{ color: C.textSec, fontSize: '10px' }}>{myMonth.length + ' работ'}</span>
              </div>
            </div>

            {(() => {
              const myExp = (ownExpenses || []).filter(expense => expense.employeeName === user.name || expense.employeeId === user.id);
              const pending = myExp.filter(expense => expense.status === 'Ожидает');
              const sumPendingExpenses = pending.reduce((sum, expense) => sum + Number(expense.amount || 0), 0);
              if (myExp.length === 0) {
                return (
                  <div style={{ ...card, padding: '14px', marginBottom: '14px', backgroundColor: C.infoLight, border: '1.5px solid ' + C.infoBorder, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                    <div>
                      <b style={{ color: C.info, fontSize: '13px' }}>💸 Свои траты на стройке?</b>
                      <p style={{ color: C.textSec, fontSize: '11px', margin: '2px 0 0' }}>Фиксируйте здесь чтобы бухгалтерия возместила</p>
                    </div>
                    <button onClick={() => setShowOwnExpenseForm(true)} style={btnO}>
                      <Plus size={14} />
                      Новая трата
                    </button>
                  </div>
                );
              }
              return (
                <div style={{ ...card, padding: '14px', marginBottom: '14px', backgroundColor: pending.length > 0 ? C.warningLight : C.successLight, border: '1.5px solid ' + (pending.length > 0 ? C.warningBorder : C.successBorder) }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px', flexWrap: 'wrap', marginBottom: '8px' }}>
                    <div>
                      <b style={{ color: C.text, fontSize: '13px' }}>💸 Мои траты — {pending.length > 0 ? 'ждут возмещения' : 'все возмещены ✅'}</b>
                      {pending.length > 0 && <p style={{ color: C.warning, margin: '2px 0 0', fontSize: '12px' }}>Сумма к возмещению: <b>{Math.round(sumPendingExpenses).toLocaleString('ru-RU') + ' ₽'}</b> · {pending.length + ' шт'}</p>}
                    </div>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button onClick={() => setActivePage('myexpenses')} style={{ ...btnG, padding: '5px 10px', fontSize: '12px' }}>📜 Все траты</button>
                      <button onClick={() => setShowOwnExpenseForm(true)} style={{ ...btnO, padding: '5px 12px', fontSize: '12px' }}>
                        <Plus size={12} />
                        Новая
                      </button>
                    </div>
                  </div>
                </div>
              );
            })()}

            {(() => {
              const myReqs = (supplyRequests || []).filter(request => request.createdBy === user.name || request.requestedById === user.id);
              const pendingReqs = myReqs.filter(request => request.status === 'Новая' || request.status === 'Подтверждена прорабом');
              const approvedReqs = myReqs.filter(request => request.status === 'Утверждена');
              const rejectedReqs = myReqs.filter(request => request.status === 'Отклонена');
              const openForm = () => {
                setActivePage('supply');
                setShowSupplyForm(true);
              };
              if (myReqs.length === 0) {
                return (
                  <div style={{ ...card, padding: '14px', marginBottom: '14px', backgroundColor: C.infoLight, border: '1.5px solid ' + C.infoBorder, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                    <div>
                      <b style={{ color: C.info, fontSize: '13px' }}>🛒 Не хватает материала?</b>
                      <p style={{ color: C.textSec, fontSize: '11px', margin: '2px 0 0' }}>Создайте заявку — её увидит прораб и директор</p>
                    </div>
                    <button onClick={openForm} style={btnO}>
                      <Plus size={14} />
                      Заявка на материал
                    </button>
                  </div>
                );
              }
              return (
                <div style={{ ...card, padding: '14px', marginBottom: '14px', backgroundColor: pendingReqs.length > 0 ? C.warningLight : C.successLight, border: '1.5px solid ' + (pendingReqs.length > 0 ? C.warningBorder : C.successBorder) }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                    <div>
                      <b style={{ color: C.text, fontSize: '13px' }}>🛒 Мои заявки на материалы</b>
                      <p style={{ color: C.textSec, margin: '2px 0 0', fontSize: '12px' }}>
                        {pendingReqs.length > 0 && '⏳ В работе: ' + pendingReqs.length + ' шт. '}
                        {approvedReqs.length > 0 && '✅ Утверждено: ' + approvedReqs.length + '. '}
                        {rejectedReqs.length > 0 && '❌ Отклонено: ' + rejectedReqs.length + '.'}
                      </p>
                    </div>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button onClick={() => setActivePage('supply')} style={{ ...btnG, padding: '5px 10px', fontSize: '12px' }}>📋 Открыть</button>
                      <button onClick={openForm} style={{ ...btnO, padding: '5px 12px', fontSize: '12px' }}>
                        <Plus size={12} />
                        Заявка
                      </button>
                    </div>
                  </div>
                </div>
              );
            })()}

            {(() => {
              const myEstimateChanges = (unexpectedWorksList || [])
                .filter(item => {
                  const sameAuthor = String(item.addedBy || '').trim().toLowerCase() === String(user.name || '').trim().toLowerCase();
                  const sameProject = !selectedMasterProject?.name || item.projectName === selectedMasterProject.name;
                  return sameAuthor && sameProject && item.status !== 'Аннулировано';
                })
                .slice(0, 4);
              const packageOptions = Array.from(new Set(['Основная', ...userAssignedPackages].filter(Boolean)));
              return (
                <div style={{ ...card, padding: '14px', marginBottom: '14px', backgroundColor: C.bg, border: '1.5px solid ' + C.border }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                    <div>
                      <b style={{ color: C.text, fontSize: '13px' }}>Изменение к смете / работа вне сметы</b>
                      <p style={{ color: C.textSec, margin: '2px 0 0', fontSize: '11px' }}>Черновик уйдет директору и сметчику на согласование</p>
                    </div>
                    <button onClick={() => setShowEstimateChangeForm(value => !value)} style={{ ...btnB, padding: '6px 10px', fontSize: '12px' }}>
                      {showEstimateChangeForm ? 'Скрыть' : '+ Допработа'}
                    </button>
                  </div>
                  {showEstimateChangeForm && (
                    <div style={{ marginTop: '12px', display: 'grid', gap: '8px' }}>
                      {!selectedMasterProject?.name && (
                        <div style={{ padding: '10px', borderRadius: '8px', backgroundColor: C.warningLight, border: '1px solid ' + C.warningBorder, color: C.warning, fontSize: '12px', fontWeight: 700 }}>
                          Сначала выберите объект выше
                        </div>
                      )}
                      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1.2fr) minmax(0,.8fr)', gap: '8px' }}>
                        <select
                          value={estimateChangeDraft.changeType}
                          onChange={e => setEstimateChangeDraft(prev => ({ ...prev, changeType: e.target.value }))}
                          style={{ ...inp, marginBottom: 0 }}
                        >
                          <option>Работа вне сметы</option>
                          <option>Дополнительный объём к строке сметы</option>
                          <option>Замена решения</option>
                          <option>Исключение объёма</option>
                        </select>
                        <select
                          value={estimateChangePackage}
                          onChange={e => setEstimateChangeDraft(prev => ({ ...prev, workPackage: e.target.value }))}
                          style={{ ...inp, marginBottom: 0 }}
                        >
                          {packageOptions.map(option => <option key={option}>{option}</option>)}
                        </select>
                      </div>
                      <input
                        placeholder="Что нужно выполнить"
                        value={estimateChangeDraft.description}
                        onChange={e => setEstimateChangeDraft(prev => ({ ...prev, description: e.target.value }))}
                        style={{ ...inp, marginBottom: 0 }}
                      />
                      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,.8fr) minmax(0,.6fr) minmax(0,1.6fr)', gap: '8px' }}>
                        <input
                          type="number"
                          step="any"
                          inputMode="decimal"
                          placeholder="Кол-во"
                          value={estimateChangeDraft.quantity}
                          onChange={e => setEstimateChangeDraft(prev => ({ ...prev, quantity: e.target.value }))}
                          style={{ ...inp, marginBottom: 0 }}
                        />
                        <select
                          value={estimateChangeDraft.unit}
                          onChange={e => setEstimateChangeDraft(prev => ({ ...prev, unit: e.target.value }))}
                          style={{ ...inp, marginBottom: 0 }}
                        >
                          {(UNITS || ['шт', 'м2', 'м3', 'м.п.', 'кг']).map(unit => <option key={unit}>{unit}</option>)}
                        </select>
                        <input
                          placeholder="Причина"
                          value={estimateChangeDraft.reason}
                          onChange={e => setEstimateChangeDraft(prev => ({ ...prev, reason: e.target.value }))}
                          style={{ ...inp, marginBottom: 0 }}
                        />
                      </div>
                      <textarea
                        placeholder="Комментарий"
                        value={estimateChangeDraft.notes}
                        onChange={e => setEstimateChangeDraft(prev => ({ ...prev, notes: e.target.value }))}
                        style={{ ...inp, minHeight: '72px', marginBottom: 0 }}
                      />
                      <PhotoAttachmentField
                        C={C}
                        value={estimateChangeDraft.photoUrl}
                        onChange={photoUrl => setEstimateChangeDraft(prev => ({ ...prev, photoUrl }))}
                        appendPhotos={appendPhotos}
                        fileSrc={fileSrc}
                        setShowPhotoModal={setShowPhotoModal}
                        projectName={selectedMasterProject?.name || ''}
                        context="estimate-change"
                        title="Фото основания"
                      />
                      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                        <button onClick={submitEstimateChangeDraft} disabled={!selectedMasterProject?.name} style={{ ...btnO, opacity: selectedMasterProject?.name ? 1 : 0.65 }}>
                          Отправить на согласование
                        </button>
                        <button onClick={() => setShowEstimateChangeForm(false)} style={btnG}>Отмена</button>
                      </div>
                    </div>
                  )}
                  {myEstimateChanges.length > 0 && (
                    <div style={{ marginTop: '10px', display: 'grid', gap: '6px' }}>
                      {myEstimateChanges.map(item => (
                        <div key={item.id} style={{ padding: '8px 10px', borderRadius: '8px', backgroundColor: C.bgWhite, border: '1px solid ' + C.border }}>
                          <b style={{ color: C.text, fontSize: '12px' }}>{item.description}</b>
                          <p style={{ color: C.textSec, margin: '2px 0 0', fontSize: '11px' }}>
                            {(item.changeType || 'Работа вне сметы') + ' · ' + (item.status || 'Ожидает согласования') + ' · ' + safeFmtMeasure(item.deltaQuantity || item.quantity, item.unit)}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })()}

            <div style={{ ...card, padding: '20px', marginBottom: '15px' }}>
              <h4 style={{ marginBottom: '15px', color: C.text, fontSize: '14px', fontWeight: '600' }}>Добавить работы</h4>
              {masterProjectOptions.length === 0 && <div style={{ padding: '12px', backgroundColor: C.warningLight, border: '1.5px solid ' + C.warningBorder, borderRadius: '10px', color: C.text, fontSize: '12px', marginBottom: '10px' }}>Нет доступных объектов. Назначьте мастера на объект или привяжите его к договору бригады.</div>}
              <div style={{ marginBottom: '10px' }}>
                <button
                  type="button"
                  onClick={() => masterProjectOptions.length > 0 && setShowProjectPicker(value => !value)}
                  disabled={masterProjectOptions.length === 0}
                  style={{
                    ...inp,
                    marginBottom: 0,
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    textAlign: 'left',
                    cursor: masterProjectOptions.length ? 'pointer' : 'not-allowed',
                    opacity: masterProjectOptions.length ? 1 : 0.65,
                  }}
                >
                  <span>{selectedMasterProject?.name || (masterProjectOptions.length ? 'Выберите объект' : 'Нет доступных объектов')}</span>
                  <span style={{ color: C.textSec, fontSize: '18px', lineHeight: 1 }}>{showProjectPicker ? '⌃' : '⌄'}</span>
                </button>
                {showProjectPicker && masterProjectOptions.length > 0 && (
                  <div style={{ marginTop: '8px', display: 'grid', gap: '8px' }}>
                    {masterProjectOptions.map(project => {
                      const selected = String(project.id) === String(masterProjectId);
                      return (
                        <button
                          key={project.id}
                          type="button"
                          onClick={() => selectMasterProject(String(project.id))}
                          style={{
                            width: '100%',
                            padding: '12px 14px',
                            borderRadius: '10px',
                            border: '1.5px solid ' + (selected ? C.accent : C.border),
                            backgroundColor: selected ? C.accentLight : C.bgWhite,
                            color: selected ? C.accent : C.text,
                            fontSize: '14px',
                            fontWeight: selected ? 700 : 600,
                            textAlign: 'left',
                            cursor: 'pointer',
                          }}
                        >
                          {project.name}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
              {masterProjectId && (
                <>
                  {pricelistItems.length === 0 && !selectedProjectHasActiveCustomerEstimate && <p style={{ color: C.textMuted, textAlign: 'center', padding: '20px' }}>Прайс-лист не привязан к проекту</p>}
                  {activePage === 'works' && null}
                  {/* Содержимое списка работ оставлено в компоненте, но в отдельном файле — это и есть текущий шаг рефакторинга. */}
                </>
              )}
              {masterProjectId && (() => {
                const { projectName, myItems, hasActiveEstimate } = masterEstimateWorkState;
                if (myItems.length === 0) {
                  if (!hasActiveEstimate) return null;
                  return (
                    <div style={{ ...card, padding: '14px', marginBottom: '15px', backgroundColor: C.warningLight, border: '1.5px solid ' + C.warningBorder }}>
                      <b style={{ color: C.warning, fontSize: '13px' }}>Работы по смете еще не назначены</b>
                      <p style={{ color: C.textSec, margin: '5px 0 0', fontSize: '12px' }}>После выдачи работ мастеру здесь появятся объемы, цены исполнителя и кнопка отправки в ЖПР.</p>
                    </div>
                  );
	                }
	                const currentProject = projects.find(projectRow => projectRow.id === Number(masterProjectId));
	                const visibleLimit = Math.min(estimateWorkVisibleLimit, myItems.length);
	                const visibleMyItems = myItems.slice(0, visibleLimit);
	                const hiddenMyItemsCount = Math.max(0, myItems.length - visibleMyItems.length);
	                return (
	                  <div style={{ ...card, padding: '14px', marginBottom: '15px', backgroundColor: C.accentLight, border: '1.5px solid ' + C.accentBorder }}>
	                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px', flexWrap: 'wrap', marginBottom: '10px' }}>
	                      <div>
	                        <b style={{ color: C.accent, fontSize: '13px', display: 'block' }}>🎯 Мои работы по смете ({myItems.length})</b>
	                        {myItems.length > visibleMyItems.length && (
	                          <span style={{ color: C.textSec, fontSize: '11px' }}>Показано {visibleMyItems.length} из {myItems.length}. Остальные строки не рисуются, чтобы ввод не подвисал.</span>
	                        )}
	                      </div>
	                      <button onClick={() => openDailyEstimateWorkReview(myItems)} style={{ ...btnO, padding: '7px 11px', fontSize: '12px' }}>
	                        Рассчитать день
	                      </button>
	                    </div>
	                    {dailyWorkError && (
	                      <div style={{ padding: '9px 10px', borderRadius: '9px', backgroundColor: C.dangerLight, border: '1px solid ' + C.dangerBorder, color: C.danger, fontSize: '12px', fontWeight: 700, marginBottom: '8px' }}>
	                        {dailyWorkError}
	                      </div>
	                    )}
	                    {visibleMyItems.map((item, index) => {
	                      const quantity = Number(item.quantity) || 0;
	                      const done = Number(item.doneQuantity) || 0;
	                      const remain = Math.max(0, quantity - done);
                      const doneNorm = safeNormalizeMeasure(done, item.unit);
                      const workKey = estimateWorkKey(item.estId, item.sectionIdx, item.itemIdx);
                      const params = estimateWorkParams[workKey] || {};
	                      const draft = estimateDoneDrafts[workKey] !== undefined
	                        ? estimateDoneDrafts[workKey]
	                        : (estimateDraftValueRef.current[workKey] !== undefined ? estimateDraftValueRef.current[workKey] : '');
	                      const delta = Math.max(0, safeDenormalizeMeasure(draft, item.unit));
	                      const project = currentProject;
	                      const roomCheck = project && params.roomId ? roomMeasurementCheck(project.name, params.roomId, params.surface || 'Стены', delta, item.unit, item.name) : null;
                      const usedMaterials = estimateWorkMaterials[workKey] || [];
                      const materialPanelOpen = activeEstimateMaterialKey === workKey;
                      const projectMaterials = materialPanelOpen && project ? getWorkMaterialRows(project.name, item.workPackage) : [];
                      const availableMap = materialPanelOpen && project ? getWorkMaterialAvailability(project.name, item.workPackage) : {};
                      const usedMap = {};
                      if (materialPanelOpen) {
                        usedMaterials.forEach(material => { usedMap[materialNameKey(material.name)] = material; });
                      }
                      const suggestions = materialPanelOpen && project ? getWorkMaterialSuggestions(project.name, item.name, item.section, item.workPackage) : [];
                      const executionUnitPrice = Number(item.executionPricePerUnit || item.internalPricePerUnit || item.masterPricePerUnit || item.contractorPricePerUnit || 0);
                      const deltaEarning = Math.round(delta * executionUnitPrice);
                      const missingExecutionPrice = executionUnitPrice <= 0;
                      return (
                        <div key={workKey} style={{ padding: '10px', marginBottom: '6px', backgroundColor: C.bgWhite, borderRadius: '8px', border: '1px solid ' + C.border, contentVisibility: 'auto', containIntrinsicSize: '118px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                            <div style={{ flex: '1 1 260px', minWidth: '220px' }}>
                              <b style={{ fontSize: '12px', color: C.text }}>{item.name}</b>
                              <p style={{ color: C.textSec, margin: '2px 0', fontSize: '11px' }}>{item.section + ' · план ' + safeFmtMeasure(quantity, item.unit) + ' · сделано ' + safeFmtMeasure(done, item.unit) + ' · осталось ' + safeFmtMeasure(remain, item.unit)}</p>
                            </div>
                            {projectRooms.length > 0 ? (
                              <select value={params.roomId || ''} onChange={e => { const room = projectRooms.find(roomItem => Number(roomItem.id) === Number(e.target.value)); setEstimateWorkParams(prev => ({ ...prev, [workKey]: { ...(prev[workKey] || {}), roomId: e.target.value, roomName: room?.name || '' } })); }} style={{ ...inp, marginBottom: 0, width: '180px', maxWidth: '100%', fontSize: '11px', padding: '5px 8px' }}>
                                <option value="">Помещение</option>
                                {projectRooms.map(room => <option key={room.id} value={room.id}>{room.name}</option>)}
                              </select>
                            ) : project ? (
                              <span style={{ padding: '6px 9px', borderRadius: '8px', border: '1px solid ' + C.warningBorder, backgroundColor: C.warningLight, color: C.warning, fontSize: '11px', fontWeight: '700', whiteSpace: 'nowrap' }}>
                                {GENERAL_WORK_ROOM_NAME}
                              </span>
                            ) : null}
                            <input
                              key={workKey + ':' + done}
                              type="number"
                              step="any"
                              inputMode="decimal"
                              placeholder={'сегодня, ' + (doneNorm.unit || item.unit)}
	                              defaultValue={draft}
	                              onChange={e => {
	                                estimateDraftValueRef.current[workKey] = e.target.value;
	                                if (dailyWorkError) setDailyWorkError('');
	                              }}
                              onBlur={e => {
                                const nextValue = e.target.value;
                                commitEstimateDoneDraft(workKey, nextValue);
                                if (safeDenormalizeMeasure(nextValue, item.unit) > 0) {
                                  syncEstimateNormMaterials(workKey, project, item, nextValue, 0);
                                }
                              }}
                              style={{ ...inp, marginBottom: 0, width: '80px', fontSize: '12px', padding: '4px 6px' }}
                            />
                            <select value={params.surface || 'Стены'} onChange={e => setEstimateWorkParams(prev => ({ ...prev, [workKey]: { ...(prev[workKey] || {}), surface: e.target.value } }))} style={{ ...inp, marginBottom: 0, width: '118px', fontSize: '11px', padding: '5px 8px' }}>
                              {SURFACES.map(surface => <option key={surface}>{surface}</option>)}
                            </select>
                            {needsThicknessParam(item.name, item.section) && (
                              <input
                                type="number"
                                step="any"
                                inputMode="decimal"
                                placeholder="слой, мм"
                                value={estimateWorkParams[workKey]?.thicknessMm || ''}
                                onChange={e => {
                                  const value = e.target.value;
                                  const nextParams = { ...(estimateWorkParams[workKey] || {}), thicknessMm: value };
                                  setEstimateWorkParams(prev => ({ ...prev, [workKey]: nextParams }));
                                }}
                                onBlur={e => syncEstimateNormMaterials(
                                  workKey,
                                  project,
                                  item,
                                  draft,
                                  0,
                                  { ...(estimateWorkParams[workKey] || {}), thicknessMm: e.target.value },
                                )}
                                style={{ ...inp, marginBottom: 0, width: '78px', fontSize: '12px', padding: '4px 6px' }}
                              />
                            )}
                            <span style={{ fontSize: '11px', color: missingExecutionPrice ? C.warning : C.success, fontWeight: '600', whiteSpace: 'nowrap' }}>{missingExecutionPrice ? 'цена не назначена' : deltaEarning.toLocaleString('ru-RU') + ' ₽'}</span>
                            <button
                              onClick={() => {
                                const liveDraft = estimateDraftValueRef.current[workKey] !== undefined ? estimateDraftValueRef.current[workKey] : draft;
                                commitEstimateDoneDraft(workKey, liveDraft);
                                const targetDisplay = safeNormalizeMeasure(done + safeDenormalizeMeasure(liveDraft, item.unit), item.unit).qty;
                                submitEstimateWorkDone(item, targetDisplay);
                              }}
                              disabled={missingExecutionPrice}
                              style={{ ...(!missingExecutionPrice ? btnO : btnG), padding: '5px 9px', fontSize: '11px', opacity: !missingExecutionPrice ? 1 : 0.65 }}
                            >
                              Отправить
                            </button>
                          </div>
                          {roomCheck && <div style={{ marginTop: '6px', padding: '7px 9px', borderRadius: '8px', border: '1px solid ' + (roomCheck.over > 0 ? C.dangerBorder : C.successBorder), backgroundColor: roomCheck.over > 0 ? C.dangerLight : C.successLight, color: roomCheck.over > 0 ? C.danger : C.success, fontSize: '11px', fontWeight: '600' }}>{roomMeasurementMessage(roomCheck)}</div>}
                          <div style={{ marginTop: '8px' }}>
                            <MasterWorkJournalPhotoField
                              C={C}
                              btnG={btnG}
                              value={params.photoUrl || ''}
                              onChange={photoUrl => setEstimateWorkParams(prev => ({ ...prev, [workKey]: { ...(prev[workKey] || {}), photoUrl } }))}
                              appendPhotos={appendPhotos}
                              fileSrc={fileSrc}
                              setShowPhotoModal={setShowPhotoModal}
                              projectName={project?.name || projectName}
                              title="Фото работы / помещения"
                              compact
                            />
                          </div>
                          {project && (
                            <div style={{ marginTop: '8px' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                                <button
                                  type="button"
                                  onClick={() => setActiveEstimateMaterialKey(prev => prev === workKey ? '' : workKey)}
                                  style={{ ...btnG, padding: '5px 9px', fontSize: '11px' }}
                                >
                                  {materialPanelOpen ? 'Скрыть материалы' : (usedMaterials.length ? 'Материалы: ' + usedMaterials.length : 'Материалы')}
                                </button>
                                {!materialPanelOpen && usedMaterials.length > 0 && (
                                  <span style={{ color: C.textSec, fontSize: '11px' }}>Выбрано материалов: {usedMaterials.length}</span>
                                )}
                              </div>
                              {materialPanelOpen && (
                                <div style={{ marginTop: '6px', padding: '8px', backgroundColor: C.bg, borderRadius: '8px', border: '1px solid ' + C.border }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'center', marginBottom: '6px' }}>
                                <b style={{ fontSize: '11px', color: C.text }}>📦 Материалы к списанию</b>
                                <span style={{ fontSize: '10px', color: C.textSec }}>{delta > 0 ? 'новый объём: ' + safeFmtMeasure(delta, item.unit) : 'сначала укажите новый объём'}</span>
                              </div>
                              {suggestions.length > 0 && (
                                <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap', marginBottom: '6px' }}>
                                  {suggestions.slice(0, 6).map(suggestion => {
                                    const key = materialNameKey(suggestion.name);
                                    const checked = !!usedMap[key];
                                    const available = availableMap[key];
                                    const unit = available?.unit || suggestion.unit || 'шт';
                                    const hasStock = safeToNum(available?.quantity) > 0;
                                    const status = materialControlStatus(suggestion);
                                    const norm = materialNormForWork(project.name, item.name, item.section, delta, item.unit, { name: suggestion.name, unit }, estimateWorkParams[workKey] || {});
                                    const writeQty = norm ? capMaterialWriteoffQty(project.name, suggestion.name, norm.quantity, item.workPackage) : '';
                                    return (
                                      <button
                                        type="button"
                                        key={key}
                                        disabled={!hasStock}
                                        onClick={() => checked ? removeEstimateWorkMaterial(workKey, suggestion.name) : upsertEstimateWorkMaterial(workKey, { name: suggestion.name, unit, workPackage: item.workPackage || '', autoNorm: !!norm, normQuantity: norm?.normQuantity || '', normSource: norm?.normSource || '', normRuleId: norm?.ruleId || '', normThicknessMm: estimateWorkParams[workKey]?.thicknessMm || '' }, writeQty)}
                                        style={{ padding: '4px 7px', borderRadius: '7px', border: '1px solid ' + (checked ? C.accentBorder : status.border), backgroundColor: checked ? C.accentLight : status.bg, color: hasStock ? (checked ? C.accent : status.color) : C.textMuted, cursor: hasStock ? 'pointer' : 'not-allowed', fontSize: '10px', fontWeight: '600' }}
                                      >
                                        {(checked ? '✓ ' : '') + suggestion.name + (norm ? ' · норма ' + safeFmtMeasure(norm.quantity, unit) + (writeQty && safeToNum(writeQty) < safeToNum(norm.quantity) ? ' · доступно ' + safeFmtMeasure(writeQty, unit) : '') : (hasStock ? ' · ' + safeFmtMeasure(available.quantity, available.unit) : ''))}
                                      </button>
                                    );
                                  })}
                                </div>
                              )}
                              {renderMaterialWriteoffStatus(project.name, usedMaterials)}
                              {projectMaterials.length > 0 ? (
                                <div style={{ maxHeight: '155px', overflowY: 'auto', display: 'grid', gap: '5px' }}>
                                  {projectMaterials.map(material => {
                                    const key = materialNameKey(material.name);
                                    const checked = !!usedMap[key];
                                    const selected = usedMap[key] || {};
                                    const hint = materialHintForProject(project.name, material.name, item.workPackage);
                                    const stock = safeToNum(material.quantity);
                                    const norm = materialNormForWork(project.name, item.name, item.section, delta, item.unit, material, estimateWorkParams[workKey] || {});
                                    const normStatus = checked ? materialNormStatus(selected) : null;
                                    const over = checked && safeToNum(selected.quantity) > stock;
                                    return (
                                      <div key={material.id} style={{ display: 'grid', gridTemplateColumns: '18px minmax(0,1fr) auto', gap: '6px', alignItems: 'center', fontSize: '11px', padding: '5px 6px', border: '1px solid ' + (over ? C.dangerBorder : checked ? C.accentBorder : C.border), borderRadius: '7px' }}>
                                        <input type="checkbox" checked={checked} onChange={e => e.target.checked ? upsertEstimateWorkMaterial(workKey, { name: material.name, unit: material.unit || 'шт', workPackage: item.workPackage || '', autoNorm: !!norm, normQuantity: norm?.normQuantity || '', normSource: norm?.normSource || '', normRuleId: norm?.ruleId || '', normThicknessMm: estimateWorkParams[workKey]?.thicknessMm || '' }, norm ? capMaterialWriteoffQty(project.name, material.name, norm.quantity, item.workPackage) : '') : removeEstimateWorkMaterial(workKey, material.name)} style={{ width: '14px', height: '14px', accentColor: C.accent }} />
                                        <span style={{ color: C.text, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                          {material.name}
                                          <span style={{ color: over ? C.danger : C.textSec }}>
                                            {' · доступно ' + safeFmtMeasure(stock, material.unit)}
                                            {hint?.used > 0 ? ' · списано ' + safeFmtMeasure(hint.used, hint.unit) : ''}
                                            {norm ? ' · норма ' + safeFmtMeasure(norm.quantity, norm.unit) : ''}
                                          </span>
                                          {normStatus && <span style={{ marginLeft: '5px', padding: '1px 5px', borderRadius: '7px', fontSize: '9px', fontWeight: '700', backgroundColor: normStatus.bg, color: normStatus.color, border: '1px solid ' + normStatus.border }}>{normStatus.label}</span>}
                                        </span>
                                        {checked && <input type="number" step="any" inputMode="decimal" placeholder="кол-во" value={selected.quantity || ''} onChange={e => updateEstimateWorkMaterialQty(workKey, material.name, e.target.value)} style={{ width: '76px', padding: '4px 6px', border: '1.5px solid ' + (over ? C.danger : C.border), borderRadius: '6px', fontSize: '11px', backgroundColor: C.bgWhite, color: C.text }} />}
                                      </div>
                                    );
                                  })}
                                </div>
                              ) : (
                                <p style={{ margin: 0, color: C.textMuted, fontSize: '11px' }}>{isPersonalMaterialRole() ? 'Нет подтверждённых материалов, выданных вам для списания.' : 'На складе объекта нет остатков для списания.'}</p>
                              )}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
	                      );
	                    })}
	                    {hiddenMyItemsCount > 0 && (
	                      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'center', marginTop: '10px' }}>
	                        <button
	                          type="button"
	                          onClick={() => setEstimateWorkVisibleLimit(prev => Math.min(myItems.length, prev + MASTER_WORKS_VISIBLE_STEP))}
	                          style={{ ...btnG, padding: '8px 12px', fontSize: '12px' }}
	                        >
	                          Показать ещё {Math.min(MASTER_WORKS_VISIBLE_STEP, hiddenMyItemsCount)}
	                        </button>
	                        <button
	                          type="button"
	                          onClick={() => setEstimateWorkVisibleLimit(myItems.length)}
	                          style={{ ...btnG, padding: '8px 12px', fontSize: '12px' }}
	                        >
	                          Показать все
	                        </button>
	                        <span style={{ color: C.textSec, fontSize: '11px' }}>Скрыто: {hiddenMyItemsCount}</span>
	                      </div>
	                    )}
	                    <button onClick={() => openDailyEstimateWorkReview(myItems)} style={{ ...btnO, width: '100%', padding: '12px', justifyContent: 'center', marginTop: '10px' }}>
	                      Сформировать работы в один акт
                    </button>
                  </div>
                );
              })()}

              {pricelistItems.length > 0 && !selectedBrigadeContract && selectedProjectHasActiveCustomerEstimate && (
                <div style={{ padding: '12px', border: '1.5px solid ' + C.warningBorder, borderRadius: '10px', backgroundColor: C.warningLight, color: C.text, fontSize: '12px', marginTop: '12px' }}>
                  По объекту есть активная заказная смета. Работы закрываются только по назначенным сметным позициям, прайс-режим скрыт.
                </div>
              )}

              {pricelistItems.length > 0 && !selectedBrigadeContract && !selectedProjectHasActiveCustomerEstimate && (
                <>
                  {categories.map(category => (
                    <div key={category} style={{ marginBottom: '15px' }}>
                      <div style={{ color: C.accent, fontSize: '11px', fontWeight: '700', marginBottom: '8px', borderBottom: '1.5px solid ' + C.border, paddingBottom: '5px', textTransform: 'uppercase' }}>{category}</div>
                      {pricelistItems.filter(item => item.category === category).map(item => {
                        const project = projects.find(projectRow => projectRow.id === Number(masterProjectId));
                        const pricelist = project && props.pricelists.find(price => price.id === project.pricelistId);
                        const price = item.price * (pricelist ? pricelist.coefficient : 1.0);
                        const isSelected = selectedWorks[item.id] !== undefined;
                        return (
                          <div key={item.id} style={{ padding: '12px', marginBottom: '8px', borderRadius: '10px', border: '1.5px solid ' + (isSelected ? C.accent : C.border), backgroundColor: isSelected ? C.accentLight : C.bgWhite }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <label style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer', flex: 1 }}>
                                <input
                                  type="checkbox"
                                  checked={isSelected}
                                  onChange={e => {
                                    if (e.target.checked) setSelectedWorks(prev => ({ ...prev, [item.id]: { quantity: '', comment: '', photoUrl: '', roomId: '', roomName: '', surface: 'Стены', materials: [] } }));
                                    else {
                                      const next = { ...selectedWorks };
                                      delete next[item.id];
                                      setSelectedWorks(next);
                                    }
                                  }}
                                  style={{ width: '18px', height: '18px', accentColor: C.accent }}
                                />
                                <span style={{ fontWeight: isSelected ? '600' : '400', fontSize: '13px', color: C.text }}>{item.name}</span>
                              </label>
                              <span style={{ color: C.accent, fontWeight: '700', fontSize: '12px', whiteSpace: 'nowrap' }}>{price.toLocaleString() + ' ₽/' + item.unit}</span>
                            </div>
                            {isSelected && (
                              <div style={{ paddingLeft: '30px', marginTop: '10px' }}>
                                <input
                                  placeholder={'Количество (' + item.unit + ')'}
                                  type="number"
                                  step="any"
                                  inputMode="decimal"
                                  value={selectedWorks[item.id]?.quantity || ''}
                                  onChange={e => setSelectedWorks(prev => ({ ...prev, [item.id]: { ...(prev[item.id] || { materials: [] }), quantity: e.target.value } }))}
                                  onBlur={e => {
                                    const value = e.target.value;
                                    setSelectedWorks(prev => {
                                      const current = prev[item.id] || { materials: [] };
                                      const base = { ...current, quantity: value };
                                      const materials = project ? fillNormMaterialsForWork(project.name, item.name, category, safeToNum(value), item.unit, base.materials || [], base) : base.materials;
                                      return { ...prev, [item.id]: { ...base, materials } };
                                    });
                                  }}
                                  style={inp}
                                />
                                {needsThicknessParam(item.name, category) && (
                                  <input
                                    placeholder="Толщина слоя, мм"
                                    type="number"
                                    step="any"
                                    inputMode="decimal"
                                    value={selectedWorks[item.id]?.thicknessMm || ''}
                                    onChange={e => setSelectedWorks(prev => ({ ...prev, [item.id]: { ...(prev[item.id] || { materials: [] }), thicknessMm: e.target.value } }))}
                                    onBlur={e => {
                                      const value = e.target.value;
                                      setSelectedWorks(prev => {
                                        const current = prev[item.id] || { materials: [] };
                                        const base = { ...current, thicknessMm: value };
                                        const materials = project ? fillNormMaterialsForWork(project.name, item.name, category, safeToNum(base.quantity), item.unit, base.materials || [], base) : base.materials;
                                        return { ...prev, [item.id]: { ...base, materials } };
                                      });
                                    }}
                                    style={inp}
                                  />
                                )}
                                {projectRooms.length > 0 ? (
                                  <>
                                    <select value={selectedWorks[item.id]?.roomId || ''} onChange={e => { const room = projectRooms.find(roomItem => roomItem.id === Number(e.target.value)); setSelectedWorks(prev => ({ ...prev, [item.id]: { ...prev[item.id], roomId: e.target.value, roomName: room?.name || '' } })); }} style={inp}>
                                      <option value="">Выберите помещение</option>
                                      {projectRooms.map(room => <option key={room.id} value={room.id}>{room.name}</option>)}
                                    </select>
                                    <select value={selectedWorks[item.id]?.surface || 'Стены'} onChange={e => setSelectedWorks(prev => ({ ...prev, [item.id]: { ...prev[item.id], surface: e.target.value } }))} style={inp}>
                                      {SURFACES.map(surface => <option key={surface}>{surface}</option>)}
                                    </select>
                                  </>
                                ) : project ? (
                                  <div style={{ marginBottom: '8px', padding: '8px 10px', borderRadius: '8px', border: '1px solid ' + C.warningBorder, backgroundColor: C.warningLight, color: C.warning, fontSize: '11px', fontWeight: '600' }}>
                                    Помещение: {GENERAL_WORK_ROOM_NAME}
                                  </div>
                                ) : null}
                                {(() => {
                                  const check = project && selectedWorks[item.id]?.roomId ? roomMeasurementCheck(project.name, selectedWorks[item.id]?.roomId, selectedWorks[item.id]?.surface || 'Стены', selectedWorks[item.id]?.quantity, item.unit, item.name) : null;
                                  return check ? <div style={{ marginBottom: '8px', padding: '8px 10px', borderRadius: '8px', border: '1px solid ' + (check.over > 0 ? C.dangerBorder : C.successBorder), backgroundColor: check.over > 0 ? C.dangerLight : C.successLight, color: check.over > 0 ? C.danger : C.success, fontSize: '11px', fontWeight: '600' }}>{roomMeasurementMessage(check)}</div> : null;
                                })()}
                                <input placeholder="Комментарий" value={selectedWorks[item.id]?.comment || ''} onChange={e => setSelectedWorks(prev => ({ ...prev, [item.id]: { ...prev[item.id], comment: e.target.value } }))} style={inp} />
                                <MasterWorkJournalPhotoField
                                  C={C}
                                  btnG={btnG}
                                  value={selectedWorks[item.id]?.photoUrl || ''}
                                  onChange={photoUrl => setSelectedWorks(prev => ({ ...prev, [item.id]: { ...prev[item.id], photoUrl } }))}
                                  appendPhotos={appendPhotos}
                                  fileSrc={fileSrc}
                                  setShowPhotoModal={setShowPhotoModal}
                                  projectName={project?.name || ''}
                                  title="Фото работы / помещения"
                                />
                                {(() => {
                                  const scopedPackage = userAssignedPackages.length === 1 ? userAssignedPackages[0] : '';
                                  const projectMaterials = project ? getWorkMaterialRows(project.name, scopedPackage) : [];
                                  const availableMap = project ? getWorkMaterialAvailability(project.name, scopedPackage) : {};
                                  const usedMaterials = selectedWorks[item.id]?.materials || [];
                                  const usedMap = {};
                                  usedMaterials.forEach(material => { usedMap[materialNameKey(material.name)] = material; });
                                  if (!project) return null;
                                  const suggestions = getWorkMaterialSuggestions(project.name, item.name, category, scopedPackage);
                                  if (!projectMaterials.length && !suggestions.length) {
                                    return (
                                      <div style={{ marginTop: '8px', padding: '10px', backgroundColor: C.warningLight, borderRadius: '8px', border: '1px solid ' + C.warningBorder, fontSize: '11px', color: C.warning }}>
                                        {isPersonalMaterialRole() ? 'У вас пока нет подтверждённых материалов для списания. Подтвердите получение во вкладке «Склад» или попросите прораба/кладовщика выдать материал.' : 'На складе объекта пока нет материалов для списания. Сначала примите поставку или переместите материал на объект.'}
                                      </div>
                                    );
                                  }
                                  return (
                                    <div style={{ marginTop: '8px', padding: '10px', backgroundColor: C.bg, borderRadius: '8px', border: '1px solid ' + C.border }}>
                                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                                        <b style={{ fontSize: '12px', color: C.text }}>📦 Материалы к списанию</b>
                                        <span style={{ fontSize: '10px', color: C.textSec }}>спишутся при отправке ЖПР</span>
                                      </div>
                                      {suggestions.length > 0 && (
                                        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '8px' }}>
                                          {suggestions.map(suggestion => {
                                            const key = materialNameKey(suggestion.name);
                                            const checked = !!usedMap[key];
                                            const available = availableMap[key];
                                            const hasStock = safeToNum(available?.quantity) > 0;
                                            const status = materialControlStatus(suggestion);
                                            const unit = available?.unit || suggestion.unit || 'шт';
                                            const norm = materialNormForWork(project.name, item.name, category, safeToNum(selectedWorks[item.id]?.quantity), item.unit, { name: suggestion.name, unit }, selectedWorks[item.id] || {});
                                            const writeQty = norm ? capMaterialWriteoffQty(project.name, suggestion.name, norm.quantity, scopedPackage) : '';
                                            return (
                                              <button
                                                type="button"
                                                key={'sug-' + key}
                                                disabled={!hasStock}
                                                onClick={() => checked ? removeSelectedWorkMaterial(item.id, suggestion.name) : upsertSelectedWorkMaterial(item.id, { name: suggestion.name, unit, workPackage: scopedPackage || '', autoNorm: !!norm, normQuantity: norm?.normQuantity || '', normSource: norm?.normSource || '', normRuleId: norm?.ruleId || '', normThicknessMm: selectedWorks[item.id]?.thicknessMm || '' }, writeQty)}
                                                style={{ padding: '5px 8px', borderRadius: '8px', border: '1px solid ' + (checked ? C.accentBorder : status.border), backgroundColor: checked ? C.accentLight : status.bg, color: hasStock ? (checked ? C.accent : status.color) : C.textMuted, cursor: hasStock ? 'pointer' : 'not-allowed', fontSize: '10px', fontWeight: '600' }}
                                              >
                                                {(checked ? '✓ ' : '') + suggestion.name + ' · ' + (norm ? 'норма ' + safeFmtMeasure(norm.quantity, unit) + (writeQty && safeToNum(writeQty) < safeToNum(norm.quantity) ? ' · доступно ' + safeFmtMeasure(writeQty, unit) : '') : (hasStock ? 'доступно ' + safeFmtMeasure(available.quantity, available.unit) : isPersonalMaterialRole() ? 'не выдано мне' : 'нет на объекте'))}
                                              </button>
                                            );
                                          })}
                                        </div>
                                      )}
                                      {renderMaterialWriteoffStatus(project.name, usedMaterials)}
                                      {projectMaterials.length > 0 && (
                                        <div style={{ maxHeight: '190px', overflowY: 'auto', display: 'grid', gap: '6px' }}>
                                          {projectMaterials.map(material => {
                                            const key = materialNameKey(material.name);
                                            const checked = !!usedMap[key];
                                            const selected = usedMap[key] || {};
                                            const hint = materialHintForProject(project.name, material.name, scopedPackage);
                                            const stock = safeToNum(material.quantity);
                                            const norm = materialNormForWork(project.name, item.name, category, safeToNum(selectedWorks[item.id]?.quantity), item.unit, material, selectedWorks[item.id] || {});
                                            const normStatus = checked ? materialNormStatus(selected) : null;
                                            const over = checked && safeToNum(selected.quantity) > stock;
                                            const status = hint ? materialControlStatus(hint) : null;
                                            return (
                                              <div key={material.id} style={{ display: 'grid', gridTemplateColumns: '18px minmax(0,1fr) auto', alignItems: 'center', gap: '8px', padding: '7px 8px', backgroundColor: checked ? C.bgWhite : 'transparent', border: '1px solid ' + (over ? C.dangerBorder : checked ? C.accentBorder : C.border), borderRadius: '8px', fontSize: '11px' }}>
                                                <input type="checkbox" checked={checked} onChange={e => e.target.checked ? upsertSelectedWorkMaterial(item.id, { name: material.name, unit: material.unit || 'шт', workPackage: scopedPackage || '', autoNorm: !!norm, normQuantity: norm?.normQuantity || '', normSource: norm?.normSource || '', normRuleId: norm?.ruleId || '', normThicknessMm: selectedWorks[item.id]?.thicknessMm || '' }, norm ? capMaterialWriteoffQty(project.name, material.name, norm.quantity, scopedPackage) : '') : removeSelectedWorkMaterial(item.id, material.name)} style={{ width: '14px', height: '14px', cursor: 'pointer', accentColor: C.accent }} />
                                                <div style={{ minWidth: 0 }}>
                                                  <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap' }}>
                                                    <b style={{ color: C.text, overflow: 'hidden', textOverflow: 'ellipsis' }}>{material.name}</b>
                                                    {status && <span style={{ padding: '1px 6px', borderRadius: '8px', fontSize: '9px', fontWeight: '700', backgroundColor: status.bg, color: status.color, border: '1px solid ' + status.border }}>{status.label}</span>}
                                                    {normStatus && <span style={{ padding: '1px 6px', borderRadius: '8px', fontSize: '9px', fontWeight: '700', backgroundColor: normStatus.bg, color: normStatus.color, border: '1px solid ' + normStatus.border }}>{normStatus.label}</span>}
                                                  </div>
                                                  <div style={{ color: over ? C.danger : C.textSec, marginTop: '2px' }}>{'доступно ' + safeFmtMeasure(stock, material.unit)}{norm ? ' · норма ' + safeFmtMeasure(norm.quantity, norm.unit) : ''}{hint?.planQty > 0 ? ' · по смете ' + safeFmtMeasure(hint.planQty, hint.unit) : ''}{hint?.used > 0 ? ' · списано ' + safeFmtMeasure(hint.used, hint.unit) : ''}</div>
                                                </div>
                                                {checked && <input type="number" step="any" inputMode="decimal" placeholder="кол-во" value={selected.quantity || ''} max={stock} onChange={e => updateSelectedWorkMaterialQty(item.id, material.name, e.target.value)} style={{ width: '86px', padding: '5px 7px', border: '1.5px solid ' + (over ? C.danger : C.border), borderRadius: '6px', fontSize: '11px', backgroundColor: C.bgWhite, color: C.text }} />}
                                              </div>
                                            );
                                          })}
                                        </div>
                                      )}
                                    </div>
                                  );
                                })()}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  ))}
                  <button onClick={addMasterWorks} style={{ ...btnO, width: '100%', padding: '12px', justifyContent: 'center' }}>Отправить работы</button>
                </>
              )}
            </div>

            <div style={{ ...card, padding: '20px' }}>
              <h4 style={{ marginBottom: '15px', color: C.text, fontSize: '14px', fontWeight: '600' }}>Последние работы</h4>
              {myWorks.slice(0, 5).map(work => {
                const journalEntry = workJournal.find(entry => entry.masterId === user.id && entry.description === work.description && entry.date === work.date);
                return (
                  <div key={work.id} style={{ padding: '12px 0', borderBottom: '1.5px solid ' + C.border, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <b style={{ fontSize: '13px', color: C.text }}>{work.description}</b>
                      <p style={{ color: C.textSec, margin: '3px 0', fontSize: '12px' }}>{safeFmtMeasure(work.quantity, work.unit) + ' · ' + work.project + ' · ' + work.date}</p>
                      {journalEntry && <span style={badge(journalEntry.status === 'Подтверждено' ? C.success : journalEntry.status === 'Отклонено' ? C.danger : C.warning, journalEntry.status === 'Подтверждено' ? C.successLight : journalEntry.status === 'Отклонено' ? C.dangerLight : C.warningLight, journalEntry.status === 'Подтверждено' ? C.successBorder : journalEntry.status === 'Отклонено' ? C.dangerBorder : C.warningBorder)}>{journalEntry.status}</span>}
                    </div>
                    <b style={{ color: C.success, fontSize: '13px', whiteSpace: 'nowrap' }}>{(work.total || 0).toLocaleString() + ' ₽'}</b>
                  </div>
                );
              })}
              {myWorks.length === 0 && <p style={{ color: C.textMuted, textAlign: 'center', padding: '20px' }}>Работ пока нет</p>}
            </div>
          </div>
        )}

        {activePage === 'history' && (
          <MasterHistoryPage
            C={{ ...C, inp }}
            btnG={btnG}
            card={card}
            expandedProject={expandedProject}
            fileSrc={fileSrc}
            fmtMeasure={fmtMeasure}
            listSearch={listSearch}
            matchSearch={matchSearch}
            myJournal={myJournal}
            piecework={piecework}
            setExpandedProject={setExpandedProject}
            setListSearch={setListSearch}
            setShowPhotoModal={setShowPhotoModal}
            sumConfirmed={sumConfirmed}
            user={user}
          />
        )}

        {activePage === 'materials' && (
          <MasterMaterialsPage
            C={C}
            badge={badge}
            btnG={btnG}
            btnGr={btnGr}
            card={card}
            confirmMaterialReceipt={confirmMaterialReceipt}
            fmtMeasure={fmtMeasure}
            myMaterialBalances={myMaterialBalances}
            myPendingMaterialTransfers={myPendingMaterialTransfers}
            myTools={myTools}
            returnMaterialToProject={returnMaterialToProject}
            toNum={toNum}
          />
        )}

        {activePage === 'cable' && (
          <MasterCablePage
            API={API}
            C={{ ...C, inp }}
            btnB={btnB}
            btnO={btnO}
            buildCableJournalContent={buildCableJournalContent}
            cableJournal={cableJournal}
            cableTypeOf={cableTypeOf}
            card={card}
            projects={projects}
            setCableJournal={props.setCableJournal}
            showPreview={showPreview}
            user={user}
          />
        )}

        {activePage === 'myexpenses' && (
          <MyExpensesPage
            C={C}
            EXPENSE_CATEGORIES={EXPENSE_CATEGORIES}
            accountablePayments={accountablePayments}
            btnO={btnO}
            card={card}
            fileSrc={fileSrc}
            ownExpenses={ownExpenses}
            projectOptions={projects}
            setReportingPayment={setReportingPayment}
            setShowOwnExpenseForm={setShowOwnExpenseForm}
            setShowPhotoModal={setShowPhotoModal}
            user={user}
          />
        )}

        {activePage === 'documents' && (
          <MasterDocumentsPage
            API={API}
            C={C}
            btnB={btnB}
            btnG={btnG}
            btnO={btnO}
            buildActContent={buildActContent}
            buildContractContent={buildContractContent}
            buildHiddenActContent={buildHiddenActContent}
            card={card}
            doPrint={doPrint}
            editingHiddenAct={props.editingAct}
            fileSrc={fileSrc}
            hiddenActs={hiddenActs}
            inp={inp}
            masterProfile={masterProfile}
            masterProfiles={masterProfiles}
            myActs={myActs}
            myContract={myContract}
            myTools={myTools}
            pdConsents={pdConsents}
            PD_CONSENT_TEXT={PD_CONSENT_TEXT}
            refreshData={props.refreshData}
            setEditingHiddenAct={setEditingAct}
            setHiddenActs={setHiddenActs}
            showPreview={showPreview}
            uploadPhoto={uploadPhoto}
            user={user}
          />
        )}

        {activePage === 'assignments' && (
          <AssignmentsPage
            C={C}
            acceptAiTask={acceptAiTask}
            aiTasks={aiTasks}
            btnB={btnB}
            btnG={btnG}
            btnO={btnO}
            btnR={btnR}
            card={card}
            closeAiTask={closeAiTask}
            createAiTask={createAiTask}
            inp={inp}
            isMobile={isMobile}
            openAiTaskAction={openAiTaskAction}
            projects={projects}
            refreshData={refreshData}
            submitAiTaskReport={submitAiTaskReport}
            uploadPhoto={uploadPhoto}
            user={user}
            users={users || []}
          />
        )}

        {activePage === 'supply' && (
          <MasterSupplyPage
            C={C}
            card={card}
            inp={inp}
            btnO={btnO}
            btnG={btnG}
            btnR={btnR}
            badge={badge}
            isMobile={isMobile}
            role={user.role}
            user={user}
            showSupplyForm={showSupplyForm}
            setShowSupplyForm={setShowSupplyForm}
            supplyRequests={supplyRequests}
            supplyTemplates={supplyTemplates}
            applySupplyTemplate={applySupplyTemplate}
            deleteSupplyTemplate={props.deleteSupplyTemplate}
            newSupplyReq={newSupplyReq}
            setNewSupplyReq={setNewSupplyReq}
            priceHints={priceHints}
            fetchPriceHint={fetchPriceHint}
            UNITS={UNITS}
            masterProjectOptions={masterProjectOptions}
            renderSupplyPlanningHint={renderSupplyPlanningHint}
            createSupplyReq={createSupplyReq}
            saveSupplyTemplate={saveSupplyTemplate}
            parseSupplyItems={parseSupplyItems}
            renderSupplyRequestOrigin={renderSupplyRequestOrigin}
            supplyRequestOrigin={supplyRequestOrigin}
            cancelSupply={props.cancelSupply}
            supplyCollapsedProjects={supplyCollapsedProjects}
            setSupplyCollapsedProjects={setSupplyCollapsedProjects}
          />
        )}

        {activePage === 'companychat' && (
          <CompanyChatPage
            C={C}
            card={card}
            inp={inp}
            btnO={btnO}
            companyMessages={companyMessages}
            user={user}
            roleColor={roleColor}
            fileSrc={fileSrc}
            setShowPhotoModal={setShowPhotoModal}
            companyChatMessage={companyChatMessage}
            setCompanyChatMessage={setCompanyChatMessage}
            uploadPhoto={uploadPhoto}
            sendCompanyChatMessage={sendCompanyChatMessage}
          />
        )}
      </div>

      <div style={{ position: 'fixed', bottom: 0, left: 0, right: 0, backgroundColor: 'white', borderTop: '1.5px solid ' + C.border, display: 'flex', justifyContent: 'flex-start', gap: '2px', padding: '10px 8px 14px', zIndex: 100, boxShadow: '0 -4px 20px rgba(0,0,0,0.06)', overflowX: 'auto' }}>
        {[
          { id: 'works', icon: <Briefcase size={22} />, label: 'Работы' },
          { id: 'assignments', icon: <ClipboardList size={22} />, label: 'Поруч.', badge: myOpenAssignmentsCount },
          { id: 'history', icon: <BarChart3 size={22} />, label: 'История' },
          { id: 'materials', icon: <Package size={22} />, label: 'Склад', badge: myPendingMaterialTransfers.length },
          { id: 'cable', icon: <ScrollText size={22} />, label: 'Кабель' },
          { id: 'supply', icon: <ShoppingCart size={22} />, label: 'Снабжение', badge: (supplyRequests || []).filter(request => (request.createdBy === user.name || request.requestedById === user.id) && request.status === 'Отклонена').length },
          { id: 'documents', icon: <FileText size={22} />, label: 'Документы' },
          { id: 'companychat', icon: <MessageSquare size={22} />, label: 'Чат' },
        ].map(item => (
          <div key={item.id} onClick={() => setActivePage(item.id)} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', cursor: 'pointer', padding: '5px 7px', borderRadius: '10px', backgroundColor: activePage === item.id ? C.accentLight : 'transparent', position: 'relative', flex: '0 0 58px' }}>
            <span style={{ color: activePage === item.id ? C.accent : C.textMuted }}>{item.icon}</span>
            <span style={{ fontSize: '10px', color: activePage === item.id ? C.accent : C.textMuted, fontWeight: activePage === item.id ? '600' : '400', marginTop: '2px', whiteSpace: 'nowrap' }}>{item.label}</span>
            {item.badge > 0 && <span style={{ position: 'absolute', top: 0, right: 3, backgroundColor: C.danger, color: 'white', borderRadius: '50%', width: '16px', height: '16px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px' }}>{item.badge}</span>}
          </div>
        ))}
        <div onClick={() => handleLogout()} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', cursor: 'pointer', padding: '5px 7px', flex: '0 0 58px' }}>
          <LogOut size={22} color={C.textMuted} />
          <span style={{ fontSize: '10px', color: C.textMuted, marginTop: '2px', whiteSpace: 'nowrap' }}>Выйти</span>
        </div>
      </div>
    </div>
  );
}
