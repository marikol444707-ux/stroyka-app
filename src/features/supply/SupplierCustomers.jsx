import React from 'react';
import useSupplierInbox from './useSupplierInbox';
import { supplierCustomers } from './supplierCustomerProjection';
import { SupplierOrderCards, supplierDocumentUrl } from './SupplierOrders';

export default function SupplierCustomers({API,user,C,onOpen,fileSrc,teamContext}) {
 const inbox=useSupplierInbox(API,user,true);
 const [selected,setSelected]=React.useState('');
 const customers=React.useMemo(()=>{
  const history=supplierCustomers(inbox.requests,inbox.offers,inbox.deliveries,inbox.invoices);
  const extra=(teamContext?.customers||[]).filter(c=>!history.some(h=>String(h.id)===String(c.id)));
  return [...history,...extra.map(c=>({...c,id:String(c.id),requests:[],orders:[],invoices:[],deliveries:[]}))];
 },[inbox.requests,inbox.offers,inbox.deliveries,inbox.invoices,teamContext?.customers]);
 const customer=customers.find(row=>row.id===selected);
 return <section className="supplier-customers supplier-orders" aria-label="Заказчики поставщика" style={{color:C.text}}>
  <h2>Заказчики</h2><p>Компании, от которых вам доступны запросы КП.</p>
  <button type="button" disabled={inbox.status==='loading'} onClick={()=>Promise.allSettled([inbox.reload(),teamContext?.reload?.()])}>Обновить заказчиков</button>
  {inbox.status==='loading' && <p role="status">Загружаем заказчиков и историю…</p>}
  {inbox.status==='error' && <p role="alert">Не удалось загрузить заказчиков: {inbox.error}</p>}
  {inbox.status==='ready' && <>
   <label className="supplier-customer-filter">Заказчик<select aria-label="Выбор заказчика" value={selected} onChange={e=>setSelected(e.target.value)}>
    <option value="">Все заказчики</option>{customers.map(c=><option key={c.id} value={c.id}>{c.name} · №{c.id}</option>)}
    {selected&&!customer&&<option value={selected}>Заказчик недоступен</option>}
   </select></label>
   {!customers.length && <p>Заказчиков пока нет. Они появятся после адресного запроса КП.</p>}
   {!selected && <div className="supplier-customer-list">{customers.map(c=><article className="supplier-order" key={c.id}>
    <h3>{c.name} · №{c.id}</h3><p>Заявки: {c.requests.length} · Заказы: {c.orders.length} · Счета: {c.invoices.length} · Поставки: {c.deliveries.length}</p>
    <button type="button" onClick={()=>setSelected(c.id)}>Открыть заказчика №{c.id}</button>
   </article>)}</div>}
   {selected&&!customer&&<p role="status">Заказчик больше не входит в доступный вам список.</p>}
   {customer && <div className="supplier-customer-history">
    <h3>{customer.name} · №{customer.id}</h3>
    <h4>Заявки ({customer.requests.length})</h4>
    {customer.requests.map(r=><article className="supplier-order" key={r.id}><strong>Заявка №{r.id} · {r.material}</strong><p>{r.project} · {r.statusLabel}</p><button type="button" onClick={()=>onOpen(r.id)}>Открыть заявку №{r.id}</button></article>)}
    <h4>Подтверждённые заказы ({customer.orders.length})</h4>
    <SupplierOrderCards orders={customer.orders} onOpen={onOpen} fileSrc={fileSrc}/>
    {!customer.orders.length&&<p>Подтверждённых заказов пока нет.</p>}
    <h4>Счета и документы поставок</h4>
    {!customer.invoices.length&&!customer.deliveries.length&&<p>Документов и поставок пока нет.</p>}
    {customer.invoices.map(i=><p key={'i'+i.id}>Счёт №{i.invoiceNumber || i.id} · КП №{i.offerId} · {i.status}{supplierDocumentUrl(i.fileUrl || i.photoUrl,fileSrc)&&<> · <a href={supplierDocumentUrl(i.fileUrl || i.photoUrl,fileSrc)} target="_blank" rel="noopener noreferrer">Документ счёта №{i.invoiceNumber || i.id}</a></>}</p>)}
    {customer.deliveries.map(d=><p key={'d'+d.id}>Поставка №{d.id} · КП №{d.offerId} · {d.materialName} · {d.status}{supplierDocumentUrl(d.documentUrl,fileSrc)&&<> · <a href={supplierDocumentUrl(d.documentUrl,fileSrc)} target="_blank" rel="noopener noreferrer">Накладная №{d.waybillNumber || d.id}</a></>}</p>)}
   </div>}
  </>}
 </section>;
}
