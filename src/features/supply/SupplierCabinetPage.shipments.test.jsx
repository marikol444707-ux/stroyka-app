import React from 'react';
import {fireEvent,render,screen,waitFor} from '@testing-library/react';
import SupplierCabinetPage from './SupplierCabinetPage';
function Cabinet({send}) {
 const [shippingOfferId,setShippingOfferId]=React.useState(null);
 const [shipmentForm,setShipmentForm]=React.useState({});
 return <SupplierCabinetPage API="/api" C={{}} badge={()=>({})} user={{id:7,role:'поставщик'}} supplierTab="requests" suppliers={[]} supplierRequisites={{}}
  supplierOffers={[{id:70,requestId:879,companyId:1,supplierId:158,status:'Утверждено',paymentTerms:'Постоплата'}]}
  supplyRequests={[{id:879,companyId:1,materialName:'Кабель',quantity:2,unit:'м',workPackage:'Основная',project:'Тест'}]}
  supplyDeliveries={[{id:16,offerId:70,requestId:879,companyId:1,supplierId:158,materialName:'Кабель',unit:'м',workPackage:'Основная',shippedQuantity:1,receivedQuantity:1,status:'Принято'}]}
  supplierInvoices={[{id:144,offerId:70,requestId:879,companyId:1,supplierId:158,status:'На утверждении'}]}
  parseSupplyItems={r=>[r]} shippingOfferId={shippingOfferId} setShippingOfferId={setShippingOfferId} shipmentForm={shipmentForm} setShipmentForm={setShipmentForm}
  createShipmentFromOffer={send} />;
}
it('offers remaining quantity on the same KP and prevents a double click',async()=>{
 window.history.replaceState({},'', '/app?supplyRequestId=879');
 Object.defineProperty(window,'crypto',{configurable:true,value:{randomUUID:()=> '12345678-1234-4234-8234-123456789012'}});
 let resolve;const send=jest.fn(()=>new Promise(r=>{resolve=r;}));
 render(<Cabinet send={send}/>);
 expect(screen.queryByRole('button',{name:/Выставить счёт/})).not.toBeInTheDocument();
 fireEvent.click(screen.getByRole('button',{name:/Отгрузить остаток/}));
 expect(screen.getByLabelText('Отгрузить: Кабель')).toHaveValue(1);
 const submit=screen.getByRole('button',{name:'Отгрузить'});
 fireEvent.click(submit);fireEvent.click(submit);
 expect(send).toHaveBeenCalledTimes(1);
 resolve(true);
 await waitFor(()=>expect(screen.getByRole('button',{name:'Отгрузить'})).not.toBeDisabled());
 window.history.replaceState({},'', '/app');
});
