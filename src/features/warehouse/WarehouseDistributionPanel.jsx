import React, { useCallback, useEffect, useRef, useState } from 'react';
import { API } from '../../api';
import { warehouseRequestId, pendingCommand, saveCommand, clearCommand, readResponse, validateList, validateCommandResult } from './distributionCommands';
import useWarehouseBatchDraft from './useWarehouseBatchDraft';
import useWarehouseReturnDraft from './useWarehouseReturnDraft';
import WarehouseTransfersPanel from './WarehouseTransfersPanel';
import IntercompanyWarehouseTransfersPanel from './IntercompanyWarehouseTransfersPanel';
import './WarehouseDistributionPanel.css';

const emptyRow = () => ({ lotId: '', projectId: '', quantity: '' });
const unverifiedSource = source => ({ ...source, availabilityUnknown: true });
const writers = ['директор', 'зам_директора', 'кладовщик', 'снабженец'];
const readers = [...writers, 'бухгалтер'];
const validQuantity = value => /^\d+(\.\d{1,6})?$/.test(value) && Number(value) > 0 && Number(value) < 100000000;
const quantityUnits = value => {
  const [whole, fraction = ''] = String(value).split('.');
  return /^\d+$/.test(whole) && /^\d{0,6}$/.test(fraction) ? Number(whole) * 1000000 + Number(fraction.padEnd(6, '0')) : null;
};
const formatUnits = value => String(value / 1000000);
const countLabel = (count, one, few, many) => {
  const lastTwo = count % 100;
  if (lastTwo >= 11 && lastTwo <= 14) return many;
  const last = count % 10;
  return last === 1 ? one : last >= 2 && last <= 4 ? few : many;
};
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
  return <CompanyDistribution key={`${props.user?.id}:${selectedCompanyId}:${editable}`} {...props} companyId={Number(selectedCompanyId)} companies={companies} editable={editable} />;
}

