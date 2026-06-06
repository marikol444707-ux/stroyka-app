import { useCallback, useEffect, useState } from 'react';

function SystemOwnerCabinet({user, setUser, C, card, btnO, btnG, btnGr, btnR, inp, badge, API}) {
  const [tab, setTab] = useState('dashboard');
  const [dashboard, setDashboard] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [payments, setPayments] = useState([]);
  const [demos, setDemos] = useState([]);
  const [showNewCompany, setShowNewCompany] = useState(false);
  const [newCompany, setNewCompany] = useState({name:'',shortName:'',inn:'',kpp:'',contactName:'',contactPhone:'',contactEmail:'',plan:'demo',trialDays:30,monthlyFee:'',maxProjects:'',maxUsers:'',notes:''});
  const [newPayment, setNewPayment] = useState({companyId:'',amount:'',paymentDate:new Date().toISOString().split('T')[0],method:'card',invoiceNumber:'',periodStart:'',periodEnd:'',notes:''});
  const [showNewPayment, setShowNewPayment] = useState(false);
  const [lastInviteCode, setLastInviteCode] = useState(null);

  const loadAll = useCallback(async () => {
    try {
      const [d, c, p, dr] = await Promise.all([
        fetch(API+'/system/dashboard').then(r=>r.json()),
        fetch(API+'/system/companies').then(r=>r.json()),
        fetch(API+'/system/payments').then(r=>r.json()),
        fetch(API+'/demo-requests').then(r=>r.json()),
      ]);
      setDashboard(d);
      setCompanies(Array.isArray(c)?c:[]);
      setPayments(Array.isArray(p)?p:[]);
      setDemos(Array.isArray(dr)?dr:[]);
    } catch(_){}
  }, [API]);
  useEffect(()=>{ loadAll(); }, [loadAll]);

  const TABS = [
    {id:'dashboard', label:'📊 Дашборд'},
    {id:'companies', label:'🏢 Компании'},
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
            <div style={{...card,padding:'16px'}}><p style={{color:C.textSec,fontSize:'12px',margin:'0 0 6px'}}>🏢 Активные компании</p><b style={{color:C.success,fontSize:'24px'}}>{dashboard.activeCompanies}</b></div>
            <div style={{...card,padding:'16px'}}><p style={{color:C.textSec,fontSize:'12px',margin:'0 0 6px'}}>🎁 В демо</p><b style={{color:C.info,fontSize:'24px'}}>{dashboard.inDemo}</b></div>
            <div style={{...card,padding:'16px'}}><p style={{color:C.textSec,fontSize:'12px',margin:'0 0 6px'}}>⏸ Заморожены</p><b style={{color:C.textMuted,fontSize:'24px'}}>{dashboard.suspended}</b></div>
            <div style={{...card,padding:'16px'}}><p style={{color:C.textSec,fontSize:'12px',margin:'0 0 6px'}}>⚠️ Просрочка</p><b style={{color:C.danger,fontSize:'24px'}}>{dashboard.overdue}</b></div>
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
            <b style={{color:C.text,fontSize:'15px'}}>Подключённые компании ({companies.length})</b>
            <button onClick={()=>{setShowNewCompany(true);setLastInviteCode(null);}} style={btnO}>+ Подключить компанию</button>
          </div>
          {showNewCompany && (<div style={{...card,padding:'16px',marginBottom:'14px'}}>
            <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'10px'}}>Новая компания</b>
            {lastInviteCode && (<div style={{padding:'12px',backgroundColor:C.successLight,border:'1.5px solid '+C.successBorder,borderRadius:'8px',marginBottom:'12px'}}>
              <b style={{color:C.success,fontSize:'13px',display:'block',marginBottom:'6px'}}>✅ Компания создана!</b>
              <p style={{margin:'0 0 8px',fontSize:'12px',color:C.text}}>Отправьте директору ссылку для регистрации:</p>
              <div style={{padding:'10px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border,borderRadius:'6px',fontSize:'12px',color:C.text,wordBreak:'break-all',userSelect:'all',marginBottom:'8px'}}>{window.location.origin+'/?invite='+lastInviteCode}</div>
              <button onClick={()=>navigator.clipboard.writeText(window.location.origin+'/?invite='+lastInviteCode).then(()=>alert('Скопировано'))} style={{...btnO,padding:'5px 12px',fontSize:'12px'}}>📋 Скопировать</button>
              <button onClick={()=>{setShowNewCompany(false);setLastInviteCode(null);setNewCompany({name:'',shortName:'',inn:'',kpp:'',contactName:'',contactPhone:'',contactEmail:'',plan:'demo',trialDays:30,monthlyFee:'',maxProjects:'',maxUsers:'',notes:''});}} style={{...btnG,padding:'5px 12px',fontSize:'12px',marginLeft:'6px'}}>Закрыть</button>
            </div>)}
            {!lastInviteCode && (<>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px'}}>
                <input placeholder='Название компании *' value={newCompany.name} onChange={e=>setNewCompany({...newCompany,name:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                <input placeholder='ИНН' value={newCompany.inn} onChange={e=>setNewCompany({...newCompany,inn:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='КПП' value={newCompany.kpp} onChange={e=>setNewCompany({...newCompany,kpp:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Контактное лицо' value={newCompany.contactName} onChange={e=>setNewCompany({...newCompany,contactName:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Телефон' value={newCompany.contactPhone} onChange={e=>setNewCompany({...newCompany,contactPhone:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Email' value={newCompany.contactEmail} onChange={e=>setNewCompany({...newCompany,contactEmail:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                <select value={newCompany.plan} onChange={e=>setNewCompany({...newCompany,plan:e.target.value})} style={{...inp,marginBottom:0}}>
                  <option value='demo'>🎁 Демо (триал)</option>
                  <option value='starter'>🚀 Старт</option>
                  <option value='pro'>💼 Pro</option>
                  <option value='enterprise'>🏢 Enterprise</option>
                </select>
                {newCompany.plan==='demo' ? (
                  <input type='number' placeholder='Дней триала' value={newCompany.trialDays} onChange={e=>setNewCompany({...newCompany,trialDays:e.target.value})} style={{...inp,marginBottom:0}}/>
                ) : (
                  <input type='number' placeholder='₽ в месяц' value={newCompany.monthlyFee} onChange={e=>setNewCompany({...newCompany,monthlyFee:e.target.value})} style={{...inp,marginBottom:0}}/>
                )}
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
          {companies.length===0 && <div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}>Пока подключена только ваша компания. Нажмите «+ Подключить компанию» чтобы добавить клиента.</div>}
          {companies.map(c=>{
            const isDemo = c.plan==='demo';
            const isSuspended = c.suspended_at;
            const stC = isSuspended?C.danger:isDemo?C.info:C.success;
            const stBg = isSuspended?C.dangerLight:isDemo?C.infoLight:C.successLight;
            const stBd = isSuspended?C.dangerBorder:isDemo?C.infoBorder:C.successBorder;
            return (<div key={c.id} style={{...card,padding:'14px',marginBottom:'10px',borderLeft:'4px solid '+stC}}>
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
                  </p>
                </div>
                <div style={{display:'flex',gap:'4px',flexWrap:'wrap',alignItems:'flex-start'}}>
                  <span style={badge(stC,stBg,stBd)}>{isSuspended?'⏸ Заморожена':isDemo?'🎁 Демо':c.plan}</span>
                  {c.monthly_fee>0 && <span style={badge(C.text,C.bg,C.border)}>{Number(c.monthly_fee).toLocaleString('ru-RU')+' ₽/мес'}</span>}
                </div>
              </div>
              {c.id!==1 && (
                <div style={{display:'flex',gap:'6px',marginTop:'8px',flexWrap:'wrap'}}>
                  {isDemo && <button onClick={async()=>{const days=prompt('Продлить триал на сколько дней?','30');if(days){const newDate=new Date(c.trial_until||new Date());newDate.setDate(newDate.getDate()+Number(days));await fetch(API+'/system/companies/'+c.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({trialUntil:newDate.toISOString().split('T')[0]})});loadAll();}}} style={{...btnG,padding:'4px 10px',fontSize:'11px'}}>📅 Продлить триал</button>}
                  {!isSuspended && <button onClick={async()=>{const reason=prompt('Причина заморозки:','Не оплачен');if(reason!==null){await fetch(API+'/system/companies/'+c.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'suspend',reason})});loadAll();}}} style={{...btnR,padding:'4px 10px',fontSize:'11px'}}>⏸ Заморозить</button>}
                  {isSuspended && <button onClick={async()=>{await fetch(API+'/system/companies/'+c.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'resume'})});loadAll();}} style={{...btnGr,padding:'4px 10px',fontSize:'11px'}}>▶ Разморозить</button>}
                  <button onClick={()=>{setNewPayment({...newPayment,companyId:c.id,amount:c.monthly_fee||''});setShowNewPayment(true);setTab('payments');}} style={{...btnO,padding:'4px 10px',fontSize:'11px'}}>💰 Зачислить оплату</button>
                </div>
              )}
              {c.suspended_reason && <p style={{color:C.danger,fontSize:'11px',margin:'6px 0 0',fontStyle:'italic'}}>⚠️ {c.suspended_reason}</p>}
            </div>);
          })}
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
