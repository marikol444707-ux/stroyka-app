import { registryRows } from './supplierRegistryQuery';
import { supplierOrders } from './supplierOrderProjection';
const same=(a,b)=>a!=null && b!=null && String(a)===String(b);
export function supplierCustomers(requests,offers,deliveries,invoices) {
 const coherent=offers.filter(o=>requests.some(r=>same(r.id,o.requestId)&&same(r.companyId,o.companyId)));
 const rows=registryRows(requests,coherent);
 const groups=new Map();
 for(const row of rows){
  if(!row.company)continue;
  if(!groups.has(row.company))groups.set(row.company,{id:row.company,name:row.companyName,requests:[]});
  groups.get(row.company).requests.push(row);
 }
 return [...groups.values()].map(customer=>{
  const ids=new Set(customer.requests.map(r=>String(r.id)));
  const quotes=coherent.filter(o=>same(o.companyId,customer.id)&&ids.has(String(o.requestId)));
  const linked=row=>same(row.companyId,customer.id)&&quotes.some(o=>same(row.offerId,o.id)&&(!row.requestId||same(row.requestId,o.requestId))&&(!row.supplierId||same(row.supplierId,o.supplierId)));
  const ownDeliveries=deliveries.filter(linked),ownInvoices=invoices.filter(linked);
  return {...customer,orders:supplierOrders(requests.filter(r=>ids.has(String(r.id))),quotes,deliveries,invoices),deliveries:ownDeliveries,invoices:ownInvoices};
 });
}
