import React from 'react';

export default function ProjectBrigadeBudgetSummary({
  projectName,
  brigadeContracts = [],
  smetaTotal = 0,
  C,
  card,
}) {
  const projectContracts = brigadeContracts.filter(bc => bc.projectName === projectName);
  const brigadeTotal = projectContracts.reduce((sum, bc) => sum + Number(bc.totalAmount || 0), 0);

  if (projectContracts.length === 0 || smetaTotal === 0) return null;

  const percent = Math.round((brigadeTotal / smetaTotal) * 100);
  const isOverBudget = brigadeTotal > smetaTotal;
  const bgColor = isOverBudget ? C.dangerLight : percent > 85 ? C.warningLight : C.successLight;
  const borderColor = isOverBudget ? C.dangerBorder : percent > 85 ? C.warningBorder : C.successBorder;

  return (
    <div style={{...card, padding: '12px', marginBottom: '14px', backgroundColor: bgColor, border: '1.5px solid ' + borderColor}}>
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px', flexWrap: 'wrap'}}>
        <div>
          <b style={{color: C.text, fontSize: '13px'}}>📊 Сумма работ бригадам vs смета: {percent}%</b>
          <p style={{color: C.textSec, margin: '2px 0 0', fontSize: '11px'}}>
            По {projectContracts.length} бригадам: {Math.round(brigadeTotal).toLocaleString('ru-RU') + ' ₽'} · По смете заказчика: {Math.round(smetaTotal).toLocaleString('ru-RU') + ' ₽'}
          </p>
        </div>
        {isOverBudget && (
          <span style={{padding: '4px 10px', backgroundColor: C.danger, color: 'white', borderRadius: '10px', fontSize: '11px', fontWeight: '700'}}>
            ⚠️ ПРЕВЫШЕНА СМЕТА
          </span>
        )}
      </div>
      {isOverBudget && (
        <p style={{color: C.danger, margin: '8px 0 0', fontSize: '11px', lineHeight: 1.4}}>
          Суммарная стоимость работ бригадам превысила смету заказчика. Уменьшите цены бригадам или согласуйте увеличение сметы с заказчиком (доп.соглашение).
        </p>
      )}
    </div>
  );
}
