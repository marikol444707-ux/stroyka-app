import React from 'react';
import { Check, ExternalLink, Plus, RefreshCw, Upload, X } from 'lucide-react';

const STATUSES = ['', 'Нужно проверить', 'Подходит', 'Не подходит', 'Дубль'];

const normalizeReportPrice = (value) => {
  const match = String(value || '').match(/[0-9][0-9\s.,]*/)?.[0];
  if (!match) return null;
  let normalized = match.replace(/\s/g, '');
  const comma = normalized.lastIndexOf(',');
  const dot = normalized.lastIndexOf('.');
  const decimalIndex = Math.max(comma, dot);
  const decimalDigits = decimalIndex >= 0 ? normalized.length - decimalIndex - 1 : 0;
  if (decimalIndex >= 0 && decimalDigits > 0 && decimalDigits <= 2) {
    const decimalSeparator = normalized[decimalIndex];
    normalized = normalized.slice(0, decimalIndex).replace(/[.,]/g, '') + '.' + normalized.slice(decimalIndex + 1);
    if (decimalSeparator === '.') normalized = normalized.replace(/\.(?=.*\.)/g, '');
  } else {
    normalized = normalized.replace(/[.,]/g, '');
  }
  return /^\d+(?:\.\d{1,2})?$/.test(normalized) ? normalized : null;
};

