import { useCallback, useEffect, useMemo, useState } from 'react';

function SystemOwnerCabinet({user, setUser, C, card, btnO, btnG, btnGr, btnR, inp, badge, API}) {
  const [tab, setTab] = useState('dashboard');
  const [dashboard, setDashboard] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [payments, setPayments] = useState([]);
  const [demos, setDemos] = useState([]);
  const [tariffs, setTariffs] = useState([]);
  const [showNewCompany, setShowNewCompany] = useState(false);
  const emptyCompanyForm = {platformAccountId:'',platformAccountName:'',name:'',shortName:'',inn:'',kpp:'',contactName:'',contactPhone:'',contactEmail:'',plan:'demo',trialDays:30,monthlyFee:'',maxProjects:'',maxUsers:'',notes:''};
  const [newCompany, setNewCompany] = useState(emptyCompanyForm);
  const [newPayment, setNewPayment] = useState({companyId:'',amount:'',paymentDate:new Date().toISOString().split('T')[0],method:'card',invoiceNumber:'',periodStart:'',periodEnd:'',notes:''});
  const [showNewPayment, setShowNewPayment] = useState(false);
  const [lastInviteCode, setLastInviteCode] = useState(null);

  const loadAll = useCallback(async () => {
    try {
      const [d, c, p, dr, t] = await Promise.all([
        fetch(API+'/system/dashboard').then(r=>r.json()),
        fetch(API+'/system/companies').then(r=>r.json()),
        fetch(API+'/system/payments').then(r=>r.json()),
        fetch(API+'/demo-requests').then(r=>r.json()),
        fetch(API+'/system/tariffs').then(r=>r.json()),
      ]);
      setDashboard(d);
      setCompanies(Array.isArray(c)?c:[]);
      setPayments(Array.isArray(p)?p:[]);
      setDemos(Array.isArray(dr)?dr:[]);
      setTariffs(Array.isArray(t)?t:[]);
    } catch(_){}
	  }, [API]);
	  useEffect(()=>{ loadAll(); }, [loadAll]);

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

  const billingColorSet = (level) => {
    if (level === 'danger') return {color:C.danger, bg:C.dangerLight, border:C.dangerBorder};
    if (level === 'warning') return {color:C.warning, bg:C.warningLight, border:C.warningBorder};
    if (level === 'info') return {color:C.info, bg:C.infoLight, border:C.infoBorder};
    return {color:C.success, bg:C.successLight, border:C.successBorder};
  };

  const billingNeedsAction = (state) => ['trial_expired','payment_expired','payment_overdue','trial_no_date'].includes(state?.status);

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

	  const TABS = [
    {id:'dashboard', label:'📊 Дашборд'},
	    {id:'companies', label:'🏢 Аккаунты/компании'},
    {id:'tariffs', label:'💼 Тарифы'},
    {id:'payments', label:'💰 Платежи'},
    {id:'demos', label:'🎁 Демо-заявки'},
    {id:'system', label:'🔧 Система'},
  ];

  return (
    <div style={{minHeight:'100vh',backgroundColor:C.bg,padding:'20px'}}>
      <div style={{maxWidth:'1100px',margin:'0 auto'}}>
        {/* Шапка */}
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'18px'}}>
          <div style={{display:'flex',alignItems:'center',gap:'12px'}}>
            <span style={{fontSize:'28px'}}>⚙️</span>
            <div>
              <b style={{color:C.text,fontSize:'18px',display:'block'}}>Кабинет владельца платформы</b>
              <p style={{color:C.textSec,margin:0,fontSize:'13px'}}>{user.name}</p>
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
	            <button onClick={()=>{setShowNewCompany(true);setLastInviteCode(null);}} style={btnO}>+ Подключить аккаунт/компанию</button>
	          </div>
	          {showNewCompany && (<div style={{...card,padding:'16px',marginBottom:'14px'}}>
	            <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'10px'}}>Подключить аккаунт или компанию</b>
            {lastInviteCode && (<div style={{padding:'12px',backgroundColor:C.successLight,border:'1.5px solid '+C.successBorder,borderRadius:'8px',marginBottom:'12px'}}>
              <b style={{color:C.success,fontSize:'13px',display:'block',marginBottom:'6px'}}>✅ Компания создана!</b>
              <p style={{margin:'0 0 8px',fontSize:'12px',color:C.text}}>Отправьте директору ссылку для регистрации:</p>
              <div style={{padding:'10px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border,borderRadius:'6px',fontSize:'12px',color:C.text,wordBreak:'break-all',userSelect:'all',marginBottom:'8px'}}>{window.location.origin+'/?invite='+lastInviteCode}</div>
              <button onClick={()=>navigator.clipboard.writeText(window.location.origin+'/?invite='+lastInviteCode).then(()=>alert('Скопировано'))} style={{...btnO,padding:'5px 12px',fontSize:'12px'}}>📋 Скопировать</button>
	              <button onClick={()=>{setShowNewCompany(false);setLastInviteCode(null);setNewCompany(emptyCompanyForm);}} style={{...btnG,padding:'5px 12px',fontSize:'12px',marginLeft:'6px'}}>Закрыть</button>
	            </div>)}
	            {!lastInviteCode && (<>
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
                  const r = await fetch(API+'/system/companies',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...newCompany,createdBy:user.name})});
                  const data = await r.json();
                  if (data.id) { setLastInviteCode(data.inviteCode); await loadAll(); }
                  else { alert('Ошибка создания'); }
                }} style={btnO}>✓ Создать компанию + ссылку</button>
	                <button onClick={()=>setShowNewCompany(false)} style={btnG}>Отмена</button>
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
	                  {c.id!==1 && (
	                    <div style={{display:'flex',gap:'6px',marginTop:'8px',flexWrap:'wrap'}}>
	                      {isDemo && <button onClick={async()=>{const days=prompt('Продлить триал на сколько дней?','30');if(days){const base=new Date(c.trial_until||new Date());const today=new Date();const newDate=base>today?base:today;newDate.setDate(newDate.getDate()+Number(days));await fetch(API+'/system/companies/'+c.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({trialUntil:newDate.toISOString().split('T')[0],paymentStatus:'trial'})});loadAll();}}} style={{...btnG,padding:'4px 10px',fontSize:'11px'}}>📅 Продлить триал</button>}
	                      {!isDemo && !isSuspended && <button onClick={async()=>{await fetch(API+'/system/companies/'+c.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'mark_overdue'})});loadAll();}} style={{...btnG,padding:'4px 10px',fontSize:'11px'}}>⚠️ Просрочка</button>}
	                      {!isSuspended && <button onClick={async()=>{const reason=prompt('Причина мягкой заморозки:',billingState.reason || 'Не оплачен доступ');if(reason!==null){await fetch(API+'/system/companies/'+c.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'soft_suspend',reason})});loadAll();}}} style={{...btnR,padding:'4px 10px',fontSize:'11px'}}>⏸ Мягко заморозить</button>}
	                      {isSuspended && <button onClick={async()=>{await fetch(API+'/system/companies/'+c.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'resume'})});loadAll();}} style={{...btnGr,padding:'4px 10px',fontSize:'11px'}}>▶ Разморозить</button>}
	                      <button onClick={()=>{setNewPayment({...newPayment,companyId:c.id,amount:c.monthly_fee||''});setShowNewPayment(true);setTab('payments');}} style={{...btnO,padding:'4px 10px',fontSize:'11px'}}>💰 Зачислить оплату</button>
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
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'14px'}}>
            <b style={{color:C.text,fontSize:'15px'}}>Платежи от клиентов ({payments.length})</b>
            <button onClick={()=>setShowNewPayment(!showNewPayment)} style={btnO}>+ Зачислить платёж</button>
          </div>
          {showNewPayment && (<div style={{...card,padding:'16px',marginBottom:'14px'}}>
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
                await fetch(API+'/system/payments',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...newPayment,createdBy:user.name})});
                setShowNewPayment(false);
                setNewPayment({companyId:'',amount:'',paymentDate:new Date().toISOString().split('T')[0],method:'card',invoiceNumber:'',periodStart:'',periodEnd:'',notes:''});
                await loadAll();
              }} style={btnO}>✓ Зачислить</button>
              <button onClick={()=>setShowNewPayment(false)} style={btnG}>Отмена</button>
            </div>
          </div>)}
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
              <button onClick={async()=>{await fetch(API+'/demo-requests/'+d.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Обработана'})});loadAll();}} style={{...btnGr,padding:'4px 10px',fontSize:'11px'}}>✓ Обработана</button>
              <button onClick={async()=>{await fetch(API+'/demo-requests/'+d.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Отклонена'})});loadAll();}} style={{...btnR,padding:'4px 10px',fontSize:'11px'}}>✕ Отклонить</button>
            </div>)}
          </div>))}
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
