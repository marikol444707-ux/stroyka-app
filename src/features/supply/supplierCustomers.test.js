import { supplierCustomers } from './supplierCustomerProjection';
const requests=[{id:1,companyId:2,companyName:'Одинаково'},{id:2,companyId:3,companyName:'Одинаково'}];
const offers=[{id:11,requestId:1,companyId:2,supplierId:7,status:'Утверждено'},{id:12,requestId:2,companyId:3,supplierId:7,status:'Получено'}];
it('separates same-name customers and does not mix invoice identities',()=>{
 const invoices=[{id:21,offerId:11,requestId:1,companyId:2,supplierId:7},{id:22,offerId:12,requestId:2,companyId:3,supplierId:7},{id:23,offerId:11,requestId:1,companyId:3,supplierId:7},{id:24,offerId:11,requestId:2,companyId:2,supplierId:7}];
 const rows=supplierCustomers(requests,offers,[],invoices);
 expect(rows.map(r=>r.id)).toEqual(['2','3']);
 expect(rows[0].requests.map(r=>r.id)).toEqual([1]);
 expect(rows[0].orders.map(r=>r.id)).toEqual([11]);
 expect(rows[0].invoices.map(r=>r.id)).toEqual([21]);
 expect(rows[1].invoices.map(r=>r.id)).toEqual([22]);
});
it('removes customers without live request/offer pairing and ignores foreign supplier links',()=>{
 expect(supplierCustomers([],offers,[],[])).toEqual([]);
 expect(supplierCustomers(requests,[],[],[])).toEqual([]);
 const rows=supplierCustomers(requests,offers,[{id:1,offerId:11,requestId:1,companyId:2,supplierId:99}],[]);
 expect(rows[0].deliveries).toEqual([]);
});
