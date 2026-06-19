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
  return (
    <div style={{
      display:isMobile?'grid':'flex',
      gridTemplateColumns:isMobile?'repeat(2,minmax(0,1fr))':undefined,
      gap:isMobile?'8px':'8px',
      margin:'0 auto 20px',
      flexWrap:'wrap',
      width:'100%',
      maxWidth:isMobile?'420px':'100%',
      justifyContent:isMobile?'center':'flex-start',
    }}>
      {WAREHOUSE_TABS.map(([tab, label]) => (
        <button key={tab} onClick={() => {setWarehouseTab(tab);setShowForm(false);}} style={{...(warehouseTab===tab?btnO:btnG),fontSize:isMobile?'12px':'12px',padding:isMobile?'9px 8px':'7px 14px',justifyContent:'center',width:isMobile?'100%':undefined,minWidth:0}}>
          {label}
        </button>
      ))}
    </div>
  );
}
