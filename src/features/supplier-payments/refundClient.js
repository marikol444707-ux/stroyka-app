import { paymentKopecks } from '../../utils/paymentMoney';
import { paymentPath, paymentRequest } from './paymentClient';
const fail = message => { throw new Error(message); };
const id = value => Number.isSafeInteger(value) && value > 0;
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const cents = value => {
  if (typeof value !== 'string' || paymentKopecks(value) === null) fail('Укажите точную сумму до копейки.');
  return paymentKopecks(value);
};
const decimal = value => `${Math.floor(value / 100)}.${String(value % 100).padStart(2, '0')}`;
const keyFor = scope => {
  if (![scope.userId, scope.companyId, scope.invoiceId].every(id) || typeof scope.API !== 'string') fail('Не определён контекст возврата.');
  return `supplier-refund:v1:${JSON.stringify([scope.API, scope.userId, scope.companyId, scope.invoiceId])}`;
};
export function verifyContext(value, scope) {
  if (value?.companyId !== scope.companyId || value?.invoiceId !== scope.invoiceId) fail('Ответ относится к другому счёту.');
  if (value.groupId === null) return value;
  if (!id(value.groupId) || !Number.isInteger(value.version) || value.version < 0 || value.version >= 2147483647
      || !['payments', 'receipts', 'allocations'].every(key => Array.isArray(value[key]))) fail('Неполные данные возврата.');
  const payments = new Map(), receipts = new Map(), pairs = new Set();
  for (const row of value.payments) {
    if (!id(row.paymentId) || payments.has(row.paymentId)
        || cents(row.amount) !== cents(row.refundedAmount) + cents(row.remainingAmount)
        || cents(row.remainingAmount) !== cents(row.allocatedAmount) + cents(row.unallocatedAmount)) fail('Остаток оплаты требует сверки.');
    payments.set(row.paymentId, { row, allocated: 0 });
  }
  for (const row of value.receipts) {
    if (!id(row.receiptId) || !id(row.warehouseId) || receipts.has(row.receiptId)
        || cents(row.amount) !== cents(row.allocated) + cents(row.remaining)) fail('Приёмка требует сверки.');
    receipts.set(row.receiptId, { row, allocated: 0 });
  }
  for (const row of value.allocations) {
    const key = `${row.paymentId}:${row.receiptId}`, amount = cents(row.amount);
    if (pairs.has(key) || !payments.has(row.paymentId) || !receipts.has(row.receiptId) || amount <= 0) fail('Распределение требует сверки.');
    pairs.add(key); payments.get(row.paymentId).allocated += amount; receipts.get(row.receiptId).allocated += amount;
  }
  if ([...payments.values()].some(item => item.allocated !== cents(item.row.allocatedAmount))
      || [...receipts.values()].some(item => item.allocated !== cents(item.row.allocated))) fail('Распределение неполное.');
  return value;
}
function command(context, draft, requestId) {
  const payment = context.payments?.find(row => row.paymentId === draft?.paymentId);
  const date = typeof draft?.paidAt === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(draft.paidAt) ? new Date(draft.paidAt + 'T00:00:00Z') : null;
  if (!payment || !uuidPattern.test(requestId || '') || !date || !Number.isFinite(date.getTime())
      || date.toISOString().slice(0, 10) !== draft.paidAt || draft.paidAt.startsWith('0000')
      || typeof draft.reason !== 'string' || !draft.reason.trim() || draft.reason.length > 1000
      || !Array.isArray(draft.releases) || draft.releases.length > 2000) fail('Выберите оплату, дату и основание возврата.');
  const amount = cents(draft.amount), free = cents(draft.unallocatedAmount), seen = new Set();
  const releases = draft.releases.map(row => {
    const allocation = context.allocations.find(item => item.paymentId === payment.paymentId && item.receiptId === row.receiptId);
    const release = cents(row.amount);
    if (seen.has(row.receiptId) || !allocation || release <= 0 || release > cents(allocation.amount)) fail('Сумма по приёмке превышает распределённую оплату.');
    seen.add(row.receiptId); return { receiptId: row.receiptId, amount: decimal(release) };
  }).sort((a, b) => a.receiptId - b.receiptId);
  if (amount <= 0 || amount > cents(payment.remainingAmount) || free > cents(payment.unallocatedAmount)
      || free + releases.reduce((total, row) => total + cents(row.amount), 0) !== amount) fail('Сумма возврата должна совпадать с суммой по приёмкам и свободному остатку.');
  return { requestId, groupId: context.groupId, expectedVersion: context.version, paymentId: payment.paymentId,
    amount: decimal(amount), unallocatedAmount: decimal(free), paidAt: draft.paidAt, reason: draft.reason.trim(), releases };
}
export function readRefundPending(scope, storage = window.localStorage) {
  const raw = storage.getItem(keyFor(scope));
  if (raw === null) return null;
  let saved;
  try { saved = JSON.parse(raw); } catch (_) { fail('Сохранённый возврат повреждён. Отправка заблокирована.'); }
  if (saved?.version !== 1 || ['API', 'userId', 'companyId', 'invoiceId'].some(key => saved[key] !== scope[key])
      || ('cancelRequested' in saved && saved.cancelRequested !== true)) fail('Сохранённый возврат относится к другому счёту.');
  verifyContext(saved.context, scope);
  if (JSON.stringify(command(saved.context, saved.body, saved.body?.requestId)) !== JSON.stringify(saved.body)) fail('Сохранённая команда возврата повреждена.');
  return saved;
}
export async function refundContext(scope, options) {
  keyFor(scope);
  return verifyContext(await paymentRequest(scope.API, scope.companyId,
    `${paymentPath(scope.companyId)}/refund-context/${scope.invoiceId}`, options), scope);
}
function verifyOperation(result, amount) {
  if (result?.kind !== 'refund' || result.amount !== amount || !id(result.operationId) || !id(result.projectPaymentId)) fail('Результат возврата не подтверждён. Повторите сохранённый запрос.');
}
async function perform({ scope, context, draft, expectedPending, storage = window.localStorage,
  locks = window.navigator.locks, uuid = () => window.crypto.randomUUID(), fetcher = window.fetch, signal }, cancel) {
  const key = keyFor(scope);
  if (!locks?.request) fail('Для возврата нужен браузер с поддержкой Web Locks и HTTPS.');
  return locks.request(key, { mode: 'exclusive', ifAvailable: true }, async lock => {
    if (!lock) fail('Возврат уже обрабатывается в другой вкладке.');
    let saved = readRefundPending(scope, storage);
    if (expectedPending) {
      if (JSON.stringify(saved) !== JSON.stringify(expectedPending)) fail('Сохранённый запрос изменился. Откройте его заново.');
    } else {
      if (cancel || saved) fail('Сначала завершите сохранённый возврат.');
      verifyContext(context, scope);
      saved = { version: 1, ...scope, context, body: command(context, draft, uuid()) };
    }
    if (!cancel && saved.cancelRequested) fail('Сначала завершите отмену попытки.');
    if (cancel) saved = { ...saved, cancelRequested: true };
    const encoded = JSON.stringify(saved);
    storage.setItem(key, encoded);
    if (storage.getItem(key) !== encoded) fail('Не удалось сохранить запрос. Отправка заблокирована.');
    const body = cancel ? { requestId: saved.body.requestId, kind: 'refund', documentKind: 'invoice', documentId: scope.invoiceId,
      amount: saved.body.amount, paidAt: saved.body.paidAt, reason: saved.body.reason } : saved.body;
    // Every failure retains the exact request. Only a server-confirmed
    // cancellation or a validated committed result permits a fresh UUID.
    const result = await paymentRequest(scope.API, scope.companyId,
      `${paymentPath(scope.companyId)}/${cancel ? 'cancel-request' : 'allocated-refunds'}`, { body, fetcher, signal });
    if (result?.companyId !== scope.companyId || result?.requestId !== saved.body.requestId) fail('Результат относится к другому запросу.');
    if (cancel) {
      if (result.documentKind !== 'invoice' || result.documentId !== scope.invoiceId || result.kind !== 'refund'
          || !['confirmed', 'cancelled'].includes(result.status)) fail('Отмена попытки не подтверждена.');
      if (result.status === 'confirmed') verifyOperation(result.result, saved.body.amount);
    } else {
      verifyOperation(result, saved.body.amount);
      if (result.groupId !== saved.body.groupId || result.paymentId !== saved.body.paymentId
          || !id(result.revisionId) || result.version !== saved.body.expectedVersion + 1) fail('Распределение возврата не подтверждено.');
    }
    if (storage.getItem(key) !== encoded) fail('Сохранённый запрос изменился. Требуется сверка результата.');
    storage.removeItem(key);
    return result;
  });
}
export const submitRefund = options => perform(options, false);
export const cancelRefund = options => perform(options, true);
