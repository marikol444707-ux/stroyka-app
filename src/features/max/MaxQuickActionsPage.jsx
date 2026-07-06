import React from 'react';
import { Bot, ClipboardList, CloudSun, CreditCard, FolderKanban, LogIn, MessageSquare, Package, Plus, ReceiptText, Truck } from 'lucide-react';
import { API } from '../../api';
import { normalizeStoredUser } from '../../utils/appRuntimeUtils';
import { getQuickActionsForUser, QUICK_ACTION_IDS } from '../quick-actions/quickActionRegistry';

const iconByAction = {
  [QUICK_ACTION_IDS.ASSIGNMENTS]: ClipboardList,
  [QUICK_ACTION_IDS.RECEIVE_WAREHOUSE]: Plus,
  [QUICK_ACTION_IDS.TRANSFER_MATERIAL]: Truck,
  [QUICK_ACTION_IDS.OBJECT_EXPENSE]: ReceiptText,
  [QUICK_ACTION_IDS.OWN_EXPENSE]: CreditCard,
  [QUICK_ACTION_IDS.CHAT]: MessageSquare,
  [QUICK_ACTION_IDS.WEATHER]: CloudSun,
  [QUICK_ACTION_IDS.PROJECTS]: FolderKanban,
  [QUICK_ACTION_IDS.WAREHOUSE]: Package,
  [QUICK_ACTION_IDS.AI]: Bot,
};

