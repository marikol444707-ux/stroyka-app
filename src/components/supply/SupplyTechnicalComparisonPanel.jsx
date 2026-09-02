import React from 'react';

const DEFAULT_ENABLED = process.env.REACT_APP_SUPPLY_TECHNICAL_COMPARISON_ENABLED === 'true';
const ALLOWED_ROLES = new Set(['директор', 'зам_директора', 'снабженец']);
const SOURCE_KINDS = new Set(['supplier_offer', 'supplier_invoice']);
const DECISIONS = new Set(['exact', 'comparable', 'review_required', 'incompatible']);
const STATUSES = new Set(['ok', 'review', 'blocked']);
const SHA256 = /^[0-9a-f]{64}$/;
const MAX_LINES = 100;

const OUTER_KEYS = new Set([
  'ok', 'dryRun', 'contractVersion', 'companyId', 'projectId', 'requestId',
  'sourceKind', 'sourceId', 'file', 'requestedLineCount', 'offeredLineCount',
  'comparisonCount', 'comparisons', 'resultSha256', 'automaticApprovalAllowed',
  'writesAttempted', 'modelCalls', 'readOnlyTransaction', 'rolledBack',
]);
const FILE_KEYS = new Set(['id', 'contentUrl', 'context', 'originalName', 'contentType']);
const COMPARISON_KEYS = new Set(['lineNumber', 'required', 'offered', 'result']);
const LINE_KEYS = new Set(['name', 'unit', 'quantity', 'workPackage', 'category']);
const RESULT_KEYS = new Set([
  'contractVersion', 'status', 'decision', 'confidence', 'confidenceBasisPoints',
  'reasonCodes', 'reasons', 'requiredSignature', 'offeredSignature',
  'comparisonSha256', 'writesAttempted', 'modelCalls', 'automaticApprovalAllowed',
]);
const SIGNATURE_KEYS = new Set([
  'normalizedName', 'family', 'dimensions', 'diametersMm', 'threadSizes',
  'threadGenders', 'anglesDeg', 'pnClasses', 'sdrClasses', 'reinforcement',
  'directions', 'designFlags', 'weightsG', 'signatureSha256',
]);

const REASON_LABELS = {
  ONLY_ONE_SUPPLIER_QUOTED: 'Получена только одна строка предложения.',
  PRODUCT_FAMILY_CONFLICT: 'Типы материалов не совпадают.',
  THREAD_GENDER_CONFLICT: 'Не совпадает тип резьбы.',
  ANGLE_CONFLICT: 'Не совпадает угол изделия.',
  DIRECTION_OR_DESIGN_DIFFERS: 'Отличается направление или конструкция.',
  PACKAGING_OR_WEIGHT_DIFFERS: 'Отличается упаковка или вес.',
  DRY_SIPHON_DESIGN_DIFFERS: 'Отличается конструкция сухого сифона.',
  ECCENTRICITY_DIFFERS: 'Отличается геометрия перехода.',
  SEWER_APPLICATION_DIFFERS: 'Отличается назначение канализационного изделия.',
  COMPATIBLE_ENGINEERING_SIGNATURE: 'Технические характеристики совместимы.',
  MODEL_SENSITIVE_FAMILY: 'Модель изделия требует ручного подтверждения.',
  WEAK_NOMENCLATURE_MATCH: 'Названия совпадают недостаточно уверенно.',
  SAME_FAMILY_NO_CRITICAL_CONFLICT: 'Тип материала совпадает, критических расхождений не найдено.',
  INSUFFICIENT_TECHNICAL_EVIDENCE: 'Недостаточно характеристик для уверенного вывода.',
  UNIT_CONFLICT: 'Не совпадают единицы измерения.',
  DIMENSION_CONFLICT: 'Не совпадают критические размеры.',
  DIAMETER_CONFLICT: 'Не совпадает диаметр.',
  THREAD_SIZE_CONFLICT: 'Не совпадает размер резьбы.',
  PRESSURE_CLASS_BELOW_REQUIRED: 'Класс давления ниже требуемого.',
  PRESSURE_CLASS_ABOVE_REQUIRED: 'Класс давления выше требуемого — нужна проверка совместимости.',
  PRESSURE_CLASS_MISSING: 'В предложении не указан требуемый класс давления.',
  SDR_WEAKER_THAN_REQUIRED: 'SDR предложения указывает на более тонкую стенку.',
  SDR_DIFFERS: 'SDR отличается — нужна проверка совместимости.',
  SDR_MISSING: 'В предложении не указан требуемый SDR.',
  REINFORCEMENT_CONFLICT: 'Не совпадает армирование трубы.',
  REINFORCEMENT_MISSING: 'В предложении не указано требуемое армирование.',
  REQUIRED_DIMENSION_MISSING: 'В предложении не указан требуемый размер.',
  REQUIRED_DIAMETER_MISSING: 'В предложении не указан требуемый диаметр.',
  REQUIRED_THREAD_SIZE_MISSING: 'В предложении не указан требуемый размер резьбы.',
  REQUIRED_THREAD_GENDER_MISSING: 'В предложении не указан требуемый тип резьбы.',
  REQUIRED_ANGLE_MISSING: 'В предложении не указан требуемый угол.',
  EXACT_NORMALIZED_NAME: 'Название и единица измерения совпадают.',
};

