import React from 'react';
import { AlertTriangle, Building2, Check, ClipboardList, Edit2, FileText, Filter, Plus, Search, Trash2, Upload, UserCheck, Users, X } from 'lucide-react';
import DocumentRecognitionPanel from '../../components/DocumentRecognitionPanel';
import PhotoAttachmentField from '../../components/PhotoAttachmentField';

const EMPTY_LEAD = {
  name: '',
  phone: '',
  email: '',
  source: '',
  budget: '',
  notes: '',
  stage: 'Новый',
  photoUrl: '',
  leadType: 'Клиент',
  counterpartyType: '',
  responsibleName: '',
  nextContactAt: '',
  address: '',
  workType: '',
  area: '',
  priority: 'Обычный',
  lossReason: '',
  legalForm: '',
  passportData: '',
  inn: '',
  kpp: '',
  ogrn: '',
  legalAddress: '',
  contractSubject: '',
  bank: '',
  bik: '',
  bankAccount: '',
  corrAccount: '',
  signerName: '',
  signerBasis: '',
  documentStatus: 'Не собраны',
  reviewStatus: 'Новая',
};

const LEAD_TYPES = ['Клиент', 'Поставщик', 'Мастер', 'Бригадир', 'Субподрядчик', 'Партнер', 'Другое'];
const LEGAL_FORMS = ['', 'Физлицо', 'Самозанятый', 'ИП', 'Юрлицо'];
const PRIORITIES = ['Низкий', 'Обычный', 'Высокий', 'Срочно'];
const DOCUMENT_TYPES = ['Смета', 'КП', 'Договор', 'Реквизиты', 'Паспортные данные', 'ТЗ / обмеры', 'Доверенность', 'Прочее'];

const field = (inp) => ({ ...inp, marginBottom: 0, width: '100%', minWidth: 0, boxSizing: 'border-box' });
const safeList = (value) => Array.isArray(value) ? value : [];

