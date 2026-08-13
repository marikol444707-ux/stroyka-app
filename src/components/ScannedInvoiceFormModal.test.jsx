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
