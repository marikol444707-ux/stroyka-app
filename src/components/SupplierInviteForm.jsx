import React from 'react';
import { Check, X } from 'lucide-react';

export default function SupplierInviteForm({C, inp, btnO, btnG, supplierInviteForm, setSupplierInviteForm, suppliers, supplierCategories, createSupplierInvite, setShowSupplierInviteModal}) {
  return (
    <>
      <div style={{padding:'10px 12px',backgroundColor:C.infoLight,border:'1.5px solid '+C.infoBorder,borderRadius:'8px',marginBottom:'12px',fontSize:'12px',color:C.text}}>
        ℹ️ Сгенерируем уникальную ссылку для поставщика. Он перейдёт по ней, заполнит реквизиты компании и зарегистрируется сам. Договор поставки и прайс прикрепит в кабинете.
      </div>
      <label style={{fontSize:'12px',color:C.textSec,display:'block',marginBottom:'4px'}}>Название компании (опц.)</label>
      <input value={supplierInviteForm.presetName} onChange={e=>setSupplierInviteForm({...supplierInviteForm,presetName:e.target.value})} placeholder='Например: ООО Стройторг' style={inp}/>
      <label style={{fontSize:'12px',color:C.textSec,display:'block',marginBottom:'4px'}}>Категория поставок</label>
      <select value={supplierInviteForm.presetCategory} onChange={e=>setSupplierInviteForm({...supplierInviteForm,presetCategory:e.target.value})} style={inp}>
        {supplierCategories.map(c=><option key={c}>{c}</option>)}
      </select>
      <label style={{fontSize:'12px',color:C.textSec,display:'block',marginBottom:'4px'}}>Привязать к существующей компании (опц.)</label>
      <select value={supplierInviteForm.supplierId||''} onChange={e=>setSupplierInviteForm({...supplierInviteForm,supplierId:e.target.value?Number(e.target.value):null})} style={inp}>
        <option value=''>— новая компания —</option>
        {(suppliers||[]).filter(s=>!s.user_id&&!s.userId).map(s=><option key={s.id} value={s.id}>{s.name}</option>)}
      </select>
      <label style={{fontSize:'12px',color:C.textSec,display:'block',marginBottom:'4px'}}>Срок действия ссылки (дней)</label>
      <input type='number' value={supplierInviteForm.expiresInDays} onChange={e=>setSupplierInviteForm({...supplierInviteForm,expiresInDays:Number(e.target.value)})} style={inp}/>
      <div style={{display:'flex',gap:'8px',marginTop:'12px'}}>
        <button onClick={createSupplierInvite} style={btnO}><Check size={14}/>Создать ссылку</button>
        <button onClick={()=>setShowSupplierInviteModal(false)} style={btnG}><X size={14}/>Отмена</button>
      </div>
    </>
  );
}
