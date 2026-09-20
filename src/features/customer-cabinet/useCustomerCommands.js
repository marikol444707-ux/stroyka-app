import { useEffect, useRef, useState } from 'react';
import { API } from '../../api';

const unknown = 'Результат операции не подтверждён. Обновите страницу и проверьте данные перед повтором.';

export default function useCustomerCommands({ scope, companyId, refresh }) {
  const lifecycle = useRef({ scope, mounted: true, busy: false, uncertain: false });
  if (lifecycle.current.scope !== scope) {
    lifecycle.current = { scope, mounted: true, busy: false, uncertain: false };
  }
  const [state, setState] = useState(null);
  useEffect(() => {
    lifecycle.current.mounted = true;
    return () => { lifecycle.current.mounted = false; };
  }, []);
  async function run(path, { method = 'PUT', body, onSuccess }) {
    const owner = lifecycle.current;
    const current = () => lifecycle.current === owner && owner.mounted;
    if (owner.busy || owner.uncertain) return;
    if (!Number.isSafeInteger(Number(companyId)) || Number(companyId) <= 0) {
      setState({ owner, error: 'Компания объекта не определена. Обновите страницу.' }); return;
    }
    owner.busy = true;
    setState({ owner, error: '' });
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);
    let saved = false;
    try {
      const response = await fetch(API + path, { method, signal: controller.signal,
        headers: { 'Content-Type': 'application/json', 'X-Company-Id': String(companyId), 'X-Company-Mode': 'company' },
        body: JSON.stringify(body),
      });
      const result = await response.json().catch(() => null);
      if (!response.ok) {
        owner.uncertain = response.status >= 500;
        if (current()) setState({ owner, error: owner.uncertain ? unknown : typeof result?.detail === 'string' ? result.detail : 'Операция отклонена сервером (HTTP ' + response.status + ').' });
        return;
      }
      if (result?.ok !== true) throw new Error('Unconfirmed response');
      saved = true;
      if (current()) {
        onSuccess?.();
        await refresh?.();
      }
    } catch (_) {
      // Even an acknowledged write must not repeat against a stale screen.
      owner.uncertain = true;
      if (current()) setState({ owner, error: saved ? 'Изменение сохранено, но обновить данные не удалось. Обновите страницу.' : unknown });
    } finally {
      clearTimeout(timeout);
      owner.busy = false;
      if (current()) setState(previous => ({ owner, error: previous?.owner === owner ? previous.error : '' }));
    }
  }
  return { run, error: state?.owner === lifecycle.current ? state.error : '',
    blocked: lifecycle.current.busy || lifecycle.current.uncertain };
}
