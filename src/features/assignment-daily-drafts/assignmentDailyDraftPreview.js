const TOP_KEYS = [
  'version', 'state', 'companyId', 'projectId', 'date', 'assignmentDraft',
  'dailyWorkDraft', 'review', 'previewOnly', 'applyAllowed', 'writesAttempted',
  'readOnlyTransaction', 'rolledBack',
];
const ASSIGNMENT_KEYS = ['state', 'items', 'summary', 'review'];
const ASSIGNMENT_ITEM_KEYS = [
  'sourceEstimateId', 'sourceEstimateVersionId', 'sectionIndex', 'itemIndex',
  'itemKey', 'sectionName', 'itemName', 'unit', 'estimateQuantity',
  'assignedQuantity', 'availableQuantity', 'workPackage', 'assignee',
];
const ASSIGNMENT_SUMMARY_KEYS = ['sourceWorkRows', 'availableRows', 'fullyAssignedRows'];
const DAILY_KEYS = ['state', 'items', 'summary', 'review'];
const DAILY_ITEM_KEYS = [
  'sourceId', 'description', 'unit', 'quantity', 'responsibleId',
  'responsibleName', 'workPackage', 'status',
];
const DAILY_SUMMARY_KEYS = ['confirmedRows', 'workPackages', 'responsiblePeople'];
const STATES = new Set(['ready', 'clear', 'review_required']);
const REVIEW_CODES = new Set([
  'assignment_snapshot_source_not_found',
  'assignment_snapshot_source_ambiguous',
  'assignment_snapshot_payload_too_large',
  'assignment_snapshot_project_ambiguous',
  'assignment_snapshot_version_stale',
  'assignment_snapshot_source_invalid',
  'assignment_snapshot_lineage_invalid',
  'assignment_source_invalid',
  'assignment_source_duplicate',
  'assignment_lineage_invalid',
  'assignment_balance_invalid',
  'assignment_draft_scan_limit_exceeded',
  'daily_work_source_invalid',
  'daily_work_source_duplicate',
  'daily_work_scan_limit_exceeded',
]);

const invalid = () => {
  throw new Error('assignment_daily_preview_invalid');
};

const isRecord = value => value !== null
  && typeof value === 'object'
  && !Array.isArray(value)
  && Object.getPrototypeOf(value) === Object.prototype;

const exactKeys = (value, keys) => isRecord(value)
  && Object.keys(value).length === keys.length
  && keys.every(key => Object.prototype.hasOwnProperty.call(value, key));

const positiveId = value => Number.isSafeInteger(value) && value > 0;
const nonNegativeInt = value => Number.isSafeInteger(value) && value >= 0;
const boundedString = (value, max = 4096, { allowEmpty = false } = {}) => (
  typeof value === 'string'
  && value.length <= max
  && (allowEmpty || value.length > 0)
);
const decimalString = value => boundedString(value, 64)
  && /^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/.test(value);
const canonicalDate = value => {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(value + 'T00:00:00Z');
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
};

const validateReviews = value => {
  if (!Array.isArray(value) || value.length !== new Set(value).size) invalid();
  value.forEach(code => {
    if (typeof code !== 'string' || !REVIEW_CODES.has(code)) invalid();
  });
  return [...value];
};

const validateAssignment = (value, expected) => {
  if (!exactKeys(value, ASSIGNMENT_KEYS) || !STATES.has(value.state) || !Array.isArray(value.items)) invalid();
  if (value.items.length > 100 || !exactKeys(value.summary, ASSIGNMENT_SUMMARY_KEYS)) invalid();
  const review = validateReviews(value.review);
  const items = value.items.map(item => {
    if (!exactKeys(item, ASSIGNMENT_ITEM_KEYS)) invalid();
    if (
      !positiveId(item.sourceEstimateId)
      || !positiveId(item.sourceEstimateVersionId)
      || item.sourceEstimateId !== expected.estimateId
      || item.sourceEstimateVersionId !== expected.estimateVersionId
      || !nonNegativeInt(item.sectionIndex)
      || !nonNegativeInt(item.itemIndex)
      || !boundedString(item.itemKey, 512)
      || !boundedString(item.sectionName, 1024)
      || !boundedString(item.itemName, 4096)
      || !boundedString(item.unit, 128)
      || !decimalString(item.estimateQuantity)
      || !decimalString(item.assignedQuantity)
      || !decimalString(item.availableQuantity)
      || !boundedString(item.workPackage, 1024)
      || item.workPackage !== expected.workPackage
      || item.assignee !== null
    ) invalid();
    return { ...item };
  });
  const summary = value.summary;
  if (!ASSIGNMENT_SUMMARY_KEYS.every(key => nonNegativeInt(summary[key]))) invalid();
  if (
    summary.availableRows !== items.length
    || summary.sourceWorkRows !== summary.availableRows + summary.fullyAssignedRows
  ) invalid();
  if (
    (value.state === 'ready' && (items.length === 0 || review.length !== 0))
    || (value.state === 'clear' && (items.length !== 0 || review.length !== 0))
    || (value.state === 'review_required' && (items.length !== 0 || review.length === 0))
  ) invalid();
  return { state: value.state, items, summary: { ...summary }, review };
};

