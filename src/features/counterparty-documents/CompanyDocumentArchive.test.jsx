import React from 'react';
import {render,screen,waitFor,fireEvent} from '@testing-library/react';
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

test('opens exact related contract and returns to the previous list',async()=>{
 const invoice={id:'invoice:161',source:'invoice',sourceId:161,companyId:1,title:'Счёт В-1',attachments:[],contractId:9};
 const contract={id:'contract:9',source:'contract',sourceId:9,companyId:1,title:'Договор 362',attachments:[]};
 const wrap=item=>({ok:true,json:async()=>({companyId:1,items:[item],hasMore:false})});
 global.fetch=jest.fn().mockResolvedValueOnce(wrap(invoice)).mockResolvedValueOnce(wrap(contract)).mockResolvedValueOnce(wrap(invoice));
 render(<Archive {...props}/>);
 fireEvent.click(await screen.findByText('Показать договор'));
 await screen.findByText('Договор 362');
 const params=new URLSearchParams(global.fetch.mock.calls[1][0].split('?')[1]);
 expect(params.get('source')).toBe('contract');expect(params.get('recordId')).toBe('9');
 expect(global.fetch.mock.calls[1][1].headers['X-Company-Id']).toBe('1');
 fireEvent.click(screen.getByText('Вернуться к списку'));
 await screen.findByText('Счёт В-1');
 expect(global.fetch.mock.calls[2][0]).toBe(global.fetch.mock.calls[0][0]);
});

test('lists invoices for exact contract version and returns to contract list',async()=>{
 const wrap=items=>({ok:true,json:async()=>({companyId:1,items,hasMore:false})});
 const contract={id:'contract:9',source:'contract',sourceId:9,companyId:1,title:'Договор 362',attachments:[]};
 global.fetch=jest.fn().mockResolvedValueOnce(wrap([contract])).mockResolvedValueOnce(wrap([])).mockResolvedValueOnce(wrap([contract]));
 render(<Archive {...props}/>);
 fireEvent.click(await screen.findByText('Счета по этой версии'));
 await screen.findByText('К этой версии договора счета ещё не привязаны.');
 expect(new URLSearchParams(global.fetch.mock.calls[1][0].split('?')[1]).get('contractId')).toBe('9');
 fireEvent.click(screen.getByText('Вернуться к списку'));
 await screen.findByText('Договор 362');
 expect(global.fetch.mock.calls[2][0]).toBe(global.fetch.mock.calls[0][0]);
});

test('rejects invoice belonging to another contract version',async()=>{
 const wrap=items=>({ok:true,json:async()=>({companyId:1,items,hasMore:false})});
 global.fetch=jest.fn().mockResolvedValueOnce(wrap([{id:'contract:9',source:'contract',sourceId:9,companyId:1,title:'Договор 362',attachments:[]}]))
  .mockResolvedValueOnce(wrap([{id:'invoice:161',source:'invoice',sourceId:161,companyId:1,contractId:10,title:'Другой счёт',attachments:[]}]));
 render(<Archive {...props}/>);
 fireEvent.click(await screen.findByText('Счета по этой версии'));
 await screen.findByRole('alert');
 expect(screen.queryByText('Другой счёт')).toBeNull();
});

test('opens verified original contract and restores list on return',async()=>{
 const wrap=item=>({ok:true,json:async()=>({companyId:1,items:[item],hasMore:false})});
 const reused={id:'contract:10',source:'contract',sourceId:10,companyId:1,title:'Повторный договор',attachments:[],originContractId:9};
 const original={id:'contract:9',source:'contract',sourceId:9,companyId:1,title:'Первый договор',attachments:[]};
 global.fetch=jest.fn().mockResolvedValueOnce(wrap(reused)).mockResolvedValueOnce(wrap(original)).mockResolvedValueOnce(wrap(reused));
 render(<Archive {...props}/>);
 fireEvent.click(await screen.findByText('Исходный договор'));
 await screen.findByText('Первый договор');
 expect(screen.queryByText('Исходный договор')).toBeNull();
 const params=new URLSearchParams(global.fetch.mock.calls[1][0].split('?')[1]);
 expect(params.get('source')).toBe('contract');expect(params.get('recordId')).toBe('9');
 fireEvent.click(screen.getByText('Вернуться к списку'));
 await screen.findByText('Повторный договор');
 expect(global.fetch.mock.calls[2][0]).toBe(global.fetch.mock.calls[0][0]);
});

