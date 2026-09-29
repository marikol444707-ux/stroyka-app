import React,{useEffect,useRef,useState} from 'react';
import ContractPartyFields from './ContractPartyFields';
import {legalDraft} from './contractReviewClient';
import './SupplierContractReviewPanel.css';
export default function SupplierContracts(props){
 if(!Number.isSafeInteger(props.companyId)||!Number.isSafeInteger(props.supplierId))return null;
 return <Contracts key={`${props.companyId}:${props.supplierId}:${props.userId}`} {...props}/>;
}
function Contracts({API,companyId,supplierId,userId}){
 const base=`${API}/companies/${companyId}/suppliers/${supplierId}/contracts`;
 const key=`supplier-original:${API}:${userId}:${companyId}:${supplierId}`;
 const [data,setData]=useState(null),[form,setForm]=useState(null),[side,setSide]=useState('supplier');
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[checked,setChecked]=useState(false);
 const [recognized,setRecognized]=useState(null),[pending,setPending]=useState(null),[success,setSuccess]=useState('');
 const active=useRef(true),running=useRef(false);
 const request=async(url,options={})=>{
  const r=await fetch(url,{credentials:'include',...options,headers:{'X-Company-Id':String(companyId),'X-Company-Mode':'company',...(options.body instanceof FormData?{}:{'Content-Type':'application/json'})}});
  const value=await r.json();if(!r.ok){const e=new Error(typeof value.detail==='string'?value.detail:'Проверьте заполнение полей.');e.status=r.status;throw e;}return value;
 };
 const load=async()=>{const value=await request(base);if(value.companyId!==companyId||value.supplierId!==supplierId)throw new Error('Компания изменилась. Откройте карточку заново.');if(active.current)setData(value);};
 useEffect(()=>{active.current=true;load().catch(e=>{if(active.current)setError(e.message);});
  try{const value=localStorage.getItem(key);if(value)setPending(JSON.parse(value));}catch(e){setError('Не удалось прочитать незавершённое сохранение.');}
  return()=>{active.current=false;};
  // Remount on company, supplier or user change.
  // eslint-disable-next-line react-hooks/exhaustive-deps
 },[base,key]);
 const act=async work=>{if(running.current)return;running.current=true;setBusy(true);setError('');try{await work();}catch(e){if(active.current)setError(e.message);}finally{running.current=false;if(active.current)setBusy(false);}};
 const edit=(source=null,addendum=false)=>{const s=source?.snapshot;setSuccess('');setRecognized(null);setChecked(false);
  setForm({requestId:crypto.randomUUID(),sourceFileId:source?.sourceFileId||null,number:s?.number||'',date:s?.date||'',buyer:legalDraft(s?.buyer||data.buyer),supplier:legalDraft(s?.supplier||data.supplier),
   paymentTerms:s?.paymentTerms||'',applicability:s?.applicability||{scope:'company',projectId:null,term:'',startsOn:'',endsOn:null},
   ...(source?{revisesContractId:source.id}:{}),...(addendum?{addendum:{sourceFileId:null,number:'',date:''}}:{})});};
 const change=patch=>{setChecked(false);setForm(v=>({...v,...patch}));};
 const upload=file=>act(async()=>{
  if(!file)return;const body=new FormData();body.append('file',file);body.append('context','supplier-contract');
  const uploaded=await request(`${API}/upload-photo`,{method:'POST',body});
  if(uploaded.companyId!==companyId||!Number.isSafeInteger(uploaded.fileId))throw new Error('Файл не подтверждён в компании.');
  if(!active.current)return;
  setRecognized(null);setChecked(false);
  setForm(v=>v.addendum?{...v,addendum:{...v.addendum,sourceFileId:uploaded.fileId}}:{...v,sourceFileId:uploaded.fileId});
  const result=await request(base+'/recognize',{method:'POST',body:JSON.stringify({sourceFileId:uploaded.fileId})});
  if(!active.current)return;
  if(result.companyId!==companyId||result.supplierId!==supplierId||result.sourceFileId!==uploaded.fileId)throw new Error('Результат относится к другому документу.');
  setRecognized(result.parties);
  setForm(v=>{const next={...v};for(const party of ['buyer','supplier']){next[party]={...v[party]};const found=result.parties?.[party];
   if(found?.status==='matched')for(const [field,item] of Object.entries(found.fields||{}))if(field in next[party]&&field!=='inn'&&!next[party][field])next[party][field]=item.value;}return next;});
 });
 const save=()=>act(async()=>{
  const body=pending||{...form,reviewConfirmed:checked};
  if(!pending){if(!checked)throw new Error('Проверьте реквизиты.');localStorage.setItem(key,JSON.stringify(body));if(localStorage.getItem(key)!==JSON.stringify(body))throw new Error('Не удалось подготовить сохранение.');setPending(body);}
  try{const saved=await request(base,{method:'POST',body:JSON.stringify(body)});
   if(saved.companyId!==companyId||saved.snapshot?.supplier?.supplierId!==supplierId)throw new Error('Не удалось подтвердить результат. Повторите сохранение.');
   localStorage.removeItem(key);if(!active.current)return;setPending(null);setForm(null);setSuccess('Договор сохранён. Повторно загружать его в КП не нужно.');await load();
  }catch(e){if(e.status===409||e.status===422||e.status===403||e.status===404){localStorage.removeItem(key);if(active.current)setPending(null);}throw e;}
 });
 return <section onClick={e=>e.stopPropagation()} aria-label="Документы поставщика" className="supplier-contract-review">
  <h3>Документы · договоры</h3><p>Один договор для следующих КП и счетов вашей компании.</p>
  {error&&<p role="alert">{error}</p>}{success&&<p role="status">{success}</p>}
  {!data&&!error&&<p>Загрузка…</p>}
  {pending?<div><p>Сохранение ещё не подтверждено. Повтор безопасен.</p><button disabled={busy} onClick={save}>Проверить сохранение</button></div>:form?<form onSubmit={e=>{e.preventDefault();save();}}>
   <fieldset disabled={busy} className="contract-review-content"><legend>{form.addendum?'Допсоглашение':'Договор поставки'}</legend>
    <label>{form.addendum?'Файл допсоглашения':'Файл договора'}<input type="file" accept=".pdf,.doc,.docx,.txt,.jpg,.jpeg,.png" onChange={e=>upload(e.target.files?.[0])}/></label>
    {(form.addendum?.sourceFileId||form.sourceFileId)&&<p>Файл загружен.</p>}
    <label>Номер договора<input required readOnly={Boolean(form.addendum)} value={form.number} onChange={e=>change({number:e.target.value})}/></label>
    <label>Дата договора<input required type="date" readOnly={Boolean(form.addendum)} value={form.date} onChange={e=>change({date:e.target.value})}/></label>
    {form.addendum&&<><label>Номер допсоглашения<input required value={form.addendum.number} onChange={e=>change({addendum:{...form.addendum,number:e.target.value}})}/></label><label>Дата допсоглашения<input required type="date" value={form.addendum.date} onChange={e=>change({addendum:{...form.addendum,date:e.target.value}})}/></label></>}
    <label>Срок<select required value={form.applicability.term} onChange={e=>change({applicability:{...form.applicability,term:e.target.value,endsOn:null}})}><option value="">Выберите</option><option value="open_ended">Без окончания</option><option value="fixed">До указанной даты</option></select></label>
    <label>Действует с<input required type="date" value={form.applicability.startsOn} onChange={e=>change({applicability:{...form.applicability,startsOn:e.target.value}})}/></label>
    {form.applicability.term==='fixed'&&<label>Действует по<input required type="date" min={form.applicability.startsOn} value={form.applicability.endsOn||''} onChange={e=>change({applicability:{...form.applicability,endsOn:e.target.value}})}/></label>}
    <div className="contract-actions">{['supplier','buyer'].map(s=><button type="button" key={s} onClick={()=>setSide(s)}>{s==='supplier'?'Поставщик':'Наша компания'}</button>)}</div>
    <ContractPartyFields side={side} value={form[side]} profile={data[side]} recognized={recognized?.[side]} onChange={(field,value)=>change({[side]:{...form[side],[field]:value}})} onApply={(field,value)=>change({[side]:{...form[side],[field]:value}})}/>
    <label>Условия оплаты<textarea value={form.paymentTerms} onChange={e=>change({paymentTerms:e.target.value})}/></label>
    <label><input type="checkbox" checked={checked} onChange={e=>setChecked(e.target.checked)}/>Реквизиты и условия проверены</label>
    <div className="contract-actions"><button type="submit" disabled={!checked||!form.sourceFileId||(form.addendum&&!form.addendum.sourceFileId)}>Сохранить договор</button><button type="button" onClick={()=>setForm(null)}>Отмена</button></div>
   </fieldset></form>:data&&<>
    <button type="button" onClick={()=>edit()}>Добавить договор</button>
    {data.items.length===0&&<p>Договоров пока нет.</p>}
    {data.items.map(item=><article key={item.id} className="supplier-contract-item"><h4>№ {item.snapshot.number} от {item.snapshot.date}{item.archived?' · в архиве':''}</h4>
     <a href={`${API}${item.sourceFileUrl}`} target="_blank" rel="noopener noreferrer">Открыть договор</a>
     {item.snapshot.addenda?.map(a=><p key={a.sourceFileId}><a href={`${API}/tenant-files/${a.sourceFileId}/content`} target="_blank" rel="noopener noreferrer">Допсоглашение № {a.number}</a></p>)}
     {!item.archived&&<div className="contract-actions"><button onClick={()=>edit(item)}>Изменить</button><button onClick={()=>edit(item,true)}>Добавить допсоглашение</button></div>}
    </article>)}
   </>}
 </section>;
}
