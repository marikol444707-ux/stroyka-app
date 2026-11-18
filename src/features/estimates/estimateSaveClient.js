export const ESTIMATE_CONFLICT_MESSAGE = 'Смета изменена на сервере. Ваши правки остались в редакторе. Скопируйте их отдельно, обновите страницу и сравните с актуальной сметой перед повторным сохранением.';

export function estimateMutationPayload(estimate, payload = {}) {
  if (!Number.isSafeInteger(estimate?.revision) || estimate.revision < 1) {
    throw new Error('Ревизия сметы неизвестна. Сохраните локальные правки отдельно и заново откройте смету.');
  }
  return {...payload, expectedRevision: estimate.revision};
}

export async function readEstimateMutationResponse(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    const error = new Error(detail?.code === 'estimate_revision_conflict'
      ? ESTIMATE_CONFLICT_MESSAGE
      : detail?.message || (typeof detail === 'string' ? detail : 'Не удалось сохранить смету'));
    error.code = detail?.code;
    error.status = response.status;
    throw error;
  }
  if (!Number.isSafeInteger(data.revision) || data.revision < 1) {
    throw new Error('Сервер не подтвердил ревизию сметы. Сохраните локальные правки отдельно и проверьте актуальную смету.');
  }
  return data;
}

export function estimateSaveFailure(error) {
  return {status: error.code === 'estimate_revision_conflict' ? 'conflict' : 'error', error: error.message || 'Ошибка соединения'};
}

// A status response acknowledges metadata only. Never rebase an unknown server
// snapshot or replace a list entry edited/refreshed while the request was pending.
export function applyConfirmedEstimateStatuses(list, originals, affected = []) {
  const byId = new Map(affected.map(item => [item.id, item]));
  return (list || []).map(item => {
    const change = byId.get(item.id);
    if (!change || originals.find(original => original.id === item.id) !== item
      || item.revision !== change.previousRevision) return item;
    return {...item, status: change.status, revision: change.revision};
  });
}
