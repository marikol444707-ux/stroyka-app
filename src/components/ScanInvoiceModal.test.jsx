import React, {useState} from 'react';
import {fireEvent, render, screen, waitFor} from '@testing-library/react';
import ScanInvoiceModal from './ScanInvoiceModal';
import {normalizeInvoiceImageFiles} from '../utils/invoiceImages';
import * as XLSX from 'xlsx';

jest.mock('../utils/invoiceImages', () => ({
  invoiceImageAccept: 'image/*,application/pdf', normalizeInvoiceImageFiles: jest.fn(),
}));

function renderScanner() {
  const setNewInvoice=jest.fn(), setShowScanInvoice=jest.fn(), setShowScannedInvoiceForm=jest.fn();
  function Harness({show=true}) {
    const [scanningInvoice,setScanningInvoice]=useState(false);
    return <ScanInvoiceModal showScanInvoice={show} setShowScanInvoice={setShowScanInvoice}
      setShowScannedInvoiceForm={setShowScannedInvoiceForm} scanningInvoice={scanningInvoice}
      setScanningInvoice={setScanningInvoice} C={{}} card={{}} btnG={{}} API="/api"
      newInvoice={{location:'Кисловодск Лицей 4',items:[]}} setNewInvoice={setNewInvoice}
      projects={[{id:7,name:'Кисловодск Лицей 4'}]} user={{name:'Кладовщик'}} />;
  }
  const view=render(<Harness />);
  return {setNewInvoice,setShowScanInvoice,setShowScannedInvoiceForm,
    setVisible:show=>view.rerender(<Harness show={show} />)};
}

beforeEach(() => {
  jest.clearAllMocks();
  jest.spyOn(window,'alert').mockImplementation(() => {});
  normalizeInvoiceImageFiles.mockImplementation(async files => files.map(file => ({
    base64:'U1lOVEhFVElD', mimeType:'image/jpeg', originalName:file.name, uploadFile:file,
  })));
});
afterEach(() => jest.restoreAllMocks());

test.each(['Файлы накладной','Фото накладной с камеры'])('provider failure on %s leaves the draft unchanged and can retry the same file', async inputLabel => {
  const file=new File(['synthetic'],'invoice.jpg',{type:'image/jpeg'});
  global.fetch=jest.fn()
    .mockResolvedValueOnce({ok:true,json:async()=>({ok:false,error:'AI не ответил: model_gateway_provider_failed'})})
    .mockResolvedValueOnce({ok:true,json:async()=>({ok:true,data:{number:'TEST-1',date:'2026-10-22',
      supplier:'Synthetic supplier',items:[{name:'Synthetic cement',quantity:2,unit:'мешок',price:100}],vat:'Без НДС'}})})
    .mockResolvedValueOnce({ok:true,json:async()=>({url:'/tenant-files/1/content'})});
  const utils=renderScanner();
  fireEvent.change(screen.getByLabelText(inputLabel),{target:{files:[file]}});
  expect(await screen.findByRole('alert')).toHaveTextContent('Выбранные файлы можно отправить повторно');
  expect(screen.getByRole('alert')).not.toHaveTextContent('model_gateway');
  expect(window.alert).not.toHaveBeenCalled();
  expect(utils.setNewInvoice).not.toHaveBeenCalled();
  expect(utils.setShowScannedInvoiceForm).not.toHaveBeenCalled();
  expect(fetch).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole('button',{name:'Повторить распознавание'}));
  await waitFor(()=>expect(utils.setShowScannedInvoiceForm).toHaveBeenCalledWith(true));
  const first=JSON.parse(fetch.mock.calls[0][1].body), second=JSON.parse(fetch.mock.calls[1][1].body);
  expect(second).toEqual(first);
  expect(normalizeInvoiceImageFiles.mock.calls[1][0][0]).toBe(file);
  const draft=utils.setNewInvoice.mock.calls[0][0]({items:[],photos:[]});
  expect(draft).toMatchObject({location:'Кисловодск Лицей 4',warehouseTarget:'object',
    selectedAction:'receive_to_warehouse',number:'TEST-1',items:[{name:'Synthetic cement',quantity:'2'}]});
  expect(fetch.mock.calls.map(([url])=>url)).toEqual(['/api/scan-invoice','/api/scan-invoice','/api/upload-photo']);
});

