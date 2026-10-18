import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import UnifiedReceiptReview from './UnifiedReceiptReview';
import ScanInvoiceModal from './ScanInvoiceModal';
import { normalizeInvoiceImageFiles } from '../utils/invoiceImages';
jest.mock('../utils/invoiceImages', () => ({ invoiceImageAccept: 'image/*', normalizeInvoiceImageFiles: jest.fn() }));
const response = data => ({ok:true,json:async()=>data});
const scan = {parsed:{documentType:'waybill',number:'12',date:'2026-10-18',supplierInn:'123',buyerInn:'456',items:[{name:'Цемент',unit:'т',quantity:10}]},originalUrls:['/original'],location:'Объект'};
const match = {status:'match',matchedBatch:{waybillNumber:'12',lines:[{id:1,materialName:'Цемент',unit:'т',shippedQuantity:10}]}};
beforeEach(() => {global.fetch=jest.fn();normalizeInvoiceImageFiles.mockResolvedValue([{base64:'data',mimeType:'image/jpeg',originalName:'a.jpg'}]);});
afterEach(() => jest.restoreAllMocks());
test('actual quantity starts blank, requires confirmation and prevents duplicate posting', async()=>{
  fetch.mockResolvedValueOnce(response(match)).mockResolvedValueOnce(response({status:'accepted'}));
  render(<UnifiedReceiptReview API="/api" scan={scan}/>);
  const qty = await screen.findByLabelText('Фактически принято: Цемент');
  const button = screen.getByText('Подтвердить фактическую приёмку');
  expect(qty).toHaveValue(null); expect(button).toBeDisabled();
  fireEvent.change(qty,{target:{value:'8'}});expect(button).toBeDisabled();
  fireEvent.click(screen.getByRole('checkbox'));fireEvent.click(button);fireEvent.click(button);
  await screen.findByText(/Приёмка подтверждена/);
  expect(fetch).toHaveBeenCalledTimes(2);
  expect(JSON.parse(fetch.mock.calls[1][1].body).actualLines[0].receivedQuantity).toBe(8);
});
test('finalized shortage is read only and opens existing receipt through provided callback',async()=>{
  const open=jest.fn();fetch.mockResolvedValue(response({...match,matchedBatch:{...match.matchedBatch,lines:[{...match.matchedBatch.lines[0],receivedQuantity:7,receivedAt:'now',warehouseInvoiceId:9}]}}));
  render(<UnifiedReceiptReview API="/api" scan={scan} onOpenReceipt={open}/>);
  await screen.findByText(/Недостача: 3/);expect(screen.queryByRole('spinbutton')).not.toBeInTheDocument();
  expect(screen.queryByText('Подтвердить фактическую приёмку')).not.toBeInTheDocument();fireEvent.click(screen.getByText('Открыть приход'));expect(open).toHaveBeenCalledWith(9);
});
test.each(['review','ambiguous'])('%s cannot create a separate document',async(status)=>{
  fetch.mockResolvedValue(response({status}));render(<UnifiedReceiptReview API="/api" scan={scan}/>);
  await screen.findByRole('alert');expect(screen.queryByText('Оформить отдельный документ')).not.toBeInTheDocument();
});
test('only no_match explicitly continues standalone with original and confirmation',async()=>{
  const next=jest.fn();fetch.mockResolvedValue(response({status:'no_match'}));render(<UnifiedReceiptReview API="/api" scan={scan} onNewDocument={next}/>);
  fireEvent.click(await screen.findByText('Оформить отдельный документ'));expect(next).toHaveBeenCalledWith(expect.objectContaining({newDocumentConfirmed:true,physicalReceiptConfirmed:false,originalUrls:['/original']}));
});
function Scanner({onDraft, ...props}) {
  const [draft,setDraft]=React.useState({location:'Объект',supplier:'',items:[]});
  const [busy,setBusy]=React.useState(false);
  return <><button onClick={()=>setDraft(prev=>({...prev,supplier:'Ручное имя'}))}>Править поставщика</button><ScanInvoiceModal showScanInvoice setShowScanInvoice={()=>{}} setShowScannedInvoiceForm={()=>{}} C={{}} API="/api" projects={[{id:11,name:"Объект",companyId:7}]} companyId={7} newInvoice={draft} setNewInvoice={value=>setDraft(prev=>{const next=typeof value==='function'?value(prev):value;onDraft?.(next);return next;})} scanningInvoice={busy} setScanningInvoice={setBusy} unifiedReceipt {...props}/></>;
}
const pick = container => fireEvent.change(screen.getByLabelText('Оригиналы документа'), {target:{files:[new File(['x'],'a.jpg',{type:'image/jpeg'})]}});
test('scan uploads original before OCR and opens review without posting',async()=>{
  fetch.mockResolvedValueOnce(response({url:'/original'})).mockResolvedValueOnce(response({ok:true,data:scan.parsed})).mockResolvedValueOnce(response(match));
  const {container}=render(<Scanner/>);pick(container);await screen.findByLabelText('Фактически принято: Цемент');
  expect(fetch.mock.calls.map(call=>call[0])).toEqual(['/api/upload-photo','/api/scan-invoice','/api/warehouse-receipts/resolve']);
});
test('OCR failure retains uploaded original and blocks posting',async()=>{
  const draft=jest.fn();fetch.mockResolvedValueOnce(response({url:'/original'})).mockResolvedValueOnce(response({ok:false,error:'Не распознано'})).mockResolvedValueOnce(response({status:'review'}));
  const {container}=render(<Scanner onDraft={draft}/>);pick(container);await screen.findByText(/Перенесите реквизиты/);
  await screen.findByText(/Приёмка заблокирована, оригиналы сохранены/);
  expect(draft).toHaveBeenLastCalledWith(expect.objectContaining({originalUrls:['/original']}));expect(fetch).toHaveBeenCalledTimes(3);
});
test('upload failure blocks OCR and resolver',async()=>{
  fetch.mockResolvedValue({ok:false,json:async()=>({})});const {container}=render(<Scanner/>);pick(container);await screen.findByRole('alert');expect(fetch).toHaveBeenCalledTimes(1);
});
test('late OCR preserves manual edit',async()=>{
  let finish;const draft=jest.fn();fetch.mockResolvedValueOnce(response({url:'/original'})).mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve;})).mockResolvedValueOnce(response(match));
  const {container}=render(<Scanner onDraft={draft}/>);pick(container);await waitFor(()=>expect(finish).toBeDefined());fireEvent.click(screen.getByText('Править поставщика'));
  finish(response({ok:true,data:{...scan.parsed,supplier:'OCR supplier'}}));await screen.findByLabelText('Фактически принято: Цемент');expect(draft).toHaveBeenLastCalledWith(expect.objectContaining({supplier:'Ручное имя'}));
});
test('cancel ignores late OCR',async()=>{
  let finish;const callback=jest.fn();fetch.mockResolvedValueOnce(response({url:'/original'})).mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve;}));
  const {container}=render(<Scanner onDocumentScanned={callback}/>);pick(container);await waitFor(()=>expect(finish).toBeDefined());fireEvent.click(screen.getByText('Отмена'));finish(response({ok:true,data:scan.parsed}));
  await waitFor(()=>expect(screen.queryByText('Проверка документа и фактической поставки')).not.toBeInTheDocument());expect(callback).not.toHaveBeenCalled();
});
test('manual document changes require fresh resolver and survive unrelated render',async()=>{
  fetch.mockResolvedValueOnce(response(match)).mockResolvedValueOnce(response({status:'no_match'}));
  const next=jest.fn();const view=render(<UnifiedReceiptReview API="/api" scan={scan} onNewDocument={next}/>);
  await screen.findByLabelText('Фактически принято: Цемент');
  fireEvent.change(screen.getByLabelText('Номер документа'),{target:{value:'MANUAL-2'}});
  view.rerender(<UnifiedReceiptReview API="/api" scan={scan} onNewDocument={next}/>);
  expect(screen.getByLabelText('Номер документа')).toHaveValue('MANUAL-2');
  fireEvent.click(screen.getByText('Повторить проверку'));
  fireEvent.click(await screen.findByText('Оформить отдельный документ'));
  expect(JSON.parse(fetch.mock.calls[1][1].body).document.waybillNumber).toBe('MANUAL-2');
  expect(next).toHaveBeenCalledWith(expect.objectContaining({receiptDocument:expect.objectContaining({waybillNumber:'MANUAL-2'})}));
});
test('partial batch displays closed shortage and asks actual only for unreceived line',async()=>{
  fetch.mockResolvedValue(response({...match,receiptState:'partial',matchedBatch:{...match.matchedBatch,lines:[{...match.matchedBatch.lines[0],receivedQuantity:7,status:'Проблема'}, {id:2,materialName:'Песок',unit:'т',shippedQuantity:5}]}}));
  render(<UnifiedReceiptReview API="/api" scan={scan}/>);
  await screen.findByText(/Недостача: 3/);
  expect(screen.queryByLabelText('Фактически принято: Цемент')).not.toBeInTheDocument();
  expect(screen.getByLabelText('Фактически принято: Песок')).toHaveValue(null);
  expect(screen.getByText(/Ожидает приёмки: 5/)).toBeInTheDocument();
});
test('outdated resolver cannot replace new document review',async()=>{
  let finish;fetch.mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve;})).mockResolvedValueOnce(response({status:'no_match'}));
  const view=render(<UnifiedReceiptReview API="/api" scan={scan}/>);
  view.rerender(<UnifiedReceiptReview API="/api" scan={{...scan,parsed:{...scan.parsed,number:'new'}}}/>);
  await screen.findByText('Оформить отдельный документ');finish(response(match));
  await waitFor(()=>expect(screen.queryByLabelText('Фактически принято: Цемент')).not.toBeInTheDocument());
});
test('project original upload carries exact authorized projectId and company filter',async()=>{
  fetch.mockResolvedValueOnce(response({url:'/original'})).mockResolvedValueOnce(response({ok:true,data:scan.parsed})).mockResolvedValueOnce(response(match));
  const {container}=render(<Scanner companyId={7} projects={[{id:22,name:'Объект',companyId:8},{id:11,name:'Объект',companyId:7}]}/>);
  pick(container);await screen.findByLabelText('Фактически принято: Цемент');
  const body=fetch.mock.calls[0][1].body;
  expect(body.get('projectId')).toBe('11');expect(body.get('projectName')).toBe('Объект');
});
test.each([
  [], [{id:11,name:'Объект',companyId:8}], [{name:'Объект'}], [{id:0,name:'Объект'}],
  [{id:11,name:'Объект',companyId:7},{id:12,name:'Объект',companyId:7}],
].map(projects => [projects]))('missing, invalid or ambiguous authorized project blocks upload (%j)',async(projects)=>{
  const {container}=render(<Scanner companyId={7} projects={projects}/>);pick(container);
  expect(await screen.findByText(/Не удалось однозначно определить объект/)).toBeInTheDocument();expect(fetch).not.toHaveBeenCalled();
});
test('main warehouse original does not carry projectId',async()=>{
  fetch.mockResolvedValueOnce(response({url:'/original'})).mockResolvedValueOnce(response({ok:true,data:scan.parsed})).mockResolvedValueOnce(response(match));
  const {container}=render(<Scanner/>);
  fireEvent.change(screen.getByRole('combobox'),{target:{value:'Основной склад'}});pick(container);
  await screen.findByLabelText('Фактически принято: Цемент');
  expect(fetch.mock.calls[0][1].body.get('projectId')).toBeNull();
});
test('company scope change discards late uploaded result before recognition',async()=>{
  let finish;const callback=jest.fn();fetch.mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve;}));
  const view=render(<Scanner companyId={7} onDocumentScanned={callback}/>);pick(view.container);
  await waitFor(()=>expect(finish).toBeDefined());view.rerender(<Scanner companyId={8} onDocumentScanned={callback}/>);
  finish(response({url:'/old-company-original'}));await waitFor(()=>expect(callback).not.toHaveBeenCalled());
  expect(fetch).toHaveBeenCalledTimes(1);
});

