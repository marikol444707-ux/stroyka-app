import React from 'react';
import {
  Calendar,
  CheckCircle2,
  ClipboardList,
  ExternalLink,
  FileText,
  Filter,
  Paperclip,
  Plus,
  RefreshCw,
  Search,
  Send,
  UserCheck,
  XCircle,
} from 'lucide-react';
import { isOpenAiStatus } from '../utils/statusMetaUtils';

const CLOSED_STATUSES = ['Закрыто', 'Отклонено', 'Отменено'];
const REVIEW_STATUS = 'На проверке';
const DEFAULT_ROLE_OPTIONS = [
  'прораб',
  'главный_инженер',
  'сметчик',
  'снабженец',
  'кладовщик',
  'бухгалтер',
  'стройконтроль',
  'технадзор',
  'мастер',
  'бригадир',
  'субподрядчик',
];
const EXTRA_ROLE_OPTIONS = [
  'директор',
  'зам_директора',
  'менеджер_crm',
  'заказчик',
  'поставщик',
  'system_owner',
  'platform_support',
];
const ROLE_OPTIONS = Array.from(new Set([...DEFAULT_ROLE_OPTIONS, ...EXTRA_ROLE_OPTIONS]));
const ROLE_ORDER = new Map(ROLE_OPTIONS.map((role, index) => [role, index]));
let assignmentDraftSeq = 0;

const clean = value => String(value || '').trim();
const lower = value => clean(value).toLowerCase();
const todayKey = () => new Date().toISOString().slice(0, 10);
const roleOrder = role => ROLE_ORDER.has(role) ? ROLE_ORDER.get(role) : ROLE_OPTIONS.length + 1;
const userDisplayName = item => clean(item?.name) || clean(item?.email);
const createDraftRow = () => ({
  id: 'assignment-draft-' + Date.now() + '-' + (assignmentDraftSeq += 1),
  title: '',
  description: '',
  assignedRole: '',
  assignedTo: '',
  dueDate: '',
});

const roleLabel = role => ({
  директор: 'Директор',
  зам_директора: 'Зам. директора',
  главный_инженер: 'Гл. инженер',
  прораб: 'Прораб',
  кладовщик: 'Кладовщик',
  бухгалтер: 'Бухгалтер',
  снабженец: 'Снабженец',
  стройконтроль: 'Стройконтроль',
  сметчик: 'Сметчик',
  мастер: 'Мастер',
  бригадир: 'Бригадир',
  субподрядчик: 'Субподрядчик',
  технадзор: 'Технадзор',
  менеджер_crm: 'Менеджер CRM',
  заказчик: 'Заказчик',
  поставщик: 'Поставщик',
  system_owner: 'Владелец платформы',
  platform_support: 'Поддержка платформы',
}[role] || role || 'Роль');

const statusMeta = (C, status) => {
  if (status === 'Закрыто' || status === 'Готово') return { color: C.success, bg: C.successLight, border: C.successBorder };
  if (status === 'Отклонено' || status === 'Отменено') return { color: C.danger, bg: C.dangerLight, border: C.dangerBorder };
  if (status === REVIEW_STATUS) return { color: C.warning, bg: C.warningLight, border: C.warningBorder };
  if (status === 'В работе' || status === 'Принято к исполнению') return { color: C.info, bg: C.infoLight, border: C.infoBorder };
  return { color: C.accent, bg: C.accentLight, border: C.accentBorder || C.border };
};

const chipStyle = (C, status) => {
  const meta = statusMeta(C, status);
  return {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '5px',
    padding: '4px 8px',
    borderRadius: '999px',
    color: meta.color,
    backgroundColor: meta.bg,
    border: '1px solid ' + meta.border,
    fontSize: '11px',
    fontWeight: 700,
    whiteSpace: 'nowrap',
  };
};

const latestReportOf = task => {
  if (task?.latestReport) return task.latestReport;
  if (task?.latestReportText) {
    return {
      text: task.latestReportText,
      authorName: task.latestReportAuthor,
      createdAt: task.latestReportAt,
    };
  }
  const reports = Array.isArray(task?.reports) ? task.reports : [];
  return reports[0] || null;
};

