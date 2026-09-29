import React from 'react';
import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import SupplierContractDocuments from './SupplierContractDocuments';
const flag='REACT_APP_SUPPLIER_DOCUMENT_CONTRACT_BINDINGS_ENABLED';
const props={API:'/api',userId:3,C:{text:'#eee',bg:'#18202a',border:'#345'}};
const item={id:8,companyId:1,customer:'Заказчик А',number:'362',date:'2026-09-22',version:1,fileUrl:'/tenant-files/31/content',addenda:[]};
let oldFlag,oldFetch;
beforeEach(()=>{oldFlag=process.env[flag];process.env[flag]='true';oldFetch=global.fetch;});
afterEach(()=>{global.fetch=oldFetch;if(oldFlag===undefined)delete process.env[flag];else process.env[flag]=oldFlag;});
const reply=(items=[item],nextCursor=null)=>({ok:true,json:async()=>({items,nextCursor})});
test('shows customer and downloadable original without approval steps',async()=>{
 global.fetch=jest.fn(async()=>reply());render(<SupplierContractDocuments {...props}/>);
 await screen.findByText('Договор № 362 от 22.09.2026');expect(screen.getByText('Заказчик А')).toBeTruthy();
 expect(screen.getByRole('button',{name:'Скачать договор'})).toBeTruthy();expect(screen.queryByRole('checkbox')).toBeNull();
 expect(global.fetch.mock.calls[0][1]).toMatchObject({credentials:'include',cache:'no-store'});
});
test('refresh removes old documents when access is revoked',async()=>{
 global.fetch=jest.fn(async()=>reply());render(<SupplierContractDocuments {...props}/>);await screen.findByText('Заказчик А');
 global.fetch=jest.fn(async()=>({ok:false,json:async()=>({})}));fireEvent.click(screen.getByRole('button',{name:'Обновить'}));
 await screen.findByRole('alert');expect(screen.queryByText('Заказчик А')).toBeNull();
});
test('actor change cannot keep the old actor documents or delayed response',async()=>{
 let resolve;global.fetch=jest.fn(()=>new Promise(r=>{resolve=r;}));
 const view=render(<SupplierContractDocuments {...props}/>);
 global.fetch=jest.fn(async()=>reply([]));view.rerender(<SupplierContractDocuments {...props} userId={4}/>);
 await screen.findByText(/Договоров пока нет/);resolve(reply());await waitFor(()=>expect(screen.queryByText('Заказчик А')).toBeNull());
});
test('paginates and refresh returns to first page',async()=>{
 global.fetch=jest.fn(async url=>url.includes('before=8')?reply([{...item,id:7,number:'7'}]):reply([item],8));
 render(<SupplierContractDocuments {...props}/>);fireEvent.click(await screen.findByRole('button',{name:'Следующие договоры'}));
 await screen.findByText('Договор № 7 от 22.09.2026');expect(screen.queryByText('Договор № 362 от 22.09.2026')).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'Обновить'}));await screen.findByText('Договор № 362 от 22.09.2026');
});
