import React from 'react';
import useSupplierInbox from './useSupplierInbox';
import { supplierOrders } from './supplierOrderProjection';

function documentUrl(value,fileSrc) {
 if(!value)return null;
 try{const url=new URL(fileSrc ? fileSrc(value) : value,window.location.origin);return ['https:','http:'].includes(url.protocol)?url.href:null;}catch{return null;}
}
export default function SupplierOrders({API,user,C,onOpen,fileSrc}) {
 const inbox=useSupplierInbox(API,user,true);
 const orders=React.useMemo(()=>supplierOrders(inbox.requests,inbox.offers,inbox.deliveries,inbox.invoices),[inbox.requests,inbox.offers,inbox.deliveries,inbox.invoices]);
 return <section className="supplier-orders" aria-label="Подтверждённые заказы" style={{color:C.text}}>
  <h2>Заказы</h2><p>Подтверждённые КП и остаток по каждой позиции.</p>
  <button type="button" onClick={inbox.reload} disabled={inbox.status==='loading'}>Обновить заказы</button>
  {inbox.status==='loading' && <p role="status">Загружаем заказы и поставки…</p>}
  {inbox.status==='error' && <p role="alert">Не удалось загрузить заказы: {inbox.error}</p>}
  {inbox.status==='ready' && !orders.length && <p>Подтверждённых заказов пока нет.</p>}
  {inbox.status==='ready' && orders.map(order=><article className="supplier-order" key={order.id}>
   <div className="supplier-order-heading"><h3>Заказ по КП №{order.id} · заявка №{order.request.id}</h3><strong>{order.status}</strong></div>
   <p>{order.request.companyName || 'Компания №'+order.request.companyId} · {order.request.project || 'Объект не указан'}</p>
   <p>Условия: {order.offer.paymentTerms || 'Не указаны'} · срок поставки: {order.offer.deliveryDays ?? 'Не указан'} дн. · сумма КП: {order.offer.totalPrice ?? 'Не указана'} ₽</p>
   {order.review && <p role="status">Данные поставок требуют сверки. Остаток не подтверждён.</p>}
   <div className="supplier-order-lines">{order.lines.map((line,index)=><div key={index}>
    <h4>{line.materialName} · {line.unit}{line.workPackage?' · '+line.workPackage:''}</h4>
    <dl>{[['Заказано',line.ordered],['Отгружено',line.shipped],['Принято',line.received],['Осталось отгрузить',line.toShip],['В пути',line.inTransit],['Осталось принять',line.toReceive]].map(([label,value])=><div key={label}><dt>{label}</dt><dd>{order.review && ['Осталось отгрузить','В пути','Осталось принять'].includes(label)?'Требует сверки':value}</dd></div>)}</dl>
   </div>)}</div>
   {order.lines.some(l=>l.toReceive>0) && order.shipments.some(d=>d.receivedAt || ['Принято','Проблема','Принято с замечаниями'].includes(d.status)) && <p>Есть непринятый остаток. Допоставка после приёмки оформляется отдельной заявкой/КП.</p>}
   <details><summary>Поставки и документы ({order.shipments.length + order.documents.length})</summary>
    {order.shipments.map(d=><p key={'d'+d.id}>Поставка №{d.id} · {d.materialName} · {d.status}{documentUrl(d.documentUrl,fileSrc) && <> · <a href={documentUrl(d.documentUrl,fileSrc)} target="_blank" rel="noopener noreferrer">Накладная {d.waybillNumber || d.id}</a></>}</p>)}
    {order.documents.map(i=><p key={'i'+i.id}>Счёт №{i.invoiceNumber || i.id} · {i.status}{documentUrl(i.fileUrl,fileSrc) && <> · <a href={documentUrl(i.fileUrl,fileSrc)} target="_blank" rel="noopener noreferrer">Файл счёта</a></>}</p>)}
    {!order.shipments.length && !order.documents.length && <p>Поставок и документов пока нет.</p>}
   </details>
   <button type="button" onClick={()=>onOpen(order.request.id)}>Открыть заявку и действия</button>
  </article>)}
 </section>;
}
