import React, { useEffect, useState } from 'react';
import { useLedger } from '../work-material-accounting/ledgerUi';
import WorkSubmissionRecovery from '../work-material-accounting/WorkSubmissionRecovery';
import ToolCustodyPanel from '../tool-custody/ToolCustodyPanel';
import { actions, buildInventoryReport, conditions } from './inventoryPrint';
import '../work-material-accounting/ledger.css';
import './inventory.css';

export const inventoryReconciliationEnabled = () => process.env.REACT_APP_INVENTORY_RECONCILIATION_ENABLED === '1';

function draftRows(rows) {
  return rows.map(row => row.kind === 'tool'
    ? { key: row.key, condition: row.condition || '', reason: row.reason || '' }
    : { key: row.key, actual: row.actual == null ? '' : String(row.actual), reason: row.reason || row.notes || '' });
}

function InventoryDetail({ inventoryId, onClose, ...props }) {
  const path = `/inventory/${inventoryId}/reconciliation`;
  const { data, error, busy, submit, recovered, reload, setError } = useLedger({ ...props, path, onRecovered: () => setError('') });
  const [draft, setDraft] = useState({ state: null, counts: [] });
  const [reason, setReason] = useState('');
  const [deductions, setDeductions] = useState({});
  const [tool, setTool] = useState(null);
  useEffect(() => {
    if (data) { setDeductions({}); setReason(''); }
  }, [data]);
  const counts = draft.state === data?.expectedState ? draft.counts : draftRows(data?.rows || []);
  const update = (key, field, value) => setDraft({ state: data.expectedState,
    counts: counts.map(c => c.key === key ? { ...c, [field]: value } : c) });
  const dirty = data && JSON.stringify(counts) !== JSON.stringify(draftRows(data.rows));
  const shortageRows = data?.rows.filter(r => r.kind === 'material' && r.stockTable === 'warehouse_main' && Number(r.actual) < Number(r.expected)) || [];
  const command = action => submit(path, { action, expectedState: data.expectedState, reason,
    ...(action === 'save' ? { counts: counts.map(c => 'actual' in c ? { ...c, actual: c.actual === '' ? null : c.actual } : { ...c, condition: c.condition || null }) } : {}),
    ...(action === 'approve' ? { lotDeductions: shortageRows.map(r => ({ key: r.key,
      untrackedQuantity: deductions[r.key]?.untrackedQuantity || '0',
      lots: (r.lots || []).map(l => ({ lotId: l.lotId, quantity: deductions[r.key]?.[l.lotId] || '0' })),
    })) } : {}),
  });
  const setDeduction = (key, source, value) => setDeductions(values => ({ ...values, [key]: { ...values[key], [source]: value } }));
  return <section className="inventory-detail">
    <div className="ledger-actions"><h3>Ведомость №{inventoryId}</h3><button disabled={busy} onClick={onClose}>К списку</button></div>
    <WorkSubmissionRecovery {...props} onRecovered={recovered} />
    {error && <p role="alert" className="ledger-error">{error} <button disabled={busy} onClick={() => reload().then(() => setError('')).catch(e => setError(e.message))}>Обновить ведомость</button></p>}
    {!data && !error && <p role="status">Загрузка ведомости…</p>}
    {data && <>
      <p><b>{data.inventory.project}</b> · {data.inventory.date} · {data.inventory.status}</p>
      {data.inventory.notes && <p>{data.inventory.notes}</p>}
      {data.inventory.legacy && <p>Прежняя ведомость сохранена для чтения. Для нового пересчёта создайте новую сверку.</p>}
      {data.canCount && <p>Введите фактическое наличие. Пустое поле означает «не пересчитано»; ноль укажите явно. Материалы на руках и в пути в складской остаток не входят.</p>}
      <fieldset disabled={busy || !data.canCount} className="inventory-fields">
        {data.rows.map(row => {
          const count = counts.find(c => c.key === row.key) || {};
          return <article key={row.key} className="inventory-row"><div><b>{row.name}</b>
            {row.kind === 'tool' ? <p>№{row.inventoryNumber || row.toolId} · {row.status}{row.holderName ? ` · ${row.holderName}` : ''}</p>
              : <p>По учёту: {row.expected} {row.unit}{row.package ? ` · ${row.package}` : ''}</p>}</div>
            {row.kind === 'tool'
              ? <label>Проверка: {row.name}<select value={count.condition || ''} onChange={e => update(row.key, 'condition', e.target.value)}><option value="">Не проверено</option>{Object.entries(conditions).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
              : <label>Факт: {row.name}<input type="number" min="0" step="any" inputMode="decimal" value={count.actual ?? ''} onChange={e => update(row.key, 'actual', e.target.value)} /></label>}
            <label>Причина: {row.name}<textarea maxLength={4000} value={count.reason || ''} onChange={e => update(row.key, 'reason', e.target.value)} /></label>
            {row.difference != null && <p>Расхождение в сохранённой ведомости: {row.difference} {row.unit}</p>}
          </article>;
        })}
      </fieldset>
      <div className="ledger-actions">
        {data.canCount && <><button disabled={busy} className="primary" onClick={() => command('save')}>Сохранить пересчёт</button><button disabled={busy || dirty} onClick={() => command('submit')}>Передать директору</button></>}
        {props.showPreview && <button disabled={busy || dirty} onClick={() => props.showPreview(buildInventoryReport(data), 'Ведомость инвентаризации')}>Печатная ведомость</button>}
      </div>
      {dirty && <p>Есть несохранённые изменения. Сохраните пересчёт перед передачей директору или печатью.</p>}
      {data.canDecide && <section><h4>Решение директора</h4><fieldset disabled={busy} className="inventory-fields">
        {data.inventory.state === 'submitted' && shortageRows.map(row => <article key={row.key} className="inventory-row"><b>{row.name}: распределение недостачи {Math.abs(Number(row.difference)).toLocaleString('ru-RU')} {row.unit}</b>
          <p>Укажите, из каких партий отсутствует материал. Учётное количество каждой партии сохранено при начале сверки.</p>
          <label>Без привязки к партии (доступно {row.untrackedQuantity})<input type="number" min="0" step="any" value={deductions[row.key]?.untrackedQuantity || ''} onChange={e => setDeduction(row.key, 'untrackedQuantity', e.target.value)} /></label>
          {(row.lots || []).map(lot => <label key={lot.lotId}>Партия №{lot.lotId}, накладная №{lot.invoiceId} (доступно {lot.quantity})<input type="number" min="0" step="any" value={deductions[row.key]?.[lot.lotId] || ''} onChange={e => setDeduction(row.key, lot.lotId, e.target.value)} /></label>)}
        </article>)}
        <label>Основание решения<textarea maxLength={4000} value={reason} onChange={e => setReason(e.target.value)} /></label>
        <div className="ledger-actions">
          {data.inventory.state === 'submitted' && <><button className="primary" disabled={!reason.trim()} onClick={() => command('approve')}>Утвердить и скорректировать остатки</button><button disabled={!reason.trim()} onClick={() => command('return')}>Вернуть на пересчёт</button></>}
          <button disabled={!reason.trim()} onClick={() => command('cancel')}>Отменить ведомость</button>
        </div>
        <p>Утверждение проводит разницу материалов отдельными складскими операциями. Штрафы этой ведомостью не назначаются.</p>
      </fieldset></section>}
      {data.inventory.state === 'approved' && data.rows.filter(r => r.kind === 'tool' && r.condition !== 'as_recorded').map(row => <article key={row.key} className="inventory-row"><b>{row.name}: {conditions[row.condition]}</b><p>Оформите отдельную операцию инструмента по результату проверки.</p><button onClick={() => setTool({ id: row.toolId })}>Операции и ответственность</button></article>)}
      <h4>История сверки</h4>{data.history.map(event => <article key={event.id}><b>{actions[event.action]}</b><p>{event.actorName} · {new Date(event.createdAt).toLocaleString('ru-RU')}</p>{event.reason && <p>{event.reason}</p>}</article>)}
    </>}
    {tool && <ToolCustodyPanel {...props} tool={tool} onClose={() => setTool(null)} />}
  </section>;
}

function Workspace(props) {
  const { data, error, busy, submit, recovered, reload, setError } = useLedger({ ...props, path: '/inventory/reconciliation', onRecovered: () => setError('') });
  const [selected, setSelected] = useState(null);
  const [project, setProject] = useState('');
  const [notes, setNotes] = useState('');
  const [creating, setCreating] = useState(false);
  if (selected) return <InventoryDetail {...props} inventoryId={selected} onClose={() => {
    setSelected(null); reload().catch(e => setError(e.message));
  }} />;
  return <>
    <WorkSubmissionRecovery {...props} onRecovered={recovered} />
    <div className="ledger-actions"><h3>Инвентаризация</h3>{data?.canCreate && <button disabled={busy} onClick={() => setCreating(!creating)}>Новая сверка</button>}</div>
    {error && <p role="alert" className="ledger-error">{error}</p>}
    {!data && !error && <p role="status">Загрузка инвентаризаций…</p>}
    {creating && <fieldset disabled={busy} className="inventory-fields inventory-row"><label>Место пересчёта<select value={project} onChange={e => setProject(e.target.value)}><option value="">Выберите склад или объект</option>{data?.canCountMain !== false && <option value="main">Основной склад</option>}{data?.projects.map(p => <option key={p.id} value={p.id}>{p.name} · №{p.id}</option>)}</select></label>
      <label>Примечание<textarea maxLength={4000} value={notes} onChange={e => setNotes(e.target.value)} /></label>
      <button className="primary" disabled={!project} onClick={async () => { if (await submit('/inventory/reconciliation', { projectId: project === 'main' ? null : Number(project), notes })) { setCreating(false); setNotes(''); } }}>Начать пересчёт</button>
    </fieldset>}
    {data?.items.map(inv => <article key={inv.id} className="inventory-list-row"><div><b>{inv.project}</b><p>№{inv.id} · {inv.date} · {inv.status}{inv.legacy ? ' · прежняя ведомость' : ''}</p></div><button onClick={() => setSelected(inv.id)}>Открыть</button></article>)}
    {data && !data.items.length && <p>Ведомостей пока нет. Новая сверка сохранит снимок учёта для пересчёта.</p>}
    {data?.truncated && <p>Показаны последние 500 ведомостей.</p>}
  </>;
}

export default function InventoryWorkspace(props) {
  if (props.companyContext?.mode !== 'company' || !props.companyContext?.selectedCompanyId) return <p>Для инвентаризации выберите конкретную компанию.</p>;
  return <div className="work-ledger inventory-workspace" style={{ '--ledger-bg': props.C.card || props.C.bg, '--ledger-text': props.C.text, '--ledger-border': props.C.border }}>
    <Workspace key={`${props.companyContext.selectedCompanyId}:${props.user?.id}:${props.user?.role}`} {...props} />
  </div>;
}
