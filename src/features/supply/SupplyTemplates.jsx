import React, { useState } from 'react';
import { useLedger } from '../work-material-accounting/ledgerUi';
import WorkSubmissionRecovery from '../work-material-accounting/WorkSubmissionRecovery';
import { templateItemsForProject, templatePayload } from './templateItems';
import './supplyTemplates.css';

function Templates({ draft, setDraft, getProjectWorkPackageOptions, disabled, C, ...scope }) {
  const [name, setName] = useState(null);
  const [archive, setArchive] = useState(null);
  const [notice, setNotice] = useState('');
  const { data, error, busy, submit, recovered, reload, setError } = useLedger({
    ...scope, path: '/supply-request-templates/catalog', onRecovered: batch => {
      setError('');
      if (batch.next !== batch.commands.length) return;
      const commands = batch.commands.filter(c => c.path.startsWith('/supply-request-templates'));
      // Preserve drafts edited since the original uncertain submission.
      setName(current => commands.some(c => c.path === '/supply-request-templates'
        && c.payload.name === current?.trim()) ? null : current);
      setArchive(current => current && commands.some(c => c.path === `/supply-request-templates/${current.id}/archive`
        && c.payload.expectedVersion === current.version) ? null : current);
      if (commands.length) setNotice('Изменения шаблонов сохранены.');
    },
  });
  const apply = id => {
    const template = data.items.find(item => String(item.id) === id);
    if (!template) return;
    setDraft(current => ({ ...current, category: template.category || current.category,
      items: templateItemsForProject(template.items, getProjectWorkPackageOptions?.(current.project) || []),
    }));
    setNotice('Материалы из шаблона перенесены в заявку. Проверьте количество и разделы сметы.');
  };
  return <section className="supply-templates" aria-label="Шаблоны заявок">
    <b>Шаблоны вашей компании</b>
    <WorkSubmissionRecovery {...scope} C={C} onRecovered={recovered} />
    {error && <p role="alert">{error}<button type="button" disabled={busy} onClick={() => reload().then(() => setError('')).catch(e => setError(e.message))}>Обновить шаблоны</button></p>}
    {!data && !error && <p role="status">Загрузка шаблонов…</p>}
    {notice && <p role="status">{notice}</p>}
    {data && <fieldset disabled={disabled || busy}>
      <div className="supply-template-actions">
        {data.items.length > 0 ? <label>Готовый набор<select value="" onChange={e => apply(e.target.value)}>
          <option value="">Выберите шаблон</option>
          {data.items.map(item => <option key={item.id} value={item.id}>{item.name} ({item.items.length} поз.)</option>)}
        </select></label> : <span>Пока нет сохранённых шаблонов.</span>}
        {data.canCreate && name === null && <button type="button" onClick={() => { setName(''); setNotice(''); }}>Сохранить как шаблон</button>}
        {data.canArchive && data.items.length > 0 && <label>Архивировать шаблон<select value="" onChange={e => setArchive(data.items.find(item => String(item.id) === e.target.value) || null)}>
          <option value="">Выберите для архива</option>
          {data.items.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select></label>}
      </div>
      {data.truncated && <p>Показаны первые 1000 шаблонов.</p>}
      {name !== null && <div className="supply-template-actions">
        <label>Название шаблона<input maxLength={255} value={name} onChange={e => setName(e.target.value)} /></label>
        <button type="button" onClick={async () => {
          try { await submit('/supply-request-templates', templatePayload(name, draft)); }
          catch (e) { setError(e.message); }
        }}>{busy ? 'Сохранение…' : 'Сохранить набор'}</button>
        <button type="button" onClick={() => setName(null)}>Отменить сохранение шаблона</button>
      </div>}
      {archive && <div>
        <p>Перенести «{archive.name}» в архив? Созданные по нему заявки сохранятся.</p>
        <div className="supply-template-actions">
          <button type="button" onClick={() => submit(`/supply-request-templates/${archive.id}/archive`, { expectedVersion: archive.version })}>Перенести в архив</button>
          <button type="button" onClick={() => setArchive(null)}>Отменить архивирование</button>
        </div>
      </div>}
    </fieldset>}
  </section>;
}

export default function SupplyTemplates(props) {
  const { companyContext, user } = props;
  if (companyContext?.loading || companyContext?.mode !== 'company' || !companyContext?.selectedCompanyId || !user?.id) {
    return <p>Выберите компанию, чтобы работать с шаблонами заявок.</p>;
  }
  return <Templates key={`${companyContext.selectedCompanyId}:${user.id}:${user.role}`} {...props} />;
}
