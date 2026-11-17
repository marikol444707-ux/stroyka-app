import React, { useEffect, useRef, useState } from 'react';
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
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const flight = useRef(false);
  const session = useRef(0);
  const identity = showAccountableForm;
  useEffect(() => {
    session.current += 1;
    flight.current = false;
    setBusy(false);
    setError('');
    return () => { session.current += 1; };
  }, [identity, setBusy]);
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
    if(!selectedProject||!selectedStaff||!newAccountable.amount||flight.current) return;
    flight.current = true; setBusy(true); setError('');
    const startedSession = session.current;
    const current = () => session.current === startedSession;
    try {
      const response = await fetch(API+'/accountable-payments',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
        projectId:Number(selectedProject.id), givenToId:Number(selectedStaff.id),
        amount:Number(newAccountable.amount), paymentMethod:newAccountable.paymentMethod,
        paymentKind:newAccountable.paymentKind, purpose:newAccountable.purpose, date:newAccountable.date,
      })});
      const result = await response.json().catch(() => ({}));
      if(!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Выдача не подтверждена сервером. Проверьте список выдач перед повтором.');
      if(!result.ok || !result.id) throw new Error('Ответ не подтверждает выдачу. Проверьте список перед повтором.');
      if (!current()) return;
      setNewAccountable(createAccountablePaymentForm());
      setShowAccountableForm(false);
      try { await loadAll(); } catch { window.alert('Выдача сохранена, но список не обновился. Обновите данные; повторная выдача не требуется.'); }
    } catch(e) {
      if (current()) setError(e.message || 'Ответ не получен. Проверьте список выдач перед повтором; введённые данные сохранены.');
    } finally { if (current()) { flight.current = false; setBusy(false); } }

  };

  return (
    <div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:500,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div className='mobile-modal' style={{...card,padding:'20px',width:'340px',margin:'20px',maxHeight:'90vh',overflowY:'auto'}}>
        <b style={{color:C.text,fontSize:'15px',display:'block',marginBottom:'12px'}}>💵 Выдать деньги сотруднику</b>
        {error && <p role="alert" style={{color:C.danger}}>{error}</p>}
        <fieldset disabled={busy} style={{border:0,padding:0,margin:0}}>
        <select aria-label="Тип выдачи" value={newAccountable.paymentKind || ''} onChange={e=>setNewAccountable({...newAccountable,paymentKind:e.target.value})} style={inp}>
          <option value="">Выберите тип выдачи</option><option value="expense">Подотчёт на расходы</option><option value="salary_advance">Зарплатный аванс</option>
        </select>
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
        </fieldset>
      </div>
    </div>
  );
}
