import React, { useEffect, useId, useRef, useState } from 'react';
import { paymentKopecks, paymentLabel } from '../../utils/paymentMoney';
import useSupplierPaymentDialog from './useSupplierPaymentDialog';
import './SupplierPaymentDialog.css';
import SupplierOpeningPanel from './SupplierOpeningPanel';

const documentLabel = kind => ({ invoice: 'счёт', warehouse: 'накладная' }[kind] || 'документ');
const operationLabel = kind => ({payment:'Платёж',refund:'Возврат денег',credit:'Уменьшение суммы счёта',reversal:'Сторно'}[kind] || 'Операция');

const money = amount => {
  const cents = paymentKopecks(amount);
  return cents === null ? '—' : `${paymentLabel(cents)} ₽`;
};

function PaymentDialogContent(props) {
  const state = useSupplierPaymentDialog(props);
  const [openingBlocked, setOpeningBlocked] = useState(false);
  const titleId = useId();
  const root = useRef(null);
  const close = useRef(null);
  useEffect(() => {
    const previous = document.activeElement;
    close.current?.focus();
    return () => { if (previous?.isConnected) previous.focus(); };
  }, []);
  const keyDown = event => {
    if (event.key === 'Escape') { event.stopPropagation(); props.onClose?.(); }
    if (event.key !== 'Tab') return;
    const nodes = [...root.current.querySelectorAll('button, input, select, textarea, [tabindex="0"]')]
      .filter(node => !node.matches(':disabled'));
    const first = nodes[0], last = nodes[nodes.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
  };
  const blocked = openingBlocked || state.busy || state.loading || !!state.storageError || !state.snapshot;
  const reversingPayment = state.reversal?.operation.kind === 'payment';
  const reversalTitle = reversingPayment ? 'Сторно платежа' : 'Сторно операции';
  return <div className="supplier-payment-dialog-backdrop">
    <section className="supplier-payment-dialog" role="dialog" aria-modal="true" aria-labelledby={titleId}
      ref={root} onKeyDown={keyDown}>
      <header><h2 id={titleId}>Оплата поставщику</h2><button type="button" ref={close} onClick={props.onClose}>Закрыть</button></header>
      <p>Компания #{props.companyId} · {documentLabel(props.documentKind)} #{props.documentId}</p>
      {state.loading && <p role="status">Загрузка документа и истории…</p>}
      {state.error && <p role="alert">{state.error}</p>}
      {state.storageError && <p role="alert">{state.storageError} Отправка заблокирована.</p>}
      {(state.error || state.storageError) && <button type="button" disabled={state.busy || state.loading} onClick={state.reload}>Обновить документ и историю</button>}
      {state.snapshot && <div className="supplier-payment-dialog-summary">
        <p>Документ оплаты: {documentLabel(state.snapshot.canonicalTarget.documentKind)} #{state.snapshot.canonicalTarget.documentId}</p>
        <p>Поставщик #{state.snapshot.scope?.supplierId} · {state.snapshot.scope?.projectName || 'Без объекта'} · {state.snapshot.scope?.workPackage || 'Без пакета'}</p>
        <p>Остаток долга: <strong>{money(state.snapshot.remainingAmount)}</strong></p>
        {Number(state.snapshot.openingPaidAmount)>0 && <p>Прежняя оплата на момент регистрации: {money(state.snapshot.openingPaidAmount)}</p>}
        {Number(state.snapshot.creditAmount)>0 && <p>Исходная сумма: {money(state.snapshot.amount)} · Уменьшение: {money(state.snapshot.creditAmount)} · К расчёту: {money(state.snapshot.effectiveAmount)}</p>}
        {Number(state.snapshot.overpaidAmount)>0 && <p>Переплата поставщику: <strong>{money(state.snapshot.overpaidAmount)}</strong>. Возврат денег фиксируется после фактического получения.</p>}
      </div>}
      {props.documentKind === 'invoice' && <SupplierOpeningPanel API={props.API} userId={props.userId}
        companyId={props.companyId} invoiceId={props.documentId}
        registered={state.snapshot?.openingPaidAmount != null}
        disabled={state.busy || state.loading || !!state.pending || !!state.storageError || !state.snapshot}
        onBlocked={setOpeningBlocked} onSuccess={() => { state.reload(); props.onSuccess?.(); }} />}
      {state.pending && <section aria-label="Незавершённая операция">
        <h3>Сохранённый запрос</h3>
        <p>Результат ещё не подтверждён. Запрос может относиться к другому документу этой компании. Повтор отправляет ту же команду с тем же UUID.</p>
        <pre aria-label="Сохранённая команда" tabIndex={0}>{JSON.stringify(state.pending, null, 2)}</pre>
        {!state.pending.cancelRequested && <button type="button" disabled={state.busy || !!state.storageError} onClick={state.retry}>Повторить сохранённый запрос</button>}
        <p>Если операция уже проведена, получим подтверждение; сторно автоматически не выполняется</p>
        {!state.pending.cancelRequested && <label><input type="checkbox" checked={!!state.cancellationConfirmed}
          style={{ width: 'auto', minHeight: 0, justifySelf: 'start' }} disabled={state.busy || !!state.storageError}
          onChange={event => state.confirmCancellation(event.target.checked)} />Подтверждаю отмену сохранённой попытки</label>}
        <button type="button" disabled={state.busy || !!state.storageError || (!state.pending.cancelRequested && !state.cancellationConfirmed)}
          onClick={state.cancelPending}>{state.pending.cancelRequested ? 'Повторить отмену попытки' : 'Отменить попытку'}</button>
        <p>Не создавайте новый платёж вместо завершения сохранённой попытки.</p>
      </section>}
      {state.success && <section>
        {state.success.status === 'cancelled'
          ? <p role="status">Попытка отменена. Денежная операция не проведена.</p>
          : <p role="status">{state.success.kind === 'reversal' ? 'Сторно подтверждено.' : state.success.kind === 'payment' ? 'Платёж подтверждён.' : `${operationLabel(state.success.kind)}: запись подтверждена.`} Операция #{state.success.operationId}.</p>}
        <button type="button" disabled={blocked || !!state.error || !!state.pending} onClick={state.startNext}>Новый платёж</button>
      </section>}
      {!state.pending && !state.success && state.reversal && <form aria-label={reversalTitle}
        onSubmit={event => { event.preventDefault(); state.submitReversal(); }}>
        <fieldset disabled={blocked}>
          <legend>{reversalTitle}</legend>
          <p>{state.reversal.operation.kind==='payment' ? 'Исходный платёж' : operationLabel(state.reversal.operation.kind)} #{state.reversal.operation.operationId}: {money(state.reversal.operation.amount)} от {state.reversal.operation.paidAt}</p>
          <p>Документ исходной операции: {documentLabel(state.reversal.operation.documentKind)} #{state.reversal.operation.documentId}. Сумма сторно определяется сервером; исходная запись сохраняется.</p>
          {state.reversal.operation.kind==='credit' && <p>Сумма счёта к оплате увеличится обратно. Денежного движения не будет.</p>}
          {state.reversal.operation.kind==='refund' && <p>Записанный возврат отменится, оплаченная сумма увеличится. Банковский перевод не выполняется.</p>}
          <label>Дата сторно<input type="date" required value={state.reversal.paidAt}
            onChange={event => state.updateReversal({ paidAt: event.target.value })} /></label>
          <label>Причина сторно<textarea required maxLength={1000} value={state.reversal.reason}
            onChange={event => state.updateReversal({ reason: event.target.value })} /></label>
          <label><input type="checkbox" required checked={state.reversal.confirmed}
            style={{ width: 'auto', minHeight: 0, justifySelf: 'start' }}
            onChange={event => state.updateReversal({ confirmed: event.target.checked })} />{reversingPayment ? 'Подтверждаю сторно выбранного платежа' : 'Подтверждаю сторно выбранной операции'}</label>
          <button type="submit">{state.busy ? 'Запись сторно…' : 'Подтвердить сторно'}</button>
        </fieldset>
        <button type="button" disabled={state.busy || !!state.storageError} onClick={state.cancelReversal}>Отменить черновик сторно</button>
      </form>}
      {!state.pending && !state.success && !state.reversal && <form aria-label="Запись платежа" onSubmit={event => { event.preventDefault(); state.submit(); }}>
        <fieldset disabled={blocked}>
          <legend>{state.draft.kind && state.draft.kind!=='payment' ? operationLabel(state.draft.kind) : 'Новый платёж'}</legend>
          {state.snapshot?.settlementsEnabled && <label>Вид операции<select value={state.draft.kind || 'payment'}
            onChange={event => state.updateDraft({kind:event.target.value,amount:''})}>
            <option value="payment">Платёж поставщику</option><option value="refund">Возврат денег от поставщика</option>
            <option value="credit">Уменьшение суммы счёта</option>
          </select></label>}
          <label>Сумма, ₽<input inputMode="decimal" autoComplete="off" required value={state.draft.amount}
            onChange={event => state.updateDraft({ amount: event.target.value })} /></label>
          <label>{state.draft.kind && state.draft.kind!=='payment' ? 'Дата операции' : 'Дата оплаты'}<input type="date" required value={state.draft.paidAt}
            onChange={event => state.updateDraft({ paidAt: event.target.value })} /></label>
          <label>{state.draft.kind && state.draft.kind!=='payment' ? 'Основание и номер документа' : 'Основание платежа'}<textarea required maxLength={1000} value={state.draft.reason}
            onChange={event => state.updateDraft({ reason: event.target.value })} /></label>
          <p>{state.draft.kind==='credit' ? 'Укажите основание и номер корректирующего документа. Уменьшается обязательство; деньги и склад не меняются.'
            : state.draft.kind==='refund' ? 'Запишите только фактически полученный возврат, с датой и основанием. Стоимость счёта не меняется.'
            : 'Можно оплатить частями или раньше срока. График не ограничивает сумму платежа; остаток долга проверяется сервером.'}</p>
          <button type="submit">{state.busy ? 'Запись…' : state.draft.kind==='credit' ? 'Записать корректировку' : state.draft.kind==='refund' ? 'Записать возврат' : 'Записать платёж'}</button>
        </fieldset>
      </form>}
      {state.busy && <p role="status">Ожидаем подтверждение. При закрытии окна сохранённый запрос останется доступен для повтора.</p>}
      {state.history && <section aria-label="История платежей">
        <h3>Последние операции</h3>
        {!state.history.items.length && <p>Платежей пока нет.</p>}
        <ul>{state.history.items.map(item => <li key={item.operationId}>
          <p>{item.kind === 'reversal' ? `Сторно операции #${item.reversesId}` : `${operationLabel(item.kind)} #${item.operationId}`} · {money(item.amount)} · {item.paidAt}</p>
          <p>{item.reason}</p>
          {item.reversedById && <p>Сторнирован операцией #{item.reversedById}</p>}
          {['payment','refund','credit'].includes(item.kind) && item.reversedById === null && <button type="button"
            disabled={blocked || !!state.pending || !!state.reversal} onClick={() => state.beginReversal(item.operationId)}>
            {item.kind==='payment' ? 'Сторнировать платёж' : 'Сторнировать операцию'} #{item.operationId}</button>}
        </li>)}</ul>
        {state.history.hasMore && <p>Показаны только последние 50 операций; история не полная.</p>}
      </section>}
    </section>
  </div>;
}

export default function SupplierPaymentDialog({ open = true, ...props }) {
  if (!open || process.env.REACT_APP_SUPPLIER_PAYMENTS_ENABLED !== 'true') return null;
  return <PaymentDialogContent key={JSON.stringify([props.API, props.userId, props.companyId, props.documentKind, props.documentId])} {...props} />;
}
