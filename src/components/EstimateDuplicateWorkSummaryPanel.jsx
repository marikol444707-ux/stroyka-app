import React, { useState } from 'react';
import { C, btnB, btnO, card, tbl, tblC, tblH } from '../constants/uiTheme';

export default function EstimateDuplicateWorkSummaryPanel({
  selectedEstimate,
  userRole,
  isMobile,
  showEstimateWorkSummary,
  setShowEstimateWorkSummary,
  setShowEstimateIssuesOnly,
  setMobileExpandedRenderLists,
  buildEstimateWorkSummary,
  buildEstimateMaterialSummary,
  estimateIssueDomId,
}) {
  const [summaryKind, setSummaryKind] = useState('work');
  if (!['директор', 'зам_директора'].includes(userRole) || !selectedEstimate) {
    return null;
  }

  const workSummary = buildEstimateWorkSummary(selectedEstimate);
  const materialSummary = buildEstimateMaterialSummary?.(selectedEstimate) || {groups: [], duplicateGroups: 0, totalSourceRows: 0};
  const workDuplicateGroups = (workSummary.groups || []).filter(group => group.sourceCount > 1);
  const materialDuplicateGroups = (materialSummary.groups || []).filter(group => group.sourceCount > 1);
  if (!workDuplicateGroups.length && !materialDuplicateGroups.length) {
    return null;
  }
  const activeKind = summaryKind === 'material' && materialDuplicateGroups.length
    ? 'material'
    : workDuplicateGroups.length ? 'work' : 'material';
  const isMaterialSummary = activeKind === 'material';
  const activeSummary = isMaterialSummary ? materialSummary : workSummary;
  const duplicateGroups = isMaterialSummary ? materialDuplicateGroups : workDuplicateGroups;

  const compactLimit = isMobile ? 8 : 14;
  const visibleGroups = showEstimateWorkSummary ? duplicateGroups : duplicateGroups.slice(0, compactLimit);
  const hiddenGroups = duplicateGroups.length - visibleGroups.length;
  const fmtNum = (value, max = 3) => Number(value || 0).toLocaleString('ru-RU', {maximumFractionDigits: max});
  const fmtMoney = value => Math.round(Number(value || 0)).toLocaleString('ru-RU') + ' ₽';

  const jumpToSource = source => {
    const rowId = estimateIssueDomId(selectedEstimate.id, source.sectionIndex, source.itemIndex);
    const sectionListKey = ['estimate-sections', selectedEstimate.id, 'all'].join(':');
    const groupKey = ['estimate', selectedEstimate.id, source.sectionIndex, isMaterialSummary ? 'Материалы' : 'Работы'].join(':');
    setShowEstimateIssuesOnly(false);
    setMobileExpandedRenderLists(prev => ({...prev, [sectionListKey]: true, [groupKey]: true}));
    setTimeout(() => document.getElementById(rowId)?.scrollIntoView({behavior: 'smooth', block: 'center'}), 120);
  };

  const summaryTbl = {...tbl, width: '100%', minWidth: isMobile ? '0' : '760px', tableLayout: 'fixed'};
  const summaryH = {...tblH, padding: '5px 6px', fontSize: '10px', whiteSpace: 'nowrap'};
  const summaryC = {...tblC, padding: '5px 6px', fontSize: '11px', verticalAlign: 'top'};

  const renderSources = group => group.sources.slice(0, 8).map(source => (
    <div key={`${source.sectionIndex}-${source.itemIndex}`} style={{display: 'grid', gridTemplateColumns: isMobile ? '1fr auto' : 'minmax(0,1fr) 80px 70px', gap: '6px', alignItems: 'center', padding: '5px 0', borderTop: '1px solid ' + C.border}}>
      <span style={{color: C.textSec, fontSize: '11px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: isMobile ? 'normal' : 'nowrap'}}>{source.sectionName} · строка {source.rowNumber}</span>
      <b style={{color: C.text, fontSize: '11px', whiteSpace: 'nowrap'}}>{fmtNum(source.quantity)} {source.unit}</b>
      <button type="button" onClick={() => jumpToSource(source)} style={{...btnB, padding: '4px 6px', fontSize: '10px', justifyContent: 'center'}}>К строке</button>
    </div>
  ));

  return (
    <div style={{...card, padding: isMobile ? '10px' : '12px', marginBottom: '12px', backgroundColor: C.bg}}>
      <div style={{display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: isMobile ? 'flex-start' : 'center', flexDirection: isMobile ? 'column' : 'row'}}>
        <div>
          <b style={{color: C.text, fontSize: isMobile ? '15px' : '14px'}}>🧾 Свод одинаковых позиций</b>
          <p style={{color: C.textSec, margin: '3px 0 0', fontSize: '11px'}}>
            Повторов: {activeSummary.duplicateGroups} · строк: {activeSummary.totalSourceRows}. Одинаковые {isMaterialSummary ? 'материалы' : 'работы'} суммируются здесь, сама смета не меняется.
          </p>
        </div>
        <button type="button" onClick={() => setShowEstimateWorkSummary(v => !v)} style={{...btnB, justifyContent: 'center', width: isMobile ? '100%' : 'auto', padding: '6px 10px', fontSize: '12px'}}>
          {showEstimateWorkSummary ? 'Свернуть' : 'Показать все'}
        </button>
      </div>
      <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', marginTop: '10px'}}>
        <button
          type="button"
          disabled={!workDuplicateGroups.length}
          onClick={() => setSummaryKind('work')}
          style={{...(activeKind === 'work' ? btnO : btnB), justifyContent: 'center', opacity: workDuplicateGroups.length ? 1 : 0.55}}
        >
          Работы ({workDuplicateGroups.length})
        </button>
        <button
          type="button"
          disabled={!materialDuplicateGroups.length}
          onClick={() => setSummaryKind('material')}
          style={{...(activeKind === 'material' ? btnO : btnB), justifyContent: 'center', opacity: materialDuplicateGroups.length ? 1 : 0.55}}
        >
          Материалы ({materialDuplicateGroups.length})
        </button>
      </div>
      {isMobile ? (
        <div style={{display: 'grid', gap: '6px', marginTop: '10px'}}>
          {visibleGroups.map(group => (
            <details key={group.key} style={{border: '1px solid ' + C.border, borderRadius: '8px', padding: '8px', backgroundColor: C.bgWhite}}>
              <summary style={{cursor: 'pointer', listStyle: 'none'}}>
                <div style={{display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto', gap: '8px', alignItems: 'start'}}>
                  <b style={{color: C.text, fontSize: '12px', lineHeight: 1.25, overflow: 'hidden', textOverflow: 'ellipsis'}}>{group.name}</b>
                  <b style={{color: C.warning, fontSize: '12px', whiteSpace: 'nowrap'}}>{fmtNum(group.quantity)} {group.unit}</b>
                </div>
                <span style={{color: C.textMuted, fontSize: '10px'}}>строк: {group.sourceCount}{group.basisLabel ? ` · ${group.basisLabel}` : ''} · {fmtMoney(isMaterialSummary ? group.materialSum : group.workSum)}</span>
              </summary>
              <div style={{marginTop: '6px'}}>
                {renderSources(group)}
                {group.sources.length > 8 && <span style={{color: C.textMuted, fontSize: '10px'}}>Еще источников: {group.sources.length - 8}</span>}
              </div>
            </details>
          ))}
        </div>
      ) : (
        <div style={{overflowX: 'auto', marginTop: '10px'}}>
          <table style={summaryTbl}>
            <thead>
              <tr>
                <th style={{...summaryH, width: '36%'}}>{isMaterialSummary ? 'Материал' : 'Работа'}</th>
                <th style={{...summaryH, width: '48px'}}>Строк</th>
                <th style={{...summaryH, width: '82px'}}>Объем</th>
                <th style={{...summaryH, width: '92px'}}>Сумма</th>
                <th style={{...summaryH, width: '88px'}}>Средняя</th>
                <th style={{...summaryH, width: '154px'}}>Где</th>
              </tr>
            </thead>
            <tbody>
              {visibleGroups.map(group => (
                <tr key={group.key}>
                  <td style={summaryC}>
                    <b style={{color: C.text, lineHeight: 1.25}}>{group.name}</b>
                    <div style={{color: C.textMuted, fontSize: '10px', marginTop: '2px'}}>{group.basisLabel ? `${group.basisLabel} · ` : ''}{group.sectionNames.slice(0, 3).join(', ')}{group.sectionNames.length > 3 ? '...' : ''}</div>
                  </td>
                  <td style={{...summaryC, fontWeight: '700', color: C.warning}}>{group.sourceCount}</td>
                  <td style={{...summaryC, fontWeight: '700', color: C.text}}>{fmtNum(group.quantity)} {group.unit}</td>
                  <td style={{...summaryC, fontWeight: '700', color: C.success, whiteSpace: 'nowrap'}}>{fmtMoney(isMaterialSummary ? group.materialSum : group.workSum)}</td>
                  <td style={{...summaryC, color: C.textSec, whiteSpace: 'nowrap'}}>{fmtMoney(group.unitPriceAvg)} / {group.unit}</td>
                  <td style={summaryC}>
                    <details>
                      <summary style={{cursor: 'pointer', color: C.info, fontSize: '11px'}}>источники</summary>
                      <div style={{marginTop: '4px'}}>
                        {renderSources(group)}
                        {group.sources.length > 8 && <span style={{color: C.textMuted, fontSize: '10px'}}>Еще источников: {group.sources.length - 8}</span>}
                      </div>
                    </details>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {hiddenGroups > 0 && (
        <button type="button" onClick={() => setShowEstimateWorkSummary(true)} style={{...btnO, justifyContent: 'center', marginTop: '8px', width: '100%', padding: '6px 10px', fontSize: '12px'}}>
          Показать еще {hiddenGroups}
        </button>
      )}
    </div>
  );
}
