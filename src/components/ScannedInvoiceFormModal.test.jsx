import React, {useState} from 'react';
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

test('wrong OCR quantity blocks receipt and template learning until the draft is corrected', () => {
  const saveInvoiceNew=jest.fn();
  global.fetch=jest.fn();
  function Harness() {
    const [newInvoice,setNewInvoice]=useState({number:'SYNTHETIC',date:'2026-10-22',supplier:'Synthetic supplier',
      sourceType:'scan_main_invoice',location:'Основной склад',vat:'С НДС 22%',totalWithVat:2400,
      scanValidation:{valid:true},items:[{name:'Synthetic plaster',article:'SYN-1',quantity:'796',price:'400',lineTotal:'2400',unit:'шт'}]});
    return <ScannedInvoiceFormModal showScannedInvoiceForm setShowScannedInvoiceForm={jest.fn()} newInvoice={newInvoice}
      setNewInvoice={setNewInvoice} projects={[]} units={['шт']} C={{}} card={{}} inp={{}} btnO={{}} btnG={{}} btnR={{}}
      saveInvoiceNew={saveInvoiceNew} user={{role:'кладовщик'}} />;
  }
  render(<Harness />);
  expect(screen.getByRole('alert')).toHaveTextContent('Строка 1');
  expect(screen.getByRole('button',{name:'Сохранить'})).toBeDisabled();
  expect(screen.getByRole('button',{name:/Запомнить исправления/})).toBeDisabled();
  expect(screen.getByText('Артикул: SYN-1')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Сохранить'}));
  expect(saveInvoiceNew).not.toHaveBeenCalled();
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.change(screen.getByPlaceholderText('Кол.'),{target:{value:'6'}});
  expect(screen.getByPlaceholderText('Сумма строки')).toHaveValue(2400);
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(screen.getByRole('button',{name:'Сохранить'})).toBeEnabled();
  expect(screen.getByRole('button',{name:/Запомнить исправления/})).toBeEnabled();
  fireEvent.change(screen.getByPlaceholderText('Цена с НДС'),{target:{value:'500'}});
  expect(screen.getByPlaceholderText('Сумма строки')).toHaveValue(3000);
  expect(screen.getByRole('alert')).toHaveTextContent('Сумма строк не совпадает');
  expect(screen.getByRole('button',{name:'Сохранить'})).toBeDisabled();
});

test('a user can correct a wrong OCR document total without changing rows or retaining stale tax totals', () => {
  const saveInvoiceNew = jest.fn();
  let latestDraft;
  const items = [{name:'Synthetic goods',quantity:'2',price:'122',lineTotal:'244',unit:'шт'}];
  function Harness() {
    const [newInvoice,setNewInvoice] = useState({number:'SYNTHETIC',sourceType:'scan_main_invoice',
      location:'Основной склад',supplier:'Synthetic supplier',vat:'С НДС 22%',
      totalWithVat:999,totalBase:800,totalVat:199,items});
    latestDraft = newInvoice;
    return <ScannedInvoiceFormModal showScannedInvoiceForm setShowScannedInvoiceForm={jest.fn()}
      newInvoice={newInvoice} setNewInvoice={setNewInvoice} projects={[]} units={['шт']}
      C={{}} card={{}} inp={{}} btnO={{}} btnG={{}} btnR={{}} saveInvoiceNew={saveInvoiceNew}
      user={{role:'кладовщик'}} />;
  }
  render(<Harness />);
  const totalInput = screen.getByRole('spinbutton',{name:'Итог по оригиналу, с НДС'});
  const save = screen.getByRole('button',{name:'Сохранить'});
  expect(save).toBeDisabled();
  for (const value of ['', '-1', '0', '1e20', '200']) {
    fireEvent.change(totalInput,{target:{value}});
    expect(save).toBeDisabled();
    expect(latestDraft.items).toBe(items);
  }
  fireEvent.change(totalInput,{target:{value:'244'}});
  expect(save).toBeEnabled();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(latestDraft).toMatchObject({totalWithVat:'244',totalBase:0,totalVat:0,scanHasManualCorrections:true,scanOriginalTotalWithVat:999});
  expect(latestDraft.items).toBe(items);
  expect(screen.getByText('Распознанный итог до исправления: 999')).toBeInTheDocument();
  fireEvent.click(save);
  expect(saveInvoiceNew).toHaveBeenCalledTimes(1);
});
