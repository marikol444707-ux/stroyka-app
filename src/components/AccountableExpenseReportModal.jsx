import React, { useEffect, useRef, useState } from 'react';
import { Check, X } from 'lucide-react';
import { createAccountableExpenseForm } from '../features/payments/paymentInitialForms';

export default function AccountableExpenseReportModal({
  reportingPayment,
  setReportingPayment,
  C,
  card,
  inp,
  btnO,
  btnG,
  expenseCategories,
  newExpense,
  setNewExpense,
  appendPhotos,
  fileSrc,
  expenseSubmitting,
  setExpenseSubmitting,
  API,
  loadAll,
}) {
  const [error, setError] = useState('');
  const flight = useRef(false);
  const session = useRef(0);
  const identity = reportingPayment ? `${reportingPayment.companyId}:${reportingPayment.id}` : null;
  useEffect(() => {
    session.current += 1;
    flight.current = false;
    setExpenseSubmitting(false);
    setError('');
    return () => { session.current += 1; };
  }, [identity, setExpenseSubmitting]);
  if (!reportingPayment) return null;

  const reset = () => {
    setReportingPayment(null);
    setNewExpense(createAccountableExpenseForm());
  };

  const submit = async () => {
    if(!newExpense.description||!newExpense.amount||expenseSubmitting||flight.current) return;
    flight.current=true;setExpenseSubmitting(true);setError('');
    const startedSession = session.current;
    const current = () => session.current === startedSession;
    try {
      const response=await fetch(API+'/accountable-expenses',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({paymentId:reportingPayment.id,description:newExpense.description,amount:Number(newExpense.amount),photoUrl:newExpense.photoUrl||'',date:new Date().toISOString().split('T')[0]})});
      const result=await response.json().catch(()=>({}));
      if(!response.ok || !result.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Отчёт не подтверждён. Проверьте список перед повтором.');
      if (!current()) return;
      setReportingPayment(null);setNewExpense(createAccountableExpenseForm());
      try { await loadAll(); } catch { window.alert('Отчёт сохранён, но список не обновился. Повторно отправлять его не нужно.');return; }
      window.alert('Отчёт отправлен!');
    } catch(e) { if (current()) setError(e.message || 'Ответ не получен. Введённые данные сохранены; проверьте список отчётов.'); }
    finally { if (current()) { flight.current=false;setExpenseSubmitting(false); } }

  };

  return (
    <div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:500,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div className='mobile-modal' style={{...card,padding:'20px',width:'340px',margin:'20px',maxHeight:'90vh',overflowY:'auto'}}>
        {error && <p role="alert" style={{color:C.danger}}>{error}</p>}
        <b style={{color:C.text,fontSize:'15px',display:'block',marginBottom:'12px'}}>💵 Отчёт о трате</b>
        <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 12px'}}>{'Выдано: '+Number(reportingPayment.amount).toLocaleString()+' ₽ · Остаток: '+(Number(reportingPayment.amount)-Number(reportingPayment.spentAmount||0)).toLocaleString()+' ₽'}</p>
        <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 12px'}}>{'Объект: '+reportingPayment.projectName}</p>
        <fieldset disabled={expenseSubmitting} style={{border:0,padding:0,margin:0}}>
        <select value={newExpense.category||'accountable'} onChange={e=>setNewExpense({...newExpense,category:e.target.value})} style={inp}><option value=''>Категория затрат</option>{expenseCategories.map(c=><option key={c.id} value={c.id}>{c.label}</option>)}</select>
        <input placeholder='За что потрачено *' value={newExpense.description} onChange={e=>setNewExpense({...newExpense,description:e.target.value})} style={inp}/>
        <input placeholder='Сумма (₽) *' type='number' step='any' inputMode='decimal' value={newExpense.amount} onChange={e=>setNewExpense({...newExpense,amount:e.target.value})} style={inp}/>
        <div style={{marginBottom:'12px'}}>
          <span style={{fontSize:'12px',color:C.textSec,display:'block',marginBottom:'6px'}}>📷 Фото чеков (можно несколько):</span>
          <label style={{cursor:'pointer'}}>
            <input type='file' accept='image/*' multiple style={{display:'none'}} onChange={async e=>{
              if(e.target.files&&e.target.files.length>0){
                const newCsv = await appendPhotos(newExpense.photoUrl, e.target.files,{projectName:reportingPayment.projectName,context:'accountable-expenses'});
                setNewExpense(prev=>({...prev,photoUrl:newCsv}));
                e.target.value='';
              }
            }}/>
            {(()=>{const urls=(newExpense.photoUrl||'').split(',').filter(Boolean);
              if (urls.length===0) return (<div style={{border:'2px dashed '+C.border,borderRadius:'8px',padding:'16px',textAlign:'center',color:C.textMuted,fontSize:'12px'}}>📷 Нажмите чтобы добавить фото<br/><span style={{fontSize:'10px'}}>можно несколько за раз</span></div>);
              return (<div>
                <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(80px,1fr))',gap:'6px',marginBottom:'8px'}}>
                  {urls.map((u,i)=>(<div key={i} style={{position:'relative'}}>
                    <img src={fileSrc(u)} alt='' style={{width:'100%',height:'80px',objectFit:'cover',borderRadius:'6px',border:'1px solid '+C.border}}/>
                    <button type='button' onClick={(ev)=>{ev.preventDefault();ev.stopPropagation();const rem=urls.filter((_,j)=>j!==i).join(',');setNewExpense(prev=>({...prev,photoUrl:rem}));}} style={{position:'absolute',top:'2px',right:'2px',background:'rgba(220,38,38,0.9)',color:'white',border:'none',borderRadius:'50%',width:'20px',height:'20px',cursor:'pointer',fontSize:'12px',lineHeight:'1',padding:0}}>×</button>
                  </div>))}
                </div>
                <div style={{padding:'8px',backgroundColor:C.bg,borderRadius:'6px',textAlign:'center',fontSize:'11px',color:C.accent,fontWeight:'600'}}>+ Добавить ещё фото ({urls.length} загружено)</div>
              </div>);
            })()}
          </label>
        </div>
        <div className='mobile-actions' style={{display:'flex',gap:'8px'}}>
          <button disabled={expenseSubmitting} onClick={submit} style={btnO}><Check size={14}/>Отправить</button>
          <button disabled={expenseSubmitting} onClick={reset} style={btnG}><X size={14}/>Отмена</button>
        </div>
        </fieldset>
      </div>
    </div>
  );
}
