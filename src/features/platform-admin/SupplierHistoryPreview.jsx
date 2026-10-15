import {useEffect,useState} from 'react';
import '../participant-support/ConnectionRequests.css';

const labels={invoices:'Счета',receipts:'Накладные',offers:'Предложения',contracts:'Версии договоров',files:'Основные файлы'};
const access={available:'Доступ сейчас разрешён',unavailable:'Сейчас недоступно поставщику',needs_check:'Доступ проверяется в карточке документа'};
const itemLabels={invoices:'Счёт',receipts:'Накладная',offers:'Предложение',contracts:'Версия договора',files:'Основной файл'};
const pageSize=5;

export default function SupplierHistoryPreview({prefix,sourceId,targetId}) {
  const [category,setCategory]=useState('invoices');
  const [offset,setOffset]=useState(0);
  const [retry,setRetry]=useState(0);
  const [state,setState]=useState({});
  const path=prefix+'/participants/'+sourceId+'/history-preview';
  const scope=path+':'+targetId+':'+category+':'+offset;
  useEffect(()=>{
    const abort=new AbortController();
    setState({scope,status:'loading'});
    (async()=>{
      try {
        const query=new URLSearchParams({targetSupplierId:targetId,category,offset,limit:pageSize});
        const response=await fetch(path+'?'+query,{signal:abort.signal,cache:'no-store'});
        const body=await response.json();
        if(!response.ok)throw new Error(typeof body.detail==='string'?body.detail:'Не удалось проверить старые документы');
        if(!abort.signal.aborted)setState({scope,status:'ready',data:body});
      }catch(error){if(!abort.signal.aborted)setState({scope,status:'error',error:error.message});}
    })();
    return()=>abort.abort();
  },[path,targetId,category,offset,scope,retry]);
  const current=state.scope===scope?state:{status:'loading'};
  return <section className="connection-requests" aria-label="История карточки в выбранной компании">
    <h4>Старые документы</h4>
    <p>Показаны документы выбранной компании. Это просмотр: объединение и права доступа не меняются.</p>
    {current.status==='loading'&&<p role="status">Проверяю историю…</p>}
    {current.status==='error'&&<p role="alert">{current.error}</p>}
    <button type="button" disabled={current.status==='loading'} onClick={()=>setRetry(n=>n+1)}>Обновить историю</button>
    {current.status==='ready'&&<>
      <p><strong>{current.data.sourceName}</strong> → <strong>{current.data.targetName}</strong></p>
      <div className="connection-requests__actions" role="group" aria-label="Виды документов">
        {Object.entries(labels).map(([kind,label])=><button key={kind} type="button" aria-pressed={category===kind}
          disabled={current.data.summary[kind]===null} onClick={()=>{setCategory(kind);setOffset(0);}}>{label}: {current.data.summary[kind]??'нужна проверка схемы'}</button>)}
      </div>
      <p>Назначения менеджеров сохраняются. Основные файлы — зарегистрированные оригиналы счетов, КП и договоров; это не проверка всех вложений или их наличия в хранилище.</p>
      {current.data.blockers?.length>0&&<details><summary>Что нужно проверить перед объединением</summary>
        <ul>{current.data.blockers.map(item=><li key={item.code}>{item.message}</li>)}</ul></details>}
      {!current.data.items.length&&<p>В этой группе документов нет.</p>}
      <ul className="connection-requests__list">{current.data.items.map(item=><li key={item.id}>
        <strong>{itemLabels[category]} · запись #{item.id}</strong><p>{access[item.currentSupplierAccess]}</p>
      </li>)}</ul>
      {(offset>0||current.data.hasMore)&&<nav className="connection-requests__actions" aria-label="Страницы старых документов">
        <button type="button" disabled={offset===0} onClick={()=>setOffset(n=>Math.max(0,n-pageSize))}>Назад</button>
        <button type="button" disabled={!current.data.hasMore} onClick={()=>setOffset(n=>n+pageSize)}>Далее</button>
      </nav>}
    </>}
  </section>;
}
