import { useEffect, useRef, useState } from 'react';
import './OrganizationParticipants.css';
import { directoryTabs, MembershipItem, InvitationItem } from './ParticipantDirectoryItems';
import SupplierConnectionPreview from './SupplierConnectionPreview';
import SupportAccessPanel from './SupportAccessPanel';

export const ticketStatuses = {new:'Новое',in_progress:'В работе',waiting:'Ожидает сведения',resolved:'Исправлено',closed:'Проверено и закрыто'};
const transitions = {new:['in_progress'],in_progress:['waiting','resolved'],waiting:['in_progress'],resolved:['closed','in_progress'],closed:['in_progress']};
const sources = {warehouse_invoice:'Из накладной',invite_link:'По приглашению',manual:'Создана вручную',owner_confirmed_connection:'Подтверждено владельцем кабинета'};

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
  const [previewId,setPreviewId] = useState(null);
  const alive = useRef(true);
  const command = useRef(0);
  const prefix = API+'/system/companies/'+company.id;
  const selectedTab = directoryTabs[tab];
  const states = tab==='tickets'?ticketStatuses:selectedTab.states;
  useEffect(()=>{alive.current=true;return ()=>{alive.current=false;command.current+=1;};},[company.id]);
  useEffect(()=>{
    const abort = new AbortController();
    setData(null);setError('');setDetail(null);setPreviewId(null);setBusy(false);command.current+=1;
    const config = directoryTabs[tab];
    const filters = new URLSearchParams();
    if(config.searchLabel) filters.set('search',search);
    if(config.statusLabel) filters.set('status',status);
    const path = config.path+'?'+filters.toString();
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
    setBusy(true);setError('');setDetail(null);setPreviewId(null);
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
  const switchTab = value => {if(busy||value===tab)return;setTab(value);setOffset(0);setDetail(null);setData(null);setQuery('');setSearch('');setStatus('');};
  return <section aria-label={'Участники и доступ: '+company.name} className="organization-participants" style={{color:C.text,borderColor:C.border,background:C.bg}}>
    <h3>Участники и доступ · {company.name}</h3>
    <p className="organization-participants__muted" style={{color:C.textSec}}>Участники, приглашения и обращения выбранной организации.</p>
    <div className="organization-participants__toolbar organization-participants__tabs">
      {Object.entries(directoryTabs).map(([key,config])=><button key={key} type="button" disabled={busy} aria-pressed={tab===key} onClick={()=>switchTab(key)} style={tab===key?btnO:btnG}>{config.label}</button>)}
    </div>
    {tab==='memberships'&&<p className="organization-participants__muted">Показаны сохранённые членства, включая отключённые. Доступ к объектам и документам проверяется отдельно.</p>}
    {tab==='invitations'&&<p className="organization-participants__muted">Здесь видны назначение и срок. Возможность принять приглашение проверяет сервер при регистрации. Удалённые приглашения в этот список не входят.</p>}
    {selectedTab.searchLabel&&<form onSubmit={e=>{e.preventDefault();if(busy)return;setOffset(0);setSearch(query.trim());}} className="organization-participants__toolbar">
      <label className="organization-participants__search">{selectedTab.searchLabel}<input disabled={busy} value={query} onChange={e=>setQuery(e.target.value)} maxLength={100} style={{...inp,marginBottom:0}}/></label>
      <button type="submit" disabled={busy} style={btnG}>Найти</button>
    </form>}
    {selectedTab.statusLabel&&<label>{selectedTab.statusLabel}<select value={status} disabled={busy} onChange={e=>{setStatus(e.target.value);setOffset(0);}} style={inp}>
      <option value="">Все состояния</option>{Object.entries(states).map(([key,label])=><option key={key} value={key}>{label}</option>)}
    </select></label>}
    {error&&<div role="alert"><p>{error}</p><button type="button" onClick={()=>{setBusy(false);setRetry(n=>n+1);}} style={btnG}>Повторить загрузку</button></div>}
    {!data&&!error&&<p role="status">Загружаю…</p>}
    {data&&data.items.length===0&&<p>{search||status?'По выбранным условиям ничего не найдено.':selectedTab.empty}</p>}
    {data&&<ul className="organization-participants__list">{data.items.map(item=><li key={item[selectedTab.idKey]} style={{borderColor:C.border}}>
      {tab==='participants'?<>
        <strong>{item.name}</strong><span>ИНН: {item.inn||'не указан'}</span>
        <span>{item.merged_into_supplier_id?'Объединённая карточка':item.has_account?'Кабинет зарегистрирован':'Без кабинета'} · {sources[item.source_type]||'Источник создания неизвестен'}</span>
        <span>Отношение: {item.status||'не указано'}{item.merged_into_supplier_id?' · Карточка объединена':''}</span>
        {Number(item.open_tickets)>0&&<button style={btnG} onClick={()=>switchTab('tickets')}>Обращения: {item.open_tickets}</button>}
        <button type="button" disabled={busy} style={btnG} onClick={()=>setPreviewId(item.id)}>{item.merged_into_supplier_id?'Открыть основную карточку':'Проверить кабинет'}</button>
        {previewId===item.id&&<SupplierConnectionPreview key={prefix+'/'+item.id} prefix={prefix}
          supplierId={Number(item.merged_into_supplier_id)||item.id} btnG={btnG} onClose={()=>setPreviewId(null)} onChanged={()=>setRetry(n=>n+1)}/>}
      </>:tab==='memberships'?<MembershipItem item={item}/>:tab==='invitations'?<InvitationItem item={item}/>:<>
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
      {detail.participant_type==='supplier'&&<><button type="button" disabled={busy} style={btnG} onClick={()=>setPreviewId(detail.participant_id)}>Проверить кабинет</button>
        {previewId===detail.participant_id&&<SupplierConnectionPreview key={prefix+'/'+detail.participant_id} prefix={prefix} supplierId={detail.participant_id} btnG={btnG} onClose={()=>setPreviewId(null)} onChanged={()=>setRetry(n=>n+1)}/>}</>}
      <details><summary>История и диагностика</summary><p>Причина: {detail.reason_code} · Номер диагностики: {detail.diagnostic_id}</p>
        <p>Версия приложения: {detail.context.applicationVersion} · Роль: {detail.context.role}</p>
        <ul>{detail.history.map((event,n)=><li key={n}>{ticketStatuses[event.to_status]} · {new Date(event.created_at).toLocaleString('ru-RU')}{event.result?' · '+event.result:''}</li>)}</ul>
      </details>
      {process.env.REACT_APP_PARTICIPANT_SUPPORT_ACCESS_ENABLED==='1'&&<details><summary>Доступ сотрудника поддержки</summary><SupportAccessPanel key={prefix+'/'+detail.id+'/'+detail.version} prefix={prefix} ticketId={detail.id} btnG={btnG} btnO={btnO} inp={inp}/></details>}
      <label>Сообщение о результате — видно автору обращения<textarea value={result} onChange={e=>setResult(e.target.value)} maxLength={2000} style={{...inp,minHeight:80}}/></label>
      {detail.status==='resolved'&&<label><input type="checkbox" checked={verified} onChange={e=>setVerified(e.target.checked)}/> Исходный сценарий проверен</label>}
      <div className="organization-participants__toolbar">{transitions[detail.status].map(next=><button key={next} type="button" disabled={busy||(next==='closed'&&!verified)||(['resolved','closed'].includes(next)&&result.trim().length<5)} onClick={()=>update(next)} style={btnO}>{next==='in_progress'&&detail.status!=='new'?'Вернуть в работу':ticketStatuses[next]}</button>)}
        <button type="button" disabled={busy} onClick={()=>setDetail(null)} style={btnG}>Скрыть карточку</button>
      </div>
    </article>}
  </section>;
}
