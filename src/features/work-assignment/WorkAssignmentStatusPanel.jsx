import React, { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronUp, Trash2 } from 'lucide-react';
import {
  assignmentsForEstimate,
  contractName,
  formatMoney,
  formatQty,
  toNumber,
  workAssignmentStats,
} from './workAssignmentUtils';

export default function WorkAssignmentStatusPanel({
  selectedEstimate,
  brigadeContracts = [],
  brigadeContractItems = [],
  API,
  loadAll,
  C,
  card,
  btnG,
  btnR,
  isMobile,
  showLeadership,
}) {
  const [busyId, setBusyId] = useState(null);
  const [expandedEstimateId, setExpandedEstimateId] = useState(null);
  const [view, setView] = useState(null);
  const [pendingRemovalId, setPendingRemovalId] = useState(null);
  const [removedIds, setRemovedIds] = useState({});
  const [actionError, setActionError] = useState('');
  const [notice, setNotice] = useState('');
  const sourceRows = useMemo(
    () => assignmentsForEstimate(selectedEstimate, brigadeContractItems, brigadeContracts),
    [selectedEstimate, brigadeContractItems, brigadeContracts]
  );
  const rows = useMemo(() => sourceRows.map(row => ({
    ...row,
    assignments: row.assignments.filter(item => !removedIds[item.id]),
  })), [sourceRows, removedIds]);
  const stats = useMemo(() => workAssignmentStats(rows), [rows]);
  const rowsExpanded = selectedEstimate?.id != null && String(expandedEstimateId) === String(selectedEstimate.id);
  const activeView = view || (stats.assignedRows ? 'assigned' : 'unassigned');
  const visibleRows = rows.filter(row => activeView === 'assigned' ? row.assignments.length > 0 : row.assignments.length === 0);

  useEffect(() => {
    setView(null);
    setPendingRemovalId(null);
    setRemovedIds({});
    setActionError('');
    setNotice('');
  }, [selectedEstimate?.id]);

  if (!showLeadership || !selectedEstimate || !rows.length) return null;

  const removeAssignment = async (assignment) => {
    setActionError('');
    setNotice('');
    setBusyId(assignment.id);
    try {
      const response = await fetch(API + '/brigade-contract-items/' + assignment.id, {method: 'DELETE'});
      const data = await response.json().catch(() => ({}));
      if (!response.ok || data.ok === false) {
        setActionError({id: assignment.id, message: typeof data.detail === 'string' ? data.detail : 'Не удалось снять назначение. Повторите попытку.'});
        return;
      }
      setRemovedIds(previous => ({...previous, [assignment.id]: true}));
      setPendingRemovalId(null);
      try {
        await loadAll();
        setNotice('Назначение снято. Работа снова доступна для выдачи.');
      } catch (_) {
        setNotice('Назначение снято, но список не обновился. Обновите страницу.');
      }
    } catch (_) {
      setActionError({id: assignment.id, message: 'Не удалось снять назначение. Проверьте соединение и повторите попытку.'});
    } finally {
      setBusyId(null);
    }
  };

  const statItems = [
    {label: 'Выдано работ', value: stats.assignedRows, color: C.success},
    {label: 'Осталось выдать', value: stats.unassignedRows, color: stats.unassignedRows ? C.warning : C.success},
    {label: 'Исполнителям по плану', value: formatMoney(stats.planAmount), detail: `Выполнено: ${formatMoney(stats.doneAmount)}`, color: C.text},
  ];

  return (
    <div style={{...card, padding: '14px', marginBottom: '14px', border: '1px solid ' + C.border, backgroundColor: C.bgWhite}}>
      <div style={{marginBottom: '12px'}}>
        <div>
          <div style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
            {stats.unassignedRows ? <AlertTriangle size={17} color={C.warning} /> : <CheckCircle2 size={17} color={C.success} />}
            <b style={{color: C.text, fontSize: '14px'}}>Назначенные работы</b>
          </div>
          <p style={{color: C.textSec, fontSize: '12px', margin: '4px 0 0'}}>Что уже выдано исполнителям и что ещё нужно назначить.</p>
        </div>
      </div>

      <div style={{display: 'grid', gridTemplateColumns: isMobile ? 'repeat(2,minmax(0,1fr))' : 'repeat(3,minmax(0,1fr))', gap: '8px', marginBottom: '12px'}}>
        {statItems.map(item => (
          <div key={item.label} style={{gridColumn: isMobile && item.detail ? '1 / -1' : undefined, padding: '9px 10px', borderRadius: '8px', border: '1px solid ' + C.border, backgroundColor: C.bgWhite}}>
            <p style={{margin: '0 0 4px', color: C.textMuted, fontSize: '10px'}}>{item.label}</p>
            <b style={{color: item.color, fontSize: '13px'}}>{item.value}</b>
            {item.detail && <span style={{display: 'block', color: C.textSec, fontSize: '10px', marginTop: '4px'}}>{item.detail}</span>}
          </div>
        ))}
      </div>

      {stats.duplicateRows > 0 && (
        <div style={{padding: '8px 10px', borderRadius: '8px', border: '1px solid ' + C.dangerBorder, backgroundColor: C.dangerLight, color: C.danger, fontSize: '12px', marginBottom: '10px'}}>
          {stats.duplicateRows} {stats.duplicateRows === 1 ? 'работа выдана' : 'работы выданы'} нескольким исполнителям. Проверьте их перед закрытием объёмов.
        </div>
      )}

      {notice && <div role="status" style={{color: C.success, fontSize: '12px', marginBottom: '10px'}}>{notice}</div>}

      <button
        type="button"
        aria-expanded={rowsExpanded}
        onClick={() => setExpandedEstimateId(rowsExpanded ? null : selectedEstimate.id)}
        style={{...btnG, width: '100%', justifyContent: 'center', marginBottom: rowsExpanded ? '10px' : 0}}
      >
        {rowsExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        {rowsExpanded ? 'Скрыть работы' : `Показать работы (${stats.totalRows})`}
      </button>

      {rowsExpanded && <div>
        <div role="group" aria-label="Фильтр работ" style={{display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '10px'}}>
          <button type="button" aria-pressed={activeView === 'assigned'} onClick={() => {setView('assigned'); setPendingRemovalId(null); setActionError('');}} style={activeView === 'assigned' ? {...btnG, borderColor: C.successBorder, color: C.success} : btnG}>Выдано ({stats.assignedRows})</button>
          <button type="button" aria-pressed={activeView === 'unassigned'} onClick={() => {setView('unassigned'); setPendingRemovalId(null); setActionError('');}} style={activeView === 'unassigned' ? {...btnG, borderColor: C.warningBorder, color: C.warning} : btnG}>Не выдано ({stats.unassignedRows})</button>
        </div>
        <div style={{display: 'grid', gap: '7px', maxHeight: '310px', overflowY: 'auto'}}>
        {visibleRows.map(row => {
          const assigned = row.assignments.length > 0;
          return (
            <div key={row.id} style={{display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'minmax(0,1.25fr) minmax(220px,1fr)', gap: '8px', padding: '9px 10px', borderRadius: '8px', border: '1px solid ' + (assigned ? C.successBorder : C.warningBorder), backgroundColor: C.bgWhite}}>
              <div style={{minWidth: 0}}>
                <b style={{display: 'block', color: C.text, fontSize: '12px', overflow: 'hidden', textOverflow: 'ellipsis'}}>{row.name}</b>
                <span style={{color: C.textSec, fontSize: '11px'}}>{row.section} · {formatQty(row.quantity, row.unit)} · смета {formatMoney(row.priceSmeta)}/ед.</span>
                {row.assignments.length > 1 && <span style={{display: 'block', color: C.danger, fontSize: '11px'}}>Выдано {row.assignments.length} исполнителям</span>}
              </div>
              <div style={{display: 'grid', gap: '5px'}}>
                {!assigned && (
                  <span style={{color: C.warning, fontSize: '12px', fontWeight: 700}}>Не назначено</span>
                )}
                {row.assignments.map(assignment => {
                  const contract = assignment.contract || {};
                  const done = toNumber(assignment.doneQuantity);
                  const qty = toNumber(assignment.quantity);
                  const canRemove = done <= 0;
                  const performer = contractName(contract) || contractName(assignment) || 'Исполнитель';
                  return (
                    <div key={assignment.id} style={{display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'minmax(0,1fr) auto', gap: '6px', alignItems: 'center', padding: '8px', borderRadius: '7px', backgroundColor: C.bg, border: '1px solid ' + C.border}}>
                      <span style={{color: C.text, fontSize: '11px', minWidth: 0}}>
                        <b>{performer}</b>
                        <span style={{color: C.textSec}}> · {formatQty(qty, assignment.unit)} · {formatMoney(assignment.priceBrigade)}/ед. · сделано {formatQty(done, assignment.unit)}</span>
                      </span>
                      {canRemove ? <button
                        type="button"
                        aria-label={'Снять назначение: ' + performer}
                        onClick={() => {setPendingRemovalId(assignment.id); setActionError('');}}
                        disabled={busyId != null}
                        style={{...btnR, padding: '4px 7px', fontSize: '11px'}}
                      ><Trash2 size={12} />Снять выдачу</button> : <span style={{color: C.textSec, fontSize: '11px'}}>Снять нельзя: есть выполненный объём</span>}
                      {pendingRemovalId === assignment.id && <div style={{gridColumn: '1 / -1', display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap', color: C.textSec, fontSize: '11px'}}>
                        <span>Работа снова станет доступна для назначения.</span>
                        <button type="button" disabled={busyId != null} onClick={() => removeAssignment(assignment)} style={{...btnR, padding: '4px 7px'}}>Подтвердить снятие</button>
                        <button type="button" disabled={busyId != null} onClick={() => setPendingRemovalId(null)} style={{...btnG, padding: '4px 7px'}}>Отмена</button>
                      </div>}
                      {actionError?.id === assignment.id && <div role="alert" style={{gridColumn: '1 / -1', color: C.danger, fontSize: '11px'}}>{actionError.message}</div>}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
        {!visibleRows.length && <div style={{padding: '16px', color: C.textSec, fontSize: '12px'}}>В этом списке пока нет работ.</div>}
        </div>
      </div>}
    </div>
  );
}
