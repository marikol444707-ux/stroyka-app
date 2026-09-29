import React,{useState} from 'react';
import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import SupplierInvoiceContractChoice from './SupplierInvoiceContractChoice';
const flag='REACT_APP_SUPPLIER_DOCUMENT_CONTRACT_BINDINGS_ENABLED';
let oldFlag,oldFetch;
beforeEach(()=>{oldFlag=process.env[flag];process.env[flag]='true';oldFetch=global.fetch;});
afterEach(()=>{global.fetch=oldFetch;if(oldFlag===undefined)delete process.env[flag];else process.env[flag]=oldFlag;});
const contract={id:8,companyId:1,offerId:4,partyVersion:2,version:1,status:'reviewed',snapshot:{number:'C-1',date:'2026-09-28',buyer:{fullName:'Buyer'},payer:{fullName:'Payer'}}};
function responses(item=contract,parties={companyId:1,offerId:4,version:2}){global.fetch=jest.fn(async url=>({ok:true,json:async()=>url.includes('/contracts')?{items:item?[item]:[]}:parties}));}
function Form(){const [id,setId]=useState(null);return <><SupplierInvoiceContractChoice API="/api" userId={3} companyId={1} offerId={4} value={id} onChange={setId}/><output data-testid="chosen">{id||'none'}</output></>;}
test('selects checked contract automatically and clears selection if refresh fails',async()=>{responses();render(<Form/>);await waitFor(()=>expect(screen.getByTestId('chosen').textContent).toBe('8'));expect(screen.queryByRole('checkbox')).toBeNull();responses(null);fireEvent.click(screen.getByRole('button'));await screen.findByRole('alert');expect(screen.getByTestId('chosen').textContent).toBe('none');});
test.each([
 ['missing',null,{companyId:1,offerId:4,version:2}],
 ['stale',contract,{companyId:1,offerId:4,version:3}],
 ['foreign',{...contract,companyId:9},{companyId:1,offerId:4,version:2}],
 ['unreviewed',{...contract,status:'draft'},{companyId:1,offerId:4,version:2}],
])('does not allow %s contract',async(_,item,parties)=>{responses(item,parties);render(<Form/>);await screen.findByRole('alert');expect(screen.queryByRole('checkbox')).toBeNull();expect(screen.getByTestId('chosen').textContent).toBe('none');});
