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

export default function WarehouseTabsNav({warehouseTab, setWarehouseTab, setShowForm, btnO, btnG}) {
  return (
    <div style={{display:'flex',gap:'8px',marginBottom:'20px',flexWrap:'wrap'}}>
      {WAREHOUSE_TABS.map(([tab, label]) => (
        <button key={tab} onClick={() => {setWarehouseTab(tab);setShowForm(false);}} style={{...(warehouseTab===tab?btnO:btnG),fontSize:'12px',padding:'7px 14px'}}>
          {label}
        </button>
      ))}
    </div>
  );
}
