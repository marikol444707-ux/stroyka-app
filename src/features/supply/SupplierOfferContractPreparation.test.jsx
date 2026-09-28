import React from 'react';
import {render,screen,fireEvent} from '@testing-library/react';
import SupplierOfferContractPreparation from './SupplierOfferContractPreparation';
jest.mock('../supplier-payments/SupplierContractReviewPanel',()=>props=><button onClick={props.onSaved}>Save reviewed contract</button>);
const flag='REACT_APP_SUPPLIER_DOCUMENT_CONTRACT_BINDINGS_ENABLED';
let old;
beforeEach(()=>{old=process.env[flag];process.env[flag]='true';});
afterEach(()=>{if(old===undefined)delete process.env[flag];else process.env[flag]=old;});
const props={API:'/api',user:{id:1,role:'директор'},companyContext:{selectedCompanyId:1,selectedCompany:{companyId:1,role:'директор'}},request:{companyId:1},offer:{id:4,companyId:1,status:'Утверждено'}};
test('opens review from approved offer without an invoice',()=>{render(<SupplierOfferContractPreparation {...props}/>);fireEvent.click(screen.getByRole('button'));fireEvent.click(screen.getByText('Save reviewed contract'));expect(screen.getByRole('status').textContent).toContain('Версия договора сохранена');});
test.each([
 {offer:{...props.offer,status:'Новое'}},
 {request:{companyId:2}},
 {companyContext:{...props.companyContext,mode:'all_companies'}},
 {companyContext:{...props.companyContext,selectedCompany:{role:'поставщик'}}},
 {companyContext:{...props.companyContext,selectedCompany:{role:'директор',readOnly:true}}},
])('hides preparation outside editable approved company scope %j',extra=>{render(<SupplierOfferContractPreparation {...props} {...extra}/>);expect(screen.queryByRole('button')).toBeNull();});
