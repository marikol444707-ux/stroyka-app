import React from 'react';
import { X } from 'lucide-react';

export default function ScanInvoiceModal({
  showScanInvoice,
  setShowScanInvoice,
  setShowScannedInvoiceForm,
  C,
  card,
  btnG,
  scanningInvoice,
  setScanningInvoice,
  API,
  user,
  setNewInvoice,
}) {
  if (!showScanInvoice) return null;

  const scan = async (file) => {
    if(!file) return;
    setScanningInvoice(true);
    const base64 = await new Promise(res=>{const r=new FileReader();r.onload=()=>res(r.result.split(',')[1]);r.readAsDataURL(file);});
    try {
      const resp = await fetch(API+'/scan-invoice',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image:base64})});
      const data = await resp.json();
      if(!data.ok) throw new Error(data.error||'Ошибка');
      const parsed = data.data;
      const today = new Date().toISOString().split('T')[0];
      setNewInvoice(prev=>({...prev,
        supplier:parsed.supplier||'',
        newSupplierName:parsed.supplier||'',
        isNewSupplier:true,
        date:today,
        acceptedBy:user.name,
        vat:'Без НДС',
        totalWithVat:parsed.total||0,
        items:(parsed.items||[]).map(item=>({
          name:item.name||'',
          quantity:String(item.quantity||''),
          unit:item.unit||'шт',
          price:String(item.price||''),
          category:'',
          workPackage:''
        }))
      }));
      setShowScanInvoice(false);
      setShowScannedInvoiceForm(true);
      alert('Накладная распознана! Проверьте данные.');
    } catch(e){
      alert('Не удалось распознать. Попробуйте ещё раз.');
    }
    setScanningInvoice(false);
  };

  return (
    <div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:500,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div className='mobile-modal' style={{...card,padding:'20px',width:'340px',margin:'20px',maxHeight:'90vh',overflowY:'auto'}}>
        <b style={{color:C.text,fontSize:'15px',display:'block',marginBottom:'12px'}}>📷 Сканировать накладную</b>
        <label style={{display:'block',marginBottom:'12px',cursor:'pointer'}}>
          <input type='file' accept='image/*' capture='environment' style={{display:'none'}} onChange={e=>scan(e.target.files[0])}/>
          <div style={{border:'2px dashed '+C.border,borderRadius:'12px',padding:'30px',textAlign:'center',cursor:'pointer'}}>
            {scanningInvoice?<div><div style={{fontSize:'32px',marginBottom:'8px'}}>⏳</div><p style={{color:C.textSec,fontSize:'13px'}}>ИИ распознаёт накладную...</p></div>:<div><div style={{fontSize:'48px',marginBottom:'8px'}}>📷</div><p style={{color:C.text,fontSize:'14px',fontWeight:'600'}}>Нажмите чтобы сфотографировать</p><p style={{color:C.textSec,fontSize:'12px',marginTop:'4px'}}>ИИ автоматически заполнит форму</p></div>}
          </div>
        </label>
        <button onClick={()=>setShowScanInvoice(false)} style={{...btnG,width:'100%',justifyContent:'center'}}><X size={14}/>Отмена</button>
      </div>
    </div>
  );
}
