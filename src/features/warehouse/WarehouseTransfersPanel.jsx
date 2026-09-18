import React, { useCallback, useEffect, useRef, useState } from 'react';
import { API } from '../../api';
import { readResponse, transferPath, transferQuantity, readTransferCommand, saveTransferCommand, clearTransferCommand, validateTransferPage, validateTransferResult } from './distributionCommands';
import './WarehouseTransfersPanel.css';

export default function WarehouseTransfersPanel(props) {
  if (process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED !== 'true' || !props.companyId || props.accessDenied) return null;
  return <Transfers key={`${props.companyId}:${Boolean(props.editable && !props.readOnly)}`} {...props} editable={Boolean(props.editable && !props.readOnly)} />;
}
const statusLabels = { in_transit: 'В пути', partial: 'Частично принято', received: 'Принято', discrepancy: 'Есть расхождение' };
function Transfers({ companyId, editable, source, projects = [], blocked = false, onClose, onChanged, onDenied, onPendingChange }) {
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
  const active = useRef(false);
  const generation = useRef(0);
  const fetching = useRef(false);
  const locked = useRef(false);
  const deniedRef = useRef(false);
  const applied = useRef('');
  const callbacks = useRef({ onClose, onChanged, onDenied, onPendingChange });
  callbacks.current = { onClose, onChanged, onDenied, onPendingChange };
  const deny = useCallback(() => {
    deniedRef.current = true; generation.current += 1; fetching.current = false;
    setDenied(true); setLoading(false); setItems([]); setCursor(null); setReceiving(null);
    callbacks.current.onClose?.(); callbacks.current.onDenied?.();
  }, []);
  const load = useCallback(async (beforeId = null) => {
    if (deniedRef.current || (beforeId && fetching.current)) return;
    const current = ++generation.current;
    fetching.current = true; setLoading(true); setError('');
    if (!beforeId) { setItems([]); setCursor(null); setReceiving(null); }
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
      setItems([]); setCursor(null); setReceiving(null); setError(e.message);
      if ([401, 403].includes(e.status)) deny();
    } finally {
      if (active.current && current === generation.current) { fetching.current = false; setLoading(false); }
    }
  }, [companyId, deny]);
  useEffect(() => {
    active.current = true; load();
    if (editable) {
      try { setPending(readTransferCommand(companyId)); }
      catch (e) { setStorageError(e.message || 'Хранилище сеанса недоступно.'); }
    }
    return () => { active.current = false; generation.current += 1; };
  }, [companyId, editable, load]);
  useEffect(() => { callbacks.current.onPendingChange?.(Boolean(pending || storageError || busy)); }, [pending, storageError, busy]);

  async function submit(path, payload, retry = null) {
    if (!editable || blocked || deniedRef.current || locked.current || storageError || (pending && !retry)) return;
    locked.current = true; setBusy(true); setError(''); setNotice('');
    let command;
    let hadPending = false;
    try {
      let existing;
      try { existing = readTransferCommand(companyId) || retry; }
      catch (_) { setStorageError('Не удалось проверить неподтверждённое перемещение. Требуется сверка.'); return; }
      hadPending = Boolean(existing);
      const signature = JSON.stringify({ path, ...payload });
      if (existing && existing.signature !== signature) { setPending(existing); throw new Error('Сначала повторите неподтверждённое перемещение.'); }
      if (!existing && !window.crypto?.randomUUID) throw new Error('Для перемещения откройте платформу по HTTPS в современном браузере.');
      command = existing || { id: window.crypto.randomUUID(), path, payload, signature };
      try { saveTransferCommand(companyId, command); }
      catch (_) { setStorageError('Не удалось сохранить запрос перемещения. Отправка заблокирована.'); return; }
      setPending(command);
      const result = await fetch(`${API}${command.path}`, { method: 'POST', credentials: 'include', headers: { 'X-Company-Id': String(companyId), 'X-Company-Mode': 'company', 'Content-Type': 'application/json' }, body: JSON.stringify({ ...command.payload, requestId: command.id }) }).then(readResponse);
      validateTransferResult(result, command);
      clearTransferCommand(companyId, command.id);
      if (!active.current) return;
      setPending(readTransferCommand(companyId)); setReceiving(null); callbacks.current.onClose?.();
      setNotice('Перемещение сохранено. История обновляется.');
      await load();
      if (active.current && !deniedRef.current) {
        try { await callbacks.current.onChanged?.(); }
        catch (_) { if (active.current) setNotice('Перемещение сохранено. Обновите остальные разделы.'); }
      }
    } catch (e) {
      if (!hadPending && command && [400, 409, 422].includes(e.status)) {
        try { clearTransferCommand(companyId, command.id); if (active.current) setPending(readTransferCommand(companyId)); }
        catch (_) { if (active.current) setStorageError('Не удалось проверить неподтверждённое перемещение.'); }
      }
      if (!active.current) return;
      if ([401, 403].includes(e.status)) deny();
      setError(e.message || 'Ответ не получен. Повторите перемещение безопасно.');
    } finally { locked.current = false; if (active.current) setBusy(false); }
  }
  const disabled = blocked || loading || busy || denied || Boolean(pending || storageError);
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
    {editable && source && !denied && <DispatchForm key={source.id} source={source} projects={projects} companyId={companyId} disabled={disabled || Boolean(receiving)} onClose={onClose} onSubmit={payload => submit(transferPath, payload)} />}
    <form className="wd-filters" onSubmit={e => { e.preventDefault(); applied.current = search.trim(); load(); }}>
      <label>Поиск перемещений<input type="search" maxLength={200} value={search} onChange={e => setSearch(e.target.value)} /></label>
      <button disabled={busy || denied}>Найти перемещения</button>
    </form>
    {!loading && !error && !items.length && <p>{applied.current ? 'По поиску перемещений не найдено.' : 'Перемещений пока нет.'}</p>}
    <div className="wd-records">{items.map(item => <article key={item.id}>
      <h5>{item.fromProjectName} → {item.toProjectName} · {item.materialName}</h5>
      <p>Перемещение #{item.id} · накладная {item.invoiceNumber || `#${item.warehouseInvoiceId}`} · партия #{item.lotId}</p>
      <p>Отправлено: {item.quantity} {item.unit} · Принято: {item.receivedQuantity} {item.unit}</p>
      <strong>В пути: {item.inTransitQuantity} {item.unit}</strong><p>{statusLabels[item.status]} · {item.reason} · {item.createdAt} · {item.createdBy}</p>
      {item.receipts.length > 0 && <details><summary>Приёмки и расхождения ({item.receipts.length})</summary><ul>{item.receipts.map(receipt => <li key={receipt.id}>Ожидалось {receipt.expectedQuantity} · принято {receipt.quantity} · расхождение {receipt.discrepancyQuantity} {item.unit} · {receipt.reason} · {receipt.createdAt} · {receipt.createdBy}</li>)}</ul></details>}
      {editable && Number(item.inTransitQuantity) > 0 && <button type="button" disabled={disabled} onClick={() => { onClose?.(); setReceiving(item); }}>Принять на объекте</button>}
    </article>)}</div>
    {cursor !== null && <button type="button" disabled={busy || loading || denied} onClick={() => load(cursor)}>Загрузить ещё перемещения</button>}
    {editable && receiving && !denied && <ReceiptForm key={receiving.id} item={receiving} companyId={companyId} disabled={disabled} onClose={() => setReceiving(null)} onSubmit={payload => submit(`${transferPath}/${receiving.id}/receipts`, payload)} />}
  </section>;
}

