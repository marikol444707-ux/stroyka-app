import React from 'react';
import {fireEvent,render,screen,waitFor} from '@testing-library/react';
import SupplierCabinetPage from './SupplierCabinetPage';
function Cabinet({send, paymentTerms='Постоплата', paidAmount=0, invoiceStatus='На утверждении'}) {
 const [shippingOfferId,setShippingOfferId]=React.useState(null);
 const [shipmentForm,setShipmentForm]=React.useState({});
 return <SupplierCabinetPage API="/api" C={{}} badge={()=>({})} user={{id:7,role:'поставщик'}} supplierTab="requests" suppliers={[]} supplierRequisites={{}}
  supplierOffers={[{id:70,requestId:879,companyId:1,supplierId:158,status:'Утверждено',paymentTerms,totalPrice:526000}]}
  supplyRequests={[{id:879,companyId:1,companyName:'ООО Заказчик',materialName:'Кабель',quantity:2,unit:'м',workPackage:'Основная',project:'Тест',deliveryAddress:'Кисловодск, ул. Школьная, 4',contactName:'Иван'}]}
  supplyDeliveries={[{id:16,offerId:70,requestId:879,companyId:1,supplierId:158,materialName:'Кабель',unit:'м',workPackage:'Основная',shippedQuantity:1,receivedQuantity:1,status:'Принято'}]}
  supplierInvoices={[{id:144,offerId:70,requestId:879,companyId:1,supplierId:158,status:invoiceStatus,amount:263000,paidAmount}]}
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
 expect(screen.getAllByText(/Кисловодск, ул. Школьная, 4/)).toHaveLength(2);
 expect(screen.getByText(/ООО Заказчик · Тест/)).toBeInTheDocument();
 expect(screen.getByLabelText('Отгрузить: Кабель')).toHaveValue(1);
 const submit=screen.getByRole('button',{name:'Отгрузить'});
 fireEvent.click(submit);fireEvent.click(submit);
 expect(send).toHaveBeenCalledTimes(1);
 resolve(true);
 await waitFor(()=>expect(screen.getByRole('button',{name:'Отгрузить'})).not.toBeDisabled());
 window.history.replaceState({},'', '/app');
});
it('allows shipment before a bank payment when the supplier grants deferral',()=>{
 window.history.replaceState({},'', '/app?supplyRequestId=879');
 render(<Cabinet send={jest.fn()} paymentTerms="Предоплата 100%" invoiceStatus="Утверждён" paidAmount={0}/>);
 expect(screen.queryByText(/дождитесь фактической оплаты счёта/)).not.toBeInTheDocument();
 const ship=screen.getByRole('button',{name:'🚚 Отгрузить остаток'});
 expect(ship).not.toBeDisabled();
 fireEvent.click(ship);
 expect(screen.getByLabelText('Отгрузить: Кабель')).toHaveValue(1);
 window.history.replaceState({},'', '/app');
});
