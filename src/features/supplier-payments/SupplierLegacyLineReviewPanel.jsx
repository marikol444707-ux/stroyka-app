import React,{useEffect,useMemo,useRef,useState} from 'react';
import {createLegacyLineReviewClient} from './legacyLineReviewClient';
const tax=value=>/^\d{1,12}(?:\.\d{1,2})?$/.test(value)?`${value.split('.')[0]}.${(value.split('.')[1]||'').padEnd(2,'0')}`:null;
const quantity=value=>/^\d{1,12}(?:\.\d{1,6})?$/.test(value)&&Number(value)>0?`${value.split('.')[0]}.${(value.split('.')[1]||'').padEnd(6,'0')}`:null;
export default function SupplierLegacyLineReviewPanel(props){
 if(process.env.REACT_APP_SUPPLIER_LEGACY_LINE_REVIEW_ENABLED!=='true')return null;
 return <Review key={`${props.API}:${props.userId}:${props.companyId}:${props.invoiceId}`} {...props}/>;
}
function Review({API,userId,companyId,invoiceId,disabled,onBlocked,onSuccess}){
 const abort=useRef(null),live=useRef(true),running=useRef(false);
 const client=useMemo(()=>createLegacyLineReviewClient({API,userId,companyId,invoiceId},{signal:()=>abort.current?.signal}),[API,userId,companyId,invoiceId]);
 const [draft,setDraft]=useState(null),[pending,setPending]=useState(null),[busy,setBusy]=useState(false);
 const [error,setError]=useState(''),[fatal,setFatal]=useState(false),[done,setDone]=useState(false);
 const [rows,setRows]=useState([]),[file,setFile]=useState(null),[reason,setReason]=useState(''),[checked,setChecked]=useState(false);
 useEffect(()=>{abort.current=new AbortController();live.current=true;try{setPending(client.pending());}catch(e){setError(e.message);setFatal(true);}
  return()=>{live.current=false;abort.current.abort();};},[client]);
 useEffect(()=>{onBlocked?.(!!draft || !!pending || busy || fatal);return()=>onBlocked?.(false);},[draft,pending,busy,fatal,onBlocked]);
 const blocked=disabled || busy || fatal;
 const act=async work=>{
  if(blocked || running.current)return;
  running.current=true;setBusy(true);setError('');
  try{await work();}catch(e){if(live.current)setError(e.message);}
  finally{running.current=false;if(live.current){try{setPending(client.pending());}catch(e){setFatal(true);setError(e.message);}setBusy(false);}}
 };
 const load=()=>act(async()=>{const value=await client.load();if(!live.current)return;
  if(value.reviewed){setDone(true);return;}
  const source=value.sourceFile;
  setDraft(value);setRows(value.lines.map(line=>({quantity:line.quantity||'',amount:line.amount||'',vatAmount:''})));
  setFile(source&&Number.isSafeInteger(source.fileId)&&source.fileId>0&&source.url===`/tenant-files/${source.fileId}/content`
   ?{fileId:source.fileId,name:source.name||'Оригинал счёта',url:source.url,existing:true}:null);
  setReason('');setChecked(false);setDone(false);
 });
 const uploaded=e=>{const selected=e.target.files?.[0];e.target.value='';if(!selected)return;
  act(async()=>{const result=await client.upload(selected);if(live.current){setFile({...result,name:selected.name});setChecked(false);}});
 };
 const finish=async body=>{await client.save(body);if(live.current){setDraft(null);setDone(true);setChecked(false);onSuccess?.();}};
 const ready=!!draft && !!file && checked && !!reason.trim() && rows.length===draft.lines.length
  && rows.every(row=>quantity(row.quantity)!==null&&tax(row.amount)!==null&&tax(row.vatAmount)!==null);
 const submit=()=>{if(!ready || pending)return;act(()=>finish({requestId:window.crypto.randomUUID(),
  contractVersionId:draft.contractVersionId,sourceFileId:file.fileId,expectedAmount:draft.amount,vatAmount:draft.vatAmount,
  reason:reason.trim(),confirmed:true,lines:draft.lines.map((line,index)=>({
   sourceRequestPosition:line.sourceRequestPosition,sourceOfferPosition:line.sourceOfferPosition,
   materialName:line.materialName,unit:line.unit,workPackage:line.workPackage,unitPrice:line.unitPrice,
   quantity:quantity(rows[index].quantity),amount:tax(rows[index].amount),vatAmount:tax(rows[index].vatAmount)}))}));};
 return <section aria-label="Сверка состава старого счёта">
  <h3>Позиции счёта</h3>
  <p>Проверьте товары, количество, цены и НДС по счёту поставщика.</p>
  {error && <p role="alert">{error}</p>}
  {done && <p role="status">Состав и НДС подтверждены.</p>}
  {!draft && !pending && !done && <button type="button" disabled={blocked} onClick={load}>Проверить позиции</button>}
  {pending ? <><p>Сохранён запрос сверки. Повтор проверит его результат без создания второй записи.</p>
    <button type="button" disabled={blocked} onClick={()=>act(()=>finish(client.pending()))}>Проверить и повторить сверку</button></>
   : draft && <fieldset disabled={blocked}>
    <legend>Проверка по оригиналу счёта</legend>
    <p>Сумма счёта: {draft.amount} ₽. НДС в счёте: {draft.vatAmount} ₽. Позиции ниже взяты из утверждённого КП: проверьте каждую по оригиналу. При расхождении сначала исправьте исходные документы.</p>
    {file?.existing && <p>Прикреплённый оригинал: <strong>{file.name}</strong> · <a href={API+file.url} target="_blank" rel="noopener noreferrer">Открыть оригинал</a></p>}
    <label>{file?.existing?'Заменить оригинал счёта':'Оригинал счёта'}<input type="file" accept=".pdf,.txt,.doc,.docx,.jpg,.jpeg,.png" onChange={uploaded}/></label>
    {file && !file.existing && <p>Загружен: {file.name}</p>}
    {draft.lines.map((line,index)=><fieldset key={line.lineNo}><legend>{line.lineNo}. {line.materialName}</legend>
      <p>По КП: до {line.maxQuantity||line.quantity} {line.unit} · цена {line.unitPrice} ₽. Раздел: {line.workPackage}</p>
      <label>Количество по счёту, {line.unit}<input inputMode="decimal" value={rows[index]?.quantity||''} onChange={e=>{setRows(v=>v.map((row,i)=>i===index?{...row,quantity:e.target.value.replace(',','.')}:row));setChecked(false);}}/></label>
      <label>Сумма строки, ₽<input inputMode="decimal" value={rows[index]?.amount||''} onChange={e=>{setRows(v=>v.map((row,i)=>i===index?{...row,amount:e.target.value.replace(',','.')}:row));setChecked(false);}}/></label>
      <label>НДС строки {line.lineNo}, ₽<input inputMode="decimal" value={rows[index]?.vatAmount||''} onChange={e=>{setRows(v=>v.map((row,i)=>i===index?{...row,vatAmount:e.target.value.replace(',','.')}:row));setChecked(false);}}/></label>
     </fieldset>)}
    <p>Сверьте количества и суммы с оригиналом. НДС укажите для каждой строки; если НДС нет, введите 0.</p>
    <label>Основание сверки<textarea maxLength={1000} value={reason} onChange={e=>setReason(e.target.value)}/></label>
    <label className="supplier-original-review-check"><input type="checkbox" checked={checked} onChange={e=>setChecked(e.target.checked)}/>Количество, цены, суммы и НДС каждой позиции сверены с оригиналом</label>
    <button type="button" disabled={!ready} onClick={submit}>Подтвердить состав счёта</button>
    <button type="button" onClick={()=>{setDraft(null);setChecked(false);}}>Закрыть сверку</button>
   </fieldset>}
 </section>;
}