const DECISION_LABELS = {
  exact: 'Точное совпадение',
  comparable: 'Сопоставимо',
  review_required: 'Нужна проверка',
  incompatible: 'Не подходит',
};

const exactKeys = (value, keys) => (
  value !== null
  && typeof value === 'object'
  && !Array.isArray(value)
  && Object.keys(value).length === keys.size
  && Object.keys(value).every(key => keys.has(key))
);
const positiveId = value => Number.isSafeInteger(value) && value > 0;
const utf8Length = value => {
  let bytes = 0;
  for (const character of value) {
    const code = character.codePointAt(0);
    bytes += code <= 0x7f ? 1 : code <= 0x7ff ? 2 : code <= 0xffff ? 3 : 4;
  }
  return bytes;
};
const boundedText = (value, maximum, allowEmpty = false) => (
  typeof value === 'string'
  && !value.includes('\0')
  && (allowEmpty || value.length > 0)
  && utf8Length(value) <= maximum
);

export const parseSupplyTechnicalComparisonCompanyIds = raw => {
  if (typeof raw !== 'string') return null;
  const parts = raw.split(',');
  if (parts.length < 1 || parts.length > 100) return null;
  const result = new Set();
  for (const part of parts) {
    if (!/^[1-9][0-9]*$/.test(part)) return null;
    const value = Number(part);
    if (!positiveId(value) || result.has(value)) return null;
    result.add(value);
  }
  return result;
};

const DEFAULT_ALLOWED_COMPANY_IDS = parseSupplyTechnicalComparisonCompanyIds(
  process.env.REACT_APP_SUPPLY_TECHNICAL_COMPARISON_COMPANY_IDS,
) || new Set();

export const protectedTenantFileId = value => {
  if (typeof value !== 'string') return null;
  const match = /^\/tenant-files\/([1-9][0-9]*)\/content$/.exec(value);
  if (!match) return null;
  const fileId = Number(match[1]);
  return positiveId(fileId) ? fileId : null;
};

export const uniqueScopedProjectId = (projects, projectName, companyId) => {
  if (!Array.isArray(projects) || typeof projectName !== 'string' || !projectName || !positiveId(companyId)) {
    return null;
  }
  const matches = projects.filter(project => (
    positiveId(project?.id)
    && project?.companyId === companyId
    && project?.name === projectName
  ));
  return matches.length === 1 ? matches[0].id : null;
};

const normalizeLine = value => {
  if (!exactKeys(value, LINE_KEYS)) return null;
  if (
    !boundedText(value.name, 4096)
    || !boundedText(value.unit, 64)
    || !/^(?:0|[1-9][0-9]{0,63})(?:\.[0-9]{1,12})?$/.test(value.quantity)
    || !boundedText(value.workPackage, 512)
    || !boundedText(value.category, 512, true)
  ) return null;
  return { ...value };
};

const normalizeSignature = value => {
  if (!exactKeys(value, SIGNATURE_KEYS)) return null;
  if (
    !boundedText(value.normalizedName, 4096, true)
    || !boundedText(value.family, 128, true)
    || !SHA256.test(value.signatureSha256)
  ) return null;
  for (const key of [
    'dimensions', 'diametersMm', 'threadSizes', 'threadGenders', 'pnClasses',
    'sdrClasses', 'reinforcement', 'directions', 'designFlags', 'weightsG',
  ]) {
    if (!Array.isArray(value[key]) || value[key].length > 100 || value[key].some(item => !boundedText(item, 256))) {
      return null;
    }
  }
  if (!Array.isArray(value.anglesDeg) || value.anglesDeg.length > 100 || value.anglesDeg.some(item => !Number.isInteger(item) || item < 0 || item > 360)) {
    return null;
  }
  return { ...value };
};

