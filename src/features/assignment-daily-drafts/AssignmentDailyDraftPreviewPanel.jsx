import React from 'react';
import { Eye, FileText, Printer } from 'lucide-react';

import {
  assignmentDailyReviewLabel,
  buildAssignmentDailyDraftPrintContent,
  validateAssignmentDailyDraftPreview,
} from './assignmentDailyDraftPreview';

export const parseAssignmentDailyPreviewCompanyIds = raw => {
  if (typeof raw !== 'string') return null;
  const parts = raw.split(',');
  if (parts.length < 1 || parts.length > 100) return null;
  const companyIds = new Set();
  for (const part of parts) {
    if (!/^[1-9][0-9]*$/.test(part)) return null;
    const companyId = Number(part);
    if (!Number.isSafeInteger(companyId) || companyIds.has(companyId)) return null;
    companyIds.add(companyId);
  }
  return companyIds;
};

const DEFAULT_ENABLED = process.env.REACT_APP_ASSIGNMENT_DAILY_DRAFT_PREVIEW_ENABLED === 'true';
const DEFAULT_ALLOWED_COMPANY_IDS = parseAssignmentDailyPreviewCompanyIds(
  process.env.REACT_APP_ASSIGNMENT_DAILY_DRAFT_PREVIEW_COMPANY_IDS,
) || new Set();
const allowedRoles = new Set(['директор', 'зам_директора']);
const today = () => new Date().toISOString().slice(0, 10);
const positiveId = value => Number.isSafeInteger(value) && value > 0;

const visibleProjects = (projects, selectedCompanyId) => (Array.isArray(projects) ? projects : [])
  .filter(project => positiveId(project?.id) && positiveId(project?.companyId))
  .filter(project => !positiveId(selectedCompanyId) || project.companyId === selectedCompanyId);

const matchingEstimates = (estimates, project) => (Array.isArray(estimates) ? estimates : [])
  .filter(estimate => (
    positiveId(estimate?.id)
    && Number(estimate.companyId) === Number(project?.companyId)
    && Number(estimate.projectId) === Number(project?.id)
    && estimate.status === 'Активная'
    && estimate.smetaType === 'Заказчик'
    && estimate.isTemplate === false
    && typeof estimate.workPackage === 'string'
    && estimate.workPackage.trim() === estimate.workPackage
    && estimate.workPackage.length > 0
  ));

const parseVersions = value => {
  if (!Array.isArray(value) || value.length > 1000) throw new Error('versions_invalid');
  const ids = new Set();
  return value.map(row => {
    if (
      row === null
      || typeof row !== 'object'
      || Array.isArray(row)
      || !positiveId(row.id)
      || ids.has(Number(row.id))
      || typeof row.versionLabel !== 'string'
      || row.versionLabel.length === 0
      || row.versionLabel.length > 128
    ) throw new Error('versions_invalid');
    ids.add(Number(row.id));
    return { id: Number(row.id), versionLabel: row.versionLabel };
  });
};

const allReviews = preview => Array.from(new Set([
  ...(preview?.review || []),
  ...(preview?.assignmentDraft?.review || []),
  ...(preview?.dailyWorkDraft?.review || []),
]));

