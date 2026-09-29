import React, {useEffect,useState} from 'react';
import PublishContractButton from './PublishContractButton';

const categories=[
 ['company','Документы компании','company'],
 ['supplier','Документы поставщиков','supplier'],
 ['contract','Договоры поставки','supplier'],
 ['offer','КП','supplier'],
 ['invoice','Счета','supplier'],
 ['delivery','Отгрузки','supplier'],
 ['warehouse','Складские накладные','supplier'],
 ['customer','Документы заказчиков','customer'],
];

export default function CompanyDocumentArchive(props) {
 return <Archive key={props.companyId || 'none'} {...props}/>;
}
function Archive({API,companyId,C,card,inp,btnG,setShowPhotoModal}) {
 const [section,setSection]=useState('all'),[query,setQuery]=useState(''),[search,setSearch]=useState(''),[offset,setOffset]=useState(0);
 const [category,setCategory]=useState('');
 const [refresh,setRefresh]=useState(0),[decision,setDecision]=useState(null),[saving,setSaving]=useState(false),[decisionError,setDecisionError]=useState('');
 const [focused,setFocused]=useState(null),[related,setRelated]=useState(null);
 const [data,setData]=useState(null),[error,setError]=useState(''),[loading,setLoading]=useState(false);
 useEffect(()=>{
  if(!companyId)return;
  const controller=new AbortController();let active=true;
  setLoading(true);setData(null);setError('');
  const params=new URLSearchParams(related?{section:'supplier',[related.kind==='versions'?'registryId':'contractId']:String(related.id),offset:String(related.offset),limit:'30'}:focused?{section:'all',source:focused.source,recordId:String(focused.id),limit:'1'}:{section,q:search,offset:String(offset),limit:'30'});
  if(category&&!focused&&!related)params.set('category',category);
  fetch(`${API}/company-document-archive?${params}`,{signal:controller.signal,headers:{'X-Company-Id':String(companyId),'X-Company-Mode':'company'}})
   .then(async response=>{const value=await response.json();if(!response.ok)throw new Error(typeof value.detail==='string'?value.detail:'Не удалось загрузить архив');
    if(value.requiresCompanySelection || Number(value.companyId)!==Number(companyId) || !Array.isArray(value.items) || value.items.some(row=>Number(row.companyId)!==Number(companyId)))throw new Error('Компания архива изменилась. Обновите раздел.');
    if(related && value.items.some(row=>related.kind==='versions'?(row.source!=='contract'||Number(row.registryId)!==related.id):(row.source!=='invoice' || Number(row.contractId)!==related.id)))throw new Error('Документы не соответствуют выбранному договору.');
    if(!related && focused && value.items.some(row=>row.source!==focused.source || Number(row.sourceId)!==focused.id))throw new Error('Ответ не соответствует выбранному документу.');
    if(!focused&&!related&&category&&value.items.some(row=>row.source!==category))throw new Error('Ответ не соответствует выбранному виду документов.');
    if(active)setData(value);})
   .catch(e=>{if(active && e.name!=='AbortError')setError(e.message);})
   .finally(()=>{if(active)setLoading(false);});
  return()=>{active=false;controller.abort();};
 },[API,companyId,section,search,offset,focused,related,category,refresh]);
 async function changeArchive() {
  if(saving||!decision)return;
  setSaving(true);setDecisionError('');
  try {
   const response=await fetch(`${API}/supplier-contract-registry/${decision.registryId}/archive`,{
    method:'PUT',headers:{'Content-Type':'application/json','X-Company-Id':String(companyId),'X-Company-Mode':'company'},
    body:JSON.stringify({archived:!decision.registryState.archived,expectedVersion:decision.registryState.version})});
   const value=await response.json();
   if(!response.ok)throw new Error(typeof value.detail==='string'?value.detail:'Не удалось изменить статус договора');
   if(Number(value.companyId)!==Number(companyId)||Number(value.registryId)!==Number(decision.registryId)||value.archived!==!decision.registryState.archived||value.stateVersion!==decision.registryState.version+1)throw new Error('Не удалось подтвердить изменение. Обновите список и проверьте статус договора.');
   setDecision(null);
  } catch(e) {setDecisionError(e.message || 'Не удалось подтвердить изменение. Обновите список и проверьте статус договора.');}
  finally {setSaving(false);setRefresh(v=>v+1);}
 }
 if(!companyId)return <p role="status">Выберите компанию, чтобы открыть её архив.</p>;
 return <section style={{...card,padding:20}} aria-label="Архив документов компании">
  <h3 style={{color:C.text}}>Архив документов</h3>
  <p style={{color:C.textSec}}>Договоры, счета, накладные и другие документы вашей компании.</p>
  <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>{[['all','Все документы'],['company','Моя компания'],['supplier','Поставщики'],['customer','Заказчики']].map(([value,label])=>
   <button key={value} style={btnG} aria-pressed={section===value} onClick={()=>{setRelated(null);setFocused(null);setSection(value);setCategory('');setOffset(0);}}>{label}</button>)}</div>
  <form style={{display:'flex',gap:8,flexWrap:'wrap',alignItems:'flex-end',marginTop:16}} onSubmit={e=>{e.preventDefault();setRelated(null);setFocused(null);setSearch(query.trim());setOffset(0);}}>
   <label style={{display:'flex',flexDirection:'column',gap:6,flex:'1 1 200px',minWidth:0,color:C.textSec}}>Вид документа
    <select value={category} onChange={e=>{setCategory(e.target.value);setFocused(null);setRelated(null);setOffset(0);}} style={{...inp,width:'100%',minWidth:0}}>
     <option value="">Все виды документов</option>
     {categories.filter(([, ,group])=>section==='all'||group===section).map(([value,label])=><option key={value} value={value}>{label}</option>)}
    </select>
   </label>
   <input aria-label="Поиск документов" placeholder="Название, номер или тип документа" maxLength={200} value={query} onChange={e=>setQuery(e.target.value)} style={{...inp,flex:'1 1 200px',minWidth:0}}/>
   <button style={btnG} type="submit">Найти</button>
  </form>
  {(focused||related)&&<button style={{...btnG,marginTop:16}} onClick={()=>{if(related)setRelated(related.parent || null);else setFocused(null);}}>Вернуться к списку</button>}
  {related&&<p><strong>{related.kind==='versions'?'История договора':'Счета'}: {related.title}</strong></p>}
  {decision&&<div role="dialog" aria-label="Статус договора" style={{...card,padding:16,marginTop:16,border:`1px solid ${C.border}`}}>
   <strong>{decision.registryState.archived?'Восстановить договор?':'Перенести договор в архив?'}</strong>
   <p>{decision.title}</p>
   <p>{decision.registryState.archived?'Договор снова можно будет использовать, если его срок и условия подходят к новому КП.':'Все версии останутся в истории. Для новых КП этот договор будет недоступен. Старые счета сохранятся.'}</p>
   {decisionError&&<p role="alert">{decisionError}</p>}
   <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
    <button style={btnG} disabled={saving||!!decisionError} onClick={changeArchive}>{saving?'Сохраняем…':'Подтвердить'}</button>
    <button style={btnG} disabled={saving} onClick={()=>{setDecision(null);setDecisionError('');}}>{decisionError?'Закрыть и проверить статус':'Отмена'}</button>
   </div>
  </div>}
  {loading&&<p role="status">Загружаем документы…</p>}
  {error&&<p role="alert">{error}</p>}
  {data?.items.length===0&&<p>{related?(related.kind==='versions'?'Версии договора недоступны в выбранной компании.':'К этой версии договора счета ещё не привязаны.'):focused?'Документ недоступен в выбранной компании.':'Документы не найдены.'}</p>}
  {data?.items.map(row=><article key={row.id} style={{borderBottom:`1px solid ${C.border}`,padding:'14px 0'}}>
   <strong style={{color:C.text}}>{row.title || row.documentType}</strong>
   <p style={{color:C.textSec,margin:'6px 0'}}>{row.documentType}{row.createdAt ? ` · ${new Date(row.createdAt).toLocaleDateString('ru-RU')}`:''}</p>
   {row.applicability&&<p style={{color:C.textSec,margin:'6px 0'}}>
    {row.applicability.scope==='company'?'Все объекты компании':`Объект: ${row.scopeProjectName || 'не указан'}`}
    {' · с '}{row.applicability.startsOn?.split('-').reverse().join('.')}
    {row.applicability.term==='open_ended'?' · бессрочно':` по ${row.applicability.endsOn?.split('-').reverse().join('.')}`}
   </p>}
   {row.registryState?.archived&&<p style={{color:C.textSec}}>В архиве · недоступен для новых КП</p>}
   {row.addenda?.length>0&&<p style={{color:C.textSec}}>Допсоглашения: {row.addenda.map(a=>`№ ${a.number} от ${a.date.split('-').reverse().join('.')}`).join('; ')}</p>}
   {row.offerId&&<p style={{color:C.textSec,margin:'6px 0'}}>КП № {row.offerId}{row.contractVersion ? ` · Договор № ${row.contractNumber || 'без номера'}, версия ${row.contractVersion}`:''}</p>}
   <div style={{display:'flex',gap:8,flexWrap:'wrap',marginBottom:8}}>
    {row.source==='contract'&&row.registryId&&row.registryState&&<button disabled={saving||!!decision} style={btnG} onClick={()=>{setDecision(row);setDecisionError('');}}>{row.registryState.archived?'Восстановить':'В архив'}</button>}
    {row.source==='contract'&&<button style={btnG} onClick={()=>setRelated({id:row.sourceId,title:row.title,offset:0,parent:related?.kind==='versions'?related:null})}>Счета по этой версии</button>}
    {row.registryId&&related?.kind!=='versions'&&<button style={btnG} onClick={()=>setRelated({kind:'versions',id:row.registryId,title:row.title,offset:0})}>Все версии договора</button>}
    {row.originContractId&&<button style={btnG} onClick={()=>{setRelated(null);setFocused({source:'contract',id:row.originContractId});}}>Исходный договор</button>}
    {row.contractId&&<button style={btnG} onClick={()=>{setRelated(null);setFocused({source:'contract',id:row.contractId});}}>Показать договор</button>}
    {row.offerId&&<button style={btnG} onClick={()=>{setRelated(null);setFocused({source:'offer',id:row.offerId});}}>Показать КП</button>}
   </div>
   {row.source==='contract'&&row.offerId&&<PublishContractButton API={API} companyId={companyId} row={row} buttonStyle={btnG} onPublished={()=>setRefresh(v=>v+1)}/>}
   {row.projectName&&<p style={{color:C.textSec}}>{row.projectName}{row.status?` · ${row.status}`:''}</p>}
   {row.fileStatus==='not_attached'&&<span>Файл не прикреплён</span>}
   {row.fileStatus==='needs_review'&&<p>Часть вложений недоступна — требуется проверка.</p>}
   <div style={{display:'flex',flexWrap:'wrap',gap:8}}>{row.attachments.map((file,index)=><button key={file.fileId} style={btnG} onClick={()=>setShowPhotoModal(file.fileUrl)}>{row.source==='contract'&&row.addenda?.length?(row.addenda.find(a=>a.sourceFileId===file.fileId)?`Допсоглашение № ${row.addenda.find(a=>a.sourceFileId===file.fileId).number}`:'Основной договор'):row.attachments.length===1?'Открыть файл':`Открыть файл ${index+1}`}</button>)}</div>
  </article>)}
  {data&&related&&<div style={{display:'flex',gap:8,marginTop:16}}>
   <button style={btnG} disabled={related.offset===0} onClick={()=>setRelated(v=>({...v,offset:Math.max(0,v.offset-30)}))}>Назад</button>
   <button style={btnG} disabled={!data.hasMore} onClick={()=>setRelated(v=>({...v,offset:data.nextOffset}))}>Далее</button>
  </div>}
  {data&&!focused&&!related&&<div style={{display:'flex',gap:8,marginTop:16}}>
   <button style={btnG} disabled={offset===0} onClick={()=>setOffset(Math.max(0,offset-30))}>Назад</button>
   <button style={btnG} disabled={!data.hasMore} onClick={()=>setOffset(data.nextOffset)}>Далее</button>
  </div>}
 </section>;
}
