import React, { useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronUp, FileText } from 'lucide-react';
import { API } from '../../api';

const TYPE_META = {
  receipt: {label: 'Приход', color: '#0f9d75'},
  warehouse_operation: {label: 'Склад', color: '#3274d9'},
  movement: {label: 'Перемещение', color: '#7c5ce0'},
  customer_payment: {label: 'Оплата', color: '#0f9d75'},
  expense: {label: 'Расход', color: '#d15b33'},
  own_expense: {label: 'Трата сотрудника', color: '#c57c00'},
  work: {label: 'Работы', color: '#2860c7'},
};

const dayKey = value => String(value || '').slice(0, 10) || 'Без даты';
const dayLabel = value => {
  const key = dayKey(value);
  const [year, month, day] = key.split('-');
  return year && month && day ? `${day}.${month}.${year}` : key;
};

export default function ProjectEventsPanel({ projectName, C, card, btnG, fileSrc, setShowPhotoModal }) {
  const [events, setEvents] = useState([]);
  const [openId, setOpenId] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [hasMore, setHasMore] = useState(false);

  const load = async ({offset = 0, append = false} = {}) => {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams({project_name: projectName, limit: '100', offset: String(offset)});
      if (dateFrom) params.set('date_from', dateFrom);
      if (dateTo) params.set('date_to', dateTo);
      const response = await fetch(`${API}/project-events?${params.toString()}`);
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || 'Не удалось загрузить события объекта.');
      const rows = Array.isArray(body.items) ? body.items : [];
      setEvents(previous => append ? [...previous, ...rows] : rows);
      setHasMore(Boolean(body.hasMore));
    } catch (loadError) {
      setError(loadError.message || 'Не удалось загрузить события объекта.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [projectName]); // eslint-disable-line react-hooks/exhaustive-deps

  const groups = useMemo(() => {
    const grouped = new Map();
    events.forEach(event => {
      const key = dayKey(event.eventAt || event.documentDate);
      if (!grouped.has(key)) grouped.set(key, []);
      grouped.get(key).push(event);
    });
    return [...grouped.entries()];
  }, [events]);

  const openFile = (url) => {
    const src = typeof fileSrc === 'function' ? fileSrc(url) : url;
    if (/\.(png|jpe?g|webp|gif|heic|heif|bmp)(\?|$)/i.test(String(url || ''))) {
      setShowPhotoModal?.(src);
      return;
    }
    window.open(src, '_blank', 'noopener,noreferrer');
  };

  return <div>
    <div style={{display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12, alignItems: 'center'}}>
      <input type="date" value={dateFrom} onChange={event => setDateFrom(event.target.value)} style={{padding: '8px 10px', borderRadius: 7, border: `1px solid ${C.border}`, background: C.bgWhite, color: C.text}} />
      <input type="date" value={dateTo} onChange={event => setDateTo(event.target.value)} style={{padding: '8px 10px', borderRadius: 7, border: `1px solid ${C.border}`, background: C.bgWhite, color: C.text}} />
      <button onClick={() => load()} style={{...btnG, padding: '8px 12px'}}>Обновить</button>
    </div>
    <p style={{margin: '0 0 12px', color: C.textSec, fontSize: 12}}>
      События показывают исходные операции. Дата документа и время добавления не смешиваются.
    </p>
    {loading && <div style={{...card, padding: 16, color: C.textSec}}>Загружаем события…</div>}
    {error && <div style={{...card, padding: 16, color: C.danger}}>{error}</div>}
    {!loading && !error && groups.length === 0 && <div style={{...card, padding: 16, color: C.textSec}}>За выбранный период событий нет.</div>}
    {!loading && !error && groups.map(([date, rows]) => <section key={date} style={{marginBottom: 14}}>
      <h4 style={{margin: '0 0 8px', color: C.text, fontSize: 15}}>{dayLabel(date)}</h4>
      {rows.map(event => {
        const meta = TYPE_META[event.type] || {label: 'Событие', color: C.accent};
        const isOpen = openId === event.id;
        return <article key={event.id} style={{...card, padding: 13, marginBottom: 8, borderLeft: `4px solid ${meta.color}`}}>
          <button onClick={() => setOpenId(isOpen ? '' : event.id)} style={{background: 'none', color: C.text, border: 0, padding: 0, textAlign: 'left', width: '100%', cursor: 'pointer'}}>
            <div style={{display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'start'}}>
              <div>
                <span style={{fontSize: 11, color: meta.color, fontWeight: 700}}>{meta.label}</span>
                <div style={{fontSize: 14, fontWeight: 700, marginTop: 3}}>{event.title}</div>
                <div style={{fontSize: 12, color: C.textSec, marginTop: 4}}>{event.summary || 'Без комментария'}</div>
              </div>
              <div style={{display: 'flex', alignItems: 'center', gap: 8, whiteSpace: 'nowrap'}}>
                {event.amount ? <b style={{color: event.type === 'expense' || event.type === 'own_expense' ? C.danger : C.success}}>{Number(event.amount).toLocaleString('ru-RU')} ₽</b> : null}
                {isOpen ? <ChevronUp size={17} /> : <ChevronDown size={17} />}
              </div>
            </div>
          </button>
          {isOpen && <div style={{borderTop: `1px solid ${C.border}`, marginTop: 10, paddingTop: 10, fontSize: 12, color: C.textSec}}>
            <div>Добавил: <b style={{color: C.text}}>{event.actor || 'Не указан'}</b></div>
            {event.documentDate && <div style={{marginTop: 4}}>Дата документа: {dayLabel(event.documentDate)}</div>}
            {event.workPackage && <div style={{marginTop: 4}}>Раздел: {event.workPackage}</div>}
            {event.status && <div style={{marginTop: 4}}>Статус: {event.status}</div>}
            {event.note && <div style={{marginTop: 8}}>{event.note}</div>}
            {event.items?.length ? <div style={{marginTop: 10}}>
              <b style={{color: C.text}}>Позиции</b>
              {event.items.slice(0, 8).map((item, index) => <div key={index} style={{marginTop: 4}}>{item.name || 'Материал'} · {item.quantity || 0} {item.unit || ''}</div>)}
              {event.items.length > 8 && <div style={{marginTop: 4}}>И ещё {event.items.length - 8} поз.</div>}
            </div> : null}
            {event.photos?.length ? <div style={{display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 10}}>
              {event.photos.map((url, index) => <button key={`${url}-${index}`} onClick={() => openFile(url)} style={{...btnG, padding: '6px 9px', fontSize: 12}}><FileText size={14} />Открыть файл {index + 1}</button>)}
            </div> : null}
            <div style={{marginTop: 10, color: C.textSec}}>Источник: {event.sourceKind} #{event.sourceId}</div>
          </div>}
        </article>;
      })}
    </section>)}
    {!loading && !error && hasMore && <button onClick={() => load({offset: events.length, append: true})} style={{...btnG, width: '100%', justifyContent: 'center'}}>
      Показать более ранние события
    </button>}
  </div>;
}