test('category filters the full archive and survives related navigation',async()=>{
 const wrap=(items,hasMore=false)=>({ok:true,json:async()=>({companyId:1,items,hasMore,nextOffset:30})});
 const invoice={id:'invoice:161',source:'invoice',sourceId:161,companyId:1,title:'Счёт В-1',attachments:[],contractId:9};
 const contract={id:'contract:9',source:'contract',sourceId:9,companyId:1,title:'Договор 362',attachments:[]};
 global.fetch=jest.fn().mockResolvedValueOnce(wrap([])).mockResolvedValueOnce(wrap([invoice],true))
  .mockResolvedValueOnce(wrap([invoice])).mockResolvedValueOnce(wrap([contract])).mockResolvedValueOnce(wrap([invoice]));
 render(<Archive {...props}/>);
 await screen.findByText('Документы не найдены.');
 fireEvent.change(screen.getByLabelText('Вид документа'),{target:{value:'invoice'}});
 await screen.findByText('Счёт В-1');
 fireEvent.click(screen.getByText('Далее'));
 await waitFor(()=>expect(global.fetch).toHaveBeenCalledTimes(3));
 await screen.findByText('Счёт В-1');
 let params=new URLSearchParams(global.fetch.mock.calls[2][0].split('?')[1]);
 expect(params.get('category')).toBe('invoice');expect(params.get('offset')).toBe('30');
 fireEvent.click(screen.getByText('Показать договор'));
 await screen.findByText('Договор 362');
 expect(new URLSearchParams(global.fetch.mock.calls[3][0].split('?')[1]).has('category')).toBe(false);
 fireEvent.click(screen.getByText('Вернуться к списку'));
 await screen.findByText('Счёт В-1');
 expect(global.fetch.mock.calls[4][0]).toBe(global.fetch.mock.calls[2][0]);
 expect(screen.getByLabelText('Вид документа').value).toBe('invoice');
});

test('changing section or company clears category',async()=>{
 global.fetch=jest.fn().mockImplementation((_url,options)=>Promise.resolve({ok:true,json:async()=>({companyId:Number(options.headers['X-Company-Id']),items:[],hasMore:false})}));
 const view=render(<Archive {...props}/>);
 await screen.findByText('Документы не найдены.');
 fireEvent.change(screen.getByLabelText('Вид документа'),{target:{value:'invoice'}});
 await waitFor(()=>expect(global.fetch).toHaveBeenCalledTimes(2));
 fireEvent.click(screen.getByText('Моя компания'));
 await waitFor(()=>expect(global.fetch).toHaveBeenCalledTimes(3));
 expect(screen.getByLabelText('Вид документа').value).toBe('');
 expect(screen.queryByRole('option',{name:'Счета',exact:true})).toBeNull();
 fireEvent.change(screen.getByLabelText('Вид документа'),{target:{value:'company'}});
 await waitFor(()=>expect(global.fetch).toHaveBeenCalledTimes(4));
 view.rerender(<Archive {...props} companyId={2}/>);
 await waitFor(()=>expect(global.fetch).toHaveBeenCalledTimes(5));
 expect(screen.getByLabelText('Вид документа').value).toBe('');
 expect(new URLSearchParams(global.fetch.mock.calls[4][0].split('?')[1]).has('category')).toBe(false);
});

test('rejects rows from a different category',async()=>{
 global.fetch=jest.fn().mockResolvedValue(response(1,'Устав компании'));
 render(<Archive {...props}/>);
 await screen.findByText('Устав компании');
 fireEvent.change(screen.getByLabelText('Вид документа'),{target:{value:'invoice'}});
 await screen.findByRole('alert');
 expect(screen.queryByText('Устав компании')).toBeNull();
});

test('shows reviewed scope and term from contract snapshot',async()=>{
 global.fetch=jest.fn().mockResolvedValue({ok:true,json:async()=>({companyId:1,hasMore:false,items:[{
  id:'contract:9',source:'contract',sourceId:9,companyId:1,title:'Договор 362',attachments:[],
  applicability:{scope:'project',projectId:44,term:'fixed',startsOn:'2026-09-01',endsOn:'2026-12-31'},scopeProjectName:'Лицей'}]})});
 render(<Archive {...props}/>);
 await screen.findByText('Объект: Лицей · с 01.09.2026 по 31.12.2026');
});
