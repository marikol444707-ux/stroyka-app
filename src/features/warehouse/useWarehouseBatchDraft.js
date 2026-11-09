import { useCallback, useEffect, useRef, useState } from 'react';
import { API } from '../../api';
import { readResponse, warehouseRequestId } from './distributionCommands';

// Unacknowledged input survives an in-app unmount; the server remains authoritative.
// This buffer is scoped to the signed-in identity and never replaces a newer server revision.
const recovery = new Map();
const warnRecovery = event => {
  if (recovery.size) { event.preventDefault(); event.returnValue = ''; }
};
const forgetRecovery = key => {
  recovery.delete(key);
  if (!recovery.size) window.removeEventListener('beforeunload', warnRecovery);
};
const encode = value => JSON.stringify(value);
const positive = value => Number.isSafeInteger(value) && value > 0;
export function batchDocument(rows, reason) {
  return { rows: rows.map(row => ({ lotId: row.lotId === '' ? null : Number(row.lotId),
    projectId: row.projectId === '' ? null : Number(row.projectId), quantity: row.quantity })), reason };
}
export function validateDraft(data, companyId, userId) {
  if (data?.companyId !== companyId || data.userId !== userId || !Number.isSafeInteger(data.revision) || data.revision < 0
      || !Array.isArray(data.document?.rows) || !data.document.rows.length || data.document.rows.length > 50
      || typeof data.document.reason !== 'string' || data.document.reason.length > 1000
      || data.document.rows.some(r => !r || (r.lotId !== null && !positive(r.lotId)) || (r.projectId !== null && !positive(r.projectId))
        || typeof r.quantity !== 'string' || r.quantity.length > 100)
      || !Array.isArray(data.sources)) throw Error('Сервер не подтвердил черновик пользователя и компании.');
  return { ...data, document: { rows: data.document.rows.map(r => ({ lotId: r.lotId, projectId: r.projectId, quantity: r.quantity })), reason: data.document.reason } };
}

