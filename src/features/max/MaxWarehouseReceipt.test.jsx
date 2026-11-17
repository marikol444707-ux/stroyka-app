import React from 'react';
import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import {MaxWarehouseCompact} from './MaxQuickActionsPage';

jest.mock('../../components/ScanInvoiceModal',()=>function Review(props){
 if(!props.showScanInvoice)return null;
 return <section aria-label="Общая сверка оригинала">
 <button onClick={()=>props.onReceiptConfirmed({ok:true,warehouseInvoiceIds:[41]})}>Принять связанную поставку</button>
 <button onClick={()=>props.onStandaloneReceipt({location:'Объект',number:'DOC1',date:'2026-11-09',supplier:'Поставщик',supplierInn:'7701234567',
   originalUrls:['/tenant-files/1/content'],photos:['/tenant-files/1/content'],receiptDocument:{documentType:'waybill',supplierInn:'7701234567',buyerInn:'7702222222'},
   physicalReceiptConfirmed:false,newDocumentConfirmed:true,items:[{name:'Цемент',quantity:1,price:100,unit:'шт'}]} )}>Отдельная накладная</button>
 <button onClick={()=>props.onStandaloneReceipt({location:'Основной склад',number:'ACT1',date:'2026-11-09',inventoryOnly:true,
   originalUrls:['/tenant-files/1/content'],receiptDocument:{documentType:'inventory_act'},syncSupplierInvoice:false,
   physicalReceiptConfirmed:false,newDocumentConfirmed:true,items:[{name:'Цемент',quantity:1,price:100,unit:'шт'}]})}>Акт основного склада</button>
 </section>;
});
const response=(data,ok=true)=>({ok,status:ok?200:409,json:async()=>data});
beforeEach(()=>{global.fetch=jest.fn().mockResolvedValue(response([{id:2,name:'Объект',companyId:2}]))});
const open=async()=>{
 render(<MaxWarehouseCompact account={{employeeRole:'прораб',employeeName:'Мастер',companyId:2}}/>);
 await screen.findByRole('option',{name:'Объект'});
 fireEvent.click(screen.getByRole('button',{name:'Проверить оригинал'}));
 await screen.findByRole('region',{name:'Общая сверка оригинала'});
};
test('MAX receipt enters shared original review before any posting',async()=>{
 await open();expect(fetch.mock.calls.map(c=>c[0])).toEqual([expect.stringContaining('/projects')]);
});
test('matched receipt confirmation never also posts a standalone invoice',async()=>{
 await open();fireEvent.click(screen.getByText('Принять связанную поставку'));
 await screen.findByText(/Приёмка подтверждена/);
 expect(fetch).toHaveBeenCalledTimes(1);
});
test('standalone confirmation carries reviewed original and preserves the draft on409',async()=>{
 await open();fireEvent.click(screen.getByText('Отдельная накладная'));
 const save=screen.getByRole('button',{name:/Подтвердить приёмку/});expect(save).toBeDisabled();
 fireEvent.click(screen.getByRole('checkbox'));
 fetch.mockResolvedValueOnce(response({detail:'Документ требует повторной сверки'},false));
 fireEvent.click(save);await screen.findByText('Документ требует повторной сверки');
 const payload=JSON.parse(fetch.mock.calls[1][1].body);
 expect(payload).toEqual(expect.objectContaining({physicalReceiptConfirmed:true,newDocumentConfirmed:true,originalUrls:['/tenant-files/1/content'],receiptDocument:expect.objectContaining({documentType:'waybill'})}));
 expect(screen.getByPlaceholderText('Номер накладной')).toHaveValue('DOC1');
 expect(fetch).toHaveBeenCalledTimes(2);
});

test('MAX director can confirm reviewed own-stock act without inventing supplier',async()=>{
 render(<MaxWarehouseCompact account={{employeeRole:'директор',employeeName:'Директор',companyId:2}}/>);
 await screen.findByRole('option',{name:'Объект'});
 fireEvent.click(screen.getByRole('button',{name:'Проверить оригинал'}));
 fireEvent.click(await screen.findByText('Акт основного склада'));
 fireEvent.click(screen.getByRole('checkbox'));
 fetch.mockResolvedValueOnce(response({ok:true,id:41}));
 fireEvent.click(screen.getByRole('button',{name:/Подтвердить приёмку/}));
 await waitFor(()=>expect(fetch).toHaveBeenCalledTimes(2));
 expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual(expect.objectContaining({inventoryOnly:true,physicalReceiptConfirmed:true,supplierName:'',receiptDocument:{documentType:'inventory_act'},syncSupplierInvoice:false}));
});