test('existing receipt can reset to upload a different document without posting', async()=>{
  const draft=jest.fn();
  fetch.mockResolvedValueOnce(response({url:'/original'})).mockResolvedValueOnce(response({ok:true,data:scan.parsed})).mockResolvedValueOnce(response({status:'existing_receipt',receipts:[{id:91,number:'12',date:'2026-10-18',lines:[]}]}));
  const {container}=render(<Scanner onDraft={draft}/>);pick(container);
  await screen.findByText(/Документ уже оприходован/);
  fireEvent.click(screen.getByText('Другой документ (сбросить черновик)'));
  expect(await screen.findByLabelText('Оригиналы документа')).toBeInTheDocument();
  expect(screen.queryByText(/Документ уже оприходован/)).not.toBeInTheDocument();
  expect(draft).toHaveBeenLastCalledWith(expect.objectContaining({location:'Объект',originalUrls:[],items:[]}));
  expect(fetch).toHaveBeenCalledTimes(3);
});

const candidate = {id:21,companyId:7,sourceSupplierInvoiceId:81,sourceInvoice:{id:81,invoiceNumber:'INV-8',invoiceDate:'2026-10-01'},waybillNumber:'12',waybillDate:'2026-10-18',project:'Объект',documentParties:{supplier:{fullName:'Поставщик',inn:'123'},buyer:{fullName:'Покупатель',inn:'456'}},lines:match.matchedBatch.lines};
const paymentScan = {...scan,companyId:7,parsed:{...scan.parsed,documentType:'payment_invoice',number:'INV-8',date:'2026-10-01'}};
const chooseCandidate = async (label = 'Проверить выбранную отгрузку') => {
  fireEvent.click((await screen.findAllByRole('radio'))[0]);
  fireEvent.click(screen.getByLabelText('Подтверждаю выбранную отгрузку и связь с загруженным документом.'));
  fireEvent.click(screen.getByText(label));
};

