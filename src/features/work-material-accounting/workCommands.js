const prefix = 'stroyka:work-material-batch:v2:';
const inFlight = new Set();
const commandPath = /^\/(supply-claims\/[1-9][0-9]*\/case|supply-request-templates(?:\/[1-9][0-9]*\/archive)?|warehouses(?:\/[1-9][0-9]*)?\/directory|inventory(?:\/[1-9][0-9]*)?\/reconciliation|work-journal(?:\/[1-9][0-9]*\/(?:acceptance|resubmit|material-corrections|material-defects(?:\/[1-9][0-9]*\/decisions)?))?|tools\/[1-9][0-9]*\/(?:custody|incidents\/[1-9][0-9]*\/decisions)|estimates\/[1-9][0-9]*|brigade-contracts\/[1-9][0-9]*\/acts(?:\/[1-9][0-9]*\/signature)?|brigade-payments)$/;
export const workBatchScope = (context, user) => ({ companyId: context?.selectedCompanyId, userId: user?.id });

function storageKey(scope) {
  if (![scope?.companyId, scope?.userId].every(id => Number.isSafeInteger(Number(id)) && Number(id) > 0)) {
    throw new Error('Выберите компанию перед отправкой работы.');
  }
  return prefix + Number(scope.companyId) + ':' + Number(scope.userId);
}

function uuid() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID();
  if (!window.crypto?.getRandomValues) throw new Error('Для отправки откройте программу по HTTPS в современном браузере.');
  const bytes = window.crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = [...bytes].map(byte => byte.toString(16).padStart(2, '0')).join('');
  return [hex.slice(0, 8), hex.slice(8, 12), hex.slice(12, 16), hex.slice(16, 20), hex.slice(20)].join('-');
}

export function pendingWorkBatch(scope) {
  const raw = sessionStorage.getItem(storageKey(scope));
  if (raw === null) return null;
  const batch = JSON.parse(raw);
  if (!Array.isArray(batch.commands) || !batch.commands.length || !Number.isInteger(batch.next)
    || batch.next < 0 || batch.next > batch.commands.length
    || batch.commands.some(c => !commandPath.test(c.path)
      || c.method !== (c.path.startsWith('/estimates/') ? 'PUT' : 'POST') || !c.payload?.requestId)) {
    throw new Error('Сохранённая отправка повреждена. Требуется сверка журнала.');
  }
  return batch;
}

function save(scope, batch) {
  sessionStorage.setItem(storageKey(scope), JSON.stringify(batch));
  window.dispatchEvent(new Event('work-material-batch-change'));
}

export function clearWorkBatch(scope) {
  const batch = pendingWorkBatch(scope);
  if (batch && batch.next !== batch.commands.length) throw new Error('Сначала повторите неподтверждённую отправку.');
  sessionStorage.removeItem(storageKey(scope));
  window.dispatchEvent(new Event('work-material-batch-change'));
}

export function abandonRejectedWorkTail(scope) {
  const batch = pendingWorkBatch(scope);
  if (!batch?.rejected) throw new Error('Исход отправки неизвестен. Сначала повторите её или сверьте журнал.');
  sessionStorage.removeItem(storageKey(scope));
  window.dispatchEvent(new Event('work-material-batch-change'));
}

async function execute({ API, scope, fetchFn = window.fetch, fresh = false }) {
  const key = storageKey(scope);
  if (inFlight.has(key)) throw new Error('Отправка уже выполняется.');
  inFlight.add(key);
  try {
    const batch = pendingWorkBatch(scope);
    if (!batch) throw new Error('Нет сохранённой отправки.');
    while (batch.next < batch.commands.length) {
      const command = batch.commands[batch.next];
      const attempted = Boolean(command.attempted);
      command.attempted = true;
      batch.rejected = false;
      save(scope, batch);
      const response = await fetchFn(API + command.path, { method: command.method, credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-Company-Mode': 'company', 'X-Company-Id': String(scope.companyId) },
        body: JSON.stringify(command.payload) });
      const result = await response.json().catch(() => null);
      if (!response.ok) {
        if (!attempted && [400, 403, 404, 409, 422].includes(response.status)) {
          if (fresh && batch.next === 0) {
            sessionStorage.removeItem(key);
            window.dispatchEvent(new Event('work-material-batch-change'));
          } else {
            batch.rejected = true;
            command.attempted = false;
            save(scope, batch);
          }
        }
        throw new Error(typeof result?.detail === 'string' ? result.detail : 'Не удалось подтвердить отправку работы.');
      }
      if (command.path === '/work-journal' ? !Number.isSafeInteger(result?.id) : result?.ok !== true) {
        throw new Error('Сервер вернул неизвестный ответ. Повторите сохранённую отправку.');
      }
      batch.next += 1;
      save(scope, batch);
    }
    return batch;
  } finally { inFlight.delete(key); }
}

export async function sendWorkBatch({ API, scope, commands, fetchFn }) {
  if (pendingWorkBatch(scope)) throw new Error('Сначала повторите сохранённую отправку работ.');
  if (!commands.length) throw new Error('Нет работ для отправки.');
  save(scope, { next: 0, commands: commands.map(command => ({ ...command,
    payload: { ...command.payload, expectedCompanyId: Number(scope.companyId), expectedActorId: Number(scope.userId),
      materialAccountingVersion: 2, requestId: uuid() } })) });
  return execute({ API, scope, fetchFn, fresh: true });
}

export const resumeWorkBatch = options => execute(options);
