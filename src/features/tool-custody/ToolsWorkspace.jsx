import React, { useState } from 'react';
import ToolCustodyPanel from './ToolCustodyPanel';
import { formatMoney } from '../work-material-accounting/ledgerUi';
import '../work-material-accounting/ledger.css';

function ToolForm({ initial, API, companyId, onSaved, onCancel }) {
  const [form, setForm] = useState(initial || { name: '', inventoryNumber: '', cost: '', notes: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const save = async event => {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const response = await fetch(API + '/tools' + (initial ? '/' + initial.id : ''), {
        method: initial ? 'PUT' : 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-Company-Id': String(companyId), 'X-Company-Mode': 'company' },
        body: JSON.stringify({ ...form, cost: Number(form.cost) }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result?.detail === 'string' ? result.detail : 'Не удалось сохранить инструмент.');
      await onSaved();
    } catch (e) { setError(e.message || 'Не удалось сохранить инструмент.'); }
    finally { setBusy(false); }
  };
  return <form onSubmit={save}><section><h4>{initial ? 'Карточка каталога' : 'Новый инструмент'}</h4>
    {error && <p role="alert" className="ledger-error">{error}</p>}
    <fieldset disabled={busy} style={{ border: 0, padding: 0 }}>
      <div className="ledger-grid">
        <label>Название<input required maxLength={255} value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} /></label>
        <label>Инвентарный номер<input maxLength={100} value={form.inventoryNumber} onChange={e => setForm({ ...form, inventoryNumber: e.target.value })} /></label>
        <label>Стоимость, ₽<input type="number" min="0" step="0.01" value={form.cost} onChange={e => setForm({ ...form, cost: e.target.value })} /></label>
      </div>
      <label>Примечание<textarea maxLength={4000} value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} /></label>
      <p>{initial ? 'Выдача, возврат и изменение состояния оформляются в карточке операций.' : 'Инструмент будет добавлен на основной склад.'}</p>
      <div className="ledger-actions"><button className="primary" type="submit" disabled={!form.name.trim()}>{busy ? 'Сохраняем…' : 'Сохранить инструмент'}</button><button type="button" onClick={onCancel}>Отмена</button></div>
    </fieldset>
  </section></form>;
}

function Workspace({ tools, toolHistory, API, companyContext, user, C, refreshData }) {
  const [selected, setSelected] = useState(null);
  const [editing, setEditing] = useState(undefined);
  const [search, setSearch] = useState('');
  const [tab, setTab] = useState('list');
  const [showArchive, setShowArchive] = useState(false);
  const selectedCompany = companyContext?.mode === 'company' && Number(companyContext?.selectedCompanyId) > 0;
  const canManage = selectedCompany && ['директор', 'зам_директора', 'прораб', 'главный_инженер', 'кладовщик', 'снабженец'].includes(user?.role);
  const visible = tools.filter(tool => (showArchive || tool.status !== 'В архиве')
    && [tool.name, tool.inventoryNumber, tool.masterName, tool.project].join(' ').toLocaleLowerCase('ru-RU').includes(search.toLocaleLowerCase('ru-RU')));
  return <div className="work-ledger tool-custody" style={{ '--ledger-bg': C.card || C.bg, '--ledger-text': C.text, '--ledger-border': C.border }}>
    <h3>Инструмент</h3><p>Местонахождение, получатель и история ответственности.</p>
    <div className="ledger-actions"><button onClick={() => setTab('list')} aria-pressed={tab === 'list'}>Список</button><button onClick={() => setTab('history')} aria-pressed={tab === 'history'}>Общая история</button>{canManage && <button className="primary" onClick={() => setEditing(null)}>Добавить инструмент</button>}</div>
    {!selectedCompany && <p>Выберите конкретную компанию, чтобы открыть карточку или оформить движение.</p>}
    {editing !== undefined && canManage && <ToolForm key={editing?.id || 'new'} initial={editing} {...{ API }} companyId={companyContext.selectedCompanyId} onCancel={() => setEditing(undefined)} onSaved={async () => { await refreshData('warehouse'); setEditing(undefined); }} />}
    {tab === 'list' ? <>
      <div className="ledger-grid"><label>Найти инструмент<input type="search" value={search} onChange={e => setSearch(e.target.value)} placeholder="Название, номер, получатель или объект" /></label><label>Архив<select value={showArchive ? 'all' : 'active'} onChange={e => setShowArchive(e.target.value === 'all')}><option value="active">Без архивных</option><option value="all">Включая архивные</option></select></label></div>
      {!visible.length && <p>Инструменты не найдены.</p>}
      {visible.map(tool => <article key={tool.id}>
        <div className="ledger-actions" style={{ justifyContent: 'space-between', marginTop: 0 }}><h4>{tool.name}</h4><b>{tool.status}</b></div>
        <p>Инв. № {tool.inventoryNumber || '—'} · {formatMoney(tool.cost)}<br />{tool.masterName || tool.location || 'Местонахождение не указано'}{tool.project ? ` · ${tool.project}` : ''}</p>
        {tool.notes && <p>{tool.notes}</p>}
        <div className="ledger-actions"><button className="primary" disabled={!selectedCompany} onClick={() => setSelected(tool)}>Операции и ответственность</button>{canManage && <button onClick={() => setEditing(tool)}>Изменить карточку</button>}</div>
      </article>)}
    </> : <section><h4>Последние операции</h4>
      {!toolHistory.length && <p>История пока пуста.</p>}
      {toolHistory.slice(0, 200).map(row => <article key={row.id}><b>{row.action} · {row.toolName}</b><p>{row.date} · {row.createdBy}<br />{row.fromLocation} → {row.toLocation}<br />{row.masterName}{row.project ? ` · ${row.project}` : ''}</p>{row.condition && <p>{row.condition}</p>}</article>)}
    </section>}
    {selected && selectedCompany && <ToolCustodyPanel tool={selected} {...{ API, companyContext, user, C }} onChanged={() => refreshData('warehouse')} onClose={() => setSelected(null)} />}
  </div>;
}

export default function ToolsWorkspace(props) {
  return <Workspace key={`${props.companyContext?.mode}:${props.companyContext?.selectedCompanyId}:${props.user?.id}:${props.user?.role}`} {...props} />;
}