test('ambiguous choice requires separate selection confirmation and rechecks before posting',async()=>{
  fetch.mockResolvedValueOnce(response({status:'ambiguous',candidateBatches:[candidate,{...candidate,id:22}]}))
    .mockResolvedValueOnce(response(match)).mockResolvedValueOnce(response({status:'accepted'}));
  render(<UnifiedReceiptReview API="/api" scan={{...scan,companyId:7}}/>);
  const options=await screen.findAllByRole('radio');
  const button=screen.getByText('Проверить выбранную отгрузку');
  expect(options.every(option=>!option.checked)).toBe(true);expect(button).toBeDisabled();
  expect(screen.queryByText('Подтвердить фактическую приёмку')).not.toBeInTheDocument();
  fireEvent.click(options[0]);expect(button).toBeDisabled();
  fireEvent.click(screen.getByRole('checkbox'));fireEvent.click(options[1]);expect(button).toBeDisabled();
  fireEvent.click(screen.getByRole('checkbox'));fireEvent.click(button);
  fireEvent.change(await screen.findByLabelText('Фактически принято: Цемент'),{target:{value:'9'}});
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual(expect.objectContaining({selectedBatchId:22,explicitSelectionConfirmed:true,sourceSupplierInvoiceId:81,companyId:7}));
  fireEvent.click(screen.getByRole('checkbox'));fireEvent.click(screen.getByText('Подтвердить фактическую приёмку'));
  await screen.findByText(/Приёмка подтверждена/);
  expect(JSON.parse(fetch.mock.calls[2][1].body)).toEqual(expect.objectContaining({selectedBatchId:22,explicitSelectionConfirmed:true,sourceSupplierInvoiceId:81,physicalReceiptConfirmed:true}));
});

