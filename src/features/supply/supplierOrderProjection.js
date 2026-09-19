const list=value=>{if(Array.isArray(value))return value;try{const rows=JSON.parse(value);return Array.isArray(rows)?rows:[];}catch{return [];}};
const key=row=>JSON.stringify([row.materialName || row.name || '',row.unit || '',row.workPackage || row.work_package || 'Основная'].map(v=>String(v).trim().toLowerCase()));
const quantity=value=>{if(value===null || value===undefined || value==='')return null;const n=Number(value);return Number.isFinite(n)&&n>=0?n:null;};
const same=(a,b)=>a!==undefined && a!==null && b!==undefined && b!==null && String(a)===String(b);
const linked=(row,offer,request)=>same(row.offerId,offer.id) && same(row.companyId,request.companyId) && (!row.requestId || same(row.requestId,request.id)) && (!row.supplierId || same(row.supplierId,offer.supplierId));
const clean=n=>Math.round(n*1000000)/1000000;
export function supplierOrders(requests,offers,deliveries,invoices) {
 return offers.filter(offer=>offer.status==='Утверждено').flatMap(offer=>{
  const request=requests.find(r=>same(r.id,offer.requestId)&&same(r.companyId,offer.companyId));
  if(!request)return [];
  const candidates=deliveries.filter(d=>same(d.offerId,offer.id));
  const shipments=candidates.filter(d=>linked(d,offer,request));
  let review=candidates.length!==shipments.length;
  let items=list(request.itemsJson || request.items);
  if(!items.length)items=[request];
  const grouped=new Map();
  for(const item of items){
   if(!item || typeof item!=='object'){review=true;continue;}
   const row={...item,unit:item.unit || request.unit || '',workPackage:item.workPackage || request.workPackage || ''};
   const q=quantity(item.quantity);
   if(q===null || q===0 || !(row.materialName || row.name)){review=true;continue;}
   const id=key(row);const previous=grouped.get(id);
   grouped.set(id,{...row,ordered:clean((previous?.ordered || 0)+q)});
  }
  const lines=[...grouped].map(([id,item])=>{
   const matching=shipments.filter(d=>key(d)===id);
   let shipped=0,received=0,inTransit=0;
   for(const d of matching){
    if(!['Отгружено','В пути','Доставлено','Принято','Проблема','Принято с замечаниями'].includes(d.status))review=true;
    const s=quantity(d.shippedQuantity),r=quantity(d.receivedQuantity ?? 0);
    if(s===null || r===null || r>s){review=true;continue;}
    if(r>0 && !d.receivedAt && !['Принято','Проблема','Принято с замечаниями'].includes(d.status))review=true;
    shipped+=s;received+=r;
    if(!['Принято','Проблема','Принято с замечаниями'].includes(d.status) && !d.receivedAt)inTransit+=Math.max(0,s-r);
    if(['Проблема','Принято с замечаниями'].includes(d.status))review=true;
   }
   if(received>item.ordered+0.000001 || shipped>item.ordered+0.000001)review=true;
   return {...item,materialName:item.materialName || item.name,shipped:clean(shipped),received:clean(received),inTransit:clean(inTransit),toShip:clean(Math.max(0,item.ordered-shipped)),toReceive:clean(Math.max(0,item.ordered-received))};
  });
  if(!lines.length || shipments.some(d=>!grouped.has(key(d))))review=true;
  const complete=lines.length>0 && lines.every(l=>l.toReceive<=0.000001);
  const status=review?'Требует сверки':complete?'Принято полностью':lines.some(l=>l.received>0)?'Частично принято':lines.some(l=>l.shipped>0)?'В поставке':'Ожидает отгрузки';
  return [{id:offer.id,request,offer,lines,shipments,documents:invoices.filter(i=>linked(i,offer,request)),status,review}];
 });
}
