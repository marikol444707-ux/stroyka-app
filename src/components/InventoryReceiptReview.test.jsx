import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ScanInvoiceModal from './ScanInvoiceModal';
import UnifiedReceiptReview from './UnifiedReceiptReview';
import ScannedInvoiceFormModal from './ScannedInvoiceFormModal';
import { normalizeInvoiceImageFiles } from '../utils/invoiceImages';

jest.mock('../utils/invoiceImages', () => ({ invoiceImageAccept:'image/*', normalizeInvoiceImageFiles:jest.fn() }));
const response = data => ({ok:true,json:async()=>data});
const parsed = {documentType:'',number:'ACT-12',date:'2026-11-09',items:[{name:'Цемент',unit:'т',quantity:10}]};
const scan = {parsed,originalUrls:['/tenant-files/17/content'],location:'Основной склад',companyId:7};

beforeEach(() => {
  global.fetch=jest.fn();
  normalizeInvoiceImageFiles.mockResolvedValue([{base64:'data',mimeType:'image/jpeg',originalName:'act.jpg'}]);
  jest.spyOn(window,'alert').mockImplementation(()=>{});
});
afterEach(() => jest.restoreAllMocks());

function Scanner({onStandaloneReceipt}) {
  const [draft,setDraft]=React.useState({location:'Основной склад',supplier:'',items:[]});
  const [busy,setBusy]=React.useState(false);
  return <ScanInvoiceModal showScanInvoice setShowScanInvoice={()=>{}} C={{}} API="/api"
    projects={[]} companyId={7} newInvoice={draft} setNewInvoice={setDraft}
    scanningInvoice={busy} setScanningInvoice={setBusy} unifiedReceipt onStandaloneReceipt={onStandaloneReceipt}/>;
}

test('main warehouse act is explicitly rechecked and continues without fabricated parties or accounting',async()=>{
  const next=jest.fn();
  fetch.mockResolvedValueOnce(response({url:scan.originalUrls[0]}))
    .mockResolvedValueOnce(response({ok:true,data:parsed}))
    .mockResolvedValueOnce(response({status:'review'}))
    .mockResolvedValueOnce(response({status:'no_match'}));
  render(<Scanner onStandaloneReceipt={next}/>);
  fireEvent.change(screen.getByLabelText('Оригиналы документа'),{target:{files:[new File(['act'],'act.jpg',{type:'image/jpeg'})]}});
  await screen.findByRole('alert');
  const type=screen.getByLabelText('Тип документа');
  expect([...type.options].some(option=>option.value==='inventory_act')).toBe(true);
  fireEvent.change(type,{target:{value:'inventory_act'}});
  fireEvent.change(screen.getByLabelText('Номер документа'),{target:{value:'ACT-REVIEWED'}});
  fireEvent.change(screen.getByLabelText('Количество по документу 1'),{target:{value:'8'}});
  expect(fetch).toHaveBeenCalledTimes(3);
  expect(next).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText('Повторить проверку'));
  fireEvent.click(await screen.findByText('Оформить отдельный документ'));
  expect(fetch.mock.calls.map(call=>call[0])).toEqual(['/api/upload-photo','/api/scan-invoice','/api/warehouse-receipts/resolve','/api/warehouse-receipts/resolve']);
  const reviewed=JSON.parse(fetch.mock.calls[3][1].body);
  expect(reviewed.document).toEqual(expect.objectContaining({documentType:'inventory_act',waybillNumber:'ACT-REVIEWED',waybillDate:parsed.date,lines:[expect.objectContaining({quantity:'8'})]}));
  expect(reviewed.document.supplierInn || '').toBe('');
  expect(reviewed.document.buyerInn || '').toBe('');
  expect(next).toHaveBeenCalledWith(expect.objectContaining({
    inventoryOnly:true,selectedAction:'receive_stock_without_supplier',syncSupplierInvoice:false,
    number:'ACT-REVIEWED',date:parsed.date,receiptDocument:reviewed.document,originalUrls:scan.originalUrls,
    newDocumentConfirmed:true,physicalReceiptConfirmed:false,
  }));
  expect(next.mock.calls[0][0].supplierId || '').toBe('');
  expect(next.mock.calls[0][0].supplierInvoiceId || '').toBe('');
});

test.each([
  {location:'Объект',projectId:11},
  {sourceSupplierInvoiceId:81},
])('inventory act option is unavailable for procurement/object scope %j',async(scope)=>{
  fetch.mockResolvedValue(response({status:'review'}));
  render(<UnifiedReceiptReview API="/api" scan={{...scan,...scope}}/>);
  await screen.findByRole('alert');
  expect([...screen.getByLabelText('Тип документа').options].some(option=>option.value==='inventory_act')).toBe(false);
});

function InventoryForm({initial,save}) {
  const [draft,setDraft]=React.useState({location:'Основной склад',inventoryOnly:true,
    selectedAction:'receive_stock_without_supplier',number:'ACT-12',date:'2026-11-09',
    receiptDocument:{documentType:'inventory_act'},scanDocumentType:'inventory_act',
    originalUrls:scan.originalUrls,physicalReceiptConfirmed:true,newDocumentConfirmed:true,
    items:[{name:'Цемент',unit:'т',quantity:'8',price:'0'}],...initial});
  return <ScannedInvoiceFormModal user={{role:'директор'}} showScannedInvoiceForm
    setShowScannedInvoiceForm={()=>{}} C={{}} card={{}} inp={{}} btnO={{}} btnG={{}} btnR={{}}
    newInvoice={draft} setNewInvoice={setDraft} projects={[]} units={['т']}
    getProjectWorkPackageOptions={()=>[]} getProjectEstimateWorkOptions={()=>[]} saveInvoiceNew={save}/>;
}

test.each(['number','date'])('edited inventory act cannot save with empty actual %s',async(field)=>{
  const save=jest.fn().mockResolvedValue(true);
  const {container}=render(<InventoryForm save={save}/>);
  const input=field==='number' ? screen.getByDisplayValue('ACT-12') : container.querySelector('input[type="date"]');
  fireEvent.change(input,{target:{value:''}});
  fireEvent.click(screen.getByRole('button',{name:'Сохранить'}));
  await waitFor(()=>expect(save).not.toHaveBeenCalled());
});
