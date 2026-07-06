import React from 'react';
import { ArrowLeft, Bot, Camera, CheckCircle2, ClipboardList, CloudSun, CreditCard, ExternalLink, FileText, FolderKanban, LogIn, MessageSquare, Package, Plus, ReceiptText, RefreshCw, Send, Truck } from 'lucide-react';
import { API } from '../../api';
import { EXPENSE_CATEGORIES } from '../../constants/catalogs';
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

const COMPACT_ACTION_IDS = new Set([
  QUICK_ACTION_IDS.ASSIGNMENTS,
  QUICK_ACTION_IDS.OWN_EXPENSE,
  QUICK_ACTION_IDS.RECEIVE_WAREHOUSE,
]);

const CLOSED_TASK_STATUSES = new Set(['Закрыто', 'Отклонено', 'Отменено', 'Готово']);
const LEADERSHIP_ROLES = new Set(['директор', 'зам_директора', 'главный_инженер']);

const todayKey = () => new Date().toISOString().slice(0, 10);

const jsonFetch = async (path, options = {}) => {
  const res = await fetch(API + path, {
    ...options,
    headers: {
      ...(options.body && !(options.body instanceof FormData) ? {'Content-Type': 'application/json'} : {}),
      ...(options.headers || {}),
    },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || data.message || 'Запрос не выполнен');
  return data;
};

const uploadMaxFile = async (file, meta = {}) => {
  if (!file) return '';
  const fd = new FormData();
  fd.append('file', file);
  if (meta.projectName) fd.append('projectName', meta.projectName);
  fd.append('context', meta.context || 'max-app');
  const data = await jsonFetch('/upload-photo', {method:'POST', body:fd});
  return data.url || '';
};

const fileList = (value) => Array.from(value || []);

const compactButton = (variant = 'secondary') => ({
  border:'1px solid ' + (variant === 'primary' ? 'rgba(249,115,22,.55)' : 'rgba(148,163,184,.28)'),
  background: variant === 'primary' ? '#f97316' : 'rgba(15,23,42,.92)',
  color:'#f8fafc',
  borderRadius:'10px',
  padding:'10px 12px',
  display:'inline-flex',
  alignItems:'center',
  justifyContent:'center',
  gap:'7px',
  fontWeight:800,
  fontSize:'13px',
});

const compactField = {
  width:'100%',
  boxSizing:'border-box',
  border:'1px solid rgba(148,163,184,.28)',
  background:'#111827',
  color:'#e5e7eb',
  borderRadius:'10px',
  padding:'11px 12px',
  fontSize:'14px',
  outline:'none',
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

function CompactHeader({title, subtitle, onBack, onOpenFull}) {
  return (
    <div style={{display:'flex',alignItems:'flex-start',justifyContent:'space-between',gap:'10px',marginBottom:'12px'}}>
      <button onClick={onBack} style={{...compactButton(),padding:'9px 10px'}}><ArrowLeft size={16}/>Назад</button>
      <div style={{flex:1,minWidth:0}}>
        <b style={{display:'block',fontSize:'18px',lineHeight:1.15,color:'#f8fafc'}}>{title}</b>
        {subtitle && <span style={{display:'block',marginTop:'4px',fontSize:'12px',color:'#94a3b8'}}>{subtitle}</span>}
      </div>
      <button onClick={onOpenFull} style={{...compactButton(),padding:'9px 10px'}}><ExternalLink size={15}/></button>
    </div>
  );
}

function CompactNotice({children, tone = 'info'}) {
  const color = tone === 'error' ? '#fca5a5' : tone === 'success' ? '#86efac' : '#cbd5e1';
  const border = tone === 'error' ? 'rgba(248,113,113,.35)' : tone === 'success' ? 'rgba(34,197,94,.35)' : 'rgba(148,163,184,.24)';
  return <div style={{border:'1px solid ' + border,background:'rgba(15,23,42,.62)',borderRadius:'10px',padding:'11px 12px',fontSize:'13px',lineHeight:1.45,color}}>{children}</div>;
}

function MaxAssignmentsCompact({account, onBack, onOpenFull}) {
  const [tasks, setTasks] = React.useState([]);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState('');
  const [busyId, setBusyId] = React.useState(null);
  const [reportById, setReportById] = React.useState({});
  const [attachmentsById, setAttachmentsById] = React.useState({});
  const [uploadingId, setUploadingId] = React.useState(null);

  const role = account?.employeeRole || '';
  const assignedOnly = !LEADERSHIP_ROLES.has(role);

  const loadTasks = React.useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const query = assignedOnly ? '?assigned_only=true' : '';
      const data = await jsonFetch('/assignments' + query);
      const rows = Array.isArray(data) ? data : [];
      const sorted = rows
        .slice()
        .sort((a, b) => Number(CLOSED_TASK_STATUSES.has(a.status || '')) - Number(CLOSED_TASK_STATUSES.has(b.status || '')));
      setTasks(sorted.slice(0, 40));
    } catch (err) {
      setError(err.message || 'Не удалось загрузить поручения');
    } finally {
      setLoading(false);
    }
  }, [assignedOnly]);

  React.useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  const updateTask = (nextTask) => {
    if (!nextTask?.id) return;
    setTasks(prev => prev.map(task => Number(task.id) === Number(nextTask.id) ? nextTask : task));
  };

  const acceptTask = async (task) => {
    setBusyId(task.id);
    try {
      const data = await jsonFetch('/ai-tasks/' + task.id + '/accept', {
        method:'POST',
        body:JSON.stringify({status:'В работе'}),
      });
      updateTask(data);
    } catch (err) {
      setError(err.message || 'Не удалось взять в работу');
    } finally {
      setBusyId(null);
    }
  };

  const uploadReportFiles = async (task, files) => {
    const items = fileList(files);
    if (!items.length) return;
    setUploadingId(task.id);
    setError('');
    try {
      const uploaded = [];
      for (const file of items) {
        const url = await uploadMaxFile(file, {projectName: task.projectName, context:'ai-task-reports'});
        if (url) uploaded.push({url, type:file.type && file.type.startsWith('image/') ? 'photo' : 'file', name:file.name, source:'max-app'});
      }
      if (uploaded.length) {
        setAttachmentsById(prev => ({...prev, [task.id]: [...(prev[task.id] || []), ...uploaded]}));
      }
    } catch (err) {
      setError(err.message || 'Не удалось загрузить файл');
    } finally {
      setUploadingId(null);
    }
  };

  const sendReport = async (task) => {
    const text = (reportById[task.id] || '').trim();
    const attachments = attachmentsById[task.id] || [];
    if (!text && attachments.length === 0) return;
    setBusyId(task.id);
    setError('');
    try {
      const data = await jsonFetch('/ai-tasks/' + task.id + '/reports', {
        method:'POST',
        body:JSON.stringify({text, attachments, nextStatus:'На проверке'}),
      });
      if (data.task) updateTask(data.task);
      setReportById(prev => ({...prev, [task.id]: ''}));
      setAttachmentsById(prev => ({...prev, [task.id]: []}));
    } catch (err) {
      setError(err.message || 'Не удалось отправить отчет');
    } finally {
      setBusyId(null);
    }
  };

  const visibleTasks = tasks.filter(task => !CLOSED_TASK_STATUSES.has(task.status || '')).slice(0, 20);

  return (
    <section>
      <CompactHeader title="Поручения" subtitle={assignedOnly ? 'Мои и по роли' : 'Открытые поручения'} onBack={onBack} onOpenFull={onOpenFull} />
      <div style={{display:'flex',gap:'8px',marginBottom:'10px'}}>
        <button onClick={loadTasks} disabled={loading} style={compactButton()}><RefreshCw size={14}/>{loading ? 'Обновление' : 'Обновить'}</button>
      </div>
      {error && <div style={{marginBottom:'10px'}}><CompactNotice tone="error">{error}</CompactNotice></div>}
      {loading && <CompactNotice>Загружаю поручения...</CompactNotice>}
      {!loading && visibleTasks.length === 0 && <CompactNotice>Открытых поручений для этого режима нет.</CompactNotice>}
      <div style={{display:'grid',gap:'10px'}}>
        {visibleTasks.map(task => {
          const due = String(task.dueDate || '').slice(0, 10);
          const overdue = due && due < todayKey();
          const attachments = attachmentsById[task.id] || [];
          const reportText = reportById[task.id] || '';
          const latestReport = task.latestReport || (Array.isArray(task.reports) ? task.reports[0] : null);
          return (
            <article key={task.id} style={{border:'1px solid rgba(148,163,184,.24)',borderRadius:'10px',padding:'12px',background:'#1e293b'}}>
              <div style={{display:'flex',justifyContent:'space-between',gap:'8px',alignItems:'flex-start'}}>
                <div style={{minWidth:0}}>
                  <span style={{fontSize:'11px',color:overdue ? '#fca5a5' : '#94a3b8'}}>{task.projectName || 'Без объекта'}{due ? ' · до ' + due : ''}</span>
                  <b style={{display:'block',marginTop:'5px',fontSize:'15px',lineHeight:1.25,color:'#f8fafc'}}>{task.title || 'Поручение'}</b>
                </div>
                <span style={{flexShrink:0,border:'1px solid rgba(148,163,184,.25)',borderRadius:'999px',padding:'4px 8px',fontSize:'11px',color:'#cbd5e1'}}>{task.status || 'Новое'}</span>
              </div>
              {task.description && <p style={{margin:'9px 0 0',fontSize:'13px',lineHeight:1.45,color:'#cbd5e1',whiteSpace:'pre-wrap'}}>{task.description}</p>}
              {latestReport?.text && (
                <div style={{marginTop:'10px',borderTop:'1px solid rgba(148,163,184,.18)',paddingTop:'9px',fontSize:'12px',color:'#94a3b8'}}>
                  <FileText size={12} style={{verticalAlign:'-2px'}}/> Последний отчет: {latestReport.text}
                </div>
              )}
              <div style={{display:'grid',gap:'8px',marginTop:'11px'}}>
                {task.status !== 'В работе' && task.status !== 'На проверке' && (
                  <button onClick={() => acceptTask(task)} disabled={busyId === task.id} style={compactButton('primary')}><CheckCircle2 size={15}/>В работу</button>
                )}
                <textarea
                  value={reportText}
                  onChange={event => setReportById(prev => ({...prev, [task.id]: event.target.value}))}
                  placeholder="Краткий отчет"
                  style={{...compactField,minHeight:'74px',resize:'vertical'}}
                />
                {attachments.length > 0 && <span style={{fontSize:'12px',color:'#86efac'}}>Вложений: {attachments.length}</span>}
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px'}}>
                  <label style={{...compactButton(),cursor:'pointer'}}>
                    <Camera size={14}/>{uploadingId === task.id ? 'Загрузка' : 'Фото'}
                    <input type="file" accept="image/*,.pdf" multiple capture="environment" onChange={event => { uploadReportFiles(task, event.target.files); event.target.value = ''; }} style={{display:'none'}} />
                  </label>
                  <button onClick={() => sendReport(task)} disabled={busyId === task.id || (!reportText.trim() && attachments.length === 0)} style={{...compactButton('primary'),opacity:busyId === task.id || (!reportText.trim() && attachments.length === 0) ? .62 : 1}}><Send size={14}/>Отчет</button>
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function MaxOwnExpenseCompact({account, onBack, onOpenFull}) {
  const [projects, setProjects] = React.useState([]);
  const [recent, setRecent] = React.useState([]);
  const [form, setForm] = React.useState({projectName:'',category:'other',description:'',amount:'',date:'',photoUrl:''});
  const [loading, setLoading] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [uploading, setUploading] = React.useState(false);
  const [message, setMessage] = React.useState('');
  const [error, setError] = React.useState('');

  const loadData = React.useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [projectRows, expenseRows] = await Promise.all([
        jsonFetch('/projects'),
        jsonFetch('/own-expenses'),
      ]);
      setProjects(Array.isArray(projectRows) ? projectRows.filter(project => !project.archived) : []);
      setRecent(Array.isArray(expenseRows) ? expenseRows.slice(0, 5) : []);
    } catch (err) {
      setError(err.message || 'Не удалось загрузить данные');
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadData();
  }, [loadData]);

  const updateForm = patch => setForm(prev => ({...prev, ...patch}));

  const uploadReceipts = async files => {
    const items = fileList(files);
    if (!items.length) return;
    setUploading(true);
    setError('');
    try {
      const urls = [];
      for (const file of items) {
        const url = await uploadMaxFile(file, {projectName: form.projectName, context:'own-expenses'});
        if (url) urls.push(url);
      }
      if (urls.length) updateForm({photoUrl: [form.photoUrl, ...urls].filter(Boolean).join(',')});
    } catch (err) {
      setError(err.message || 'Не удалось загрузить чек');
    } finally {
      setUploading(false);
    }
  };

  const submit = async () => {
    setMessage('');
    setError('');
    if (!form.description.trim() || !Number(form.amount)) {
      setError('Укажите описание и сумму');
      return;
    }
    setSaving(true);
    try {
      await jsonFetch('/own-expenses', {
        method:'POST',
        body:JSON.stringify({...form, amount:Number(form.amount)}),
      });
      setForm({projectName:'',category:'other',description:'',amount:'',date:'',photoUrl:''});
      setMessage('Трата отправлена на возмещение');
      await loadData();
    } catch (err) {
      setError(err.message || 'Не удалось отправить трату');
    } finally {
      setSaving(false);
    }
  };

  const photoCount = form.photoUrl ? form.photoUrl.split(',').filter(Boolean).length : 0;

  return (
    <section>
      <CompactHeader title="Мои траты" subtitle={account?.employeeName || 'Возмещение сотруднику'} onBack={onBack} onOpenFull={onOpenFull} />
      {error && <div style={{marginBottom:'10px'}}><CompactNotice tone="error">{error}</CompactNotice></div>}
      {message && <div style={{marginBottom:'10px'}}><CompactNotice tone="success">{message}</CompactNotice></div>}
      <div style={{display:'grid',gap:'9px',border:'1px solid rgba(148,163,184,.24)',borderRadius:'10px',padding:'12px',background:'#1e293b'}}>
        <select value={form.projectName} onChange={event => updateForm({projectName:event.target.value})} style={compactField}>
          <option value="">Без объекта / личная трата</option>
          {projects.map(project => <option key={project.id || project.name} value={project.name}>{project.name}</option>)}
        </select>
        <select value={form.category} onChange={event => updateForm({category:event.target.value})} style={compactField}>
          {EXPENSE_CATEGORIES.map(category => <option key={category.id} value={category.id}>{category.label}</option>)}
        </select>
        <input value={form.description} onChange={event => updateForm({description:event.target.value})} placeholder="За что потрачено" style={compactField}/>
        <input value={form.amount} onChange={event => updateForm({amount:event.target.value})} placeholder="Сумма, ₽" type="number" inputMode="decimal" step="any" style={compactField}/>
        <input value={form.date} onChange={event => updateForm({date:event.target.value})} type="date" style={compactField}/>
        {photoCount > 0 && <span style={{fontSize:'12px',color:'#86efac'}}>Чеков прикреплено: {photoCount}</span>}
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px'}}>
          <label style={{...compactButton(),cursor:'pointer'}}>
            <Camera size={14}/>{uploading ? 'Загрузка' : 'Чек'}
            <input type="file" accept="image/*" multiple capture="environment" onChange={event => { uploadReceipts(event.target.files); event.target.value = ''; }} style={{display:'none'}} />
          </label>
          <button onClick={submit} disabled={saving} style={{...compactButton('primary'),opacity:saving ? .7 : 1}}><Send size={14}/>{saving ? 'Отправка' : 'Отправить'}</button>
        </div>
      </div>
      <div style={{marginTop:'12px'}}>
        <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:'8px',marginBottom:'8px'}}>
          <b style={{fontSize:'14px',color:'#e5e7eb'}}>Последние</b>
          <button onClick={loadData} disabled={loading} style={{...compactButton(),padding:'7px 9px'}}><RefreshCw size={13}/></button>
        </div>
        {recent.length === 0 ? <CompactNotice>{loading ? 'Загружаю...' : 'Трат пока нет.'}</CompactNotice> : (
          <div style={{display:'grid',gap:'8px'}}>
            {recent.map(item => (
              <div key={item.id} style={{border:'1px solid rgba(148,163,184,.2)',borderRadius:'9px',padding:'10px',background:'rgba(30,41,59,.72)'}}>
                <b style={{fontSize:'13px',color:'#f8fafc'}}>{Number(item.amount || 0).toLocaleString('ru-RU')} ₽ · {item.status || 'Ожидает'}</b>
                <div style={{marginTop:'4px',fontSize:'12px',color:'#94a3b8'}}>{item.description || 'Без описания'}{item.projectName ? ' · ' + item.projectName : ''}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function MaxWarehouseCompact({onBack, onOpenFull}) {
  const openReceive = () => {
    window.location.href = '/app?quickAction=receive_warehouse&from=max&page=warehouse';
  };
  const openWarehouse = () => {
    window.location.href = '/app?from=max&page=warehouse';
  };
  return (
    <section>
      <CompactHeader title="Приемка на склад" subtitle="OCR и подтверждение идут через текущую складскую цепочку" onBack={onBack} onOpenFull={onOpenFull} />
      <div style={{display:'grid',gap:'10px'}}>
        <CompactNotice>
          Накладная должна пройти существующий путь: фото или файл -> распознавание -> проверка позиций -> подтверждение -> склад объекта и бухгалтерская первичка.
        </CompactNotice>
        <button onClick={openReceive} style={{...compactButton('primary'),minHeight:'50px'}}><Camera size={16}/>Сфотографировать накладную</button>
        <button onClick={openWarehouse} style={{...compactButton(),minHeight:'50px'}}><Package size={16}/>Открыть склад</button>
      </div>
    </section>
  );
}

export default function MaxQuickActionsPage() {
  const [activeActionId, setActiveActionId] = React.useState('');
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
  const activeAction = actions.find(action => action.id === activeActionId) || null;
  const compactActionsAvailable = state.sessionCreated || state.source === 'web' || state.source === 'local';
  const openFullAction = (action) => {
    const params = new URLSearchParams();
    params.set('from', 'max');
    if (action?.id) params.set('quickAction', action.id);
    if (action?.appPage) params.set('page', action.appPage);
    window.location.href = '/app?' + params.toString();
  };
  const openAction = (action) => {
    if (COMPACT_ACTION_IDS.has(action.id) && compactActionsAvailable) {
      setActiveActionId(action.id);
      return;
    }
    openFullAction(action);
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

        {state.account && activeAction && (
          <>
            {activeAction.id === QUICK_ACTION_IDS.ASSIGNMENTS && (
              <MaxAssignmentsCompact
                account={state.account}
                onBack={() => setActiveActionId('')}
                onOpenFull={() => openFullAction(activeAction)}
              />
            )}
            {activeAction.id === QUICK_ACTION_IDS.OWN_EXPENSE && (
              <MaxOwnExpenseCompact
                account={state.account}
                onBack={() => setActiveActionId('')}
                onOpenFull={() => openFullAction(activeAction)}
              />
            )}
            {activeAction.id === QUICK_ACTION_IDS.RECEIVE_WAREHOUSE && (
              <MaxWarehouseCompact
                onBack={() => setActiveActionId('')}
                onOpenFull={() => openFullAction(activeAction)}
              />
            )}
          </>
        )}

        {state.account && !activeAction && (
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
