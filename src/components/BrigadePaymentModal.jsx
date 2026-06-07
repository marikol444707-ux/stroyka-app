import React from 'react';
import { Check } from 'lucide-react';

export default function BrigadePaymentModal({
  showBrigadePayModal,
  setShowBrigadePayModal,
  selectedBrigadeContract,
  C,
  card,
  inp,
  btnO,
  btnG,
  newBrigadePayment,
  setNewBrigadePayment,
  saveBrigadePayment,
}) {
  if (!showBrigadePayModal || !selectedBrigadeContract) return null;
  return (
    <div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',display:'flex',justifyContent:'center',alignItems:'center',zIndex:1500}} onClick={()=>setShowBrigadePayModal(false)}>
      <div style={{...card,padding:'28px',width:'400px'}} onClick={e=>e.stopPropagation()}>
        <h3 style={{color:C.text,marginBottom:'5px',fontWeight:'700'}}>💰 Записать оплату бригаде</h3>
        <p style={{color:C.textSec,fontSize:'13px',marginBottom:'15px'}}>{selectedBrigadeContract.brigadeName}</p>
        <input placeholder="Сумма (₽) *" type="number" step="any" inputMode="decimal" value={newBrigadePayment.amount} onChange={e=>setNewBrigadePayment({...newBrigadePayment,amount:e.target.value})} style={inp}/>
        <input type="date" value={newBrigadePayment.paidDate} onChange={e=>setNewBrigadePayment({...newBrigadePayment,paidDate:e.target.value})} style={inp}/>
        <input placeholder="Примечание (за что / как)" value={newBrigadePayment.note} onChange={e=>setNewBrigadePayment({...newBrigadePayment,note:e.target.value})} style={inp}/>
        <div style={{display:'flex',gap:'10px'}}><button onClick={saveBrigadePayment} style={btnO}><Check size={14}/>Записать</button><button onClick={()=>setShowBrigadePayModal(false)} style={btnG}>Отмена</button></div>
      </div>
    </div>
  );
}
