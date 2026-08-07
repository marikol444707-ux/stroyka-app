const PLAN_SHA256_RE = /^[0-9a-f]{64}$/;
const MONEY_RE = /^(?:0|[1-9]\d{0,11})\.\d{2}$/;
const SIGNED_MONEY_RE = /^-?(?:0|[1-9]\d{0,11})\.\d{2}$/;
const PUBLIC_ERROR_RE = /^budget_adjustment_[a-z0-9_]{1,80}$/;
const LEADERSHIP_ROLES = new Set(['директор', 'зам_директора']);

const ERROR_MESSAGES = {
  budget_adjustment_already_applied:'Изменение бюджета уже применено. Обновите историю.',
  budget_adjustment_company_context_ambiguous:'Выберите одну компанию и повторите попытку.',
  budget_adjustment_not_found:'Сверка не найдена или недоступна.',
  budget_adjustment_plan_stale:'Расчёт устарел. Обновите предварительный расчёт и подтвердите его заново.',
  budget_adjustment_project_not_found:'Объект не найден или недоступен.',
  budget_adjustment_reconciliation_not_approved:'Сначала утвердите сверку смет.',
  budget_adjustment_request_failed:'Не удалось выполнить операцию с бюджетом. Повторите попытку.',
  budget_adjustment_response_invalid:'Сервер вернул некорректный расчёт. Изменение бюджета не выполнено.',
  budget_adjustment_role_forbidden:'Недостаточно прав для изменения бюджета.',
  budget_adjustment_schema_not_ready:'Изменение бюджета временно недоступно.',
  budget_adjustment_source_drift:'Данные смет изменились. Обновите сверку и расчёт.',
  budget_adjustment_write_conflict:'Бюджет изменился параллельно. Обновите расчёт и повторите подтверждение.',
  budget_adjustment_zero_delta:'Итоги редакций совпадают — изменение бюджета не требуется.',
};

const positiveInt = (value) => (
  Number.isInteger(value) && value > 0 ? value : null
);

const moneyToCents = (value, {signed = false} = {}) => {
  if (typeof value !== 'string' || !(signed ? SIGNED_MONEY_RE : MONEY_RE).test(value)) return null;
  if (value === '-0.00') return null;
  const negative = value.startsWith('-');
  const [whole, decimal] = (negative ? value.slice(1) : value).split('.');
  const cents = BigInt(whole) * 100n + BigInt(decimal);
  return negative ? -cents : cents;
};

const safeText = (value, maxLength) => (
  typeof value === 'string' && value.trim() && value.length <= maxLength
    ? value
    : null
);

const validTimestamp = (value) => {
  const text = safeText(value, 64);
  return text && Number.isFinite(Date.parse(text)) ? text : null;
};

const invalidResponse = () => {
  throw new BudgetAdjustmentClientError('budget_adjustment_response_invalid');
};

const normalizeMoneyEvidence = (source) => {
  const projectBudgetBefore = typeof source?.projectBudgetBefore === 'string' ? source.projectBudgetBefore : '';
  const estimateBaseTotal = typeof source?.estimateBaseTotal === 'string' ? source.estimateBaseTotal : '';
  const estimateNextTotal = typeof source?.estimateNextTotal === 'string' ? source.estimateNextTotal : '';
  const adjustmentAmount = typeof source?.adjustmentAmount === 'string' ? source.adjustmentAmount : '';
  const projectBudgetAfter = typeof source?.projectBudgetAfter === 'string' ? source.projectBudgetAfter : '';
  const before = moneyToCents(projectBudgetBefore);
  const base = moneyToCents(estimateBaseTotal);
  const next = moneyToCents(estimateNextTotal);
  const adjustment = moneyToCents(adjustmentAmount, {signed:true});
  const after = moneyToCents(projectBudgetAfter);
  if (
    before === null || base === null || next === null || adjustment === null || after === null
    || next - base !== adjustment || before + adjustment !== after
  ) invalidResponse();
  return {
    projectBudgetBefore,
    estimateBaseTotal,
    estimateNextTotal,
    adjustmentAmount,
    projectBudgetAfter,
  };
};

const normalizeIdentity = (source) => {
  const identity = {};
  for (const key of ['reconciliationId', 'companyId', 'projectId', 'baseEstimateId', 'nextEstimateId']) {
    identity[key] = positiveInt(source?.[key]);
    if (!identity[key]) invalidResponse();
  }
  if (identity.baseEstimateId === identity.nextEstimateId) invalidResponse();
  return identity;
};

export class BudgetAdjustmentClientError extends Error {
  constructor(code = 'budget_adjustment_request_failed', status = 0) {
    super(code);
    this.name = 'BudgetAdjustmentClientError';
    this.code = code;
    this.status = status;
  }
}

export const budgetAdjustmentErrorMessage = (error) => (
  ERROR_MESSAGES[error?.code] || ERROR_MESSAGES.budget_adjustment_request_failed
);

export const normalizeBudgetAdjustmentPreview = (source) => {
  const identity = normalizeIdentity(source);
  const money = normalizeMoneyEvidence(source);
  const planSha256 = typeof source?.planSha256 === 'string' && PLAN_SHA256_RE.test(source.planSha256)
    ? source.planSha256
    : null;
  const blockers = Array.isArray(source?.blockers) && source.blockers.length <= 10
    ? source.blockers.filter(code => typeof code === 'string' && PUBLIC_ERROR_RE.test(code))
    : null;
  if (!planSha256 || typeof source?.readyForApproval !== 'boolean' || !blockers || blockers.length !== source.blockers.length) {
    invalidResponse();
  }
  if (source.readyForApproval !== (blockers.length === 0)) invalidResponse();
  return {...identity, ...money, planSha256, readyForApproval:source.readyForApproval, blockers};
};

