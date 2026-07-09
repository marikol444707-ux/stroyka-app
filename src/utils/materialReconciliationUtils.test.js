import { buildMaterialReconciliationRows } from './materialReconciliationUtils';

const materialItem = (name, quantity, unit = 'шт') => ({
  itemType: 'material',
  name,
  quantity,
  unit,
  priceMaterial: 1,
});

const buildRows = (items, canonicalMaterialMeta = (_projectName, name, unit) => ({
  name,
  unit,
  alias: null,
}), options = {}) => buildMaterialReconciliationRows({
  projectName: 'Тестовый объект',
  projects: [{ id: 1, name: 'Тестовый объект' }],
  invoices: options.invoices || [],
  activeEstimatesForProject: (_project, kind) => kind === 'Заказчик' ? [{
    id: 10,
    name: 'Активная смета',
    status: 'Активная',
    smetaType: 'Заказчик',
    workPackage: 'Общестрой',
    sections: [{ name: 'Раздел 1', items }],
  }] : [],
  canonicalMaterialMeta,
  warehouseInvoiceItems: invoice => ({ items: invoice.items || [] }),
  isSupplyDeliveryInvoice: () => false,
  estimateWorkNormRequirementRows: () => [],
  parseSupplyItems: () => [],
});

describe('buildMaterialReconciliationRows material identity', () => {
  test('keeps different fasteners as separate procurement rows', () => {
    const rows = buildRows([
      materialItem('Дюбель распорный полипропиленовый 8х60 мм', 100),
      materialItem('Шуруп самонарезающий TN 3,5х35 мм', 200),
    ]);

    expect(rows).toHaveLength(2);
    expect(rows.map(row => row.name)).toEqual(expect.arrayContaining([
      'Дюбель распорный полипропиленовый 8х60 мм',
      'Шуруп самонарезающий TN 3,5х35 мм',
    ]));
  });

  test.each([
    [
      'profiles',
      'Профиль направляющий ПН 50х40 мм',
      'Профиль маячковый 10 мм',
      'м',
    ],
    [
      'cables',
      'Кабель ВВГнг-LS 3х1,5 мм2',
      'Кабель ВВГнг-LS 3х2,5 мм2',
      'м',
    ],
  ])('keeps different %s as separate procurement rows', (_family, first, second, unit) => {
    const rows = buildRows([
      materialItem(first, 100, unit),
      materialItem(second, 200, unit),
    ]);

    expect(rows).toHaveLength(2);
    expect(rows.map(row => row.name)).toEqual(expect.arrayContaining([first, second]));
  });

  test('sums exact repeated material rows inside one package', () => {
    const rows = buildRows([
      materialItem('Смесь штукатурная Ротбанд', 120, 'кг'),
      materialItem('Смесь штукатурная Ротбанд', 80, 'кг'),
    ]);

    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      name: 'Смесь штукатурная Ротбанд',
      planQty: 200,
      planSourceCount: 2,
    });
  });

  test('merges different source names only through a confirmed alias', () => {
    const canonicalMaterialMeta = (_projectName, name, unit) => name === 'Гипрок влагостойкий 12,5 мм'
      ? { name: 'Лист гипсокартонный влагостойкий 12,5 мм', unit, alias: { id: 7 } }
      : { name, unit, alias: null };
    const rows = buildRows([
      materialItem('Лист гипсокартонный влагостойкий 12,5 мм', 10),
      materialItem('Гипрок влагостойкий 12,5 мм', 5),
    ], canonicalMaterialMeta);

    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      name: 'Лист гипсокартонный влагостойкий 12,5 мм',
      planQty: 15,
      planSourceCount: 2,
    });
    expect(rows[0].aliasIds).toContain(7);
  });

  test('links an unassigned warehouse invoice to one exact estimate material', () => {
    const rows = buildRows([
      materialItem('Смесь штукатурная Ротбанд', 10, 'кг'),
    ], undefined, {
      invoices: [{
        id: 20,
        project: 'Тестовый объект',
        number: 'ТЕСТ-20',
        items: [materialItem('Смесь штукатурная Ротбанд', 4, 'кг')],
      }],
    });

    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      planQty: 10,
      received: 4,
      toBuy: 6,
    });
  });
});
