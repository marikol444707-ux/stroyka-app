import React from 'react';

const WEATHER_TABS = [
  ['log', 'Журнал погоды'],
  ['jpr', 'ЖПР'],
];

export default function WeatherTabsNav({weatherTab, setWeatherTab, btnO, btnG}) {
  return (
    <div style={{display:'flex',gap:'8px',marginBottom:'20px',flexWrap:'wrap'}}>
      {WEATHER_TABS.map(([tab, label])=>(
        <button key={tab} onClick={()=>setWeatherTab(tab)} style={{...(weatherTab===tab?btnO:btnG),fontSize:'12px',padding:'7px 14px'}}>
          {label}
        </button>
      ))}
    </div>
  );
}
