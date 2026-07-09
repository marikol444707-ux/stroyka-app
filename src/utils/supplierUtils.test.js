import {
  groupSuppliers,
  supplierMatchesRecord,
  supplierSourceInfo,
  warehouseInvoiceDocumentKey,
} from './supplierUtils';

describe('groupSuppliers', () => {
  it('keeps request and recommendation flags when linked supplier cards are merged', () => {
    const [group] = groupSuppliers([
      {
        id: 17,
        name: 'АО «САТУРН ЮГ»',
        inn: '2635000000',
        alreadyRequested: false,
        aiRecommend: false,
        deliveriesCount: 1,
      },
      {
        id: 25,
        name: 'ООО Сатурн',
        inn: '2635000000',
        alreadyRequested: true,
        aiRecommend: true,
        deliveriesCount: 4,
      },
    ]);

    expect(group._supplierIds).toEqual([17, 25]);
    expect(group.alreadyRequested).toBe(true);
    expect(group.aiRecommend).toBe(true);
    expect(group.deliveriesCount).toBe(4);
  });

  it('matches documents to any supplier id in a duplicate group', () => {
    const [group] = groupSuppliers([
      { id: 17, name: 'АО «САТУРН ЮГ»', inn: '2635000000' },
      { id: 25, name: 'САТУРН ЮГ из накладной', inn: '2635000000' },
    ]);

    expect(supplierMatchesRecord(group, { supplierId: 25 })).toBe(true);
    expect(supplierMatchesRecord(group, { supplierName: 'АО Сатурн Юг' })).toBe(true);
    expect(supplierMatchesRecord(group, { supplierId: 99, supplierName: 'Другой поставщик' })).toBe(false);
  });

  it('summarizes supplier source using linked account and warehouse evidence', () => {
    const [group] = groupSuppliers([
      { id: 17, name: 'АО «САТУРН ЮГ»', inn: '2635000000', sourceType: 'manual', sourceDetail: 'добавил директор' },
      { id: 25, name: 'САТУРН ЮГ', inn: '2635000000', user_id: 44, source_type: 'linked_account' },
    ]);

    const info = supplierSourceInfo(group, { warehouseInvoices: [{ id: 3 }] });

    expect(info.primary).toBe('warehouse_invoice');
    expect(info.types).toEqual(expect.arrayContaining(['manual', 'linked_account', 'warehouse_invoice']));
    expect(info.filterTypes).toEqual(expect.arrayContaining(['warehouse_invoice', 'linked_account']));
  });
});

describe('warehouseInvoiceDocumentKey', () => {
  const baseInvoice = {
    number: '323/3091032',
    date: '2026-05-18',
    project: 'Кисловодск Лицей 4',
    totalWithVat: 148111.33,
    items: [
      { name: 'Кабель ВВГнг-LS 3х2.5', unit: 'м', quantity: 100, price: 1481.1133 },
    ],
  };

  it('deduplicates the same warehouse invoice when OCR reads supplier names differently', () => {
    const first = warehouseInvoiceDocumentKey({
      ...baseInvoice,
      supplierName: 'ООО "АЛЬЯНСПРОМСТРОЙ"',
    });
    const second = warehouseInvoiceDocumentKey({
      ...baseInvoice,
      supplierName: 'АО ТД Электромонтаж',
    });

    expect(second).toBe(first);
  });

  it('keeps invoices separate when the amount and items differ', () => {
    const first = warehouseInvoiceDocumentKey(baseInvoice);
    const second = warehouseInvoiceDocumentKey({
      ...baseInvoice,
      totalWithVat: 200000,
      items: [{ name: 'Труба ПВХ', unit: 'шт', quantity: 10, price: 20000 }],
    });

    expect(second).not.toBe(first);
  });
});
