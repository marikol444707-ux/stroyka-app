import { useLayoutEffect, useRef, useState } from 'react';
import { readStoredCompanyRequestContext } from '../features/company-context/companyContextStorage';
import { beginQualityJournalMutation, finishQualityJournalMutation } from '../utils/qualityJournalEvents';

export const journalRowKey = row => row ? JSON.stringify([row.companyId ?? null, row.projectId ?? null, row.id]) : '';

export const journalScopeKey = () => {
  let userId = null;
  try { userId = JSON.parse(localStorage.getItem('user') || 'null')?.id ?? null; } catch (_) {}
  return JSON.stringify([userId, readStoredCompanyRequestContext()]);
};

// One in-flight mutation per editor. Abort is best-effort: every application of
// its result must also pass the identity/scope/lifecycle guard.
export default function useJournalMutation(record, { draft = false } = {}) {
  const identity = journalRowKey(record);
  const initial = useRef({ identity, json: JSON.stringify(record) });
  if (initial.current.identity !== identity) initial.current = { identity, json: JSON.stringify(record) };
  const printDirty = draft && initial.current.json !== JSON.stringify(record);
  const scope = journalScopeKey();
  const key = JSON.stringify([identity, scope]);
  const latest = useRef(key);
  latest.current = key;
  const mounted = useRef(false);
  const generation = useRef(0);
  const active = useRef(null);
  const [state, setState] = useState({ key, busy: false, error: '' });

  useLayoutEffect(() => {
    mounted.current = true;
    generation.current += 1;
    setState({ key, busy: false, error: '' });
    return () => {
      mounted.current = false;
      generation.current += 1;
      active.current?.abort();
      active.current = null;
    };
  }, [key]);

  const cancel = () => {
    generation.current += 1;
    active.current?.abort();
    active.current = null;
    if (mounted.current) setState({ key, busy: false, error: '' });
  };

  const run = async ({ url, method = 'PUT', body, onSuccess }) => {
    if (!mounted.current || active.current || latest.current !== key || !record) return;
    const context = readStoredCompanyRequestContext();
    if (scope !== journalScopeKey() || (context && (context.mode !== 'company'
      || (record.companyId != null && Number(record.companyId) !== Number(context.companyId))))) {
      setState({ key, busy: false, error: 'Компания изменилась. Откройте запись заново.' });
      return;
    }
    const controller = new AbortController();
    const epoch = generation.current;
    active.current = controller;
    const current = () => mounted.current && !controller.signal.aborted
      && generation.current === epoch && latest.current === key && scope === journalScopeKey();
    setState({ key, busy: true, error: '' });
    // Invalidate before dispatch: a committed write may lose its response.
    const token = beginQualityJournalMutation();
    let outcome = { confirmed: false, uncertain: true };
    let settled = false;
    const settle = () => {
      if (settled) return;
      settled = true;
      finishQualityJournalMutation(token, outcome);
    };
    controller.signal.addEventListener('abort', settle, { once: true });
    try {
      if (controller.signal.aborted) {
        settle();
        return;
      }
      const response = await fetch(url, {
        method, signal: controller.signal,
        ...(body === undefined ? {} : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
      });
      if (!settled && !response.ok && [400, 401, 403, 404, 409, 422, 429].includes(response.status)) {
        outcome = { confirmed: false, uncertain: false };
      }
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : `Не удалось сохранить запись (HTTP ${response.status})`);
      if (!data || data.ok !== true) throw new Error('Сервер не подтвердил сохранение. Обновите журнал перед повторной отправкой.');
      if (!settled) outcome = { confirmed: true, uncertain: false };
      if (current()) onSuccess?.(data, current);
    } catch (error) {
      if (current()) setState({ key, busy: false, error: outcome.uncertain
        ? `${error?.message ? error.message + '. ' : ''}Сохранение не подтверждено. Печать заблокирована; проверьте результат перед повторной отправкой.`
        : error?.message || 'Не удалось сохранить запись.' });
    } finally {
      // Also runs after unmount/close. A prior abort has already settled uncertain;
      // a late response cannot erase it or uncertainty belonging to another token.
      controller.signal.removeEventListener('abort', settle);
      settle();
      if (active.current === controller) {
        active.current = null;
        if (mounted.current && latest.current === key) setState(prev => ({ ...prev, busy: false }));
      }
    }
  };

  const print = (builder, preview, title, dateTo) => {
    if (!mounted.current || active.current || latest.current !== key || !record) return;
    try {
      if (printDirty) throw new Error('Сохраните изменения перед печатью и откройте запись заново.');
      const context = readStoredCompanyRequestContext();
      if (scope !== journalScopeKey() || (context && (context.mode !== 'company'
          || Number(record.companyId) !== Number(context.companyId)))) {
        throw new Error('Компания изменилась. Откройте запись заново.');
      }
      if (![record.companyId, record.projectId].every(id => Number.isSafeInteger(Number(id)) && Number(id) > 0)) {
        throw new Error('Для печати требуется подтверждённая принадлежность записи компании и объекту.');
      }
      const project = { id: record.projectId, companyId: record.companyId, name: record.projectName };
      preview(builder([record], project, record.receivedAt, dateTo || record.receivedAt), title);
      setState({ key, busy: false, error: '' });
    } catch (error) {
      setState({ key, busy: false, error: error.message || 'Печать журнала недоступна.' });
    }
  };

  return { run, cancel, print, printDirty, busy: state.key === key && state.busy, error: state.key === key ? state.error : '' };
}
