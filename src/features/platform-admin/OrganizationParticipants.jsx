import { useEffect, useRef, useState } from 'react';
import './OrganizationParticipants.css';

export const ticketStatuses = {new:'Новое',in_progress:'В работе',waiting:'Ожидает сведения',resolved:'Исправлено',closed:'Проверено и закрыто'};
const transitions = {new:['in_progress'],in_progress:['waiting','resolved'],waiting:['in_progress'],resolved:['closed','in_progress'],closed:['in_progress']};
const sources = {warehouse_invoice:'Из накладной',invite_link:'По приглашению',manual:'Создана вручную'};

export default function OrganizationParticipants({company,API,C,btnG,btnO,inp}) {
  const [tab,setTab] = useState('participants');
  const [query,setQuery] = useState('');
  const [search,setSearch] = useState('');
  const [status,setStatus] = useState('');
  const [offset,setOffset] = useState(0);
  const [data,setData] = useState(null);
  const [error,setError] = useState('');
  const [retry,setRetry] = useState(0);
  const [detail,setDetail] = useState(null);
  const [result,setResult] = useState('');
  const [verified,setVerified] = useState(false);
  const [busy,setBusy] = useState(false);
  const alive = useRef(true);
  const command = useRef(0);
  const prefix = API+'/system/companies/'+company.id;
  useEffect(()=>{alive.current=true;return ()=>{alive.current=false;command.current+=1;};},[company.id]);
  useEffect(()=>{
    const abort = new AbortController();
    setData(null);setError('');setDetail(null);setBusy(false);command.current+=1;
    const path = tab==='participants'?'/participants?search='+encodeURIComponent(search):'/participant-tickets?status='+status;
    (async()=>{
      try {
        const response = await fetch(prefix+path+'&limit=25&offset='+offset,{signal:abort.signal});
        const body = await response.json();
        if (!response.ok) throw new Error(typeof body.detail==='string'?body.detail:'Не удалось загрузить раздел');
        if (!abort.signal.aborted) setData(body);
      } catch(e) {if (!abort.signal.aborted) setError(e.message);}
    })();
    return ()=>abort.abort();
  },[prefix,tab,search,status,offset,retry]);
  const open = async id => {
    const version = ++command.current;
    setBusy(true);setError('');setDetail(null);
    try {
      const response = await fetch(prefix+'/participant-tickets/'+id);
      const body = await response.json();
      if (!response.ok) throw new Error(typeof body.detail==='string'?body.detail:'Не удалось открыть обращение');
      if (alive.current&&command.current===version) {setDetail(body);setResult('');setVerified(false);}
    } catch(e) {if(alive.current&&command.current===version)setError(e.message);}
    finally {if(alive.current&&command.current===version)setBusy(false);}
  };
  const update = async nextStatus => {
    if (busy) return;
    const version = ++command.current;
    setBusy(true);setError('');
    try {
      const response = await fetch(prefix+'/participant-tickets/'+detail.id,{
        method:'PATCH',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({status:nextStatus,expectedVersion:detail.version,result,verified}),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(typeof body.detail==='string'?body.detail:'Не удалось изменить статус');
      if (alive.current&&command.current===version) {setDetail(null);setRetry(n=>n+1);}
    } catch(e) {if(alive.current&&command.current===version)setError(e.message);}
    finally {if(alive.current&&command.current===version)setBusy(false);}
  };
  const switchTab = value => {if(busy)return;setTab(value);setOffset(0);setDetail(null);};
  return <section aria-label={'Участники и доступ: '+company.name} className="organization-participants" style={{color:C.text,borderColor:C.border,background:C.bg}}>
    <h3>Участники и доступ · {company.name}</h3>
    <p className="organization-participants__muted" style={{color:C.textSec}}>Поставщики и обращения этой организации. Здесь проверяются связи; доступ к документам не изменяется.</p>
    <div className="organization-participants__toolbar">
      <button type="button" disabled={busy} aria-pressed={tab==='participants'} onClick={()=>switchTab('participants')} style={tab==='participants'?btnO:btnG}>Поставщики</button>
      <button type="button" disabled={busy} aria-pressed={tab==='tickets'} onClick={()=>switchTab('tickets')} style={tab==='tickets'?btnO:btnG}>Проблемы и обращения</button>
    </div>
    {tab==='participants'?<form onSubmit={e=>{e.preventDefault();if(busy)return;setOffset(0);setSearch(query);}} className="organization-participants__toolbar">
      <label className="organization-participants__search">Название или ИНН<input disabled={busy} value={query} onChange={e=>setQuery(e.target.value)} maxLength={100} style={{...inp,marginBottom:0}}/></label>
      <button type="submit" disabled={busy} style={btnG}>Найти</button>
    </form>:<label>Статус обращения<select value={status} disabled={busy} onChange={e=>{setStatus(e.target.value);setOffset(0);}} style={inp}>
      <option value="">Все статусы</option>{Object.entries(ticketStatuses).map(([key,label])=><option key={key} value={key}>{label}</option>)}
    </select></label>}
    {error&&<div role="alert"><p>{error}</p><button type="button" onClick={()=>{setBusy(false);setRetry(n=>n+1);}} style={btnG}>Повторить загрузку</button></div>}
    {!data&&!error&&<p role="status">Загружаю…</p>}
    {data&&data.items.length===0&&<p>{search||status?'По выбранным условиям ничего не найдено.':tab==='participants'?'Поставщики этой организации пока не подключены.':'Обращений этой организации пока нет.'}</p>}
    {data&&<ul className="organization-participants__list">{data.items.map(item=><li key={item.id} style={{borderColor:C.border}}>
      {tab==='participants'?<>
        <strong>{item.name}</strong><span>ИНН: {item.inn||'не указан'}</span>
        <span>{item.has_account?'Кабинет зарегистрирован':'Без кабинета'} · {sources[item.source_type]||'Источник создания неизвестен'}</span>
        <span>Отношение: {item.status||'не указано'}{item.merged_into_supplier_id?' · Карточка объединена':''}</span>
        {Number(item.open_tickets)>0&&<button style={btnG} onClick={()=>switchTab('tickets')}>Обращения: {item.open_tickets}</button>}
      </>:<>
        <strong>№{item.id} · {item.context?.participantName||'Участник'}</strong>
        <span>{ticketStatuses[item.status]}</span><span>{item.reason}</span>
        <button type="button" disabled={busy} onClick={()=>open(item.id)} style={btnG}>Разобрать обращение</button>
      </>}
    </li>)}</ul>}
    {data&&<div className="organization-participants__toolbar">
      <button type="button" disabled={busy||offset===0} onClick={()=>setOffset(n=>Math.max(0,n-25))} style={btnG}>Назад</button>
      <span>Страница {offset/25+1}</span>
      <button type="button" disabled={busy||!data.hasMore} onClick={()=>setOffset(n=>n+25)} style={btnG}>Далее</button>
    </div>}
    {detail&&<article aria-label={'Обращение №'+detail.id} className="organization-participants__detail" style={{borderColor:C.border}}>
      <h4>Обращение №{detail.id} · {ticketStatuses[detail.status]}</h4>
      <p><strong>Причина:</strong> {detail.reason}</p>
      <p><strong>Где:</strong> приглашение поставщика → создание ссылки.</p>
      <p><strong>Карточка:</strong> {detail.context.participantName} · {sources[detail.context.sourceType]||'Источник неизвестен'}</p>
      <p><strong>Запрос пользователя:</strong> {detail.comment}</p>
      <p><strong>Следующее действие:</strong> {detail.recommendedAction}</p>
      <p><strong>Результат:</strong> {detail.result||'Ещё не указан'}</p>
      <details><summary>История и диагностика</summary><p>Причина: {detail.reason_code} · Номер диагностики: {detail.diagnostic_id}</p>
        <p>Версия приложения: {detail.context.applicationVersion} · Роль: {detail.context.role}</p>
        <ul>{detail.history.map((event,n)=><li key={n}>{ticketStatuses[event.to_status]} · {new Date(event.created_at).toLocaleString('ru-RU')}{event.result?' · '+event.result:''}</li>)}</ul>
      </details>
      <label>Сообщение о результате — видно автору обращения<textarea value={result} onChange={e=>setResult(e.target.value)} maxLength={2000} style={{...inp,minHeight:80}}/></label>
      {detail.status==='resolved'&&<label><input type="checkbox" checked={verified} onChange={e=>setVerified(e.target.checked)}/> Исходный сценарий проверен</label>}
      <div className="organization-participants__toolbar">{transitions[detail.status].map(next=><button key={next} type="button" disabled={busy||(next==='closed'&&!verified)||(['resolved','closed'].includes(next)&&result.trim().length<5)} onClick={()=>update(next)} style={btnO}>{next==='in_progress'&&detail.status!=='new'?'Вернуть в работу':ticketStatuses[next]}</button>)}
        <button type="button" disabled={busy} onClick={()=>setDetail(null)} style={btnG}>Скрыть карточку</button>
      </div>
    </article>}
  </section>;
}
