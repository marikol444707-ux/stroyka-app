import React from 'react';

export default function ProjectBrigadeCalculationSummary({
  brigadeContractItems = [],
  showFinance = false,
  C,
  card,
}) {
  const brigadeTotal = brigadeContractItems.reduce((sum, item) => sum + Number(item.quantity || 0) * Number(item.priceBrigade || 0), 0);
  const estimateTotal = brigadeContractItems.reduce((sum, item) => sum + Number(item.quantity || 0) * Number(item.priceSmeta || 0), 0);
  const economy = estimateTotal - brigadeTotal;

  if (brigadeTotal === 0 && estimateTotal === 0) {
    return (
      <div style={{...card, padding: '14px', marginBottom: '16px', backgroundColor: C.bg, border: '1.5px dashed ' + C.border, textAlign: 'center'}}>
        <p style={{margin: 0, color: C.textMuted, fontSize: '13px'}}>
          📋 Расчёт пустой. Нажмите <b>«Подгрузить из прайса»</b> или добавьте позиции вручную ниже.
        </p>
      </div>
    );
  }

  return (
    <div style={{...card, padding: '16px', marginBottom: '16px', backgroundColor: C.accentLight, border: '1.5px solid ' + C.accentBorder}}>
      <div style={{display: 'grid', gridTemplateColumns: showFinance ? 'repeat(3,1fr)' : '1fr', gap: '12px'}}>
        <div>
          <p style={{color: C.textSec, fontSize: '12px', margin: '0 0 4px'}}>Бригаде по договору</p>
          <b style={{color: C.accent, fontSize: '16px'}}>{brigadeTotal.toLocaleString('ru-RU') + ' ₽'}</b>
        </div>
        <div style={{display: showFinance ? 'block' : 'none'}}>
          <p style={{color: C.textSec, fontSize: '12px', margin: '0 0 4px'}}>По смете заказчика</p>
          <b style={{color: C.text, fontSize: '16px'}}>{estimateTotal.toLocaleString('ru-RU') + ' ₽'}</b>
        </div>
        <div style={{display: showFinance ? 'block' : 'none'}}>
          <p style={{color: C.textSec, fontSize: '12px', margin: '0 0 4px'}}>Экономия</p>
          <b style={{color: economy > 0 ? C.success : C.textMuted, fontSize: '16px'}}>{economy.toLocaleString('ru-RU') + ' ₽'}</b>
        </div>
      </div>
    </div>
  );
}
