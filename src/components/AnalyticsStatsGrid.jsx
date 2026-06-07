import React from 'react';

export default function AnalyticsStatsGrid({C, card, projects, staff, suppliers, contracts}) {
  const stats = [
    {label:'Всего проектов',value:projects.length,icon:'📋'},
    {label:'В работе',value:projects.filter(p=>p.status==='В работе').length,icon:'🔨'},
    {label:'Завершено',value:projects.filter(p=>p.status==='Завершён').length,icon:'✅'},
    {label:'Сотрудников',value:staff.length,icon:'👷'},
    {label:'Поставщиков',value:suppliers.length,icon:'🚛'},
    {label:'Договоров',value:contracts.length,icon:'📄'},
  ];

  return (
    <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:'16px',marginBottom:'24px'}}>
      {stats.map((s,i)=>(
        <div key={i} style={{...card,padding:'16px'}}>
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
            <div>
              <p style={{margin:'0 0 4px',color:C.textSec,fontSize:'12px'}}>{s.label}</p>
              <b style={{fontSize:'20px',color:C.text}}>{s.value}</b>
            </div>
            <span style={{fontSize:'24px'}}>{s.icon}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
