// Persist the command before sending. Unknown results retain the exact UUID/body.
export const paymentStorageKey = (api, userId, companyId, invoiceId) =>
  `legacy-invoice-payment:${api}:${userId}:${companyId}:${invoiceId}`;

export async function recordLegacyPayment({api, key, storage, command, companyId = command?.companyId, invoiceId: expectedInvoiceId = command?.invoiceId, fetchFn = fetch, locks = typeof navigator === 'undefined' ? undefined : navigator.locks, isCurrent = ()=>true}) {
  if (!locks?.request) throw new Error('Безопасная блокировка вкладок недоступна. Используйте поддерживаемый браузер; оплата не отправлена.');
  return locks.request(key, {mode: 'exclusive', ifAvailable: true}, async lock => {
  if (!lock) throw new Error('Операция открыта в другой вкладке. Продолжите там.');
  if (!isCurrent()) throw new Error('Контекст оплаты изменился.');
  let pending;
  const raw = storage.getItem(key);
  if (raw) {
    pending = JSON.parse(raw);
  } else {
    if (!command) throw new Error('Нет сохранённой операции для проверки.');
    pending = command;
  }
  if (pending?.companyId !== companyId || pending?.invoiceId !== expectedInvoiceId) {
    throw new Error('Сохранённая попытка относится к другому счёту или компании.');
  }
  if (!pending?.requestId || !Number.isSafeInteger(pending.companyId) || !Number.isSafeInteger(pending.invoiceId)) {
    throw new Error('Сохранённая операция повреждена. Требуется сверка; новая оплата заблокирована.');
  }
  const saved = JSON.stringify(pending);
  const attemptKey = `${key}:attempt:${pending.requestId}`;
  const existingAttempt = storage.getItem(attemptKey);
  if (existingAttempt && existingAttempt !== saved) throw new Error('UUID уже сохранён с другими данными.');
  if (!existingAttempt) storage.setItem(attemptKey, saved);
  if (storage.getItem(attemptKey) !== saved) throw new Error('Не удалось сохранить попытку.');
  if (!raw) storage.setItem(key, saved);
  if (storage.getItem(key) !== saved) throw new Error('Сохранённая операция изменилась. Требуется сверка.');
  const {invoiceId, ...body} = pending;
  if (!isCurrent()) throw new Error('Контекст оплаты изменился.');
  const response = await fetchFn(`${api}/supplier-invoices/${invoiceId}/legacy-payments`, {
    method:'POST', headers:{'Content-Type':'application/json','X-Company-Id':String(body.companyId),'X-Company-Mode':'company'},
    body:JSON.stringify(body),
  });
  const data = await response.json().catch(()=>({}));
  if (!response.ok || data.ok !== true || data.requestId !== body.requestId
      || data.companyId !== body.companyId || data.invoiceId !== invoiceId || !Number.isSafeInteger(data.projectPaymentId)) {
    throw new Error(typeof data.detail === 'string' ? data.detail : 'Сервер не подтвердил результат операции.');
  }
  if (storage.getItem(key) !== saved) throw new Error('Ответ получен, но сохранённая попытка изменилась. Требуется сверка.');
  // Keep confirmed identity until a successful refresh, so a stale row cannot start a new payment.
  return {data, clear:async(isCurrent=()=>true)=>locks.request(key, {mode:'exclusive',ifAvailable:true}, lock=>{
    if (!lock) throw new Error('Подтверждение занято другой вкладкой.');
    if (!isCurrent()) throw new Error('Контекст оплаты изменился.');
    if(storage.getItem(key)===saved) storage.removeItem(key);
  })};
  });
}


// Strict payment-specific refresh; never converts HTTP/network failure to empty rows.
export async function refreshLegacyPayment({api, confirmation, isCurrent, setInvoices, fetchFn=fetch}) {
  if (!isCurrent()) throw new Error('Контекст оплаты изменился.');
  const response = await fetchFn(`${api}/supplier-invoices`, {headers:{
    'X-Company-Id':String(confirmation.companyId),'X-Company-Mode':'company'},cache:'no-store'});
  if (!response.ok) throw new Error('Не удалось обновить счета после оплаты.');
  const rows = await response.json();
  const row = Array.isArray(rows) && rows.find(r=>r.id===confirmation.invoiceId && r.companyId===confirmation.companyId);
  if (!row || !Number.isFinite(Number(row.paidAmount)) || !Number.isFinite(Number(confirmation.paidAmount))
      || Number(row.paidAmount)<Number(confirmation.paidAmount)) throw new Error('Обновлённый счёт не подтверждает результат оплаты.');
  if (!isCurrent()) throw new Error('Контекст оплаты изменился.');
  setInvoices(rows);
  return {requestId:confirmation.requestId,companyId:confirmation.companyId,invoiceId:confirmation.invoiceId};
}
