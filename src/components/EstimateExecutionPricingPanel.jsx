import React from 'react';
import { C, btnG, btnO, card, inp } from '../constants/uiTheme';

export default function EstimateExecutionPricingPanel({
  priceStats,
  executionPriceFillPercent,
  setExecutionPriceFillPercent,
  fillSelectedEstimateExecutionPrices,
  isMobile,
}) {
  return (
    <div style={{...card, padding: '12px 14px', marginBottom: '12px', display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'minmax(260px,1fr) 120px auto auto', gap: '10px', alignItems: 'center', backgroundColor: C.bg}}>
      <div>
        <b style={{color: C.text, fontSize: '14px'}}>💵 Внутренние цены исполнителям</b>
        <p style={{color: C.textSec, margin: '3px 0 0', fontSize: '12px'}}>
          Работ: {priceStats.workRows} · заполнено: {priceStats.pricedRows} · пустых: {priceStats.emptyRows}. Цена сохраняется в каждой строке и идет в ЖПР/акты исполнителя.
        </p>
      </div>
      <label style={{display: 'flex', alignItems: 'center', gap: '6px', color: C.textSec, fontSize: '12px'}}>
        <input type="number" min="1" max="100" step="1" value={executionPriceFillPercent} onChange={e => setExecutionPriceFillPercent(e.target.value)} style={{...inp, marginBottom: 0, width: '78px'}} />
        %
      </label>
      <button type="button" onClick={() => fillSelectedEstimateExecutionPrices(false)} disabled={!priceStats.emptyRows} style={{...btnO, justifyContent: 'center', opacity: priceStats.emptyRows ? 1 : 0.55}}>
        Заполнить пустые
      </button>
      <button type="button" onClick={() => window.confirm('Перезаписать внутренние цены по всем строкам работ этой сметы?') && fillSelectedEstimateExecutionPrices(true)} disabled={!priceStats.workRows} style={{...btnG, justifyContent: 'center', opacity: priceStats.workRows ? 1 : 0.55}}>
        Пересчитать все
      </button>
    </div>
  );
}
