import React,{useCallback,useEffect,useRef,useState} from 'react';

export default function SupplierTeam({API,context,C={},mode='team',onChanged}) {
 const leaders=(context?.suppliers||[]).filter(s=>s.role==='leader');
 const [selected,setSelected]=useState('');
 const supplierId=leaders.some(s=>String(s.id)===selected)?selected:String(leaders[0]?.id||'');
 const [snapshot,setSnapshot]=useState(null);
 const [error,setError]=useState('');const [notice,setNotice]=useState('');
 const [busy,setBusy]=useState(false);const locked=useRef(false);const pending=useRef(null);
 const generation=useRef(0);
 const reload=useCallback(async()=>{
  const run=++generation.current;setSnapshot(null);setError('');
  if(!supplierId)return;
  try{
   const response=await fetch(`${API}/supplier-team/${supplierId}`,{cache:'no-store'});
   const data=await response.json();
   if(!response.ok)throw new Error(data?.detail||'Не удалось загрузить команду');
   if(run===generation.current)setSnapshot({...data,supplierId});
  }catch(e){if(run===generation.current)setError(e.message);}
 },[API,supplierId]);
 useEffect(()=>{const counter=generation;reload();return()=>{counter.current++;};},[reload]);
 const command=async(fields)=>{
  if(locked.current)return;
  locked.current=true;setBusy(true);setError('');setNotice('');
  const key=JSON.stringify([supplierId,fields]);
  if(pending.current?.key!==key)pending.current={key,requestId:crypto.randomUUID()};
  try{
   const response=await fetch(`${API}/supplier-team/${supplierId}/commands`,{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({...fields,requestId:pending.current.requestId})});
   const data=await response.json();
   if(!response.ok){if(response.status<500)pending.current=null;throw new Error(data?.detail||'Изменение не сохранено');}
   pending.current=null;await reload();await onChanged?.();setNotice('Изменения сохранены');
  }catch(e){setError(e.message);}
  finally{locked.current=false;setBusy(false);}
 };
 if(!leaders.length)return null;
 const data=snapshot?.supplierId===supplierId?snapshot:null;
 const managers=(data?.members||[]).filter(m=>m.role==='manager');
 return <section style={{color:C.text}} className="supplier-orders supplier-team" aria-label={mode==='team'?'Команда поставщика':'Ответственные за заказчиков'}>
  <h2>{mode==='team'?'Команда':'Ответственные за заказчиков'}</h2>
  <p>{mode==='team'?'Пригласите менеджеров в этот кабинет. Количество участников не ограничено.':'Выберите одного менеджера для каждого заказчика. Он получит все доступные текущие и новые заявки этой компании. Количество заказчиков на менеджера не ограничено.'}</p>
  {leaders.length>1&&<label>Поставщик <select disabled={busy} value={supplierId} onChange={e=>{setSelected(e.target.value);setNotice('');}}>{leaders.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label>}
  <button type="button" disabled={busy} onClick={reload}>Обновить команду и назначения</button>
  {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
  {!data&&!error&&<p role="status">Загрузка…</p>}
  {data&&mode==='customers'&&<>
   {!data.customers.length&&<p>Пока нет связанных заказчиков. Они появятся после приглашения поставщика или запроса КП.</p>}
   {data.customers.map(c=><article className="supplier-order" key={c.id}>
    <h3>{c.name} · №{c.id}</h3>
    <label>Ответственный за {c.name}<select disabled={busy} value={c.memberId||''} onChange={e=>command({action:'assign_customer',companyId:c.id,memberId:e.target.value?Number(e.target.value):null,version:c.version})}>
     <option value="">Не назначен — только руководитель</option>
     {managers.filter(m=>m.active&&m.userActive).map(m=><option key={m.id} value={m.id}>{m.name} · {m.email}</option>)}
    </select></label>
   </article>)}
  </>}
  {data&&mode==='team'&&<>
   <button type="button" disabled={busy} onClick={()=>command({action:'invite_manager',expiresInDays:14})}>Создать приглашение менеджеру</button>
   <p>Ссылка действует 14 дней и используется один раз. Передайте её нужному сотруднику.</p>
   {!managers.length&&<p>Менеджеров пока нет. Создайте приглашение, чтобы добавить первого.</p>}
   {managers.map(m=><article className="supplier-order" key={m.id}>
    <h3>{m.name}</h3><p>{m.email} · {m.active&&m.userActive?'Активен':'Отключён'} · Заказчиков: {data.customers.filter(c=>c.memberId===m.id).length}</p>
    <button type="button" disabled={busy||!m.userActive} onClick={()=>{
     const reason=m.active?window.prompt('Причина отключения менеджера. Его заказчики останутся у руководителя до нового назначения.',''):'';
     if(reason===null)return;
     command({action:'member_active',memberId:m.id,version:m.version,active:!m.active,reason});
    }}>{m.active?'Отключить менеджера':'Включить менеджера'}</button>
   </article>)}
   <h3>Приглашения</h3>
   {data.invites.map(i=>{
    const active=typeof i.valid==='boolean'?i.valid:!i.used&&!i.revokedAt&&new Date(i.expiresAt)>new Date();
    const link=`${window.location.origin}/?invite=${encodeURIComponent(i.code)}`;
    return <article className="supplier-order" key={i.id}><p>Приглашение №{i.id} · {i.used?'Использовано':i.revokedAt?'Отозвано':active?'Действует':'Недействительно'}</p>
     {active&&<><label>Ссылка для менеджера<input readOnly value={link} onFocus={e=>e.target.select()} /></label>
      <button type="button" disabled={busy} onClick={async()=>{try{await navigator.clipboard.writeText(link);setNotice('Ссылка скопирована');}catch{setError('Выделите и скопируйте ссылку из поля');}}}>Скопировать ссылку</button>
      <button type="button" disabled={busy} onClick={()=>command({action:'revoke_invite',inviteId:i.id})}>Отозвать приглашение</button></>}
    </article>;
   })}
   <h3>История изменений</h3>
   {!data.history?.length&&<p>Изменений пока нет.</p>}
   {(data.history||[]).map(event=>{
    const memberName=id=>id?(data.members.find(m=>m.id===id)?.name||`Менеджер №${id}`):'Не назначен';
    const labels={assign_customer:'Смена ответственного',member_active:event.result.active?'Включение менеджера':'Отключение менеджера',invite_manager:'Приглашение менеджера',revoke_invite:'Отзыв приглашения'};
    return <p key={event.id}>{new Date(event.createdAt).toLocaleString('ru-RU')} · {event.actorName} · {labels[event.action]||event.action}
     {event.action==='assign_customer'&&` · Заказчик №${event.result.companyId}: ${memberName(event.result.previousMemberId)} → ${memberName(event.result.memberId)}`}
     {event.action==='member_active'&&` · ${memberName(event.result.memberId)}`}
     {event.details.reason&&` · ${event.details.reason}`}</p>;
   })}
  </>}
 </section>;
}