export default function AssignmentDailyDraftPreviewPanel({
  API = '',
  allowedCompanyIds = DEFAULT_ALLOWED_COMPANY_IDS,
  C = {},
  btnG = {},
  btnO = {},
  card = {},
  enabled = DEFAULT_ENABLED,
  estimates = [],
  inp = {},
  isMobile = false,
  projects = [],
  selectedCompanyId,
  showPreview,
  user = {},
}) {
  const allowed = (
    enabled === true
    && allowedRoles.has(user?.role)
    && positiveId(selectedCompanyId)
    && allowedCompanyIds instanceof Set
    && allowedCompanyIds.has(Number(selectedCompanyId))
  );
  const projectOptions = React.useMemo(
    () => visibleProjects(projects, selectedCompanyId),
    [projects, selectedCompanyId],
  );
  const [projectId, setProjectId] = React.useState('');
  const [estimateId, setEstimateId] = React.useState('');
  const [versionId, setVersionId] = React.useState('');
  const [date, setDate] = React.useState(today);
  const [versions, setVersions] = React.useState([]);
  const [loadingVersions, setLoadingVersions] = React.useState(false);
  const [loadingPreview, setLoadingPreview] = React.useState(false);
  const [error, setError] = React.useState('');
  const [result, setResult] = React.useState(null);
  const previewControllerRef = React.useRef(null);

  const resetPreview = React.useCallback(() => {
    previewControllerRef.current?.abort();
    previewControllerRef.current = null;
    setLoadingPreview(false);
    setResult(null);
    setError('');
  }, []);

  React.useEffect(() => () => previewControllerRef.current?.abort(), []);

  React.useEffect(() => {
    if (!allowed) return;
    const stillExists = projectOptions.some(project => String(project.id) === String(projectId));
    if (!stillExists) setProjectId(projectOptions[0] ? String(projectOptions[0].id) : '');
  }, [allowed, projectId, projectOptions]);

  const project = projectOptions.find(item => String(item.id) === String(projectId)) || null;
  const estimateOptions = React.useMemo(() => matchingEstimates(estimates, project), [estimates, project]);

  React.useEffect(() => {
    if (!allowed) return;
    const stillExists = estimateOptions.some(estimate => String(estimate.id) === String(estimateId));
    if (!stillExists) setEstimateId(estimateOptions[0] ? String(estimateOptions[0].id) : '');
  }, [allowed, estimateId, estimateOptions]);

  const estimate = estimateOptions.find(item => String(item.id) === String(estimateId)) || null;

  React.useEffect(() => {
    if (!allowed || !estimate) {
      setVersions([]);
      setVersionId('');
      return undefined;
    }
    const controller = new AbortController();
    setLoadingVersions(true);
    setVersions([]);
    setVersionId('');
    resetPreview();
    fetch(`${API}/estimates/${estimate.id}/versions`, {
      credentials: 'include',
      signal: controller.signal,
    })
      .then(response => {
        if (!response.ok) throw new Error('versions_unavailable');
        return response.json();
      })
      .then(parseVersions)
      .then(rows => {
        if (controller.signal.aborted) return;
        setVersions(rows);
        setVersionId(rows[0] ? String(rows[0].id) : '');
      })
      .catch(reason => {
        if (reason?.name === 'AbortError' || controller.signal.aborted) return;
        setError('Сохранённые версии сметы временно недоступны');
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoadingVersions(false);
      });
    return () => controller.abort();
  }, [API, allowed, estimate, resetPreview]);

  if (!allowed) return null;

  const selectedVersion = versions.find(item => String(item.id) === String(versionId)) || null;
  const canPreview = project && estimate && selectedVersion && /^\d{4}-\d{2}-\d{2}$/.test(date) && !loadingPreview;

  const requestPreview = async () => {
    if (!canPreview) return;
    previewControllerRef.current?.abort();
    const controller = new AbortController();
    previewControllerRef.current = controller;
    setLoadingPreview(true);
    setError('');
    setResult(null);
    const expected = {
      companyId: Number(project.companyId),
      projectId: Number(project.id),
      date,
      estimateId: Number(estimate.id),
      estimateVersionId: Number(selectedVersion.id),
      workPackage: estimate.workPackage,
    };
    try {
      const response = await fetch(`${API}/assignment-daily-draft-previews`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
        body: JSON.stringify({
          projectId: expected.projectId,
          date: expected.date,
          estimateId: expected.estimateId,
          estimateVersionId: expected.estimateVersionId,
          workPackage: expected.workPackage,
        }),
      });
      if (!response.ok) throw new Error('preview_unavailable');
      const body = await response.json();
      if (controller.signal.aborted) return;
      setResult(validateAssignmentDailyDraftPreview(body, expected));
    } catch (reason) {
      if (controller.signal.aborted || reason?.name === 'AbortError') return;
      setError('Предпросмотр временно недоступен');
    } finally {
      if (previewControllerRef.current === controller) {
        previewControllerRef.current = null;
        setLoadingPreview(false);
      }
    }
  };

  const openPrintable = () => {
    if (!result || typeof showPreview !== 'function') return;
    showPreview(buildAssignmentDailyDraftPrintContent(result, {
      projectName: project?.name || '',
      estimateName: estimate?.name || '',
      versionLabel: selectedVersion?.versionLabel || '',
    }), `Черновик назначений и работ — ${project?.name || 'объект'}`);
  };

  const reviews = result ? allReviews(result) : [];
  const labelStyle = { display: 'grid', gap: '6px', color: C.textSec, fontSize: '12px', fontWeight: 700 };
  const grid = { display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'repeat(4, minmax(0, 1fr))', gap: '10px' };

  return (
    <section style={{ ...card, padding: isMobile ? '14px' : '16px', marginBottom: '14px' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
        <div>
          <h3 style={{ margin: 0, color: C.text, fontSize: '17px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileText size={18} />Черновик назначений и работ
          </h3>
          <p style={{ margin: '5px 0 14px', color: C.textSec, fontSize: '12px' }}>
            Только просмотр: данные не сохраняются и исполнители не назначаются.
          </p>
        </div>
        {result && (
          <button type="button" onClick={openPrintable} style={btnG}>
            <Printer size={14} />Печатная версия
          </button>
        )}
      </div>

      <div style={grid}>
        <label style={labelStyle}>
          Объект
          <select value={projectId} onChange={event => { setProjectId(event.target.value); resetPreview(); }} style={inp}>
            {projectOptions.length === 0 && <option value="">Нет доступных объектов</option>}
            {projectOptions.map(item => <option key={item.id} value={item.id}>{item.name || `Объект ${item.id}`}</option>)}
          </select>
        </label>
        <label style={labelStyle}>
          Активная смета заказчика
          <select value={estimateId} onChange={event => { setEstimateId(event.target.value); resetPreview(); }} style={inp}>
            {estimateOptions.length === 0 && <option value="">Нет подходящей сметы</option>}
            {estimateOptions.map(item => (
              <option key={item.id} value={item.id}>{item.name} · {item.workPackage}</option>
            ))}
          </select>
        </label>
        <label style={labelStyle}>
          Сохранённая версия
          <select value={versionId} onChange={event => { setVersionId(event.target.value); resetPreview(); }} style={inp} disabled={loadingVersions}>
            {versions.length === 0 && <option value="">{loadingVersions ? 'Загрузка…' : 'Нет версий'}</option>}
            {versions.map(item => <option key={item.id} value={item.id}>{item.versionLabel}</option>)}
          </select>
        </label>
        <label style={labelStyle}>
          Дата подтверждённых работ
          <input type="date" value={date} onChange={event => { setDate(event.target.value); resetPreview(); }} style={inp} />
        </label>
      </div>

      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '12px' }}>
        <button type="button" onClick={requestPreview} disabled={!canPreview} style={{ ...btnO, opacity: canPreview ? 1 : 0.6 }}>
          <Eye size={14} />{loadingPreview ? 'Формирование…' : 'Сформировать предпросмотр'}
        </button>
      </div>

      {error && <div role="alert" style={{ marginTop: '12px', color: C.danger, background: C.dangerLight, padding: '10px', borderRadius: '8px' }}>{error}</div>}

      {result && (
        <div style={{ marginTop: '14px', display: 'grid', gap: '12px' }}>
          {reviews.length > 0 && (
            <div style={{ color: C.warning, background: C.warningLight, padding: '10px', borderRadius: '8px' }}>
              <b>Требуется проверка</b>
              <ul style={{ margin: '6px 0 0', paddingLeft: '20px' }}>
                {reviews.map(code => <li key={code}>{assignmentDailyReviewLabel(code)}</li>)}
              </ul>
            </div>
          )}
          <div>
            <h4 style={{ margin: '0 0 8px', color: C.text }}>Доступно к назначению</h4>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                <thead><tr>{['Раздел', 'Работа', 'Ед.', 'По смете', 'Назначено', 'Остаток', 'Пакет'].map(label => <th key={label} style={{ textAlign: 'left', color: C.textSec, borderBottom: `1px solid ${C.border}`, padding: '7px' }}>{label}</th>)}</tr></thead>
                <tbody>
                  {result.assignmentDraft.items.length === 0 && <tr><td colSpan="7" style={{ padding: '10px', color: C.textSec }}>Нет доступных строк</td></tr>}
                  {result.assignmentDraft.items.map(item => <tr key={`${item.sectionIndex}:${item.itemIndex}`}><td style={{ padding: '7px' }}>{item.sectionName}</td><td style={{ padding: '7px' }}>{item.itemName}</td><td style={{ padding: '7px' }}>{item.unit}</td><td style={{ padding: '7px' }}>{item.estimateQuantity}</td><td style={{ padding: '7px' }}>{item.assignedQuantity}</td><td style={{ padding: '7px' }}>{item.availableQuantity}</td><td style={{ padding: '7px' }}>{item.workPackage}</td></tr>)}
                </tbody>
              </table>
            </div>
          </div>
          <div>
            <h4 style={{ margin: '0 0 8px', color: C.text }}>Подтверждённые работы за день</h4>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                <thead><tr>{['Работа', 'Ед.', 'Объём', 'Ответственный', 'Пакет'].map(label => <th key={label} style={{ textAlign: 'left', color: C.textSec, borderBottom: `1px solid ${C.border}`, padding: '7px' }}>{label}</th>)}</tr></thead>
                <tbody>
                  {result.dailyWorkDraft.items.length === 0 && <tr><td colSpan="5" style={{ padding: '10px', color: C.textSec }}>Подтверждённых работ нет</td></tr>}
                  {result.dailyWorkDraft.items.map(item => <tr key={item.sourceId}><td style={{ padding: '7px' }}>{item.description}</td><td style={{ padding: '7px' }}>{item.unit}</td><td style={{ padding: '7px' }}>{item.quantity}</td><td style={{ padding: '7px' }}>{item.responsibleName}</td><td style={{ padding: '7px' }}>{item.workPackage}</td></tr>)}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
