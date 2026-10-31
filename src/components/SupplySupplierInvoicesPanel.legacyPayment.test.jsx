import React from 'react';
import {render,screen,fireEvent,waitFor,act} from '@testing-library/react';
import Panel from './SupplySupplierInvoicesPanel';
import {paymentStorageKey,refreshLegacyPayment} from '../features/supply/legacyInvoicePayment';
import {API} from '../api';
const invoice={id:4,companyId:2,projectName:'Объект',supplierName:'Поставщик',invoiceNumber:'1',amount:100,paidAmount:0,status:'Утверждён'};
const props={C:{},card:{},inp:{},btnO:{},btnG:{},btnGr:{},btnR:{},badge:()=>({}),user:{id:7,name:'Test'},
 suppliers:[],projects:[],supplierInvoices:[invoice],newSupplierInvoice:null,matchSearch:()=>true,expandedProject:'sup-Объект',canPay:true,
 companyContext:{mode:'company',selectedCompanyId:2},loadAll:jest.fn(async()=>{}),toNum:Number};
const key=paymentStorageKey(API,7,2,4);
const pending={requestId:'11111111-1111-4111-8111-111111111111',companyId:2,invoiceId:4,amount:'100.00',expectedPaidAmount:'0.00',paidAt:'2026-10-31'};
const oldFetch=global.fetch,oldFlag=process.env.REACT_APP_SUPPLIER_PAYMENTS_ENABLED;
beforeEach(()=>{localStorage.clear();process.env.REACT_APP_SUPPLIER_PAYMENTS_ENABLED='false';jest.spyOn(window,'alert').mockImplementation(()=>{});props.loadAll.mockReset();props.loadAll.mockImplementation(async options=>options.paymentConfirmation);Object.defineProperty(navigator,'locks',{configurable:true,value:{request:async(_k,_o,fn)=>fn({})}});});
afterEach(()=>{delete navigator.locks;jest.restoreAllMocks();global.fetch=oldFetch;if(oldFlag===undefined)delete process.env.REACT_APP_SUPPLIER_PAYMENTS_ENABLED;else process.env.REACT_APP_SUPPLIER_PAYMENTS_ENABLED=oldFlag;});
it('can recover pending identity even when refreshed invoice is fully paid',async()=>{
 localStorage.setItem(key,JSON.stringify(pending));const prompt=jest.spyOn(window,'prompt');
 global.fetch=jest.fn(async()=>({ok:true,json:async()=>({ok:true,requestId:pending.requestId,invoiceId:4,companyId:2,projectPaymentId:8})}));
 render(<Panel {...props} supplierInvoices={[{...invoice,status:'Оплачен',paidAmount:100}]}/>);
 fireEvent.click(screen.getByText('Проверить сохранённую оплату'));
 await waitFor(()=>expect(props.loadAll).toHaveBeenCalledTimes(1));
 expect(prompt).not.toHaveBeenCalled();expect(global.fetch).toHaveBeenCalledTimes(1);
 await waitFor(()=>expect(localStorage.getItem(key)).toBeNull());
});
it('blocks concurrent clicks and retains pending on network loss',async()=>{
 localStorage.setItem(key,JSON.stringify(pending));let reject;
 global.fetch=jest.fn(()=>new Promise((_,r)=>{reject=r;}));render(<Panel {...props}/>);
 fireEvent.click(screen.getByText('Проверить сохранённую оплату'));fireEvent.click(screen.getByText('Проверить сохранённую оплату'));
 expect(global.fetch).toHaveBeenCalledTimes(1);reject(new Error('lost'));
 await waitFor(()=>expect(window.alert).toHaveBeenCalled());expect(localStorage.getItem(key)).toBe(JSON.stringify(pending));
 expect(props.loadAll).not.toHaveBeenCalled();
});
it('ignores stale company response without clearing saved command',async()=>{
 localStorage.setItem(key,JSON.stringify(pending));let resolve;
 global.fetch=jest.fn(()=>new Promise(r=>{resolve=r;}));const view=render(<Panel {...props}/>);
 fireEvent.click(screen.getByText('Проверить сохранённую оплату'));
 view.rerender(<Panel {...props} companyContext={{mode:'company',selectedCompanyId:3}}/>);
 resolve({ok:true,json:async()=>({ok:true,requestId:pending.requestId,invoiceId:4,companyId:2,projectPaymentId:8})});
 await waitFor(()=>expect(global.fetch).toHaveBeenCalledTimes(1));
 expect(props.loadAll).not.toHaveBeenCalled();expect(localStorage.getItem(key)).not.toBeNull();
});

it('POST success followed by strict GET failure retains UUID and reports refresh error',async()=>{
 localStorage.setItem(key,JSON.stringify(pending));
 const receipt={ok:true,requestId:pending.requestId,invoiceId:4,companyId:2,projectPaymentId:8,paidAmount:'100'};
 global.fetch=jest.fn().mockResolvedValueOnce({ok:true,json:async()=>receipt}).mockResolvedValueOnce({ok:false});
 props.loadAll.mockImplementation(options=>refreshLegacyPayment({api:API,confirmation:options.paymentConfirmation,isCurrent:options.isCurrent,setInvoices:jest.fn()}));
 render(<Panel {...props}/>);fireEvent.click(screen.getByText('Проверить сохранённую оплату'));
 await waitFor(()=>expect(window.alert).toHaveBeenCalledWith(expect.stringContaining('список не обновился')));
 expect(localStorage.getItem(key)).toBe(JSON.stringify(pending));expect(global.fetch).toHaveBeenCalledTimes(2);
});
it('send then unmount then response never refreshes or clears',async()=>{
 localStorage.setItem(key,JSON.stringify(pending));let resolve;
 global.fetch=jest.fn(()=>new Promise(r=>{resolve=r;}));const view=render(<Panel {...props}/>);
 fireEvent.click(screen.getByText('Проверить сохранённую оплату'));view.unmount();
 await act(async()=>resolve({ok:true,json:async()=>({ok:true,requestId:pending.requestId,invoiceId:4,companyId:2,projectPaymentId:8})}));
 expect(props.loadAll).not.toHaveBeenCalled();expect(localStorage.getItem(key)).toBe(JSON.stringify(pending));expect(window.alert).not.toHaveBeenCalled();
});
it('logout then response retains pending for the same user next login',async()=>{
 localStorage.setItem(key,JSON.stringify(pending));let resolve;
 global.fetch=jest.fn(()=>new Promise(r=>{resolve=r;}));const view=render(<Panel {...props}/>);
 fireEvent.click(screen.getByText('Проверить сохранённую оплату'));view.rerender(<Panel {...props} user={null}/>);
 await act(async()=>resolve({ok:true,json:async()=>({ok:true,requestId:pending.requestId,invoiceId:4,companyId:2,projectPaymentId:8})}));
 expect(props.loadAll).not.toHaveBeenCalled();expect(localStorage.getItem(key)).not.toBeNull();
});