export default function CrmPage({
  API,
  C,
  CRM_STAGES,
  btnG,
  btnB,
  btnO,
  btnR,
  card,
  createProjectFromLead,
  deleteLead,
  editingItem,
  inp,
  leads,
  newLead,
  saveLead,
  setEditingItem,
  setLeads,
  setNewLead,
  setShowForm,
  showForm,
  isMobile = false,
  appendPhotos,
  uploadPhoto,
  fileSrc,
  setShowPhotoModal,
  users = [],
}) {
  const [details, setDetails] = React.useState({ documents: [], tasks: [] });
  const [detailsLoading, setDetailsLoading] = React.useState(false);
  const [documentForm, setDocumentForm] = React.useState({ docType: 'Договор', title: '', status: 'Загружен', number: '', docDate: '', confidential: false, notes: '', fileUrl: '' });
  const [taskForm, setTaskForm] = React.useState({ title: '', dueDate: '', assignedTo: '', notes: '' });
  const [inviteResult, setInviteResult] = React.useState(null);
  const [filters, setFilters] = React.useState({ search: '', leadType: '', responsibleName: '', attention: '' });
  const [saving, setSaving] = React.useState(false);
  const compact = isMobile || (typeof window !== 'undefined' && window.innerWidth <= 1100);
  const today = React.useMemo(() => new Date().toISOString().slice(0, 10), []);

  const isPastDue = React.useCallback((dateValue) => {
    const value = String(dateValue || '').slice(0, 10);
    return Boolean(value && value < today);
  }, [today]);

  const isDueToday = React.useCallback((dateValue) => {
    const value = String(dateValue || '').slice(0, 10);
    return Boolean(value && value === today);
  }, [today]);

  const reloadLeads = React.useCallback(async () => {
    if (!API || !setLeads) return;
    const rows = await fetch(API + '/crm/lead-summaries').then(r => r.json()).catch(() => []);
    setLeads(Array.isArray(rows) ? rows : []);
  }, [API, setLeads]);

  const loadDetails = React.useCallback(async (leadId) => {
    if (!API || !leadId) {
      setDetails({ documents: [], tasks: [] });
      return;
    }
    setDetailsLoading(true);
    const data = await fetch(API + '/crm/leads/' + leadId + '/details').then(r => r.ok ? r.json() : null).catch(() => null);
    setDetails({
      documents: safeList(data?.documents),
      tasks: safeList(data?.tasks),
    });
    setDetailsLoading(false);
  }, [API]);

  const startNew = () => {
    setShowForm(!showForm);
    setEditingItem(null);
    setNewLead(EMPTY_LEAD);
    setDetails({ documents: [], tasks: [] });
  };

  const editLead = (lead) => {
    setEditingItem(lead);
    setNewLead({ ...EMPTY_LEAD, ...lead });
    setShowForm(true);
    loadDetails(lead.id);
    setInviteResult(null);
  };

  const saveCurrentLead = async () => {
    if (!newLead?.name) return alert('Укажите имя / название заявки');
    setSaving(true);
    await saveLead(editingItem ? { ...newLead, id: editingItem.id } : newLead);
    await reloadLeads();
    setSaving(false);
    setShowForm(false);
    setEditingItem(null);
    setDetails({ documents: [], tasks: [] });
  };

  const removeLead = async (id) => {
    await deleteLead(id);
    await reloadLeads();
  };

  const uploadCrmDocument = async (file) => {
    if (!file || !editingItem?.id) return;
    if (!uploadPhoto) return alert('Загрузка файлов недоступна');
    const url = await uploadPhoto(file, { projectName: newLead.name || 'CRM', context: 'crm-documents' });
    if (!url) return;
    const payload = {
      ...documentForm,
      fileUrl: url,
      title: documentForm.title || file.name,
    };
    const res = await fetch(API + '/crm/leads/' + editingItem.id + '/documents', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      return alert(data.detail || 'Не удалось загрузить документ CRM');
    }
    setDocumentForm({ docType: 'Договор', title: '', status: 'Загружен', number: '', docDate: '', confidential: false, notes: '', fileUrl: '' });
    await loadDetails(editingItem.id);
    await reloadLeads();
  };

  const deleteCrmDocument = async (docId) => {
    await fetch(API + '/crm/documents/' + docId, { method: 'DELETE' });
    await loadDetails(editingItem.id);
    await reloadLeads();
  };

  const createRecognizedCrmDocument = async (docPatch) => {
    if (!editingItem?.id) return alert('Сначала сохраните карточку CRM');
    const res = await fetch(API + '/crm/leads/' + editingItem.id + '/documents', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(docPatch),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return alert(data.detail || 'Не удалось добавить распознанный документ');
    await loadDetails(editingItem.id);
    await reloadLeads();
  };

  const createTask = async () => {
    if (!editingItem?.id || !taskForm.title) return;
    const res = await fetch(API + '/crm/leads/' + editingItem.id + '/tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(taskForm),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      return alert(data.detail || 'Не удалось создать задачу');
    }
    setTaskForm({ title: '', dueDate: '', assignedTo: '', notes: '' });
    await loadDetails(editingItem.id);
    await reloadLeads();
  };

  const closeTask = async (task) => {
    await fetch(API + '/crm/tasks/' + task.id, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...task, status: 'Закрыта' }),
    });
    await loadDetails(editingItem.id);
    await reloadLeads();
  };

  const approveSupplier = async (lead) => {
    const res = await fetch(API + '/crm/leads/' + lead.id + '/approve-supplier', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return alert(data.detail || 'Не удалось одобрить поставщика');
    await reloadLeads();
    alert('Поставщик создан/связан. Дальше отправьте ему приглашение из раздела снабжения.');
  };

  const approveWorker = async (lead, role) => {
    const res = await fetch(API + '/crm/leads/' + lead.id + '/approve-worker', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return alert(data.detail || 'Не удалось одобрить исполнителя');
    await reloadLeads();
    alert('Исполнитель создан/связан. Дальше выдайте доступ через приглашение.');
  };

  const createInviteForLead = async (lead) => {
    if (!lead?.id) return;
    const role = {
      'Поставщик': 'поставщик',
      'Мастер': 'мастер',
      'Бригадир': 'бригадир',
      'Субподрядчик': 'субподрядчик',
      'Клиент': 'заказчик',
    }[lead.leadType] || '';
    if (!role) return alert('Для этого типа заявки роль приглашения не определена');
    let projectName = '';
    let assignedPackages = [];
    if (['мастер', 'бригадир', 'субподрядчик', 'заказчик'].includes(role)) {
      projectName = window.prompt('Объект для доступа:', '') || '';
      if (!projectName && role !== 'заказчик') return;
    }
    if (['мастер', 'бригадир', 'субподрядчик'].includes(role)) {
      const pkg = window.prompt('Пакет работ / раздел сметы:', lead.workType || lead.counterpartyType || 'Основная') || '';
      if (!pkg) return;
      assignedPackages = [pkg];
    }
    const res = await fetch(API + '/crm/leads/' + lead.id + '/create-invite', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        role,
        projectName,
        assignedProjects: projectName ? [projectName] : [],
        assignedPackages,
        expiresInDays: 14,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return alert(data.detail || 'Не удалось создать приглашение');
    const link = data.link && data.link.startsWith('/') ? window.location.origin + data.link : data.link;
    setInviteResult({ ...data, link });
    await reloadLeads();
  };

  const transferDocumentsToProject = async (lead) => {
    if (!lead?.id) return;
    const projectName = lead.projectId ? '' : (window.prompt('Название объекта:', lead.name || '') || '');
    if (!lead.projectId && !projectName) return;
    const res = await fetch(API + '/crm/leads/' + lead.id + '/transfer-documents-to-project', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ projectName }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return alert(data.detail || 'Не удалось передать документы в объект');
    await loadDetails(lead.id);
    await reloadLeads();
    alert('Передано документов: ' + (data.created || []).length + (data.skipped?.length ? ', уже были: ' + data.skipped.length : ''));
  };

  const allLeads = safeList(leads);
  const attentionForLead = React.useCallback((lead) => ({
    overdue: isPastDue(lead.nextContactAt) || isPastDue(lead.nextTaskDueDate),
    today: isDueToday(lead.nextContactAt) || isDueToday(lead.nextTaskDueDate),
    noResponsible: !String(lead.responsibleName || '').trim(),
    noDocuments: Number(lead.documentsCount || 0) === 0 && !['Отказ', 'Новый'].includes(lead.stage || ''),
    openTasks: Number(lead.openTasksCount || 0) > 0,
  }), [isDueToday, isPastDue]);

  const filteredLeads = React.useMemo(() => {
    const query = filters.search.trim().toLowerCase();
    return allLeads.filter(lead => {
      if (filters.leadType && lead.leadType !== filters.leadType) return false;
      if (filters.responsibleName && (lead.responsibleName || '') !== filters.responsibleName) return false;
      const attention = attentionForLead(lead);
      if (filters.attention && !attention[filters.attention]) return false;
      if (!query) return true;
      return [
        lead.name, lead.phone, lead.email, lead.source, lead.address,
        lead.workType, lead.responsibleName, lead.notes, lead.stage,
      ].some(value => String(value || '').toLowerCase().includes(query));
    });
  }, [allLeads, attentionForLead, filters]);

  const responsibleOptions = React.useMemo(
    () => [...new Set(allLeads.map(lead => lead.responsibleName).filter(Boolean))].sort(),
    [allLeads],
  );

  const summary = React.useMemo(() => {
    const openStages = new Set(['Новый', 'На проверке', 'Квалификация', 'Замер / ТЗ', 'Смета / КП', 'Договор']);
    const open = allLeads.filter(lead => openStages.has(lead.stage || 'Новый'));
    const overdue = allLeads.filter(lead => attentionForLead(lead).overdue);
    const todayRows = allLeads.filter(lead => attentionForLead(lead).today);
    const noResponsible = allLeads.filter(lead => attentionForLead(lead).noResponsible && (lead.stage || '') !== 'Отказ');
    const budget = open.reduce((sum, lead) => sum + Number(lead.budget || 0), 0);
    return {
      total: allLeads.length,
      visible: filteredLeads.length,
      open: open.length,
      overdue: overdue.length,
      today: todayRows.length,
      noResponsible: noResponsible.length,
      budget,
    };
  }, [allLeads, attentionForLead, filteredLeads.length]);

  const grouped = React.useMemo(() => {
    const map = new Map((CRM_STAGES || []).map(stage => [stage, []]));
    filteredLeads.forEach(lead => {
      const stage = lead.stage || 'Новый';
      if (!map.has(stage)) map.set(stage, []);
      map.get(stage).push(lead);
    });
    return map;
  }, [CRM_STAGES, filteredLeads]);

  const stageColor = (stage) => {
    if (stage === 'Отказ') return [C.danger, C.dangerLight, C.dangerBorder];
    if (stage === 'Договор' || stage === 'Передан в объект') return [C.success, C.successLight, C.successBorder];
    if (stage.includes('Одобрен')) return [C.info || C.accent, C.infoLight || C.accentLight, C.infoBorder || C.accentBorder || C.border];
    return [C.text, C.bg, C.border];
  };

  const renderLeadCard = (lead) => {
    const photos = String(lead.photoUrl || lead.photo_url || '').split(',').map(x => x.trim()).filter(Boolean);
    const isSupplier = lead.leadType === 'Поставщик';
    const isWorker = ['Мастер', 'Бригадир', 'Субподрядчик'].includes(lead.leadType);
    const attention = attentionForLead(lead);
    const borderColor = attention.overdue ? C.danger : attention.today ? C.warning : C.accent;
    return (
      <article key={lead.id} style={{ ...card, padding: compact ? '12px' : '14px', borderLeft: '3px solid ' + borderColor, marginBottom: '10px', overflow: 'hidden' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'flex-start' }}>
          <div style={{ minWidth: 0 }}>
            <b style={{ color: C.text, fontSize: '14px', display: 'block', overflowWrap: 'anywhere' }}>{lead.name || 'Без названия'}</b>
            <p style={{ color: C.textSec, margin: '4px 0 0', fontSize: '12px', overflowWrap: 'anywhere' }}>
              {[lead.phone, lead.email].filter(Boolean).join(' · ') || 'Контакт не указан'}
            </p>
          </div>
          <span style={{ flex: '0 0 auto', color: C.accent, backgroundColor: C.accentLight, border: '1px solid ' + C.accentBorder, borderRadius: '999px', padding: '3px 7px', fontSize: '10px', fontWeight: 700 }}>
            {lead.leadType || 'Клиент'}
          </span>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px', marginTop: '8px' }}>
          {lead.source && <span style={miniBadge(C.textSec, C.bg, C.border)}>Источник: {lead.source}</span>}
          {lead.reviewStatus && <span style={miniBadge(C.info || C.accent, C.infoLight || C.accentLight, C.infoBorder || C.accentBorder || C.border)}>{lead.reviewStatus}</span>}
          {lead.documentStatus && <span style={miniBadge(C.warning, C.warningLight, C.warningBorder)}>{lead.documentStatus}</span>}
          {Number(lead.openTasksCount || 0) > 0 && <span style={miniBadge(C.textSec, C.bg, C.border)}>Задач: {lead.openTasksCount}</span>}
          {Number(lead.documentsCount || 0) > 0 && <span style={miniBadge(C.success, C.successLight, C.successBorder)}>Док: {lead.documentsCount}</span>}
          {attention.noResponsible && <span style={miniBadge(C.warning, C.warningLight, C.warningBorder)}>без ответственного</span>}
        </div>
        {(lead.nextContactAt || lead.nextTaskDueDate) && (
          <p style={{ color: attention.overdue ? C.danger : C.warning, margin: '7px 0 0', fontSize: '12px', fontWeight: 700 }}>
            {attention.overdue && <AlertTriangle size={12} style={{ verticalAlign: '-2px', marginRight: '4px' }} />}
            {lead.nextContactAt ? 'Следующий контакт: ' + lead.nextContactAt : 'Ближайшая задача: ' + lead.nextTaskDueDate}
          </p>
        )}
        {lead.budget ? <p style={{ color: C.success, margin: '7px 0 0', fontSize: '13px', fontWeight: 800 }}>{Number(lead.budget).toLocaleString('ru-RU')} ₽</p> : null}
        {photos.length > 0 && (
          <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap', marginTop: '8px' }}>
            {photos.slice(0, 4).map((url, index) => (
              <img key={url + index} src={fileSrc ? fileSrc(url) : url} alt="" onClick={() => setShowPhotoModal && setShowPhotoModal(fileSrc ? fileSrc(url) : url)} style={{ width: '48px', height: '48px', borderRadius: '7px', objectFit: 'cover', cursor: 'pointer', border: '1px solid ' + C.border }} />
            ))}
            {photos.length > 4 && <span style={{ alignSelf: 'center', color: C.textSec, fontSize: '11px' }}>+{photos.length - 4}</span>}
          </div>
        )}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '10px' }}>
          <button onClick={() => editLead(lead)} style={{ ...btnG, padding: '6px 9px', fontSize: '11px' }}><Edit2 size={12} />Открыть</button>
          {lead.leadType === 'Клиент' && createProjectFromLead && (
            <button onClick={() => createProjectFromLead(lead)} disabled={!!lead.projectId} style={{ ...btnG, padding: '6px 9px', fontSize: '11px', opacity: lead.projectId ? 0.7 : 1 }}>
              <Building2 size={12} />{lead.projectId ? 'Объект создан' : 'В объект'}
            </button>
          )}
          {isSupplier && <button onClick={() => approveSupplier(lead)} style={{ ...btnG, padding: '6px 9px', fontSize: '11px' }}><UserCheck size={12} />Одобрить</button>}
          {isWorker && <button onClick={() => approveWorker(lead, lead.leadType === 'Бригадир' ? 'бригадир' : (lead.leadType === 'Субподрядчик' ? 'субподрядчик' : 'мастер'))} style={{ ...btnG, padding: '6px 9px', fontSize: '11px' }}><Users size={12} />В исполнители</button>}
          <button onClick={() => removeLead(lead.id)} style={{ ...btnR, padding: '6px 9px', fontSize: '11px' }}><Trash2 size={12} /></button>
        </div>
      </article>
    );
  };

  return (
    <div style={{ width: '100%', maxWidth: '100%', minWidth: 0, overflowX: 'hidden' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px', flexWrap: 'wrap', marginBottom: '18px' }}>
        <div>
          <h3 style={{ color: C.text, margin: 0, fontSize: compact ? '15px' : '16px', fontWeight: 800 }}>CRM — входящие заявки</h3>
          <p style={{ color: C.textSec, margin: '3px 0 0', fontSize: '12px' }}>Клиенты, поставщики и исполнители проходят проверку до выдачи роли.</p>
        </div>
        <button onClick={startNew} style={{ ...btnO, width: compact ? '100%' : 'auto', justifyContent: 'center', minHeight: compact ? '44px' : undefined }}>
          <Plus size={14} />Новая заявка
        </button>
      </div>

      <CrmSummary C={C} card={card} compact={compact} summary={summary} />
      <CrmFilters
        C={C}
        inp={inp}
        btnG={btnG}
        compact={compact}
        filters={filters}
        setFilters={setFilters}
        leadTypes={LEAD_TYPES}
        responsibleOptions={responsibleOptions}
      />

      {showForm && (
        <section style={{ ...card, padding: compact ? '14px' : '18px', marginBottom: '18px', maxWidth: '1180px', boxSizing: 'border-box' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap', marginBottom: '14px' }}>
            <div>
              <b style={{ color: C.text, fontSize: '14px' }}>{editingItem ? 'Карточка заявки' : 'Новая заявка'}</b>
              <p style={{ color: C.textSec, margin: '3px 0 0', fontSize: '12px' }}>CRM хранит входные данные, документы и проверку. Роли выдаются отдельно через приглашение.</p>
            </div>
            <button onClick={() => { setShowForm(false); setEditingItem(null); }} style={{ ...btnG, padding: '7px 10px' }}><X size={13} />Закрыть</button>
          </div>

          {inviteResult?.link && (
            <div style={{ padding: '10px 12px', border: '1.5px solid ' + C.successBorder, backgroundColor: C.successLight, borderRadius: '8px', marginBottom: '12px' }}>
              <b style={{ color: C.success, fontSize: '12px' }}>Приглашение создано</b>
              <p style={{ color: C.text, margin: '4px 0 0', fontSize: '12px', overflowWrap: 'anywhere' }}>{inviteResult.link}</p>
            </div>
          )}

          <FormGrid compact={compact}>
            <select value={newLead.leadType || 'Клиент'} onChange={e => setNewLead({ ...newLead, leadType: e.target.value })} style={field(inp)}>{LEAD_TYPES.map(x => <option key={x}>{x}</option>)}</select>
            <select value={newLead.stage || 'Новый'} onChange={e => setNewLead({ ...newLead, stage: e.target.value })} style={field(inp)}>{CRM_STAGES.map(x => <option key={x}>{x}</option>)}</select>
            <input placeholder="Имя / компания *" value={newLead.name || ''} onChange={e => setNewLead({ ...newLead, name: e.target.value })} style={field(inp)} />
            <input placeholder="Телефон" value={newLead.phone || ''} onChange={e => setNewLead({ ...newLead, phone: e.target.value })} style={field(inp)} />
            <input placeholder="Email" value={newLead.email || ''} onChange={e => setNewLead({ ...newLead, email: e.target.value })} style={field(inp)} />
            <input placeholder="Источник" value={newLead.source || ''} onChange={e => setNewLead({ ...newLead, source: e.target.value })} style={field(inp)} />
            <input placeholder="Тип работ / специализация" value={newLead.workType || ''} onChange={e => setNewLead({ ...newLead, workType: e.target.value })} style={field(inp)} />
            <input placeholder="Адрес / город" value={newLead.address || ''} onChange={e => setNewLead({ ...newLead, address: e.target.value })} style={field(inp)} />
            <input placeholder="Бюджет (₽)" type="number" step="any" value={newLead.budget || ''} onChange={e => setNewLead({ ...newLead, budget: e.target.value })} style={field(inp)} />
            <input placeholder="Площадь / объем" type="number" step="any" value={newLead.area || ''} onChange={e => setNewLead({ ...newLead, area: e.target.value })} style={field(inp)} />
            <select value={newLead.priority || 'Обычный'} onChange={e => setNewLead({ ...newLead, priority: e.target.value })} style={field(inp)}>{PRIORITIES.map(x => <option key={x}>{x}</option>)}</select>
            <select value={newLead.legalForm || ''} onChange={e => setNewLead({ ...newLead, legalForm: e.target.value })} style={field(inp)}>{LEGAL_FORMS.map(x => <option key={x} value={x}>{x || 'Тип контрагента'}</option>)}</select>
            <input placeholder="Ответственный" value={newLead.responsibleName || ''} onChange={e => setNewLead({ ...newLead, responsibleName: e.target.value })} list="crm-users" style={field(inp)} />
            <input placeholder="Следующий контакт" type="date" value={newLead.nextContactAt || ''} onChange={e => setNewLead({ ...newLead, nextContactAt: e.target.value })} style={field(inp)} />
            <datalist id="crm-users">{safeList(users).map(u => <option key={u.id || u.name} value={u.name} />)}</datalist>
          </FormGrid>

          <SectionTitle C={C} title="Реквизиты и персональные данные" subtitle="Паспорт и банковские данные показываем только в карточке, не в списках." />
          <FormGrid compact={compact}>
            <input placeholder="ИНН" value={newLead.inn || ''} onChange={e => setNewLead({ ...newLead, inn: e.target.value })} style={field(inp)} />
            <input placeholder="КПП" value={newLead.kpp || ''} onChange={e => setNewLead({ ...newLead, kpp: e.target.value })} style={field(inp)} />
            <input placeholder="ОГРН / ОГРНИП" value={newLead.ogrn || ''} onChange={e => setNewLead({ ...newLead, ogrn: e.target.value })} style={field(inp)} />
            <input placeholder="Банк" value={newLead.bank || ''} onChange={e => setNewLead({ ...newLead, bank: e.target.value })} style={field(inp)} />
            <input placeholder="БИК" value={newLead.bik || ''} onChange={e => setNewLead({ ...newLead, bik: e.target.value })} style={field(inp)} />
            <input placeholder="Расчетный счет" value={newLead.bankAccount || ''} onChange={e => setNewLead({ ...newLead, bankAccount: e.target.value })} style={field(inp)} />
            <input placeholder="Корр. счет" value={newLead.corrAccount || ''} onChange={e => setNewLead({ ...newLead, corrAccount: e.target.value })} style={field(inp)} />
            <input placeholder="Подписант" value={newLead.signerName || ''} onChange={e => setNewLead({ ...newLead, signerName: e.target.value })} style={field(inp)} />
            <input placeholder="Основание подписи" value={newLead.signerBasis || ''} onChange={e => setNewLead({ ...newLead, signerBasis: e.target.value })} style={field(inp)} />
            <textarea placeholder="Юридический адрес" value={newLead.legalAddress || ''} onChange={e => setNewLead({ ...newLead, legalAddress: e.target.value })} style={{ ...field(inp), height: '70px', resize: 'vertical' }} />
            <textarea placeholder="Паспортные данные / данные физлица" value={newLead.passportData || ''} onChange={e => setNewLead({ ...newLead, passportData: e.target.value })} style={{ ...field(inp), height: '70px', resize: 'vertical' }} />
            <textarea placeholder="Предмет договора" value={newLead.contractSubject || ''} onChange={e => setNewLead({ ...newLead, contractSubject: e.target.value })} style={{ ...field(inp), height: '70px', resize: 'vertical' }} />
            <textarea placeholder="Причина отказа" value={newLead.lossReason || ''} onChange={e => setNewLead({ ...newLead, lossReason: e.target.value })} style={{ ...field(inp), height: '70px', resize: 'vertical' }} />
          </FormGrid>

          <textarea placeholder="Заметки" value={newLead.notes || ''} onChange={e => setNewLead({ ...newLead, notes: e.target.value })} style={{ ...field(inp), height: '86px', resize: 'vertical', marginTop: '10px' }} />
          <div style={{ marginTop: '10px' }}>
            <PhotoAttachmentField
              C={C}
              btnG={btnG}
              value={newLead.photoUrl || ''}
              onChange={photoUrl => setNewLead({ ...newLead, photoUrl })}
              appendPhotos={appendPhotos}
              fileSrc={fileSrc}
              setShowPhotoModal={setShowPhotoModal}
              projectName={newLead.name || 'CRM'}
              context="crm-leads"
              title="Фото объекта / документов"
            />
          </div>

          <DocumentRecognitionPanel
            API={API}
            C={C}
            card={card}
            inp={inp}
            btnG={btnG}
            btnO={btnO}
            btnB={btnB}
            uploadPhoto={uploadPhoto}
            fileSrc={fileSrc}
            projectName={newLead.name || 'CRM'}
            context="crm-counterparty-documents"
            entityType={newLead.leadType || 'CRM'}
            currentFields={newLead}
            onApplyLead={patch => setNewLead(prev => ({ ...prev, ...patch }))}
            onCreateCrmDocument={editingItem?.id ? createRecognizedCrmDocument : null}
          />

          {editingItem?.id && (
            <div style={{ display: 'grid', gridTemplateColumns: compact ? '1fr' : '1.1fr .9fr', gap: '12px', marginTop: '14px' }}>
              <DocumentsPanel
                C={C}
                card={card}
                inp={inp}
                btnG={btnG}
                btnR={btnR}
                fileSrc={fileSrc}
                details={details}
                detailsLoading={detailsLoading}
                documentForm={documentForm}
                setDocumentForm={setDocumentForm}
                uploadCrmDocument={uploadCrmDocument}
                deleteCrmDocument={deleteCrmDocument}
              />
              <TasksPanel
                C={C}
                inp={inp}
                btnG={btnG}
                taskForm={taskForm}
                setTaskForm={setTaskForm}
                tasks={details.tasks}
                users={users}
                createTask={createTask}
                closeTask={closeTask}
              />
            </div>
          )}

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginTop: '15px' }}>
            <button onClick={saveCurrentLead} disabled={saving} style={{ ...btnO, minHeight: compact ? '44px' : undefined }}><Check size={14} />{saving ? 'Сохраняем...' : (editingItem ? 'Сохранить' : 'Создать')}</button>
            {editingItem?.id && newLead.leadType === 'Поставщик' && <button onClick={() => approveSupplier({ ...newLead, id: editingItem.id })} style={btnG}><UserCheck size={14} />Одобрить поставщика</button>}
            {editingItem?.id && ['Мастер', 'Бригадир', 'Субподрядчик'].includes(newLead.leadType) && <button onClick={() => approveWorker({ ...newLead, id: editingItem.id }, newLead.leadType === 'Бригадир' ? 'бригадир' : (newLead.leadType === 'Субподрядчик' ? 'субподрядчик' : 'мастер'))} style={btnG}><Users size={14} />В исполнители</button>}
            {editingItem?.id && ['Поставщик', 'Мастер', 'Бригадир', 'Субподрядчик', 'Клиент'].includes(newLead.leadType) && <button onClick={() => createInviteForLead({ ...newLead, id: editingItem.id })} style={btnG}><UserCheck size={14} />Создать приглашение</button>}
            {editingItem?.id && details.documents.length > 0 && <button onClick={() => transferDocumentsToProject({ ...newLead, id: editingItem.id })} style={btnG}><FileText size={14} />Документы в объект</button>}
          </div>
        </section>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: compact ? '1fr' : 'repeat(5,minmax(220px,1fr))', gap: '12px', overflowX: compact ? 'hidden' : 'auto', alignItems: 'start' }}>
        {Array.from(grouped.entries()).map(([stage, items]) => {
          const [color, bg, border] = stageColor(stage);
          return (
            <section key={stage} style={{ minWidth: compact ? 0 : '220px' }}>
              <div style={{ padding: '9px 11px', backgroundColor: bg, border: '1.5px solid ' + border, borderRadius: '8px', marginBottom: '10px', display: 'flex', justifyContent: 'space-between', gap: '8px' }}>
                <b style={{ color, fontSize: '12px', overflowWrap: 'anywhere' }}>{stage}</b>
                <span style={{ color: C.textSec, fontSize: '11px' }}>{items.length}</span>
              </div>
              {items.length ? items.map(renderLeadCard) : <div style={{ ...card, padding: '14px', color: C.textMuted, fontSize: '12px', borderStyle: 'dashed' }}>Заявок нет</div>}
            </section>
          );
        })}
      </div>
    </div>
  );
}

function CrmSummary({ C, card, compact, summary }) {
  const money = (value) => Math.round(Number(value || 0)).toLocaleString('ru-RU') + ' ₽';
  const items = [
    { label: 'Всего заявок', value: summary.total, color: C.text },
    { label: 'В работе', value: summary.open, color: C.accent },
    { label: 'На сегодня', value: summary.today, color: C.warning },
    { label: 'Просрочено', value: summary.overdue, color: C.danger },
    { label: 'Без ответственного', value: summary.noResponsible, color: C.warning },
    { label: 'Потенциал', value: money(summary.budget), color: C.success },
  ];
  return (
    <div style={{ display: 'grid', gridTemplateColumns: compact ? 'repeat(2,minmax(0,1fr))' : 'repeat(6,minmax(120px,1fr))', gap: '10px', marginBottom: '12px' }}>
      {items.map(item => (
        <div key={item.label} style={{ ...card, padding: compact ? '10px' : '12px', minWidth: 0 }}>
          <span style={{ color: C.textSec, fontSize: '11px', display: 'block', marginBottom: '4px' }}>{item.label}</span>
          <b style={{ color: item.color, fontSize: compact ? '15px' : '16px', overflowWrap: 'anywhere' }}>{item.value}</b>
        </div>
      ))}
      {summary.visible !== summary.total && (
        <div style={{ ...card, padding: compact ? '10px' : '12px', minWidth: 0, borderColor: C.infoBorder || C.border }}>
          <span style={{ color: C.textSec, fontSize: '11px', display: 'block', marginBottom: '4px' }}>Показано</span>
          <b style={{ color: C.info || C.accent, fontSize: compact ? '15px' : '16px' }}>{summary.visible}</b>
        </div>
      )}
    </div>
  );
}

function CrmFilters({ C, inp, btnG, compact, filters, setFilters, leadTypes, responsibleOptions }) {
  const update = (patch) => setFilters(current => ({ ...current, ...patch }));
  const reset = () => setFilters({ search: '', leadType: '', responsibleName: '', attention: '' });
  return (
    <div style={{ display: 'grid', gridTemplateColumns: compact ? '1fr' : 'minmax(220px,1.4fr) repeat(3,minmax(150px,1fr)) auto', gap: '8px', alignItems: 'center', marginBottom: '14px' }}>
      <label style={{ position: 'relative', display: 'block' }}>
        <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: C.textMuted }} />
        <input
          value={filters.search}
          onChange={event => update({ search: event.target.value })}
          placeholder="Поиск: клиент, телефон, объект, источник"
          style={{ ...inp, marginBottom: 0, paddingLeft: '32px', width: '100%', boxSizing: 'border-box' }}
        />
      </label>
      <select value={filters.leadType} onChange={event => update({ leadType: event.target.value })} style={field(inp)}>
        <option value="">Все типы</option>
        {leadTypes.map(type => <option key={type}>{type}</option>)}
      </select>
      <select value={filters.responsibleName} onChange={event => update({ responsibleName: event.target.value })} style={field(inp)}>
        <option value="">Все ответственные</option>
        {responsibleOptions.map(name => <option key={name}>{name}</option>)}
      </select>
      <select value={filters.attention} onChange={event => update({ attention: event.target.value })} style={field(inp)}>
        <option value="">Все состояния</option>
        <option value="overdue">Просрочено</option>
        <option value="today">На сегодня</option>
        <option value="noResponsible">Без ответственного</option>
        <option value="noDocuments">Нет документов</option>
        <option value="openTasks">Есть задачи</option>
      </select>
      <button onClick={reset} style={{ ...btnG, justifyContent: 'center', minHeight: compact ? '42px' : undefined }}>
        <Filter size={13} />Сброс
      </button>
    </div>
  );
}

