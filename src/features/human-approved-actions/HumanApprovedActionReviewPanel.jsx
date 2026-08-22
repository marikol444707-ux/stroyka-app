import React from 'react';
import {
  CheckCircle2,
  ClipboardCheck,
  RefreshCw,
  ShieldAlert,
  XCircle,
} from 'lucide-react';

import {
  HUMAN_ACTION_ANOMALIES,
  buildHumanActionSource,
  humanActionProposalExpired,
  humanActionSourceKey,
  parseHumanApprovedActionCompanyIds,
  validateHumanActionDecisionReceipt,
  validateHumanActionProposalReceipt,
  validateWarehouseAnomalyPreview,
} from './humanApprovedActions';

const DEFAULT_ENABLED = process.env.REACT_APP_HUMAN_APPROVED_ACTIONS_ENABLED === 'true';
const DEFAULT_ALLOWED_COMPANY_IDS = parseHumanApprovedActionCompanyIds(
  process.env.REACT_APP_HUMAN_APPROVED_ACTIONS_COMPANY_IDS,
) || new Set();

const CONSEQUENCE = (
  'Будет записан только факт ручной проверки. Это не изменит накладную, '
  + 'складские остатки, движения или суммы и не означает, что аномалия исправлена.'
);

const responseJson = async response => {
  if (!response?.ok) throw new Error('human_approved_action_ui_request_failed');
  return response.json();
};

const requestJson = (API, path, body, signal) => fetch(`${API}${path}`, {
  method: 'POST',
  credentials: 'include',
  cache: 'no-store',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
  signal,
}).then(responseJson);

const Field = ({ children, label, ...props }) => (
  <label style={{ display: 'grid', gap: '5px', minWidth: 0 }}>
    <span style={{ fontSize: '12px', fontWeight: 700 }}>{label}</span>
    {React.cloneElement(children, props)}
  </label>
);

function DecisionReceipt({ C, receipt }) {
  const applied = receipt.state === 'applied';
  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        marginTop: '14px', padding: '13px', borderRadius: '8px',
        color: applied ? C.success : C.textSec,
        background: applied ? C.successLight : (C.bgGray || '#f3f4f6'),
      }}
    >
      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        {applied
          ? <CheckCircle2 size={18} aria-hidden="true" />
          : <XCircle size={18} aria-hidden="true" />}
        <b>{applied ? 'Факт проверки записан' : 'Предложение отклонено'}</b>
      </div>
      <p style={{ margin: '7px 0 0', fontSize: '12px' }}>
        Квитанция №{receipt.eventId}
        {receipt.auditEventId !== null ? ` · аудит №${receipt.auditEventId}` : ''}
        {receipt.idempotent ? ' · повтор без новых записей' : ''}
      </p>
      <p style={{ margin: '5px 0 0', fontSize: '12px' }}>
        Предложение №{receipt.proposalId} · {receipt.actionKind}
      </p>
      <p style={{ margin: '5px 0 0', fontSize: '12px' }}>
        Складские и финансовые записи не изменялись. Записано только решение о проверке.
      </p>
    </div>
  );
}

