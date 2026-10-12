import { useEffect, useState } from 'react';

const titles={already_connected:'Кабинет уже связан с карточкой',connect_existing:'Найден существующий кабинет',merge_cards:'В каталоге есть две карточки',no_cabinet:'Существующий кабинет не найден',ambiguous:'Найдено несколько кабинетов',review:'Нужна проверка карточки'};
const accounts={active:'Пользователь включён',disabled:'Пользователь отключён',wrong_role:'У пользователя другая роль',missing:'Пользователь не найден'};

export default function SupplierConnectionPreview({prefix,supplierId,btnG,onClose}) {
  const [data,setData]=useState(null);
  const [error,setError]=useState('');
  const [retry,setRetry]=useState(0);
  useEffect(()=>{
    const abort=new AbortController();
    setData(null);setError('');
    (async()=>{
      try {
        const response=await fetch(prefix+'/participants/'+supplierId+'/connection-preview',{signal:abort.signal});
        const body=await response.json();
        if(!response.ok) throw new Error(typeof body.detail==='string'?body.detail:'Не удалось проверить кабинет');
        if(!abort.signal.aborted) setData(body);
      } catch(e) {if(!abort.signal.aborted)setError(e.message);}
    })();
    return ()=>abort.abort();
  },[prefix,supplierId,retry]);
  return <section className="organization-participants__preview" aria-label="Проверка кабинета поставщика">
    <div className="organization-participants__toolbar"><h4>Кабинет и документы</h4><button type="button" style={btnG} onClick={onClose}>Скрыть проверку</button></div>
    {!data&&!error&&<p role="status">Проверяю кабинет…</p>}
    {error&&<div role="alert"><p>{error}</p><button type="button" style={btnG} onClick={()=>setRetry(n=>n+1)}>Повторить проверку</button></div>}
    {data&&<>
      <strong>{titles[data.scenario]}</strong>
      {data.cabinet&&<p>{data.cabinet.name} · ИНН {data.cabinet.inn||'не указан'}<br/>{accounts[data.cabinet.accountState]} · {data.cabinet.hasBuyerRelationship?'Есть в каталоге этой компании':'В каталоге этой компании ещё нет'}</p>}
      <p>Документы этой карточки в выбранной компании: счета — {data.history.invoices}, накладные — {data.history.receipts}, КП — {data.history.offers}.</p>
      {data.currentVisibility&&<p>Сейчас пользователь кабинета может видеть: счета — {data.currentVisibility.invoices}, КП — {data.currentVisibility.offers}. Файлы и договоры проверяются отдельно.</p>}
      {data.blockers.length>0&&<><h4>Что нужно уточнить</h4><ul>{data.blockers.map(item=><li key={item.code}>{item.message}</li>)}</ul></>}
      <p className="organization-participants__muted">Это проверка. Подключение и доступ к истории здесь не изменяются.</p>
      <details><summary>Данные проверки</summary><p>Компания: {data.companyId} · Аккаунт компании: {data.platformAccountId}<br/>Карточка: {data.supplier.supplierId} · Версия связи: {data.supplier.relationshipVersion}</p>
        {data.cabinet&&<p>Карточка кабинета: {data.cabinet.supplierId} · Пользователь: {data.cabinet.ownerUserId}<br/>Версия связи с компанией: {data.cabinet.relationshipVersion??'Связи нет'}</p>}
        {data.blockers.length>0&&<p>Причины: {data.blockers.map(item=>item.code).join(', ')}</p>}
      </details>
    </>}
  </section>;
}
