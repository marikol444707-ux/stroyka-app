import React, {useEffect, useRef, useState} from 'react';
import {API} from '../api';

const money = n => Number(n || 0).toLocaleString('ru-RU', {maximumFractionDigits:2}) + ' ₽';
const numeric = value => value !== '' && Number.isFinite(Number(value)) && Number(value) >= 0;
const headers = company => ({'Content-Type':'application/json','X-Company-Id':String(company),'X-Company-Mode':'company'});
async function request(path, options) {
  const response=await fetch(API+path,options);
  const result=await response.json().catch(()=>({}));
  if(!response.ok)throw new Error(typeof result.detail==='string'?result.detail:`Не удалось выполнить действие (${response.status})`);
  return result;
}

function ReviewSource({source, data, refresh, C, inp, btnB}) {
  const [staffId,setStaffId]=useState(''),[projectId,setProjectId]=useState('');
  const [amount,setAmount]=useState(''),[previous,setPrevious]=useState(''),[basis,setBasis]=useState('');
  const [confirmed,setConfirmed]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [state,setState]=useState(source.expectedState);
  const active=useRef(true),flight=useRef(false),current=useRef(source.expectedState);current.current=source.expectedState;
  useEffect(()=>{active.current=true;return()=>{active.current=false;};},[]);
  const stale=state!==source.expectedState;
  const save=async()=>{
    if(flight.current||stale)return;flight.current=true;setBusy(true);setError('');
    try {
      const result=await request('/tool-deductions/review',{method:'POST',headers:headers(data.companyId),body:JSON.stringify({
        sourceKey:source.sourceKey,expectedState:state,staffId:Number(staffId),projectId:Number(projectId),amount,
        previouslyDeducted:previous,basis,confirmed})});
      if(!active.current||current.current!==state)return;
      if(!result.ok||!Number.isSafeInteger(result.id)||!Number.isSafeInteger(result.revision))throw Error('Ответ не подтверждает сверку. Обновите данные перед повтором.');
      await refresh();
    }catch(e){if(active.current&&current.current===state)setError(e.message);}finally{flight.current=false;if(active.current)setBusy(false);}
  };
  return <fieldset disabled={busy} style={{border:'1px solid '+C.border,padding:12,marginBottom:8}}>
    <legend>{source.name} · {source.inventory_number || 'Без номера'} · {source.history_id?`выдача №${source.history_id}`:'Старая карточка без записи выдачи'}</legend>
    <p>В старой записи: {source.master_name || 'Получатель не указан'} · {source.project || 'Объект не указан'} · {source.date || 'Дата не указана'}. Текущая цена карточки {money(source.cost)} — проверьте стоимость именно этой выдачи по документам.</p>
    {error&&<p role="alert">{error}</p>}{stale&&<p role="alert">Исходная запись изменилась. Сверьте её заново; введённые значения сохранены.</p>}
    <label>Получатель <select aria-label={`Получатель ${source.sourceKey}`} style={inp} value={staffId} onChange={e=>setStaffId(e.target.value)}><option value="">Выберите точного сотрудника</option>{data.staff.map(s=><option key={s.id} value={s.id}>{s.name} · №{s.id}</option>)}</select></label>
    <label>Объект <select aria-label={`Объект ${source.sourceKey}`} style={inp} value={projectId} onChange={e=>setProjectId(e.target.value)}><option value="">Выберите объект</option>{data.projects.map(p=><option key={p.id} value={p.id}>{p.name} · №{p.id}</option>)}</select></label>
    <label>Стоимость выдачи <input aria-label={`Стоимость ${source.sourceKey}`} style={inp} type="number" min="0.01" step="0.01" value={amount} onChange={e=>setAmount(e.target.value)}/></label>
    <label>Уже удержано ранее <input aria-label={`Ранее удержано ${source.sourceKey}`} style={inp} type="number" min="0" step="0.01" value={previous} onChange={e=>setPrevious(e.target.value)}/></label>
    <label>Основание по документам <input aria-label={`Основание ${source.sourceKey}`} style={inp} maxLength={2000} value={basis} onChange={e=>setBasis(e.target.value)}/></label>
    <label><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>Получатель, стоимость и прошлые удержания проверены по документам</label>
    <button style={btnB} disabled={stale||!staffId||!projectId||!numeric(amount)||Number(amount)<=0||!numeric(previous)||Number(previous)>Number(amount)||!basis.trim()||!confirmed} onClick={save}>Подтвердить выдачу для распределения</button>
    {stale&&<button onClick={()=>{setState(source.expectedState);setConfirmed(false);}}>Использовать новую запись после сверки</button>}
  </fieldset>;
}

