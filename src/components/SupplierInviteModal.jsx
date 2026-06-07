import React from 'react';
import { X } from 'lucide-react';
import SupplierInviteForm from './SupplierInviteForm';
import SupplierInviteResult from './SupplierInviteResult';

export default function SupplierInviteModal({
  showSupplierInviteModal,
  setShowSupplierInviteModal,
  C,
  card,
  inp,
  btnO,
  btnG,
  generatedInviteLink,
  setGeneratedInviteLink,
  supplierInviteForm,
  setSupplierInviteForm,
  suppliers,
  supplierCategories,
  createSupplierInvite,
}) {
  if (!showSupplierInviteModal) return null;

  return (
    <div onClick={()=>setShowSupplierInviteModal(false)} style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.55)',zIndex:1700,display:'flex',alignItems:'center',justifyContent:'center',padding:'20px'}}>
      <div onClick={e=>e.stopPropagation()} style={{...card,padding:'20px',width:'min(560px,100%)',maxHeight:'85vh',overflowY:'auto'}}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'14px'}}>
          <b style={{color:C.text,fontSize:'16px'}}>🔗 Пригласить поставщика по ссылке</b>
          <button onClick={()=>setShowSupplierInviteModal(false)} style={{...btnG,padding:'4px 8px'}}><X size={14}/></button>
        </div>
        {!generatedInviteLink && (
          <SupplierInviteForm
            C={C}
            inp={inp}
            btnO={btnO}
            btnG={btnG}
            supplierInviteForm={supplierInviteForm}
            setSupplierInviteForm={setSupplierInviteForm}
            suppliers={suppliers}
            supplierCategories={supplierCategories}
            createSupplierInvite={createSupplierInvite}
            setShowSupplierInviteModal={setShowSupplierInviteModal}
          />
        )}
        {generatedInviteLink && (
          <SupplierInviteResult
            C={C}
            btnO={btnO}
            btnG={btnG}
            generatedInviteLink={generatedInviteLink}
            setGeneratedInviteLink={setGeneratedInviteLink}
            setShowSupplierInviteModal={setShowSupplierInviteModal}
          />
        )}
      </div>
    </div>
  );
}
