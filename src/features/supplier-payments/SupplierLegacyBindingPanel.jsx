import React, { useEffect, useRef, useState } from 'react';
import { paymentRequest } from './paymentClient';
import SupplierContractReviewPanel from './SupplierContractReviewPanel';

export default function SupplierLegacyBindingPanel(props) {
  if (process.env.REACT_APP_SUPPLIER_LEGACY_CONTRACT_BINDING_ENABLED !== 'true') return null;
  return <BindingContent key={`${props.API}:${props.userId}:${props.companyId}:${props.invoiceId}`} {...props} />;
}

function BindingContent({API, userId, companyId, invoiceId, disabled, onBlocked, onSuccess}) {
  const [context, setContext] = useState(null);
  const [preparing, setPreparing] = useState(false);
  const [reason, setReason] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [pending, setPending] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [storageError, setStorageError] = useState('');
  const alive = useRef(true);
  const controller = useRef(null);
  const sending = useRef(false);
  const key = `supplier-legacy-binding:v1:${API}:${userId}:${companyId}:${invoiceId}`;
  const path = `/supplier-invoices/${invoiceId}/legacy-contract-binding`;
  useEffect(() => {
    alive.current = true;
    try {
      const raw = window.localStorage.getItem(key);
      if (raw) {
        const data = JSON.parse(raw);
        if (data.companyId !== companyId || data.invoiceId !== invoiceId || data.userId !== userId
            || typeof data.body?.requestId !== 'string' || !Number.isSafeInteger(data.body?.contractVersionId)
            || !/^\d+\.\d{2}$/.test(data.body?.expectedAmount) || !data.body?.reason || data.body?.confirmed !== true) {
          throw new Error('Сохранённая привязка повреждена. Требуется сверка.');
        }
        setPending(data.body);
      }
    } catch (e) { setStorageError(e.message || 'Хранилище недоступно.'); }
    return () => { alive.current = false; controller.current?.abort(); };
  }, [key, companyId, invoiceId, userId]);
  useEffect(() => {
    onBlocked?.(!!pending || busy || !!storageError || !!context);
    return () => onBlocked?.(false);
  }, [pending, busy, storageError, context, onBlocked]);
  const request = async body => {
    controller.current?.abort(); controller.current = new AbortController();
    return paymentRequest(API, companyId, path, {body, signal:controller.current.signal});
  };
  const load = async () => {
    setBusy(true); setError('');
    try {
      const value = await request();
      if (value.companyId !== companyId || value.invoiceId !== invoiceId) throw new Error('Ответ относится к другому счёту.');
      if (alive.current) setContext(value);
    } catch (e) { if (alive.current) setError(e.message); }
    finally { if (alive.current) setBusy(false); }
  };
  const send = async () => {
    if (!confirmed || busy || storageError || sending.current) return;
    sending.current = true;
    setBusy(true); setError('');
    try {
      if (!window.navigator.locks?.request) throw new Error('Браузер не поддерживает безопасное повторение операции. Используйте актуальный браузер.');
      await window.navigator.locks.request(key, {mode:'exclusive', ifAvailable:true}, async lock => {
      if (!lock) throw new Error('Привязка выполняется в другой вкладке.');
      const body = pending || {requestId:crypto.randomUUID(), contractVersionId:context.contract.id,
        expectedAmount:context.amount, reason:reason.trim(), confirmed:true};
      if (!pending) {
        const saved = JSON.stringify({userId,companyId,invoiceId,body});
        if (window.localStorage.getItem(key)) throw new Error('В другой вкладке уже сохранён запрос. Откройте счёт заново.');
        window.localStorage.setItem(key,saved);
        if (window.localStorage.getItem(key)!==saved) throw new Error('Не удалось сохранить запрос.');
        setPending(body);
      }
      if (JSON.stringify(JSON.parse(window.localStorage.getItem(key) || 'null')?.body) !== JSON.stringify(body)) {
        throw new Error('Сохранённый запрос изменился. Откройте счёт заново.');
      }
      let value;
      try { value = await request(body); }
      catch (e) {
        if (e.status === 409 && e.detail?.code === 'legacy_binding_not_saved'
            && e.detail.companyId === companyId && e.detail.invoiceId === invoiceId
            && e.detail.requestId === body.requestId
            && JSON.stringify(JSON.parse(window.localStorage.getItem(key) || 'null')?.body) === JSON.stringify(body)) {
          window.localStorage.removeItem(key);
          if (alive.current) { setPending(null); setContext(null); setConfirmed(false); }
          e.definitelyNotSaved = true;
        }
        throw e;
      }
      if (value.companyId!==companyId || value.invoiceId!==invoiceId || value.requestId!==body.requestId
          || value.contractVersionId!==body.contractVersionId || value.bindingStatus!=='bound') {
        throw new Error('Ответ требует сверки. Повторите сохранённый запрос.');
      }
      const stored = JSON.parse(window.localStorage.getItem(key) || 'null');
      if (JSON.stringify(stored?.body) !== JSON.stringify(body)) throw new Error('Сохранённый запрос изменился в другой вкладке. Откройте счёт заново.');
      window.localStorage.removeItem(key);
      if (alive.current) { setPending(null); setContext(null); setConfirmed(false); setReason(''); onSuccess?.(); }
      });
    } catch (e) { if (alive.current) setError(e.definitelyNotSaved
      ? `${e.message} Привязка не сохранена. Проверьте данные заново.`
      : `${e.message} Если запрос сохранён, повторите его после проверки.`); }
    finally { sending.current = false; if (alive.current) setBusy(false); }
  };
  return <section aria-label="Привязка прежнего счёта к договору">
    <h3>Договор</h3>
    <p>Выберите договор, по которому выставлен этот счёт.</p>
    {error && <p role="alert">{error}</p>}
    {storageError && <p role="alert">{storageError} Отправка заблокирована.</p>}
    {!pending && !context && <button type="button" disabled={disabled || busy || preparing || !!storageError} onClick={load}>Выбрать договор</button>}
    {context && !pending && <>
      {context.boundContractId ? <p>Счёт уже связан с версией договора #{context.boundContractId}.</p>
        : !context.contract ? <><p>Сначала добавьте договор и проверьте его реквизиты.</p>
          {!preparing && <button type="button" disabled={disabled || busy} onClick={()=>setPreparing(true)}>Добавить договор</button>}</>
          : <><p>КП № {context.offerId} · {Number(context.amount).toLocaleString('ru-RU',{minimumFractionDigits:2})} ₽</p>
            <p>Договор № {context.contract.snapshot?.number} от {context.contract.snapshot?.date?.split('-').reverse().join('.')} · версия {context.contract.version}</p>
            <p>Проверил: {context.contract.reviewedBy}</p>
            <p>Покупатель: {context.contract.snapshot?.buyer?.fullName} · ИНН {context.contract.snapshot?.buyer?.inn}</p>
            {(context.contract.snapshot?.buyer?.companyId!==context.contract.snapshot?.payer?.companyId || context.contract.snapshot?.buyer?.inn!==context.contract.snapshot?.payer?.inn) && <p>Плательщик: {context.contract.snapshot?.payer?.fullName} · ИНН {context.contract.snapshot?.payer?.inn}</p>}
            <p>Поставщик: {context.contract.snapshot?.supplier?.fullName} · ИНН {context.contract.snapshot?.supplier?.inn}</p>
            <label>Комментарий<input placeholder="Например: счёт соответствует договору" value={reason} maxLength={1000} onChange={e=>setReason(e.target.value)} /></label></>}


    </>}
    {preparing && context && <SupplierContractReviewPanel API={API} userId={userId} companyId={companyId} offerId={context.offerId}
      disabled={disabled || busy} onClose={()=>setPreparing(false)} onSaved={()=>{setPreparing(false);load();}}/>}
    {pending && <p>Сохранённый запрос: версия договора #{pending.contractVersionId}, счёт {pending.expectedAmount} ₽. Основание: {pending.reason}</p>}
    {!preparing && (pending || (context?.contract && !context.boundContractId)) && <>
      <label className="supplier-original-review-check"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)} />Договор подходит к этому счёту</label>
      <button className="payment-primary" type="button" disabled={disabled || busy || !!storageError || !confirmed || (!pending && !reason.trim())} onClick={send}>
        {pending ? 'Повторить подтверждение' : 'Подтвердить договор'}</button>
    </>}
    {!preparing && context && !pending && <div className="payment-secondary-actions">
      {context.contract && !context.boundContractId && <button type="button" disabled={disabled || busy}
        onClick={()=>{setPreparing(true);setConfirmed(false);}}>Изменить договор</button>}
      <button type="button" disabled={busy} onClick={()=>{setContext(null);setConfirmed(false);}}>Назад</button>
    </div>}
  </section>;
}