function miniBadge(color, bg, border) {
  return {
    color,
    backgroundColor: bg,
    border: '1px solid ' + border,
    borderRadius: '999px',
    padding: '2px 6px',
    fontSize: '10px',
    fontWeight: 700,
  };
}

function FormGrid({ compact, children }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: compact ? '1fr' : 'repeat(3,minmax(180px,1fr))', gap: '10px' }}>
      {children}
    </div>
  );
}

function SectionTitle({ C, title, subtitle }) {
  return (
    <div style={{ margin: '16px 0 10px' }}>
      <b style={{ color: C.text, fontSize: '13px' }}>{title}</b>
      <p style={{ color: C.textSec, margin: '2px 0 0', fontSize: '11px' }}>{subtitle}</p>
    </div>
  );
}

function DocumentsPanel({ C, inp, btnG, btnR, fileSrc, details, detailsLoading, documentForm, setDocumentForm, uploadCrmDocument, deleteCrmDocument }) {
  return (
    <div style={{ border: '1.5px solid ' + C.border, borderRadius: '8px', padding: '12px', backgroundColor: C.bg }}>
      <SectionTitle C={C} title="Документы сделки" subtitle="Смета, КП, договор, реквизиты, паспортные данные, ТЗ." />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '8px' }}>
        <select value={documentForm.docType} onChange={e => setDocumentForm({ ...documentForm, docType: e.target.value })} style={field(inp)}>{DOCUMENT_TYPES.map(x => <option key={x}>{x}</option>)}</select>
        <input placeholder="Название" value={documentForm.title} onChange={e => setDocumentForm({ ...documentForm, title: e.target.value })} style={field(inp)} />
        <input placeholder="Номер" value={documentForm.number} onChange={e => setDocumentForm({ ...documentForm, number: e.target.value })} style={field(inp)} />
        <input type="date" value={documentForm.docDate} onChange={e => setDocumentForm({ ...documentForm, docDate: e.target.value })} style={field(inp)} />
      </div>
      <label style={{ ...btnG, display: 'inline-flex', cursor: 'pointer', marginBottom: '10px' }}>
        <Upload size={13} />Загрузить файл
        <input type="file" accept=".pdf,.doc,.docx,.xls,.xlsx,image/*" style={{ display: 'none' }} onChange={async e => { if (e.target.files?.[0]) await uploadCrmDocument(e.target.files[0]); e.target.value = ''; }} />
      </label>
      {detailsLoading && <p style={{ color: C.textMuted, fontSize: '12px' }}>Загружаем документы...</p>}
      {safeList(details.documents).map(doc => (
        <div key={doc.id} style={{ padding: '8px 0', borderTop: '1px solid ' + C.border, display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'center' }}>
          <div style={{ minWidth: 0 }}>
            <b style={{ color: C.text, fontSize: '12px', display: 'block', overflowWrap: 'anywhere' }}><FileText size={12} /> {doc.docType || 'Документ'} · {doc.title || 'без названия'}</b>
            <p style={{ color: C.textSec, margin: '2px 0 0', fontSize: '11px' }}>{[doc.number, doc.docDate, doc.status].filter(Boolean).join(' · ')}</p>
          </div>
          <div style={{ display: 'flex', gap: '5px', flex: '0 0 auto' }}>
            {doc.fileUrl && <a href={fileSrc ? fileSrc(doc.fileUrl) : doc.fileUrl} target="_blank" rel="noreferrer" style={{ ...btnG, padding: '5px 8px', fontSize: '11px', textDecoration: 'none' }}>Файл</a>}
            <button onClick={() => deleteCrmDocument(doc.id)} style={{ ...btnR, padding: '5px 8px', fontSize: '11px' }}><Trash2 size={11} /></button>
          </div>
        </div>
      ))}
      {!detailsLoading && safeList(details.documents).length === 0 && <p style={{ color: C.textMuted, fontSize: '12px', margin: 0 }}>Документы еще не загружены</p>}
    </div>
  );
}

