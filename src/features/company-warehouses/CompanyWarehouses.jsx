import React, { useState } from 'react';
import { useLedger } from '../work-material-accounting/ledgerUi';
import WorkSubmissionRecovery from '../work-material-accounting/WorkSubmissionRecovery';
import '../work-material-accounting/ledger.css';
import './warehouses.css';

const emptyCard = { name: '', city: '', address: '', notes: '' };
const fieldLabels = { name: 'Название склада', city: 'Город', address: 'Адрес', notes: 'Заметки' };
const eventLabels = { create: 'Создана карточка', update: 'Изменена карточка', archive: 'Перенесено в архив', restore: 'Восстановлено', assign_owner: 'Подтверждена компания' };

function History({ warehouseId, onClose, ...props }) {
  const { data, error, reload, setError } = useLedger({ ...props, path: `/warehouses/${warehouseId}/directory` });
  return <section aria-label="История склада" className="warehouse-directory-history">
    <div className="ledger-actions"><h4>История склада</h4><button onClick={onClose}>Закрыть историю</button></div>
    {error && <p role="alert">{error}<button onClick={() => reload().then(() => setError('')).catch(e => setError(e.message))}>Повторить загрузку истории</button></p>}
    {!data && !error && <p role="status">Загрузка истории…</p>}
    {data?.history.map(event => <article key={event.id}>
      <b>{eventLabels[event.action]}</b><p>{event.actorName} · {new Date(event.createdAt).toLocaleString('ru-RU')}</p>
      {event.reason && <p>{event.reason}</p>}
      <dl>{Object.entries(fieldLabels).filter(([key]) => !event.before || event.before[key] !== event.after[key]).map(([key, label]) =>
        <React.Fragment key={key}><dt>{label}</dt><dd>{event.before ? `${event.before[key] || '—'} → ` : ''}{event.after[key] || '—'}</dd></React.Fragment>)}</dl>
    </article>)}
    {data && !data.history.length && <p>Карточка создана до введения истории изменений.</p>}
    {data?.historyTruncated && <p>Показаны последние 200 изменений.</p>}
  </section>;
}