const normalizePairResult = value => {
  if (!exactKeys(value, RESULT_KEYS)) return null;
  if (
    value.contractVersion !== 1
    || !STATUSES.has(value.status)
    || !DECISIONS.has(value.decision)
    || !Number.isInteger(value.confidenceBasisPoints)
    || value.confidenceBasisPoints < 0
    || value.confidenceBasisPoints > 10000
    || (typeof value.confidence !== 'number')
    || value.confidence !== Number((value.confidenceBasisPoints / 10000).toFixed(4))
    || !Array.isArray(value.reasonCodes)
    || value.reasonCodes.length > 50
    || value.reasonCodes.some(code => !Object.prototype.hasOwnProperty.call(REASON_LABELS, code))
    || !Array.isArray(value.reasons)
    || value.reasons.length !== value.reasonCodes.length
    || value.reasons.some(reason => !boundedText(reason, 1024))
    || !SHA256.test(value.comparisonSha256)
    || value.writesAttempted !== 0
    || value.modelCalls !== 0
    || value.automaticApprovalAllowed !== false
  ) return null;
  const requiredSignature = normalizeSignature(value.requiredSignature);
  const offeredSignature = normalizeSignature(value.offeredSignature);
  if (!requiredSignature || !offeredSignature) return null;
  return { ...value, requiredSignature, offeredSignature };
};

const normalizeReport = (value, selectors) => {
  if (!exactKeys(value, OUTER_KEYS)) return null;
  if (
    value.ok !== true
    || value.dryRun !== true
    || value.contractVersion !== 1
    || value.companyId !== selectors.companyId
    || value.projectId !== selectors.projectId
    || value.requestId !== selectors.requestId
    || value.sourceKind !== selectors.sourceKind
    || value.sourceId !== selectors.sourceId
    || value.automaticApprovalAllowed !== false
    || value.writesAttempted !== 0
    || value.modelCalls !== 0
    || value.readOnlyTransaction !== true
    || value.rolledBack !== true
    || !SHA256.test(value.resultSha256)
  ) return null;
  if (
    !exactKeys(value.file, FILE_KEYS)
    || value.file.id !== selectors.fileId
    || value.file.contentUrl !== `/tenant-files/${selectors.fileId}/content`
    || !boundedText(value.file.context, 100)
    || !boundedText(value.file.originalName, 1024, true)
    || !boundedText(value.file.contentType, 255, true)
  ) return null;
  if (
    !Number.isInteger(value.comparisonCount)
    || value.comparisonCount < 1
    || value.comparisonCount > MAX_LINES
    || value.requestedLineCount !== value.comparisonCount
    || value.offeredLineCount !== value.comparisonCount
    || !Array.isArray(value.comparisons)
    || value.comparisons.length !== value.comparisonCount
  ) return null;
  const comparisons = value.comparisons.map((item, index) => {
    if (!exactKeys(item, COMPARISON_KEYS) || item.lineNumber !== index + 1) return null;
    const required = normalizeLine(item.required);
    const offered = normalizeLine(item.offered);
    const result = normalizePairResult(item.result);
    return required && offered && result ? { ...item, required, offered, result } : null;
  });
  if (comparisons.some(item => !item)) return null;
  return { ...value, comparisons };
};

const decisionColors = (decision, C) => {
  if (decision === 'exact' || decision === 'comparable') {
    return [C.success || '#2b8a3e', C.successLight || '#ebfbee', C.successBorder || '#b2f2bb'];
  }
  if (decision === 'incompatible') {
    return [C.danger || '#c92a2a', C.dangerLight || '#fff5f5', C.dangerBorder || '#ffc9c9'];
  }
  return [C.warning || '#9c6500', C.warningLight || '#fff9db', C.warningBorder || '#ffe066'];
};