const isClosedTask = task => CLOSED_STATUSES.includes(task?.status || '');
const isOpenTask = task => isOpenAiStatus(task?.status) && !isClosedTask(task);

const isTaskAssignedToUser = (task, user) => {
  if (!task || !user) return false;
  const assignedRole = lower(task.assignedRole);
  const assignedTo = lower(task.assignedTo);
  const identityMatch = [user.name, user.email, user.id].some(value => lower(value) && assignedTo === lower(value));
  if (assignedTo) return identityMatch;
  return assignedRole && assignedRole === lower(user.role);
};

const isTaskOverdue = task => {
  const due = clean(task?.dueDate).slice(0, 10);
  return due && due < todayKey() && isOpenTask(task);
};

function TaskReportForm({ C, btnG, btnO, inp, isMobile, submitAiTaskReport, task, uploadPhoto }) {
  const fileInputRef = React.useRef(null);
  const [text, setText] = React.useState('');
  const [attachments, setAttachments] = React.useState([]);
  const [sending, setSending] = React.useState(false);
  const [uploading, setUploading] = React.useState(false);

  const handleFile = async event => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file || typeof uploadPhoto !== 'function') return;
    setUploading(true);
    try {
      const url = await uploadPhoto(file, { projectName: task.projectName, context: 'ai-task-reports' });
      if (url) {
        setAttachments(prev => [...prev, {
          url,
          type: file.type && file.type.startsWith('image/') ? 'photo' : 'file',
          name: file.name,
          source: 'assignments-page',
        }]);
      }
    } finally {
      setUploading(false);
    }
  };

  const sendReport = async () => {
    if (!clean(text) && attachments.length === 0) return;
    if (typeof submitAiTaskReport !== 'function') return;
    setSending(true);
    try {
      const result = await submitAiTaskReport(task.id, {
        text,
        attachments,
        nextStatus: REVIEW_STATUS,
      });
      if (result) {
        setText('');
        setAttachments([]);
      }
    } finally {
      setSending(false);
    }
  };

  return (
    <div style={{ borderTop: '1px solid ' + C.border, marginTop: '12px', paddingTop: '12px' }}>
      <textarea
        value={text}
        onChange={e => setText(e.target.value)}
        placeholder="Краткий отчет по поручению"
        style={{ ...inp, minHeight: '68px', resize: 'vertical', width: '100%', boxSizing: 'border-box' }}
      />
      {attachments.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '8px' }}>
          {attachments.map((item, idx) => (
            <span key={item.url + idx} style={{ ...chipStyle(C, 'В работе'), maxWidth: '100%' }}>
              <Paperclip size={12} />
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.name || item.url}</span>
            </span>
          ))}
        </div>
      )}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '10px' }}>
        <input ref={fileInputRef} type="file" accept="image/*,.pdf" onChange={handleFile} style={{ display: 'none' }} />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          style={{ ...btnG, minHeight: isMobile ? '40px' : undefined }}
        >
          <Paperclip size={14} />{uploading ? 'Загрузка' : 'Фото/файл'}
        </button>
        <button
          onClick={sendReport}
          disabled={sending || (!clean(text) && attachments.length === 0)}
          style={{ ...btnO, minHeight: isMobile ? '40px' : undefined, opacity: sending || (!clean(text) && attachments.length === 0) ? 0.65 : 1 }}
        >
          <Send size={14} />{sending ? 'Отправка' : 'Отправить отчет'}
        </button>
      </div>
    </div>
  );
}

