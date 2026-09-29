import React, { useEffect, useRef, useState } from 'react';
import { aliasMembershipKey, aliasScopeKey, deactivateOwnedAlias, loadAliasPage, saveOwnedAlias } from './ownedAliases';
import './ownedAliases.css';

const emptyDraft = () => ({aliasName: '', canonicalName: '', canonicalUnit: '', expectedAliasId: null});
const writeRoles = ['директор', 'зам_директора', 'прораб', 'главный_инженер', 'сметчик', 'снабженец', 'кладовщик'];

export default function OwnedAliasEditor({API, project, companyContext, invalidateOwnedAliases, reloadOwnedAliases, C = {}}) {
  const selected = companyContext?.selectedCompany;
  const membershipKey = aliasMembershipKey(companyContext);
  const allowed = !!membershipKey && Number(selected?.companyId) === Number(project?.companyId);
  const canWrite = allowed && !selected.readOnly && writeRoles.includes(selected?.role);
  const [scope, setScope] = useState('project');
  const owner = {companyId: Number(project?.companyId), projectId: scope === 'project' ? Number(project?.id || project?.projectId) : null};
  const scopeKey = aliasScopeKey(owner) + ':' + (allowed ? membershipKey : 'denied');
  const [page, setPage] = useState({key: '', rows: [], offset: 0, loading: true});
  const [draft, setDraft] = useState(emptyDraft);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(null);
  const current = useRef(scopeKey);
  current.current = scopeKey;
  const sequence = useRef(0);
  const mounted = useRef(true);
  const writing = useRef(false);
  const limit = 25;

  async function reload(offset = 0) {
    const ticket = ++sequence.current;
    const key = scopeKey;
    setPage(previous => ({...previous, loading: true}));
    try {
      const rows = await loadAliasPage(API, owner, {limit, offset});
      if (mounted.current && ticket === sequence.current && current.current === key) setPage({key, rows, offset, loading: false});
    } catch (err) {
      if (mounted.current && ticket === sequence.current && current.current === key) {
        setPage({key, rows: [], offset, loading: false});
        setError(err.message);
      }
    }
  }

  useEffect(() => {
    mounted.current = true;
    setDraft(emptyDraft()); setError(''); setNotice(''); setConfirm(null); setBusy(false);
    if (allowed) reload();
    return () => { mounted.current = false; sequence.current += 1; };
    // Scope changes invalidate every outstanding response and draft.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [API, scopeKey]);

  async function mutate(operation) {
    if (!canWrite || writing.current || page.key !== scopeKey) return;
    writing.current = true; setBusy(true); setError(''); setNotice('');
    const key = scopeKey;
    const release = invalidateOwnedAliases?.();
    try {
      await operation();
      if (!mounted.current || current.current !== key) return;
      setDraft(emptyDraft()); setConfirm(null); setNotice('Изменения сохранены');
      await reload(page.offset);
    } catch (err) {
      if (mounted.current && current.current === key) {
        setError(err.status === 409 ? 'Соответствие уже изменено. Черновик сохранён. Обновите список и выберите актуальную запись для редактирования.' : err.message);
      }
    } finally {
      release?.();
      await reloadOwnedAliases?.();
      writing.current = false;
      if (mounted.current && current.current === key) setBusy(false);
    }
  }

  if (!allowed) return <section className="owned-aliases"><h3>Соответствия материалов</h3><p role="status">Выберите компанию объекта в верхнем переключателе компаний.</p></section>;
  const loading = page.loading || page.key !== scopeKey;
  const rows = page.key === scopeKey ? page.rows : [];
  return <section className="owned-aliases" aria-label="Справочник соответствий материалов" style={{
    '--alias-text': C.text, '--alias-muted': C.textSec, '--alias-border': C.border,
    '--alias-surface': C.bgCard || C.bg, '--alias-accent': C.accent,
  }}>
    <h3>Соответствия материалов</h3>
    <p>Компания: <strong>{selected.companyName || selected.name || `№ ${owner.companyId}`}</strong> · объект: {project.name || project.projectName} (№ {project.id || project.projectId})</p>
    <p className="alias-help">Название из накладной → название в смете. Исходные строки документов сохраняются. Это соответствие названий, не пересчёт единиц.</p>
    <div className="alias-toolbar">
      <label>Область действия<select value={scope} disabled={busy} onChange={event => setScope(event.target.value)}>
        <option value="project">Только этот объект</option><option value="company">Вся компания</option>
      </select></label>
      <button type="button" disabled={loading || busy} onClick={() => {setError(''); reload(page.offset);}}>Обновить список</button>
    </div>
    {error && <p role="alert" className="alias-error">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    {!canWrite && <p role="status">Доступен только просмотр. Право изменения определяется ролью в выбранной компании.</p>}
    {canWrite && <form onSubmit={event => {event.preventDefault(); mutate(() => saveOwnedAlias(API, {...owner, ...draft}));}}>
      <fieldset disabled={busy || loading}>
        <legend>{draft.expectedAliasId ? `Новая версия ${draft.expectedAliasId}` : 'Новое соответствие'}</legend>
        <div className="alias-fields">
          <label>Название поставщика<input required maxLength={500} readOnly={!!draft.expectedAliasId} value={draft.aliasName} onChange={event => setDraft({...draft, aliasName: event.target.value})}/></label>
          <label>Название в смете<input required maxLength={500} value={draft.canonicalName} onChange={event => setDraft({...draft, canonicalName: event.target.value})}/></label>
          <label>Единица<input maxLength={50} value={draft.canonicalUnit} onChange={event => setDraft({...draft, canonicalUnit: event.target.value})}/></label>
        </div>
        <div className="alias-toolbar"><button type="submit">{busy ? 'Сохраняем…' : 'Сохранить соответствие'}</button>
          <button type="button" onClick={() => {setDraft(emptyDraft()); setError('');}}>Сбросить черновик</button></div>
      </fieldset>
    </form>}
    {confirm && <div role="alert" className="alias-confirm"><p>Отключить «{confirm.aliasName}»? История и документы сохранятся.</p>
      <button type="button" disabled={busy} onClick={() => mutate(() => deactivateOwnedAlias(API, owner, confirm.id))}>Подтвердить отключение</button>
      <button type="button" disabled={busy} onClick={() => setConfirm(null)}>Отмена</button></div>}
    {loading ? <p role="status">Загружаем соответствия…</p> : !rows.length ? <p role="status">В этой области соответствий пока нет.</p> :
      <div className="alias-table-scroll"><table><caption>Активные соответствия; объектные имеют приоритет над общими</caption><thead><tr><th>Поставщик → смета</th><th>Область / версия</th><th>Автор / время</th><th>Действия</th></tr></thead><tbody>
        {rows.map(row => <tr key={row.id}><td>{row.aliasName}<br/><strong>→ {row.canonicalName}</strong> {row.canonicalUnit}</td>
          <td>{row.projectId === null ? 'Вся компания' : 'Этот объект'}<br/>{row.id}</td>
          <td>Сотрудник № {row.createdById}<br/>{row.createdAt ? new Date(row.createdAt).toLocaleString('ru-RU') : '—'}</td>
          <td>{canWrite && row.projectId === owner.projectId ? <div className="alias-toolbar">
            <button type="button" disabled={busy} onClick={() => {setDraft({aliasName: row.aliasName, canonicalName: row.canonicalName, canonicalUnit: row.canonicalUnit, expectedAliasId: row.id}); setError(''); setNotice('');}}>Изменить</button>
            <button type="button" disabled={busy} onClick={() => setConfirm(row)}>Отключить</button></div> : row.projectId === null && scope === 'project' ? 'Изменение: область «Вся компания»' : 'Просмотр'}</td></tr>)}
      </tbody></table></div>}
    <div className="alias-toolbar"><button type="button" disabled={loading || busy || page.offset === 0} onClick={() => reload(Math.max(0, page.offset-limit))}>Назад</button>
      <span>Страница {Math.floor(page.offset/limit)+1}</span><button type="button" disabled={loading || busy || rows.length < limit} onClick={() => reload(page.offset+limit)}>Далее</button></div>
  </section>;
}
