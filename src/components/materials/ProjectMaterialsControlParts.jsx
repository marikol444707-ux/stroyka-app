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
        <b style={{color: C.text, fontSize: '14px'}}>📊 Материалы: смета ↔ нормы ↔ поставки ↔ склад</b>
        <p style={{color: C.textSec, fontSize: '11px', margin: '2px 0 0'}}>Контрольная потребность берётся из активной сметы и норм расхода, цепочка — из заявок, поставок, накладных, перемещений, выдач и списаний.</p>
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

const traceScalar = (value) => {
  const number = Number(value || 0);
  return Number.isFinite(number)
    ? number.toLocaleString('ru-RU', {maximumFractionDigits: 6})
    : '0';
};

export function EstimateSourceTrace({
  row,
  details = [],
  C,
  tbl,
  tblH,
  tblC,
  fmtMeasure,
  colSpan = 17,
}) {
  return (
    <tr>
      <td colSpan={colSpan} style={{...tblC, padding: '10px 14px', backgroundColor: C.bg}}>
        <div style={{border: '1px solid ' + C.border, borderRadius: '8px', overflow: 'hidden', backgroundColor: C.bgWhite}}>
          <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px', flexWrap: 'wrap', padding: '8px 10px', borderBottom: '1px solid ' + C.border}}>
            <b style={{color: C.text, fontSize: '12px'}}>Строки сметы и решение по расчёту</b>
            <span style={{color: C.textSec, fontSize: '11px'}}>
              {fmtMeasure(row.planQty, row.unit)} · {Math.round(row.planSum || 0).toLocaleString('ru-RU')} ₽
            </span>
          </div>
          <div style={{overflowX: 'auto'}}>
            <table style={{...tbl, fontSize: '10px', minWidth: '1180px'}}>
              <thead>
                <tr>
                  <th style={tblH}>Смета</th>
                  <th style={tblH}>Пакет</th>
                  <th style={tblH}>Раздел</th>
                  <th style={tblH}>Работа-основание</th>
                  <th style={tblH}>Строка материала</th>
                  <th style={tblH}>Исходное количество</th>
                  <th style={tblH}>В плане</th>
                  <th style={tblH}>Сумма</th>
                  <th style={tblH}>Решение</th>
                </tr>
              </thead>
              <tbody>
                {details.map((detail, idx) => {
                  const invalid = row.reviewRequired || detail.includedInProcurement === false || !!detail.reason;
                  const sourceQty = detail.rawQty !== undefined && detail.rawQty !== null && detail.rawQty !== ''
                    ? Number(detail.rawQty || 0)
                    : Number(detail.sourceQty || 0);
                  const sourceUnit = detail.rawUnit || detail.sourceUnit || detail.unit || row.unit;
                  return (
                    <tr key={(detail.estimateId || 'e') + '-' + idx} style={invalid ? {backgroundColor: C.warningLight} : undefined}>
                      <td style={tblC}>{detail.estimateName || '—'}</td>
                      <td style={tblC}>{detail.packageName || 'Основная'}</td>
                      <td style={tblC}>{detail.sectionName || '—'}</td>
                      <td style={tblC}>{detail.workName || '—'}</td>
                      <td style={tblC}>{detail.materialName || row.name}</td>
                      <td style={tblC}>{traceScalar(sourceQty)} {sourceUnit}</td>
                      <td style={{...tblC, fontWeight: '700'}}>
                        {fmtMeasure(detail.normalizedQty ?? detail.qty ?? 0, detail.normalizedUnit || detail.unit || row.unit)}
                        {detail.conversionApplied && (
                          <p style={{color: C.info, fontSize: '10px', margin: '3px 0 0'}}>
                            преобразовано{Number(detail.normalizationFactor || 1) !== 1 ? ' × ' + traceScalar(detail.normalizationFactor) : ''}
                          </p>
                        )}
                      </td>
                      <td style={tblC}>{Math.round(detail.sum || 0).toLocaleString('ru-RU')} ₽</td>
                      <td style={{...tblC, color: invalid ? C.warning : C.success, fontWeight: '700'}}>
                        {invalid ? 'Проверить' : 'В закупочном плане'}
                        {(detail.reason || (invalid && row.reviewReasons?.[0])) && (
                          <p style={{color: C.warning, fontSize: '10px', margin: '3px 0 0'}}>
                            {detail.reason || row.reviewReasons[0]}
                          </p>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </td>
    </tr>
  );
}

const normFormulaText = (work, fmtMeasure) => {
  const formula = work.formula || {};
  const parts = [fmtMeasure(formula.workQty ?? work.quantity ?? 0, formula.workUnit || work.unit || '')];
  if (Number(formula.qtyPerUnit || 0) > 0) {
    parts.push('× ' + traceScalar(formula.qtyPerUnit) + ' ' + (formula.materialUnit || work.requiredUnit || '') + '/' + (formula.workUnit || work.unit || 'ед.'));
  }
  if (Number(formula.thicknessBaseMm || 0) > 0) {
    parts.push('× ' + traceScalar(formula.thicknessMm || formula.thicknessBaseMm) + '/' + traceScalar(formula.thicknessBaseMm));
  }
  return parts.join(' ') + ' = ' + fmtMeasure(formula.requiredQty ?? work.requiredQty ?? 0, formula.requiredUnit || work.requiredUnit || '');
};

export function NormSourceTrace({row, C, tbl, tblH, tblC, fmtMeasure, colSpan = 4}) {
  return (
    <tr>
      <td colSpan={colSpan} style={{...tblC, padding: '10px 14px', backgroundColor: C.bg}}>
        <div style={{overflowX: 'auto', border: '1px solid ' + C.border, borderRadius: '8px'}}>
          <table style={{...tbl, fontSize: '10px', minWidth: '1080px'}}>
            <thead>
              <tr>
                <th style={tblH}>Смета</th>
                <th style={tblH}>Пакет</th>
                <th style={tblH}>Раздел</th>
                <th style={tblH}>Работа</th>
                <th style={tblH}>Правило</th>
                <th style={tblH}>Формула</th>
                <th style={tblH}>Результат</th>
              </tr>
            </thead>
            <tbody>
              {(row.works || []).map((work, idx) => (
                <tr key={(work.estimateId || 'e') + '-' + (work.itemId || idx) + '-' + idx}>
                  <td style={tblC}>{work.estimateName || '—'}</td>
                  <td style={tblC}>{work.packageName || 'Основная'}</td>
                  <td style={tblC}>{work.section || '—'}</td>
                  <td style={tblC}>{work.name || '—'}</td>
                  <td style={tblC}>{work.ruleId || '—'} · {work.ruleScope || 'base'}</td>
                  <td style={{...tblC, color: C.textSec}}>{normFormulaText(work, fmtMeasure)}</td>
                  <td style={{...tblC, color: C.info, fontWeight: '700'}}>{fmtMeasure(work.requiredQty || 0, work.requiredUnit || row.unit)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </td>
    </tr>
  );
}