function AssignmentCard({
  C,
  btnB,
  btnG,
  btnO,
  btnR,
  card,
  inp,
  isMobile,
  acceptAiTask,
  closeAiTask,
  openAiTaskAction,
  submitAiTaskReport,
  task,
  uploadPhoto,
  user,
}) {
  const [closing, setClosing] = React.useState(false);
  const [closeText, setCloseText] = React.useState('');
  const latestReport = latestReportOf(task);
  const closed = isClosedTask(task);
  const canClose = ['директор', 'зам_директора', 'главный_инженер', 'прораб', 'стройконтроль', 'технадзор'].includes(user?.role || '');
  const overdue = isTaskOverdue(task);
  const assigned = [task.assignedRole && roleLabel(task.assignedRole), task.assignedTo].filter(Boolean).join(' / ');

  const runAccept = async () => {
    if (typeof acceptAiTask === 'function') await acceptAiTask(task.id, 'В работе');
  };

  const runClose = async status => {
    if (typeof closeAiTask !== 'function') return;
    setClosing(true);
    try {
      const result = await closeAiTask(task.id, { status, text: closeText });
      if (result) setCloseText('');
    } finally {
      setClosing(false);
    }
  };

  return (
    <div style={{ ...card, padding: isMobile ? '14px' : '16px', marginBottom: '12px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', flexWrap: 'wrap' }}>
        <div style={{ minWidth: 0, flex: '1 1 280px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginBottom: '7px' }}>
            <span style={chipStyle(C, task.status || 'Новое')}>{task.status || 'Новое'}</span>
            {overdue && <span style={chipStyle(C, 'Отклонено')}>Просрочено</span>}
            {(task.reportsCount || latestReport) && <span style={chipStyle(C, REVIEW_STATUS)}>{task.reportsCount || 1} отчет</span>}
          </div>
          <h3 style={{ margin: 0, color: C.text, fontSize: isMobile ? '16px' : '18px', lineHeight: 1.25, overflowWrap: 'anywhere' }}>
            {task.title || 'Поручение'}
          </h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginTop: '8px', color: C.textSec, fontSize: '12px' }}>
            {task.projectName && <span><ClipboardList size={12} style={{ verticalAlign: '-2px' }} /> {task.projectName}</span>}
            {assigned && <span><UserCheck size={12} style={{ verticalAlign: '-2px' }} /> {assigned}</span>}
            {task.dueDate && <span><Calendar size={12} style={{ verticalAlign: '-2px' }} /> до {String(task.dueDate).slice(0, 10)}</span>}
          </div>
        </div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: isMobile ? 'flex-start' : 'flex-end' }}>
          {typeof openAiTaskAction === 'function' && (
            <button onClick={() => openAiTaskAction(task)} style={{ ...btnG, padding: '8px 10px' }}>
              <ExternalLink size={14} />Открыть
            </button>
          )}
          {!closed && task.status !== 'В работе' && task.status !== REVIEW_STATUS && (
            <button onClick={runAccept} style={{ ...btnB, padding: '8px 10px' }}>
              <CheckCircle2 size={14} />В работу
            </button>
          )}
        </div>
      </div>

      {task.description && (
        <p style={{ margin: '12px 0 0', color: C.text, fontSize: '13px', lineHeight: 1.55, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
          {task.description}
        </p>
      )}

      {latestReport && (
        <div style={{ marginTop: '12px', padding: '10px 12px', borderRadius: '8px', backgroundColor: C.bg, border: '1px solid ' + C.border }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: C.textSec, fontSize: '11px', marginBottom: '4px' }}>
            <FileText size={12} />Последний отчет{latestReport.authorName ? ': ' + latestReport.authorName : ''}
          </div>
          <div style={{ color: C.text, fontSize: '13px', lineHeight: 1.45, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
            {latestReport.text || 'Отчет без текста'}
          </div>
        </div>
      )}

      {!closed && (
        <TaskReportForm
          C={C}
          btnG={btnG}
          btnO={btnO}
          inp={inp}
          isMobile={isMobile}
          submitAiTaskReport={submitAiTaskReport}
          task={task}
          uploadPhoto={uploadPhoto}
        />
      )}

      {!closed && canClose && (
        <div style={{ borderTop: '1px solid ' + C.border, marginTop: '12px', paddingTop: '12px' }}>
          <input
            value={closeText}
            onChange={e => setCloseText(e.target.value)}
            placeholder="Комментарий при закрытии"
            style={{ ...inp, width: '100%', boxSizing: 'border-box', marginBottom: '8px' }}
          />
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            <button onClick={() => runClose('Закрыто')} disabled={closing} style={{ ...btnO, padding: '8px 10px' }}>
              <CheckCircle2 size={14} />Закрыть
            </button>
            <button onClick={() => runClose('Отклонено')} disabled={closing} style={{ ...btnR, padding: '8px 10px' }}>
              <XCircle size={14} />Отклонить отчет
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function AssignmentsPage({
  C,
  aiTasks = [],
  acceptAiTask,
  btnB,
  btnG,
  btnO,
  btnR,
  card,
  createAiTask,
  inp,
  isMobile,
  openAiTaskAction,
  projects = [],
  refreshData,
  submitAiTaskReport,
  uploadPhoto,
  user,
  users = [],
  closeAiTask,
}) {
  const projectOptions = React.useMemo(
    () => (projects || []).filter(project => !project.archived && project.status !== 'Завершён'),
    [projects],
  );
  const [filters, setFilters] = React.useState({ scope: 'open', project: '', status: '', role: '', search: '' });
  const [showCreate, setShowCreate] = React.useState(false);
  const [showSystemTasks, setShowSystemTasks] = React.useState(false);
  const [creating, setCreating] = React.useState(false);
  const [draft, setDraft] = React.useState(() => ({
    projectName: '',
    rows: [createDraftRow()],
  }));
  const canCreate = ['директор', 'зам_директора', 'главный_инженер', 'прораб', 'сметчик', 'снабженец', 'кладовщик', 'бухгалтер'].includes(user?.role || '');
  const canInspectSystemTasks = ['директор', 'зам_директора'].includes(user?.role || '');

  const systemTasksCount = React.useMemo(
    () => (aiTasks || []).filter(task => task.systemGenerated).length,
    [aiTasks],
  );

  const assignmentTasks = React.useMemo(
    () => (aiTasks || []).filter(task => showSystemTasks || !task.systemGenerated),
    [aiTasks, showSystemTasks],
  );

  React.useEffect(() => {
    if (draft.projectName || projectOptions.length === 0) return;
    setDraft(prev => ({ ...prev, projectName: projectOptions[0].name || '' }));
  }, [draft.projectName, projectOptions]);

  const uniqueProjects = React.useMemo(() => {
    const names = new Set();
    projectOptions.forEach(project => project.name && names.add(project.name));
    assignmentTasks.forEach(task => task.projectName && names.add(task.projectName));
    return Array.from(names).sort((a, b) => a.localeCompare(b, 'ru'));
  }, [assignmentTasks, projectOptions]);

  const statusOptions = React.useMemo(() => Array.from(new Set(assignmentTasks.map(task => task.status || 'Новое'))), [assignmentTasks]);
  const roleOptions = React.useMemo(() => {
    const roles = new Set(ROLE_OPTIONS);
    (users || []).forEach(item => item.role && roles.add(item.role));
    assignmentTasks.forEach(task => task.assignedRole && roles.add(task.assignedRole));
    return Array.from(roles).sort((a, b) => (
      roleOrder(a) - roleOrder(b) || roleLabel(a).localeCompare(roleLabel(b), 'ru')
    ));
  }, [assignmentTasks, users]);

  const stats = React.useMemo(() => {
    const rows = Array.isArray(assignmentTasks) ? assignmentTasks : [];
    return {
      all: rows.length,
      open: rows.filter(isOpenTask).length,
      mine: rows.filter(task => isTaskAssignedToUser(task, user) && isOpenTask(task)).length,
      review: rows.filter(task => task.status === REVIEW_STATUS).length,
      overdue: rows.filter(isTaskOverdue).length,
    };
  }, [assignmentTasks, user]);

  const filteredTasks = React.useMemo(() => {
    const term = lower(filters.search);
    return assignmentTasks
      .filter(task => {
        if (filters.project && task.projectName !== filters.project) return false;
        if (filters.status && (task.status || 'Новое') !== filters.status) return false;
        if (filters.role && task.assignedRole !== filters.role) return false;
        if (filters.scope === 'open' && !isOpenTask(task)) return false;
        if (filters.scope === 'mine' && !isTaskAssignedToUser(task, user)) return false;
        if (filters.scope === 'review' && task.status !== REVIEW_STATUS) return false;
        if (filters.scope === 'overdue' && !isTaskOverdue(task)) return false;
        if (filters.scope === 'closed' && !isClosedTask(task)) return false;
        if (term) {
          const haystack = lower([task.title, task.description, task.projectName, task.assignedRole, task.assignedTo, latestReportOf(task)?.text].join(' '));
          if (!haystack.includes(term)) return false;
        }
        return true;
      })
      .sort((a, b) => {
        const aReview = a.status === REVIEW_STATUS ? 1 : 0;
        const bReview = b.status === REVIEW_STATUS ? 1 : 0;
        if (aReview !== bReview) return bReview - aReview;
        const aOverdue = isTaskOverdue(a) ? 1 : 0;
        const bOverdue = isTaskOverdue(b) ? 1 : 0;
        if (aOverdue !== bOverdue) return bOverdue - aOverdue;
        return String(b.updatedAt || b.createdAt || '').localeCompare(String(a.updatedAt || a.createdAt || ''));
      });
  }, [assignmentTasks, filters, user]);

  const sortedAssignees = React.useMemo(() => {
    return (users || [])
      .filter(item => userDisplayName(item))
      .sort((a, b) => (
        roleOrder(a.role) - roleOrder(b.role)
        || roleLabel(a.role).localeCompare(roleLabel(b.role), 'ru')
        || userDisplayName(a).localeCompare(userDisplayName(b), 'ru')
      ));
  }, [users]);

  const assigneeGroupsForRole = React.useCallback((role = '') => {
    const groups = new Map();
    sortedAssignees
      .filter(item => !role || item.role === role)
      .forEach(item => {
        const key = item.role || 'no_role';
        if (!groups.has(key)) groups.set(key, { role: key, label: roleLabel(item.role || 'Без роли'), items: [] });
        groups.get(key).items.push(item);
      });
    return Array.from(groups.values()).sort((a, b) => (
      roleOrder(a.role) - roleOrder(b.role) || a.label.localeCompare(b.label, 'ru')
    ));
  }, [sortedAssignees]);

  const validDraftRows = React.useMemo(
    () => (draft.rows || []).filter(row => clean(row.title)),
    [draft.rows],
  );

  const updateDraftRow = (rowId, patch) => {
    setDraft(prev => ({
      ...prev,
      rows: (prev.rows || []).map(row => row.id === rowId ? { ...row, ...patch } : row),
    }));
  };

  const addDraftRow = () => {
    setDraft(prev => ({ ...prev, rows: [...(prev.rows || []), createDraftRow()] }));
  };

  const removeDraftRow = rowId => {
    setDraft(prev => {
      const rows = (prev.rows || []).filter(row => row.id !== rowId);
      return { ...prev, rows: rows.length ? rows : [createDraftRow()] };
    });
  };

  const createTask = async () => {
    const projectName = clean(draft.projectName);
    const rows = (draft.rows || []).filter(row => clean(row.title));
    if (!projectName || rows.length === 0 || typeof createAiTask !== 'function' || creating) return;
    setCreating(true);
    try {
      for (const row of rows) {
        const payload = {
          projectName,
          title: clean(row.title),
          description: row.description,
          assignedRole: row.assignedRole,
          assignedTo: row.assignedTo,
          dueDate: row.dueDate,
          actionLabel: 'Открыть объект',
          actionPayload: JSON.stringify({
            type: 'manual_assignment',
            source: 'assignments_page',
            projectName,
          }),
        };
        const result = await createAiTask(payload);
        if (!result) return;
      }
      setDraft({ projectName: draft.projectName, rows: [createDraftRow()] });
      setShowCreate(false);
    } finally {
      setCreating(false);
    }
  };

  const draftRows = draft.rows || [];
  const canSubmitDraft = clean(draft.projectName) && validDraftRows.length > 0 && !creating;

  const statButton = (id, label, value) => {
    const active = filters.scope === id;
    return (
    <button
      onClick={() => setFilters(prev => ({ ...prev, scope: id }))}
      style={{
        border: '1.5px solid ' + (active ? (C.accentBorder || C.accent) : C.border),
        backgroundColor: active ? C.accentLight : C.bgWhite,
        color: active ? C.accent : C.text,
        borderRadius: '8px',
        padding: isMobile ? '12px 14px' : '10px 12px',
        minHeight: isMobile ? '72px' : '64px',
        minWidth: 0,
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-start',
        gap: '3px',
        cursor: 'pointer',
      }}
    >
      <span style={{ fontSize: '18px', fontWeight: 800 }}>{value}</span>
      <span style={{ fontSize: '11px', fontWeight: 700, color: active ? C.accent : C.textSec }}>{label}</span>
    </button>
    );
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', flexWrap: 'wrap', flexDirection: isMobile ? 'column' : 'row', marginBottom: '18px' }}>
        <div>
          <h2 style={{ margin: 0, color: C.text, fontSize: isMobile ? '22px' : '26px', fontWeight: 800 }}>Поручения</h2>
        </div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', width: isMobile ? '100%' : 'auto' }}>
          <button onClick={() => typeof refreshData === 'function' && refreshData('assignments')} style={btnG}>
            <RefreshCw size={14} />Обновить
          </button>
          {canCreate && (
            <button onClick={() => setShowCreate(value => !value)} style={btnO}>
              <Plus size={14} />Поручение
            </button>
          )}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: isMobile ? 'repeat(2, minmax(0, 1fr))' : 'repeat(5, minmax(120px, 1fr))', gap: '10px', marginBottom: '14px' }}>
        {statButton('open', 'Открытые', stats.open)}
        {statButton('mine', 'Мои', stats.mine)}
        {statButton('review', 'На проверке', stats.review)}
        {statButton('overdue', 'Просрочены', stats.overdue)}
        {statButton('all', 'Все', stats.all)}
      </div>

      {showCreate && canCreate && (
        <div style={{ ...card, padding: isMobile ? '14px' : '16px', marginBottom: '14px' }}>
          <h3 style={{ margin: '0 0 12px', color: C.text, fontSize: '16px' }}>Новое поручение</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '10px' }}>
            <select value={draft.projectName} onChange={e => setDraft(prev => ({ ...prev, projectName: e.target.value }))} style={{ ...inp, width: '100%', boxSizing: 'border-box' }}>
              <option value="">Объект</option>
              {projectOptions.map(project => <option key={project.id || project.name} value={project.name}>{project.name}</option>)}
            </select>

            {draftRows.map((row, index) => {
              const assigneeGroups = assigneeGroupsForRole(row.assignedRole);
              return (
                <div
                  key={row.id}
                  style={{
                    borderTop: index === 0 ? 'none' : '1px solid ' + C.border,
                    paddingTop: index === 0 ? 0 : '12px',
                    marginTop: index === 0 ? 0 : '2px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                    <div style={{ color: C.textSec, fontSize: '12px', fontWeight: 700 }}>Поручение {index + 1}</div>
                    {draftRows.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeDraftRow(row.id)}
                        style={{ ...btnG, padding: '7px 9px' }}
                      >
                        <XCircle size={14} />Убрать
                      </button>
                    )}
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1.35fr 0.8fr 0.8fr 1fr', gap: '10px' }}>
                    <input
                      value={row.title}
                      onChange={e => updateDraftRow(row.id, { title: e.target.value })}
                      placeholder="Что нужно сделать"
                      style={inp}
                    />
                    <select
                      value={row.assignedRole}
                      onChange={e => updateDraftRow(row.id, { assignedRole: e.target.value, assignedTo: '' })}
                      style={inp}
                    >
                      <option value="">Роль</option>
                      {roleOptions.map(role => <option key={role} value={role}>{roleLabel(role)}</option>)}
                    </select>
                    <input
                      type="date"
                      value={row.dueDate}
                      onChange={e => updateDraftRow(row.id, { dueDate: e.target.value })}
                      style={inp}
                    />
                    <select
                      value={row.assignedTo}
                      onChange={e => updateDraftRow(row.id, { assignedTo: e.target.value })}
                      style={inp}
                    >
                      <option value="">Исполнитель не выбран</option>
                      {assigneeGroups.length === 0 && row.assignedRole && <option value="" disabled>Нет пользователей этой роли</option>}
                      {assigneeGroups.map(group => (
                        <optgroup key={group.role} label={group.label}>
                          {group.items.map(item => (
                            <option key={item.id || item.email || item.name} value={userDisplayName(item)}>
                              {userDisplayName(item) + (item.role ? ' / ' + roleLabel(item.role) : '')}
                            </option>
                          ))}
                        </optgroup>
                      ))}
                    </select>
                  </div>
                  <textarea
                    value={row.description}
                    onChange={e => updateDraftRow(row.id, { description: e.target.value })}
                    placeholder="Детали поручения"
                    style={{ ...inp, minHeight: '70px', resize: 'vertical', width: '100%', boxSizing: 'border-box', marginTop: '10px' }}
                  />
                </div>
              );
            })}
          </div>
          <div style={{ display: 'flex', gap: '8px', marginTop: '10px', flexWrap: 'wrap' }}>
            <button type="button" onClick={addDraftRow} style={btnG}>
              <Plus size={14} />Еще поручение
            </button>
            <button onClick={createTask} disabled={!canSubmitDraft} style={{ ...btnO, opacity: !canSubmitDraft ? 0.65 : 1 }}>
              <Plus size={14} />{creating ? 'Создание' : validDraftRows.length > 1 ? 'Создать ' + validDraftRows.length : 'Создать'}
            </button>
            <button onClick={() => setShowCreate(false)} style={btnG}>Отмена</button>
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1.1fr 0.8fr 0.8fr 0.8fr', gap: '10px', marginBottom: '14px' }}>
        <label style={{ position: 'relative' }}>
          <Search size={14} style={{ position: 'absolute', top: '50%', left: '11px', transform: 'translateY(-50%)', color: C.textMuted }} />
          <input
            value={filters.search}
            onChange={e => setFilters(prev => ({ ...prev, search: e.target.value }))}
            placeholder="Поиск по поручениям"
            style={{ ...inp, width: '100%', boxSizing: 'border-box', paddingLeft: '32px' }}
          />
        </label>
        <select value={filters.project} onChange={e => setFilters(prev => ({ ...prev, project: e.target.value }))} style={inp}>
          <option value="">Все объекты</option>
          {uniqueProjects.map(name => <option key={name} value={name}>{name}</option>)}
        </select>
        <select value={filters.role} onChange={e => setFilters(prev => ({ ...prev, role: e.target.value }))} style={inp}>
          <option value="">Все роли</option>
          {roleOptions.map(role => <option key={role} value={role}>{roleLabel(role)}</option>)}
        </select>
        <select value={filters.status} onChange={e => setFilters(prev => ({ ...prev, status: e.target.value }))} style={inp}>
          <option value="">Все статусы</option>
          {statusOptions.map(status => <option key={status} value={status}>{status}</option>)}
        </select>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: C.textSec, fontSize: '12px', marginBottom: '10px', flexWrap: 'wrap' }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '7px' }}>
          <Filter size={14} />Показано {filteredTasks.length} из {assignmentTasks.length}
        </span>
        {!showSystemTasks && systemTasksCount > 0 && (
          <span>Скрыто ИИ-контроля: {systemTasksCount}</span>
        )}
        {canInspectSystemTasks && systemTasksCount > 0 && (
          <button
            type="button"
            onClick={() => setShowSystemTasks(value => !value)}
            style={{ ...btnG, padding: '6px 9px', fontSize: '12px' }}
          >
            {showSystemTasks ? 'Скрыть ИИ-контроль' : 'Показать ИИ-контроль'}
          </button>
        )}
      </div>

      {filteredTasks.length === 0 && (
        <div style={{ ...card, padding: '22px', textAlign: 'center', color: C.textSec, fontSize: '13px' }}>
          Поручений по выбранным фильтрам нет.
        </div>
      )}

      {filteredTasks.map(task => (
        <AssignmentCard
          key={task.id}
          C={C}
          btnB={btnB}
          btnG={btnG}
          btnO={btnO}
          btnR={btnR}
          card={card}
          closeAiTask={closeAiTask}
          inp={inp}
          isMobile={isMobile}
          acceptAiTask={acceptAiTask}
          openAiTaskAction={openAiTaskAction}
          submitAiTaskReport={submitAiTaskReport}
          task={task}
          uploadPhoto={uploadPhoto}
          user={user}
        />
      ))}
    </div>
  );
}
