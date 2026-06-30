import { useCallback, useEffect, useMemo, useState } from 'react';

function SystemOwnerCabinet({user, setUser, C, card, btnO, btnG, btnGr, btnR, inp, badge, API}) {
  const [tab, setTab] = useState('dashboard');
  const [dashboard, setDashboard] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [payments, setPayments] = useState([]);
  const [billingDocuments, setBillingDocuments] = useState([]);
  const [paymentProviders, setPaymentProviders] = useState([]);
  const [paymentEvents, setPaymentEvents] = useState([]);
  const [demos, setDemos] = useState([]);
  const [tariffs, setTariffs] = useState([]);
  const [auditLog, setAuditLog] = useState([]);
  const [showNewCompany, setShowNewCompany] = useState(false);
  const emptyCompanyForm = {platformAccountId:'',platformAccountName:'',name:'',shortName:'',inn:'',kpp:'',contactName:'',contactPhone:'',contactEmail:'',plan:'demo',trialDays:30,monthlyFee:'',maxProjects:'',maxUsers:'',notes:''};
  const [newCompany, setNewCompany] = useState(emptyCompanyForm);
  const [clientCardScanning, setClientCardScanning] = useState(false);
  const [clientCardRecognition, setClientCardRecognition] = useState(null);
  const [newPayment, setNewPayment] = useState({companyId:'',amount:'',paymentDate:new Date().toISOString().split('T')[0],method:'card',invoiceNumber:'',periodStart:'',periodEnd:'',notes:''});
  const [showNewPayment, setShowNewPayment] = useState(false);
  const [newBillingDocument, setNewBillingDocument] = useState({companyId:'',documentType:'invoice',status:'draft',amount:'',issueDate:new Date().toISOString().split('T')[0],dueDate:'',periodStart:'',periodEnd:'',paymentProvider:'manual',paymentUrl:'',fileUrl:'',notes:''});
  const [showNewBillingDocument, setShowNewBillingDocument] = useState(false);
  const [lastInviteCode, setLastInviteCode] = useState(null);
  const [platformUsers, setPlatformUsers] = useState([]);
  const [supportSessions, setSupportSessions] = useState([]);
  const [platformInvite, setPlatformInvite] = useState({role:'platform_support',name:'',email:'',expiresInDays:7});
  const [lastPlatformInvite, setLastPlatformInvite] = useState(null);
  const [supportForm, setSupportForm] = useState({platformAccountId:'',companyId:'',scope:'read_only',reason:'',expiresInHours:24});
  const emptyAuditFilters = {platformAccountId:'',companyId:'',action:'',search:''};
  const [auditFilters, setAuditFilters] = useState(emptyAuditFilters);
  const [auditDraftFilters, setAuditDraftFilters] = useState(emptyAuditFilters);
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
  const canManagePlatform = ['system_owner','platform_admin'].includes(user.role);
  const canManageBilling = ['system_owner','platform_admin','billing_admin'].includes(user.role);
  const canManageTeam = user.role === 'system_owner';
  const canUseSupport = ['system_owner','platform_admin','platform_support'].includes(user.role);
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
    client_card_recognized: 'Распознана карта клиента',
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
      const [d, c, p, bd, pp, dr, t, a, u, s] = await Promise.all([
        fetchJson('/system/dashboard', null),
        fetchJson('/system/companies', []),
        canManageBilling ? fetchJson('/system/payments', []) : Promise.resolve([]),
        canManageBilling ? fetchJson('/system/billing-documents', []) : Promise.resolve([]),
        canManageBilling ? fetchJson('/system/payment-providers', []) : Promise.resolve([]),
        canManagePlatform ? fetchJson('/demo-requests', []) : Promise.resolve([]),
        fetchJson('/system/tariffs', []),
        fetchJson('/system/audit-log?'+auditParams.toString(), []),
        canManageTeam ? fetchJson('/system/platform-users', []) : Promise.resolve([]),
        canUseSupport ? fetchJson('/system/support-sessions', []) : Promise.resolve([]),
      ]);
      setDashboard(d);
      setCompanies(Array.isArray(c)?c:[]);
      setPayments(Array.isArray(p)?p:[]);
      setBillingDocuments(Array.isArray(bd)?bd:[]);
      setPaymentProviders(Array.isArray(pp)?pp:[]);
      setDemos(Array.isArray(dr)?dr:[]);
      setTariffs(Array.isArray(t)?t:[]);
      setAuditLog(Array.isArray(a)?a:[]);
      setPlatformUsers(Array.isArray(u)?u:[]);
      setSupportSessions(Array.isArray(s)?s:[]);
    } catch(_){}
	  }, [auditFilters, canManageBilling, canManagePlatform, canManageTeam, canUseSupport, fetchJson]);
	  useEffect(()=>{ loadAll(); }, [loadAll]);

  const loadPaymentEvents = useCallback(async () => {
    if (!canManageBilling) {
      setPaymentEvents([]);
      return;
    }
    const rows = await fetchJson('/system/payment-events', []);
    setPaymentEvents(Array.isArray(rows) ? rows : []);
  }, [canManageBilling, fetchJson]);

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
          projects: 0,
          paid: 0,
        });
      }
      const group = byAccount.get(accountId);
      group.companies.push(c);
      group.users += Number(c.users_count || 0);
      group.projects += Number(c.projects_count || 0);
      group.paid += Number(c.total_paid || 0);
    });
    return Array.from(byAccount.values());
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
  const hasAuditFilters = Boolean(
    auditFilters.platformAccountId || auditFilters.companyId || auditFilters.action || auditFilters.search.trim()
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
    {id:'tariffs', label:'💼 Тарифы'},
    canManageBilling && {id:'payments', label:'💰 Платежи'},
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
            <div style={{...card,padding:'16px'}}><p style={{color:C.textSec,fontSize:'12px',margin:'0 0 6px'}}>💳 Оплата истекла</p><b style={{color:(dashboard.paymentExpired||0)?C.danger:C.success,fontSize:'24px'}}>{dashboard.paymentExpired || 0}</b></div>
            <div style={{...card,padding:'16px'}}><p style={{color:C.textSec,fontSize:'12px',margin:'0 0 6px'}}>💰 Выручка месяц</p><b style={{color:C.success,fontSize:'20px'}}>{Math.round(dashboard.monthRevenue).toLocaleString('ru-RU')+' ₽'}</b></div>
            <div style={{...card,padding:'16px'}}><p style={{color:C.textSec,fontSize:'12px',margin:'0 0 6px'}}>💰 Выручка год</p><b style={{color:C.success,fontSize:'20px'}}>{Math.round(dashboard.yearRevenue).toLocaleString('ru-RU')+' ₽'}</b></div>
            <div style={{...card,padding:'16px'}}><p style={{color:C.textSec,fontSize:'12px',margin:'0 0 6px'}}>🎁 Новых заявок</p><b style={{color:C.warning,fontSize:'24px'}}>{dashboard.newDemoRequests}</b></div>
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
	            {canManagePlatform && <button onClick={()=>{setShowNewCompany(true);setLastInviteCode(null);setClientCardRecognition(null);}} style={btnO}>+ Подключить аккаунт/компанию</button>}
	          </div>
	          {canManagePlatform && showNewCompany && (<div style={{...card,padding:'16px',marginBottom:'14px'}}>
	            <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'10px'}}>Подключить аккаунт или компанию</b>
            {lastInviteCode && (<div style={{padding:'12px',backgroundColor:C.successLight,border:'1.5px solid '+C.successBorder,borderRadius:'8px',marginBottom:'12px'}}>
              <b style={{color:C.success,fontSize:'13px',display:'block',marginBottom:'6px'}}>✅ Компания создана!</b>
              <p style={{margin:'0 0 8px',fontSize:'12px',color:C.text}}>Отправьте директору ссылку для регистрации:</p>
              <div style={{padding:'10px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border,borderRadius:'6px',fontSize:'12px',color:C.text,wordBreak:'break-all',userSelect:'all',marginBottom:'8px'}}>{window.location.origin+'/?invite='+lastInviteCode}</div>
              <button onClick={()=>navigator.clipboard.writeText(window.location.origin+'/?invite='+lastInviteCode).then(()=>alert('Скопировано'))} style={{...btnO,padding:'5px 12px',fontSize:'12px'}}>📋 Скопировать</button>
	              <button onClick={()=>{setShowNewCompany(false);setLastInviteCode(null);setNewCompany(emptyCompanyForm);setClientCardRecognition(null);}} style={{...btnG,padding:'5px 12px',fontSize:'12px',marginLeft:'6px'}}>Закрыть</button>
	            </div>)}
	            {!lastInviteCode && (<>
              <div style={{padding:'12px',backgroundColor:C.infoLight,border:'1.5px solid '+C.infoBorder,borderRadius:'10px',marginBottom:'12px'}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap'}}>
                  <div>
                    <b style={{color:C.info,fontSize:'13px',display:'block'}}>⚡ Быстрая загрузка карты клиента</b>
                    <p style={{color:C.textSec,fontSize:'11px',margin:'3px 0 0'}}>PDF или фото визитки/карточки организации. Система заполнит поля формы, но компанию создаст только после сохранения.</p>
                  </div>
                  <label style={{...btnO,cursor:clientCardScanning?'default':'pointer',opacity:clientCardScanning?0.65:1}}>
                    {clientCardScanning?'⏳ Распознаю...':'📷 Загрузить карту'}
                    <input type='file' accept='image/*,application/pdf' disabled={clientCardScanning} style={{display:'none'}} onChange={recognizeClientCard}/>
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
              <div style={{display:'flex',gap:'8px',marginTop:'10px'}}>
                <button onClick={async()=>{
                  if (!newCompany.name) { alert('Укажите название'); return; }
                  const r = await sendJson('/system/companies',{method:'POST',body:JSON.stringify({...newCompany,createdBy:user.name})});
                  const data = await r.json();
                  if (data.id) { setLastInviteCode(data.inviteCode); await loadAll(); }
                  else { alert('Ошибка создания'); }
                }} style={btnO}>✓ Создать компанию + ссылку</button>
	                <button onClick={()=>{setShowNewCompany(false);setClientCardRecognition(null);}} style={btnG}>Отмена</button>
	              </div>
	            </>)}
	          </div>)}
	          {companies.length===0 && <div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}>Пока подключена только ваша компания. Нажмите «+ Подключить аккаунт/компанию» чтобы добавить клиента.</div>}
	          {groupsWithLimitStatus.map(group=>(
	            <div key={group.id} style={{...card,padding:'14px',marginBottom:'12px'}}>
	              <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap',marginBottom:'10px'}}>
	                <div>
	                  <b style={{color:C.text,fontSize:'14px'}}>🧭 {group.name}</b>
	                  <p style={{color:C.textMuted,margin:'4px 0 0',fontSize:'11px'}}>Компаний: {group.companies.length} · пользователей: {group.users} · объектов: {group.projects} · оплачено {Math.round(group.paid).toLocaleString('ru-RU')} ₽</p>
	                </div>
		                <span style={badge(C.info,C.infoLight,C.infoBorder)}>{tariffById[group.plan]?.name || group.plan || 'тариф не задан'}</span>
	              </div>
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
	                return (<div key={c.id} style={{padding:'12px 0',borderTop:'1px solid '+C.border}}>
	                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
	                    <div style={{flex:1,minWidth:'250px'}}>
	                      <b style={{color:C.text,fontSize:'14px'}}>{c.name}</b>{c.id===1 && <span style={{marginLeft:'8px',fontSize:'10px',color:C.textMuted}}>(основная)</span>}
	                      <p style={{color:C.textSec,margin:'3px 0',fontSize:'12px'}}>
	                        {c.inn?'ИНН '+c.inn+' · ':''}{c.contact_name||'—'}{c.contact_phone?' · '+c.contact_phone:''}{c.contact_email?' · '+c.contact_email:''}
	                      </p>
	                      <p style={{color:C.textMuted,margin:0,fontSize:'11px'}}>
	                        👥 {c.users_count} польз. · 🏗 {c.projects_count} объектов · 💰 заплачено {Math.round(c.total_paid).toLocaleString('ru-RU')} ₽
	                        {c.trial_until && ' · 🎁 триал до '+c.trial_until}
	                        {c.plan_expires_at && ' · 💼 оплачено до '+c.plan_expires_at}
	                        {(c.max_projects || c.max_users) && ' · лимит '+(c.max_projects || '∞')+' объектов / '+(c.max_users || '∞')+' пользователей'}
	                      </p>
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
	                      {isDemo && <button onClick={async()=>{const days=prompt('Продлить триал на сколько дней?','30');if(days){const base=new Date(c.trial_until||new Date());const today=new Date();const newDate=base>today?base:today;newDate.setDate(newDate.getDate()+Number(days));await sendJson('/system/companies/'+c.id,{method:'PUT',body:JSON.stringify({trialUntil:newDate.toISOString().split('T')[0],paymentStatus:'trial'})});loadAll();}}} style={{...btnG,padding:'4px 10px',fontSize:'11px'}}>📅 Продлить триал</button>}
	                      {!isDemo && !isSuspended && <button onClick={async()=>{await sendJson('/system/companies/'+c.id,{method:'PUT',body:JSON.stringify({action:'mark_overdue'})});loadAll();}} style={{...btnG,padding:'4px 10px',fontSize:'11px'}}>⚠️ Просрочка</button>}
	                      {!isSuspended && <button onClick={async()=>{const reason=prompt('Причина мягкой заморозки:',billingState.reason || 'Не оплачен доступ');if(reason!==null){await sendJson('/system/companies/'+c.id,{method:'PUT',body:JSON.stringify({action:'soft_suspend',reason})});loadAll();}}} style={{...btnR,padding:'4px 10px',fontSize:'11px'}}>⏸ Мягко заморозить</button>}
	                      {isSuspended && <button onClick={async()=>{await sendJson('/system/companies/'+c.id,{method:'PUT',body:JSON.stringify({action:'resume'})});loadAll();}} style={{...btnGr,padding:'4px 10px',fontSize:'11px'}}>▶ Разморозить</button>}
                      {canManageBilling && <button onClick={()=>{setNewPayment({...newPayment,companyId:c.id,amount:c.monthly_fee||''});setShowNewPayment(true);setTab('payments');}} style={{...btnO,padding:'4px 10px',fontSize:'11px'}}>💰 Зачислить оплату</button>}
                      {canManageBilling && <button onClick={()=>{setNewBillingDocument({...newBillingDocument,companyId:c.id,amount:c.monthly_fee||'',documentType:'invoice'});setShowNewBillingDocument(true);setTab('payments');}} style={{...btnG,padding:'4px 10px',fontSize:'11px'}}>📄 Счет/акт</button>}
	                    </div>
	                  )}
	                  {c.suspended_reason && <p style={{color:C.danger,fontSize:'11px',margin:'6px 0 0',fontStyle:'italic'}}>⚠️ {c.suspended_reason}</p>}
	                </div>);
	              })}
	            </div>
	          ))}
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

          {paymentEvents.length > 0 && (<div style={{...card,padding:'12px',marginBottom:'14px',backgroundColor:C.warningLight,border:'1.5px solid '+C.warningBorder}}>
            <b style={{color:C.warning,fontSize:'13px',display:'block',marginBottom:'8px'}}>События провайдеров ({paymentEvents.length})</b>
            <p style={{color:C.textSec,fontSize:'11px',margin:'0 0 8px'}}>Это входящие события ЮKassa/Robokassa. Они не являются оплатой, пока биллинг отдельно не зачислит фактический платеж.</p>
            <div style={{display:'grid',gap:'6px'}}>
              {paymentEvents.slice(0,8).map(event=>{
                const eventColors = paymentEventStatusColor(event.action_status);
                const canConfirmEvent = event.action_status !== 'payment_recorded' && event.billing_document_id && event.billing_document_number;
                return (<div key={event.id} style={{display:'grid',gridTemplateColumns:'minmax(90px,130px) 1fr auto',gap:'8px',alignItems:'center',padding:'8px',border:'1px solid '+C.border,borderRadius:'8px',backgroundColor:C.card}}>
                <b style={{color:C.text,fontSize:'12px'}}>{event.provider || 'provider'}</b>
                <div style={{minWidth:0}}>
                  <p style={{color:C.textSec,fontSize:'11px',margin:0,overflowWrap:'anywhere'}}>{event.event_type || 'event'} · {event.provider_status || 'без статуса'} · {event.billing_document_number || 'документ не найден'} · {Number(event.amount || 0).toLocaleString('ru-RU')} ₽</p>
                  <p style={{color:C.textMuted,fontSize:'10px',margin:'2px 0 0'}}>{event.company_name || '—'} · {event.received_at ? String(event.received_at).slice(0,19).replace('T',' ') : ''}{event.payment_id ? ' · платеж #'+event.payment_id : ''}</p>
                </div>
                <div style={{display:'flex',gap:'6px',alignItems:'center',justifyContent:'flex-end',flexWrap:'wrap'}}>
                  <span style={badge(eventColors.color,eventColors.bg,eventColors.border)}>{event.action_status || 'received'}</span>
                  {canConfirmEvent && <button onClick={()=>confirmPaymentEvent(event)} style={{...btnO,padding:'5px 10px',fontSize:'11px'}}>Зачислить</button>}
                </div>
              </div>);
              })}
            </div>
          </div>)}

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