export default function useWarehouseBatchDraft({ companyId, userId, enabled, rows, reason, setRows, setReason, setSelectedSources, onDenied }) {
  const [state, setState] = useState({ phase: enabled ? 'loading' : 'disabled', error: '', lastOperation: null });
  const phase = useRef(state.phase), generation = useRef(0), revision = useRef(0), saved = useRef(null);
  const latest = useRef(null), flight = useRef(null), retry = useRef(null);
  const recoveryKey = `${userId}:${companyId}`;
  latest.current = batchDocument(rows, reason);
  const change = useCallback(next => { phase.current = next.phase; setState(previous => ({ ...previous, ...next })); }, []);
  const request = useCallback(async (method, body) => {
    const response = await fetch(`${API}/warehouse-distributions/draft`, { method, credentials: 'include',
      headers: { 'X-Company-Id': String(companyId), 'X-Company-Mode': 'company', 'Content-Type': 'application/json' },
      ...(body ? { body: JSON.stringify(body) } : {}) });
    return validateDraft(await readResponse(response), companyId, userId);
  }, [companyId, userId]);
  const hydrate = useCallback(data => {
    const local = recovery.get(recoveryKey); forgetRecovery(recoveryKey);
    revision.current = data.revision; saved.current = encode(data.document); retry.current = null;
    let document = data.document, conflict = false;
    if (local && encode(local.document) !== saved.current) {
      document = local.document;
      const acknowledged = local.retry && data.revision === local.retry.expectedRevision + 1
        && encode(local.retry.document) === saved.current;
      conflict = local.revision !== data.revision && !acknowledged;
      if (!conflict && !acknowledged) retry.current = local.retry;
    }
    latest.current = document;
    setRows(document.rows.map(row => ({ ...row, lotId: row.lotId === null ? '' : String(row.lotId), projectId: row.projectId === null ? '' : String(row.projectId) })));
    setReason(document.reason);
    setSelectedSources(data.sources.map(source => ({ ...source, availabilityUnknown: true })));
    change({ phase: conflict ? 'conflict' : 'ready', error: conflict
      ? 'Серверный черновик изменился. Правки из предыдущего открытия сохранены в форме; сохраните копию перед загрузкой серверной версии.' : '', lastOperation: data.lastOperation });
  }, [change, recoveryKey, setRows, setReason, setSelectedSources]);
  const fail = useCallback(error => {
    if ([401, 403].includes(error.status)) { forgetRecovery(recoveryKey); change({ phase: 'denied', error: error.message }); onDenied(); }
    else change({ phase: error.status === 409 ? 'conflict' : 'error', error: error.message || 'Не удалось сохранить черновик на сервере.' });
  }, [change, onDenied, recoveryKey]);
  const reload = useCallback(async () => {
    const session = ++generation.current;
    change({ phase: 'loading', error: '' });
    try {
      if (!positive(userId)) throw Error('Пользователь не определён. Войдите в приложение для работы с черновиком.');
      const data = await request('GET');
      if (session === generation.current) hydrate(data);
    } catch (error) { if (session === generation.current) fail(error); }
  }, [change, fail, hydrate, request, userId]);
  useEffect(() => {
    if (enabled) reload();
    return () => {
      generation.current += 1;
      if (enabled && phase.current !== 'denied' && saved.current !== null
          && (retry.current || saved.current !== encode(latest.current))) {
        window.addEventListener('beforeunload', warnRecovery);
        recovery.set(recoveryKey, { document: latest.current, revision: revision.current, retry: retry.current });
      }
    };
  }, [enabled, recoveryKey, reload]);

  const flush = useCallback(() => {
    if (flight.current) return flight.current;
    if (!enabled || !['ready', 'saving', 'error'].includes(phase.current) || saved.current === null) {
      return Promise.reject(Error('Сначала загрузите и проверьте серверный черновик.'));
    }
    const session = generation.current;
    const perform = async () => {
      change({ phase: 'saving', error: '' });
      try {
        while (retry.current || saved.current !== encode(latest.current)) {
          const body = retry.current || { companyId, expectedRevision: revision.current,
            requestId: warehouseRequestId(), document: JSON.parse(encode(latest.current)) };
          retry.current = body;
          const data = await request('PUT', body);
          if (session !== generation.current) throw Error('Форма черновика уже закрыта.');
          if (data.revision !== body.expectedRevision + 1 || encode(data.document) !== encode(body.document)) {
            throw Error('Сервер вернул неподтверждённый результат сохранения черновика.');
          }
          revision.current = data.revision; saved.current = encode(data.document); retry.current = null;
        }
        change({ phase: 'ready', error: '' });
        return revision.current;
      } catch (error) {
        if (session === generation.current) fail(error);
        throw error;
      }
    };
    flight.current = perform().finally(() => { flight.current = null; });
    return flight.current;
  }, [change, companyId, enabled, fail, request]);
  const snapshot = encode(latest.current);
  useEffect(() => {
    if (!enabled || state.phase !== 'ready' || saved.current === snapshot) return undefined;
    const timer = setTimeout(() => { flush().catch(() => {}); }, 350);
    return () => clearTimeout(timer);
  }, [enabled, flush, snapshot, state.phase]);
  useEffect(() => {
    const warn = event => {
      if (enabled && phase.current !== 'denied' && saved.current !== null && (retry.current || saved.current !== encode(latest.current))) {
        event.preventDefault(); event.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [enabled]);
  const download = () => {
    const blob = new Blob([JSON.stringify(latest.current, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob), link = document.createElement('a');
    link.href = url; link.download = 'warehouse-batch-draft.json'; link.click(); URL.revokeObjectURL(url);
  };
  const reloadFromServer = () => {
    if (saved.current !== encode(latest.current) && !window.confirm('Заменить правки в этой форме серверным черновиком? Сначала сохраните копию, если эти правки нужны.')) return;
    reload();
  };
  const clear = () => { setRows([{ lotId: '', projectId: '', quantity: '' }]); setReason(''); setSelectedSources([]); };
  return { ...state, loading: state.phase === 'loading', saving: state.phase === 'saving',
    dirty: saved.current !== snapshot, flush, rejectConflict: fail, reloadAfterIssue: reload, reloadFromServer, download, clear,
    readyToSubmit: ['ready', 'saving'].includes(state.phase) };
}
