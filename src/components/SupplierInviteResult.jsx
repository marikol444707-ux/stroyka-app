import React from 'react';
import { Copy } from 'lucide-react';

export default function SupplierInviteResult({C, btnO, btnG, generatedInviteLink, setGeneratedInviteLink, setShowSupplierInviteModal}) {
  return (
    <>
      <div style={{padding:'14px',backgroundColor:C.successLight,border:'1.5px solid '+C.successBorder,borderRadius:'10px',marginBottom:'12px'}}>
        <b style={{color:C.success,fontSize:'13px',display:'block',marginBottom:'8px'}}>✅ Ссылка создана!</b>
        <p style={{margin:'0 0 8px',fontSize:'12px',color:C.text}}>Отправьте её поставщику любым способом (email, мессенджер, телефон):</p>
        <div style={{padding:'10px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border,borderRadius:'6px',fontSize:'12px',color:C.text,wordBreak:'break-all',userSelect:'all'}}>
          {generatedInviteLink.link}
        </div>
        <p style={{margin:'8px 0 0',fontSize:'11px',color:C.textSec}}>Код: <b>{generatedInviteLink.code}</b> · Истекает: {generatedInviteLink.expiresAt?new Date(generatedInviteLink.expiresAt).toLocaleDateString('ru-RU'):'через 14 дней'}</p>
      </div>
      <div style={{display:'flex',gap:'8px'}}>
        <button onClick={()=>{navigator.clipboard.writeText(generatedInviteLink.link).then(()=>{alert('Ссылка скопирована в буфер обмена');}).catch(()=>{alert('Скопируйте вручную');});}} style={btnO}><Copy size={14}/>Скопировать ссылку</button>
        <button onClick={()=>{setGeneratedInviteLink(null);}} style={btnG}>Создать ещё одну</button>
        <button onClick={()=>{setShowSupplierInviteModal(false);setGeneratedInviteLink(null);}} style={btnG}>Закрыть</button>
      </div>
    </>
  );
}