test('HTTP rejection cannot be treated as a successfully scanned invoice', async () => {
  global.fetch=jest.fn(async()=>({ok:false,json:async()=>({ok:true,detail:'Сервис недоступен',data:{items:[]}})}));
  const utils=renderScanner();
  fireEvent.change(screen.getByLabelText('Файлы накладной'),{target:{files:[new File(['x'],'invoice.jpg')]}});
  expect(await screen.findByRole('alert')).toHaveTextContent('Сервис недоступен');
  expect(utils.setNewInvoice).not.toHaveBeenCalled();
  expect(utils.setShowScannedInvoiceForm).not.toHaveBeenCalled();
});

test('closing the scanner clears the previous failure and retry selection', async () => {
  global.fetch=jest.fn(async()=>({ok:true,json:async()=>({ok:false,error:'model_gateway_provider_failed'})}));
  const utils=renderScanner();
  fireEvent.change(screen.getByLabelText('Файлы накладной'),{target:{files:[new File(['x'],'invoice.jpg')]}});
  await screen.findByRole('alert');
  utils.setVisible(false);
  utils.setVisible(true);
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(screen.queryByRole('button',{name:'Повторить распознавание'})).not.toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(1);
});

test('string decimal amounts keep cents and OCR mistakes remain visible for review', async () => {
  global.fetch=jest.fn()
    .mockResolvedValueOnce({ok:true,json:async()=>({ok:true,data:{number:'SYNTHETIC',date:'2026-10-22',supplier:'Synthetic supplier',
      totalWithVat:'2400.00',vat:'С НДС 22%',items:[{name:'Synthetic plaster',article:'SYN-1',quantity:'796',price:'399.99',lineTotal:'2400.00'}]}})})
    .mockResolvedValueOnce({ok:true,json:async()=>({url:'/tenant-files/synthetic/content'})});
  const utils=renderScanner();
  fireEvent.change(screen.getByLabelText('Файлы накладной'),{target:{files:[new File(['synthetic'],'invoice.jpg')]}});
  await waitFor(()=>expect(utils.setShowScannedInvoiceForm).toHaveBeenCalledWith(true));
  const draft=utils.setNewInvoice.mock.calls[0][0]({items:[],photos:[]});
  expect(draft.items[0]).toMatchObject({article:'SYN-1',quantity:'796',price:'399.99',lineTotal:'2400'});
  expect(draft.scanValidation.valid).toBe(false);
  expect(draft.totalWithVat).toBe(2400);
});

test.each(['xlsx','xls'])('Excel %s opens a review draft and uploads its original without an AI or receipt request', async bookType => {
  const book=XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(book,XLSX.utils.aoa_to_sheet([
    ['УПД № SYNTHETIC от 06.10.2026'],['Поставщик','Synthetic supplier'],
    ['Наименование','Код ОКЕИ','Количество','Ед.','Цена с НДС','Сумма с НДС','Ставка НДС'],
    ['Synthetic plaster',796,6,'шт',400,2400,'22%'],['Итого','','','','',2400],
  ]),'Invoice');
  const file=new File([XLSX.write(book,{type:'array',bookType})],`invoice.${bookType}`);
  global.fetch=jest.fn(async()=>({ok:true,json:async()=>({contentUrl:'/tenant-files/synthetic/content'})}));
  const utils=renderScanner();
  fireEvent.change(screen.getByLabelText('Файлы накладной'),{target:{files:[file]}});
  await waitFor(()=>expect(utils.setShowScannedInvoiceForm).toHaveBeenCalledWith(true));
  const draft=utils.setNewInvoice.mock.calls[0][0]({items:[],photos:[]});
  expect(draft.items[0]).toMatchObject({quantity:'6',price:'400',lineTotal:'2400'});
  expect(draft.scanValidation.valid).toBe(true);
  expect(draft.scanRecognition.method).toBe('spreadsheet');
  expect(fetch.mock.calls.map(([url])=>url)).toEqual(['/api/upload-photo']);
  expect(normalizeInvoiceImageFiles).not.toHaveBeenCalled();
});

test('mixed Excel and image selection cannot silently merge different documents',async()=>{
  global.fetch=jest.fn();
  const utils=renderScanner();
  fireEvent.change(screen.getByLabelText('Файлы накладной'),{target:{files:[new File(['x'],'one.xlsx'),new File(['x'],'photo.jpg')]}});
  expect(await screen.findByRole('alert')).toHaveTextContent('одну накладную Excel отдельно');
  expect(fetch).not.toHaveBeenCalled();
  expect(utils.setNewInvoice).not.toHaveBeenCalled();
});