export default function OpportunityCandidatesPanel({ API = '', C = {}, compact = false }) {
  const [items, setItems] = React.useState([]);
  const [status, setStatus] = React.useState('Нужно проверить');
  const [searchText, setSearchText] = React.useState('');
  const [sourceFilter, setSourceFilter] = React.useState('');
  const [deadlineFilter, setDeadlineFilter] = React.useState('');
  const [loading, setLoading] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [importing, setImporting] = React.useState(false);
  const [error, setError] = React.useState('');
  const [access, setAccess] = React.useState(null);
  const [accessLoading, setAccessLoading] = React.useState(true);
  const [formOpen, setFormOpen] = React.useState(false);
  const fileInput = React.useRef(null);
  const sources = React.useMemo(() => [...new Set(items.map(item => item.sourceName || item.source).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'ru')), [items]);
  const visibleItems = React.useMemo(() => {
    const query = searchText.trim().toLocaleLowerCase('ru').replace(/ё/g, 'е');
    const queryWords = query.split(/\s+/).filter(Boolean);
    return items.filter(item => {
      const searchable = [item.title, item.description, item.region, item.sourceName, item.source, ...(item.workTypes || [])]
        .filter(Boolean).join(' ').toLocaleLowerCase('ru').replace(/ё/g, 'е');
      const searchableWords = searchable.match(/[а-яa-z0-9-]+/gi) || [];
      if (queryWords.length && !queryWords.every(word => {
        const prefix = word.slice(0, Math.max(4, word.length - 2));
        return searchableWords.some(value => value.startsWith(prefix));
      })) return false;
      if (sourceFilter && (item.sourceName || item.source) !== sourceFilter) return false;
      if (deadlineFilter) {
        const deadline = item.deadline ? Date.parse(item.deadline) : NaN;
        const expired = Number.isFinite(deadline) && deadline < Date.now();
        if (deadlineFilter === 'expired' && !expired) return false;
        if (deadlineFilter === 'active' && (!Number.isFinite(deadline) || expired)) return false;
        if (deadlineFilter === 'unknown' && Number.isFinite(deadline)) return false;
      }
      return true;
    });
  }, [items, searchText, sourceFilter, deadlineFilter]);
  const [draft, setDraft] = React.useState({ title: '', url: '', region: 'Ставропольский край', workType: '', description: '', evidence: '', price: '', deadline: '' });

  React.useEffect(() => {
    let active = true;
    fetch(`${API}/crm/job-candidates/access`)
      .then(async response => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || 'Не удалось проверить подключение JEV');
        return data;
      })
      .then(data => { if (active) setAccess(data); })
      .catch(loadError => { if (active) setError(loadError.message || 'Не удалось проверить подключение JEV'); })
      .finally(() => { if (active) setAccessLoading(false); });
    return () => { active = false; };
  }, [API]);

  const load = React.useCallback(async () => {
    if (access?.enabled !== true) return;
    setLoading(true);
    setError('');
    try {
      const query = status ? `?status=${encodeURIComponent(status)}` : '';
      const response = await fetch(`${API}/crm/job-candidates${query}`);
      const data = await response.json().catch(() => []);
      if (!response.ok) throw new Error(data.detail || 'Не удалось загрузить находки');
      setItems(Array.isArray(data) ? data : []);
    } catch (loadError) {
      setError(loadError.message || 'Не удалось загрузить находки');
    } finally {
      setLoading(false);
    }
  }, [API, access?.enabled, status]);

  React.useEffect(() => { if (access?.enabled) load(); }, [access?.enabled, load]);

  const addCandidate = async (event) => {
    event.preventDefault();
    if (!draft.title.trim() || !draft.url.trim()) return;
    setSaving(true);
    setError('');
    try {
      const response = await fetch(`${API}/crm/job-candidates`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source: 'manual',
          title: draft.title,
          url: draft.url,
          region: draft.region,
          workTypes: draft.workType ? [draft.workType] : [],
          description: draft.description,
          evidence: draft.evidence,
          price: draft.price || null,
          deadline: draft.deadline || null,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'Не удалось сохранить находку');
      setDraft({ title: '', url: '', region: 'Ставропольский край', workType: '', description: '', evidence: '', price: '', deadline: '' });
      setFormOpen(false);
      await load();
    } catch (saveError) {
      setError(saveError.message || 'Не удалось сохранить находку');
    } finally {
      setSaving(false);
    }
  };

  const review = async (item, nextStatus) => {
    setError('');
    try {
      const response = await fetch(`${API}/crm/job-candidates/${item.id}/review`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: nextStatus }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'Не удалось сохранить решение');
      await load();
    } catch (reviewError) {
      setError(reviewError.message || 'Не удалось сохранить решение');
    }
  };

  const importReport = async (file) => {
    if (!file) return;
    setImporting(true);
    setError('');
    try {
      const report = JSON.parse(await file.text());
      const rows = [...(Array.isArray(report.confirmed) ? report.confirmed : []), ...(Array.isArray(report.review) ? report.review : []), ...(Array.isArray(report.government_review) ? report.government_review : [])];
      const items = rows.slice(0, 200).map(row => {
        const provider = String(row.provider || row.source || '').trim();
        const sourceId = String(row.id || row.procedure_record_id || '').trim();
        const amount = normalizeReportPrice(row.price);
        const deadline = String(row.deadline_msk || '').trim();
        const deadlineIso = /^\d{4}-\d\d-\d\dT/.test(deadline) ? deadline : '';
        const details = [row.organizer && `Заказчик: ${row.organizer}`, row.procedure_type && `Тип: ${row.procedure_type}`, row.status && `Статус источника: ${row.status}`, row.place && `Место: ${row.place}`, row.regime && `Режим: ${row.regime}`].filter(Boolean).join('\n');
        return {
          source: 'browser_agent',
          sourceName: provider,
          sourceItemId: sourceId ? `${provider}:${sourceId}` : '',
          url: row.url,
          title: row.title,
          description: details,
          region: row.region || (['not_filtered', 'unknown'].includes(row.region_scope) ? '' : report.region || ''),
          workTypes: ['Строительство / ремонт'],
          price: amount,
          deadline: deadlineIso || null,
          evidence: `${row.regime ? `Режим закупки: ${row.regime}. ` : ''}JEV: предварительная проверка; сверить карточку источника. ${Array.isArray(row.reasons) ? row.reasons.join(', ') : ''}`.trim(),
        };
      }).filter(item => item.title && item.url && item.sourceName);
      if (!items.length) throw new Error('В отчёте нет пригодных находок в разделах confirmed, review и government_review');
      if (rows.length > 200) throw new Error('В отчёте больше 200 находок. Импортируйте меньшую часть отчёта');
      const response = await fetch(`${API}/crm/job-candidates/import-report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail || 'Не удалось импортировать отчёт');
      await load();
      const failedSources = Array.isArray(report.sources) ? report.sources.filter(source => source && source.ok === false) : [];
      const partialNote = failedSources.length
        ? `\nИсточники с ошибкой: ${failedSources.map(source => source.provider || source.query || 'неизвестный источник').join(', ')}.`
        : '';
      alert(`Импорт завершён: новых ${result.created}, обновлено ${result.updated}.${partialNote}`);
    } catch (importError) {
      setError(importError.message || 'Не удалось прочитать отчёт JEV');
    } finally {
      setImporting(false);
      if (fileInput.current) fileInput.current.value = '';
    }
  };

  const panelStyle = {
    ...((C.card || {})),
    background: C.bgWhite || C.surface || '#fff',
    border: `1px solid ${C.border || '#d0d5dd'}`,
    borderRadius: 12,
    padding: compact ? 12 : 16,
    marginBottom: 18,
    minWidth: 0,
  };
  const buttonStyle = {
    border: `1px solid ${C.border || '#d0d5dd'}`,
    borderRadius: 8,
    minHeight: 38,
    padding: '7px 10px',
    background: C.bg || '#fff',
    color: C.text || '#101828',
    cursor: 'pointer',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
  };
  const inputStyle = {
    width: '100%',
    minWidth: 0,
    boxSizing: 'border-box',
    border: `1px solid ${C.border || '#d0d5dd'}`,
    borderRadius: 8,
    padding: '10px 11px',
    color: C.text || '#101828',
    background: C.bg || '#fff',
    font: 'inherit',
  };

  if (accessLoading) {
    return <section aria-label="Кандидаты заказов" aria-busy="true" style={panelStyle}>Проверяю доступ к поиску заказов…</section>;
  }
  if (access && !access.enabled) {
    return (
      <section aria-label="Кандидаты заказов" style={panelStyle}>
        <h3 style={{ margin: 0, color: C.text || '#101828', fontSize: compact ? 15 : 17 }}>Поиск коммерческих заказов JEV</h3>
        <p style={{ margin: '6px 0 0', color: C.textSec || '#667085' }}>
          Эта функция пока не подключена вашей организации. Запросите подключение у администратора платформы.
        </p>
      </section>
    );
  }
  if (!access) {
    return (
      <section aria-label="Кандидаты заказов" style={panelStyle}>
        <h3 style={{ margin: 0, color: C.text || '#101828', fontSize: compact ? 15 : 17 }}>Поиск коммерческих заказов JEV</h3>
        <p role="alert" style={{ color: C.danger || '#b42318', margin: '6px 0 0' }}>
          {error || 'Не удалось проверить подключение. Обновите страницу или обратитесь к администратору платформы.'}
        </p>
      </section>
    );
  }

  return (
    <section aria-label="Кандидаты заказов" style={panelStyle}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' }}>
        <div>
          <h3 style={{ margin: 0, color: C.text || '#101828', fontSize: compact ? 15 : 17 }}>Кандидаты заказов</h3>
          <p style={{ margin: '4px 0 0', color: C.textSec || '#667085', fontSize: 12 }}>Найденные закупки и объекты. Решение остаётся за вами.</p>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button type="button" onClick={() => load()} disabled={loading} style={buttonStyle}><RefreshCw size={14} />Обновить</button>
          <button type="button" onClick={() => fileInput.current?.click()} disabled={importing} style={buttonStyle}><Upload size={14} />{importing ? 'Импортирую…' : 'Импорт отчёта JEV'}</button>
          <button type="button" onClick={() => setFormOpen(value => !value)} style={{ ...buttonStyle, background: C.accent || '#f97316', color: '#fff', borderColor: C.accent || '#f97316' }}><Plus size={14} />Добавить находку</button>
          <input ref={fileInput} type="file" accept="application/json,.json" aria-label="Файл отчёта JEV" style={{ display: 'none' }} onChange={event => importReport(event.target.files?.[0])} />
        </div>
      </div>

      {formOpen && (
        <form onSubmit={addCandidate} style={{ display: 'grid', gridTemplateColumns: compact ? '1fr' : 'repeat(2, minmax(0, 1fr))', gap: 9, marginTop: 14, padding: 12, borderRadius: 10, background: C.bg || '#f9fafb' }}>
          <input aria-label="Название заказа" placeholder="Название заказа *" required maxLength={500} value={draft.title} onChange={event => setDraft({ ...draft, title: event.target.value })} style={inputStyle} />
          <input aria-label="Ссылка на источник" placeholder="Ссылка на источник *" type="url" required value={draft.url} onChange={event => setDraft({ ...draft, url: event.target.value })} style={inputStyle} />
          <input aria-label="Регион" placeholder="Регион" value={draft.region} onChange={event => setDraft({ ...draft, region: event.target.value })} style={inputStyle} />
          <input aria-label="Вид работ" placeholder="Вид работ" value={draft.workType} onChange={event => setDraft({ ...draft, workType: event.target.value })} style={inputStyle} />
          <input aria-label="Бюджет" placeholder="Бюджет, ₽" type="number" min="0" step="0.01" value={draft.price} onChange={event => setDraft({ ...draft, price: event.target.value })} style={inputStyle} />
          <input aria-label="Срок подачи" type="date" value={draft.deadline} onChange={event => setDraft({ ...draft, deadline: event.target.value ? `${event.target.value}T23:59:59` : '' })} style={inputStyle} />
          <textarea aria-label="Описание" placeholder="Краткое описание заказа" value={draft.description} onChange={event => setDraft({ ...draft, description: event.target.value })} style={{ ...inputStyle, minHeight: 68, resize: 'vertical' }} />
          <textarea aria-label="Фрагмент источника" placeholder="Фрагмент страницы или примечание для проверки" value={draft.evidence} onChange={event => setDraft({ ...draft, evidence: event.target.value })} style={{ ...inputStyle, minHeight: 68, resize: 'vertical' }} />
          <div style={{ display: 'flex', gap: 8, gridColumn: compact ? 'auto' : '1 / -1' }}>
            <button type="submit" disabled={saving} style={{ ...buttonStyle, background: C.accent || '#f97316', color: '#fff' }}><Check size={14} />{saving ? 'Сохраняю…' : 'Сохранить'}</button>
            <button type="button" onClick={() => setFormOpen(false)} style={buttonStyle}><X size={14} />Отмена</button>
          </div>
        </form>
      )}

      <div aria-label="Фильтры находок" style={{ display: 'grid', gridTemplateColumns: compact ? '1fr' : 'minmax(0, 2fr) repeat(2, minmax(0, 1fr))', gap: 8, marginTop: 14 }}>
        <input
          type="search"
          aria-label="Поиск по находкам"
          placeholder="Поиск по названию, заказчику, региону"
          value={searchText}
          onChange={event => setSearchText(event.target.value)}
          style={inputStyle}
        />
        <select aria-label="Площадка" value={sourceFilter} onChange={event => setSourceFilter(event.target.value)} style={inputStyle}>
          <option value="">Все площадки</option>
          {sources.map(source => <option key={source} value={source}>{source}</option>)}
        </select>
        <select aria-label="Срок подачи" value={deadlineFilter} onChange={event => setDeadlineFilter(event.target.value)} style={inputStyle}>
          <option value="">Любой срок</option>
          <option value="active">Срок не истёк</option>
          <option value="expired">Срок истёк</option>
          <option value="unknown">Срок не указан</option>
        </select>
      </div>

      <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap', marginTop: 10 }}>
        {STATUSES.map(value => (
          <button key={value || 'all'} type="button" onClick={() => setStatus(value)} aria-pressed={status === value} style={{ ...buttonStyle, minHeight: 34, fontSize: 12, background: status === value ? (C.accentLight || '#fff7ed') : buttonStyle.background, borderColor: status === value ? (C.accent || '#f97316') : buttonStyle.border }}>
            {value || 'Все'}
          </button>
        ))}
      </div>

      {error && <p role="alert" style={{ color: C.danger || '#b42318', margin: '12px 0 0' }}>{error}</p>}
      {loading ? <p style={{ color: C.textSec || '#667085' }}>Загружаю…</p> : items.length === 0 ? <p style={{ color: C.textSec || '#667085', margin: '14px 0 0' }}>В этой подборке пока нет находок.</p> : visibleItems.length === 0 ? <p role="status" style={{ color: C.textSec || '#667085', margin: '14px 0 0' }}>По этим фильтрам находок нет.</p> : (
        <div style={{ display: 'grid', gap: 9, marginTop: 12 }}>
          {visibleItems.map(item => (
            <article key={item.id} style={{ border: `1px solid ${C.border || '#d0d5dd'}`, borderRadius: 9, padding: compact ? 10 : 12, minWidth: 0 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
                <b style={{ color: C.text || '#101828', overflowWrap: 'anywhere' }}>{item.title}</b>
                <span style={{ color: C.textSec || '#667085', fontSize: 12 }}>{item.status}</span>
              </div>
              <div style={{ color: C.textSec || '#667085', fontSize: 12, marginTop: 5, overflowWrap: 'anywhere' }}>
                {[item.region, ...(item.workTypes || []), item.price ? `${Number(item.price).toLocaleString('ru-RU')} ₽` : '', item.deadline ? `до ${String(item.deadline).slice(0, 10)}` : '', item.sourceName || item.source].filter(Boolean).join(' · ')}
              </div>
              {item.description && <p style={{ color: C.text || '#344054', margin: '7px 0 0', whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{item.description}</p>}
              {item.evidence && <p style={{ color: C.textSec || '#667085', margin: '6px 0 0', fontSize: 12, whiteSpace: 'pre-wrap' }}>Заметка проверки: {item.evidence}</p>}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7, marginTop: 9 }}>
                <a href={item.url} target="_blank" rel="noreferrer" style={{ ...buttonStyle, textDecoration: 'none' }}><ExternalLink size={13} />Открыть источник</a>
                {item.status !== 'Подходит' && <button type="button" onClick={() => review(item, 'Подходит')} style={buttonStyle}><Check size={13} />Подходит</button>}
                {item.status !== 'Не подходит' && <button type="button" onClick={() => review(item, 'Не подходит')} style={buttonStyle}><X size={13} />Не подходит</button>}
                {item.status !== 'Дубль' && <button type="button" onClick={() => review(item, 'Дубль')} style={buttonStyle}>Дубль</button>}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