export default function HumanApprovedActionReviewPanel({
  API = '',
  C = {},
  allowedCompanyIds = DEFAULT_ALLOWED_COMPANY_IDS,
  card = {},
  clock = Date.now,
  companyMode,
  enabled = DEFAULT_ENABLED,
  isMobile = false,
  projects = [],
  selectedCompanyId,
  user = {},
}) {
  const allowed = (
    enabled === true
    && companyMode === 'company'
    && Number.isSafeInteger(selectedCompanyId)
    && selectedCompanyId > 0
    && allowedCompanyIds instanceof Set
    && allowedCompanyIds.size === 1
    && allowedCompanyIds.has(selectedCompanyId)
    && user?.role === 'директор'
  );
  const companyProjects = projects.filter(project => (
    Number(project?.companyId) === selectedCompanyId
    && Number.isSafeInteger(Number(project?.id))
    && Number(project.id) > 0
  ));
  const projectContextKey = companyProjects
    .map(project => String(project.id))
    .sort()
    .join(',');
  const [form, setForm] = React.useState({
    projectId: '', jobId: '', anomalyCode: '', subjectId: '',
  });
  const [previewRecord, setPreviewRecord] = React.useState(null);
  const [proposalRecord, setProposalRecord] = React.useState(null);
  const [receipt, setReceipt] = React.useState(null);
  const [pending, setPending] = React.useState('');
  const [error, setError] = React.useState('');
  const [nowMs, setNowMs] = React.useState(() => clock());
  const generationRef = React.useRef(0);
  const pendingRef = React.useRef('');
  const controllerRef = React.useRef(null);

  const clearReview = React.useCallback(() => {
    generationRef.current += 1;
    controllerRef.current?.abort();
    controllerRef.current = null;
    pendingRef.current = '';
    setPending('');
    setError('');
    setPreviewRecord(null);
    setProposalRecord(null);
    setReceipt(null);
  }, []);

  React.useEffect(() => {
    clearReview();
    if (!allowed) {
      setForm({ projectId: '', jobId: '', anomalyCode: '', subjectId: '' });
    }
    return () => controllerRef.current?.abort();
  }, [allowed, clearReview, companyMode, projectContextKey, selectedCompanyId]);

  React.useEffect(() => {
    if (!proposalRecord) return undefined;
    const update = () => setNowMs(clock());
    update();
    const delay = Math.max(0, Date.parse(proposalRecord.receipt.expiresAt) - clock());
    const timer = setTimeout(update, Math.min(delay + 10, 2147483647));
    return () => clearTimeout(timer);
  }, [clock, proposalRecord]);

  if (!allowed) return null;

  const palette = {
    text: C.text || '#111827', textSec: C.textSec || '#4b5563',
    muted: C.textMuted || '#6b7280', border: C.border || '#d1d5db',
    accent: C.accent || '#ea580c', accentLight: C.accentLight || '#fff7ed',
    success: C.success || '#15803d', successLight: C.successLight || '#f0fdf4',
    warning: C.warning || '#a16207', warningLight: C.warningLight || '#fefce8',
    danger: C.danger || '#b91c1c', dangerLight: C.dangerLight || '#fef2f2',
  };
  const selectedProject = companyProjects.find(project => String(project.id) === form.projectId);
  let source = null;
  if (selectedProject) {
    try {
      source = buildHumanActionSource(form);
    } catch (_error) {}
  }
  const sourceKey = source ? humanActionSourceKey(source) : '';
  const previewCurrent = previewRecord?.sourceKey === sourceKey;
  const proposalCurrent = proposalRecord?.sourceKey === sourceKey;
  const proposalExpired = proposalCurrent
    ? humanActionProposalExpired(proposalRecord.receipt, nowMs)
    : false;
  const busy = Boolean(pending);
  const inputStyle = {
    width: '100%', boxSizing: 'border-box', padding: '9px 10px',
    border: `1px solid ${palette.border}`, borderRadius: '8px',
    color: palette.text, background: C.bgWhite || C.bg || '#fff',
  };

  const changeField = field => event => {
    clearReview();
    setForm(current => ({ ...current, [field]: event.target.value }));
  };

  const run = async (operation, path, body, validate) => {
    if (pendingRef.current) return null;
    const generation = generationRef.current;
    const controller = new AbortController();
    controllerRef.current?.abort();
    controllerRef.current = controller;
    pendingRef.current = operation;
    setPending(operation);
    setError('');
    try {
      const raw = await requestJson(API, path, body, controller.signal);
      if (controller.signal.aborted || generation !== generationRef.current) return null;
      return validate(raw);
    } catch (reason) {
      if (reason?.name !== 'AbortError' && generation === generationRef.current) {
        setError(operation === 'preview'
          ? 'Текущая проверка недоступна'
          : operation === 'proposal'
            ? 'Не удалось подготовить запись проверки'
            : 'Не удалось записать решение');
      }
      return null;
    } finally {
      if (generation === generationRef.current) {
        pendingRef.current = '';
        setPending('');
        controllerRef.current = null;
      }
    }
  };

  const loadPreview = async () => {
    if (!source) return;
    const key = humanActionSourceKey(source);
    const result = await run(
      'preview', '/warehouse-anomaly-previews', source,
      raw => validateWarehouseAnomalyPreview(raw, source),
    );
    if (result) setPreviewRecord({ sourceKey: key, result });
  };

  const createProposal = async () => {
    if (!source || !previewCurrent || previewRecord.result.state !== 'preview_ready') return;
    const key = humanActionSourceKey(source);
    const result = await run(
      'proposal', '/human-approved-actions/proposals', source,
      raw => validateHumanActionProposalReceipt(raw, selectedCompanyId, source),
    );
    if (result) setProposalRecord({ sourceKey: key, receipt: result });
  };

  const decide = async decision => {
    if (!proposalCurrent || proposalExpired) return;
    const currentProposal = proposalRecord.receipt;
    const body = {
      proposalId: currentProposal.proposalId,
      proposalSha256: currentProposal.proposalSha256,
      decision,
    };
    const result = await run(
      'decision', '/human-approved-actions/decisions', body,
      raw => validateHumanActionDecisionReceipt(raw, selectedCompanyId, currentProposal),
    );
    if (result) setReceipt(result);
  };

  const preview = previewCurrent ? previewRecord.result : null;
  const proposal = proposalCurrent ? proposalRecord.receipt : null;

  return (
    <section
      aria-labelledby="human-approved-action-title"
      style={{ ...card, padding: isMobile ? '14px' : '18px', marginBottom: '16px' }}
    >
      <div style={{ display: 'flex', gap: '9px', alignItems: 'flex-start' }}>
        <ShieldAlert size={20} color={palette.accent} aria-hidden="true" />
        <div>
          <h2 id="human-approved-action-title" style={{ margin: 0, color: palette.text, fontSize: '18px' }}>
            Ручная фиксация проверки аномалии
          </h2>
          <p style={{ margin: '6px 0 0', color: palette.textSec, fontSize: '12px' }}>
            Трёхэтапная проверка: текущий снимок → предложение → отдельное решение.
          </p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'repeat(2, minmax(0, 1fr))', gap: '10px', marginTop: '14px', color: palette.text }}>
        <Field label="Объект проверки">
          <select aria-label="Объект проверки" value={form.projectId} onChange={changeField('projectId')} style={inputStyle}>
            <option value="">Выберите объект</option>
            {companyProjects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}
          </select>
        </Field>
        <Field label="Задание проверки">
          <input aria-label="Задание проверки" inputMode="numeric" value={form.jobId} onChange={changeField('jobId')} placeholder="Например, 27" style={inputStyle} />
        </Field>
        <Field label="Тип аномалии">
          <select aria-label="Тип аномалии" value={form.anomalyCode} onChange={changeField('anomalyCode')} style={inputStyle}>
            <option value="">Выберите тип</option>
            {Object.entries(HUMAN_ACTION_ANOMALIES).map(([code, item]) => (
              <option key={code} value={code}>{item.label}</option>
            ))}
          </select>
        </Field>
        <Field label="Номер записи">
          <input aria-label="Номер записи" inputMode="numeric" value={form.subjectId} onChange={changeField('subjectId')} placeholder="ID записи" style={inputStyle} />
        </Field>
      </div>

      <button
        type="button"
        onClick={loadPreview}
        disabled={!source || busy}
        style={{
          marginTop: '12px', border: `1px solid ${palette.border}`,
          background: palette.accentLight, color: palette.text, borderRadius: '8px',
          padding: '9px 12px', fontWeight: 700,
          cursor: !source || busy ? 'default' : 'pointer',
          display: 'inline-flex', gap: '7px', alignItems: 'center',
        }}
      >
        <RefreshCw size={15} aria-hidden="true" />
        {pending === 'preview' ? 'Проверяем…' : 'Проверить текущие данные'}
      </button>

      {error && <div role="alert" style={{ marginTop: '12px', padding: '11px', borderRadius: '8px', color: palette.danger, background: palette.dangerLight }}>{error}</div>}

      {preview && preview.state !== 'preview_ready' && (
        <div role="alert" style={{ marginTop: '12px', padding: '11px', borderRadius: '8px', color: palette.warning, background: palette.warningLight }}>
          Текущий снимок заблокирован или устарел. Создать запись проверки нельзя.
        </div>
      )}

      {preview?.state === 'preview_ready' && (
        <div style={{ marginTop: '14px', border: `1px solid ${palette.border}`, borderRadius: '10px', padding: '13px' }}>
          <p style={{ margin: 0, color: palette.muted, fontSize: '12px' }}>
            Компания №{selectedCompanyId} · Объект {selectedProject?.name || `№${source.projectId}`} · Задание №{source.jobId}
          </p>
          <h3 style={{ margin: '8px 0 0', color: palette.text, fontSize: '15px' }}>{preview.content.title}</h3>
          <p style={{ margin: '7px 0 0', color: palette.text, fontSize: '12px' }}>
            <b>Затронутая запись:</b> {HUMAN_ACTION_ANOMALIES[source.selected.anomalyCode].label} · №{source.selected.subjectId}
          </p>
          <p style={{ margin: '7px 0 0', color: palette.textSec, fontSize: '13px' }}>{preview.content.finding}</p>
          <p style={{ margin: '7px 0 0', color: palette.textSec, fontSize: '12px' }}><b>Следующий безопасный шаг:</b> {preview.content.nextSafeAction}</p>
          <p style={{ margin: '10px 0 0', padding: '10px', color: palette.warning, background: palette.warningLight, borderRadius: '8px', fontSize: '12px' }}>
            {CONSEQUENCE}
          </p>
          {!proposal && !receipt && (
            <button
              type="button"
              onClick={createProposal}
              disabled={busy || !previewCurrent}
              style={{ marginTop: '11px', border: 0, borderRadius: '8px', padding: '9px 12px', fontWeight: 700, color: '#fff', background: palette.accent, cursor: busy ? 'default' : 'pointer' }}
            >
              {pending === 'proposal' ? 'Подготавливаем…' : 'Подготовить запись проверки'}
            </button>
          )}
        </div>
      )}

      {proposal && !receipt && (
        <div style={{ marginTop: '14px', border: `1px solid ${palette.border}`, borderRadius: '10px', padding: '13px' }}>
          <h3 style={{ margin: 0, color: palette.text, fontSize: '15px' }}>Предложение №{proposal.proposalId}</h3>
          <p style={{ margin: '6px 0 0', color: palette.textSec, fontSize: '12px' }}>
            Действует до {new Date(proposal.expiresAt).toLocaleString('ru-RU')}
          </p>
          <p style={{ margin: '9px 0 0', color: palette.warning, fontSize: '12px' }}>{CONSEQUENCE}</p>
          {proposalExpired && <div role="alert" style={{ marginTop: '9px', color: palette.danger }}>Срок предложения истёк. Обновите текущие данные.</div>}
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '11px' }}>
            <button type="button" onClick={() => decide('reject')} disabled={busy || proposalExpired} style={{ border: `1px solid ${palette.border}`, borderRadius: '8px', padding: '9px 12px', background: 'transparent', color: palette.text, fontWeight: 700 }}>
              Отклонить запись
            </button>
            <button type="button" onClick={() => decide('approve')} disabled={busy || proposalExpired} style={{ border: 0, borderRadius: '8px', padding: '9px 12px', background: palette.accent, color: '#fff', fontWeight: 700 }}>
              <ClipboardCheck size={15} aria-hidden="true" style={{ verticalAlign: 'text-bottom', marginRight: '6px' }} />
              Записать факт проверки — данные не исправляются
            </button>
          </div>
        </div>
      )}

      {receipt && <DecisionReceipt C={palette} receipt={receipt} />}
    </section>
  );
}
