import React from 'react';

export default function ProjectWeatherTab({
  C,
  card,
  project,
  weatherLog,
}) {
  const rows = (weatherLog || [])
    .filter(row => row.projectName === project.name)
    .slice()
    .sort((a, b) => (b.date || '').localeCompare(a.date || ''));

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
        <b style={{ color: C.text, fontSize: '15px', fontWeight: '700' }}>🌤 Журнал погоды</b>
        <span style={{ fontSize: '11px', color: C.textMuted }}>Метеоусловия по дням строительства</span>
      </div>

      {rows.length === 0 ? (
        <div style={{ ...card, padding: '30px', textAlign: 'center', color: C.textMuted }}>
          Записей о погоде нет. Логируйте погоду из глобального раздела «Погода» — она автоматически появится здесь по этому объекту.
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: '10px' }}>
          {rows.map((row, index) => (
            <div key={index} style={{ ...card, padding: '12px' }}>
              <b style={{ color: C.text, fontSize: '13px' }}>{row.date}</b>
              <p style={{ color: C.textSec, margin: '4px 0 0', fontSize: '12px' }}>
                {(row.condition || '—') + ' · ' + (row.temperature != null ? row.temperature + '°C' : '—') + (row.windSpeed ? ' · ветер ' + row.windSpeed + ' м/с' : '')}
              </p>
              {row.notes && <p style={{ color: C.textMuted, fontSize: '11px', margin: '4px 0 0', fontStyle: 'italic' }}>{row.notes}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
