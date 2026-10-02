import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { API } from '../../api';
import { readResponse } from './distributionCommands';

const writers = ['директор', 'зам_директора', 'кладовщик', 'снабженец'];
const statusText = { pending: 'Ожидает решения', accepted: 'Принято', rejected: 'Отклонено', cancelled: 'Отменено' };
const pendingKey = companyId => `intercompany-warehouse-transfer.pending.v1.${companyId}`;

function readPending(companyId) {
  try {
    const value = JSON.parse(sessionStorage.getItem(pendingKey(companyId)) || 'null');
    return value && value.requestId && Number(value.sourceStockId) > 0 && Number(value.destinationCompanyId) > 0 ? value : null;
  } catch (_) { return null; }
}

function requestId() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID();
  const bytes = window.crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128;
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
}

export default function IntercompanyWarehouseTransfersPanel(props) {
  if (process.env.REACT_APP_INTERCOMPANY_WAREHOUSE_TRANSFERS_ENABLED !== 'true') return null;
  return <IntercompanyWarehouseTransfersWorkspace {...props} />;
}

export function IntercompanyWarehouseTransfersWorkspace({ companyId, companies = [], warehouseMain = [], editable = false, onChanged }) {
  const headers = useMemo(() => ({ 'X-Company-Id': String(companyId), 'X-Company-Mode': 'company' }), [companyId]);
  const destinations = companies.filter(company => Number(company.companyId) !== Number(companyId)
    && company.active !== false && company.companyActive !== false);
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({ destinationCompanyId: '', sourceStockId: '', quantity: '', reason: '' });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [pendingCreate, setPendingCreate] = useState(() => readPending(companyId));
  const alive = useRef(true);
  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const data = await fetch(`${API}/intercompany-warehouse-transfers`, { credentials: 'include', headers }).then(readResponse);
      if (alive.current) setItems(Array.isArray(data?.items) ? data.items : []);
    } catch (e) {
      if (alive.current) { setItems([]); setError(e.message || 'Не удалось загрузить межфирменные перемещения.'); }
    } finally { if (alive.current) setLoading(false); }
  }, [headers]);
  useEffect(() => { alive.current = true; load(); return () => { alive.current = false; }; }, [load]);

  const stock = warehouseMain.find(item => Number(item.id) === Number(form.sourceStockId));
  const valid = destinations.some(item => Number(item.companyId) === Number(form.destinationCompanyId))
    && stock && Number(form.quantity) > 0 && Number(form.quantity) <= Number(stock.quantity) && form.reason.trim();

  async function send(path, body, success) {
    if (busy) return false;
    setBusy(true); setError(''); setNotice('');
    try {
      await fetch(`${API}${path}`, { method: 'POST', credentials: 'include', headers: { ...headers, 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(readResponse);
      if (!alive.current) return;
      setNotice(success); await load();
      try { await onChanged?.(); } catch (_) { /* The transfer result remains authoritative. */ }
      return true;
    } catch (e) { if (alive.current) setError(e.message || 'Операция не выполнена.'); return false; }
    finally { if (alive.current) setBusy(false); }
  }

  async function createTransfer() {
    const payload = pendingCreate || { ...form, destinationCompanyId: Number(form.destinationCompanyId),
      sourceStockId: Number(form.sourceStockId), requestId: requestId(), reason: form.reason.trim() };
    if (!pendingCreate) {
      sessionStorage.setItem(pendingKey(companyId), JSON.stringify(payload));
      setPendingCreate(payload);
    }
    const saved = await send('/intercompany-warehouse-transfers', payload, 'Передача отправлена на подтверждение.');
    if (saved) {
      sessionStorage.removeItem(pendingKey(companyId)); setPendingCreate(null);
      setForm({ destinationCompanyId: '', sourceStockId: '', quantity: '', reason: '' });
    }
  }

  function decide(item, action) {
    let reason = '';
    if (action !== 'accept') {
      reason = window.prompt(action === 'reject' ? 'Почему вы отклоняете передачу?' : 'Почему передача отменяется?', '') || '';
      if (!reason.trim()) return;
    }
    const labels = { accept: 'Материал принят на склад.', reject: 'Передача отклонена.', cancel: 'Передача отменена.' };
    send(`/intercompany-warehouse-transfers/${item.id}/${action}`, { reason: reason.trim() }, labels[action]);
  }

  return <section className="intercompany-transfers" aria-label="Между компаниями">
    <div className="wd-heading"><div><h3>Передача между компаниями</h3><p>Отправитель оформляет передачу. Остатки изменятся после подтверждения получателем.</p></div><button type="button" disabled={busy || loading} onClick={load}>Обновить</button></div>
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}{loading && <p role="status">Загрузка передач…</p>}
    {editable && <form className="ict-form" onSubmit={event => { event.preventDefault(); if (!pendingCreate && !valid) return; createTransfer(); }}>
      <label>Компания-получатель<select aria-label="Компания-получатель" value={form.destinationCompanyId} onChange={event => setForm({ ...form, destinationCompanyId: event.target.value })}><option value="">Выберите компанию</option>{destinations.map(company => <option key={company.companyId} value={company.companyId}>{company.companyName || company.shortName || `Компания #${company.companyId}`}</option>)}</select></label>
      <label>Материал<select aria-label="Материал" value={form.sourceStockId} onChange={event => setForm({ ...form, sourceStockId: event.target.value, quantity: '' })}><option value="">Выберите материал</option>{warehouseMain.filter(item => Number(item.quantity) > 0).map(item => <option key={item.id} value={item.id}>{item.name} · доступно {item.quantity} {item.unit}</option>)}</select></label>
      <label>Количество<input aria-label="Количество" inputMode="decimal" value={form.quantity} onChange={event => setForm({ ...form, quantity: event.target.value.replace(',', '.') })} /></label>
      <label>Основание передачи<textarea aria-label="Основание передачи" maxLength={1000} value={form.reason} onChange={event => setForm({ ...form, reason: event.target.value })} /></label>
      {!destinations.length && <p>Для передачи нужен доступ к карточке второй компании в вашем кабинете.</p>}
      {pendingCreate && <p role="status">Предыдущая отправка не подтверждена сервером. Повтор использует тот же номер и не создаст дубль.</p>}
      <button type="submit" disabled={busy || (!pendingCreate && !valid)}>{pendingCreate ? 'Повторить отправку' : 'Отправить на подтверждение'}</button>
    </form>}
    <h4>Заявки на передачу</h4>
    {!loading && !items.length && <p>Межфирменных передач пока нет.</p>}
    <div className="ict-list">{items.map(item => <article key={item.id}>
      <div><strong>№ {item.id} · {item.materialName}</strong><span className={`ict-status ict-${item.status}`}>{statusText[item.status] || item.status}</span></div>
      <p>{item.quantity} {item.unit} · {item.side === 'source' ? 'получатель' : 'отправитель'}: {item.counterparty?.name || `Компания #${item.counterparty?.companyId}`}</p>
      <p>{item.reason}</p>
      {editable && item.status === 'pending' && item.side === 'destination' && <div className="ict-actions"><button type="button" disabled={busy} onClick={() => decide(item, 'accept')}>Принять на склад</button><button type="button" disabled={busy} onClick={() => decide(item, 'reject')}>Отклонить</button></div>}
      {editable && item.status === 'pending' && item.side === 'source' && <button type="button" disabled={busy} onClick={() => decide(item, 'cancel')}>Отменить передачу</button>}
    </article>)}</div>
  </section>;
}
