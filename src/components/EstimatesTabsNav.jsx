import React from 'react';

const ESTIMATES_TABS = [
  ['list', '📋 Сметы'],
  ['import', '📥 Импорт Гранд Смета'],
  ['norms', '⚙️ Нормы материалов'],
];

export default function EstimatesTabsNav({estimatesTab, setEstimatesTab, setActivePage, btnO, btnG}) {
  return (
    <div style={{display:'flex',gap:'8px',marginBottom:'20px',flexWrap:'wrap'}}>
      {ESTIMATES_TABS.map(([tab, label]) => (
        <button
          key={tab}
          onClick={() => setEstimatesTab(tab)}
          style={{...(estimatesTab===tab?btnO:btnG),fontSize:'12px',padding:'7px 14px'}}
        >
          {label}
        </button>
      ))}
      <button onClick={() => setActivePage('pricelists')} style={{...btnG,fontSize:'12px',padding:'7px 14px'}}>
        🏷️ Прайс-листы
      </button>
    </div>
  );
}
