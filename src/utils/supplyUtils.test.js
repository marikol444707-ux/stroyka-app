import {
  splitSupplierOffersByStatus,
  supplierRecipientLinkAction,
  supplierRecipientStatusSummary,
} from './supplyUtils';

describe('splitSupplierOffersByStatus', () => {
  it('keeps working KP offers separate from withdrawn and rejected history', () => {
    const result = splitSupplierOffersByStatus([
      { id: 1, status: 'Ожидает ответа' },
      { id: 2, status: 'Отозвано' },
      { id: 3, status: 'Получено' },
      { id: 4, status: 'Отклонено' },
      { id: 5, status: 'Утверждено' },
    ]);

    expect(result.active.map(offer => offer.id)).toEqual([1, 3, 5]);
    expect(result.history.map(offer => offer.id)).toEqual([2, 4]);
  });

  it('treats an empty or unknown status as a visible working offer', () => {
    const result = splitSupplierOffersByStatus([
      { id: 1, status: '' },
      { id: 2 },
    ]);

    expect(result.active.map(offer => offer.id)).toEqual([1, 2]);
    expect(result.history).toEqual([]);
  });
});

describe('supplierRecipient diagnostics helpers', () => {
  it('builds a supplier-link action only for invisible recipients', () => {
    expect(supplierRecipientLinkAction({
      visibleToSupplier: false,
      targetSupplierId: 17,
      targetSupplierName: 'АО «САТУРН ЮГ»',
      targetSupplierEmail: 'saturn@example.test',
      problemReason: 'Карточка не связана',
    })).toEqual({
      type: 'link_supplier_user',
      supplierId: 17,
      supplierName: 'АО «САТУРН ЮГ»',
      email: 'saturn@example.test',
      reason: 'Карточка не связана',
    });

    expect(supplierRecipientLinkAction({
      visibleToSupplier: true,
      targetSupplierId: 17,
    })).toBeNull();
  });

  it('summarizes KP statuses for recipient diagnostics', () => {
    expect(supplierRecipientStatusSummary([
      { status: 'Отозвано' },
      { status: 'Ожидает ответа' },
      { status: 'Отозвано' },
    ])).toBe('Отозвано: 2 · Ожидает ответа: 1');
  });
});
