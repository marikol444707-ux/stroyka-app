import React from 'react';
import {
  BarChart3,
  Briefcase,
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
import ImagePreviewModal from './ImagePreviewModal';
import MasterCablePage from './MasterCablePage';
import MasterDocumentsPage from './MasterDocumentsPage';
import MasterHistoryPage from './MasterHistoryPage';
import MasterMaterialsPage from './MasterMaterialsPage';
import MasterSupplyPage from './MasterSupplyPage';
import MyExpensesPage from './MyExpensesPage';
import NotificationsDropdown from './NotificationsDropdown';
import OwnExpenseFormModal from './OwnExpenseFormModal';
import PhotoAttachmentField from './PhotoAttachmentField';
import PreviewModal from './PreviewModal';
import DocumentRecognitionPanel from './DocumentRecognitionPanel';

export default function MasterCabinetPage(props) {
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
    addMasterWorks,
    appendPhotos,
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
    materialNormStatus,
    materialRowsAvailableForWork,
    materialSuggestionsForWork,
    materialTransfers,
    myNotifications,
    navigateTo,
    newOwnExpense,
    newSupplyReq,
    normalizeMeasure,
    notifications,
    notify,
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
    submitEstimateWorkDone,
    supplyCollapsedProjects,
    supplyRequestOrigin,
    supplyRequests,
    supplyTemplates,
    toNum,
    toggleNotifications,
    tools,
    unreadNotifications,
    updateEstimateWorkMaterialQty,
    updateSelectedWorkMaterialQty,
    uploadPhoto,
    upsertEstimateWorkMaterial,
    upsertSelectedWorkMaterial,
    user,
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
  const visibleEstimatesList = typeof visibleEstimatesForCurrentUser === 'function'
    ? visibleEstimatesForCurrentUser(estimatesList || [])
    : (estimatesList || []);
  const selectedProjectHasActiveCustomerEstimate = !!selectedMasterProject && visibleEstimatesList.some(estimate =>
    (estimate.projectName || estimate.project_name) === selectedMasterProject.name &&
    String(estimate.status || 'Активная').toLowerCase() === 'активная' &&
    String(estimate.smetaType || estimate.smeta_type || 'Заказчик') === 'Заказчик'
  );
  const userAssignedPackages = Array.isArray(user?.assignedPackages)
    ? user.assignedPackages.filter(Boolean)
    : (Array.isArray(user?.assigned_packages) ? user.assigned_packages.filter(Boolean) : []);
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

            <div style={{ ...card, padding: '20px', marginBottom: '15px' }}>
              <h4 style={{ marginBottom: '15px', color: C.text, fontSize: '14px', fontWeight: '600' }}>Добавить работы</h4>
              {masterProjectOptions.length === 0 && <div style={{ padding: '12px', backgroundColor: C.warningLight, border: '1.5px solid ' + C.warningBorder, borderRadius: '10px', color: C.text, fontSize: '12px', marginBottom: '10px' }}>Нет доступных объектов. Назначьте мастера на объект или привяжите его к договору бригады.</div>}
              <select
                value={masterProjectId}
                onChange={async e => {
                  const projectId = e.target.value;
                  setMasterProjectId(projectId);
                  setSelectedWorks({});
                  const project = masterProjectOptions.find(item => item.id === Number(projectId)) || projects.find(item => item.id === Number(projectId));
                  if (project && project.pricelistId) await loadPricelistItems(project.pricelistId);
                  else loadPricelistItems && loadPricelistItems(null);
                }}
                style={inp}
                disabled={masterProjectOptions.length === 0}
              >
                <option value="">{masterProjectOptions.length ? 'Выберите объект' : 'Нет доступных объектов'}</option>
                {masterProjectOptions.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}
              </select>
              {masterProjectId && (
                <>
                  {pricelistItems.length === 0 && !selectedProjectHasActiveCustomerEstimate && <p style={{ color: C.textMuted, textAlign: 'center', padding: '20px' }}>Прайс-лист не привязан к проекту</p>}
                  {activePage === 'works' && null}
                  {/* Содержимое списка работ оставлено в компоненте, но в отдельном файле — это и есть текущий шаг рефакторинга. */}
                </>
              )}
              {masterProjectId && (() => {
                const projectName = projects.find(project => project.id === Number(masterProjectId))?.name || '';
                const projectEstimates = visibleEstimatesList.filter(estimate => (estimate.projectName || estimate.project_name) === projectName);
                const assignedContractItems = Array.isArray(brigadeContractItems) ? brigadeContractItems : [];
                const myItems = [];
                projectEstimates.forEach(estimate => (estimate.sections || []).forEach((section, sectionIndex) => (section.items || []).forEach((item, itemIndex) => {
                  if (!estimateIsActive(estimate) || estimateItemIsMaterial(item)) return;
                  const packageAllowed = userAssignedPackages.length > 0 && userAssignedPackages.includes(estimatePackageName(estimate));
                  const namedToMe = item.brigadeName && (item.brigadeName === user.name || (user.brigade && item.brigadeName === user.brigade));
                  const itemKey = String(estimateItemKeyForRow(estimate, sectionIndex, itemIndex, item) || '').trim();
                  const itemName = String(item.name || '').trim().toLowerCase();
                  const sectionName = String(section.name || '').trim().toLowerCase();
                  const itemUnit = String(item.unit || '').trim().toLowerCase();
                  const assignedContractItem = assignedContractItems.find(contractItem => {
                    const contractKey = String(contractItem.estimateItemKey || contractItem.estimate_item_key || '').trim();
                    const contractName = String(contractItem.name || contractItem.description || '').trim().toLowerCase();
                    const contractUnit = String(contractItem.unit || '').trim().toLowerCase();
                    const contractSection = String(contractItem.estimateSection || contractItem.estimate_section || '').trim().toLowerCase();
                    const contractProject = String(contractItem.projectName || contractItem.project_name || '').trim();
                    const contractPackage = String(contractItem.workPackage || contractItem.work_package || '').trim();
                    const sameProject = !contractProject || contractProject === projectName;
                    const samePackage = contractPackage && contractPackage === estimatePackageName(estimate);
                    const sameKey = itemKey && contractKey && contractKey === itemKey;
                    const sameName = contractName && contractName === itemName && (!contractSection || !sectionName || contractSection === sectionName) && (!itemUnit || !contractUnit || contractUnit === itemUnit);
                    return sameProject && samePackage && (sameKey || sameName);
                  });
                  if ((assignedContractItems.length > 0 && assignedContractItem) || (assignedContractItems.length === 0 && (packageAllowed || namedToMe))) {
                    myItems.push({
                      ...item,
                      estId: estimate.id,
                      estName: estimate.name,
                      workPackage: estimatePackageName(estimate),
                      sectionIdx: sectionIndex,
                      itemIdx: itemIndex,
                      section: section.name,
                      estimateItemKey: itemKey,
                      contractItemId: assignedContractItem?.id || null,
                      executionPricePerUnit: assignedContractItem?.priceBrigade || item.executionPricePerUnit,
                    });
                  }
                })));
                if (myItems.length === 0) {
                  if (!projectEstimates.some(estimate => estimateIsActive(estimate))) return null;
                  return (
                    <div style={{ ...card, padding: '14px', marginBottom: '15px', backgroundColor: C.warningLight, border: '1.5px solid ' + C.warningBorder }}>
                      <b style={{ color: C.warning, fontSize: '13px' }}>Работы по смете еще не назначены</b>
                      <p style={{ color: C.textSec, margin: '5px 0 0', fontSize: '12px' }}>После выдачи работ мастеру здесь появятся объемы, цены исполнителя и кнопка отправки в ЖПР.</p>
                    </div>
                  );
                }
                return (
                  <div style={{ ...card, padding: '14px', marginBottom: '15px', backgroundColor: C.accentLight, border: '1.5px solid ' + C.accentBorder }}>
                    <b style={{ color: C.accent, fontSize: '13px', display: 'block', marginBottom: '10px' }}>🎯 Мои работы по смете ({myItems.length})</b>
                    {myItems.map((item, index) => {
                      const quantity = Number(item.quantity) || 0;
                      const done = Number(item.doneQuantity) || 0;
                      const remain = Math.max(0, quantity - done);
                      const doneNorm = normalizeMeasure(done, item.unit);
                      const workKey = estimateWorkKey(item.estId, item.sectionIdx, item.itemIdx);
                      const params = estimateWorkParams[workKey] || {};
                      const draft = estimateDoneDrafts[workKey] !== undefined ? estimateDoneDrafts[workKey] : (doneNorm.qty || '');
                      const rawDraft = denormalizeMeasure(draft, item.unit);
                      const delta = Math.max(0, rawDraft - done);
                      const project = projects.find(projectRow => projectRow.id === Number(masterProjectId));
                      const roomCheck = project ? roomMeasurementCheck(project.name, params.roomId, params.surface || 'Стены', delta, item.unit, item.name) : null;
                      const projectMaterials = project ? materialRowsAvailableForWork(project.name, item.workPackage) : [];
                      const availableMap = project ? materialAvailabilityMapForWork(project.name, item.workPackage) : {};
                      const usedMaterials = estimateWorkMaterials[workKey] || [];
                      const usedMap = {};
                      usedMaterials.forEach(material => { usedMap[materialNameKey(material.name)] = material; });
                      const suggestions = project ? materialSuggestionsForWork(project.name, item.name, item.section, item.workPackage) : [];
                      const executionUnitPrice = Number(item.executionPricePerUnit || item.internalPricePerUnit || item.masterPricePerUnit || item.contractorPricePerUnit || 0);
                      const deltaEarning = Math.round(delta * executionUnitPrice);
                      const missingExecutionPrice = executionUnitPrice <= 0;
                      return (
                        <div key={index} style={{ padding: '10px', marginBottom: '6px', backgroundColor: C.bgWhite, borderRadius: '8px', border: '1px solid ' + C.border }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }}>
                            <div style={{ flex: 1 }}>
                              <b style={{ fontSize: '12px', color: C.text }}>{item.name}</b>
                              <p style={{ color: C.textSec, margin: '2px 0', fontSize: '11px' }}>{item.section + ' · план ' + fmtMeasure(quantity, item.unit) + ' · сделано ' + fmtMeasure(done, item.unit) + ' · осталось ' + fmtMeasure(remain, item.unit)}</p>
                            </div>
                            <input
                              type="number"
                              step="any"
                              inputMode="decimal"
                              placeholder={'+' + (normalizeMeasure(1, item.unit).unit || item.unit)}
                              value={draft}
                              onChange={e => {
                                const value = e.target.value;
                                setEstimateDoneDrafts(prev => ({ ...prev, [workKey]: value }));
                                const raw = denormalizeMeasure(value, item.unit);
                                const nextDelta = Math.max(0, raw - done);
                                if (project) {
                                  const currentParams = estimateWorkParams[workKey] || {};
                                  setEstimateWorkMaterials(prev => ({ ...prev, [workKey]: props.autoFillNormMaterialsForWork(project.name, item.name, item.section, nextDelta, item.unit, prev[workKey] || [], currentParams) }));
                                }
                              }}
                              style={{ ...inp, marginBottom: 0, width: '80px', fontSize: '12px', padding: '4px 6px' }}
                            />
                            {props.workNeedsThicknessParam(item.name, item.section) && (
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
                                  if (project) {
                                    setEstimateWorkMaterials(prev => ({ ...prev, [workKey]: props.autoFillNormMaterialsForWork(project.name, item.name, item.section, delta, item.unit, prev[workKey] || [], nextParams) }));
                                  }
                                }}
                                style={{ ...inp, marginBottom: 0, width: '78px', fontSize: '12px', padding: '4px 6px' }}
                              />
                            )}
                            <span style={{ fontSize: '11px', color: missingExecutionPrice ? C.warning : C.success, fontWeight: '600', whiteSpace: 'nowrap' }}>{missingExecutionPrice ? 'цена не назначена' : deltaEarning.toLocaleString('ru-RU') + ' ₽'}</span>
                            <button onClick={() => submitEstimateWorkDone(item, draft)} disabled={delta <= 0 || missingExecutionPrice} style={{ ...(!missingExecutionPrice && delta > 0 ? btnO : btnG), padding: '5px 9px', fontSize: '11px', opacity: (!missingExecutionPrice && delta > 0) ? 1 : 0.65 }}>
                              Отправить
                            </button>
                          </div>
                          {projectRooms.length > 0 && (
                            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 150px', gap: '6px', marginTop: '8px' }}>
                              <select value={params.roomId || ''} onChange={e => { const room = projectRooms.find(roomItem => Number(roomItem.id) === Number(e.target.value)); setEstimateWorkParams(prev => ({ ...prev, [workKey]: { ...(prev[workKey] || {}), roomId: e.target.value, roomName: room?.name || '' } })); }} style={{ ...inp, marginBottom: 0, fontSize: '11px', padding: '6px 8px' }}>
                                <option value="">Помещение по обмеру</option>
                                {projectRooms.map(room => <option key={room.id} value={room.id}>{room.name}</option>)}
                              </select>
                              <select value={params.surface || 'Стены'} onChange={e => setEstimateWorkParams(prev => ({ ...prev, [workKey]: { ...(prev[workKey] || {}), surface: e.target.value } }))} style={{ ...inp, marginBottom: 0, fontSize: '11px', padding: '6px 8px' }}>
                                {SURFACES.map(surface => <option key={surface}>{surface}</option>)}
                              </select>
                            </div>
                          )}
                          {roomCheck && <div style={{ marginTop: '6px', padding: '7px 9px', borderRadius: '8px', border: '1px solid ' + (roomCheck.over > 0 ? C.dangerBorder : C.successBorder), backgroundColor: roomCheck.over > 0 ? C.dangerLight : C.successLight, color: roomCheck.over > 0 ? C.danger : C.success, fontSize: '11px', fontWeight: '600' }}>{roomMeasurementMessage(roomCheck)}</div>}
                          <div style={{ marginTop: '8px' }}>
                            <PhotoAttachmentField
                              C={C}
                              btnG={btnG}
                              value={params.photoUrl || ''}
                              onChange={photoUrl => setEstimateWorkParams(prev => ({ ...prev, [workKey]: { ...(prev[workKey] || {}), photoUrl } }))}
                              appendPhotos={appendPhotos}
                              fileSrc={fileSrc}
                              setShowPhotoModal={setShowPhotoModal}
                              projectName={project?.name || projectName}
                              context="work-journal"
                              title="Фото работы / помещения"
                              compact
                            />
                          </div>
                          {project && (
                            <div style={{ marginTop: '8px', padding: '8px', backgroundColor: C.bg, borderRadius: '8px', border: '1px solid ' + C.border }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'center', marginBottom: '6px' }}>
                                <b style={{ fontSize: '11px', color: C.text }}>📦 Материалы к списанию</b>
                                <span style={{ fontSize: '10px', color: C.textSec }}>{delta > 0 ? 'новый объём: ' + fmtMeasure(delta, item.unit) : 'сначала укажите новый объём'}</span>
                              </div>
                              {suggestions.length > 0 && (
                                <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap', marginBottom: '6px' }}>
                                  {suggestions.slice(0, 6).map(suggestion => {
                                    const key = materialNameKey(suggestion.name);
                                    const checked = !!usedMap[key];
                                    const available = availableMap[key];
                                    const unit = available?.unit || suggestion.unit || 'шт';
                                    const hasStock = toNum(available?.quantity) > 0;
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
                                        {(checked ? '✓ ' : '') + suggestion.name + (norm ? ' · норма ' + fmtMeasure(norm.quantity, unit) + (writeQty && toNum(writeQty) < toNum(norm.quantity) ? ' · доступно ' + fmtMeasure(writeQty, unit) : '') : (hasStock ? ' · ' + fmtMeasure(available.quantity, available.unit) : ''))}
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
                                    const stock = toNum(material.quantity);
                                    const norm = materialNormForWork(project.name, item.name, item.section, delta, item.unit, material, estimateWorkParams[workKey] || {});
                                    const normStatus = checked ? materialNormStatus(selected) : null;
                                    const over = checked && toNum(selected.quantity) > stock;
                                    return (
                                      <div key={material.id} style={{ display: 'grid', gridTemplateColumns: '18px minmax(0,1fr) auto', gap: '6px', alignItems: 'center', fontSize: '11px', padding: '5px 6px', border: '1px solid ' + (over ? C.dangerBorder : checked ? C.accentBorder : C.border), borderRadius: '7px' }}>
                                        <input type="checkbox" checked={checked} onChange={e => e.target.checked ? upsertEstimateWorkMaterial(workKey, { name: material.name, unit: material.unit || 'шт', workPackage: item.workPackage || '', autoNorm: !!norm, normQuantity: norm?.normQuantity || '', normSource: norm?.normSource || '', normRuleId: norm?.ruleId || '', normThicknessMm: estimateWorkParams[workKey]?.thicknessMm || '' }, norm ? capMaterialWriteoffQty(project.name, material.name, norm.quantity, item.workPackage) : '') : removeEstimateWorkMaterial(workKey, material.name)} style={{ width: '14px', height: '14px', accentColor: C.accent }} />
                                        <span style={{ color: C.text, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                          {material.name}
                                          <span style={{ color: over ? C.danger : C.textSec }}>
                                            {' · доступно ' + fmtMeasure(stock, material.unit)}
                                            {hint?.used > 0 ? ' · списано ' + fmtMeasure(hint.used, hint.unit) : ''}
                                            {norm ? ' · норма ' + fmtMeasure(norm.quantity, norm.unit) : ''}
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
                      );
                    })}
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
                                  onChange={e => {
                                    const value = e.target.value;
                                    setSelectedWorks(prev => {
                                      const current = prev[item.id] || { materials: [] };
                                      const base = { ...current, quantity: value };
                                      const materials = project ? props.autoFillNormMaterialsForWork(project.name, item.name, category, toNum(value), item.unit, base.materials || [], base) : base.materials;
                                      return { ...prev, [item.id]: { ...base, materials } };
                                    });
                                  }}
                                  style={inp}
                                />
                                {props.workNeedsThicknessParam(item.name, category) && (
                                  <input
                                    placeholder="Толщина слоя, мм"
                                    type="number"
                                    step="any"
                                    inputMode="decimal"
                                    value={selectedWorks[item.id]?.thicknessMm || ''}
                                    onChange={e => {
                                      const value = e.target.value;
                                      setSelectedWorks(prev => {
                                        const current = prev[item.id] || { materials: [] };
                                        const base = { ...current, thicknessMm: value };
                                        const materials = project ? props.autoFillNormMaterialsForWork(project.name, item.name, category, toNum(base.quantity), item.unit, base.materials || [], base) : base.materials;
                                        return { ...prev, [item.id]: { ...base, materials } };
                                      });
                                    }}
                                    style={inp}
                                  />
                                )}
                                {projectRooms.length > 0 && (
                                  <>
                                    <select value={selectedWorks[item.id]?.roomId || ''} onChange={e => { const room = projectRooms.find(roomItem => roomItem.id === Number(e.target.value)); setSelectedWorks(prev => ({ ...prev, [item.id]: { ...prev[item.id], roomId: e.target.value, roomName: room?.name || '' } })); }} style={inp}>
                                      <option value="">Выберите помещение</option>
                                      {projectRooms.map(room => <option key={room.id} value={room.id}>{room.name}</option>)}
                                    </select>
                                    <select value={selectedWorks[item.id]?.surface || 'Стены'} onChange={e => setSelectedWorks(prev => ({ ...prev, [item.id]: { ...prev[item.id], surface: e.target.value } }))} style={inp}>
                                      {SURFACES.map(surface => <option key={surface}>{surface}</option>)}
                                    </select>
                                  </>
                                )}
                                {(() => {
                                  const check = project ? roomMeasurementCheck(project.name, selectedWorks[item.id]?.roomId, selectedWorks[item.id]?.surface || 'Стены', selectedWorks[item.id]?.quantity, item.unit, item.name) : null;
                                  return check ? <div style={{ marginBottom: '8px', padding: '8px 10px', borderRadius: '8px', border: '1px solid ' + (check.over > 0 ? C.dangerBorder : C.successBorder), backgroundColor: check.over > 0 ? C.dangerLight : C.successLight, color: check.over > 0 ? C.danger : C.success, fontSize: '11px', fontWeight: '600' }}>{roomMeasurementMessage(check)}</div> : null;
                                })()}
                                <input placeholder="Комментарий" value={selectedWorks[item.id]?.comment || ''} onChange={e => setSelectedWorks(prev => ({ ...prev, [item.id]: { ...prev[item.id], comment: e.target.value } }))} style={inp} />
                                <PhotoAttachmentField
                                  C={C}
                                  btnG={btnG}
                                  value={selectedWorks[item.id]?.photoUrl || ''}
                                  onChange={photoUrl => setSelectedWorks(prev => ({ ...prev, [item.id]: { ...prev[item.id], photoUrl } }))}
                                  appendPhotos={appendPhotos}
                                  fileSrc={fileSrc}
                                  setShowPhotoModal={setShowPhotoModal}
                                  projectName={project?.name || ''}
                                  context="work-journal"
                                  title="Фото работы / помещения"
                                />
                                {(() => {
                                  const scopedPackage = userAssignedPackages.length === 1 ? userAssignedPackages[0] : '';
                                  const projectMaterials = project ? materialRowsAvailableForWork(project.name, scopedPackage) : [];
                                  const availableMap = project ? materialAvailabilityMapForWork(project.name, scopedPackage) : {};
                                  const usedMaterials = selectedWorks[item.id]?.materials || [];
                                  const usedMap = {};
                                  usedMaterials.forEach(material => { usedMap[materialNameKey(material.name)] = material; });
                                  if (!project) return null;
                                  const suggestions = materialSuggestionsForWork(project.name, item.name, category, scopedPackage);
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
                                            const hasStock = toNum(available?.quantity) > 0;
                                            const status = materialControlStatus(suggestion);
                                            const unit = available?.unit || suggestion.unit || 'шт';
                                            const norm = materialNormForWork(project.name, item.name, category, toNum(selectedWorks[item.id]?.quantity), item.unit, { name: suggestion.name, unit }, selectedWorks[item.id] || {});
                                            const writeQty = norm ? capMaterialWriteoffQty(project.name, suggestion.name, norm.quantity, scopedPackage) : '';
                                            return (
                                              <button
                                                type="button"
                                                key={'sug-' + key}
                                                disabled={!hasStock}
                                                onClick={() => checked ? removeSelectedWorkMaterial(item.id, suggestion.name) : upsertSelectedWorkMaterial(item.id, { name: suggestion.name, unit, workPackage: scopedPackage || '', autoNorm: !!norm, normQuantity: norm?.normQuantity || '', normSource: norm?.normSource || '', normRuleId: norm?.ruleId || '', normThicknessMm: selectedWorks[item.id]?.thicknessMm || '' }, writeQty)}
                                                style={{ padding: '5px 8px', borderRadius: '8px', border: '1px solid ' + (checked ? C.accentBorder : status.border), backgroundColor: checked ? C.accentLight : status.bg, color: hasStock ? (checked ? C.accent : status.color) : C.textMuted, cursor: hasStock ? 'pointer' : 'not-allowed', fontSize: '10px', fontWeight: '600' }}
                                              >
                                                {(checked ? '✓ ' : '') + suggestion.name + ' · ' + (norm ? 'норма ' + fmtMeasure(norm.quantity, unit) + (writeQty && toNum(writeQty) < toNum(norm.quantity) ? ' · доступно ' + fmtMeasure(writeQty, unit) : '') : (hasStock ? 'доступно ' + fmtMeasure(available.quantity, available.unit) : isPersonalMaterialRole() ? 'не выдано мне' : 'нет на объекте'))}
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
                                            const stock = toNum(material.quantity);
                                            const norm = materialNormForWork(project.name, item.name, category, toNum(selectedWorks[item.id]?.quantity), item.unit, material, selectedWorks[item.id] || {});
                                            const normStatus = checked ? materialNormStatus(selected) : null;
                                            const over = checked && toNum(selected.quantity) > stock;
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
                                                  <div style={{ color: over ? C.danger : C.textSec, marginTop: '2px' }}>{'доступно ' + fmtMeasure(stock, material.unit)}{norm ? ' · норма ' + fmtMeasure(norm.quantity, norm.unit) : ''}{hint?.planQty > 0 ? ' · по смете ' + fmtMeasure(hint.planQty, hint.unit) : ''}{hint?.used > 0 ? ' · списано ' + fmtMeasure(hint.used, hint.unit) : ''}</div>
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
                      <p style={{ color: C.textSec, margin: '3px 0', fontSize: '12px' }}>{fmtMeasure(work.quantity, work.unit) + ' · ' + work.project + ' · ' + work.date}</p>
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
