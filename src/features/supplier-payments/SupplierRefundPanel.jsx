import React, { useEffect, useRef, useState } from 'react';
import { paymentKopecks, paymentLabel } from '../../utils/paymentMoney';
import { refundContext, readRefundPending, submitRefund, cancelRefund } from './refundClient';
const money = value => paymentKopecks(value) === null ? '—' : `${paymentLabel(paymentKopecks(value))} ₽`;
const decimal = cents => `${Math.floor(cents / 100)}.${String(cents % 100).padStart(2, '0')}`;
const today = () => new Intl.DateTimeFormat('sv-SE', { timeZone: 'Europe/Moscow' }).format(new Date());
function RefundPanel({ API, userId, companyId, invoiceId, disabled, onBlocked, onSuccess }) {
  const scope = { API, userId, companyId, invoiceId };
  const [context, setContext] = useState(null), [pending, setPending] = useState(null);
  const [paymentId, setPaymentId] = useState(''), [free, setFree] = useState('0'), [releases, setReleases] = useState({});
  const [paidAt, setPaidAt] = useState(today), [reason, setReason] = useState(''), [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [storageError, setStorageError] = useState('');
  const [success, setSuccess] = useState(null), [cancelConfirmed, setCancelConfirmed] = useState(false);
  const lifecycle = useRef({ active: false, busy: false, finished: false });
  const callback = useRef(onSuccess); callback.current = onSuccess;
  const sync = () => {
    try { const saved = readRefundPending(scope); setPending(saved); setStorageError(''); return saved; }
    catch (failure) { setStorageError(failure.message); throw failure; }
  };
  useEffect(() => {
    const cycle = lifecycle.current; cycle.active = true; cycle.controller = new AbortController();
    const refresh = () => { try { sync(); } catch (_) { /* Fail closed with a visible error. */ } };
    refresh(); window.addEventListener('storage', refresh);
    return () => { cycle.active = false; cycle.controller.abort(); window.removeEventListener('storage', refresh); };
    // Scope changes remount this component and abort its previous requests.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => { onBlocked?.(busy || !!pending || !!storageError || (!!context?.groupId && !success)); },
    [busy, pending, storageError, context, success, onBlocked]);
  useEffect(() => () => onBlocked?.(false), [onBlocked]);
  const load = async () => {
    const cycle = lifecycle.current;
    if (!cycle.active || cycle.busy || disabled || storageError) return;
    cycle.busy = true; setBusy(true); setError(''); setConfirmed(false); setContext(null);
    try {
      if (sync()) throw new Error('Сначала завершите сохранённый возврат.');
      const value = await refundContext(scope, { signal: cycle.controller.signal });
      if (cycle.active) { setContext(value); setPaymentId(''); setFree('0'); setReleases({}); }
    } catch (failure) { if (cycle.active) setError(failure.message); }
    finally { cycle.busy = false; if (cycle.active) setBusy(false); }
  };
  const payment = context?.payments?.find(row => row.paymentId === Number(paymentId));
  const assigned = context?.allocations?.filter(row => row.paymentId === Number(paymentId)) || [];
  const parts = [free, ...assigned.map(row => releases[row.receiptId] || '0')].map(paymentKopecks);
  const total = parts.every(value => value !== null) ? parts.reduce((sum, value) => sum + value, 0) : null;
  const send = async cancel => {
    const cycle = lifecycle.current;
    if (!cycle.active || cycle.busy || cycle.finished || disabled || storageError) return;
    if (cancel && !pending?.cancelRequested && !cancelConfirmed) return;
    if (!cancel && !pending && (!confirmed || !payment || !(total > 0) || !reason.trim())) return;
    cycle.busy = true; setBusy(true); setError('');
    try {
      const options = { scope, context, expectedPending: pending || undefined, signal: cycle.controller.signal,
        draft: { paymentId: Number(paymentId), amount: total === null ? '' : decimal(total), unallocatedAmount: free, paidAt, reason,
          releases: assigned.filter(row => paymentKopecks(releases[row.receiptId] || '0') > 0)
            .map(row => ({ receiptId: row.receiptId, amount: releases[row.receiptId] })) } };
      const result = await (cancel ? cancelRefund(options) : submitRefund(options));
      cycle.finished = true;
      if (cycle.active) {
        setSuccess(result); setPending(null); setContext(null);
        Promise.resolve().then(() => { if (cycle.active) return callback.current?.(result); }).catch(() => {
          if (cycle.active) setError('Результат подтверждён. Обновите документ, чтобы увидеть баланс.');
        });
      }
    } catch (failure) {
      if (cycle.active) {
        setError(failure instanceof TypeError && !failure.status ? 'Связь прервалась. Повторите сохранённый запрос.' : failure.message);
        try { sync(); } catch (_) { /* Storage error blocks further sends. */ }
      }
    } finally { cycle.busy = false; if (cycle.active) setBusy(false); }
  };
  const blocked = busy || disabled || !!storageError;
  return <section className="supplier-refund-panel" aria-label="Возврат денег">
    <h3>Возврат денег</h3>
    <p>Укажите, сколько денег вернул поставщик и за какую оплату. Если оплата относится к накладным, укажите сумму возврата по каждой.</p>
    {error && <p role="alert">{error}</p>}{storageError && <p role="alert">{storageError}</p>}
    {success ? <p role="status">{success.status === 'cancelled' ? 'Попытка отменена. Возврат не записан.'
      : `Возврат подтверждён: ${money((success.result || success).amount)}. Операция #${(success.result || success).operationId}.`}</p>
      : pending ? <>
        <p>Сохранённый возврат: {money(pending.body.amount)} · оплата #{pending.body.paymentId} · {pending.body.paidAt}</p>
        <p>Основание: {pending.body.reason}</p>
        <p>Результат ещё не подтверждён. Повтор проверит тот же запрос.</p>
        {!pending.cancelRequested && <button type="button" disabled={blocked} onClick={() => send(false)}>Повторить сохранённый возврат</button>}
        {!pending.cancelRequested && <label className="supplier-refund-check"><input type="checkbox" checked={cancelConfirmed}
          disabled={blocked} onChange={event => setCancelConfirmed(event.target.checked)} />Подтверждаю отмену попытки возврата</label>}
        <button type="button" disabled={blocked || (!pending.cancelRequested && !cancelConfirmed)} onClick={() => send(true)}>
          {pending.cancelRequested ? 'Повторить отмену попытки' : 'Отменить попытку возврата'}</button>
        <p>Повторная проверка не создаст второй возврат.</p>
      </> : <>
        {!context && <button type="button" disabled={blocked} onClick={load}>Оформить возврат по оплате</button>}
        {context?.groupId === null && <p>По этому счёту ещё нет принятых накладных. Запишите возврат в форме ниже.</p>}
        {context?.groupId && <form aria-label="Возврат по приёмкам" onSubmit={event => { event.preventDefault(); send(false); }}>
          <fieldset disabled={blocked}>
            <label>Исходная оплата<select value={paymentId} required onChange={event => {
              setPaymentId(event.target.value); setFree('0'); setReleases({}); setConfirmed(false);
            }}><option value="">Выберите оплату</option>{context.payments.map(row =>
              <option key={row.paymentId} value={row.paymentId}>Оплата #{row.paymentId} · осталось {money(row.remainingAmount)}</option>)}</select></label>
            {!context.payments.length && <p>Нет оплат с доступной суммой для возврата.</p>}
            {payment && <>
              <p>Свободно по оплате: {money(payment.unallocatedAmount)}</p>
              <label>Из свободного остатка, ₽<input inputMode="decimal" value={free} onChange={event => { setFree(event.target.value); setConfirmed(false); }} /></label>
              {assigned.map(row => {
                const receipt = context.receipts.find(item => item.receiptId === row.receiptId);
                return <label key={row.receiptId}>Снять с накладной #{receipt.warehouseId}, ₽
                  <small>Распределено: {money(row.amount)}</small>
                  <input aria-label={`Снять с накладной #${receipt.warehouseId}, ₽`} inputMode="decimal" value={releases[row.receiptId] || '0'}
                    onChange={event => { setReleases({ ...releases, [row.receiptId]: event.target.value }); setConfirmed(false); }} /></label>;
              })}
              <p>Итого возврат: <strong>{total === null ? '—' : money(decimal(total))}</strong></p>
              <label>Дата получения возврата<input type="date" required value={paidAt} onChange={event => setPaidAt(event.target.value)} /></label>
              <label>Основание возврата<textarea required maxLength={1000} value={reason} onChange={event => setReason(event.target.value)} /></label>
              <label className="supplier-refund-check"><input type="checkbox" required checked={confirmed}
                onChange={event => setConfirmed(event.target.checked)} />Возврат денег фактически получен</label>
              <button type="submit" disabled={!confirmed || !reason.trim() || !(total > 0)}>Подтвердить возврат</button>
            </>}
          </fieldset>
          <button type="button" disabled={busy} onClick={() => { setContext(null); setConfirmed(false); }}>Закрыть форму возврата</button>
        </form>}
      </>}
    {busy && <p role="status">Ожидаем подтверждение возврата…</p>}
  </section>;
}
export default function SupplierRefundPanel(props) {
  if (process.env.REACT_APP_SUPPLIER_ALLOCATED_REFUNDS_ENABLED !== 'true') return null;
  return <RefundPanel key={JSON.stringify([props.API, props.userId, props.companyId, props.invoiceId])} {...props} />;
}
