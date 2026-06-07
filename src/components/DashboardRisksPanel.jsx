import React from 'react';

export default function DashboardRisksPanel({
  risks,
  setShowReimburseModal,
  setActivePage,
  setWarehouseTab,
}) {
  return (
    <div style={{background:'rgba(17,24,39,.88)',border:'1px solid rgba(148,163,184,.18)',borderRadius:'22px',padding:'20px',backdropFilter:'blur(24px)'}}>
      <h2 style={{margin:'0 0 12px',fontSize:'17px',color:'#f8fafc',display:'flex',alignItems:'center',gap:'8px'}}>⚠️ Предупреждения системы {risks.length>0&&<span style={{fontSize:'12px',padding:'2px 8px',borderRadius:'10px',background:'rgba(239,68,68,.2)',color:'#fca5a5',fontWeight:'700'}}>{risks.length}</span>}</h2>
      {risks.length>0?risks.map((r,i)=>{
        const cdng=r.severity==='danger';
        const isClickable = r.page || r.action;
        const handleClick = () => {
          if (r.action==='reimburse') { setShowReimburseModal(true); return; }
          if (r.page) { setActivePage(r.page); if (r.tab) setWarehouseTab(r.tab); }
        };
        return(<div key={i} onClick={isClickable?handleClick:undefined} style={{padding:'10px 12px',borderRadius:'12px',background:cdng?'rgba(239,68,68,.10)':'rgba(245,158,11,.10)',border:'1px solid '+(cdng?'rgba(239,68,68,.22)':'rgba(245,158,11,.24)'),color:cdng?'#fca5a5':'#fcd34d',fontSize:'12px',marginBottom:'8px',display:'flex',gap:'8px',alignItems:'flex-start',cursor:isClickable?'pointer':'default',transition:'transform 0.15s'}} onMouseEnter={e=>{if(isClickable) e.currentTarget.style.transform='translateX(2px)';}} onMouseLeave={e=>{e.currentTarget.style.transform='';}}>
          <span style={{fontSize:'14px',flexShrink:0}}>{r.icon}</span>
          <span style={{flex:1}}>{r.text}</span>
          {isClickable && <span style={{fontSize:'11px',opacity:0.6}}>→</span>}
        </div>);
      }):<div style={{padding:'14px',borderRadius:'14px',background:'rgba(34,197,94,.10)',border:'1px solid rgba(34,197,94,.24)',color:'#86efac',fontSize:'13px',textAlign:'center'}}>✅ Всё под контролем<br/><span style={{fontSize:'11px',color:'#94a3b8'}}>Нет просроченных проектов, дефицита материалов, открытых замечаний и изменений к смете свыше 10%</span></div>}
    </div>
  );
}
