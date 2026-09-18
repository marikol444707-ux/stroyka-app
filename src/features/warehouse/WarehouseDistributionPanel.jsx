import React, { useCallback, useEffect, useRef, useState } from 'react';
import { API } from '../../api';
import { pendingCommand, saveCommand, clearCommand, readResponse, validateList, validateCommandResult } from './distributionCommands';
import WarehouseTransfersPanel from './WarehouseTransfersPanel';
import './WarehouseDistributionPanel.css';

const emptyRow = () => ({ lotId: '', projectId: '', quantity: '' });
const writers = ['директор', 'зам_директора', 'кладовщик', 'снабженец'];
const readers = [...writers, 'бухгалтер'];
const validQuantity = value => /^\d+(\.\d{1,6})?$/.test(value) && Number(value) > 0 && Number(value) < 100000000;
function requestId() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID();
  if (!window.crypto?.getRandomValues) throw new Error('Для сохранения откройте платформу по HTTPS в современном браузере.');
  const bytes = window.crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
export default function WarehouseDistributionPanel(props) {
  return process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_ENABLED === 'true' ? <DistributionWorkspace {...props} /> : null;
}

export function DistributionWorkspace({ companyContext = {}, ...props }) {
  const { mode, selectedCompanyId, companies = [], loading, error } = companyContext;
  if (loading) return <p role="status">Загрузка контекста компании…</p>;
  if (error || mode !== 'company' || !selectedCompanyId) return <p>Выберите одну компанию для просмотра распределений.</p>;
  const membership = companies.find(c => Number(c.companyId) === Number(selectedCompanyId));
  if (!membership || membership.active === false || membership.companyActive === false || !readers.includes(membership.role)) return null;
  const editable = !props.readOnly && !companyContext.readOnly && !membership.readOnly && writers.includes(membership.role);
  return <CompanyDistribution key={`${selectedCompanyId}:${editable}`} {...props} companyId={Number(selectedCompanyId)} editable={editable} />;
}

