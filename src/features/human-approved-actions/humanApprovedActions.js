const ACTION_KIND = 'warehouse_anomaly_review_acknowledged';
const UI_INPUT_INVALID = 'human_approved_action_ui_input_invalid';
const UI_RESPONSE_INVALID = 'human_approved_action_ui_response_invalid';
const MAX_ID = Number.MAX_SAFE_INTEGER;
const SHA256_RE = /^[0-9a-f]{64}$/;
const TIMESTAMP_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$/;

export const HUMAN_ACTION_ANOMALIES = Object.freeze({
  warehouse_invoice_request_mismatch: Object.freeze({
    subjectKind: 'warehouseInvoice',
    recommendationCode: 'review_warehouse_invoice_lineage',
    label: 'Накладная связана не с той заявкой',
  }),
  warehouse_invoice_project_mismatch: Object.freeze({
    subjectKind: 'warehouseInvoice',
    recommendationCode: 'review_warehouse_invoice_lineage',
    label: 'Накладная относится к другому объекту',
  }),
  warehouse_invoice_delivery_mismatch: Object.freeze({
    subjectKind: 'warehouseInvoice',
    recommendationCode: 'review_warehouse_invoice_lineage',
    label: 'Накладная связана не с той поставкой',
  }),
  warehouse_invoice_supplier_invoice_mismatch: Object.freeze({
    subjectKind: 'warehouseInvoice',
    recommendationCode: 'review_warehouse_invoice_lineage',
    label: 'Накладная связана не с тем документом поставщика',
  }),
  warehouse_invoice_items_invalid: Object.freeze({
    subjectKind: 'warehouseInvoice',
    recommendationCode: 'review_warehouse_invoice_items',
    label: 'Строки складской накладной требуют проверки',
  }),
  warehouse_receipt_invoice_mismatch: Object.freeze({
    subjectKind: 'warehouseHistory',
    recommendationCode: 'review_warehouse_receipt_lineage',
    label: 'Приход связан не с той накладной',
  }),
  warehouse_receipt_line_invalid: Object.freeze({
    subjectKind: 'warehouseHistory',
    recommendationCode: 'review_warehouse_receipt_lineage',
    label: 'Строка источника прихода некорректна',
  }),
  warehouse_receipt_package_mismatch: Object.freeze({
    subjectKind: 'warehouseHistory',
    recommendationCode: 'review_warehouse_receipt_lineage',
    label: 'Пакет работ прихода не совпадает',
  }),
  warehouse_receipt_lot_invoice_mismatch: Object.freeze({
    subjectKind: 'receiptLot',
    recommendationCode: 'review_receipt_lot_lineage',
    label: 'Партия прихода связана не с той накладной',
  }),
  warehouse_receipt_lot_line_invalid: Object.freeze({
    subjectKind: 'receiptLot',
    recommendationCode: 'review_receipt_lot_lineage',
    label: 'Строка источника партии некорректна',
  }),
  warehouse_receipt_lot_project_mismatch: Object.freeze({
    subjectKind: 'receiptLot',
    recommendationCode: 'review_receipt_lot_lineage',
    label: 'Партия прихода относится к другому объекту',
  }),
  warehouse_movement_invoice_mismatch: Object.freeze({
    subjectKind: 'warehouseMovement',
    recommendationCode: 'review_warehouse_movement_lineage',
    label: 'Движение связано не с той накладной',
  }),
  warehouse_movement_line_invalid: Object.freeze({
    subjectKind: 'warehouseMovement',
    recommendationCode: 'review_warehouse_movement_lineage',
    label: 'Строка источника движения некорректна',
  }),
  warehouse_movement_package_mismatch: Object.freeze({
    subjectKind: 'warehouseMovement',
    recommendationCode: 'review_warehouse_movement_lineage',
    label: 'Пакет работ движения не совпадает',
  }),
  warehouse_movement_lot_missing: Object.freeze({
    subjectKind: 'warehouseMovement',
    recommendationCode: 'review_warehouse_movement_traceability',
    label: 'У движения отсутствует связь с партией',
  }),
  warehouse_lot_movement_missing: Object.freeze({
    subjectKind: 'warehouseMovement',
    recommendationCode: 'review_warehouse_movement_traceability',
    label: 'Для партии не найдено складское движение',
  }),
  warehouse_lot_movement_parent_mismatch: Object.freeze({
    subjectKind: 'lotMovement',
    recommendationCode: 'review_lot_movement_lineage',
    label: 'Родительская связь события партии не совпадает',
  }),
  warehouse_lot_movement_source_mismatch: Object.freeze({
    subjectKind: 'lotMovement',
    recommendationCode: 'review_lot_movement_lineage',
    label: 'Источник события партии не совпадает',
  }),
});

