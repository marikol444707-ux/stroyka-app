import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import ScannedInvoiceFormModal from './ScannedInvoiceFormModal';

test('editing the OCR supplier name clears a stale matched supplier id', () => {
  const setNewInvoice = jest.fn();
  const newInvoice = {
    number: '14555',
    date: '2026-08-13',
    supplierId: 77,
    supplier: 'ООО Старое',
    newSupplierName: 'ООО Старое',
    isNewSupplier: false,
    location: 'Кисловодск Лицей 4',
    project: 'Кисловодск Лицей 4',
    sourceType: 'scan_project_invoice',
    scanRecognition: {supplierId: 77, supplierName: 'ООО Старое'},
    vat: 'Без НДС',
    items: [{name: 'Штукатурка', quantity: '10', unit: 'шт', price: '100'}],
  };

  render(
    <ScannedInvoiceFormModal
      user={{role: 'прораб'}}
      showScannedInvoiceForm
      setShowScannedInvoiceForm={jest.fn()}
      C={{text: '#fff', textSec: '#aaa', border: '#333', bg: '#111'}}
      card={{}}
      inp={{}}
      btnO={{}}
      btnG={{}}
      btnR={{}}
      newInvoice={newInvoice}
      setNewInvoice={setNewInvoice}
      projects={[]}
      getProjectWorkPackageOptions={() => []}
      getProjectEstimateWorkOptions={() => []}
      units={['шт']}
      saveInvoiceNew={jest.fn()}
    />,
  );

  fireEvent.change(screen.getByPlaceholderText('Поставщик'), {
    target: {value: 'ООО Новое'},
  });

  expect(setNewInvoice).toHaveBeenCalledWith(expect.objectContaining({
    supplierId: '',
    supplier: 'ООО Новое',
    newSupplierName: 'ООО Новое',
    isNewSupplier: true,
    scanHasManualCorrections: true,
    scanRecognition: expect.objectContaining({
      supplierId: 0,
      supplierName: 'ООО Новое',
    }),
  }));
});

const formProps = {user:{id:1,role:'прораб',companyId:7},showScannedInvoiceForm:true,setShowScannedInvoiceForm:jest.fn(),C:{},card:{},inp:{},btnO:{},btnG:{},btnR:{},projects:[],units:['шт'],saveInvoiceNew:jest.fn()};
const scanDraft = {receiptDraftId:'one',sourceType:'scan_project_invoice',location:'Объект',supplier:'Первый',number:'1',items:[{name:'Материал',quantity:'2',price:'10',lineTotal:'20'}]};

test('learning a template cannot overwrite edits made while request was pending',async()=>{
  let finish;
  global.fetch=jest.fn(()=>new Promise(resolve=>{finish=resolve;}));
  jest.spyOn(window,'alert').mockImplementation(()=>{});
  function Form() {const [draft,setDraft]=React.useState(scanDraft);return <><output data-testid="draft">{JSON.stringify(draft)}</output><ScannedInvoiceFormModal {...formProps} newInvoice={draft} setNewInvoice={setDraft}/></>;}
  render(<Form/>);
  fireEvent.click(screen.getByText(/Запомнить/));
  fireEvent.change(screen.getByPlaceholderText('Номер документа *'),{target:{value:'MANUAL'}});
  fireEvent.change(screen.getByPlaceholderText('Поставщик'),{target:{value:'Новый'}});
  await require('@testing-library/react').act(async()=>{finish({ok:true,json:async()=>({ok:true,template:{supplierId:11,supplierName:'Первый'},recognition:{supplierId:11}})});});
  const draft=JSON.parse(screen.getByTestId('draft').textContent);
  expect(draft).toEqual(expect.objectContaining({number:'MANUAL',supplier:'Новый',supplierId:'',scanHasManualCorrections:true}));
  jest.restoreAllMocks();
});

test('quantity edit recalculates line amount and requires reviewing the document total',async()=>{
  const save=jest.fn().mockResolvedValue(true);
  jest.spyOn(window,'alert').mockImplementation(()=>{});
  function Form() {const [draft,setDraft]=React.useState({...scanDraft,totalWithVat:20,totalBase:20,totalVat:0,vat:'Без НДС',date:'2026-11-10',originalUrls:['/original'],physicalReceiptConfirmed:true});return <ScannedInvoiceFormModal {...formProps} newInvoice={draft} setNewInvoice={setDraft} saveInvoiceNew={save}/>;}
  render(<Form/>);
  fireEvent.change(screen.getByPlaceholderText('Кол.'),{target:{value:'3'}});
  expect(screen.getByPlaceholderText('Сумма строки').value).toBe('30');
  await require('@testing-library/react').act(async()=>fireEvent.click(screen.getByText('Сохранить')));
  expect(save).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText('Итого по оригиналу, с НДС'),{target:{value:'30'}});
  await require('@testing-library/react').act(async()=>fireEvent.click(screen.getByText('Сохранить')));
  expect(save).toHaveBeenCalledTimes(1);
  jest.restoreAllMocks();
});

test.each(['close-reopen','company','draft'])('late template answer is ignored after %s',async change=>{
  let finish;global.fetch=jest.fn(()=>new Promise(resolve=>{finish=resolve;}));
  jest.spyOn(window,'alert').mockImplementation(()=>{});
  const update=jest.fn();
  const view=render(<ScannedInvoiceFormModal {...formProps} companyId={7} newInvoice={scanDraft} setNewInvoice={update}/>);
  fireEvent.click(screen.getByText(/Запомнить/));
  if(change==='close-reopen') view.rerender(<ScannedInvoiceFormModal {...formProps} showScannedInvoiceForm={false} companyId={7} newInvoice={scanDraft} setNewInvoice={update}/>);
  view.rerender(<ScannedInvoiceFormModal {...formProps} companyId={change==='company'?8:7} newInvoice={change==='draft'?{...scanDraft,receiptDraftId:'two'}:scanDraft} setNewInvoice={update}/>);
  await require('@testing-library/react').act(async()=>finish({ok:true,json:async()=>({ok:true,recognition:{supplierId:11}})}));
  expect(update).not.toHaveBeenCalled();expect(window.alert).not.toHaveBeenCalled();
  jest.restoreAllMocks();
});

test('double click learns once and an API refusal retains the reviewed draft',async()=>{
  let finish;global.fetch=jest.fn(()=>new Promise(resolve=>{finish=resolve;}));
  jest.spyOn(window,'alert').mockImplementation(()=>{});
  const update=jest.fn();
  render(<ScannedInvoiceFormModal {...formProps} newInvoice={scanDraft} setNewInvoice={update}/>);
  const button=screen.getByText(/Запомнить/);fireEvent.click(button);fireEvent.click(button);
  expect(fetch).toHaveBeenCalledTimes(1);
  await require('@testing-library/react').act(async()=>finish({ok:false,json:async()=>({detail:'Поставщик недоступен в выбранной компании'})}));
  expect(update).not.toHaveBeenCalled();expect(window.alert).toHaveBeenCalledWith('Поставщик недоступен в выбранной компании');
  jest.restoreAllMocks();
});