function DispatchForm({ source, projects, companyId, disabled, onClose, onSubmit }) {
  const [toProjectId, setProject] = useState('');
  const [quantity, setQuantity] = useState('');
  const [reason, setReason] = useState('');
  const destinations = projects.filter(p => Number(p.companyId ?? p.company_id) === companyId && Number(p.id) !== Number(source.projectId) && p.status !== 'Закрыт');
  const valid = destinations.some(p => Number(p.id) === Number(toProjectId)) && transferQuantity(quantity) && Number(quantity) <= Number(source.netQuantity) && reason.trim();
  return <form onSubmit={e => { e.preventDefault(); if (valid && !disabled) onSubmit({ companyId, allocationId: source.id, toProjectId: Number(toProjectId), quantity, reason: reason.trim() }); }}>
    <fieldset disabled={disabled}><legend>Отправка: {source.projectName} · {source.materialName}</legend>
      <p>Распределение #{source.id}. Максимум: {source.netQuantity} {source.unit}; сервер проверит остаток объекта.</p>
      <label>Объект назначения<select autoFocus value={toProjectId} onChange={e => setProject(e.target.value)}><option value="">Выберите объект</option>{destinations.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
      <label>Количество отправки<input inputMode="decimal" value={quantity} onChange={e => setQuantity(e.target.value.replace(',', '.'))} /></label>
      <label>Основание отправки<textarea maxLength={1000} value={reason} onChange={e => setReason(e.target.value)} /></label>
      <div className="wd-heading"><button disabled={!valid}>Подтвердить отправку</button><button type="button" onClick={onClose}>Отменить отправку</button></div>
    </fieldset>
  </form>;
}
function ReceiptForm({ item, companyId, disabled, onClose, onSubmit }) {
  const [quantity, setQuantity] = useState('');
  const [expectedQuantity, setExpected] = useState('');
  const [reason, setReason] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const valid = transferQuantity(quantity, true) && transferQuantity(expectedQuantity) && Number(quantity) <= Number(expectedQuantity)
    && Number(expectedQuantity) <= Number(item.inTransitQuantity) && reason.trim() && confirmed;
  return <form onSubmit={e => { e.preventDefault(); if (valid && !disabled) onSubmit({ companyId, quantity, expectedQuantity, reason: reason.trim() }); }}>
    <fieldset disabled={disabled}><legend>Приёмка #{item.id}: {item.toProjectName} · {item.materialName}</legend>
      <p>Осталось в пути: {item.inTransitQuantity} {item.unit}. При недостаче укажите фактически принятое, включая 0. Ожидаемое — только для этой приёмки.</p>
      <label>Ожидалось в этой приёмке<input autoFocus inputMode="decimal" value={expectedQuantity} onChange={e => setExpected(e.target.value.replace(',', '.'))} /></label>
      <label>Фактически принято<input inputMode="decimal" value={quantity} onChange={e => setQuantity(e.target.value.replace(',', '.'))} /></label>
      <label>Основание приёмки / расхождения<textarea maxLength={1000} value={reason} onChange={e => setReason(e.target.value)} /></label>
      <label className="wd-confirm"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />Подтверждаю фактическую приёмку на объекте и указанное расхождение, включая отсутствие поступления при количестве 0.</label>
      <div className="wd-heading"><button disabled={!valid}>Подтвердить приёмку</button><button type="button" onClick={onClose}>Отменить приёмку</button></div>
    </fieldset>
  </form>;
}
