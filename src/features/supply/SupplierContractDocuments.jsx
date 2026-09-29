import React, {useEffect, useState} from 'react';
import './SupplierContractDocuments.css';
import SupplyFileLink from './SupplyFileLink';

export default function SupplierContractDocuments(props) {
  if (process.env.REACT_APP_SUPPLIER_DOCUMENT_CONTRACT_BINDINGS_ENABLED !== 'true') return null;
  return <Documents key={`${props.API}:${props.userId}`} {...props}/>;
}
function Documents({API, fileSrc, C}) {
  const [state, setState] = useState({loading:true});
  const [pages, setPages] = useState([null]);
  const [revision, setRevision] = useState(0);
  const before = pages[pages.length-1];
  useEffect(() => {
    const controller = new AbortController();
    setState({loading:true});
    fetch(`${API}/supplier-documents/contracts${before ? `?before=${before}` : ''}`, {
      credentials:'include', cache:'no-store', signal:controller.signal,
    }).then(async response => {
      const data = await response.json();
      if (!response.ok) throw new Error('Не удалось загрузить договоры. Обновите список.');
      if (!Array.isArray(data.items) || data.items.some(item => !Number.isSafeInteger(item.id) || !Number.isSafeInteger(item.companyId))) {
        throw new Error('Не удалось проверить список договоров. Обновите страницу.');
      }
      if (!controller.signal.aborted) setState(data);
    }).catch(error => {if (!controller.signal.aborted) setState({error:error.message});});
    return () => controller.abort();
  }, [API, before, revision]);
  const date = value => /^\d{4}-\d{2}-\d{2}$/.test(value || '') ? value.split('-').reverse().join('.') : value;
  return <section className="supplier-contract-documents" aria-label="Договоры с заказчиками" style={{color:C.text,marginBottom:24,'--contract-border':C.border}}>
    <div style={{display:'flex',justifyContent:'space-between',gap:12,alignItems:'center',flexWrap:'wrap'}}>
      <h3>Договоры с заказчиками</h3>
      <button type="button" onClick={() => {setState({loading:true});setPages([null]);setRevision(value=>value+1);}}>Обновить</button>
    </div>
    {state.loading && <p role="status">Загружаем договоры…</p>}
    {state.error && <p role="alert">{state.error}</p>}
    {state.items?.length===0 && <p>Договоров пока нет. Они появятся после сохранения заказчиком.</p>}
    {state.items?.map(item => <article key={item.id} style={{background:C.bg,border:`1px solid ${C.border}`,borderRadius:12,padding:16,marginBottom:12}}>
      <p style={{color:C.textMuted,marginTop:0}}>{item.customer}</p>
      <h4 style={{margin:'8px 0'}}>Договор № {item.number} от {date(item.date)}</h4>
      <p>Версия {item.version}{item.archived ? ' · В архиве' : ''}</p>
      <SupplyFileLink url={item.fileUrl} fileSrc={fileSrc}>Скачать договор</SupplyFileLink>
      {item.addenda?.map(a => <p key={a.fileUrl}><SupplyFileLink url={a.fileUrl} fileSrc={fileSrc}>Допсоглашение № {a.number} от {date(a.date)}</SupplyFileLink></p>)}
    </article>)}
    {!state.loading && <div style={{display:'flex',gap:12}}>
      {pages.length>1 && <button type="button" onClick={()=>{setState({loading:true});setPages(value=>value.slice(0,-1));}}>Назад</button>}
      {Number.isSafeInteger(state.nextCursor) && <button type="button" onClick={()=>{setState({loading:true});setPages(value=>[...value,state.nextCursor]);}}>Следующие договоры</button>}
    </div>}
  </section>;
}
