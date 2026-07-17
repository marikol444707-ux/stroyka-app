import {
  buildAllProjectsMaterialProjectionReview,
  buildLegacyMaterialProjection,
  buildMaterialProjectionDryRun,
  buildSupplyRequestProjectionReview,
} from './materialProjectionDryRunUtils';

const row = (name, planQty, overrides = {}) => ({
  name,
  materialKey: name.toLowerCase(),
  unit: 'шт',
  workPackage: 'Электрика',
  planQty,
  ...overrides,
});

describe('buildMaterialProjectionDryRun', () => {
  test('reconstructs unsafe legacy family aggregation from corrected source rows', () => {
    const correctedRows = [
      row('Дюбель распорный 8х60', 100, {
        planDetails: [{estimateId: 10, packageName: 'Электрика', sectionName: 'Крепёж', materialName: 'Дюбель распорный 8х60', qty: 100, unit: 'шт'}],
      }),
      row('Шуруп самонарезающий 3,5х35', 200, {
        planDetails: [{estimateId: 10, packageName: 'Электрика', sectionName: 'Крепёж', materialName: 'Шуруп самонарезающий 3,5х35', qty: 200, unit: 'шт'}],
      }),
    ];

    const legacyRows = buildLegacyMaterialProjection(correctedRows);

    expect(legacyRows).toHaveLength(1);
    expect(legacyRows[0]).toMatchObject({planQty: 300, unit: 'шт', workPackage: 'Электрика'});
    expect(legacyRows[0].planDetails).toHaveLength(2);
  });

  test('compares quantities without mutating either projection', () => {
    const legacyRows = [row('Кабель ВВГ 3х1,5', 100)];
    const correctedRows = [row('Кабель ВВГ 3х1,5', 80)];
    const legacySnapshot = JSON.stringify(legacyRows);
    const correctedSnapshot = JSON.stringify(correctedRows);

    const report = buildMaterialProjectionDryRun([{
      projectId: 7,
      projectName: 'Лицей',
      legacyRows,
      correctedRows,
    }]);

    expect(report).toMatchObject({
      ok: true,
      dryRun: true,
      writesAttempted: 0,
      summary: {
        projects: 1,
        legacyRows: 1,
        correctedRows: 1,
        unchanged: 0,
        quantityChanged: 1,
        legacyOnly: 0,
        correctedOnly: 0,
        splitRows: 0,
      },
    });
    expect(report.projects[0].changes[0]).toMatchObject({
      status: 'quantity_changed',
      legacyQty: 100,
      correctedQty: 80,
      deltaQty: -20,
    });
    expect(JSON.stringify(legacyRows)).toBe(legacySnapshot);
    expect(JSON.stringify(correctedRows)).toBe(correctedSnapshot);
  });

  test('reports rows that exist on only one side', () => {
    const report = buildMaterialProjectionDryRun([{
      projectName: 'Школа',
      legacyRows: [row('Старый материал', 5)],
      correctedRows: [row('Новый материал', 7)],
    }]);

    expect(report.summary).toMatchObject({legacyOnly: 1, correctedOnly: 1});
    expect(report.projects[0].changes.map(change => change.status)).toEqual([
      'corrected_only',
      'legacy_only',
    ]);
    expect(report.projects[0].changes).toEqual([
      expect.objectContaining({status: 'corrected_only', correctedQty: 7}),
      expect.objectContaining({status: 'legacy_only', legacyQty: 5}),
    ]);
  });

  test('detects when one legacy aggregate splits into corrected material identities', () => {
    const sourceA = {estimateId: 10, packageName: 'Электрика', sectionName: 'Кабели', materialName: 'Кабель ВВГ 3х1,5'};
    const sourceB = {estimateId: 10, packageName: 'Электрика', sectionName: 'Кабели', materialName: 'Кабель ВВГ 3х2,5'};
    const report = buildMaterialProjectionDryRun([{
      projectName: 'Больница',
      legacyRows: [row('Кабель ВВГ', 300, {planDetails: [sourceA, sourceB]})],
      correctedRows: [
        row('Кабель ВВГ 3х1,5', 100, {planDetails: [sourceA]}),
        row('Кабель ВВГ 3х2,5', 200, {planDetails: [sourceB]}),
      ],
    }]);

    expect(report.summary).toMatchObject({
      splitRows: 1,
      legacyOnly: 0,
      correctedOnly: 0,
    });
    expect(report.projects[0].changes).toEqual([
      expect.objectContaining({
        status: 'split',
        legacyName: 'Кабель ВВГ',
        correctedNames: ['Кабель ВВГ 3х1,5', 'Кабель ВВГ 3х2,5'],
      }),
    ]);
  });

  test('reviews active requests created from a split legacy aggregate without changing requests', () => {
    const sourceA = {estimateId: 10, packageName: 'Электрика', sectionName: 'Крепёж', materialName: 'Дюбель распорный 8х60', qty: 100, unit: 'шт'};
    const sourceB = {estimateId: 10, packageName: 'Электрика', sectionName: 'Крепёж', materialName: 'Шуруп самонарезающий 3,5х35', qty: 200, unit: 'шт'};
    const correctedRows = [
      row('Дюбель распорный 8х60', 100, {planDetails: [sourceA]}),
      row('Шуруп самонарезающий 3,5х35', 200, {planDetails: [sourceB]}),
      row('Кабель ВВГ 3х1,5', 80, {unit: 'м'}),
    ];
    const requests = [
      {id: 21, project: 'Лицей', status: 'Новая', materialName: 'Дюбель распорный 8х60', quantity: 300, unit: 'шт', workPackage: 'Электрика', notes: 'Создано из контроля материалов: строка `Докупить`.'},
      {id: 22, project: 'Лицей', status: 'Утверждена', materialName: 'Кабель ВВГ 3х1,5', quantity: 20, unit: 'м', workPackage: 'Электрика'},
      {id: 23, project: 'Лицей', status: 'Новая', materialName: 'Неизвестный материал', quantity: 5, unit: 'шт', workPackage: 'Электрика'},
      {id: 24, project: 'Лицей', status: 'Доставлено', materialName: 'Старый закрытый материал', quantity: 1, unit: 'шт'},
    ];
    const snapshot = JSON.stringify(requests);

    const review = buildSupplyRequestProjectionReview({
      projectName: 'Лицей',
      requests,
      correctedRows,
      parseSupplyItems: request => [{
        materialName: request.materialName,
        quantity: request.quantity,
        unit: request.unit,
        workPackage: request.workPackage,
      }],
    });

    expect(review).toMatchObject({
      ok: true,
      dryRun: true,
      writesAttempted: 0,
      summary: {
        activeRequests: 3,
        items: 3,
        ready: 1,
        needsReview: 2,
        legacyAggregate: 1,
        unmatched: 1,
      },
    });
    expect(review.needsReview).toEqual([
      expect.objectContaining({requestId: 21, reason: 'legacy_aggregate_split'}),
      expect.objectContaining({requestId: 23, reason: 'material_not_in_projection'}),
    ]);
    expect(JSON.stringify(requests)).toBe(snapshot);
  });

  test('summarizes every active project and sorts projects needing review first', () => {
    const sourceA = {estimateId: 10, packageName: 'Электрика', sectionName: 'Крепёж', materialName: 'Дюбель распорный 8х60', qty: 100, unit: 'шт'};
    const sourceB = {estimateId: 10, packageName: 'Электрика', sectionName: 'Крепёж', materialName: 'Шуруп самонарезающий 3,5х35', qty: 200, unit: 'шт'};
    const inputs = [
      {
        projectId: 2,
        projectName: 'Школа',
        correctedRows: [
          row('Дюбель распорный 8х60', 100, {planDetails: [sourceA]}),
          row('Шуруп самонарезающий 3,5х35', 200, {planDetails: [sourceB]}),
        ],
        requests: [{id: 31, project: 'Школа', status: 'Новая', materialName: 'Дюбель распорный 8х60', quantity: 300, unit: 'шт', workPackage: 'Электрика', notes: 'Создано из контроля материалов'}],
      },
      {
        projectId: 1,
        projectName: 'Лицей',
        correctedRows: [row('Кабель ВВГ 3х1,5', 80, {unit: 'м'})],
        requests: [{id: 32, project: 'Лицей', status: 'Утверждена', materialName: 'Кабель ВВГ 3х1,5', quantity: 20, unit: 'м', workPackage: 'Электрика'}],
      },
      {projectId: 3, projectName: 'Пустой объект', correctedRows: [], requests: []},
    ];
    const snapshot = JSON.stringify(inputs);

    const report = buildAllProjectsMaterialProjectionReview(inputs, request => [{
      materialName: request.materialName,
      quantity: request.quantity,
      unit: request.unit,
      workPackage: request.workPackage,
    }]);

    expect(report).toMatchObject({
      ok: true,
      dryRun: true,
      writesAttempted: 0,
      summary: {
        projects: 3,
        projectsNeedingReview: 1,
        activeRequests: 2,
        requestItems: 2,
        requestItemsReady: 1,
        requestItemsNeedingReview: 1,
        splitRows: 1,
      },
    });
    expect(report.projects.map(project => project.projectName)).toEqual(['Школа', 'Лицей', 'Пустой объект']);
    expect(report.projects[0]).toMatchObject({
      projectId: 2,
      projectionChanges: 1,
      requestItemsNeedingReview: 1,
      needsReview: true,
    });
    expect(report.projects[2]).toMatchObject({projectionChanges: 0, requestItemsNeedingReview: 0, needsReview: false});
    expect(JSON.stringify(inputs)).toBe(snapshot);
  });
});
