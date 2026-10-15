import {useEffect,useRef,useState} from 'react';
import useAsyncSubmit from '../../hooks/useAsyncSubmit';

function validRequests(body,mode) {
  if(mode==='disconnect_unused')return true;
  return body?.mode===mode&&Array.isArray(body.affectedRequests)&&body.affectedRequests.length<=50&&
    body.affectedRequests.every(row=>row&&Number.isInteger(row.requestId)&&row.requestId>0&&Number.isInteger(row.recipientId)&&row.recipientId>0&&
      Array.isArray(row.offerIds)&&row.offerIds.length>0&&row.offerIds.every(id=>Number.isInteger(id)&&id>0))&&
    new Set(body.affectedRequests.map(row=>row.requestId)).size===body.affectedRequests.length&&
    Number.isInteger(body.queuedNotificationCount)&&body.queuedNotificationCount>=0;
}

function validQuotes(body) {
  if(!Array.isArray(body.affectedOffers))return false;
  const ids=new Set(body.affectedRequests.flatMap(row=>row.offerIds));
  return body.affectedOffers.length===ids.size&&new Set(body.affectedOffers.map(row=>row?.offerId)).size===ids.size&&
    body.affectedOffers.every(row=>row&&ids.has(row.offerId)&&
      ((row.statusBefore==='Получено'&&row.statusAfter==='Отклонено')||(row.statusBefore==='Ожидает ответа'&&row.statusAfter==='Отозвано')))&&
    Number.isInteger(body.preservedQuoteFileCount)&&body.preservedQuoteFileCount>=0&&
    body.preservedQuoteFileCount<=body.affectedOffers.filter(row=>row.statusBefore==='Получено').length;
}

