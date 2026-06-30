import { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle,
  Building2,
  CreditCard,
  FileText,
  Headphones,
  RefreshCw,
  ShieldCheck,
  Users,
} from 'lucide-react';

function ClientAccountCabinet({user, setUser, C, card, btnG, API, handleLogout}) {
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const authHeaders = useCallback((headers={}) => {
    const token = localStorage.getItem('authToken');
    return token ? {...headers, Authorization:'Bearer '+token} : headers;
  }, []);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await fetch(API + '/account/dashboard', {headers:authHeaders()});
      if (response.status === 401) {
        localStorage.removeItem('authToken');
        setUser(null);
        setError('Сессия истекла. Войдите заново.');
        return;
      }
      if (!response.ok) {
        let message = 'Не удалось загрузить кабинет аккаунта.';
        try {
          const body = await response.json();
          message = body?.detail || message;
        } catch (_) {}
        setError(message);
        return;
      }
      setDashboard(await response.json());
    } catch (_) {
      setError('Сервер недоступен. Проверьте соединение и повторите загрузку.');
    } finally {
      setLoading(false);
    }
  }, [API, authHeaders, setUser]);

  useEffect(()=>{ loadDashboard(); }, [loadDashboard]);

  const formatDate = value => {
    if (!value) return '-';
    try {
      return new Date(value).toLocaleDateString('ru-RU');
    } catch (_) {
      return String(value).slice(0, 10);
    }
  };
  const formatMoney = value => {
    const amount = Number(value || 0);
    if (!amount) return '-';
    return Math.round(amount).toLocaleString('ru-RU') + ' ₽';
  };
  const statusTone = level => {
    if (level === 'danger') return {backgroundColor:C.dangerLight || '#fee2e2', color:C.danger || '#dc2626', borderColor:C.dangerBorder || '#fecaca'};
    if (level === 'warning') return {backgroundColor:C.warningLight || '#fef3c7', color:C.warning || '#b45309', borderColor:C.warningBorder || '#fde68a'};
    if (level === 'info') return {backgroundColor:C.infoLight || '#dbeafe', color:C.info || '#2563eb', borderColor:C.infoBorder || '#bfdbfe'};
    return {backgroundColor:C.successLight || '#dcfce7', color:C.success || '#16a34a', borderColor:C.successBorder || '#bbf7d0'};
  };
  const chip = (text, level='success') => (
    <span style={{
      ...statusTone(level),
      border:'1px solid',
      borderRadius:'999px',
      padding:'3px 8px',
      fontSize:'11px',
      fontWeight:800,
      whiteSpace:'nowrap',
      display:'inline-flex',
      alignItems:'center',
      gap:'4px',
    }}>{text}</span>
  );
  const usage = dashboard?.usage || {};
  const account = dashboard?.account || {};
  const tariff = dashboard?.tariff || {};
  const stats = [
    {label:'Компании', value:usage.companies ?? 0, hint:`активных: ${usage.activeCompanies ?? 0}`, icon:Building2},
    {label:'Пользователи', value:usage.activeUsers ?? 0, hint:`всего: ${usage.totalUsers ?? 0}`, icon:Users},
    {label:'Объекты', value:usage.projects ?? 0, hint:'только количество, без доступа к объектам', icon:ShieldCheck},
    {label:'Счета', value:usage.billingDocuments ?? 0, hint:'документы платформы', icon:FileText},
    {label:'Контакты', value:usage.openFollowups ?? 0, hint:'открытые задачи платформы', icon:Headphones},
  ];

  const pageStyle = {minHeight:'100vh',background:C.bg,padding:'clamp(14px,3vw,28px)'};
  const shellStyle = {maxWidth:'1180px',margin:'0 auto'};
  const sectionTitle = {color:C.text,fontSize:'18px',margin:'0 0 12px',fontWeight:900};
  const muted = {color:C.textSec,fontSize:'13px',lineHeight:1.45};
  const tableWrap = {overflowX:'auto',border:'1px solid '+C.border,borderRadius:'8px'};
  const th = {padding:'10px 12px',color:C.textSec,fontSize:'12px',fontWeight:800,textAlign:'left',borderBottom:'1px solid '+C.border,backgroundColor:C.bg,whiteSpace:'nowrap'};
  const td = {padding:'10px 12px',color:C.text,fontSize:'13px',borderBottom:'1px solid '+C.border,verticalAlign:'top'};

  if (loading && !dashboard) {
    return (
      <div style={pageStyle}>
        <div style={shellStyle}>
          <div style={{...card,padding:'18px',display:'flex',alignItems:'center',gap:'10px'}}>
            <RefreshCw size={18} />
            <div>
              <div style={{color:C.text,fontWeight:900}}>Загружаю кабинет аккаунта</div>
              <div style={muted}>Собираю компании, пользователей, счета и задачи платформы.</div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={pageStyle}>
      <div style={shellStyle}>
        <header style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'14px',flexWrap:'wrap',marginBottom:'18px'}}>
          <div>
            <div style={{display:'flex',alignItems:'center',gap:'8px',flexWrap:'wrap',marginBottom:'8px'}}>
              {chip(account.active === false ? 'Аккаунт отключен' : account.status || 'Аккаунт активен', account.active === false ? 'danger' : 'success')}
              {chip(account.planLabel || tariff.name || 'Тариф', 'info')}
            </div>
            <h1 style={{color:C.text,fontSize:'clamp(22px,4vw,34px)',lineHeight:1.1,margin:'0 0 6px'}}>
              {account.name || 'Клиентский аккаунт'}
            </h1>
            <p style={{...muted,margin:0}}>
              {dashboard?.user?.name || user?.name || user?.email} · {dashboard?.user?.roleLabel || user?.role}
            </p>
          </div>
          <div style={{display:'flex',gap:'8px',flexWrap:'wrap'}}>
            <button onClick={loadDashboard} disabled={loading} style={{...btnG,display:'inline-flex',alignItems:'center',gap:'6px'}}>
              <RefreshCw size={16} /> Обновить
            </button>
            <button onClick={handleLogout} style={btnG}>Выйти</button>
          </div>
        </header>

        {error && (
          <div style={{...card,padding:'14px',borderColor:C.dangerBorder || '#fecaca',backgroundColor:C.dangerLight || '#fee2e2',marginBottom:'14px'}}>
            <div style={{display:'flex',alignItems:'center',gap:'8px',color:C.danger || '#dc2626',fontWeight:900}}>
              <AlertTriangle size={18} /> {error}
            </div>
          </div>
        )}

        <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(170px,1fr))',gap:'10px',marginBottom:'14px'}}>
          {stats.map(item => {
            const Icon = item.icon;
            return (
              <div key={item.label} style={{...card,padding:'14px',minHeight:'104px'}}>
                <div style={{display:'flex',justifyContent:'space-between',gap:'8px',alignItems:'center',marginBottom:'10px'}}>
                  <span style={{color:C.textSec,fontSize:'12px',fontWeight:800}}>{item.label}</span>
                  <Icon size={18} color={C.textSec} />
                </div>
                <div style={{color:C.text,fontSize:'28px',fontWeight:900,lineHeight:1}}>{item.value}</div>
                <div style={{...muted,fontSize:'12px',marginTop:'8px'}}>{item.hint}</div>
              </div>
            );
          })}
        </div>

        {!!dashboard?.limitWarnings?.length && (
          <section style={{...card,padding:'14px',marginBottom:'14px',backgroundColor:C.warningLight || '#fef3c7',borderColor:C.warningBorder || '#fde68a'}}>
            <h2 style={{...sectionTitle,fontSize:'15px',display:'flex',alignItems:'center',gap:'8px',marginBottom:'8px'}}>
              <AlertTriangle size={18} /> Лимиты тарифа
            </h2>
            <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(220px,1fr))',gap:'8px'}}>
              {dashboard.limitWarnings.map((item, idx) => (
                <div key={idx} style={{...muted,color:C.text}}>{item.message}</div>
              ))}
            </div>
          </section>
        )}

        <section style={{...card,padding:'16px',marginBottom:'14px'}}>
          <div style={{display:'flex',justifyContent:'space-between',gap:'12px',alignItems:'flex-start',flexWrap:'wrap',marginBottom:'12px'}}>
            <div>
              <h2 style={sectionTitle}>Компании аккаунта</h2>
              <p style={{...muted,margin:0}}>Видны только юрлица вашей группы и агрегаты по объектам, без перехода в рабочую ERP.</p>
            </div>
            {tariff.includedCompanies ? chip(`Лимит компаний: ${tariff.includedCompanies}`, 'info') : chip('Компании без лимита', 'info')}
          </div>
          <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(240px,1fr))',gap:'10px'}}>
            {(dashboard?.companies || []).map(company => (
              <article key={company.id} style={{border:'1px solid '+C.border,borderRadius:'8px',padding:'12px',backgroundColor:C.card || '#fff'}}>
                <div style={{display:'flex',justifyContent:'space-between',gap:'8px',alignItems:'flex-start',marginBottom:'8px'}}>
                  <div>
                    <div style={{color:C.text,fontWeight:900,fontSize:'15px'}}>{company.shortName || company.name}</div>
                    <div style={{...muted,fontSize:'12px'}}>{company.inn ? 'ИНН '+company.inn : 'ИНН не указан'}</div>
                  </div>
                  {chip(company.billingState?.label || (company.active ? 'Активна' : 'Отключена'), company.billingState?.level || (company.active ? 'success' : 'danger'))}
                </div>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginTop:'10px'}}>
                  <div style={{...muted}}>Объекты<br/><b style={{color:C.text,fontSize:'16px'}}>{company.projectsCount}</b></div>
                  <div style={{...muted}}>Пользователи<br/><b style={{color:C.text,fontSize:'16px'}}>{company.activeUsersCount}/{company.usersCount}</b></div>
                </div>
                <div style={{...muted,fontSize:'12px',marginTop:'10px'}}>
                  {company.contactName || 'Контакт не указан'}
                  {company.contactPhone ? ' · '+company.contactPhone : ''}
                  {company.contactEmail ? ' · '+company.contactEmail : ''}
                </div>
              </article>
            ))}
            {!dashboard?.companies?.length && <p style={{...muted,margin:0}}>Компании еще не подключены к аккаунту.</p>}
          </div>
        </section>

        <section style={{...card,padding:'16px',marginBottom:'14px'}}>
          <h2 style={sectionTitle}>Пользователи</h2>
          <div style={tableWrap}>
            <table style={{width:'100%',borderCollapse:'collapse',minWidth:'680px'}}>
              <thead>
                <tr>
                  <th style={th}>Пользователь</th>
                  <th style={th}>Роль</th>
                  <th style={th}>Компания</th>
                  <th style={th}>Статус</th>
                  <th style={th}>2FA</th>
                </tr>
              </thead>
              <tbody>
                {(dashboard?.users || []).map(item => (
                  <tr key={item.id}>
                    <td style={td}><b>{item.name || item.email}</b><br/><span style={muted}>{item.email}</span></td>
                    <td style={td}>{item.roleLabel || item.role}</td>
                    <td style={td}>{item.companyName || 'Уровень аккаунта'}</td>
                    <td style={td}>{chip(item.active ? 'Активен' : 'Отключен', item.active ? 'success' : 'danger')}</td>
                    <td style={td}>{item.twoFactorEnabled ? chip('Включена', 'success') : item.twoFactorRequired ? chip('Требуется', 'warning') : chip('Не требуется', 'info')}</td>
                  </tr>
                ))}
                {!dashboard?.users?.length && (
                  <tr><td style={td} colSpan={5}>Пользователи не найдены.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(300px,1fr))',gap:'14px'}}>
          <section style={{...card,padding:'16px'}}>
            <h2 style={{...sectionTitle,display:'flex',alignItems:'center',gap:'8px'}}><CreditCard size={18}/> Счета и документы</h2>
            <div style={{display:'grid',gap:'8px'}}>
              {(dashboard?.billingDocuments || []).slice(0, 8).map(item => (
                <div key={item.id} style={{border:'1px solid '+C.border,borderRadius:'8px',padding:'10px'}}>
                  <div style={{display:'flex',justifyContent:'space-between',gap:'8px',alignItems:'center',marginBottom:'6px'}}>
                    <b style={{color:C.text}}>{item.documentTypeLabel} {item.number || '#'+item.id}</b>
                    {chip(item.statusLabel || item.status, item.status === 'closed' ? 'success' : item.status === 'cancelled' ? 'danger' : 'warning')}
                  </div>
                  <div style={muted}>{item.companyName || 'Аккаунт'} · {formatMoney(item.amount)} · срок {formatDate(item.dueDate)}</div>
                </div>
              ))}
              {!dashboard?.billingDocuments?.length && <p style={{...muted,margin:0}}>Платежные документы еще не выставлялись.</p>}
            </div>
          </section>

          <section style={{...card,padding:'16px'}}>
            <h2 style={{...sectionTitle,display:'flex',alignItems:'center',gap:'8px'}}><Headphones size={18}/> Поддержка и контакты</h2>
            <div style={{display:'grid',gap:'8px'}}>
              {(dashboard?.followups || []).slice(0, 6).map(item => (
                <div key={'f'+item.id} style={{border:'1px solid '+C.border,borderRadius:'8px',padding:'10px'}}>
                  <div style={{display:'flex',justifyContent:'space-between',gap:'8px',alignItems:'center',marginBottom:'6px'}}>
                    <b style={{color:C.text}}>{item.title || item.sourceLabel}</b>
                    {chip(item.statusLabel || item.status, item.status === 'waiting' ? 'warning' : 'info')}
                  </div>
                  <div style={muted}>{item.companyName || 'Аккаунт'} · {item.responsibleName || 'без ответственного'} · {formatDate(item.dueDate)}</div>
                </div>
              ))}
              {(dashboard?.supportSessions || []).slice(0, 4).map(item => (
                <div key={'s'+item.id} style={{border:'1px solid '+C.border,borderRadius:'8px',padding:'10px'}}>
                  <div style={{display:'flex',justifyContent:'space-between',gap:'8px',alignItems:'center',marginBottom:'6px'}}>
                    <b style={{color:C.text}}>{item.reason || item.scopeLabel}</b>
                    {chip(item.status || 'active', item.status === 'active' ? 'success' : 'info')}
                  </div>
                  <div style={muted}>{item.companyName || 'Аккаунт'} · доступ до {formatDate(item.expiresAt)}</div>
                </div>
              ))}
              {!dashboard?.followups?.length && !dashboard?.supportSessions?.length && (
                <p style={{...muted,margin:0}}>Открытых задач поддержки сейчас нет.</p>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

export default ClientAccountCabinet;