test('server rejection of chosen batch blocks posting without standalone fallback',async()=>{
  fetch.mockResolvedValueOnce(response({status:'ambiguous',candidateBatches:[candidate]}))
    .mockResolvedValueOnce({ok:false,json:async()=>({detail:'Нет доступа к выбранной отгрузке'})});
  render(<UnifiedReceiptReview API="/api" scan={scan}/>);await chooseCandidate();
  expect(await screen.findByRole('alert')).toHaveTextContent('Нет доступа к выбранной отгрузке');
  expect(screen.queryByText('Подтвердить фактическую приёмку')).not.toBeInTheDocument();
  expect(screen.queryByText('Оформить отдельный документ')).not.toBeInTheDocument();expect(fetch).toHaveBeenCalledTimes(2);
});

test('foreign company candidates are not exposed and cannot be chosen',async()=>{
  fetch.mockResolvedValue(response({status:'ambiguous',candidateBatches:[{...candidate,companyId:8}]}));
  render(<UnifiedReceiptReview API="/api" scan={{...scan,companyId:7}}/>);
  await screen.findByRole('alert');expect(screen.queryByRole('radio')).not.toBeInTheDocument();
  expect(screen.queryByText('Проверить выбранную отгрузку')).not.toBeInTheDocument();
});

test.each(['no_match','match','review','source_selection'])('payment invoice %s cannot post stock or open standalone receipt',async(status)=>{
  fetch.mockResolvedValue(response({...match,status}));
  render(<UnifiedReceiptReview API="/api" scan={paymentScan}/>);
  await screen.findByRole('alert');
  expect(screen.getByLabelText('Тип документа')).toBeDisabled();
  expect(screen.queryByText('Подтвердить фактическую приёмку')).not.toBeInTheDocument();
  expect(screen.queryByText('Оформить отдельный документ')).not.toBeInTheDocument();
  const payload=JSON.parse(fetch.mock.calls[0][1].body);
  expect(payload.document).toEqual(expect.objectContaining({documentType:'payment_invoice',invoiceNumber:'INV-8',invoiceDate:'2026-10-01'}));
  expect(payload.document).not.toHaveProperty('waybillNumber');expect(payload.document).not.toHaveProperty('waybillDate');
});