function CompanyDistribution({ companyId, editable, projects = [], refreshData, C = {} }) {
  const transfersEnabled = process.env.REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED === 'true';
  const [transferSource, setTransferSource] = useState(null);
  const [transferBlocked, setTransferBlocked] = useState(false);
  const [sources, setSources] = useState([]);
  const [records, setRecords] = useState([]);
  const [pages, setPages] = useState({ history: {}, sources: {} });
  const loading = Boolean(pages.history.loading || pages.sources.loading);
  const [selectedSources, setSelectedSources] = useState([]);
  const [sourceSearch, setSourceSearch] = useState('');
  const [filters, setFilters] = useState({ projectId: '', dateFrom: '', dateTo: '' });
  const applied = useRef({ history: {}, sources: {} });
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [rows, setRows] = useState([emptyRow()]);
  const [reason, setReason] = useState('');
  const [returning, setReturning] = useState(null);
  const [returnQuantity, setReturnQuantity] = useState('');
  const [returnReason, setReturnReason] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [search, setSearch] = useState('');
  const [accessDenied, setAccessDenied] = useState(false);
  const [pending, setPending] = useState(null);
  const [pendingError, setPendingError] = useState('');
  const active = useRef(true);
  const locked = useRef(false);
  const command = useRef(null);
  const generation = useRef({ history: 0, sources: 0 });
  const inFlight = useRef({ history: false, sources: false });
  const denied = useRef(false);
  const headers = { 'X-Company-Id': String(companyId), 'X-Company-Mode': 'company' };
  const ownProjects = projects.filter(p => Number(p.companyId ?? p.company_id) === companyId && p.status !== 'Закрыт');
  const denyAccess = useCallback(() => {
    denied.current = true;
    setError('Доступ к складским операциям отозван. Обновите данные после проверки прав.');
    generation.current.history += 1; generation.current.sources += 1;
    inFlight.current = { history: false, sources: false };
    setPages({ history: {}, sources: {} });
    setRecords([]); setSources([]); setSelectedSources([]); setRows([emptyRow()]);
    setReturning(null); setTransferSource(null); setTransferBlocked(false); setAccessDenied(true);
  }, []);
  const loadPage = useCallback(async (kind, beforeId = null) => {
    if (denied.current || (beforeId && inFlight.current[kind])) return;
    const source = kind === 'sources';
    const current = ++generation.current[kind];
    inFlight.current[kind] = true;
    const setItems = source ? setSources : setRecords;
    if (!beforeId) { setItems([]); if (!source) { setReturning(null); setTransferSource(null); } }
    setPages(previous => ({ ...previous, [kind]: { ...previous[kind], loading: true, error: '' } }));
    try {
      const options = { credentials: 'include', headers: { 'X-Company-Id': String(companyId), 'X-Company-Mode': 'company' } };
      const query = new URLSearchParams({ limit: source ? '200' : '100' });
      Object.entries(applied.current[kind]).forEach(([key, value]) => { if (value) query.set(key, value); });
      if (beforeId) query.set('beforeId', beforeId);
      const data = await fetch(`${API}/warehouse-distributions${source ? '/sources' : ''}?${query}`, options)
        .then(readResponse).then(value => validateList(value, source, beforeId));
      if (!active.current || current !== generation.current[kind]) return;
      setItems(previous => beforeId ? [...previous, ...data.items] : data.items);
      setPages(previous => ({ ...previous, [kind]: { nextCursor: data.nextCursor ?? null, truncated: Boolean(data.truncated), loading: false } }));
    } catch (e) {
      if (active.current && current === generation.current[kind]) {
        setItems([]);
        if (source) setSelectedSources([]);
        else { setReturning(null); setTransferSource(null); }
        if ([401, 403].includes(e.status)) { denyAccess(); setError(e.message); }
        else setPages(previous => ({ ...previous, [kind]: { loading: false, error: e.message || 'Не удалось загрузить распределения.' } }));
      }
    } finally {
      if (active.current && current === generation.current[kind]) inFlight.current[kind] = false;
    }
  }, [companyId, denyAccess]);
  const load = useCallback(() => {
    denied.current = false; setAccessDenied(false); setError(''); setSelectedSources([]);
    return Promise.all([loadPage('history'), editable ? loadPage('sources') : Promise.resolve()]);
  }, [editable, loadPage]);
  useEffect(() => {
    const requests = generation.current;
    active.current = true; load();
    return () => { active.current = false; requests.history += 1; requests.sources += 1; };
  }, [load]);
  useEffect(() => {
    if (!editable) return;
    try { command.current = pendingCommand(companyId); setPending(command.current); }
    catch (e) { setPendingError(e.message || 'Хранилище сеанса недоступно.'); }
  }, [companyId, editable]);

  async function submit(path, payload, reset, retryCommand = null) {
    if (locked.current || !editable || accessDenied || pendingError || transferBlocked || transferSource) return;
    locked.current = true; setBusy(true); setError(''); setNotice('');
    let hadPending = false;
    try {
      const signature = JSON.stringify({ path, ...payload });
      const existing = pendingCommand(companyId) || retryCommand;
      hadPending = Boolean(existing);
      if (existing && existing.signature !== signature) { setPending(existing); throw new Error('Сначала повторите неподтверждённую операцию.'); }
      command.current = existing || { signature, id: requestId(), path, payload };
      saveCommand(companyId, command.current); setPending(command.current);
      const result = await fetch(`${API}${path}`, { method: 'POST', credentials: 'include', headers: { ...headers, 'Content-Type': 'application/json' }, body: JSON.stringify({ ...payload, requestId: command.current.id }) }).then(readResponse);
      validateCommandResult(result, command.current);
      clearCommand(companyId, command.current.id);
      if (!active.current) return;
      command.current = null; setPending(pendingCommand(companyId)); reset(); setNotice('Операция сохранена. Ниже — результат последнего обновления истории.');
      await load();
      if (!active.current) return;
      try { await refreshData?.(); } catch (_) { if (active.current) setNotice('Операция сохранена. Обновите остальные разделы страницы.'); }
    } catch (e) {
      if (!hadPending && [400, 409, 422].includes(e.status)) {
        try {
          clearCommand(companyId, command.current?.id); command.current = null;
          if (active.current) setPending(pendingCommand(companyId));
        } catch (_) { if (active.current) setPendingError('Не удалось проверить хранилище неподтверждённой операции.'); }
      }
      if (active.current && [401, 403].includes(e.status)) denyAccess();
      if (active.current) setError(`${e.message || 'Нет ответа сервера.'} Для неподтверждённой операции используйте кнопку безопасного повтора.`);
    } finally {
      locked.current = false; if (active.current) setBusy(false);
    }
  }
  const sourceOptions = [...sources, ...selectedSources.filter(s => !sources.some(item => item.lotId === s.lotId))];
  const batchValid = rows.every(r => sourceOptions.some(s => s.lotId === Number(r.lotId)) && ownProjects.some(p => Number(p.id) === Number(r.projectId)) && validQuantity(r.quantity)) && reason.trim();
  const updateRow = (index, field, value) => {
    const next = rows.map((r, i) => i === index ? { ...r, [field]: value } : r);
    setRows(next);
    setSelectedSources(sourceOptions.filter(s => next.some(r => Number(r.lotId) === s.lotId)));
  };
  const closeReturn = () => { setReturning(null); setReturnQuantity(''); setReturnReason(''); setConfirmed(false); };
  return <section className="warehouse-distribution" style={{ '--wd-text': C.text, '--wd-muted': C.textMuted, '--wd-border': C.border, '--wd-surface': C.card, '--wd-accent': C.accent }} aria-label="Распределение по объектам">
    <div className="wd-heading"><h3>Распределение по объектам</h3><button type="button" disabled={busy || loading} onClick={load}>Обновить</button></div>
    <p>Движение с общего склада — не новый долг поставщику. Осталось по распределению — выданное минус возвраты и отправки на другие объекты, а не фактический остаток на объекте.</p>
    {loading && <p role="status">Загрузка партий и распределений…</p>}
    {error && <p role="alert">{error}</p>}
    {pages.history.error && <p role="alert">{pages.history.error}</p>}
    {pages.sources.error && <p role="alert">{pages.sources.error}</p>}
    {pendingError && <p role="alert">{pendingError}</p>}
    {pending && editable && <div role="status"><p>Есть неподтверждённая операция. Новая выдача заблокирована до проверки её результата. Повтор безопасен: используется прежний номер запроса.</p>
      <details><summary>Состав неподтверждённой операции</summary><p>{pending.payload.reason}</p>{pending.payload.rows ? <ul>{pending.payload.rows.map((r, i) => <li key={i}>Партия #{r.lotId} → объект #{r.projectId}: {r.quantity}</li>)}</ul> : <p>Возврат по распределению #{pending.path.split('/')[2]}: {pending.payload.quantity}</p>}</details>
      <button type="button" disabled={busy || accessDenied || transferBlocked || Boolean(transferSource)} onClick={() => submit(pending.path, pending.payload, () => { setRows([emptyRow()]); setReason(''); closeReturn(); }, pending)}>Повторить неподтверждённую операцию</button></div>}
    {notice && <p role="status">{notice}</p>}
    {((pages.history.truncated && !pages.history.nextCursor) || (pages.sources.truncated && !pages.sources.nextCursor)) && <p>Сервер вернул неполный реестр без продолжения. Уточните поиск.</p>}
    {editable && <form className="wd-filters" onSubmit={e => { e.preventDefault(); applied.current.sources = { q: sourceSearch.trim() }; loadPage('sources'); }}>
      <label>Поиск партий<input type="search" maxLength={200} value={sourceSearch} onChange={e => setSourceSearch(e.target.value)} /></label>
      <button disabled={busy || accessDenied}>Найти партии</button>
      {pages.sources.nextCursor && <button type="button" disabled={busy || pages.sources.loading || accessDenied} onClick={() => loadPage('sources', pages.sources.nextCursor)}>Загрузить ещё партии</button>}
    </form>}
    {editable && <form onSubmit={e => { e.preventDefault(); if (batchValid) submit('/warehouse-distributions', { companyId, reason: reason.trim(), rows: rows.map(r => ({ lotId: Number(r.lotId), projectId: Number(r.projectId), quantity: r.quantity })) }, () => { setRows([emptyRow()]); setReason(''); }); }}>
      <fieldset disabled={busy || loading || Boolean(returning) || Boolean(pending) || Boolean(pendingError) || accessDenied || transferBlocked || Boolean(transferSource)}><legend>Один пакет — все строки или ни одной</legend>
        {!loading && !sources.length && <p>{applied.current.sources.q
          ? 'По заданному поиску партий не найдено.'
          : 'Нет доступных партий общего склада. Старые поступления без учёта партий здесь не распределяются.'}</p>}
        {rows.map((row, index) => <div className="wd-row" key={index}>
          <label>Партия {index + 1}<select value={row.lotId} onChange={e => updateRow(index, 'lotId', e.target.value)}><option value="">Выберите поступление</option>{sourceOptions.map(s => <option key={s.lotId} value={s.lotId}>{s.invoiceNumber || `Накладная #${s.warehouseInvoiceId}`} · {s.materialName} · доступно {s.availableQuantity} {s.unit} · строка {s.invoiceLineIndex + 1}</option>)}</select></label>
          <label>Объект {index + 1}<select value={row.projectId} onChange={e => updateRow(index, 'projectId', e.target.value)}><option value="">Выберите объект</option>{ownProjects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
          <label>Количество {index + 1}<input inputMode="decimal" value={row.quantity} onChange={e => updateRow(index, 'quantity', e.target.value.replace(',', '.'))} /></label>
          <button type="button" disabled={rows.length === 1} aria-label={`Удалить строку ${index + 1}`} onClick={() => setRows(rows.filter((_, i) => i !== index))}>Удалить</button>
        </div>)}
        <button type="button" disabled={rows.length >= 50} onClick={() => setRows([...rows, emptyRow()])}>Добавить строку</button>
        <label>Основание распределения<textarea maxLength={1000} value={reason} onChange={e => setReason(e.target.value)} /></label>
        <button type="submit" disabled={!batchValid}>Распределить одним пакетом</button>
      </fieldset>
    </form>}
    <h4>История выдачи и возвратов</h4>
    <p>Период включает обе даты, дни считаются по UTC. Поиск применяется ко всей истории на сервере.</p>
    <form className="wd-filters" onSubmit={e => { e.preventDefault(); applied.current.history = { q: search.trim(), ...filters }; closeReturn(); loadPage('history'); }}>
      <label>Найти по объекту, материалу или накладной<input type="search" maxLength={200} value={search} onChange={e => setSearch(e.target.value)} /></label>
      <label>История: объект<select value={filters.projectId} onChange={e => setFilters({ ...filters, projectId: e.target.value })}><option value="">Все объекты</option>{projects.filter(p => Number(p.companyId ?? p.company_id) === companyId).map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
      <label>Дата с<input type="date" value={filters.dateFrom} max={filters.dateTo || undefined} onChange={e => setFilters({ ...filters, dateFrom: e.target.value })} /></label>
      <label>Дата по<input type="date" value={filters.dateTo} min={filters.dateFrom || undefined} onChange={e => setFilters({ ...filters, dateTo: e.target.value })} /></label>
      <button disabled={busy || accessDenied || Boolean(filters.dateFrom && filters.dateTo && filters.dateFrom > filters.dateTo)}>Применить фильтры</button>
    </form>
    {!loading && !records.length && <p>{Object.values(applied.current.history).some(Boolean)
      ? 'По заданным фильтрам распределений не найдено.'
      : 'Распределений в выбранной компании пока нет.'}</p>}
    <div className="wd-records">{records.map(record => <article key={record.id}>
      <h4>{record.projectName} · {record.materialName}</h4>
      <p>Накладная {record.invoiceNumber || `#${record.warehouseInvoiceId}`} · партия #{record.lotId} · распределение #{record.id}</p>
      <p>Выдано: {record.quantity} {record.unit} · Возвращено: {record.returnedQuantity} {record.unit}</p>
      {Number(record.transferredQuantity) > 0 && <p>Отправлено на другие объекты: {record.transferredQuantity} {record.unit}</p>}
      <strong>Осталось по распределению: {record.netQuantity} {record.unit}</strong>
      <p>{record.reason} {record.createdAt && `· ${record.createdAt}`} {record.createdBy && `· ${record.createdBy}`}</p>
      {record.returns?.length > 0 && <details><summary>Возвраты ({record.returns.length})</summary><ul>{record.returns.map(r => <li key={r.id}>{r.quantity} {record.unit} · {r.reason} · {r.createdAt} · {r.createdBy}</li>)}</ul></details>}
      {editable && Number(record.netQuantity) > 0 && <button type="button" disabled={busy || Boolean(pending) || Boolean(pendingError) || accessDenied || transferBlocked || Boolean(transferSource)} onClick={() => { closeReturn(); setReturning(record); }}>Оформить возврат</button>}
      {transfersEnabled && editable && Number(record.netQuantity) > 0 && <button type="button" disabled={busy || loading || Boolean(pending) || Boolean(pendingError) || accessDenied || transferBlocked} onClick={() => { closeReturn(); setTransferSource(record); }}>Отправить на другой объект</button>}
    </article>)}</div>
    {pages.history.nextCursor && <button type="button" disabled={busy || pages.history.loading || accessDenied} onClick={() => loadPage('history', pages.history.nextCursor)}>Загрузить ещё распределения</button>}
    {transfersEnabled && <WarehouseTransfersPanel companyId={companyId} editable={editable} source={transferSource} projects={projects}
      accessDenied={accessDenied} blocked={busy || loading || Boolean(pending) || Boolean(pendingError) || Boolean(returning)}
      onClose={() => setTransferSource(null)} onDenied={denyAccess} onPendingChange={setTransferBlocked}
      onChanged={async () => { await load(); await refreshData?.(); }} />}
    {editable && returning && <form onSubmit={e => { e.preventDefault(); if (confirmed && validQuantity(returnQuantity) && returnReason.trim() && Number(returnQuantity) <= Number(returning.netQuantity)) submit(`/warehouse-distributions/${returning.id}/returns`, { companyId, reason: returnReason.trim(), quantity: returnQuantity }, closeReturn); }}>
      <fieldset disabled={busy || Boolean(pending) || Boolean(pendingError) || accessDenied || transferBlocked}><legend>Возврат: {returning.projectName} · {returning.materialName}</legend>
        <p>Максимум по распределению: {returning.netQuantity} {returning.unit}. Сервер также проверит фактический остаток объекта.</p>
        <label>Количество возврата<input autoFocus inputMode="decimal" value={returnQuantity} onChange={e => setReturnQuantity(e.target.value.replace(',', '.'))} /></label>
        <label>Основание возврата<textarea maxLength={1000} value={returnReason} onChange={e => setReturnReason(e.target.value)} /></label>
        <label className="wd-confirm"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />Подтверждаю фактический возврат на общий склад и его отнесение к этому распределению. Физическая принадлежность конкретной партии системой не устанавливается.</label>
        <div className="wd-heading"><button type="submit" disabled={!confirmed || !validQuantity(returnQuantity) || !returnReason.trim() || Number(returnQuantity) > Number(returning.netQuantity)}>Подтвердить возврат</button><button type="button" onClick={closeReturn}>Отмена</button></div>
      </fieldset>
    </form>}
  </section>;
}
