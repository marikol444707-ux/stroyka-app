import React, { useCallback, useEffect, useRef, useState } from 'react';
import { API } from '../../api';
import { readResponse, transferPath, transferQuantity, readTransferCommand, saveTransferCommand, clearTransferCommand, validateTransferPage, validateTransferResult } from './distributionCommands';
import useWarehouseTransferDraft, { emptyTransferDraft } from './useWarehouseTransferDraft';
import './WarehouseTransfersPanel.css';

export default function WarehouseTransfersPanel(props) {
  if (process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED !== 'true' || !props.companyId || props.accessDenied) return null;
  return <Transfers key={`${props.userId}:${props.companyId}:${Boolean(props.editable && !props.readOnly)}`} {...props} editable={Boolean(props.editable && !props.readOnly)} />;
}
const statusLabels = { in_transit: 'В пути', partial: 'Частично принято', received: 'Принято', discrepancy: 'Есть расхождение' };
function Transfers({ companyId, userId, editable, source, sourceUnavailable = false, projects = [], blocked = false, onClose, onChanged, onDenied, onPendingChange, onRestoreSource }) {
  const [items, setItems] = useState([]);
  const [cursor, setCursor] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [search, setSearch] = useState('');
  const [pending, setPending] = useState(null);
  const [storageError, setStorageError] = useState('');
  const [busy, setBusy] = useState(false);
  const [denied, setDenied] = useState(false);
  const [receiving, setReceiving] = useState(null);
  const [restoredSource, setRestoredSource] = useState(null);
  const [document, setDocument] = useState(emptyTransferDraft);
  const [confirmed, setConfirmed] = useState(false);
  const selectedSource = useRef(null);
  const active = useRef(false);
  const generation = useRef(0);
  const fetching = useRef(false);
  const locked = useRef(false);
  const deniedRef = useRef(false);
  const applied = useRef('');
  const callbacks = useRef({ onClose, onChanged, onDenied, onPendingChange, onRestoreSource });
  callbacks.current = { onClose, onChanged, onDenied, onPendingChange, onRestoreSource };
  const deny = useCallback(() => {
    deniedRef.current = true; generation.current += 1; fetching.current = false;
    setDenied(true); setLoading(false); setItems([]); setCursor(null); setReceiving(null);
    callbacks.current.onClose?.(); callbacks.current.onDenied?.();
  }, []);
  const applyDocument = useCallback((doc, data) => {
    setDocument(doc); setConfirmed(false);
    const entity = data.document.kind === doc.kind && data.source?.id === (doc.allocationId || doc.transferId) ? data.source : null;
    const dispatchSource = doc.kind === 'dispatch' ? entity || { id: doc.allocationId, projectName: `Распределение #${doc.allocationId}`, materialName: '', unit: '', netQuantity: 0 } : null;
    setRestoredSource(dispatchSource);
    setReceiving(doc.kind === 'receipt' ? entity || { id: doc.transferId, fromProjectName: '', toProjectName: '', materialName: '', unit: '', quantity: '0', receivedQuantity: '0', inTransitQuantity: '0', receipts: [] } : null);
    callbacks.current.onRestoreSource?.(dispatchSource);
  }, []);
  const draft = useWarehouseTransferDraft({ companyId, userId, enabled: editable && !denied,
    document, applyDocument, onDenied: deny });
  useEffect(() => {
    if (!source) { selectedSource.current = null; return; }
    if (draft.loading || selectedSource.current === source.id) return;
    selectedSource.current = source.id;
    setDocument(previous => previous.kind ? previous : { ...emptyTransferDraft(), kind: 'dispatch', allocationId: source.id });
  }, [source, draft.loading]);
  const closeForm = () => {
    setDocument(emptyTransferDraft()); setReceiving(null); setRestoredSource(null); setConfirmed(false);
    callbacks.current.onClose?.();
  };
  const changeField = (key, value) => setDocument(previous => ({ ...previous, [key]: value }));
  const load = useCallback(async (beforeId = null) => {
    if (deniedRef.current || (beforeId && fetching.current)) return;
    const current = ++generation.current;
    fetching.current = true; setLoading(true); setError('');
    if (!beforeId) { setItems([]); setCursor(null); }
    try {
      const query = new URLSearchParams({ limit: '100' });
      if (applied.current) query.set('q', applied.current);
      if (beforeId) query.set('beforeId', beforeId);
      const data = await fetch(`${API}${transferPath}?${query}`, { credentials: 'include', headers: { 'X-Company-Id': String(companyId), 'X-Company-Mode': 'company' } })
        .then(readResponse).then(value => validateTransferPage(value, companyId, beforeId));
      if (!active.current || current !== generation.current) return;
      setItems(previous => beforeId ? [...previous, ...data.items] : data.items); setCursor(data.nextCursor);
    } catch (e) {
      if (!active.current || current !== generation.current) return;
      setItems([]); setCursor(null); setError(e.message);
      if ([401, 403].includes(e.status)) deny();
    } finally {
      if (active.current && current === generation.current) { fetching.current = false; setLoading(false); }
    }
  }, [companyId, deny]);
  useEffect(() => {
    active.current = true; load();
    if (editable) {
      try { setPending(readTransferCommand(companyId, userId)); }
      catch (e) { setStorageError(e.message || 'Хранилище сеанса недоступно.'); }
    }
    return () => { active.current = false; generation.current += 1; };
  }, [companyId, userId, editable, load]);
  useEffect(() => { callbacks.current.onPendingChange?.(Boolean(pending || storageError || busy || document.kind || draft.loading || draft.error || draft.dirty)); }, [pending, storageError, busy, document.kind, draft.loading, draft.error, draft.dirty]);

  async function submit(path, payload, retry = null) {
    if (!editable || blocked || deniedRef.current || locked.current || storageError || (pending && !retry)) return;
    locked.current = true; setBusy(true); setError(''); setNotice('');
    let command;
    let hadPending = false;
    try {
      let existing;
      try { existing = readTransferCommand(companyId, userId) || retry; }
      catch (_) { setStorageError('Не удалось проверить неподтверждённое перемещение. Требуется сверка.'); return; }
      hadPending = Boolean(existing);
      const signature = JSON.stringify({ path, ...payload });
      if (existing && existing.signature !== signature) { setPending(existing); throw new Error('Сначала повторите неподтверждённое перемещение.'); }
      if (!existing && !window.crypto?.randomUUID) throw new Error('Для перемещения откройте платформу по HTTPS в современном браузере.');
      const draftRevision = existing ? existing.draftRevision : await draft.flush();
      if (!active.current || deniedRef.current) return;
      command = existing || { id: window.crypto.randomUUID(), path, payload, signature, draftRevision };
      try { saveTransferCommand(companyId, command, userId); }
      catch (_) { setStorageError('Не удалось сохранить запрос перемещения. Отправка заблокирована.'); return; }
      setPending(command);
      const result = await fetch(`${API}${command.path}`, { method: 'POST', credentials: 'include', headers: { 'X-Company-Id': String(companyId), 'X-Company-Mode': 'company', 'Content-Type': 'application/json', ...(command.draftRevision !== undefined ? { 'X-Warehouse-Transfer-Draft-Revision': String(command.draftRevision) } : {}) }, body: JSON.stringify({ ...command.payload, requestId: command.id }) }).then(readResponse);
      validateTransferResult(result, command);
      clearTransferCommand(companyId, command.id, userId);
      if (!active.current) return;
      setPending(readTransferCommand(companyId, userId)); closeForm();
      await draft.reloadAfterOperation();
      if (!active.current || deniedRef.current) return;
      setNotice('Перемещение сохранено. История обновляется.');
      await load();
      if (active.current && !deniedRef.current) {
        try { await callbacks.current.onChanged?.(); }
        catch (_) { if (active.current) setNotice('Перемещение сохранено. Обновите остальные разделы.'); }
      }
    } catch (e) {
      if (!hadPending && command && [400, 409, 422].includes(e.status)) {
        try { clearTransferCommand(companyId, command.id, userId); if (active.current) setPending(readTransferCommand(companyId, userId)); }
        catch (_) { if (active.current) setStorageError('Не удалось проверить неподтверждённое перемещение.'); }
      }
      if (!active.current) return;
      if ([401, 403].includes(e.status)) deny();
      if (e.code === 'warehouse_transfer_draft_conflict') draft.rejectConflict(e);
      setError(e.message || 'Ответ не получен. Повторите перемещение безопасно.');
    } finally { locked.current = false; if (active.current) setBusy(false); }
  }
  const disabled = blocked || loading || busy || denied || draft.loading || Boolean(pending || storageError);
  const closeDisabled = busy || denied || draft.loading || Boolean(pending || storageError);
  const dispatchSource = document.kind === 'dispatch' ? (source?.id === document.allocationId ? source : restoredSource) : null;
  // Keep the same keyed form mounted through reloads, empty searches and read
  // failures. Its old snapshot is only a draft; only a fresh list enables submit.
  const receiptInList = receiving && items.some(item => item.id === receiving.id);
  const visibleItems = receiving && !receiptInList ? [receiving, ...items] : items;
  const receiptUnavailable = Boolean(receiving && (!receiptInList || error || loading));
  return <section className="warehouse-transfers" aria-label="Перемещения между объектами">
    <div className="wd-heading"><h4>Перемещения между объектами</h4><button type="button" disabled={loading || busy || denied} onClick={() => load()}>Обновить перемещения</button></div>
    <p>Отправка и приёмка — два этапа. Непринятое остаётся в пути и не считается потерей. Расхождение фиксируется отдельно; новый долг поставщику не возникает.</p>
    {loading && <p role="status">Загрузка перемещений…</p>}
    {error && <p role="alert">{error}</p>}
    {storageError && <p role="alert">{storageError}</p>}
    {notice && <p role="status">{notice}</p>}
    {editable && pending && <div role="status"><p>Есть неподтверждённое перемещение. Новые операции заблокированы.</p>
      <details><summary>Неподтверждённая отправка / приёмка</summary><p>{pending.payload.reason} · количество {pending.payload.quantity}{pending.payload.expectedQuantity !== undefined && ` · ожидалось ${pending.payload.expectedQuantity}`}</p></details>
      <button type="button" disabled={busy || denied || blocked} onClick={() => submit(pending.path, pending.payload, pending)}>Повторить перемещение безопасно</button>
    </div>}
    {editable && !denied && <div aria-label="Серверный черновик перемещения" aria-live="polite">
      {draft.loading ? <p role="status">Загружаем серверный черновик перемещения…</p> : draft.error ? <p role="alert">{draft.error}</p>
        : <p role="status">{draft.saving ? 'Сохраняем черновик перемещения…' : draft.dirty ? 'Есть несохранённые правки перемещения.' : 'Черновик перемещения сохранён на сервере.'}</p>}
      {draft.error && <><button type="button" disabled={busy || draft.saving} onClick={draft.download}>Скачать правки перемещения</button><button type="button" disabled={busy || draft.saving || Boolean(pending)} onClick={draft.reloadFromServer}>Загрузить серверное перемещение</button></>}
      {(document.kind || draft.dirty) && <button type="button" disabled={busy || draft.loading || draft.saving || draft.phase === 'conflict' || Boolean(pending)} onClick={() => draft.flush().catch(() => {})}>Сохранить черновик перемещения</button>}
      {draft.lastOperation && !document.kind && !draft.dirty && <p>Предыдущее перемещение сохранено. Результат доступен в истории.</p>}
    </div>}
    {editable && dispatchSource && !denied && <DispatchForm key={dispatchSource.id} source={dispatchSource} projects={projects} companyId={companyId}
      document={document} changeField={changeField} closeDisabled={closeDisabled} canSubmit={draft.readyToSubmit} disabled={disabled || Boolean(receiving)} unavailable={sourceUnavailable}
      onClose={closeForm} onSubmit={payload => submit(transferPath, payload)} />}
    <form className="wd-filters" onSubmit={e => { e.preventDefault(); applied.current = search.trim(); load(); }}>
      <label>Поиск перемещений<input type="search" maxLength={200} value={search} onChange={e => setSearch(e.target.value)} /></label>
      <button disabled={busy || denied}>Найти перемещения</button>
    </form>
    {!loading && !error && !items.length && <p>{applied.current ? 'По поиску перемещений не найдено.' : 'Перемещений пока нет.'}</p>}
    {receiving && receiptUnavailable && <p role="status">Черновик приёмки сохранён в открытой форме. Для отправки дождитесь успешного обновления перемещения; если оно скрыто поиском, очистите поиск.</p>}
    <div className="wd-records">{visibleItems.map(item => <article key={item.id}>
      <h5>{item.fromProjectName} → {item.toProjectName} · {item.materialName}</h5>
      <p>Перемещение #{item.id} · накладная {item.invoiceNumber || `#${item.warehouseInvoiceId}`} · партия #{item.lotId}</p>
      <p>Отправлено: {item.quantity} {item.unit} · Принято: {item.receivedQuantity} {item.unit}</p>
      <strong>В пути: {item.inTransitQuantity} {item.unit}</strong><p>{statusLabels[item.status]} · {item.reason} · {item.createdAt} · {item.createdBy}</p>
      {item.receipts.length > 0 && <details><summary>Приёмки и расхождения ({item.receipts.length})</summary><ul>{item.receipts.map(receipt => <li key={receipt.id}>Ожидалось {receipt.expectedQuantity} · принято {receipt.quantity} · расхождение {receipt.discrepancyQuantity} {item.unit} · {receipt.reason} · {receipt.createdAt} · {receipt.createdBy}</li>)}</ul></details>}
      {editable && Number(item.inTransitQuantity) > 0 && <button type="button" disabled={disabled || Boolean(receiving || dispatchSource) || !draft.readyToSubmit} onClick={() => { onClose?.(); setReceiving(item); setDocument({ ...emptyTransferDraft(), kind: 'receipt', transferId: item.id }); setConfirmed(false); }}>Принять на объекте</button>}
      {editable && receiving?.id === item.id && !denied && <ReceiptForm key={item.id} item={item} companyId={companyId} document={document} changeField={changeField} closeDisabled={closeDisabled} confirmed={confirmed} setConfirmed={setConfirmed} canSubmit={draft.readyToSubmit} disabled={disabled} unavailable={receiptUnavailable} onClose={closeForm} onSubmit={payload => submit(`${transferPath}/${item.id}/receipts`, payload)} />}
    </article>)}</div>
    {cursor !== null && <button type="button" disabled={busy || loading || denied} onClick={() => load(cursor)}>Загрузить ещё перемещения</button>}
  </section>;
}

