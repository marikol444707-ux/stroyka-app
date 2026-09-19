import { supplierOrders } from './supplierOrderProjection';
const moscowParts = date => new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Moscow',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(date).replace(' ','T');
export function defaultResponseDeadline(now=new Date()) {
  const shifted=new Date(moscowParts(now)+':00Z');
  do {shifted.setUTCDate(shifted.getUTCDate()+1);} while([0,6].includes(shifted.getUTCDay()));
  return shifted.toISOString().slice(0,16);
}
export function deadlineState(offer,now=Date.now()) {
  if(offer.status!=='Ожидает ответа') return '';
  const due=Date.parse(offer.responseDueAt);
  if(!Number.isFinite(due)) return 'undated';
  if(due<=now) return 'overdue';
  return moscowParts(new Date(due)).slice(0,10)===moscowParts(new Date(now)).slice(0,10)?'today':'later';
}
export function responseDeadlineLabel(value) {
  if(!value || !Number.isFinite(Date.parse(value))) return 'Без срока';
  return new Date(value).toLocaleString('ru-RU',{timeZone:'Europe/Moscow',dateStyle:'short',timeStyle:'short'})+' МСК';
}
export function canPrepareOffer(offer,invoices=[],deliveries=[],request=null) {
  if(offer.status!=='Утверждено') return false;
  if(request) {
    const order=supplierOrders([request],[offer],deliveries,invoices)[0];
    if(!order || order.review || !order.lines.some(line=>line.toShip>0)) return false;
  } else if(deliveries.some(d=>String(d.offerId ?? d.offer_id)===String(offer.id))) return false;
  const terms=String(offer.paymentTerms || '').toLowerCase();
  const needPay=terms.includes('предоплат') || terms.includes('50/50') || (terms.includes('50') && !terms.includes('постоплат'));
  if(!needPay) return true;
  const invoice=invoices.filter(i=>String(i.offerId ?? i.offer_id)===String(offer.id)).sort((a,b)=>Number(b.id)-Number(a.id))[0];
  if(!invoice) return false;
  const amount=Number(invoice.amount ?? offer.totalPrice),paid=Number(invoice.paidAmount ?? invoice.paid_amount ?? 0);
  if(!Number.isFinite(amount) || amount<=0 || !Number.isFinite(paid)) return false;
  const required=terms.includes('100') || terms.includes('предоплат') ? amount : amount*.5;
  return paid+.01>=required;
}
export function requestAttention(quotes,invoices,deliveries,now,request=null) {
  const states=new Set(quotes.map(q=>deadlineState(q,now)).filter(Boolean));
  if(quotes.some(q=>q.status==='Получено')) states.add('customer');
  if(quotes.some(q=>canPrepareOffer(q,invoices,deliveries,request))) states.add('ready');
  return [...states];
}
export const attentionLabels={today:'Ответить сегодня',overdue:'Просрочено',customer:'Ждём заказчика',ready:'Можно готовить к поставке',undated:'Без срока'};
