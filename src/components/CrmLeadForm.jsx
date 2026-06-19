import React from 'react';
import { Check, X } from 'lucide-react';

export default function CrmLeadForm({card, inp, btnO, btnG, newLead, setNewLead, crmStages, editingItem, onSave, onCancel, isMobile=false}) {
  const fieldStyle = {...inp,marginBottom:0,minWidth:0,width:'100%',boxSizing:'border-box'};

  return (
    <div style={{...card,padding:isMobile?'14px':'20px',marginBottom:'20px',maxWidth:isMobile?'720px':undefined,marginLeft:isMobile?'auto':undefined,marginRight:isMobile?'auto':undefined}}>
      <div style={{display:'grid',gridTemplateColumns:isMobile?'1fr':'1fr 1fr',gap:'10px'}}>
        <input placeholder="Имя клиента *" value={newLead.name} onChange={e=>setNewLead({...newLead,name:e.target.value})} style={fieldStyle}/>
        <input placeholder="Телефон" value={newLead.phone} onChange={e=>setNewLead({...newLead,phone:e.target.value})} style={fieldStyle}/>
        <input placeholder="Email" value={newLead.email} onChange={e=>setNewLead({...newLead,email:e.target.value})} style={fieldStyle}/>
        <input placeholder="Источник" value={newLead.source} onChange={e=>setNewLead({...newLead,source:e.target.value})} style={fieldStyle}/>
        <input placeholder="Бюджет (₽)" type="number" step="any" inputMode="decimal" value={newLead.budget} onChange={e=>setNewLead({...newLead,budget:e.target.value})} style={fieldStyle}/>
        <select value={newLead.stage} onChange={e=>setNewLead({...newLead,stage:e.target.value})} style={fieldStyle}>
          {crmStages.map(s=><option key={s}>{s}</option>)}
        </select>
        <textarea placeholder="Заметки" value={newLead.notes} onChange={e=>setNewLead({...newLead,notes:e.target.value})} style={{...fieldStyle,gridColumn:isMobile?'auto':'span 2',height:isMobile?'88px':'60px',resize:'vertical'}}/>
      </div>
      <div style={{display:'flex',gap:'10px',marginTop:'15px',flexWrap:'wrap'}}>
        <button onClick={onSave} style={{...btnO,flex:isMobile?'1 1 160px':'0 0 auto',justifyContent:'center',minHeight:isMobile?'44px':undefined}}><Check size={14}/>{editingItem?'Сохранить':'Добавить'}</button>
        <button onClick={onCancel} style={{...btnG,flex:isMobile?'1 1 140px':'0 0 auto',justifyContent:'center',minHeight:isMobile?'44px':undefined}}><X size={14}/>Отмена</button>
      </div>
    </div>
  );
}
