import React, {useEffect,useMemo,useRef,useState} from 'react';
import {createContractReviewClient,legalDraft,legalFields} from './contractReviewClient';

const labels={fullName:'Полное наименование',inn:'ИНН',kpp:'КПП',ogrn:'ОГРН / ОГРНИП',legalAddress:'Юридический адрес',
 bankName:'Банк',bik:'БИК',rs:'Расчётный счёт',ks:'Корреспондентский счёт',directorName:'ФИО подписанта',
 directorPosition:'Должность подписанта',basis:'Основание полномочий',phone:'Телефон',email:'Email'};
const sides={buyer:'Покупатель',payer:'Плательщик',supplier:'Поставщик'};
const limits={fullName:500,kpp:9,ogrn:15,legalAddress:2000,bankName:500,bik:9,rs:20,ks:20,directorName:255,directorPosition:255,basis:1000,phone:100,email:255};
const patterns={inn:'(?:[0-9]{10}|[0-9]{12})',kpp:'[0-9]{9}',ogrn:'(?:[0-9]{13}|[0-9]{15})',bik:'[0-9]{9}',rs:'[0-9]{20}',ks:'[0-9]{20}'};

export default function SupplierContractReviewPanel(props) {
 return <ReviewContent key={`${props.API}:${props.userId}:${props.companyId}:${props.offerId}`} {...props}/>;
}
function ReviewContent({API,userId,companyId,offerId,disabled,onSaved,onClose}) {
 const controller=useRef(null);
 const client=useMemo(()=>createContractReviewClient({API,userId,companyId,offerId},{signal:()=>controller.current?.signal}),[API,userId,companyId,offerId]);
 const live=useRef(true),running=useRef(false);
 const [loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [pending,setPending]=useState(null),[fatal,setFatal]=useState(false);
 const [choices,setChoices]=useState([]),[parties,setParties]=useState(null);
 const [buyer,setBuyer]=useState(''),[payer,setPayer]=useState(''),[partyReason,setPartyReason]=useState('');
 const [review,setReview]=useState(null),[legal,setLegal]=useState({});
 const [number,setNumber]=useState(''),[date,setDate]=useState(''),[terms,setTerms]=useState(''),[reason,setReason]=useState('');
 const [file,setFile]=useState(null),[checked,setChecked]=useState(false);
 const blocked=disabled || busy || loading || fatal;
 const loadReview=async()=>{
  const value=await client.reviewContext();
  if(live.current){setReview(value);setLegal(Object.fromEntries(Object.keys(sides).map(side=>[side,legalDraft(value[side])])));setChecked(false);}
 };
 const loadParties=async()=>{
  const value=await client.load();
  if(live.current){setParties(value.parties);setChoices(value.companies);
   setBuyer(String(value.parties.buyerCompanyId || companyId));setPayer(String(value.parties.payerCompanyId || companyId));}
  return value;
 };
 useEffect(()=>{
  let cancelled=false;
  const abort=new AbortController();controller.current=abort;
  live.current=true;
  (async()=>{
   try{setPending(client.pending());await loadParties();}
   catch(e){if(live.current && !cancelled){setError(e.message);setFatal(true);}}
   finally{if(live.current && !cancelled)setLoading(false);}
  })();
  return ()=>{cancelled=true;live.current=false;abort.abort();};
  // Scope changes remount the whole form; no draft crosses a company boundary.
  // eslint-disable-next-line react-hooks/exhaustive-deps
 },[client]);
 const act=async work=>{
  if(running.current || blocked)return;
  running.current=true;setBusy(true);setError('');
  try{await work();}
  catch(e){
   if(live.current)setError(e.message);
   if(e.reloadContext && live.current){
    setChecked(false);setReview(null);
    try{await loadParties();}catch(refreshError){if(live.current){setError(refreshError.message);setFatal(true);}}
   }
  }
  finally{
   if(live.current){try{setPending(client.pending());}catch(e){setError(e.message);setFatal(true);}setBusy(false);}
   running.current=false;
  }
 };
 const saveParties=e=>{e.preventDefault();if(pending || !partyReason.trim() || !choices.some(c=>c.companyId===Number(buyer)) || !choices.some(c=>c.companyId===Number(payer)))return;act(async()=>{
  await client.save('parties',{buyerCompanyId:Number(buyer),payerCompanyId:Number(payer),expectedVersion:parties.version,reason:partyReason.trim()});
  await loadParties();await loadReview();
 });};
 const saveContract=e=>{e.preventDefault();if(pending || !checked || !file || !number.trim() || !date || !reason.trim())return;act(async()=>{
  const body={partyVersion:review.partyVersion,expectedVersion:review.expectedVersion,sourceFileId:file.fileId,
   number:number.trim(),date,reviewConfirmed:true,paymentTerms:terms.trim(),reason:reason.trim(),
   ...Object.fromEntries(Object.keys(sides).map(side=>[side,Object.fromEntries(legalFields.map(k=>[k,legal[side][k].trim()]))]))};
  await client.save('contract',body);if(live.current)onSaved?.();
 });};
 const retry=()=>act(async()=>{
  const saved=client.pending();if(!saved)throw new Error('Сохранённый запрос не найден. Откройте форму заново.');
  await client.save(saved.kind,saved.body);
  if(saved.kind==='contract'){if(live.current)onSaved?.();}else{await loadParties();await loadReview();}
 });
 const upload=event=>{
  const selected=event.target.files?.[0];if(!selected)return;
  act(async()=>{const result=await client.upload(selected);if(live.current){setFile({...result,name:selected.name});setChecked(false);}});
  event.target.value='';
 };
 return <section className="supplier-contract-review" aria-label="Проверка договора поставки">
  <h3>Проверка договора поставки</h3>
  <p>КП #{offerId}. Эта проверка сохраняет реквизиты договора; она не подтверждает подпись, оплату или получение материала.</p>
  {loading && <p role="status">Загрузка сторон сделки…</p>}
  {error && <p role="alert">{error}</p>}
  {pending ? <>
   <p>Есть сохранённый запрос: {pending.kind==='parties'?'выбор сторон':'проверка договора'}. Основание: {pending.body.reason}</p>
   <button type="button" disabled={blocked} onClick={retry}>Проверить и повторить сохранённый запрос</button>
  </> : !review && parties ? <form onSubmit={saveParties}>
   <fieldset disabled={blocked}>
    <legend>1. Покупатель и плательщик</legend>
    <label>Покупатель<select required value={buyer} onChange={e=>setBuyer(e.target.value)}>
     <option value="">Выберите компанию</option>{choices.map(c=><option key={c.companyId} value={c.companyId}>{c.shortName || c.companyName}</option>)}
    </select></label>
    <label>Плательщик<select required value={payer} onChange={e=>setPayer(e.target.value)}>
     <option value="">Выберите компанию</option>{choices.map(c=><option key={c.companyId} value={c.companyId}>{c.shortName || c.companyName}</option>)}
    </select></label>
    {parties.version>0 && Number(buyer)===parties.buyerCompanyId && Number(payer)===parties.payerCompanyId &&
      <button type="button" onClick={()=>act(loadReview)}>Перейти к проверке договора</button>}
    <label>Основание выбора сторон<input required maxLength={1000} value={partyReason} onChange={e=>setPartyReason(e.target.value)}/></label>
    <button type="submit" disabled={!partyReason.trim() || !buyer || !payer}>Сохранить выбранные стороны</button>
   </fieldset>
  </form> : !pending && review && <form onSubmit={saveContract}>
   <fieldset disabled={blocked}>
    <legend>2. Оригинал и реквизиты договора</legend>
    <p>Названия и ИНН взяты из карточек организаций. Сверьте их с оригиналом. Если ИНН отличается, исправьте выбор стороны или её карточку.</p>
    <label>Оригинал договора<input type="file" accept=".pdf,.txt,.doc,.docx,.jpg,.jpeg,.png" onChange={upload}/></label>
    {file && <p>Загружен: {file.name}</p>}
    <label>Номер договора<input required maxLength={100} value={number} onChange={e=>{setNumber(e.target.value);setChecked(false);}}/></label>
    <label>Дата договора<input required type="date" value={date} onChange={e=>{setDate(e.target.value);setChecked(false);}}/></label>
    {Object.entries(sides).map(([side,label])=><fieldset key={side}><legend>{label}</legend>
     {['fullName','inn'].map(k=><label key={k}>{labels[k]}<input required readOnly={k==='inn'} pattern={patterns[k]} maxLength={limits[k] || 12}
       value={legal[side][k]} onChange={e=>{setLegal(v=>({...v,[side]:{...v[side],[k]:e.target.value}}));setChecked(false);}}/></label>)}
     <details><summary>Банковские реквизиты и подписант</summary>
      {legalFields.filter(k=>!['fullName','inn'].includes(k)).map(k=><label key={k}>{labels[k]}<input pattern={patterns[k]} maxLength={limits[k]} value={legal[side][k]}
       onChange={e=>{setLegal(v=>({...v,[side]:{...v[side],[k]:e.target.value}}));setChecked(false);}}/></label>)}
     </details>
    </fieldset>)}
    <label>Условия оплаты по договору<textarea maxLength={4000} value={terms} onChange={e=>{setTerms(e.target.value);setChecked(false);}}/></label>
    <label>Основание проверки<textarea required maxLength={1000} value={reason} onChange={e=>setReason(e.target.value)}/></label>
    <label className="supplier-refund-check"><input type="checkbox" checked={checked} onChange={e=>setChecked(e.target.checked)}/>Реквизиты и условия сверены с загруженным оригиналом</label>
    <button type="submit" disabled={!checked || !file || !number.trim() || !date || !reason.trim()}>Сохранить проверенную версию договора</button>
    <button type="button" onClick={()=>{setReview(null);setChecked(false);}}>Вернуться к сторонам</button>
   </fieldset>
  </form>}
  <button type="button" disabled={busy} onClick={onClose}>Закрыть подготовку договора</button>
 </section>;
}
