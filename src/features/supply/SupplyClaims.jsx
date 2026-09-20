import SupplyFileLink from './SupplyFileLink';
import React, { useCallback, useEffect, useState } from 'react';
import { useLedger } from '../work-material-accounting/ledgerUi';
import { pendingWorkBatch, workBatchScope } from '../work-material-accounting/workCommands';
import WorkSubmissionRecovery from '../work-material-accounting/WorkSubmissionRecovery';
import './supplyClaims.css';

const actions = [
  ['start', 'canStart', 'Взять в работу'], ['comment', 'canComment', 'Добавить комментарий'],
  ['reply', 'canReply', 'Ответить на претензию'], ['resolve', 'canResolve', 'Признать урегулированной'],
  ['reopen', 'canReopen', 'Открыть повторно'],
];

function ClaimCard({ claim, ...scope }) {
  const path = `/supply-claims/${claim.id}/case`;
  const [draft, setDraft] = useState({ action: '', text: '', version: null });
  const { data, error, busy, submit, recovered, reload, setError } = useLedger({
    ...scope, path, onRecovered: batch => {
      setError('');
      if (batch.next !== batch.commands.length) return;
      setDraft(current => batch.commands.some(command => command.path === path
        && command.payload.action === current.action && command.payload.text === current.text.trim()
        && command.payload.expectedVersion === current.version)
        ? { action: '', text: '', version: null } : current);
    },
  });
  const available = actions.filter(([, capability]) => data?.[capability]);
  const action = available.some(([value]) => value === draft.action) ? draft.action : available[0]?.[0] || '';
  const change = next => setDraft({ ...draft, action, version: data.claim.version, ...next });
  return <section aria-label={`Претензия ${claim.id}`} className="supply-claim-card">
    <h3>Претензия №{claim.id}</h3>
    <WorkSubmissionRecovery {...scope} onRecovered={recovered} />
    {error && <p role="alert">{error} <button type="button" disabled={busy}
      onClick={() => reload().then(fresh => { if (!pendingWorkBatch(workBatchScope(scope.companyContext, scope.user))) setDraft(current => ({ ...current, version: fresh.claim.version })); setError(''); }).catch(e => setError(e.message))}>Повторить загрузку карточки</button></p>}
    {!data && !error && <p role="status">Загрузка карточки…</p>}
    {data && <>
      <p><b>{data.claim.materialName}</b> · {data.claim.claimType}</p>
      <p>{data.claim.supplierName || 'Поставщик'} · {data.claim.project || 'Объект не указан'}</p>
      <p>{data.claim.status}</p>
      <p>{data.claim.description}</p>
      <SupplyFileLink url={data.claim.photoUrl} fileSrc={url=>scope.API+url}>Скачать фото претензии</SupplyFileLink>
      <p>Ожидалось: {data.claim.expectedQuantity ?? '—'} · Принято: {data.claim.receivedQuantity ?? '—'} · Недостача: {data.claim.shortageQuantity ?? '—'}</p>
      {data.claim.resolution && <p><b>Решение:</b> {data.claim.resolution}</p>}
      <h4>История разбора</h4>
      {data.history.length === 0 && <p>Сообщений пока нет.</p>}
      {data.historyTruncated && <p>Показаны последние 200 записей.</p>}
      <ol>{data.history.map(event => <li key={event.id}>
        <p><b>{event.actorName}</b> · {actions.find(([value]) => value === event.action)?.[2] || event.action}
          {' · '}{new Date(event.createdAt).toLocaleString('ru-RU')}</p>
        <p className="supply-claim-text">{event.text}</p>
      </li>)}</ol>
      {available.length > 0 && <form onSubmit={async event => {
        event.preventDefault();
        const version = draft.version ?? data.claim.version;
        setDraft(current => ({ ...current, action, version }));
        await submit(path, { action, text: draft.text.trim(), expectedVersion: version });
      }}>
        <p>Сообщение увидят участники претензии, включая поставщика.</p>
        <fieldset disabled={busy}>
          <label>Действие<select value={action} onChange={event => change({ action: event.target.value })}>
            {available.map(([value,, label]) => <option key={value} value={value}>{label}</option>)}
          </select></label>
          <label>Сообщение<textarea required maxLength={4000} value={draft.text}
            onChange={event => change({ text: event.target.value })} /></label>
          {action === 'resolve' && <p>Фиксируется результат разбора. Допоставку, возврат или возмещение нужно оформить соответствующим документом.</p>}
          <button type="submit" disabled={busy}>{busy ? 'Сохранение…' : 'Сохранить'}</button>
        </fieldset>
      </form>}
    </>}
  </section>;
}

function Claims({ API, companyContext, user, C, onChanged }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState(null);
  const supplier = user.role === 'поставщик';
  const companyId = companyContext?.selectedCompanyId;
  const reload = useCallback(async signal => {
    const response = await fetch(API + '/supply-claims/cases', { credentials: 'include', signal,
      headers: supplier ? {} : { 'X-Company-Mode': 'company', 'X-Company-Id': String(companyId) } });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || 'Не удалось загрузить претензии');
    setData(result); setError('');
  }, [API, supplier, companyId]);
  useEffect(() => {
    const controller = new AbortController();
    reload(controller.signal).catch(e => { if (e.name !== 'AbortError') setError(e.message); });
    return () => controller.abort();
  }, [reload]);
  return <section className="supply-claims" aria-label="Претензии по поставкам" style={{ color: C?.text }}>
    <h3>Претензии по поставкам</h3>
    {error && <p role="alert">{error} <button type="button" onClick={() => reload().catch(e => setError(e.message))}>Повторить загрузку списка</button></p>}
    {!data && !error && <p role="status">Загрузка претензий…</p>}
    {data && <>
      {data.items.length === 0 && <p>Претензий нет.</p>}
      {data.truncated && <p>Показаны последние 200 претензий.</p>}
      <ul className="supply-claim-list">{data.items.map(claim => <li key={claim.id}>
        <div><b>{claim.materialName}</b><p>{claim.supplierName} · {claim.project} · {claim.status}</p></div>
        <button type="button" aria-label={`Открыть претензию ${claim.id}`} onClick={() => setSelected(claim)}>Открыть №{claim.id}</button>
      </li>)}</ul>
    </>}
    {selected && <ClaimCard key={`${selected.companyId}:${selected.id}`} claim={selected} API={API} user={user} C={C}
      companyContext={{ mode: 'company', selectedCompanyId: selected.companyId }}
      onChanged={async () => { await reload(); await onChanged?.(); }} />}
  </section>;
}

export default function SupplyClaims(props) {
  const { companyContext, user } = props;
  if (!user?.id) return null;
  if (user.role !== 'поставщик' && (companyContext?.loading || companyContext?.mode !== 'company' || !companyContext.selectedCompanyId)) {
    return <p>Выберите компанию для работы с претензиями.</p>;
  }
  return <Claims key={`${user.id}:${user.role}:${companyContext?.mode}:${companyContext?.selectedCompanyId}`} {...props} />;
}
