import React, {useCallback, useEffect, useRef, useState} from 'react';

const groups = [
  ['Основные реквизиты', [
    ['name','Название компании'], ['inn','ИНН'], ['kpp','КПП'], ['ogrn','ОГРН / ОГРНИП'],
    ['legalAddress','Юридический адрес'], ['actualAddress','Фактический адрес'],
    ['directorName','ФИО руководителя'], ['directorPosition','Должность руководителя'],
  ]],
  ['Контакты', [['phone','Телефон'], ['email','Email','email'], ['website','Сайт','url'], ['specialization','Что поставляете']]],
  ['Банковские реквизиты', [['bank','Банк'], ['bik','БИК'], ['korAccount','Корреспондентский счёт'], ['account','Расчётный счёт']]],
];

function Profile({API, supplierId, C, card, inp, btnO, btnG}) {
  const [saved, setSaved] = useState(null);
  const [draft, setDraft] = useState({});
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [conflict, setConflict] = useState(false);
  const mounted = useRef(true);
  const locked = useRef(false);
  const request = useRef(null);
  const generation = useRef(0);
  const accept = useCallback(data => {setSaved(data); setDraft(data.fields); setConflict(false);}, []);
  const reload = useCallback(async () => {
    if (locked.current) return;
    locked.current = true; setLoading(true); setError(''); setMessage(''); setSaved(null);
    const run = ++generation.current;
    request.current = new AbortController();
    try {
      const response = await fetch(`${API}/suppliers/${supplierId}/requisites`, {credentials:'include', cache:'no-store', signal:request.current.signal});
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Не удалось загрузить профиль');
      if (mounted.current && generation.current === run) accept(data);
    } catch (e) {if (mounted.current && generation.current === run && e.name !== 'AbortError') setError(e.message);}
    finally {if (mounted.current && generation.current === run) {locked.current=false; setLoading(false);}}
  }, [API, supplierId, accept]);
  const cancelRequests = useCallback(() => {
    mounted.current=false; generation.current++; request.current?.abort(); locked.current=false;
  }, []);
  useEffect(() => {mounted.current=true; reload(); return cancelRequests;}, [reload, cancelRequests]);
  const changes = Object.fromEntries(Object.entries(draft).filter(([key,value]) => value !== saved?.fields[key]));
  return <section aria-label="Профиль поставщика" style={{color:C.text}}>
    <h2>Профиль компании</h2>
    <p style={{color:C.textSec}}>Общие реквизиты поставщика видны заказчикам. Договоры и индивидуальные условия хранятся отдельно в каждой сделке.</p>
    {loading && <p role="status">Загружаем профиль…</p>}
    {error && <p role="alert">{error}</p>}
    {message && <p role="status">{message}</p>}
    {!loading && <button type="button" disabled={busy} style={btnG} onClick={reload}>{conflict ? 'Загрузить актуальные реквизиты' : 'Обновить профиль'}</button>}
    {saved && !loading && <>
      <form onSubmit={async event => {
        event.preventDefault();
        if (locked.current || conflict || !Object.keys(changes).length) return;
        locked.current=true; setBusy(true); setError(''); setMessage('');
        const run = ++generation.current;
        request.current=new AbortController();
        try {
          const response=await fetch(`${API}/suppliers/${supplierId}/requisites`, {method:'PUT',credentials:'include',
            headers:{'Content-Type':'application/json'},signal:request.current.signal,
            body:JSON.stringify({...changes,expectedProfileVersion:saved.version})});
          const data=await response.json();
          if (!mounted.current || generation.current !== run) return;
          if (response.status===409) setConflict(true);
          if (!response.ok) throw new Error(data.detail || 'Не удалось сохранить реквизиты');
          accept(data); setMessage('Реквизиты сохранены');
        } catch (e) {if (mounted.current && generation.current === run && e.name!=='AbortError') setError(e.message);}
        finally {if (mounted.current && generation.current === run) {locked.current=false; setBusy(false);}}
      }}>
        <fieldset disabled={busy || conflict || !saved.canEdit} style={{border:0,padding:0,minWidth:0}}>
          {groups.map(([title,fields])=><section key={title} style={{...card,padding:16,marginTop:16}}>
            <h3 style={{marginTop:0}}>{title}</h3>
            <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(min(100%,240px),1fr))',gap:12}}>
              {fields.map(([key,label,type])=><label key={key} style={{fontSize:13}}>{label}
                <input name={key} type={type||'text'} required={key==='name'} maxLength={saved.fieldLimits?.[key] ?? 255}
                  value={draft[key]||''} onChange={e=>{setDraft({...draft,[key]:e.target.value});setMessage('');}}
                  style={{...inp,display:'block',width:'100%',boxSizing:'border-box',marginTop:6,marginBottom:0}}/>
              </label>)}
            </div>
          </section>)}
          <button type="submit" disabled={!Object.keys(changes).length} style={{...btnO,marginTop:16,padding:'12px 18px'}}>{busy?'Сохраняем…':'Сохранить реквизиты'}</button>
        </fieldset>
      </form>
      <section aria-label="Тариф поставщика" style={{...card,padding:16,marginTop:20}}>
        <h3 style={{marginTop:0}}>Тариф</h3>
        <p>{saved.tariff?.status==='not_configured' ? 'Условия тарифа поставщика пока не заданы.' : 'Информация о тарифе недоступна.'}</p>
        {saved.team?.enabled && saved.team.managerLimit===null && <p>Сейчас количество менеджеров программой не ограничено.</p>}
        {saved.team?.enabled && saved.team.customerAssignments && saved.team.customersPerManagerLimit===null && <p>За одним менеджером можно закрепить любое количество заказчиков.</p>}
      </section>
    </>}
  </section>;
}

export default function SupplierProfile({suppliers=[], user, ...props}) {
  const [selected, setSelected] = useState('');
  const current = suppliers.find(s=>String(s.id)===selected) || suppliers[0];
  if (!current) return <p>Профиль доступен руководителю поставщика после подтверждения прав.</p>;
  return <>
    {suppliers.length>1 && <label>Компания поставщика<select value={current.id} onChange={e=>setSelected(e.target.value)}>
      {suppliers.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}
    </select></label>}
    <Profile key={`${user?.id}:${user?.role}:${props.API}:${current.id}`} {...props} supplierId={current.id}/>
  </>;
}
