// Business drafts only, no credentials. Session-scoped so an unanswered command
// survives navigation/reload without becoming a second warehouse movement.
const key = companyId => `warehouse-distribution.pending.v1.${companyId}`;
export function pendingCommand(companyId) {
  const raw = sessionStorage.getItem(key(companyId));
  if (!raw) return null;
  const value = JSON.parse(raw);
  const isQuantity = number => typeof number === 'string' && /^\d+(\.\d{1,6})?$/.test(number) && Number(number) > 0 && Number(number) < 100000000;
  const payload = value?.payload;
  const rowsValid = value?.path?.endsWith('/returns') ? isQuantity(payload?.quantity)
    : Array.isArray(payload?.rows) && payload.rows.length > 0 && payload.rows.length <= 50
      && payload.rows.every(row => row && Number.isInteger(row.lotId) && Number.isInteger(row.projectId) && isQuantity(row.quantity));
  if (payload?.companyId !== companyId || typeof payload?.reason !== 'string' || !rowsValid
      || !/^\/warehouse-distributions(?:\/\d+\/returns)?$/.test(value?.path) || !/^[0-9a-f-]{36}$/i.test(value?.id)
      || value.signature !== JSON.stringify({ path: value.path, ...payload })) {
    throw new Error('Неподтверждённая операция повреждена. Требуется сверка истории перед новой выдачей.');
  }
  return value;
}
export function saveCommand(companyId, command) {
  sessionStorage.setItem(key(companyId), JSON.stringify(command));
}
export function clearCommand(companyId, requestId) {
  if (pendingCommand(companyId)?.id === requestId) sessionStorage.removeItem(key(companyId));
}

export async function readResponse(response) {
  let data;
  try { data = await response.json(); }
  catch (e) { if (response.ok) throw e; }
  if (!response.ok) {
    const error = new Error(typeof data?.detail === 'string' ? data.detail : 'Операция не выполнена. Проверьте данные и права доступа.');
    error.status = response.status;
    throw error;
  }
  return data;
}
export function validateList(data, source = false, beforeId = null) {
  const quantity = value => ['number', 'string'].includes(typeof value) && String(value).trim() !== '' && Number.isFinite(Number(value)) && Number(value) >= 0;
  if (!data || !Array.isArray(data.items) || data.items.some(r => !r || typeof r !== 'object'
      || !Number.isInteger(source ? r.lotId : r.id)
      || typeof r.materialName !== 'string' || typeof r.unit !== 'string'
      || (source ? !quantity(r.availableQuantity) : !quantity(r.quantity) || !quantity(r.returnedQuantity) || !quantity(r.netQuantity))
      || (!source && r.returns !== undefined && (!Array.isArray(r.returns) || r.returns.some(event => !event || !Number.isInteger(event.id) || !quantity(event.quantity)))))) {
    throw new Error('Сервер вернул неизвестный формат истории. Обновите данные.');
  }
  validatePagination(data, data.items.map(row => source ? row.lotId : row.id), beforeId);
  return data;
}
function validatePagination(data, ids, beforeId = null) {
  if (ids.some(id => !Number.isSafeInteger(id) || id <= 0 || (beforeId !== null && id >= beforeId))
      || ('nextCursor' in data && (typeof data.truncated !== 'boolean'
        || data.truncated !== (data.nextCursor !== null)
        || ids.some((id, i) => i > 0 && id >= ids[i - 1])
        || (data.nextCursor !== null && (!Number.isSafeInteger(data.nextCursor) || data.nextCursor <= 0
          || !ids.length || data.nextCursor !== ids[ids.length - 1]))))) {
    throw new Error('Сервер вернул неизвестный формат пагинации. Обновите данные.');
  }
}
export function validateCommandResult(data, command) {
  const valid = data?.ok === true && data.requestId === command.id
    && (command.path.endsWith('/returns') ? Number.isInteger(data.item?.id) : Array.isArray(data.items)
      && data.items.length === command.payload.rows.length && data.items.every(item => Number.isInteger(item?.id)));
  if (!valid) throw new Error('Результат операции не подтверждён сервером. Повторите тот же запрос.');
}

