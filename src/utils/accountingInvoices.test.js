import {
  buildAccountingInvoiceRows,
  buildInternalWarehouseReceiptNumber,
  isWarehouseInvoiceAccountingRequired,
} from './accountingInvoices';

describe('warehouse invoice accounting policy', () => {
  test('supplierless main warehouse receipt is not an accounting document', () => {
    const invoice = {
      id: 37,
      location: 'Основной склад',
      warehouseTarget: 'main',
      supplierId: null,
      supplierName: '',
      supplierInvoiceId: null,
      selectedAction: 'receive_stock_without_supplier',
      totalWithVat: 15000,
    };

    expect(isWarehouseInvoiceAccountingRequired(invoice)).toBe(false);
    expect(buildAccountingInvoiceRows([invoice])).toEqual([]);
  });

  test('explicit inventory-only action remains non-accounting even with stale supplier text', () => {
    expect(isWarehouseInvoiceAccountingRequired({
      warehouseTarget: 'main',
      selectedAction: 'receive_stock_without_supplier',
      supplierName: 'Старое ошибочное значение',
    })).toBe(false);
  });

  test('legacy supplierless main warehouse receipt is also excluded', () => {
    const invoice = {
      id: 37,
      location: 'Основной склад',
      warehouseTarget: 'main',
      supplierName: '',
      totalWithVat: 15000,
    };

    expect(isWarehouseInvoiceAccountingRequired(invoice)).toBe(false);
  });

  test('main warehouse invoice with supplier remains in accounting', () => {
    const invoice = {
      id: 38,
      location: 'Основной склад',
      warehouseTarget: 'main',
      supplierId: 10,
      supplierName: 'ООО Поставка',
      totalWithVat: 15000,
    };

    expect(isWarehouseInvoiceAccountingRequired(invoice)).toBe(true);
    expect(buildAccountingInvoiceRows([invoice])).toHaveLength(1);
  });

  test('object invoice keeps existing accounting behavior', () => {
    const invoice = {
      id: 39,
      location: 'Объект 1',
      project: 'Объект 1',
      warehouseTarget: 'object',
      supplierName: '',
      totalWithVat: 15000,
    };

    expect(isWarehouseInvoiceAccountingRequired(invoice)).toBe(true);
  });

  test('inventory receipt gets an internal traceable number', () => {
    expect(buildInternalWarehouseReceiptNumber(new Date(2026, 6, 15, 10, 11, 12, 13)))
      .toBe('ПРИХОД-20260715-101112013');
  });
});

test('partial receipt remains visible without creating a second payable debt', () => {
  const rows = buildAccountingInvoiceRows([
    { id: 91, settlementInvoiceId: 12, supplierId: 3, project: 'Объект', totalWithVat: 100, paidAmount: 0 },
    { id: 92, settlementInvoiceId: 12, supplierId: 3, project: 'Объект', totalWithVat: 100, paidAmount: 0 },
  ]);
  expect(rows).toHaveLength(2);
  expect(rows.map(row => row.status)).toEqual(['Расчёты по счёту', 'Расчёты по счёту']);
  expect(rows.reduce((sum, row) => sum + row.debt, 0)).toBe(0);
  expect(rows.reduce((sum, row) => sum + row.amount, 0)).toBe(200);
});
