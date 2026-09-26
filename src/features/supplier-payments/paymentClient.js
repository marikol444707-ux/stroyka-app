import { paymentKopecks } from '../../utils/paymentMoney';

const fail = message => { throw new Error(message); };
const positiveId = value => Number.isSafeInteger(value) && value > 0;
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const allowed = new Set(['requestId', 'kind', 'documentKind', 'documentId', 'amount', 'paidAt', 'reason', 'reversesId']);
export const paymentPath = companyId => `/companies/${companyId}/supplier-payments`;

export function withSupplierPaymentContext(path, init) {
  const company = path.match(/^\/companies\/([1-9][0-9]*)\/supplier-(?:payments|payment-documents)(?:[/?]|$)/)?.[1];
  if (!company) return init;
  const headers = new Headers(init.headers || {});
  headers.set('X-Company-Id', company);
  headers.set('X-Company-Mode', 'company');
  return { ...init, headers };
}

function keyFor({ userId, companyId }) {
  if (!positiveId(userId) || !positiveId(companyId)) fail('Не определены сотрудник и компания оплаты.');
  return `supplier-payment:v1:${userId}:${companyId}`;
}

function normalizeBody(body) {
  if (!body || typeof body !== 'object' || Array.isArray(body)
      || Object.keys(body).some(key => !allowed.has(key)) || !uuidPattern.test(body.requestId || '')
      || !['payment', 'reversal'].includes(body.kind) || !['invoice', 'warehouse'].includes(body.documentKind)
      || !positiveId(body.documentId) || body.documentId > 2147483647) fail('Некорректная операция оплаты.');
  const date = typeof body.paidAt === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(body.paidAt)
    ? new Date(body.paidAt + 'T00:00:00Z') : null;
  if (!date || !Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== body.paidAt
      || body.paidAt.startsWith('0000')) fail('Укажите существующую дату оплаты.');
  if (typeof body.reason !== 'string' || !body.reason.trim() || body.reason.length > 1000) {
    fail('Укажите основание операции, до 1000 символов.');
  }
  const normalized = { requestId: body.requestId, kind: body.kind, documentKind: body.documentKind,
    documentId: body.documentId, paidAt: body.paidAt, reason: body.reason.trim() };
  if (body.kind === 'payment') {
    const cents = paymentKopecks(body.amount);
    if (!Number.isSafeInteger(cents) || cents <= 0 || 'reversesId' in body) fail('Некорректная сумма платежа.');
    normalized.amount = `${Math.floor(cents / 100)}.${String(cents % 100).padStart(2, '0')}`;
  } else {
    if ('amount' in body || !positiveId(body.reversesId)) fail('Сумма сторно берётся из исходного платежа.');
    normalized.reversesId = body.reversesId;
  }
  return normalized;
}

export function readPending(scope, storage = window.localStorage) {
  const raw = storage.getItem(keyFor(scope));
  if (raw === null) return null;
  let command;
  try { command = JSON.parse(raw); } catch (_) { fail('Сохранённая операция повреждена. Нужна сверка истории.'); }
  if (!command || command.version !== 1 || command.userId !== scope.userId || command.companyId !== scope.companyId
      || Object.keys(command).some(key => !['version', 'userId', 'companyId', 'body', 'cancelRequested'].includes(key))
      || ('cancelRequested' in command && command.cancelRequested !== true)) {
    fail('Сохранённая операция относится к другому сотруднику или компании.');
  }
  return { ...command, body: normalizeBody(command.body) };
}

export async function paymentRequest(API, companyId, path, { body, fetcher = window.fetch, signal } = {}) {
  const response = await fetcher(API + path, { credentials: 'include', signal,
    headers: { 'X-Company-Id': String(companyId), 'X-Company-Mode': 'company',
      ...(body ? { 'Content-Type': 'application/json' } : {}) },
    ...(body ? { method: 'POST', body: JSON.stringify(body) } : {}) });
  const data = await response.json();
  if (!response.ok) {
    const message = typeof data?.detail === 'string' ? data.detail : data?.detail?.message;
    const error = new Error(typeof message === 'string' ? message : 'Не удалось выполнить операцию.');
    if (typeof data?.detail?.code === 'string') error.code = data.detail.code;
    error.status = response.status;
    throw error;
  }
  return data;
}

function verifyResult(result, command) {
  const { body } = command;
  if (result?.companyId !== command.companyId || result?.requestId !== body.requestId
      || result?.documentKind !== body.documentKind || result?.documentId !== body.documentId
      || result?.kind !== body.kind || !positiveId(result?.operationId) || !positiveId(result?.projectPaymentId)
      || typeof result?.amount !== 'string' || !/^\d+\.\d{2}$/.test(result.amount)
      || !(paymentKopecks(result.amount) > 0)
      || (body.kind === 'payment' && result.amount !== body.amount)) {
    fail('Ответ требует сверки. Повторите сохранённый запрос — новый платёж не создан автоматически.');
  }
}

