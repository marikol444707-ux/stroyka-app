import {useEffect, useRef, useState} from 'react';
import '../platform-admin/OrganizationParticipants.css';

export default function SupportWorkspace({API, C={}, btnG={}, onLogout}) {
  const [data,setData] = useState(null);
  const [detail,setDetail] = useState(null);
  const [error,setError] = useState('');
  const [busy,setBusy] = useState(false);
  const [offset,setOffset] = useState(0);
  const [retry,setRetry] = useState(0);
  const command = useRef(0);
  const active = useRef(true);
  const path = API+'/participant-support/workspace';
  useEffect(()=>{
    active.current=true;
    const abort=new AbortController(); command.current++;
    setData(null);setDetail(null);setError('');setBusy(false);
    (async()=>{
      try {
        const response=await fetch(path+'?offset='+offset,{signal:abort.signal});
        const body=await response.json();
        if(!response.ok) throw new Error(typeof body.detail==='string'?body.detail:'Не удалось загрузить обращения');
        if(!abort.signal.aborted) setData(body);
      } catch(e) {if(!abort.signal.aborted)setError(e.message);}
    })();
    return ()=>{active.current=false;abort.abort();};
  },[path,offset,retry]);
  const open=async id=>{
    const version=++command.current;setDetail(null);setError('');setBusy(true);
    try {
      const response=await fetch(path+'/'+id+'/diagnostic', {cache:'no-store'});
      const body=await response.json();
      if(!response.ok) throw new Error(typeof body.detail==='string'?body.detail:'Не удалось открыть диагностику');
      if(active.current&&command.current===version)setDetail(body);
    } catch(e) {if(active.current&&command.current===version)setError(e.message);}
    finally {if(active.current&&command.current===version)setBusy(false);}
  };
  // Do not retain an expired diagnostic on a device left open.
  useEffect(()=>{
    if(!detail)return;
    const expiry=Date.parse(detail.expiresAt)-Date.now();
    const timer=setTimeout(()=>{setDetail(null);setError('Срок доступа закончился. Запросите новый доступ администратора.');},Math.max(0,Math.min(86400000,expiry)));
    return ()=>clearTimeout(timer);
  },[detail]);
  return <main className="organization-participants" style={{color:C.text,background:C.bg,borderColor:C.border}}>
    <h3>Назначенные обращения</h3>
    <p>Диагностика по организациям. Каждый просмотр записывается в историю.</p>
    <div className="organization-participants__toolbar"><button style={btnG} disabled={busy} onClick={()=>setRetry(n=>n+1)}>Обновить обращения</button>{onLogout&&<button style={btnG} onClick={onLogout}>Выйти</button>}</div>
    {error&&<p role="alert">{error}</p>}
    {!data&&!error&&<p role="status">Загружаю…</p>}
    {data&&!data.items.length&&<p>Назначенных обращений нет. Администратор выдаёт доступ из карточки обращения.</p>}
    {data&&<ul className="organization-participants__list">{data.items.map(item=><li key={item.id} style={{borderColor:C.border}}>
      <strong>{item.companyName}</strong><span>Организация №{item.companyId} · Обращение №{item.ticketId}</span>
      <span>{item.reasonLabel}</span><span>Доступ до {new Date(item.expiresAt).toLocaleString('ru-RU')}</span>
      <button style={btnG} disabled={busy} onClick={()=>open(item.id)}>Открыть диагностику №{item.ticketId}</button>
    </li>)}</ul>}
    {data&&<div className="organization-participants__toolbar"><button style={btnG} disabled={busy||offset===0} onClick={()=>setOffset(n=>Math.max(0,n-25))}>Назад</button><span>Страница {offset/25+1}</span><button style={btnG} disabled={busy||!data.hasMore} onClick={()=>setOffset(n=>n+25)}>Далее</button></div>}
    {detail&&<article aria-label={'Диагностика обращения №'+detail.ticketId}>
      <h4>{detail.companyName} · Обращение №{detail.ticketId}</h4>
      <p><strong>Причина:</strong> {detail.reasonLabel}</p>
      <p><strong>Карточка:</strong> {detail.context.participantName}</p>
      <p><strong>Запрос пользователя:</strong> {detail.comment}</p>
      <p><strong>Результат:</strong> {detail.result||'Ещё не указан'}</p>
      <details><summary>Сведения для диагностики</summary><p>Код: {detail.reasonCode}</p><p>Экран: {detail.context.screen} · Действие: {detail.context.action}</p><p>Версия: {detail.context.applicationVersion}</p></details>
      <button style={btnG} onClick={()=>setDetail(null)}>Закрыть диагностику</button>
    </article>}
  </main>;
}