const validateDaily = value => {
  if (!exactKeys(value, DAILY_KEYS) || !STATES.has(value.state) || !Array.isArray(value.items)) invalid();
  if (value.items.length > 100 || !exactKeys(value.summary, DAILY_SUMMARY_KEYS)) invalid();
  const review = validateReviews(value.review);
  const items = value.items.map(item => {
    if (!exactKeys(item, DAILY_ITEM_KEYS)) invalid();
    if (
      !positiveId(item.sourceId)
      || (item.responsibleId !== null && !positiveId(item.responsibleId))
      || !boundedString(item.description, 4096)
      || !boundedString(item.unit, 128)
      || !decimalString(item.quantity)
      || !boundedString(item.responsibleName, 512, { allowEmpty: true })
      || (item.responsibleId === null && item.responsibleName.length === 0)
      || !boundedString(item.workPackage, 1024)
      || item.status !== 'Подтверждено'
    ) invalid();
    return { ...item };
  });
  const summary = value.summary;
  if (!DAILY_SUMMARY_KEYS.every(key => nonNegativeInt(summary[key]))) invalid();
  if (
    summary.confirmedRows !== items.length
    || summary.workPackages > summary.confirmedRows
    || summary.responsiblePeople > summary.confirmedRows
  ) invalid();
  if (
    (value.state === 'ready' && (items.length === 0 || review.length !== 0))
    || (value.state === 'clear' && (items.length !== 0 || review.length !== 0))
    || (value.state === 'review_required' && (items.length !== 0 || review.length === 0))
  ) invalid();
  return { state: value.state, items, summary: { ...summary }, review };
};

export const validateAssignmentDailyDraftPreview = (value, expected) => {
  if (
    !exactKeys(value, TOP_KEYS)
    || !isRecord(expected)
    || value.version !== 1
    || !STATES.has(value.state)
    || !positiveId(value.companyId)
    || !positiveId(value.projectId)
    || value.companyId !== expected.companyId
    || value.projectId !== expected.projectId
    || value.date !== expected.date
    || !canonicalDate(value.date)
    || value.previewOnly !== true
    || value.applyAllowed !== false
    || value.writesAttempted !== 0
    || value.readOnlyTransaction !== true
    || value.rolledBack !== true
  ) invalid();
  const assignmentDraft = validateAssignment(value.assignmentDraft, expected);
  const dailyWorkDraft = validateDaily(value.dailyWorkDraft);
  const review = validateReviews(value.review);
  if (
    (value.state === 'ready' && (
      review.length !== 0
      || assignmentDraft.state === 'review_required'
      || dailyWorkDraft.state === 'review_required'
      || (assignmentDraft.state !== 'ready' && dailyWorkDraft.state !== 'ready')
    ))
    || (value.state === 'clear' && (
      review.length !== 0
      || assignmentDraft.state !== 'clear'
      || dailyWorkDraft.state !== 'clear'
    ))
    || (value.state === 'review_required' && (
      review.length === 0
      && assignmentDraft.state !== 'review_required'
      && dailyWorkDraft.state !== 'review_required'
    ))
  ) invalid();
  return {
    version: 1,
    state: value.state,
    companyId: value.companyId,
    projectId: value.projectId,
    date: value.date,
    assignmentDraft,
    dailyWorkDraft,
    review,
    previewOnly: true,
    applyAllowed: false,
    writesAttempted: 0,
    readOnlyTransaction: true,
    rolledBack: true,
  };
};

