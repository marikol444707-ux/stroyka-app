import React from 'react';
import { Check, X } from 'lucide-react';
import PhotoAttachmentField from './PhotoAttachmentField';

export default function CrmLeadForm({
  C,
  card,
  inp,
  btnO,
  btnG,
  newLead,
  setNewLead,
  crmStages,
  editingItem,
  onSave,
  onCancel,
  isMobile = false,
  appendPhotos,
  fileSrc,
  setShowPhotoModal,
}) {
  const useCompactForm = isMobile || (typeof window !== 'undefined' && window.innerWidth <= 1100);
  const fieldStyle = {...inp,marginBottom:0,minWidth:0,width:'100%',boxSizing:'border-box'};

  return (
    <div style={{...card,padding:useCompactForm?'14px':'20px',marginBottom:'20px',width:'100%',boxSizing:'border-box',minWidth:0,overflowX:'hidden',maxWidth:useCompactForm?'720px':undefined,marginLeft:useCompactForm?'auto':undefined,marginRight:useCompactForm?'auto':undefined}}>
      <div style={{display:'grid',gridTemplateColumns:useCompactForm?'1fr':'1fr 1fr',gap:'10px'}}>
        <input placeholder="Имя клиента *" value={newLead.name} onChange={e=>setNewLead({...newLead,name:e.target.value})} style={fieldStyle}/>
        <input placeholder="Телефон" value={newLead.phone} onChange={e=>setNewLead({...newLead,phone:e.target.value})} style={fieldStyle}/>
        <input placeholder="Email" value={newLead.email} onChange={e=>setNewLead({...newLead,email:e.target.value})} style={fieldStyle}/>
        <input placeholder="Источник" value={newLead.source} onChange={e=>setNewLead({...newLead,source:e.target.value})} style={fieldStyle}/>
        <input placeholder="Бюджет (₽)" type="number" step="any" inputMode="decimal" value={newLead.budget} onChange={e=>setNewLead({...newLead,budget:e.target.value})} style={fieldStyle}/>
        <select value={newLead.stage} onChange={e=>setNewLead({...newLead,stage:e.target.value})} style={fieldStyle}>
          {crmStages.map(s=><option key={s}>{s}</option>)}
        </select>
        <textarea placeholder="Заметки" value={newLead.notes} onChange={e=>setNewLead({...newLead,notes:e.target.value})} style={{...fieldStyle,gridColumn:useCompactForm?'auto':'span 2',height:useCompactForm?'88px':'60px',resize:'vertical'}}/>
        <div style={{gridColumn:useCompactForm?'auto':'span 2'}}>
          <PhotoAttachmentField
            C={C}
            btnG={btnG}
            value={newLead.photoUrl || ''}
            onChange={photoUrl => setNewLead({...newLead, photoUrl})}
            appendPhotos={appendPhotos}
            fileSrc={fileSrc}
            setShowPhotoModal={setShowPhotoModal}
            projectName={newLead.name || 'CRM'}
            context="crm-leads"
            title="Фото объекта / дефектов / документов"
          />
        </div>
      </div>
      <div style={{display:'flex',gap:'10px',marginTop:'15px',flexWrap:'wrap'}}>
        <button onClick={onSave} style={{...btnO,flex:useCompactForm?'1 1 160px':'0 0 auto',justifyContent:'center',minHeight:useCompactForm?'44px':undefined}}><Check size={14}/>{editingItem?'Сохранить':'Добавить'}</button>
        <button onClick={onCancel} style={{...btnG,flex:useCompactForm?'1 1 140px':'0 0 auto',justifyContent:'center',minHeight:useCompactForm?'44px':undefined}}><X size={14}/>Отмена</button>
      </div>
    </div>
  );
}
