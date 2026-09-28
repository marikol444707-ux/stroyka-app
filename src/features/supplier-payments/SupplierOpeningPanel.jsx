import React, { useEffect, useRef, useState } from 'react';
import { paymentKopecks, paymentLabel } from '../../utils/paymentMoney';
import { previewOpening, readOpeningPending, submitOpening } from './openingClient';

const money = value => `${paymentLabel(paymentKopecks(value))} ₽`;
function OpeningPanel({ API, userId, companyId, invoiceId, registered, disabled, onSuccess, onBlocked }) {
  const scope = { API, userId, companyId, invoiceId };
  const [preview, setPreview] = useState(null);
  const [pending, setPending] = useState(null);
  const [reason, setReason] = useState('');
  const [checked, setChecked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [storageError, setStorageError] = useState('');
  const [success, setSuccess] = useState(null);
  const lifecycle = useRef({ active: false, busy: false, finished: false });
  const callback = useRef(onSuccess); callback.current = onSuccess;
  const syncPending = () => {
    try {
      const value = readOpeningPending(scope);
      setPending(value); setStorageError('');
      return value;
    } catch (failure) { setStorageError(failure.message); throw failure; }
  };
  useEffect(() => {
    const cycle = lifecycle.current;
    cycle.active = true; cycle.controller = new AbortController();
    try { syncPending(); } catch (_) { /* No sends with unreadable storage. */ }
    return () => { cycle.active = false; cycle.controller.abort(); };
    // The wrapper remounts this component for every scope change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    onBlocked?.(busy || !!pending || !!storageError);
  }, [busy, pending, storageError, onBlocked]);
  useEffect(() => () => onBlocked?.(false), [onBlocked]);
  const load = async () => {
    const cycle = lifecycle.current;
    if (!cycle.active || cycle.busy || disabled || storageError) return;
    cycle.busy = true; setBusy(true); setError(''); setPreview(null); setChecked(false);
    try {
      if (syncPending()) throw new Error('Сначала завершите сохранённую сверку.');
      const value = await previewOpening(scope, { signal: cycle.controller.signal });
      if (cycle.active) setPreview(value);
    } catch (failure) { if (cycle.active) setError(failure.message); }
    finally { cycle.busy = false; if (cycle.active) setBusy(false); }
  };
  const send = async () => {
    const cycle = lifecycle.current;
    if (!cycle.active || cycle.busy || cycle.finished || disabled || storageError) return;
    if (!pending && (!checked || !reason.trim() || !preview)) return;
    cycle.busy = true; setBusy(true); setError('');
    try {
      const result = await submitOpening({ scope, preview, reason, expectedPending: pending || undefined,
        signal: cycle.controller.signal });
      cycle.finished = true;
      if (cycle.active) {
        setSuccess(result); setPending(null); setPreview(null);
        Promise.resolve().then(() => { if (cycle.active) return callback.current?.(result); }).catch(() => {
          if (cycle.active) setError('Остаток подтверждён. Обновите документ, чтобы увидеть текущий баланс.');
        });
      }
    } catch (failure) {
      if (cycle.active) {
        setError(failure instanceof TypeError && !failure.status
          ? 'Связь прервалась. Сохранённый запрос можно повторить.' : failure.message);
        try { syncPending(); } catch (_) { /* Visible storage error blocks sends. */ }
        if (failure.status === 409) { setPreview(null); setChecked(false); }
      }
    } finally { cycle.busy = false; if (cycle.active) setBusy(false); }
  };
  if (registered && !pending && !error && !storageError && !success) return null;
  const shown = pending?.preview || preview;
  return <section className="supplier-opening-panel" aria-label="Сверка прежней оплаты">
    <h3>Прежняя оплата по счёту</h3>
    <p>Если счёт оплачивался до ведения журнала, сверьте начальный остаток с документами. Нового платежа и движения по складу не будет.</p>
    {error && <p role="alert">{error}</p>}
    {storageError && <p role="alert">{storageError}</p>}
    {success ? <p role="status">Начальный остаток подтверждён: {money(success.openingPaid)}. Подтверждение остатка не создало нового платежа.</p> : <>
      {!shown && !pending && <button type="button" disabled={busy || disabled || !!storageError}
        onClick={load}>{error ? 'Обновить сверку' : 'Сверить прежнюю оплату'}</button>}
      {shown && <>
        <dl><dt>Сумма счёта</dt><dd>{money(shown.amount)}</dd>
          <dt>Уже оплачено</dt><dd>{money(shown.openingPaid)}</dd>
          <dt>Остаток долга на момент сверки</dt><dd>{money(shown.remainingAmount)}</dd></dl>
        {pending ? <>
          <p>Основание: {pending.body.reason}</p>
          <p>Ответ на сохранённый запрос ещё не получен. Повтор проверит тот же результат.</p>
          <button type="button" disabled={busy || disabled || !!storageError} onClick={send}>Повторить подтверждение</button>
        </> : <form onSubmit={event => { event.preventDefault(); send(); }}>
          <fieldset disabled={busy || disabled || !!storageError}>
            <label>Основание сверки<textarea required maxLength={1000} value={reason}
              onChange={event => setReason(event.target.value)} /></label>
            <label><input type="checkbox" checked={checked} required
              style={{ width: 'auto', minHeight: 0, justifySelf: 'start' }}
              onChange={event => setChecked(event.target.checked)} />Суммы сверены с документами</label>
            <button type="submit" disabled={!checked || !reason.trim()}>Подтвердить начальный остаток</button>
          </fieldset>
        </form>}
      </>}
    </>}
    {busy && <p role="status">Ожидаем ответ сервера…</p>}
  </section>;
}
export default function SupplierOpeningPanel(props) {
  if (process.env.REACT_APP_SUPPLIER_OPENING_CONFIRMATIONS_ENABLED !== 'true') return null;
  return <OpeningPanel key={JSON.stringify([props.API, props.userId, props.companyId, props.invoiceId])} {...props} />;
}