const PREVIEW_FIELDS = new Set([
  'warehouseAnomalyRuntimeVersion', 'ok', 'dryRun', 'writesAttempted',
  'previewOnly', 'stockMovementAllowed', 'inventoryAdjustmentAllowed',
  'applyAllowed', 'state', 'candidate', 'content', 'blockers',
  'readOnlyTransaction', 'rolledBack',
]);
const CANDIDATE_FIELDS = new Set([
  'subjectKind', 'subjectId', 'anomalyCode', 'recommendationCode',
]);
const CONTENT_FIELDS = new Set(['title', 'finding', 'nextSafeAction']);
const PROPOSAL_FIELDS = new Set([
  'humanActionReceiptVersion', 'state', 'actionKind', 'proposalId',
  'proposalSha256', 'companyId', 'projectId', 'sourceJobId', 'subjectKind',
  'subjectId', 'actorUserId', 'actorMembershipId', 'expiresAt',
  'writesAttempted', 'committed', 'idempotent',
]);
const DECISION_FIELDS = new Set([
  'humanActionReceiptVersion', 'state', 'actionKind', 'proposalId',
  'proposalSha256', 'companyId', 'projectId', 'sourceJobId', 'subjectKind',
  'subjectId', 'actorUserId', 'actorMembershipId', 'eventId', 'auditEventId',
  'writesAttempted', 'committed', 'idempotent',
]);

const plainObject = value => (
  value !== null
  && typeof value === 'object'
  && !Array.isArray(value)
  && Object.getPrototypeOf(value) === Object.prototype
);
const exactKeys = (value, fields) => {
  const keys = Object.keys(value);
  return keys.length === fields.size && keys.every(key => fields.has(key));
};
const positiveId = value => Number.isSafeInteger(value) && value > 0 && value <= MAX_ID;
const canonicalPositiveIdText = value => (
  typeof value === 'string'
  && /^[1-9][0-9]*$/.test(value)
  && positiveId(Number(value))
);
const fixedText = value => typeof value === 'string' && value.length > 0 && value.length <= 1000;
const failInput = () => { throw new Error(UI_INPUT_INVALID); };
const failResponse = () => { throw new Error(UI_RESPONSE_INVALID); };
const detached = value => JSON.parse(JSON.stringify(value));

export const parseHumanApprovedActionCompanyIds = raw => {
  if (!canonicalPositiveIdText(raw)) return null;
  return new Set([Number(raw)]);
};

export const buildHumanActionSource = ({ projectId, jobId, subjectId, anomalyCode }) => {
  const anomaly = HUMAN_ACTION_ANOMALIES[anomalyCode];
  if (
    !canonicalPositiveIdText(projectId)
    || !canonicalPositiveIdText(jobId)
    || !canonicalPositiveIdText(subjectId)
    || !anomaly
  ) failInput();
  return {
    projectId: Number(projectId),
    jobId: Number(jobId),
    selected: {
      subjectKind: anomaly.subjectKind,
      subjectId: Number(subjectId),
      anomalyCode,
    },
  };
};

const sameSelection = (left, right) => (
  left.subjectKind === right.subjectKind
  && left.subjectId === right.subjectId
  && left.anomalyCode === right.anomalyCode
);

export const humanActionSourceKey = source => JSON.stringify(source);

