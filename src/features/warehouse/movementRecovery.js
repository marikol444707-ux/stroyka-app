export const movementScope = (user, context = {}) => {
  const actorUserId = Number(user?.id);
  const companyId = Number(context.selectedCompanyId);
  return !context.loading && !context.error && context.mode === 'company' && Number.isSafeInteger(actorUserId) && actorUserId > 0
    && Number.isSafeInteger(companyId) && companyId > 0
    ? {actorUserId, companyId, key: `${actorUserId}:${companyId}`} : null;
};
export const movementHeaders = scope => ({
  'Content-Type': 'application/json', 'X-Company-Mode': 'company',
  'X-Company-Id': String(scope.companyId),
});
export async function movementRequest(API, path, scope, body) {
  const response = await fetch(API + path, {
    method: body === undefined ? 'GET' : 'POST', headers: movementHeaders(scope),
    ...(body === undefined ? {} : {body: JSON.stringify(body)}),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Не удалось проверить перемещение');
  return result;
}
export const matchesMovementScope = (result, scope) => Boolean(scope && result
  && Number(result.companyId) === scope.companyId && Number(result.actorUserId) === scope.actorUserId);
export const newMovementId = () => {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128;
  const h = Array.from(bytes, x => x.toString(16).padStart(2, '0')).join('');
  return `${h.slice(0,8)}-${h.slice(8,12)}-${h.slice(12,16)}-${h.slice(16,20)}-${h.slice(20)}`;
};