function verifyExpectedBody(command, expectedBody) {
  if (!expectedBody) fail('Сначала проверьте сохранённую команду и подтвердите действие.');
  if (JSON.stringify(command.body) !== JSON.stringify(normalizeBody(expectedBody))) {
    fail('Сохранённая команда изменилась. Проверьте её и подтвердите действие заново.');
  }
}

export async function submitPayment({ API, userId, companyId, input, retry = false, expectedBody,
  storage = window.localStorage, locks = window.navigator.locks,
  uuid = () => window.crypto.randomUUID(), fetcher = window.fetch, signal }) {
  const scope = { userId, companyId }, key = keyFor(scope);
  if (!locks?.request) fail('Для безопасной оплаты нужен браузер с поддержкой Web Locks и HTTPS.');
  // ifAvailable avoids queuing a double-click/new command behind a completed
  // first one. All panels/tabs for this actor/company share the same lock/key.
  return locks.request(key, { mode: 'exclusive', ifAvailable: true }, async lock => {
    if (!lock) fail('Оплата уже обрабатывается в другой вкладке. Дождитесь результата.');
    let command = readPending(scope, storage);
    if (command?.cancelRequested) fail('Запрошена отмена попытки. Повторите отмену, а не исходный платёж.');
    if (command && !retry) fail('Сначала завершите или сверьте сохранённую операцию.');
    if (command && retry) verifyExpectedBody(command, expectedBody);
    if (!command) {
      if (retry) fail('Сохранённая операция не найдена. Обновите историю.');
      command = { version: 1, ...scope, body: normalizeBody({ ...input, requestId: uuid() }) };
      const encoded = JSON.stringify(command);
      storage.setItem(key, encoded);
      if (storage.getItem(key) !== encoded) fail('Не удалось надёжно сохранить запрос. Отправка заблокирована.');
    }
    const result = await paymentRequest(API, companyId, paymentPath(companyId), { body: command.body, fetcher, signal });
    verifyResult(result, command);
    if (JSON.stringify(readPending(scope, storage)) !== JSON.stringify(command)) {
      fail('Сохранённая операция изменилась. Требуется сверка истории.');
    }
    storage.removeItem(key);
    return result;
  });
}

export async function cancelPendingPayment({ API, userId, companyId, expectedBody,
  storage = window.localStorage, locks = window.navigator.locks, fetcher = window.fetch, signal }) {
  const scope = { userId, companyId }, key = keyFor(scope);
  if (!locks?.request) fail('Для безопасной отмены нужен браузер с поддержкой Web Locks и HTTPS.');
  return locks.request(key, { mode: 'exclusive', ifAvailable: true }, async lock => {
    if (!lock) fail('Операция уже обрабатывается в другой вкладке. Дождитесь результата.');
    let command = readPending(scope, storage);
    if (!command) fail('Сохранённая операция не найдена. Обновите историю.');
    verifyExpectedBody(command, expectedBody);
    // Persist the direction before dispatch. An uncertain cancellation must never
    // silently switch back to submitting the original payment after a reload.
    command = { ...command, cancelRequested: true };
    const encoded = JSON.stringify(command);
    storage.setItem(key, encoded);
    if (storage.getItem(key) !== encoded) fail('Не удалось сохранить намерение отмены. Отправка заблокирована.');
    const result = await paymentRequest(API, companyId, paymentPath(companyId) + '/cancel-request',
      { body: command.body, fetcher, signal });
    if (result?.companyId !== companyId || result?.requestId !== command.body.requestId
        || result?.documentKind !== command.body.documentKind || result?.documentId !== command.body.documentId
        || result?.kind !== command.body.kind || !['confirmed', 'cancelled'].includes(result?.status)) {
      fail('Отмена не подтверждена. Повторите отмену сохранённой попытки.');
    }
    if (result.status === 'confirmed') {
      verifyResult({ companyId, requestId: result.requestId, documentKind: result.documentKind,
        documentId: result.documentId, ...result.result }, command);
    } else if (typeof result.cancelledAt !== 'string' || !Number.isFinite(Date.parse(result.cancelledAt))) {
      fail('Отмена не подтверждена. Повторите отмену сохранённой попытки.');
    }
    if (JSON.stringify(readPending(scope, storage)) !== JSON.stringify(command)) {
      fail('Сохранённая операция изменилась. Требуется сверка истории.');
    }
    storage.removeItem(key);
    return result;
  });
}