export const validateWarehouseAnomalyPreview = (value, source) => {
  if (
    !plainObject(value)
    || !plainObject(source)
    || !plainObject(source.selected)
    || !exactKeys(value, PREVIEW_FIELDS)
    || value.warehouseAnomalyRuntimeVersion !== 1
    || value.ok !== true
    || value.dryRun !== true
    || value.writesAttempted !== 0
    || value.previewOnly !== true
    || value.stockMovementAllowed !== false
    || value.inventoryAdjustmentAllowed !== false
    || value.applyAllowed !== false
    || value.readOnlyTransaction !== true
    || value.rolledBack !== true
    || !['preview_ready', 'blocked', 'stale'].includes(value.state)
    || !plainObject(value.candidate)
    || !exactKeys(value.candidate, CANDIDATE_FIELDS)
    || !sameSelection(value.candidate, source.selected)
  ) failResponse();
  const anomaly = HUMAN_ACTION_ANOMALIES[value.candidate.anomalyCode];
  if (
    !anomaly
    || anomaly.subjectKind !== value.candidate.subjectKind
    || anomaly.recommendationCode !== value.candidate.recommendationCode
  ) failResponse();
  if (value.state === 'preview_ready') {
    if (
      !plainObject(value.content)
      || !exactKeys(value.content, CONTENT_FIELDS)
      || !Object.values(value.content).every(fixedText)
      || !Array.isArray(value.blockers)
      || value.blockers.length !== 0
    ) failResponse();
  } else {
    const blocker = value.state === 'blocked'
      ? 'warehouse_anomaly_preview_blocked'
      : 'warehouse_anomaly_preview_stale';
    if (value.content !== null || !Array.isArray(value.blockers) || value.blockers.length !== 1 || value.blockers[0] !== blocker) {
      failResponse();
    }
  }
  return detached(value);
};

const validBaseReceipt = (value, fields, companyId) => (
  plainObject(value)
  && exactKeys(value, fields)
  && value.humanActionReceiptVersion === 1
  && value.actionKind === ACTION_KIND
  && value.companyId === companyId
  && ['proposalId', 'companyId', 'projectId', 'sourceJobId', 'subjectId', 'actorUserId', 'actorMembershipId']
    .every(field => positiveId(value[field]))
  && typeof value.subjectKind === 'string'
  && SHA256_RE.test(value.proposalSha256)
  && Number.isSafeInteger(value.writesAttempted)
  && value.writesAttempted >= 0
  && value.committed === true
  && typeof value.idempotent === 'boolean'
);

export const validateHumanActionProposalReceipt = (value, companyId, source) => {
  if (
    !validBaseReceipt(value, PROPOSAL_FIELDS, companyId)
    || value.state !== 'proposed'
    || value.projectId !== source.projectId
    || value.sourceJobId !== source.jobId
    || value.subjectKind !== source.selected.subjectKind
    || value.subjectId !== source.selected.subjectId
    || !TIMESTAMP_RE.test(value.expiresAt)
    || !Number.isFinite(Date.parse(value.expiresAt))
    || ![0, 2].includes(value.writesAttempted)
    || value.idempotent !== (value.writesAttempted === 0)
  ) failResponse();
  return detached(value);
};

export const validateHumanActionDecisionReceipt = (value, companyId, proposal) => {
  if (
    !validBaseReceipt(value, DECISION_FIELDS, companyId)
    || !['applied', 'rejected'].includes(value.state)
    || value.proposalId !== proposal.proposalId
    || value.proposalSha256 !== proposal.proposalSha256
    || value.projectId !== proposal.projectId
    || value.sourceJobId !== proposal.sourceJobId
    || value.subjectKind !== proposal.subjectKind
    || value.subjectId !== proposal.subjectId
    || !positiveId(value.eventId)
    || (value.state === 'applied' ? !positiveId(value.auditEventId) : value.auditEventId !== null)
    || ![0, 1, 3].includes(value.writesAttempted)
    || value.idempotent !== (value.writesAttempted === 0)
  ) failResponse();
  return detached(value);
};

export const humanActionProposalExpired = (proposal, nowMs) => (
  !proposal || !Number.isFinite(nowMs) || nowMs >= Date.parse(proposal.expiresAt)
);
