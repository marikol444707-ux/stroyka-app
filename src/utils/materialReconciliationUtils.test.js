import { buildEstimateMaterialPlanRows, buildMaterialControlSummary, buildMaterialReconciliationRows } from './materialReconciliationUtils';

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
  project: { companyId: 1, projectId: 1, projectName: 'Тестовый объект' },
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
  isSupplyDeliveryInvoice: invoice => Boolean(invoice.supplyDeliveryId || invoice.sourceType === 'supply_delivery'),
  estimateWorkNormRequirementRows: options.estimateWorkNormRequirementRows || (() => []),
  supplyDeliveries: options.supplyDeliveries || [],
  supplyHistory: options.supplyHistory || [],
  materials: options.materials || [],
  supplyRequests: options.supplyRequests || [],
  materialTransfers: options.materialTransfers || [],
  workJournal: options.workJournal || [],
  history: options.history || [],
  parseSupplyItems: options.parseSupplyItems || (() => []),
});

describe('accepted supply material cost', () => {
  const delivery = changes => ({
    id: 81, companyId: 1, requestId: 61, project: 'Тестовый объект',
    materialName: 'Кабель', unit: 'м', workPackage: 'Общестрой', status: 'Проблема',
    plannedQuantity: 20, shippedQuantity: 10, receivedQuantity: 4,
    pricePerUnit: 100, totalPrice: 1000, ...changes,
  });
  const historical = changes => ({
    id: 91, project: 'Тестовый объект', materialName: 'Кабель', unit: 'м',
    workPackage: 'Общестрой', status: 'Принято', quantity: 10,
    pricePerUnit: 100, totalPrice: 1000, ...changes,
  });
  const receipt = changes => ({
    id: 101, companyId: 1, supplyDeliveryId: 81, sourceType: 'supply_delivery', sourceId: 81,
    project: 'Тестовый объект', status: 'Принята', totalWithVat: 360,
    items: [{name: 'Кабель', unit: 'м', quantity: 4, price: 100, total: 360, workPackage: 'Общестрой', deliveryId: 81}],
    ...changes,
  });
  const stock = {name: 'Кабель', unit: 'м', project: 'Тестовый объект', workPackage: 'Общестрой', quantity: 10, price: 100};
  const reconcile = options => buildRows([materialItem('Кабель', 20, 'м')], undefined, options)[0];

  test.each([[4, 400], [0, 0], [10, 1000], ['4', 400]])('costs only actual accepted quantity %s', (receivedQuantity, total) => {
    const row = reconcile({supplyDeliveries: [delivery({receivedQuantity})]});
    expect(row).toMatchObject({received: Number(receivedQuantity), receivedSum: total});
    expect(row.supplyDetails).toHaveLength(1);
    expect(row.supplyDetails[0].total).toBe(total);
    expect(buildMaterialControlSummary([row]).suppliedSum).toBe(total);
  });

  test.each([undefined, null, '', ' ', 'bad', -1, Infinity, false])('never guesses missing/invalid actual quantity %s', receivedQuantity => {
    const row = reconcile({supplyDeliveries: [delivery({receivedQuantity})]});
    expect(row).toMatchObject({received: 0, receivedSum: 0, supplyDetails: []});
  });

  test.each([undefined, null, ''])('keeps actual historical evidence when legacy delivery quantity is missing (%s)', receivedQuantity => {
    const row = reconcile({
      supplyDeliveries: [delivery({receivedQuantity})],
      supplyHistory: [historical({quantity: 3, totalPrice: 270})],
    });
    expect(row).toMatchObject({received: 3, receivedSum: 270});
  });

  test('explicit zero blocks stale history and stock cost fallback', () => {
    const row = reconcile({supplyDeliveries: [delivery({receivedQuantity: 0})], supplyHistory: [historical()], materials: [stock]});
    expect(row).toMatchObject({received: 0, receivedSum: 0, stock: 10});
    expect(row.supplyDetails).toHaveLength(1);
  });

  test('uses one saved linked receipt amount without counting invoice/history twice', () => {
    const row = reconcile({supplyDeliveries: [delivery()], invoices: [receipt()], supplyHistory: [historical()], materials: [stock]});
    expect(row).toMatchObject({received: 4, supplyReceived: 4, invoiceReceived: 0, receivedSum: 360, invoiceDetails: []});
    expect(row.supplyDetails).toHaveLength(1);
  });

  test('keeps saved VAT-inclusive gross amount and does not add tax again', () => {
    const grossReceipt = receipt({totalBase: 333.33, totalVat: 66.67, totalWithVat: 400});
    grossReceipt.items[0].total = 400;
    const row = reconcile({supplyDeliveries: [delivery()], invoices: [grossReceipt]});
    expect(row.receivedSum).toBe(400);
  });

  test('preserves a saved zero amount instead of restoring its unit-price or stock value', () => {
    const freeReceipt = receipt();
    freeReceipt.items[0].total = 0;
    const row = reconcile({supplyDeliveries: [delivery()], invoices: [freeReceipt], materials: [stock]});
    expect(row).toMatchObject({received: 4, receivedSum: 0});
  });

  test('explicit zero accepted quantity wins even over conflicting linked receipt', () => {
    const row = reconcile({supplyDeliveries: [delivery({receivedQuantity: 0})], invoices: [receipt()], supplyHistory: [historical()], materials: [stock]});
    expect(row).toMatchObject({received: 0, receivedSum: 0});
  });

  test('accepts the exact legacy source link without supplyDeliveryId', () => {
    const row = reconcile({supplyDeliveries: [delivery()], invoices: [receipt({supplyDeliveryId: null})]});
    expect(row.receivedSum).toBe(360);
  });

  test.each([
    ['cancelled', value => ({...value, status: 'Аннулирована'})],
    ['other delivery', value => ({...value, supplyDeliveryId: 82, sourceId: 82})],
    ['conflicting delivery links', value => ({...value, sourceId: 82})],
    ['other project', value => ({...value, project: 'Другой объект'})],
    ['other company', value => ({...value, companyId: 2})],
    ['wrong quantity', value => ({...value, items: [{...value.items[0], quantity: 10}]})],
    ['wrong material', value => ({...value, items: [{...value.items[0], name: 'Другая марка кабеля'}]})],
    ['wrong unit', value => ({...value, items: [{...value.items[0], unit: 'шт'}]})],
    ['wrong package', value => ({...value, items: [{...value.items[0], workPackage: 'Отделка'}]})],
    ['wrong item link', value => ({...value, items: [{...value.items[0], deliveryId: 82}]})],
    ['missing saved items', value => ({...value, items: []})],
    ['missing amount', value => ({...value, items: [{...value.items[0], total: null}]})],
  ])('rejects %s receipt as amount evidence', (_label, alter) => {
    const row = reconcile({supplyDeliveries: [delivery()], invoices: [alter(receipt())]});
    expect(row).toMatchObject({received: 4, receivedSum: 400});
  });

  test('never chooses between two linked receipts', () => {
    const row = reconcile({supplyDeliveries: [delivery()], invoices: [receipt(), receipt({id: 102})]});
    expect(row.receivedSum).toBe(400);
  });

  test('keeps partial and full batches of one material instead of using shipped amounts', () => {
    const row = reconcile({supplyDeliveries: [delivery(), delivery({id: 82, receivedQuantity: 2, pricePerUnit: 200})], supplyHistory: [historical()]});
    expect(row).toMatchObject({received: 6, receivedSum: 800});
    expect(row.supplyDetails).toHaveLength(2);
  });

  test('unit normalization changes quantity but never the cost basis', () => {
    const row = reconcile({supplyDeliveries: [delivery({unit: '100 м', receivedQuantity: 0.4, pricePerUnit: 10000, totalPrice: 100000})]});
    expect(row).toMatchObject({received: 40, receivedSum: 4000});
  });

  test.each([
    [1.2345, 12.34, 15.23], [1.5, 0.01, 0.01], [2.5, 0.05, 0.12],
    [3, 0.125, 0.38], [1, 2.675, 2.67], [1, 1.005, 1],
  ])('matches receipt writer rounding for %s × %s', (receivedQuantity, pricePerUnit, expected) => {
    const row = reconcile({supplyDeliveries: [delivery({receivedQuantity, pricePerUnit})]});
    expect(row.receivedSum).toBe(expected);
  });

  test('does not substitute shipped total for a missing unit price', () => {
    expect(reconcile({supplyDeliveries: [delivery({pricePerUnit: undefined})]}).receivedSum).toBe(0);
  });

  test('unreceived shipments contribute no accepted amount', () => {
    const row = reconcile({supplyDeliveries: [delivery({status: 'В пути'})]});
    expect(row).toMatchObject({received: 0, receivedSum: 0});
  });

  test('legacy history zero quantity or zero amount never revives stock cost', () => {
    for (const changes of [{quantity: 0}, {totalPrice: 0}]) {
      const row = reconcile({supplyHistory: [historical(changes)], materials: [stock]});
      expect(row.receivedSum).toBe(0);
    }
  });

  test('retains stock-only legacy fallback when no receipt evidence exists', () => {
    expect(reconcile({materials: [stock]}).receivedSum).toBe(1000);
  });
});