export default function SupplyTechnicalComparisonPanel({
  API = '',
  C = {},
  enabled = DEFAULT_ENABLED,
  allowedCompanyIds = DEFAULT_ALLOWED_COMPANY_IDS,
  companyContext = {},
  projectId,
  requestId,
  sourceKind,
  sourceId,
  fileId,
}) {
  const companyId = companyContext?.selectedCompanyId || companyContext?.selectedCompany?.companyId;
  const role = companyContext?.selectedCompany?.role || '';
  const allowed = (
    enabled === true
    && companyContext?.mode === 'company'
    && positiveId(companyId)
    && allowedCompanyIds instanceof Set
    && allowedCompanyIds.has(companyId)
    && ALLOWED_ROLES.has(role)
    && positiveId(projectId)
    && positiveId(requestId)
    && SOURCE_KINDS.has(sourceKind)
    && positiveId(sourceId)
    && positiveId(fileId)
  );
  const scopeKey = [allowed ? 'allowed' : 'blocked', companyId, role, projectId, requestId, sourceKind, sourceId, fileId].join(':');
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState('');
  const [result, setResult] = React.useState(null);
  const controllerRef = React.useRef(null);

  React.useEffect(() => {
    controllerRef.current?.abort();
    controllerRef.current = null;
    setLoading(false);
    setError('');
    setResult(null);
    return () => controllerRef.current?.abort();
  }, [scopeKey]);

  const loadComparison = async () => {
    if (!allowed || loading) return;
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    const selectors = { companyId, projectId, requestId, sourceKind, sourceId, fileId };
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const response = await fetch(
        `${API || ''}/supply-requests/${requestId}/technical-comparisons/${sourceKind}/${sourceId}?projectId=${projectId}&fileId=${fileId}`,
        { credentials: 'include', cache: 'no-store', signal: controller.signal },
      );
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error('request_failed');
      const normalized = normalizeReport(body, selectors);
      if (!normalized) throw new Error('response_invalid');
      if (!controller.signal.aborted) setResult(normalized);
    } catch (requestError) {
      if (!controller.signal.aborted) {
        setError('Сервер не подтвердил безопасный результат. Повторите проверку.');
      }
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false);
        controllerRef.current = null;
      }
    }
  };

  if (!allowed) return null;

  return (
    <section
      aria-label="Проверка характеристик предложения"
      style={{
        marginTop: '8px', padding: '9px 10px', borderRadius: '7px',
        border: `1px solid ${C.infoBorder || C.border || '#ccc'}`,
        backgroundColor: C.infoLight || C.bg || '#f7f7f7',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', flexWrap: 'wrap' }}>
        <div>
          <b style={{ color: C.text || '#111', fontSize: '11px' }}>Техническое соответствие</b>
          <div style={{ color: C.textSec || '#555', fontSize: '10px', marginTop: '2px' }}>
            Только проверка. Поставщик не выбирается.
          </div>
        </div>
        <button
          type="button"
          onClick={loadComparison}
          disabled={loading}
          style={{
            border: `1px solid ${C.infoBorder || C.border || '#ccc'}`,
            borderRadius: '6px', padding: '5px 9px', cursor: loading ? 'default' : 'pointer',
            color: C.info || C.text || '#111', backgroundColor: C.bgWhite || '#fff',
            fontSize: '11px', opacity: loading ? 0.65 : 1,
          }}
        >
          {loading ? 'Проверяю...' : 'Проверить характеристики'}
        </button>
      </div>

      {error && <p role="alert" style={{ color: C.danger || '#c92a2a', fontSize: '10px', margin: '7px 0 0' }}>{error}</p>}

      {result && (
        <div style={{ display: 'grid', gap: '6px', marginTop: '8px' }}>
          {result.comparisons.map(item => {
            const [color, backgroundColor, borderColor] = decisionColors(item.result.decision, C);
            return (
              <div key={item.lineNumber} style={{ padding: '8px', borderRadius: '6px', border: `1px solid ${borderColor}`, backgroundColor }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', flexWrap: 'wrap' }}>
                  <b style={{ color, fontSize: '11px' }}>{DECISION_LABELS[item.result.decision]}</b>
                  <span style={{ color, fontSize: '10px', fontWeight: 700 }}>{Math.round(item.result.confidenceBasisPoints / 100)}%</span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: '5px', marginTop: '5px', fontSize: '10px' }}>
                  <span style={{ color: C.textSec || '#555' }}>Нужно: <b style={{ color: C.text || '#111' }}>{item.required.name}</b></span>
                  <span style={{ color: C.textSec || '#555' }}>Предложено: <b style={{ color: C.text || '#111' }}>{item.offered.name}</b></span>
                </div>
                {item.result.reasonCodes.map(code => (
                  <p key={code} style={{ color: C.textSec || '#555', fontSize: '10px', margin: '4px 0 0' }}>{REASON_LABELS[code]}</p>
                ))}
              </div>
            );
          })}
          <p style={{ color: C.textMuted || '#777', fontSize: '9px', margin: 0 }}>
            Записей не создано · модель не вызывалась · итоговое решение остаётся за сотрудником.
          </p>
        </div>
      )}
    </section>
  );
}