export const normalizeBudgetAdjustmentReceipt = (source, {allowIdempotent = true} = {}) => {
  const id = positiveInt(source?.id);
  const identity = normalizeIdentity(source);
  const money = normalizeMoneyEvidence(source);
  const planSha256 = typeof source?.planSha256 === 'string' && PLAN_SHA256_RE.test(source.planSha256)
    ? source.planSha256
    : null;
  const approvedByUserId = positiveInt(source?.approvedByUserId);
  const approvedByName = safeText(source?.approvedByName, 255);
  const approvedByRole = safeText(source?.approvedByRole, 64);
  const approvedAt = validTimestamp(source?.approvedAt);
  const createdAt = validTimestamp(source?.createdAt);
  if (
    !id || !planSha256 || !approvedByUserId || !approvedByName || !approvedByRole
    || !LEADERSHIP_ROLES.has(approvedByRole) || !approvedAt || !createdAt
  ) invalidResponse();
  const result = {
    id,
    ...identity,
    ...money,
    planSha256,
    approvedByUserId,
    approvedByName,
    approvedByRole,
    approvedAt,
    createdAt,
  };
  if (allowIdempotent && typeof source?.idempotent === 'boolean') result.idempotent = source.idempotent;
  return result;
};

const responseError = async (response) => {
  let detail = '';
  try {
    const body = await response.json();
    detail = typeof body?.detail === 'string' ? body.detail : '';
  } catch (_error) {}
  const code = PUBLIC_ERROR_RE.test(detail) ? detail : 'budget_adjustment_request_failed';
  return new BudgetAdjustmentClientError(code, response?.status || 0);
};

const readJson = async (response) => {
  try {
    return await response.json();
  } catch (_error) {
    invalidResponse();
  }
};

export function createProjectBudgetAdjustmentActions({
  API = '',
  apiAuthHeaders = (headers = {}) => headers,
  fetchFn = fetch,
}) {
  const request = async (path, init) => {
    let response;
    try {
      response = await fetchFn(API + path, init);
    } catch (error) {
      if (error instanceof BudgetAdjustmentClientError) throw error;
      throw new BudgetAdjustmentClientError('budget_adjustment_request_failed');
    }
    if (!response?.ok) throw await responseError(response);
    return readJson(response);
  };

  const loadBudgetAdjustmentPreview = async (reconciliationId) => {
    const id = positiveInt(reconciliationId);
    if (!id) throw new BudgetAdjustmentClientError('budget_adjustment_identity_invalid');
    const body = await request(
      `/estimate-reconciliations/${id}/budget-adjustment-preview`,
      {headers:apiAuthHeaders()},
    );
    const result = normalizeBudgetAdjustmentPreview(body);
    if (result.reconciliationId !== id) invalidResponse();
    return result;
  };

  const approveProjectBudgetAdjustment = async (reconciliationId, planSha256) => {
    const id = positiveInt(reconciliationId);
    if (!id) throw new BudgetAdjustmentClientError('budget_adjustment_identity_invalid');
    if (typeof planSha256 !== 'string' || !PLAN_SHA256_RE.test(planSha256)) {
      throw new BudgetAdjustmentClientError('budget_adjustment_plan_hash_invalid');
    }
    const body = await request(
      `/estimate-reconciliations/${id}/budget-adjustment-approval`,
      {
        method:'POST',
        headers:apiAuthHeaders({'Content-Type':'application/json'}),
        body:JSON.stringify({planSha256}),
      },
    );
    const result = normalizeBudgetAdjustmentReceipt(body);
    if (result.reconciliationId !== id) invalidResponse();
    return result;
  };

  const loadProjectBudgetAdjustments = async (projectId, {limit = 25, beforeId = null} = {}) => {
    const id = positiveInt(projectId);
    const pageSize = positiveInt(limit);
    const cursor = beforeId === null ? null : positiveInt(beforeId);
    if (!id || !pageSize || pageSize > 100 || (beforeId !== null && !cursor)) {
      throw new BudgetAdjustmentClientError('budget_adjustment_history_query_invalid');
    }
    const query = new URLSearchParams({limit:String(pageSize)});
    if (cursor) query.set('beforeId', String(cursor));
    const body = await request(
      `/projects/${id}/budget-adjustments?${query.toString()}`,
      {headers:apiAuthHeaders()},
    );
    const responseProjectId = positiveInt(body?.projectId);
    const items = Array.isArray(body?.items) && body.items.length <= pageSize
      ? body.items.map(item => normalizeBudgetAdjustmentReceipt(item, {allowIdempotent:false}))
      : null;
    const nextBeforeId = body?.nextBeforeId === null ? null : positiveInt(body?.nextBeforeId);
    if (responseProjectId !== id || !items || (body?.nextBeforeId !== null && !nextBeforeId)) invalidResponse();
    return {projectId:id, items, nextBeforeId};
  };

  return {
    approveProjectBudgetAdjustment,
    loadBudgetAdjustmentPreview,
    loadProjectBudgetAdjustments,
  };
}
