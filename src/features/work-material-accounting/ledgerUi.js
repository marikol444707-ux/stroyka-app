import { useCallback, useEffect, useState } from 'react';
import { clearWorkBatch, sendWorkBatch, workBatchScope } from './workCommands';

export const formatMoney = value => Number(value || 0).toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' ₽';

export function useLedger({ API, path, companyContext, user, onChanged, onRecovered }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const companyId = companyContext?.selectedCompanyId;
  const reload = useCallback(async (signal) => {
    const response = await fetch(API + path, { signal, credentials: 'include', headers: {
      'X-Company-Mode': 'company', 'X-Company-Id': String(companyId),
    } });
    const result = await response.json();
    if (!response.ok) throw new Error(typeof result?.detail === 'string' ? result.detail : 'Не удалось загрузить учёт.');
    setData(result);
    return result;
  }, [API, path, companyId]);
  useEffect(() => {
    const controller = new AbortController();
    setData(null); setError('');
    reload(controller.signal).catch(e => { if (e.name !== 'AbortError') setError(e.message); });
    return () => controller.abort();
  }, [reload]);
  const recovered = async batch => { await reload(); await onChanged?.(); await onRecovered?.(batch); };
  const submit = async (commandPath, payload) => {
    if (busy) return false;
    setBusy(true); setError('');
    try {
      const scope = workBatchScope(companyContext, user);
      const completed = await sendWorkBatch({ API, scope, commands: [{ path: commandPath, method: 'POST', payload }] });
      await recovered(completed);
      clearWorkBatch(scope);
      return true;
    } catch (e) {
      setError(e.message === 'Failed to fetch'
        ? 'Связь прервалась. Повторите сохранённую отправку, чтобы проверить результат без повторного проведения.'
        : e.message || 'Не удалось подтвердить операцию.');
      return false;
    }
    finally { setBusy(false); }
  };
  return { data, error, busy, submit, recovered, setError, reload };
}
