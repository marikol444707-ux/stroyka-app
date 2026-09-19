import { useEffect, useRef, useState } from 'react';

export default function useSupplierOfferCheck({ API, scope, requestId, supplierOffers }) {
  const lifecycle = useRef({ scope, mounted: true, busy: false });
  if (lifecycle.current.scope !== scope) {
    lifecycle.current.controller?.abort();
    clearTimeout(lifecycle.current.timeout);
    lifecycle.current = { scope, mounted: true, busy: false };
  }
  const [state, setState] = useState(null);
  useEffect(() => {
    lifecycle.current.mounted = true;
    return () => {
      lifecycle.current.mounted = false;
      lifecycle.current.controller?.abort();
      clearTimeout(lifecycle.current.timeout);
    };
  }, []);

  async function reload() {
    const owner = lifecycle.current;
    if (!owner.mounted || owner.scope !== scope || owner.busy) return;
    owner.busy = true;
    owner.controller = new AbortController();
    const current = () => lifecycle.current === owner && owner.mounted;
    const base = { owner, source: supplierOffers, rows: null, offers: [], error: '' };
    setState({ ...base, status: 'loading' });
    owner.timeout = setTimeout(() => owner.controller.abort(), 20000);
    try {
      const read = async path => {
        const response = await fetch((API || '') + path, { cache: 'no-store', signal: owner.controller.signal });
        const data = await response.json().catch(() => null);
        if (!response.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : 'Ошибка загрузки: HTTP ' + response.status);
        if (!Array.isArray(data)) throw new Error('Сервер вернул некорректные данные. Повторите обновление.');
        return data;
      };
      const [rows, offers] = await Promise.all([read('/supply-requests/' + requestId + '/recipients'), read('/supplier-offers')]);
      if (current()) setState({ ...base, rows, offers: offers.filter(o => o.requestId === requestId), status: 'ready' });
    } catch (failure) {
      if (current()) setState({ ...base, status: 'error', error: failure.name === 'AbortError'
        ? 'Истекло время ожидания. Повторите обновление.' : failure.message || 'Не удалось обновить КП и уведомления.' });
    } finally {
      clearTimeout(owner.timeout);
      owner.controller.abort();
      owner.busy = false;
    }
  }
  const snapshot = state?.owner === lifecycle.current && state?.source === supplierOffers ? state : null;
  return { reload, status: snapshot?.status || 'idle', rows: snapshot?.rows || null, error: snapshot?.error || '',
    offers: snapshot ? snapshot.offers : (supplierOffers || []).filter(o => o.requestId === requestId) };
}
