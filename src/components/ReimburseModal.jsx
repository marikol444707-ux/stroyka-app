import React from 'react';
import ExpenseReceiptPhoto from './ExpenseReceiptPhoto';
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
  const pendingRef = React.useRef(false);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState('');
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

  const changeExpenseStatus = async (expense, status) => {
    if (pendingRef.current) return;
    pendingRef.current = true;
    setSaving(true);
    setError('');
    try {
      const response = await fetch(API+'/own-expenses/'+expense.id, {
        method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({status}),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail?.message || (typeof body.detail === 'string' ? body.detail : 'Не удалось изменить статус траты'));
      }
      await loadAll();
    } catch (failure) {
      setError(failure.message || 'Не удалось изменить статус траты');
    } finally {
      pendingRef.current = false;
      setSaving(false);
    }
  };
  const approveExpense = expense => changeExpenseStatus(expense, 'Возмещено');
  const rejectExpense = async expense => {
    if (prompt('Причина отклонения:', '') === null) return;
    await changeExpenseStatus(expense, 'Отклонено');
  };

  return (
    <div onClick={()=>setShowReimburseModal(false)} style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.55)',zIndex:1700,display:'flex',alignItems:'center',justifyContent:'center',padding:'20px'}}>
      <div onClick={e=>e.stopPropagation()} style={{...card,padding:'20px',width:'min(560px,100%)',maxHeight:'85vh',overflowY:'auto'}}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'14px'}}>
          <b style={{color:C.text,fontSize:'16px'}}>💰 Возмещения сотрудникам</b>
          <button onClick={()=>setShowReimburseModal(false)} style={{...btnG,padding:'4px 10px'}}><X size={14}/></button>
        </div>
        {error && <p role="alert" style={{color:C.danger}}>{error}</p>}
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
                      {(()=>{const urls=(e.photoUrl||'').split(',').filter(Boolean);if(urls.length===0) return null;return (<div style={{display:'flex',gap:'3px',marginTop:'4px',flexWrap:'wrap'}}>{urls.map((u,i)=>(<ExpenseReceiptPhoto key={i} url={u.trim()} fileSrc={fileSrc} onOpen={setShowPhotoModal} style={{width:'40px',height:'40px',borderRadius:'4px',objectFit:'cover',cursor:'pointer',border:'1px solid '+C.border}}/>))}</div>);})()}
                    </div>
                    <div style={{textAlign:'right',display:'flex',gap:'4px',alignItems:'center'}}>
                      <b style={{color:C.warning,fontSize:'13px'}}>{Math.round(Number(e.amount||0)).toLocaleString('ru-RU')+' ₽'}</b>
                      <button disabled={saving} onClick={()=>approveExpense(e)} style={{...btnO,padding:'3px 10px',fontSize:'11px'}}>✅</button>
                      <button disabled={saving} onClick={()=>rejectExpense(e)} style={{...btnR,padding:'3px 10px',fontSize:'11px'}}>❌</button>
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
