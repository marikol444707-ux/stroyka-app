import React from 'react';

const WAREHOUSE_TABS = [
  ['control', 'Контроль'],
  ['objects', 'Объекты'],
  ['main', 'Основной склад'],
  ['move', 'Перемещение'],
  ['invoices', 'Накладные'],
  ['history', 'История'],
  ['tools', 'Инструменты'],
  ['inventory', 'Инвентаризация'],
  ['warehouses', 'Склады'],
];

export default function WarehouseTabsNav({warehouseTab, setWarehouseTab, setShowForm, btnO, btnG, isMobile}) {
  const touchCompact = typeof window !== 'undefined'
    && (window.visualViewport?.width || window.innerWidth || 0) < 1100
    && (
      (typeof window.matchMedia === 'function' && window.matchMedia('(pointer: coarse)').matches)
      || (typeof navigator !== 'undefined' && /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent || ''))
    );
  const compactTabs = isMobile || touchCompact;
  return (
    <div style={{
      display:compactTabs?'grid':'flex',
      gridTemplateColumns:compactTabs?'repeat(2,minmax(0,1fr))':undefined,
      gap:compactTabs?'8px':'8px',
      margin:'0 auto 20px',
      flexWrap:'wrap',
      width:'100%',
      maxWidth:compactTabs?'min(720px,100%)':'100%',
      justifyContent:compactTabs?'center':'flex-start',
    }}>
      {WAREHOUSE_TABS.map(([tab, label]) => (
        <button key={tab} onClick={() => {setWarehouseTab(tab);setShowForm(false);}} style={{...(warehouseTab===tab?btnO:btnG),fontSize:compactTabs?'11px':'12px',padding:compactTabs?'9px 6px':'7px 14px',justifyContent:'center',width:compactTabs?'100%':undefined,minWidth:0,whiteSpace:'normal',lineHeight:1.2}}>
          {label}
        </button>
      ))}
    </div>
  );
}
