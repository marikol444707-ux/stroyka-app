import {useCallback,useEffect,useId,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
import '../participant-support/ConnectionRequests.css';
import './SupplierCorrectionPreview.css';
import SupplierConnectionCorrection from './SupplierConnectionCorrection';
import SupplierFinancialReview,{financialReviewState} from './SupplierFinancialReview';

const labels={invoices:'Счета',receipts:'Накладные',offers:'Предложения',contracts:'Договоры',files:'Основные файлы'};
const access={available:'Доступ сейчас разрешён',unavailable:'Сейчас недоступно поставщику',needs_check:'Доступ проверяется в карточке документа'};
const pageSize=5;
const itemLabels={invoices:'Счёт',receipts:'Накладная',offers:'КП',contracts:'Договор',files:'Файл'};

export default function SupplierCorrectionPreview({prefix,supplierId,requestId,onClose,onCompleted}) {
  const [category,setCategory]=useState('invoices');
  const [offset,setOffset]=useState(0);
  const [retry,setRetry]=useState(0);
  const [state,setState]=useState({});
  const [applied,setApplied]=useState(null),[commandPending,setCommandPending]=useState(false);
  const dialog=useRef(null);
  const titleId=useId();
  const path=prefix+'/participants/'+supplierId+'/connection-requests/'+requestId+'/correction-preview';
  const scope=path+':'+category+':'+offset;
  const completed=applied?.scope===path;
  const close=useCallback(()=>{if(commandPending)return;onClose();if(completed)onCompleted?.();},[commandPending,completed,onClose,onCompleted]);
  useEffect(()=>{
    const previous=document.activeElement,overflow=document.body.style.overflow;
    document.body.style.overflow='hidden';dialog.current?.focus();
    return()=>{document.body.style.overflow=overflow;previous?.focus();};
  },[]);
  useEffect(()=>{
    // Paging temporarily removes the focused button. Listen on document so
    // Escape and the focus trap still work while focus has fallen to body.
    const handleKey=event=>{
      if(event.key==='Escape'){event.preventDefault();close();}
      if(event.key==='Tab'){
        const nodes=[...dialog.current.querySelectorAll('button:not(:disabled),input:not(:disabled):not([type="hidden"]),textarea:not(:disabled),select:not(:disabled),a[href],summary')];
        const first=nodes[0],last=nodes[nodes.length-1];
        const outside=!dialog.current.contains(document.activeElement)||document.activeElement===dialog.current;
        if(event.shiftKey&&(document.activeElement===first||outside)){event.preventDefault();last?.focus();}
        else if(!event.shiftKey&&(document.activeElement===last||outside)){event.preventDefault();first?.focus();}
      }
    };
    document.addEventListener('keydown',handleKey);
    return()=>document.removeEventListener('keydown',handleKey);
  },[close]);
  useEffect(()=>{
    const abort=new AbortController();
    setState({scope,status:'loading'});
    (async()=>{
      try {
        const query=new URLSearchParams({category,offset,limit:pageSize});
        const response=await fetch(path+'?'+query,{signal:abort.signal,cache:'no-store'});
        const body=await response.json();
        if(!response.ok)throw new Error(typeof body.detail==='string'?body.detail:'Не удалось проверить последствия подключения');
        if(!abort.signal.aborted)setState({scope,status:'ready',data:body});
      }catch(error){if(!abort.signal.aborted)setState({scope,status:'error',error:error.message});}
    })();
    return()=>abort.abort();
  },[path,category,offset,scope,retry]);
  const current=state.scope===scope?state:{status:'loading'};
  const data=current.data;
  return createPortal(<div className="supplier-correction-dialog" role="dialog" aria-modal="true" aria-labelledby={titleId}
    ref={dialog} tabIndex={-1}>
    <section className="connection-requests supplier-correction-dialog__panel" aria-label="Последствия подключения поставщика">
    <div className="connection-requests__actions supplier-correction-dialog__toolbar">
      <h3 id={titleId}>Последствия подключения</h3>
      <button type="button" disabled={commandPending} onClick={close}>{completed?'Готово':'Скрыть последствия'}</button>
    </div>
    {current.status==='loading'&&<p role="status">Проверяю документы и доступ…</p>}
    {current.status==='error'&&<p role="alert">{current.error}</p>}
    {completed&&<p role="status">Подключение отключено. Исходные документы и кабинет поставщика сохранены.</p>}
    {completed&&applied.result.withdrawnRequestCount>0&&<p>{applied.result.rejectedQuoteCount>0?'Доступ к заявкам закрыт':'Отозвано заявок'}: {applied.result.withdrawnRequestCount}.</p>}
    {completed&&applied.result.rejectedQuoteCount>0&&<p>Отклонено КП: {applied.result.rejectedQuoteCount}.</p>}
    {completed&&applied.result.preservedIssuedCounts?.invoices>0&&applied.result.revokedRequestCount===0&&<p>Доступ к счетам закрыт: {applied.result.preservedIssuedCounts.invoices}. Статусы документов, оплаты и складские записи сохранены.</p>}
    {completed&&applied.result.revokedRequestCount>0&&<p>Доступ к заявкам закрыт: {applied.result.revokedRequestCount}. Статусы документов, оплаты и складские записи сохранены.</p>}
    {!completed&&<button type="button" disabled={current.status==='loading'||commandPending} onClick={()=>setRetry(n=>n+1)}>{current.status==='error'?'Повторить проверку':'Обновить проверку'}</button>}
    {!completed&&current.status==='ready'&&<>
      <p><strong>{data.companyName}</strong><br/>{data.sourceName} → {data.targetName}</p>
      <p>Подключено: {new Date(data.connectedAt).toLocaleString('ru-RU')}</p>
      <p><strong>Документы и оплаты сохраняются.</strong> Отключение связи само по себе не закрывает доступ к ранее адресованным документам.</p>
      <SupplierFinancialReview review={data.financialReview}/>
      <div className="connection-requests__actions" role="group" aria-label="Документы подключения">
        {Object.entries(labels).map(([kind,label])=><button key={kind} type="button" aria-pressed={category===kind}
          disabled={commandPending||data.summary[kind].total===null} onClick={()=>{setCategory(kind);setOffset(0);}}>
          {label}: {data.summary[kind].total??'нужна проверка'}
        </button>)}
      </div>
      <p>Создано после подключения в этой группе: <strong>{data.summary[category].afterConnection??'не установлено'}</strong>
        {data.summary[category].undated>0&&<> · Без подтверждённой даты: <strong>{data.summary[category].undated}</strong></>}.</p>
      {data.blockers.length>0&&<details open><summary>Что требует внимания</summary>
        <ul>{data.blockers.map(item=><li key={item.code}>{item.message}</li>)}</ul>
      </details>}
      {!data.items.length&&<p>В этой группе документов нет.</p>}
      <ul className="connection-requests__list">{data.items.map(item=><li key={item.id}>
        <strong>{itemLabels[category]} №{item.id}</strong>
        {item.context&&<>
          <p>{item.context.supplierCard==='source'?'Исходная карточка':'Подключённый кабинет'}</p>
          {item.context.linksConfirmed?<p>{[item.context.requestId&&`Заявка №${item.context.requestId}`,
            item.context.offerId&&category!=='offers'&&`КП №${item.context.offerId}`].filter(Boolean).join(' · ')}</p>:
            <p>Связи документа требуют проверки</p>}
        </>}
        <p><span>{item.createdAfterConnection===null?'Дата создания не подтверждена':item.createdAfterConnection?'Создан после подключения':'Создан до подключения'}</span><br/><span>{access[item.currentSupplierAccess]}</span></p>
      </li>)}</ul>
      {(offset>0||data.hasMore)&&<nav className="connection-requests__actions" aria-label="Страницы документов подключения">
        <button type="button" disabled={commandPending||offset===0} onClick={()=>setOffset(n=>Math.max(0,n-pageSize))}>Назад</button>
        <button type="button" disabled={commandPending||!data.hasMore} onClick={()=>setOffset(n=>n+pageSize)}>Далее</button>
      </nav>}
      <details><summary>Границы проверки</summary>
        <p>Показаны документы обеих карточек только в этой компании. Дата создания записи не доказывает, что документ появился из-за подключения.</p>
        <p>Доступ к оригиналам и их наличие проверяются отдельно. Уже состоявшийся просмотр отменить нельзя.</p>
      </details>
      <p>Просмотр последствий не меняет связи и права доступа.</p>
      {process.env.REACT_APP_PARTICIPANT_CORRECTIONS_ENABLED==='1'&&financialReviewState(data.financialReview)!=='needs_check'&&
        (financialReviewState(data.financialReview)!=='review_required'||process.env.REACT_APP_PARTICIPANT_ISSUED_ACCESS_CORRECTIONS_ENABLED==='1'||process.env.REACT_APP_PARTICIPANT_INVOICE_ACCESS_CORRECTIONS_ENABLED==='1')&&<SupplierConnectionCorrection
        prefix={prefix} companyId={data.companyId} supplierId={supplierId} targetId={data.targetId} requestId={requestId}
        onPendingChange={setCommandPending} onApplied={result=>setApplied({scope:path,result})}/>}
    </>}
  </section></div>,document.body);
}
