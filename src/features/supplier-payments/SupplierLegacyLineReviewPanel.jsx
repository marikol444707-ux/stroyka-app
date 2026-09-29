import React,{useEffect,useMemo,useRef,useState} from 'react';
import {createLegacyLineReviewClient} from './legacyLineReviewClient';
const tax=value=>/^\d{1,12}(?:\.\d{1,2})?$/.test(value)?`${value.split('.')[0]}.${(value.split('.')[1]||'').padEnd(2,'0')}`:null;
export default function SupplierLegacyLineReviewPanel(props){
 if(process.env.REACT_APP_SUPPLIER_LEGACY_LINE_REVIEW_ENABLED!=='true')return null;
 return <Review key={`${props.API}:${props.userId}:${props.companyId}:${props.invoiceId}`} {...props}/>;
}
function Review({API,userId,companyId,invoiceId,disabled,onBlocked,onSuccess}){
 const abort=useRef(null),live=useRef(true),running=useRef(false);
 const client=useMemo(()=>createLegacyLineReviewClient({API,userId,companyId,invoiceId},{signal:()=>abort.current?.signal}),[API,userId,companyId,invoiceId]);
 const [draft,setDraft]=useState(null),[pending,setPending]=useState(null),[busy,setBusy]=useState(false);
 const [error,setError]=useState(''),[fatal,setFatal]=useState(false),[done,setDone]=useState(false);
 const [taxes,setTaxes]=useState([]),[file,setFile]=useState(null),[reason,setReason]=useState(''),[checked,setChecked]=useState(false);
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
  setDraft(value);setTaxes(value.lines.map(()=>''));setFile(null);setReason('');setChecked(false);setDone(false);
 });
 const uploaded=e=>{const selected=e.target.files?.[0];e.target.value='';if(!selected)return;
  act(async()=>{const result=await client.upload(selected);if(live.current){setFile({...result,name:selected.name});setChecked(false);}});
 };
 const finish=async body=>{await client.save(body);if(live.current){setDraft(null);setDone(true);setChecked(false);onSuccess?.();}};
 const ready=!!draft && !!file && checked && !!reason.trim() && taxes.length===draft.lines.length && taxes.every(v=>tax(v)!==null);
 const submit=()=>{if(!ready || pending)return;act(()=>finish({requestId:window.crypto.randomUUID(),
  contractVersionId:draft.contractVersionId,sourceFileId:file.fileId,expectedAmount:draft.amount,vatAmount:draft.vatAmount,
  reason:reason.trim(),confirmed:true,lines:draft.lines.map(({lineNo,...row},index)=>({...row,vatAmount:tax(taxes[index])}))}));};
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
    <label>Оригинал счёта<input type="file" accept=".pdf,.txt,.doc,.docx,.jpg,.jpeg,.png" onChange={uploaded}/></label>
    {file && <p>Загружен: {file.name}</p>}
    {draft.lines.map((line,index)=><fieldset key={line.lineNo}><legend>{line.lineNo}. {line.materialName}</legend>
      <p>{line.quantity} {line.unit} × {line.unitPrice} ₽ = {line.amount} ₽. Раздел: {line.workPackage}</p>
      <label>НДС строки {line.lineNo}, ₽<input inputMode="decimal" value={taxes[index]} onChange={e=>{setTaxes(v=>v.map((value,i)=>i===index?e.target.value.replace(',','.'):value));setChecked(false);}}/></label>
     </fieldset>)}
    <p>Введите НДС каждой строки. Если НДС нет, явно укажите 0.</p>
    <label>Основание сверки<textarea maxLength={1000} value={reason} onChange={e=>setReason(e.target.value)}/></label>
    <label className="supplier-original-review-check"><input type="checkbox" checked={checked} onChange={e=>setChecked(e.target.checked)}/>Количество, цены, суммы и НДС каждой позиции сверены с оригиналом</label>
    <button type="button" disabled={!ready} onClick={submit}>Подтвердить состав счёта</button>
    <button type="button" onClick={()=>{setDraft(null);setChecked(false);}}>Закрыть сверку</button>
   </fieldset>}
 </section>;
}