describe('material reconciliation holder identity', () => {
  const transfer = (id, quantity, name = 'Иван Петров') => ({
    id, projectName: 'Тестовый объект', toUserId: id, toPerson: name,
    materialName: 'Кабель', unit: 'м', quantity, signed: true,
  });
  const usage = (id, name = 'Иван Петров') => ({
    project: 'Тестовый объект', master_id: id, master_name: name,
    materialsUsed: [{name: 'Кабель', unit: 'м', quantity: 2}],
  });
  const returned = (id, name = 'Иван Петров') => ({
    project: 'Тестовый объект', type: 'возврат от мастера', material: 'Кабель', unit: 'м',
    quantity: 3, issued_by: name,
    ...(id ? {source_type: 'material_return_user', source_id: id} : {}),
  });

  test('distinct accounts with the same name retain their own balances', () => {
    const [row] = buildRows([], undefined, {
      materialTransfers: [transfer(41, 10), transfer(42, 20)],
      workJournal: [usage(42)], history: [returned(41)],
    });
    expect(row.holders).toHaveLength(2);
    expect(row.holders.find(holder => holder.userId === 41)).toMatchObject({issued: 10, used: 0, returned: 3, balance: 7});
    expect(row.holders.find(holder => holder.userId === 42)).toMatchObject({issued: 20, used: 2, returned: 0, balance: 18});
    expect(row).toMatchObject({issued: 30, used: 2, returnedFromMasters: 3, masterBalance: 25});
  });

  test('renamed account consumption and identified returns stay with its original issue', () => {
    const [row] = buildRows([], undefined, {
      materialTransfers: [transfer(41, 10, 'Прежняя фамилия')],
      workJournal: [usage(41, 'Новая фамилия')], history: [returned(41, 'Другое написание')],
    });
    expect(row.holders).toHaveLength(1);
    expect(row.holders[0]).toMatchObject({userId: 41, issued: 10, used: 2, returned: 3, balance: 5});
    expect(row).toMatchObject({issued: 10, used: 2, returnedFromMasters: 3, masterBalance: 5});
  });

  test('legacy names resolve to an identified holder only when unique', () => {
    const [row] = buildRows([], undefined, {
      materialTransfers: [transfer(41, 10)], workJournal: [usage(null)], history: [returned(null)],
    });
    expect(row.holders).toHaveLength(1);
    expect(row.holders[0]).toMatchObject({userId: 41, issued: 10, used: 2, returned: 3, balance: 5});
  });

  test('ambiguous name-only history stays separate without changing aggregate activity', () => {
    const [row] = buildRows([], undefined, {
      materialTransfers: [transfer(41, 10), transfer(42, 20)],
      workJournal: [usage(null)], history: [returned(null)],
    });
    expect(row.holders).toHaveLength(3);
    expect(row.holders.find(holder => holder.userId === 41)).toMatchObject({issued: 10, used: 0, returned: 0, balance: 10});
    expect(row.holders.find(holder => holder.userId === 42)).toMatchObject({issued: 20, used: 0, returned: 0, balance: 20});
    expect(row.holders.find(holder => !holder.userId)).toMatchObject({issued: 0, used: 2, returned: 3});
    expect(row).toMatchObject({issued: 30, used: 2, returnedFromMasters: 3});
  });
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

  test('subtracts a negative resource correction from the material plan', () => {
    const rows = buildRows([
      {
        ...materialItem('Доски необрезные хвойных пород 32-40 мм, III сорта', 41.4, 'м3'),
        isImported: true,
        sourceCode: '102-0053',
      },
      {
        itemType: 'adjustment',
        name: 'Доски необрезные хвойных пород 32-40 мм, III сорта',
        quantity: -41.4,
        unit: 'м3',
        isImported: true,
        sourceCode: '102-0053',
        lineTotal: -1000,
      },
    ]);

    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      planQty: 0,
      toBuy: 0,
    });
    expect(rows[0].planDetails).toEqual(expect.arrayContaining([
      expect.objectContaining({ sourceType: 'estimate_adjustment', normalizedQty: -41.4 }),
    ]));

    const planRows = buildEstimateMaterialPlanRows({
      project: { companyId: 1, projectId: 1, projectName: 'Тестовый объект' },
      activeEstimatesForProject: (_project, kind) => kind === 'Заказчик' ? [{
        id: 10,
        name: 'Активная смета',
        status: 'Активная',
        smetaType: 'Заказчик',
        workPackage: 'Общестрой',
        sections: [{ name: 'Раздел 1', items: [
          {
            ...materialItem('Доски необрезные хвойных пород 32-40 мм, III сорта', 41.4, 'м3'),
            isImported: true,
            sourceCode: '102-0053',
          },
          {
            itemType: 'adjustment',
            name: 'Доски необрезные хвойных пород 32-40 мм, III сорта',
            quantity: -41.4,
            unit: 'м3',
            isImported: true,
            sourceCode: '102-0053',
            lineTotal: -1000,
          },
        ] }],
      }] : [],
    });

    expect(planRows).toHaveLength(1);
    expect(planRows[0].planQty).toBe(0);
  });

  test('merges different source names only through a confirmed alias', () => {
    const canonicalMaterialMeta = (_projectName, name, unit) => name === 'Гипрок влагостойкий 12,5 мм'
      ? { name: 'Лист гипсокартонный влагостойкий 12,5 мм', unit, alias: { id: 7 } }
      : { name, unit, alias: null };
    const rows = buildRows([
      materialItem('Лист гипсокартонный влагостойкий 12,5 мм', 10, 'м2'),
      materialItem('Гипрок влагостойкий 12,5 мм', 5, 'м2'),
    ], canonicalMaterialMeta);

    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      name: 'Лист гипсокартонный влагостойкий 12,5 мм',
      planQty: 15,
      planSourceCount: 2,
    });
    expect(rows[0].aliasIds).toContain(7);
    expect(rows[0]).toMatchObject({
      identityStatus: 'confirmed_alias',
      procurementEligible: true,
      reviewRequired: false,
    });
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

  test('keeps a structured trace of estimate quantity conversion', () => {
    const [row] = buildRows([
      materialItem('Смесь сухая строительная', 1, '1000 кг'),
    ]);

    expect(row.planDetails[0]).toMatchObject({
      sourceType: 'estimate_material',
      includedInProcurement: true,
      sourceQty: 1,
      sourceUnit: '1000 кг',
      normalizedQty: 1000,
      normalizedUnit: 'кг',
      conversionApplied: true,
      estimateId: 10,
      sectionIndex: 0,
      itemIndex: 0,
    });
  });

  test('routes unit conflicts to review and blocks procurement', () => {
    const rows = buildRows([
      materialItem('Смесь штукатурная Ротбанд', 10, 'кг'),
    ], undefined, {
      invoices: [{
        id: 21,
        project: 'Тестовый объект',
        number: 'ТЕСТ-21',
        items: [materialItem('Смесь штукатурная Ротбанд', 4, 'шт')],
      }],
    });
    const summary = buildMaterialControlSummary(rows);

    expect(rows[0]).toMatchObject({
      unitMismatch: true,
      reviewRequired: true,
      procurementEligible: false,
      toBuy: 0,
    });
    expect(rows[0].reviewReasons).toContain('Конфликт единиц измерения');
    expect(summary.reviewRows).toEqual([rows[0]]);
  });

  test('keeps norm-only demand as a non-procurement hint', () => {
    const [row] = buildRows([], undefined, {
      estimateWorkNormRequirementRows: () => [{
        key: 'plaster_mix|штукатурная смесь|кг',
        name: 'Штукатурная смесь',
        unit: 'кг',
        planQty: 85,
        works: [],
        sections: ['Общестрой / Стены'],
        normSources: ['8.5 кг/м2'],
        packageNames: ['Общестрой'],
      }],
    });

    expect(row).toMatchObject({
      estimatePlanQty: 0,
      normPlanQty: 85,
      planningSource: 'norm_hint',
      procurementEligible: false,
      toBuy: 0,
    });
  });

  test('does not turn imported work rows into procurement materials', () => {
    const rows = buildRows([
      {
        isImported: true,
        itemType: 'material',
        name: 'Установка сплит-систем с внутренним блоком напольного типа',
        unit: 'компл.',
        quantity: 8,
        totalWork: 120000,
        totalMaterial: 0,
        lineTotal: 120000,
      },
      materialItem('Труба медная для кондиционера 1/4', 30, 'м'),
    ]);

    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      name: 'Труба медная для кондиционера 1/4',
      planningSource: 'estimate',
      procurementEligible: true,
    });
    expect(rows[0].planDetails).toEqual(expect.arrayContaining([
      expect.objectContaining({sourceType: 'estimate_material', includedInProcurement: true}),
    ]));
  });

  test('moves only ledger-allocated request balance to the exact target row', () => {
    const rows = buildRows([
      materialItem('Новая смесь', 20, 'кг'),
    ], undefined, {
      supplyRequests: [{
        id: 61,
        project: 'Тестовый объект',
        status: 'Новая',
        items: [{materialName: 'Старая смесь', quantity: 10, unit: 'кг', workPackage: 'Общестрой'}],
        supplyTransferAllocations: [{
          entryId: 8,
          requestItemIndex: 0,
          state: 'ready',
          quantity: '3',
          remainingQuantity: '7',
          targetEstimateId: 10,
          targetSectionIndex: 0,
          targetItemIndex: 0,
          targetMaterialName: 'Новая смесь',
          targetUnit: 'кг',
          targetWorkPackage: 'Общестрой',
        }],
      }],
      parseSupplyItems: request => request.items,
    });

    expect(rows.find(row => row.name === 'Старая смесь')).toMatchObject({
      requested: 7,
      reviewRequired: false,
    });
    expect(rows.find(row => row.name === 'Новая смесь')).toMatchObject({
      requested: 3,
      reviewRequired: false,
    });
  });

  test('keeps received history and only the ledger remainder on the original row', () => {
    const rows = buildRows([
      materialItem('Новая смесь', 20, 'кг'),
    ], undefined, {
      supplyRequests: [{
        id: 61,
        project: 'Тестовый объект',
        status: 'Новая',
        items: [{materialName: 'Старая смесь', quantity: 10, unit: 'кг', workPackage: 'Общестрой'}],
        supplyTransferAllocations: [{
          entryId: 8,
          requestItemIndex: 0,
          state: 'ready',
          quantity: '3',
          remainingQuantity: '5',
          targetEstimateId: 10,
          targetSectionIndex: 0,
          targetItemIndex: 0,
          targetMaterialName: 'Новая смесь',
          targetUnit: 'кг',
          targetWorkPackage: 'Общестрой',
        }],
      }],
      supplyDeliveries: [{
        id: 81,
        requestId: 61,
        project: 'Тестовый объект',
        workPackage: 'Общестрой',
        materialName: 'Старая смесь',
        unit: 'кг',
        status: 'Принято',
        receivedQuantity: 2,
      }],
      parseSupplyItems: request => request.items,
    });

    expect(rows.find(row => row.name === 'Старая смесь')).toMatchObject({
      received: 2,
      requested: 5,
      reviewRequired: false,
    });
    expect(rows.find(row => row.name === 'Новая смесь')).toMatchObject({
      requested: 3,
      reviewRequired: false,
    });
  });

  test('keeps full request on original identity when allocation cannot resolve exactly', () => {
    const rows = buildRows([
      materialItem('Новая смесь', 20, 'кг'),
    ], undefined, {
      supplyRequests: [{
        id: 61,
        project: 'Тестовый объект',
        status: 'Новая',
        items: [{materialName: 'Старая смесь', quantity: 10, unit: 'кг', workPackage: 'Общестрой'}],
        supplyTransferAllocations: [{
          entryId: 8,
          requestItemIndex: 0,
          state: 'needs_review',
          reasonCode: 'request_item_snapshot_drift',
          quantity: '3',
          targetEstimateId: 10,
          targetSectionIndex: 0,
          targetItemIndex: 0,
          targetMaterialName: 'Новая смесь',
          targetUnit: 'кг',
          targetWorkPackage: 'Общестрой',
        }],
      }],
      parseSupplyItems: request => request.items,
    });

    expect(rows.find(row => row.name === 'Старая смесь')).toMatchObject({
      requested: 10,
      reviewRequired: true,
      procurementEligible: false,
    });
    expect(rows.find(row => row.name === 'Новая смесь').requested).toBe(0);
  });
});