function CorrectionForm({path,mode,companyId,supplierId,targetId,onApplied,onPendingChange}) {
  const [plan,setPlan]=useState(null),[reason,setReason]=useState(''),[confirmed,setConfirmed]=useState(false);
  const [uncertain,setUncertain]=useState(false),[done,setDone]=useState(false);
  const operation=useRef(null),alive=useRef(true);
  const handlesRequests=mode!=='disconnect_unused';
  const rejectedQuotes=plan?.affectedOffers?.filter(row=>row.statusBefore==='Получено')||[];
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
  const {submit,pending,error}=useAsyncSubmit(async()=>{
    if(!operation.current)operation.current=window.crypto.randomUUID();
    const url=plan?path+'/'+plan.id+'/confirm':path;
    const payload=plan?{confirmed:true,reason:reason.trim()}:{operationId:operation.current};
    let response;
    try {response=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},cache:'no-store',body:JSON.stringify(payload)});}
    catch(failure){
      if(!alive.current)return;
      if(plan)setUncertain(true);
      throw new Error('Ответ сервера не получен. Повторите действие с теми же данными.');
    }
    const body=await response.json().catch(()=>null);
    if(!alive.current)return;
    if(!response.ok){
      if(plan&&response.status>=500){
        setUncertain(true);
        throw new Error('Сервер не подтвердил результат. Повторите подтверждение с теми же данными.');
      }
      if(response.status===409){setPlan(null);setConfirmed(false);setUncertain(false);operation.current=null;}
      throw new Error(typeof body?.detail==='string'?body.detail:'Не удалось проверить или отключить связь');
    }
    if(!plan){
      const consequencesValid=validRequests(body,mode)&&(mode!=='reject_received_quotes'||validQuotes(body));
      if(!body?.id||body.companyId!==companyId||body.sourceId!==supplierId||body.targetId!==targetId||!body.retainedDocuments||!consequencesValid)
        throw new Error('Сервер не подтвердил план для выбранной компании. Повторите проверку.');
      setPlan(body);return;
    }
    if(body?.ok!==true||body.planId!==plan.id||body.companyId!==companyId||body.sourceId!==supplierId||body.targetId!==targetId||body.relationshipStatus!=='Неактивный'||!Number.isInteger(body.relationshipVersion)||body.relationshipVersion<2||
      (handlesRequests&&body.withdrawnRequestCount!==plan.affectedRequests.length)||(mode==='reject_received_quotes'&&body.rejectedQuoteCount!==rejectedQuotes.length)){
      setUncertain(true);
      throw new Error('Сервер не подтвердил результат для выбранной компании. Повторите подтверждение.');
    }
    setDone(true);onApplied?.(body);
  });
  useEffect(()=>{onPendingChange?.(pending);return()=>onPendingChange?.(false);},[pending,onPendingChange]);
  const withdrawsRfq=handlesRequests&&plan?.affectedRequests.length>0;
  const rejectsQuotes=rejectedQuotes.length>0;
  const prepareText=mode==='reject_received_quotes'?'Проверим полученные КП и заявки. КП без заказов и счетов можно отклонить; цены и оригиналы сохранятся.':
    handlesRequests?'Проверим, можно ли отключить связь и отозвать заявки без ответа. Полученные КП, счета и другие оформленные документы требуют отдельного разбора.':
    'Доступно, если кабинет ещё не получил заявок, документов и назначений этой компании.';
  const confirmText=rejectsQuotes?'Отклонить КП и отключить':withdrawsRfq?'Отозвать заявки и отключить':'Подтвердить отключение';
  const checkboxText=rejectsQuotes?'Отклонить указанные КП и отключить эту связь':withdrawsRfq?'Отозвать указанные заявки и отключить эту связь':'Отключить только эту связь с выбранной компанией';
  return <section aria-label={handlesRequests?'Исправление подключения':'Отключение неиспользованной связи'}>
    <h4>Отключить ошибочную связь</h4>
    {done?<p role="status">Подключение отключено.</p>:<>
      {!plan?<>
        <p>{prepareText} Документы исходной карточки сохранятся.</p>
        <button type="button" disabled={pending} onClick={submit}>{pending?'Проверяю…':handlesRequests?'Проверить подключение':'Подготовить отключение'}</button>
      </>:<>
        <p><strong>{plan.companyName}</strong><br/>{plan.targetName}</p>
        <p>Эта связь станет неактивной. Кабинет поставщика и его связи с другими компаниями сохранятся.</p>
        {rejectsQuotes&&<>
          <p><strong>Будут отклонены КП: {rejectedQuotes.length}.</strong></p>
          <ul>{rejectedQuotes.map(row=><li key={row.offerId}>КП №{row.offerId} — будет отклонено</li>)}</ul>
          <p>Цены, состав, реквизиты и оригиналы КП сохранятся в архиве компании.</p>
          {plan.preservedQuoteFileCount>0&&<p>Оригиналов КП в архиве: {plan.preservedQuoteFileCount}.</p>}
        </>}
        {withdrawsRfq&&<>
          <p><strong>{rejectsQuotes?'Будет закрыт доступ к заявкам':'Будут отозваны заявки'}: {plan.affectedRequests.length}.</strong></p>
          <p>Только у этого поставщика. Заявки и ответы других поставщиков сохранятся.</p>
          <ul>{plan.affectedRequests.map(row=><li key={row.requestId}>Заявка №{row.requestId}</li>)}</ul>
          <p>Уведомлений в очереди будет отменено: {plan.queuedNotificationCount}.</p>
          <p>Уже отправленные письма и скачанные файлы останутся у получателя. После отзыва открыть заявку и ответить в кабинете будет нельзя.</p>
        </>}
        <p>В исходной карточке останутся: счета — {plan.retainedDocuments.invoices}, накладные — {plan.retainedDocuments.receipts}, КП — {plan.retainedDocuments.offers}.</p>
        <p>Проверка действует до {new Date(plan.expiresAt).toLocaleTimeString('ru-RU')}.</p>
        <label>Причина отключения<textarea value={reason} onChange={event=>setReason(event.target.value)} maxLength={1000} disabled={pending||uncertain}/></label>
        <label><input type="checkbox" checked={confirmed} onChange={event=>setConfirmed(event.target.checked)} disabled={pending||uncertain}/>
          {checkboxText}</label>
        <button type="button" disabled={pending||!confirmed||reason.trim().length<10} onClick={submit}>
          {pending?'Отключаю…':uncertain?'Повторить подтверждение':confirmText}
        </button>
      </>}
    </>}
    {error&&<p role="alert">{error}</p>}
  </section>;
}

export default function SupplierConnectionCorrection(props) {
  const mode=process.env.REACT_APP_PARTICIPANT_QUOTE_CORRECTIONS_ENABLED==='1'?'reject_received_quotes':
    process.env.REACT_APP_PARTICIPANT_RFQ_CORRECTIONS_ENABLED==='1'?'withdraw_unanswered_rfq':'disconnect_unused';
  const suffix={disconnect_unused:'correction-plans',withdraw_unanswered_rfq:'rfq-correction-plans',reject_received_quotes:'quote-correction-plans'}[mode];
  const path=props.prefix+'/participants/'+props.supplierId+'/connection-requests/'+props.requestId+'/'+suffix;
  return <CorrectionForm key={path} {...props} path={path} mode={mode}/>;
}
