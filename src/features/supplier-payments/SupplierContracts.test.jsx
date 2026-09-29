import React from 'react';
import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import Panel from './SupplierContracts';
const props={API:'/api',companyId:12,supplierId:5,userId:8};
const buyer={fullName:'Buyer',inn:'7701234567'},supplier={fullName:'Supplier',inn:'7709876543'};
let oldFetch,oldUUID;
beforeEach(()=>{oldFetch=global.fetch;oldUUID=global.crypto;global.crypto={randomUUID:()=> '11111111-1111-4111-8111-111111111111'};localStorage.clear();});
afterEach(()=>{global.fetch=oldFetch;global.crypto=oldUUID;});
const context={companyId:12,supplierId:5,items:[],buyer,supplier};
test('creates original directly from supplier card without offer or payer form',async()=>{
 global.fetch=jest.fn(async(url,options)=>({ok:true,json:async()=>url.endsWith('/upload-photo')?{companyId:12,fileId:31}:url.endsWith('/recognize')?{companyId:12,supplierId:5,sourceFileId:31,parties:{}}:options.method==='POST'?{companyId:12,snapshot:{supplier:{supplierId:5}}}:context}));
 render(<Panel {...props}/>);fireEvent.click(await screen.findByText('Добавить договор'));
 fireEvent.change(screen.getByLabelText('Файл договора'),{target:{files:[new File(['text'],'contract.txt')]}});
 await screen.findByText('Файл загружен.');await waitFor(()=>expect(screen.getByLabelText('Номер договора').disabled).toBe(false));
 fireEvent.change(screen.getByLabelText('Номер договора'),{target:{value:'C-1'}});
 fireEvent.change(screen.getByLabelText('Дата договора'),{target:{value:'2026-09-20'}});
 fireEvent.change(screen.getByLabelText('Срок'),{target:{value:'open_ended'}});
 fireEvent.change(screen.getByLabelText('Действует с'),{target:{value:'2026-09-20'}});
 fireEvent.click(screen.getByLabelText('Реквизиты и условия проверены'));
 fireEvent.click(screen.getByText('Сохранить договор'));
 await screen.findByText('Договор сохранён. Повторно загружать его в КП не нужно.');
 const call=global.fetch.mock.calls.find(([url,options])=>url.endsWith('/contracts')&&options.method==='POST');
 const body=JSON.parse(call[1].body);expect(body.sourceFileId).toBe(31);expect(body.buyer.inn).toBe(buyer.inn);expect(body.payer).toBeUndefined();expect(body.offerId).toBeUndefined();
 expect(call[1].headers['X-Company-Id']).toBe('12');
});
test('shows existing original and starts addendum without uploading original again',async()=>{
 global.fetch=jest.fn(async()=>({ok:true,json:async()=>({...context,items:[{id:10,sourceFileId:31,sourceFileUrl:'/tenant-files/31/content',snapshot:{number:'C',date:'2026-09-20',buyer,supplier}}]})}));
 render(<Panel {...props}/>);expect((await screen.findByText('Открыть договор')).getAttribute('href')).toBe('/api/tenant-files/31/content');
 fireEvent.click(screen.getByText('Добавить допсоглашение'));expect(screen.getByLabelText('Номер договора').readOnly).toBe(true);
 expect(screen.queryByLabelText('Файл договора')).toBeNull();expect(screen.getByLabelText('Файл допсоглашения')).toBeTruthy();
});
test('company mismatch never displays foreign documents',async()=>{
 global.fetch=jest.fn(async()=>({ok:true,json:async()=>({...context,companyId:99})}));render(<Panel {...props}/>);
 await screen.findByRole('alert');expect(screen.queryByText('Добавить договор')).toBeNull();
});
