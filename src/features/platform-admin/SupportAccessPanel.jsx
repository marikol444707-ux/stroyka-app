import {useEffect, useId, useRef, useState} from 'react';

export default function SupportAccessPanel({prefix, ticketId, btnG, btnO, inp}) {
  const assigneeControl = useId();
  const [data, setData] = useState(null);
  const [assignees, setAssignees] = useState([]);
  const [assignee, setAssignee] = useState('');
  const [minutes, setMinutes] = useState('60');
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [retry, setRetry] = useState(0);
  const command = useRef(0);
  const active = useRef(true);
  const pending = useRef(false);
  const path = prefix + '/participant-tickets/' + ticketId + '/support-access';
  useEffect(() => {
    active.current = true;
    const abort = new AbortController();
    setData(null); setError(''); setAssignee(''); setReason(''); setBusy(false); pending.current=false;
    command.current++;
    const read = async url => {
      const response = await fetch(url, {signal:abort.signal});
      const body = await response.json();
      if (!response.ok) throw new Error(typeof body.detail==='string'?body.detail:'Не удалось загрузить доступ поддержки');
      return body;
    };
    Promise.all([read(path), read(prefix + '/support-assignees')]).then(([grants, staff]) => {
      if (!abort.signal.aborted) {setData(grants); setAssignees(staff.items);}
    }).catch(e => {if (!abort.signal.aborted) setError(e.message);});
    return () => {active.current=false; abort.abort();};
  }, [path, prefix, retry]);
  const send = async (url, body) => {
    if (pending.current) return;
    pending.current=true; setBusy(true); setError('');
    const version = ++command.current;
    try {
      const response = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail==='string'?result.detail:'Не удалось изменить доступ');
      if (active.current && command.current===version) {setReason(''); setRetry(n=>n+1);}
    } catch(e) {if (active.current && command.current===version) setError(e.message);}
    finally {if (active.current && command.current===version) {pending.current=false; setBusy(false);}}
  };
  return <section aria-label="Доступ поддержки">
    <h4>Доступ поддержки</h4>
    <p>Только диагностика этого обращения. Счета, файлы и изменения в компании недоступны.</p>
    {error&&<p role="alert">{error}</p>}
    {!data&&!error&&<p role="status">Загружаю доступ…</p>}
    {data&&<>
      <form onSubmit={e=>{e.preventDefault(); send(path, {assigneeId:Number(assignee), action:'diagnostic.read', expiresInMinutes:Number(minutes), reason});}}>
        <label htmlFor={assigneeControl}>Сотрудник поддержки</label><select id={assigneeControl} required disabled={busy} value={assignee} onChange={e=>setAssignee(e.target.value)} style={inp}>
          <option value="">Выберите сотрудника</option>{assignees.map(person=><option key={person.id} value={person.id}>{person.name} · №{person.id}</option>)}
        </select>
        {!assignees.length&&<p>Нет действующих сотрудников поддержки. Управление сотрудниками — в разделе команды платформы.</p>}
        <label>Срок доступа, минут<input type="number" required min="1" max="1440" step="1" disabled={busy} value={minutes} onChange={e=>setMinutes(e.target.value)} style={inp}/></label>
        <label>Зачем нужен доступ<textarea required minLength={5} maxLength={1000} disabled={busy} value={reason} onChange={e=>setReason(e.target.value)} style={inp}/></label>
        <button type="submit" disabled={busy||!assignee||reason.trim().length<5||!Number.isInteger(Number(minutes))||Number(minutes)<1||Number(minutes)>1440} style={btnO}>Дать доступ к диагностике</button>
      </form>
      <p>Изменение обращения или прав сотрудника прекращает доступ. Повторная выдача заменяет прежний доступ.</p>
      {data.items.length===0&&<p>Доступ к этому обращению ещё не выдавался.</p>}
      <ul className="organization-participants__list">{data.items.map(grant=><li key={grant.id}>
        <strong>{grant.assigneeName} · №{grant.assigneeId}</strong>
        <span>{grant.revokedAt?'Отозван':grant.active?'Действует':'Срок или условия доступа изменились'}</span>
        <span>До {new Date(grant.expiresAt).toLocaleString('ru-RU')}</span>
        <span>{grant.reason}</span>
        {!grant.revokedAt&&<button type="button" disabled={busy} style={btnG} onClick={()=>send(path+'/'+grant.id+'/revoke', {reason:'Администратор отозвал доступ к обращению'})}>Отозвать доступ</button>}
        <details><summary>Последние действия</summary><ul>{grant.history.map((event,n)=><li key={n}>{({granted:'Доступ выдан',listed:'Показано в списке', 'diagnostic.read':'Диагностика открыта', revoked:'Доступ отозван'})[event.action]} · сотрудник №{event.actor_id} · {new Date(event.created_at).toLocaleString('ru-RU')}</li>)}</ul></details>
      </li>)}</ul>
      {data.hasMore&&<p>Показаны последние 25 доступов.</p>}
    </>}
    {error&&<button type="button" disabled={busy} style={btnG} onClick={()=>setRetry(n=>n+1)}>Обновить доступ</button>}
  </section>;
}
