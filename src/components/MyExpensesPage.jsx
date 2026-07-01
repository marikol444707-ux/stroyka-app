import React, { useMemo, useState } from 'react';
import { FileText, Plus } from 'lucide-react';

export default function MyExpensesPage({
  C,
  EXPENSE_CATEGORIES,
  accountablePayments,
  btnO,
  card,
  fileSrc,
  ownExpenses,
  projectOptions = [],
  setReportingPayment,
  setShowOwnExpenseForm,
  setShowPhotoModal,
  user,
}) {
  const [projectFilter, setProjectFilter] = useState('');
  const [employeeFilter, setEmployeeFilter] = useState('');
  const reviewerRoles = ['директор','зам_директора','бухгалтер'];
  const canReviewAll = reviewerRoles.includes(user.role);
  const baseExp = canReviewAll ? (ownExpenses||[]) : (ownExpenses||[]).filter(e=>e.employeeName===user.name||e.employeeId===user.id);
  const projectNames = useMemo(() => {
    const names = new Set((projectOptions||[]).map(p=>p.name).filter(Boolean));
    (ownExpenses||[]).forEach(e=>{ if(e.projectName) names.add(e.projectName); });
    return Array.from(names).sort((a,b)=>a.localeCompare(b,'ru'));
  }, [ownExpenses, projectOptions]);
  const employeeNames = useMemo(() => {
    const names = new Set((ownExpenses||[]).map(e=>e.employeeName).filter(Boolean));
    return Array.from(names).sort((a,b)=>a.localeCompare(b,'ru'));
  }, [ownExpenses]);
  const myExp=baseExp.filter(e=>
    (!projectFilter || (projectFilter==='__none__' ? !e.projectName : e.projectName===projectFilter)) &&
    (!employeeFilter || e.employeeName===employeeFilter)
  );
  const pending=myExp.filter(e=>e.status==='Ожидает');
  const approved=myExp.filter(e=>e.status==='Возмещено');
  const rejected=myExp.filter(e=>e.status==='Отклонено');
  const sumP=pending.reduce((s,e)=>s+Number(e.amount||0),0);
  const sumA=approved.reduce((s,e)=>s+Number(e.amount||0),0);
  const sumR=rejected.reduce((s,e)=>s+Number(e.amount||0),0);
  const myAcc=(accountablePayments||[]).filter(a=>a.givenTo===user.name&&Number(a.amount||0)>Number(a.spentAmount||0));
  const sortExpenseRows = (items) => [...items].sort((a,b)=>{
    const dateA = String(a.date || a.createdAt || '');
    const dateB = String(b.date || b.createdAt || '');
    const byDate = dateB.localeCompare(dateA);
    if (byDate) return byDate;
    return Number(b.id || 0) - Number(a.id || 0);
  });
  const employeeExpenseGroups = (items) => {
    const map = new Map();
    sortExpenseRows(items).forEach(expense => {
      const name = expense.employeeName || 'Без сотрудника';
      const key = String(expense.employeeId || name);
      if (!map.has(key)) map.set(key, { key, name, items: [], total: 0 });
      const group = map.get(key);
      group.items.push(expense);
      group.total += Number(expense.amount || 0);
    });
    return Array.from(map.values()).sort((a,b)=>a.name.localeCompare(b.name,'ru'));
  };

  return (
    <div>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'18px',flexWrap:'wrap',gap:'10px'}}>
        <b style={{color:C.text,fontSize:'18px',fontWeight:'700'}}>{canReviewAll?'💸 Траты сотрудников на возмещении':'💸 Мои траты на возмещении'}</b>
        <button onClick={()=>setShowOwnExpenseForm(true)} style={btnO}><Plus size={14}/>Новая трата</button>
      </div>
      {canReviewAll&&(
        <div style={{...card,padding:'12px',marginBottom:'14px',display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(220px,1fr))',gap:'10px'}}>
          <select value={projectFilter} onChange={e=>setProjectFilter(e.target.value)} style={{padding:'10px 12px',borderRadius:'10px',border:'1.5px solid '+C.border,backgroundColor:C.bgWhite,color:C.text,fontSize:'13px'}}>
            <option value=''>Все объекты</option>
            {projectNames.map(name=><option key={name} value={name}>{name}</option>)}
            <option value='__none__'>Личные/без объекта</option>
          </select>
          <select value={employeeFilter} onChange={e=>setEmployeeFilter(e.target.value)} style={{padding:'10px 12px',borderRadius:'10px',border:'1.5px solid '+C.border,backgroundColor:C.bgWhite,color:C.text,fontSize:'13px'}}>
            <option value=''>Все сотрудники</option>
            {employeeNames.map(name=><option key={name} value={name}>{name}</option>)}
          </select>
        </div>
      )}
      {myAcc.length>0&&(<div style={{...card,padding:'14px',marginBottom:'14px',backgroundColor:C.warningLight,border:'1.5px solid '+C.warningBorder}}>
        <b style={{color:C.warning,fontSize:'13px',display:'block',marginBottom:'8px'}}>💵 Подотчётные — нужно отчитаться</b>
        {myAcc.map(a=>{const total=Number(a.amount||0);const spent=Number(a.spentAmount||0);const remaining=total-spent;return(<div key={a.id} style={{...card,padding:'10px 12px',marginBottom:'6px',backgroundColor:C.bgWhite,display:'flex',justifyContent:'space-between',alignItems:'center',gap:'8px',flexWrap:'wrap'}}>
          <div style={{flex:1,minWidth:'200px'}}>
            <b style={{color:C.text,fontSize:'12px'}}>{a.projectName||'—'}{a.purpose?' · '+a.purpose:''}</b>
            <p style={{color:C.textSec,margin:'2px 0',fontSize:'11px'}}>{'Выдано: '+Math.round(total).toLocaleString('ru-RU')+' ₽ · Потрачено: '+Math.round(spent).toLocaleString('ru-RU')+' ₽'}</p>
            <b style={{color:C.warning,fontSize:'12px'}}>{'⏳ Остаток отчитаться: '+Math.round(remaining).toLocaleString('ru-RU')+' ₽'}</b>
          </div>
          <button onClick={()=>setReportingPayment(a)} style={btnO}><FileText size={14}/>Отчитаться</button>
        </div>);})}
      </div>)}
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:'12px',marginBottom:'18px'}}>
        <div style={{...card,padding:'14px',backgroundColor:C.warningLight,border:'1.5px solid '+C.warningBorder}}><p style={{color:C.warning,fontSize:'11px',margin:'0 0 4px'}}>⏳ Ожидают возмещения</p><b style={{color:C.warning,fontSize:'18px'}}>{Math.round(sumP).toLocaleString('ru-RU')+' ₽'}</b><p style={{color:C.textSec,fontSize:'11px',margin:'2px 0 0'}}>{pending.length+' шт'}</p></div>
        <div style={{...card,padding:'14px',backgroundColor:C.successLight,border:'1.5px solid '+C.successBorder}}><p style={{color:C.success,fontSize:'11px',margin:'0 0 4px'}}>✅ Возмещено</p><b style={{color:C.success,fontSize:'18px'}}>{Math.round(sumA).toLocaleString('ru-RU')+' ₽'}</b><p style={{color:C.textSec,fontSize:'11px',margin:'2px 0 0'}}>{approved.length+' шт'}</p></div>
        <div style={{...card,padding:'14px',backgroundColor:C.dangerLight,border:'1.5px solid '+C.dangerBorder}}><p style={{color:C.danger,fontSize:'11px',margin:'0 0 4px'}}>❌ Отклонено</p><b style={{color:C.danger,fontSize:'18px'}}>{Math.round(sumR).toLocaleString('ru-RU')+' ₽'}</b><p style={{color:C.textSec,fontSize:'11px',margin:'2px 0 0'}}>{rejected.length+' шт'}</p></div>
      </div>
      <p style={{color:C.textMuted,fontSize:'12px',marginBottom:'12px'}}>
        {canReviewAll
          ? 'Здесь видны траты сотрудников из веба и Telegram. Трата с объектом сразу попадает в расходы объекта как «Прочее», без объекта — в «Личные/без объекта».'
          : 'Здесь видны все ваши траты собственными деньгами. Трата с объектом сразу попадает в расходы объекта как «Прочее», без объекта — в «Личные/без объекта».'}
      </p>
      {myExp.length===0?<div style={{...card,padding:'40px',textAlign:'center',color:C.textMuted}}>Трат пока нет.<br/>Нажмите «Новая трата» чтобы зафиксировать расход.</div>:
        ['Ожидает','Возмещено','Отклонено'].map(st=>{const items=myExp.filter(e=>e.status===st);if(items.length===0) return null;const stColor=st==='Возмещено'?C.success:st==='Отклонено'?C.danger:C.warning;const stBg=st==='Возмещено'?C.successLight:st==='Отклонено'?C.dangerLight:C.warningLight;const groups=employeeExpenseGroups(items);return(<div key={st} style={{marginBottom:'18px'}}>
          <b style={{color:stColor,fontSize:'12px',display:'block',marginBottom:'8px'}}>{st==='Ожидает'?'⏳':st==='Возмещено'?'✅':'❌'} {st} ({items.length})</b>
          {groups.map(group=>(<div key={group.key} style={{marginBottom:'14px'}}>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap',padding:'8px 2px',borderBottom:'1px solid '+C.border,marginBottom:'8px'}}>
              <b style={{color:C.text,fontSize:'13px'}}>👤 {group.name}</b>
              <span style={{color:stColor,fontSize:'12px',fontWeight:'700'}}>{group.items.length+' шт · '+Math.round(group.total).toLocaleString('ru-RU')+' ₽'}</span>
            </div>
            {group.items.map(e=>{const cat=EXPENSE_CATEGORIES.find(c=>c.id===e.category)||{label:'Прочее',color:C.textMuted};return(<div key={e.id} style={{...card,padding:'12px',marginBottom:'6px',display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
              <div style={{flex:1,minWidth:'200px'}}>
                <b style={{color:C.text,fontSize:'13px'}}>{e.description}</b>
                <p style={{color:C.textSec,margin:'4px 0',fontSize:'11px'}}>📍 {e.projectName||'Личные/без объекта'} · 📅 {e.date||e.createdAt||'—'}</p>
                <span style={{padding:'2px 8px',borderRadius:'8px',backgroundColor:stBg,color:cat.color,fontSize:'10px',fontWeight:'600'}}>{cat.label}</span>
                {e.photoUrl&&<img src={fileSrc(e.photoUrl)} alt='' onClick={()=>setShowPhotoModal(fileSrc(e.photoUrl))} style={{width:'40px',height:'40px',borderRadius:'6px',objectFit:'cover',cursor:'pointer',marginLeft:'8px',verticalAlign:'middle'}}/>}
              </div>
              <div style={{textAlign:'right'}}>
                <b style={{color:stColor,fontSize:'15px',display:'block'}}>{Math.round(Number(e.amount||0)).toLocaleString('ru-RU')+' ₽'}</b>
                {e.approvedBy&&<p style={{color:C.textMuted,fontSize:'10px',margin:'2px 0 0'}}>{e.status==='Возмещено'?'Утв.':'Откл.'} {e.approvedBy}</p>}
              </div>
            </div>);})}
          </div>))}
        </div>);})
      }
    </div>
  );
}
