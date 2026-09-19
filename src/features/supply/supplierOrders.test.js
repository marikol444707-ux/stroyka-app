import { supplierOrders } from './supplierOrderProjection';
const request={id:1,companyId:2,items:[{materialName:'Кабель',unit:'м',quantity:10},{materialName:'Крепёж',unit:'шт',quantity:5}]};
const offer={id:4,requestId:1,companyId:2,supplierId:3,status:'Утверждено'};
const delivery={id:7,offerId:4,requestId:1,companyId:2,supplierId:3,materialName:'Кабель',unit:'м',shippedQuantity:6,receivedQuantity:4,status:'Принято'};
it('keeps partial orders open and separates each material quantity',()=>{
 const [order]=supplierOrders([request],[offer],[delivery],[]);
 expect(order.status).toBe('Частично принято');
 expect(order.lines[0]).toMatchObject({ordered:10,shipped:6,received:4,toShip:4,toReceive:6,inTransit:0});
 expect(order.lines[1]).toMatchObject({ordered:5,shipped:0,received:0,toShip:5,toReceive:5});
});
it('excludes unselected offers and foreign invoice/delivery identities',()=>{
 expect(supplierOrders([request],[{...offer,status:'Отозвано'}],[],[])).toEqual([]);
 const [order]=supplierOrders([request],[offer],[{...delivery,companyId:9}],[{id:8,offerId:4,companyId:9}]);
 expect(order.status).toBe('Требует сверки');expect(order.documents).toEqual([]);
});
it('does not confuse units or call shipped goods received',()=>{
 const [order]=supplierOrders([request],[offer],[{...delivery,status:'Отгружено',receivedQuantity:0}],[]);
 expect(order.lines[0].inTransit).toBe(6);expect(order.lines[0].toReceive).toBe(10);
 const [bad]=supplierOrders([request],[offer],[{...delivery,unit:'шт'}],[]);
 expect(bad.status).toBe('Требует сверки');
});
it('closes only fully accepted lines and flags unknown shipment states',()=>{
 const shipments=[{...delivery,shippedQuantity:10,receivedQuantity:10},{...delivery,id:8,materialName:'Крепёж',unit:'шт',shippedQuantity:5,receivedQuantity:5}];
 expect(supplierOrders([request],[offer],shipments,[])[0].status).toBe('Принято полностью');
 expect(supplierOrders([request],[offer],shipments.map(d=>({...d,status:'Отменено'})),[])[0].status).toBe('Требует сверки');
});
it('marks malformed historic lines for review instead of crashing or showing completion',()=>{
 const [order]=supplierOrders([{...request,items:[null,{materialName:'Неизвестно',quantity:null}]}],[offer],[],[]);
 expect(order.status).toBe('Требует сверки');expect(order.lines).toEqual([]);
});