test('invoice selection requires new waybill upload and keeps only actual waybill originals in resolve and confirm',async()=>{
  const draft=jest.fn();
  fetch.mockResolvedValueOnce(response({url:'/invoice-original'})).mockResolvedValueOnce(response({ok:true,data:paymentScan.parsed}))
    .mockResolvedValueOnce(response({status:'source_selection',requiresWaybill:true,candidateBatches:[candidate]}))
    .mockResolvedValueOnce(response({url:'/waybill-original'})).mockResolvedValueOnce(response({ok:true,data:scan.parsed}))
    .mockResolvedValueOnce(response(match)).mockResolvedValueOnce(response({status:'accepted'}));
  const view=render(<Scanner onDraft={draft}/>);pick(view.container);
  await chooseCandidate('Загрузить фактическую накладную');
  await screen.findByLabelText('Оригиналы документа');
  expect(screen.getByText(/Выбрана отгрузка #21 по счёту #81/)).toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(3);
  expect(draft).toHaveBeenLastCalledWith(expect.objectContaining({sourceSupplierInvoiceId:81,selectedBatchId:21,explicitSelectionConfirmed:true,originalUrls:[],sourceInvoiceOriginalUrls:['/invoice-original'],items:[]}));
  expect(draft.mock.calls.at(-1)[0]).not.toHaveProperty('number');
  expect(draft.mock.calls.at(-1)[0]).not.toHaveProperty('date');
  pick(view.container);fireEvent.change(await screen.findByLabelText('Фактически принято: Цемент'),{target:{value:'8'}});
  const resolved=JSON.parse(fetch.mock.calls[5][1].body);
  expect(resolved).toEqual(expect.objectContaining({sourceSupplierInvoiceId:81,selectedBatchId:21,explicitSelectionConfirmed:true,originalUrls:['/waybill-original'],companyId:7,projectId:11}));
  expect(resolved.document).toEqual(expect.objectContaining({documentType:'waybill',waybillNumber:'12',waybillDate:'2026-10-18'}));
  fireEvent.click(screen.getByRole('checkbox'));fireEvent.click(screen.getByText('Подтвердить фактическую приёмку'));
  await screen.findByText(/Приёмка подтверждена/);
  expect(JSON.parse(fetch.mock.calls[6][1].body)).toEqual(expect.objectContaining({...resolved,physicalReceiptConfirmed:true}));
});

test('resetting selected invoice clears its original and source context',async()=>{
  const draft=jest.fn();fetch.mockResolvedValueOnce(response({url:'/invoice-original'})).mockResolvedValueOnce(response({ok:true,data:paymentScan.parsed}))
    .mockResolvedValueOnce(response({status:'source_selection',requiresWaybill:true,candidateBatches:[candidate]}));
  const view=render(<Scanner onDraft={draft}/>);pick(view.container);await chooseCandidate('Загрузить фактическую накладную');
  fireEvent.click(await screen.findByText('Другой документ (сбросить черновик)'));
  const reset=draft.mock.calls.at(-1)[0];
  expect(reset).toEqual(expect.objectContaining({originalUrls:[],items:[]}));
  for (const key of ['selectedBatchId','sourceSupplierInvoiceId','sourceInvoiceOriginalUrls','requiresWaybill']) expect(reset).not.toHaveProperty(key);
  expect(fetch).toHaveBeenCalledTimes(3);
});

test('company change clears selected invoice source and originals',async()=>{
  const draft=jest.fn();fetch.mockResolvedValueOnce(response({url:'/invoice-original'})).mockResolvedValueOnce(response({ok:true,data:paymentScan.parsed}))
    .mockResolvedValueOnce(response({status:'source_selection',requiresWaybill:true,candidateBatches:[candidate]}));
  const view=render(<Scanner onDraft={draft} companyId={7}/>);pick(view.container);await chooseCandidate('Загрузить фактическую накладную');
  await screen.findByText(/Выбрана отгрузка #21/);
  view.rerender(<Scanner onDraft={draft} companyId={8}/>);
  await waitFor(()=>expect(screen.queryByText(/Выбрана отгрузка #21/)).not.toBeInTheDocument());
  expect(draft.mock.calls.at(-1)[0]).not.toHaveProperty('sourceSupplierInvoiceId');
});

test('missing OCR identity stays blank instead of assuming waybill number and date',async()=>{
  const draft=jest.fn();fetch.mockResolvedValueOnce(response({url:'/original'})).mockResolvedValueOnce(response({ok:true,data:{...scan.parsed,number:'',date:''}}))
    .mockResolvedValueOnce(response({status:'review'}));
  const view=render(<Scanner onDraft={draft}/>);pick(view.container);await screen.findByRole('alert');
  expect(screen.getByLabelText('Номер документа')).toHaveValue('');expect(screen.getByLabelText('Дата документа')).toHaveValue('');
  expect(draft).toHaveBeenLastCalledWith(expect.objectContaining({number:'',date:''}));
});

test('source-scoped no match cannot escape into standalone receipt',async()=>{
  fetch.mockResolvedValue(response({status:'no_match'}));
  render(<UnifiedReceiptReview API="/api" scan={{...scan,sourceSupplierInvoiceId:81,selectedBatchId:21,explicitSelectionConfirmed:true}}/>);
  await screen.findByRole('alert');expect(screen.queryByText('Оформить отдельный документ')).not.toBeInTheDocument();
});

test('company-wide scan displays actual shipment destination before confirmation',async()=>{
  fetch.mockResolvedValue(response({...match,matchedBatch:{...match.matchedBatch,project:'Школа'}}));
  render(<UnifiedReceiptReview API="/api" scan={{...scan,location:'Основной склад'}}/>);
  expect(await screen.findByText('Место приёмки: Школа')).toBeInTheDocument();
  expect(screen.getByRole('alert')).toHaveTextContent('Приход будет оформлен на склад этого объекта');
  expect(screen.queryByText('Место приёмки: Основной склад')).not.toBeInTheDocument();
});

test('mismatched returned shipment project blocks confirmation',async()=>{
  fetch.mockResolvedValue(response({...match,matchedBatch:{...match.matchedBatch,project:'Другой объект'}}));
  render(<UnifiedReceiptReview API="/api" scan={scan}/>);
  fireEvent.change(await screen.findByLabelText('Фактически принято: Цемент'),{target:{value:'10'}});
  fireEvent.click(screen.getByRole('checkbox'));
  expect(screen.getByRole('alert')).toHaveTextContent('Выбран другой объект, приёмка заблокирована');
  expect(screen.getByText('Подтвердить фактическую приёмку')).toBeDisabled();expect(fetch).toHaveBeenCalledTimes(1);
});

test('editing an ambiguous selected document clears its prior selection on fresh verification',async()=>{
  fetch.mockResolvedValueOnce(response({status:'ambiguous',candidateBatches:[candidate]}))
    .mockResolvedValueOnce(response(match)).mockResolvedValueOnce(response({status:'review'}));
  render(<UnifiedReceiptReview API="/api" scan={scan}/>);await chooseCandidate();
  await screen.findByLabelText('Фактически принято: Цемент');
  fireEvent.change(screen.getByLabelText('Номер документа'),{target:{value:'13'}});
  fireEvent.click(screen.getByText('Повторить проверку'));await screen.findByRole('alert');
  const payload=JSON.parse(fetch.mock.calls[2][1].body);
  expect(payload.document.waybillNumber).toBe('13');
  expect(payload).not.toHaveProperty('selectedBatchId');expect(payload).not.toHaveProperty('explicitSelectionConfirmed');
});

test('late selected-batch verification cannot replace another uploaded document',async()=>{
  let finish;fetch.mockResolvedValueOnce(response({status:'ambiguous',candidateBatches:[candidate]}))
    .mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve;})).mockResolvedValueOnce(response({status:'review'}));
  const view=render(<UnifiedReceiptReview API="/api" scan={scan}/>);await chooseCandidate();
  await waitFor(()=>expect(finish).toBeDefined());
  view.rerender(<UnifiedReceiptReview API="/api" scan={{...scan,originalUrls:['/different-original']}}/>);
  await screen.findByRole('alert');finish(response(match));
  await waitFor(()=>expect(screen.queryByLabelText('Фактически принято: Цемент')).not.toBeInTheDocument());
  expect(JSON.parse(fetch.mock.calls[2][1].body)).not.toHaveProperty('selectedBatchId');
});

test('source selected actual-waybill original requires same exact project ID',async()=>{
  fetch.mockResolvedValueOnce(response({url:'/invoice-original'})).mockResolvedValueOnce(response({ok:true,data:paymentScan.parsed}))
    .mockResolvedValueOnce(response({status:'source_selection',requiresWaybill:true,candidateBatches:[candidate]}));
  const view=render(<Scanner/>);pick(view.container);await chooseCandidate('Загрузить фактическую накладную');
  await screen.findByLabelText('Оригиналы документа');
  view.rerender(<Scanner projects={[{id:12,name:'Объект',companyId:7}]}/>);pick(view.container);
  expect(await screen.findByRole('alert')).toHaveTextContent('Объект выбранной отгрузки изменился');expect(fetch).toHaveBeenCalledTimes(3);
});

test('closing and reopening scan retains manual review changes',async()=>{
  fetch.mockResolvedValueOnce(response({url:'/original'})).mockResolvedValueOnce(response({ok:true,data:scan.parsed})).mockResolvedValueOnce(response(match));
  const view=render(<Scanner/>);pick(view.container);await screen.findByLabelText('Фактически принято: Цемент');
  fireEvent.change(screen.getByLabelText('Номер документа'),{target:{value:'MANUAL-KEPT'}});
  fireEvent.click(screen.getByText('Закрыть'));view.rerender(<Scanner showScanInvoice={false}/>);view.rerender(<Scanner showScanInvoice/>);
  expect(screen.getByLabelText('Номер документа')).toHaveValue('MANUAL-KEPT');expect(fetch).toHaveBeenCalledTimes(3);
});

test('zero accepted receipt exposes every saved original without another posting action', async()=>{
  fetch.mockResolvedValue(response({...match,matchedBatch:{...match.matchedBatch,lines:[{...match.matchedBatch.lines[0],receivedQuantity:0,receivedAt:'now',status:'Проблема',receiptOriginalUrls:['/tenant-files/3/content','/tenant-files/4/content']}]}}));
  render(<UnifiedReceiptReview API="/api" scan={scan}/>);
  await screen.findByText('Оригинал принятой поставки 1');
  expect(screen.getByText('Оригинал принятой поставки 2')).toBeInTheDocument();
  expect(screen.queryByText('Подтвердить фактическую приёмку')).not.toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(1);
});
