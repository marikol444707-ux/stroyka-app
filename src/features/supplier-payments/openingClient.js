import { paymentKopecks } from '../../utils/paymentMoney';
import { paymentRequest } from './paymentClient';

const fail = message => { throw new Error(message); };
const id = value => Number.isSafeInteger(value) && value > 0 && value <= 2147483647;
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
export const openingPath = companyId => `/companies/${companyId}/supplier-opening-confirmations`;
const keyFor = scope => {
  if (![scope.userId, scope.companyId, scope.invoiceId].every(id) || typeof scope.API !== 'string') fail('Не определён контекст сверки.');
  return `supplier-opening:v1:${JSON.stringify([scope.API, scope.userId, scope.companyId, scope.invoiceId])}`;
};
function verifyPreview(preview, scope) {
  if (preview?.companyId !== scope.companyId || preview?.invoiceId !== scope.invoiceId
      || ('warehouseId' in preview && !id(preview.warehouseId))
      || !/^[a-f0-9]{64}$/.test(preview.reviewedHash || '') || preview.newCashAmount !== '0.00'
      || !['amount', 'openingPaid', 'remainingAmount'].every(field => typeof preview[field] === 'string'
        && /^\d+\.\d{2}$/.test(preview[field]) && paymentKopecks(preview[field]) !== null)
      || paymentKopecks(preview.amount) <= 0
      || paymentKopecks(preview.openingPaid) + paymentKopecks(preview.remainingAmount) !== paymentKopecks(preview.amount)) {
    fail('Ответ сверки не соответствует выбранному счёту.');
  }
  return preview;
}
export function readOpeningPending(scope, storage = window.localStorage) {
  const raw = storage.getItem(keyFor(scope));
  if (raw === null) return null;
  let saved;
  try { saved = JSON.parse(raw); } catch (_) { fail('Сохранённая сверка повреждена. Отправка заблокирована.'); }
  const body = saved?.body;
  if (saved?.version !== 1 || saved.userId !== scope.userId || saved.companyId !== scope.companyId
      || saved.invoiceId !== scope.invoiceId || saved.API !== scope.API || body?.invoiceId !== scope.invoiceId
      || !uuidPattern.test(body?.requestId || '') || typeof body?.reason !== 'string'
      || !body.reason.trim() || body.reason.length > 1000 || body.reviewedHash !== saved.preview?.reviewedHash
      || Object.keys(body).sort().join(',') !== 'invoiceId,reason,requestId,reviewedHash') {
    fail('Сохранённая сверка не соответствует выбранному счёту.');
  }
  verifyPreview(saved.preview, scope);
  return saved;
}
export async function previewOpening(scope, options) {
  keyFor(scope);
  return verifyPreview(await paymentRequest(scope.API, scope.companyId,
    `${openingPath(scope.companyId)}/preview/${scope.invoiceId}`, options), scope);
}
export async function submitOpening({ scope, preview, reason, expectedPending,
  storage = window.localStorage, locks = window.navigator.locks,
  uuid = () => window.crypto.randomUUID(), fetcher = window.fetch, signal }) {
  const key = keyFor(scope);
  if (!locks?.request) fail('Для подтверждения нужен браузер с поддержкой Web Locks и HTTPS.');
  return locks.request(key, { mode: 'exclusive', ifAvailable: true }, async lock => {
    if (!lock) fail('Сверка уже подтверждается в другой вкладке.');
    let saved = readOpeningPending(scope, storage);
    if (expectedPending) {
      if (JSON.stringify(saved) !== JSON.stringify(expectedPending)) fail('Сохранённая сверка изменилась. Откройте её повторно.');
    } else {
      if (saved) fail('Сначала завершите сохранённую сверку.');
      verifyPreview(preview, scope);
      if (typeof reason !== 'string' || !reason.trim() || reason.trim().length > 1000) fail('Укажите основание сверки.');
      saved = { version: 1, ...scope, preview, body: { invoiceId: scope.invoiceId,
        requestId: uuid(), reviewedHash: preview.reviewedHash, reason: reason.trim() } };
      if (!uuidPattern.test(saved.body.requestId)) fail('Не удалось создать идентификатор сверки.');
      const encoded = JSON.stringify(saved);
      storage.setItem(key, encoded);
      if (storage.getItem(key) !== encoded) fail('Не удалось сохранить запрос. Отправка заблокирована.');
    }
    const unchanged = () => JSON.stringify(readOpeningPending(scope, storage)) === JSON.stringify(saved);
    let result;
    try {
      result = await paymentRequest(scope.API, scope.companyId, openingPath(scope.companyId),
        { body: saved.body, fetcher, signal });
    } catch (error) {
      // A received 409 rolls back this attempt. A late earlier attempt cannot
      // duplicate an opening: the server uniquely registers each invoice.
      // Network/503/permission uncertainty retains the exact request for replay.
      if (error.status === 409 && unchanged()) storage.removeItem(key);
      throw error;
    }
    if (result?.companyId !== scope.companyId || result?.invoiceId !== scope.invoiceId
        || result?.requestId !== saved.body.requestId || !Number.isSafeInteger(result?.confirmationId)
        || result.confirmationId <= 0 || result.newCashAmount !== '0.00'
        || result.warehouseId !== saved.preview.warehouseId
        || result.amount !== saved.preview.amount || result.openingPaid !== saved.preview.openingPaid) {
      fail('Результат не подтверждён. Повторите сохранённую сверку.');
    }
    if (!unchanged()) fail('Сохранённая сверка изменилась. Требуется проверка результата.');
    storage.removeItem(key);
    return result;
  });
}
