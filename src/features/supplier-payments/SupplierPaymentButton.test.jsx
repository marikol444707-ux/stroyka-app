import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import SupplierPaymentButton from './SupplierPaymentButton';
jest.mock('./SupplierPaymentDialog', () => props => <div role="dialog">{JSON.stringify({userId:props.userId,companyId:props.companyId,documentKind:props.documentKind,documentId:props.documentId})}</div>);
const props={document:{id:4,companyId:2},documentKind:'invoice',companyContext:{mode:'company',selectedCompanyId:2},user:{id:7}};
const original=process.env.REACT_APP_SUPPLIER_PAYMENTS_ENABLED;
beforeEach(()=>{process.env.REACT_APP_SUPPLIER_PAYMENTS_ENABLED='true';});
afterEach(()=>{if(original===undefined) delete process.env.REACT_APP_SUPPLIER_PAYMENTS_ENABLED;else process.env.REACT_APP_SUPPLIER_PAYMENTS_ENABLED=original;});
it('opens the canonical document with explicit actor and company',()=>{
 render(<SupplierPaymentButton {...props}/>);
 fireEvent.click(screen.getByRole('button',{name:'Оплата и история'}));
 expect(JSON.parse(screen.getByRole('dialog').textContent)).toEqual({userId:7,companyId:2,documentKind:'invoice',documentId:4});
});
it('does not carry the open document across companies or reopen when switching back',()=>{
 const view=render(<SupplierPaymentButton {...props}/>);
 fireEvent.click(screen.getByRole('button'));
 view.rerender(<SupplierPaymentButton {...props} companyContext={{mode:'company',selectedCompanyId:3}}/>);
 expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
 expect(screen.getByRole('button')).toBeDisabled();
 view.rerender(<SupplierPaymentButton {...props}/>);
 expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});
it.each([{mode:'all',selectedCompanyId:2},{mode:'company',selectedCompanyId:2,loading:true},{mode:'company',selectedCompanyId:2,error:'offline'}])('blocks an unresolved company context %j',companyContext=>{
 render(<SupplierPaymentButton {...props} companyContext={companyContext}/>);
 expect(screen.getByRole('button')).toBeDisabled();
});
it('is absent when the release flag is off',()=>{
 process.env.REACT_APP_SUPPLIER_PAYMENTS_ENABLED='false';
 render(<SupplierPaymentButton {...props}/>);
 expect(screen.queryByRole('button')).not.toBeInTheDocument();
});
