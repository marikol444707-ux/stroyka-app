import React from 'react';
import { Printer } from 'lucide-react';

const MetricCard = ({C, label, value, active, color, bg, border}) => (
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

export default function ProjectMaterialsControlPanel({
  projectName,
  rows = [],
  normRows = [],
  normCtrl = {overRows: [], withoutNormRows: []},
  C,
  card,
  tbl,
  tblH,
  tblC,
  btnB,
  badge,
  fmtMeasure,
  materialControlStatus,
  renderMaterialSupplyAction,
  renderMaterialAliasControls,
  showPreview,
  buildMaterialRequirementContent,
  onIssueMaterial,
}) {
  const [query, setQuery] = React.useState('');
  const [filter, setFilter] = React.useState('all');
  const planRows = rows.filter(r => r.planQty > 0);
  const toBuyRows = rows.filter(r => r.toBuy > 0);
  const pipelineRows = rows.filter(r => r.requested > 0 || r.inTransit > 0);
  const outsideRows = rows.filter(r => r.isOutsideEstimate);
  const suppliedRows = rows.filter(r => r.supplied > 0);
  const invoiceRows = rows.filter(r => r.invoiceReceived > 0);
  const deliveryRows = rows.filter(r => r.supplyReceived > 0);
  const movedRows = rows.filter(r => r.movedNet !== 0);
  const masterBalanceRows = rows.filter(r => r.masterBalance > 0);
  const stockMismatchRows = rows.filter(r => r.stockMismatch);
  const overRows = normCtrl.overRows || [];
  const withoutNormRows = normCtrl.withoutNormRows || [];
  const normProblemRows = [
    ...overRows,
    ...withoutNormRows.filter(r => !overRows.some(o => o.key === r.key))
  ];
  const queryKey = String(query || '').toLowerCase().trim();
  const filterOptions = [
    {id: 'all', label: 'Все', rows},
    {id: 'toBuy', label: 'Докупить', rows: toBuyRows},
    {id: 'pipeline', label: 'В заявках/пути', rows: pipelineRows},
    {id: 'outside', label: 'Вне сметы', rows: outsideRows},
    {id: 'stock', label: 'Остатки/расх.', rows: rows.filter(r => r.stock > 0 || r.stockMismatch || r.masterBalance > 0)}
  ];
  const filterSet = filter === 'all'
    ? null
    : new Set((filterOptions.find(f => f.id === filter)?.rows || []).map(r => r.key));
  const visibleRows = rows.filter(r => {
    if (filterSet && !filterSet.has(r.key)) return false;
    if (!queryKey) return true;
    return [
      r.name,
      ...(r.sections || []),
      ...(r.workRefs || []),
      ...(r.aliases || [])
    ].join(' ').toLowerCase().includes(queryKey);
  });
  const headCell = {
    ...tblH,
    position: 'sticky',
    top: 0,
    zIndex: 2,
    backgroundColor: C.bg
  };

  return (
    <div style={{
      ...card,
      padding: '14px',
      marginBottom: '14px',
      backgroundColor: C.bgWhite,
      border: '1.5px solid ' + C.accentBorder
    }}>
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginBottom: '12px'}}>
        <div>
          <b style={{color: C.text, fontSize: '14px'}}>📊 Материалы: смета ↔ поставки ↔ склад</b>
          <p style={{color: C.textSec, fontSize: '11px', margin: '2px 0 0'}}>План берётся из активной сметы заказчика, цепочка — из заявок, поставок, накладных, перемещений, выдач и списаний.</p>
        </div>
        <button onClick={() => showPreview(buildMaterialRequirementContent(projectName), 'Потребность материалов — ' + projectName)} style={{...btnB, fontSize: '12px', padding: '6px 12px'}}>
          <Printer size={13}/>Печать
        </button>
      </div>

      <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(130px,1fr))', gap: '8px', marginBottom: '12px'}}>
        <MetricCard C={C} label="Позиций по смете" value={planRows.length} active color={C.text} bg={C.bg} border={C.border}/>
        <MetricCard C={C} label="Поставлялось" value={suppliedRows.length} active color={C.success} bg={C.successLight} border={C.successBorder}/>
        <MetricCard C={C} label="Накладные" value={invoiceRows.length} active={invoiceRows.length > 0} color={C.info} bg={C.infoLight} border={C.infoBorder}/>
        <MetricCard C={C} label="Поставки" value={deliveryRows.length} active={deliveryRows.length > 0} color={C.success} bg={C.successLight} border={C.successBorder}/>
        <MetricCard C={C} label="Перемещения" value={movedRows.length} active={movedRows.length > 0} color={C.info} bg={C.infoLight} border={C.infoBorder}/>
        <MetricCard C={C} label="У мастеров" value={masterBalanceRows.length} active={masterBalanceRows.length > 0} color={C.info} bg={C.infoLight} border={C.infoBorder}/>
        <MetricCard C={C} label="В заявках/пути" value={pipelineRows.length} active={pipelineRows.length > 0} color={C.info} bg={C.infoLight} border={C.infoBorder}/>
        <MetricCard C={C} label="Докупить" value={toBuyRows.length} active color={toBuyRows.length ? C.warning : C.success} bg={toBuyRows.length ? C.warningLight : C.successLight} border={toBuyRows.length ? C.warningBorder : C.successBorder}/>
        <MetricCard C={C} label="Вне сметы" value={outsideRows.length} active={outsideRows.length > 0} color={C.danger} bg={C.dangerLight} border={C.dangerBorder}/>
        <MetricCard C={C} label="По нормам работ" value={normRows.length} active={normRows.length > 0} color={C.info} bg={C.infoLight} border={C.infoBorder}/>
        <MetricCard C={C} label="Перерасход норм" value={overRows.length} active={overRows.length > 0} color={C.danger} bg={C.dangerLight} border={C.dangerBorder}/>
        <MetricCard C={C} label="Списано без нормы" value={withoutNormRows.length} active={withoutNormRows.length > 0} color={C.warning} bg={C.warningLight} border={C.warningBorder}/>
        <MetricCard C={C} label="Расхождения" value={stockMismatchRows.length} active={stockMismatchRows.length > 0} color={C.danger} bg={C.dangerLight} border={C.dangerBorder}/>
      </div>

      {rows.length === 0 ? (
        <p style={{color: C.textMuted, fontSize: '12px', textAlign: 'center', padding: '14px'}}>Нет сметных материалов и движений по объекту.</p>
      ) : (
        <>
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
        <div style={{overflow: 'auto', maxHeight: '68vh', border: '1px solid ' + C.border, borderRadius: '10px'}}>
          <table style={{...tbl, fontSize: '11px', minWidth: '1420px'}}>
            <thead>
              <tr>
                <th style={headCell}>Материал</th>
                <th style={headCell}>План</th>
                <th style={headCell}>В заявках</th>
                <th style={headCell}>В пути</th>
                <th style={headCell}>Накладные</th>
                <th style={headCell}>Поставки</th>
                <th style={headCell}>Перемещено</th>
                <th style={headCell}>Всего получено</th>
                <th style={headCell}>Выдано</th>
                <th style={headCell}>Списано</th>
                <th style={headCell}>У мастеров</th>
                <th style={headCell}>Остаток</th>
                <th style={headCell}>Расчёт</th>
                <th style={headCell}>Расх.</th>
                <th style={headCell}>Докупить</th>
                <th style={headCell}>Статус</th>
              </tr>
            </thead>
            <tbody>
              {visibleRows.map(r => {
                const st = materialControlStatus(r);
                return (
                  <tr key={r.key}>
                    <td style={tblC}>
                      <b style={{fontSize: '12px'}}>{r.name}</b>
                      {r.sections.length > 0 && <p style={{color: C.textMuted, fontSize: '10px', margin: '2px 0 0'}}>{r.sections.slice(0, 2).join(', ')}{r.sections.length > 2 ? '…' : ''}</p>}
                      {r.aliases?.length > 0 && <p style={{color: C.info, fontSize: '10px', margin: '2px 0 0'}}>Синонимы: {r.aliases.slice(0, 2).join(', ')}{r.aliases.length > 2 ? '…' : ''}</p>}
                      {r.unitMismatch && <p style={{color: C.warning, fontSize: '10px', margin: '2px 0 0'}}>⚠️ Разные единицы измерения</p>}
                      {renderMaterialAliasControls(projectName, r)}
                    </td>
                    <td style={tblC}>{r.planQty > 0 ? fmtMeasure(r.planQty, r.unit) : '—'}</td>
                    <td style={{...tblC, color: r.requested > 0 ? C.info : C.textMuted}}>{fmtMeasure(r.requested, r.unit)}</td>
                    <td style={{...tblC, color: r.inTransit > 0 ? C.warning : C.textMuted}}>{fmtMeasure(r.inTransit, r.unit)}</td>
                    <td style={{...tblC, color: r.invoiceReceived > 0 ? C.success : C.textMuted}}>{fmtMeasure(r.invoiceReceived, r.unit)}</td>
                    <td style={{...tblC, color: r.supplyReceived > 0 ? C.success : C.textMuted}}>{fmtMeasure(r.supplyReceived, r.unit)}</td>
                    <td style={{...tblC, color: r.movedNet !== 0 ? C.info : C.textMuted}}>{fmtMeasure(r.movedNet, r.unit)}</td>
                    <td style={{...tblC, color: r.supplied >= r.planQty && r.planQty > 0 ? C.success : C.text}}>{fmtMeasure(r.supplied, r.unit)}</td>
                    <td style={tblC}>{fmtMeasure(r.issued, r.unit)}</td>
                    <td style={tblC}>{fmtMeasure(r.used, r.unit)}</td>
	                    <td style={{...tblC, color: r.masterBalance > 0 ? C.info : C.textMuted}}>
	                      <b>{fmtMeasure(r.masterBalance, r.unit)}</b>
	                      {r.pendingAtMasters > 0 && <p style={{margin: '2px 0 0', color: C.warning, fontSize: '10px'}}>Ждёт подписи: {fmtMeasure(r.pendingAtMasters, r.unit)}</p>}
	                      {r.holders?.slice(0, 3).map(h => (
	                        <p key={h.name} style={{margin: '2px 0 0', color: h.balance > 0 ? C.textSec : C.textMuted, fontSize: '10px'}}>
	                          {h.name}: {fmtMeasure(h.balance, h.unit || r.unit)}{h.pending > 0 ? ' · ждёт ' + fmtMeasure(h.pending, h.unit || r.unit) : ''}
	                        </p>
	                      ))}
	                    </td>
                    <td style={{...tblC, fontWeight: '600', color: r.stock > 0 ? C.success : C.textMuted}}>{fmtMeasure(r.stock, r.unit)}</td>
                    <td style={{...tblC, color: r.expectedStock > 0 ? C.text : C.textMuted}}>{fmtMeasure(r.expectedStock, r.unit)}</td>
                    <td style={{...tblC, fontWeight: '700', color: r.stockMismatch ? C.danger : C.success}}>{r.stockMismatch ? fmtMeasure(r.stockDiff, r.unit) : '0'}</td>
                    <td style={{...tblC, fontWeight: '700', color: r.toBuy > 0 ? C.warning : C.success}}>{fmtMeasure(r.toBuy, r.unit)}</td>
                    <td style={tblC}>
	                      <span style={badge(st.color, st.bg, st.border)}>
	                        {st.label}
	                        {r.stockMismatch ? ' · ' + fmtMeasure(r.stockDiff, r.unit) : r.toBuy > 0 ? ' · ' + fmtMeasure(r.toBuy, r.unit) : r.shortage > 0 ? ' · ' + fmtMeasure(r.shortage, r.unit) : r.masterBalance > 0 ? ' · ' + fmtMeasure(r.masterBalance, r.unit) : ''}
	                      </span>
	                      {renderMaterialSupplyAction(projectName, r)}
	                      {onIssueMaterial && r.stock > 0 && (
	                        <button
	                          type="button"
	                          onClick={() => onIssueMaterial(r)}
	                          style={{
	                            marginTop: '5px',
	                            padding: '4px 8px',
	                            borderRadius: '999px',
	                            border: '1px solid ' + C.successBorder,
	                            backgroundColor: C.successLight,
	                            color: C.success,
	                            fontSize: '10px',
	                            fontWeight: '800',
	                            cursor: 'pointer'
	                          }}
	                        >
	                          Выдать
	                        </button>
	                      )}
	                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {visibleRows.length === 0 && <p style={{color: C.textMuted, fontSize: '12px', textAlign: 'center', padding: '14px'}}>По фильтру ничего не найдено.</p>}
        </div>
        <p style={{color: C.textMuted, fontSize: '11px', margin: '8px 0 0'}}>
          Показано {visibleRows.length} из {rows.length}. Заявку можно создать прямо в колонке «Статус».
        </p>
        </>
      )}

      {normRows.length > 0 && (
        <div style={{marginTop: '14px', paddingTop: '12px', borderTop: '1.5px solid ' + C.border}}>
          <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginBottom: '8px'}}>
            <div>
              <b style={{color: C.info, fontSize: '13px'}}>🧮 Нормативная потребность по работам</b>
              <p style={{color: C.textSec, fontSize: '11px', margin: '2px 0 0'}}>Подсказка для проверки сметы: это не заявка и не списание, пока материал не заведён строкой типа «Материал».</p>
            </div>
          </div>
          <div style={{overflowX: 'auto'}}>
            <table style={{...tbl, fontSize: '11px'}}>
              <thead><tr><th style={tblH}>Материал по норме</th><th style={tblH}>Потребность</th><th style={tblH}>Работы-источники</th><th style={tblH}>Норма</th></tr></thead>
              <tbody>
                {normRows.slice(0, 12).map(r => (
                  <tr key={r.key}>
                    <td style={tblC}><b style={{fontSize: '12px'}}>{r.name}</b>{r.sections.length > 0 && <p style={{color: C.textMuted, fontSize: '10px', margin: '2px 0 0'}}>{r.sections.slice(0, 2).join(', ')}{r.sections.length > 2 ? '…' : ''}</p>}</td>
                    <td style={{...tblC, fontWeight: '700', color: C.info}}>{fmtMeasure(r.planQty, r.unit)}</td>
                    <td style={tblC}>{r.works.slice(0, 3).map(w => w.name).join('; ')}{r.works.length > 3 ? ' …' : ''}</td>
                    <td style={{...tblC, color: C.textSec, fontSize: '10px'}}>{r.normSources.slice(0, 2).join('; ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {normRows.length > 12 && <p style={{color: C.textMuted, fontSize: '11px', margin: '8px 0 0'}}>Показаны первые 12 строк. Полный список — в печатной ведомости.</p>}
          </div>
        </div>
      )}

      {normProblemRows.length > 0 && (
        <div style={{marginTop: '14px', paddingTop: '12px', borderTop: '1.5px solid ' + C.border}}>
          <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginBottom: '8px'}}>
            <div>
              <b style={{color: overRows.length ? C.danger : C.warning, fontSize: '13px'}}>🚦 Контроль списания по нормам</b>
              <p style={{color: C.textSec, fontSize: '11px', margin: '2px 0 0'}}>Показывает, где факт списания материалов отличается от нормы, которую подставила система при закрытии работы.</p>
            </div>
          </div>
          <div style={{overflowX: 'auto'}}>
            <table style={{...tbl, fontSize: '11px'}}>
              <thead><tr><th style={tblH}>Материал</th><th style={tblH}>Факт</th><th style={tblH}>Норма</th><th style={tblH}>Отклонение</th><th style={tblH}>Работы</th><th style={tblH}>Статус</th></tr></thead>
              <tbody>
                {normProblemRows.slice(0, 12).map(r => {
                  const over = r.overQty > 0;
                  return (
                    <tr key={r.key}>
                      <td style={tblC}><b style={{fontSize: '12px'}}>{r.name}</b>{r.normSources.length > 0 && <p style={{color: C.textMuted, fontSize: '10px', margin: '2px 0 0'}}>{r.normSources.slice(0, 2).join('; ')}</p>}</td>
                      <td style={tblC}>{fmtMeasure(r.qty, r.unit)}</td>
                      <td style={tblC}>{r.normQty > 0 ? fmtMeasure(r.normQty, r.unit) : '—'}</td>
                      <td style={{...tblC, fontWeight: '700', color: over ? C.danger : C.warning}}>{over ? ('+' + fmtMeasure(r.overQty, r.unit)) : 'без нормы ' + fmtMeasure(r.withoutNormQty, r.unit)}</td>
                      <td style={tblC}>{r.works.slice(0, 3).map(w => w.workName + (w.master ? ' · ' + w.master : '')).join('; ')}{r.works.length > 3 ? ' …' : ''}</td>
                      <td style={tblC}><span style={badge(over ? C.danger : C.warning, over ? C.dangerLight : C.warningLight, over ? C.dangerBorder : C.warningBorder)}>{over ? 'Проверить перерасход' : 'Нужна норма'}</span></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {normProblemRows.length > 12 && <p style={{color: C.textMuted, fontSize: '11px', margin: '8px 0 0'}}>Показаны первые 12 строк. Полный список — в печатной ведомости.</p>}
          </div>
        </div>
      )}
    </div>
  );
}