function Directory(props) {
  const [form, setForm] = useState(null);
  const [decision, setDecision] = useState(null);
  const [history, setHistory] = useState(null);
  const [archived, setArchived] = useState(false);
  const { data, error, busy, submit, recovered, reload, setError } = useLedger({ ...props, path: '/warehouses/directory', onRecovered: batch => {
    setError('');
    if (batch.next !== batch.commands.length) return;
    // Recovery is shared with other modules; only clear the draft actually sent.
    const commands = batch.commands.filter(c => /^\/warehouses(?:\/[1-9][0-9]*)?\/directory$/.test(c.path));
    setForm(current => current && commands.some(c => c.path === (current.id ? `/warehouses/${current.id}/directory` : '/warehouses/directory')
      && c.payload.action === (current.id ? 'update' : 'create')
      && (!current.id || c.payload.expectedVersion === current.version)
      && Object.keys(emptyCard).every(key => c.payload[key] === (current[key] || ''))) ? null : current);
    setDecision(current => current && commands.some(c => c.path === `/warehouses/${current.card.id}/directory`
      && c.payload.action === current.action && c.payload.expectedVersion === current.card.version
      && c.payload.reason === current.reason) ? null : current);
    setHistory(current => commands.some(c => c.path === `/warehouses/${current}/directory`) ? null : current);
  } });
  const edit = card => { setForm(card ? { ...card } : { ...emptyCard }); setDecision(null); setHistory(null); setError(''); };
  const decide = (card, action) => { setDecision({ card, action, reason: '' }); setForm(null); setHistory(null); setError(''); };
  const refresh = () => reload().then(() => setError('')).catch(e => setError(e.message));
  const rows = (data?.items || []).filter(card => card.archived === archived);
  return <>
    <div className="ledger-actions"><h3>Склады компании</h3>{data?.canManage && <button disabled={busy} onClick={() => edit(null)}>Добавить склад</button>}</div>
    <p>Адреса и сведения о складах. Остатки материалов доступны во вкладках «Основной склад» и «Объекты».</p>
    <WorkSubmissionRecovery {...props} onRecovered={recovered} />
    {error && <div role="alert">{error}<button disabled={busy} onClick={refresh}>Обновить каталог</button></div>}
    {!data && !error && <p role="status">Загрузка складов…</p>}
    {form && <form onSubmit={e => {
      e.preventDefault();
      const fields = Object.fromEntries(Object.keys(emptyCard).map(key => [key, form[key] || '']));
      submit(form.id ? `/warehouses/${form.id}/directory` : '/warehouses/directory', {
        action: form.id ? 'update' : 'create', ...fields, ...(form.id ? { expectedVersion: form.version } : {}),
      });
    }}>
      <fieldset disabled={busy} className="warehouse-directory-form"><legend>{form.id ? 'Изменение карточки' : 'Новый склад'}</legend>
        {Object.entries(fieldLabels).map(([key, label]) => <label key={key}>{label}
          {key === 'notes' ? <textarea maxLength={4000} value={form[key] || ''} onChange={e => setForm({ ...form, [key]: e.target.value })} />
            : <input required={key === 'name'} maxLength={key === 'address' ? 2000 : 255} value={form[key] || ''} onChange={e => setForm({ ...form, [key]: e.target.value })} />}
        </label>)}
        <div className="ledger-actions"><button className="primary" disabled={!form.name.trim()}>Сохранить карточку</button><button type="button" onClick={() => setForm(null)}>Отмена</button></div>
      </fieldset>
    </form>}
    {decision && <fieldset disabled={busy} className="warehouse-directory-form"><legend>{decision.action === 'archive' ? 'В архив' : 'Восстановить'}: {decision.card.name}</legend>
      <p>Карточка и история сохраняются. Архивирование карточки не изменяет остатки материалов.</p>
      <label>Основание<textarea maxLength={2000} value={decision.reason} onChange={e => setDecision({ ...decision, reason: e.target.value })} /></label>
      <div className="ledger-actions"><button className="primary" disabled={!decision.reason.trim()} onClick={() => submit(`/warehouses/${decision.card.id}/directory`, {
        action: decision.action, expectedVersion: decision.card.version, reason: decision.reason,
      })}>{decision.action === 'archive' ? 'Подтвердить архивирование' : 'Подтвердить восстановление'}</button><button onClick={() => setDecision(null)}>Отмена</button></div>
    </fieldset>}
    <div className="ledger-actions" aria-label="Состояние складов"><button aria-pressed={!archived} onClick={() => setArchived(false)}>Действующие ({data?.items.filter(c => !c.archived).length || 0})</button><button aria-pressed={archived} onClick={() => setArchived(true)}>Архив ({data?.items.filter(c => c.archived).length || 0})</button></div>
    {rows.map(card => <article key={card.id} className="warehouse-directory-row"><div><h4>{card.name}</h4><p>{[card.city, card.address].filter(Boolean).join(', ') || 'Адрес пока не указан'}</p>{card.notes && <p className="warehouse-directory-notes">{card.notes}</p>}</div>
      <div className="ledger-actions">
        <button disabled={busy} aria-label={`История ${card.name}`} onClick={() => setHistory(card.id)}>История</button>
        {data.canManage && !card.archived && <button disabled={busy} aria-label={`Изменить ${card.name}`} onClick={() => edit(card)}>Изменить</button>}
        {data.canArchive && <button disabled={busy} aria-label={`${card.archived ? 'Восстановить' : 'В архив'} ${card.name}`} onClick={() => decide(card, card.archived ? 'restore' : 'archive')}>{card.archived ? 'Восстановить' : 'В архив'}</button>}
      </div>
    </article>)}
    {data && !rows.length && <p>{archived ? 'Архивных карточек нет.' : 'Действующих карточек пока нет. Добавьте склад вашей компании.'}</p>}
    {data?.truncated && <p>Показаны первые 1000 карточек.</p>}
    {history && <History key={history} {...props} warehouseId={history} onClose={() => setHistory(null)} />}
  </>;
}

export default function CompanyWarehouses(props) {
  if (props.companyContext?.mode !== 'company' || !props.companyContext.selectedCompanyId) return <p>Для каталога складов выберите конкретную компанию.</p>;
  return <section className="work-ledger warehouse-directory" style={{ '--ledger-bg': props.C?.card || props.C?.bg, '--ledger-text': props.C?.text, '--ledger-border': props.C?.border }}>
    <Directory key={`${props.companyContext.selectedCompanyId}:${props.user?.id}:${props.user?.role}`} {...props} />
  </section>;
}
