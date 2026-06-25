import React from 'react';
import { Check, Eye, FileText, Plus, Trash2, Upload, X } from 'lucide-react';
import SettingsTabsNav from './SettingsTabsNav';
import SitePricingSettingsPanel from './SitePricingSettingsPanel';

const COMPANY_DOC_TYPES = ['Устав','ОГРН','ИНН','Выписка ЕГРЮЛ','Лицензия СРО','Доверенность','Прочее'];

export default function SettingsPage({
  API,
  C,
  btnB,
  btnG,
  btnO,
  btnR,
  card,
  companyDocuments,
  companyReqForm,
  companyRequisites,
  inp,
  loadAll,
  newCompanyDoc,
  saveCompanyRequisites,
  setCompanyReqForm,
  setCompanyRequisites,
  setNewCompanyDoc,
  setShowForm,
  setShowPhotoModal,
  settingsTab,
  setSettingsTab,
  showForm,
  uploadPhoto,
  user,
}) {
  const canManageSitePricing = ['директор', 'зам_директора'].includes(user?.role);
  return (
    <div>
      <SettingsTabsNav settingsTab={settingsTab} setSettingsTab={setSettingsTab} btnO={btnO} btnG={btnG} canManageSitePricing={canManageSitePricing}/>

      {settingsTab==='requisites'&&(<div>
        <div style={{...card,padding:'24px',marginBottom:'20px'}}>
          <h3 style={{color:C.text,marginBottom:'20px',fontWeight:'700',fontSize:'16px'}}>🏢 Реквизиты организации</h3>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'12px'}}>
            <input placeholder="Полное название организации" value={companyReqForm.fullName} onChange={e=>setCompanyReqForm({...companyReqForm,fullName:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
            <input placeholder="Краткое название" value={companyReqForm.shortName} onChange={e=>setCompanyReqForm({...companyReqForm,shortName:e.target.value})} style={{...inp,marginBottom:0}}/>
            <input placeholder="ИНН" value={companyReqForm.inn} onChange={e=>setCompanyReqForm({...companyReqForm,inn:e.target.value})} style={{...inp,marginBottom:0}}/>
            <input placeholder="КПП" value={companyReqForm.kpp} onChange={e=>setCompanyReqForm({...companyReqForm,kpp:e.target.value})} style={{...inp,marginBottom:0}}/>
            <input placeholder="ОГРН" value={companyReqForm.ogrn} onChange={e=>setCompanyReqForm({...companyReqForm,ogrn:e.target.value})} style={{...inp,marginBottom:0}}/>
            <input placeholder="Юридический адрес" value={companyReqForm.legalAddress} onChange={e=>setCompanyReqForm({...companyReqForm,legalAddress:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
            <input placeholder="Фактический адрес" value={companyReqForm.actualAddress} onChange={e=>setCompanyReqForm({...companyReqForm,actualAddress:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
            <input placeholder="Телефон" value={companyReqForm.phone} onChange={e=>setCompanyReqForm({...companyReqForm,phone:e.target.value})} style={{...inp,marginBottom:0}}/>
            <input placeholder="Email" value={companyReqForm.email} onChange={e=>setCompanyReqForm({...companyReqForm,email:e.target.value})} style={{...inp,marginBottom:0}}/>
          </div>
          <div style={{borderTop:'1.5px solid '+C.border,marginTop:'20px',paddingTop:'20px'}}>
            <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>Руководство</b>
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'12px'}}>
              <input placeholder="ФИО директора" value={companyReqForm.directorName} onChange={e=>setCompanyReqForm({...companyReqForm,directorName:e.target.value})} style={{...inp,marginBottom:0}}/>
              <input placeholder="Должность" value={companyReqForm.directorPosition} onChange={e=>setCompanyReqForm({...companyReqForm,directorPosition:e.target.value})} style={{...inp,marginBottom:0}}/>
              <input placeholder="Действует на основании" value={companyReqForm.basis} onChange={e=>setCompanyReqForm({...companyReqForm,basis:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
            </div>
          </div>
          <div style={{borderTop:'1.5px solid '+C.border,marginTop:'20px',paddingTop:'20px'}}>
            <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>Банковские реквизиты</b>
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'12px'}}>
              <input placeholder="Банк" value={companyReqForm.bankName} onChange={e=>setCompanyReqForm({...companyReqForm,bankName:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
              <input placeholder="БИК" value={companyReqForm.bik} onChange={e=>setCompanyReqForm({...companyReqForm,bik:e.target.value})} style={{...inp,marginBottom:0}}/>
              <input placeholder="Расчётный счёт" value={companyReqForm.rs} onChange={e=>setCompanyReqForm({...companyReqForm,rs:e.target.value})} style={{...inp,marginBottom:0}}/>
              <input placeholder="Корр. счёт" value={companyReqForm.ks} onChange={e=>setCompanyReqForm({...companyReqForm,ks:e.target.value})} style={{...inp,marginBottom:0}}/>
            </div>
          </div>
          <button onClick={async()=>{await saveCompanyRequisites();setCompanyRequisites(companyReqForm);}} style={{...btnO,marginTop:'20px',padding:'12px 30px',fontSize:'15px'}}><Check size={16}/>Сохранить реквизиты</button>
        </div>
        {companyRequisites&&companyRequisites.fullName&&(<div style={{...card,padding:'20px',backgroundColor:C.successLight,border:'1.5px solid '+C.successBorder}}>
          <b style={{color:C.success,fontSize:'14px',display:'block',marginBottom:'10px'}}>✅ Реквизиты сохранены — подставляются во все документы</b>
          <p style={{color:C.text,margin:'3px 0',fontSize:'13px'}}>{companyRequisites.fullName}</p>
          <p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{'ИНН: '+companyRequisites.inn+' · КПП: '+companyRequisites.kpp+' · ОГРН: '+companyRequisites.ogrn}</p>
          <p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{'Директор: '+companyRequisites.directorName}</p>
          <p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{'Банк: '+companyRequisites.bankName+' · Р/с: '+companyRequisites.rs}</p>
        </div>)}
      </div>)}

      {settingsTab==='documents'&&(<div>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
          <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>Юридические документы</b>
          <button onClick={()=>setShowForm(!showForm)} style={btnO}><Plus size={14}/>Добавить документ</button>
        </div>
        {showForm&&(<div style={{...card,padding:'20px',marginBottom:'16px'}}>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
            <input placeholder="Название документа *" value={newCompanyDoc.name} onChange={e=>setNewCompanyDoc({...newCompanyDoc,name:e.target.value})} style={{...inp,marginBottom:0}}/>
            <select value={newCompanyDoc.docType} onChange={e=>setNewCompanyDoc({...newCompanyDoc,docType:e.target.value})} style={{...inp,marginBottom:0}}>{COMPANY_DOC_TYPES.map(t=><option key={t}>{t}</option>)}</select>
            <input type="date" placeholder="Срок действия" value={newCompanyDoc.expiresAt} onChange={e=>setNewCompanyDoc({...newCompanyDoc,expiresAt:e.target.value})} style={{...inp,marginBottom:0}}/>
            <label style={{cursor:'pointer',backgroundColor:C.infoLight,padding:'10px',borderRadius:'8px',fontSize:'13px',color:C.info,border:'1.5px solid '+C.infoBorder,display:'flex',alignItems:'center',gap:'8px'}}><Upload size={14}/>Загрузить файл<input type="file" accept="image/*,application/pdf" style={{display:'none'}} onChange={async e=>{if(e.target.files[0]){const url=await uploadPhoto(e.target.files[0],{context:'company-documents'});setNewCompanyDoc(prev=>({...prev,fileUrl:url}));}}} /></label>
          </div>
          {newCompanyDoc.fileUrl&&<p style={{color:C.success,fontSize:'12px',marginTop:'8px'}}>✅ Файл загружен</p>}
          <div style={{display:'flex',gap:'8px',marginTop:'12px'}}><button onClick={async()=>{if(!newCompanyDoc.name) return;await fetch(API+'/company-documents',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...newCompanyDoc,uploadedBy:user.name})});await loadAll();setNewCompanyDoc({name:'',docType:'Устав',fileUrl:'',expiresAt:''});setShowForm(false);}} style={btnO}><Check size={14}/>Сохранить</button><button onClick={()=>setShowForm(false)} style={btnG}><X size={14}/>Отмена</button></div>
        </div>)}
        {COMPANY_DOC_TYPES.map(docType=>{
          const docs=companyDocuments.filter(d=>d.docType===docType);
          if(docs.length===0) return null;
          return(<div key={docType} style={{marginBottom:'16px'}}>
            <div style={{padding:'8px 12px',backgroundColor:C.bg,borderRadius:'8px',border:'1.5px solid '+C.border,marginBottom:'8px'}}><b style={{color:C.accent,fontSize:'12px'}}>{'📄 '+docType}</b></div>
            {docs.map(doc=>(<div key={doc.id} style={{...card,padding:'14px',marginBottom:'6px',marginLeft:'12px',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
              <div><b style={{color:C.text,fontSize:'13px'}}>{doc.name}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{doc.uploadedBy+(doc.expiresAt?' · до '+doc.expiresAt:'')}</p></div>
              <div style={{display:'flex',gap:'6px'}}>
                {doc.fileUrl&&<button onClick={()=>setShowPhotoModal(doc.fileUrl)} style={btnB}><Eye size={13}/>Открыть</button>}
                <button onClick={async()=>{await fetch(API+'/company-documents/'+doc.id,{method:'DELETE'});await loadAll();}} style={{...btnR,padding:'5px 8px'}}><Trash2 size={11}/></button>
              </div>
            </div>))}
          </div>);
        })}
        {companyDocuments.length===0&&<div style={{...card,padding:'40px',textAlign:'center',color:C.textMuted}}><FileText size={48} style={{marginBottom:'15px',opacity:0.3}}/><p>Документов нет — загрузите первый!</p></div>}
      </div>)}

      {settingsTab==='sitePricing'&&canManageSitePricing&&(
        <SitePricingSettingsPanel API={API} C={C} card={card} inp={inp} btnO={btnO} btnG={btnG}/>
      )}
    </div>
  );
}
