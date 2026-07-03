import React from 'react';
import { Check, X } from 'lucide-react';
import { createAccountablePaymentForm } from '../features/payments/paymentInitialForms';

export default function AccountablePaymentModal({
  showAccountableForm,
  setShowAccountableForm,
  C,
  card,
  inp,
  btnO,
  btnG,
  projects,
  users,
  newAccountable,
  setNewAccountable,
  API,
  user,
  loadAll,
}) {
  if (!showAccountableForm) return null;

  const reset = () => {
    setShowAccountableForm(false);
    setNewAccountable(createAccountablePaymentForm());
  };

  const submit = async () => {
    if(!newAccountable.givenTo||!newAccountable.amount||!newAccountable.projectName) return;
    await fetch(API+'/accountable-payments',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...newAccountable,amount:Number(newAccountable.amount),addedBy:user.name})});
    setNewAccountable(createAccountablePaymentForm());
    setShowAccountableForm(false);
    await loadAll();
  };

  return (
    <div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:500,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div className='mobile-modal' style={{...card,padding:'20px',width:'340px',margin:'20px',maxHeight:'90vh',overflowY:'auto'}}>
        <b style={{color:C.text,fontSize:'15px',display:'block',marginBottom:'12px'}}>💵 Выдать подотчёт</b>
        {newAccountable.projectName?<p style={{color:C.textSec,fontSize:'12px',margin:'0 0 12px'}}>{'Объект: '+newAccountable.projectName}</p>:<select value={newAccountable.projectName||''} onChange={e=>setNewAccountable({...newAccountable,projectName:e.target.value})} style={inp}><option value=''>Выберите проект *</option>{projects.map(pr=><option key={pr.id} value={pr.name}>{pr.name}</option>)}</select>}
        <select value={newAccountable.givenTo} onChange={e=>setNewAccountable({...newAccountable,givenTo:e.target.value})} style={inp}><option value=''>Кому выдать *</option>{users.filter(u=>['прораб','мастер','снабженец','кладовщик'].includes(u.role)).map(u=><option key={u.id} value={u.name}>{u.name}</option>)}</select>
        <div className='mobile-two-cols' style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px'}}>
          <input placeholder='Сумма *' type='number' step='any' inputMode='decimal' value={newAccountable.amount} onChange={e=>setNewAccountable({...newAccountable,amount:e.target.value})} style={{...inp,marginBottom:0}}/>
          <select value={newAccountable.paymentMethod} onChange={e=>setNewAccountable({...newAccountable,paymentMethod:e.target.value})} style={{...inp,marginBottom:0}}>{['Наличные','Перевод на карту','Корпоративная карта','Через кассу'].map(m=><option key={m}>{m}</option>)}</select>
        </div>
        <input placeholder='Назначение' value={newAccountable.purpose} onChange={e=>setNewAccountable({...newAccountable,purpose:e.target.value})} style={inp}/>
        <input type='date' value={newAccountable.date} onChange={e=>setNewAccountable({...newAccountable,date:e.target.value})} style={inp}/>
        <div className='mobile-actions' style={{display:'flex',gap:'8px'}}>
          <button onClick={submit} style={btnO}><Check size={14}/>Выдать</button>
          <button onClick={reset} style={btnG}><X size={14}/>Отмена</button>
        </div>
      </div>
    </div>
  );
}