function CompanyDistribution({ companyId, companies, editable, user, projects = [], warehouseMain = [], refreshData, C = {} }) {
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
    setRecords([]); setSources([]); setSelectedSources([]); setRows([emptyRow()]); setReason('');
    setReturning(null); setReturnQuantity(''); setReturnReason(''); setConfirmed(false); setTransferSource(null); setTransferBlocked(false); setAccessDenied(true);
  }, []);
  const draft = useWarehouseBatchDraft({ companyId, userId: user?.id, enabled: editable && !accessDenied, rows, reason, setRows, setReason, setSelectedSources, onDenied: denyAccess });
  const returnDraft = useWarehouseReturnDraft({ companyId, userId: user?.id, enabled: editable && !accessDenied,
    returning, quantity: returnQuantity, reason: returnReason, setReturning, setQuantity: setReturnQuantity,
    setReason: setReturnReason, setConfirmed, onDenied: denyAccess });
  const loadPage = useCallback(async (kind, beforeId = null) => {
    if (denied.current || (beforeId && inFlight.current[kind])) return;
    const source = kind === 'sources';
    const current = ++generation.current[kind];
    inFlight.current[kind] = true;
    const setItems = source ? setSources : setRecords;
    if (!beforeId) {
      setItems([]);
      if (source && !applied.current.sources.q) setSelectedSources(previous => previous.map(unverifiedSource));
    }
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
      // A selected lot can outlive the search page. Always retain its newest
      // observed balance, never the older snapshot captured at selection time.
      if (source) setSelectedSources(previous => previous.map(selected => {
        const fresh = data.items.find(item => item.lotId === selected.lotId);
        return fresh ? { ...fresh, availabilityUnknown: false } : selected;
      }));
      setPages(previous => ({ ...previous, [kind]: { nextCursor: data.nextCursor ?? null, truncated: Boolean(data.truncated), loading: false } }));
    } catch (e) {
      if (active.current && current === generation.current[kind]) {
        setItems([]);
        if (source) setSelectedSources(previous => previous.map(unverifiedSource));
        if ([401, 403].includes(e.status)) { denyAccess(); setError(e.message); }
        else setPages(previous => ({ ...previous, [kind]: { loading: false, error: e.message || 'Не удалось загрузить распределения.' } }));
      }
    } finally {
      if (active.current && current === generation.current[kind]) inFlight.current[kind] = false;
    }
  }, [companyId, denyAccess]);
  const load = useCallback(() => {
    denied.current = false; setAccessDenied(false); setError('');
    setSelectedSources(previous => previous.map(unverifiedSource));
    return Promise.all([loadPage('history'), editable ? loadPage('sources') : Promise.resolve()]);
  }, [editable, loadPage]);
  useEffect(() => {
    const requests = generation.current;
    active.current = true; load();
    return () => { active.current = false; requests.history += 1; requests.sources += 1; };
  }, [load]);
  useEffect(() => {
    if (!editable) return;
    try { command.current = pendingCommand(companyId, user?.id); setPending(command.current); }
    catch (e) { setPendingError(e.message || 'Хранилище сеанса недоступно.'); }
  }, [companyId, editable, user?.id]);

  async function submit(path, payload, reset, retryCommand = null) {
    if (locked.current || !editable || accessDenied || pendingError || transferBlocked || transferSource) return;
    locked.current = true; setBusy(true); setError(''); setNotice('');
    const returningCommand = path.endsWith('/returns');
    const persistence = returningCommand ? returnDraft : draft;
    let hadPending = false;
    try {
      const signature = JSON.stringify({ path, ...payload });
      const existing = pendingCommand(companyId, user?.id) || retryCommand;
      hadPending = Boolean(existing);
      if (existing && existing.signature !== signature) { setPending(existing); throw new Error('Сначала повторите неподтверждённую операцию.'); }
      const draftRevision = !existing ? await persistence.flush() : existing?.draftRevision;
      if (!active.current) return;
      command.current = existing || { signature, id: warehouseRequestId(), path, payload, ...(draftRevision ? { draftRevision } : {}) };
      saveCommand(companyId, command.current, user?.id); setPending(command.current);
      const result = await fetch(`${API}${path}`, { method: 'POST', credentials: 'include', headers: { ...headers, 'Content-Type': 'application/json', ...(command.current.draftRevision ? { [returningCommand ? 'X-Warehouse-Return-Draft-Revision' : 'X-Warehouse-Draft-Revision']: String(command.current.draftRevision) } : {}) }, body: JSON.stringify({ ...payload, requestId: command.current.id }) }).then(readResponse);
      validateCommandResult(result, command.current);
      clearCommand(companyId, command.current.id, user?.id);
      if (!active.current) return;
      command.current = null; setPending(pendingCommand(companyId, user?.id));
      if (draftRevision) {
        if (returningCommand) await returnDraft.reloadAfterOperation();
        else await draft.reloadAfterIssue();
      }
      else reset();
      if (!active.current) return;
      setNotice('Операция сохранена. Ниже — результат последнего обновления истории.');
      await load();
      if (!active.current) return;
      try { await refreshData?.(); } catch (_) { if (active.current) setNotice('Операция сохранена. Обновите остальные разделы страницы.'); }
    } catch (e) {
      if ((!hadPending && [400, 409, 422].includes(e.status)) || ['warehouse_draft_conflict', 'warehouse_return_draft_conflict'].includes(e.code)) {
        try {
          clearCommand(companyId, command.current?.id, user?.id); command.current = null;
          if (active.current) setPending(pendingCommand(companyId, user?.id));
        } catch (_) { if (active.current) setPendingError('Не удалось проверить хранилище неподтверждённой операции.'); }
      }
      if (active.current && ['warehouse_draft_conflict', 'warehouse_return_draft_conflict'].includes(e.code)) persistence.rejectConflict(e);
      if (active.current && [401, 403].includes(e.status)) denyAccess();
      if (active.current) setError(`${e.message || 'Нет ответа сервера.'} Для неподтверждённой операции используйте кнопку безопасного повтора.`);
    } finally {
      locked.current = false; if (active.current) setBusy(false);
    }
  }
  const sourceOptions = [...sources, ...selectedSources.filter(s => !sources.some(item => item.lotId === s.lotId))];
  const lotTotals = new Map();
  rows.forEach(row => {
    if (!row.lotId || !validQuantity(row.quantity)) return;
    const lotId = Number(row.lotId);
    lotTotals.set(lotId, (lotTotals.get(lotId) || 0) + quantityUnits(row.quantity));
  });
  const batchProblems = rows.flatMap((row, index) => {
    const missing = [];
    const selected = sourceOptions.find(source => source.lotId === Number(row.lotId));
    if (!selected) missing.push('выберите партию');
    else if (selected.availabilityUnknown) missing.push('обновите остаток выбранной партии: найдите её в списке');
    if (!ownProjects.some(project => Number(project.id) === Number(row.projectId))) missing.push('выберите объект');
    if (!validQuantity(row.quantity)) missing.push('укажите количество больше нуля (до 6 знаков после запятой)');
    return missing.length ? [`Строка ${index + 1}: ${missing.join('; ')}.`] : [];
  });
  sourceOptions.forEach(source => {
    const requested = lotTotals.get(source.lotId);
    const available = quantityUnits(source.availableQuantity);
    if (!source.availabilityUnknown && requested != null && available != null && requested > available) {
      batchProblems.push(`Партия «${source.materialName}»: указано ${formatUnits(requested)} ${source.unit}, доступно ${formatUnits(available)} ${source.unit}. Уменьшите количество в строках этой партии.`);
    }
  });
  if (!reason.trim()) batchProblems.push('Укажите основание распределения.');
  const batchValid = batchProblems.length === 0;
  const batchBlocked = busy || loading || draft.loading || returnDraft.loading || Boolean(returning || pending || pendingError || transferSource) || accessDenied || transferBlocked;
  const selectedProjectCount = new Set(rows.filter(row => ownProjects.some(project => Number(project.id) === Number(row.projectId))).map(row => row.projectId)).size;
  const updateRow = (index, field, value) => {
    const next = rows.map((r, i) => i === index ? { ...r, [field]: value } : r);
    setRows(next);
    setSelectedSources(sourceOptions.filter(s => next.some(r => Number(r.lotId) === s.lotId)));
  };
  const closeReturn = () => { setReturning(null); setReturnQuantity(''); setReturnReason(''); setConfirmed(false); };
  // Retain the dispatch form through history refreshes, but authorize a new
  // submission only from the freshly loaded allocation and its current balance.
  const loadedTransferSource = transferSource && records.find(record => record.id === transferSource.id);
  const transferSourceUnavailable = Boolean(transferSource && (!loadedTransferSource || pages.history.loading || pages.history.error));
  const loadedReturnSource = returning && records.find(record => record.id === returning.id);
  const returnSource = loadedReturnSource || returning;
  const returnUnavailable = Boolean(returning && (!loadedReturnSource || pages.history.loading || pages.history.error));
  const returnBlocked = busy || loading || returnDraft.loading || Boolean(pending || pendingError || transferSource) || accessDenied || transferBlocked;
  const returnValid = returnDraft.readyToSubmit && !returnUnavailable && confirmed && validQuantity(returnQuantity) && returnReason.trim()
    && returnSource && Number(returnQuantity) <= Number(returnSource.netQuantity);
  return <><section className="warehouse-distribution" style={{ '--wd-text': C.text, '--wd-muted': C.textSec || C.textMuted, '--wd-border': C.border, '--wd-surface': C.bgWhite || C.card, '--wd-accent': C.accent }} aria-label="Распределение по объектам">
    <div className="wd-heading"><div><h3>Материалы по объектам</h3><p>Выдайте материалы с общего склада и отслеживайте возвраты.</p></div><button type="button" disabled={busy || loading} onClick={load}>Обновить</button></div>
    <details className="wd-help"><summary>Как считается остаток</summary><p>В истории показано, сколько было выдано, возвращено и отправлено на другой объект. Это не фактический остаток на объекте и не новый долг поставщику.</p></details>
    {loading && <p role="status">Загрузка партий и распределений…</p>}
    {!editable && error && <p role="alert">{error}</p>}
    {pages.history.error && <p role="alert">{pages.history.error}</p>}
    {pages.sources.error && <p role="alert">{pages.sources.error}</p>}
    {pendingError && <p role="alert">{pendingError}</p>}
    {pending && editable && <div role="status"><p>Есть неподтверждённая операция. Новая выдача заблокирована до проверки её результата. Повтор безопасен: используется прежний номер запроса.</p>
      <details><summary>Состав неподтверждённой операции</summary><p>{pending.payload.reason}</p>{pending.payload.rows ? <ul>{pending.payload.rows.map((r, i) => <li key={i}>Партия #{r.lotId} → объект #{r.projectId}: {r.quantity}</li>)}</ul> : <p>Возврат по распределению #{pending.path.split('/')[2]}: {pending.payload.quantity}</p>}</details>
      <button type="button" disabled={busy || accessDenied || transferBlocked || Boolean(transferSource)} onClick={() => submit(pending.path, pending.payload, () => {
        if (pending.path.endsWith('/returns')) closeReturn();
        else { setRows([emptyRow()]); setReason(''); setSelectedSources([]); }
      }, pending)}>Повторить неподтверждённую операцию</button></div>}
    {!editable && notice && <p role="status">{notice}</p>}
    {((pages.history.truncated && !pages.history.nextCursor) || (pages.sources.truncated && !pages.sources.nextCursor)) && <p>Сервер вернул неполный реестр без продолжения. Уточните поиск.</p>}
    {editable && <form className="wd-filters" onSubmit={e => { e.preventDefault(); applied.current.sources = { q: sourceSearch.trim() }; loadPage('sources'); }}>
      <label>Поиск партий<input type="search" maxLength={200} value={sourceSearch} onChange={e => setSourceSearch(e.target.value)} /></label>
      <button disabled={busy || accessDenied}>Найти партии</button>
      {pages.sources.nextCursor && <button type="button" disabled={busy || pages.sources.loading || accessDenied} onClick={() => loadPage('sources', pages.sources.nextCursor)}>Загрузить ещё партии</button>}
    </form>}
    {editable && <form onSubmit={e => { e.preventDefault(); if (batchValid && !batchBlocked && draft.readyToSubmit) submit('/warehouse-distributions', { companyId, reason: reason.trim(), rows: rows.map(r => ({ lotId: Number(r.lotId), projectId: Number(r.projectId), quantity: r.quantity })) }, () => { setRows([emptyRow()]); setReason(''); setSelectedSources([]); }); }}>
      <div aria-live="polite">
        {draft.loading ? <p role="status">Загружаем ваш серверный черновик…</p> : draft.error ? <div role="alert"><p>{draft.error}</p><p>Введённые правки остаются в форме. Не закрывайте страницу, пока они не сохранены.</p></div>
          : <p role="status">{draft.saving ? 'Сохраняем черновик…' : draft.dirty ? 'Есть несохранённые изменения.' : 'Черновик сохранён на сервере.'}</p>}
        {draft.error && <><button type="button" onClick={draft.download}>Скачать мои правки</button><button type="button" onClick={draft.reloadFromServer}>Загрузить серверный черновик</button></>}
        {!draft.loading && <button type="button" disabled={busy || draft.saving || accessDenied || draft.phase === 'conflict'} onClick={() => draft.flush().catch(() => {})}>Сохранить черновик</button>}
        <button type="button" disabled={busy || draft.loading || Boolean(pending) || accessDenied} onClick={draft.clear}>Очистить черновик</button>
        {draft.lastOperation && !draft.dirty && !reason && <p>Предыдущая выдача сохранена. Результат доступен в истории.</p>}
      </div>
      <fieldset className="wd-batch" disabled={batchBlocked}><legend>Новая выдача</legend>
        <p className="wd-batch-intro">Выберите партию, объект и количество. Можно добавить несколько материалов.</p>
        {!loading && !sources.length && <p>{applied.current.sources.q
          ? 'По заданному поиску партий не найдено.'
          : 'Нет доступных партий общего склада. Старые поступления без учёта партий здесь не распределяются.'}</p>}
        <div className="wd-table-head" aria-hidden="true"><span>Партия и материал</span><span>Объект</span><span>Количество</span><span>Остаток после выдачи</span><span></span></div>
        {rows.map((row, index) => {
          const selectedLot = sourceOptions.find(source => source.lotId === Number(row.lotId));
          const available = selectedLot && !selectedLot.availabilityUnknown ? quantityUnits(selectedLot.availableQuantity) : null;
          const requested = selectedLot && lotTotals.get(selectedLot.lotId);
          const remaining = available != null && requested != null ? formatUnits(available - requested) : null;
          return <div className="wd-row" key={index}>
          <div className="wd-row-heading"><strong>Материал {index + 1}</strong></div>
          <label>Партия {index + 1}<select value={row.lotId} onChange={e => updateRow(index, 'lotId', e.target.value)}><option value="">Выберите поступление</option>{row.lotId && !selectedLot && <option value={row.lotId}>Партия #{row.lotId} — загрузите доступный остаток</option>}{sourceOptions.map(s => <option key={s.lotId} value={s.lotId}>{s.invoiceNumber || `Накладная #${s.warehouseInvoiceId}`} · {s.materialName} · {s.availabilityUnknown ? 'остаток не подтверждён' : `доступно ${s.availableQuantity} ${s.unit}`} · строка {s.invoiceLineIndex + 1}</option>)}</select></label>
          <label>Объект {index + 1}<select value={row.projectId} onChange={e => updateRow(index, 'projectId', e.target.value)}><option value="">Выберите объект</option>{row.projectId && !ownProjects.some(p => Number(p.id) === Number(row.projectId)) && <option value={row.projectId}>Объект #{row.projectId} недоступен</option>}{ownProjects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
          <label>Количество {index + 1}<input inputMode="decimal" maxLength={100} value={row.quantity} onChange={e => updateRow(index, 'quantity', e.target.value.replace(',', '.'))} /></label>
          <p className={`wd-row-available${remaining != null && Number(remaining) < 0 ? ' wd-overdrawn' : ''}`}>{selectedLot?.availabilityUnknown ? 'Выбранная партия сохранена. Остаток не подтверждён: обновите её данные через поиск или список.' : selectedLot ? `Доступно ${selectedLot.availableQuantity} ${selectedLot.unit}${remaining != null ? ` · останется ${remaining} ${selectedLot.unit}` : ''}` : 'Выберите партию'}</p>
          <button type="button" disabled={rows.length === 1} aria-label={`Удалить строку ${index + 1}`} onClick={() => setRows(rows.filter((_, i) => i !== index))}>Удалить</button>
        </div>;
        })}
        <button className="wd-add-row" type="button" disabled={rows.length >= 50} onClick={() => setRows([...rows, emptyRow()])}>+ Добавить материал</button>
        <label>Основание распределения<textarea maxLength={1000} value={reason} onChange={e => setReason(e.target.value)} placeholder="Например: передача материалов на объект" /></label>
        <p className="wd-batch-summary">В пакете: {rows.length} {countLabel(rows.length, 'строка', 'строки', 'строк')} · {selectedProjectCount} {countLabel(selectedProjectCount, 'объект', 'объекта', 'объектов')} · {lotTotals.size} {countLabel(lotTotals.size, 'партия', 'партии', 'партий')}</p>
        <button className="wd-submit" type="submit" disabled={!batchValid || !draft.readyToSubmit} aria-describedby="distribution-submit-feedback">Распределить одним пакетом</button>
      </fieldset>
      <div id="distribution-submit-feedback" aria-live="polite">
        {busy ? <p role="status">Сохраняем распределение…</p> : <>
          {error && <p role="alert">{error}</p>}
          {notice && <p role="status">{notice}</p>}

          {pending && <p>Результат предыдущей операции ещё не подтверждён. Используйте кнопку «Повторить неподтверждённую операцию» выше.</p>}
          {loading && <p>Дождитесь загрузки партий и распределений.</p>}
          {(returning || transferBlocked || transferSource) && <p>Сначала завершите или закройте текущий возврат или перемещение.</p>}
          {!loading && !pending && !accessDenied && !pendingError && batchProblems.length > 0 && <><p>Чтобы распределить материалы:</p><ul>{batchProblems.map(problem => <li key={problem}>{problem}</li>)}</ul></>}
        </>}
      </div>

    </form>}
    {editable && (returning || returnDraft.loading || returnDraft.error || returnDraft.dirty || returnDraft.lastOperation) && <div aria-label="Серверный черновик возврата" aria-live="polite">
      {returnDraft.loading ? <p role="status">Загружаем серверный черновик возврата…</p> : returnDraft.error
        ? <p role="alert">{returnDraft.error}</p>
        : <p role="status">{returnDraft.saving ? 'Сохраняем черновик возврата…' : returnDraft.dirty ? 'Есть несохранённые правки возврата.' : 'Черновик возврата сохранён на сервере.'}</p>}
      {returnDraft.error && <><button type="button" disabled={busy || returnDraft.saving || accessDenied} onClick={returnDraft.download}>Скачать правки возврата</button><button type="button" disabled={busy || returnDraft.saving || accessDenied} onClick={returnDraft.reloadFromServer}>Загрузить серверный возврат</button></>}
      {(returning || returnDraft.dirty) && <button type="button" disabled={busy || returnDraft.loading || returnDraft.saving || accessDenied || returnDraft.phase === 'conflict'} onClick={() => returnDraft.flush().catch(() => {})}>Сохранить черновик возврата</button>}
      {returnDraft.lastOperation && !returning && !returnDraft.dirty && <p>Предыдущий возврат сохранён. Результат доступен в истории.</p>}
    </div>}
    <h4>История выдачи и возвратов</h4>
    <details className="wd-help"><summary>О поиске и датах</summary><p>Поиск проверяет всю историю на сервере. Период включает обе выбранные даты; дни считаются по UTC.</p></details>
    <form className="wd-filters" onSubmit={e => { e.preventDefault(); applied.current.history = { q: search.trim(), ...filters }; loadPage('history'); }}>
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
      {editable && Number(record.netQuantity) > 0 && <button type="button" disabled={returnBlocked || Boolean(returning)} onClick={() => { closeReturn(); setReturning(record); }}>Оформить возврат</button>}
      {transfersEnabled && editable && Number(record.netQuantity) > 0 && <button type="button" disabled={busy || loading || Boolean(pending) || Boolean(pendingError) || accessDenied || transferBlocked || Boolean(transferSource || returning) || returnDraft.loading} onClick={() => { closeReturn(); setTransferSource(record); }}>Отправить на другой объект</button>}
    </article>)}</div>
    {pages.history.nextCursor && <button type="button" disabled={busy || pages.history.loading || accessDenied} onClick={() => loadPage('history', pages.history.nextCursor)}>Загрузить ещё распределения</button>}
    {transfersEnabled && <WarehouseTransfersPanel companyId={companyId} editable={editable} source={loadedTransferSource || transferSource} sourceUnavailable={transferSourceUnavailable} projects={projects}
      accessDenied={accessDenied} blocked={busy || loading || returnDraft.loading || Boolean(pending) || Boolean(pendingError) || Boolean(returning)}
      onClose={() => setTransferSource(null)} onDenied={denyAccess} onPendingChange={setTransferBlocked}
      onChanged={async () => { await load(); await refreshData?.(); }} />}
    {editable && returning && <form onSubmit={e => { e.preventDefault(); if (returnValid && !returnBlocked) submit(`/warehouse-distributions/${returning.id}/returns`, { companyId, reason: returnReason.trim(), quantity: returnQuantity }, closeReturn); }}>
      <fieldset disabled={returnBlocked}><legend>Возврат: {returnSource.projectName} · {returnSource.materialName}</legend>
        {returnUnavailable && <p role="status">Черновик возврата сохранён в открытой форме. Остаток пока не подтверждён: обновите историю распределений или очистите её фильтры.</p>}
        <p>Максимум по распределению: {returnSource.netQuantity} {returnSource.unit}. Сервер также проверит фактический остаток объекта.</p>
        <label>Количество возврата<input autoFocus inputMode="decimal" maxLength={100} value={returnQuantity} onChange={e => setReturnQuantity(e.target.value.replace(',', '.'))} /></label>
        <label>Основание возврата<textarea maxLength={1000} value={returnReason} onChange={e => setReturnReason(e.target.value)} /></label>
        <label className="wd-confirm"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />Подтверждаю фактический возврат на общий склад и его отнесение к этому распределению. Физическая принадлежность конкретной партии системой не устанавливается.</label>
        <div className="wd-heading"><button type="submit" disabled={!returnValid}>Подтвердить возврат</button><button type="button" onClick={closeReturn}>Отмена</button></div>
      </fieldset>
    </form>}
  </section><IntercompanyWarehouseTransfersPanel companyId={companyId} companies={companies} warehouseMain={warehouseMain} editable={editable} onChanged={refreshData}
    style={{ '--wd-text': C.text, '--wd-muted': C.textSec || C.textMuted, '--wd-border': C.border, '--wd-surface': C.bgWhite || C.card, '--wd-accent': C.accent }} /></>;
}
