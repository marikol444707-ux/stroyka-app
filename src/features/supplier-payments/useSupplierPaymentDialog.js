import { useEffect, useRef, useState } from 'react';
import { paymentKopecks } from '../../utils/paymentMoney';
import { cancelPendingPayment, paymentPath, paymentRequest, readPending, submitPayment } from './paymentClient';

const positiveId = id => Number.isSafeInteger(id) && id > 0;
const targetValid = target => ['invoice', 'warehouse'].includes(target?.documentKind) && positiveId(target?.documentId);
const empty = () => ({ snapshot: null, history: null, loading: true, busy: false, error: '', storageError: '',
  pending: null, success: null, reversal: null, cancellationConfirmed: false, draft: { amount: '', paidAt: '', reason: '' } });

export default function useSupplierPaymentDialog({ API, userId, companyId, documentKind, documentId, onSuccess }) {
  const key = JSON.stringify([API, userId, companyId, documentKind, documentId]);
  const current = useRef(null);
  const callback = useRef(onSuccess); callback.current = onSuccess;
  if (current.current?.key !== key) current.current = { key, active: false, busy: false, retired: false, generation: 0, intent: 0 };
  const cycle = current.current;
  const intent = cycle.intent;
  const [state, setState] = useState(() => ({ ...empty(), key }));
  const live = () => current.current === cycle && cycle.active;
  const patch = values => { if (live()) setState(old => ({ ...old, ...values, key })); };
  const value = state.key === key ? state : empty();
  const checkPending = () => {
    try { const pending = readPending({ userId, companyId }); patch({ pending, storageError: '' }); return pending; }
    catch (error) { patch({ storageError: error.message }); throw error; }
  };
  const load = async () => {
    const generation = ++cycle.generation;
    patch({ loading: true, snapshot: null, history: null, error: '' });
    try {
      if (!positiveId(userId) || !positiveId(companyId) || !targetValid({ documentKind, documentId })) throw new Error('Не определён контекст оплаты.');
      const snapshot = await paymentRequest(API, companyId,
        `/companies/${companyId}/supplier-payment-documents/${documentKind}/${documentId}`, { signal: cycle.controller.signal });
      if (snapshot?.schemaVersion !== 1 || snapshot.companyId !== companyId || snapshot.documentKind !== documentKind
          || snapshot.documentId !== documentId || !targetValid(snapshot.canonicalTarget)
          || !['amount', 'paidAmount', 'remainingAmount'].every(field => typeof snapshot[field] === 'string' && paymentKopecks(snapshot[field]) !== null)) {
        throw new Error('Ответ документа не соответствует контексту оплаты.');
      }
      const target = snapshot.canonicalTarget;
      const history = await paymentRequest(API, companyId,
        `${paymentPath(companyId)}?documentKind=${target.documentKind}&documentId=${target.documentId}&limit=50`, { signal: cycle.controller.signal });
      if (history?.schemaVersion !== 1 || history.companyId !== companyId || !Array.isArray(history.items)
          // The server filters by impacts, not operation origin: paired-document
          // operations can legitimately retain a different original document ID.
          || history.items.some(item => item.companyId !== companyId || !targetValid(item))) {
        throw new Error('История не соответствует контексту оплаты.');
      }
      if (generation === cycle.generation) patch({ snapshot, history });
    } catch (error) { if (generation === cycle.generation) patch({ error: error instanceof TypeError && !error.status
      ? 'Не удалось загрузить документ и историю. Проверьте связь и обновите данные.' : error.message }); }
    finally { if (generation === cycle.generation) patch({ loading: false }); }
  };
  useEffect(() => {
    cycle.active = true; cycle.controller = new AbortController();
    setState({ ...empty(), key });
    try { checkPending(); } catch (_) { /* Fail closed, while allowing document reads. */ }
    load();
    return () => { cycle.active = false; cycle.generation += 1; cycle.controller.abort(); };
    // Each effect owns exactly one immutable scope and its request controller.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const eligible = operation => operation?.companyId === companyId && operation.kind === 'payment'
    && operation.reversedById === null && positiveId(operation.operationId) && targetValid(operation);
  const send = async mode => {
    const cancelling = mode === 'cancel', retry = mode === 'retry', reversing = mode === 'reversal';
    if (!live() || cycle.busy || cycle.retired || intent !== cycle.intent) return;
    let input;
    try {
      const pending = checkPending();
      if (retry || cancelling) {
        if (!pending) throw new Error('Сохранённая операция не найдена.');
        if (retry && pending.cancelRequested) throw new Error('Запрошена отмена попытки. Повторите отмену попытки.');
        if (JSON.stringify(pending.body) !== JSON.stringify(value.pending?.body)) {
          patch({ cancellationConfirmed: false });
          throw new Error('Сохранённая команда изменилась. Проверьте её и подтвердите действие заново.');
        }
        if (cancelling && !pending.cancelRequested && !value.cancellationConfirmed) throw new Error('Подтвердите отмену сохранённой попытки.');
      } else if (pending) throw new Error('Сначала завершите сохранённую операцию.');
      if (!retry && !cancelling) {
        if (!value.snapshot || value.loading) throw new Error('Дождитесь загрузки документа и истории.');
        if (reversing) {
          const reversal = value.reversal;
          const original = value.history?.items.find(item => item.operationId === reversal?.operation.operationId);
          if (!eligible(original) || !reversal?.confirmed) throw new Error('Выберите доступный платёж и подтвердите сторно.');
          input = { kind: 'reversal', documentKind: original.documentKind, documentId: original.documentId,
            reversesId: original.operationId, paidAt: reversal.paidAt, reason: reversal.reason };
        } else {
          if (value.reversal) throw new Error('Сначала закройте черновик сторно.');
          const cents = paymentKopecks(value.draft.amount);
          if (!(cents > 0) || cents > paymentKopecks(value.snapshot.remainingAmount)) throw new Error('Укажите точную положительную сумму в пределах остатка долга.');
          input = { ...value.draft, ...value.snapshot.canonicalTarget, kind: 'payment',
            amount: `${Math.floor(cents / 100)}.${String(cents % 100).padStart(2, '0')}` };
        }
      }
      cycle.busy = true;
      patch({ busy: true, error: '' });
      const options = { API, userId, companyId, signal: cycle.controller.signal,
        ...((retry || cancelling) ? { expectedBody: value.pending?.body } : {}) };
      const response = cancelling ? await cancelPendingPayment(options)
        : await submitPayment({ ...options, ...(retry ? { retry: true } : { input }) });
      // The client verified both envelope identity and nested operation. Keep
      // the original document/request identity when unwrapping a confirmed race.
      const result = cancelling && response.status === 'confirmed'
        ? { ...response.result, companyId: response.companyId, requestId: response.requestId,
          documentKind: response.documentKind, documentId: response.documentId, kind: response.kind }
        : response;
      // Retire before React renders or any callback runs: a captured handler cannot
      // turn a second click into a new UUID after the first request has committed.
      cycle.retired = true;
      if (!live()) return;
      patch({ success: result, pending: null, reversal: null, cancellationConfirmed: false });
      await load();
      if (live()) callback.current?.(result);
    } catch (error) {
      const networkMessage = cancelling
        ? 'Связь прервалась. Отмена попытки не подтверждена; повторите отмену попытки.'
        : 'Связь прервалась. Результат операции не подтверждён; повторите сохранённый запрос.';
      if (live()) { patch({ error: error instanceof TypeError && !error.status ? networkMessage : error.message });
        try { checkPending(); } catch (_) { /* Error already displayed. */ } }
    } finally { cycle.busy = false; patch({ busy: false }); }
  };
  return { ...value,
    updateDraft: changes => { if (!cycle.busy && !cycle.retired) patch({ draft: { ...value.draft, ...changes } }); },
    submit: () => send('payment'), retry: () => send('retry'), submitReversal: () => send('reversal'),
    cancelPending: () => send('cancel'),
    confirmCancellation: confirmed => { if (!cycle.busy) patch({ cancellationConfirmed: confirmed === true }); },
    beginReversal: operationId => {
      if (!live() || cycle.busy || value.loading || !value.snapshot || value.storageError) return;
      try { if (checkPending()) return; } catch (_) { return; }
      const operation = value.history?.items.find(item => item.operationId === operationId);
      if (!eligible(operation)) return;
      cycle.intent += 1; cycle.retired = false;
      patch({ success: null, error: '', reversal: { operation, paidAt: '', reason: '', confirmed: false } });
    },
    updateReversal: changes => {
      if (!cycle.busy && !cycle.retired && value.reversal) patch({ reversal: { ...value.reversal,
        paidAt: changes.paidAt ?? value.reversal.paidAt, reason: changes.reason ?? value.reversal.reason,
        confirmed: changes.confirmed ?? value.reversal.confirmed } });
    },
    cancelReversal: () => {
      if (!live() || cycle.busy) return;
      try { if (checkPending()) return; } catch (_) { return; }
      cycle.intent += 1; patch({ reversal: null, error: '' });
    },
    reload: () => { if (!cycle.busy) { try { checkPending(); } catch (_) { /* Fail closed. */ } return load(); } },
    startNext: () => {
      if (!live() || cycle.busy || value.loading || !value.snapshot || value.error || value.storageError) return;
      try { if (checkPending()) return; } catch (_) { return; }
      cycle.retired = false; cycle.intent += 1;
      patch({ success: null, reversal: null, draft: { amount: '', paidAt: '', reason: '' } });
    },
  };
}
