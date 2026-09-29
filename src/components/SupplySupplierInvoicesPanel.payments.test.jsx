import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import SupplySupplierInvoicesPanel from './SupplySupplierInvoicesPanel';
jest.mock('../features/supplier-payments/SupplierPaymentDialog',()=>props=><div role="dialog">Счёт {props.documentId}</div>);
const base={C:{},card:{},inp:{},btnO:{},btnG:{},btnGr:{},btnR:{},badge:()=>({}),
 user:{id:7,name:'Тестовый бухгалтер'},suppliers:[],projects:[],supplierInvoices:[{id:4,companyId:2,projectName:'Объект',supplierName:'Поставщик',invoiceNumber:'1',amount:100,paidAmount:0,status:'Утверждён'}],
 newSupplierInvoice:null,matchSearch:()=>true,expandedProject:'sup-Объект',canPay:true,
 companyContext:{mode:'company',selectedCompanyId:2},loadAll:jest.fn()};
const original=process.env.REACT_APP_SUPPLIER_PAYMENTS_ENABLED;
afterEach(()=>{if(original===undefined)delete process.env.REACT_APP_SUPPLIER_PAYMENTS_ENABLED;else process.env.REACT_APP_SUPPLIER_PAYMENTS_ENABLED=original;});
it('uses the transaction dialog rather than the two-request payment action',()=>{
 process.env.REACT_APP_SUPPLIER_PAYMENTS_ENABLED='true';
 render(<SupplySupplierInvoicesPanel {...base}/>);
 expect(screen.queryByRole('button',{name:/^💰/})).not.toBeInTheDocument();
 fireEvent.click(screen.getByRole('button',{name:'Оплата и история'}));
 expect(screen.getByRole('dialog')).toHaveTextContent('Счёт 4');
});
it('keeps reversal/history accessible for a fully paid invoice',()=>{
 process.env.REACT_APP_SUPPLIER_PAYMENTS_ENABLED='true';
 render(<SupplySupplierInvoicesPanel {...base} supplierInvoices={[{...base.supplierInvoices[0],status:'Оплачен',paidAmount:100}]}/>);
 expect(screen.getByRole('button',{name:'Оплата и история'})).toBeEnabled();
});
it('leaves the old interface unchanged before activation',()=>{
 process.env.REACT_APP_SUPPLIER_PAYMENTS_ENABLED='false';
 render(<SupplySupplierInvoicesPanel {...base}/>);
 expect(screen.queryByRole('button',{name:'Оплата и история'})).not.toBeInTheDocument();
 expect(screen.getByRole('button',{name:/^💰/})).toBeEnabled();
});
