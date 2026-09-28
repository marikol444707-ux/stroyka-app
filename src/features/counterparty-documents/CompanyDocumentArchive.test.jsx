import React from 'react';
import {render,screen,waitFor} from '@testing-library/react';
import Archive from './CompanyDocumentArchive';
const props={API:'',companyId:1,C:{},card:{},inp:{},btnG:{},setShowPhotoModal:jest.fn()};
const response=(companyId,title)=>({ok:true,json:async()=>({companyId,items:[{id:'company:1',companyId,title,documentType:'Устав',attachments:[],fileStatus:'not_attached'}],hasMore:false})});
afterEach(()=>jest.restoreAllMocks());
test('shows record without pretending there is a file',async()=>{
 global.fetch=jest.fn().mockResolvedValue(response(1,'Устав компании'));
 render(<Archive {...props}/>);
 await screen.findByText('Устав компании');
 expect(screen.queryByText('Открыть файл')).toBeNull();
 expect(screen.getByText('Файл не прикреплён')).not.toBeNull();
});
test('rejects a response belonging to another company',async()=>{
 global.fetch=jest.fn().mockResolvedValue(response(2,'Чужой документ'));
 render(<Archive {...props}/>);
 await screen.findByRole('alert');
 expect(screen.queryByText('Чужой документ')).toBeNull();
});
test('late previous company response is ignored',async()=>{
 let finish;
 global.fetch=jest.fn().mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve;})).mockResolvedValue(response(2,'Вторая компания'));
 const view=render(<Archive {...props}/>);
 view.rerender(<Archive {...props} companyId={2}/>);
 await screen.findByText('Вторая компания');
 finish(response(1,'Первая компания'));
 await waitFor(()=>expect(screen.queryByText('Первая компания')).toBeNull());
 expect(screen.getByText('Вторая компания')).not.toBeNull();
});

test('shows stored quotation and contract version beside an invoice',async()=>{
 global.fetch=jest.fn().mockResolvedValue({ok:true,json:async()=>({companyId:1,hasMore:false,items:[{
  id:'invoice:161',companyId:1,title:'Счёт №В-1',documentType:'Счёт',attachments:[],fileStatus:'not_attached',
  offerId:71,contractNumber:'362',contractVersion:2}]})});
 render(<Archive {...props}/>);
 await screen.findByText('КП № 71 · Договор № 362, версия 2');
 expect(screen.queryByText('Открыть файл')).toBeNull();
});
