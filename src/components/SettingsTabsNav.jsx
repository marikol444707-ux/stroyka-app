import React from 'react';

const SETTINGS_TABS = [
  ['requisites', 'Реквизиты компании'],
  ['documents', 'Юр. документы'],
];

export default function SettingsTabsNav({settingsTab, setSettingsTab, btnO, btnG}) {
  return (
    <div style={{display:'flex',gap:'8px',marginBottom:'20px',flexWrap:'wrap'}}>
      {SETTINGS_TABS.map(([tab, label])=>(
        <button key={tab} onClick={()=>setSettingsTab(tab)} style={{...(settingsTab===tab?btnO:btnG),fontSize:'12px',padding:'7px 14px'}}>
          {label}
        </button>
      ))}
    </div>
  );
}
