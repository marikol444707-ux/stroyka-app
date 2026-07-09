import {
  splitSupplierOffersByStatus,
  supplyRequestEstimateGroupLabel,
  supplyRequestListGroup,
  supplyRequestSourceBucket,
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

describe('supply request source grouping', () => {
  it('groups material-control requests by estimate package', () => {
    const request = {
      project: 'Тестовый объект',
      workPackage: 'Электрика',
      notes: [
        'Создано из контроля материалов: строка `Докупить`.',
        'MATERIAL_CONTROL_REQUEST:1|2|3',
        'Объект: Тестовый объект',
        'Пакет работ: Электрика',
      ].join('\n'),
    };

    expect(supplyRequestSourceBucket(request)).toBe('estimate');
    expect(supplyRequestEstimateGroupLabel(request)).toBe('Электрика');
    expect(supplyRequestListGroup(request)).toMatchObject({
      project: 'Тестовый объект',
      label: 'Электрика',
      bucket: 'estimate',
    });
  });

  it('groups estimate-norm batch requests by their work package', () => {
    const request = {
      project: 'Тестовый объект',
      workPackage: 'Общестрой',
      notes: [
        'Пакетная заявка из черновика сметы по нормам.',
        'NORM_ESTIMATE_REQUEST:42:Общестрой',
        'Раздел сметы: Общестрой',
      ].join('\n'),
    };

    expect(supplyRequestSourceBucket(request)).toBe('estimate');
    expect(supplyRequestEstimateGroupLabel(request)).toBe('Общестрой');
  });

  it('keeps plain user-created requests in the manual group', () => {
    const request = {
      project: 'Тестовый объект',
      materialName: 'Саморезы',
      notes: 'Купить на завтра',
    };

    expect(supplyRequestSourceBucket(request)).toBe('manual');
    expect(supplyRequestListGroup(request)).toMatchObject({
      label: 'Вручную',
      bucket: 'manual',
    });
  });

  it('moves estimate-control problems into the review group', () => {
    const request = {
      project: 'Тестовый объект',
      itemsJson: JSON.stringify([
        {
          materialName: 'Кабель',
          quantity: 10,
          unit: 'м',
          workPackage: 'Электрика',
          estimateControl: { status: 'over_estimate_need' },
        },
      ]),
    };

    expect(supplyRequestSourceBucket(request)).toBe('review');
    expect(supplyRequestListGroup(request)).toMatchObject({
      label: 'Требуют проверки',
      bucket: 'review',
    });
  });
});
