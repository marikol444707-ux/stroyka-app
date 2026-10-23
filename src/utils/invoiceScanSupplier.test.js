import {resolveInvoiceScanSupplier} from './invoiceScanSupplier';

test('selects a supplier card already matched by recognition', () => {
  expect(resolveInvoiceScanSupplier('ООО «Поставщик»', {supplierId: 42})).toEqual({
    supplierId: 42,
    isNewSupplier: false,
  });
});

test('treats a recognized supplier name without a matched card as new', () => {
  expect(resolveInvoiceScanSupplier('ООО «Новый поставщик»', {supplierId: 0})).toEqual({
    supplierId: '',
    isNewSupplier: true,
  });
});

test('ignores invalid recognition ids and blank names', () => {
  expect(resolveInvoiceScanSupplier('', {supplierId: 'not-an-id', supplierName: ''})).toEqual({
    supplierId: '',
    isNewSupplier: false,
  });
});
