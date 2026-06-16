import React from 'react';

export default function DashboardStatsGrid({
  dashboardProjects,
  avgProg,
  totalDone,
  setActivePage,
  navigateTo,
  setAccountingTab,
}) {
  const cards = [
    {label:'Объекты',value:dashboardProjects.length,sub:'активных проектов',color:'#fdba74',bg:'rgba(234,88,12,.14)',border:'rgba(234,88,12,.32)',page:'projects'},
    {label:'Прогресс',value:avgProg+'%',sub:'среднее по объектам',color:'#86efac',bg:'rgba(34,197,94,.12)',border:'rgba(34,197,94,.28)',page:'projects'},
    {label:'Себестоимость',value:totalDone>=1000000?(totalDone/1000000).toFixed(1)+' млн':Math.round(totalDone/1000)+' тыс',sub:'затраты по всем объектам',color:'#bef264',bg:'rgba(132,204,22,.12)',border:'rgba(132,204,22,.28)',page:'accounting',tab:'payments'},
    {label:'Бюджет',value:(()=>{const t=dashboardProjects.reduce((s,p)=>s+Number(p.budget||0),0);return t>=1000000?Math.round(t/1000000)+' млн':Math.round(t/1000)+' тыс';})(),sub:'общий бюджет ₽',color:'#fca5a5',bg:'rgba(239,68,68,.12)',border:'rgba(239,68,68,.28)',page:'accounting',tab:'summary'},
  ];

  return (
    <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:'16px',marginBottom:'20px'}}>
      {cards.map((k,i)=>(
        <div key={i} onClick={()=>{if(k.page){(navigateTo || setActivePage)(k.page);if(k.tab)setAccountingTab(k.tab);}}} style={{background:'rgba(17,24,39,.88)',border:'1px solid rgba(148,163,184,.18)',borderRadius:'22px',padding:'20px',backdropFilter:'blur(24px)',boxShadow:'0 24px 80px rgba(0,0,0,.35)',cursor:'pointer',transition:'transform 0.15s, box-shadow 0.15s'}} onMouseEnter={e=>{e.currentTarget.style.transform='translateY(-2px)';e.currentTarget.style.boxShadow='0 30px 90px rgba(0,0,0,.45)';}} onMouseLeave={e=>{e.currentTarget.style.transform='';e.currentTarget.style.boxShadow='0 24px 80px rgba(0,0,0,.35)';}}>
          <span style={{display:'inline-flex',borderRadius:'999px',padding:'5px 10px',fontSize:'11px',fontWeight:'700',background:k.bg,color:k.color,border:'1px solid '+k.border}}>{k.label}</span>
          <div style={{fontSize:'34px',fontWeight:'800',letterSpacing:'-.04em',margin:'10px 0 4px',color:'#f8fafc'}}>{k.value}</div>
          <div style={{color:'#94a3b8',fontSize:'13px'}}>{k.sub}</div>
        </div>
      ))}
    </div>
  );
}
