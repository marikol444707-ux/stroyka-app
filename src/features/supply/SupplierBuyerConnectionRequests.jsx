import useConnectionRequests from '../participant-support/useConnectionRequests';
import ConnectionRequestList,{connectionDate} from '../participant-support/ConnectionRequestList';

export default function SupplierBuyerConnectionRequests({API,user,onChanged}) {
  const path=API+'/supplier/connection-requests';
  const state=useConnectionRequests(path,user?.id+':'+user?.role);
  const decide=(item,action)=>state.send(path+'/'+item.id+'/'+action,{expectedVersion:item.version,confirmed:true},
    action==='accept'?'Компания подключена к вашему кабинету.':'Запрос отклонён.',onChanged);
  return <section className="connection-requests" aria-label="Подключение к покупателям">
    <h3>Подключение к покупателям</h3>
    <p>Подтвердить связь может владелец кабинета. Подключение не меняет ваш аккаунт и не переносит старые документы из других карточек.</p>
    <ConnectionRequestList state={state}>
      {!state.items.length&&<p>Новых запросов нет.</p>}
      <ul className="connection-requests__list">{state.items.map(item=><li key={item.id}>
        <strong>{item.companyName}</strong><p>Кабинет: {item.supplierName} · ИНН {item.inn||'не указан'}</p>
        <p>Ответьте до {connectionDate(item.expiresAt)}. Документы будут доступны по их адресатам и назначениям вашей команды.</p>
        <div className="connection-requests__actions">
          <button type="button" disabled={state.busy} onClick={()=>decide(item,'accept')}>Подключить покупателя</button>
          <button type="button" disabled={state.busy} onClick={()=>decide(item,'decline')}>Отказаться</button>
        </div>
      </li>)}</ul>
    </ConnectionRequestList>
  </section>;
}
