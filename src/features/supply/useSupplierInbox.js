import { useCallback, useEffect, useRef, useState } from 'react';

const empty = { status: 'loading', offers: [], requests: [], deliveries: [], invoices: [], error: '' };

export default function useSupplierInbox(API, user, includeOrderData=false) {
  const actorId = user?.id || user?.userId || user?.user_id;
  const role = user?.role;
  const scope = `${API}:${actorId}:${role}:${includeOrderData}`;
  const currentScope = useRef(scope);
  currentScope.current = scope;
  const mounted = useRef(true);
  const sequence = useRef(0);
  const controller = useRef(null);
  const [snapshot, setSnapshot] = useState({ ...empty, scope });

  const reload = useCallback(async () => {
    if (!mounted.current || currentScope.current !== scope) return;
    const request = ++sequence.current;
    controller.current?.abort();
    const abort = new AbortController();
    controller.current = abort;
    const current = () => mounted.current && sequence.current === request && currentScope.current === scope;
    setSnapshot({ ...empty, scope });
    const timeout = setTimeout(() => abort.abort(), 20000);
    try {
      if (!actorId || role !== 'поставщик') throw new Error('Войдите в кабинет поставщика');
      const read = async path => {
        const response = await fetch(API + path, { cache: 'no-store', signal: abort.signal });
        const rows = await response.json().catch(() => null);
        if (!response.ok) throw new Error(typeof rows?.detail === 'string' ? rows.detail : `Ошибка сервера (${response.status})`);
        if (!Array.isArray(rows)) throw new Error('Сервер вернул неполный список заявок');
        return rows;
      };
      const [requests, offers, deliveries=[], invoices=[]] = await Promise.all([read('/supply-requests'), read('/supplier-offers'), ...(includeOrderData ? [read('/supply-deliveries'),read('/supplier-invoices')] : [])]);
      const ids = new Set(requests.map(row => String(row.id)));
      if (offers.some(offer => !ids.has(String(offer.requestId)))) {
        throw new Error('Состав заявок изменился. Повторите загрузку');
      }
      if (current()) setSnapshot({ scope, status: 'ready', requests, offers, deliveries, invoices, error: '' });
    } catch (error) {
      if (current()) setSnapshot({ ...empty, scope, status: 'error', error: error.name === 'AbortError'
        ? 'Не удалось загрузить заявки за 20 секунд. Повторите попытку'
        : error.message || 'Не удалось загрузить заявки' });
    } finally {
      clearTimeout(timeout);
      abort.abort();
    }
  }, [API, actorId, role, scope, includeOrderData]);

  useEffect(() => {
    mounted.current = true;
    reload();
    return () => { mounted.current = false; controller.current?.abort(); };
  }, [reload]);

  return { ...(snapshot.scope === scope ? snapshot : empty), reload };
}
