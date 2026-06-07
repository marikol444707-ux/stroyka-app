import React from 'react';
import { Check, X } from 'lucide-react';

export default function CrmLeadForm({card, inp, btnO, btnG, newLead, setNewLead, crmStages, editingItem, onSave, onCancel}) {
  return (
    <div style={{...card,padding:'20px',marginBottom:'20px'}}>
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
        <input placeholder="Имя клиента *" value={newLead.name} onChange={e=>setNewLead({...newLead,name:e.target.value})} style={{...inp,marginBottom:0}}/>
        <input placeholder="Телефон" value={newLead.phone} onChange={e=>setNewLead({...newLead,phone:e.target.value})} style={{...inp,marginBottom:0}}/>
        <input placeholder="Email" value={newLead.email} onChange={e=>setNewLead({...newLead,email:e.target.value})} style={{...inp,marginBottom:0}}/>
        <input placeholder="Источник" value={newLead.source} onChange={e=>setNewLead({...newLead,source:e.target.value})} style={{...inp,marginBottom:0}}/>
        <input placeholder="Бюджет (₽)" type="number" step="any" inputMode="decimal" value={newLead.budget} onChange={e=>setNewLead({...newLead,budget:e.target.value})} style={{...inp,marginBottom:0}}/>
        <select value={newLead.stage} onChange={e=>setNewLead({...newLead,stage:e.target.value})} style={{...inp,marginBottom:0}}>
          {crmStages.map(s=><option key={s}>{s}</option>)}
        </select>
        <textarea placeholder="Заметки" value={newLead.notes} onChange={e=>setNewLead({...newLead,notes:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2',height:'60px',resize:'vertical'}}/>
      </div>
      <div style={{display:'flex',gap:'10px',marginTop:'15px'}}>
        <button onClick={onSave} style={btnO}><Check size={14}/>{editingItem?'Сохранить':'Добавить'}</button>
        <button onClick={onCancel} style={btnG}><X size={14}/>Отмена</button>
      </div>
    </div>
  );
}
