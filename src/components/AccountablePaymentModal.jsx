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
  staff,
  newAccountable,
  setNewAccountable,
  API,
  loadAll,
}) {
  if (!showAccountableForm) return null;

  const projectOptions = (projects || []).filter(project => Number(project?.id) > 0);
  const staffOptions = (staff || []).filter(person => (
    Number(person?.id) > 0
    && ['прораб','мастер','снабженец','кладовщик'].includes(person.role)
  ));
  const selectedProject = projectOptions.find(project => (
    Number(project.id) === Number(newAccountable.projectId)
  )) || projectOptions.filter(project => project.name === newAccountable.projectName)[0] || null;
  const selectedStaff = staffOptions.find(person => (
    Number(person.id) === Number(newAccountable.givenToId)
  )) || null;

  const reset = () => {
    setShowAccountableForm(false);
    setNewAccountable(createAccountablePaymentForm());
  };

  const submit = async () => {
    if(!selectedProject||!selectedStaff||!newAccountable.amount) return;
    await fetch(API+'/accountable-payments',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      projectId:Number(selectedProject.id),
      givenToId:Number(selectedStaff.id),
      amount:Number(newAccountable.amount),
      paymentMethod:newAccountable.paymentMethod,
      purpose:newAccountable.purpose,
      date:newAccountable.date,
    })});
    setNewAccountable(createAccountablePaymentForm());
    setShowAccountableForm(false);
    await loadAll();
  };

  return (
    <div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:500,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div className='mobile-modal' style={{...card,padding:'20px',width:'340px',margin:'20px',maxHeight:'90vh',overflowY:'auto'}}>
        <b style={{color:C.text,fontSize:'15px',display:'block',marginBottom:'12px'}}>💵 Выдать подотчёт</b>
        {newAccountable.projectName&&selectedProject?<p style={{color:C.textSec,fontSize:'12px',margin:'0 0 12px'}}>{'Объект: '+selectedProject.name}</p>:<select value={newAccountable.projectId||''} onChange={e=>{const project=projectOptions.find(item=>String(item.id)===e.target.value);setNewAccountable({...newAccountable,projectId:project?Number(project.id):'',projectName:project?.name||''});}} style={inp}><option value=''>Выберите проект *</option>{projectOptions.map(pr=><option key={pr.id} value={pr.id}>{pr.name}</option>)}</select>}
        <select value={newAccountable.givenToId||''} onChange={e=>{const person=staffOptions.find(item=>String(item.id)===e.target.value);setNewAccountable({...newAccountable,givenToId:person?Number(person.id):'',givenTo:person?.name||''});}} style={inp}><option value=''>Кому выдать *</option>{staffOptions.map(person=><option key={person.id} value={person.id}>{person.name}</option>)}</select>
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
