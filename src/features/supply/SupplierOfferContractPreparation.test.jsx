import React from 'react';
import {render,screen,fireEvent} from '@testing-library/react';
import SupplierOfferContractPreparation from './SupplierOfferContractPreparation';
jest.mock('../supplier-payments/SupplierContractReviewPanel',()=>props=><button onClick={props.onSaved}>Save reviewed contract</button>);
const flag='REACT_APP_SUPPLIER_DOCUMENT_CONTRACT_BINDINGS_ENABLED';
let old;
const originalFetch=global.fetch;
const contract={id:7,companyId:1,offerId:4,status:'reviewed',partyVersion:1,sourceFileId:11,snapshot:{number:'362',date:'2026-09-22'}};
const mockHistory=items=>{global.fetch=jest.fn(async url=>({ok:true,json:async()=>url.includes('/contracts')?{items}:{companyId:1,offerId:4,version:1}}));};
beforeEach(()=>{old=process.env[flag];process.env[flag]='true';mockHistory([]);});
afterEach(()=>{global.fetch=originalFetch;if(old===undefined)delete process.env[flag];else process.env[flag]=old;});
const props={API:'/api',user:{id:1,role:'директор'},companyContext:{selectedCompanyId:1,selectedCompany:{companyId:1,role:'директор'}},request:{companyId:1},offer:{id:4,companyId:1,status:'Утверждено'}};
test('adds the contract once and displays the saved original after saving',async()=>{
 render(<SupplierOfferContractPreparation {...props}/>);
 fireEvent.click(await screen.findByRole('button',{name:'Добавить договор'}));
 mockHistory([contract]);
 fireEvent.click(screen.getByText('Save reviewed contract'));
 expect(await screen.findByText(/Договор № 362/)).toBeInTheDocument();
 expect(screen.getByRole('link',{name:'Открыть договор'})).toHaveAttribute('href','/api/tenant-files/11/content');
 expect(screen.queryByText('Проверить договор до выставления счёта')).not.toBeInTheDocument();
});
test('a saved contract stays connected after remount without another review',async()=>{
 mockHistory([contract]);
 const view=render(<SupplierOfferContractPreparation {...props}/>);
 await screen.findByText(/Договор № 362/);view.unmount();
 render(<SupplierOfferContractPreparation {...props}/>);
 await screen.findByText(/Договор № 362/);
 expect(screen.queryByRole('button',{name:'Добавить договор'})).not.toBeInTheDocument();
});
test('failed loading does not ask to upload or review the contract again',async()=>{
 global.fetch=jest.fn(async()=>({ok:false,json:async()=>({})}));
 render(<SupplierOfferContractPreparation {...props}/>);
 await screen.findByRole('alert');
 expect(screen.getByRole('button',{name:'Повторить загрузку'})).toBeInTheDocument();
 expect(screen.queryByRole('button',{name:'Добавить договор'})).not.toBeInTheDocument();
});
test('a foreign contract is not displayed as connected',async()=>{
 mockHistory([{...contract,companyId:2}]);render(<SupplierOfferContractPreparation {...props}/>);
 await screen.findByRole('alert');expect(screen.queryByRole('link',{name:'Открыть договор'})).not.toBeInTheDocument();
});
test('a changed party version requires choosing a contract for the changed parties',async()=>{
 mockHistory([{...contract,partyVersion:2}]);render(<SupplierOfferContractPreparation {...props}/>);
 await screen.findByRole('button',{name:'Выбрать договор'});
 expect(screen.queryByText(/используется автоматически/)).not.toBeInTheDocument();
});
test.each([
 {offer:{...props.offer,status:'Новое'}},
 {request:{companyId:2}},
 {companyContext:{...props.companyContext,mode:'all_companies'}},
 {companyContext:{...props.companyContext,selectedCompany:{role:'поставщик'}}},
 {companyContext:{...props.companyContext,selectedCompany:{role:'директор',readOnly:true}}},
])('hides preparation outside editable approved company scope %j',extra=>{render(<SupplierOfferContractPreparation {...props} {...extra}/>);expect(screen.queryByRole('button')).toBeNull();});
