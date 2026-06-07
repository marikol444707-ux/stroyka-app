import React from 'react';

export default function DashboardActivityPanel({ activityLog }) {
  return (
    <div style={{background:'rgba(17,24,39,.88)',border:'1px solid rgba(148,163,184,.18)',borderRadius:'22px',padding:'20px',backdropFilter:'blur(24px)'}}>
      <h2 style={{margin:'0 0 12px',fontSize:'17px',color:'#f8fafc'}}>📜 Активность</h2>
      {activityLog.slice(0,5).map((a,i)=>(
        <div key={i} style={{display:'flex',gap:'12px',padding:'10px 0',borderBottom:'1px solid rgba(148,163,184,.18)'}}>
          <div style={{width:'10px',height:'10px',borderRadius:'50%',background:'#f97316',boxShadow:'0 0 14px rgba(249,115,22,.8)',marginTop:'4px',flexShrink:0}}/>
          <div><div style={{fontSize:'13px',fontWeight:'700',color:'#f8fafc'}}>{a.action}</div><div style={{color:'#94a3b8',fontSize:'11px',marginTop:'2px'}}>{a.user+' · '+a.time}</div></div>
        </div>
      ))}
      {activityLog.length===0&&<div style={{color:'#94a3b8',fontSize:'13px'}}>Пока нет активности</div>}
    </div>
  );
}