function TasksPanel({ C, inp, btnG, taskForm, setTaskForm, tasks, users, createTask, closeTask }) {
  return (
    <div style={{ border: '1.5px solid ' + C.border, borderRadius: '8px', padding: '12px', backgroundColor: C.bg }}>
      <SectionTitle C={C} title="Следующие шаги" subtitle="Звонки, КП, замер, запрос документов." />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 130px', gap: '8px', marginBottom: '8px' }}>
        <input placeholder="Задача" value={taskForm.title} onChange={e => setTaskForm({ ...taskForm, title: e.target.value })} style={field(inp)} />
        <input type="date" value={taskForm.dueDate} onChange={e => setTaskForm({ ...taskForm, dueDate: e.target.value })} style={field(inp)} />
        <input placeholder="Ответственный" value={taskForm.assignedTo} onChange={e => setTaskForm({ ...taskForm, assignedTo: e.target.value })} list="crm-task-users" style={field(inp)} />
        <button onClick={createTask} style={{ ...btnG, justifyContent: 'center' }}><ClipboardList size={13} />Добавить</button>
        <datalist id="crm-task-users">{safeList(users).map(u => <option key={u.id || u.name} value={u.name} />)}</datalist>
      </div>
      {safeList(tasks).map(task => (
        <div key={task.id} style={{ padding: '8px 0', borderTop: '1px solid ' + C.border, display: 'flex', justifyContent: 'space-between', gap: '8px' }}>
          <div>
            <b style={{ color: C.text, fontSize: '12px' }}>{task.title}</b>
            <p style={{ color: C.textSec, margin: '2px 0 0', fontSize: '11px' }}>{[task.dueDate, task.assignedTo, task.status].filter(Boolean).join(' · ')}</p>
          </div>
          {task.status !== 'Закрыта' && <button onClick={() => closeTask(task)} style={{ ...btnG, padding: '5px 8px', fontSize: '11px' }}><Check size={11} /></button>}
        </div>
      ))}
      {safeList(tasks).length === 0 && <p style={{ color: C.textMuted, fontSize: '12px', margin: 0 }}>Задач нет</p>}
    </div>
  );
}
