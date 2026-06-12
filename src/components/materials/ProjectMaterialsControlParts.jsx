import React from 'react';
import { Printer } from 'lucide-react';

export const MetricCard = ({C, label, value, active, color, bg, border}) => (
  <div style={{
    padding: '10px',
    backgroundColor: active ? bg : C.bg,
    borderRadius: '8px',
    border: '1px solid ' + (active ? border : C.border)
  }}>
    <p style={{
      color: active ? color : C.textSec,
      fontSize: '10px',
      margin: '0 0 3px'
    }}>{label}</p>
    <b style={{
      color: active ? color : C.text,
      fontSize: '15px'
    }}>{value}</b>
  </div>
);

export function MaterialsControlHeader({projectName, C, btnB, showPreview, buildMaterialRequirementContent}) {
  return (
    <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginBottom: '12px'}}>
      <div>
        <b style={{color: C.text, fontSize: '14px'}}>📊 Материалы: смета ↔ поставки ↔ склад</b>
        <p style={{color: C.textSec, fontSize: '11px', margin: '2px 0 0'}}>План берётся из активной сметы заказчика, цепочка — из заявок, поставок, накладных, перемещений, выдач и списаний.</p>
      </div>
      <button onClick={() => showPreview(buildMaterialRequirementContent(projectName), 'Потребность материалов — ' + projectName)} style={{...btnB, fontSize: '12px', padding: '6px 12px'}}>
        <Printer size={13}/>Печать
      </button>
    </div>
  );
}

export function MaterialsMetricsGrid({C, metrics}) {
  return (
    <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(130px,1fr))', gap: '8px', marginBottom: '12px'}}>
      {metrics.map(metric => (
        <MetricCard key={metric.label} C={C} {...metric}/>
      ))}
    </div>
  );
}

export function MaterialsFilterBar({query, setQuery, filter, setFilter, filterOptions, C}) {
  return (
    <div style={{display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center', marginBottom: '10px'}}>
      <input
        value={query}
        onChange={e => setQuery(e.target.value)}
        placeholder="Поиск материала, раздела или работы..."
        style={{
          flex: '1 1 280px',
          minWidth: 0,
          padding: '10px 12px',
          borderRadius: '8px',
          border: '1.5px solid ' + C.border,
          backgroundColor: C.bg,
          color: C.text,
          fontSize: '12px'
        }}
      />
      <div style={{display: 'flex', gap: '6px', flexWrap: 'wrap'}}>
        {filterOptions.map(opt => (
          <button
            key={opt.id}
            type="button"
            onClick={() => setFilter(opt.id)}
            style={{
              padding: '8px 10px',
              borderRadius: '999px',
              border: '1.5px solid ' + (filter === opt.id ? C.accentBorder : C.border),
              backgroundColor: filter === opt.id ? C.accentLight : C.bg,
              color: filter === opt.id ? C.accent : C.textSec,
              fontSize: '11px',
              fontWeight: '700',
              cursor: 'pointer'
            }}
          >
            {opt.label}: {opt.rows.length}
          </button>
        ))}
      </div>
    </div>
  );
}

export function ShowMoreButton({hiddenRows, onClick, btnB, children}) {
  if (hiddenRows <= 0) return null;
  return (
    <button
      type="button"
      onClick={onClick}
      style={{...btnB, width: '100%', justifyContent: 'center', marginTop: '8px', fontSize: '12px'}}
    >
      {children || 'Показать ещё ' + hiddenRows}
    </button>
  );
}

export function SourceLine({label, details = [], color, fmtMeasure}) {
  if (!details.length) return null;
  const shown = details.slice(0, 3).map(d => {
    const title = d.number ? '№' + d.number : d.supplierName || d.status || d.to || d.from || 'запись';
    return title + ' · ' + fmtMeasure(d.qty || 0, d.unit || '') + (d.date ? ' · ' + String(d.date).slice(0, 10) : '');
  }).join('; ');
  return (
    <p style={{color, fontSize: '10px', margin: '2px 0 0'}}>
      {label}: {shown}{details.length > 3 ? ' +' + (details.length - 3) : ''}
    </p>
  );
}