function AllocationRow({row,acts,staff,refresh,C,inp,btnB,btnG}) {
  const [revision,setRevision]=useState(row.revision),[target,setTarget]=useState('act'),[actId,setActId]=useState(''),[month,setMonth]=useState('');
  const [amount,setAmount]=useState(''),[basis,setBasis]=useState(''),[confirmed,setConfirmed]=useState(false);
  const [refundId,setRefundId]=useState(''),[refundAmount,setRefundAmount]=useState(''),[refundBasis,setRefundBasis]=useState(''),[refundConfirmed,setRefundConfirmed]=useState(false);
  const [correctedStaff,setCorrectedStaff]=useState(String(row.staff_id)),[correctedAmount,setCorrectedAmount]=useState(String(row.amount));
  const [correctionBasis,setCorrectionBasis]=useState(''),[correctionConfirmed,setCorrectionConfirmed]=useState(false);
  const [previousRefund,setPreviousRefund]=useState(''),[historyBasis,setHistoryBasis]=useState(''),[historyConfirmed,setHistoryConfirmed]=useState(false);
  const [oldRefundAmount,setOldRefundAmount]=useState(''),[oldRefundBasis,setOldRefundBasis]=useState(''),[oldRefundConfirmed,setOldRefundConfirmed]=useState(false);
  const history=row.historicalRefund;

  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const active=useRef(true),flight=useRef(false),current=useRef(row);current.current=row;
  useEffect(()=>{active.current=true;return()=>{active.current=false;};},[]);
  const stale=revision!==row.revision;
  const eligible=(acts||[]).filter(a=>Number(a.companyId)===row.company_id&&Number(a.masterId)===row.staff_id&&a.project===row.project_name&&a.sourceType!=='daily_work'&&a.status!=='Аннулирован');
  const used=row.allocations.reduce((n,a)=>n+Number(a.amount),0);
  const canCorrect=Number(row.previously_deducted)===0&&row.allocations.every(a=>Number(a.amount)===0&&Number(a.refunded)===0);
  const change=async kind=>{
    const correction=kind==='correction',refund=kind===true;
    const historyReview=kind==='history-review',historyRefund=kind==='history-refund';
    if(flight.current||stale)return;flight.current=true;setBusy(true);setError('');setNotice('');
    const isCurrent=()=>active.current&&current.current.revision===row.revision;
    try {
      const result=await request(`/tool-deductions/${row.id}/${historyReview?'historical-refund-review':historyRefund?'historical-refunds':correction?'correction':refund?'refunds':'allocations'}`,{method:refund||historyRefund?'POST':'PUT',headers:headers(row.company_id),body:JSON.stringify({expectedRevision:revision,
        ...(historyReview?{previouslyRefunded:previousRefund,basis:historyBasis,confirmed:historyConfirmed}:historyRefund?{amount:oldRefundAmount,basis:oldRefundBasis,confirmed:oldRefundConfirmed}:correction?{staffId:Number(correctedStaff),amount:correctedAmount,basis:correctionBasis,confirmed:correctionConfirmed}:refund?{allocationId:Number(refundId),amount:refundAmount,basis:refundBasis,confirmed:refundConfirmed}:{...(target==='act'?{actId:Number(actId)}:{month}),amount,basis,confirmed})})});
      if(!isCurrent())return;
      if(!result.ok||result.id!==row.id||!Number.isSafeInteger(result.revision)||result.revision<=revision)throw Error('Ответ не подтверждает новую ревизию. Обновите данные перед повтором; ввод сохранён.');
      setRevision(result.revision);setConfirmed(false);setRefundConfirmed(false);setCorrectionConfirmed(false);setHistoryConfirmed(false);setOldRefundConfirmed(false);
      setNotice(historyReview?'Прежние возвраты сверены. Новая денежная запись не создана.':historyRefund?'Возврат старого удержания записан отдельным платежом; история актов и зарплаты сохранена.':correction?'Сверка исправлена. Прежние данные сохранены в истории; выплаты не изменились.':refund?'Возврат денег записан отдельной операцией.':'Распределение сохранено. Денежная выплата не создана.');
      await refresh();
    }catch(e){if(isCurrent())setError(e.message);}finally{flight.current=false;if(active.current)setBusy(false);}
  };
  return <fieldset disabled={busy} style={{border:'1px solid '+C.border,padding:12,marginBottom:8}}>
    <legend>Проверенная выдача №{row.id} · {row.tool_name} · {row.staff_name}</legend>
    <p>{row.project_name} · Стоимость {money(row.amount)} · Ранее удержано {money(row.previously_deducted)} · Распределено {money(used)} · Осталось {money(Number(row.amount)-Number(row.previously_deducted)-used)}</p>
    {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
    {stale&&<p role="alert">Серверная версия изменилась. Введённые суммы сохранены; автоматического повтора нет.</p>}
    {row.allocations.map(a=><p key={a.id}>Распределение №{a.id} · {a.act_id?`акт №${a.act_id}`:`зарплата ${a.month}`} · {money(a.amount)} · возвращено {money(a.refunded)}</p>)}
    <label>Куда удержать <select aria-label={`Назначение ${row.id}`} value={target} onChange={e=>setTarget(e.target.value)} style={inp}><option value="act">Акт исполнителя</option><option value="salary">Месяц зарплаты</option></select></label>
    {target==='act'?<select aria-label={`Акт удержания ${row.id}`} style={inp} value={actId} onChange={e=>setActId(e.target.value)}><option value="">Выберите акт</option>{eligible.map(a=><option key={a.id} value={a.id}>№{a.id} · {a.workPackage} · {a.periodStart} — {a.periodEnd}</option>)}</select>:<input aria-label={`Месяц удержания ${row.id}`} style={inp} type="month" value={month} onChange={e=>setMonth(e.target.value)}/>}
    <label>Полная сумма распределения <input aria-label={`Сумма удержания ${row.id}`} style={inp} type="number" min="0" step="0.01" value={amount} onChange={e=>setAmount(e.target.value)}/></label>
    <label>Основание <input aria-label={`Основание распределения ${row.id}`} style={inp} maxLength={2000} value={basis} onChange={e=>setBasis(e.target.value)}/></label>
    <label><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>Подтверждаю распределение по выбранному акту или месяцу</label>
    <button style={btnB} disabled={stale||!numeric(amount)||!basis.trim()||!confirmed||(target==='act'?!actId:!month)} onClick={()=>change(false)}>Сохранить распределение</button>
    <p>Указывается полная сумма этой выдачи в выбранном акте или месяце. Ноль отменяет неоплаченное распределение. После оплаты используйте отдельный возврат.</p>
    <details><summary>Записать фактический возврат удержанных денег</summary>
      <select aria-label={`Возврат распределения ${row.id}`} style={inp} value={refundId} onChange={e=>setRefundId(e.target.value)}><option value="">Выберите распределение</option>{row.allocations.filter(a=>Number(a.amount)>Number(a.refunded)).map(a=><option key={a.id} value={a.id}>№{a.id} · {a.act_id?`акт ${a.act_id}`:a.month} · можно вернуть {money(Number(a.amount)-Number(a.refunded))}</option>)}</select>
      <input aria-label={`Сумма возврата ${row.id}`} style={inp} type="number" min="0.01" step="0.01" value={refundAmount} onChange={e=>setRefundAmount(e.target.value)}/>
      <input aria-label={`Основание возврата ${row.id}`} style={inp} maxLength={2000} value={refundBasis} onChange={e=>setRefundBasis(e.target.value)}/>
      <label><input type="checkbox" checked={refundConfirmed} onChange={e=>setRefundConfirmed(e.target.checked)}/>Подтверждаю основание и фактический возврат денег сотруднику</label>
      <button style={btnB} disabled={stale||!refundId||!numeric(refundAmount)||Number(refundAmount)<=0||!refundBasis.trim()||!refundConfirmed} onClick={()=>change(true)}>Записать возврат денег</button>
      <p>Создаёт денежную запись по объекту, но не банковский перевод. Возврат инструмента на склад сам по себе деньги не возвращает.</p>
    </details>
    {Number(row.previously_deducted)>0&&<details><summary>Возврат старых удержаний</summary>
      <p>Сотрудник №{row.staff_id} · {row.staff_name} · {row.project_name}. Старое удержание: {money(row.previously_deducted)}. Сначала сверьте все прежние возвраты по документам. Сверка не создаёт повторного расхода.</p>
      {!history?<p role="alert">Сервер не подтвердил состояние старых возвратов. Обновите данные; запись недоступна.</p>:!history.reviewed?<>
        <label>Ранее возвращено вне реестра <input aria-label={`Ранее возвращено вне реестра ${row.id}`} style={inp} type="number" min="0" max={row.previously_deducted} step="0.01" value={previousRefund} onChange={e=>{setPreviousRefund(e.target.value);setHistoryConfirmed(false);}}/></label>
        <label>Основание сверки <input aria-label={`Основание сверки возвратов ${row.id}`} style={inp} maxLength={2000} value={historyBasis} onChange={e=>{setHistoryBasis(e.target.value);setHistoryConfirmed(false);}}/></label>
        <label><input type="checkbox" checked={historyConfirmed} onChange={e=>setHistoryConfirmed(e.target.checked)}/>Прежние возвраты проверены по документам, включая отсутствие возвратов</label>
        <button style={btnB} disabled={stale||!numeric(previousRefund)||Number(previousRefund)>Number(row.previously_deducted)||!historyBasis.trim()||!historyConfirmed} onClick={()=>change('history-review')}>Подтвердить прежние возвраты</button>
        <p>Если возвратов не было, введите 0. Сверка записывается один раз и не переписывается; проверьте сумму до подтверждения.</p>
      </>:<>
        <p>Ранее возвращено вне реестра: {money(history.previouslyRefunded)} · Возвращено через реестр: {money(history.refunded)} · Доступно к возврату старых удержаний: {money(history.remaining)}</p>
        <label>Сумма фактического возврата <input aria-label={`Возврат старого удержания ${row.id}`} style={inp} type="number" min="0.01" max={history.remaining} step="0.01" value={oldRefundAmount} onChange={e=>{setOldRefundAmount(e.target.value);setOldRefundConfirmed(false);}}/></label>
        <label>Основание возврата <input aria-label={`Основание старого возврата ${row.id}`} style={inp} maxLength={2000} value={oldRefundBasis} onChange={e=>{setOldRefundBasis(e.target.value);setOldRefundConfirmed(false);}}/></label>
        <label><input type="checkbox" checked={oldRefundConfirmed} onChange={e=>setOldRefundConfirmed(e.target.checked)}/>Подтверждаю фактический возврат старого удержания этому сотруднику</label>
        <button style={btnB} disabled={stale||!numeric(oldRefundAmount)||Number(oldRefundAmount)<=0||Number(oldRefundAmount)>Number(history.remaining)||!oldRefundBasis.trim()||!oldRefundConfirmed} onClick={()=>change('history-refund')}>Записать возврат старого удержания</button>
        <p>Создаёт отдельный расход по объекту, но не банковский перевод. Старые акты и зарплата не меняются; возвращённая сумма не доступна для нового удержания.</p>
      </>}
    </details>}
    <details><summary>Исправить первоначальную сверку</summary>
      {canCorrect?<>
        <p>Сейчас: {row.staff_name} · сотрудник №{row.staff_id} · {money(row.amount)}. Исправление меняет только получателя и стоимость; исходная выдача, объект и история сохраняются.</p>
        <label>Исправленный получатель <select aria-label={`Исправленный получатель ${row.id}`} style={inp} value={correctedStaff} onChange={e=>{setCorrectedStaff(e.target.value);setCorrectionConfirmed(false);}}>
          <option value="">Выберите точного сотрудника</option>{staff.map(s=><option key={s.id} value={s.id}>{s.name} · №{s.id}</option>)}
        </select></label>
        <label>Исправленная стоимость <input aria-label={`Исправленная стоимость ${row.id}`} style={inp} type="number" min="0.01" step="0.01" value={correctedAmount} onChange={e=>{setCorrectedAmount(e.target.value);setCorrectionConfirmed(false);}}/></label>
        <label>Причина исправления <input aria-label={`Причина исправления ${row.id}`} style={inp} maxLength={2000} value={correctionBasis} onChange={e=>{setCorrectionBasis(e.target.value);setCorrectionConfirmed(false);}}/></label>
        <label><input type="checkbox" checked={correctionConfirmed} onChange={e=>setCorrectionConfirmed(e.target.checked)}/>Подтверждаю исправленные данные по документам</label>
        <button style={btnB} disabled={stale||!correctedStaff||!numeric(correctedAmount)||Number(correctedAmount)<=0||!correctionBasis.trim()||!correctionConfirmed||(Number(correctedStaff)===row.staff_id&&Number(correctedAmount)===Number(row.amount))} onClick={()=>change('correction')}>Сохранить исправление сверки</button>
      </>:<p>Сверку можно исправить только без прошлых и действующих удержаний. Сначала отмените неоплаченные распределения. При оплаченных удержаниях нужна отдельная финансовая корректировка.</p>}
    </details>
    <button style={btnG} onClick={refresh}>Обновить распределение</button>
    {stale&&<button style={btnG} onClick={()=>{setRevision(row.revision);setConfirmed(false);setRefundConfirmed(false);setCorrectionConfirmed(false);setHistoryConfirmed(false);setOldRefundConfirmed(false);setError('');}}>Сверено: использовать новую версию</button>}
    <details><summary>История решений</summary>{row.events.map(e=><p key={e.revision}>Версия {e.revision} · {e.actor} · {({review:'Первоначальная сверка',allocate:'Распределение',refund:'Возврат денег',correct_review:'Исправление сверки',historical_refund_review:'Сверка прежних возвратов',historical_refund:'Возврат старого удержания'})[e.change.operation]||e.change.operation} · {e.change.basis}{e.change.operation==='correct_review'&&e.change.before&&e.change.after&&<span> · Получатель №{e.change.before.staffId} → №{e.change.after.staffId}; стоимость {money(e.change.before.amount)} → {money(e.change.after.amount)}</span>}{e.change.operation==='historical_refund_review'&&<span> · Ранее возвращено {money(e.change.previouslyRefunded)}</span>}{e.change.operation==='historical_refund'&&<span> · {money(e.change.amount)} · Платёж №{e.change.projectPaymentId}</span>}</p>)}</details>
  </fieldset>;
}

export default function ToolDeductionPanel({companyContext={},acts=[],refreshData,C={},inp,btnB,btnG}) {
  const company=companyContext.mode==='company'?Number(companyContext.selectedCompanyId):0;
  const [open,setOpen]=useState(false),[data,setData]=useState(null),[error,setError]=useState(''),[loading,setLoading]=useState(false);
  const generation=useRef({value:0});
  useEffect(()=>{const counter=generation.current;counter.value++;setData(null);setError('');setLoading(false);return()=>{counter.value++;};},[company]);
  const load=async()=>{
    if(!company)return;
    const requestId=++generation.current.value;setLoading(true);setError('');
    try{
      const result=await request('/tool-deductions',{headers:headers(company)});
      if(requestId!==generation.current.value)return;
      if(result.companyId!==company||!Array.isArray(result.sources)||!Array.isArray(result.reviewed))throw Error('Ответ не относится к выбранной компании');
      setData(result); return true;
    }catch(e){if(requestId===generation.current.value)setError(e.message);}
    finally{if(requestId===generation.current.value)setLoading(false);}
  };
  const refresh=async()=>{if(await load())await refreshData?.();};
  return <details open={open} onToggle={e=>{const next=e.currentTarget.open;setOpen(next);if(next&&!data&&!loading)load();}} style={{marginBottom:16}}>
    <summary>Инструмент в счёт оплаты · сверка и распределение</summary>
    <p>Бухгалтер проверяет конкретную выдачу и прошлые удержания, затем вручную задаёт суммы по актам или месяцам. Стоимость карточки и совпадение ФИО не являются удержанием. Штрафы за поломку/утерю ведутся отдельно.</p>
    {!company&&<p>Выберите одну компанию для финансовой сверки.</p>}
    {error&&<p role="alert">{error}</p>}{loading&&<p>Загрузка распределений…</p>}
    {company>0&&<button style={btnG} onClick={load}>Обновить выдачи инструмента</button>}
    {data&&data.companyId===company&&<div key={company}>
      {!data.sources.length&&!data.reviewed.length&&<p>Выдач для сверки и распределения нет.</p>}
      {data.sources.map(s=><ReviewSource key={s.sourceKey} source={s} data={data} refresh={refresh} C={C} inp={inp} btnB={btnB}/>)}
      {data.reviewed.map(row=><AllocationRow key={row.id} row={row} acts={acts} staff={data.staff} refresh={refresh} C={C} inp={inp} btnB={btnB} btnG={btnG}/>)}
    </div>}
  </details>;
}
