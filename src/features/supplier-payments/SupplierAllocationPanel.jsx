import React, { useEffect, useRef, useState } from 'react';
import { paymentKopecks, paymentLabel } from '../../utils/paymentMoney';
import { allocationContext, readAllocationPending, submitAllocation } from './allocationClient';
const money = value => paymentKopecks(value) === null ? '—' : `${paymentLabel(paymentKopecks(value))} ₽`;
function AllocationPanel({ API, userId, companyId, invoiceId, disabled, onBlocked, onSuccess }) {
  const scope = { API, userId, companyId, invoiceId };
  const [context, setContext] = useState(null), [pending, setPending] = useState(null);
  const [paymentId, setPaymentId] = useState(''), [amounts, setAmounts] = useState({});
  const [reason, setReason] = useState(''), [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [storageError, setStorageError] = useState('');
  const [success, setSuccess] = useState(false);
  const cycle = useRef({ active: false, busy: false });
  const callback = useRef(onSuccess); callback.current = onSuccess;
  const sync = () => {
    try { const value = readAllocationPending(scope); setPending(value); setStorageError(''); return value; }
    catch (failure) { setStorageError(failure.message); throw failure; }
  };
  useEffect(() => {
    const lifecycle = cycle.current; lifecycle.active = true; lifecycle.controller = new AbortController();
    const refresh = () => { try { sync(); } catch (_) { /* Visible storage error blocks sends. */ } };
    refresh(); window.addEventListener('storage', refresh);
    return () => { lifecycle.active = false; lifecycle.controller.abort(); window.removeEventListener('storage', refresh); };
    // The scope wrapper remounts and aborts old requests.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => { onBlocked?.(busy || !!pending || !!storageError || !!context?.groupId); },
    [busy, pending, storageError, context, onBlocked]);
  useEffect(() => () => onBlocked?.(false), [onBlocked]);
  const load = async () => {
    const lifecycle = cycle.current;
    if (!lifecycle.active || lifecycle.busy || disabled || storageError) return;
    lifecycle.busy = true; setBusy(true); setError(''); setSuccess(false); setContext(null); setConfirmed(false);
    try {
      if (sync()) throw new Error('Сначала завершите сохранённое распределение.');
      const value = await allocationContext(scope, { signal: lifecycle.controller.signal });
      if (lifecycle.active) {
        setContext(value); setPaymentId(''); setReason('');
        setAmounts(Object.fromEntries((value.allocations || []).map(row => [`${row.paymentId}:${row.receiptId}`, row.amount])));
      }
    } catch (failure) { if (lifecycle.active) setError(failure.message); }
    finally { lifecycle.busy = false; if (lifecycle.active) setBusy(false); }
  };
  const send = async () => {
    const lifecycle = cycle.current;
    if (!lifecycle.active || lifecycle.busy || disabled || storageError || (!pending && (!confirmed || !reason.trim()))) return;
    lifecycle.busy = true; setBusy(true); setError('');
    try {
      const rows = Object.entries(amounts).filter(([, amount]) => paymentKopecks(amount) !== 0)
        .map(([key, amount]) => { const [pid, rid] = key.split(':').map(Number); return { paymentId: pid, receiptId: rid, amount }; });
      await submitAllocation({ scope, context, draft: { reason, rows }, expectedPending: pending || undefined,
        signal: lifecycle.controller.signal });
      if (lifecycle.active) {
        setPending(null); setContext(null); setSuccess(true); setConfirmed(false);
        Promise.resolve().then(() => { if (lifecycle.active) return callback.current?.(); }).catch(() => {
          if (lifecycle.active) setError('Распределение сохранено. Обновите документ.');
        });
      }
    } catch (failure) {
      if (lifecycle.active) {
        setError(failure instanceof TypeError && !failure.status ? 'Связь прервалась. Повторите сохранённое распределение.' : failure.message);
        try {
          const saved = sync();
          if (!saved && failure.code === 'allocation_not_saved') { setContext(null); setConfirmed(false); }
        } catch (_) { /* Keep the visible storage error. */ }
      }
    } finally { lifecycle.busy = false; if (lifecycle.active) setBusy(false); }
  };
  const payment = context?.payments?.find(row => row.paymentId === Number(paymentId));
  const blocked = busy || disabled || !!storageError;
  return <section className="supplier-refund-panel" aria-label="Распределение оплаты по приёмкам">
    <h3>Распределение оплаты по приёмкам</h3>
    <p>Укажите, какую часть каждой оплаты отнести к накладным. Деньги и склад от этого не меняются. Ноль снимает распределение.</p>
    {error && <p role="alert">{error}</p>}{storageError && <p role="alert">{storageError}</p>}
    {success && <p role="status">Распределение сохранено. Новый платёж не создан.</p>}
    {pending ? <>
      <p>Ответ на сохранённое распределение ещё не получен. Повтор проверит тот же запрос.</p>
      <p>Основание: {pending.body.reason}</p>
      <ul>{pending.body.rows.map(row => <li key={`${row.paymentId}:${row.receiptId}`}>
        Оплата #{row.paymentId} → накладная #{pending.context.receipts.find(receipt => receipt.receiptId === row.receiptId)?.warehouseId}: {money(row.amount)}
      </li>)}</ul>
      {!pending.body.rows.length && <p>Снять всё распределение этого счёта.</p>}
      <button type="button" disabled={blocked} onClick={send}>Повторить сохранённое распределение</button>
    </> : !context?.groupId ? <>
      <button type="button" disabled={blocked} onClick={load}>Распределить оплату по приёмкам</button>
      {context && <p>У счёта пока нет группы приёмок для распределения.</p>}
    </> : <form aria-label="Распределение оплаты" onSubmit={event => { event.preventDefault(); send(); }}>
      <fieldset disabled={blocked}>
        {!context.payments.length || !context.receipts.length ? <p>Для распределения нужны проведённая оплата и принятая накладная.</p> : <>
          <label>Оплата для распределения<select value={paymentId} onChange={event => setPaymentId(event.target.value)}>
            <option value="">Выберите оплату</option>
            {context.payments.map(row => <option key={row.paymentId} value={row.paymentId}>Оплата #{row.paymentId} · {money(row.remainingAmount)}</option>)}
          </select></label>
          {payment && <>
            <p>Всего в этой оплате после возвратов: {money(payment.remainingAmount)}. Свободно до изменения: {money(payment.unallocatedAmount)}.</p>
            {context.receipts.map(receipt => <label key={receipt.receiptId}>На накладную #{receipt.warehouseId}, ₽
              <small>Сумма приёмки: {money(receipt.amount)}. Распределено до изменения: {money(receipt.allocated)}.</small>
              <input aria-label={`На накладную #${receipt.warehouseId}, ₽`} inputMode="decimal"
                value={amounts[`${paymentId}:${receipt.receiptId}`] || '0'} onChange={event => {
                  setAmounts({ ...amounts, [`${paymentId}:${receipt.receiptId}`]: event.target.value }); setConfirmed(false);
                }} />
            </label>)}
          </>}
          <label>Основание распределения<textarea required maxLength={1000} value={reason} onChange={event => { setReason(event.target.value); setConfirmed(false); }} /></label>
          <label className="supplier-refund-check"><input type="checkbox" checked={confirmed} required onChange={event => setConfirmed(event.target.checked)} />Подтверждаю распределение всех оплат этого счёта</label>
          <button type="submit" disabled={!confirmed || !reason.trim()}>Сохранить распределение</button>
        </>}
      </fieldset>
      <button type="button" disabled={busy} onClick={() => { setContext(null); setConfirmed(false); }}>Закрыть без сохранения</button>
    </form>}
    {busy && <p role="status">Ожидаем подтверждение распределения…</p>}
  </section>;
}
export default function SupplierAllocationPanel(props) {
  // Delivered together with the source-payment refund workflow and its gates.
  if (process.env.REACT_APP_SUPPLIER_ALLOCATED_REFUNDS_ENABLED !== 'true') return null;
  return <AllocationPanel key={JSON.stringify([props.API, props.userId, props.companyId, props.invoiceId])} {...props} />;
}