function DispatchForm({ source, projects, companyId, document, changeField, canSubmit, closeDisabled, disabled, unavailable, onClose, onSubmit }) {
  const { toProjectId, quantity, reason } = document;
  const destinations = projects.filter(p => Number(p.companyId ?? p.company_id) === companyId && Number(p.id) !== Number(source.projectId) && p.status !== 'Закрыт');
  const valid = canSubmit && !unavailable && destinations.some(p => Number(p.id) === Number(toProjectId)) && transferQuantity(quantity) && Number(quantity) <= Number(source.netQuantity) && reason.trim();
  return <form onSubmit={e => { e.preventDefault(); if (valid && !disabled) onSubmit({ companyId, allocationId: source.id, toProjectId: Number(toProjectId), quantity, reason: reason.trim() }); }}>
    <fieldset disabled={disabled}><legend>Отправка: {source.projectName} · {source.materialName}</legend>
      {unavailable && <p role="status">Черновик отправки сохранён в открытой форме. Остаток пока не подтверждён: обновите историю распределений или очистите её фильтры.</p>}
      <p>Распределение #{source.id}. Максимум: {source.netQuantity} {source.unit}; сервер проверит остаток объекта.</p>
      <label>Объект назначения<select autoFocus value={toProjectId ?? ''} onChange={e => changeField('toProjectId', e.target.value ? Number(e.target.value) : null)}><option value="">Выберите объект</option>{destinations.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
      <label>Количество отправки<input inputMode="decimal" value={quantity} onChange={e => changeField('quantity', e.target.value.replace(',', '.'))} /></label>
      <label>Основание отправки<textarea maxLength={1000} value={reason} onChange={e => changeField('reason', e.target.value)} /></label>
      <div className="wd-heading"><button disabled={!valid}>Подтвердить отправку</button></div>
    </fieldset>
    <button type="button" disabled={closeDisabled} onClick={onClose}>Отменить отправку</button>
  </form>;
}
function ReceiptForm({ item, companyId, document, changeField, confirmed, setConfirmed, canSubmit, closeDisabled, disabled, unavailable, onClose, onSubmit }) {
  const { quantity, expectedQuantity, reason } = document;
  const valid = canSubmit && !unavailable && transferQuantity(quantity, true) && transferQuantity(expectedQuantity) && Number(quantity) <= Number(expectedQuantity)
    && Number(expectedQuantity) <= Number(item.inTransitQuantity) && reason.trim() && confirmed;
  return <form onSubmit={e => { e.preventDefault(); if (valid && !disabled) onSubmit({ companyId, quantity, expectedQuantity, reason: reason.trim() }); }}>
    <fieldset disabled={disabled}><legend>Приёмка #{item.id}: {item.toProjectName} · {item.materialName}</legend>
      <p>Осталось в пути: {item.inTransitQuantity} {item.unit}. При недостаче укажите фактически принятое, включая 0. Ожидаемое — только для этой приёмки.</p>
      <label>Ожидалось в этой приёмке<input autoFocus inputMode="decimal" value={expectedQuantity} onChange={e => changeField('expectedQuantity', e.target.value.replace(',', '.'))} /></label>
      <label>Фактически принято<input inputMode="decimal" value={quantity} onChange={e => changeField('quantity', e.target.value.replace(',', '.'))} /></label>
      <label>Основание приёмки / расхождения<textarea maxLength={1000} value={reason} onChange={e => changeField('reason', e.target.value)} /></label>
      <label className="wd-confirm"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />Подтверждаю фактическую приёмку на объекте и указанное расхождение, включая отсутствие поступления при количестве 0.</label>
      <div className="wd-heading"><button disabled={!valid}>Подтвердить приёмку</button></div>
    </fieldset>
    <button type="button" disabled={closeDisabled} onClick={onClose}>Отменить приёмку</button>
  </form>;
}
