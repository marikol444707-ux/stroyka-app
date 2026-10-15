import './ConnectionRequests.css';

export const connectionStates={pending:'Ожидает ответа',accepted:'Подключено',declined:'Поставщик отказался',revoked:'Запрос отозван'};
export const connectionDate=value=>new Date(value).toLocaleString('ru-RU');

export default function ConnectionRequestList({state,children}) {
  return <>
    {state.status==='loading'&&<p role="status">Загружаю запросы…</p>}
    {state.loadError&&<p role="alert">{state.loadError}</p>}
    {state.error&&<p role="alert">{state.error}</p>}
    {state.notice&&<p role="status">{state.notice}</p>}
    <div className="connection-requests__actions"><button type="button" disabled={state.busy||state.status==='loading'} onClick={state.reload}>Обновить запросы</button></div>
    {state.status==='ready'&&children}
    {state.status==='ready'&&(state.offset>0||state.hasMore)&&<nav className="connection-requests__actions" aria-label="Страницы запросов">
      <button type="button" disabled={state.busy||state.offset===0} onClick={()=>state.setOffset(n=>Math.max(0,n-25))}>Назад</button>
      <button type="button" disabled={state.busy||!state.hasMore} onClick={()=>state.setOffset(n=>n+25)}>Далее</button>
    </nav>}
  </>;
}
