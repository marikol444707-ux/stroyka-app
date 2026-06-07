import React from 'react';
import { X } from 'lucide-react';

export default function ReimburseModal({
  showReimburseModal,
  setShowReimburseModal,
  C,
  card,
  btnG,
  btnO,
  btnR,
  ownExpenses,
  users,
  staff,
  roleLabels,
  expenseCategories,
  fileSrc,
  setShowPhotoModal,
  API,
  user,
  loadAll,
}) {
  if (!showReimburseModal) return null;

  const pending = (ownExpenses||[]).filter(e=>e.status==='Ожидает');
  const byEmp = new Map();
  pending.forEach(e=>{
    const key = e.employeeId||e.employeeName||'—';
    if (!byEmp.has(key)) byEmp.set(key, {name:e.employeeName||'—', empId:e.employeeId, items:[], total:0});
    const g = byEmp.get(key);
    g.items.push(e);
    g.total += Number(e.amount||0);
  });

  const roleOf = (g) => {
    const u = users.find(x=>x.id===g.empId) || users.find(x=>x.name===g.name);
    if (u) return u.role;
    const s = staff.find(x=>x.name===g.name);
    return s?.role || '';
  };
  const priority = (r)=> r==='директор'?0 : r==='зам_директора'?1 : r==='бухгалтер'?2 : r==='прораб'?3 : 4;
  const groups = Array.from(byEmp.values()).sort((a,b)=>priority(roleOf(a))-priority(roleOf(b)));
  const grandTotal = pending.reduce((s,e)=>s+Number(e.amount||0),0);

  const approveExpense = async (e) => {
    await fetch(API+'/own-expenses/'+e.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Возмещено',approvedBy:user.name})});
    if(e.projectName){
      await fetch(API+'/project-payments',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({projectName:e.projectName,amount:-Number(e.amount||0),note:'Возмещение «'+(e.description||'')+'» — '+(e.employeeName||''),date:new Date().toISOString().split('T')[0],paidBy:user.name})}).catch(()=>{});
    }
    await loadAll();
  };

  const rejectExpense = async (e) => {
    const reason=prompt('Причина отклонения:','');
    if(reason===null) return;
    await fetch(API+'/own-expenses/'+e.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Отклонено',approvedBy:user.name})});
    await loadAll();
  };

  return (
    <div onClick={()=>setShowReimburseModal(false)} style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.55)',zIndex:1700,display:'flex',alignItems:'center',justifyContent:'center',padding:'20px'}}>
      <div onClick={e=>e.stopPropagation()} style={{...card,padding:'20px',width:'min(560px,100%)',maxHeight:'85vh',overflowY:'auto'}}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'14px'}}>
          <b style={{color:C.text,fontSize:'16px'}}>💰 Возмещения сотрудникам</b>
          <button onClick={()=>setShowReimburseModal(false)} style={{...btnG,padding:'4px 10px'}}><X size={14}/></button>
        </div>
        {pending.length===0 ? (
          <p style={{color:C.textMuted,textAlign:'center',padding:'20px',fontSize:'13px'}}>Нет трат на возмещении</p>
        ) : (<>
          <div style={{padding:'10px 12px',backgroundColor:C.warningLight,border:'1.5px solid '+C.warningBorder,borderRadius:'8px',marginBottom:'10px',fontSize:'12px',color:C.text}}>
            💰 Всего к возмещению: <b>{Math.round(grandTotal).toLocaleString('ru-RU')+' ₽'}</b> · {pending.length} трат, {groups.length} сотр.
          </div>
          {groups.map((g,i)=>{
            const r = roleOf(g);
            const label = roleLabels[r] || r || 'сотрудник';
            const isLead = r==='директор'||r==='зам_директора';
            return (
              <div key={i} style={{...card,padding:'10px 12px',marginBottom:'8px',backgroundColor:C.bg,borderLeft:'4px solid '+(isLead?C.accent:C.warning)}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'8px'}}>
                  <div>
                    <b style={{color:C.text,fontSize:'13px'}}>{g.name}</b>
                    <span style={{fontSize:'11px',color:C.textSec,marginLeft:'8px'}}>{label}</span>
                  </div>
                  <b style={{color:isLead?C.accent:C.warning,fontSize:'14px'}}>{Math.round(g.total).toLocaleString('ru-RU')+' ₽'}</b>
                </div>
                {g.items.map(e=>(
                  <div key={e.id} style={{padding:'8px 10px',backgroundColor:C.bgWhite,borderRadius:'6px',marginBottom:'4px',display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'8px',flexWrap:'wrap'}}>
                    <div style={{flex:1,minWidth:'180px'}}>
                      <p style={{color:C.text,margin:0,fontSize:'12px',fontWeight:'600'}}>{e.description}</p>
                      <p style={{color:C.textMuted,margin:'2px 0 0',fontSize:'11px'}}>{(e.projectName?'🏗 '+e.projectName+' · ':'')+(e.date||'')+(e.category?' · '+(expenseCategories.find(c=>c.id===e.category)?.label||e.category):'')}</p>
                      {(()=>{const urls=(e.photoUrl||'').split(',').filter(Boolean);if(urls.length===0) return null;return (<div style={{display:'flex',gap:'3px',marginTop:'4px',flexWrap:'wrap'}}>{urls.map((u,i)=>(<img key={i} src={fileSrc(u)} alt='' onClick={()=>setShowPhotoModal(fileSrc(u))} style={{width:'40px',height:'40px',borderRadius:'4px',objectFit:'cover',cursor:'pointer',border:'1px solid '+C.border}}/>))}</div>);})()}
                    </div>
                    <div style={{textAlign:'right',display:'flex',gap:'4px',alignItems:'center'}}>
                      <b style={{color:C.warning,fontSize:'13px'}}>{Math.round(Number(e.amount||0)).toLocaleString('ru-RU')+' ₽'}</b>
                      <button onClick={()=>approveExpense(e)} style={{...btnO,padding:'3px 10px',fontSize:'11px'}}>✅</button>
                      <button onClick={()=>rejectExpense(e)} style={{...btnR,padding:'3px 10px',fontSize:'11px'}}>❌</button>
                    </div>
                  </div>
                ))}
              </div>
            );
          })}
        </>)}
      </div>
    </div>
  );
}
