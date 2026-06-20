import React from 'react';
import { Bot, Check, Upload, X } from 'lucide-react';
import { API } from '../api';
import { invoiceImageAccept, normalizeInvoiceImageFile } from '../utils/invoiceImages';

function SupplyDeliveriesPanel({
  C,
  card,
  inp,
  btnO,
  btnG,
  btnB,
  btnGr,
  badge,
  role,
  supplyClaims,
  supplyDeliveries,
  receivingDeliveryId,
  setReceivingDeliveryId,
  receiveForm,
  setReceiveForm,
  deliveryAiLoadingId,
  setDeliveryAiLoadingId,
  deliveryAiResultById,
  setDeliveryAiResultById,
  runDeliveryAiCheck,
  receiveSupplyDelivery,
  invoices,
  showPreview,
  buildInvoiceContent,
  uploadPhoto,
}) {
  const openClaimsCount = (supplyClaims || []).filter(c=>c.status==='Открыта').length;

  const startReceiving = (delivery, isReceiving) => {
    setReceivingDeliveryId(isReceiving ? null : delivery.id);
    setReceiveForm({
      receivedQuantity: String(delivery.shippedQuantity || delivery.plannedQuantity || ''),
      qualityStatus: 'Принято',
      qualityNotes: '',
      photoUrl: '',
      claimDescription: '',
    });
  };

  const scanInvoice = async (event, delivery) => {
    const file = event.target.files[0];
    if (!file) return;
    setDeliveryAiLoadingId(delivery.id);
    try {
      const normalized = await normalizeInvoiceImageFile(file);
      const resp = await fetch(API+'/scan-invoice',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({image:{
          data: normalized.base64,
          mimeType: normalized.mimeType,
          name: normalized.originalName,
        }}),
      });
      const parsed = await resp.json();
      const items = parsed?.data?.items || [];
      await runDeliveryAiCheck(delivery, items);
      const match = items.find(it=>String(it.name||'').toLowerCase().includes(String(delivery.materialName||'').split(' ')[0].toLowerCase()));
      if (match) {
        setReceiveForm(form=>({
          ...form,
          receivedQuantity:String(match.quantity||''),
          qualityNotes:'AI распознал: '+(match.name||'')+' '+(match.quantity||'')+' '+(match.unit||''),
        }));
      }
    } catch(error) {
      setDeliveryAiResultById(prev=>({...prev,[delivery.id]:error?.message || 'Не удалось распознать накладную'}));
    }
    setDeliveryAiLoadingId(null);
    event.target.value='';
  };

  const uploadReceptionFile = async (event, delivery) => {
    const file = event.target.files[0];
    if (!file) return;
    const url = await uploadPhoto(file,{projectName:delivery.project||delivery.projectName,context:'supply-deliveries'});
    setReceiveForm({...receiveForm, photoUrl:url});
  };

  return (
    <div style={{...card,padding:'16px',marginBottom:'16px'}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'8px',flexWrap:'wrap',marginBottom:'10px'}}>
        <div>
          <b style={{color:C.text,fontSize:'14px'}}>🚚 Поставки и приёмка</b>
          <p style={{color:C.textSec,fontSize:'11px',margin:'2px 0 0'}}>Отгрузка поставщика → AI-сверка накладной → приёмка на склад объекта → претензия при проблеме.</p>
        </div>
        {openClaimsCount>0 && <span style={badge(C.danger,C.dangerLight,C.dangerBorder)}>⚠️ Претензий: {openClaimsCount}</span>}
      </div>

      {(supplyDeliveries||[]).length===0 && <p style={{color:C.textMuted,fontSize:'12px',margin:'8px 0'}}>Поставок пока нет. Они появятся после отгрузки выигранного КП поставщиком.</p>}

      {(supplyDeliveries||[]).slice(0,8).map(delivery=>{
        const problem = delivery.status==='Проблема';
        const done = delivery.status==='Принято';
        const stC = problem?C.danger:done?C.success:C.info;
        const stBg = problem?C.dangerLight:done?C.successLight:C.infoLight;
        const stBd = problem?C.dangerBorder:done?C.successBorder:C.infoBorder;
        const isReceiving = receivingDeliveryId===delivery.id;
        const canReceive = ['прораб','кладовщик','снабженец','директор','зам_директора'].includes(role) && !done;
        const claim = (supplyClaims||[]).find(c=>c.id===delivery.claimId || c.deliveryId===delivery.id);
        const linkedInvoice = (invoices||[]).find(inv=>String(inv.supplyDeliveryId||'')===String(delivery.id));

        return (
          <div key={delivery.id} style={{padding:'12px',border:'1.5px solid '+stBd,backgroundColor:stBg,borderRadius:'8px',marginBottom:'8px'}}>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
              <div style={{flex:'1 1 260px'}}>
                <b style={{color:C.text,fontSize:'13px'}}>{delivery.materialName}</b>
                <p style={{color:C.textSec,margin:'3px 0',fontSize:'12px'}}>{delivery.shippedQuantity || delivery.plannedQuantity} {delivery.unit} · 🏗 {delivery.project || '—'} · {delivery.supplierName || 'Поставщик'}</p>
                <p style={{color:C.textMuted,margin:0,fontSize:'11px'}}>ТТН/накладная: {delivery.waybillNumber || '—'}{delivery.vehicleNumber?' · авто '+delivery.vehicleNumber:''}{delivery.driverName?' · '+delivery.driverName:''}</p>
                {delivery.aiCheckResult && <p style={{color:C.accent,margin:'5px 0 0',fontSize:'11px'}}>🤖 {delivery.aiCheckResult}</p>}
                {claim && <p style={{color:C.danger,margin:'5px 0 0',fontSize:'11px'}}>⚠️ Претензия: {claim.claimType} · {claim.status}</p>}
                {linkedInvoice && <p style={{color:C.success,margin:'5px 0 0',fontSize:'11px'}}>📄 Накладная № {linkedInvoice.number} · запись #{linkedInvoice.id}</p>}
              </div>
              <div style={{display:'flex',gap:'5px',flexWrap:'wrap',justifyContent:'flex-end'}}>
                <span style={badge(stC,stBg,stBd)}>{delivery.status}</span>
                <label style={{...btnG,padding:'5px 10px',fontSize:'11px',cursor:'pointer'}}>
                  <Bot size={11}/>AI накладная
                  <input type='file' accept={invoiceImageAccept} capture='environment' style={{display:'none'}} onChange={event=>scanInvoice(event, delivery)}/>
                </label>
                {canReceive && <button onClick={()=>startReceiving(delivery, isReceiving)} style={{...btnGr,padding:'5px 10px',fontSize:'11px'}}><Check size={11}/>Принять</button>}
                {linkedInvoice && <button onClick={()=>showPreview(buildInvoiceContent(linkedInvoice),'Накладная № '+linkedInvoice.number)} style={{...btnB,padding:'5px 10px',fontSize:'11px'}}>Печать накл.</button>}
              </div>
            </div>

            {deliveryAiLoadingId===delivery.id && <p style={{color:C.textMuted,fontSize:'11px',margin:'8px 0 0'}}>AI сверяет накладную...</p>}
            {deliveryAiResultById[delivery.id] && <div style={{padding:'8px 10px',backgroundColor:C.bg,border:'1px solid '+C.border,borderRadius:'6px',fontSize:'11px',color:C.text,marginTop:'8px'}}>{deliveryAiResultById[delivery.id]}</div>}

            {isReceiving && (
              <div style={{borderTop:'1.5px solid '+C.border,paddingTop:'10px',marginTop:'10px'}}>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginBottom:'8px'}}>
                  <input type='number' step='any' inputMode='decimal' value={receiveForm.receivedQuantity} onChange={e=>setReceiveForm({...receiveForm,receivedQuantity:e.target.value})} placeholder='Принято количество' style={{...inp,marginBottom:0}}/>
                  <select value={receiveForm.qualityStatus} onChange={e=>setReceiveForm({...receiveForm,qualityStatus:e.target.value})} style={{...inp,marginBottom:0}}>
                    <option>Принято</option>
                    <option>Частично</option>
                    <option>Недостача</option>
                    <option>Брак</option>
                    <option>Несоответствие</option>
                  </select>
                </div>
                <textarea value={receiveForm.qualityNotes} onChange={e=>setReceiveForm({...receiveForm,qualityNotes:e.target.value})} placeholder='Комментарий по качеству / упаковке / документам' style={{...inp,height:'54px',resize:'vertical'}}/>
                {receiveForm.qualityStatus!=='Принято' && <textarea value={receiveForm.claimDescription} onChange={e=>setReceiveForm({...receiveForm,claimDescription:e.target.value})} placeholder='Текст претензии поставщику' style={{...inp,height:'54px',resize:'vertical'}}/>}
                <label style={{...btnG,padding:'7px 12px',fontSize:'12px',cursor:'pointer',display:'inline-flex',marginBottom:'8px'}}>
                  <Upload size={12}/>{receiveForm.photoUrl?'Фото загружено':'Фото приёмки'}
                  <input type='file' accept='image/*,.pdf' style={{display:'none'}} onChange={event=>uploadReceptionFile(event, delivery)}/>
                </label>
                <div style={{display:'flex',gap:'8px'}}>
                  <button onClick={()=>receiveSupplyDelivery(delivery)} style={btnO}><Check size={14}/>Сохранить приёмку</button>
                  <button onClick={()=>setReceivingDeliveryId(null)} style={btnG}><X size={14}/>Отмена</button>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default SupplyDeliveriesPanel;
