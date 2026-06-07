import React from 'react';
import { FileText, Plus } from 'lucide-react';

export default function MyExpensesPage({
  C,
  EXPENSE_CATEGORIES,
  accountablePayments,
  btnO,
  card,
  fileSrc,
  ownExpenses,
  setReportingPayment,
  setShowOwnExpenseForm,
  setShowPhotoModal,
  user,
}) {
  const myExp=(ownExpenses||[]).filter(e=>e.employeeName===user.name||e.employeeId===user.id);
  const pending=myExp.filter(e=>e.status==='Ожидает');
  const approved=myExp.filter(e=>e.status==='Возмещено');
  const rejected=myExp.filter(e=>e.status==='Отклонено');
  const sumP=pending.reduce((s,e)=>s+Number(e.amount||0),0);
  const sumA=approved.reduce((s,e)=>s+Number(e.amount||0),0);
  const sumR=rejected.reduce((s,e)=>s+Number(e.amount||0),0);
  const myAcc=(accountablePayments||[]).filter(a=>a.givenTo===user.name&&Number(a.amount||0)>Number(a.spentAmount||0));

  return (
    <div>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'18px',flexWrap:'wrap',gap:'10px'}}>
        <b style={{color:C.text,fontSize:'18px',fontWeight:'700'}}>💸 Мои траты на возмещении</b>
        <button onClick={()=>setShowOwnExpenseForm(true)} style={btnO}><Plus size={14}/>Новая трата</button>
      </div>
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
      <p style={{color:C.textMuted,fontSize:'12px',marginBottom:'12px'}}>Здесь видны все ваши траты собственными деньгами. После одобрения бухгалтерией сумма попадёт в расходы объекта по выбранной категории.</p>
      {myExp.length===0?<div style={{...card,padding:'40px',textAlign:'center',color:C.textMuted}}>Трат пока нет.<br/>Нажмите «Новая трата» чтобы зафиксировать расход.</div>:
        ['Ожидает','Возмещено','Отклонено'].map(st=>{const items=myExp.filter(e=>e.status===st);if(items.length===0) return null;const stColor=st==='Возмещено'?C.success:st==='Отклонено'?C.danger:C.warning;const stBg=st==='Возмещено'?C.successLight:st==='Отклонено'?C.dangerLight:C.warningLight;return(<div key={st} style={{marginBottom:'18px'}}>
          <b style={{color:stColor,fontSize:'12px',display:'block',marginBottom:'8px'}}>{st==='Ожидает'?'⏳':st==='Возмещено'?'✅':'❌'} {st} ({items.length})</b>
          {items.map(e=>{const cat=EXPENSE_CATEGORIES.find(c=>c.id===e.category)||{label:'Прочее',color:C.textMuted};return(<div key={e.id} style={{...card,padding:'12px',marginBottom:'6px',display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
            <div style={{flex:1,minWidth:'200px'}}>
              <b style={{color:C.text,fontSize:'13px'}}>{e.description}</b>
              <p style={{color:C.textSec,margin:'4px 0',fontSize:'11px'}}>📍 {e.projectName||'—'} · 📅 {e.date||e.createdAt||'—'}</p>
              <span style={{padding:'2px 8px',borderRadius:'8px',backgroundColor:stBg,color:cat.color,fontSize:'10px',fontWeight:'600'}}>{cat.label}</span>
              {e.photoUrl&&<img src={fileSrc(e.photoUrl)} alt='' onClick={()=>setShowPhotoModal(fileSrc(e.photoUrl))} style={{width:'40px',height:'40px',borderRadius:'6px',objectFit:'cover',cursor:'pointer',marginLeft:'8px',verticalAlign:'middle'}}/>}
            </div>
            <div style={{textAlign:'right'}}>
              <b style={{color:stColor,fontSize:'15px',display:'block'}}>{Math.round(Number(e.amount||0)).toLocaleString('ru-RU')+' ₽'}</b>
              {e.approvedBy&&<p style={{color:C.textMuted,fontSize:'10px',margin:'2px 0 0'}}>{e.status==='Возмещено'?'Утв.':'Откл.'} {e.approvedBy}</p>}
            </div>
          </div>);})}
        </div>);})
      }
    </div>
  );
}

