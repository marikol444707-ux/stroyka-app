import { paymentKopecks } from '../../utils/paymentMoney';
import { paymentPath, paymentRequest } from './paymentClient';
import { refundContext, verifyContext } from './refundClient';
export const allocationContext = refundContext;
const fail = message => { throw new Error(message); };
const id = value => Number.isSafeInteger(value) && value > 0;
const decimal = cents => `${Math.floor(cents / 100)}.${String(cents % 100).padStart(2, '0')}`;
const keyFor = scope => {
  if (![scope.userId, scope.companyId, scope.invoiceId].every(id) || typeof scope.API !== 'string') fail('Не определён счёт распределения.');
  return `supplier-allocation:v1:${JSON.stringify([scope.API, scope.userId, scope.companyId, scope.invoiceId])}`;
};
function command(context, draft, requestId) {
  if (!id(context.groupId) || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(requestId || '')
      || typeof draft?.reason !== 'string' || !draft.reason.trim() || draft.reason.length > 1000
      || !Array.isArray(draft.rows) || draft.rows.length > 2000) fail('Укажите основание распределения.');
  const payments = new Map(), receipts = new Map(), seen = new Set();
  const rows = draft.rows.map(row => {
    const amount = typeof row.amount === 'string' ? paymentKopecks(row.amount) : null;
    const payment = context.payments.find(item => item.paymentId === row.paymentId);
    const receipt = context.receipts.find(item => item.receiptId === row.receiptId);
    const key = `${row.paymentId}:${row.receiptId}`;
    if (!payment || !receipt || seen.has(key) || amount === null || amount <= 0) fail('Проверьте суммы и выбранные приёмки.');
    seen.add(key);
    payments.set(row.paymentId, (payments.get(row.paymentId) || 0) + amount);
    receipts.set(row.receiptId, (receipts.get(row.receiptId) || 0) + amount);
    if (payments.get(row.paymentId) > paymentKopecks(payment.remainingAmount)
        || receipts.get(row.receiptId) > paymentKopecks(receipt.amount)) fail('Распределение превышает сумму оплаты или приёмки.');
    return { paymentId: row.paymentId, receiptId: row.receiptId, amount: decimal(amount) };
  }).sort((a, b) => a.paymentId - b.paymentId || a.receiptId - b.receiptId);
  return { requestId, groupId: context.groupId, expectedVersion: context.version, reason: draft.reason.trim(), rows };
}
export function readAllocationPending(scope, storage = window.localStorage) {
  const raw = storage.getItem(keyFor(scope));
  if (raw === null) return null;
  let saved;
  try { saved = JSON.parse(raw); } catch (_) { fail('Сохранённое распределение повреждено.'); }
  if (saved?.version !== 1 || ['API','userId','companyId','invoiceId'].some(key => saved[key] !== scope[key])) fail('Сохранённое распределение относится к другому счёту.');
  verifyContext(saved.context, scope);
  if (JSON.stringify(command(saved.context, saved.body, saved.body?.requestId)) !== JSON.stringify(saved.body)) fail('Сохранённая команда распределения повреждена.');
  return saved;
}
export async function submitAllocation({ scope, context, draft, expectedPending, storage = window.localStorage,
  locks = window.navigator.locks, uuid = () => window.crypto.randomUUID(), fetcher = window.fetch, signal }) {
  const key = keyFor(scope);
  if (!locks?.request) fail('Для распределения нужен браузер с поддержкой Web Locks и HTTPS.');
  return locks.request(key, { mode: 'exclusive', ifAvailable: true }, async lock => {
    if (!lock) fail('Распределение уже сохраняется в другой вкладке.');
    let saved = readAllocationPending(scope, storage);
    if (expectedPending) {
      if (JSON.stringify(saved) !== JSON.stringify(expectedPending)) fail('Сохранённый запрос изменился. Откройте его заново.');
    } else {
      if (saved) fail('Сначала завершите сохранённое распределение.');
      verifyContext(context, scope);
      saved = { version: 1, ...scope, context, body: command(context, draft, uuid()) };
    }
    const encoded = JSON.stringify(saved);
    storage.setItem(key, encoded);
    if (storage.getItem(key) !== encoded) fail('Не удалось сохранить запрос. Отправка заблокирована.');
    let result;
    try {
      result = await paymentRequest(scope.API, scope.companyId, `${paymentPath(scope.companyId)}/allocations`,
        { body: saved.body, fetcher, signal });
    } catch (error) {
      const detail = error.detail;
      // Only a scoped rejection issued AFTER UUID replay lookup proves no save.
      if (error.status === 409 && detail?.code === 'allocation_not_saved' && detail.companyId === scope.companyId
          && detail.groupId === saved.body.groupId && detail.requestId === saved.body.requestId
          && storage.getItem(key) === encoded) storage.removeItem(key);
      throw error;
    }
    if (result?.companyId !== scope.companyId || result?.groupId !== saved.body.groupId
        || result?.requestId !== saved.body.requestId || result.version !== saved.body.expectedVersion + 1
        || !id(result.revisionId)) fail('Сохранение распределения не подтверждено. Повторите тот же запрос.');
    if (storage.getItem(key) !== encoded) fail('Сохранённый запрос изменился. Требуется сверка.');
    storage.removeItem(key);
    return result;
  });
}
