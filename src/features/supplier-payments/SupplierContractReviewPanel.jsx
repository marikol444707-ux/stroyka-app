import React, {useEffect,useMemo,useRef,useState} from 'react';
import {createContractReviewClient,legalDraft,legalFields} from './contractReviewClient';
import ContractPartyFields from './ContractPartyFields';
import './SupplierContractReviewPanel.css';

const sides={buyer:'Покупатель',payer:'Плательщик',supplier:'Поставщик'};

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
 const [file,setFile]=useState(null),[checked,setChecked]=useState(false),[draftEdited,setDraftEdited]=useState(false);
 const [recognition,setRecognition]=useState(null),[recognitionMessage,setRecognitionMessage]=useState('');
 const autoFields=useRef([]);
 const [reusedFrom,setReusedFrom]=useState(null);
 const [activeSide,setActiveSide]=useState('supplier');
 const separatePayer=Boolean(parties?.version && parties.buyerCompanyId!==parties.payerCompanyId);
 const visibleSides=separatePayer?sides:{buyer:'Покупатель и плательщик',supplier:'Поставщик'};
 const recognitionEnabled=process.env.REACT_APP_SUPPLIER_CONTRACT_RECOGNITION_ENABLED==='true';
 const blocked=disabled || busy || loading || fatal;
 const loadReview=async()=>{
  const value=await client.reviewContext();
  if(live.current){setReusedFrom(null);setDraftEdited(false);setReview(value);setLegal(Object.fromEntries(Object.keys(sides).map(side=>[side,legalDraft(value[side])])));setChecked(false);setRecognition(null);setRecognitionMessage('');autoFields.current=[];setFile(null);}
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
  await client.save('parties',{buyerCompanyId:Number(buyer),payerCompanyId:Number(separatePayer?payer:buyer),expectedVersion:parties.version,reason:partyReason.trim()});
  await loadParties();await loadReview();
 });};
 const saveContract=e=>{e.preventDefault();if(pending || !checked || !file || !number.trim() || !date || !reason.trim())return;act(async()=>{
  const acceptedFields=recognition ? autoFields.current.filter(item=>(separatePayer || item.side!=='payer') && legal[item.side][item.field]===item.value).map(({side,field})=>({side,field})) : [];
  const body={...(reusedFrom?{reusedFromContractId:reusedFrom}:{}),...(acceptedFields.length ? {recognitionReview:{sourceContentHash:recognition.sourceContentHash,acceptedFields}} : {}),partyVersion:review.partyVersion,expectedVersion:review.expectedVersion,sourceFileId:file.fileId,
   number:number.trim(),date,reviewConfirmed:true,paymentTerms:terms.trim(),reason:reason.trim(),
   ...Object.fromEntries(Object.keys(sides).map(side=>[side,Object.fromEntries(legalFields.map(k=>[k,legal[side==='payer' && !separatePayer?'buyer':side][k].trim()]))]))};
  await client.save('contract',body);if(live.current)onSaved?.();
 });};
 const retry=()=>act(async()=>{
  const saved=client.pending();if(!saved)throw new Error('Сохранённый запрос не найден. Откройте форму заново.');
  await client.save(saved.kind,saved.body);
  if(saved.kind==='contract'){if(live.current)onSaved?.();}else{await loadParties();await loadReview();}
 });
 const recognize=async fileId=>{
   setChecked(false);setRecognition(null);
   const previous=autoFields.current;autoFields.current=[];
   setLegal(current=>{
    const next=Object.fromEntries(Object.entries(current).map(([side,fields])=>[side,{...fields}]));
    for(const item of previous)if(next[item.side][item.field]===item.value)next[item.side][item.field]='';
    return next;
   });
   if(!recognitionEnabled){setRecognitionMessage('Оригинал загружен. Автозаполнение пока недоступно.');return;}
   setRecognitionMessage('Распознаём договор…');
   try{
    const found=await client.recognize(fileId,review);if(!live.current)return;
    setRecognition(found);
    const candidates=[];
    for(const side of Object.keys(sides)){
     const party=found.parties[side];
     if(party.status==='matched' && party.fields.inn?.value===review[side].inn)
      for(const [field,item] of Object.entries(party.fields))if(field!=='inn' && field!=='fullName')candidates.push({side,field,value:item.value});
    }
    setLegal(current=>{
     const next=Object.fromEntries(Object.entries(current).map(([side,fields])=>[side,{...fields}]));
     const applied=[];
     for(const item of candidates)if(!next[item.side][item.field]){next[item.side][item.field]=item.value;applied.push(item);}
     autoFields.current=applied;return next;
    });
    const mismatched=Object.values(found.parties).some(p=>p.status==='identity_mismatch');
    setRecognitionMessage(mismatched?'Есть расхождение ИНН с выбранной организацией. Проверьте стороны договора.':candidates.length?'Найденные реквизиты добавлены в пустые поля. Проверьте их по оригиналу; номер, дату и условия оплаты укажите вручную.':'Реквизиты не удалось уверенно определить. Оригинал сохранён; заполните поля вручную.');
   }catch(e){if(live.current)setRecognitionMessage('Оригинал сохранён. Распознавание: '+e.message);}
 };
 const upload=event=>{
  const selected=event.target.files?.[0];if(!selected)return;
  act(async()=>{
   const result=await client.upload(selected);if(!live.current)return;
   setReusedFrom(null);setFile({...result,name:selected.name});setChecked(false);setRecognition(null);
   await recognize(result.fileId);
  });
  event.target.value='';
 };
 return <section className="supplier-contract-review" aria-label="Проверка договора поставки">
  <header className="contract-review-header"><div><span className="contract-eyebrow">ДОГОВОР ПОСТАВКИ · КП #{offerId}</span>
   <h3>Проверим реквизиты</h3><p>Выберите сохранённый договор или загрузите новый, сверьте данные и сохраните проверенную версию.</p></div>
   <span className="contract-draft-badge">Черновик проверки</span></header>
  <ol className="contract-review-steps" aria-label="Этапы проверки"><li className={!review?'is-current':'is-complete'}>1. Стороны</li><li className={review&&!file?'is-current':file?'is-complete':''}>2. Документ</li><li className={file?'is-current':''}>3. Сверка</li></ol>
  {loading && <p role="status">Загрузка сторон сделки…</p>}
  {error && <p role="alert">{error}</p>}
  {pending ? <>
   <p>Есть сохранённый запрос: {pending.kind==='parties'?'выбор сторон':'проверка договора'}. Основание: {pending.body.reason}</p>
   <button type="button" disabled={blocked} onClick={retry}>Проверить и повторить сохранённый запрос</button>
  </> : !review && parties ? <form onSubmit={saveParties}>
   <fieldset className="contract-review-content" disabled={blocked}>
    <legend>1. Покупатель и плательщик</legend>
    <label>Покупатель<select required value={buyer} onChange={e=>{setBuyer(e.target.value);if(!separatePayer)setPayer(e.target.value);}}>
     <option value="">Выберите компанию</option>{choices.map(c=><option key={c.companyId} value={c.companyId}>{c.shortName || c.companyName}</option>)}
    </select></label>
    {separatePayer&&<label>Плательщик<select required value={payer} disabled onChange={e=>setPayer(e.target.value)}>
     <option value="">Выберите компанию</option>{choices.map(c=><option key={c.companyId} value={c.companyId}>{c.shortName || c.companyName}</option>)}
    </select></label>}
    {!separatePayer&&<p className="contract-hint">Покупатель одновременно является плательщиком.</p>}
    {parties.version>0 && Number(buyer)===parties.buyerCompanyId && Number(payer)===parties.payerCompanyId &&
      <button type="button" onClick={()=>act(loadReview)}>Перейти к проверке договора</button>}
    <label>Основание выбора сторон<input required maxLength={1000} value={partyReason} onChange={e=>setPartyReason(e.target.value)}/></label>
    <button type="submit" disabled={!partyReason.trim() || !buyer || !payer}>Сохранить выбранные стороны</button>
   </fieldset>
  </form> : !pending && review && <form onSubmit={saveContract} onChange={()=>setDraftEdited(true)} onInvalid={event=>{
    const panel=event.target.closest('[role="tabpanel"]');
    if(panel){setActiveSide(panel.id.replace('contract-party-',''));const target=event.target;setTimeout(()=>target.focus(),0);}
   }}>
   <fieldset className="contract-review-content" disabled={blocked}>
    <legend className="contract-visually-hidden">Оригинал и реквизиты договора</legend>

    {review.reusableContracts?.length>0 && !file && !draftEdited && <div className="contract-upload-card">
     <h4>Использовать сохранённый договор</h4>
     <p className="contract-hint">Те же стороны, оригинал уже загружен. Выбор заполнит поля данными проверенной версии; перед сохранением сверьте их с текущими реквизитами.</p>
     {review.reusableContracts.map(contract=><button key={contract.id} type="button" onClick={()=>{
      setReusedFrom(contract.id);setFile({fileId:contract.sourceFileId,name:`Договор № ${contract.snapshot.number} · версия ${contract.version}`});
      setNumber(contract.snapshot.number);setDate(contract.snapshot.date);setTerms(contract.snapshot.paymentTerms || '');
      setLegal(Object.fromEntries(Object.keys(sides).map(side=>[side,legalDraft(contract.snapshot[side])])));
      setReason(`Повторное использование договора из КП № ${contract.offerId}, версия ${contract.version}`);
      setChecked(false);setRecognition(null);autoFields.current=[];
      setRecognitionMessage('Используется сохранённый оригинал. Повторная загрузка и распознавание не нужны.');
     }}>Договор № {contract.snapshot.number} от {contract.snapshot.date} · версия {contract.version}</button>)}
    </div>}
    <div className="contract-upload-card"><span className="contract-eyebrow">01 / ОРИГИНАЛ</span><label>Оригинал договора<input type="file" accept=".pdf,.txt,.doc,.docx,.jpg,.jpeg,.png" onChange={upload}/></label>
    {file && <p>Загружен: {file.name}</p>}
    <p className="contract-hint">PDF, Word, скан или фото · до 10 МБ. Распознавание скана может занять до двух минут.</p>
    {recognitionMessage && <p className="contract-recognition-status" role="status">{recognitionMessage}</p>}
    {file && recognitionEnabled && <button type="button" onClick={()=>act(()=>recognize(file.fileId))}>Повторить распознавание</button>}
    </div><div className="contract-field-grid contract-document-meta">
    <label>Номер договора<input required maxLength={100} value={number} onChange={e=>{setNumber(e.target.value);setChecked(false);}}/></label>
    <label>Дата договора<input required type="date" value={date} onChange={e=>{setDate(e.target.value);setChecked(false);}}/></label>
    </div>
    <div className="contract-section-heading"><div><span className="contract-eyebrow">02 / СТОРОНЫ ДОГОВОРА</span><h4>Сверьте данные каждой стороны</h4></div><p className="contract-hint">Заполненные вручную поля сохраняются при распознавании.</p></div>
    <div className="contract-party-tabs" role="tablist" aria-label="Сторона договора">{Object.entries(visibleSides).map(([side,label])=>
     <button key={side} type="button" role="tab" id={`contract-tab-${side}`} aria-selected={activeSide===side} aria-controls={`contract-party-${side}`} onClick={()=>setActiveSide(side)}>
      <strong>{label}</strong><span>{legal[side].fullName || 'Организация'}</span>
     </button>)}</div>
    {Object.entries(visibleSides).map(([side,label])=><div key={side} id={`contract-party-${side}`} role="tabpanel" aria-labelledby={`contract-tab-${side}`} hidden={activeSide!==side}>
     <div className="contract-party-summary"><strong>{label}</strong><span>ИНН {legal[side].inn}</span>
      {recognition && <span className="contract-draft-badge">{recognition.parties[side].status==='matched'?'ИНН совпадает':recognition.parties[side].status==='identity_mismatch'?'ИНН отличается — проверьте':'Сторона не распознана'}</span>}
     </div>
     {side==='payer' && review.payer.inn===review.buyer.inn && <div className="contract-payer-help"><p>Покупатель и плательщик — одна организация. Можно перенести уже проверенные вами реквизиты покупателя.</p>
      <button type="button" onClick={()=>{setLegal(v=>({...v,payer:{...v.buyer}}));autoFields.current=autoFields.current.filter(item=>item.side!=='payer');setChecked(false);}}>Взять реквизиты покупателя</button></div>}
     <ContractPartyFields side={side} value={legal[side]} profile={review[side]} recognized={recognition?.parties[side]}
      onChange={(field,value)=>{setLegal(v=>({...v,[side]:{...v[side],[field]:value}}));setChecked(false);}}
      onApply={(field,value)=>{setDraftEdited(true);setLegal(v=>({...v,[side]:{...v[side],[field]:value}}));autoFields.current=[...autoFields.current.filter(item=>!(item.side===side&&item.field===field)),{side,field,value}];setChecked(false);}}/>
    </div>)}
    <div className="contract-final-review"><span className="contract-eyebrow">03 / ПОДТВЕРЖДЕНИЕ</span>
    <label>Условия оплаты по договору<textarea maxLength={4000} value={terms} onChange={e=>{setTerms(e.target.value);setChecked(false);}}/></label>
    <label>Основание проверки<textarea required maxLength={1000} value={reason} onChange={e=>setReason(e.target.value)}/></label>
    <label className="supplier-refund-check"><input type="checkbox" checked={checked} onChange={e=>setChecked(e.target.checked)}/>Реквизиты и условия сверены с загруженным оригиналом</label>
    <p className="contract-hint">Сохранение реквизитов не подтверждает подпись, оплату или получение материала.</p>
    <div className="contract-actions"><button className="contract-primary" type="submit" disabled={!checked || !file || !number.trim() || !date || !reason.trim()}>Сохранить проверенную версию договора</button>
    <button type="button" onClick={()=>{setReview(null);setChecked(false);}}>Вернуться к сторонам</button></div></div>
   </fieldset>
  </form>}
  <button type="button" disabled={busy} onClick={onClose}>Закрыть подготовку договора</button>
 </section>;
}
