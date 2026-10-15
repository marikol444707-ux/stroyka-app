import {useEffect,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
import useAsyncSubmit from '../../hooks/useAsyncSubmit';
import '../participant-support/ConnectionRequests.css';

const labels={invoices:'Счета',offers:'Предложения',files:'Файлы',deliveries:'Отгрузки',claims:'Претензии'};
const recordLabels={supplier_invoices:'Счета старой карточки',warehouse_invoices:'Накладные',supplier_offers:'Предложения старой карточки',
  supplier_contract_registry:'Договоры',supply_deliveries:'Отгрузки',supply_claims:'Претензии',
  company_supplier_links:'Карточка в каталоге',supplier_aliases:'Названия поставщика'};

export default function SupplierHistoryMergeDialog({prefix,sourceId,targetId,sourceName,targetName,onClose,onDone}) {
  const [plan,setPlan]=useState(null);
  const [checked,setChecked]=useState(false);
  const [reason,setReason]=useState('');
  const [done,setDone]=useState(false);
  const dialog=useRef(null),active=useRef(true);
  const path=prefix+'/participants/'+sourceId+'/history-merge-plans';
  const {submit,pending,error}=useAsyncSubmit(async()=>{
    const response=await fetch(path+(plan?'/'+plan.id+'/confirm':''),{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(plan?{confirmed:true,reason:reason.trim()}:{targetSupplierId:targetId})});
    const data=await response.json().catch(()=>({}));
    if(!active.current)return;
    if(!response.ok){if(response.status===409){setPlan(null);setChecked(false);}throw new Error(typeof data.detail==='string'?data.detail:'Не удалось выполнить объединение');}
    if(!plan){
      if(data.sourceId!==sourceId||data.targetId!==targetId||!data.id||!data.newAccess)throw new Error('Результат проверки неполный. Повторите проверку.');
      setPlan(data);return;
    }
    if(!data.ok||data.sourceId!==sourceId||data.targetId!==targetId)throw new Error('Проверьте результат объединения перед повторной отправкой.');
    setDone(true);
  });
  useEffect(()=>{
    active.current=true;
    const previous=document.activeElement,overflow=document.body.style.overflow;
    document.body.style.overflow='hidden';dialog.current?.focus();
    return()=>{active.current=false;document.body.style.overflow=overflow;previous?.focus();};
  },[]);
  return createPortal(<div style={{position:'fixed',inset:0,zIndex:950,background:'rgba(15,23,42,.65)',display:'flex',alignItems:'center',justifyContent:'center',padding:12}}>
    <section ref={dialog} role="dialog" aria-modal="true" aria-labelledby="history-merge-title" tabIndex={-1}
      className="connection-requests" style={{background:'var(--c-card,#fff)',color:'var(--c-text,#172033)',width:520,maxWidth:'100%',maxHeight:'85dvh',overflowY:'auto',boxSizing:'border-box',padding:20,borderRadius:16}}
      onKeyDown={event=>{
        if(event.key==='Escape'&&!pending){if(done)onDone();else onClose();}
        if(event.key==='Tab'){
          const nodes=[...dialog.current.querySelectorAll('button:not(:disabled),input:not(:disabled),textarea:not(:disabled),summary')];
          const first=nodes[0],last=nodes[nodes.length-1];
          if(event.shiftKey&&(document.activeElement===first||document.activeElement===dialog.current)){event.preventDefault();last?.focus();}
          else if(!event.shiftKey&&(document.activeElement===last||document.activeElement===dialog.current)){event.preventDefault();first?.focus();}
        }
      }}>
      <h3 id="history-merge-title">Объединить карточки поставщика</h3>
      <p><strong>{sourceName}</strong> → <strong>{targetName}</strong></p>
      {done?<p role="status">Карточки объединены. Документы и суммы оплат сохранены.</p>:<>
        <p>Старая карточка будет связана с кабинетом поставщика. Назначения сотрудников сохранятся.</p>
        {plan&&<>
          <h4>Что откроется владельцу кабинета</h4>
          <ul>{Object.entries(labels).filter(([key])=>['invoices','offers','files'].includes(key)||plan.newAccess[key]?.length)
            .map(([key,label])=><li key={key}>{label}: <strong>{plan.newAccess[key]?.length||0}</strong></li>)}</ul>
          <p>Документы без подходящего адресата останутся закрытыми. Доступ к файлам зависит также от их сохранности.</p>
          <details><summary>Какие записи затронуты</summary>
            {Object.entries(labels).map(([key,label])=><p key={key}>{label}: {plan.newAccess[key]?.map(id=>'#'+id).join(', ')||'нет новых доступных записей'}</p>)}
            <p>Останутся закрытыми: счета — {plan.stillClosed.invoices.length}, предложения — {plan.stillClosed.offers.length}.</p>
            <h4>Записи, связанные со старой карточкой</h4>
            {Object.entries(plan.affected||{}).filter(([,ids])=>ids.length).map(([key,ids],index)=><p key={key}>
              {recordLabels[key]||'Связанные записи · группа '+(index+1)}: {ids.map(id=>'#'+id).join(', ')}
            </p>)}
          </details>
          <label style={{display:'flex',alignItems:'center',gap:8,minHeight:44,marginTop:12}}><input type="checkbox" checked={checked} disabled={pending} onChange={e=>setChecked(e.target.checked)}/>
            Я проверил, что карточки и старые документы принадлежат этому поставщику</label>
          <label style={{display:'grid',gap:8,marginTop:12}}>Основание объединения
            <textarea rows={3} value={reason} maxLength={1000} disabled={pending} onChange={e=>setReason(e.target.value)} placeholder="Что вы проверили" style={{width:'100%',boxSizing:'border-box',padding:10,font:'inherit',resize:'vertical'}}/>
          </label>
          <p>Проверка действует 15 минут. Если документы изменятся, потребуется новая проверка.</p>
        </>}
      </>}
      {error&&<p role="alert">{error}</p>}
      <div className="connection-requests__actions" style={{marginTop:16}}>
        <button type="button" disabled={pending} onClick={()=>{if(done)onDone();else onClose();}}>Закрыть</button>
        {!done&&<button type="button" disabled={pending||(plan&&(!checked||reason.trim().length<10))} onClick={submit}>
          {pending?'Подождите…':plan?'Подтвердить объединение':'Проверить последствия'}</button>}
      </div>
    </section>
  </div>,document.body);
}
