import React from 'react';
import { Check } from 'lucide-react';

export default function ActPaymentModal({
  showPayActModal,
  setShowPayActModal,
  C,
  card,
  inp,
  btnO,
  btnG,
  newPayment,
  setNewPayment,
  paymentTypes,
  financeUsers,
  roleLabels,
  saveActPayment,
  actPayments,
}) {
  if (!showPayActModal) return null;
  const payments = actPayments.filter(p=>p.actId===showPayActModal.id);
  return (
    <div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',display:'flex',justifyContent:'center',alignItems:'center',zIndex:1500}}>
      <div style={{...card,padding:'30px',width:'420px'}}>
        <h3 style={{color:C.text,marginBottom:'5px',fontWeight:'700'}}>Добавить оплату</h3>
        <p style={{color:C.textSec,fontSize:'13px',marginBottom:'15px'}}>{'Акт №'+showPayActModal.id+' · '+showPayActModal.masterName}</p>
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
          <input placeholder="Сумма *" type="number" step="any" inputMode="decimal" value={newPayment.amount} onChange={e=>setNewPayment({...newPayment,amount:e.target.value})} style={{...inp,marginBottom:0}}/>
          <select value={newPayment.paymentType} onChange={e=>setNewPayment({...newPayment,paymentType:e.target.value})} style={{...inp,marginBottom:0}}>{paymentTypes.map(t=><option key={t} value={t}>{t}</option>)}</select>
          <select value={newPayment.paidBy} onChange={e=>setNewPayment({...newPayment,paidBy:e.target.value})} style={{...inp,marginBottom:0}}><option value="">Кто выплатил</option>{financeUsers.map(u=><option key={u.id} value={u.name}>{u.name+' ('+roleLabels[u.role]+')'}</option>)}<option value="__manual__">Ввести вручную</option></select>
          <input type="date" value={newPayment.date} onChange={e=>setNewPayment({...newPayment,date:e.target.value})} style={{...inp,marginBottom:0}}/>
        </div>
        {newPayment.paidBy==='__manual__'&&<input placeholder="ФИО выплатившего" value={newPayment.paidByManual||''} onChange={e=>setNewPayment({...newPayment,paidByManual:e.target.value})} style={{...inp,marginTop:'10px'}}/>}
        <input placeholder="Примечание" value={newPayment.notes} onChange={e=>setNewPayment({...newPayment,notes:e.target.value})} style={{...inp,marginTop:'8px'}}/>
        <div style={{display:'flex',gap:'10px'}}><button onClick={()=>saveActPayment(showPayActModal.id)} style={btnO}><Check size={14}/>Записать</button><button onClick={()=>setShowPayActModal(null)} style={btnG}>Отмена</button></div>
        <div style={{marginTop:'15px',borderTop:'1.5px solid '+C.border,paddingTop:'12px'}}>
          <b style={{color:C.text,fontSize:'13px'}}>История оплат:</b>
          {payments.map(p=>(<div key={p.id} style={{display:'flex',justifyContent:'space-between',padding:'5px 0',borderBottom:'1px solid '+C.border,fontSize:'12px'}}><span style={{color:C.textSec}}>{p.date+' · '+p.paymentType+' · '+p.paidBy}</span><b style={{color:C.success}}>{p.amount.toLocaleString()+' ₽'}</b></div>))}
          {payments.length===0&&<p style={{color:C.textMuted,fontSize:'12px',margin:'6px 0'}}>Оплат нет</p>}
        </div>
      </div>
    </div>
  );
}
