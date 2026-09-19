import React from 'react';
import { render,screen,fireEvent } from '@testing-library/react';
import SupplierOrders from './SupplierOrders';
const originalFetch=global.fetch;
afterEach(()=>{global.fetch=originalFetch;});
it('renders a partial order, own documents and navigation without closing the remainder',async()=>{
 const open=jest.fn();
 const responses={'/supply-requests':[{id:1,companyId:2,materialName:'Кабель',quantity:10,unit:'м',companyName:'Заказчик'}],'/supplier-offers':[{id:4,requestId:1,companyId:2,supplierId:3,status:'Утверждено'}],'/supply-deliveries':[{id:7,offerId:4,requestId:1,companyId:2,supplierId:3,materialName:'Кабель',unit:'м',shippedQuantity:6,receivedQuantity:4,status:'Принято'}],'/supplier-invoices':[{id:8,offerId:4,companyId:2,fileUrl:'/uploads/invoice.pdf'},{id:9,offerId:99,companyId:2,fileUrl:'/uploads/foreign.pdf'}]};
 global.fetch=jest.fn(async url=>({ok:true,json:async()=>responses[url]}));
 render(<SupplierOrders API="" user={{id:3,role:'поставщик'}} C={{}} onOpen={open}/>);
 expect(await screen.findByText('Частично принято')).toBeInTheDocument();
 expect(screen.getByText(/Допоставка после приёмки/)).toBeInTheDocument();
 expect(screen.getByRole('link',{name:'Файл счёта',hidden:true}).getAttribute('href')).toBe('http://localhost/uploads/invoice.pdf');
 expect(screen.queryByText('Счёт №9')).not.toBeInTheDocument();
 fireEvent.click(screen.getByRole('button',{name:'Открыть заявку и действия'}));expect(open).toHaveBeenCalledWith(1);
});
