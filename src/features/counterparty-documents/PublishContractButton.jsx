import React,{useState} from 'react';

export default function PublishContractButton({API,companyId,row,buttonStyle,onPublished}) {
 const [confirm,setConfirm]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
 if(row.published)return <span>Передан поставщику</span>;
 const publish=async()=>{
  if(busy)return;setBusy(true);setError('');
  try {
   const response=await fetch(`${API}/supplier-offers/${row.offerId}/contracts/${row.sourceId}/publish`,{
    method:'POST',credentials:'include',headers:{'Content-Type':'application/json','X-Company-Id':String(companyId),'X-Company-Mode':'company'},body:JSON.stringify({confirmed:true})});
   const data=await response.json();
   if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Не удалось передать договор');
   if(data.companyId!==Number(companyId)||data.contractId!==row.sourceId||data.offerId!==row.offerId||data.published!==true)throw new Error('Не удалось подтвердить передачу. Обновите список.');
   setConfirm(false);onPublished();
  }catch(e){setError(e.message || 'Проверьте связь и повторите передачу этой версии.');}
  finally{setBusy(false);}
 };
 return <div>
  {!confirm?<button style={buttonStyle} disabled={row.registryState?.archived} onClick={()=>setConfirm(true)}>Передать поставщику</button>:<div role="group" aria-label="Передача договора">
   <p>Передать «{row.title}» поставщику {row.supplierName || 'из этого КП'}?</p>
   <p>Будут доступны основной файл и допсоглашения этой версии. Остальной архив компании останется закрытым.</p>
   {error&&<p role="alert">{error}</p>}
   <button style={buttonStyle} disabled={busy} onClick={publish}>{busy?'Передаём…':'Подтвердить передачу'}</button>{' '}
   <button style={buttonStyle} disabled={busy} onClick={()=>{setConfirm(false);setError('');}}>Отмена</button>
  </div>}
 </div>;
}
