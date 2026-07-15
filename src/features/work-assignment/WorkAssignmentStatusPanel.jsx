import React, { useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, Trash2 } from 'lucide-react';
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
  const rows = useMemo(
    () => assignmentsForEstimate(selectedEstimate, brigadeContractItems, brigadeContracts),
    [selectedEstimate, brigadeContractItems, brigadeContracts]
  );
  const stats = useMemo(() => workAssignmentStats(rows), [rows]);

  if (!showLeadership || !selectedEstimate || !rows.length) return null;

  const removeAssignment = async (assignment) => {
    if (toNumber(assignment.doneQuantity) > 0) {
      alert('Нельзя снять назначение: мастер уже отправлял объем по этой строке. Сначала разберите ЖПР/акт.');
      return;
    }
    const name = assignment.name || assignment.description || 'позицию';
    if (!window.confirm('Снять назначение «' + name + '»?')) return;
    setBusyId(assignment.id);
    try {
      const token = localStorage.getItem('authToken');
      const headers = token ? {Authorization: 'Bearer ' + token} : undefined;
      const response = await fetch(API + '/brigade-contract-items/' + assignment.id, {method: 'DELETE', headers});
      const data = await response.json().catch(() => ({}));
      if (!response.ok || data.ok === false) {
        alert(data.detail || 'Не удалось снять назначение');
        return;
      }
      await loadAll();
    } finally {
      setBusyId(null);
    }
  };

  const statItems = [
    {label: 'Строк работ', value: stats.totalRows, color: C.text},
    {label: 'Назначено', value: stats.assignedRows, color: C.success},
    {label: 'Не выдано', value: stats.unassignedRows, color: stats.unassignedRows ? C.warning : C.success},
    {label: 'Нарядов по строкам', value: stats.assignmentCount, color: C.accent},
    {label: 'План мастерам', value: formatMoney(stats.planAmount), color: C.text},
    {label: 'Выполнено', value: formatMoney(stats.doneAmount), color: C.success},
  ];

  return (
    <div style={{...card, padding: '14px', marginBottom: '14px', border: '1.5px solid ' + (stats.unassignedRows ? C.warningBorder : C.successBorder), backgroundColor: stats.unassignedRows ? C.warningLight : C.successLight}}>
      <div style={{marginBottom: '12px'}}>
        <div>
          <div style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
            {stats.unassignedRows ? <AlertTriangle size={17} color={C.warning} /> : <CheckCircle2 size={17} color={C.success} />}
            <b style={{color: C.text, fontSize: '14px'}}>Назначенные работы</b>
          </div>
          <p style={{color: C.textSec, fontSize: '12px', margin: '4px 0 0'}}>
            Контроль строк, которые уже выданы исполнителям, и оставшихся неназначенных работ.
          </p>
        </div>
      </div>

      <div style={{display: 'grid', gridTemplateColumns: isMobile ? 'repeat(2,minmax(0,1fr))' : 'repeat(6,minmax(0,1fr))', gap: '8px', marginBottom: '12px'}}>
        {statItems.map(item => (
          <div key={item.label} style={{padding: '9px 10px', borderRadius: '8px', border: '1px solid ' + C.border, backgroundColor: C.bgWhite}}>
            <p style={{margin: '0 0 4px', color: C.textMuted, fontSize: '10px'}}>{item.label}</p>
            <b style={{color: item.color, fontSize: '13px'}}>{item.value}</b>
          </div>
        ))}
      </div>

      {stats.duplicateRows > 0 && (
        <div style={{padding: '8px 10px', borderRadius: '8px', border: '1px solid ' + C.dangerBorder, backgroundColor: C.dangerLight, color: C.danger, fontSize: '12px', marginBottom: '10px'}}>
          Есть строки, назначенные нескольким исполнителям. Проверьте их перед закрытием объемов.
        </div>
      )}

      <div style={{display: 'grid', gap: '7px', maxHeight: '310px', overflowY: 'auto'}}>
        {rows.map(row => {
          const assigned = row.assignments.length > 0;
          return (
            <div key={row.id} style={{display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'minmax(0,1.25fr) minmax(220px,1fr)', gap: '8px', padding: '9px 10px', borderRadius: '8px', border: '1px solid ' + (assigned ? C.successBorder : C.warningBorder), backgroundColor: C.bgWhite}}>
              <div style={{minWidth: 0}}>
                <b style={{display: 'block', color: C.text, fontSize: '12px', overflow: 'hidden', textOverflow: 'ellipsis'}}>{row.name}</b>
                <span style={{color: C.textSec, fontSize: '11px'}}>{row.section} · {formatQty(row.quantity, row.unit)} · смета {formatMoney(row.priceSmeta)}/ед.</span>
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
                    <div key={assignment.id} style={{display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'minmax(0,1fr) auto', gap: '6px', alignItems: 'center', padding: '6px 7px', borderRadius: '7px', backgroundColor: C.bg, border: '1px solid ' + C.border}}>
                      <span style={{color: C.text, fontSize: '11px', minWidth: 0}}>
                        <b>{performer}</b>
                        <span style={{color: C.textSec}}> · {formatQty(qty, assignment.unit)} · {formatMoney(assignment.priceBrigade)}/ед. · сделано {formatQty(done, assignment.unit)}</span>
                      </span>
                      <button
                        type="button"
                        onClick={() => removeAssignment(assignment)}
                        disabled={!canRemove || busyId === assignment.id}
                        title={canRemove ? 'Снять назначение' : 'Нельзя снять: уже есть выполненный объем'}
                        style={{...(canRemove ? btnR : btnG), padding: '4px 7px', fontSize: '11px', opacity: canRemove ? 1 : 0.55}}
                      >
                        <Trash2 size={12} />
                        Снять
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
