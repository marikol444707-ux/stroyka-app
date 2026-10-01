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
it('shows the frozen contract bank briefly on the invoice card',()=>{
 render(<SupplySupplierInvoicesPanel {...base} supplierInvoices={[{
  ...base.supplierInvoices[0],offerId:71,paymentRequisites:{contractNumber:'Д-1',supplier:{bankName:'Тест Банк',rs:'40702810415590000143'}},
 }]}/>);
 expect(screen.getByText('🏦 Реквизиты из договора № Д-1 · Тест Банк · счёт •0143')).toBeInTheDocument();
});
it('legacy fallback records only a bank transfer the user confirms already happened',()=>{
 process.env.REACT_APP_SUPPLIER_PAYMENTS_ENABLED='false';
 const confirm=jest.spyOn(window,'confirm').mockReturnValue(false);
 const prompt=jest.spyOn(window,'prompt').mockReturnValue('100');
 global.fetch=jest.fn();
 render(<SupplySupplierInvoicesPanel {...base}/>);
 expect(screen.queryByRole('button',{name:'Оплата и история'})).not.toBeInTheDocument();
 fireEvent.click(screen.getByRole('button',{name:'💰 Зафиксировать оплату'}));
 expect(confirm).toHaveBeenCalledWith('Деньги уже перечислены поставщику через банк? Программа только зафиксирует выполненную оплату.');
 expect(prompt).not.toHaveBeenCalled();
 expect(global.fetch).not.toHaveBeenCalled();
});