export const escapeAssignmentDailyDraftHtml = value => String(value ?? '')
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#39;');

const tableRows = (items, columns) => items.length === 0
  ? `<tr><td colspan="${columns.length}">Нет строк</td></tr>`
  : items.map(item => `<tr>${columns.map(column => `<td>${escapeAssignmentDailyDraftHtml(item[column.key])}</td>`).join('')}</tr>`).join('');

const table = (title, items, columns) => `
  <section>
    <h2>${escapeAssignmentDailyDraftHtml(title)}</h2>
    <table>
      <thead><tr>${columns.map(column => `<th>${escapeAssignmentDailyDraftHtml(column.label)}</th>`).join('')}</tr></thead>
      <tbody>${tableRows(items, columns)}</tbody>
    </table>
  </section>`;

const REVIEW_LABELS = {
  assignment_snapshot_source_not_found: 'Сохранённая версия сметы не найдена',
  assignment_snapshot_source_ambiguous: 'Источник сметы неоднозначен',
  assignment_snapshot_payload_too_large: 'Источник сметы слишком большой',
  assignment_snapshot_project_ambiguous: 'Проект сметы неоднозначен',
  assignment_snapshot_version_stale: 'Версия сметы устарела',
  assignment_snapshot_source_invalid: 'Источник сметы некорректен',
  assignment_snapshot_lineage_invalid: 'Связи строк сметы некорректны',
  assignment_source_invalid: 'Строки сметы требуют проверки',
  assignment_source_duplicate: 'В смете найдены дубли строк',
  assignment_lineage_invalid: 'Связи назначений требуют проверки',
  assignment_balance_invalid: 'Баланс назначенных объёмов некорректен',
  assignment_draft_scan_limit_exceeded: 'Строк для назначения слишком много',
  daily_work_source_invalid: 'Подтверждённые работы требуют проверки',
  daily_work_source_duplicate: 'Найдены дубли подтверждённых работ',
  daily_work_scan_limit_exceeded: 'Подтверждённых работ слишком много',
};

export const assignmentDailyReviewLabel = code => REVIEW_LABELS[code] || 'Данные требуют проверки';

export const buildAssignmentDailyDraftPrintContent = (preview, context) => {
  const warnings = Array.from(new Set([
    ...(preview.review || []),
    ...(preview.assignmentDraft?.review || []),
    ...(preview.dailyWorkDraft?.review || []),
  ]));
  return `
    <article>
      <h1>Черновик назначений и подтверждённых работ</h1>
      <p><b>Объект:</b> ${escapeAssignmentDailyDraftHtml(context.projectName)}</p>
      <p><b>Дата:</b> ${escapeAssignmentDailyDraftHtml(preview.date)}</p>
      <p><b>Смета:</b> ${escapeAssignmentDailyDraftHtml(context.estimateName)} · версия ${escapeAssignmentDailyDraftHtml(context.versionLabel)}</p>
      <p><b>Статус:</b> только предпросмотр, изменения не выполнялись</p>
      ${warnings.length ? `<section><h2>Требует проверки</h2><ul>${warnings.map(code => `<li>${escapeAssignmentDailyDraftHtml(assignmentDailyReviewLabel(code))}</li>`).join('')}</ul></section>` : ''}
      ${table('Доступно к назначению', preview.assignmentDraft.items, [
        { key: 'sectionName', label: 'Раздел' },
        { key: 'itemName', label: 'Работа' },
        { key: 'unit', label: 'Ед.' },
        { key: 'estimateQuantity', label: 'По смете' },
        { key: 'assignedQuantity', label: 'Уже назначено' },
        { key: 'availableQuantity', label: 'Остаток' },
        { key: 'workPackage', label: 'Пакет работ' },
      ])}
      ${table('Подтверждённые работы за день', preview.dailyWorkDraft.items, [
        { key: 'description', label: 'Работа' },
        { key: 'unit', label: 'Ед.' },
        { key: 'quantity', label: 'Объём' },
        { key: 'responsibleName', label: 'Ответственный' },
        { key: 'workPackage', label: 'Пакет работ' },
      ])}
    </article>`;
};
