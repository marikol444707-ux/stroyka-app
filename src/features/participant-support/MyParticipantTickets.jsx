import { useEffect, useState } from 'react';
const statuses={new:'Новое',in_progress:'В работе',waiting:'Ожидает сведения',resolved:'Исправлено',closed:'Проверено и закрыто'};

export default function MyParticipantTickets({API,companyId,C,btnG}) {
  const [opened,setOpened]=useState(false);
  const [offset,setOffset]=useState(0);
  const [data,setData]=useState(null);
  const [error,setError]=useState('');
  const [retry,setRetry]=useState(0);
  useEffect(()=>{
    if(!opened)return;
    const abort=new AbortController();
    setData(null);setError('');
    (async()=>{
      try {
        const response=await fetch(API+'/participant-support/tickets?limit=25&offset='+offset,{signal:abort.signal,headers:{'X-Company-Id':String(companyId),'X-Company-Mode':'company'}});
        const body=await response.json();
        if(!response.ok)throw new Error(typeof body.detail==='string'?body.detail:'Не удалось загрузить обращения');
        if(!abort.signal.aborted)setData(body);
      }catch(e){if(!abort.signal.aborted)setError(e.message);}
    })();
    return()=>abort.abort();
  },[API,companyId,opened,offset,retry]);
  return <section style={{color:C.text,marginBottom:12}} aria-label="Мои обращения">
    <button type="button" onClick={()=>setOpened(v=>!v)} aria-expanded={opened} style={{...btnG,minHeight:44}}>Мои обращения</button>
    {opened&&<>
      {error?<p role="alert">{error}</p>:!data?<p role="status">Загружаю…</p>:data.items.length===0?<p>У вас пока нет обращений в этой организации.</p>:<ul style={{paddingLeft:20}}>{data.items.map(item=><li key={item.id} style={{margin:'12px 0',overflowWrap:'anywhere'}}><strong>№{item.id} · {statuses[item.status]}</strong><p>{item.reason}</p>{item.result&&<p>Результат: {item.result}</p>}</li>)}</ul>}
      <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
        <button type="button" onClick={()=>setRetry(n=>n+1)} style={{...btnG,minHeight:44}}>Обновить обращения</button>
        <button type="button" disabled={offset===0} onClick={()=>setOffset(n=>Math.max(0,n-25))} style={{...btnG,minHeight:44}}>Назад</button>
        <button type="button" disabled={!data?.hasMore} onClick={()=>setOffset(n=>n+25)} style={{...btnG,minHeight:44}}>Далее</button>
      </div>
    </>}
  </section>;
}
