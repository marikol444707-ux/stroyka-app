import React,{useEffect,useRef,useState} from 'react';
export default function SavedContractChoice({API,companyId,offerId,disabled,onSaved,onFallback}){
 const alive=useRef(true),running=useRef(false);
 const [items,setItems]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [retryId,setRetryId]=useState(null);
 const url=`${API}/supplier-offers/${offerId}/saved-contracts`;
 const headers={'X-Company-Id':String(companyId),'X-Company-Mode':'company'};
 useEffect(()=>{
  const abort=new AbortController();let active=true;alive.current=true;
  Promise.resolve().then(()=>fetch(url,{credentials:'include',headers:{'X-Company-Id':String(companyId),'X-Company-Mode':'company'},signal:abort.signal}))
   .then(async response=>{if(!response.ok)throw new Error();return response.json();})
   .then(data=>{if(active){if(data.items?.length)setItems(data.items);else onFallback();}})
   .catch(()=>{if(active)onFallback();});
  return()=>{active=false;alive.current=false;abort.abort();};
 },[url,companyId,onFallback]);
 const choose=async id=>{
  if(running.current)return;running.current=true;setBusy(true);setError('');setRetryId(id);
  try{
   const response=await fetch(url,{method:'POST',credentials:'include',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({contractId:id})});
   const data=await response.json();
   if(!alive.current)return;
   if(!response.ok){if(response.status===409)setRetryId(null);throw new Error(typeof data.detail==='string'?data.detail:'Не удалось выбрать договор.');}
   if(data.companyId!==companyId||data.offerId!==offerId||data.sourceContractId!==id)throw new Error('Не удалось подтвердить выбор. Повторите попытку.');
   onSaved?.();
  }catch(e){if(alive.current)setError(e.message || 'Нет связи. Повторите выбор того же договора.');}
  finally{running.current=false;if(alive.current)setBusy(false);}
 };
 return <div className="contract-upload-card">
  <h4>Выберите договор</h4>
  <p>Эти договоры уже проверены. Загружать файл и заполнять реквизиты заново не нужно.</p>
  {!items&&<p role="status">Ищем сохранённые договоры…</p>}
  {error&&<p role="alert">{error}</p>}
  {items?.map(item=><div key={item.id} style={{display:'flex',flexWrap:'wrap',gap:12,alignItems:'center',padding:'12px 0'}}>
   <a href={`${API}/tenant-files/${item.sourceFileId}/content`} target="_blank" rel="noopener noreferrer">№ {item.number} от {item.date}</a>
   <button type="button" disabled={disabled||busy||(retryId!==null&&retryId!==item.id)} onClick={()=>choose(item.id)}>{retryId===item.id?'Повторить выбор':'Использовать'}</button>
  </div>)}
  <button type="button" disabled={busy||retryId!==null} onClick={onFallback}>Загрузить новый или изменить договор</button>
 </div>;
}