const readStoredUser = () => {
  try {
    const raw = localStorage.getItem('user');
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

const readMaxLaunchData = () => {
  if (typeof window === 'undefined') return {initData:'', inviteCode:''};
  const params = new URLSearchParams(window.location.search || '');
  const bridge = window.MAXBridge || window.maxBridge || window.max || window.Max;
  const localPreview = ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname);
  const allowWebSession = params.get('webSession') === '1' || params.get('from') === 'max';
  return {
    initData: params.get('initData') || params.get('init_data') || bridge?.initData || bridge?.init_data || '',
    inviteCode: params.get('invite') || params.get('code') || params.get('startapp') || params.get('start_param') || '',
    allowWebSession,
    previewRole: localPreview ? (params.get('role') || '') : '',
    previewName: localPreview ? (params.get('name') || 'Локальный предпросмотр') : '',
  };
};

const roleLabel = (role) => {
  const map = {
    директор: 'Директор',
    зам_директора: 'Зам. директора',
    главный_инженер: 'Главный инженер',
    прораб: 'Прораб',
    кладовщик: 'Кладовщик',
    бухгалтер: 'Бухгалтер',
    снабженец: 'Снабженец',
    мастер: 'Мастер',
    бригадир: 'Бригадир',
    субподрядчик: 'Субподрядчик',
    сметчик: 'Сметчик',
    стройконтроль: 'Стройконтроль',
    технадзор: 'Технадзор',
  };
  return map[role] || role || 'Роль не определена';
};

const persistMiniAppSession = (payload) => {
  const source = payload?.user && typeof payload.user === 'object' ? payload.user : payload;
  const token = source?.authToken || payload?.authToken || '';
  const user = normalizeStoredUser(source);
  if (!token || !user) return null;
  try {
    localStorage.setItem('authToken', token);
    localStorage.setItem('user', JSON.stringify(user));
    return user;
  } catch {
    return null;
  }
};

export default function MaxQuickActionsPage() {
  const [state, setState] = React.useState({
    loading:true,
    error:'',
    account:null,
    source:'max',
    sessionCreated:false,
    requiresWebLogin:false,
    sessionNote:'',
    webSessionAvailable:false,
    maxUser:null,
    maxChat:null,
  });

  React.useEffect(() => {
    let cancelled = false;
    const run = async () => {
      const launch = readMaxLaunchData();
      if (!launch.initData) {
        if (launch.previewRole) {
          if (!cancelled) {
            setState({
              loading:false,
              error:'',
              account: {employeeName: launch.previewName, employeeRole: launch.previewRole},
              source:'local',
              webSessionAvailable:false,
              maxUser:null,
              maxChat:null,
            });
          }
          return;
        }
        const localUser = readStoredUser();
        if (localUser && launch.allowWebSession) {
          if (!cancelled) {
            setState({
              loading:false,
              error:'',
              account: {employeeName: localUser.name, employeeRole: localUser.role},
              source:'web',
              sessionCreated:false,
              requiresWebLogin:false,
              sessionNote:'Работаете через web-вход Stroyka внутри MAX',
              webSessionAvailable:true,
              maxUser:null,
              maxChat:null,
            });
          }
          return;
        }
        if (!cancelled) {
          setState({
            loading:false,
            error: localUser
              ? 'MAX не передал подписанные данные. Откройте через web-вход или проверьте настройку mini-app.'
              : 'Откройте мини-приложение из MAX или войдите в Stroyka в этом браузере.',
            account:null,
            source:'max',
            sessionCreated:false,
            requiresWebLogin:false,
            sessionNote:'',
            webSessionAvailable:Boolean(localUser),
            maxUser:null,
            maxChat:null,
          });
        }
        return;
      }
      try {
        try {
          localStorage.removeItem('authToken');
          localStorage.removeItem('user');
        } catch {}
        const res = await fetch(API + '/max/miniapp/validate', {
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({initData: launch.initData, code: launch.inviteCode}),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || 'MAX-проверка не прошла');
        let account = data.linkedAccount || null;
        let sessionCreated = false;
        let requiresWebLogin = false;
        let sessionNote = '';
        if (account) {
          try {
            const sessionRes = await fetch(API + '/max/miniapp/session', {
              method:'POST',
              headers:{'Content-Type':'application/json'},
              body: JSON.stringify({initData: launch.initData, code: launch.inviteCode}),
            });
            const sessionData = await sessionRes.json().catch(() => ({}));
            if (sessionRes.ok && sessionData.sessionCreated) {
              const sessionUser = persistMiniAppSession(sessionData);
              sessionCreated = Boolean(sessionUser);
              account = sessionData.linkedAccount || {
                employeeName: sessionUser?.name || account.employeeName,
                employeeRole: sessionUser?.role || account.employeeRole,
                projectName: sessionUser?.projectName || sessionUser?.project_name || account.projectName,
                assignedProjects: sessionUser?.assignedProjects || account.assignedProjects,
              };
              sessionNote = sessionCreated ? 'Вход из MAX готов' : 'MAX-связка найдена, но сессию сохранить не удалось';
            } else if (sessionRes.ok && sessionData.requiresWebLogin) {
              requiresWebLogin = true;
              sessionNote = sessionData.detail || 'Для этой роли нужен обычный вход в Stroyka';
            } else {
              sessionNote = sessionData.detail || 'MAX-связка найдена, но быстрый вход не создан';
            }
          } catch (error) {
            sessionNote = error?.message || 'MAX-связка найдена, но быстрый вход не создан';
          }
        }
        if (!cancelled) {
          setState({
            loading:false,
            error: account ? '' : 'MAX-аккаунт не связан с сотрудником Stroyka.',
            account,
            source:'max',
            sessionCreated,
            requiresWebLogin,
            sessionNote,
            webSessionAvailable:false,
            maxUser:data.maxUser || null,
            maxChat:data.maxChat || null,
          });
        }
      } catch (error) {
        if (!cancelled) setState({loading:false, error:error.message || 'MAX-проверка не прошла', account:null, source:'max', sessionCreated:false, requiresWebLogin:false, sessionNote:'', webSessionAvailable:false, maxUser:null, maxChat:null});
      }
    };
    run();
    return () => { cancelled = true; };
  }, []);

  const role = state.account?.employeeRole || '';
  const actions = getQuickActionsForUser(role, {surface:'max'});
  const openAction = (action) => {
    const params = new URLSearchParams();
    params.set('quickAction', action.id);
    params.set('from', 'max');
    if (action.appPage) params.set('page', action.appPage);
    window.location.href = '/app?' + params.toString();
  };
  const maxUserId = String(state.maxUser?.id || '');
  const maxChatId = String(state.maxChat?.id || maxUserId || '');
  const copyMaxLinkData = () => {
    const text = ['MAX userId: ' + (maxUserId || '-'), 'MAX chatId: ' + (maxChatId || '-')].join('\n');
    navigator.clipboard?.writeText(text).catch(() => {});
  };
  const openWebSessionMode = () => {
    window.location.href = '/max-app?webSession=1';
  };
  const sourceLabel = state.source === 'max'
    ? 'MAX · быстрые действия'
    : state.source === 'web'
      ? 'MAX · web-вход'
      : 'Локальный предпросмотр';

  return (
    <div style={{minHeight:'100dvh',background:'#0f172a',color:'#e5e7eb',padding:'16px',boxSizing:'border-box'}}>
      <main style={{width:'100%',maxWidth:'560px',margin:'0 auto'}}>
        <header style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:'10px',marginBottom:'14px'}}>
          <div>
            <h1 style={{margin:0,fontSize:'24px',lineHeight:1.1,fontWeight:800}}>Stroyka</h1>
            <p style={{margin:'5px 0 0',fontSize:'13px',color:'#94a3b8'}}>{sourceLabel}</p>
          </div>
          <button onClick={() => { window.location.href = '/app?from=max'; }} style={{border:'1px solid rgba(148,163,184,.35)',background:'rgba(15,23,42,.9)',color:'#e5e7eb',borderRadius:'10px',padding:'10px 12px',display:'flex',alignItems:'center',gap:'7px',fontWeight:700}}>
            <LogIn size={16}/>Войти
          </button>
        </header>

        <section style={{border:'1px solid rgba(148,163,184,.24)',background:'rgba(30,41,59,.72)',borderRadius:'8px',padding:'12px',marginBottom:'12px'}}>
          {state.loading ? (
            <b style={{fontSize:'14px'}}>Проверка доступа...</b>
          ) : state.account ? (
            <>
              <b style={{fontSize:'15px'}}>{state.account.employeeName || 'Сотрудник'}</b>
              <div style={{fontSize:'13px',color:'#cbd5e1',marginTop:'4px'}}>{roleLabel(role)}</div>
              {state.sessionNote && (
                <div style={{fontSize:'12px',color:state.requiresWebLogin ? '#fbbf24' : '#86efac',marginTop:'8px'}}>{state.sessionNote}</div>
              )}
            </>
          ) : (
            <>
              <b style={{fontSize:'15px'}}>Аккаунт не связан</b>
              <div style={{fontSize:'13px',color:'#fca5a5',marginTop:'4px'}}>{state.error}</div>
              {state.webSessionAvailable && (
                <button onClick={openWebSessionMode} style={{marginTop:'12px',border:'1px solid rgba(251,146,60,.45)',background:'#f97316',color:'#fff',borderRadius:'10px',padding:'10px 12px',fontWeight:800}}>
                  Открыть через web-вход
                </button>
              )}
              {(maxUserId || maxChatId) && (
                <div style={{marginTop:'12px',display:'grid',gap:'8px'}}>
                  <div style={{border:'1px solid rgba(148,163,184,.24)',borderRadius:'8px',padding:'10px',background:'rgba(15,23,42,.56)'}}>
                    <span style={{display:'block',fontSize:'11px',color:'#94a3b8',marginBottom:'4px'}}>MAX userId</span>
                    <code style={{display:'block',fontSize:'13px',color:'#e5e7eb',wordBreak:'break-all'}}>{maxUserId || '-'}</code>
                  </div>
                  <div style={{border:'1px solid rgba(148,163,184,.24)',borderRadius:'8px',padding:'10px',background:'rgba(15,23,42,.56)'}}>
                    <span style={{display:'block',fontSize:'11px',color:'#94a3b8',marginBottom:'4px'}}>MAX chatId</span>
                    <code style={{display:'block',fontSize:'13px',color:'#e5e7eb',wordBreak:'break-all'}}>{maxChatId || '-'}</code>
                  </div>
                  <button onClick={copyMaxLinkData} style={{border:'1px solid rgba(148,163,184,.35)',background:'rgba(15,23,42,.9)',color:'#e5e7eb',borderRadius:'10px',padding:'10px 12px',fontWeight:800}}>
                    Скопировать данные для привязки
                  </button>
                </div>
              )}
            </>
          )}
        </section>

        {state.account && (
          <section style={{display:'grid',gridTemplateColumns:'repeat(2,minmax(0,1fr))',gap:'10px'}}>
            {actions.map(action => {
              const Icon = iconByAction[action.id] || Plus;
              return (
                <button
                  key={action.id}
                  onClick={() => openAction(action)}
                  style={{
                    minHeight:'108px',
                    border:'1px solid rgba(148,163,184,.24)',
                    borderRadius:'8px',
                    background:'#1e293b',
                    color:'#f8fafc',
                    padding:'12px',
                    textAlign:'left',
                    display:'flex',
                    flexDirection:'column',
                    justifyContent:'space-between',
                    gap:'10px',
                  }}
                >
                  <span style={{width:'42px',height:'42px',borderRadius:'10px',display:'flex',alignItems:'center',justifyContent:'center',background:'rgba(255,255,255,.08)',color:action.color}}>
                    <Icon size={23}/>
                  </span>
                  <span style={{fontSize:'14px',fontWeight:800,lineHeight:1.2}}>{action.label}</span>
                </button>
              );
            })}
          </section>
        )}

        {!state.loading && state.account && actions.length === 0 && (
          <div style={{border:'1px solid rgba(148,163,184,.24)',borderRadius:'8px',padding:'14px',color:'#cbd5e1',fontSize:'13px'}}>
            Для этой роли быстрые действия пока не назначены.
          </div>
        )}
      </main>
    </div>
  );
}
