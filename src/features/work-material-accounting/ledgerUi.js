import { useCallback, useEffect, useRef, useState } from 'react';
import { clearWorkBatch, sendWorkBatch, workBatchScope } from './workCommands';

export const formatMoney = value => Number(value || 0).toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' ₽';

export function useLedger({ API, path, companyContext, user, onChanged, onRecovered }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const companyId = companyContext?.selectedCompanyId;
  const scopeKey = JSON.stringify([API, path, companyId, user?.id]);
  const active = useRef({ key: scopeKey, request: 0 });
  if (active.current.key !== scopeKey) active.current = { key: scopeKey, request: 0 };
  const scope = active.current;
  const assertActive = useCallback(() => {
    if (active.current !== scope || !scope.alive) throw new DOMException('Запрос устарел', 'AbortError');
  }, [scope]);
  const reload = useCallback(async (signal) => {
    assertActive();
    const request = ++scope.request;
    const current = () => active.current === scope && scope.alive && scope.request === request && !signal?.aborted;
    try {
      const response = await fetch(API + path, { signal, credentials: 'include', headers: {
        'X-Company-Mode': 'company', 'X-Company-Id': String(companyId),
      } });
      const result = await response.json();
      if (!current()) throw new DOMException('Запрос устарел', 'AbortError');
      if (!response.ok) throw new Error(typeof result?.detail === 'string' ? result.detail : 'Не удалось загрузить учёт.');
      setData(result);
      return result;
    } catch (error) {
      if (!current()) throw new DOMException('Запрос устарел', 'AbortError');
      throw error;
    }
  }, [API, path, companyId, scope, assertActive]);
  useEffect(() => {
    const controller = new AbortController();
    scope.alive = true;
    setData(null); setError(''); setBusy(false);
    reload(controller.signal).catch(e => { if (e.name !== 'AbortError') setError(e.message); });
    return () => { scope.alive = false; controller.abort(); scope.request += 1; };
  }, [reload, scope]);
  const recovered = async batch => {
    await reload(); assertActive();
    await onChanged?.(); assertActive();
    await onRecovered?.(batch); assertActive();
  };
  const submit = async (commandPath, payload) => {
    if (busy || active.current !== scope || !scope.alive) return false;
    setBusy(true); setError('');
    try {
      const scope = workBatchScope(companyContext, user);
      const completed = await sendWorkBatch({ API, scope, commands: [{ path: commandPath, method: 'POST', payload }] });
      await recovered(completed);
      clearWorkBatch(scope);
      return true;
    } catch (e) {
      if (active.current === scope && scope.alive && e.name !== 'AbortError') setError(e.message === 'Failed to fetch'
        ? 'Связь прервалась. Повторите сохранённую отправку, чтобы проверить результат без повторного проведения.'
        : e.message || 'Не удалось подтвердить операцию.');
      return false;
    }
    finally { if (active.current === scope && scope.alive) setBusy(false); }
  };
  return { data, error, busy, submit, recovered, setError, reload };
}
