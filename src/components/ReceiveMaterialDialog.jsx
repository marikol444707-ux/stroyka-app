import React from 'react';
import { Edit2, Scan } from 'lucide-react';

export default function ReceiveMaterialDialog({
  showReceiveDialog,
  setShowReceiveDialog,
  setShowScanInvoice,
  setShowScannedInvoiceForm,
  C,
  card,
  btnB,
  btnG,
}) {
  if (!showReceiveDialog) return null;
  return (
    <div onClick={()=>setShowReceiveDialog(false)} style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:600,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div onClick={e=>e.stopPropagation()} className='mobile-modal' style={{...card,padding:'24px',width:'320px',margin:'20px'}}>
        <b style={{color:C.text,fontSize:'15px',display:'block',marginBottom:'4px'}}>📥 Принять материал</b>
        <p style={{color:C.textSec,fontSize:'12px',marginBottom:'18px'}}>Выберите как заполнить накладную</p>
        <button onClick={()=>{setShowReceiveDialog(false);setShowScanInvoice(true);}} style={{...btnB,width:'100%',padding:'14px',justifyContent:'center',marginBottom:'10px',fontSize:'14px'}}><Scan size={16}/>📷 Сканировать накладную</button>
        <button onClick={()=>{setShowReceiveDialog(false);setShowScannedInvoiceForm(true);}} style={{...btnG,width:'100%',padding:'14px',justifyContent:'center',fontSize:'14px'}}><Edit2 size={14}/>✍️ Ввести вручную</button>
        <button onClick={()=>setShowReceiveDialog(false)} style={{width:'100%',marginTop:'10px',padding:'8px',backgroundColor:'transparent',border:'none',color:C.textSec,cursor:'pointer',fontSize:'13px'}}>Отмена</button>
      </div>
    </div>
  );
}