export const transferPath = '/warehouse-distributions/transfers';
const transferKey = companyId => `warehouse-transfers.pending.v1.${companyId}`;
const positiveId = value => Number.isSafeInteger(value) && value > 0;
export const transferQuantity = (value, allowZero = false) => typeof value === 'string' && /^\d+(\.\d{1,6})?$/.test(value)
  && Number(value) >= 0 && (allowZero || Number(value) > 0) && Number(value) < 100000000;
export function readTransferCommand(companyId) {
  const raw = sessionStorage.getItem(transferKey(companyId));
  if (!raw) return null;
  const value = JSON.parse(raw);
  const payload = value?.payload;
  const receipt = /^\/warehouse-distributions\/transfers\/[1-9]\d*\/receipts$/.test(value?.path);
  if (!payload || payload.companyId !== companyId || !/^[0-9a-f-]{36}$/i.test(value?.id)
      || typeof payload.reason !== 'string' || !payload.reason.trim() || payload.reason.length > 1000
      || !transferQuantity(payload.quantity, receipt)
      || (receipt ? !transferQuantity(payload.expectedQuantity) || Number(payload.quantity) > Number(payload.expectedQuantity)
        : value.path !== transferPath || !positiveId(payload.allocationId) || !positiveId(payload.toProjectId))
      || value.signature !== JSON.stringify({ path: value.path, ...payload })) {
    throw new Error('Неподтверждённое перемещение повреждено. Требуется сверка перед новой операцией.');
  }
  return value;
}
export function saveTransferCommand(companyId, command) {
  sessionStorage.setItem(transferKey(companyId), JSON.stringify(command));
}
export function clearTransferCommand(companyId, id) {
  if (readTransferCommand(companyId)?.id === id) sessionStorage.removeItem(transferKey(companyId));
}
export function validateTransfer(item, companyId) {
  const quantity = value => ['number', 'string'].includes(typeof value) && String(value).trim() !== '' && Number.isFinite(Number(value)) && Number(value) >= 0;
  if (!item || item.companyId !== companyId
      || !['id', 'sourceAllocationId', 'fromProjectId', 'toProjectId', 'warehouseInvoiceId', 'lotId'].every(key => positiveId(item[key]))
      || !['fromProjectName', 'toProjectName', 'materialName', 'unit', 'reason'].every(key => typeof item[key] === 'string')
      || !['quantity', 'receivedQuantity', 'inTransitQuantity'].every(key => quantity(item[key]))
      || !['in_transit', 'partial', 'received', 'discrepancy'].includes(item.status)
      || !Array.isArray(item.receipts) || item.receipts.some(r => !r || !positiveId(r.id)
        || !['quantity', 'expectedQuantity', 'discrepancyQuantity'].every(key => quantity(r[key]))
        || Number(r.expectedQuantity) <= 0 || Number(r.quantity) > Number(r.expectedQuantity)
        || (r.allocationId !== null && !positiveId(r.allocationId)) || typeof r.reason !== 'string')) {
    throw new Error('Сервер вернул неизвестный формат перемещений. Обновите данные.');
  }
  return item;
}
export function validateTransferPage(data, companyId, beforeId = null) {
  if (!data || !Array.isArray(data.items) || !('nextCursor' in data)) throw new Error('Неизвестный формат списка перемещений.');
  data.items.forEach(item => validateTransfer(item, companyId));
  validatePagination(data, data.items.map(item => item.id), beforeId);
  return data;
}
export function validateTransferResult(data, command) {
  const item = validateTransfer(data?.item, command.payload.companyId);
  const receipt = command.path !== transferPath;
  if (data.ok !== true || data.requestId !== command.id
      || (receipt ? item.id !== Number(command.path.split('/')[3])
        : item.sourceAllocationId !== command.payload.allocationId || item.toProjectId !== command.payload.toProjectId
          || Number(item.quantity) !== Number(command.payload.quantity))) {
    throw new Error('Результат перемещения не подтверждён. Повторите тот же запрос.');
  }
  return item;
}
