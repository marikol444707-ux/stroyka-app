import { useCallback, useEffect, useMemo, useState } from 'react';

function SystemOwnerCabinet({user, setUser, C, card, btnO, btnG, btnGr, btnR, inp, badge, API}) {
  const [tab, setTab] = useState('dashboard');
  const [dashboard, setDashboard] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [payments, setPayments] = useState([]);
  const [billingDocuments, setBillingDocuments] = useState([]);
  const [paymentProviders, setPaymentProviders] = useState([]);
  const [paymentEvents, setPaymentEvents] = useState([]);
  const [platformFollowups, setPlatformFollowups] = useState([]);
  const [demos, setDemos] = useState([]);
  const [tariffs, setTariffs] = useState([]);
  const [auditLog, setAuditLog] = useState([]);
  const [showNewCompany, setShowNewCompany] = useState(false);
  const emptyCompanyForm = {platformAccountId:'',platformAccountName:'',name:'',shortName:'',inn:'',kpp:'',contactName:'',contactPhone:'',contactEmail:'',plan:'demo',trialDays:30,monthlyFee:'',maxProjects:'',maxUsers:'',notes:''};
  const [newCompany, setNewCompany] = useState(emptyCompanyForm);
  const [clientCardScanning, setClientCardScanning] = useState(false);
  const [clientCardRecognition, setClientCardRecognition] = useState(null);
  const [companyPreview, setCompanyPreview] = useState(null);
  const [companyPreviewLoading, setCompanyPreviewLoading] = useState(false);
  const [newPayment, setNewPayment] = useState({companyId:'',amount:'',paymentDate:new Date().toISOString().split('T')[0],method:'card',invoiceNumber:'',periodStart:'',periodEnd:'',notes:''});
  const [showNewPayment, setShowNewPayment] = useState(false);
  const [newBillingDocument, setNewBillingDocument] = useState({companyId:'',documentType:'invoice',status:'draft',amount:'',issueDate:new Date().toISOString().split('T')[0],dueDate:'',periodStart:'',periodEnd:'',paymentProvider:'manual',paymentUrl:'',fileUrl:'',notes:''});
  const [showNewBillingDocument, setShowNewBillingDocument] = useState(false);
  const emptyFollowupForm = {companyId:'',billingDocumentId:'',source:'payment',channel:'call',title:'',contactName:'',contactValue:'',dueDate:new Date().toISOString().split('T')[0],status:'open',responsibleName:user.name || '',notes:'',result:''};
  const [newFollowup, setNewFollowup] = useState(emptyFollowupForm);
  const [showNewFollowup, setShowNewFollowup] = useState(false);
  const [lastInviteCode, setLastInviteCode] = useState(null);
  const [clientUsers, setClientUsers] = useState([]);
  const [clientUserMoveDrafts, setClientUserMoveDrafts] = useState({});
  const [platformUsers, setPlatformUsers] = useState([]);
  const [supportSessions, setSupportSessions] = useState([]);
  const [platformInvite, setPlatformInvite] = useState({role:'platform_support',name:'',email:'',expiresInDays:7});
  const [lastPlatformInvite, setLastPlatformInvite] = useState(null);
  const [supportForm, setSupportForm] = useState({platformAccountId:'',companyId:'',scope:'read_only',reason:'',expiresInHours:24});
  const emptyAuditFilters = {platformAccountId:'',companyId:'',action:'',search:''};
  const [auditFilters, setAuditFilters] = useState(emptyAuditFilters);
  const [auditDraftFilters, setAuditDraftFilters] = useState(emptyAuditFilters);
  const emptyClientUserFilters = {platformAccountId:'',companyId:'',role:'',active:'',search:''};
  const [clientUserFilters, setClientUserFilters] = useState(emptyClientUserFilters);
  const [clientUserDraftFilters, setClientUserDraftFilters] = useState(emptyClientUserFilters);
  const emptyPaymentEventFilters = {platformAccountId:'',companyId:'',provider:'',actionStatus:'',dateFrom:'',dateTo:'',search:''};
  const [paymentEventFilters, setPaymentEventFilters] = useState(emptyPaymentEventFilters);
  const [paymentEventDraftFilters, setPaymentEventDraftFilters] = useState(emptyPaymentEventFilters);
  const platformRoleLabels = {
    system_owner:'Владелец платформы',
    platform_admin:'Администратор платформы',
    platform_support:'Поддержка платформы',
    billing_admin:'Биллинг платформы',
  };
  const supportScopeLabels = {
    read_only:'Только просмотр',
    access_help:'Помощь с доступом',
    billing_help:'Биллинг',
    technical_check:'Техническая проверка',
  };
  const billingDocumentTypeLabels = {
    invoice:'Счет',
    act:'Акт',
    offer:'КП',
  };
  const billingDocumentStatusLabels = {
    draft:'Черновик',
    issued:'Выставлен',
    payment_expected:'Ожидает оплату',
    closed:'Закрыт',
    cancelled:'Аннулирован',
  };
  const followupSourceLabels = {demo:'Демо',payment:'Оплата',renewal:'Продление',support:'Поддержка',manual:'Вручную'};
  const followupChannelLabels = {call:'Звонок',email:'Email',messenger:'Мессенджер',meeting:'Встреча'};
  const followupStatusLabels = {open:'Открыта',contacted:'Связались',waiting:'Ждем клиента',done:'Закрыта',cancelled:'Отменена'};
  const canManagePlatform = ['system_owner','platform_admin'].includes(user.role);
  const canManageBilling = ['system_owner','platform_admin','billing_admin'].includes(user.role);
  const canManageTeam = user.role === 'system_owner';
  const canUseSupport = ['system_owner','platform_admin','platform_support'].includes(user.role);
  const canViewClientUsers = canManagePlatform || canUseSupport;
  const canUseFollowups = canManagePlatform || canManageBilling || canUseSupport;
  const authHeaders = useCallback((headers={}) => {
    const token = localStorage.getItem('authToken');
    return token ? {...headers, Authorization:'Bearer '+token} : headers;
  }, []);
  const fetchJson = useCallback(async (path, fallback) => {
    const response = await fetch(API + path, {headers:authHeaders()});
    if (!response.ok) return fallback;
    return response.json();
  }, [API, authHeaders]);
  const sendJson = useCallback(async (path, options={}) => {
    const headers = authHeaders({'Content-Type':'application/json', ...(options.headers || {})});
    return fetch(API + path, {...options, headers});
  }, [API, authHeaders]);
  const auditActionLabels = {
    platform_account_created: 'Создан аккаунт',
    company_created: 'Создана компания',
    company_soft_suspended: 'Мягкая заморозка',
    company_hard_suspended: 'Жесткая заморозка',
    company_resumed: 'Разморозка',
    company_marked_overdue: 'Просрочка',
    company_trial_extended: 'Продлен триал',
    company_tariff_changed: 'Сменен тариф',
    company_updated: 'Компания изменена',
    payment_added: 'Зачислена оплата',
    demo_request_updated: 'Демо-заявка изменена',
    platform_billing_document_created: 'Создан платежный документ',
    platform_billing_document_updated: 'Изменен платежный документ',
    platform_billing_document_pdf_generated: 'Сформирован PDF документа',
    platform_payment_provider_prepared: 'Подготовлен платежный провайдер',
    platform_payment_webhook_received: 'Получено событие провайдера',
    platform_payment_event_confirmed: 'Оплата зачислена по событию',
    platform_followup_created: 'Создана задача платформы',
    platform_followup_updated: 'Задача платформы изменена',
    platform_followup_closed: 'Задача платформы закрыта',
    client_card_recognized: 'Распознана карта клиента',
    client_user_disabled: 'Доступ клиента отключен',
    client_user_enabled: 'Доступ клиента включен',
    client_user_transferred: 'Пользователь перенесен',
    client_user_updated: 'Пользователь клиента изменен',
    platform_user_invited: 'Приглашен сотрудник платформы',
    platform_user_updated: 'Сотрудник платформы изменен',
    support_session_opened: 'Открыт режим поддержки',
    support_session_closed: 'Закрыт режим поддержки',
  };

  const loadAll = useCallback(async () => {
    try {
      const auditParams = new URLSearchParams({limit:'80'});
      if (auditFilters.platformAccountId) auditParams.set('platformAccountId', auditFilters.platformAccountId);
      if (auditFilters.companyId) auditParams.set('companyId', auditFilters.companyId);
      if (auditFilters.action) auditParams.set('action', auditFilters.action);
      if (auditFilters.search.trim()) auditParams.set('search', auditFilters.search.trim());
      const clientUserParams = new URLSearchParams({limit:'500'});
      if (clientUserFilters.platformAccountId) clientUserParams.set('platformAccountId', clientUserFilters.platformAccountId);
      if (clientUserFilters.companyId) clientUserParams.set('companyId', clientUserFilters.companyId);
      if (clientUserFilters.role) clientUserParams.set('role', clientUserFilters.role);
      if (clientUserFilters.active) clientUserParams.set('active', clientUserFilters.active);
      if (clientUserFilters.search.trim()) clientUserParams.set('search', clientUserFilters.search.trim());
      const [d, c, p, bd, pp, pf, dr, t, a, cu, u, s] = await Promise.all([
        fetchJson('/system/dashboard', null),
        fetchJson('/system/companies', []),
        canManageBilling ? fetchJson('/system/payments', []) : Promise.resolve([]),
        canManageBilling ? fetchJson('/system/billing-documents', []) : Promise.resolve([]),
        canManageBilling ? fetchJson('/system/payment-providers', []) : Promise.resolve([]),
        canUseFollowups ? fetchJson('/system/followups?status=active&limit=200', []) : Promise.resolve([]),
        canManagePlatform ? fetchJson('/demo-requests', []) : Promise.resolve([]),
        fetchJson('/system/tariffs', []),
        fetchJson('/system/audit-log?'+auditParams.toString(), []),
        canViewClientUsers ? fetchJson('/system/client-users?'+clientUserParams.toString(), []) : Promise.resolve([]),
        canManageTeam ? fetchJson('/system/platform-users', []) : Promise.resolve([]),
        canUseSupport ? fetchJson('/system/support-sessions', []) : Promise.resolve([]),
      ]);
      setDashboard(d);
      setCompanies(Array.isArray(c)?c:[]);
      setPayments(Array.isArray(p)?p:[]);
      setBillingDocuments(Array.isArray(bd)?bd:[]);
      setPaymentProviders(Array.isArray(pp)?pp:[]);
      setPlatformFollowups(Array.isArray(pf)?pf:[]);
      setDemos(Array.isArray(dr)?dr:[]);
      setTariffs(Array.isArray(t)?t:[]);
      setAuditLog(Array.isArray(a)?a:[]);
      setClientUsers(Array.isArray(cu)?cu:[]);
      setPlatformUsers(Array.isArray(u)?u:[]);
      setSupportSessions(Array.isArray(s)?s:[]);
    } catch(_){}
	  }, [auditFilters, canManageBilling, canManagePlatform, canManageTeam, canUseFollowups, canUseSupport, canViewClientUsers, clientUserFilters, fetchJson]);
	  useEffect(()=>{ loadAll(); }, [loadAll]);

  const loadPaymentEvents = useCallback(async () => {
    if (!canManageBilling) {
      setPaymentEvents([]);
      return;
    }
    const params = new URLSearchParams({limit:'200'});
    if (paymentEventFilters.platformAccountId) params.set('platformAccountId', paymentEventFilters.platformAccountId);
    if (paymentEventFilters.companyId) params.set('companyId', paymentEventFilters.companyId);
    if (paymentEventFilters.provider) params.set('provider', paymentEventFilters.provider);
    if (paymentEventFilters.actionStatus) params.set('actionStatus', paymentEventFilters.actionStatus);
    if (paymentEventFilters.dateFrom) params.set('dateFrom', paymentEventFilters.dateFrom);
    if (paymentEventFilters.dateTo) params.set('dateTo', paymentEventFilters.dateTo);
    if (paymentEventFilters.search.trim()) params.set('search', paymentEventFilters.search.trim());
    const rows = await fetchJson('/system/payment-events?' + params.toString(), []);
    setPaymentEvents(Array.isArray(rows) ? rows : []);
  }, [canManageBilling, fetchJson, paymentEventFilters]);

  useEffect(()=>{
    if (tab === 'payments') loadPaymentEvents();
  }, [tab, loadPaymentEvents]);

  const companyGroups = useMemo(() => {
    const byAccount = new Map();
    companies.forEach(c => {
      const accountId = c.platform_account_id || c.id;
      const accountName = c.platform_account_name || c.name || 'Без аккаунта';
      if (!byAccount.has(accountId)) {
        byAccount.set(accountId, {
          id: accountId,
          name: accountName,
          plan: c.platform_account_plan || c.plan,
          status: c.platform_account_status || c.payment_status || 'active',
          companies: [],
          users: 0,
          usersTotal: 0,
          usersByRole: new Map(),
          projects: 0,
          paid: 0,
        });
      }
      const group = byAccount.get(accountId);
      const activeUsers = Number(c.users_active_count ?? c.users_count ?? 0);
      const totalUsers = Number(c.users_count ?? activeUsers);
      group.companies.push(c);
      group.users += activeUsers;
      group.usersTotal += totalUsers;
      (c.users_by_role || []).forEach(roleInfo => {
        const role = roleInfo.role || 'без роли';
        const current = group.usersByRole.get(role) || {role, active:0, total:0};
        current.active += Number(roleInfo.active || 0);
        current.total += Number(roleInfo.total || 0);
        group.usersByRole.set(role, current);
      });
      group.projects += Number(c.projects_count || 0);
      group.paid += Number(c.total_paid || 0);
    });
    return Array.from(byAccount.values()).map(group => ({
      ...group,
      usersByRole: Array.from(group.usersByRole.values()).sort((a,b)=>b.active-a.active || a.role.localeCompare(b.role,'ru')),
    }));
  }, [companies]);

  const tariffOptions = useMemo(() => tariffs.length ? tariffs : [
    {id:'demo', name:'Демо', monthlyFee:0, maxProjects:1, maxUsers:5, includedCompanies:1, ocrPages:50, storageGb:2, trialDays:14, features:['Базовая ERP', 'Сметы', 'Склад объекта']},
    {id:'starter', name:'Старт', monthlyFee:19900, maxProjects:3, maxUsers:15, includedCompanies:1, ocrPages:200, storageGb:10, features:['Объекты', 'Сметы', 'Склад', 'Финансы']},
    {id:'pro', name:'Компания', monthlyFee:49900, maxProjects:10, maxUsers:40, includedCompanies:2, ocrPages:1000, storageGb:50, features:['Бухгалтерия', 'Снабжение', 'OCR', 'Роли']},
    {id:'group', name:'Группа', monthlyFee:99000, maxProjects:30, maxUsers:100, includedCompanies:5, ocrPages:3000, storageGb:150, features:['Общий кабинет группы', 'Переключатель компаний', 'Аудит']},
    {id:'enterprise', name:'Enterprise', monthlyFee:150000, maxProjects:null, maxUsers:null, includedCompanies:null, ocrPages:null, storageGb:null, features:['Индивидуальные лимиты', 'Домен', 'API', 'SLA']},
  ], [tariffs]);

  const tariffById = useMemo(() => {
    const result = {};
    tariffOptions.forEach(t => { result[t.id] = t; });
    return result;
  }, [tariffOptions]);

  const buildLimitWarnings = useCallback((group) => {
    const tariff = tariffById[group.plan] || {};
    const checks = [
      {key:'companies', label:'компаний', used:group.companies.length, limit:tariff.includedCompanies},
      {key:'projects', label:'объектов', used:group.projects, limit:tariff.maxProjects},
      {key:'users', label:'пользователей', used:group.users, limit:tariff.maxUsers},
    ];
    return checks
      .filter(item => item.limit !== null && item.limit !== undefined && Number(item.limit) > 0)
      .map(item => {
        const limit = Number(item.limit);
        const used = Number(item.used || 0);
        if (used > limit) return {...item, limit, used, level:'danger', text:`Превышен лимит ${item.label}: ${used}/${limit}`};
        if (used / limit >= 0.8) return {...item, limit, used, level:'warning', text:`Близко к лимиту ${item.label}: ${used}/${limit}`};
        return null;
      })
      .filter(Boolean);
  }, [tariffById]);

  const groupsWithLimitStatus = useMemo(() => companyGroups.map(group => ({
    ...group,
    limitWarnings: buildLimitWarnings(group),
  })), [companyGroups, buildLimitWarnings]);

  const limitWarningAccounts = useMemo(() => groupsWithLimitStatus.filter(group => group.limitWarnings.length > 0), [groupsWithLimitStatus]);
  const auditCompanyOptions = useMemo(() => companies.filter(company => (
    !auditDraftFilters.platformAccountId || String(company.platform_account_id || company.id) === String(auditDraftFilters.platformAccountId)
  )), [companies, auditDraftFilters.platformAccountId]);
  const clientUserCompanyOptions = useMemo(() => companies.filter(company => (
    !clientUserDraftFilters.platformAccountId || String(company.platform_account_id || company.id) === String(clientUserDraftFilters.platformAccountId)
  )), [companies, clientUserDraftFilters.platformAccountId]);
  const clientUserMoveCompanyOptions = useCallback((item) => companies.filter(company => (
    company.id !== 1 &&
    company.active !== false &&
    company.platform_account_id &&
    (!item.platformAccountId || String(company.platform_account_id) === String(item.platformAccountId))
  )), [companies]);
  const clientUserRoleOptions = useMemo(() => {
    const roles = new Set(['директор','зам_директора','бухгалтер','прораб','главный_инженер','сметчик','кладовщик','снабженец','мастер','бригадир','субподрядчик','поставщик','менеджер_crm','стройконтроль']);
    clientUsers.forEach(item => {
      if (item.role) roles.add(item.role);
    });
    return Array.from(roles).sort((a,b)=>a.localeCompare(b,'ru'));
  }, [clientUsers]);
  const paymentEventCompanyOptions = useMemo(() => companies.filter(company => (
    !paymentEventDraftFilters.platformAccountId || String(company.platform_account_id || company.id) === String(paymentEventDraftFilters.platformAccountId)
  )), [companies, paymentEventDraftFilters.platformAccountId]);
  const hasAuditFilters = Boolean(
    auditFilters.platformAccountId || auditFilters.companyId || auditFilters.action || auditFilters.search.trim()
  );
  const hasClientUserFilters = Boolean(
    clientUserFilters.platformAccountId || clientUserFilters.companyId || clientUserFilters.role ||
    clientUserFilters.active || clientUserFilters.search.trim()
  );
  const clientUserStats = useMemo(() => ({
    active: clientUsers.filter(item => item.active).length,
    inactive: clientUsers.filter(item => !item.active).length,
  }), [clientUsers]);
  const clientUserRoleStats = useMemo(() => {
    const result = new Map();
    clientUsers.forEach(item => {
      const role = item.role || 'без роли';
      const current = result.get(role) || {role, active:0, total:0};
      current.total += 1;
      if (item.active) current.active += 1;
      result.set(role, current);
    });
    return Array.from(result.values()).sort((a,b)=>b.active-a.active || a.role.localeCompare(b.role,'ru'));
  }, [clientUsers]);
  const accessWatchlist = useMemo(() => {
    const priority = {
      trial_expired: 1,
      payment_expired: 1,
      payment_overdue: 1,
      soft_frozen: 2,
      trial_no_date: 2,
      trial_expiring: 3,
      payment_expiring: 3,
    };
    return companies
      .filter(company => company.id !== 1 && priority[company.billing_state?.status])
      .map(company => ({...company, watchPriority: priority[company.billing_state?.status] || 9}))
      .sort((a,b)=>a.watchPriority-b.watchPriority || (a.billing_state?.daysLeft ?? 999)-(b.billing_state?.daysLeft ?? 999));
  }, [companies]);
  const followupStats = useMemo(() => {
    const today = new Date().toISOString().split('T')[0];
    return platformFollowups.reduce((acc, item) => {
      const closed = ['done','cancelled'].includes(item.status);
      if (!closed) acc.open += 1;
      if (!closed && item.dueDate && item.dueDate < today) acc.overdue += 1;
      if (!closed && item.dueDate === today) acc.today += 1;
      return acc;
    }, {open:0, overdue:0, today:0});
  }, [platformFollowups]);
  const followupDocumentOptions = useMemo(() => billingDocuments.filter(doc => (
    !newFollowup.companyId || String(doc.company_id || doc.companyId) === String(newFollowup.companyId)
  )), [billingDocuments, newFollowup.companyId]);
  const hasPaymentEventFilters = Boolean(
    paymentEventFilters.platformAccountId || paymentEventFilters.companyId || paymentEventFilters.provider ||
    paymentEventFilters.actionStatus || paymentEventFilters.dateFrom || paymentEventFilters.dateTo ||
    paymentEventFilters.search.trim()
  );

  const billingColorSet = (level) => {
    if (level === 'danger') return {color:C.danger, bg:C.dangerLight, border:C.dangerBorder};
    if (level === 'warning') return {color:C.warning, bg:C.warningLight, border:C.warningBorder};
    if (level === 'info') return {color:C.info, bg:C.infoLight, border:C.infoBorder};
    return {color:C.success, bg:C.successLight, border:C.successBorder};
  };

  const billingNeedsAction = (state) => ['trial_expired','payment_expired','payment_overdue','trial_no_date'].includes(state?.status);
  const billingDocumentStatusColor = (status) => {
    if (status === 'closed') return {color:C.success, bg:C.successLight, border:C.successBorder};
    if (status === 'payment_expected') return {color:C.warning, bg:C.warningLight, border:C.warningBorder};
    if (status === 'cancelled') return {color:C.danger, bg:C.dangerLight, border:C.dangerBorder};
    if (status === 'issued') return {color:C.info, bg:C.infoLight, border:C.infoBorder};
    return {color:C.textSec, bg:C.bg, border:C.border};
  };
  const paymentEventStatusColor = (status) => {
    if (status === 'payment_recorded') return {color:C.success, bg:C.successLight, border:C.successBorder};
    if (status === 'needs_review') return {color:C.danger, bg:C.dangerLight, border:C.dangerBorder};
    return {color:C.warning, bg:C.warningLight, border:C.warningBorder};
  };
  const followupStatusColor = (status, dueDate) => {
    const today = new Date().toISOString().split('T')[0];
    if (status === 'done') return {color:C.success, bg:C.successLight, border:C.successBorder};
    if (status === 'cancelled') return {color:C.textMuted, bg:C.bg, border:C.border};
    if (dueDate && dueDate < today) return {color:C.danger, bg:C.dangerLight, border:C.dangerBorder};
    if (status === 'waiting') return {color:C.warning, bg:C.warningLight, border:C.warningBorder};
    if (status === 'contacted') return {color:C.info, bg:C.infoLight, border:C.infoBorder};
    return {color:C.textSec, bg:C.bg, border:C.border};
  };
  const confirmPaymentEvent = async (event) => {
    if (!event?.id) return;
    const amount = Number(event.amount || 0).toLocaleString('ru-RU') + ' ₽';
    const documentNumber = event.billing_document_number || 'документ не найден';
    if (!window.confirm('Зачислить оплату по событию провайдера?\n\nДокумент: '+documentNumber+'\nСумма: '+amount+'\nКомпания: '+(event.company_name || '—'))) return;
    const note = window.prompt('Комментарий к ручной сверке:', 'Сумма и документ сверены биллингом') || '';
    const response = await sendJson('/system/payment-events/'+event.id+'/confirm', {
      method:'POST',
      body:JSON.stringify({notes:note}),
    });
    const data = await response.json().catch(()=>({}));
    if (!response.ok) {
      alert(data.detail || 'Не удалось зачислить оплату по событию');
      return;
    }
    alert('Оплата зачислена. Платеж #'+data.paymentId);
    await loadAll();
    await loadPaymentEvents();
  };
  const exportPaymentEvents = async () => {
    const params = new URLSearchParams({limit:'2000', export:'csv'});
    if (paymentEventFilters.platformAccountId) params.set('platformAccountId', paymentEventFilters.platformAccountId);
    if (paymentEventFilters.companyId) params.set('companyId', paymentEventFilters.companyId);
    if (paymentEventFilters.provider) params.set('provider', paymentEventFilters.provider);
    if (paymentEventFilters.actionStatus) params.set('actionStatus', paymentEventFilters.actionStatus);
    if (paymentEventFilters.dateFrom) params.set('dateFrom', paymentEventFilters.dateFrom);
    if (paymentEventFilters.dateTo) params.set('dateTo', paymentEventFilters.dateTo);
    if (paymentEventFilters.search.trim()) params.set('search', paymentEventFilters.search.trim());
    const response = await fetch(API + '/system/payment-events?' + params.toString(), {headers:authHeaders()});
    if (!response.ok) {
      alert('Не удалось выгрузить реестр событий');
      return;
    }
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'platform-payment-events.csv';
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  };
  const updateClientUser = async (clientUser, payload) => {
    if (!clientUser?.id) return;
    const response = await sendJson('/system/client-users/'+clientUser.id, {
      method:'PUT',
      body:JSON.stringify(payload),
    });
    const data = await response.json().catch(()=>({}));
    if (!response.ok) {
      alert(data.detail || 'Не удалось изменить доступ пользователя');
      return;
    }
    await loadAll();
  };
  const toggleClientUserAccess = async (clientUser) => {
    const nextActive = !clientUser.active;
    const reason = window.prompt(
      nextActive ? 'Причина включения доступа:' : 'Причина отключения доступа:',
      nextActive ? 'Доступ восстановлен после проверки' : 'Отключение доступа по решению платформы',
    );
    if (!reason) return;
    await updateClientUser(clientUser, {active:nextActive, reason});
  };
  const transferClientUser = async (clientUser) => {
    const companyId = clientUserMoveDrafts[clientUser.id];
    if (!companyId || String(companyId) === String(clientUser.companyId || '')) return;
    const targetCompany = companies.find(company => String(company.id) === String(companyId));
    const reason = window.prompt('Причина переноса пользователя в другую компанию:', 'Перенос доступа между юрлицами клиента');
    if (!reason) return;
    if (!window.confirm('Перенести пользователя '+(clientUser.email || clientUser.name)+' в компанию '+(targetCompany?.name || companyId)+'?\n\nДоступ к объектам будет очищен, чтобы не оставить права от старой компании.')) return;
    await updateClientUser(clientUser, {companyId, reason});
    setClientUserMoveDrafts(current => ({...current, [clientUser.id]: ''}));
  };
  const extendCompanyTrial = async (company) => {
    const days = window.prompt('Продлить триал на сколько дней?', '30');
    if (!days) return;
    const daysNumber = Number(days);
    if (!Number.isFinite(daysNumber) || daysNumber <= 0) {
      alert('Укажите положительное количество дней.');
      return;
    }
    const base = new Date(company.trial_until || new Date());
    const today = new Date();
    const newDate = base > today ? base : today;
    newDate.setDate(newDate.getDate() + daysNumber);
    await sendJson('/system/companies/'+company.id, {method:'PUT', body:JSON.stringify({trialUntil:newDate.toISOString().split('T')[0], paymentStatus:'trial'})});
    await loadAll();
  };
  const markCompanyOverdue = async (company) => {
    if (!window.confirm('Пометить компанию "'+(company.name || '—')+'" как просрочку? Доступ не отключится автоматически.')) return;
    await sendJson('/system/companies/'+company.id, {method:'PUT', body:JSON.stringify({action:'mark_overdue'})});
    await loadAll();
  };
  const softSuspendCompany = async (company) => {
    const reason = window.prompt('Причина мягкой заморозки:', company.billing_state?.reason || 'Не оплачен доступ');
    if (reason === null) return;
    await sendJson('/system/companies/'+company.id, {method:'PUT', body:JSON.stringify({action:'soft_suspend', reason})});
    await loadAll();
  };
  const resumeCompany = async (company) => {
    await sendJson('/system/companies/'+company.id, {method:'PUT', body:JSON.stringify({action:'resume'})});
    await loadAll();
  };
  const openCompanyPayment = (company) => {
    setNewPayment({...newPayment, companyId:company.id, amount:company.monthly_fee || ''});
    setShowNewPayment(true);
    setTab('payments');
  };
  const openCompanyBillingDocument = (company) => {
    setNewBillingDocument({...newBillingDocument, companyId:company.id, amount:company.monthly_fee || '', documentType:'invoice'});
    setShowNewBillingDocument(true);
    setTab('payments');
  };
  const openFollowupForm = (company={}, source='payment', document=null) => {
    const state = company.billing_state || {};
    const channel = company.contact_email ? 'email' : 'call';
    setNewFollowup({
      ...emptyFollowupForm,
      companyId: company.id || '',
      billingDocumentId: document?.id || '',
      source,
      channel,
      title: source === 'demo'
        ? 'Связаться по демо: ' + (company.name || '')
        : 'Связаться по оплате: ' + (company.name || ''),
      contactName: company.contact_name || '',
      contactValue: channel === 'email' ? (company.contact_email || '') : (company.contact_phone || company.contact_email || ''),
      dueDate: new Date().toISOString().split('T')[0],
      status: 'open',
      responsibleName: user.name || '',
      notes: [state.label, state.reason, document?.number ? 'Документ '+document.number : ''].filter(Boolean).join(' · '),
      result: '',
    });
    setShowNewFollowup(true);
    setTab('followups');
  };
  const createFollowup = async () => {
    if (!newFollowup.companyId || !newFollowup.title.trim()) {
      alert('Укажите компанию и задачу');
      return;
    }
    const response = await sendJson('/system/followups', {method:'POST', body:JSON.stringify(newFollowup)});
    const data = await response.json().catch(()=>({}));
    if (!response.ok) {
      alert(data.detail || 'Не удалось создать задачу');
      return;
    }
    setShowNewFollowup(false);
    setNewFollowup(emptyFollowupForm);
    await loadAll();
  };
  const updateFollowup = async (item, patch) => {
    const response = await sendJson('/system/followups/'+item.id, {method:'PUT', body:JSON.stringify(patch)});
    const data = await response.json().catch(()=>({}));
    if (!response.ok) {
      alert(data.detail || 'Не удалось обновить задачу');
      return;
    }
    await loadAll();
  };
  const companyCreateErrorText = (data) => {
    const detail = data?.detail;
    if (typeof detail === 'string') return detail;
    if (detail?.message) {
      const reasons = Array.isArray(detail.blockingReasons) ? detail.blockingReasons.join('\n') : '';
      return [detail.message, reasons].filter(Boolean).join('\n');
    }
    return data?.error || 'Не удалось создать компанию';
  };
  const runCompanyPreview = async (form=newCompany, quiet=false) => {
    setCompanyPreviewLoading(true);
    try {
      const response = await sendJson('/system/companies/preview', {method:'POST', body:JSON.stringify(form)});
      const data = await response.json().catch(()=>({}));
      if (!response.ok) {
        if (!quiet) alert(companyCreateErrorText(data));
        return null;
      }
      setCompanyPreview(data);
      return data;
    } finally {
      setCompanyPreviewLoading(false);
    }
  };
  const fileSrc = (url) => {
    if (!url) return '';
    return String(url).startsWith('http') ? url : API + url;
  };

  const applyTariffToForm = (plan) => {
    const selected = tariffById[plan];
    setNewCompany({
      ...newCompany,
      plan,
      trialDays: plan === 'demo' ? (selected?.trialDays || 14) : newCompany.trialDays,
      monthlyFee: plan === 'demo' ? '' : (selected?.monthlyFee || ''),
      maxProjects: selected?.maxProjects || '',
      maxUsers: selected?.maxUsers || '',
    });
  };

  const applyClientCardFields = useCallback((fields={}) => {
    const extraNotes = [
      fields.ogrn && 'ОГРН: ' + fields.ogrn,
      fields.legalAddress && 'Адрес: ' + fields.legalAddress,
      fields.website && 'Сайт: ' + fields.website,
      fields.contactPosition && 'Должность: ' + fields.contactPosition,
      fields.notes,
    ].filter(Boolean).join('\n');
    setNewCompany(prev => {
      const nextNotes = extraNotes && !String(prev.notes || '').includes(extraNotes)
        ? [prev.notes, extraNotes].filter(Boolean).join('\n')
        : prev.notes;
      return {
        ...prev,
        platformAccountName: prev.platformAccountId ? prev.platformAccountName : (fields.platformAccountName || prev.platformAccountName),
        name: fields.companyName || prev.name,
        shortName: fields.shortName || prev.shortName,
        inn: fields.inn || prev.inn,
        kpp: fields.kpp || prev.kpp,
        contactName: fields.contactName || prev.contactName,
        contactPhone: fields.contactPhone || prev.contactPhone,
        contactEmail: fields.contactEmail || prev.contactEmail,
        notes: nextNotes,
      };
    });
  }, []);

  const recognizeClientCard = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file || clientCardScanning) return;
    setClientCardScanning(true);
    setClientCardRecognition(null);
    try {
      const form = new FormData();
      form.append('file', file);
      const response = await fetch(API + '/system/client-card/recognize', {
        method:'POST',
        headers:authHeaders(),
        body:form,
      });
      const data = await response.json().catch(()=>({}));
      if (!response.ok || !data.ok) {
        alert(data.detail || data.error || 'Не удалось распознать карту клиента');
        return;
      }
      applyClientCardFields(data.fields || {});
      setClientCardRecognition(data);
    } catch (error) {
      alert(error?.message || 'Не удалось распознать карту клиента');
    } finally {
      setClientCardScanning(false);
    }
  };

	  const TABS = [
    {id:'dashboard', label:'📊 Дашборд'},
	    {id:'companies', label:'🏢 Аккаунты/компании'},
    canViewClientUsers && {id:'clientUsers', label:'👤 Пользователи клиентов'},
    {id:'tariffs', label:'💼 Тарифы'},
    canManageBilling && {id:'payments', label:'💰 Платежи'},
    canUseFollowups && {id:'followups', label:'📞 Задачи'},
    canManagePlatform && {id:'demos', label:'🎁 Демо-заявки'},
    canUseSupport && {id:'support', label:'🛟 Поддержка'},
    canManageTeam && {id:'team', label:'👥 Команда'},
    {id:'audit', label:'🧾 Журнал'},
    {id:'system', label:'🔧 Система'},
  ].filter(Boolean);

  return (
    <div style={{minHeight:'100vh',backgroundColor:C.bg,padding:'20px'}}>
      <div style={{maxWidth:'1100px',margin:'0 auto'}}>
        {/* Шапка */}
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'18px'}}>
          <div style={{display:'flex',alignItems:'center',gap:'12px'}}>
            <span style={{fontSize:'28px'}}>⚙️</span>
            <div>
              <b style={{color:C.text,fontSize:'18px',display:'block'}}>Кабинет платформы</b>
              <p style={{color:C.textSec,margin:0,fontSize:'13px'}}>{user.name} · {platformRoleLabels[user.role] || user.role}</p>
            </div>
          </div>
          <button onClick={()=>{localStorage.removeItem('authToken');localStorage.removeItem('user');setUser(null);}} style={{...btnG,fontSize:'12px'}}>Выйти</button>
        </div>

        {/* Вкладки */}
        <div style={{display:'flex',gap:'6px',marginBottom:'16px',overflowX:'auto',borderBottom:'1.5px solid '+C.border}}>
          {TABS.map(t=>(
            <button key={t.id} onClick={()=>setTab(t.id)} style={{padding:'10px 16px',border:'none',backgroundColor:'transparent',cursor:'pointer',fontSize:'13px',fontWeight:tab===t.id?'700':'400',color:tab===t.id?C.accent:C.textSec,borderBottom:tab===t.id?'2px solid '+C.accent:'2px solid transparent',whiteSpace:'nowrap'}}>{t.label}</button>
          ))}
        </div>

        {/* Дашборд */}
        {tab==='dashboard' && dashboard && (<div>
          <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:'12px',marginBottom:'18px'}}>
	            <div style={{...card,padding:'16px'}}><p style={{color:C.textSec,fontSize:'12px',margin:'0 0 6px'}}>🧭 Клиентские аккаунты</p><b style={{color:C.success,fontSize:'24px'}}>{dashboard.activeAccounts ?? groupsWithLimitStatus.length}</b></div>
	            <div style={{...card,padding:'16px'}}><p style={{color:C.textSec,fontSize:'12px',margin:'0 0 6px'}}>🚦 Лимиты</p><b style={{color:limitWarningAccounts.length?C.warning:C.success,fontSize:'24px'}}>{limitWarningAccounts.length}</b></div>
	            <div style={{...card,padding:'16px'}}><p style={{color:C.textSec,fontSize:'12px',margin:'0 0 6px'}}>🏢 Активные компании</p><b style={{color:C.success,fontSize:'24px'}}>{dashboard.activeCompanies}</b></div>
            <div style={{...card,padding:'16px'}}><p style={{color:C.textSec,fontSize:'12px',margin:'0 0 6px'}}>🎁 В демо</p><b style={{color:C.info,fontSize:'24px'}}>{dashboard.inDemo}</b></div>
            <div style={{...card,padding:'16px'}}><p style={{color:C.textSec,fontSize:'12px',margin:'0 0 6px'}}>⏳ Демо 3 дня</p><b style={{color:(dashboard.trialExpiring||0)?C.warning:C.success,fontSize:'24px'}}>{dashboard.trialExpiring || 0}</b></div>
            <div style={{...card,padding:'16px'}}><p style={{color:C.textSec,fontSize:'12px',margin:'0 0 6px'}}>🚨 Демо истекло</p><b style={{color:(dashboard.trialExpired||0)?C.danger:C.success,fontSize:'24px'}}>{dashboard.trialExpired || 0}</b></div>
            <div style={{...card,padding:'16px'}}><p style={{color:C.textSec,fontSize:'12px',margin:'0 0 6px'}}>⏸ Заморожены</p><b style={{color:C.textMuted,fontSize:'24px'}}>{dashboard.suspended}</b></div>
            <div style={{...card,padding:'16px'}}><p style={{color:C.textSec,fontSize:'12px',margin:'0 0 6px'}}>⚠️ Просрочка</p><b style={{color:C.danger,fontSize:'24px'}}>{dashboard.overdue}</b></div>
            <div style={{...card,padding:'16px'}}><p style={{color:C.textSec,fontSize:'12px',margin:'0 0 6px'}}>💳 Оплата 7 дней</p><b style={{color:(dashboard.paymentExpiring||0)?C.warning:C.success,fontSize:'24px'}}>{dashboard.paymentExpiring || 0}</b></div>
            <div style={{...card,padding:'16px'}}><p style={{color:C.textSec,fontSize:'12px',margin:'0 0 6px'}}>💳 Оплата истекла</p><b style={{color:(dashboard.paymentExpired||0)?C.danger:C.success,fontSize:'24px'}}>{dashboard.paymentExpired || 0}</b></div>
            <div style={{...card,padding:'16px'}}><p style={{color:C.textSec,fontSize:'12px',margin:'0 0 6px'}}>📞 Задачи</p><b style={{color:followupStats.open?C.warning:C.success,fontSize:'24px'}}>{dashboard.openFollowups ?? followupStats.open}</b></div>
            <div style={{...card,padding:'16px'}}><p style={{color:C.textSec,fontSize:'12px',margin:'0 0 6px'}}>🔥 Проср. задачи</p><b style={{color:(dashboard.overdueFollowups||followupStats.overdue)?C.danger:C.success,fontSize:'24px'}}>{dashboard.overdueFollowups ?? followupStats.overdue}</b></div>
            <div style={{...card,padding:'16px'}}><p style={{color:C.textSec,fontSize:'12px',margin:'0 0 6px'}}>💰 Выручка месяц</p><b style={{color:C.success,fontSize:'20px'}}>{Math.round(dashboard.monthRevenue).toLocaleString('ru-RU')+' ₽'}</b></div>
            <div style={{...card,padding:'16px'}}><p style={{color:C.textSec,fontSize:'12px',margin:'0 0 6px'}}>💰 Выручка год</p><b style={{color:C.success,fontSize:'20px'}}>{Math.round(dashboard.yearRevenue).toLocaleString('ru-RU')+' ₽'}</b></div>
            <div style={{...card,padding:'16px'}}><p style={{color:C.textSec,fontSize:'12px',margin:'0 0 6px'}}>🎁 Новых заявок</p><b style={{color:C.warning,fontSize:'24px'}}>{dashboard.newDemoRequests}</b></div>
          </div>
          <div style={{...card,padding:'16px',marginBottom:'18px'}}>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap',marginBottom:'10px'}}>
              <div>
                <b style={{color:C.text,fontSize:'14px',display:'block'}}>🚦 Демо и оплата требуют внимания ({accessWatchlist.length})</b>
                <p style={{color:C.textSec,fontSize:'12px',margin:'4px 0 0'}}>Система показывает риск заранее. Жесткого автоотключения нет: владелец платформы выбирает продление, просрочку, счет или мягкую заморозку.</p>
              </div>
              <button onClick={()=>setTab('companies')} style={{...btnG,padding:'7px 12px',fontSize:'12px'}}>Открыть компании</button>
              {canUseFollowups && <button onClick={()=>setTab('followups')} style={{...btnO,padding:'7px 12px',fontSize:'12px'}}>Открыть задачи</button>}
            </div>
            {accessWatchlist.length===0 && <div style={{padding:'18px',textAlign:'center',color:C.textMuted,fontSize:'12px'}}>По демо и оплатам критичных действий нет</div>}
            {accessWatchlist.slice(0,8).map(company=>{
              const state = company.billing_state || {};
              const colors = billingColorSet(state.level);
              const isDemoCompany = company.plan === 'demo';
              const isSuspended = Boolean(company.suspended_at || state.status === 'soft_frozen');
              return (
                <div key={company.id} style={{padding:'10px 0',borderTop:'1px solid '+C.border,display:'grid',gridTemplateColumns:'minmax(220px,1fr) auto',gap:'10px',alignItems:'center'}}>
                  <div style={{minWidth:0}}>
                    <b style={{color:C.text,fontSize:'13px',display:'block',overflowWrap:'anywhere'}}>{company.name}</b>
                    <p style={{color:C.textSec,fontSize:'11px',margin:'3px 0 0',overflowWrap:'anywhere'}}>{company.platform_account_name || 'аккаунт не связан'} · {state.reason || 'проверьте доступ'}</p>
                  </div>
                  <div style={{display:'flex',gap:'6px',alignItems:'center',justifyContent:'flex-end',flexWrap:'wrap'}}>
                    <span style={badge(colors.color,colors.bg,colors.border)}>{state.label || 'проверить'}</span>
                    {canManagePlatform && isDemoCompany && <button onClick={()=>extendCompanyTrial(company)} style={{...btnG,padding:'5px 10px',fontSize:'11px'}}>Продлить</button>}
                    {canManagePlatform && !isDemoCompany && state.status !== 'payment_overdue' && <button onClick={()=>markCompanyOverdue(company)} style={{...btnG,padding:'5px 10px',fontSize:'11px'}}>Просрочка</button>}
                    {canManageBilling && <button onClick={()=>openCompanyBillingDocument(company)} style={{...btnG,padding:'5px 10px',fontSize:'11px'}}>Счет</button>}
                    {canManageBilling && <button onClick={()=>openCompanyPayment(company)} style={{...btnO,padding:'5px 10px',fontSize:'11px'}}>Оплата</button>}
                    {canUseFollowups && <button onClick={()=>openFollowupForm(company,isDemoCompany?'demo':'payment')} style={{...btnG,padding:'5px 10px',fontSize:'11px'}}>Задача</button>}
                    {canManagePlatform && !isSuspended && <button onClick={()=>softSuspendCompany(company)} style={{...btnR,padding:'5px 10px',fontSize:'11px'}}>Мягко заморозить</button>}
                    {canManagePlatform && isSuspended && <button onClick={()=>resumeCompany(company)} style={{...btnGr,padding:'5px 10px',fontSize:'11px'}}>Разморозить</button>}
                  </div>
                </div>
              );
            })}
          </div>
          <div style={{...card,padding:'16px'}}>
            <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'10px'}}>📌 Следующие шаги</b>
            <p style={{color:C.textSec,fontSize:'12px',marginBottom:'8px'}}>Эта панель — заготовка для управления SaaS-платформой. Тут будут:</p>
            <ul style={{color:C.textSec,fontSize:'12px',paddingLeft:'18px',margin:0}}>
              <li>Графики MRR / LTV / churn rate</li>
              <li>Уведомления о просроченных платежах</li>
              <li>Автоматическое выставление счетов</li>
              <li>Интеграция с ЮKassa</li>
              <li>Email-рассылки клиентам</li>
            </ul>
          </div>
        </div>)}

        {/* Компании */}
        {tab==='companies' && (<div>
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'14px'}}>
	            <b style={{color:C.text,fontSize:'15px'}}>Клиентские аккаунты ({groupsWithLimitStatus.length}) / компании ({companies.length})</b>
	            {canManagePlatform && <button onClick={()=>{setShowNewCompany(true);setLastInviteCode(null);setClientCardRecognition(null);setCompanyPreview(null);}} style={btnO}>+ Подключить аккаунт/компанию</button>}
	          </div>
	          {canManagePlatform && showNewCompany && (<div style={{...card,padding:'16px',marginBottom:'14px'}}>
	            <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'10px'}}>Подключить аккаунт или компанию</b>
            {lastInviteCode && (<div style={{padding:'12px',backgroundColor:C.successLight,border:'1.5px solid '+C.successBorder,borderRadius:'8px',marginBottom:'12px'}}>
              <b style={{color:C.success,fontSize:'13px',display:'block',marginBottom:'6px'}}>✅ Компания создана!</b>
              <p style={{margin:'0 0 8px',fontSize:'12px',color:C.text}}>Отправьте директору ссылку для регистрации:</p>
              <div style={{padding:'10px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border,borderRadius:'6px',fontSize:'12px',color:C.text,wordBreak:'break-all',userSelect:'all',marginBottom:'8px'}}>{window.location.origin+'/?invite='+lastInviteCode}</div>
              <button onClick={()=>navigator.clipboard.writeText(window.location.origin+'/?invite='+lastInviteCode).then(()=>alert('Скопировано'))} style={{...btnO,padding:'5px 12px',fontSize:'12px'}}>📋 Скопировать</button>
	              <button onClick={()=>{setShowNewCompany(false);setLastInviteCode(null);setNewCompany(emptyCompanyForm);setClientCardRecognition(null);setCompanyPreview(null);}} style={{...btnG,padding:'5px 12px',fontSize:'12px',marginLeft:'6px'}}>Закрыть</button>
	            </div>)}
	            {!lastInviteCode && (<>
              <div style={{padding:'12px',backgroundColor:C.infoLight,border:'1.5px solid '+C.infoBorder,borderRadius:'10px',marginBottom:'12px'}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap'}}>
                  <div>
                    <b style={{color:C.info,fontSize:'13px',display:'block'}}>⚡ Быстрая загрузка карты клиента</b>
                    <p style={{color:C.textSec,fontSize:'11px',margin:'3px 0 0'}}>Фото, PDF, Word, Excel, TXT/CSV/RTF или другой файл с реквизитами. Система заполнит поля формы, но компанию создаст только после сохранения.</p>
                  </div>
                  <label style={{...btnO,cursor:clientCardScanning?'default':'pointer',opacity:clientCardScanning?0.65:1}}>
                    {clientCardScanning?'⏳ Распознаю...':'📷 Загрузить карту'}
                    <input type='file' accept='*/*' disabled={clientCardScanning} style={{display:'none'}} onChange={recognizeClientCard}/>
                  </label>
                </div>
                {clientCardRecognition && (
                  <div style={{marginTop:'10px',padding:'10px',backgroundColor:C.card,border:'1px solid '+C.border,borderRadius:'8px'}}>
                    <div style={{display:'flex',justifyContent:'space-between',gap:'8px',alignItems:'center',flexWrap:'wrap',marginBottom:'8px'}}>
                      <b style={{color:C.text,fontSize:'12px'}}>Распознано: {clientCardRecognition.source === 'ai' ? 'AI/OCR' : 'правила'}</b>
                      <span style={badge((clientCardRecognition.confidence || 0) >= 0.7 ? C.success : C.warning,(clientCardRecognition.confidence || 0) >= 0.7 ? C.successLight : C.warningLight,(clientCardRecognition.confidence || 0) >= 0.7 ? C.successBorder : C.warningBorder)}>
                        уверенность {Math.round(Number(clientCardRecognition.confidence || 0) * 100)}%
                      </span>
                    </div>
                    <div style={{display:'flex',gap:'6px',flexWrap:'wrap'}}>
                      {Object.entries({
                        companyName:'Компания',
                        inn:'ИНН',
                        kpp:'КПП',
                        contactName:'Контакт',
                        contactPhone:'Телефон',
                        contactEmail:'Email',
                        legalAddress:'Адрес',
                        website:'Сайт',
                      }).filter(([key])=>clientCardRecognition.fields?.[key]).map(([key,label])=>(
                        <span key={key} style={badge(C.textSec,C.bg,C.border)}>{label}: {String(clientCardRecognition.fields[key]).slice(0,60)}</span>
                      ))}
                    </div>
                    {(clientCardRecognition.warnings || []).length > 0 && (
                      <p style={{color:C.warning,fontSize:'11px',margin:'8px 0 0'}}>⚠️ {clientCardRecognition.warnings.join(' · ')}</p>
                    )}
                    <button type='button' onClick={()=>applyClientCardFields(clientCardRecognition.fields || {})} style={{...btnG,padding:'5px 10px',fontSize:'11px',marginTop:'8px'}}>Применить поля еще раз</button>
                  </div>
                )}
              </div>
	              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px'}}>
	                <select value={newCompany.platformAccountId} onChange={e=>setNewCompany({...newCompany,platformAccountId:e.target.value,platformAccountName:e.target.value?'':newCompany.platformAccountName})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}>
	                  <option value=''>Новый клиентский аккаунт</option>
	                  {groupsWithLimitStatus.map(g=><option key={g.id} value={g.id}>Добавить компанию в: {g.name}</option>)}
	                </select>
	                {!newCompany.platformAccountId && <input placeholder='Клиентский аккаунт / группа (например: Земля Групп)' value={newCompany.platformAccountName} onChange={e=>setNewCompany({...newCompany,platformAccountName:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>}
	                <input placeholder='Компания / юрлицо * (например: ООО Земля 1)' value={newCompany.name} onChange={e=>setNewCompany({...newCompany,name:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                <input placeholder='ИНН' value={newCompany.inn} onChange={e=>setNewCompany({...newCompany,inn:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='КПП' value={newCompany.kpp} onChange={e=>setNewCompany({...newCompany,kpp:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Контактное лицо' value={newCompany.contactName} onChange={e=>setNewCompany({...newCompany,contactName:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Телефон' value={newCompany.contactPhone} onChange={e=>setNewCompany({...newCompany,contactPhone:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Email' value={newCompany.contactEmail} onChange={e=>setNewCompany({...newCompany,contactEmail:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
	                <select value={newCompany.plan} onChange={e=>applyTariffToForm(e.target.value)} style={{...inp,marginBottom:0}}>
	                  {tariffOptions.map(t=><option key={t.id} value={t.id}>{t.name}{t.monthlyFee ? ' · '+Number(t.monthlyFee).toLocaleString('ru-RU')+' ₽/мес' : ' · демо'}</option>)}
	                </select>
	                {newCompany.plan==='demo' ? (
	                  <input type='number' placeholder='Дней триала' value={newCompany.trialDays} onChange={e=>setNewCompany({...newCompany,trialDays:e.target.value})} style={{...inp,marginBottom:0}}/>
	                ) : (
	                  <input type='number' placeholder='₽ в месяц' value={newCompany.monthlyFee} onChange={e=>setNewCompany({...newCompany,monthlyFee:e.target.value})} style={{...inp,marginBottom:0}}/>
	                )}
	                <input type='number' placeholder='Лимит объектов' value={newCompany.maxProjects} onChange={e=>setNewCompany({...newCompany,maxProjects:e.target.value})} style={{...inp,marginBottom:0}}/>
	                <input type='number' placeholder='Лимит пользователей' value={newCompany.maxUsers} onChange={e=>setNewCompany({...newCompany,maxUsers:e.target.value})} style={{...inp,marginBottom:0}}/>
	              </div>
              <textarea placeholder='Заметки (опц.)' value={newCompany.notes} onChange={e=>setNewCompany({...newCompany,notes:e.target.value})} style={{...inp,height:'50px',marginTop:'8px'}}/>
              <div style={{display:'flex',gap:'8px',alignItems:'center',flexWrap:'wrap',margin:'8px 0'}}>
                <button type='button' onClick={()=>runCompanyPreview(newCompany)} disabled={companyPreviewLoading} style={{...btnG,padding:'7px 12px',fontSize:'12px',opacity:companyPreviewLoading?0.65:1}}>
                  {companyPreviewLoading?'⏳ Проверяю...':'🔎 Проверить ИНН и лимиты'}
                </button>
                <span style={{color:C.textMuted,fontSize:'11px'}}>Проверка не создает компанию и не выдает доступ.</span>
              </div>
              {companyPreview && (
                <div style={{padding:'10px',border:'1.5px solid '+(companyPreview.canCreate?C.successBorder:C.dangerBorder),backgroundColor:companyPreview.canCreate?C.successLight:C.dangerLight,borderRadius:'8px',marginBottom:'8px'}}>
                  <b style={{color:companyPreview.canCreate?C.success:C.danger,fontSize:'12px',display:'block',marginBottom:'6px'}}>
                    {companyPreview.canCreate?'Проверка пройдена':'Нужно разобрать перед созданием'}
                  </b>
                  {companyPreview.account && <p style={{color:C.textSec,fontSize:'11px',margin:'0 0 5px'}}>Аккаунт: {companyPreview.account.name} · тариф {companyPreview.tariff?.name || companyPreview.plan}</p>}
                  {!companyPreview.account && <p style={{color:C.textSec,fontSize:'11px',margin:'0 0 5px'}}>Будет создан новый клиентский аккаунт · тариф {companyPreview.tariff?.name || companyPreview.plan}</p>}
                  {(companyPreview.blockingReasons || []).map(reason=><p key={reason} style={{color:C.danger,fontSize:'11px',fontWeight:800,margin:'3px 0'}}>⛔ {reason}</p>)}
                  {(companyPreview.limitWarnings || []).map(w=>(
                    <p key={w.key} style={{color:w.level==='danger'?C.danger:C.warning,fontSize:'11px',fontWeight:700,margin:'3px 0'}}>⚠️ {w.text}</p>
                  ))}
                  {(companyPreview.duplicates || []).length > 0 && (
                    <div style={{display:'grid',gap:'5px',marginTop:'7px'}}>
                      {companyPreview.duplicates.map(duplicate=>(
                        <div key={duplicate.id} style={{padding:'7px',border:'1px solid '+C.border,borderRadius:'7px',backgroundColor:C.card}}>
                          <b style={{color:C.text,fontSize:'11px',display:'block'}}>{duplicate.name}</b>
                          <span style={{color:C.textMuted,fontSize:'10px'}}>ИНН {duplicate.inn || '—'}{duplicate.kpp?' · КПП '+duplicate.kpp:''} · {duplicate.platform_account_name || 'без аккаунта'} · {duplicate.active?'активна':'неактивна'}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
              <div style={{display:'flex',gap:'8px',marginTop:'10px'}}>
                <button onClick={async()=>{
                  if (!newCompany.name) { alert('Укажите название'); return; }
                  const preview = await runCompanyPreview(newCompany, true);
                  if (!preview) return;
                  if (!preview.canCreate) {
                    const reasons = (preview.blockingReasons || []).join('\n');
                    alert('Компания не создана. Сначала разберите предупреждения:\n' + reasons);
                    return;
                  }
                  const r = await sendJson('/system/companies',{method:'POST',body:JSON.stringify({...newCompany,createdBy:user.name})});
                  const data = await r.json().catch(()=>({}));
                  if (data.id) { setLastInviteCode(data.inviteCode); await loadAll(); }
                  else { alert(companyCreateErrorText(data)); }
                }} style={btnO}>✓ Создать компанию + ссылку</button>
	                <button onClick={()=>{setShowNewCompany(false);setClientCardRecognition(null);setCompanyPreview(null);}} style={btnG}>Отмена</button>
	              </div>
	            </>)}
	          </div>)}
	          {companies.length===0 && <div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}>Пока подключена только ваша компания. Нажмите «+ Подключить аккаунт/компанию» чтобы добавить клиента.</div>}
	          {groupsWithLimitStatus.map(group=>(
	            <div key={group.id} style={{...card,padding:'14px',marginBottom:'12px'}}>
	              <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap',marginBottom:'10px'}}>
	                <div>
	                  <b style={{color:C.text,fontSize:'14px'}}>🧭 {group.name}</b>
	                  <p style={{color:C.textMuted,margin:'4px 0 0',fontSize:'11px'}}>Компаний: {group.companies.length} · активных пользователей: {group.users}{group.usersTotal!==group.users?' / всего '+group.usersTotal:''} · объектов: {group.projects} · оплачено {Math.round(group.paid).toLocaleString('ru-RU')} ₽</p>
	                </div>
		                <span style={badge(C.info,C.infoLight,C.infoBorder)}>{tariffById[group.plan]?.name || group.plan || 'тариф не задан'}</span>
	              </div>
	              {group.usersByRole.length > 0 && (
	                <div style={{display:'flex',gap:'6px',flexWrap:'wrap',alignItems:'center',margin:'0 0 10px'}}>
	                  <span style={{color:C.textMuted,fontSize:'11px'}}>Роли в лимите пользователей:</span>
	                  {group.usersByRole.slice(0,8).map(roleInfo=>(
	                    <span key={roleInfo.role} style={badge(C.textSec,C.bg,C.border)}>
	                      {roleInfo.role}: {roleInfo.active}{roleInfo.total!==roleInfo.active?' / '+roleInfo.total:''}
	                    </span>
	                  ))}
	                  {group.usersByRole.length>8 && <span style={{color:C.textMuted,fontSize:'11px'}}>+{group.usersByRole.length-8} ролей</span>}
	                </div>
	              )}
	              {group.limitWarnings.length > 0 && (
	                <div style={{display:'grid',gap:'6px',margin:'0 0 10px'}}>
	                  {group.limitWarnings.map(w=>{
	                    const isDanger = w.level === 'danger';
	                    return (
	                      <div key={w.key} style={{padding:'8px 10px',border:'1.5px solid '+(isDanger?C.dangerBorder:C.warningBorder),backgroundColor:isDanger?C.dangerLight:C.warningLight,borderRadius:'8px',color:isDanger?C.danger:C.warning,fontSize:'12px',fontWeight:700}}>
	                        {isDanger?'🚨':'⚠️'} {w.text}. Клиент не блокируется автоматически.
	                      </div>
	                    );
	                  })}
	                </div>
	              )}
	              {group.companies.map(c=>{
	                const isDemo = c.plan==='demo';
	                const billingState = c.billing_state || {};
	                const isSuspended = Boolean(c.suspended_at || billingState.status === 'soft_frozen');
	                const billingColors = billingColorSet(billingState.level || (isDemo ? 'info' : 'success'));
	                const activeUsers = Number(c.users_active_count ?? c.users_count ?? 0);
	                const totalUsers = Number(c.users_count ?? activeUsers);
	                const roleSummary = (c.users_by_role || []).filter(roleInfo=>Number(roleInfo.active || roleInfo.total || 0)>0);
	                return (<div key={c.id} style={{padding:'12px 0',borderTop:'1px solid '+C.border}}>
	                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
	                    <div style={{flex:1,minWidth:'250px'}}>
	                      <b style={{color:C.text,fontSize:'14px'}}>{c.name}</b>{c.id===1 && <span style={{marginLeft:'8px',fontSize:'10px',color:C.textMuted}}>(основная)</span>}
	                      <p style={{color:C.textSec,margin:'3px 0',fontSize:'12px'}}>
	                        {c.inn?'ИНН '+c.inn+' · ':''}{c.contact_name||'—'}{c.contact_phone?' · '+c.contact_phone:''}{c.contact_email?' · '+c.contact_email:''}
	                      </p>
	                      <p style={{color:C.textMuted,margin:0,fontSize:'11px'}}>
	                        👥 {activeUsers} активн.{totalUsers!==activeUsers?' / '+totalUsers+' всего':''} · 🏗 {c.projects_count} объектов · 💰 заплачено {Math.round(c.total_paid).toLocaleString('ru-RU')} ₽
	                        {c.trial_until && ' · 🎁 триал до '+c.trial_until}
	                        {c.plan_expires_at && ' · 💼 оплачено до '+c.plan_expires_at}
	                        {(c.max_projects || c.max_users) && ' · лимит '+(c.max_projects || '∞')+' объектов / '+(c.max_users || '∞')+' пользователей'}
	                      </p>
	                      {roleSummary.length > 0 && (
	                        <p style={{color:C.textMuted,margin:'5px 0 0',fontSize:'10px'}}>
	                          Роли: {roleSummary.slice(0,6).map(roleInfo=>`${roleInfo.role}: ${roleInfo.active}${roleInfo.total!==roleInfo.active?' / '+roleInfo.total:''}`).join(' · ')}{roleSummary.length>6?' · +'+(roleSummary.length-6):''}
	                        </p>
	                      )}
	                    </div>
	                    <div style={{display:'flex',gap:'4px',flexWrap:'wrap',alignItems:'flex-start'}}>
	                      <span style={badge(billingColors.color,billingColors.bg,billingColors.border)}>{billingState.label || (isSuspended?'⏸ Заморожена':isDemo?'🎁 Демо':(tariffById[c.plan]?.name || c.plan))}</span>
	                      <span style={badge(C.textSec,C.bg,C.border)}>{tariffById[c.plan]?.name || c.plan || 'тариф'}</span>
	                      {c.monthly_fee>0 && <span style={badge(C.text,C.bg,C.border)}>{Number(c.monthly_fee).toLocaleString('ru-RU')+' ₽/мес'}</span>}
	                    </div>
	                  </div>
	                  {billingState.reason && <p style={{color:billingColors.color,fontSize:'11px',margin:'6px 0 0',fontWeight:billingNeedsAction(billingState)?700:400}}>🚦 {billingState.reason}</p>}
	                  {canManagePlatform && c.id!==1 && (
	                    <div style={{display:'flex',gap:'6px',marginTop:'8px',flexWrap:'wrap'}}>
	                      {isDemo && <button onClick={()=>extendCompanyTrial(c)} style={{...btnG,padding:'4px 10px',fontSize:'11px'}}>📅 Продлить триал</button>}
	                      {!isDemo && !isSuspended && <button onClick={()=>markCompanyOverdue(c)} style={{...btnG,padding:'4px 10px',fontSize:'11px'}}>⚠️ Просрочка</button>}
	                      {!isSuspended && <button onClick={()=>softSuspendCompany(c)} style={{...btnR,padding:'4px 10px',fontSize:'11px'}}>⏸ Мягко заморозить</button>}
	                      {isSuspended && <button onClick={()=>resumeCompany(c)} style={{...btnGr,padding:'4px 10px',fontSize:'11px'}}>▶ Разморозить</button>}
                      {canManageBilling && <button onClick={()=>openCompanyPayment(c)} style={{...btnO,padding:'4px 10px',fontSize:'11px'}}>💰 Зачислить оплату</button>}
                      {canManageBilling && <button onClick={()=>openCompanyBillingDocument(c)} style={{...btnG,padding:'4px 10px',fontSize:'11px'}}>📄 Счет/акт</button>}
	                    </div>
	                  )}
	                  {c.suspended_reason && <p style={{color:C.danger,fontSize:'11px',margin:'6px 0 0',fontStyle:'italic'}}>⚠️ {c.suspended_reason}</p>}
	                </div>);
	              })}
	            </div>
	          ))}
	        </div>)}

        {/* Пользователи клиентов */}
        {tab==='clientUsers' && canViewClientUsers && (<div>
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'12px',flexWrap:'wrap',marginBottom:'14px'}}>
            <div>
              <b style={{color:C.text,fontSize:'15px',display:'block'}}>Пользователи клиентских групп ({clientUsers.length})</b>
              <p style={{color:C.textSec,fontSize:'12px',margin:'4px 0 0'}}>Доступы клиентов не удаляем: отключаем или переносим между компаниями с записью в журнал платформы.</p>
            </div>
            <div style={{display:'flex',gap:'6px',flexWrap:'wrap'}}>
              <span style={badge(C.success,C.successLight,C.successBorder)}>активных {clientUserStats.active}</span>
              <span style={badge(C.textSec,C.bg,C.border)}>отключено {clientUserStats.inactive}</span>
              {clientUserRoleStats.slice(0,5).map(roleInfo=>(
                <span key={roleInfo.role} style={badge(C.textSec,C.bg,C.border)}>
                  {roleInfo.role}: {roleInfo.active}{roleInfo.total!==roleInfo.active?' / '+roleInfo.total:''}
                </span>
              ))}
            </div>
          </div>
          <div style={{...card,padding:'12px',marginBottom:'12px'}}>
            <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:'8px'}}>
              <select value={clientUserDraftFilters.platformAccountId} onChange={e=>setClientUserDraftFilters({...clientUserDraftFilters,platformAccountId:e.target.value,companyId:''})} style={{...inp,marginBottom:0}}>
                <option value=''>Все аккаунты</option>
                {groupsWithLimitStatus.map(group=><option key={group.id} value={group.id}>{group.name}</option>)}
              </select>
              <select value={clientUserDraftFilters.companyId} onChange={e=>setClientUserDraftFilters({...clientUserDraftFilters,companyId:e.target.value})} style={{...inp,marginBottom:0}}>
                <option value=''>Все компании</option>
                {clientUserCompanyOptions.map(company=><option key={company.id} value={company.id}>{company.name}</option>)}
              </select>
              <select value={clientUserDraftFilters.role} onChange={e=>setClientUserDraftFilters({...clientUserDraftFilters,role:e.target.value})} style={{...inp,marginBottom:0}}>
                <option value=''>Все роли</option>
                {clientUserRoleOptions.map(role=><option key={role} value={role}>{role}</option>)}
              </select>
              <select value={clientUserDraftFilters.active} onChange={e=>setClientUserDraftFilters({...clientUserDraftFilters,active:e.target.value})} style={{...inp,marginBottom:0}}>
                <option value=''>Все статусы</option>
                <option value='true'>Активные</option>
                <option value='false'>Отключенные</option>
              </select>
              <input placeholder='Поиск: имя, email, роль, компания' value={clientUserDraftFilters.search} onChange={e=>setClientUserDraftFilters({...clientUserDraftFilters,search:e.target.value})} style={{...inp,marginBottom:0}}/>
            </div>
            <div style={{display:'flex',gap:'8px',flexWrap:'wrap',marginTop:'10px',alignItems:'center'}}>
              <button onClick={()=>setClientUserFilters(clientUserDraftFilters)} style={{...btnO,padding:'7px 12px',fontSize:'12px'}}>Показать</button>
              <button onClick={()=>{setClientUserDraftFilters(emptyClientUserFilters);setClientUserFilters(emptyClientUserFilters);}} style={{...btnG,padding:'7px 12px',fontSize:'12px'}}>Сбросить</button>
              <span style={{color:C.textMuted,fontSize:'11px'}}>{hasClientUserFilters?'Показаны пользователи по фильтрам':'Показаны пользователи всех клиентских компаний'}</span>
            </div>
          </div>
          {clientUsers.length===0 && <div style={{...card,padding:'26px',textAlign:'center',color:C.textMuted}}>Пользователей по выбранным фильтрам нет</div>}
          {clientUsers.map(item=>{
            const selectedCompany = clientUserMoveDrafts[item.id] || item.companyId || '';
            const canTransfer = canManagePlatform && selectedCompany && String(selectedCompany) !== String(item.companyId || '');
            const moveOptions = clientUserMoveCompanyOptions(item);
            return (
              <div key={item.id} style={{...card,padding:'12px',marginBottom:'8px'}}>
                <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(220px,1fr))',gap:'10px',alignItems:'center'}}>
                  <div style={{minWidth:0}}>
                    <b style={{color:C.text,fontSize:'13px',display:'block',overflowWrap:'anywhere'}}>{item.name || item.email}</b>
                    <p style={{color:C.textSec,fontSize:'11px',margin:'3px 0 0',overflowWrap:'anywhere'}}>{item.email || 'без email'} · {item.role || 'роль не указана'}{item.projectName?' · объект '+item.projectName:''}</p>
                    <p style={{color:C.textMuted,fontSize:'10px',margin:'2px 0 0'}}>{item.twoFactorEnabled?'2FA включена':(item.twoFactorRequired?'2FA требуется':'2FA не требуется')} · создан {item.createdAt || '—'}</p>
                  </div>
                  <div style={{minWidth:0}}>
                    <p style={{color:C.textSec,fontSize:'11px',margin:'0 0 6px'}}>{item.platformAccountName || 'аккаунт не связан'} · {item.companyName || 'компания не связана'}</p>
                    {canManagePlatform && (
                      <div style={{display:'flex',gap:'6px',alignItems:'center',flexWrap:'wrap'}}>
                        <select value={selectedCompany} onChange={e=>setClientUserMoveDrafts(current=>({...current,[item.id]:e.target.value}))} style={{...inp,marginBottom:0,minWidth:'190px',fontSize:'11px',padding:'6px 8px'}}>
                          <option value=''>Выбрать компанию</option>
                          {moveOptions.map(company=><option key={company.id} value={company.id}>{company.name}</option>)}
                        </select>
                        <button disabled={!canTransfer} onClick={()=>transferClientUser(item)} style={{...btnG,padding:'6px 10px',fontSize:'11px',opacity:canTransfer?1:0.55}}>Перенести</button>
                      </div>
                    )}
                  </div>
                  <div style={{display:'flex',gap:'6px',alignItems:'center',justifyContent:'flex-end',flexWrap:'wrap'}}>
                    <span style={badge(item.active?C.success:C.textMuted,item.active?C.successLight:C.bg,item.active?C.successBorder:C.border)}>{item.active?'Активен':'Отключен'}</span>
                    {canManagePlatform && <button onClick={()=>toggleClientUserAccess(item)} style={{...btnG,padding:'6px 10px',fontSize:'11px'}}>{item.active?'Отключить':'Включить'}</button>}
                  </div>
                </div>
              </div>
            );
          })}
        </div>)}

	        {/* Тарифы */}
	        {tab==='tariffs' && (<div>
	          <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'12px',flexWrap:'wrap',marginBottom:'14px'}}>
	            <div>
	              <b style={{color:C.text,fontSize:'15px',display:'block'}}>Тарифная сетка платформы</b>
	              <p style={{color:C.textSec,fontSize:'12px',margin:'4px 0 0'}}>Гибридная модель: аккаунт клиента + компании + объекты + пользователи + AI/OCR.</p>
	            </div>
	            <span style={badge(C.warning,C.warningLight,C.warningBorder)}>read-only v1</span>
	          </div>
	          <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(240px,1fr))',gap:'12px'}}>
	            {tariffOptions.map(t=>{
	              const isCustom = t.id === 'enterprise';
	              return (<div key={t.id} style={{...card,padding:'16px',border:t.id==='group'?'1.5px solid '+C.accent:card.border}}>
	                <div style={{display:'flex',justifyContent:'space-between',gap:'8px',alignItems:'flex-start',marginBottom:'10px'}}>
	                  <div>
	                    <b style={{color:C.text,fontSize:'15px',display:'block'}}>{t.name}</b>
	                    <p style={{color:C.textMuted,fontSize:'11px',margin:'4px 0 0'}}>{t.audience || 'Тариф платформы'}</p>
	                  </div>
	                  <b style={{color:C.success,fontSize:'16px',whiteSpace:'nowrap'}}>{isCustom?'от ':''}{Number(t.monthlyFee || 0).toLocaleString('ru-RU')} ₽</b>
	                </div>
	                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginBottom:'10px'}}>
	                  <div style={{padding:'8px',border:'1px solid '+C.border,borderRadius:'8px'}}><span style={{color:C.textMuted,fontSize:'10px',display:'block'}}>Компании</span><b style={{color:C.text,fontSize:'13px'}}>{t.includedCompanies ?? 'инд.'}</b></div>
	                  <div style={{padding:'8px',border:'1px solid '+C.border,borderRadius:'8px'}}><span style={{color:C.textMuted,fontSize:'10px',display:'block'}}>Объекты</span><b style={{color:C.text,fontSize:'13px'}}>{t.maxProjects ?? 'инд.'}</b></div>
	                  <div style={{padding:'8px',border:'1px solid '+C.border,borderRadius:'8px'}}><span style={{color:C.textMuted,fontSize:'10px',display:'block'}}>Пользователи</span><b style={{color:C.text,fontSize:'13px'}}>{t.maxUsers ?? 'инд.'}</b></div>
	                  <div style={{padding:'8px',border:'1px solid '+C.border,borderRadius:'8px'}}><span style={{color:C.textMuted,fontSize:'10px',display:'block'}}>OCR/мес</span><b style={{color:C.text,fontSize:'13px'}}>{t.ocrPages ?? 'инд.'}</b></div>
	                </div>
	                <div style={{display:'flex',gap:'6px',flexWrap:'wrap'}}>
	                  {(t.features || []).map(f=><span key={f} style={badge(C.textSec,C.bg,C.border)}>{f}</span>)}
	                </div>
	              </div>);
	            })}
	          </div>
	          <div style={{...card,padding:'14px',marginTop:'14px',backgroundColor:C.infoLight,border:'1.5px solid '+C.infoBorder}}>
	            <b style={{color:C.info,fontSize:'13px',display:'block',marginBottom:'6px'}}>Дополнительные правила для следующего блока</b>
	            <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 6px'}}>Доп. компания: 7 000-10 000 ₽/мес; доп. активный объект: 2 000-5 000 ₽/мес; OCR/AI сверх лимита — пакетами. Эти правила пока только отображаются, автоматических списаний и блокировок нет.</p>
	          </div>
	        </div>)}

        {/* Платежи */}
        {tab==='payments' && (<div>
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap',marginBottom:'14px'}}>
            <div>
              <b style={{color:C.text,fontSize:'15px',display:'block'}}>Биллинг платформы</b>
              <p style={{color:C.textSec,fontSize:'12px',margin:'3px 0 0'}}>Документы создают основание, а факт денег фиксируется отдельным платежом.</p>
            </div>
            <div style={{display:'flex',gap:'8px',flexWrap:'wrap'}}>
              <button onClick={()=>setShowNewBillingDocument(!showNewBillingDocument)} style={btnG}>+ Счет/акт</button>
              <button onClick={()=>setShowNewPayment(!showNewPayment)} style={btnO}>+ Зачислить платеж</button>
            </div>
          </div>

          {paymentProviders.length > 0 && (<div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(190px,1fr))',gap:'8px',marginBottom:'14px'}}>
            {paymentProviders.map(provider=>{
              const ready = provider.configured;
              return (<div key={provider.id} style={{...card,padding:'11px',border:'1.5px solid '+(ready?C.successBorder:C.warningBorder),backgroundColor:ready?C.successLight:C.warningLight}}>
                <b style={{color:ready?C.success:C.warning,fontSize:'12px',display:'block'}}>{provider.label}</b>
                <p style={{color:C.textSec,fontSize:'11px',margin:'4px 0 0'}}>{ready?'Готов к использованию':'Нужны ключи в .env'} · {provider.mode}</p>
              </div>);
            })}
          </div>)}

          <div style={{...card,padding:'12px',marginBottom:'14px',backgroundColor:C.warningLight,border:'1.5px solid '+C.warningBorder}}>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap',marginBottom:'8px'}}>
              <div>
                <b style={{color:C.warning,fontSize:'13px',display:'block'}}>События провайдеров ({paymentEvents.length})</b>
                <p style={{color:C.textSec,fontSize:'11px',margin:'3px 0 0'}}>Входящие события ЮKassa/Robokassa не являются оплатой, пока биллинг не зачислит фактический платеж.</p>
              </div>
              <button onClick={exportPaymentEvents} style={{...btnG,padding:'7px 12px',fontSize:'12px'}}>⬇ Реестр CSV</button>
            </div>
            <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(150px,1fr))',gap:'8px',marginBottom:'10px'}}>
              <select value={paymentEventDraftFilters.platformAccountId} onChange={e=>setPaymentEventDraftFilters({...paymentEventDraftFilters,platformAccountId:e.target.value,companyId:''})} style={{...inp,marginBottom:0}}>
                <option value=''>Все аккаунты</option>
                {companyGroups.map(group=><option key={group.id} value={group.id}>{group.name}</option>)}
              </select>
              <select value={paymentEventDraftFilters.companyId} onChange={e=>setPaymentEventDraftFilters({...paymentEventDraftFilters,companyId:e.target.value})} style={{...inp,marginBottom:0}}>
                <option value=''>Все компании</option>
                {paymentEventCompanyOptions.filter(c=>c.id!==1).map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <select value={paymentEventDraftFilters.provider} onChange={e=>setPaymentEventDraftFilters({...paymentEventDraftFilters,provider:e.target.value})} style={{...inp,marginBottom:0}}>
                <option value=''>Все провайдеры</option>
                <option value='yukassa'>ЮKassa</option>
                <option value='robokassa'>Robokassa</option>
              </select>
              <select value={paymentEventDraftFilters.actionStatus} onChange={e=>setPaymentEventDraftFilters({...paymentEventDraftFilters,actionStatus:e.target.value})} style={{...inp,marginBottom:0}}>
                <option value=''>Все статусы</option>
                <option value='received'>Получено</option>
                <option value='needs_review'>Нужна проверка</option>
                <option value='payment_recorded'>Платеж зачислен</option>
              </select>
              <input type='date' value={paymentEventDraftFilters.dateFrom} onChange={e=>setPaymentEventDraftFilters({...paymentEventDraftFilters,dateFrom:e.target.value})} style={{...inp,marginBottom:0}}/>
              <input type='date' value={paymentEventDraftFilters.dateTo} onChange={e=>setPaymentEventDraftFilters({...paymentEventDraftFilters,dateTo:e.target.value})} style={{...inp,marginBottom:0}}/>
              <input placeholder='Поиск: событие, счет, компания' value={paymentEventDraftFilters.search} onChange={e=>setPaymentEventDraftFilters({...paymentEventDraftFilters,search:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
            </div>
            <div style={{display:'flex',gap:'8px',flexWrap:'wrap',marginBottom:'10px',alignItems:'center'}}>
              <button onClick={()=>setPaymentEventFilters(paymentEventDraftFilters)} style={{...btnO,padding:'7px 12px',fontSize:'12px'}}>Показать</button>
              <button onClick={()=>{setPaymentEventDraftFilters(emptyPaymentEventFilters);setPaymentEventFilters(emptyPaymentEventFilters);}} style={{...btnG,padding:'7px 12px',fontSize:'12px'}}>Сбросить</button>
              <span style={{color:C.textMuted,fontSize:'11px'}}>{hasPaymentEventFilters?'Показаны события по фильтрам':'Показаны последние события провайдеров'}</span>
            </div>
            <div style={{display:'grid',gap:'6px'}}>
              {paymentEvents.length===0 && <div style={{padding:'18px',textAlign:'center',color:C.textMuted,fontSize:'12px',backgroundColor:C.card,border:'1px solid '+C.border,borderRadius:'8px'}}>Событий по выбранным фильтрам нет</div>}
              {paymentEvents.map(event=>{
                const eventColors = paymentEventStatusColor(event.action_status);
                const canConfirmEvent = Boolean(event.canConfirm);
                return (<div key={event.id} style={{display:'grid',gridTemplateColumns:'minmax(90px,130px) minmax(0,1fr) auto',gap:'8px',alignItems:'center',padding:'8px',border:'1px solid '+C.border,borderRadius:'8px',backgroundColor:C.card}}>
                  <div>
                    <b style={{color:C.text,fontSize:'12px',display:'block'}}>{event.providerLabel || event.provider || 'provider'}</b>
                    <span style={{color:C.textMuted,fontSize:'10px'}}>{event.received_at ? String(event.received_at).slice(0,16).replace('T',' ') : ''}</span>
                  </div>
                  <div style={{minWidth:0}}>
                    <p style={{color:C.textSec,fontSize:'11px',margin:0,overflowWrap:'anywhere'}}>{event.event_type || 'event'} · {event.provider_status || 'без статуса'} · {event.billing_document_number || 'документ не найден'} · {Number(event.amount || 0).toLocaleString('ru-RU')} ₽</p>
                    <p style={{color:C.textMuted,fontSize:'10px',margin:'2px 0 0'}}>{event.platform_account_name || '—'} · {event.company_name || '—'}{event.payment_id ? ' · платеж #'+event.payment_id : ''}</p>
                    <p style={{color:canConfirmEvent?C.success:C.warning,fontSize:'10px',margin:'2px 0 0'}}>{event.reviewReason || 'принято в журнал'}</p>
                  </div>
                  <div style={{display:'flex',gap:'6px',alignItems:'center',justifyContent:'flex-end',flexWrap:'wrap'}}>
                    <span style={badge(eventColors.color,eventColors.bg,eventColors.border)}>{event.actionStatusLabel || event.action_status || 'Получено'}</span>
                    {event.amountMatches === false && <span style={badge(C.danger,C.dangerLight,C.dangerBorder)}>сумма</span>}
                    {event.providerMatches === false && <span style={badge(C.danger,C.dangerLight,C.dangerBorder)}>провайдер</span>}
                    {event.currencyMatches === false && <span style={badge(C.danger,C.dangerLight,C.dangerBorder)}>валюта</span>}
                    {canConfirmEvent && <button onClick={()=>confirmPaymentEvent(event)} style={{...btnO,padding:'5px 10px',fontSize:'11px'}}>Зачислить</button>}
                  </div>
                </div>);
              })}
            </div>
          </div>

          {showNewBillingDocument && (<div style={{...card,padding:'16px',marginBottom:'14px'}}>
            <b style={{color:C.text,fontSize:'13px',display:'block',marginBottom:'10px'}}>Создать платежный документ платформы</b>
            <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(170px,1fr))',gap:'8px'}}>
              <select value={newBillingDocument.companyId} onChange={e=>setNewBillingDocument({...newBillingDocument,companyId:Number(e.target.value)})} style={{...inp,marginBottom:0}}>
                <option value=''>Компания *</option>
                {companies.filter(c=>c.id!==1).map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <select value={newBillingDocument.documentType} onChange={e=>setNewBillingDocument({...newBillingDocument,documentType:e.target.value})} style={{...inp,marginBottom:0}}>
                <option value='invoice'>Счет</option>
                <option value='act'>Акт</option>
                <option value='offer'>КП</option>
              </select>
              <select value={newBillingDocument.status} onChange={e=>setNewBillingDocument({...newBillingDocument,status:e.target.value})} style={{...inp,marginBottom:0}}>
                <option value='draft'>Черновик</option>
                <option value='issued'>Выставлен</option>
                <option value='payment_expected'>Ожидает оплату</option>
              </select>
              <input type='number' placeholder='Сумма ₽ *' value={newBillingDocument.amount} onChange={e=>setNewBillingDocument({...newBillingDocument,amount:e.target.value})} style={{...inp,marginBottom:0}}/>
              <input type='date' value={newBillingDocument.issueDate} onChange={e=>setNewBillingDocument({...newBillingDocument,issueDate:e.target.value})} style={{...inp,marginBottom:0}}/>
              <input type='date' placeholder='Оплатить до' value={newBillingDocument.dueDate} onChange={e=>setNewBillingDocument({...newBillingDocument,dueDate:e.target.value})} style={{...inp,marginBottom:0}}/>
              <input type='date' placeholder='Период с' value={newBillingDocument.periodStart} onChange={e=>setNewBillingDocument({...newBillingDocument,periodStart:e.target.value})} style={{...inp,marginBottom:0}}/>
              <input type='date' placeholder='Период по' value={newBillingDocument.periodEnd} onChange={e=>setNewBillingDocument({...newBillingDocument,periodEnd:e.target.value})} style={{...inp,marginBottom:0}}/>
              <select value={newBillingDocument.paymentProvider} onChange={e=>setNewBillingDocument({...newBillingDocument,paymentProvider:e.target.value})} style={{...inp,marginBottom:0}}>
                <option value='manual'>Безнал / вручную</option>
                <option value='yukassa'>ЮKassa позже</option>
                <option value='robokassa'>Robokassa позже</option>
              </select>
              <input placeholder='Ссылка на оплату/файл' value={newBillingDocument.paymentUrl} onChange={e=>setNewBillingDocument({...newBillingDocument,paymentUrl:e.target.value})} style={{...inp,marginBottom:0}}/>
            </div>
            <input placeholder='Комментарий' value={newBillingDocument.notes} onChange={e=>setNewBillingDocument({...newBillingDocument,notes:e.target.value})} style={{...inp,marginTop:'8px'}}/>
            <div style={{display:'flex',gap:'8px',marginTop:'8px',flexWrap:'wrap'}}>
              <button onClick={async()=>{
                if(!newBillingDocument.companyId||!newBillingDocument.amount) { alert('Заполните компанию и сумму'); return; }
                const response = await sendJson('/system/billing-documents',{method:'POST',body:JSON.stringify(newBillingDocument)});
                const data = await response.json().catch(()=>({}));
                if(!response.ok) { alert(data.detail || 'Не удалось создать документ'); return; }
                setShowNewBillingDocument(false);
                setNewBillingDocument({companyId:'',documentType:'invoice',status:'draft',amount:'',issueDate:new Date().toISOString().split('T')[0],dueDate:'',periodStart:'',periodEnd:'',paymentProvider:'manual',paymentUrl:'',fileUrl:'',notes:''});
                await loadAll();
              }} style={btnO}>✓ Создать документ</button>
              <button onClick={()=>setShowNewBillingDocument(false)} style={btnG}>Отмена</button>
            </div>
          </div>)}

          <div style={{marginBottom:'16px'}}>
            <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'8px'}}>Документы платформы ({billingDocuments.length})</b>
            {billingDocuments.length===0 && <div style={{...card,padding:'22px',textAlign:'center',color:C.textMuted,marginBottom:'10px'}}>Счетов и актов пока нет</div>}
            {billingDocuments.map(doc=>{
              const colors = billingDocumentStatusColor(doc.status);
              return (<div key={doc.id} style={{...card,padding:'12px',marginBottom:'8px'}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
                  <div style={{minWidth:0,flex:1}}>
                    <b style={{color:C.text,fontSize:'13px',display:'block'}}>{doc.documentTypeLabel || billingDocumentTypeLabels[doc.document_type] || doc.document_type} {doc.number || 'без номера'}</b>
                    <p style={{color:C.textSec,fontSize:'11px',margin:'3px 0 0'}}>{doc.company_name || '—'}{doc.period_start?' · период '+doc.period_start+' – '+(doc.period_end || ''):''}{doc.due_date?' · оплатить до '+doc.due_date:''}</p>
                    {(doc.payment_provider || doc.payment_url) && <p style={{color:C.textMuted,fontSize:'11px',margin:'3px 0 0',overflowWrap:'anywhere'}}>{doc.payment_provider || 'manual'}{doc.payment_url?' · '+doc.payment_url:''}</p>}
                    {doc.file_url && <a href={fileSrc(doc.file_url)} target='_blank' rel='noreferrer' style={{color:C.info,fontSize:'11px',fontWeight:800,textDecoration:'none',display:'inline-block',marginTop:'5px'}}>Открыть PDF</a>}
                  </div>
                  <div style={{display:'flex',gap:'6px',alignItems:'center',flexWrap:'wrap',justifyContent:'flex-end'}}>
                    <b style={{color:C.success,fontSize:'14px',whiteSpace:'nowrap'}}>{Number(doc.amount || 0).toLocaleString('ru-RU')} ₽</b>
                    <span style={badge(colors.color,colors.bg,colors.border)}>{doc.statusLabel || billingDocumentStatusLabels[doc.status] || doc.status}</span>
                    <button onClick={async()=>{
                      const response = await sendJson('/system/billing-documents/'+doc.id+'/generate-pdf',{method:'POST'});
                      const data = await response.json().catch(()=>({}));
                      if(!response.ok){ alert(data.detail || 'Не удалось сформировать PDF'); return; }
                      await loadAll();
                    }} style={{...btnG,padding:'5px 10px',fontSize:'11px'}}>PDF</button>
                    <button onClick={async()=>{
                      const response = await sendJson('/system/billing-documents/'+doc.id+'/prepare-payment',{method:'POST',body:JSON.stringify({provider:doc.payment_provider || 'manual', paymentUrl:doc.payment_url || ''})});
                      const data = await response.json().catch(()=>({}));
                      if(!response.ok){ alert(data.detail || 'Не удалось подготовить оплату'); return; }
                      alert(data.message || 'Провайдер подготовлен');
                      await loadAll();
                    }} style={{...btnG,padding:'5px 10px',fontSize:'11px'}}>Провайдер</button>
                    {canUseFollowups && <button onClick={()=>openFollowupForm(companies.find(c=>String(c.id)===String(doc.company_id)) || {id:doc.company_id,name:doc.company_name,platform_account_name:doc.platform_account_name}, 'payment', doc)} style={{...btnG,padding:'5px 10px',fontSize:'11px'}}>Задача</button>}
                    {doc.status === 'draft' && <button onClick={async()=>{await sendJson('/system/billing-documents/'+doc.id,{method:'PUT',body:JSON.stringify({status:'issued'})});loadAll();}} style={{...btnG,padding:'5px 10px',fontSize:'11px'}}>Выставлен</button>}
                    {doc.status !== 'cancelled' && doc.status !== 'closed' && <button onClick={async()=>{await sendJson('/system/billing-documents/'+doc.id,{method:'PUT',body:JSON.stringify({status:'payment_expected'})});loadAll();}} style={{...btnO,padding:'5px 10px',fontSize:'11px'}}>Ждет оплату</button>}
                    {doc.status !== 'cancelled' && <button onClick={async()=>{await sendJson('/system/billing-documents/'+doc.id,{method:'PUT',body:JSON.stringify({status:'closed'})});loadAll();}} style={{...btnGr,padding:'5px 10px',fontSize:'11px'}}>Закрыть</button>}
                  </div>
                </div>
              </div>);
            })}
          </div>

          {showNewPayment && (<div style={{...card,padding:'16px',marginBottom:'14px'}}>
            <b style={{color:C.text,fontSize:'13px',display:'block',marginBottom:'10px'}}>Зачислить фактический платеж</b>
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px'}}>
              <select value={newPayment.companyId} onChange={e=>setNewPayment({...newPayment,companyId:Number(e.target.value)})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}>
                <option value=''>Компания *</option>
                {companies.filter(c=>c.id!==1).map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <input type='number' placeholder='Сумма ₽ *' value={newPayment.amount} onChange={e=>setNewPayment({...newPayment,amount:e.target.value})} style={{...inp,marginBottom:0}}/>
              <select value={newPayment.method} onChange={e=>setNewPayment({...newPayment,method:e.target.value})} style={{...inp,marginBottom:0}}>
                <option value='card'>💳 Карта</option>
                <option value='transfer'>🏦 Безнал</option>
                <option value='yukassa'>🟣 ЮKassa</option>
                <option value='robokassa'>🤖 Robokassa</option>
              </select>
              <input type='date' placeholder='Дата оплаты' value={newPayment.paymentDate} onChange={e=>setNewPayment({...newPayment,paymentDate:e.target.value})} style={{...inp,marginBottom:0}}/>
              <input placeholder='Номер счёта' value={newPayment.invoiceNumber} onChange={e=>setNewPayment({...newPayment,invoiceNumber:e.target.value})} style={{...inp,marginBottom:0}}/>
              <input type='date' placeholder='Период с' value={newPayment.periodStart} onChange={e=>setNewPayment({...newPayment,periodStart:e.target.value})} style={{...inp,marginBottom:0}}/>
              <input type='date' placeholder='Период по' value={newPayment.periodEnd} onChange={e=>setNewPayment({...newPayment,periodEnd:e.target.value})} style={{...inp,marginBottom:0}}/>
            </div>
            <input placeholder='Заметки' value={newPayment.notes} onChange={e=>setNewPayment({...newPayment,notes:e.target.value})} style={{...inp,marginTop:'8px'}}/>
            <div style={{display:'flex',gap:'8px',marginTop:'8px'}}>
              <button onClick={async()=>{
                if(!newPayment.companyId||!newPayment.amount) { alert('Заполните компанию и сумму'); return; }
                await sendJson('/system/payments',{method:'POST',body:JSON.stringify({...newPayment,createdBy:user.name})});
                setShowNewPayment(false);
                setNewPayment({companyId:'',amount:'',paymentDate:new Date().toISOString().split('T')[0],method:'card',invoiceNumber:'',periodStart:'',periodEnd:'',notes:''});
                await loadAll();
              }} style={btnO}>✓ Зачислить</button>
              <button onClick={()=>setShowNewPayment(false)} style={btnG}>Отмена</button>
            </div>
          </div>)}
          <b style={{color:C.text,fontSize:'14px',display:'block',margin:'4px 0 8px'}}>Фактические платежи ({payments.length})</b>
          {payments.length===0 && <div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}>Платежей пока нет</div>}
          {payments.map(p=>(<div key={p.id} style={{...card,padding:'12px',marginBottom:'8px'}}>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',flexWrap:'wrap',gap:'8px'}}>
              <div>
                <b style={{color:C.text,fontSize:'13px'}}>{p.company_name||'—'}</b>
                <p style={{color:C.textSec,margin:'2px 0',fontSize:'11px'}}>{p.payment_date} · {p.method} · {p.invoice_number||'без номера'}{p.period_start?' · '+p.period_start+' – '+p.period_end:''}</p>
              </div>
              <b style={{color:p.status==='paid'?C.success:C.warning,fontSize:'14px'}}>{Number(p.amount).toLocaleString('ru-RU')} ₽</b>
            </div>
          </div>))}
        </div>)}

        {/* Задачи платформы */}
        {tab==='followups' && canUseFollowups && (<div>
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'12px',flexWrap:'wrap',marginBottom:'14px'}}>
            <div>
              <b style={{color:C.text,fontSize:'15px',display:'block'}}>Задачи по демо и оплате ({platformFollowups.length})</b>
              <p style={{color:C.textSec,fontSize:'12px',margin:'4px 0 0'}}>Фиксируем, кому позвонить или написать, когда следующий контакт, чем закончился разговор и к какому счету это относится.</p>
            </div>
            <div style={{display:'flex',gap:'6px',flexWrap:'wrap',justifyContent:'flex-end'}}>
              <span style={badge(C.warning,C.warningLight,C.warningBorder)}>открытых {followupStats.open}</span>
              <span style={badge(followupStats.overdue?C.danger:C.success,followupStats.overdue?C.dangerLight:C.successLight,followupStats.overdue?C.dangerBorder:C.successBorder)}>просрочено {followupStats.overdue}</span>
              <span style={badge(C.info,C.infoLight,C.infoBorder)}>сегодня {followupStats.today}</span>
              <button onClick={()=>setShowNewFollowup(!showNewFollowup)} style={btnO}>+ Задача</button>
            </div>
          </div>
          {showNewFollowup && (<div style={{...card,padding:'14px',marginBottom:'14px'}}>
            <b style={{color:C.text,fontSize:'13px',display:'block',marginBottom:'10px'}}>Новая задача контакта</b>
            <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:'8px'}}>
              <select value={newFollowup.companyId} onChange={e=>{
                const company = companies.find(item=>String(item.id)===String(e.target.value)) || {};
                const channel = company.contact_email ? 'email' : 'call';
                setNewFollowup({
                  ...newFollowup,
                  companyId:e.target.value,
                  billingDocumentId:'',
                  channel,
                  contactName:company.contact_name || '',
                  contactValue:channel==='email' ? (company.contact_email || '') : (company.contact_phone || company.contact_email || ''),
                  title:newFollowup.title || 'Связаться с '+(company.name || ''),
                });
              }} style={{...inp,marginBottom:0}}>
                <option value=''>Компания *</option>
                {companies.filter(c=>c.id!==1).map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <select value={newFollowup.billingDocumentId} onChange={e=>setNewFollowup({...newFollowup,billingDocumentId:e.target.value})} style={{...inp,marginBottom:0}}>
                <option value=''>Без платежного документа</option>
                {followupDocumentOptions.map(doc=><option key={doc.id} value={doc.id}>{doc.number || ('Документ #'+doc.id)} · {Number(doc.amount || 0).toLocaleString('ru-RU')} ₽</option>)}
              </select>
              <select value={newFollowup.source} onChange={e=>setNewFollowup({...newFollowup,source:e.target.value})} style={{...inp,marginBottom:0}}>
                {Object.entries(followupSourceLabels).map(([key,label])=><option key={key} value={key}>{label}</option>)}
              </select>
              <select value={newFollowup.channel} onChange={e=>setNewFollowup({...newFollowup,channel:e.target.value})} style={{...inp,marginBottom:0}}>
                {Object.entries(followupChannelLabels).map(([key,label])=><option key={key} value={key}>{label}</option>)}
              </select>
              <input placeholder='Задача *' value={newFollowup.title} onChange={e=>setNewFollowup({...newFollowup,title:e.target.value})} style={{...inp,marginBottom:0}}/>
              <input placeholder='Кому' value={newFollowup.contactName} onChange={e=>setNewFollowup({...newFollowup,contactName:e.target.value})} style={{...inp,marginBottom:0}}/>
              <input placeholder='Телефон / email / мессенджер' value={newFollowup.contactValue} onChange={e=>setNewFollowup({...newFollowup,contactValue:e.target.value})} style={{...inp,marginBottom:0}}/>
              <input type='date' value={newFollowup.dueDate} onChange={e=>setNewFollowup({...newFollowup,dueDate:e.target.value})} style={{...inp,marginBottom:0}}/>
              <select value={newFollowup.status} onChange={e=>setNewFollowup({...newFollowup,status:e.target.value})} style={{...inp,marginBottom:0}}>
                {Object.entries(followupStatusLabels).map(([key,label])=><option key={key} value={key}>{label}</option>)}
              </select>
              <input placeholder='Ответственный' value={newFollowup.responsibleName} onChange={e=>setNewFollowup({...newFollowup,responsibleName:e.target.value})} style={{...inp,marginBottom:0}}/>
            </div>
            <textarea placeholder='Контекст / что обсудить' value={newFollowup.notes} onChange={e=>setNewFollowup({...newFollowup,notes:e.target.value})} style={{...inp,height:'58px',marginTop:'8px'}}/>
            <div style={{display:'flex',gap:'8px',flexWrap:'wrap',marginTop:'8px'}}>
              <button onClick={createFollowup} style={btnO}>✓ Создать задачу</button>
              <button onClick={()=>setShowNewFollowup(false)} style={btnG}>Отмена</button>
            </div>
          </div>)}
          {platformFollowups.length===0 && <div style={{...card,padding:'28px',textAlign:'center',color:C.textMuted}}>Открытых задач по демо и оплате нет</div>}
          {platformFollowups.map(item=>{
            const colors = followupStatusColor(item.status,item.dueDate);
            const closed = ['done','cancelled'].includes(item.status);
            return (<div key={item.id} style={{...card,padding:'12px',marginBottom:'8px'}}>
              <div style={{display:'grid',gridTemplateColumns:'minmax(220px,1fr) minmax(180px,260px) auto',gap:'10px',alignItems:'center'}}>
                <div style={{minWidth:0}}>
                  <b style={{color:C.text,fontSize:'13px',display:'block',overflowWrap:'anywhere'}}>{item.title || 'Задача без названия'}</b>
                  <p style={{color:C.textSec,fontSize:'11px',margin:'3px 0 0',overflowWrap:'anywhere'}}>{item.companyName || 'компания не выбрана'} · {item.sourceLabel} · {item.channelLabel}</p>
                  <p style={{color:C.textMuted,fontSize:'10px',margin:'2px 0 0'}}>{item.contactName || 'контакт не указан'}{item.contactValue?' · '+item.contactValue:''}{item.billingDocumentNumber?' · счет '+item.billingDocumentNumber:''}</p>
                  {item.notes && <p style={{color:C.textMuted,fontSize:'10px',margin:'4px 0 0',overflowWrap:'anywhere'}}>{item.notes}</p>}
                </div>
                <div>
                  <p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Следующий контакт: <b>{item.dueDate || 'не указан'}</b></p>
                  <p style={{color:C.textMuted,fontSize:'10px',margin:0}}>Ответственный: {item.responsibleName || '—'}{item.result?' · итог: '+item.result:''}</p>
                </div>
                <div style={{display:'flex',gap:'6px',justifyContent:'flex-end',alignItems:'center',flexWrap:'wrap'}}>
                  <span style={badge(colors.color,colors.bg,colors.border)}>{item.statusLabel}</span>
                  {!closed && <button onClick={()=>updateFollowup(item,{status:'contacted'})} style={{...btnG,padding:'5px 10px',fontSize:'11px'}}>Связались</button>}
                  {!closed && <button onClick={()=>updateFollowup(item,{status:'waiting'})} style={{...btnG,padding:'5px 10px',fontSize:'11px'}}>Ждем</button>}
                  {!closed && <button onClick={()=>{
                    const result = window.prompt('Итог контакта:', item.result || '');
                    if (result === null) return;
                    updateFollowup(item,{status:'done',result});
                  }} style={{...btnGr,padding:'5px 10px',fontSize:'11px'}}>Закрыть</button>}
                  {!closed && <button onClick={()=>{
                    const dueDate = window.prompt('Новая дата контакта (ГГГГ-ММ-ДД):', item.dueDate || new Date().toISOString().split('T')[0]);
                    if (!dueDate) return;
                    updateFollowup(item,{dueDate,status:'open'});
                  }} style={{...btnG,padding:'5px 10px',fontSize:'11px'}}>Дата</button>}
                </div>
              </div>
            </div>);
          })}
        </div>)}

        {/* Демо-заявки */}
        {tab==='demos' && (<div>
          <b style={{color:C.text,fontSize:'15px',display:'block',marginBottom:'12px'}}>Заявки на демо ({demos.length})</b>
          {demos.length===0 && <div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}>Заявок пока нет. Они будут приходить с лендинга (когда сделаем).</div>}
          {demos.map(d=>(<div key={d.id} style={{...card,padding:'12px',marginBottom:'8px'}}>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'8px',flexWrap:'wrap'}}>
              <div style={{flex:1,minWidth:'200px'}}>
                <b style={{color:C.text,fontSize:'13px'}}>{d.company_name||'—'}</b>
                <p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{d.contact_name+' · '+(d.phone||'')+(d.email?' · '+d.email:'')}</p>
                {d.comment && <p style={{color:C.textMuted,margin:0,fontSize:'11px',fontStyle:'italic'}}>«{d.comment}»</p>}
                <p style={{color:C.textMuted,margin:'2px 0 0',fontSize:'10px'}}>{new Date(d.created_at).toLocaleString('ru-RU')}{d.source?' · '+d.source:''}</p>
              </div>
              <span style={badge(d.status==='Новая'?C.warning:C.success,d.status==='Новая'?C.warningLight:C.successLight,d.status==='Новая'?C.warningBorder:C.successBorder)}>{d.status}</span>
            </div>
            {d.status==='Новая' && (<div style={{display:'flex',gap:'6px',marginTop:'8px'}}>
              <button onClick={async()=>{await sendJson('/demo-requests/'+d.id,{method:'PUT',body:JSON.stringify({status:'Обработана'})});loadAll();}} style={{...btnGr,padding:'4px 10px',fontSize:'11px'}}>✓ Обработана</button>
              <button onClick={async()=>{await sendJson('/demo-requests/'+d.id,{method:'PUT',body:JSON.stringify({status:'Отклонена'})});loadAll();}} style={{...btnR,padding:'4px 10px',fontSize:'11px'}}>✕ Отклонить</button>
            </div>)}
          </div>))}
        </div>)}

        {/* Поддержка */}
        {tab==='support' && canUseSupport && (<div>
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'12px',flexWrap:'wrap',marginBottom:'14px'}}>
            <div>
              <b style={{color:C.text,fontSize:'15px',display:'block'}}>Режим поддержки ({supportSessions.length})</b>
              <p style={{color:C.textSec,fontSize:'12px',margin:'4px 0 0'}}>Это журналируемое разрешение на разбор проблемы клиента. Само по себе оно не открывает ЖПР, склад или финансы.</p>
            </div>
            {canManagePlatform && <span style={badge(C.warning,C.warningLight,C.warningBorder)}>открывает владелец/админ</span>}
          </div>
          {canManagePlatform && (<div style={{...card,padding:'14px',marginBottom:'14px'}}>
            <b style={{color:C.text,fontSize:'13px',display:'block',marginBottom:'10px'}}>Открыть support-сессию</b>
            <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(190px,1fr))',gap:'8px'}}>
              <select value={supportForm.platformAccountId} onChange={e=>setSupportForm({...supportForm,platformAccountId:e.target.value,companyId:''})} style={{...inp,marginBottom:0}}>
                <option value=''>Аккаунт клиента</option>
                {groupsWithLimitStatus.map(group=><option key={group.id} value={group.id}>{group.name}</option>)}
              </select>
              <select value={supportForm.companyId} onChange={e=>setSupportForm({...supportForm,companyId:e.target.value})} style={{...inp,marginBottom:0}}>
                <option value=''>Компания / весь аккаунт</option>
                {companies.filter(company => !supportForm.platformAccountId || String(company.platform_account_id || company.id) === String(supportForm.platformAccountId)).map(company=><option key={company.id} value={company.id}>{company.name}</option>)}
              </select>
              <select value={supportForm.scope} onChange={e=>setSupportForm({...supportForm,scope:e.target.value})} style={{...inp,marginBottom:0}}>
                {Object.entries(supportScopeLabels).map(([value,label])=><option key={value} value={value}>{label}</option>)}
              </select>
              <input type='number' min='1' max='168' placeholder='Часов' value={supportForm.expiresInHours} onChange={e=>setSupportForm({...supportForm,expiresInHours:e.target.value})} style={{...inp,marginBottom:0}}/>
            </div>
            <textarea placeholder='Причина: что именно разбираем и кто согласовал' value={supportForm.reason} onChange={e=>setSupportForm({...supportForm,reason:e.target.value})} style={{...inp,height:'58px',marginTop:'8px'}}/>
            <button onClick={async()=>{
              const response = await sendJson('/system/support-sessions',{method:'POST',body:JSON.stringify(supportForm)});
              const data = await response.json().catch(()=>({}));
              if (!response.ok) { alert(data.detail || 'Не удалось открыть режим поддержки'); return; }
              setSupportForm({platformAccountId:'',companyId:'',scope:'read_only',reason:'',expiresInHours:24});
              await loadAll();
            }} style={btnO}>✓ Открыть режим поддержки</button>
          </div>)}
          {supportSessions.length===0 && <div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}>Активных support-сессий нет</div>}
          {supportSessions.map(session=>{
            const statusColor = session.status === 'active' ? C.success : (session.status === 'expired' ? C.warning : C.textMuted);
            return (<div key={session.id} style={{...card,padding:'12px',marginBottom:'8px'}}>
              <div style={{display:'flex',justifyContent:'space-between',gap:'10px',alignItems:'flex-start',flexWrap:'wrap'}}>
                <div style={{minWidth:0,flex:1}}>
                  <b style={{color:C.text,fontSize:'13px',display:'block'}}>{session.company_name || session.platform_account_name || 'Аккаунт не выбран'}</b>
                  <p style={{color:C.textSec,fontSize:'12px',margin:'3px 0 0',overflowWrap:'anywhere'}}>{session.reason}</p>
                  <p style={{color:C.textMuted,fontSize:'11px',margin:'4px 0 0'}}>
                    {session.scopeLabel || supportScopeLabels[session.scope] || session.scope} · открыл {session.opened_by_name || 'system'} · до {session.expires_at ? new Date(session.expires_at).toLocaleString('ru-RU') : '—'}
                  </p>
                </div>
                <div style={{display:'flex',gap:'6px',alignItems:'center',flexWrap:'wrap'}}>
                  <span style={badge(statusColor,C.bg,C.border)}>{session.status}</span>
                  {canManagePlatform && session.status === 'active' && <button onClick={async()=>{await sendJson('/system/support-sessions/'+session.id,{method:'PUT',body:JSON.stringify({action:'close'})});loadAll();}} style={{...btnG,padding:'5px 10px',fontSize:'11px'}}>Закрыть</button>}
                </div>
              </div>
            </div>);
          })}
        </div>)}

        {/* Команда платформы */}
        {tab==='team' && canManageTeam && (<div>
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'12px',flexWrap:'wrap',marginBottom:'14px'}}>
            <div>
              <b style={{color:C.text,fontSize:'15px',display:'block'}}>Команда платформы ({platformUsers.length})</b>
              <p style={{color:C.textSec,fontSize:'12px',margin:'4px 0 0'}}>Приглашения идут через одноразовый код. Пароли не создаем и не храним открытым текстом.</p>
            </div>
            <span style={badge(C.info,C.infoLight,C.infoBorder)}>только владелец</span>
          </div>
          <div style={{...card,padding:'14px',marginBottom:'14px'}}>
            <b style={{color:C.text,fontSize:'13px',display:'block',marginBottom:'10px'}}>Пригласить сотрудника платформы</b>
            {lastPlatformInvite && (<div style={{padding:'10px',backgroundColor:C.successLight,border:'1.5px solid '+C.successBorder,borderRadius:'8px',marginBottom:'10px'}}>
              <b style={{color:C.success,fontSize:'12px',display:'block',marginBottom:'6px'}}>Ссылка приглашения</b>
              <div style={{padding:'9px',backgroundColor:C.bgWhite,border:'1px solid '+C.border,borderRadius:'6px',fontSize:'12px',color:C.text,wordBreak:'break-all',userSelect:'all'}}>{lastPlatformInvite.link}</div>
              <button onClick={()=>navigator.clipboard.writeText(lastPlatformInvite.link).then(()=>alert('Скопировано'))} style={{...btnO,padding:'5px 10px',fontSize:'11px',marginTop:'8px'}}>Скопировать</button>
            </div>)}
            <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(190px,1fr))',gap:'8px'}}>
              <select value={platformInvite.role} onChange={e=>setPlatformInvite({...platformInvite,role:e.target.value})} style={{...inp,marginBottom:0}}>
                <option value='platform_support'>Поддержка платформы</option>
                <option value='platform_admin'>Администратор платформы</option>
                <option value='billing_admin'>Биллинг платформы</option>
              </select>
              <input placeholder='Имя / должность' value={platformInvite.name} onChange={e=>setPlatformInvite({...platformInvite,name:e.target.value})} style={{...inp,marginBottom:0}}/>
              <input type='email' placeholder='Email для подписи приглашения' value={platformInvite.email} onChange={e=>setPlatformInvite({...platformInvite,email:e.target.value})} style={{...inp,marginBottom:0}}/>
              <input type='number' min='1' max='30' placeholder='Дней действия' value={platformInvite.expiresInDays} onChange={e=>setPlatformInvite({...platformInvite,expiresInDays:e.target.value})} style={{...inp,marginBottom:0}}/>
            </div>
            <button onClick={async()=>{
              const response = await sendJson('/system/platform-users/invite',{method:'POST',body:JSON.stringify(platformInvite)});
              const data = await response.json().catch(()=>({}));
              if (!response.ok) { alert(data.detail || 'Не удалось создать приглашение'); return; }
              const link = window.location.origin + '/?invite=' + data.code;
              setLastPlatformInvite({code:data.code, link});
              setPlatformInvite({role:'platform_support',name:'',email:'',expiresInDays:7});
              await loadAll();
            }} style={{...btnO,marginTop:'10px'}}>+ Создать приглашение</button>
          </div>
          {platformUsers.map(item=>(<div key={item.id} style={{...card,padding:'12px',marginBottom:'8px'}}>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap'}}>
              <div>
                <b style={{color:C.text,fontSize:'13px'}}>{item.name || item.email}</b>
                <p style={{color:C.textSec,fontSize:'11px',margin:'3px 0 0'}}>{item.email} · {item.roleLabel || platformRoleLabels[item.role] || item.role} · {item.two_factor_enabled ? '2FA включена' : '2FA потребуется при входе'}</p>
              </div>
              <div style={{display:'flex',gap:'6px',alignItems:'center',flexWrap:'wrap'}}>
                <span style={badge(item.active?C.success:C.textMuted,item.active?C.successLight:C.bg,item.active?C.successBorder:C.border)}>{item.active?'Активен':'Отключен'}</span>
                {item.role !== 'system_owner' && <button onClick={async()=>{await sendJson('/system/platform-users/'+item.id,{method:'PUT',body:JSON.stringify({active:!item.active})});loadAll();}} style={{...btnG,padding:'5px 10px',fontSize:'11px'}}>{item.active?'Отключить':'Включить'}</button>}
              </div>
            </div>
          </div>))}
        </div>)}

        {/* Журнал платформы */}
        {tab==='audit' && (<div>
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap',marginBottom:'12px'}}>
            <div>
              <b style={{color:C.text,fontSize:'15px',display:'block'}}>Журнал действий платформы ({auditLog.length})</b>
              <p style={{color:C.textSec,fontSize:'12px',margin:'3px 0 0'}}>Создание аккаунтов, компаний, оплаты, заморозки, демо-заявки.</p>
            </div>
            <button onClick={loadAll} style={{...btnG,padding:'7px 12px',fontSize:'12px'}}>Обновить</button>
          </div>
          <div style={{...card,padding:'12px',marginBottom:'12px'}}>
            <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(190px,1fr))',gap:'8px'}}>
              <select value={auditDraftFilters.platformAccountId} onChange={e=>setAuditDraftFilters({...auditDraftFilters,platformAccountId:e.target.value,companyId:''})} style={{...inp,marginBottom:0}}>
                <option value=''>Все аккаунты</option>
                {groupsWithLimitStatus.map(group=><option key={group.id} value={group.id}>{group.name}</option>)}
              </select>
              <select value={auditDraftFilters.companyId} onChange={e=>setAuditDraftFilters({...auditDraftFilters,companyId:e.target.value})} style={{...inp,marginBottom:0}}>
                <option value=''>Все компании</option>
                {auditCompanyOptions.map(company=><option key={company.id} value={company.id}>{company.name}</option>)}
              </select>
              <select value={auditDraftFilters.action} onChange={e=>setAuditDraftFilters({...auditDraftFilters,action:e.target.value})} style={{...inp,marginBottom:0}}>
                <option value=''>Все действия</option>
                {Object.entries(auditActionLabels).map(([value,label])=><option key={value} value={value}>{label}</option>)}
              </select>
              <input placeholder='Поиск по журналу' value={auditDraftFilters.search} onChange={e=>setAuditDraftFilters({...auditDraftFilters,search:e.target.value})} style={{...inp,marginBottom:0}}/>
            </div>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'8px',marginTop:'8px',flexWrap:'wrap'}}>
              <span style={{color:C.textMuted,fontSize:'11px'}}>{hasAuditFilters?'Показаны события по выбранным фильтрам':'Показаны последние события платформы'}</span>
              <div style={{display:'flex',gap:'8px',flexWrap:'wrap'}}>
                <button onClick={()=>setAuditFilters(auditDraftFilters)} style={{...btnO,padding:'6px 12px',fontSize:'12px'}}>Показать</button>
                {hasAuditFilters && <button onClick={()=>{setAuditDraftFilters(emptyAuditFilters);setAuditFilters(emptyAuditFilters);}} style={{...btnG,padding:'6px 12px',fontSize:'12px'}}>Сбросить</button>}
              </div>
            </div>
          </div>
          {auditLog.length===0 && <div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}>Событий пока нет</div>}
          {auditLog.map(item=>{
            const details = item.details || {};
            const meta = [
              item.actor_name || item.actor_role || 'system',
              item.entity_name,
              item.company_id ? 'company #' + item.company_id : '',
            ].filter(Boolean).join(' · ');
            return (
              <div key={item.id} style={{...card,padding:'12px',marginBottom:'8px'}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
                  <div style={{minWidth:0,flex:1}}>
                    <b style={{color:C.text,fontSize:'13px',display:'block'}}>{auditActionLabels[item.action] || item.action}</b>
                    <p style={{color:C.textSec,margin:'3px 0 0',fontSize:'11px',overflowWrap:'anywhere'}}>{meta || '—'}</p>
                    {(details.amount || details.plan || details.status || details.paymentDate || details.periodEnd) && (
                      <p style={{color:C.textMuted,margin:'4px 0 0',fontSize:'11px',overflowWrap:'anywhere'}}>
                        {[details.plan && 'тариф '+details.plan, details.status, details.amount && Number(details.amount).toLocaleString('ru-RU')+' ₽', details.paymentDate, details.periodEnd && 'до '+details.periodEnd].filter(Boolean).join(' · ')}
                      </p>
                    )}
                  </div>
                  <span style={badge(C.textSec,C.bg,C.border)}>{item.created_at ? new Date(item.created_at).toLocaleString('ru-RU') : '—'}</span>
                </div>
              </div>
            );
          })}
        </div>)}

        {/* Система */}
        {tab==='system' && (<div>
          <b style={{color:C.text,fontSize:'15px',display:'block',marginBottom:'12px'}}>🔧 Здоровье системы</b>
          <div style={{...card,padding:'16px',marginBottom:'14px'}}>
            <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 8px'}}>Это заготовка. Будет показывать:</p>
            <ul style={{color:C.textSec,fontSize:'12px',paddingLeft:'18px',margin:0,lineHeight:'1.7'}}>
              <li>🖥 CPU / RAM / Disk usage сервера</li>
              <li>🗄 Размер БД и таблиц</li>
              <li>📁 Размер /uploads (фото) с предупреждением о близости к лимиту</li>
              <li>📊 Количество запросов в день, среднее время ответа</li>
              <li>🔴 Последние ошибки из journalctl</li>
              <li>📅 Последний бэкап БД и время</li>
              <li>🤖 Расход на AI (Yandex GPT calls × токены)</li>
            </ul>
          </div>
          <div style={{...card,padding:'16px',backgroundColor:C.warningLight,border:'1.5px solid '+C.warningBorder}}>
            <b style={{color:C.warning,fontSize:'13px',display:'block',marginBottom:'8px'}}>📋 Подключения для следующего этапа:</b>
            <ul style={{color:C.text,fontSize:'12px',paddingLeft:'18px',margin:0,lineHeight:'1.7'}}>
              <li>ЮKassa или Robokassa — для приёма платежей картой</li>
              <li>Mailgun / SendPulse — для email уведомлений</li>
              <li>Яндекс.Объект-стор (S3) — для хранения фото</li>
              <li>Sentry — мониторинг ошибок</li>
              <li>UptimeRobot — мониторинг доступности</li>
              <li>Лендинг-сайт — для приёма demo-заявок (POST /demo-request)</li>
            </ul>
          </div>
        </div>)}
      </div>
    </div>
  );
}

export default SystemOwnerCabinet;
