// Persist the command before sending. Unknown results retain the exact UUID/body.
export const paymentStorageKey = (api, userId, companyId, invoiceId) =>
  `legacy-invoice-payment:${api}:${userId}:${companyId}:${invoiceId}`;

export async function recordLegacyPayment({api, key, storage, command, companyId = command?.companyId, invoiceId: expectedInvoiceId = command?.invoiceId, fetchFn = fetch}) {
  let pending;
  const raw = storage.getItem(key);
  if (raw) {
    pending = JSON.parse(raw);
  } else {
    if (!command) throw new Error('Нет сохранённой операции для проверки.');
    pending = command;
    storage.setItem(key, JSON.stringify(pending));
  }
  if (pending?.companyId !== companyId || pending?.invoiceId !== expectedInvoiceId) {
    throw new Error('Сохранённая попытка относится к другому счёту или компании.');
  }
  if (!pending?.requestId || !Number.isSafeInteger(pending.companyId) || !Number.isSafeInteger(pending.invoiceId)) {
    throw new Error('Сохранённая операция повреждена. Требуется сверка; новая оплата заблокирована.');
  }
  const saved = JSON.stringify(pending);
  if (storage.getItem(key) !== saved) throw new Error('Сохранённая операция изменилась. Требуется сверка.');
  const {invoiceId, ...body} = pending;
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
  return {data, clear:()=>{if(storage.getItem(key)===saved) storage.removeItem(key);}};
}
