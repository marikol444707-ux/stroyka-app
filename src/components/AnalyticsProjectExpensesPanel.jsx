import React from 'react';

export default function AnalyticsProjectExpensesPanel({C, card, projects, expByCategory}) {
  return (
    <div style={{...card,padding:'20px',marginBottom:'20px'}}>
      <h4 style={{color:C.text,marginBottom:'15px',fontSize:'14px',fontWeight:'700'}}>Расходы по проектам</h4>
      {projects.filter(p=>p.status==='В работе').map(p=>{
        const cat = expByCategory(p.name);
        const total = Object.values(cat).reduce((s,v)=>s+v,0);
        const pct = p.budget>0?Math.min(100,Math.round(total/p.budget*100)):0;
        return (
          <div key={p.id} style={{marginBottom:'14px'}}>
            <div style={{display:'flex',justifyContent:'space-between',marginBottom:'5px'}}>
              <b style={{fontSize:'13px',color:C.text}}>{p.name}</b>
              <span style={{fontSize:'12px',color:total>p.budget?C.danger:C.textSec}}>
                {total.toLocaleString()+' / '+p.budget.toLocaleString()+' ₽ ('+pct+'%)'}
              </span>
            </div>
            <div style={{backgroundColor:C.bgGray,borderRadius:'6px',height:'10px'}}>
              <div style={{backgroundColor:pct>80?C.danger:pct>60?C.warning:C.success,width:pct+'%',height:'100%',borderRadius:'6px'}}/>
            </div>
          </div>
        );
      })}
    </div>
  );
}
