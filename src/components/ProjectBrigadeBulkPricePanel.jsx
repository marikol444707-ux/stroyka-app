import React from 'react';
import { API } from '../api';

export default function ProjectBrigadeBulkPricePanel({
  show = false,
  brigadeCoef,
  setBrigadeCoef,
  brigadeContractItems = [],
  setBrigadeContractItems,
  C,
  card,
  inp,
  btnO,
  btnG,
}) {
  const updateItems = async (items) => {
    setBrigadeContractItems(items);
    for (const item of items) {
      await fetch(API + '/brigade-contract-items/' + item.id, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(item),
      });
    }
  };

  const applyCoefficient = async () => {
    if (!window.confirm('Применить коэффициент ' + brigadeCoef + ' ко всем позициям?')) return;

    const updated = brigadeContractItems.map(item => ({
      ...item,
      priceBrigade: Math.round(Number(item.priceSmeta || 0) * Number(brigadeCoef || 0.6)),
    }));
    await updateItems(updated);
    alert('Цены обновлены!');
  };

  const resetPrices = async () => {
    if (!window.confirm('Сбросить все цены бригаде в 0?')) return;

    const updated = brigadeContractItems.map(item => ({...item, priceBrigade: 0}));
    await updateItems(updated);
  };

  return (
    <div style={{...card, padding: '12px 16px', marginBottom: '8px', backgroundColor: C.bg, display: show ? 'flex' : 'none', gap: '10px', alignItems: 'center', flexWrap: 'wrap'}}>
      <b style={{color: C.text, fontSize: '13px'}}>Массовое выставление цены:</b>
      <span style={{fontSize: '12px', color: C.textSec}}>Коэффициент от сметной цены:</span>
      <input
        type="number"
        inputMode="decimal"
        value={brigadeCoef}
        onChange={e => setBrigadeCoef(e.target.value)}
        style={{...inp, marginBottom: 0, width: '80px', fontSize: '12px', padding: '4px 8px'}}
        step="0.05"
        min="0.1"
        max="1"
      />
      <span style={{fontSize: '12px', color: C.textSec}}>({Math.round(brigadeCoef * 100)}% от сметы)</span>
      <button onClick={applyCoefficient} style={{...btnO, padding: '6px 14px', fontSize: '12px'}}>Применить ко всем</button>
      <button onClick={resetPrices} style={{...btnG, padding: '6px 14px', fontSize: '12px'}}>Сбросить цены</button>
    </div>
  );
}
