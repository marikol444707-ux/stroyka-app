import {useRef,useState} from 'react';
import useConnectionRequests from '../participant-support/useConnectionRequests';
import ConnectionRequestList,{connectionDate,connectionStates} from '../participant-support/ConnectionRequestList';

export default function SupplierConnectionRequests({prefix,supplierId,cabinet,sourceVersion,canRequest}) {
  const path=prefix+'/participants/'+supplierId+'/connection-requests';
  const state=useConnectionRequests(path);
  const [confirmed,setConfirmed]=useState(false);
  const operation=useRef(null);
  const pending=state.items.some(item=>item.status==='pending');
  const create=async()=>{
    if(!operation.current)operation.current=window.crypto.randomUUID();
    const saved=await state.send(path,{requestId:operation.current,targetSupplierId:cabinet.supplierId,
      expectedSourceVersion:sourceVersion,confirmed:true},'Запрос появился в кабинете поставщика: «Заказчики» → «Подключение к покупателям».');
    if(saved){operation.current=null;setConfirmed(false);}
  };
  if(state.status==='ready'&&!canRequest&&!state.items.length)return null;
  return <section className="connection-requests" aria-label="Подключение кабинета к компании">
    <h4>Запрос подключения</h4>
    <p>Старые счета и накладные этой карточки останутся на месте; объединение истории проверяется отдельно.</p>
    <ConnectionRequestList state={state}>
      {state.items.length>0&&<ul className="connection-requests__list">{state.items.map(item=><li key={item.id}>
        <strong>{item.expired&&item.status==='pending'?'Срок запроса истёк':connectionStates[item.status]}</strong>
        <p>{item.supplierName} · срок до {connectionDate(item.expiresAt)}</p>
        {item.status==='pending'&&<button type="button" disabled={state.busy} onClick={()=>state.send(path+'/'+item.id+'/revoke',
          {expectedVersion:item.version,confirmed:true},'Запрос отозван. Связь с покупателем не добавлена.')}>Отозвать запрос</button>}
      </li>)}</ul>}
      {canRequest&&!pending&&<>
        <label><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/><span>Отправить запрос владельцу кабинета «{cabinet.name}» для этой компании</span></label>
        <button type="button" disabled={state.busy||!confirmed} onClick={create}>Запросить подключение</button>
      </>}
      {!state.items.length&&!canRequest&&<p>Запросов на подключение пока нет.</p>}
    </ConnectionRequestList>
  </section>;
}
