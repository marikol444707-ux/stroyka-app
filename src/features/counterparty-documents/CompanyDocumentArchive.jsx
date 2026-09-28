import React, {useEffect,useState} from 'react';

export default function CompanyDocumentArchive(props) {
 return <Archive key={props.companyId || 'none'} {...props}/>;
}
function Archive({API,companyId,C,card,inp,btnG,setShowPhotoModal}) {
 const [section,setSection]=useState('all'),[query,setQuery]=useState(''),[search,setSearch]=useState(''),[offset,setOffset]=useState(0);
 const [focused,setFocused]=useState(null);
 const [data,setData]=useState(null),[error,setError]=useState(''),[loading,setLoading]=useState(false);
 useEffect(()=>{
  if(!companyId)return;
  const controller=new AbortController();let active=true;
  setLoading(true);setData(null);setError('');
  const params=new URLSearchParams(focused?{section:'all',source:focused.source,recordId:String(focused.id),limit:'1'}:{section,q:search,offset:String(offset),limit:'30'});
  fetch(`${API}/company-document-archive?${params}`,{signal:controller.signal,headers:{'X-Company-Id':String(companyId),'X-Company-Mode':'company'}})
   .then(async response=>{const value=await response.json();if(!response.ok)throw new Error(typeof value.detail==='string'?value.detail:'Не удалось загрузить архив');
    if(value.requiresCompanySelection || Number(value.companyId)!==Number(companyId) || !Array.isArray(value.items) || value.items.some(row=>Number(row.companyId)!==Number(companyId)))throw new Error('Компания архива изменилась. Обновите раздел.');
    if(focused && value.items.some(row=>row.source!==focused.source || Number(row.sourceId)!==focused.id))throw new Error('Ответ не соответствует выбранному документу.');
    if(active)setData(value);})
   .catch(e=>{if(active && e.name!=='AbortError')setError(e.message);})
   .finally(()=>{if(active)setLoading(false);});
  return()=>{active=false;controller.abort();};
 },[API,companyId,section,search,offset,focused]);
 if(!companyId)return <p role="status">Выберите компанию, чтобы открыть её архив.</p>;
 return <section style={{...card,padding:20}} aria-label="Архив документов компании">
  <h3 style={{color:C.text}}>Архив документов</h3>
  <p style={{color:C.textSec}}>Договоры, счета, накладные и другие документы вашей компании.</p>
  <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>{[['all','Все документы'],['company','Моя компания'],['supplier','Поставщики'],['customer','Заказчики']].map(([value,label])=>
   <button key={value} style={btnG} aria-pressed={section===value} onClick={()=>{setFocused(null);setSection(value);setOffset(0);}}>{label}</button>)}</div>
  <form style={{display:'flex',gap:8,flexWrap:'wrap',marginTop:16}} onSubmit={e=>{e.preventDefault();setFocused(null);setSearch(query.trim());setOffset(0);}}>
   <input aria-label="Поиск документов" placeholder="Название, номер или тип документа" maxLength={200} value={query} onChange={e=>setQuery(e.target.value)} style={{...inp,flex:'1 1 200px',minWidth:0}}/>
   <button style={btnG} type="submit">Найти</button>
  </form>
  {focused&&<button style={{...btnG,marginTop:16}} onClick={()=>setFocused(null)}>Вернуться к списку</button>}
  {loading&&<p role="status">Загружаем документы…</p>}
  {error&&<p role="alert">{error}</p>}
  {data?.items.length===0&&<p>{focused?'Документ недоступен в выбранной компании.':'Документы не найдены.'}</p>}
  {data?.items.map(row=><article key={row.id} style={{borderBottom:`1px solid ${C.border}`,padding:'14px 0'}}>
   <strong style={{color:C.text}}>{row.title || row.documentType}</strong>
   <p style={{color:C.textSec,margin:'6px 0'}}>{row.documentType}{row.createdAt ? ` · ${new Date(row.createdAt).toLocaleDateString('ru-RU')}`:''}</p>
   {row.offerId&&<p style={{color:C.textSec,margin:'6px 0'}}>КП № {row.offerId}{row.contractVersion ? ` · Договор № ${row.contractNumber || 'без номера'}, версия ${row.contractVersion}`:''}</p>}
   <div style={{display:'flex',gap:8,flexWrap:'wrap',marginBottom:8}}>
    {row.contractId&&<button style={btnG} onClick={()=>setFocused({source:'contract',id:row.contractId})}>Показать договор</button>}
    {row.offerId&&<button style={btnG} onClick={()=>setFocused({source:'offer',id:row.offerId})}>Показать КП</button>}
   </div>
   {row.projectName&&<p style={{color:C.textSec}}>{row.projectName}{row.status?` · ${row.status}`:''}</p>}
   {row.fileStatus==='not_attached'&&<span>Файл не прикреплён</span>}
   {row.fileStatus==='needs_review'&&<p>Часть вложений недоступна — требуется проверка.</p>}
   <div style={{display:'flex',flexWrap:'wrap',gap:8}}>{row.attachments.map((file,index)=><button key={file.fileId} style={btnG} onClick={()=>setShowPhotoModal(file.fileUrl)}>{row.attachments.length===1?'Открыть файл':`Открыть файл ${index+1}`}</button>)}</div>
  </article>)}
  {data&&!focused&&<div style={{display:'flex',gap:8,marginTop:16}}>
   <button style={btnG} disabled={offset===0} onClick={()=>setOffset(Math.max(0,offset-30))}>Назад</button>
   <button style={btnG} disabled={!data.hasMore} onClick={()=>setOffset(data.nextOffset)}>Далее</button>
  </div>}
 </section>;
}
