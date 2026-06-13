import React from 'react';

const wordRecord = (count) => {
  const n = Math.abs(Number(count || 0));
  const last = n % 10;
  const last2 = n % 100;
  if (last === 1 && last2 !== 11) return 'запись';
  if (last >= 2 && last <= 4 && (last2 < 12 || last2 > 14)) return 'записи';
  return 'записей';
};

export default function ProjectObjectLinksPanel({
  C,
  card,
  items = [],
  isMobile,
  onOpen,
}) {
  if (!items.length) return null;

  return (
    <div style={{...card, padding: '16px', marginBottom: '12px', backgroundColor: C.bgWhite, border: '1.5px solid ' + C.border}}>
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', flexWrap: 'wrap', marginBottom: '12px'}}>
        <div>
          <b style={{display: 'block', color: C.text, fontSize: '15px'}}>🧭 Связи объекта</b>
          <p style={{margin: '4px 0 0', color: C.textSec, fontSize: '12px', lineHeight: 1.4}}>
            Быстрый контроль: сметы, обмеры, журналы, материалы, документы и поручения.
          </p>
        </div>
      </div>

      <div style={{display: 'grid', gridTemplateColumns: isMobile ? '1fr 1fr' : 'repeat(auto-fit,minmax(180px,1fr))', gap: '10px'}}>
        {items.map((item) => {
          const toneColor = item.color || C.accent;
          const toneBg = item.bg || C.bg;
          const toneBorder = item.border || C.border;
          return (
            <button
              key={item.key || item.tab || item.label}
              type="button"
              onClick={() => onOpen && onOpen(item.tab)}
              style={{
                ...card,
                padding: '12px',
                textAlign: 'left',
                backgroundColor: toneBg,
                border: '1.5px solid ' + toneBorder,
                cursor: item.tab ? 'pointer' : 'default',
                minWidth: 0,
              }}
            >
              <div style={{display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'flex-start', marginBottom: '6px'}}>
                <span style={{display: 'flex', alignItems: 'center', gap: '7px', minWidth: 0}}>
                  <span style={{fontSize: '18px', lineHeight: 1}}>{item.icon}</span>
                  <b style={{color: C.text, fontSize: '12px', lineHeight: 1.25, overflow: 'hidden', textOverflow: 'ellipsis'}}>{item.label}</b>
                </span>
                <b style={{color: toneColor, fontSize: '16px', lineHeight: 1}}>{item.count}</b>
              </div>
              <p style={{margin: 0, color: C.textMuted, fontSize: '10px', lineHeight: 1.35}}>
                {item.hint || `${item.count} ${wordRecord(item.count)}`}
              </p>
              {item.status ? (
                <p style={{margin: '7px 0 0', color: toneColor, fontSize: '10px', fontWeight: 700, lineHeight: 1.3}}>
                  {item.status}
                </p>
              ) : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}
