import React from 'react';
import { ChevronDown, ChevronRight, ShoppingCart } from 'lucide-react';
import MaterialProjectionDryRunPanel from './MaterialProjectionDryRunPanel';
import {
  EstimateSourceTrace,
  MaterialsControlHeader,
  MaterialsFilterBar,
  MaterialsMetricsGrid,
  NormSourceTrace,
  ShowMoreButton,
  SourceLine
} from './materials/ProjectMaterialsControlParts';

export default function ProjectMaterialsControlPanel({
  projectName,
  rows: initialRows = [],
  normRows: initialNormRows = [],
  normCtrl: initialNormCtrl = {overRows: [], withoutNormRows: []},
  buildRowsForPackage,
  buildNormRowsForPackage,
  buildNormCtrlForPackage,
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
  onCreateSupplyForRows,
  isMobile = false,
}) {
  const [query, setQuery] = React.useState('');
  const [filter, setFilter] = React.useState('all');
  const [showAllRows, setShowAllRows] = React.useState(false);
  const [showAllNormRows, setShowAllNormRows] = React.useState(false);
  const [showAllNormProblemRows, setShowAllNormProblemRows] = React.useState(false);
  const [rowDisplayLimit, setRowDisplayLimit] = React.useState(null);
  const [expandedRows, setExpandedRows] = React.useState({});
  const [expandedNormRows, setExpandedNormRows] = React.useState({});
  const [workPackage, setWorkPackage] = React.useState('');
  const toggleExpandedRow = (key) => setExpandedRows(prev => ({...prev, [key]: !prev[key]}));
  const toggleExpandedNormRow = (key) => setExpandedNormRows(prev => ({...prev, [key]: !prev[key]}));
  const packageOptions = React.useMemo(() => {
    const names = new Set();
    const add = (value) => {
      const name = String(value || '').trim();
      if (name && name !== 'Основная') names.add(name);
    };
    (initialRows || []).forEach(row => {
      (row.planDetails || []).forEach(detail => add(detail.packageName));
      (row.invalidPlanDetails || []).forEach(detail => add(detail.packageName));
      (row.normDetails || []).forEach(detail => {
        (detail.packageNames || []).forEach(add);
        add(detail.packageName);
      });
    });
    (initialNormRows || []).forEach(row => (row.packageNames || []).forEach(add));
    return Array.from(names).sort((a, b) => a.localeCompare(b, 'ru'));
  }, [initialRows, initialNormRows]);
  const rows = React.useMemo(
    () => (workPackage && buildRowsForPackage ? buildRowsForPackage(workPackage) : initialRows),
    [workPackage, buildRowsForPackage, initialRows]
  );
  const normRows = React.useMemo(
    () => (workPackage && buildNormRowsForPackage ? buildNormRowsForPackage(workPackage) : initialNormRows),
    [workPackage, buildNormRowsForPackage, initialNormRows]
  );
  const normCtrl = React.useMemo(
    () => (workPackage && buildNormCtrlForPackage ? buildNormCtrlForPackage(workPackage) : initialNormCtrl),
    [workPackage, buildNormCtrlForPackage, initialNormCtrl]
  );
  const planRows = rows.filter(r => r.planQty > 0);
  const toBuyRows = rows.filter(r => r.toBuy > 0 && r.procurementEligible !== false);
  const toBuyPreviewRows = toBuyRows.slice(0, isMobile ? 5 : 8);
  const toBuyUnitsText = Object.entries(toBuyRows.reduce((acc, r) => {
    const unit = r.unit || 'шт';
    acc[unit] = (acc[unit] || 0) + Number(r.toBuy || 0);
    return acc;
  }, {})).slice(0, 4).map(([unit, qty]) => qty.toLocaleString('ru-RU', {maximumFractionDigits: 3}) + ' ' + unit).join(' · ');
  const pipelineRows = rows.filter(r => r.requested > 0 || r.inTransit > 0);
  const outsideRows = rows.filter(r => r.isOutsideEstimate);
  const suppliedRows = rows.filter(r => r.supplied > 0);
  const invoiceRows = rows.filter(r => r.invoiceReceived > 0);
  const deliveryRows = rows.filter(r => r.supplyReceived > 0);
  const movedRows = rows.filter(r => r.movedNet !== 0);
  const masterBalanceRows = rows.filter(r => r.masterBalance > 0);
  const stockMismatchRows = rows.filter(r => r.stockMismatch);
  const reviewRows = rows.filter(r => r.reviewRequired || r.invalidPlanCount > 0 || r.unitMismatch);
  const rowNormRows = rows.filter(r => r.normPlanQty > 0);
  const normOverEstimateRows = rows.filter(r => r.normOverEstimateQty > 0);
  const usedOverControlRows = rows.filter(r => r.usedOverControlQty > 0);
  const usedOverEstimateRows = rows.filter(r => r.usedOverEstimateQty > 0);
  const overRows = normCtrl.overRows || [];
  const withoutNormRows = normCtrl.withoutNormRows || [];
  const normProblemRows = [
    ...overRows,
    ...withoutNormRows.filter(r => !overRows.some(o => o.key === r.key))
  ];
  const queryKey = String(query || '').toLowerCase().trim();
  const filterOptions = [
    {id: 'all', label: 'Все', rows},
    {id: 'estimate', label: 'Смета', rows: planRows},
    {id: 'toBuy', label: 'Докупить', rows: toBuyRows},
    {id: 'review', label: 'Проверить', rows: reviewRows},
    {id: 'normGap', label: 'Нормы', rows: rows.filter(r => r.normPlanQty > 0 || r.normWithoutEstimateQty > 0 || r.normOverEstimateQty > 0 || r.usedOverEstimateQty > 0 || r.usedOverControlQty > 0)},
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
  React.useEffect(() => {
    setShowAllRows(false);
    setRowDisplayLimit(null);
  }, [queryKey, filter, rows.length, workPackage]);
  const rowLimit = isMobile
    ? (queryKey || filter !== 'all' ? 90 : 45)
    : (queryKey || filter !== 'all' ? 240 : 120);
  const activeRowLimit = showAllRows ? visibleRows.length : (rowDisplayLimit || rowLimit);
  const displayedRows = visibleRows.slice(0, activeRowLimit);
  const hiddenRows = Math.max(0, visibleRows.length - displayedRows.length);
  const visibleToBuyRows = visibleRows.filter(r => Number(r.toBuy || 0) > 0 && r.procurementEligible !== false && !r.reviewRequired);
  const visibleToBuyUnits = Object.entries(visibleToBuyRows.reduce((acc, r) => {
    const unit = r.unit || 'шт';
    acc[unit] = (acc[unit] || 0) + Number(r.toBuy || 0);
    return acc;
  }, {})).slice(0, 4).map(([unit, qty]) => qty.toLocaleString('ru-RU', {maximumFractionDigits: 3}) + ' ' + unit).join(' · ');
  const normRowLimit = isMobile ? 8 : 12;
  const displayedNormRows = showAllNormRows ? normRows : normRows.slice(0, normRowLimit);
  const hiddenNormRows = Math.max(0, normRows.length - displayedNormRows.length);
  const displayedNormProblemRows = showAllNormProblemRows ? normProblemRows : normProblemRows.slice(0, normRowLimit);
  const hiddenNormProblemRows = Math.max(0, normProblemRows.length - displayedNormProblemRows.length);
  const headCell = {
    ...tblH,
    position: 'sticky',
    top: 0,
    zIndex: 2,
    backgroundColor: C.bg
  };
  const metrics = [
    {label: 'Позиций по смете', value: planRows.length, active: true, color: C.text, bg: C.bg, border: C.border},
    {label: 'Поставлялось', value: suppliedRows.length, active: true, color: C.success, bg: C.successLight, border: C.successBorder},
    {label: 'Накладные', value: invoiceRows.length, active: invoiceRows.length > 0, color: C.info, bg: C.infoLight, border: C.infoBorder},
    {label: 'Поставки', value: deliveryRows.length, active: deliveryRows.length > 0, color: C.success, bg: C.successLight, border: C.successBorder},
    {label: 'Перемещения', value: movedRows.length, active: movedRows.length > 0, color: C.info, bg: C.infoLight, border: C.infoBorder},
    {label: 'У мастеров', value: masterBalanceRows.length, active: masterBalanceRows.length > 0, color: C.info, bg: C.infoLight, border: C.infoBorder},
    {label: 'В заявках/пути', value: pipelineRows.length, active: pipelineRows.length > 0, color: C.info, bg: C.infoLight, border: C.infoBorder},
    {label: 'Докупить', value: toBuyRows.length, active: true, color: toBuyRows.length ? C.warning : C.success, bg: toBuyRows.length ? C.warningLight : C.successLight, border: toBuyRows.length ? C.warningBorder : C.successBorder},
    {label: 'Проверить', value: reviewRows.length, active: reviewRows.length > 0, color: C.warning, bg: C.warningLight, border: C.warningBorder},
    {label: 'Норма выше сметы', value: normOverEstimateRows.length, active: normOverEstimateRows.length > 0, color: C.warning, bg: C.warningLight, border: C.warningBorder},
    {label: 'Списано сверх сметы', value: usedOverEstimateRows.length, active: usedOverEstimateRows.length > 0, color: C.warning, bg: C.warningLight, border: C.warningBorder},
    {label: 'Расход сверх', value: usedOverControlRows.length, active: usedOverControlRows.length > 0, color: C.danger, bg: C.dangerLight, border: C.dangerBorder},
    {label: 'Вне сметы', value: outsideRows.length, active: outsideRows.length > 0, color: C.danger, bg: C.dangerLight, border: C.dangerBorder},
    {label: 'Нормативные подсказки', value: rowNormRows.length || normRows.length, active: (rowNormRows.length || normRows.length) > 0, color: C.info, bg: C.infoLight, border: C.infoBorder},
    {label: 'Перерасход норм', value: overRows.length, active: overRows.length > 0, color: C.danger, bg: C.dangerLight, border: C.dangerBorder},
    {label: 'Списано без нормы', value: withoutNormRows.length, active: withoutNormRows.length > 0, color: C.warning, bg: C.warningLight, border: C.warningBorder},
    {label: 'Расхождения', value: stockMismatchRows.length, active: stockMismatchRows.length > 0, color: C.danger, bg: C.dangerLight, border: C.dangerBorder}
  ];

  return (
    <div style={{
      ...card,
      padding: '14px',
      marginBottom: '14px',
      backgroundColor: C.bgWhite,
      border: '1.5px solid ' + C.accentBorder
    }}>
      <MaterialsControlHeader
        projectName={projectName}
        C={C}
        btnB={btnB}
        showPreview={showPreview}
        buildMaterialRequirementContent={buildMaterialRequirementContent}
      />

      <MaterialsMetricsGrid C={C} metrics={metrics}/>

      <MaterialProjectionDryRunPanel
        projectName={projectName}
        rows={rows}
        C={C}
        fmtMeasure={fmtMeasure}
        isMobile={isMobile}
      />

      <div style={{
        marginBottom: '12px',
        padding: '12px',
        borderRadius: '10px',
        border: '1.5px solid ' + (toBuyRows.length ? C.warningBorder : C.successBorder),
        backgroundColor: toBuyRows.length ? C.warningLight : C.successLight
      }}>
        <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '10px', flexWrap: 'wrap'}}>
          <div style={{minWidth: 0, flex: '1 1 260px'}}>
            <b style={{color: toBuyRows.length ? C.warning : C.success, fontSize: '14px'}}>
              Материалы к закупке по смете
            </b>
            <p style={{color: C.textSec, fontSize: '11px', margin: '3px 0 0', lineHeight: 1.35}}>
              Это не текущий остаток на объекте. Здесь показана расчетная нехватка: план сметы минус получено, заявки и поставки в пути.
            </p>
            <p style={{color: C.text, fontSize: '12px', margin: '7px 0 0', fontWeight: '700'}}>
              {toBuyRows.length ? ('Купить: ' + toBuyRows.length + ' поз.' + (toBuyUnitsText ? ' · ' + toBuyUnitsText : '')) : 'К закупке по смете сейчас ничего нет'}
            </p>
            {reviewRows.length > 0 && (
              <button
                type="button"
                onClick={() => setFilter('review')}
                style={{border: 0, padding: 0, marginTop: '5px', background: 'transparent', color: C.warning, fontSize: '11px', fontWeight: '700', cursor: 'pointer'}}
              >
                Не включено до проверки: {reviewRows.length} поз.
              </button>
            )}
          </div>
          <div style={{display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'flex-end'}}>
            {toBuyRows.length > 0 && (
              <button
                type="button"
                onClick={() => setFilter('toBuy')}
                style={{
                  padding: '8px 10px',
                  borderRadius: '8px',
                  border: '1.5px solid ' + C.warningBorder,
                  backgroundColor: C.bgWhite,
                  color: C.warning,
                  cursor: 'pointer',
                  fontSize: '11px',
                  fontWeight: '800'
                }}
              >
                Показать все
              </button>
            )}
            {toBuyRows.length > 0 && onCreateSupplyForRows && (
              <button
                type="button"
                onClick={() => onCreateSupplyForRows(toBuyRows)}
                style={{
                  padding: '8px 10px',
                  borderRadius: '8px',
                  border: '1.5px solid ' + C.accentBorder,
                  backgroundColor: C.accent,
                  color: 'white',
                  cursor: 'pointer',
                  fontSize: '11px',
                  fontWeight: '800',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
              >
                <ShoppingCart size={13}/>Создать заявки
              </button>
            )}
          </div>
        </div>
        {toBuyPreviewRows.length > 0 && (
          <div style={{
            display: 'grid',
            gridTemplateColumns: isMobile ? '1fr' : 'repeat(auto-fit,minmax(240px,1fr))',
            gap: '8px',
            marginTop: '10px'
          }}>
            {toBuyPreviewRows.map(row => (
              <div key={row.key || row.name} style={{
                padding: '9px 10px',
                borderRadius: '8px',
                border: '1px solid ' + C.warningBorder,
                backgroundColor: C.bgWhite
              }}>
                <b style={{color: C.text, fontSize: '12px', display: 'block'}}>{row.name}</b>
                <p style={{color: C.textSec, fontSize: '10px', margin: '3px 0 0'}}>
                  {(row.workPackage || row.packageName || 'Основная') + (row.sections?.length ? ' · ' + row.sections.slice(0, 2).join(', ') : '')}
                </p>
                <p style={{color: C.text, fontSize: '11px', margin: '6px 0 0'}}>
                  По смете {fmtMeasure(row.planQty, row.unit)} · закрыто {fmtMeasure(row.coveredWithPipeline || 0, row.unit)}
                </p>
                <b style={{color: C.warning, fontSize: '12px', display: 'block', marginTop: '3px'}}>
                  Докупить {fmtMeasure(row.toBuy, row.unit)}
                </b>
              </div>
            ))}
          </div>
        )}
      </div>

      {packageOptions.length > 0 && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          flexWrap: 'wrap',
          marginBottom: '10px',
          padding: '10px 12px',
          borderRadius: '10px',
          border: '1px solid ' + C.border,
          backgroundColor: C.bg
        }}>
          <span style={{color: C.textSec, fontSize: '12px', fontWeight: '700'}}>Пакет работ:</span>
          <button
            type="button"
            onClick={() => setWorkPackage('')}
            style={{
              padding: '6px 10px',
              borderRadius: '999px',
              border: '1.5px solid ' + (!workPackage ? C.accentBorder : C.border),
              backgroundColor: !workPackage ? C.accentLight : C.bgWhite,
              color: !workPackage ? C.accent : C.textSec,
              fontSize: '11px',
              fontWeight: '800',
              cursor: 'pointer'
            }}
          >
            Весь объект
          </button>
          {packageOptions.map(name => (
            <button
              key={name}
              type="button"
              onClick={() => setWorkPackage(name)}
              style={{
                padding: '6px 10px',
                borderRadius: '999px',
                border: '1.5px solid ' + (workPackage === name ? C.accentBorder : C.border),
                backgroundColor: workPackage === name ? C.accentLight : C.bgWhite,
                color: workPackage === name ? C.accent : C.textSec,
                fontSize: '11px',
                fontWeight: '800',
                cursor: 'pointer'
              }}
              title={'Показать потребность, выдачу и списание только по пакету «' + name + '»'}
            >
              {name}
            </button>
          ))}
        </div>
      )}

      {rows.length === 0 ? (
        <p style={{color: C.textMuted, fontSize: '12px', textAlign: 'center', padding: '14px'}}>Нет сметных материалов и движений {workPackage ? 'по выбранному пакету.' : 'по объекту.'}</p>
      ) : (
        <>
        <MaterialsFilterBar
          query={query}
          setQuery={setQuery}
          filter={filter}
          setFilter={setFilter}
          filterOptions={filterOptions}
          C={C}
        />
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '8px',
          flexWrap: 'wrap',
          marginBottom: '10px',
          padding: '10px 12px',
          borderRadius: '10px',
          border: '1px solid ' + C.border,
          backgroundColor: C.bg
        }}>
          <div>
            <b style={{color: C.text, fontSize: '12px'}}>Выборка: {visibleRows.length} поз.</b>
            <p style={{color: visibleToBuyRows.length ? C.warning : C.textMuted, fontSize: '11px', margin: '2px 0 0'}}>
              К закупке: {visibleToBuyRows.length} поз.{visibleToBuyUnits ? ' · ' + visibleToBuyUnits : ''}
            </p>
          </div>
          {onCreateSupplyForRows && visibleToBuyRows.length > 0 && (
            <button
              type="button"
              onClick={() => onCreateSupplyForRows(visibleToBuyRows)}
              style={{
                padding: '8px 12px',
                borderRadius: '999px',
                border: '1.5px solid ' + C.warningBorder,
                backgroundColor: C.warningLight,
                color: C.warning,
                fontSize: '12px',
                fontWeight: '800',
                cursor: 'pointer'
              }}
            >
              Заявка по выборке
            </button>
          )}
        </div>
        <div style={{overflow: 'auto', maxHeight: isMobile ? '58vh' : '68vh', maxWidth: '100%', WebkitOverflowScrolling: 'touch', border: '1px solid ' + C.border, borderRadius: '10px'}}>
          <table style={{...tbl, fontSize: isMobile ? '10px' : '11px', minWidth: isMobile ? '1060px' : '1510px'}}>
            <thead>
              <tr>
                <th style={headCell}>Материал</th>
                <th style={headCell}>По смете</th>
                <th style={headCell}>По норме</th>
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
              {displayedRows.map(r => {
                const st = materialControlStatus(r);
                const planDetails = r.planDetails || [];
                const invalidPlanDetails = r.invalidPlanDetails || [];
                const sourceDetails = [...planDetails, ...invalidPlanDetails];
                const isExpanded = !!expandedRows[r.key];
                return (
                  <React.Fragment key={r.key}>
                  <tr>
                    <td style={tblC}>
                      <b style={{fontSize: '12px'}}>{r.name}</b>
                      {r.workPackage && <p style={{color: C.info, fontSize: '10px', margin: '2px 0 0'}}>📁 {r.workPackage}</p>}
                      {r.sections.length > 0 && <p style={{color: C.textMuted, fontSize: '10px', margin: '2px 0 0'}}>{r.sections.slice(0, 2).join(', ')}{r.sections.length > 2 ? '…' : ''}</p>}
                      {sourceDetails.length > 0 && (
                        <button
                          type="button"
                          onClick={() => toggleExpandedRow(r.key)}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            marginTop: '4px',
                            padding: '3px 7px',
                            borderRadius: '999px',
                            border: '1px solid ' + C.border,
                            backgroundColor: C.bg,
                            color: C.textSec,
                            fontSize: '10px',
                            fontWeight: '700',
                            cursor: 'pointer'
                          }}
                        >
                          {isExpanded ? <ChevronDown size={12}/> : <ChevronRight size={12}/>}
                          {sourceDetails.length} строк сметы
                        </button>
                      )}
                      {r.reviewRequired && (r.reviewReasons || []).slice(0, 2).map(reason => (
                        <p key={reason} style={{color: C.warning, fontSize: '10px', margin: '3px 0 0'}}>⚠️ {reason}</p>
                      ))}
                      {r.aliases?.length > 0 && <p style={{color: r.identityStatus === 'confirmed_alias' ? C.success : C.warning, fontSize: '10px', margin: '2px 0 0'}}>{r.identityStatus === 'confirmed_alias' ? 'Алиас подтвержден: ' : 'Нужно подтвердить: '}{r.aliases.slice(0, 2).join(', ')}{r.aliases.length > 2 ? '…' : ''}</p>}
                      <SourceLine label="Накладные" details={r.invoiceDetails} color={C.success} fmtMeasure={fmtMeasure}/>
                      <SourceLine label="Поставки" details={r.supplyDetails} color={C.info} fmtMeasure={fmtMeasure}/>
                      <SourceLine label="Перемещения" details={r.movementDetails} color={C.textSec} fmtMeasure={fmtMeasure}/>
                      {renderMaterialAliasControls(projectName, r)}
                    </td>
                    <td style={tblC}>
                      {r.planQty > 0 ? (
                        <b>{fmtMeasure(r.planQty, r.unit)}</b>
                      ) : (
                        <span style={{color: C.textMuted}}>—</span>
                      )}
                    </td>
                    <td style={tblC}>
                      {r.normPlanQty > 0 ? <b style={{color: C.info}}>{fmtMeasure(r.normPlanQty, r.unit)}</b> : <span style={{color: C.textMuted}}>—</span>}
                      {r.normOverEstimateQty > 0 && (
                        <p style={{margin: '3px 0 0', color: C.warning, fontSize: '10px'}}>
                          +{fmtMeasure(r.normOverEstimateQty, r.unit)} к смете
                        </p>
                      )}
                    </td>
                    <td style={{...tblC, color: r.requested > 0 ? C.info : C.textMuted}}>{fmtMeasure(r.requested, r.unit)}</td>
                    <td style={{...tblC, color: r.inTransit > 0 ? C.warning : C.textMuted}}>{fmtMeasure(r.inTransit, r.unit)}</td>
                    <td style={{...tblC, color: r.invoiceReceived > 0 ? C.success : C.textMuted}}>{fmtMeasure(r.invoiceReceived, r.unit)}</td>
                    <td style={{...tblC, color: r.supplyReceived > 0 ? C.success : C.textMuted}}>{fmtMeasure(r.supplyReceived, r.unit)}</td>
                    <td style={{...tblC, color: r.movedNet !== 0 ? C.info : C.textMuted}}>{fmtMeasure(r.movedNet, r.unit)}</td>
                    <td style={{...tblC, color: r.supplied >= r.planQty && r.planQty > 0 ? C.success : C.text}}>{fmtMeasure(r.supplied, r.unit)}</td>
                    <td style={tblC}>{fmtMeasure(r.issued, r.unit)}</td>
                    <td style={tblC}>
                      {fmtMeasure(r.used, r.unit)}
                      {r.controlPlanQty > 0 && (
                        <p style={{margin: '2px 0 0', color: r.usedOverControlQty > 0 ? C.danger : C.textMuted, fontSize: '10px'}}>
                          {r.spendPct || 0}% от контроля
                        </p>
                      )}
                      {r.usedOverControlQty > 0 && (
                        <p style={{margin: '2px 0 0', color: C.danger, fontSize: '10px', fontWeight: '700'}}>
                          сверх {fmtMeasure(r.usedOverControlQty, r.unit)}
                        </p>
                      )}
                      {r.usedOverEstimateQty > 0 && r.usedOverControlQty <= 0 && (
                        <p style={{margin: '2px 0 0', color: C.warning, fontSize: '10px', fontWeight: '700'}}>
                          сверх сметы {fmtMeasure(r.usedOverEstimateQty, r.unit)}
                        </p>
                      )}
                    </td>
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
		                        {r.invalidPlanCount > 0 ? ' · ' + r.invalidPlanCount : r.stockMismatch ? ' · ' + fmtMeasure(r.stockDiff, r.unit) : r.usedOverControlQty > 0 ? ' · ' + fmtMeasure(r.usedOverControlQty, r.unit) : r.usedOverEstimateQty > 0 ? ' · ' + fmtMeasure(r.usedOverEstimateQty, r.unit) : r.normWithoutEstimateQty > 0 ? ' · ' + fmtMeasure(r.normWithoutEstimateQty, r.unit) : r.normOverEstimateQty > 0 ? ' · +' + fmtMeasure(r.normOverEstimateQty, r.unit) : r.toBuy > 0 ? ' · ' + fmtMeasure(r.toBuy, r.unit) : r.shortage > 0 ? ' · ' + fmtMeasure(r.shortage, r.unit) : r.masterBalance > 0 ? ' · ' + fmtMeasure(r.masterBalance, r.unit) : ''}
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
                  {isExpanded && sourceDetails.length > 0 && (
                    <EstimateSourceTrace
                      row={r}
                      details={sourceDetails}
                      C={C}
                      tbl={tbl}
                      tblH={tblH}
                      tblC={tblC}
                      fmtMeasure={fmtMeasure}
                    />
                  )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
          {visibleRows.length === 0 && <p style={{color: C.textMuted, fontSize: '12px', textAlign: 'center', padding: '14px'}}>По фильтру ничего не найдено.</p>}
        </div>
        <ShowMoreButton
          hiddenRows={hiddenRows}
          onClick={() => {
            if (isMobile) {
              setRowDisplayLimit(limit => Math.min(visibleRows.length, (limit || rowLimit) + rowLimit));
              return;
            }
            setShowAllRows(true);
          }}
          btnB={btnB}
        >
          Показать ещё {isMobile ? Math.min(hiddenRows, rowLimit) : hiddenRows} материалов
        </ShowMoreButton>
        <p style={{color: C.textMuted, fontSize: '11px', margin: '8px 0 0'}}>
          Показано {displayedRows.length} из {visibleRows.length}{visibleRows.length !== rows.length ? ' найденных' : ''}. Заявку можно создать прямо в колонке «Статус».
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
                {displayedNormRows.map(r => {
                  const isExpanded = !!expandedNormRows[r.key];
                  return (
                    <React.Fragment key={r.key}>
                      <tr>
                        <td style={tblC}>
                          <b style={{fontSize: '12px'}}>{r.name}</b>
                          {r.sections.length > 0 && <p style={{color: C.textMuted, fontSize: '10px', margin: '2px 0 0'}}>{r.sections.slice(0, 2).join(', ')}{r.sections.length > 2 ? '…' : ''}</p>}
                        </td>
                        <td style={{...tblC, fontWeight: '700', color: C.info}}>{fmtMeasure(r.planQty, r.unit)}</td>
                        <td style={tblC}>
                          {r.works.slice(0, 3).map(w => w.name).join('; ')}{r.works.length > 3 ? ' …' : ''}
                          {r.works.length > 0 && (
                            <button
                              type="button"
                              onClick={() => toggleExpandedNormRow(r.key)}
                              style={{display: 'flex', alignItems: 'center', gap: '4px', marginTop: '5px', padding: '3px 7px', borderRadius: '999px', border: '1px solid ' + C.infoBorder, backgroundColor: C.infoLight, color: C.info, fontSize: '10px', fontWeight: '700', cursor: 'pointer'}}
                            >
                              {isExpanded ? <ChevronDown size={12}/> : <ChevronRight size={12}/>} {r.works.length} расчетов
                            </button>
                          )}
                        </td>
                        <td style={{...tblC, color: C.textSec, fontSize: '10px'}}>{r.normSources.slice(0, 2).join('; ')}</td>
                      </tr>
                      {isExpanded && <NormSourceTrace row={r} C={C} tbl={tbl} tblH={tblH} tblC={tblC} fmtMeasure={fmtMeasure}/>}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
            <ShowMoreButton hiddenRows={hiddenNormRows} onClick={() => setShowAllNormRows(true)} btnB={btnB}>
              Показать ещё {hiddenNormRows} строк норм
            </ShowMoreButton>
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
                {displayedNormProblemRows.map(r => {
                  const over = r.overQty > 0;
                  return (
                    <tr key={r.key}>
                      <td style={tblC}><b style={{fontSize: '12px'}}>{r.name}</b>{r.normSources.length > 0 && <p style={{color: C.textMuted, fontSize: '10px', margin: '2px 0 0'}}>{r.normSources.slice(0, 2).join('; ')}</p>}</td>
                      <td style={tblC}>{fmtMeasure(r.qty, r.unit)}</td>
                      <td style={tblC}>{r.normQty > 0 ? fmtMeasure(r.normQty, r.unit) : '—'}</td>
                      <td style={{...tblC, fontWeight: '700', color: over ? C.danger : C.warning}}>{over ? ('+' + fmtMeasure(r.overQty, r.unit)) : 'без нормы ' + fmtMeasure(r.withoutNormQty, r.unit)}</td>
                      <td style={tblC}>
                        {r.works.slice(0, 3).map(w => w.workName + (w.master ? ' · ' + w.master : '')).join('; ')}{r.works.length > 3 ? ' …' : ''}
                        {r.works.some(w => w.overNormReason) && (
                          <p style={{color: C.textMuted, fontSize: '10px', margin: '3px 0 0'}}>
                            Причина: {r.works.find(w => w.overNormReason)?.overNormReason}
                          </p>
                        )}
                      </td>
                      <td style={tblC}><span style={badge(over ? C.danger : C.warning, over ? C.dangerLight : C.warningLight, over ? C.dangerBorder : C.warningBorder)}>{over ? 'Проверить перерасход' : 'Нужна норма'}</span></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <ShowMoreButton hiddenRows={hiddenNormProblemRows} onClick={() => setShowAllNormProblemRows(true)} btnB={btnB}>
              Показать ещё {hiddenNormProblemRows} отклонений
            </ShowMoreButton>
          </div>
        </div>
      )}
    </div>
  );
}
