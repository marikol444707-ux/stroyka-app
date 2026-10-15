import { useEffect, useRef, useState } from 'react';
import { API } from '../../api';
const statuses = {new:'Новое',in_progress:'В работе',waiting:'Ожидает сведения',resolved:'Исправлено',closed:'Проверено и закрыто'};

export default function InviteProblem({failure,C,inp,btnO}) {
  const [comment,setComment] = useState('Подключить кабинет поставщика к нашей организации');
  const [busy,setBusy] = useState(false);
  const [ticket,setTicket] = useState(null);
  const [error,setError] = useState('');
  const alive = useRef(true);
  useEffect(()=>{alive.current=true;return ()=>{alive.current=false;};},[]);
  const refresh = async () => {
    if(busy)return;
    setBusy(true);setError('');
    try {
      const response = await fetch(API+'/participant-support/tickets/'+ticket.id, {headers:{'X-Company-Id':String(failure.companyId),'X-Company-Mode':'company'}});
      const body = await response.json();
      if (!response.ok) throw new Error(typeof body.detail==='string'?body.detail:'Не удалось загрузить результат');
      if(alive.current)setTicket(body);
    }catch(e){if(alive.current)setError(e.message);}
    finally{if(alive.current)setBusy(false);}
  };
  const send = async () => {
    if (busy) return;
    setBusy(true);setError('');
    try {
      const response = await fetch(API+'/participant-support/tickets',{
        method:'POST',headers:{'Content-Type':'application/json','X-Company-Id':String(failure.companyId),'X-Company-Mode':'company'},
        body:JSON.stringify({diagnosticId:failure.diagnosticId,comment}),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(typeof body.detail==='string'?body.detail:'Не удалось сохранить обращение');
      if (alive.current) setTicket(body);
    } catch (e) {if (alive.current) setError(e.message);}
    finally {if (alive.current) setBusy(false);}
  };
  return <section aria-label="Помощь с подключением" style={{border:'1px solid '+C.warningBorder,borderRadius:12,padding:12,marginTop:12,color:C.text}}>
    <p role="alert">{failure.message}</p>
    {ticket ? <><p role="status">Обращение №{ticket.id} · {statuses[ticket.status]}. Администратор увидит его в вашей организации.</p>
      {ticket.result&&<p>Результат: {ticket.result}</p>}<button type="button" disabled={busy} onClick={refresh} style={{...btnO,minHeight:44}}>Проверить ответ</button></> : failure.diagnosticId ? <>
      <label>Что нужно сделать<textarea value={comment} onChange={e=>setComment(e.target.value)} maxLength={2000} style={{...inp,width:'100%',boxSizing:'border-box',minHeight:80}}/></label>
      <p style={{color:C.textSec}}>Организация, карточка и причина ошибки приложены автоматически.</p>
      <button type="button" disabled={busy||comment.trim().length<5} onClick={send} style={{...btnO,minHeight:44}}>{busy?'Сохраняю…':'Сообщить о проблеме'}</button>
    </> : <p>Сообщите администратору причину отказа: {failure.reasonCode}.</p>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
