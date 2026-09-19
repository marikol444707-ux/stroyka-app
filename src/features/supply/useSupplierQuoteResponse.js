import { useEffect, useRef, useState } from 'react';

function requestId() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID();
  const bytes = window.crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = [...bytes].map(byte => byte.toString(16).padStart(2, '0')).join('');
  return [hex.slice(0, 8), hex.slice(8, 12), hex.slice(12, 16), hex.slice(16, 20), hex.slice(20)].join('-');
}

export default function useSupplierQuoteResponse({ API, actorId, offerId, onSaved }) {
  const scope = JSON.stringify([API, actorId, offerId]);
  const lifecycle = useRef({ scope, mounted: true, generation: 0, busy: false });
  if (lifecycle.current.scope !== scope) {
    lifecycle.current = { scope, mounted: true, generation: lifecycle.current.generation + 1, busy: false };
  }
  const pending = useRef(null);
  const [state, setState] = useState({ owner: lifecycle.current, busy: false, error: '' });
  useEffect(() => {
    lifecycle.current.mounted = true;
    return () => { lifecycle.current.mounted = false; lifecycle.current.generation++; };
  }, []);

  async function submit(body) {
    const owner = lifecycle.current;
    if (!owner.mounted || owner.scope !== scope || owner.busy) return;
    const generation = owner.generation;
    const current = () => lifecycle.current === owner && owner.mounted && owner.generation === generation;
    owner.busy = true;
    setState({ owner, busy: true, error: '' });
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);
    try {
      const signature = scope + JSON.stringify(body);
      if (pending.current?.signature !== signature) pending.current = { signature, requestId: requestId() };
      const response = await fetch(API + '/supplier-offers/' + offerId, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...body, requestId: pending.current.requestId }), signal: controller.signal,
      });
      const saved = await response.json().catch(() => null);
      if (!response.ok || saved?.detail || saved?.error) {
        const reason = typeof saved?.detail === 'string' ? saved.detail : saved?.error || response.status;
        throw new Error('Не удалось отправить КП: ' + reason);
      }
      if (Number(saved?.id) !== Number(offerId) || (saved?.status !== 'Получено' && saved?.submissionAccepted !== true)) {
        throw new Error('Сервер не подтвердил сохранение КП.');
      }
      if (current()) {
        pending.current = null;
        await onSaved();
      }
    } catch (failure) {
      if (current()) {
        const reason = failure.name === 'AbortError' ? 'Истекло время ожидания ответа.' : failure instanceof TypeError ? 'Связь с сервером прервалась.' : failure.message;
        const error = reason + ' Черновик сохранён. При обрыве связи результат неизвестен; повторите отправку без изменения данных или обновите заявки для сверки.';
        setState({ owner, busy: false, error });
        // Keep the existing HTTP error notification as well as the persistent form error.
        if (failure.message.startsWith('Не удалось отправить КП:')) window.alert(failure.message);
      }
    } finally {
      clearTimeout(timeout);
      owner.busy = false;
      if (current()) setState(previous => ({ ...previous, busy: false }));
    }
  }
  return { busy: state.owner === lifecycle.current && state.busy, error: state.owner === lifecycle.current ? state.error : '', submit };
}
